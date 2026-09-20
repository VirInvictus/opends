#!/usr/bin/env python3
"""Export the Draj demo regions (Arena + Slave Pens) for the Godot demo.

Pipeline for the port demo (port-spike/): reads the two opening regions
of Dark Sun: Shattered Lands with the repo's Python GFF reader, decodes
DS1-RLE bitmaps directly (spec: docs/presentation-formats.md 1),
recolors through the engine-default CPAL 200, and emits per-region
assets plus demo.json (start tile, party, and the region transitions,
pinned from the games' own GPL handlers: see README).

Stdlib-only; no game file is modified. Usage:

    python3 export_region.py            # export + write demo.json + BFS checks
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
PALETTE_KIND, PALETTE_ID = "PAL", 1000  # the world palette (CPAL 200 is the engine's pink fallback)

# The demo's maps: the opening of Shattered Lands.
#   41 = RGN29.GFF  Slave Pens (Scar, Merzol, Dinos; 117 triggers)
#   42 = RGN2A.GFF  the Arena (crowd sprites, the Announcer; boot special-case)
REGIONS = [(41, "RGN29.GFF", "Slave Pens"), (42, "RGN2A.GFF", "Arena")]
START = {"region": 41, "x": 79, "y": 70}  # pens, just south of the arrival zone
PARTY_OIDS = [300, 305, 307, 313]  # Cermak, Saria, Cilla, K'ratchek

# The first arena fight. The shipped spawn scripts place object 2039
# (request 7) at tiles (59,15)/(53,21)/(6,18)/(11,23); its combat record
# is a pool reference (action 3, index 315) rather than inline data, so
# the demo assigns spawn stats (documented as demo values, not mined
# data). Fight N spawns 2+N monsters, capped.
FIGHT = {
    "monster_oid": 2039,
    "monster": {"bmp": 2205, "hp": 12, "ac": 6, "thac0": 19, "move": 12,
                "blows": 1,
                "dice": 1, "sides": 6, "bonus": 0},
    "spawn_tiles": [[59, 15], [53, 21], [6, 18], [11, 23]],
    "zone_box": [22, 18, 16, 10],  # arena floor: entering starts the fight
}

# Transitions pinned from the shipped GPL handlers (see README for the
# disassembly evidence). Tiles/boxes in the FROM region; landing tile in
# the TO region.
TRANSITIONS = [
    {
        "name": "escape tunnel",
        "region": 42,
        "tiles": [[5, 32], [6, 31], [7, 30]],
        "to": {"region": 41, "x": 79, "y": 66},
    },
    {
        "name": "holding gate",
        "region": 42,
        "box": [28, 11, 5, 1],
        "to": {"region": 41, "x": 113, "y": 27},
    },
    {
        "name": "arena stair",
        "region": 41,
        "box": [112, 27, 3, 1],
        "to": {"region": 42, "x": 30, "y": 13},
    },
    {
        "name": "arrival zone (story beat, no exit)",
        "region": 41,
        "box": [79, 65, 1, 6],
        "to": None,
    },
]

# The shipped GMAP locks the arena's west escape door (the pens escape
# script, GPL chunk 3 @ 0x6b4: "Gladiators escaping! Guards! Sound the
# alarms!", opens it in play). The demo starts post-escape, so unblock
# exactly the three tunnel tiles.
DEMO_UNBLOCK = {42: [[5, 32], [6, 31], [7, 30]]}

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

def decode_frame(data: bytes, off: int, flip: bool = True) -> tuple[int, int, bytes]:
    """Decode one bitmap-container frame to (w, h, palette indices).

    flip=True gives the libgff orientation (correct for TILE and WALL);
    SEGOBJEX entity BMPs come out vertically inverted relative to
    in-game rendering unless flipped AGAIN (region-render flips them at
    load; here we just skip the first flip).
    """
    w, h = struct.unpack_from("<HH", data, off)
    if data[off + 5 : off + 9] in (b"PLNR", b"PLAN"):
        raise NotImplementedError("PLNR/PLAN frame (the demo covers DS1 RLE only)")
    img = bytearray(w * h)
    cpos = off + 4  # RLE stream starts at +4; the tag bytes are stream data
    rows = 0
    while rows < h:
        row_num = data[cpos]
        cpos += 1
        if row_num == 0xFF:
            break
        base = ((h - row_num - 1) if flip else row_num) * w
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


def first_frame(data: bytes, flip: bool = True) -> tuple[int, int, bytes]:
    _size, frame_count = struct.unpack_from("<IH", data, 0)
    if frame_count < 1:
        raise ValueError("empty bitmap container")
    (off,) = struct.unpack_from("<I", data, 6)
    return decode_frame(data, off, flip)


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
# Region export

def export_region(rid: int, fname: str, label: str, rg, gp, objdb, pal) -> dict:
    out = OUT / f"r{rid}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sprites").mkdir(exist_ok=True)

    rmap = ec.get_chunk(rg, "RMAP", rid)
    gmap = ec.get_chunk(rg, "GMAP", rid)
    etab = ec.get_chunk(rg, "ETAB", rid)
    assert len(rmap) == len(gmap) == 128 * 98

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
            atlas[o : o + 64] = indices_to_rgba(img[py * 16 : py * 16 + 16], pal, False)
    pngio.write_rgba(out / "tiles_atlas.png", atlas_cols * 16, atlas_rows * 16, atlas)

    wall_ids = sorted({b & 0x1F for b in gmap if b & 0x1F})
    wall_files = {}
    for w in wall_ids:
        cid = rid * 100 + w - 1
        fw, fh, img = first_frame(ec.get_chunk(gp, "WALL", cid))  # walls keep the libgff flip
        name = f"wall_{w:02d}.png"
        pngio.write_rgba(out / "sprites" / name, fw, fh, indices_to_rgba(img, pal, True))
        wall_files[w] = (name, fw, fh)

    ojff = {cid: p for cid, p in ec.resolve_type(objdb, "OJFF")}
    bmp_chunks = dict(ec.resolve_type(objdb, "BMP"))
    sprite_files = {}
    entities = []
    skipped_oob = 0
    for k in range(len(etab) // 8):
        x, y = struct.unpack_from("<hh", etab, k * 8)
        zpos = struct.unpack_from("<b", etab, k * 8 + 4)[0]
        flags = etab[k * 8 + 5]
        oid = abs(struct.unpack_from("<h", etab, k * 8 + 6)[0])
        o = ojff.get(oid)
        if o is None:
            continue
        # OJFF field map (engine-verified, wall/door research): word@2 =
        # x offset, word@4 = y offset, word@0 = a baked placement x the
        # engine ignores for drawing.
        ox, oy = struct.unpack_from("<HH", o, 2)
        (bmp,) = struct.unpack_from("<H", o, 12)
        dx, dy = x - ox, y - oy - zpos
        if dx < 0 or dy < 0 or dx >= 2048 or dy >= 1568 or bmp not in bmp_chunks:
            skipped_oob += 1
            continue
        if bmp not in sprite_files:
            sw, sh, img = first_frame(bmp_chunks[bmp], flip=False)  # entity BMPs: see decode_frame
            name = f"bmp_{bmp:04d}.png"
            pngio.write_rgba(out / "sprites" / name, sw, sh, indices_to_rgba(img, pal, True))
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
    for tx, ty in DEMO_UNBLOCK.get(rid, []):
        blocked_rows[ty] = blocked_rows[ty][:tx] + "." + blocked_rows[ty][tx + 1 :]
    walls_out = []
    for ty in range(98):
        for tx in range(128):
            w = gmap[ty * 128 + tx] & 0x1F
            if w and w in wall_files:
                name, fw, fh = wall_files[w]
                # Placement per region-render (RegionTool.java 289-290):
                # centered horizontally on the tile, bottom-aligned to
                # the tile's own bottom edge.
                walls_out.append(
                    {
                        "x": tx * 16 + 8 - fw // 2,
                        "y": (ty + 1) * 16 - fh,
                        "w": fw,
                        "h": fh,
                        "png": name,
                        "sort_y": (ty + 1) * 16 + 1,
                    }
                )
    json.dump(
        {
            "region_id": rid,
            "label": label,
            "tile": 16,
            "cells": cells,
            "blocked_rows": blocked_rows,
            "walls": walls_out,
            "entities": entities,
        },
        open(out / "region.json", "w"),
    )
    with open(out / "tileset.tres", "w") as f:
        f.write('[gd_resource type="TileSet" load_steps=3 format=3]\n\n')
        f.write(
            '[ext_resource type="Texture2D" path="res://generated/'
            f"r{rid}/tiles_atlas.png\" id=\"1\"]\n\n"
        )
        f.write('[sub_resource type="TileSetAtlasSource" id="atlas"]\n')
        f.write("texture = ExtResource(\"1\")\n")
        for i in range(len(used)):
            f.write(f"{i % atlas_cols}:{i // atlas_cols}/0 = 0\n")
        f.write("\n[resource]\ntile_size = Vector2i(16, 16)\n")
        f.write("sources/0 = SubResource(\"atlas\")\n")

    blocked_n = sum(r.count("#") for r in blocked_rows)
    print(
        f"region {rid} ({label}): {len(used)} tiles, {len(entities)} entities drawn "
        f"({skipped_oob} off-grid skipped), {blocked_n} blocked, {len(walls_out)} walls"
    )
    return {
        "id": rid,
        "label": label,
        "dir": f"r{rid}",
        "blocked_rows": blocked_rows,
    }


def walkable(reg: dict, x: int, y: int) -> bool:
    return 0 <= x < 128 and 0 <= y < 98 and reg["blocked_rows"][y][x] == "."


def bfs(reg: dict, src: tuple[int, int], dst: tuple[int, int]) -> int | None:
    """Tile length of a 4-dir path, or None."""
    if not (walkable(reg, *src) and walkable(reg, *dst)):
        return None
    seen = {src}
    frontier = [src]
    dist = 0
    while frontier:
        nxt = []
        for x, y in frontier:
            if (x, y) == dst:
                return dist
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if walkable(reg, nx, ny) and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    nxt.append((nx, ny))
        frontier = nxt
        dist += 1
    return None


def zone_tiles(tr) -> list[tuple[int, int]]:
    if "tiles" in tr:
        return [tuple(t) for t in tr["tiles"]]
    bx, by, bw, bh = tr["box"]
    return [(bx + dx, by + dy) for dx in range(bw) for dy in range(bh)]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    res = ec.parse_gff(GAME / "RESOURCE.GFF")
    objdb = ec.parse_gff(GAME / "SEGOBJEX.GFF")
    gp = ec.parse_gff(GAME / "GPLDATA.GFF")
    pal = load_palette(res)

    (party_bmp,) = (None,)
    ojff = {c: p for c, p in ec.resolve_type(objdb, "OJFF")}
    rdff = {c: p for c, p in ec.resolve_type(objdb, "RDFF")}
    party_bmps = []
    for oid in PARTY_OIDS:
        (bmp,) = struct.unpack_from("<H", ojff[oid], 12)
        party_bmps.append(bmp)

    regions = {}
    for rid, fname, label in REGIONS:
        rg = ec.parse_gff(GAME / fname)
        regions[str(rid)] = export_region(rid, fname, label, rg, gp, objdb, pal)

    # The party sprites are not ETAB-placed; make sure every region ships
    # them so the demo can use the same files everywhere. Always
    # overwrite: a stale file here survives codec/palette/flip fixes.
    # Also ship the arena fight monster's sprite (FIGHT.monster_oid).
    bmp_chunks = dict(ec.resolve_type(objdb, "BMP"))
    extra = party_bmps + [FIGHT["monster"]["bmp"]]
    for rid, _, _ in REGIONS:
        for bmp in extra:
            sw, sh, img = first_frame(bmp_chunks[bmp], flip=False)
            pngio.write_rgba(
                OUT / f"r{rid}" / "sprites" / f"bmp_{bmp:04d}.png",
                sw,
                sh,
                indices_to_rgba(img, pal, True),
            )

    # BFS sanity: the start reaches every exit zone of its region, and
    # each destination tile is walkable.
    start_reg = regions[str(START["region"])]
    assert walkable(start_reg, START["x"], START["y"]), "start tile is blocked"
    for tr in TRANSITIONS:
        reg = regions[str(tr["region"])]
        zone = zone_tiles(tr)
        open_tiles = [t for t in zone if walkable(reg, *t)]
        assert open_tiles, f"transition {tr['name']}: no walkable source tile"
        if tr["to"]:
            dest = regions[str(tr["to"]["region"])]
            assert walkable(dest, tr["to"]["x"], tr["to"]["y"]), (
                f"transition {tr['name']}: dest blocked"
            )
        if tr["region"] == START["region"]:
            path = bfs(start_reg, (START["x"], START["y"]), open_tiles[0])
            if path is None:
                print(f"WARN: transition {tr['name']}: no path from start to {open_tiles[0]}")
            else:
                print(f"transition {tr['name']}: reachable in {path} steps from start")
        else:
            print(f"transition {tr['name']}: source zone in the other region")

    # Party stats: hp/psp from charrec (+8), AC from the combat block
    # (+26, current incl. their kit), THAC0 from combat (+31). Attack
    # dice are demo values (the presets' shipped attack slot is the
    # unarmed 1x1d1).
    party_stats = []
    for oid in PARTY_OIDS:
        blocks = ec.walk_rdff(rdff[oid], oid)
        charrec = next((b.payload for b in blocks
                        if b.load_action == 3 and b.type == 4 and len(b.payload) > 40), None)
        combat = next((b.payload for b in blocks
                       if b.type == 2 and b.load_action == 1 and len(b.payload) >= 58), None)
        hp = ec.u16(charrec, 8)
        ac = ec.i8(combat, 26) if combat else 10
        thac0 = ec.i8(combat, 31) if combat else 20
        move = ec.u8(combat, 27) if combat else 12
        blows = ec.u8(charrec, 0x2A) if charrec else 1
        party_stats.append({"oid": oid, "hp": hp, "max_hp": hp,
                            "ac": ac, "thac0": thac0, "move": move,
                            "blows": max(1, blows),
                            "dice": 1, "sides": 8, "bonus": 1})

    # Transitions: the break-out (escape tunnel) stays GATED until the
    # arena loop is done, per the demo scope.
    gated = [tr for tr in TRANSITIONS if tr["name"] == "escape tunnel"]
    live = [tr for tr in TRANSITIONS if tr["name"] != "escape tunnel"]

    json.dump(
        {
            "start": START,
            "party_bmps": party_bmps,
            "party_stats": party_stats,
            "fight": FIGHT,
            "regions": {k: {"id": v["id"], "label": v["label"], "dir": v["dir"]} for k, v in regions.items()},
            "transitions": live,
            "gated_transitions": gated,
        },
        open(OUT / "demo.json", "w"),
        indent=1,
    )
    print(f"wrote {OUT}/demo.json")


if __name__ == "__main__":
    main()
