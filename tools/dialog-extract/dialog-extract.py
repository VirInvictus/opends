#!/usr/bin/env python3
"""dialog-extract: pull GPL inline strings and text-id references
from a GFF file as JSON.

v0.3.0 adds a `dialog_tree` field per chunk: a CFG-aware
structured tree that groups strings by their containing basic
block, threads observed speaker-state through the walk, and
synthesizes branches (`if` / `ifcompare`) and loops (`while`)
as nested children. Built on top of gpl-disasm v0.3.1's `cfg`
field. Use case: read the actual dialog flow, see what choices
lead where, locate a particular line within a particular branch
of the script. v0.2.0's flat `strings` list is preserved
unchanged (back-compat).

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

Output per chunk: chunk metadata, the flat `strings` list, and
a `dialog_tree` list (one subtree per entry point).
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

# Opcodes that mutate the engine's "speaker" state. We track them
# during the dialog-tree walk so each line is annotated with the
# observed snapshot of which named-NPC slot was last set. NOT a
# claim about who's actually speaking — just the engine context
# the runtime carries forward. Expand this map as more speaker-
# mutating opcodes are identified.
SPEAKER_OPCODES = {
    0x41: "other",     # gpl setother
    0x49: "thing",     # gpl setthing
}

# Max depth of nested branches in a single dialog tree. Practical
# DS scripts nest 5-6 levels deep at most. The limit guards against
# pathological CFGs (none observed in the corpus).
MAX_TREE_DEPTH = 32


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


def _last_instruction_in_block(block: dict, instr_by_offset: dict[int, dict]) -> dict | None:
    """Return the highest-offset instruction inside `block`'s
    [start_offset, end_offset) range, or None if the block is empty."""
    best: dict | None = None
    for off in range(block["start_offset"], block["end_offset"]):
        if off in instr_by_offset:
            best = instr_by_offset[off]
    return best


def _format_param(param: list[dict]) -> str:
    """Light-weight string rendering of a single parameter
    (list of Expression tokens) for ifcompare case values etc.
    Mirrors gpl-disasm's `write_param_tokens` for common cases."""
    out: list[str] = []
    prev_was_value = False
    for tok in param:
        kind = tok.get("kind")
        is_open = kind == "open_paren"
        is_close = kind == "close_paren"
        is_op = kind == "binary_op"
        if prev_was_value and not is_close and not is_op:
            out.append(" ")
        if kind == "immediate14":
            out.append(str(tok["value"]))
        elif kind == "immediate_byte":
            out.append(f"{tok['value']}i8")
        elif kind == "immediate_bignum":
            out.append(f"{tok['value']}i32")
        elif kind == "immediate_name":
            out.append(f"NAME({tok['value']})")
        elif kind == "immediate_string":
            sub = tok.get("sub_type")
            if sub == "introduce":
                out.append("INTRODUCE")
            elif sub == "uncompressed":
                out.append("UNCOMPRESSED")
            else:
                out.append(f'"{tok.get("value", "")}"')
        elif kind == "variable":
            short = {
                "accm": "ACCUM",
                "lstring": "LSTR",
                "lnum": "LNUM",
                "lbyte": "LBYTE",
                "lname": "LNAME",
                "lbignum": "LBIGNUM",
                "gstring": "GSTR",
                "gnum": "GNUM",
                "gbyte": "GBYTE",
                "gname": "GNAME",
                "gbignum": "GBIGNUM",
                "gflag": "GF",
                "lflag": "LF",
            }.get(tok.get("var_kind", ""), tok.get("var_kind", "?").upper())
            suffix = "+" if tok.get("extended") else ""
            out.append(f"{short}{suffix}[{tok.get('id')}]")
        elif kind == "binary_op":
            out.append(f" {tok.get('op', '?')} ")
        elif kind == "open_paren":
            out.append("(")
        elif kind == "close_paren":
            out.append(")")
        else:
            out.append(f"<{kind}?>")
        prev_was_value = not is_open and not is_op
    return "".join(out)


def _extract_gpl_ref(
    instr: dict,
    labels: dict[str, str],
) -> dict | None:
    """Return a gpl_refs entry for `local sub` (0x13) and
    `global sub` (0x14) instructions, else None."""
    opcode = instr.get("opcode", 0)
    if opcode == 0x13:
        params = instr.get("params") or []
        if not params:
            return None
        target = _literal_target(params[0])
        if target is None:
            return None
        return {
            "kind": "local_sub",
            "at": instr["offset"],
            "target": target,
            "target_label": labels.get(str(target)),
        }
    if opcode == 0x14:
        params = instr.get("params") or []
        if len(params) < 2:
            return None
        target = _literal_target(params[0])
        file_id = _literal_target(params[1])
        if target is None or file_id is None:
            return None
        return {
            "kind": "global_sub",
            "at": instr["offset"],
            "target": target,
            "file_id": file_id,
        }
    return None


def _literal_target(param: list[dict]) -> int | None:
    """Extract a literal integer from a single-token immediate
    param. Returns None for compound expressions, variables, etc."""
    if len(param) != 1:
        return None
    tok = param[0]
    if tok.get("kind") in ("immediate14", "immediate_byte", "immediate_bignum"):
        return int(tok["value"])
    return None


def _update_speaker_state(instr: dict, state: dict[str, str | None]) -> None:
    """Mutate `state` in place to reflect a speaker-setter opcode.
    For unrecognised opcodes the state is unchanged."""
    opcode = instr.get("opcode", 0)
    slot = SPEAKER_OPCODES.get(opcode)
    if slot is None:
        return
    params = instr.get("params") or []
    if not params:
        return
    state[slot] = _format_param(params[0])


def _walk_tree(
    cur: int | None,
    blocks: dict[int, dict],
    instr_by_offset: dict[int, dict],
    labels: dict[str, str],
    text_chunks: dict[int, str] | None,
    speaker_state: dict[str, str | None],
    visited: set[int],
    stop_at: int | None,
    depth: int,
) -> list[dict]:
    """Walk forward from `cur` through CFG blocks. Stops at
    `stop_at`, terminators (Return/ExitScript), previously-visited
    blocks (emits a `revisit` marker), or off-graph offsets. The
    returned list contains one node per visited block; each block
    node may have a synthesized `if` / `ifcompare` / `loop` / `goto`
    child describing its terminator."""
    if depth > MAX_TREE_DEPTH:
        return [{"kind": "depth_cut", "at": cur}]
    nodes: list[dict] = []
    while cur is not None:
        if stop_at is not None and cur == stop_at:
            break
        if cur in visited:
            nodes.append(
                {
                    "kind": "revisit",
                    "target": cur,
                    "target_label": labels.get(str(cur)),
                }
            )
            break
        if cur not in blocks:
            break
        visited.add(cur)
        block = blocks[cur]
        block_node = {
            "kind": "block",
            "offset": cur,
            "label": labels.get(str(cur)),
            "speaker_state_entry": dict(speaker_state),
            "lines": [],
            "gpl_refs": [],
            "terminator": block["terminator"],
            "children": [],
        }
        # Walk this block's instructions: collect strings, refs,
        # and mutate speaker_state in order.
        for off in range(block["start_offset"], block["end_offset"]):
            instr = instr_by_offset.get(off)
            if instr is None:
                continue
            for s in extract_strings_from_instruction(instr, text_chunks):
                s["speaker_state"] = dict(speaker_state)
                block_node["lines"].append(s)
            ref = _extract_gpl_ref(instr, labels)
            if ref is not None:
                block_node["gpl_refs"].append(ref)
            _update_speaker_state(instr, speaker_state)
        nodes.append(block_node)

        term = block["terminator"]
        succ = block.get("successors") or []
        last_instr = _last_instruction_in_block(block, instr_by_offset)
        last_at = last_instr["offset"] if last_instr else cur
        last_opcode = last_instr.get("opcode", 0) if last_instr else 0

        if term in ("Return", "ExitScript"):
            cur = None
        elif term == "Conditional":
            taken = succ[0]["target_offset"] if succ else None
            not_taken = succ[1]["target_offset"] if len(succ) > 1 else None
            if last_opcode == 0x63:  # gpl while
                body = _walk_tree(
                    taken,
                    blocks,
                    instr_by_offset,
                    labels,
                    text_chunks,
                    dict(speaker_state),
                    visited,
                    stop_at=not_taken,
                    depth=depth + 1,
                )
                block_node["children"].append(
                    {
                        "kind": "loop",
                        "at": last_at,
                        "body": body,
                        "join_offset": not_taken,
                    }
                )
                cur = not_taken
            elif last_opcode == 0x27:  # gpl ifcompare
                case_value = (
                    _format_param(last_instr["params"][0])
                    if last_instr and len(last_instr.get("params", [])) >= 1
                    else None
                )
                match_path = _walk_tree(
                    taken,
                    blocks,
                    instr_by_offset,
                    labels,
                    text_chunks,
                    dict(speaker_state),
                    visited,
                    stop_at=stop_at,
                    depth=depth + 1,
                )
                miss_path = _walk_tree(
                    not_taken,
                    blocks,
                    instr_by_offset,
                    labels,
                    text_chunks,
                    dict(speaker_state),
                    visited,
                    stop_at=stop_at,
                    depth=depth + 1,
                )
                block_node["children"].append(
                    {
                        "kind": "ifcompare",
                        "at": last_at,
                        "case_value": case_value,
                        "match": match_path,
                        "miss": miss_path,
                    }
                )
                cur = None
            else:  # gpl if (0x3E)
                then_path = _walk_tree(
                    taken,
                    blocks,
                    instr_by_offset,
                    labels,
                    text_chunks,
                    dict(speaker_state),
                    visited,
                    stop_at=not_taken,
                    depth=depth + 1,
                )
                # Detect if-with-else: the then-path's last block
                # terminator is UnconditionalElse, whose successor
                # is the matching endif (the natural join).
                join = not_taken
                else_path: list[dict] = []
                if then_path:
                    last_then = then_path[-1]
                    if (
                        isinstance(last_then, dict)
                        and last_then.get("kind") == "block"
                        and last_then.get("terminator") == "UnconditionalElse"
                    ):
                        last_block_offset = last_then["offset"]
                        last_block = blocks.get(last_block_offset)
                        if last_block and last_block.get("successors"):
                            join = last_block["successors"][0]["target_offset"]
                            else_path = _walk_tree(
                                not_taken,
                                blocks,
                                instr_by_offset,
                                labels,
                                text_chunks,
                                dict(speaker_state),
                                visited,
                                stop_at=join,
                                depth=depth + 1,
                            )
                block_node["children"].append(
                    {
                        "kind": "if",
                        "at": last_at,
                        "then": then_path,
                        "else": else_path,
                        "join_offset": join,
                    }
                )
                cur = join
        elif term == "Unconditional":
            target = succ[0]["target_offset"] if succ else None
            if last_opcode == 0x64:  # gpl wend — backward edge
                cur = None
            else:  # gpl jump
                block_node["children"].append(
                    {
                        "kind": "goto",
                        "at": last_at,
                        "target": target,
                        "target_label": labels.get(str(target)) if target is not None else None,
                    }
                )
                cur = target
        elif term == "UnconditionalElse":
            # `gpl else`'s own goto to endif. Reached as a
            # continuation of a then-block. Stop here; the
            # post-else continuation is the caller's join.
            cur = None
        elif term == "Fallthrough":
            cur = succ[0]["target_offset"] if succ else None
        else:
            cur = None
    return nodes


def build_dialog_tree(
    disasm: dict,
    text_chunks: dict[int, str] | None,
) -> list[dict]:
    """Build the dialog tree for one chunk's DisasmResult. Returns
    a list of subtrees, one per entry point. Empty list if the
    disassembly was not aligned (CFG absent)."""
    cfg = disasm.get("cfg")
    if cfg is None:
        return []
    blocks_by_offset: dict[int, dict] = {
        b["start_offset"]: b for b in cfg.get("blocks", [])
    }
    instr_by_offset: dict[int, dict] = {
        i["offset"]: i for i in disasm.get("instructions", [])
    }
    # gpl-disasm serialises BTreeMap<usize, String> with usize
    # keys as JSON strings; normalise to int-keyed for lookups.
    labels_raw = cfg.get("labels", {})
    labels: dict[str, str] = {str(k): v for k, v in labels_raw.items()}
    trees: list[dict] = []
    visited: set[int] = set()
    # Walk declared entry points first (chunk start + every offset
    # observed as a `local sub` target).
    for entry_offset in cfg.get("entry_points", []):
        if entry_offset not in blocks_by_offset:
            continue
        if entry_offset in visited:
            continue
        speaker_state: dict[str, str | None] = {"other": None, "thing": None}
        subtree = _walk_tree(
            entry_offset,
            blocks_by_offset,
            instr_by_offset,
            labels,
            text_chunks,
            speaker_state,
            visited,
            stop_at=None,
            depth=0,
        )
        trees.append(
            {
                "entry_offset": entry_offset,
                "entry_label": labels.get(str(entry_offset)),
                "discovered": False,
                "tree": subtree,
            }
        )
    # Some block leaders are not reachable from any declared entry
    # point — typically externally-called functions invoked via
    # `gpl global sub` from another chunk. Walk those too, treating
    # each as a discovered entry. Cross-chunk inter-procedural CFG
    # is v0.4.1 work; here we just expose the locally-unreachable
    # blocks so their dialog is visible.
    for block in cfg.get("blocks", []):
        start = block["start_offset"]
        if start in visited:
            continue
        speaker_state = {"other": None, "thing": None}
        subtree = _walk_tree(
            start,
            blocks_by_offset,
            instr_by_offset,
            labels,
            text_chunks,
            speaker_state,
            visited,
            stop_at=None,
            depth=0,
        )
        if not subtree:
            continue
        trees.append(
            {
                "entry_offset": start,
                "entry_label": labels.get(str(start)),
                "discovered": True,
                "tree": subtree,
            }
        )
    return trees


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
        dialog_tree = build_dialog_tree(disasm, text_chunks)
        chunks_out.append(
            {
                "chunk": f"{entry['chunk_kind'].strip()}-{entry['chunk_id']}",
                "kind": entry["chunk_kind"],
                "id": entry["chunk_id"],
                "aligned": disasm.get("aligned", False),
                "string_count": len(strings),
                "strings": strings,
                "dialog_tree": dialog_tree,
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
