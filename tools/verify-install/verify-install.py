#!/usr/bin/env python3
"""verify-install: check a Dark Sun install against a canonical hash manifest.

Stdlib-only. Python 3.11+ for tomllib.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text().strip()
REPO_ROOT = HERE.parents[1]
DEFAULT_MANIFEST_DIR = REPO_ROOT / "docs" / "source-hashes"

DEFAULT_PATHS = {
    "ds1": Path.home() / ".wine" / "drive_c" / "GOG Games" / "Dark Sun",
    "ds2": Path.home() / ".wine" / "drive_c" / "GOG Games" / "Dark Sun 2",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*")):
        if p.is_file():
            yield p


def relpath(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


def matches_any(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, pat) for pat in patterns)


def cmd_capture(args: argparse.Namespace) -> int:
    install = args.path.resolve()
    if not install.is_dir():
        print(f"error: not a directory: {install}", file=sys.stderr)
        return 2

    ignore_patterns: list[str] = args.ignore or []
    entries: list[tuple[str, str]] = []
    for p in walk_files(install):
        rel = relpath(p, install)
        if matches_any(rel, ignore_patterns):
            continue
        entries.append((rel, sha256_file(p)))

    out = sys.stdout if args.output in (None, "-") else open(args.output, "w")
    try:
        out.write(
            "# Canonical source-hash manifest. Schema version 1.\n"
            f"# Captured by tools/verify-install v{VERSION} (capture mode).\n"
            f"# Source path: {install}\n"
            "# Hand-edit only the [runtime_state] block; the [files] block is\n"
            "# regenerated each capture and should not be hand-edited.\n\n"
        )
        out.write("[meta]\n")
        out.write(f'game = "{args.game}"\n')
        out.write(f'source = "{args.source}"\n')
        out.write(f'engine_version = "{args.engine_version}"\n')
        out.write("schema_version = 1\n")
        if args.captured_from:
            out.write(f'captured_from = "{args.captured_from}"\n')
        out.write("\n[files]\n")
        for rel, h in entries:
            out.write(f'"{rel}" = "{h}"\n')
        out.write(
            "\n[runtime_state]\n"
            "# Paths the verifier expects may exist in a deployed install\n"
            "# but whose contents are user-mutable (saves, configs, GOG client\n"
            "# state, DOSBox tuning, etc.). Glob patterns (fnmatchcase).\n"
            "patterns = [\n"
            "]\n"
        )
    finally:
        if out is not sys.stdout:
            out.close()
    return 0


def _verify_install(
    install: Path,
    manifest_path: Path,
) -> tuple[dict, dict]:
    """Verify `install` against `manifest_path`.

    Returns `(manifest_meta, report)` where `report` is the
    machine-readable summary used by both the human-print path
    and the `--json` output.
    """
    with manifest_path.open("rb") as f:
        manifest = tomllib.load(f)

    expected: dict[str, str] = manifest.get("files", {})
    runtime_patterns: list[str] = manifest.get("runtime_state", {}).get(
        "patterns", []
    )

    matched: list[str] = []
    mismatched: list[dict] = []
    missing: list[str] = []
    extras: list[str] = []
    skipped: list[str] = []

    seen: set[str] = set()
    for rel, want_hash in expected.items():
        target = install / rel
        seen.add(rel)
        # runtime_state patterns override [files] entries: an
        # entry that appears in both is treated as runtime_state
        # (not verified). Lets us record pristine-install hashes
        # in [files] for completeness while still skipping files
        # the game or installer rewrites at runtime.
        if matches_any(rel, runtime_patterns):
            skipped.append(rel)
            continue
        if not target.is_file():
            missing.append(rel)
            continue
        got = sha256_file(target)
        if got == want_hash:
            matched.append(rel)
        else:
            mismatched.append(
                {"path": rel, "expected": want_hash, "actual": got}
            )

    for p in walk_files(install):
        rel = relpath(p, install)
        if rel in seen:
            continue
        if matches_any(rel, runtime_patterns):
            skipped.append(rel)
        else:
            extras.append(rel)

    report = {
        "install": str(install),
        "manifest": str(manifest_path),
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
        "extras": extras,
        "skipped": skipped,
        "ok": not mismatched and not missing,
    }
    return manifest.get("meta", {}), report


def _print_report(meta: dict, report: dict, args: argparse.Namespace) -> None:
    """Human-text rendering of the verify report (the v0.1 path)."""
    print(f"install:  {report['install']}")
    print(f"manifest: {report['manifest']}")
    print(
        f"  game: {meta.get('game', '?')}  "
        f"source: {meta.get('source', '?')}  "
        f"engine: {meta.get('engine_version', '?')}"
    )
    print(
        f"matched: {len(report['matched'])}  "
        f"mismatched: {len(report['mismatched'])}  "
        f"missing: {len(report['missing'])}  "
        f"extras: {len(report['extras'])}  "
        f"skipped: {len(report['skipped'])}"
    )

    if report["mismatched"]:
        print("\nMISMATCHED (file present but hash differs):")
        for m in report["mismatched"]:
            print(f"  {m['path']}")
            print(f"    expected: {m['expected']}")
            print(f"    actual:   {m['actual']}")
    if report["missing"]:
        print("\nMISSING (manifested file not found):")
        for rel in report["missing"]:
            print(f"  {rel}")
    if report["extras"]:
        if args.show_extras:
            print("\nEXTRAS (present but not in manifest or runtime_state):")
            for rel in report["extras"]:
                print(f"  {rel}")
        else:
            print(
                f"\n({len(report['extras'])} extras; pass --show-extras to list)"
            )
    if report["skipped"] and args.show_skipped:
        print("\nSKIPPED (matched runtime_state pattern):")
        for rel in report["skipped"]:
            print(f"  {rel}")

    print("\nOK" if report["ok"] else "\nFAIL")


def _extract_from_installer(installer: Path) -> Path:
    """Run innoextract on the GOG installer; return the
    extracted-files root inside a temp dir. Caller owns the
    cleanup (returned path lives under a TemporaryDirectory).
    """
    if shutil.which("innoextract") is None:
        raise SystemExit(
            "verify-install: --repair needs `innoextract` on PATH; "
            "install it via `dnf install innoextract`."
        )
    tmp = Path(tempfile.mkdtemp(prefix="verify-install-repair-"))
    # `innoextract -e <installer> -d <dir>` extracts the app/
    # tree under <dir>/app. Quiet output unless something fails.
    result = subprocess.run(
        ["innoextract", "-e", "-d", str(tmp), str(installer)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise SystemExit(
            f"verify-install: innoextract failed (rc={result.returncode}):\n"
            f"{result.stderr}"
        )
    # GOG Inno installers extract the install tree directly at the
    # output root (DSUN.EXE, MIDITSR.EXE, *.GFF, etc.). The `app/`
    # subdir present in the extract holds GOG launcher artifacts
    # (goggame-*.ico, webcache.zip) and is itself part of the
    # install, not a wrapper around it. Do not drill into it.
    return tmp


def cmd_repair(
    args: argparse.Namespace, install: Path, report: dict
) -> int:
    """Restore mismatched / missing files from the GOG installer.

    Stages a backup of any overwritten file at
    `<install>/__verify-install-backup/<path>` so the change is
    reversible. `--dry-run` reports what would be repaired
    without writing.
    """
    installer = args.repair
    if not installer.is_file():
        print(
            f"verify-install: --repair installer {installer} not found",
            file=sys.stderr,
        )
        return 2
    targets = [m["path"] for m in report["mismatched"]] + list(report["missing"])
    if not targets:
        print("repair: nothing to do (no mismatched or missing files)")
        return 0

    if args.dry_run:
        print(f"repair --dry-run: would restore {len(targets)} file(s):")
        for t in targets:
            print(f"  {t}")
        return 0

    backup_root = install / "__verify-install-backup"
    extracted_root = _extract_from_installer(installer)
    try:
        restored = 0
        skipped = []
        for rel in targets:
            src = extracted_root / rel
            if not src.is_file():
                skipped.append(rel)
                continue
            dst = install / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                backup_dst = backup_root / rel
                backup_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, backup_dst)
            shutil.copy2(src, dst)
            restored += 1
            print(f"  restored {rel}")
        print(
            f"repair: restored {restored}/{len(targets)} file(s); "
            f"{len(skipped)} not found in installer"
        )
        if skipped:
            print("  not in installer:")
            for s in skipped:
                print(f"    {s}")
        if restored > 0:
            print(f"  backups in {backup_root}")
        return 0 if not skipped else 1
    finally:
        shutil.rmtree(extracted_root, ignore_errors=True)


def cmd_rollback(args: argparse.Namespace, install: Path) -> int:
    """Restore every file under `<install>/__verify-install-backup/`
    to its original location. Inverse of v0.2.0's `--repair`. The
    backup dir was populated by `cmd_repair` with the
    pre-repair contents; after a successful rollback the dir is
    removed (with `--dry-run` it just lists what would happen).
    """
    backup_root = install / "__verify-install-backup"
    if not backup_root.is_dir():
        print(
            f"verify-install: no backup directory at {backup_root}; "
            "nothing to roll back.",
            file=sys.stderr,
        )
        return 0
    targets: list[Path] = sorted(
        p for p in backup_root.rglob("*") if p.is_file()
    )
    if not targets:
        print(f"verify-install: backup directory {backup_root} is empty.",
              file=sys.stderr)
        return 0
    if args.dry_run:
        print(f"rollback --dry-run: would restore {len(targets)} file(s):")
        for src in targets:
            rel = src.relative_to(backup_root)
            print(f"  {rel}")
        return 0
    restored = 0
    for src in targets:
        rel = src.relative_to(backup_root)
        dst = install / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored += 1
        print(f"  restored {rel}")
    print(
        f"rollback: restored {restored} file(s) from {backup_root}; "
        f"removing backup directory."
    )
    shutil.rmtree(backup_root, ignore_errors=True)
    return 0


def _print_summary(meta: dict, report: dict) -> None:
    """One-line plain-English status for the common case.

    The full table (`_print_report`) is still useful but
    dense; `--summary` is for the modder running `verify-install`
    out of habit who just wants to know whether their install is
    in shape. Frame the line by the dominant failure category
    (mismatched > missing > extras-only > clean), and surface the
    single most actionable next step.
    """
    m = len(report["mismatched"])
    miss = len(report["missing"])
    extras = len(report["extras"])
    skipped = len(report["skipped"])
    matched = len(report["matched"])
    game_label = {"ds1": "Dark Sun: Shattered Lands",
                  "ds2": "Dark Sun: Wake of the Ravager"}.get(
                      meta.get("game"), meta.get("game", "?"))
    src_label = meta.get("source", "?")
    def plural(n: int, singular: str, plural_form: str | None = None) -> str:
        word = plural_form or (singular + "s")
        return f"{n} {singular if n == 1 else word}"

    if report["ok"]:
        bits = [f"Your {game_label} install matches the canonical {src_label} hash manifest."]
        if extras > 0:
            bits.append(
                f"{plural(extras, 'extra')} (probably saves / DOSBox config / DSUN.LOG)."
            )
        if skipped > 0:
            bits.append(f"{plural(skipped, 'runtime-state file')} skipped by policy.")
        print(" ".join(bits))
        print(f"  ({plural(matched, 'file')} matched, no mismatches, no missing files.)")
        return
    bits: list[str] = []
    if m > 0:
        bits.append(plural(m, "mismatched file"))
    if miss > 0:
        bits.append(plural(miss, "missing file"))
    issue_summary = " + ".join(bits) if bits else "an issue"
    print(f"Your {game_label} install has {issue_summary}.")
    if m + miss > 0:
        print(
            "  Run with --repair <GOG-installer.exe> to restore canonical bytes."
        )
        print("  --rollback restores a previous --repair from the backup dir.")
    if extras > 0:
        print(
            f"  Also: {plural(extras, 'extra')} (saves / config); use --show-extras to list."
        )


def cmd_verify(args: argparse.Namespace) -> int:
    install = args.path.resolve()
    if not install.is_dir():
        print(f"error: not a directory: {install}", file=sys.stderr)
        return 2

    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else DEFAULT_MANIFEST_DIR / f"{args.game}-gog-1.10.toml"
    )
    if not manifest_path.is_file():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    meta, report = _verify_install(install, manifest_path)
    report["meta"] = meta

    if args.json:
        # Sort lists so identical inputs produce identical JSON
        # (useful in CI diff comparisons).
        report_json = {
            "tool": "verify-install",
            "version": VERSION,
            "install": report["install"],
            "manifest": report["manifest"],
            "meta": meta,
            "summary": {
                "matched": len(report["matched"]),
                "mismatched": len(report["mismatched"]),
                "missing": len(report["missing"]),
                "extras": len(report["extras"]),
                "skipped": len(report["skipped"]),
            },
            "mismatched": report["mismatched"],
            "missing": sorted(report["missing"]),
            "extras": sorted(report["extras"]),
            "skipped": sorted(report["skipped"]),
            "ok": report["ok"],
        }
        print(json.dumps(report_json, indent=2))
    elif args.summary:
        _print_summary(meta, report)
    else:
        _print_report(meta, report, args)

    if args.rollback:
        rc = cmd_rollback(args, install)
        if rc != 0:
            return rc

    if args.repair is not None:
        # Run repair after the verify; the repair flow uses
        # mismatched + missing from the report we just built.
        rc = cmd_repair(args, install, report)
        if rc != 0:
            return rc

    return 0 if report["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verify-install",
        description="Verify a Dark Sun install against a canonical hash manifest.",
    )
    p.add_argument(
        "--version", action="version", version=f"verify-install {VERSION}"
    )
    p.add_argument(
        "--game",
        choices=["ds1", "ds2"],
        required=True,
        help="which game (ds1 = Shattered Lands, ds2 = Wake of the Ravager)",
    )
    p.add_argument(
        "--path",
        type=Path,
        default=None,
        help="path to install (default: ~/.wine/drive_c/GOG Games/{Dark Sun, Dark Sun 2})",
    )
    p.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="manifest file (default: docs/source-hashes/<game>-gog-1.10.toml)",
    )
    p.add_argument(
        "--capture",
        action="store_true",
        help="capture mode: emit a new manifest from --path instead of verifying",
    )
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="capture-mode output file (default: stdout)",
    )
    p.add_argument(
        "--source",
        default="GOG",
        help="capture-mode: source label (default: GOG)",
    )
    p.add_argument(
        "--engine-version",
        default="1.10",
        help="capture-mode: engine version label (default: 1.10)",
    )
    p.add_argument(
        "--captured-from",
        default=None,
        help="capture-mode: free-form description of the capture origin",
    )
    p.add_argument(
        "--ignore",
        action="append",
        default=None,
        metavar="GLOB",
        help="capture-mode: glob pattern to skip; repeatable",
    )
    p.add_argument(
        "--show-extras",
        action="store_true",
        help="verify-mode: list each extra file",
    )
    p.add_argument(
        "--show-skipped",
        action="store_true",
        help="verify-mode: list each skipped (runtime_state) file",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help=(
            "verify-mode: emit the report as JSON on stdout instead of "
            "the human-readable summary. Useful for CI checks, the "
            "repro harness's pre-run sanity check, or downstream "
            "tooling. Lists are sorted for stable output."
        ),
    )
    p.add_argument(
        "--repair",
        type=Path,
        default=None,
        metavar="INSTALLER.EXE",
        help=(
            "verify-mode: for every mismatched / missing file, "
            "re-extract the canonical bytes from the GOG installer "
            "via `innoextract` and write them back. Stages a backup "
            "at <install>/__verify-install-backup/<path> so the "
            "change is reversible. Requires `innoextract` on PATH."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "with --repair / --rollback: report what would be "
            "restored without writing anything."
        ),
    )
    p.add_argument(
        "--rollback",
        action="store_true",
        help=(
            "verify-mode: restore every file under "
            "<install>/__verify-install-backup/ to its original "
            "location and remove the backup directory. Inverse of "
            "--repair. Pair with --dry-run to preview."
        ),
    )
    p.add_argument(
        "--summary",
        action="store_true",
        help=(
            "verify-mode: emit a one-line plain-English status "
            "instead of the full hash-by-hash table. Useful for "
            "the common-case modder check: \"is my install in "
            "shape, yes / no, what's wrong.\""
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.path is None:
        args.path = DEFAULT_PATHS[args.game]
    if args.capture:
        return cmd_capture(args)
    return cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main())
