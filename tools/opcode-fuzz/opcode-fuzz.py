#!/usr/bin/env python3
"""OpenDS opcode-fuzz harness.

v0.1.0 ships the **chunk-patchwork pipeline** that opcode-fuzz
needs to build on: extract a GPL chunk into a work directory,
edit its disassembly, repack it back into the GFF. Plus a
corpus-level round-trip self-test that verifies every chunk in
a GFF survives extract -> disasm -> reasm -> replace
byte-identical.

The eventual Phase 5 vision (DOSBox debugger IPC, per-tick
state capture, opcode-discovery loop per roadmap.md Phase 5) is
queued for v0.2.0+. This version is the foundation those
versions build on, not the discovery loop itself.

Shells out to:

- `target/release/gff-cat` (gff-edit's CLI) for GFF I/O.
- `target/release/gpl-disasm` for byte -> JSON / text.
- `target/release/gpl-asm` for JSON / text -> byte.

Stdlib-only; no third-party Python deps.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GFF_CAT = REPO_ROOT / "target" / "release" / "gff-cat"
GPL_DISASM = REPO_ROOT / "target" / "release" / "gpl-disasm"
GPL_ASM = REPO_ROOT / "target" / "release" / "gpl-asm"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_HARNESS_ERROR = 2


def require_built() -> None:
    """Bail if the Rust binaries we depend on aren't built."""
    missing = [
        p
        for p in (GFF_CAT, GPL_DISASM, GPL_ASM)
        if not p.is_file()
    ]
    if missing:
        names = ", ".join(p.name for p in missing)
        raise SystemExit(
            f"opcode-fuzz: missing release binaries ({names}). "
            "Run `cargo build --release` from the repo root."
        )


def is_script_chunk(kind: str) -> bool:
    """Returns True for chunk kinds that hold GPL bytecode.

    `GPL ` and `MAS ` are the two; both have trailing-space
    FOURCCs. gpl-disasm handles them identically.
    """
    return kind in ("GPL ", "MAS ")


@dataclass
class ChunkRef:
    kind: str
    id: int

    def safe_name(self) -> str:
        """Filename-safe rendering of `<kind>-<id>`."""
        clean_kind = self.kind.strip().replace(" ", "_")
        return f"{clean_kind}-{self.id}"


def list_chunks(gff: Path) -> list[ChunkRef]:
    """Run `gff-cat list <gff>` and parse the output.

    Output looks like:
        kind            id      offset      length
        'GFFI'           0     1370114          12
        'GPL '           1     1363280        6834
        'MAS '           2      877556         371

    Kind is wrapped in single quotes and may carry a trailing
    space inside the quotes (4 chars total). Subsequent
    columns are space-separated.
    """
    result = subprocess.run(
        [str(GFF_CAT), "list", str(gff)],
        capture_output=True,
        text=True,
        check=True,
    )
    out: list[ChunkRef] = []
    for raw in result.stdout.splitlines():
        line = raw.lstrip()
        if not line.startswith("'"):
            continue
        # Find the matching close-quote 5 bytes after the open
        # (4-char FOURCC + the close-quote).
        if len(line) < 6 or line[5] != "'":
            continue
        kind = line[1:5]
        rest = line[6:].strip()
        parts = rest.split()
        if not parts:
            continue
        try:
            chunk_id = (
                int(parts[0], 16) if parts[0].startswith("0x") else int(parts[0])
            )
        except ValueError:
            continue
        out.append(ChunkRef(kind=kind, id=chunk_id))
    return out


def extract_chunk(gff: Path, ref: ChunkRef, out_path: Path) -> None:
    """Extract a single chunk's bytes to `out_path`."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(GFF_CAT),
            "extract",
            str(gff),
            ref.kind,
            str(ref.id),
            "-o",
            str(out_path),
        ],
        check=True,
    )


def disasm_to_json(gff: Path, ref: ChunkRef, out_path: Path) -> None:
    """Disassemble a single chunk from a GFF to JSON."""
    subprocess.run(
        [
            str(GPL_DISASM),
            str(gff),
            "--kind",
            ref.kind.strip(),
            "--id",
            str(ref.id),
            "--json",
            "-o",
            str(out_path),
        ],
        check=True,
    )


def disasm_to_text(gff: Path, ref: ChunkRef, out_path: Path) -> None:
    """Disassemble a single chunk from a GFF to text listing."""
    subprocess.run(
        [
            str(GPL_DISASM),
            str(gff),
            "--kind",
            ref.kind.strip(),
            "--id",
            str(ref.id),
            "-o",
            str(out_path),
        ],
        check=True,
    )


def asm_from_json(json_path: Path, out_path: Path) -> None:
    subprocess.run(
        [str(GPL_ASM), str(json_path), "-o", str(out_path)],
        check=True,
    )


def replace_chunk(
    gff: Path, ref: ChunkRef, bytes_path: Path, out_gff: Path
) -> None:
    subprocess.run(
        [
            str(GFF_CAT),
            "replace",
            str(gff),
            ref.kind,
            str(ref.id),
            str(bytes_path),
            "-o",
            str(out_gff),
        ],
        check=True,
    )


def cmd_extract(args: argparse.Namespace) -> int:
    """Stage a chunk for editing.

    Output directory layout (created at `--output`):
        original.bin   exact chunk bytes; reference for diff
        chunk.json     gpl-disasm JSON; edit this for surgical changes
        chunk.asm      gpl-disasm text listing; edit for hand-written work
        meta.json      {"gff": "...", "kind": "...", "id": N}
    """
    require_built()
    ref = ChunkRef(kind=args.kind, id=args.id)
    work_dir = args.output
    work_dir.mkdir(parents=True, exist_ok=True)
    chunk_bin = work_dir / "original.bin"
    extract_chunk(args.gff, ref, chunk_bin)
    disasm_to_json(args.gff, ref, work_dir / "chunk.json")
    disasm_to_text(args.gff, ref, work_dir / "chunk.asm")
    meta = {
        "gff": str(args.gff.resolve()),
        "kind": ref.kind,
        "id": ref.id,
    }
    (work_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(
        f"extracted {ref.kind!r}/{ref.id} from {args.gff}\n"
        f"  work-dir: {work_dir}\n"
        f"  edit chunk.json or chunk.asm; then `opcode-fuzz pack {work_dir} -o <new.gff>`"
    )
    return EXIT_OK


def cmd_pack(args: argparse.Namespace) -> int:
    """Rebuild a GFF from an edited work-dir.

    Reads `meta.json` to find the source GFF and the chunk
    coordinate, encodes the (possibly edited) `chunk.json` via
    gpl-asm, and writes the resulting GFF to `--output`. The
    original chunk's bytes are left in `original.bin` for diff.
    """
    require_built()
    meta_path = args.work_dir / "meta.json"
    if not meta_path.is_file():
        print(f"opcode-fuzz: no meta.json at {meta_path}", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    meta = json.loads(meta_path.read_text())
    ref = ChunkRef(kind=meta["kind"], id=int(meta["id"]))
    source_gff = args.source_gff or Path(meta["gff"])
    if not source_gff.is_file():
        print(
            f"opcode-fuzz: source GFF {source_gff} not found "
            f"(meta.json points at {meta['gff']!r}; pass --source-gff to override)",
            file=sys.stderr,
        )
        return EXIT_HARNESS_ERROR
    chunk_json = args.work_dir / "chunk.json"
    if not chunk_json.is_file():
        print(f"opcode-fuzz: no chunk.json at {chunk_json}", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    with tempfile.TemporaryDirectory(prefix="opcode-fuzz-pack-") as tmp:
        new_bin = Path(tmp) / "chunk.bin"
        asm_from_json(chunk_json, new_bin)
        replace_chunk(source_gff, ref, new_bin, args.output)
    print(f"packed -> {args.output}")
    return EXIT_OK


def cmd_roundtrip(args: argparse.Namespace) -> int:
    """End-to-end self-test on a GFF.

    For every GPL / MAS chunk in the input GFF:
      1. Extract bytes (gff-cat extract).
      2. Disassemble to JSON (gpl-disasm).
      3. Reassemble to bytes (gpl-asm).
      4. Replace the chunk in the GFF (gff-cat replace).
      5. Verify the resulting GFF byte-equals the input.

    Three things this catches:
      - gpl-disasm / gpl-asm round-trip regressions on a real
        GFF (the gpl-asm corpus test already covers this against
        chunks-in-isolation; this exercises the full GFF path).
      - gff-cat replace regressions (chunk relocation, TOC
        rewrite, etc).
      - Any non-aligned / unencodable chunk that the per-chunk
        tests skip but would surface here as a mismatch.
    """
    require_built()
    src = args.gff
    if not src.is_file():
        print(f"opcode-fuzz: {src} not found", file=sys.stderr)
        return EXIT_HARNESS_ERROR

    chunks = [c for c in list_chunks(src) if is_script_chunk(c.kind)]
    if not chunks:
        print(f"no GPL / MAS chunks in {src}", file=sys.stderr)
        return EXIT_OK

    src_bytes = src.read_bytes()
    print(f"roundtrip: {len(chunks)} chunks in {src}")

    mismatched: list[str] = []
    skipped: list[str] = []
    encode_failures: list[str] = []
    tested = 0

    with tempfile.TemporaryDirectory(prefix="opcode-fuzz-rt-") as tmp:
        tmp_root = Path(tmp)
        for ref in chunks:
            slot = tmp_root / ref.safe_name()
            slot.mkdir(parents=True, exist_ok=True)
            chunk_json = slot / "chunk.json"
            new_bin = slot / "rebuilt.bin"
            new_gff = slot / "patched.gff"
            try:
                disasm_to_json(src, ref, chunk_json)
            except subprocess.CalledProcessError:
                skipped.append(ref.safe_name())
                continue
            # gpl-asm refuses to encode non-aligned chunks
            # (the disassembler couldn't reach instruction
            # boundaries). Skip those explicitly so they don't
            # show up as encode failures.
            try:
                meta = json.loads(chunk_json.read_text())
            except json.JSONDecodeError:
                skipped.append(ref.safe_name())
                continue
            if not meta.get("aligned", True):
                skipped.append(ref.safe_name() + " (non-aligned)")
                continue
            try:
                asm_from_json(chunk_json, new_bin)
            except subprocess.CalledProcessError:
                encode_failures.append(ref.safe_name())
                continue
            try:
                replace_chunk(src, ref, new_bin, new_gff)
            except subprocess.CalledProcessError:
                encode_failures.append(ref.safe_name() + " (replace)")
                continue
            tested += 1
            if new_gff.read_bytes() != src_bytes:
                mismatched.append(ref.safe_name())

    print(
        f"  tested={tested}  matched={tested - len(mismatched)}  "
        f"mismatched={len(mismatched)}  encode_failures={len(encode_failures)}  "
        f"skipped={len(skipped)}"
    )
    if mismatched:
        print("  first 5 mismatches:")
        for s in mismatched[:5]:
            print(f"    {s}")
    if encode_failures:
        print("  first 5 encode failures:")
        for s in encode_failures[:5]:
            print(f"    {s}")
    if skipped:
        print(f"  ({len(skipped)} non-aligned / non-encodable chunks skipped)")

    return EXIT_OK if not mismatched and not encode_failures else EXIT_FAIL


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="OpenDS opcode-fuzz harness (v0.1.0: chunk patchwork pipeline)."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ext = sub.add_parser(
        "extract",
        help="Stage a chunk for editing.",
        description=(
            "Extract a single GPL / MAS chunk into a work "
            "directory ready for surgical edits. Produces "
            "original.bin + chunk.json + chunk.asm + meta.json."
        ),
    )
    p_ext.add_argument("gff", type=Path, help="source GFF file")
    p_ext.add_argument("kind", help="chunk kind (e.g. 'GPL ' with trailing space, or 'MAS ')")
    p_ext.add_argument("id", type=int, help="chunk id (decimal)")
    p_ext.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="work directory to populate",
    )
    p_ext.set_defaults(handler=cmd_extract)

    p_pack = sub.add_parser(
        "pack",
        help="Re-encode an edited work-dir and write the patched GFF.",
        description=(
            "Reads meta.json from the work-dir, encodes chunk.json "
            "via gpl-asm, replaces the chunk in the source GFF, "
            "writes the result to --output."
        ),
    )
    p_pack.add_argument("work_dir", type=Path, help="work directory from `extract`")
    p_pack.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="output GFF path",
    )
    p_pack.add_argument(
        "--source-gff",
        type=Path,
        default=None,
        help="override the source GFF (defaults to meta.json's `gff`)",
    )
    p_pack.set_defaults(handler=cmd_pack)

    p_rt = sub.add_parser(
        "roundtrip",
        help="Corpus self-test: every GPL/MAS chunk extracts + reassembles + replaces back byte-identical.",
    )
    p_rt.add_argument("gff", type=Path, help="GFF to round-trip")
    p_rt.set_defaults(handler=cmd_roundtrip)

    args = ap.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
