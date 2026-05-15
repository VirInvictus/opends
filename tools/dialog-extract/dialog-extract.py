#!/usr/bin/env python3
"""dialog-extract: pull GPL inline strings and text-id references
from a GFF file as JSON.

v0.2.0 consumes `gpl-disasm --json` (gpl-disasm v0.2.0+) instead
of doing a heuristic byte scan. The disassembler decodes each
instruction's parameters in full, so we no longer need to guess
where strings live; we just walk the instruction list and pluck
out string-bearing parameters.

Strings appear in two forms:

1. **Inline literals** — `Expression::ImmediateString` in the
   disassembly. Decoded directly via the 7-bit packed-string
   decoder. These were the v0.1.0 path (with a heuristic prefix
   match).
2. **Text-id references** — `Expression::Variable` with
   `var_kind == "gstring" | "lstring"`. The id resolves against
   `TEXT` chunks in a sibling GFF (typically RESOURCE.GFF for
   global strings). v0.1.0 could not see these at all. Use
   `--text-source <RESOURCE.GFF>` to resolve them.

Output is one record per string with the chunk it lives in,
its offset, the opcode that consumed it, the source (inline vs
text id), and the decoded text.
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

# Opcodes that consume one or more parameters likely to be a
# string (literal or text-id). From docs/gpl-opcodes.md.
STRING_OPCODES = {
    0x2C: "gpl log",            # one packed string (no param)
    0x42: "gpl input string",   # 1 param (the prompt)
    0x48: "gpl menu",           # menu name + entry text on each entry
    0x4F: "gpl print string",   # 2 params (style, text)
    0x5A: "gpl string compare", # 2 params (one is a string)
    0x0A: "gpl string copy",    # 2 params (src, dst)
}

# var_kind values that refer to a text-id (resolvable against
# TEXT chunks in a source GFF).
TEXT_VAR_KINDS = {"gstring", "lstring"}

# Only GSTRING refs resolve against the `--text-source` GFF
# (typically RESOURCE.GFF). LSTRING refs are per-context and
# would resolve against a different source (per-region, per-script
# locals); v0.2.0 surfaces them but leaves them unresolved. The
# engine populates the LSTR table at runtime from contexts we
# don't yet model.
RESOLVABLE_VAR_KINDS = {"gstring"}

# Min printable characters for a decoded inline string to count.
# 7-bit packed strings shorter than this are usually garbage from
# a misaligned read; keep the same threshold as v0.1.0.
MIN_STRING_LEN = 3


def locate_binary(name: str, hint: str | None) -> str | None:
    """Find `name` on $PATH, at the optional hint path, or in
    `<workspace>/target/release/`."""
    candidates = []
    if hint is not None:
        candidates.append(hint)
    candidates.append(name)
    for c in candidates:
        if c and shutil.which(c):
            return c
        if c and Path(c).is_file():
            return c
    candidate = HERE.parent.parent / "target" / "release" / name
    if candidate.is_file():
        return str(candidate)
    return None


def run_gpl_disasm(file: Path, gpl_disasm: str, tmpdir: Path) -> list[dict]:
    """Shell out to `gpl-disasm --all -o tmpdir --json` and load
    every emitted JSON file. Each file describes one GPL/MAS
    chunk. Returns a list of `(chunk_kind, chunk_id, DisasmResult)`."""
    result = subprocess.run(
        [gpl_disasm, str(file), "--all", "-o", str(tmpdir), "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gpl-disasm failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    out: list[dict] = []
    for p in sorted(tmpdir.iterdir()):
        if p.suffix != ".json":
            continue
        stem = p.stem  # e.g. "GPL-7" or "MAS-12"
        kind_prefix, _, id_str = stem.rpartition("-")
        if not kind_prefix or not id_str.isdigit():
            continue
        # FOURCC restore: gpl-disasm strips the trailing space.
        kind_full = (kind_prefix + " ") if len(kind_prefix) == 3 else kind_prefix
        disasm = json.loads(p.read_text())
        out.append(
            {
                "chunk_kind": kind_full,
                "chunk_id": int(id_str),
                "disasm": disasm,
            }
        )
    return out


def load_text_chunks(resource_gff: Path, gff_cat: str) -> dict[int, str]:
    """Pre-load every TEXT chunk from `resource_gff` into a
    `{id: text}` dict. TEXT chunks are short (a single string +
    trailing `\\r\\n`); strip the CRLF for clean JSON output."""
    texts: dict[int, str] = {}
    with tempfile.TemporaryDirectory(prefix="dialog-extract-text-") as tmpdir:
        result = subprocess.run(
            [gff_cat, "extract", "--all", "-o", tmpdir, str(resource_gff)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"gff-cat failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        for p in sorted(Path(tmpdir).iterdir()):
            if not p.stem.startswith("TEXT-"):
                continue
            id_str = p.stem.split("-", 1)[1]
            if not id_str.isdigit():
                continue
            raw = p.read_bytes()
            # Trailing CRLF is the chunk terminator; strip and
            # normalise any internal CRLF to LF for JSON cleanliness.
            text = raw.rstrip(b"\r\n").decode("latin-1", errors="replace")
            text = text.replace("\r\n", "\n")
            texts[int(id_str)] = text
    return texts


def extract_strings_from_instruction(
    instr: dict,
    text_chunks: dict[int, str] | None,
) -> list[dict]:
    """Walk the params of one Instruction and emit one string
    record per string-bearing parameter."""
    out: list[dict] = []
    opcode = instr.get("opcode", 0)
    if opcode not in STRING_OPCODES:
        return out
    op_name = STRING_OPCODES[opcode]
    for param in instr.get("params", []):
        for tok in param:
            kind = tok.get("kind")
            if kind == "immediate_string":
                value = tok.get("value", "")
                if len(value.strip()) < MIN_STRING_LEN and tok.get("sub_type") == "compressed":
                    continue
                out.append(
                    {
                        "offset": instr["offset"],
                        "opcode": opcode,
                        "opcode_name": op_name,
                        "source": "inline",
                        "sub_type": tok.get("sub_type"),
                        "value": value,
                    }
                )
            elif kind == "variable" and tok.get("var_kind") in TEXT_VAR_KINDS:
                var_kind = tok["var_kind"]
                text_id = tok["id"]
                record = {
                    "offset": instr["offset"],
                    "opcode": opcode,
                    "opcode_name": op_name,
                    "source": f"text:{var_kind}",
                    "text_id": text_id,
                }
                resolvable = var_kind in RESOLVABLE_VAR_KINDS
                if (
                    resolvable
                    and text_chunks is not None
                    and text_id in text_chunks
                ):
                    record["value"] = text_chunks[text_id]
                else:
                    record["value"] = None
                    record["unresolved"] = True
                out.append(record)
    return out


def build_summary(
    source: Path,
    disasm_results: list[dict],
    text_chunks: dict[int, str] | None,
    text_source: Path | None,
    grep: re.Pattern[str] | None,
) -> dict:
    chunks_out: list[dict] = []
    total_strings = 0
    total_unresolved = 0

    for entry in disasm_results:
        strings: list[dict] = []
        disasm = entry["disasm"]
        for instr in disasm.get("instructions", []):
            strings.extend(extract_strings_from_instruction(instr, text_chunks))
        if not strings:
            continue
        if grep is not None and not any(
            s.get("value") is not None and grep.search(s["value"]) for s in strings
        ):
            continue
        for s in strings:
            if s.get("unresolved"):
                total_unresolved += 1
        total_strings += len(strings)
        chunks_out.append(
            {
                "chunk": f"{entry['chunk_kind'].strip()}-{entry['chunk_id']}",
                "kind": entry["chunk_kind"],
                "id": entry["chunk_id"],
                "aligned": disasm.get("aligned", False),
                "string_count": len(strings),
                "strings": strings,
            }
        )

    return {
        "tool": "dialog-extract",
        "version": VERSION,
        "source": str(source),
        "method": "gpl-disasm --json consumer",
        "text_source": str(text_source) if text_source is not None else None,
        "text_chunk_count": len(text_chunks) if text_chunks is not None else 0,
        "chunk_count": len(chunks_out),
        "string_count": total_strings,
        "unresolved_count": total_unresolved,
        "chunks": chunks_out,
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
        "--text-source",
        type=Path,
        default=None,
        help="sibling GFF (typically RESOURCE.GFF) whose TEXT chunks resolve "
        "GSTRING / LSTRING references; without this flag, those references "
        "are emitted as `unresolved: true`",
    )
    p.add_argument(
        "--gpl-disasm",
        default=None,
        help="path to gpl-disasm binary (default: $PATH or ../../target/release/gpl-disasm)",
    )
    p.add_argument(
        "--gff-cat",
        default=None,
        help="path to gff-cat binary, used only with --text-source "
        "(default: $PATH or ../../target/release/gff-cat)",
    )
    args = p.parse_args(argv)

    gpl_disasm = locate_binary("gpl-disasm", args.gpl_disasm)
    if gpl_disasm is None:
        print(
            "error: gpl-disasm not found; tried PATH and "
            f"{HERE.parent.parent / 'target' / 'release' / 'gpl-disasm'}. "
            "Pass --gpl-disasm <path> or build it (cargo build -p gpl-disasm --release).",
            file=sys.stderr,
        )
        return 2

    if not args.file.is_file():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2

    text_chunks: dict[int, str] | None = None
    if args.text_source is not None:
        if not args.text_source.is_file():
            print(f"error: --text-source not found: {args.text_source}", file=sys.stderr)
            return 2
        gff_cat = locate_binary("gff-cat", args.gff_cat)
        if gff_cat is None:
            print(
                "error: gff-cat not found; tried PATH and "
                f"{HERE.parent.parent / 'target' / 'release' / 'gff-cat'}. "
                "Pass --gff-cat <path> or build gff-edit.",
                file=sys.stderr,
            )
            return 2
        try:
            text_chunks = load_text_chunks(args.text_source, gff_cat)
        except RuntimeError as e:
            print(f"error: loading text source: {e}", file=sys.stderr)
            return 2

    try:
        with tempfile.TemporaryDirectory(prefix="dialog-extract-disasm-") as tmpdir:
            disasm_results = run_gpl_disasm(args.file, gpl_disasm, Path(tmpdir))
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

    summary = build_summary(
        args.file, disasm_results, text_chunks, args.text_source, grep_re
    )
    indent = 2 if args.pretty else None
    text = json.dumps(summary, indent=indent, ensure_ascii=False)
    if args.output is None:
        sys.stdout.write(text + "\n")
    else:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
