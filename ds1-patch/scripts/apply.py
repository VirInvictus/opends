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
import fnmatch
import importlib.util
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import tomllib

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_PATCH_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from darkfix import patcher as P


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
    for entry in enabled:
        module = load_fix_module(layout.patch_root / entry["path"])
        target_rel = check_fix_contract(module, entry, target_files)
        target = install / target_rel
        if not target.is_file():
            raise P.PatchError(f"{module.ID}: target file not found: {target}")
        current = P.sha256_file(target)
        if current != module.SOURCE_SHA256:
            raise P.HashMismatch(
                f"{module.ID}: {target_rel} does not match the canonical"
                f" GOG 1.10 hash.\n  expected: {module.SOURCE_SHA256}\n"
                f"  actual:   {current}\n"
                f"  (already patched? wrong build? damaged install?)"
            )
        edits = [
            P.Edit.from_dict(d, what=f"{module.ID} edit {i}")
            for i, d in enumerate(getattr(module, "EDITS", []))
        ]
        source_bytes = target.read_bytes()
        patched = P.apply_edits(source_bytes, edits, what=module.ID)
        prepared.append((module, target_rel, source_bytes, patched))
        print(f"  checked {module.ID} ({target_rel}, {len(edits)} site(s))")
    for entry in disabled:
        print(f"  skipped {entry['id']} (disabled in manifest)")

    # Write phase.
    backed_up: set[str] = set()
    records = []
    for module, target_rel, source_bytes, patched in prepared:
        target = install / target_rel
        if P.sha256_file(target) != module.SOURCE_SHA256:
            raise P.HashMismatch(
                f"{module.ID}: {target_rel} changed during apply; aborting"
            )
        if target_rel not in backed_up:
            P.backup_file(install, target_rel)
            backed_up.add(target_rel)
        tmp = target.with_name(target.name + ".darkfix-tmp")
        tmp.write_bytes(patched)
        os.replace(tmp, target)
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
        print(f"  applied {module.ID} -> {target_rel}")

    journal = {
        "tool": name,
        "version": version,
        "applied_at": P.utc_now_iso(),
        "fixes": records,
    }
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
        raise P.NotApplied(f"no {P.JOURNAL_NAME} in {install}; nothing to unapply")
    restored = P.restore_from_backup(install, journal)
    (install / P.JOURNAL_NAME).unlink()
    print(f"{name} {layout.version}: unapplied")
    for rel in restored:
        print(f"  restored {rel}")
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
    if journal:
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
    """Generate a minimal self-contained patch tree in tmp.

    Returns (patch_root, fix_id). The generated fix script goes
    through the real load path, not a shortcut.
    """
    root = tmp / name
    (root / "fixes").mkdir(parents=True)
    fid = f"fix.selftest.{name}"
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
    (root / "fixes" / "000-selftest.py").write_text("\n".join(lines))
    (root / "VERSION").write_text("0.0.1\n")
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
        f'"{target}" = "{target_hash}"\n'
        "\n"
        "[[fixes]]\n"
        f'id = "{fid}"\n'
        'path = "fixes/000-selftest.py"\n'
        "enabled = true\n"
    )
    (root / "manifest.toml").write_text(manifest)
    return root, fid


def selftest() -> int:
    """Exercise the full apply/verify/unapply cycle in temp dirs.

    Synthetic-file cycle plus refusal paths, then the roadmap's
    no-op proof: an empty-EDITS fix applied to a copy of the real
    DSUN.EXE must round-trip byte-identically. Never touches the
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
