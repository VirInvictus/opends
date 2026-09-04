#!/usr/bin/env python3
"""GPL<->EXE cross-reference index: which EXE code loads which chunk kinds.

Phase 5.6.0's "which EXE code runs this GPL chunk" lookup. The engine
loads chunks by (FOURCC, id) through the resource loader, so the join
key on the EXE side is the push pair: `66 68 <FOURCC>` (push dword
FOURCC) with, usually just before it, an immediate id push
(`66 6A imm8` / `66 68 imm32`, sometimes the 16-bit `6A` / `68`
encodings), and just after it the `9A` far call into the loader.

Measured shape (DS1 seg 21, `add sp, 0xc` after the call confirms the
three-argument `load_resource(fourcc, id, far *)` contract):

    push ss / lea ax, [bp-8] / push ax      ; far return buffer
    66 6A 01              push dword 1      ; id (immediate!)
    66 68 'GPLI'          push dword 'GPLI' ; chunk kind
    9A ...                call <loader>
    83 C4 0C              add sp, 0xc

Known limits, stated rather than hidden:

  - Direct `GPL `/`MAS ` pushes do not exist in either binary. Script
    chunks load indirectly through the GPLI/GPLX index chunks, so the
    per-chunk join resolves one level: EXE site -> index chunk id.
    Decoding GPLI's entries into GPL chunk ids is separate work
    (roadmap 5.6.2 class).
  - Far-call targets from overlay code are pre-relocation candidates
    (see propose-exe-symbols.py --census); resident-side targets are
    reliable (MZ relocation arithmetic, per ovr-map's callgraph).
  - `6A`/`68` id encodings may be unrelated argument pushes; they are
    flagged lower-confidence than the `66 `-prefixed forms.

Inputs: a DSUN.EXE (via ovr-map), optionally a `gpl-disasm --global-cfg
--json` file for the GPL chunk inventory and boot candidates, and
optionally the curated syms catalogue to flag catalogue-name hits.
Stdlib-only.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent

# id-push encodings: pattern -> (offset of immediate after pattern, size
# of immediate, confidence). `66 6A imm8` pushes a sign-extended dword;
# the 16-bit `6A`/`68` forms may be unrelated argument pushes.
ID_ENCODINGS = {
    b"\x66\x6a": ("imm8-dword", 2, 1, "high"),
    b"\x66\x68": ("imm32-dword", 2, 4, "high"),
    b"\x6a": ("imm8-word", 1, 1, "medium"),
    b"\x68": ("imm16-word", 1, 2, "medium"),
}

LOAD_CALL_WINDOW = 24  # bytes between FOURCC push and the loader call
ID_LOOKBACK = 12


def load_ovr_map():
    spec = importlib.util.spec_from_file_location("ovr_map", TOOL_DIR / "ovr-map.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {TOOL_DIR / 'ovr-map.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_id_immediate(body: bytes, push_at: int) -> dict | None:
    """Most recent id-immediate push before the FOURCC push.

    Cdecl pushes arguments right-to-left, so the id push sits closest
    behind the FOURCC push; prefer the latest candidate, and among
    equal positions the high-confidence (`66 `-prefixed) encodings.
    """
    window_start = max(0, push_at - ID_LOOKBACK)
    window = body[window_start:push_at]
    candidates = []
    for pattern, (encoding, imm_off, imm_size, confidence) in ID_ENCODINGS.items():
        idx = window.rfind(pattern)
        if idx < 0:
            continue
        at = idx + imm_off
        if at + imm_size > len(window):
            continue
        value = int.from_bytes(window[at : at + imm_size], "little")
        if encoding == "imm32-dword" and value > 0xFFFF:
            continue  # chunk ids are 16-bit; a dword this large is a pointer
        if encoding in ("imm8-dword", "imm8-word") and value & 0x80:
            continue  # sign-extended negative: not a chunk id
        candidates.append(
            {
                "id": value,
                "encoding": encoding,
                "confidence": confidence,
                "at": at,
            }
        )
    if not candidates:
        return None
    return max(candidates, key=lambda c: (c.pop("at"), c["confidence"] == "high"))


def find_load_call(body: bytes, push_at: int, header: int) -> dict | None:
    """First far call after the FOURCC push, within the window."""
    for i in range(push_at + 6, min(len(body) - 5, push_at + LOAD_CALL_WINDOW)):
        if body[i] != 0x9A:
            continue
        call_off, call_seg = struct.unpack_from("<HH", body, i + 1)
        return {
            "call_offset": i,
            "target_seg": call_seg,
            "target_off": call_off,
            "target_file_offset": header + call_seg * 16 + call_off,
        }
    return None


def collect_push_sites(data: bytes, report: dict) -> list[dict]:
    """Every `66 68 <printable>` site in the resident image and overlays."""
    mz = report["mz"]
    header = mz["header_size"]
    regions: list[tuple[str, int, int, dict | None]] = [
        ("resident", 0, mz["image_end"], None)
    ]
    for seg in report["segments"]:
        if seg["empty"]:
            continue
        regions.append(("overlay", seg["index"], seg["size"], seg))

    sites: list[dict] = []
    for kind, seg_index, size, seg in regions:
        base = 0 if seg is None else seg["file_start"]
        body = data[base : base + size]
        i = 0
        while i < len(body) - 6:
            if body[i] != 0x66 or body[i + 1] != 0x68:
                i += 1
                continue
            fourcc = body[i + 2 : i + 6]
            if not all(0x20 <= b < 0x7F for b in fourcc):
                i += 1
                continue
            site: dict = {
                "fourcc": fourcc.decode("ascii"),
                "region": kind,
                "file_offset": base + i,
            }
            if seg is not None:
                site["segment"] = seg_index
                site["segment_offset"] = i
                prior = [e for e in seg["entries"] if e["entry_offset"] <= i]
                if prior:
                    entry = max(prior, key=lambda e: e["entry_offset"])
                    site["nearest_entry"] = {
                        "entry_offset": entry["entry_offset"],
                        "distance": i - entry["entry_offset"],
                    }
            id_info = find_id_immediate(body, i)
            if id_info:
                site["id_immediate"] = id_info
            call = find_load_call(body, i, header)
            if call:
                call["call_offset"] = base + call["call_offset"]
                site["load_call"] = call
            sites.append(site)
            i += 6
    return sites


def load_gpl_inventory(path: Path) -> dict:
    data = json.loads(path.read_text())
    nodes = data.get("nodes", [])
    inventory = [
        {
            "kind": n["kind"],
            "chunk_id": n["chunk_id"],
            "inbound": n.get("inbound_calls", 0),
            "outbound": n.get("outbound_calls", 0),
            "boot_candidate": n.get("inbound_calls", 0) == 0,
        }
        for n in nodes
    ]
    return {
        "source": data.get("source"),
        "chunks": inventory,
        "edges": len(data.get("edges", [])),
        "boot_candidates": [c for c in inventory if c["boot_candidate"]],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--game", choices=("ds1", "ds2"), default="ds1")
    ap.add_argument("--exe", type=Path, help="override .games/<game>/DSUN.EXE")
    ap.add_argument(
        "--global-cfg",
        type=Path,
        help="gpl-disasm --global-cfg --json output for the game's GPLDATA.GFF",
    )
    ap.add_argument("--json", action="store_true", help="emit the index as JSON")
    args = ap.parse_args(argv)

    exe = args.exe or Path(".games") / args.game / "DSUN.EXE"
    if not exe.is_file():
        print(f"error: no EXE at {exe}", file=sys.stderr)
        return 2

    ovr_map = load_ovr_map()
    report = ovr_map.build(exe)
    data = exe.read_bytes()
    sites = collect_push_sites(data, report)

    # Catalogue names: flag load calls that hit a catalogued function.
    syms_path = TOOL_DIR / "syms" / f"{args.game}.toml"
    named = {}
    if syms_path.is_file():
        named = {key: row["name"] for key, row in ovr_map.load_syms(syms_path).items()}
    for site in sites:
        call = site.get("load_call")
        if not call:
            continue
        name = named.get(("resident", call["target_file_offset"]))
        if name:
            call["target_name"] = name
            call["target_confidence"] = "catalogued"

    inventory = None
    if args.global_cfg:
        if not args.global_cfg.is_file():
            print(f"error: no global-cfg file at {args.global_cfg}", file=sys.stderr)
            return 2
        inventory = load_gpl_inventory(args.global_cfg)

    if args.json:
        print(
            json.dumps(
                {
                    "game": args.game,
                    "exe": str(exe),
                    "push_sites": sites,
                    "gpl_inventory": inventory,
                    "notes": [
                        "id_immediate confidence 'medium' (6A/68 encodings) may be "
                        "unrelated argument pushes",
                        "load_call targets from overlay regions are pre-relocation "
                        "candidates; resident targets are reliable",
                        "no direct 'GPL '/'MAS ' pushes exist; script chunks load via "
                        "the GPLI/GPLX index chunks, so the per-chunk join resolves "
                        "one level (EXE site -> index chunk id)",
                    ],
                },
                indent=2,
            )
        )
        return 0

    # Human summary.
    by_kind = collections.Counter(s["fourcc"] for s in sites)
    id_sites = [s for s in sites if "id_immediate" in s]
    print(f"# GPL<->EXE cross-reference ({args.game}: {exe})")
    print(f"# push sites: {len(sites)} (with id-immediate: {len(id_sites)})")
    print()
    print("## Chunk kinds pushed by EXE code")
    print()
    print("| FOURCC | sites | with id | segments involved |")
    print("|---|---|---|---|")
    for fcc, count in by_kind.most_common():
        subset = [s for s in sites if s["fourcc"] == fcc]
        segs = sorted({s["segment"] for s in subset if s["region"] == "overlay"})
        with_id = sum(1 for s in subset if "id_immediate" in s)
        seg_txt = (
            ",".join(f"ovr{s:02d}" for s in segs[:6]) + ("..." if len(segs) > 6 else "")
            if segs
            else "resident"
        )
        print(f"| `{fcc}` | {count} | {with_id} | {seg_txt} |")
    print()
    print("## Index-chunk boot requests (GPLI/GPLX pushes with immediate id)")
    print()
    requests = [
        s for s in sites if s["fourcc"] in ("GPLI", "GPLX") and "id_immediate" in s
    ]
    if requests:
        print("| FOURCC | id | file offset | region | loader target |")
        print("|---|---|---|---|---|")
        for s in requests:
            call = s.get("load_call")
            target = f"0x{call['target_file_offset']:x}" if call else "?"
            name = call.get("target_name") if call else None
            if name:
                target += f" ({name})"
            region = (
                f"ovr{s['segment']:02d}+0x{s['segment_offset']:x}"
                if s["region"] == "overlay"
                else "resident"
            )
            print(
                f"| `{s['fourcc']}` | {s['id_immediate']['id']} "
                f"({s['id_immediate']['encoding']}) | 0x{s['file_offset']:x} | "
                f"{region} | {target} |"
            )
    else:
        print("_(none)_")
    print()
    if inventory:
        boots = inventory["boot_candidates"]
        gpl_boots = [c for c in boots if c["kind"] in ("GPL ", "MAS ")]
        print("## GPL inventory (from gpl-disasm --global-cfg)")
        print()
        print(
            f"{len(inventory['chunks'])} chunks, {inventory['edges']} inter-chunk "
            f"edges; boot candidates (zero inbound): {len(gpl_boots)} script chunks"
        )
        print(
            "These are the chunks the engine must dispatch directly "
            "(no GPL caller); the GPLI boot requests above are the EXE-side "
            "candidates for reaching them."
        )
    else:
        print(
            "GPL inventory: pass --global-cfg <gpl-disasm --global-cfg --json> to join."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
