#!/usr/bin/env python3
"""Export FONT/100 (RESOURCE.GFF) into a runtime-ready two-layer atlas.

The font: u16 num=256, u16 height=9, u16 bg, u16 flags, u8 colors[256],
u16 char_offset[256]@264 (offsets from chunk start), glyphs@776:
u16 width + width*9 bytes row-major. Glyph bytes are palette indices:
0x00 = skip (transparent), 0xFE = black ink, 0x14 = the dark-blue
relief baked under/right of every glyph (under PAL/1000: (56,56,85)).
Line pitch is 9 px and advance equals the glyph width (proportional,
no kerning, no bearings).

The engine recolors text at print time (%C ink/relief pairs), so the
atlas ships as two WHITE masks: font_ink.png and font_relief.png; a
TextBlitter node modulates each layer to the wanted ink/relief pair.
Writes generated/ui/font_ink.png, font_relief.png, font_metrics.json.

Stdlib + Pillow (PNG post-fixes, same policy as export_ui.py).
"""

from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "generated" / "ui"
RESOURCE = REPO / ".games" / "ds1" / "RESOURCE.GFF"

FONT_ID = 100
HEIGHT = 9
COLS = 16  # atlas grid: 16 columns x 16 rows of cells

_spec = importlib.util.spec_from_file_location(
    "opds_extract", REPO / "tools/gff-edit/scripts/extract-catalogue.py"
)
ec = importlib.util.module_from_spec(_spec)
sys.modules["opds_extract"] = ec
_spec.loader.exec_module(ec)

# Under PAL/1000: 0xFE renders (0,0,0) and 0x14 renders (56,56,85). The
# masks are white + alpha so a modulate can pick any ink/relief pair.
RELIEF_RGB = (56, 56, 85)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = ec.parse_gff(RESOURCE)
    font = ec.get_chunk(res, "FONT", FONT_ID)

    num, height = struct.unpack_from("<HH", font, 0)
    bg, flags = struct.unpack_from("<HH", font, 4)
    assert num == 256 and height == HEIGHT, (num, height)
    offsets = struct.unpack_from("<256H", font, 264)

    widths = []
    glyph_bytes = []
    seen_indices = set()
    for code in range(256):
        o = offsets[code]
        w = struct.unpack_from("<H", font, o)[0]
        rows = font[o + 2 : o + 2 + w * HEIGHT]
        widths.append(w)
        glyph_bytes.append(rows)
        seen_indices.update(rows)

    print("bg:", bg, "flags:", flags)
    print("glyph palette indices seen:", sorted(seen_indices))
    print(
        "widths: space=%d 'i'=%d 'W'=%d max=%d"
        % (widths[32], widths[ord("i")], widths[ord("W")], max(widths))
    )

    cell_w = max(widths)
    ink = Image.new("RGBA", (COLS * cell_w, COLS * HEIGHT), (0, 0, 0, 0))
    relief = Image.new("RGBA", ink.size, (0, 0, 0, 0))
    ipx = ink.load()
    rpx = relief.load()

    chars = {}
    for code in range(256):
        w = widths[code]
        if w == 0:
            continue
        u = (code % COLS) * cell_w
        v = (code // COLS) * HEIGHT
        rows = glyph_bytes[code]
        for r in range(HEIGHT):
            for c in range(w):
                idx = rows[r * w + c]
                if idx == 0x00:
                    continue
                x, y = u + c, v + r
                if idx == 0xFE:
                    ipx[x, y] = (255, 255, 255, 255)
                elif idx == 0x14:
                    rpx[x, y] = (255, 255, 255, 255)
                else:
                    # unexpected palette index: bake it into ink for visibility
                    ipx[x, y] = (255, 0, 255, 255)
        chars[str(code)] = {"u": u, "v": v, "w": w}

    ink.save(OUT / "font_ink.png")
    relief.save(OUT / "font_relief.png")
    metrics = {
        "height": HEIGHT,
        "pitch": HEIGHT,
        "cell_w": cell_w,
        "cols": COLS,
        "ink_png": "font_ink.png",
        "relief_png": "font_relief.png",
        "chars": chars,
    }
    (OUT / "font_metrics.json").write_text(json.dumps(metrics, indent=1))
    print(
        "wrote",
        OUT / "font_ink.png",
        OUT / "font_relief.png",
        OUT / "font_metrics.json",
    )


if __name__ == "__main__":
    main()
