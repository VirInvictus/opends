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

# GSTRING refs resolve against the `--text-source` GFF (typically
# RESOURCE.GFF). LSTRING refs are 1 of 10 runtime "local string"
# slots (`MAXLSTRINGS = 10` per libgff `include/gff/str.h`)
# populated by `gpl_string_copy` (0x0A) writes inside each chunk;
# v0.4.0 tracks those writes path-by-path and resolves reads to
# the most-recently-written source on the active path.
RESOLVABLE_VAR_KINDS = {"gstring", "lstring"}

# Number of LSTR slots tracked by the runtime. Matches libgff
# `include/gff/str.h` `MAXLSTRINGS`.
MAX_LSTR_SLOTS = 10

# Opcode that writes into an LSTR variable: `gpl_string_copy`
# (0x0A). `param[0]` is the destination (LSTR variable),
# `param[1]` is the source (inline literal in 96-97% of corpus
# occurrences, occasionally a chained variable read). Empirically
# confirmed during v0.4.0 RE; see `patchnotes.md` for the survey.
LSTR_WRITER_OPCODE = 0x0A

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
    lstr_state: dict[int, dict] | None = None,
) -> list[dict]:
    """Walk the params of one Instruction and emit one string
    record per string-bearing parameter.

    `lstr_state` is the path-local LSTR-slot snapshot at this
    instruction. When set, LSTRING reads in string-bearing
    opcodes resolve against it; when None (e.g. flat-list mode
    that doesn't simulate a CFG walk), LSTRING reads stay
    unresolved with the v0.3.0 shape.
    """
    out: list[dict] = []
    opcode = instr.get("opcode", 0)
    if opcode not in STRING_OPCODES:
        return out
    op_name = STRING_OPCODES[opcode]
    params = instr.get("params", []) or []
    for idx, param in enumerate(params):
        # `gpl_string_copy` (0x0A) has param[0] = LSTR destination
        # (a write target, not a string-bearing read) and
        # param[1] = the source string. v0.3.0 emitted the
        # destination as an "unresolved LSTRING ref"; skip it.
        if opcode == LSTR_WRITER_OPCODE and idx == 0:
            continue
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
                record: dict = {
                    "offset": instr["offset"],
                    "opcode": opcode,
                    "opcode_name": op_name,
                    "source": f"text:{var_kind}",
                    "text_id": text_id,
                }
                resolved_value: str | None = None
                if var_kind == "gstring":
                    if text_chunks is not None and text_id in text_chunks:
                        resolved_value = text_chunks[text_id]
                elif var_kind == "lstring":
                    resolved_value = _resolve_lstr_read(
                        text_id, lstr_state, text_chunks
                    )
                if resolved_value is not None:
                    record["value"] = resolved_value
                else:
                    record["value"] = None
                    record["unresolved"] = True
                out.append(record)
    return out


def _resolve_lstr_read(
    lstr_id: int,
    lstr_state: dict[int, dict] | None,
    text_chunks: dict[int, str] | None,
    _seen: set[int] | None = None,
) -> str | None:
    """Resolve one LSTR slot read against the path-local
    `lstr_state` snapshot. Returns the source string when it can
    be determined statically, else None.

    Handles three source kinds recorded by `_update_lstr_state`:

    - `inline`: the slot was written from an `immediate_string`.
    - `gstring`: the slot was written from a GSTRING variable;
      recurse into `text_chunks` if a text source was supplied.
    - `lstring`: the slot was written from another LSTR slot
      (chained); recurse with cycle protection.

    Anything else (computed-from-record, accumulator, etc.) is
    unresolvable today.
    """
    if lstr_state is None:
        return None
    record = lstr_state.get(lstr_id)
    if record is None:
        return None
    kind = record.get("kind")
    if kind == "inline":
        return record.get("value")
    if kind == "gstring":
        text_id = record.get("text_id")
        if text_id is None or text_chunks is None:
            return None
        return text_chunks.get(text_id)
    if kind == "lstring":
        chained_id = record.get("source_id")
        if chained_id is None:
            return None
        seen = _seen if _seen is not None else set()
        if chained_id in seen:
            return None
        seen.add(chained_id)
        return _resolve_lstr_read(chained_id, lstr_state, text_chunks, seen)
    return None


def _update_lstr_state(instr: dict, lstr_state: dict[int, dict]) -> None:
    """Mutate `lstr_state` in place when `instr` writes to an LSTR
    slot. Recognises `gpl_string_copy` (0x0A) with `param[0]` = LSTR
    variable. Sources are classified into:

    - `inline`: param[1] is an `immediate_string`. The literal value
      is captured for direct resolution.
    - `gstring`: param[1] is a `gstring` variable; the text id is
      captured for later resolution against `text_chunks`.
    - `lstring`: param[1] is another `lstring` variable; the source
      slot id is captured for chained resolution.
    - `computed`: anything else (accumulator math, complex record
      access, etc.). Recorded so the slot doesn't silently fall back
      to an older value; reads resolve to `None` (unresolved).
    """
    if instr.get("opcode") != LSTR_WRITER_OPCODE:
        return
    params = instr.get("params") or []
    if len(params) < 2:
        return
    dst = params[0]
    src = params[1]
    if len(dst) != 1:
        return
    dst_tok = dst[0]
    if dst_tok.get("kind") != "variable" or dst_tok.get("var_kind") != "lstring":
        return
    lstr_id = dst_tok.get("id")
    if lstr_id is None:
        return
    record: dict = {"kind": "computed", "src_offset": instr.get("offset")}
    if len(src) == 1:
        s0 = src[0]
        s_kind = s0.get("kind")
        if s_kind == "immediate_string":
            record = {
                "kind": "inline",
                "value": s0.get("value", ""),
                "sub_type": s0.get("sub_type"),
                "src_offset": instr.get("offset"),
            }
        elif s_kind == "variable" and s0.get("var_kind") == "gstring":
            record = {
                "kind": "gstring",
                "text_id": s0.get("id"),
                "src_offset": instr.get("offset"),
            }
        elif s_kind == "variable" and s0.get("var_kind") == "lstring":
            record = {
                "kind": "lstring",
                "source_id": s0.get("id"),
                "src_offset": instr.get("offset"),
            }
    lstr_state[lstr_id] = record


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
    lstr_state: dict[int, dict],
    visited: set[int],
    stop_at: int | None,
    depth: int,
    chunks_by_kind_id: dict[tuple[str, int], dict] | None = None,
    chunk_kind: str | None = None,
    chunk_id: int | None = None,
    cross_chunk_visited: set[tuple[str, int]] | None = None,
) -> list[dict]:
    """Walk forward from `cur` through CFG blocks. Stops at
    `stop_at`, terminators (Return/ExitScript), previously-visited
    blocks (emits a `revisit` marker), or off-graph offsets. The
    returned list contains one node per visited block; each block
    node may have a synthesized `if` / `ifcompare` / `loop` / `goto`
    child describing its terminator.

    `lstr_state` carries per-path LSTR slot assignments
    (`{id: {"kind": "inline"|"gstring"|"lstring"|"computed", ...}}`)
    accumulated along the walk. At branch points each path gets a
    `dict(lstr_state)` shallow copy; updates from
    `gpl_string_copy` writes are local to that path.

    If `chunks_by_kind_id` is set, `gpl global sub` call sites
    inside each block expand inline as a `cross_chunk_call`
    subtree under the block's `children`. `cross_chunk_visited`
    is the chunk-level cycle guard (set of `(kind, id)` already
    on the active call chain)."""
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
            "lstr_state_entry": dict(lstr_state),
            "lines": [],
            "gpl_refs": [],
            "terminator": block["terminator"],
            "children": [],
        }
        # Walk this block's instructions: collect strings, refs,
        # and mutate speaker_state + lstr_state in order. Updates
        # are applied AFTER string extraction at each instruction
        # so a `gpl_string_copy` write inside a block doesn't
        # retroactively resolve its own destination as a "read".
        for off in range(block["start_offset"], block["end_offset"]):
            instr = instr_by_offset.get(off)
            if instr is None:
                continue
            for s in extract_strings_from_instruction(
                instr, text_chunks, lstr_state
            ):
                s["speaker_state"] = dict(speaker_state)
                block_node["lines"].append(s)
            ref = _extract_gpl_ref(instr, labels)
            if ref is not None:
                block_node["gpl_refs"].append(ref)
            _update_speaker_state(instr, speaker_state)
            _update_lstr_state(instr, lstr_state)
        # Cross-chunk expansion (inter-chunk walking): for every
        # `global sub` ref in this block, inline the callee's
        # subtree under the block's children. The current path's
        # LSTR state is passed through (the engine LSTR table is
        # global; callees see what the caller has set up).
        if chunks_by_kind_id is not None:
            for ref in block_node["gpl_refs"]:
                if ref.get("kind") != "global_sub":
                    continue
                callee_subtree = _expand_cross_chunk_call(
                    ref,
                    blocks,
                    instr_by_offset,
                    labels,
                    text_chunks,
                    speaker_state,
                    lstr_state,
                    chunks_by_kind_id,
                    chunk_kind,
                    chunk_id,
                    cross_chunk_visited,
                    depth,
                )
                if callee_subtree is not None:
                    block_node["children"].append(callee_subtree)
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
                    dict(lstr_state),
                    visited,
                    stop_at=not_taken,
                    depth=depth + 1,
                    chunks_by_kind_id=chunks_by_kind_id,
                    chunk_kind=chunk_kind,
                    chunk_id=chunk_id,
                    cross_chunk_visited=cross_chunk_visited,
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
                    dict(lstr_state),
                    visited,
                    stop_at=stop_at,
                    depth=depth + 1,
                    chunks_by_kind_id=chunks_by_kind_id,
                    chunk_kind=chunk_kind,
                    chunk_id=chunk_id,
                    cross_chunk_visited=cross_chunk_visited,
                )
                miss_path = _walk_tree(
                    not_taken,
                    blocks,
                    instr_by_offset,
                    labels,
                    text_chunks,
                    dict(speaker_state),
                    dict(lstr_state),
                    visited,
                    stop_at=stop_at,
                    depth=depth + 1,
                    chunks_by_kind_id=chunks_by_kind_id,
                    chunk_kind=chunk_kind,
                    chunk_id=chunk_id,
                    cross_chunk_visited=cross_chunk_visited,
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
                    dict(lstr_state),
                    visited,
                    stop_at=not_taken,
                    depth=depth + 1,
                    chunks_by_kind_id=chunks_by_kind_id,
                    chunk_kind=chunk_kind,
                    chunk_id=chunk_id,
                    cross_chunk_visited=cross_chunk_visited,
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
                                dict(lstr_state),
                                visited,
                                stop_at=join,
                                depth=depth + 1,
                                chunks_by_kind_id=chunks_by_kind_id,
                                chunk_kind=chunk_kind,
                                chunk_id=chunk_id,
                                cross_chunk_visited=cross_chunk_visited,
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


def _expand_cross_chunk_call(
    ref: dict,
    caller_blocks: dict[int, dict],
    caller_instr_by_offset: dict[int, dict],
    caller_labels: dict[str, str],
    text_chunks: dict[int, str] | None,
    speaker_state: dict[str, str | None],
    lstr_state: dict[int, dict],
    chunks_by_kind_id: dict[tuple[str, int], dict],
    caller_kind: str | None,
    caller_id: int | None,
    cross_chunk_visited: set[tuple[str, int]] | None,
    depth: int,
) -> dict | None:
    """Build a `cross_chunk_call` subtree for one `global sub`
    reference. Resolves the target's chunk via `chunks_by_kind_id`
    using `(kind, file_id)`; if the callee is missing (e.g. not
    in the same GFF or not aligned), emits an unresolved marker
    instead of a recursive walk.

    The caller's `lstr_state` and `speaker_state` flow into the
    callee (shallow copies; the engine's LSTR table is global,
    and observed speaker state is engine-wide too). Modifications
    inside the callee do NOT propagate back: the call site loses
    its post-return state on purpose, since dialog-extract is not
    a runtime simulator and over-claiming would be misleading."""
    if depth > MAX_TREE_DEPTH:
        return {
            "kind": "cross_chunk_call",
            "at": ref.get("at"),
            "target_offset": ref.get("target"),
            "target_file_id": ref.get("file_id"),
            "unresolved": True,
            "reason": "depth_cut",
        }
    target_offset = ref.get("target")
    target_file_id = ref.get("file_id")
    if target_offset is None or target_file_id is None:
        return None
    # The `file_id` in `gpl global sub` is the resource id of the
    # target chunk; the kind matches the caller's (GPL/MAS both
    # use the same call space).
    target_kind = caller_kind
    if target_kind is None:
        return None
    target_key = (target_kind, target_file_id)
    if cross_chunk_visited is not None and target_key in cross_chunk_visited:
        return {
            "kind": "cross_chunk_call",
            "at": ref.get("at"),
            "target_chunk": f"{target_kind.strip()}-{target_file_id}",
            "target_offset": target_offset,
            "target_file_id": target_file_id,
            "unresolved": True,
            "reason": "cycle",
        }
    callee_disasm = chunks_by_kind_id.get(target_key)
    if callee_disasm is None:
        return {
            "kind": "cross_chunk_call",
            "at": ref.get("at"),
            "target_chunk": f"{target_kind.strip()}-{target_file_id}",
            "target_offset": target_offset,
            "target_file_id": target_file_id,
            "unresolved": True,
            "reason": "callee_not_loaded",
        }
    callee_cfg = callee_disasm.get("cfg")
    if callee_cfg is None:
        return {
            "kind": "cross_chunk_call",
            "at": ref.get("at"),
            "target_chunk": f"{target_kind.strip()}-{target_file_id}",
            "target_offset": target_offset,
            "target_file_id": target_file_id,
            "unresolved": True,
            "reason": "callee_unaligned",
        }
    callee_blocks: dict[int, dict] = {
        b["start_offset"]: b for b in callee_cfg.get("blocks", [])
    }
    callee_instr_by_offset: dict[int, dict] = {
        i["offset"]: i for i in callee_disasm.get("instructions", [])
    }
    callee_labels_raw = callee_cfg.get("labels", {})
    callee_labels: dict[str, str] = {
        str(k): v for k, v in callee_labels_raw.items()
    }
    if target_offset not in callee_blocks:
        return {
            "kind": "cross_chunk_call",
            "at": ref.get("at"),
            "target_chunk": f"{target_kind.strip()}-{target_file_id}",
            "target_offset": target_offset,
            "target_file_id": target_file_id,
            "unresolved": True,
            "reason": "target_offset_not_a_block_leader",
        }
    new_visited: set[tuple[str, int]] = (
        set(cross_chunk_visited) if cross_chunk_visited is not None else set()
    )
    new_visited.add(target_key)
    callee_visited: set[int] = set()
    subtree = _walk_tree(
        target_offset,
        callee_blocks,
        callee_instr_by_offset,
        callee_labels,
        text_chunks,
        dict(speaker_state),
        dict(lstr_state),
        callee_visited,
        stop_at=None,
        depth=depth + 1,
        chunks_by_kind_id=chunks_by_kind_id,
        chunk_kind=target_kind,
        chunk_id=target_file_id,
        cross_chunk_visited=new_visited,
    )
    return {
        "kind": "cross_chunk_call",
        "at": ref.get("at"),
        "target_chunk": f"{target_kind.strip()}-{target_file_id}",
        "target_offset": target_offset,
        "target_file_id": target_file_id,
        "target_label": callee_labels.get(str(target_offset)),
        "subtree": subtree,
    }


def build_dialog_tree(
    disasm: dict,
    text_chunks: dict[int, str] | None,
    chunks_by_kind_id: dict[tuple[str, int], dict] | None = None,
    chunk_kind: str | None = None,
    chunk_id: int | None = None,
) -> list[dict]:
    """Build the dialog tree for one chunk's DisasmResult. Returns
    a list of subtrees, one per entry point. Empty list if the
    disassembly was not aligned (CFG absent).

    When `chunks_by_kind_id` is provided, `gpl global sub` call
    sites in this chunk expand inline as `cross_chunk_call`
    subtrees under the calling block (v0.4.0). The expansion uses
    a per-walk `cross_chunk_visited` set keyed on
    `(chunk_kind, chunk_id)` to break recursion."""
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
    # Initial cross-chunk-visited set marks the current chunk so a
    # self-call (`gpl global sub` into our own kind+id) is treated
    # as a cycle marker rather than recursive expansion.
    initial_cross_visited: set[tuple[str, int]] | None = None
    if chunks_by_kind_id is not None and chunk_kind is not None and chunk_id is not None:
        initial_cross_visited = {(chunk_kind, chunk_id)}
    # Walk declared entry points first (chunk start + every offset
    # observed as a `local sub` target).
    for entry_offset in cfg.get("entry_points", []):
        if entry_offset not in blocks_by_offset:
            continue
        if entry_offset in visited:
            continue
        speaker_state: dict[str, str | None] = {"other": None, "thing": None}
        lstr_state: dict[int, dict] = {}
        subtree = _walk_tree(
            entry_offset,
            blocks_by_offset,
            instr_by_offset,
            labels,
            text_chunks,
            speaker_state,
            lstr_state,
            visited,
            stop_at=None,
            depth=0,
            chunks_by_kind_id=chunks_by_kind_id,
            chunk_kind=chunk_kind,
            chunk_id=chunk_id,
            cross_chunk_visited=initial_cross_visited,
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
    # each as a discovered entry. v0.4.0 inter-chunk expansion can
    # cover many of these via call-graph expansion above, but
    # locally-unreachable leaders still get a dedicated entry so
    # nothing is hidden when expansion is disabled.
    for block in cfg.get("blocks", []):
        start = block["start_offset"]
        if start in visited:
            continue
        speaker_state = {"other": None, "thing": None}
        lstr_state = {}
        subtree = _walk_tree(
            start,
            blocks_by_offset,
            instr_by_offset,
            labels,
            text_chunks,
            speaker_state,
            lstr_state,
            visited,
            stop_at=None,
            depth=0,
            chunks_by_kind_id=chunks_by_kind_id,
            chunk_kind=chunk_kind,
            chunk_id=chunk_id,
            cross_chunk_visited=initial_cross_visited,
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


def _chunk_lstr_state_linear(disasm: dict) -> dict[int, dict]:
    """Build a chunk-level LSTR-slot snapshot via a single forward
    pass over the chunk's instructions (no CFG awareness). Used as
    the LSTR context for the flat per-chunk `strings` list. The
    path-aware `dialog_tree` walk maintains its own per-path
    state via `_walk_tree`.

    "Last write wins" along the linear instruction order. Catches
    the dominant menu-setup pattern (write LSTR[0..N] then
    `gpl_menu`) for ~80% of corpus reads; CFG-aware resolution in
    the tree is strictly more accurate on the remaining cases."""
    state: dict[int, dict] = {}
    for instr in disasm.get("instructions", []):
        _update_lstr_state(instr, state)
    return state


def _writer_record_from_instr(
    chunk_kind: str, chunk_id: int, instr: dict
) -> tuple[int, dict] | None:
    """Inspect a gpl_string_copy (0x0A) instruction and, when it
    writes to an LSTR slot, return (slot, writer_record). Returns
    None for non-LSTR-writes."""
    if instr.get("opcode") != LSTR_WRITER_OPCODE:
        return None
    params = instr.get("params") or []
    if len(params) < 2:
        return None
    dst = params[0]
    if len(dst) != 1:
        return None
    dst_tok = dst[0]
    if dst_tok.get("kind") != "variable" or dst_tok.get("var_kind") != "lstring":
        return None
    slot = dst_tok.get("id")
    if slot is None:
        return None
    src = params[1]
    record: dict = {
        "chunk": f"{chunk_kind.strip()}-{chunk_id}",
        "kind": chunk_kind,
        "id": chunk_id,
        "offset": instr.get("offset"),
        "source": "computed",
    }
    if len(src) == 1:
        s0 = src[0]
        s_kind = s0.get("kind")
        if s_kind == "immediate_string":
            record["source"] = "inline"
            record["value"] = s0.get("value", "")
            if s0.get("sub_type") is not None:
                record["sub_type"] = s0.get("sub_type")
        elif s_kind == "variable" and s0.get("var_kind") == "gstring":
            record["source"] = "gstring"
            record["text_id"] = s0.get("id")
        elif s_kind == "variable" and s0.get("var_kind") == "lstring":
            record["source"] = "lstring"
            record["source_slot"] = s0.get("id")
    return slot, record


def build_lstr_writer_index(
    disasm_results: list[dict],
) -> dict[int, list[dict]]:
    """Pre-scan every chunk for gpl_string_copy writes to LSTR
    slots; index them by destination slot. Caller-populated
    LSTR slots (the v0.4 unresolved tail) can be resolved by
    looking up the slot in this index and presenting every
    statically-reachable writer as a `possible_writer`. The
    index is keyed by slot id; the value is a deduplicated
    list of writer records (one per chunk + offset).
    """
    index: dict[int, list[dict]] = {}
    seen: set[tuple[int, str, int, int]] = set()
    for entry in disasm_results:
        kind = entry["chunk_kind"]
        cid = int(entry["chunk_id"])
        disasm = entry["disasm"]
        for instr in disasm.get("instructions", []):
            result = _writer_record_from_instr(kind, cid, instr)
            if result is None:
                continue
            slot, record = result
            key = (slot, kind, cid, instr.get("offset", -1))
            if key in seen:
                continue
            seen.add(key)
            index.setdefault(slot, []).append(record)
    return index


def build_reachable_callers(
    disasm_results: list[dict],
) -> dict[tuple[str, int], dict[tuple[str, int], int]]:
    """For each chunk (kind, id), compute the transitive closure
    of callers that can reach it via `gpl global sub` edges,
    along with the shortest-path *distance* (in caller-hops) from
    each ancestor to the read site.

    Used by `attach_possible_writers` to narrow + order the
    global writer set for an unresolved LSTR read: writers in
    the same chunk are distance 0 (added by the caller),
    immediate `gpl global sub` callers are distance 1, their
    callers distance 2, etc.

    The forward edge `caller -> callee` comes from each chunk's
    `cross_chunk_calls` (gpl-disasm v0.4.1+). v0.6.0 replaces
    v0.5.0's set-of-ancestors return shape with a dict that
    maps each ancestor to its shortest BFS distance on the
    reverse graph.
    """
    # Forward graph: caller -> set of callees.
    forward: dict[tuple[str, int], set[tuple[str, int]]] = {}
    all_nodes: set[tuple[str, int]] = set()
    for entry in disasm_results:
        kind = entry["chunk_kind"]
        cid = int(entry["chunk_id"])
        node = (kind, cid)
        all_nodes.add(node)
        callees: set[tuple[str, int]] = set()
        for call in entry["disasm"].get("cross_chunk_calls", []) or []:
            target_id = call.get("target_file_id")
            if target_id is None:
                continue
            # gpl-disasm doesn't tag the target's kind; gpl global
            # sub crosses chunks of the same kind (GPL -> GPL, MAS
            # -> MAS) per the engine's chunk-resolver semantics.
            callees.add((kind, int(target_id)))
        forward[node] = callees

    # Build reverse map by inverting edges.
    reverse: dict[tuple[str, int], set[tuple[str, int]]] = {
        n: set() for n in all_nodes
    }
    for caller, callees in forward.items():
        for callee in callees:
            reverse.setdefault(callee, set()).add(caller)

    # BFS on the reverse graph; record the first (smallest)
    # distance to each ancestor.
    from collections import deque

    reachable: dict[tuple[str, int], dict[tuple[str, int], int]] = {}
    for node in all_nodes:
        distances: dict[tuple[str, int], int] = {}
        queue: deque[tuple[tuple[str, int], int]] = deque()
        for parent in reverse.get(node, set()):
            queue.append((parent, 1))
        while queue:
            n, dist = queue.popleft()
            if n in distances:
                continue
            distances[n] = dist
            for grand_parent in reverse.get(n, set()):
                if grand_parent not in distances:
                    queue.append((grand_parent, dist + 1))
        reachable[node] = distances
    return reachable


def attach_possible_writers(
    strings: list[dict],
    writer_index: dict[int, list[dict]],
    reachable_callers: dict[tuple[str, int], dict[tuple[str, int], int]] | None,
    chunk_kind: str,
    chunk_id: int,
    quick_resolve: bool = False,
) -> None:
    """Mutate `strings` in place: for every unresolved
    `text:lstring` record, attach a `possible_writers` array
    drawn from the global writer index, narrowed (when a
    callgraph is available) to writers in chunks that
    statically reach the read site. Same-chunk writers are
    always included (the linear flat-scan tracker may have
    missed them via a CFG quirk).

    v0.6.0: each writer record carries a `distance` field
    (0 = same chunk, 1 = direct caller, N = N hops on the
    reverse callgraph). `possible_writers` is sorted ascending
    by `(distance, kind, id, offset)` so the human-or-tool
    reader's first guess is the closest writer.

    When `quick_resolve=True`, the writer list is also filtered
    to `distance <= 1` (same-chunk + direct callers); useful for
    the common case where the LSTR is set by the immediate
    caller and the longer tail is noise.
    """
    self_node = (chunk_kind, chunk_id)
    # distances[ancestor_node] = distance from ancestor to self_node.
    # Same-chunk writers (self_node) → distance 0.
    distances: dict[tuple[str, int], int] | None = None
    if reachable_callers is not None:
        distances = dict(reachable_callers.get(self_node, {}))
        distances[self_node] = 0
    for s in strings:
        if not s.get("unresolved"):
            continue
        if s.get("source") != "text:lstring":
            continue
        slot = s.get("text_id")
        if slot is None:
            continue
        all_writers = writer_index.get(slot, [])
        if distances is None:
            filtered = [dict(w) for w in all_writers]
            filter_label = "global"
        else:
            filtered = []
            for w in all_writers:
                node = (w.get("kind"), int(w.get("id")))
                if node not in distances:
                    continue
                rec = dict(w)
                rec["distance"] = distances[node]
                filtered.append(rec)
            filter_label = "callgraph-reachable"
            # Fall back to unfiltered when the reachable set
            # leaves zero matches (better than nothing). The
            # fallback writers have no `distance` (no path
            # exists on the static graph), surfaced as None.
            if not filtered and all_writers:
                filtered = [dict(w, distance=None) for w in all_writers]
                filter_label = "global-fallback"
        # Sort ascending by (distance, kind, id, offset).
        # `None` distance sorts last (no path exists).
        filtered.sort(
            key=lambda w: (
                _DISTANCE_INFINITY if w.get("distance") is None else w["distance"],
                w.get("kind") or "",
                int(w.get("id") or 0),
                int(w.get("offset") or 0),
            )
        )
        if quick_resolve:
            filtered = [
                w
                for w in filtered
                if w.get("distance") is not None and w["distance"] <= 1
            ]
            filter_label = filter_label + "+quick-resolve"
        s["possible_writers"] = filtered
        s["possible_writers_filter"] = filter_label


_DISTANCE_INFINITY = 10**9


def build_summary(
    source: Path,
    disasm_results: list[dict],
    text_chunks: dict[int, str] | None,
    text_source: Path | None,
    grep: re.Pattern[str] | None,
    quick_resolve: bool = False,
) -> dict:
    chunks_out: list[dict] = []
    total_strings = 0
    total_unresolved = 0
    total_lstr_reads = 0
    total_lstr_exact_resolved = 0
    total_lstr_possible_resolved = 0
    total_lstr_no_writers = 0

    # Index every chunk's disasm by (kind, id) so the inter-chunk
    # walker can resolve `gpl global sub` targets.
    chunks_by_kind_id: dict[tuple[str, int], dict] = {
        (e["chunk_kind"], int(e["chunk_id"])): e["disasm"]
        for e in disasm_results
    }
    # v0.5.0: global LSTR-writer index + reverse callgraph.
    # Unresolved text:lstring reads in the flat-list path
    # surface a `possible_writers` array narrowed (when the
    # callgraph is available) to writers in chunks that
    # statically reach the read site.
    lstr_writer_index = build_lstr_writer_index(disasm_results)
    reachable_callers = build_reachable_callers(disasm_results)

    for entry in disasm_results:
        disasm = entry["disasm"]
        # Linear-scan LSTR snapshot, used only by the flat-list
        # path. The dialog_tree builder runs its own path-aware
        # tracker independently.
        flat_lstr_state = _chunk_lstr_state_linear(disasm)
        strings: list[dict] = []
        for instr in disasm.get("instructions", []):
            strings.extend(
                extract_strings_from_instruction(
                    instr, text_chunks, flat_lstr_state
                )
            )
        if not strings:
            continue
        if grep is not None and not any(
            s.get("value") is not None and grep.search(s["value"]) for s in strings
        ):
            continue
        # v0.5.0: enrich unresolved LSTR reads with the global
        # writer index (callgraph-narrowed when possible) before
        # counting.
        attach_possible_writers(
            strings,
            lstr_writer_index,
            reachable_callers,
            entry["chunk_kind"],
            int(entry["chunk_id"]),
            quick_resolve=quick_resolve,
        )
        for s in strings:
            is_lstring = s.get("source") == "text:lstring"
            if is_lstring:
                total_lstr_reads += 1
            if s.get("unresolved"):
                total_unresolved += 1
                if is_lstring:
                    writers = s.get("possible_writers") or []
                    if writers:
                        total_lstr_possible_resolved += 1
                    else:
                        total_lstr_no_writers += 1
            elif is_lstring:
                total_lstr_exact_resolved += 1
        total_strings += len(strings)
        dialog_tree = build_dialog_tree(
            disasm,
            text_chunks,
            chunks_by_kind_id=chunks_by_kind_id,
            chunk_kind=entry["chunk_kind"],
            chunk_id=int(entry["chunk_id"]),
        )
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
        # v0.5.0 LSTR resolution stats. `exact` = the path-aware
        # / flat-scan tracker pinned a single value; `possible`
        # = the slot was unresolved at the read site but the
        # global writer index found at least one statically
        # reachable writer (surfaced as `possible_writers`);
        # `no_writers` = no chunk in the corpus writes to that
        # slot statically (runtime-only resolution).
        "lstr_stats": {
            "total_reads": total_lstr_reads,
            "exact_resolved": total_lstr_exact_resolved,
            "possible_resolved": total_lstr_possible_resolved,
            "no_writers": total_lstr_no_writers,
        },
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
    p.add_argument(
        "--quick-resolve",
        action="store_true",
        help="restrict `possible_writers` to distance <= 1 "
        "(same-chunk + direct callers). Useful for the common "
        "case where the LSTR is set by the immediate caller and "
        "the longer ancestor tail is noise.",
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
        args.file,
        disasm_results,
        text_chunks,
        args.text_source,
        grep_re,
        quick_resolve=args.quick_resolve,
    )
    indent = 2 if args.pretty else None
    text = json.dumps(summary, indent=indent, ensure_ascii=False)
    if args.output is None:
        sys.stdout.write(text + "\n")
    else:
        args.output.write_text(text + "\n", encoding="utf-8")
    # v0.5.0: print LSTR-resolution stats to stderr so a corpus
    # run shows the v0.4 -> v0.5 improvement at a glance.
    stats = summary.get("lstr_stats") or {}
    total = stats.get("total_reads", 0)
    if total > 0:
        exact = stats.get("exact_resolved", 0)
        possible = stats.get("possible_resolved", 0)
        no_writers = stats.get("no_writers", 0)
        pct = 100.0 * exact / total
        print(
            f"dialog-extract: {total} LSTR reads, "
            f"{exact} exact ({pct:.1f}%), "
            f"{possible} via possible_writers, "
            f"{no_writers} with no writers",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
