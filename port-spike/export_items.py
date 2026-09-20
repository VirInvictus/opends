#!/usr/bin/env python3
"""Export item inventory icons + cell overlay art for the Godot port.

- Item icons: an item's inventory icon is its base object's OJFF bmp_id
  sprite, decoded from SEGOBJEX.GFF with PAL/1000 (docs/asset-bindings.md
  1; proven against the DOSBox oracle: K'tarchek's blue cell icon is
  object 1010 Chatkcha -> BMP 2381, and the sprite is what renders).
- Cell overlays: RESOURCE BMP 13007. Frames 9..22 are the 14 paperdoll
  empty-slot glyphs in body-slot-table order (matched 1.00 correlation
  against the oracle capture, 2026-09-20; f12/f19 and f13/f20 are the
  paired hand/finger slots). Frame 4 = yellow selection square, 6 = red
  X (illegal drop), 7/8 = alt selections, 0/2/5 = plain cell interiors.
- Damage splats: RESOURCE BMP 5014, 5 frames (small red, big red,
  green, grey puff, gold star).
- Parchment: RESOURCE BMP 13005, the inventory centre card.

Writes generated/ui/item_icons.json + PNGs. Stdlib-only; decodes with
export_region's DS1-RLE reader and recolors through PAL/1000.
"""

from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "generated" / "ui"
DS1 = REPO / ".games" / "ds1"

sys.path.insert(0, str(HERE))
import pngio  # noqa: E402
import export_region as er  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "opds_extract", REPO / "tools/gff-edit/scripts/extract-catalogue.py"
)
ec = importlib.util.module_from_spec(_spec)
sys.modules["opds_extract"] = ec
_spec.loader.exec_module(ec)

# The demo party's gear, picked from docs/creature-inventories-ds1.md:
# common field kit, legal for each member's classes. K'ratchek's Chatkcha
# matches the factory save the oracle capture came from.
KITS = {
    0: [1013, 1189, 1022, 1026],  # Cermak: long sword, shield, chest, legs
    1: [1011, 1010],  # K'ratchek: gythka, chatkcha
    2: [1012, 1017, 1070],  # Saria: long sword, bow, arrows
    3: [1187, 1023],  # Silla: mace, arm armor
}

CELL_BMP = 13007
SPLAT_BMP = 5014
PARCHMENT_BMP = 13005
# Frame ids inside BMP 13007 (see the module docstring for the proven map).
FRAME_SELECT_YELLOW = 4
FRAME_ILLEGAL = 6
FRAME_SELECT_PINK = 7
FRAME_SELECT_BLUE = 8
FRAME_PLAIN = 5
GLYPH_FRAME0 = 9  # f9 + paperdoll slot 0..13


def load_palette() -> list[tuple[int, int, int]]:
    res = ec.parse_gff(DS1 / "RESOURCE.GFF")
    return er.load_palette(res)


def decode_container_frame(
    container: bytes, fi: int, pal, resource: bool
) -> tuple[int, int, bytes]:
    """Decode frame fi of a bitmap container to (w, h) + RGBA, index 0
    transparent. SEGOBJEX sprites come out game-side up with the flip
    skipped; RESOURCE art needs the libgff flip plus a vertical mirror
    (what image-extract + the exporters' FLIP_TOP_BOTTOM postfix do)."""
    w, h, img = er.decode_frame(container, frame_offset(container, fi), flip=resource)
    if resource:
        img = b"".join(img[y * w : (y + 1) * w] for y in reversed(range(h)))
    return w, h, er.indices_to_rgba(img, pal, True)


def frame_offset(container: bytes, fi: int) -> int:
    return struct.unpack_from("<I", container, 6 + fi * 4)[0]


def frame_count(container: bytes) -> int:
    return struct.unpack_from("<H", container, 4)[0]


def write_png(path: Path, w: int, h: int, rgba: bytes) -> None:
    pngio.write_rgba(path, w, h, rgba)


def export_item_icons(pal) -> dict[int, dict]:
    objdb = ec.parse_gff(DS1 / "SEGOBJEX.GFF")
    bmps = dict(ec.resolve_type(objdb, "BMP"))
    ojff = dict(ec.resolve_type(objdb, "OJFF"))
    gp = ec.parse_gff(DS1 / "GPLDATA.GFF")
    it1r = ec.get_chunk(gp, "IT1R", 1)
    name_raw = ec.get_chunk(gp, "NAME", 1)
    pool = [
        ec.cstr(name_raw[k * 25 : (k + 1) * 25]) for k in range(len(name_raw) // 25)
    ]

    _creatures, items, _minis, _templates, _stats, _inventories = ec.extract_objects(
        "ds1", DS1 / "SEGOBJEX.GFF"
    )

    wanted = sorted({oid for kit in KITS.values() for oid in kit})
    out: dict[int, dict] = {}
    for oid in wanted:
        oj = ojff.get(oid)
        if oj is None:
            print(f"object {oid}: no OJFF")
            continue
        bmp_id = ec.u16(oj, 12)
        data = bmps.get(bmp_id)
        if data is None:
            print(f"object {oid}: OJFF bmp {bmp_id} missing in SEGOBJEX")
            continue
        w, h, rgba = decode_container_frame(data, 0, pal, resource=False)
        png = f"objicon_{oid}.png"
        write_png(OUT / png, w, h, rgba)
        row = items.get(oid)
        place = dice = sides = mod = attacks = 0
        name = ""
        if row is not None and 0 <= row.stats_index < len(it1r) // 20:
            st = ec.decode_ds1_it1r(it1r, row.stats_index)
            place, dice, sides, mod, attacks = (
                st.slot,
                st.dice,
                st.sides,
                st.mod,
                st.attacks,
            )
            if 0 <= row.name_idx < len(pool):
                name = pool[row.name_idx]
        out[oid] = {
            "png": png,
            "w": w,
            "h": h,
            "name": name,
            "place": place,
            "dice": dice,
            "sides": sides,
            "mod": mod,
            "attacks": attacks,
        }
        print(f"object {oid}: {name!r} bmp {bmp_id} {w}x{h} place {place}")
    return out


def export_overlays(pal) -> dict:
    res = ec.parse_gff(DS1 / "RESOURCE.GFF")
    bmps = dict(ec.resolve_type(res, "BMP"))
    out: dict = {}

    cell = bmps[CELL_BMP]
    frames = []
    for fi in range(frame_count(cell)):
        w, h, rgba = decode_container_frame(cell, fi, pal, resource=True)
        png = f"cell13007_f{fi}.png"
        write_png(OUT / png, w, h, rgba)
        frames.append({"png": png, "w": w, "h": h})
    out["cell"] = {
        "frames": frames,
        "glyph_frame0": GLYPH_FRAME0,
        "plain": FRAME_PLAIN,
        "select_yellow": FRAME_SELECT_YELLOW,
        "select_pink": FRAME_SELECT_PINK,
        "select_blue": FRAME_SELECT_BLUE,
        "illegal": FRAME_ILLEGAL,
    }
    print(f"BMP {CELL_BMP}: {len(frames)} cell frames")

    splat = bmps[SPLAT_BMP]
    splats = []
    for fi in range(frame_count(splat)):
        w, h, rgba = decode_container_frame(splat, fi, pal, resource=True)
        png = f"splat_f{fi}.png"
        write_png(OUT / png, w, h, rgba)
        splats.append({"png": png, "w": w, "h": h})
    out["splats"] = {
        "frames": splats,
        "small": 0,
        "big": 1,
        "poison": 2,
        "miss": 3,
        "crit": 4,
    }
    print(f"BMP {SPLAT_BMP}: {len(splats)} splat frames")

    parch = bmps[PARCHMENT_BMP]
    w, h, rgba = decode_container_frame(parch, 0, pal, resource=True)
    write_png(OUT / "parchment_13005.png", w, h, rgba)
    out["parchment"] = {"png": "parchment_13005.png", "w": w, "h": h}
    print(f"BMP {PARCHMENT_BMP}: {w}x{h} parchment")
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pal = load_palette()
    items = export_item_icons(pal)
    overlays = export_overlays(pal)
    payload = {"items": {str(k): v for k, v in items.items()}, "kits": KITS, **overlays}
    (OUT / "item_icons.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote {OUT}/item_icons.json ({len(items)} item icons)")


if __name__ == "__main__":
    main()
