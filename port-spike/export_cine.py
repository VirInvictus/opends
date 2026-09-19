#!/usr/bin/env python3
"""Export the DS1 intro cinematics for the Godot demo.

Decodes CINE.GFF's BMA frames (codec per docs/cinematics-ds1.md) and
interprets the ACF scripts far enough to emit a flat playback timeline:

    generated/cine/p<part>_<frame>.png   baked frames (RGBA, 320x200)
    generated/cine.json                  parts: ordered event lists

Palette: frames are baked with the palette active at their timeline
position (ACF PAL loads switch it; per-entry fade ops are approximated
by the nearest full palette). Music/sound cues are recorded as events
(playback audio is out of scope for the demo).

Stdlib-only; run after export_region.py.
"""

from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "generated" / "cine"
CINE = REPO / ".games" / "ds1" / "CINE.GFF"
RESOURCE = REPO / ".games" / "ds1" / "RESOURCE.GFF"

_spec = importlib.util.spec_from_file_location(
    "opds_extract", REPO / "tools/gff-edit/scripts/extract-catalogue.py"
)
ec = importlib.util.module_from_spec(_spec)
sys.modules["opds_extract"] = ec
_spec.loader.exec_module(ec)

sys.path.insert(0, str(HERE))
import pngio  # noqa: E402


def decode_frame(data: bytes, off: int) -> tuple[int, int, bytes]:
    """BMA frame decode (cinematics-ds1.md 1): row/record wrapper over
    the DS1-RLE primitive; rows are stored TOP-DOWN (row_num = screen
    row, per the engine decoder at file 0x1532a)."""
    w, h = struct.unpack_from("<HH", data, off)
    img = bytearray(w * h)
    cpos = off + 4
    rows = 0
    while rows < h:
        row = data[cpos]
        cpos += 1
        if row == 0xFF:
            break
        if row >= h:
            raise ValueError("row out of range")
        base = row * w
        rows += 1
        while True:
            xw = struct.unpack_from("<H", data, cpos)[0]
            cpos += 2
            span = data[cpos]
            count = data[cpos + 1]
            cpos += 2
            x = xw & 0x7FFF
            end = cpos + count
            q = cpos
            px: list[int] = []
            while q < end:
                code = data[q]
                run = code // 2 + 1
                if code & 1:
                    px += [data[q + 1]] * run
                    q += 2
                else:
                    px += data[q + 1 : q + 1 + run]
                    q += 1 + run
            cpos = end
            img[base + x : base + x + span] = px[:span]
            if xw & 0x8000:
                break
    return w, h, bytes(img)


def decode_bma_chain(data: bytes) -> list[tuple[int, int, bytes]]:
    """Walk a BMA chunk: back-to-back bitmap containers, each u32 size,
    u16 frame_count, u32 offsets[], frames of u16 w, u16 h + rows."""
    frames = []
    pos = 0
    while pos + 6 <= len(data):
        (size,) = struct.unpack_from("<I", data, pos)
        if size < 6 or pos + size > len(data):
            break
        count = struct.unpack_from("<H", data, pos + 4)[0]
        offs = struct.unpack_from(f"<{count}I", data, pos + 6)
        for fo in offs:
            frames.append(decode_frame(data, pos + fo))
        pos += size
    return frames


def parse_acf(data: bytes) -> list[dict]:
    """ACF words -> instruction list (op, operands). The instruction
    word is (op << 8) | (2 * total_words), total including the opcode
    word; so the word count per instruction is (low byte) >> 1."""
    words = struct.unpack_from(f"<{len(data) // 2}H", data)
    out = []
    pc = 0
    while pc < len(words):
        op = words[pc] >> 8
        total = (words[pc] & 0xFF) >> 1
        if total < 1:
            break  # 0x0000 terminator / END
        out.append({"op": op, "args": list(words[pc + 1 : pc + total]), "pc": pc})
        pc += total
        if op == 0:
            break
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cine = ec.parse_gff(CINE)
    res = ec.parse_gff(RESOURCE)

    def pal_bytes(chunk: bytes) -> list[tuple[int, int, int]]:
        return [
            (chunk[i] * 255 // 63, chunk[i + 1] * 255 // 63, chunk[i + 2] * 255 // 63)
            for i in range(0, 768, 3)
        ]

    pals = {cid: pal_bytes(p) for cid, p in ec.resolve_type(cine, "PAL")}
    base_pal = next(iter(pals.values())) if pals else pal_bytes(ec.get_chunk(res, "PAL", 1000))

    def bma_chain(cid: int) -> list[tuple[int, int, bytes]]:
        data = ec.get_chunk(cine, "BMA", cid)
        frames = []
        pos = 0
        while pos + 6 <= len(data):
            (size,) = struct.unpack_from("<I", data, pos)
            if size < 6 or pos + size > len(data):
                break
            count = struct.unpack_from("<H", data, pos + 4)[0]
            offs = struct.unpack_from(f"<{count}I", data, pos + 6)
            frames += [decode_frame(data, pos + fo) for fo in offs]
            pos += size
        return frames

    acfs = {cid: p for cid, p in ec.resolve_type(cine, "ACF")}
    stills = {cid: p for cid, p in ec.resolve_type(cine, "BMP ")}

    def bake(img: bytes, pal) -> bytes:
        rgba = bytearray(len(img) * 4)
        for k, idx in enumerate(img):
            r, g, b = pal[idx]
            rgba[k * 4 : k * 4 + 4] = bytes((r, g, b, 255))
        return bytes(rgba)

    parts = []
    pal = base_pal  # palette state persists ACROSS parts, as in the engine
    for part_id in range(1, 13):
        if part_id not in acfs:
            continue
        script = parse_acf(acfs[part_id])
        try:
            frame_iter = iter(bma_chain(part_id))
        except KeyError:
            frame_iter = iter([])  # still-only parts (ACF 1, 13)

        timeline = []
        frame_no = 0
        still_decoded: dict[int, tuple[int, int, bytes]] = {}
        for ins in script:
            op, args = ins["op"], ins["args"]
            if op == 5:  # movie frame: show the next BMA frame
                f = next(frame_iter, None)
                if f is None:
                    continue
                w, h, img = f
                name = f"p{part_id}_{frame_no:04d}.png"
                pngio.write_rgba(OUT / name, w, h, bake(img, pal))
                timeline.append({"kind": "frame", "png": name, "wait": 1})
                frame_no += 1
            elif op == 6:  # wait N ticks: extends the previous frame's hold
                n = args[0] if args else 1
                if timeline and timeline[-1]["kind"] == "frame":
                    timeline[-1]["wait"] += n
            elif op == 0x28:  # load a BMP still into a slot: bake and show
                sid = args[0] if args else 0
                if sid not in still_decoded and sid in stills:
                    still_decoded[sid] = decode_bma_chain(stills[sid])[0]
                if sid in still_decoded:
                    w, h, img = still_decoded[sid]
                    name = f"p{part_id}_still{sid:03d}.png"
                    pngio.write_rgba(OUT / name, w, h, bake(img, pal))
                    timeline.append({"kind": "still", "png": name, "wait": 2})
            elif op == 0x3C:  # palette load
                pid = args[0] if args else 0
                if pid in pals:
                    pal = pals[pid]
            elif op == 0x14:  # set palette entry: idx/R in op1, G/B in op2
                if len(args) >= 2:
                    idx = args[0] >> 8
                    r = args[0] & 0xFF
                    g = args[1] >> 8
                    b = args[1] & 0xFF
                    if 0 <= idx < 256:
                        pal[idx] = (r * 255 // 63, g * 255 // 63, b * 255 // 63)
                # 0x15 commits; staged writes are baked per frame here
            elif op == 8:
                timeline.append({"kind": "sound", "id": args[0] if args else 0})
            elif op == 0x64:
                timeline.append({"kind": "music", "id": args[0] if args else 0})
            # remaining ops (stream seeks, fades, compositing scenes) are
            # playback-side effects approximated by the baked palettes.

        parts.append({"id": part_id, "timeline": timeline, "frames": frame_no})
        print(f"cine part {part_id}: {frame_no} frames, {len(timeline)} events")

    json.dump({"parts": parts}, open(HERE / "generated" / "cine.json", "w"))
    print(f"wrote {OUT}/ + cine.json ({sum(p['frames'] for p in parts)} frames)")


if __name__ == "__main__":
    main()
