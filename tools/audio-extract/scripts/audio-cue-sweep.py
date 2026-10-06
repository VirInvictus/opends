#!/usr/bin/env python3
"""audio-cue-sweep: sweep disassembled GPL chunks for audio cues.

Mineout Phase A deliverable 3's tooling. Runs `gpl-disasm --all
--json` over GFF containers (the same contract dialog-extract
consumes) and collects every `gpl sound` (0x5D) and `gpl music`
(0x5F) instruction with its operand: which script, in which
container, requests which sound/music id. Output is a JSON inventory
plus a stdout summary (per-file counts, per-id histograms).

audio-routing.md owns the routing model (DS1: sound id = BVOC chunk
id, music ids 1..23; DS2: sound id N -> BVOC id N+1, no GPL music
exists). This tool produces the cue evidence docs/audio-cues.md is
written from. Stdlib-only; requires a built gpl-disasm.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = (HERE.parent / "VERSION").read_text().strip()

SOUND_OP = 0x5D
MUSIC_OP = 0x5F
AUDIO_OPS = {SOUND_OP: "sound", MUSIC_OP: "music"}


def locate_gpl_disasm(hint: str | None) -> str:
    candidates = ([hint] if hint else []) + ["gpl-disasm"]
    for c in candidates:
        if c and shutil.which(c):
            return c
        if c and Path(c).is_file():
            return c
    for profile in ("release", "debug"):
        candidate = HERE.parent.parent.parent / "target" / profile / "gpl-disasm"
        if candidate.is_file():
            return str(candidate)
    print(
        "error: gpl-disasm not found (build it: cargo build -p gpl-disasm)",
        file=sys.stderr,
    )
    raise SystemExit(2)


def run_disasm(gff: Path, binary: str, tmpdir: Path) -> list[dict]:
    result = subprocess.run(
        [binary, str(gff), "--all", "-o", str(tmpdir), "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gpl-disasm failed on {gff} (exit {result.returncode}): {result.stderr.strip()}"
        )
    out = []
    for p in sorted(tmpdir.iterdir()):
        if p.suffix != ".json":
            continue
        stem = p.stem  # e.g. "GPL-7" or "MAS-12"
        kind_prefix, _, id_str = stem.rpartition("-")
        if not kind_prefix or not id_str.isdigit():
            continue
        kind_full = (kind_prefix + " ") if len(kind_prefix) == 3 else kind_prefix
        out.append(
            {
                "chunk_kind": kind_full,
                "chunk_id": int(id_str),
                "disasm": json.loads(p.read_text()),
            }
        )
    return out


_IMM_KINDS = {
    "immediate14": "value",
    "immediate_byte": "value",
    "immediate_big_num": "value",
    "immediate_name": "value",
}


def expr_str(e: dict) -> str:
    kind = e.get("kind")
    if kind in _IMM_KINDS:
        return str(e["value"])
    if kind == "variable":
        base = f"{e['var_kind']}[{e['id']}]"
        name = e.get("name")
        return f"{base}={name}" if name else base
    if kind == "immediate_string":
        return f"str({e['value']!r})"
    return json.dumps(e)


def operand_repr(params: list[list[dict]]) -> str | None:
    """Render a one-parameter operand as a compact string."""
    if not params or not params[0]:
        return None
    return " + ".join(expr_str(e) for e in params[0])


def sweep(gffs: list[Path], binary: str) -> dict:
    files_out = []
    for gff in gffs:
        with tempfile.TemporaryDirectory(prefix="audio-cue-sweep-") as tmp:
            chunks = run_disasm(gff, binary, Path(tmp))
        cues = []
        for chunk in chunks:
            # Rolling context: the nearest inline strings before each
            # cue, from the same chunk's instruction stream (both the
            # v0.1 ASCII-run carryover and ImmediateString params).
            recent: list[str] = []
            for ins in chunk["disasm"]["instructions"]:
                if ins.get("string_run"):
                    recent.append(ins["string_run"])
                for group in ins["params"]:
                    for e in group:
                        if e.get("kind") == "immediate_string":
                            recent.append(e["value"])
                recent = recent[-3:]
                if ins["opcode"] not in AUDIO_OPS:
                    continue
                cues.append(
                    {
                        "op": AUDIO_OPS[ins["opcode"]],
                        "offset": ins["offset"],
                        "operand": operand_repr(ins["params"]),
                        "chunk_kind": chunk["chunk_kind"],
                        "chunk_id": chunk["chunk_id"],
                        "context_strings": list(recent),
                        "best_effort": bool(ins.get("best_effort")),
                    }
                )
        files_out.append(
            {"file": str(gff), "chunks_disassembled": len(chunks), "cues": cues}
        )
        print(
            f"{gff}: {len(chunks)} chunks, {len(cues)} audio cues"
            f" ({sum(1 for c in cues if c['op'] == 'music')} music)",
            file=sys.stderr,
        )
    return {"tool": "audio-cue-sweep", "version": VERSION, "files": files_out}


def summarize(inv: dict) -> str:
    sound_ids: Counter[str] = Counter()
    music_ids: Counter[str] = Counter()
    per_file: dict[str, int] = {}
    for f in inv["files"]:
        per_file[f["file"]] = len(f["cues"])
        for c in f["cues"]:
            target = music_ids if c["op"] == "music" else sound_ids
            target[c["operand"] or "?"] += 1
    lines = []
    lines.append(f"files with cues: {sum(1 for v in per_file.values() if v)}")
    lines.append(
        f"sound (0x5D) call sites: {sum(sound_ids.values())} across {len(sound_ids)} distinct operands"
    )
    for operand, n in sound_ids.most_common():
        lines.append(f"  {operand:>16s}  x{n}")
    lines.append(
        f"music (0x5F) call sites: {sum(music_ids.values())} across {len(music_ids)} distinct operands"
    )
    for operand, n in music_ids.most_common():
        lines.append(f"  {operand:>16s}  x{n}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("files", nargs="*", type=Path, help="GFF containers to sweep")
    ap.add_argument("-o", "--output", type=Path, help="write the JSON inventory here")
    ap.add_argument("--gpl-disasm", help="explicit path to the gpl-disasm binary")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    if not args.files:
        ap.error("at least one GFF file is required")
    for f in args.files:
        if not f.is_file():
            print(f"error: not a file: {f}", file=sys.stderr)
            return 2

    binary = locate_gpl_disasm(args.gpl_disasm)
    inv = sweep(args.files, binary)
    text = summarize(inv)
    print(text)
    if args.output:
        args.output.write_text(json.dumps(inv, indent=2) + "\n")
        print(f"\ninventory: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(inv, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
