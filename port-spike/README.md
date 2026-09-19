# port-spike: one Dark Sun region, live in Godot

The proof-of-life for the Godot port (docs/godot-port-readiness.md
section C, realized 2026-09-19): export one region's tiles, walls, and
entity sprites straight from the game files, rebuild it as a real Godot
4 TileMap scene, and screenshot it. This is not the port and not a
shipped tool; it is the smallest end-to-end walk of the data pipeline
the port will use. It consumes only decoded, documented formats and
modifies nothing.

## Run it

```sh
python3 export_region.py                 # exports RGN02.GFF (DS1 start region)
godot --headless --import --path .      # first run only: import textures
SPIKE_SHOT=/tmp/shot.png godot --path . # windowed run; saves a screenshot and quits
```

Requires the games under `.games/ds1/` and Godot 4.x on PATH. Stdlib-only
Python; no cargo, no assets committed (generated/ is gitignored).

## What it proves

- The repo's Python GFF reader (`tools/gff-edit/scripts/extract-catalogue.py`)
  parses regions and the SEGOBJEX object database well enough to drive a
  real engine scene.
- The DS1-RLE bitmap codec is fully reproducible from the docs
  (presentation-formats.md 1): tiles, walls, and sprites decode to
  palette indices; recolored through the engine-default CPAL 200 the
  output matches region-render's composite of the same region.
- The placement -> OJFF -> BMP binding (asset-bindings.md 1) puts every
  entity at its correct world position.
- The export is verifiable against the world dump: Region 2's 558
  placements = 465 drawn + the 93 documented off-grid staging
  placements; 6,598 blocked tiles; 645 wall sprites.

## What it fakes (on purpose)

- Static: entity frame 0 only, no SCMD animation, no triggers, no
  movement, no palette cycling (region-render 0.8.0 already animates
  those).
- Region 2's 93 off-grid staging placements are skipped (they sit
  outside the 2048x1568 world by design).
- PLNR/PLAN frames would abort the export; Region 2 needs none (all its
  tiles, walls, and sprites are DS1 RLE).
- Camera starts at the region center; there is no input.

## Files

| file | role |
|---|---|
| export_region.py | the exporter: RGN -> atlas + sprites + region.json + tileset.tres |
| pngio.py | minimal RGBA PNG writer (stdlib) |
| project.godot / main.tscn / main.gd | the Godot side: TileMapLayer + walls + y-sorted entities + camera |
| generated/ | gitignored exporter output |
