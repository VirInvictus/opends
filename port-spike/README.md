# port-spike: the Draj demo — intro, main menu, Slave Pens, Arena, and the first fight

A working demo of Dark Sun: Shattered Lands' opening loop in Godot 4:
the boot flow plays exactly like the original (SSI logo -> AD&D screen
-> title tablet -> the full intro cinematic -> the main menu), and from
there you create a character (the engine's own stat-roll rules) or
start with the four preset gladiators, walk out of the Slave Pens,
into the Arena of Draj, fight the first arena fight with the mined
combat math, and return to the pens to do it again. Break-out options
(the escape tunnel, attacking guards) are gated out of this build by
design. Built on the region pipeline proven by the port-mining
campaign; consumes only decoded, documented formats and modifies
nothing in the game install.

## Run it

```sh
python3 export_region.py      # regions 41 + 42, party/monster stats, demo.json
python3 export_cine.py        # intro frames + ACF playback timeline
python3 export_ui.py          # menu panel, flame arc, button faces, ui.json
godot --headless --import --path .   # first run and after every re-export
godot --path .                # play
```

- **Boot**: the intro plays unattended, then the main menu (the
  original's flow; Esc skips the intro).
- **Menu**: the shipped menu assembled from the game's own data (see
  "The menu is the game's menu" below). S = start, C = create
  character, L = load (stub), E = exit; the four text buttons are
  clickable.
- **Creation**: race / gender / class with the shipped class masks,
  stat roll = best of four 4d4 + racial modifier + 4, prime stats
  floored at 17, racial+20 cap; accept builds a level-3 record (HP
  from the class hit die, THAC0 from the class rate) and drops you
  into the pens.
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

`SPIKE_MENU=1` records the menu + creation flow instead; `SPIKE_INTRO=1`
plays just the intro and quits. Each QC pass is that video watched end
to end, plus `cine_sheet.py`, which tiles all 715 timeline entries into
contact sheets under /tmp/spike for frame-by-frame judging. Requires
the games under `.games/ds1/` and Godot 4.x. Stdlib-only Python (the
menu exporter post-fixes PNGs with Pillow if present); `generated/` is
gitignored.

## The menu is the game's menu

No custom art: the boot menu is rebuilt from RESOURCE.GFF the way the
engine assembles it, verified against a DOSBox capture of the real
menu (2026-09-19):

- BMP 20029, the ornate stone panel, at (3, 55) in the 320x200 menu
  space; BMP 20028, the burning arc with the green orb, at (49, 38).
- The four entries are ICON 2048..2051, each a 4-frame flickering
  gradient-text face placed at its WIND/3000 item position
  (94,70 / 50,87 / 64,104 / 92,120). Keys come from ACCL/8100
  (S/C/L/E upper+lower).
- ICON and BMP frames are stored top-down; image-extract's bottom-up
  flip is undone on export, and palette index 0 (PAL 1000's
  lavender) is punched to transparency.

The creation panel reuses the engine's rules but is still generic
Godot widgets, not the game's WIND/3011 layout; restyling it from the
shipped data is the remaining menu work.

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
  for entity sprites. CINE/RESOURCE stills and ICON faces are stored
  top-down like entities.
- The world palette is RESOURCE.GFF `PAL` 1000. The CPAL 200 fallback
  is the engine's pink lookup, not the Draj look.
- Every wall, entity, and combatant sprite is bottom-anchored inside
  recursive y-sort, so walls correctly hide whoever stands behind them.
- The intro is baked as a flat 715-entry timeline (706 BMA frames +
  still screens) with the palette state baked per entry. Palette
  semantics settled against a DOSBox capture of the real intro
  (2026-09-19): ACF 2 stages a full 256-entry palette (op 14) and
  commits it (op 15), and those frames wear the committed palette; a
  committed block wins over the same part's later 0x3C load; a 0x3C
  load re-renders the screen under the new palette (the AD&D screen
  shows under PAL 1 and then re-renders under PAL 2). ACF 1's three
  stills take ground-truth palettes 1/2/2 (see export_cine.py).

## Demo simplifications (on purpose)

- Combat follows the engine's actor-token structure (the turn-system
  research: combat_step 0x4a7 + scheduler 0x9b6): each round every
  alive combatant gets the token in morale-threshold order (20 + d10 +
  act modifier, tie by d200), with move points (move x 10; a step costs
  10 orthogonal / 14 diagonal) and attacks (the parity alternator over
  the blows byte). Party tokens wait for your move/attack/skip
  (Enter); monster tokens run their chase-and-attack AI. No GPL
  execution (the flow is hard-wired from the decoded handlers), no
  SCMD animation (frame 0 only), no door mechanics (cell doors stay
  locked; the pens heal the party on return).
- The intro bakes palette fades into the frames and drops music/sound
  cues (recorded in the timeline JSON, unplayed); scene dissolves play
  as hard cuts. The tick rate is 12 Hz: the baked timeline runs 125s
  against ~130s measured for the real intro in DOSBox. The embers'
  twinkle is palette-cycling in the engine (op 19 note-range args);
  the demo holds the baked frame.
- Entry 426 of the timeline (one frame) is the shipped data's own
  dither mid-dissolve into the desert scene; it looks like noise for
  a single tick in the original too.
- Fight monsters are object 2039 (the shipped spawn scripts' target);
  its combat record is a pool reference rather than inline data, so
  its HP/AC/THAC0 are demo-assigned, documented in export_region.py.

## Files

| file | role |
|---|---|
| export_region.py | exports both regions (atlas, sprites, region.json, tileset.tres) + demo.json (party stats from charrec, transitions, fight config) with BFS reachability checks |
| export_cine.py | decodes the BMA frames and interprets the ACF scripts into the intro timeline |
| export_ui.py | exports the menu furniture and flickering button faces + ui.json |
| cine_sheet.py | tiles the baked timeline into contact sheets for visual judging |
| pngio.py | minimal RGBA PNG writer (stdlib) |
| project.godot / main.tscn / main.gd | the demo: intro playback, walking, y-sorted world, combat, transitions, movie-ready |
| menu.tscn / menu.gd | the data-driven main menu and character creation |
| generated/ | gitignored exporter output |
