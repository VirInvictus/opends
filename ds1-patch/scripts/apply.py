#!/usr/bin/env python3
r"""apply.py: the darkfix-ds1 applier.

Verifies the install against the patch manifest, backs up every
touched file to darkfix-backup/ next to it, applies each enabled
fix, and records the result in darkfix-applied.json. --unapply
restores the pre-patch state from those backups.

Usage:
    python3 apply.py /path/to/GOG/Dark\ Sun\ Shattered\ Lands
    python3 apply.py /path/to/install --unapply
    python3 apply.py /path/to/install --verify
    python3 apply.py /path/to/install --status
    python3 apply.py /path/to/install --check-all
    python3 apply.py --selftest

Stdlib-only. Python 3.11+ (tomllib). Distribution format and
applier contract: spec.md §4; per-fix script contract:
docs/patch-workflow.md §4.2.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import importlib.util
import io
import os
import shutil
import struct
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import tomllib

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from darkfix import patcher as P  # noqa: E402 (after the sys.path setup)


def _default_patch_root() -> Path:
    """Patch root for direct CLI runs, in either shipped shape.

    Repo layout: apply.py lives in <patch>/scripts/, so the root is
    the parent directory. Release zips flatten per spec.md section 4:
    apply.py sits beside manifest.toml, so the root is the script's
    own directory.
    """
    for candidate in (SCRIPTS_DIR.parent, SCRIPTS_DIR):
        if (candidate / "manifest.toml").is_file():
            return candidate
    # Neither shape found: keep the repo-layout default so the
    # manifest error is the one the player sees.
    return SCRIPTS_DIR.parent


DEFAULT_PATCH_ROOT = _default_patch_root()


@dataclass
class Layout:
    """Where the patch's pieces live for one invocation."""

    patch_root: Path

    @property
    def manifest_path(self) -> Path:
        return self.patch_root / "manifest.toml"

    @property
    def version(self) -> str:
        try:
            return (self.patch_root / "VERSION").read_text().strip()
        except OSError:
            raise P.PatchError(
                f"missing VERSION file next to the manifest:"
                f" {self.patch_root / 'VERSION'}"
            ) from None

    @property
    def repo_root(self) -> Path:
        return self.patch_root.parent


def load_fix_module(path: Path):
    """Import a per-fix script by file path."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"darkfix_fix_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise P.PatchError(f"cannot load fix script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_fix_contract(module, entry: dict, target_files: dict[str, str]) -> str:
    """Validate a fix module against its manifest entry.

    Returns the fix's target path relative to the install root.
    """
    fid = entry["id"]
    if getattr(module, "ID", None) != fid:
        raise P.ManifestError(
            f"{entry['path']}: module ID {getattr(module, 'ID', None)!r}"
            f" != manifest id {fid!r}"
        )
    target = getattr(module, "TARGET", None)
    if not isinstance(target, str) or not target:
        raise P.ManifestError(
            f"{fid}: TARGET must name a file relative to the install root"
        )
    source_hash = getattr(module, "SOURCE_SHA256", None)
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise P.ManifestError(f"{fid}: SOURCE_SHA256 must be a 64-hex-char sha256")
    manifest_hash = target_files.get(target)
    if manifest_hash is not None and manifest_hash != source_hash:
        raise P.ManifestError(
            f"{fid}: SOURCE_SHA256 disagrees with the manifest"
            f" [target.files] entry for {target}"
        )
    if not callable(getattr(module, "apply", None)):
        raise P.ManifestError(
            f"{fid}: fix script must define apply(source_path, dest_path)"
        )
    repairs = getattr(module, "REPAIRS", None)
    if repairs is not None:
        if not isinstance(repairs, list):
            raise P.ManifestError(f"{fid}: REPAIRS must be a list of dicts")
        for i, d in enumerate(repairs):
            P.GplRepair.from_dict(d, what=f"{fid} repair {i}")
    return target


def cmd_apply(layout: Layout, install: Path, *, check_all: bool = False) -> int:
    if not install.is_dir():
        raise P.PatchError(f"not a directory: {install}")
    manifest = P.load_manifest(layout.manifest_path)
    meta = manifest["meta"]
    name, version = meta["name"], layout.version
    target_files = manifest["target"]["files"]
    if check_all:
        _check_all(layout, install, manifest)

    enabled = [e for e in manifest["fixes"] if e.get("enabled", True)]
    disabled = [e for e in manifest["fixes"] if not e.get("enabled", True)]
    if not enabled:
        # Refusing (instead of "applying" zero fixes) avoids writing
        # an empty journal that --unapply could never consume.
        raise P.PatchError(
            "no enabled fixes: the manifest's fix list is empty or"
            " every fix is disabled; nothing to apply"
        )
    journal = P.read_journal(install)
    if journal is not None:
        if journal.get("status", "applied") == "pending":
            raise P.PatchError(
                f"an interrupted apply left a pending {P.JOURNAL_NAME} in"
                f" {install}; darkfix-backup/ holds the pristine copies of"
                f" the files it reached; run --unapply to restore them"
            )
        applied_ids = [f.get("id") for f in journal.get("fixes", [])]
        if applied_ids == [e["id"] for e in enabled]:
            print(
                f"{name} {version}: already applied"
                f" ({len(enabled)} fix(es)); nothing to do"
            )
            print("Revert with: apply.py --unapply")
            return 0
        raise P.AlreadyApplied(
            f"{install / P.JOURNAL_NAME} records {applied_ids}, which does"
            f" not match the manifest's enabled set"
            f" {[e['id'] for e in enabled]}; run --unapply first"
        )

    # Check phase: verify everything before touching anything.
    print(f"darkfix: {name} {version}")
    print(f"install: {install}")
    prepared = []
    records = []
    # spec 5 composition (2026-10-07 amendment): enabled fixes may
    # share a target file when their edit ranges are disjoint; the
    # write phase composes them into one write per file. Overlapping
    # ranges refuse here, before any write, with the offending
    # offsets named.
    ranges_by_target: dict[str, list[tuple[int, int, str]]] = {}
    for entry in enabled:
        module = load_fix_module(layout.patch_root / entry["path"])
        target_rel = check_fix_contract(module, entry, target_files)
        edits = [
            P.Edit.from_dict(d, what=f"{module.ID} edit {i}")
            for i, d in enumerate(getattr(module, "EDITS", []))
        ]
        for e in edits:
            e_start = e.offset
            e_end = e.offset + len(e.replace)
            for start, end, other in ranges_by_target.get(target_rel, []):
                if e_start < end and start < e_end:
                    raise P.ManifestError(
                        f"{module.ID} edit at {e_start:#x} overlaps"
                        f" {other} edit at {start:#x} in {target_rel}:"
                        f" fixes sharing a target must touch disjoint"
                        f" byte ranges; disable one of them in the"
                        f" manifest"
                    )
        ranges_by_target.setdefault(target_rel, []).extend(
            (e.offset, e.offset + len(e.replace), module.ID) for e in edits
        )
        target = install / target_rel
        if not target.is_file():
            raise P.PatchError(f"{module.ID}: target file not found: {target}")
        current = P.sha256_file(target)
        if current != module.SOURCE_SHA256:
            raise P.HashMismatch(
                f"{module.ID}: {target_rel} does not match the canonical"
                f" GOG 1.10 hash.\n  expected: {module.SOURCE_SHA256}\n"
                f"  actual:   {current}\n"
                f"  (already patched? wrong build? damaged install?)\n"
                f"  (an apply that was interrupted before it finished"
                f" leaves the originals in {P.BACKUP_DIR}/ inside the"
                f" game folder)"
            )
        repairs = [
            P.GplRepair.from_dict(d, what=f"{module.ID} repair {i}")
            for i, d in enumerate(getattr(module, "REPAIRS", []))
        ]
        source_bytes = target.read_bytes()
        prepared.append((module, target_rel, source_bytes, edits, repairs))
    for entry in disabled:
        print(f"  skipped {entry['id']} (disabled in manifest)")

    # Compose per target: each enabled fix contributes its
    # (disjoint, fingerprint-checked) edits to one merged result;
    # every fix's fingerprints are re-checked in sequence, so a
    # drifted expect still fails the whole apply before any write.
    # Chunk repairs (GplRepair) compose after the byte edits: the
    # repaired chunks are extracted from the edit-composed bytes, so
    # an absolute edit inside a repaired chunk is already in place
    # when the repair's fingerprints are checked, and the gff-edit
    # chunk replacement carries both. All extraction and chunk math
    # happens on a staging copy before the journal, so every refusal
    # above is pre-write and a crash mid-staging leaves the target
    # untouched with no journal at all.
    composed: dict[str, dict] = {}
    for module, target_rel, source_bytes, edits, repairs in prepared:
        entry_c = composed.setdefault(
            target_rel,
            {
                "source_hash": module.SOURCE_SHA256,
                "patched": source_bytes,
                "ids": [],
                "repairs": {},
            },
        )
        entry_c["patched"] = P.apply_edits(entry_c["patched"], edits, what=module.ID)
        for repair in repairs:
            key = (repair.kind, repair.chunk_id)
            entry_c["repairs"].setdefault(key, []).append(repair)
        entry_c["ids"].append(module.ID)

    # Chunk-repair staging, once per target: extract every repaired
    # chunk from the edit-composed bytes, apply all its repairs, and
    # rebuild the file through the gff-edit writer. Refusals here are
    # still pre-write (the target is untouched); a crash mid-staging
    # leaves stray staging files and no journal, which apply.py's
    # pending path and --unapply both treat as nothing-happened.
    # gff-cat resolves lazily: a pure-EDITS apply never needs it.
    gff_cat = None
    for target_rel, entry_c in composed.items():
        if not entry_c["repairs"]:
            continue
        if gff_cat is None:
            gff_cat = P._gff_cat(None)
        staged = install / (target_rel.replace("/", "_") + ".compose" + P.STAGED_SUFFIX)
        staged.write_bytes(entry_c["patched"])
        cursor = staged
        for n, ((kind, chunk_id), chunk_repairs) in enumerate(
            sorted(entry_c["repairs"].items())
        ):
            code = P._extract_chunk(cursor, kind, chunk_id, gff_cat)
            patched_chunk = P.compute_patched_chunk(
                code,
                chunk_repairs,
                what=f"{target_rel} {kind} {chunk_id}",
            )
            chunk_file = staged.with_suffix(f".chunk{n}")
            chunk_file.write_bytes(patched_chunk)
            nxt = staged.with_suffix(f".pass{n}")
            P.apply_gff_chunk(cursor, nxt, kind, chunk_id, chunk_file, gff_cat=gff_cat)
            chunk_file.unlink()
            if cursor is not staged:
                cursor.unlink()
            cursor = nxt
        entry_c["final_bytes"] = cursor.read_bytes()
        cursor.unlink()
        staged.unlink()

    records = []
    for module, target_rel, source_bytes, edits, repairs in prepared:
        entry_c = composed[target_rel]
        final_bytes = entry_c.get("final_bytes", entry_c["patched"])
        records.append(
            {
                "id": module.ID,
                "files": [
                    {
                        "path": target_rel,
                        "original_sha256": P.sha256_bytes(source_bytes),
                        "patched_sha256": P.sha256_bytes(final_bytes),
                    }
                ],
            }
        )
        n_sites = len(edits) + sum(len(r) for r in entry_c["repairs"].values())
        print(f"  checked {module.ID} ({target_rel}, {n_sites} site(s))")

    # Pending journal first: if the write phase dies between the
    # first write and the last, what is on disk says so, and
    # --unapply can recover from darkfix-backup/ instead of leaving
    # a half-apply nothing will talk about.
    journal = {
        "tool": name,
        "version": version,
        "applied_at": P.utc_now_iso(),
        "status": "pending",
        "fixes": records,
    }
    P.write_journal(install, journal)

    # Write phase: one backup and one atomic write per target file,
    # carrying every fix composed onto it.
    backed_up: set[str] = set()
    for target_rel, entry_c in composed.items():
        target = install / target_rel
        if P.sha256_file(target) != entry_c["source_hash"]:
            raise P.HashMismatch(f"{target_rel} changed during apply; aborting")
        if target_rel not in backed_up:
            P.backup_file(install, target_rel)
            backed_up.add(target_rel)
        tmp = target.with_name(target.name + P.STAGED_SUFFIX)
        tmp.write_bytes(entry_c.get("final_bytes", entry_c["patched"]))
        os.replace(tmp, target)
        print(f"  applied {', '.join(entry_c['ids'])} -> {target_rel}")

    journal["status"] = "applied"
    P.write_journal(install, journal)
    print(f"\nOK: {len(records)} fix(es) applied.")
    print(f"Journal: {install / P.JOURNAL_NAME}")
    print("Revert with: apply.py --unapply")
    return 0


def cmd_unapply(layout: Layout, install: Path) -> int:
    if not install.is_dir():
        raise P.PatchError(f"not a directory: {install}")
    manifest = P.load_manifest(layout.manifest_path)
    name = manifest["meta"]["name"]
    journal = P.read_journal(install)
    if journal is None:
        message = f"no {P.JOURNAL_NAME} in {install}; nothing to unapply"
        if P.backup_root(install).is_dir():
            message += (
                f"\n  {P.BACKUP_DIR}/ exists without a journal; if an"
                f" apply was interrupted before it wrote anything,"
                f" restore manually by copying those files back over"
                f" the game files"
            )
        raise P.NotApplied(message)
    pending = journal.get("status", "applied") == "pending"
    restored = P.restore_from_backup(install, journal, pending=pending)
    skipped = []
    if pending:
        journaled = [
            f["path"] for fix in journal["fixes"] for f in fix.get("files", [])
        ]
        skipped = [rel for rel in journaled if rel not in restored]
    (install / P.JOURNAL_NAME).unlink()
    if pending:
        print(f"{name} {layout.version}: recovered from an interrupted apply")
    else:
        print(f"{name} {layout.version}: unapplied")
    for rel in restored:
        print(f"  restored {rel}")
    for rel in skipped:
        print(
            f"  untouched {rel} (no backup: the interrupted apply never"
            f" reached this file)"
        )
    print("\nOK: install restored to its pre-patch state.")
    return 0


def cmd_verify(layout: Layout, install: Path) -> int:
    """Check a patched install still matches its journal.

    Hash check on every journaled file, plus a byte check at every
    EDITS site (catches partial reverts the file hash would hide
    only if the file drifted back to a different patch state; the
    hash is the primary gate, the site check is the explanation).
    """
    if not install.is_dir():
        raise P.PatchError(f"not a directory: {install}")
    manifest = P.load_manifest(layout.manifest_path)
    journal = P.read_journal(install)
    if journal is None:
        raise P.NotApplied(f"no {P.JOURNAL_NAME} in {install}; nothing to verify")
    modules: dict[str, object] = {}
    for entry in manifest["fixes"]:
        try:
            modules[entry["id"]] = load_fix_module(layout.patch_root / entry["path"])
        except P.PatchError:
            pass  # verify works from the journal alone if scripts moved
    failures: list[str] = []
    for fix in journal.get("fixes", []):
        fid = fix.get("id", "?")
        for f in fix.get("files", []):
            rel = f["path"]
            target = install / rel
            if not target.is_file():
                failures.append(f"{fid}: {rel} is missing")
                continue
            current = P.sha256_file(target)
            if current != f.get("patched_sha256"):
                failures.append(
                    f"{fid}: {rel} hash drifted from the journaled patched hash"
                )
            module = modules.get(fid)
            if module is not None and getattr(module, "TARGET", None) == rel:
                data = target.read_bytes()
                for i, d in enumerate(getattr(module, "EDITS", [])):
                    e = P.Edit.from_dict(d, what=f"{fid} edit {i}")
                    seg = data[e.offset : e.offset + len(e.replace)]
                    if seg != e.replace:
                        failures.append(
                            f"{fid}: bytes at {e.offset:#x} are"
                            f" {seg.hex()}, expected {e.replace.hex()}"
                        )

    # Repair site check, composed across every journaled fix on the
    # file: a repaired chunk must carry its repairs AND any absolute
    # edit whose site falls inside it (the beta composition). The
    # pristine bytes come from the backup; without the backup (or
    # without gff-cat) the journaled file hash is the only gate.
    files_all: dict[str, list[tuple[str, object]]] = {}
    for fix in journal.get("fixes", []):
        module = modules.get(fix.get("id", "?"))
        if module is not None:
            for f in fix.get("files", []):
                files_all.setdefault(f["path"], []).append((fix.get("id", "?"), module))
    for rel, items in sorted(files_all.items()):
        has_repairs = any(getattr(m, "REPAIRS", None) for _f, m in items)
        if not has_repairs:
            continue
        target = install / rel
        backup = P.backup_root(install) / rel
        try:
            gff_cat = P._gff_cat(None)
        except P.PatchError:
            gff_cat = None
        if gff_cat is None or not backup.is_file():
            reason = "no gff-cat" if gff_cat is None else "no pristine backup"
            print(f"  note: {rel}: repair sites checked by hash only ({reason})")
            continue
        locs: dict[tuple[str, int], tuple[int, int]] = {}
        listing = subprocess.run(
            [gff_cat, "list", str(backup)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        row_re = re.compile(r"^'([^']+)'\s+(\d+)\s+(\d+)\s+(\d+)\s*$")
        for row in listing.splitlines():
            m_row = row_re.match(row)
            if m_row:
                # fourccs print 4 bytes space-padded ('GPL '); repairs
                # use the stripped form ('GPL').
                locs[(m_row.group(1).strip(), int(m_row.group(2)))] = (
                    int(m_row.group(3)),
                    int(m_row.group(4)),
                )
        chunk_repairs: dict[tuple[str, int], list[P.GplRepair]] = {}
        chunk_edits: dict[tuple[str, int], list[tuple[int, P.Edit]]] = {}
        for fid2, m2 in items:
            for i, d in enumerate(getattr(m2, "EDITS", [])):
                e = P.Edit.from_dict(d, what=f"{fid2} edit {i}")
                for (kind, cid), (off, length) in locs.items():
                    if off <= e.offset and e.offset + len(e.replace) <= off + length:
                        chunk_edits.setdefault((kind, cid), []).append(
                            (e.offset - off, e)
                        )
            for i, d in enumerate(getattr(m2, "REPAIRS", [])):
                r = P.GplRepair.from_dict(d, what=f"{fid2} repair {i}")
                chunk_repairs.setdefault((r.kind, r.chunk_id), []).append(r)
        for (kind, cid), repairs_for_chunk in sorted(chunk_repairs.items()):
            off, length = locs[(kind, cid)]
            pristine = P._extract_chunk(backup, kind, cid, gff_cat)
            base = bytearray(pristine)
            for chunk_off, e in sorted(chunk_edits.get((kind, cid), [])):
                base[chunk_off : chunk_off + len(e.replace)] = e.replace
            try:
                expected = P.compute_patched_chunk(
                    bytes(base),
                    repairs_for_chunk,
                    what=f"{rel} {kind} {cid}",
                )
            except P.PatchError as e:
                failures.append(f"{rel}: {kind} {cid}: {e}")
                continue
            current = P._extract_chunk(target, kind, cid, gff_cat)
            if current != expected:
                failures.append(
                    f"{rel}: {kind} {cid} does not match the composed"
                    f" repaired bytes (drifted or partial)"
                )
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"\nVERIFY FAILED ({len(failures)} problem(s))")
        return 1
    ids = ", ".join(f.get("id", "?") for f in journal.get("fixes", []))
    print(
        f"{journal.get('tool', 'darkfix')}"
        f" {journal.get('version', '?')}: applied [{ids}]"
    )
    print("\nVERIFY OK")
    return 0


def cmd_status(layout: Layout, install: Path) -> int:
    manifest = P.load_manifest(layout.manifest_path)
    meta = manifest["meta"]
    print(
        f"patch:    {meta['name']} {layout.version} (schema {meta['schema_version']})"
    )
    print(
        f"target:   {meta['game']} GOG {manifest['target'].get('engine_version', '?')}"
    )
    print(f"install:  {install}")
    journal = P.read_journal(install)
    if journal and journal.get("status", "applied") == "pending":
        print(
            f"state:    INTERRUPTED (pending {P.JOURNAL_NAME} from a"
            f" crashed apply; darkfix {journal.get('version', '?')})"
        )
        for fix in journal.get("fixes", []):
            print(f"          {fix.get('id')}")
        print(
            "          recover: --unapply restores what the interrupted"
            " run reached from darkfix-backup/"
        )
    elif journal:
        print(
            f"state:    applied {journal.get('applied_at', '?')}"
            f" (darkfix {journal.get('version', '?')})"
        )
        for fix in journal.get("fixes", []):
            print(f"          {fix.get('id')}")
    else:
        print("state:    not applied")
    print("fixes:")
    for entry in manifest["fixes"]:
        state = "enabled " if entry.get("enabled", True) else "disabled"
        print(f"  [{state}] {entry['id']}")
    return 0


def _check_all(layout: Layout, install: Path, manifest: dict) -> None:
    """Full-install check against the canonical hash manifest.

    Authoring-time gate: catches a wrong engine build even in
    files no fix touches. Player zips do not ship docs/, so this
    is skipped by default and errors only when asked for.
    """
    ref_rel = manifest["target"].get("reference_manifest")
    if not ref_rel:
        raise P.PatchError("manifest declares no [target] reference_manifest")
    ref = layout.repo_root / ref_rel
    if not ref.is_file():
        raise P.PatchError(
            f"reference manifest not found: {ref} (authoring check"
            " only; a distributed zip does not ship docs/)"
        )
    with ref.open("rb") as f:
        reference = tomllib.load(f)
    expected = reference.get("files", {})
    patterns = reference.get("runtime_state", {}).get("patterns", [])
    missing: list[str] = []
    mismatched: list[str] = []
    matched = 0
    for rel, want in expected.items():
        if any(fnmatch.fnmatchcase(rel, pat) for pat in patterns):
            continue
        target = install / rel
        if not target.is_file():
            missing.append(rel)
        elif P.sha256_file(target) != want:
            mismatched.append(rel)
        else:
            matched += 1
    print(
        f"  full-install check vs {ref_rel}: {matched} matched,"
        f" {len(mismatched)} mismatched, {len(missing)} missing"
    )
    if mismatched or missing:
        detail = ", ".join((mismatched + missing)[:5])
        raise P.HashMismatch(
            f"install does not match the canonical manifest ({detail}...)"
        )


# --------------------------------------------------------------- selftest


def _synth_bytes(n: int) -> bytes:
    return bytes(((i * 7 + 13) & 0xFF) for i in range(n))


def _minimal_gff(chunks: list[tuple[str, int, bytes]]) -> bytes:
    """Build a minimal valid GFF holding the given (kind, id, bytes)
    chunks, one type per kind. Layout per docs/file-formats.md §1:
    28-byte header, chunk data from 28, TOC with one type list and an
    empty free list. Selftest-only; the applier itself never writes
    GFFs from scratch (gff-cat replace does the surgery).
    """
    kinds: dict[str, list[tuple[int, bytes]]] = {}
    for kind, cid, data in chunks:
        kinds.setdefault(kind, []).append((cid, data))
    data_area = bytearray()
    entries: list[tuple[str, list[tuple[int, int, int]]]] = []
    for kind, items in kinds.items():
        rows = []
        for cid, data in items:
            off = 28 + len(data_area)
            data_area.extend(data)
            rows.append((cid, off, len(data)))
        entries.append((kind, rows))
    toc_location = 28 + len(data_area)
    types_offset = 8
    body = bytearray()
    body += struct.pack("<H", len(entries))
    for kind, rows in entries:
        body += kind.encode("ascii").ljust(4)
        body += struct.pack("<I", len(rows))
        for cid, off, length in rows:
            body += struct.pack("<iII", cid, off, length)
    free_list_offset = types_offset + len(body)
    body += struct.pack("<H", 0)
    toc = struct.pack("<II", types_offset, free_list_offset) + bytes(body)
    toc_length = len(toc)
    header = b"GFFI" + struct.pack(
        "<IIIIII",
        0x00030000,
        28,
        toc_location,
        toc_length,
        0,
        1,
    )
    assert len(header) == 28
    return bytes(header) + bytes(data_area) + toc


def _make_patch(
    tmp: Path,
    name: str,
    target: str,
    target_hash: str,
    edits: list[P.Edit],
) -> tuple[Path, str]:
    """Single-target form of _make_multi_patch."""
    root = _make_multi_patch(tmp, name, [(target, target_hash, edits)])
    return root, f"fix.selftest.{name}.0"


def _make_multi_patch(
    tmp: Path,
    name: str,
    targets: list[tuple[str, str, list[P.Edit]]],
) -> Path:
    """Generate a self-contained patch tree in tmp with one fix per
    (target, hash, edits) entry. The same target may appear twice:
    that is how the composition refusal is exercised. The generated
    fix scripts go through the real load path, not a shortcut.
    """
    root = tmp / name
    (root / "fixes").mkdir(parents=True)
    entries = []
    for i, entry_spec in enumerate(targets):
        target, target_hash, edits = entry_spec[0], entry_spec[1], entry_spec[2]
        repairs = entry_spec[3] if len(entry_spec) > 3 else []
        fid = f"fix.selftest.{name}.{i}"
        lines = [
            '"""Selftest fix: generated by apply.py --selftest."""',
            "",
            "from darkfix.patcher import apply_bytes",
            "",
            f'ID = "{fid}"',
            f'TARGET = "{target}"',
            f'SOURCE_SHA256 = "{target_hash}"',
        ]
        if edits:
            lines.append("EDITS = [")
            for e in edits:
                lines.append(
                    f'    {{"offset": {e.offset},'
                    f' "expect": "{e.expect.hex()}",'
                    f' "replace": "{e.replace.hex()}"}},'
                )
            lines.append("]")
        else:
            lines.append("EDITS = []")
        if repairs:
            lines.append("REPAIRS = [")
            for r in repairs:
                rel = ", ".join(str(x) for x in r.relocate)
                lines.append(
                    f'    {{"kind": "{r.kind}", "chunk_id": {r.chunk_id},'
                    f' "offset": {r.offset},'
                    f' "expect": "{r.expect.hex()}",'
                    f' "replace": "{r.replace.hex()}",'
                    f' "relocate": [{rel}]}},'
                )
            lines.append("]")
        lines += [
            "",
            "",
            "def apply(source_path, dest_path):",
            "    apply_bytes(source_path, dest_path, EDITS)",
            "",
        ]
        script = f"{i:03d}-selftest.py"
        (root / "fixes" / script).write_text("\n".join(lines))
        entries.append((fid, script, target, target_hash))
    (root / "VERSION").write_text("0.0.1\n")
    file_hashes: dict[str, str] = {}
    for _fid, _script, target, target_hash in entries:
        file_hashes[target] = target_hash
    manifest = (
        "[meta]\n"
        "schema_version = 1\n"
        f'game = "ds1"\n'
        f'name = "{name}"\n'
        'license = "MIT"\n'
        "\n"
        "[target]\n"
        'source = "GOG"\n'
        'engine_version = "1.10"\n'
        "\n"
        "[target.files]\n"
        + "".join(f'"{t}" = "{h}"\n' for t, h in file_hashes.items())
        + "\n"
        + "".join(
            f'[[fixes]]\nid = "{fid}"\npath = "fixes/{script}"\nenabled = true\n\n'
            for fid, script, _t, _h in entries
        )
    )
    (root / "manifest.toml").write_text(manifest)
    return root


def selftest() -> int:
    """Exercise the full apply/verify/unapply cycle in temp dirs.

    Synthetic-file cycle plus refusal paths, the roadmap's no-op
    proof (an empty-EDITS fix applied to a copy of the real DSUN.EXE
    round-trips byte-identically), and a real-install cycle for the
    shipped fixes against install copies. Never touches the
    canonical install or the repo patch tree.
    """
    failures = 0

    def ok(label: str, cond: bool) -> None:
        nonlocal failures
        print(f"  {'PASS' if cond else 'FAIL'}: {label}")
        if not cond:
            failures += 1

    print("darkfix applier selftest")
    with tempfile.TemporaryDirectory(prefix="darkfix-selftest-") as td:
        tmp = Path(td)
        install = tmp / "install"
        install.mkdir()
        data = _synth_bytes(4096)
        target = install / "TEST.DAT"
        target.write_bytes(data)
        want_hash = P.sha256_bytes(data)
        edit = P.Edit(offset=0x10, expect=data[0x10:0x12], replace=b"\xaa\xbb")
        patched_expect = P.apply_edits(data, [edit])
        root, _fid = _make_patch(tmp, "editfix", "TEST.DAT", want_hash, [edit])

        rc = run([str(install)], patch_root=root)
        ok("apply succeeds", rc == 0)
        ok("target patched as expected", target.read_bytes() == patched_expect)
        journal = P.read_journal(install)
        ok(
            "journal records original hash",
            journal is not None
            and journal["fixes"][0]["files"][0]["original_sha256"] == want_hash,
        )
        backup = P.backup_root(install) / "TEST.DAT"
        ok(
            "backup holds the pristine copy",
            backup.is_file() and P.sha256_file(backup) == want_hash,
        )

        rc = run([str(install)], patch_root=root)
        ok(
            "re-apply reports already-applied, changes nothing",
            rc == 0 and target.read_bytes() == patched_expect,
        )
        rc = run([str(install), "--verify"], patch_root=root)
        ok("verify passes on the patched install", rc == 0)

        rc = run([str(install), "--unapply"], patch_root=root)
        ok("unapply succeeds", rc == 0)
        ok("target restored byte-identically", target.read_bytes() == data)
        ok("journal removed", P.read_journal(install) is None)
        ok("backup consumed", not backup.exists())

        # spec 5 composition: two enabled fixes on ONE target with
        # disjoint ranges compose into a single correct write; the
        # journal carries the merged patched hash so --verify and
        # --unapply see one consistent file.
        data2 = _synth_bytes(128)
        t2 = install / "COMPOSE.DAT"
        t2.write_bytes(data2)
        h2 = P.sha256_bytes(data2)
        e_a = P.Edit(offset=0x10, expect=data2[0x10:0x12], replace=b"\xaa\xbb")
        e_b = P.Edit(offset=0x30, expect=data2[0x30:0x32], replace=b"\xcc\xdd")
        merged_expect = P.apply_edits(data2, [e_a, e_b])
        root2 = _make_multi_patch(
            tmp,
            "composefix",
            [
                ("COMPOSE.DAT", h2, [e_a]),
                ("COMPOSE.DAT", h2, [e_b]),
            ],
        )
        rc = run([str(install)], patch_root=root2)
        ok("disjoint same-file fixes apply", rc == 0)
        ok(
            "composed file matches both fixes merged",
            t2.read_bytes() == merged_expect,
        )
        rc = run([str(install), "--verify"], patch_root=root2)
        ok("verify passes on the composed install", rc == 0)
        rc = run([str(install), "--unapply"], patch_root=root2)
        ok("composed install unapplies", rc == 0)
        ok(
            "composed target restored byte-identically",
            t2.read_bytes() == data2,
        )

        # Overlapping ranges still refuse at check time, before any
        # write, with the offending offsets named.
        e_c = P.Edit(offset=0x11, expect=data2[0x11:0x13], replace=b"\xee\xff")
        root3 = _make_multi_patch(
            tmp,
            "overlapfix",
            [
                ("COMPOSE.DAT", h2, [e_a]),
                ("COMPOSE.DAT", h2, [e_c]),
            ],
        )
        rc = run([str(install)], patch_root=root3)
        ok("overlapping same-file fixes refuse", rc == 1)

        tampered = bytearray(data)
        tampered[0x20] ^= 0xFF
        tampered = bytes(tampered)
        target.write_bytes(tampered)
        rc = run([str(install)], patch_root=root)
        ok("apply refuses a tampered target", rc == 1)
        ok("tampered target left untouched", target.read_bytes() == tampered)

        bad_root, _ = _make_patch(
            tmp,
            "badsite",
            "TEST.DAT",
            P.sha256_bytes(tampered),
            [P.Edit(offset=0x4000, expect=b"\x00\x00", replace=b"\xff\xff")],
        )
        rc = run([str(install)], patch_root=bad_root)
        ok("apply refuses a wrong fingerprint", rc == 1)
        ok("wrong-fingerprint site left untouched", target.read_bytes() == tampered)

        # Interrupted-write recovery: a crash between the first file
        # write and the completed journal leaves a patched file, a
        # pristine backup, and a pending journal. Stage exactly that
        # by hand, then prove the refusal and the --unapply recovery.
        inst2 = tmp / "inst2"
        inst2.mkdir()
        data2 = _synth_bytes(2048)
        t2 = inst2 / "TEST.DAT"
        t2.write_bytes(data2)
        h2 = P.sha256_bytes(data2)
        e2 = P.Edit(offset=0x8, expect=data2[0x8:0xA], replace=b"\x11\x22")
        p2 = P.apply_edits(data2, [e2])
        root2, _ = _make_patch(tmp, "interrupted", "TEST.DAT", h2, [e2])
        P.backup_file(inst2, "TEST.DAT")
        t2.write_bytes(p2)
        P.write_journal(
            inst2,
            {
                "tool": "interrupted",
                "version": "0.0.1",
                "applied_at": P.utc_now_iso(),
                "status": "pending",
                "fixes": [
                    {
                        "id": "fix.selftest.interrupted.0",
                        "files": [
                            {
                                "path": "TEST.DAT",
                                "original_sha256": h2,
                                "patched_sha256": P.sha256_bytes(p2),
                            }
                        ],
                    }
                ],
            },
        )
        status_out = io.StringIO()
        with contextlib.redirect_stdout(status_out):
            run([str(inst2), "--status"], patch_root=root2)
        ok(
            "--status reports the interrupted state, not applied",
            "INTERRUPTED" in status_out.getvalue()
            and "state:    applied" not in status_out.getvalue(),
        )
        rc = run([str(inst2)], patch_root=root2)
        ok("apply refuses while a pending journal is present", rc == 1)
        ok(
            "pending-journal install left untouched by the refusal",
            t2.read_bytes() == p2,
        )
        rc = run([str(inst2), "--unapply"], patch_root=root2)
        ok("unapply recovers a pending-journal install", rc == 0)
        ok("recovered install is byte-identical", t2.read_bytes() == data2)
        ok("pending journal consumed", P.read_journal(inst2) is None)
        status_out = io.StringIO()
        with contextlib.redirect_stdout(status_out):
            run([str(inst2), "--status"], patch_root=root2)
        ok(
            "--status reports not applied after recovery",
            "not applied" in status_out.getvalue(),
        )
        ok(
            "recovery consumed the backup",
            not (P.backup_root(inst2) / "TEST.DAT").exists(),
        )

        # Partial state: two fixes on two targets, only the first
        # written before the crash. --unapply restores the written
        # file, leaves the never-reached file alone, and clears the
        # stray staged tmp from the interrupted rename.
        inst3 = tmp / "inst3"
        inst3.mkdir()
        data_a = _synth_bytes(1024)
        data_b = _synth_bytes(1024)
        t_a = inst3 / "A.DAT"
        t_b = inst3 / "B.DAT"
        t_a.write_bytes(data_a)
        t_b.write_bytes(data_b)
        h_a = P.sha256_bytes(data_a)
        h_b = P.sha256_bytes(data_b)
        e_a = P.Edit(offset=0x4, expect=data_a[0x4:0x6], replace=b"\x55\x66")
        e_b = P.Edit(offset=0x10, expect=data_b[0x10:0x12], replace=b"\x33\x44")
        p_a = P.apply_edits(data_a, [e_a])
        p_b = P.apply_edits(data_b, [e_b])
        root3 = _make_multi_patch(
            tmp, "partial", [("A.DAT", h_a, [e_a]), ("B.DAT", h_b, [e_b])]
        )
        P.backup_file(inst3, "A.DAT")
        t_a.write_bytes(p_a)
        (inst3 / "B.DAT.darkfix-tmp").write_bytes(p_b)
        P.write_journal(
            inst3,
            {
                "tool": "partial",
                "version": "0.0.1",
                "applied_at": P.utc_now_iso(),
                "status": "pending",
                "fixes": [
                    {
                        "id": "fix.selftest.partial.0",
                        "files": [
                            {
                                "path": "A.DAT",
                                "original_sha256": h_a,
                                "patched_sha256": P.sha256_bytes(p_a),
                            }
                        ],
                    },
                    {
                        "id": "fix.selftest.partial.1",
                        "files": [
                            {
                                "path": "B.DAT",
                                "original_sha256": h_b,
                                "patched_sha256": P.sha256_bytes(p_b),
                            }
                        ],
                    },
                ],
            },
        )
        rc = run([str(inst3)], patch_root=root3)
        ok("apply refuses the partial interrupted state", rc == 1)
        rc = run([str(inst3), "--unapply"], patch_root=root3)
        ok("unapply recovers the partial interrupted state", rc == 0)
        ok("written file restored", t_a.read_bytes() == data_a)
        ok("unreached file untouched", t_b.read_bytes() == data_b)
        ok("stray staged tmp removed", not (inst3 / "B.DAT.darkfix-tmp").exists())
        ok("partial journal removed", P.read_journal(inst3) is None)
        ok(
            "partial A backup consumed",
            not (P.backup_root(inst3) / "A.DAT").exists(),
        )

        # Two enabled fixes sharing one target refuse at check time
        # when their ranges OVERLAP (disjoint same-file fixes compose
        # since the 2026-10-07 spec 5 amendment; the compose block
        # covers that side). Before anything is written or journaled.
        inst4 = tmp / "inst4"
        inst4.mkdir()
        data4 = _synth_bytes(2048)
        t4 = inst4 / "TEST.DAT"
        t4.write_bytes(data4)
        h4 = P.sha256_bytes(data4)
        e4a = P.Edit(offset=0x8, expect=data4[0x8:0xA], replace=b"\x11\x22")
        e4b = P.Edit(offset=0x9, expect=data4[0x9:0xB], replace=b"\x33\x44")
        root4 = _make_multi_patch(
            tmp, "overlap", [("TEST.DAT", h4, [e4a]), ("TEST.DAT", h4, [e4b])]
        )
        rc = run([str(inst4)], patch_root=root4)
        ok("apply refuses overlapping same-file fixes", rc == 1)
        ok("overlap refusal left the target untouched", t4.read_bytes() == data4)
        ok("overlap refusal wrote no journal", P.read_journal(inst4) is None)

        # A negative edit offset is refused instead of wrapping
        # around Python's slice semantics into the wrong bytes.
        try:
            P.Edit.from_dict(
                {"offset": -4, "expect": "aa", "replace": "bb"}, what="guard"
            )
            ok("negative edit offset refused", False)
        except P.PatchError:
            ok("negative edit offset refused", True)

        # Torn journal with no backup directory: the error must name
        # the delete-the-journal remedy (nothing was ever written),
        # not only the restore-from-backup route.
        inst5 = tmp / "inst5"
        inst5.mkdir()
        (inst5 / "TEST.DAT").write_bytes(_synth_bytes(128))
        (inst5 / P.JOURNAL_NAME).write_text("{ torn")
        err_out = io.StringIO()
        with contextlib.redirect_stderr(err_out):
            rc = run([str(inst5)], patch_root=root)
        ok("torn journal blocks apply", rc == 1)
        ok(
            "torn-journal error names the no-backup remedy",
            f"delete {P.JOURNAL_NAME}" in err_out.getvalue(),
        )

        # An all-disabled manifest is refused instead of "applied"
        # into an empty journal that --unapply could never consume.
        root6 = _make_multi_patch(tmp, "alldisabled", [("TEST.DAT", h4, [e4a])])
        m6 = root6 / "manifest.toml"
        m6.write_text(m6.read_text().replace("enabled = true", "enabled = false"))
        inst6 = tmp / "inst6"
        inst6.mkdir()
        t6 = inst6 / "TEST.DAT"
        t6.write_bytes(data4)
        err_out = io.StringIO()
        with contextlib.redirect_stderr(err_out):
            rc = run([str(inst6)], patch_root=root6)
        ok("all-disabled manifest refused", rc == 1)
        ok("all-disabled refusal wrote no journal", P.read_journal(inst6) is None)
        ok("all-disabled refusal left the target untouched", t6.read_bytes() == data4)

    # Detour repairs (docs/detour-repairs.md): the pure chunk math
    # first, then the gff-cat end-to-end when the binary is
    # available. Mechanism and gate review are the yuan-ti adoption
    # (docs/gate-review-yuan-ti-2026-11-13.md).
    code = bytes(range(256))
    r_inplace = P.GplRepair(
        kind="GPL",
        chunk_id=1,
        offset=0x10,
        expect=code[0x10:0x13],
        replace=b"\xaa\xbb\xcc",
    )
    r_detour = P.GplRepair(
        kind="GPL",
        chunk_id=1,
        offset=0x40,
        expect=code[0x40:0x44],
        # 7-byte replace whose detour-relative label word sits at
        # bytes 2..3: 0x0010 = 16 bytes into the detour.
        replace=b"\x18\x00\x00\x10\x40\x99\x67",
        relocate=(2,),
    )
    got = P.compute_patched_chunk(code, [r_inplace, r_detour])
    detour_at = len(code) + 1  # after the EXIT_GPL sentinel
    # Expected bytes constructed by hand (never via the code under
    # test): JUMP opcode 0x12, 15-bit big-endian target; the label
    # rebases to detour_at + 16 = 273 = 0x0111.
    tail = (
        b"\x00"
        + b"\x18\x00"
        + struct.pack(">H", detour_at + 16)
        + b"\x40\x99\x67"
        + b"\x12\x00\x44"
    )
    want = bytearray(code)
    want[0x10:0x13] = b"\xaa\xbb\xcc"
    want[0x40:0x44] = b"\x12" + struct.pack(">H", detour_at) + b"\x00"
    want = bytes(want) + tail
    ok("detour: same-length edit in place", got[0x10:0x13] == b"\xaa\xbb\xcc")
    ok(
        "detour: site is JUMP to the detour + EXIT fill",
        got[0x40:0x44] == b"\x12" + struct.pack(">H", detour_at) + b"\x00",
    )
    ok(
        "detour: whole chunk byte-exact (relocated label, JUMP back)",
        got == want,
    )
    ok(
        "detour: label rebased to absolute chunk address",
        got[detour_at + 2 : detour_at + 4] == struct.pack(">H", detour_at + 16),
    )
    try:
        P.compute_patched_chunk(
            code,
            [P.GplRepair("GPL", 1, 0x10, code[0x10:0x13], b"\xaa\xbb")],
        )
        ok("detour: shorter replace refused", False)
    except P.PatchError:
        ok("detour: shorter replace refused", True)
    try:
        P.compute_patched_chunk(
            code,
            [P.GplRepair("GPL", 1, 0x50, code[0x50:0x52], b"\x01\x02\x03")],
        )
        ok("detour: expect shorter than a JUMP refused", False)
    except P.PatchError:
        ok("detour: expect shorter than a JUMP refused", True)
    try:
        P.compute_patched_chunk(
            code,
            [
                P.GplRepair("GPL", 1, 0x10, code[0x10:0x13], b"\xaa\xbb\xcc"),
                P.GplRepair("GPL", 1, 0x11, code[0x11:0x14], b"\x01\x02\x03"),
            ],
        )
        ok("detour: overlapping sites refused", False)
    except P.PatchError:
        ok("detour: overlapping sites refused", True)
    big = bytes(0x7FFF)
    try:
        P.compute_patched_chunk(
            big,
            [
                P.GplRepair(
                    "GPL",
                    1,
                    0x10,
                    big[0x10:0x15],
                    big[0x10:0x15] + b"\x18\x00\x50\x00\x99\x67\x00\x00",
                    relocate=(4,),
                )
            ],
        )
        ok("detour: chunk past 15-bit JUMP range refused", False)
    except P.PatchError:
        ok("detour: chunk past 15-bit JUMP range refused", True)

    gff_cat = os.environ.get("DARKFIX_GFF_CAT") or shutil.which("gff-cat")
    if gff_cat is None:
        print(
            "  SKIP: gff-cat not found; detour end-to-end (extract +"
            " chunk replace through gff-edit) not run"
        )
    else:
        with tempfile.TemporaryDirectory(prefix="darkfix-detour-") as td2:
            tmp2 = Path(td2)
            chunk1 = bytes(((i * 11 + 3) & 0xFF) for i in range(64))
            chunk2 = bytes(((i * 5 + 9) & 0xFF) for i in range(32))
            gff_file = tmp2 / "SELFTEST.GFF"
            gff_file.write_bytes(_minimal_gff([("GPL", 1, chunk1), ("GPL", 2, chunk2)]))
            want1 = P.compute_patched_chunk(
                chunk1,
                [
                    P.GplRepair(
                        kind="GPL",
                        chunk_id=1,
                        offset=0x10,
                        expect=chunk1[0x10:0x13],
                        replace=b"\xaa\xbb\xcc",
                    )
                ],
            )
            repairs2 = [
                P.GplRepair(
                    kind="GPL",
                    chunk_id=2,
                    offset=0x8,
                    expect=chunk2[0x8:0xC],
                    # Label word at bytes 2..3 = 0x0014 = 20 bytes
                    # into the detour.
                    replace=b"\x18\x00\x00\x14\x99\x18\xcd\x01\x67",
                    relocate=(2,),
                )
            ]
            # Hand-built expectation (never via the code under test):
            # detour starts at 32 + 1 = 33; the label rebases to
            # 20 + 33 = 53; the site becomes JUMP 33 + one EXIT fill.
            detour2_at = len(chunk2) + 1
            body2 = (
                b"\x18\x00"
                + struct.pack(">H", 20 + detour2_at)
                + b"\x99\x18\xcd\x01\x67"
                + b"\x12\x00\x0c"
            )
            want2 = (
                chunk2[:0x8]
                + b"\x12"
                + struct.pack(">H", detour2_at)
                + b"\x00"
                + chunk2[0xC:]
                + b"\x00"
                + body2
            )
            out = P.apply_gpl_repairs(
                gff_file,
                tmp2 / "SELFTEST-patched.GFF",
                repairs2,
                gff_cat=gff_cat,
            )
            got1 = P._extract_chunk(out, "GPL", 1, gff_cat)
            got2 = P._extract_chunk(out, "GPL", 2, gff_cat)
            ok("detour end-to-end: untouched chunk byte-identical", got1 == chunk1)
            ok("detour end-to-end: patched chunk matches compute", got2 == want2)
            ok(
                "detour end-to-end: site JUMP + EXIT fill as computed",
                got2[0x8:0xC] == b"\x12" + struct.pack(">H", len(chunk2) + 1) + b"\x00",
            )
            # Two chunks repaired in one call exercises the
            # sequential gff-cat replace chain.
            gff2_file = tmp2 / "SELFTEST2.GFF"
            gff2_file.write_bytes(
                _minimal_gff([("GPL", 1, chunk1), ("GPL", 2, chunk2)])
            )
            out2 = P.apply_gpl_repairs(
                gff2_file,
                tmp2 / "SELFTEST2-patched.GFF",
                [
                    P.GplRepair(
                        kind="GPL",
                        chunk_id=1,
                        offset=0x10,
                        expect=chunk1[0x10:0x13],
                        replace=b"\xaa\xbb\xcc",
                    ),
                    *repairs2,
                ],
                gff_cat=gff_cat,
            )
            ok(
                "detour end-to-end: two chunks patched in one call",
                P._extract_chunk(out2, "GPL", 1, gff_cat) == want1
                and P._extract_chunk(out2, "GPL", 2, gff_cat) == want2,
            )

            # The mixed path: an absolute-offset EDITS fix and a
            # REPAIRS fix share one GFF target (the beta scenario).
            # EDITS compose in file space first; the repaired chunks
            # are extracted from the composed bytes, so both land.
            gff3 = _minimal_gff([("GPL", 1, chunk1), ("GPL", 2, chunk2)])
            gff3_file = tmp2 / "MIXED.GFF"
            gff3_file.write_bytes(gff3)
            chunk2_file_off = 28 + len(chunk1)
            abs_edit = P.Edit(
                offset=chunk2_file_off + 0x14,
                expect=chunk2[0x14:0x16],
                replace=b"\x77\x88",
            )
            mixed_repairs = [
                P.GplRepair(
                    kind="GPL",
                    chunk_id=1,
                    offset=0x10,
                    expect=chunk1[0x10:0x13],
                    replace=b"\xaa\xbb\xcc",
                ),
                P.GplRepair(
                    kind="GPL",
                    chunk_id=2,
                    offset=0x8,
                    expect=chunk2[0x8:0xC],
                    replace=b"\x18\x00\x00\x14\x99\x18\xcd\x01\x67",
                    relocate=(2,),
                ),
            ]
            root_m = _make_multi_patch(
                tmp2,
                "mixedfix",
                [
                    ("MIXED.GFF", P.sha256_bytes(gff3), [abs_edit]),
                    ("MIXED.GFF", P.sha256_bytes(gff3), [], mixed_repairs),
                ],
            )
            inst_m = tmp2 / "inst-mixed"
            inst_m.mkdir()
            (inst_m / "MIXED.GFF").write_bytes(gff3)
            rc = run([str(inst_m)], patch_root=root_m)
            ok("detour mixed path: apply succeeds", rc == 0)
            target_m = inst_m / "MIXED.GFF"
            got_c1 = P._extract_chunk(target_m, "GPL", 1, gff_cat)
            got_c2 = P._extract_chunk(target_m, "GPL", 2, gff_cat)
            want_c1 = P.compute_patched_chunk(chunk1, [mixed_repairs[0]])
            want_c2 = bytearray(chunk2)
            want_c2[0x14:0x16] = b"\x77\x88"
            want_c2 = bytes(want_c2)
            detour2_at = len(chunk2) + 1
            body2 = (
                b"\x18\x00"
                + struct.pack(">H", 20 + detour2_at)
                + b"\x99\x18\xcd\x01\x67"
                + b"\x12\x00\x0c"
            )
            want_c2 = (
                want_c2[:0x8]
                + b"\x12"
                + struct.pack(">H", detour2_at)
                + b"\x00"
                + want_c2[0xC:]
                + b"\x00"
                + body2
            )
            ok("detour mixed path: in-place chunk patched", got_c1 == want_c1)
            ok(
                "detour mixed path: chunk carries both the edit and the detour",
                got_c2 == want_c2,
            )
            rc = run([str(inst_m), "--verify"], patch_root=root_m)
            ok("detour mixed path: verify passes", rc == 0)
            rc = run([str(inst_m), "--unapply"], patch_root=root_m)
            ok("detour mixed path: unapply restores", rc == 0)
            ok(
                "detour mixed path: file byte-identical after unapply",
                (inst_m / "MIXED.GFF").read_bytes() == gff3,
            )

    exe = DEFAULT_PATCH_ROOT.parent / ".games" / "ds1" / "DSUN.EXE"
    if exe.is_file():
        with tempfile.TemporaryDirectory(prefix="darkfix-noop-") as td:
            tmp = Path(td)
            install = tmp / "ds1"
            install.mkdir()
            shutil.copy2(exe, install / "DSUN.EXE")
            original = P.sha256_file(install / "DSUN.EXE")
            root, _ = _make_patch(tmp, "noop", "DSUN.EXE", original, [])
            rc = run([str(install)], patch_root=root)
            ok(
                "no-op fix applies to real DSUN.EXE copy byte-identically",
                rc == 0 and P.sha256_file(install / "DSUN.EXE") == original,
            )
            rc = run([str(install), "--verify"], patch_root=root)
            ok("no-op verify passes", rc == 0)
            rc = run([str(install), "--unapply"], patch_root=root)
            ok(
                "no-op unapply restores byte-identically",
                rc == 0 and P.sha256_file(install / "DSUN.EXE") == original,
            )
    else:
        print(
            "  SKIP: .games/ds1/DSUN.EXE not present; real-binary no-op cycle not run"
        )

    # Real-install cycle for the shipped fixes: apply the actual
    # repo patch tree (every enabled fix) against a temp install
    # holding copies of every [target.files] entry, then verify the
    # journaled patched hashes and unapply byte-identically. This is
    # the regression test for the shipped GPLDATA.GFF fixes
    # (deadtriggers + script-repairs composed, the default enabled
    # set): the patched hash below pins all seven edit sites; any
    # accidental EDITS change fails here. (fix-workflow 5.1 hash
    # test; the composition behavior is the composed-write path
    # itself.)
    gamedir = DEFAULT_PATCH_ROOT.parent / ".games" / "ds1"
    real_files = {"DSUN.EXE", "GPLDATA.GFF"}
    if all((gamedir / f).is_file() for f in real_files):
        with tempfile.TemporaryDirectory(prefix="darkfix-real-") as td:
            tmp = Path(td)
            install = tmp / "ds1"
            install.mkdir()
            for f in real_files:
                shutil.copy2(gamedir / f, install / f)
            rc = run([str(install)], patch_root=DEFAULT_PATCH_ROOT)
            ok("real patch tree applies to install copies", rc == 0)
            patched = P.sha256_file(install / "GPLDATA.GFF")
            ok(
                "patched GPLDATA.GFF matches the recorded deadtriggers hash",
                patched
                == "2c851deeaafcde86d5eba118e1d62f5d7320a3c6f47cffdb719b2590a9fa315f",
            )
            rc = run([str(install), "--verify"], patch_root=DEFAULT_PATCH_ROOT)
            ok("verify passes on the real patched install", rc == 0)
            rc = run([str(install), "--unapply"], patch_root=DEFAULT_PATCH_ROOT)
            ok("real patch tree unapplies", rc == 0)
            ok(
                "real install restored byte-identically",
                all(
                    P.sha256_file(install / f) == P.sha256_file(gamedir / f)
                    for f in real_files
                ),
            )
    else:
        print(
            "  SKIP: .games/ds1/ install files not present;"
            " real-fix deadtriggers cycle not run"
        )

    print()
    if failures:
        print(f"SELFTEST FAIL ({failures} failure(s))")
        return 1
    print("SELFTEST OK")
    return 0


# ------------------------------------------------------------------- CLI


def run(argv: list[str] | None, patch_root: Path = DEFAULT_PATCH_ROOT) -> int:
    layout = Layout(patch_root=patch_root)
    ap = argparse.ArgumentParser(
        prog="apply.py",
        description="darkfix-ds1 applier (spec.md §4)",
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--unapply", action="store_true", help="restore the pre-patch state")
    g.add_argument(
        "--verify",
        action="store_true",
        help="check a patched install against its journal",
    )
    g.add_argument("--status", action="store_true", help="show patch and install state")
    g.add_argument(
        "--check-all",
        action="store_true",
        help="also verify the whole install against the canonical hash"
        " manifest (authoring-time; needs the repo checkout)",
    )
    g.add_argument(
        "--selftest",
        action="store_true",
        help="run the self-test cycle in temp dirs; installs nothing",
    )
    ap.add_argument(
        "install",
        nargs="?",
        help="path to the game install directory",
    )
    args = ap.parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        if not args.install:
            ap.error("an install directory is required")
        install = Path(args.install).resolve()
        if args.unapply:
            return cmd_unapply(layout, install)
        if args.verify:
            return cmd_verify(layout, install)
        if args.status:
            return cmd_status(layout, install)
        return cmd_apply(layout, install, check_all=args.check_all)
    except P.PatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    return run(None)


if __name__ == "__main__":
    sys.exit(main())
