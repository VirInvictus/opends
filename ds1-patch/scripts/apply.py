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
    seen_targets: dict[str, str] = {}
    for entry in enabled:
        module = load_fix_module(layout.patch_root / entry["path"])
        target_rel = check_fix_contract(module, entry, target_files)
        other = seen_targets.get(target_rel)
        if other is not None:
            raise P.ManifestError(
                f"{module.ID} and {other} both target {target_rel}: two"
                f" fix scripts cannot compose against one file, so the"
                f" second write would corrupt the first fix; disable one"
                f" of them in the manifest"
            )
        seen_targets[target_rel] = module.ID
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
        edits = [
            P.Edit.from_dict(d, what=f"{module.ID} edit {i}")
            for i, d in enumerate(getattr(module, "EDITS", []))
        ]
        source_bytes = target.read_bytes()
        patched = P.apply_edits(source_bytes, edits, what=module.ID)
        prepared.append((module, target_rel, source_bytes, patched))
        records.append(
            {
                "id": module.ID,
                "files": [
                    {
                        "path": target_rel,
                        "original_sha256": P.sha256_bytes(source_bytes),
                        "patched_sha256": P.sha256_bytes(patched),
                    }
                ],
            }
        )
        print(f"  checked {module.ID} ({target_rel}, {len(edits)} site(s))")
    for entry in disabled:
        print(f"  skipped {entry['id']} (disabled in manifest)")

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

    # Write phase.
    backed_up: set[str] = set()
    for module, target_rel, source_bytes, patched in prepared:
        target = install / target_rel
        if P.sha256_file(target) != module.SOURCE_SHA256:
            raise P.HashMismatch(
                f"{module.ID}: {target_rel} changed during apply; aborting"
            )
        if target_rel not in backed_up:
            P.backup_file(install, target_rel)
            backed_up.add(target_rel)
        tmp = target.with_name(target.name + P.STAGED_SUFFIX)
        tmp.write_bytes(patched)
        os.replace(tmp, target)
        print(f"  applied {module.ID} -> {target_rel}")

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
    for i, (target, target_hash, edits) in enumerate(targets):
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

        # Two enabled fixes sharing one target refuse at check time,
        # before anything is written or journaled.
        inst4 = tmp / "inst4"
        inst4.mkdir()
        data4 = _synth_bytes(2048)
        t4 = inst4 / "TEST.DAT"
        t4.write_bytes(data4)
        h4 = P.sha256_bytes(data4)
        e4a = P.Edit(offset=0x8, expect=data4[0x8:0xA], replace=b"\x11\x22")
        e4b = P.Edit(offset=0x20, expect=data4[0x20:0x22], replace=b"\x33\x44")
        root4 = _make_multi_patch(
            tmp, "compose", [("TEST.DAT", h4, [e4a]), ("TEST.DAT", h4, [e4b])]
        )
        rc = run([str(inst4)], patch_root=root4)
        ok("apply refuses two fixes on one target", rc == 1)
        ok("composition refusal left the target untouched", t4.read_bytes() == data4)
        ok("composition refusal wrote no journal", P.read_journal(inst4) is None)

        # A negative edit offset is refused instead of wrapping
        # around Python's slice semantics into the wrong bytes.
        try:
            P.Edit.from_dict(
                {"offset": -4, "expect": "aa", "replace": "bb"}, what="guard"
            )
            ok("negative edit offset refused", False)
        except P.PatchError:
            ok("negative edit offset refused", True)

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
    # the regression test for fix.ds1.deadtriggers: the GPLDATA.GFF
    # patched hash below pins the eleven repoint bytes; any
    # accidental EDITS change fails here. (fix-workflow 5.1 hash
    # test; the recorded value lives in fixes/001-deadtriggers.md.)
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
                == "e6b163bd446637c6c68f6897c01b59518b513054c90b4a7d7439d900e14142f0",
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
