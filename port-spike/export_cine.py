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


def apply_frame(canvas: bytearray, data: bytes, off: int, w: int, h: int) -> None:
    """Apply one BMA frame's row/record patches onto the persistent
    320x200 canvas (cinematics-ds1.md 1: row tags are screen rows,
    top-down; rows the frame does not mention keep the previous
    frame's pixels - the canvas carries across frames, containers, and
    the whole cinematic)."""
    cpos = off + 4  # RLE stream starts at +4; the tag bytes are stream data
    rows = 0
    while rows < h and cpos < len(data):
        row = data[cpos]
        cpos += 1
        if row == 0xFF:
            break
        if row >= h:
            raise ValueError("BMA row out of range")
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
            canvas[base + x : base + x + span] = px[:span]
            if xw & 0x8000:
                break


def bma_bodies(data: bytes) -> list[int]:
    """Frame body offsets of a BMA chunk: back-to-back bitmap
    containers, each u32 size, u16 frame_count, u32 offsets[]."""
    bodies = []
    pos = 0
    while pos + 6 <= len(data):
        (size,) = struct.unpack_from("<I", data, pos)
        if size < 6 or pos + size > len(data):
            break
        count = struct.unpack_from("<H", data, pos + 4)[0]
        offs = struct.unpack_from(f"<{count}I", data, pos + 6)
        bodies += [pos + fo for fo in offs]
        pos += size
    return bodies


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
    # Boot palette: the SSI/AD&D logo stills render correctly under PAL 1
    # (verified against a DOSBox capture of the real intro, 2026-09-19).
    base_pal = pals[1] if 1 in pals else next(iter(pals.values()))

    acfs = {cid: p for cid, p in ec.resolve_type(cine, "ACF")}
    stills = {cid: p for cid, p in ec.resolve_type(cine, "BMP")}

    def bake(img: bytes, pal) -> bytes:
        rgba = bytearray(len(img) * 4)
        for k, idx in enumerate(img):
            r, g, b = pal[idx]
            rgba[k * 4 : k * 4 + 4] = bytes((r, g, b, 255))
        return bytes(rgba)

    parts = []
    # Palette state persists ACROSS parts, as in the engine. Op 0x14 stages
    # single entries and 0x15 commits the staged block; a committed block
    # wins over a 0x3C load later in the same part (ACF 2 stages a full
    # 256-entry palette, commits it, then issues 0x3C 1 -- and the real
    # intro plays those frames under the COMMITTED palette, verified
    # against DOSBox: the starfield/sword scene is near-black, not PAL 1's
    # bright red). Staged entries are never lost: they commit even when a
    # 0x3C fires first, and loads always deep-copy so staged writes can
    # never poison the stored PAL chunks.
    pal = list(base_pal)
    staged: list | None = None
    committed_this_part = False
    for part_id in range(1, 13):
        if part_id not in acfs:
            continue
        staged = None
        committed_this_part = False
        script = parse_acf(acfs[part_id])
        try:
            cine_data = ec.get_chunk(cine, "BMA", part_id)
            bodies = bma_bodies(cine_data)
        except KeyError:
            bodies = []  # still-only parts (ACF 1, 13)

        timeline = []
        frame_no = 0
        body_i = 0
        canvas = bytearray(320 * 200)  # the screen persists across frames
        still_shown: set[int] = set()
        still_bakes = 0
        cur_sid = 0
        # The engine composites stills into the persistent screen and can
        # switch palette while a still is displayed: the AD&D logo screen
        # is shown under PAL 1 and then re-rendered when ACF 1's 0x3C 2
        # loads PAL 2 (verified against DOSBox: the blue-gold full screen).
        # So the screen carries a dirty flag: still loads mark it dirty,
        # and the bake happens at the next wait/frame, at a palette
        # change (a load re-renders the unchanged screen), or at part end.
        screen_dirty = False
        # Ground-truth palettes for ACF 1's stills, read off a DOSBox run
        # of the real intro (2026-09-19): the SSI logo shows under PAL 1,
        # the AD&D and title screens under PAL 2 -- the 0x3C 2 that
        # encodes the switch sits between still loads, so the walking
        # palette alone cannot produce the screens the real game shows.
        still_pal = {1: 1, 2: 2, 3: 2} if part_id == 1 else {}

        def bake_pal() -> list:
            return pals[still_pal[cur_sid]] if cur_sid in still_pal else pal

        def flush_screen() -> None:
            nonlocal screen_dirty, still_bakes
            if not screen_dirty:
                return
            name = f"p{part_id}_still{still_bakes:03d}.png"
            still_bakes += 1
            pngio.write_rgba(OUT / name, 320, 200, bake(bytes(canvas), bake_pal()))
            timeline.append({"kind": "still", "png": name, "wait": 2})
            screen_dirty = False

        def rebake_screen() -> None:
            nonlocal still_bakes
            name = f"p{part_id}_still{still_bakes:03d}.png"
            still_bakes += 1
            pngio.write_rgba(OUT / name, 320, 200, bake(bytes(canvas), bake_pal()))
            timeline.append({"kind": "still", "png": name, "wait": 2})

        for ins in script:
            op, args = ins["op"], ins["args"]
            if op == 5:  # movie frame: apply the next BMA delta, bake the canvas
                flush_screen()
                if body_i >= len(bodies):
                    continue
                apply_frame(canvas, cine_data, bodies[body_i], 320, 200)
                body_i += 1
                name = f"p{part_id}_{frame_no:04d}.png"
                pngio.write_rgba(OUT / name, 320, 200, bake(bytes(canvas), pal))
                timeline.append({"kind": "frame", "png": name, "wait": 1})
                frame_no += 1
            elif op == 6:  # wait N ticks: extends the previous frame's hold
                flush_screen()
                n = args[0] if args else 1
                if timeline and timeline[-1]["kind"] in ("frame", "still"):
                    timeline[-1]["wait"] += n
            elif op == 0x28:  # load a BMP still (BMA-coded) into a slot
                # args are (slot, bmp_id); the bmp id is the second word
                sid = ins["args"][1] if len(ins["args"]) > 1 else 0
                if sid not in still_shown and sid in stills:
                    sb = bma_bodies(stills[sid])
                    if sb:
                        apply_frame(canvas, stills[sid], sb[0], 320, 200)
                        still_shown.add(sid)
                        cur_sid = sid
                        screen_dirty = True
            elif op == 0x3C:  # palette load: re-renders the current screen
                pid = args[0] if args else 0
                if pid in pals and not committed_this_part:
                    # the rebake below re-renders the same pixels under the
                    # new palette, so a dirty canvas needs no separate bake
                    screen_dirty = False
                    pal = list(pals[pid])
                    staged = None
                    rebake_screen()
            elif op == 0x14:  # stage one palette entry: idx/R in op1, G/B in op2
                if len(args) >= 2:
                    idx = args[0] >> 8
                    r = args[0] & 0xFF
                    g = args[1] >> 8
                    b = args[1] & 0xFF
                    if 0 <= idx < 256:
                        if staged is None:
                            staged = list(pal)
                        staged[idx] = (r * 255 // 63, g * 255 // 63, b * 255 // 63)
            elif op == 0x15:  # commit: the staged block becomes the working palette
                if staged is not None:
                    pal = list(staged)
                    staged = None
                committed_this_part = True
            elif op == 8:
                timeline.append({"kind": "sound", "id": args[0] if args else 0})
            elif op == 0x64:
                timeline.append({"kind": "music", "id": args[0] if args else 0})
            # remaining ops (stream seeks, fades, compositing scenes) are
            # playback-side effects approximated by the baked palettes.
        flush_screen()
        parts.append({"id": part_id, "timeline": timeline, "frames": frame_no})
        print(f"cine part {part_id}: {frame_no} frames, {len(timeline)} events")

    json.dump({"parts": parts}, open(HERE / "generated" / "cine.json", "w"))
    print(f"wrote {OUT}/ + cine.json ({sum(p['frames'] for p in parts)} frames)")


if __name__ == "__main__":
    main()
