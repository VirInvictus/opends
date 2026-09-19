# port-spike: the Draj demo — the Slave Pens and the Arena in Godot 4

A working demo of Dark Sun: Shattered Lands' opening maps: walk the four
preset gladiators through the Slave Pens and out into the Arena of Draj.
Built on the region pipeline proven by the port-mining campaign
(docs/godot-port-readiness.md); consumes only decoded, documented formats
and modifies nothing in the game install.

## Run it

```sh
python3 export_region.py                 # exports regions 41 + 42 + demo.json
godot --headless --import --path .      # first run only: import textures
godot --path .                           # play
```

Walk with arrow keys / WASD (hold to keep stepping) or click a tile to
path there. Step on the exits and the demo switches regions, exactly
where the real game's doors are. `SPIKE_SHOT=<file> godot --path .`
saves a screenshot and quits; `SPIKE_DEMO=1` runs a scripted
pens -> arena verification walk with screenshots.

Requires the games under `.games/ds1/` and Godot 4.x. Stdlib-only
Python; `generated/` is gitignored.

## The maps and the exits (all pinned from the shipped bytecode)

| Region | File | What it is |
|---|---|---|
| 41 | RGN29.GFF | the Slave Pens: Scar, Merzol, Dinos, the fountain; 117 triggers |
| 42 | RGN2A.GFF | the Arena: crowd stands, the Announcer's booth, the central monster grate; the engine boot-cases this region |

Transitions, decoded with tools/gpl-disasm from the regions' own move
triggers:

- Arena tiles (5,32)/(6,31)/(7,30), the west escape tunnel (GPL 3
  @ 0x6b4, "Gladiators escaping! Guards! Sound the alarms!") ->
  Pens tile (79,66).
- Arena box (28,11,5x1), the holding gate (GPL 3 @ 0x73e) ->
  Pens tile (113,27).
- Pens box (112,27,3x1), the arena stair (GPL 137 @ 0xbc5, which asks
  "Enter the arena?") -> Arena tile (30,13).
- Pens box (79,65,1x6) is arrival-only: its handler (GPL 137 @ 0xd45)
  is the story beat "The doors to the arena slam shut behind you."

## Two rendering facts the demo pins down

- Entity BMPs from SEGOBJEX decode vertically inverted relative to
  in-game rendering; walls and tiles do not (region-render's source
  says the same). The exporter flips tiles/walls and skips the flip
  for entity sprites.
- The world palette is RESOURCE.GFF `PAL` 1000. The CPAL 200 fallback
  is the engine's pink lookup, not the Draj look.

## What it fakes (on purpose)

No combat, no GPL execution (the transitions above are the decoded
Tport sites, hard-wired), no door mechanics (the pens' cell doors stay
locked; the escape tunnel is unblocked as the post-escape state), entity
frame 0 only, no palette cycling. The start is pens tile (79,70), next
to the arrival zone.

## Files

| file | role |
|---|---|
| export_region.py | exports both regions (atlas, sprites, region.json, tileset.tres) + demo.json with the transition table and BFS reachability checks |
| pngio.py | minimal RGBA PNG writer (stdlib) |
| project.godot / main.tscn / main.gd | the demo: TileMapLayer, y-sorted entities, party trail, click-to-walk BFS, region transitions |
| generated/ | gitignored exporter output |
