# HANDOFF: UI-parity blitz, Wave 3 close-out and Wave 4 (video audit)

Read this file plus `port-spike/BLITZ-ui-parity.md` before doing
anything. This document is the handoff for the next session: what is
done, what remains, and exactly how to finish it.

## Status at handoff (2026-09-20, all commits local on main, NOT pushed)

Done and committed (latest: 7c40231):

- **Wave 0** (cc7c24a): 25 oracle stills at exact 320x200 committed
  under `port-spike/oracle/`. Capture recipe in the rig section below.
- **Mining**: all seven open holes from BLITZ 2.5 closed and distilled
  into `docs/screen-flow.md` section 8 and `docs/object-formats.md`
  (commits 1ffbb23, 0c29466, 33e54ff). Read section 8 before touching
  any screen: it has every handler address, the event dispatch model,
  the item cell arithmetic, the save format and the print formats.
- **Wave 1** (db427ea): `export_font.py` (FONT/100 atlas + metrics),
  `export_ui.py` (all 27 WINDs to `generated/ui/winds.json` with
  resolved geometry, icon frames, titles, backdrops), `wind_screen.gd`
  (WindScreen framework), `text_blitter.gd` (FONT/100 renderer),
  `wind_test.tscn` (QC harness).
- **Wave 2**: all screens built and rendering (124b380, 2be5bf0,
  6118917, 268343b, 5c2979b, 54484b6, 5911573):
  - CreationScreen (3011): oracle-derived in-painted backdrop, live
    stat rows with backings, class list with selection inks, die
    reroll, steppers, alignment, name entry, disciplines.
  - InventoryScreen (13500): backdrop 13001 with dynamic text
    in-painted, party strip, yellow stat panel with weapon lines,
    money, member switching (keys 1-4 or clicking the party slots).
  - SheetScreen (11500): backdrop 11000 + VIEW CHARACTER title
    (BMP 20079), 2x2 party strip, stat lines, class list with per-class
    levels, EXP/HP/PSI/AC/DAM lines.
  - SpellScreen (17500): scroll border 17000, power cells, LEVEL
    cycler, EXIT.
  - GameMenuScreen (10500): all 16 icons on the plate, routed actions,
    hover tooltips.
  - PrefsScreen (16500), CombatHud (nameplate 5016 + arc 5012),
    LoadScreen (3009).
  - menu.gd: the boot menu draws STATIC flame faces (the oracle video
    proves the original has no hover, no click flash, no flicker).
- **Wave 3 core** (e030c92, 696b8d8, 7c40231): the screens are wired
  into the running demo (`main.gd`): ESC/Tab opens the game menu,
  V/I/U/C open the view screens, movement is blocked while a screen is
  up, ESC closes. Party records sync into PartyData so every screen
  shows live HP/AC/THAC0/moves. F1 saves and F2 loads a real GFFI file
  (SAVE/5 combat rows, SAVE/6 character rows, STXT label, SAVE/60 port
  state JSON), round-trip verified. CombatHud refreshes on damage.

## What remains (the work for the next session)

### Wave 3 tail

1. **Item instances**: the model is in `inventory.gd` (26 slots,
   placement legality from the 0x40A70 table, pick/place/swap, cursor
   tag). What remains: real item ICONS in the grid cells (the item icon
   pipeline runs through the OJFF layer per asset-bindings.md 1; not
   exported yet - the port currently shows two-letter tags), and
   optionally wiring the shipped preset inventories from
   docs/creature-inventories-ds1.md.
2. **Damage floats**: the demo prints text floats; the engine also
   draws BMP 5014 splat frames (5 frames: small/big red, green, grey,
   gold, chosen by damage class - see screen-flow.md 8 notes and
   combat_hud.gd). Export 5014 frames and spawn one on each hit
   centered on the target.
3. **Load screen slot labels**: `load_screen.gd` lists real
   user://saves files and reads labels from the SAVE/60 JSON. The
   original stores the label in an STXT chunk; if engine-compatible
   labels matter, extend the writer (one more chunk) and the reader.

### Wave 4: side-by-side video audit

For every surface: a side-by-side video (DOSBox left, Godot right),
watched end to end, plus a written polish list. Raw material status:

- DOSBox captures: drive the rig (recipe below). Record with
  `wf-recorder -g "<window geometry>" -f out.mp4`. Surfaces: boot menu
  (static), creation (C, then Space on the party screen, then N on the
  popup), load screen (L from the menu), in-game screens V/I/U/E/Tab,
  the combat HUD (the arena fight runs itself; see driving notes).
- Godot captures: `SPIKE_DEMO=1 godot --path . res://main.tscn
  --write-movie demo.avi --fixed-fps 30` gives the full loop; per-screen
  stills via `qc_screens.sh` / the snap harness.
- Assemble with ffmpeg hstack. Watch each video end to end (that is
  the audit), fix what it exposes, and commit the fixes plus the
  videos under `port-spike/audit/`.

Known styling gaps to expect in the audit: glyph weight (the engine
double-strikes text so its glyphs read chunkier - a bold pass on
TextBlitter output is the fix), 1px row alignments on the creation
stat block, the party slot figure sprites (SEGOBJEX sprite table
0x340:0xF36, unpinned), and item grid icons (OJFF pipeline).

## The DOSBox rig (all of this is required, in this order)

1. Scratch copy: `rm -rf /tmp/ds1-oracle && cp -r .games/ds1 /tmp/ds1-oracle`
   then copy `__support/save/DARKSAVE.GFF`, `BACKSAVE.GFF`,
   `CHARSAVE.GFF` and `tools/repro/bugs/ds1-smoke/SOUND.CFG` into it.
   NEVER mount the real install writable.
2. Conf: mirror `tools/repro/configs/ds1.conf` (sound ON at
   sb16 220/irq7/dma1 - sound OFF kills the boot with
   "Mel Fatal Error #26 DSP Detect Fail"), plus
   `windowresolution = 960x600`, `aspect = false`, `glshader = none`,
   `mouse_capture = seamless`, `captures = capture`.
3. Screenshots: dosbox native Ctrl+F5 writes 6x integer PNGs to
   `~/.config/dosbox/capture/`; downscale by 6 with NEAREST for
   pixel-exact oracles.
4. Mouse: clicking into the floating window CAPTURES the pointer
   (Hyprland cursorpos freezes while ydotool relative moves keep
   reaching the game). Prefer the KEYBOARD for everything; release the
   mouse with Ctrl+F10 when done. ydotool mousemove needs the
   positional form `ydotool mousemove -- dx dy`; the `-x/-y` flags are
   a silent no-op, and bursts of moves can wedge the daemon for
   minutes.
5. Hotkeys (manual p.92): V sheet, I inventory, U/C spells, E effects,
   Tab game menu, Esc, O map, H center leader, 1-4 leader, N/P target,
   Q end turn, G guard, W wait, Space computer control, Alt-X quit.
6. Drive flow: boot waits at the title (any key) -> menu (S = start
   game) -> story scroll (Enter) -> fade -> the arena gate. The
   announcer stays silent until the in-game cursor moves; his dialogs
   advance with Enter; the NPC exhibition fight runs itself; after it
   the party walks DOWN into the arena middle and
   "Monster Trainer releases your horde" starts the player fight. In
   combat, Space toggles the engine's own computer control, which
   plays the fight unattended.

## Session rules (Brandon's, non-negotiable)

- ALL progress notes and summaries in ENGLISH. He reads everything.
- Keyboard over mouse when driving DOS games. After two or three
  failed attempts at a step, stop pressing keys and go read or mine -
  do not loop.
- Subagents: max 4 concurrent, research/read-only, no nesting. GLM-5.3
  for RE and judgment, GLM-5.3-Flash for breadth. Say "do not spawn
  subagents" in every prompt.
- Commit per wave, informative messages, no em-dashes, never push
  without approval, stdlib-only Python (Pillow allowed in exporters),
  ruff pin 0.15.20 for anything in the CI gate.
- `.games/` and the wine installs stay read-only; the DOSBox rig uses
  a scratch copy; `generated/` is gitignored.
