#!/usr/bin/env python3
"""dialog-extract: pull GPL inline strings from a GFF file as JSON.

v0.1.0 heuristic: scans GPL and MAS chunks for `GPL_IMMED_STRING`
markers (0x92 = 0x12 | 0x80, per libgff include/gpl/var.h) and
decodes the strings via a port of soloscuro-archive's
`read_compressed` (src/gpl/gpl-string.c, MIT, Paul E. West et al.).

Limitations and v0.2.0 plan documented in README.md.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text().strip()

# GPL_IMMED_STRING (0x12) with the high bit set, per libgff
# include/gpl/var.h:
#   #define GPL_IMMED_STRING (0x12)
# Used as `GPL_IMMED_STRING | 0x80` = 0x92 in the gpl_read_number
# dispatch switch (libgff src/gpl/parse.c).
IMMED_STRING_MARKER = 0x92

# Sub-type markers inside an IMMED_STRING block. From
# soloscuro-archive src/gpl/gpl-string.c:
#   #define INTRODUCE           (0x01)
#   #define STRING_UNCOMPRESSED (0x02)
#   #define STRING_COMPRESSED   (0x05)
INTRODUCE = 0x01
STRING_UNCOMPRESSED = 0x02
STRING_COMPRESSED = 0x05

# 7-bit packed-string terminator.
TERMINATOR = 0x03

# Reject decoded strings shorter than this many characters; cuts
# heuristic noise (random param bytes that happen to look like a
# marker decode to short runs of spaces).
MIN_STRING_LEN = 3

# Cap on output string length, matching soloscuro's TEXTSTRINGSIZE.
MAX_STRING_LEN = 1023


def decode_compressed_string(buf: bytes, start: int) -> tuple[str | None, int]:
    """Decode a 7-bit packed string at buf[start]. Returns
    `(decoded_or_None, bytes_consumed)`. Ported from
    soloscuro-archive `src/gpl/gpl-string.c` `read_compressed`.

    The format: a sliding 16-bit window over the byte stream.
    `idx` cycles 1, 2, 3, 4, 5, 6, 7, 0, repeating; on each
    iteration (idx > 0) load a new byte into the low half of the
    window, then extract 7 bits at position `idx`. On idx == 0,
    skip the load and use the remaining bits of the most-recent
    byte. 7 input bytes yield 8 output characters per cycle. 0x03
    terminates the string. Non-printable decoded chars are
    replaced with space.
    """
    chars: list[str] = []
    buffer = 0
    idx = 1
    i = start
    while len(chars) < MAX_STRING_LEN and i < len(buf):
        if idx > 0:
            buffer = (buffer << 8) & 0xFF00
            buffer |= buf[i]
            i += 1
        ch = (buffer >> idx) & 0x7F
        if ch == TERMINATOR:
            return "".join(chars), i - start
        if ch < 0x20 or ch > 0x7E:
            ch = 0x20
        chars.append(chr(ch))
        idx += 1
        if idx > 7:
            idx = 0
    return None, i - start


def find_strings_in_chunk(payload: bytes) -> list[dict]:
    """Heuristic scan of a single chunk's bytes for IMMED_STRING
    markers. Returns a list of `{offset, type, string}` dicts."""
    out: list[dict] = []
    i = 0
    while i < len(payload) - 1:
        if payload[i] != IMMED_STRING_MARKER:
            i += 1
            continue
        sub = payload[i + 1]
        if sub == INTRODUCE:
            out.append(
                {
                    "offset": i,
                    "type": "INTRODUCE",
                    "string": "<active_character_name>",
                }
            )
            i += 2
            continue
        if sub == STRING_UNCOMPRESSED:
            out.append(
                {
                    "offset": i,
                    "type": "UNCOMPRESSED",
                    "string": "<uncompressed string; decoder not yet implemented>",
                }
            )
            i += 2
            continue
        if sub == STRING_COMPRESSED:
            decoded, consumed = decode_compressed_string(payload, i + 2)
            if decoded is not None and len(decoded.strip()) >= MIN_STRING_LEN:
                out.append(
                    {
                        "offset": i,
                        "type": "COMPRESSED",
                        "string": decoded,
                    }
                )
                i += 2 + consumed
                continue
        i += 1
    return out


def locate_gff_cat(hint: str) -> str | None:
    """Find gff-cat: on $PATH, at the hint path, or relative to
    this script's workspace target/release/gff-cat."""
    if shutil.which(hint):
        return hint
    if Path(hint).is_file():
        return hint
    # Try ../../target/release/gff-cat relative to this script.
    candidate = HERE.parent.parent / "target" / "release" / "gff-cat"
    if candidate.is_file():
        return str(candidate)
    return None


def extract_gpl_mas_chunks(gff_path: Path, gff_cat: str) -> dict[str, bytes]:
    """Use gff-cat extract --all to dump all chunks to a tmpdir,
    then read back only GPL-*.bin and MAS-*.bin files."""
    chunks: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="dialog-extract-") as tmpdir:
        result = subprocess.run(
            [gff_cat, "extract", "--all", "-o", tmpdir, str(gff_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"gff-cat failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        for p in sorted(Path(tmpdir).iterdir()):
            stem = p.stem
            if not (stem.startswith("GPL-") or stem.startswith("MAS-")):
                continue
            chunks[stem] = p.read_bytes()
    return chunks


def build_summary(
    source: Path,
    chunks: dict[str, bytes],
    grep: re.Pattern[str] | None,
) -> dict:
    results: list[dict] = []
    total_strings = 0
    for chunk_name, payload in chunks.items():
        strings = find_strings_in_chunk(payload)
        if not strings:
            continue
        if grep is not None and not any(grep.search(s["string"]) for s in strings):
            continue
        kind_prefix, id_str = chunk_name.rsplit("-", 1)
        # gff-cat's filename strips trailing spaces from the FOURCC; e.g.
        # the chunk kind "GPL " becomes "GPL-7.bin". Restore the trailing
        # space for the JSON output so the kind field matches FOURCC.
        kind_full = (kind_prefix + " ") if len(kind_prefix) == 3 else kind_prefix
        results.append(
            {
                "chunk": chunk_name,
                "kind": kind_full,
                "id": int(id_str),
                "string_count": len(strings),
                "strings": strings,
            }
        )
        total_strings += len(strings)

    return {
        "tool": "dialog-extract",
        "version": VERSION,
        "source": str(source),
        "method": "heuristic IMMED_STRING scan + 7-bit decoder",
        "chunk_count": len(results),
        "string_count": total_strings,
        "chunks": results,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="dialog-extract",
        description=__doc__.strip().splitlines()[0],
    )
    p.add_argument(
        "--version", action="version", version=f"dialog-extract {VERSION}"
    )
    p.add_argument("file", type=Path, help="GFF file (typically GPLDATA.GFF)")
    p.add_argument(
        "-o", "--output", type=Path, default=None, help="write JSON to file (default stdout)"
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print JSON output (2-space indent)",
    )
    p.add_argument(
        "--grep",
        default=None,
        help="filter: include only chunks with at least one string matching this regex",
    )
    p.add_argument(
        "--gff-cat",
        default="gff-cat",
        help="path to gff-cat binary (default: $PATH or ../../target/release/gff-cat)",
    )
    args = p.parse_args(argv)

    gff_cat = locate_gff_cat(args.gff_cat)
    if gff_cat is None:
        print(
            f"error: gff-cat not found; tried PATH and "
            f"{HERE.parent.parent / 'target' / 'release' / 'gff-cat'}. "
            "Pass --gff-cat <path> or build gff-edit (cargo build -p gff-edit --release).",
            file=sys.stderr,
        )
        return 2

    if not args.file.is_file():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2

    try:
        chunks = extract_gpl_mas_chunks(args.file, gff_cat)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    grep_re: re.Pattern[str] | None = None
    if args.grep is not None:
        try:
            grep_re = re.compile(args.grep)
        except re.error as e:
            print(f"error: bad --grep regex: {e}", file=sys.stderr)
            return 2

    summary = build_summary(args.file, chunks, grep_re)
    indent = 2 if args.pretty else None
    text = json.dumps(summary, indent=indent, ensure_ascii=False)
    if args.output is None:
        sys.stdout.write(text + "\n")
    else:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
