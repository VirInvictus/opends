#!/usr/bin/env python3
"""Export the DS1 main-menu UI from the game's own data.

- WIND/3000's items: the four BUTN placements (init positions in the
  320x200 menu space) and the ACCL/8100 accelerator.
- The button faces are ICON/2048..2051 (the flaming menu text), decoded
  to PNG with the game palette via tools/image-extract.
- ACCL/8100 keys: S/C/L/E upper+lower -> userids 8100..8107.

Writes generated/ui/ui.json + the button PNGs. Stdlib-only; shells out
to image-extract.
"""

from __future__ import annotations

import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "generated" / "ui"
RESOURCE = REPO / ".games" / "ds1" / "RESOURCE.GFF"
IMAGE_EXTRACT = REPO / "target" / "debug" / "image-extract"

_spec = importlib.util.spec_from_file_location(
    "opds_extract", REPO / "tools/gff-edit/scripts/extract-catalogue.py"
)
ec = importlib.util.module_from_spec(_spec)
sys.modules["opds_extract"] = ec
_spec.loader.exec_module(ec)

MENU_WIND = 3000
BUTTON_IDS = [2048, 2049, 2050, 2051]
NAMES = ["start", "create", "load", "exit"]
ACCL_ID = 8100
# The menu screen furniture: BMP 20028 is the burning arc with the green
# orb, BMP 20029 the ornate stone panel (both 2026-09-19, matched against
# a DOSBox capture of the real boot menu).
ARC_BMP = 20028
PANEL_BMP = 20029
# Measured off the real menu: the arc sits above the panel, both centred.
ARC_POS = [49, 38]
PANEL_POS = [3, 55]


def _postfix_png(path: Path) -> None:
    """image-extract emits top-down RGB with palette index 0 opaque; the
    menu art is stored top-down (so the tool's bottom-up flip shows it
    inverted) and index 0 is the transparent background. Flip back and
    punch index 0 out."""
    from PIL import Image

    pal_chunk = ec.get_chunk(ec.parse_gff(RESOURCE), "PAL", 1000)
    bg = (pal_chunk[0] * 255 // 63, pal_chunk[1] * 255 // 63, pal_chunk[2] * 255 // 63)
    im = Image.open(path).convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, _ = px[x, y]
            # image-extract rounds palette scaling slightly differently
            # (84 vs 85), so match the background index with tolerance
            if abs(r - bg[0]) <= 2 and abs(g - bg[1]) <= 2 and abs(b - bg[2]) <= 2:
                px[x, y] = (r, g, b, 0)
    im.save(path)


def _export_bitmap(kind: str, bid: int, name: str) -> dict:
    out_png = OUT / f"{name}.png"
    rr = subprocess.run(
        [str(IMAGE_EXTRACT), str(RESOURCE), "--kind", kind,
         "--id", str(bid), "--frame", "0",
         "-o", str(out_png), "--palette", "1000"],
        capture_output=True, text=True)
    if rr.returncode != 0:
        print(f"{kind} {bid} failed:", rr.stderr[-160:])
        return {}
    d = out_png.read_bytes()
    w, h = struct.unpack_from(">II", d, 16)
    _postfix_png(out_png)
    return {"png": f"{name}.png", "w": w, "h": h}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = ec.parse_gff(RESOURCE)

    wind = ec.get_chunk(res, "WIND", MENU_WIND)
    items = []
    for k in range(5):  # WIND/3000: ACCL + 4 BUTN
        o = 261 + 30 * k
        fourcc = wind[o + 4 : o + 8].decode("ascii", "replace").rstrip("\x00 ")
        iid = struct.unpack_from("<I", wind, o + 8)[0]
        init = struct.unpack_from("<2h", wind, o + 12)
        items.append({"type": fourcc, "id": iid, "init": list(init)})
    print("WIND/3000 items:", items)

    ui: dict = {"menu_space": [320, 200], "buttons": [], "keys": []}
    ui["arc"] = dict(_export_bitmap("BMP", ARC_BMP, "menu_arc"), pos=ARC_POS)
    ui["panel"] = dict(_export_bitmap("BMP", PANEL_BMP, "menu_panel"), pos=PANEL_POS)
    sys.path.insert(0, str(HERE))
    import export_cine

    for i, bid in enumerate(BUTTON_IDS):
        icon = ec.get_chunk(res, "ICON", bid)
        count = struct.unpack_from("<H", icon, 4)[0]
        pngs = []
        wh = None
        for fi in range(count):
            out_png = OUT / f"menu_{NAMES[i]}_{fi}.png"
            rr = subprocess.run(
                [str(IMAGE_EXTRACT), str(RESOURCE), "--kind", "ICON",
                 "--id", str(bid), "--frame", str(fi),
                 "-o", str(out_png), "--palette", "1000"],
                capture_output=True, text=True)
            if rr.returncode != 0:
                print(f"icon {bid} frame {fi} failed:", rr.stderr[-160:])
                continue
            # dims from the PNG header (IHDR)
            d = out_png.read_bytes()
            w, h = struct.unpack_from(">II", d, 16)
            _postfix_png(out_png)
            pngs.append({"png": f"menu_{NAMES[i]}_{fi}.png", "w": w, "h": h})
            wh = (w, h)
        pos = next((it["init"] for it in items
                    if it["type"] == "BUTN" and it["id"] == bid), [0, 0])
        ui["buttons"].append({"name": NAMES[i], "id": bid,
                              "x": pos[0], "y": pos[1],
                              "w": wh[0] if wh else 0, "h": wh[1] if wh else 0,
                              "frames": pngs, "frame_count": len(pngs)})
        print(f"button {NAMES[i]}: ICON {bid} {count} frames, "
              f"{len(pngs)} exported at {pos}")

    pal_chunk = ec.get_chunk(res, "PAL", 1000)
    pal = [(pal_chunk[j] * 255 // 63, pal_chunk[j + 1] * 255 // 63,
            pal_chunk[j + 2] * 255 // 63) for j in range(0, 768, 3)]
    accl = ec.get_chunk(res, "ACCL", ACCL_ID)
    count = struct.unpack_from("<H", accl, 12)[0]
    for k in range(count):
        o = 14 + 5 * k
        ui["keys"].append({"event": struct.unpack_from("<H", accl, o + 1)[0],
                           "userid": struct.unpack_from("<H", accl, o + 3)[0]})

    json.dump(ui, open(HERE / "generated" / "ui.json", "w"), indent=1)
    print(f"wrote {OUT}/ + ui.json")


if __name__ == "__main__":
    main()
