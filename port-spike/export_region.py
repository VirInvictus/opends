#!/usr/bin/env python3
"""Export one Dark Sun region to the Godot 4 spike project.

Pipeline proof-of-life for the port (docs/godot-port-readiness.md,
section C): reads the region's own data with the repo's Python GFF
reader, decodes DS1-RLE bitmaps directly (the codec spec is
docs/presentation-formats.md 1 and tools/image-extract's
decode_ds1_rle), recolors through PAL 1000, and emits:

    generated/tiles_atlas.png   16x16-tile atlas (RGBA)
    generated/tileset.tres      Godot TileSet over the atlas
    generated/sprites/*.png     entity + wall sprites (RGBA, index 0 = transparent)
    generated/region.json       cells, blocked rows, walls, entities

Everything lands in generated/ (gitignored); the Godot project files
live beside this script. Stdlib-only; no game file is modified.

Usage: python3 export_region.py [region file name, default RGN02.GFF]
"""

from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "generated"
GAME = REPO / ".games" / "ds1"
REGION_FILE = sys.argv[1] if len(sys.argv) > 1 else "RGN02.GFF"
PALETTE_KIND, PALETTE_ID = "CPAL", 200  # the engine-default palette (what region-render falls back to)

# The generator script's name has hyphens; import it under a module name.
_spec = importlib.util.spec_from_file_location(
    "opds_extract", REPO / "tools/gff-edit/scripts/extract-catalogue.py"
)
ec = importlib.util.module_from_spec(_spec)
sys.modules["opds_extract"] = ec
_spec.loader.exec_module(ec)

sys.path.insert(0, str(HERE))
import pngio  # noqa: E402


# ---------------------------------------------------------------------------
# DS1-RLE bitmap decoding (spec: presentation-formats.md 1; reference:
# tools/image-extract/src/lib.rs decode_ds1_rle)

def decode_frame(data: bytes, off: int) -> tuple[int, int, bytes]:
    """Decode one bitmap-container frame to (w, h, palette indices)."""
    w, h = struct.unpack_from("<HH", data, off)
    if data[off + 5 : off + 9] in (b"PLNR", b"PLAN"):
        raise NotImplementedError("PLNR/PLAN frame (spike covers DS1 RLE only)")
    img = bytearray(w * h)
    cpos = off + 4  # RLE stream starts at +4; the tag bytes are stream data
    rows = 0
    while rows < h:
        row_num = data[cpos]
        cpos += 1
        if row_num == 0xFF:
            break
        base = (h - row_num - 1) * w  # engine rows are bottom-up
        rows += 1
        while True:
            startx = data[cpos]
            flags = data[cpos + 1]
            cpos += 2
            cpos += 1  # one unknown byte, read and ignored (libgff does the same)
            clen = data[cpos]
            cpos += 1
            if flags & 0x01:
                startx += 256
            payload_end = cpos + clen
            i = 0
            while i < clen:
                code = data[cpos + i]
                i += 1
                run = code // 2 + 1
                if code % 2 == 0:
                    for _ in range(run):
                        if startx < w:
                            img[base + startx] = data[cpos + i]
                        i += 1
                        startx += 1
                else:
                    px = data[cpos + i]
                    i += 1
                    for _ in range(run):
                        if startx < w:
                            img[base + startx] = px
                        startx += 1
            cpos = payload_end
            if flags & 0x80:
                break
    return w, h, bytes(img)


def first_frame(data: bytes) -> tuple[int, int, bytes]:
    """Decode frame 0 of a universal bitmap container."""
    _size, frame_count = struct.unpack_from("<IH", data, 0)
    if frame_count < 1:
        raise ValueError("empty bitmap container")
    (off,) = struct.unpack_from("<I", data, 6)
    return decode_frame(data, off)


# ---------------------------------------------------------------------------
# Palette

def load_palette(resource_gff) -> list[tuple[int, int, int]]:
    pal = ec.get_chunk(resource_gff, PALETTE_KIND, PALETTE_ID)
    return [
        (pal[i] * 255 // 63, pal[i + 1] * 255 // 63, pal[i + 2] * 255 // 63)
        for i in range(0, 768, 3)
    ]


def indices_to_rgba(img: bytes, pal, transparent_index0: bool) -> bytes:
    out = bytearray(len(img) * 4)
    for k, idx in enumerate(img):
        r, g, b = pal[idx]
        a = 0 if (transparent_index0 and idx == 0) else 255
        out[k * 4 : k * 4 + 4] = bytes((r, g, b, a))
    return bytes(out)


# ---------------------------------------------------------------------------


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "sprites").mkdir(exist_ok=True)

    rg = ec.parse_gff(GAME / REGION_FILE)
    res = ec.parse_gff(GAME / "RESOURCE.GFF")
    objdb = ec.parse_gff(GAME / "SEGOBJEX.GFF")
    gp = ec.parse_gff(GAME / "GPLDATA.GFF")
    pal = load_palette(res)

    (rid,) = {cid for cid, _ in ec.resolve_type(rg, "RMAP")}
    rmap = ec.get_chunk(rg, "RMAP", rid)
    gmap = ec.get_chunk(rg, "GMAP", rid)
    etab = ec.get_chunk(rg, "ETAB", rid)
    assert len(rmap) == len(gmap) == 128 * 98

    # --- tiles: the region's own TILE chunks, atlas-ified -----------------
    tile_chunks = dict(ec.resolve_type(rg, "TILE"))
    used = sorted({b for b in rmap if b and b in tile_chunks})
    slot = {t: i for i, t in enumerate(used)}
    atlas_cols = 16
    atlas_rows = (len(used) + atlas_cols - 1) // atlas_cols
    atlas = bytearray(atlas_cols * 16 * atlas_rows * 16 * 4)
    for t in used:
        w, h, img = first_frame(tile_chunks[t])
        assert (w, h) == (16, 16), f"tile {t} is {w}x{h}"
        col, row = slot[t] % atlas_cols, slot[t] // atlas_cols
        for py in range(h):
            o = ((row * 16 + py) * atlas_cols * 16 + col * 16) * 4
            atlas[o : o + 64] = indices_to_rgba(
                img[py * 16 : py * 16 + 16], pal, False
            )
    pngio.write_rgba(OUT / "tiles_atlas.png", atlas_cols * 16, atlas_rows * 16, atlas)
    print(f"tiles: {len(used)} distinct -> atlas {atlas_cols*16}x{atlas_rows*16}")

    # --- walls: GPLDATA WALL[rid*100 + w - 1], bottom-anchored ------------
    wall_ids = sorted({b & 0x1F for b in gmap if b & 0x1F})
    wall_files = {}
    for w in wall_ids:
        cid = rid * 100 + w - 1
        fw, fh, img = first_frame(ec.get_chunk(gp, "WALL", cid))
        name = f"sprites/wall_{w:02d}.png"
        pngio.write_rgba(OUT / name, fw, fh, indices_to_rgba(img, pal, True))
        wall_files[w] = (name, fw, fh)
    print(f"walls: {len(wall_ids)} distinct wall indices")

    # --- entity sprites: ETAB -> OJFF -> SEGOBJEX BMP ---------------------
    ojff = {cid: p for cid, p in ec.resolve_type(objdb, "OJFF")}
    bmp_chunks = dict(ec.resolve_type(objdb, "BMP"))
    sprite_files = {}
    entities = []
    skipped_oob = 0
    n_placements = len(etab) // 8
    for k in range(n_placements):
        x, y = struct.unpack_from("<hh", etab, k * 8)
        zpos = struct.unpack_from("<b", etab, k * 8 + 4)[0]
        flags = etab[k * 8 + 5]
        oid = abs(struct.unpack_from("<h", etab, k * 8 + 6)[0])
        o = ojff.get(oid)
        if o is None:
            continue
        ox, oy, bmp = struct.unpack_from("<HH", o, 0)[0], struct.unpack_from("<H", o, 2)[0], struct.unpack_from("<H", o, 12)[0]
        dx, dy = x - ox, y - oy - zpos
        if dx < 0 or dy < 0 or dx >= 2048 or dy >= 1568 or bmp not in bmp_chunks:
            skipped_oob += 1
            continue
        if bmp not in sprite_files:
            sw, sh, img = first_frame(bmp_chunks[bmp])
            name = f"sprites/bmp_{bmp:04d}.png"
            pngio.write_rgba(OUT / name, sw, sh, indices_to_rgba(img, pal, True))
            sprite_files[bmp] = (name, sw, sh)
        name, sw, sh = sprite_files[bmp]
        entities.append(
            {
                "x": dx,
                "y": dy,
                "w": sw,
                "h": sh,
                "png": name,
                "flip": bool(flags & 0x80),
                "prio": flags & 7,
                "oid": oid,
            }
        )
    print(
        f"entities: {len(entities)} drawn, {skipped_oob} skipped "
        f"(off-grid or unresolved) of {n_placements} placements; "
        f"{len(sprite_files)} distinct sprites"
    )

    # --- map data ----------------------------------------------------------
    cells = []
    for ty in range(98):
        for tx in range(128):
            t = rmap[ty * 128 + tx]
            if t in slot:
                cells.append([tx, ty, slot[t] % atlas_cols, slot[t] // atlas_cols])
    blocked_rows = [
        "".join("#" if gmap[ty * 128 + tx] & 0x40 else "." for tx in range(128))
        for ty in range(98)
    ]
    walls_out = []
    for ty in range(98):
        for tx in range(128):
            w = gmap[ty * 128 + tx] & 0x1F
            if w and w in wall_files:
                name, fw, fh = wall_files[w]
                walls_out.append(
                    {"x": tx * 16, "y": (ty + 1) * 16 - fh, "w": fw, "h": fh, "png": name}
                )
    json.dump(
        {
            "region_file": REGION_FILE,
            "region_id": rid,
            "tile": 16,
            "cells": cells,
            "blocked_rows": blocked_rows,
            "walls": walls_out,
            "entities": entities,
        },
        open(OUT / "region.json", "w"),
    )
    blocked_n = sum(r.count("#") for r in blocked_rows)
    print(
        f"map: {len(cells)} tiled cells, {blocked_n} blocked, {len(walls_out)} wall sprites"
    )
    print(f"wrote {OUT}/ (atlas, tileset.tres, sprites/, region.json)")

    with open(OUT / "tileset.tres", "w") as f:
        f.write('[gd_resource type="TileSet" load_steps=3 format=3]\n\n')
        f.write(
            '[ext_resource type="Texture2D" path="res://generated/tiles_atlas.png" id="1"]\n\n'
        )
        f.write('[sub_resource type="TileSetAtlasSource" id="atlas"]\n')
        f.write("texture = ExtResource(\"1\")\n")
        for i in range(len(used)):
            f.write(f"{i % atlas_cols}:{i // atlas_cols}/0 = 0\n")
        f.write("\n[resource]\ntile_size = Vector2i(16, 16)\n")
        f.write("sources/0 = SubResource(\"atlas\")\n")


if __name__ == "__main__":
    main()
