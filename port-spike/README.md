# port-spike: the Draj demo — intro, Slave Pens, Arena, and the first fight

A working demo of Dark Sun: Shattered Lands' opening loop in Godot 4:
the intro cinematic plays, then you walk the four preset gladiators out
of the Slave Pens, into the Arena of Draj, fight the first arena fight
with the mined combat math, and return to the pens to do it again.
Break-out options (the escape tunnel, attacking guards) are gated out
of this build by design. Built on the region pipeline proven by the
port-mining campaign; consumes only decoded, documented formats and
modifies nothing in the game install.

## Run it

```sh
python3 export_region.py      # regions 41 + 42, party/monster stats, demo.json
python3 export_cine.py        # intro frames + ACF playback timeline
godot --headless --import --path .   # first run only: import textures
godot --path .                # play
```

- **Intro**: the baked CINE.GFF timeline plays (Enter = next part,
  Esc = skip all).
- **Walk**: arrow keys / WASD (hold to keep stepping), or click a tile
  to path there. GMAP blocking applies.
- **The loop**: pens -> arena stair -> the fight zone starts the fight
  (monsters spawn at ring distance, converge, and fight with the mined
  math: d20 vs THAC0 - AC, bestiary attack dice, HP bars) -> victory
  opens the holding gate -> back to the pens -> the stair re-arms for
  the next, slightly harder fight.

Verification capture (what the quality checks watch):

```sh
SPIKE_DEMO=1 godot --path . --write-movie demo.avi --fixed-fps 30
ffmpeg -i demo.avi -c:v libx264 -crf 26 -preset fast demo.mp4
```

The scripted run plays the intro beat, skips, walks pens -> arena,
fights, wins, and returns; each QC pass is that video watched end to
end. Requires the games under `.games/ds1/` and Godot 4.x. Stdlib-only
Python; `generated/` is gitignored.

## The maps and the exits (all pinned from the shipped bytecode)

| Region | File | What it is |
|---|---|---|
| 41 | RGN29.GFF | the Slave Pens: Scar, Merzol, Dinos, the fountain; 117 triggers |
| 42 | RGN2A.GFF | the Arena: crowd stands, the Announcer's booth, the central monster grate; the engine boot-cases this region |

Transitions decoded with tools/gpl-disasm from the regions' own move
triggers:

- Pens box (112,27,3x1), the arena stair (GPL 137 @ 0xbc5, which asks
  "Enter the arena?") -> Arena tile (30,13).
- Arena box (28,11,5x1), the holding gate (GPL 3 @ 0x73e) ->
  Pens tile (113,27).
- Arena tiles (5,32)/(6,31)/(7,30), the west escape tunnel (GPL 3
  @ 0x6b4, "Gladiators escaping! Guards! Sound the alarms!") ->
  Pens tile (79,66). **GATED OUT of this demo build** (break-out is
  deferred until the arena loop is done); the exporter unblocks the
  three tiles so the door is passable later.
- Pens box (79,65,1x6) is arrival-only: its handler (GPL 137 @ 0xd45)
  is the story beat "The doors to the arena slam shut behind you."

## Rendering facts the demo pins down

- Entity BMPs from SEGOBJEX decode vertically inverted relative to
  in-game rendering; walls and tiles do not (region-render's source
  says the same). The exporter flips tiles/walls and skips the flip
  for entity sprites.
- The world palette is RESOURCE.GFF `PAL` 1000. The CPAL 200 fallback
  is the engine's pink lookup, not the Draj look.
- Every wall, entity, and combatant sprite is bottom-anchored inside
  recursive y-sort, so walls correctly hide whoever stands behind them.
- The intro frames bake the ACF palette state per frame (op 3C loads
  and the op 14 per-entry writes), so the ember fades play as baked.

## Demo simplifications (on purpose)

- Combat is a live skirmish, not the engine's phased fight: monsters
  converge and trade blows with the mined THAC0/damage math; no GPL
  execution (the flow above is hard-wired from the decoded handlers),
  no SCMD animation (frame 0 only), no door mechanics (cell doors stay
  locked; the pens heal the party on return).
- The intro bakes palette fades into the frames and drops music/sound
  cues (recorded in the timeline JSON, unplayed); the real tick rate
  is approximated at 12 fps.
- Fight monsters are object 2039 (the shipped spawn scripts' target);
  its combat record is a pool reference rather than inline data, so
  its HP/AC/THAC0 are demo-assigned, documented in export_region.py.

## Files

| file | role |
|---|---|
| export_region.py | exports both regions (atlas, sprites, region.json, tileset.tres) + demo.json (party stats from charrec, transitions, fight config) with BFS reachability checks |
| export_cine.py | decodes the BMA frames and interprets the ACF scripts into the intro timeline |
| pngio.py | minimal RGBA PNG writer (stdlib) |
| project.godot / main.tscn / main.gd | the demo: intro playback, walking, y-sorted world, combat, transitions, movie-ready |
| generated/ | gitignored exporter output |
