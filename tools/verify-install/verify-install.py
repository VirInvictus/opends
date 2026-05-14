#!/usr/bin/env python3
"""verify-install: check a Dark Sun install against a canonical hash manifest.

Stdlib-only. Python 3.11+ for tomllib.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import sys
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

    with manifest_path.open("rb") as f:
        manifest = tomllib.load(f)

    expected: dict[str, str] = manifest.get("files", {})
    runtime_patterns: list[str] = manifest.get("runtime_state", {}).get("patterns", [])

    matched: list[str] = []
    mismatched: list[tuple[str, str, str]] = []
    missing: list[str] = []
    extras: list[str] = []
    skipped: list[str] = []

    seen: set[str] = set()
    for rel, want_hash in expected.items():
        target = install / rel
        seen.add(rel)
        # runtime_state patterns override [files] entries: an entry that
        # appears in both is treated as runtime_state (not verified). Lets
        # us record pristine-install hashes in [files] for completeness
        # while still skipping files the game or installer rewrites at
        # runtime (saves, SOUND.CFG, etc.).
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
            mismatched.append((rel, want_hash, got))

    for p in walk_files(install):
        rel = relpath(p, install)
        if rel in seen:
            continue
        if matches_any(rel, runtime_patterns):
            skipped.append(rel)
        else:
            extras.append(rel)

    meta = manifest.get("meta", {})
    print(f"install:  {install}")
    print(f"manifest: {manifest_path}")
    print(
        f"  game: {meta.get('game', '?')}  "
        f"source: {meta.get('source', '?')}  "
        f"engine: {meta.get('engine_version', '?')}"
    )
    print(
        f"matched: {len(matched)}  "
        f"mismatched: {len(mismatched)}  "
        f"missing: {len(missing)}  "
        f"extras: {len(extras)}  "
        f"skipped: {len(skipped)}"
    )

    if mismatched:
        print("\nMISMATCHED (file present but hash differs):")
        for rel, want, got in mismatched:
            print(f"  {rel}")
            print(f"    expected: {want}")
            print(f"    actual:   {got}")
    if missing:
        print("\nMISSING (manifested file not found):")
        for rel in missing:
            print(f"  {rel}")
    if extras:
        if args.show_extras:
            print("\nEXTRAS (present but not in manifest or runtime_state):")
            for rel in extras:
                print(f"  {rel}")
        else:
            print(f"\n({len(extras)} extras; pass --show-extras to list)")
    if skipped and args.show_skipped:
        print("\nSKIPPED (matched runtime_state pattern):")
        for rel in skipped:
            print(f"  {rel}")

    ok = not mismatched and not missing
    print("\nOK" if ok else "\nFAIL")
    return 0 if ok else 1


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
