#!/usr/bin/env python3
"""Tile the baked intro frames into contact sheets for visual judging.

Reads generated/cine.json (timeline order = playback order) and writes
/tmp/spike/cine_sheet_NN.png: 8x5 grids of 160x100 tiles. Frames are
DOWNSCALED 320x200 -> 160x100 (the whole frame is visible in its tile;
an earlier hand-rolled packer cropped tiles to the left half, which
read as clipped text on the story screens).

Stdlib-only (PIL if available, else pngio + manual averaging).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "generated" / "cine"
SHEET_DIR = Path("/tmp/spike")

COLS, ROWS = 8, 5
TW, TH = 160, 100


def main() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("PIL required (python3 -c 'import PIL' failed)")
        raise SystemExit(1)

    cine = json.load(open(HERE / "generated" / "cine.json"))
    files: list[str] = []
    for part in cine["parts"]:
        for ev in part["timeline"]:
            if ev.get("kind") in ("frame", "still"):
                files.append(ev["png"])
    print(f"{len(files)} frames in timeline order")

    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    per = COLS * ROWS
    for sheet_i in range(0, len(files), per):
        sheet = Image.new("RGB", (COLS * TW, ROWS * TH), (20, 20, 20))
        for k, name in enumerate(files[sheet_i : sheet_i + per]):
            im = Image.open(OUT / name).convert("RGB").resize((TW, TH), Image.NEAREST)
            sheet.paste(im, ((k % COLS) * TW, (k // COLS) * TH))
        out = SHEET_DIR / f"cine_sheet_{sheet_i // per:02d}.png"
        sheet.save(out)
    n_sheets = (len(files) + per - 1) // per
    print(f"wrote {n_sheets} sheets to {SHEET_DIR}/cine_sheet_NN.png")


if __name__ == "__main__":
    main()
