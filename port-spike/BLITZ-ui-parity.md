# BLITZ: UI parity — the prompt for 2026-09-20's session

Read this whole file before doing anything. It is the mission, the
mined knowledge base, the wave plan, and the rules. Everything in
section 2 was mined on 2026-09-19/20 from the shipped data and a DOSBox
ground-truth run; it is evidence, not guesses. Start at section 3.

## 1. Mission

Bring the OpenDS Godot demo's UI to 1:1 parity with Dark Sun:
Shattered Lands, in this order:

1. **Character creation** (WIND 3011, pages 3012/3013) -- the current
   panel is generic widgets and gets replaced wholesale.
2. **Inventory** (WIND 13500 + container pick 13501 + view item 15502
   + examine 15500) -- functional: pick up, drop, equip, split, sell.
3. **Character sheet** (WIND 11500) -- live data from the real record
   layouts, every field the original shows.
4. **Spell screens** (memorize 17500, psionic train 17501, spell info
   15503, and the casting picker that the engine renders as a dynamic
   MENU inside dialog window 3007).
5. **The rest of the chrome**: game menu 10500 (ESC), load/save
   3009/3024 (make saving REAL), preferences 16500, message log 10501,
   popups 14000-14002, interact 3020, dialog 3007/3008/3500, and the
   combat HUD (engine-drawn, no WIND; BMP 5012-5016 + font text).
6. **Parity audit of what already exists**: main menu 3000 and the
   intro get a diff pass against DOSBox captures (the menu buttons'
   frames are STATES, not flicker animation -- fix menu.gd).

Full playability first, QoL after. The bar for "done" per screen: at
320x200 it is layout-identical to the DOSBox capture (every element
within a couple of px), uses the game's own art and font, is driven by
the real data model, and is operable mouse AND keyboard like the
original. Then a side-by-side video passes.

## 2. Knowledge base (mined 2026-09-19/20; trust this, verify offsets when cheap)

### 2.1 Windows (RESOURCE.GFF, all 27 WIND chunks decoded)

Schema, validated 27/27 (gui.h names, corrected sizes): chunk header
12; bytes 12-149 are authoring-tool RESIDUE, ignore them; x@150, y@152;
flags u16@158; frame@162 (72 bytes: width@190, height@192,
border_bmp u32@194, background_bmp u32@202 = 0 everywhere, title@210
empty everywhere); titleLen u8@242 = 0 in all 27; itemCount u16@243;
bytes 245-260 = runtime handler slots, zeroed on disk; items at 261,
stride 30, count = (len-261)/30.

Item (30 B): pointer@0 = 0; fourcc@4 in {APFM, BUTN, EBOX, ACCL};
resource id u32@8; init position = two i16@12 (words @16 are 0);
item_bounds@20 = 0 everywhere; flags u16@28 = 0 everywhere.

Item types (corpus-exact): **APFM** = procedural bevel panel, size
from its own frame w/h (11200 320x189 inventory backdrop, 11213 18x18
cell, 11201 34x34 slot, 11261 98x5 stat bar, 1000 320x200, 11270 4x4
filler). No art refs: the engine draws bevels; match panel colors from
captures. **BUTN** = button; chunk: frame@12 (w@40/h@42 = hot zone),
flags@88, userid@90, iconx/icony@92/94, textx/texty@96/98, icon_id
u32@100 (ICON face; 0 = none), hotkey@108 = 0 always, textlen@109,
text@110 (only 8 shipped text-bearing: DROP/SPLIT/MORE/SELL/INFO/
EXIT x2; 13 save-slot buttons + 16 more are runtime-filled). **EBOX**
= engine text box (FONT/100): 4001 164x12, 4002 236x46 dialog,
4003 95x8 name, 4004 164x12, 4500 239x46, 15400 133x85. **ACCL** = the
single ACCL/8100 on WIND/3000: 8 entries {flags u8, event u16 = ASCII,
userid u16}, S/s->8100/8101, C/c->8102/8103, L/l->8104/8105,
E/e->8106/8107.

The screens (ids, sizes, border plate, item highlights):

- **3000 main menu** 320x200: ACCL/8100 + BUTN 2048-2051 at
  (94,70)/(50,87)/(64,104)/(92,120). Backdrop art (not WIND-bound):
  BMP 20029 panel at (3,55), BMP 20028 arc at (49,38). DONE in the
  demo; audit states.
- **3011 creation** 320x200, 22 items: invisible BUTN/2001; class list
  BUTN 2002-2009 at x=217, y=10..66 step 8; BUTN/2010@(135,75);
  2027@(135,20); 2058@(258,154); 2000 (59x18)@(243,174); 2011@(79,145);
  ability rows BUTN 2012-2018 at x=4, y=139..174 step 7; name entry
  EBOX/4003@(40,125). Pages: 3012 psionics / 3013 spheres (5-row lists,
  border BMP 20087).
- **3007 dialog** 318x58 at (10,0): invisible BUTN/12300; scroll arrows
  2093/2094@(305,4)/(305,18); EBOX/4002@(58,6); portrait frame
  BUTN/2090@(8,6) (48x47 frame + 32x32 face; PORT chunks are the
  dialog portraits, 112 x 32x32 in GPLDATA).
- **3008 dialog choices**: five 300x10 bar buttons 2076-2080 at x=3,
  y=13..45 (ICON 12102-12106) + arrows 2095/2096 at x=305.
- **3009 load** / **3024 save** 320x181: header BUTN/2056@(126,0);
  page buttons 2057/2058@(231,30)/(231,50); ten slot lines BUTN
  2059-2068 at (46, 31..130 step 11) face ICON 18100 165x11; name
  EBOX/4001@(49,147); 3024 adds 62x15 BUTN/2097@(215,148) and scroll
  pair 10314/10315@(215,30)/(215,130).
- **10500 game menu (ESC)** 210x116, 30 items: 16x16 icon buttons
  10300@(49,24), 11304-11306@(81/113/145,24), 10301-10306 row 2 y=51,
  10308 X@(139,78) + 10310-10313@(44..139,78); APFM underlays same
  coords.
- **10501 message log** 192x28: BUTN/10309 + APFM/11270.
- **11500 character sheet** 320x189, 86 items: name BUTN/11318@(151,26)
  over EBOX/4003@(153,28); paper-doll 4x 34x34 BUTN 11300-11303 at
  (53/104, 30/90) with 10x9 sub-buttons 11309-11316; portrait area
  APFM/11269@(147,41) 136x108; right stat grid 18x18 APFM cells at
  x=167..262/148, y=18..129; six ability bars APFM 11261-11266 98x5 at
  (43, 66..140); bottom party strip 10300/11304-11306/11319/11320/
  11308/10308 at y=155.
- **13500 inventory** 320x189, 89 items: backdrop APFM/11200 320x189;
  name 11318@(57,3) over EBOX/4003@(59,5); left paper-doll 4x 34x34
  BUTN 11300-11303 at (12, 5/53/101/149) + small 10x9 11309-11316;
  centre figure APFM/13200@(75,36) 90x125 (art: BMP 13002/13003/13005
  90x125, 13004 86x170); belt grid 18x18 cells 11248-11259 at
  (92/110/128, 65/83/100/118); centre slots 11216-11222 + 11217-11219
  + 11223-11229 scattered x=57..165; right readied grid 11230-11247 at
  x=186/204 (y=18..108 step 18) and x=245/288 (y=80/105/130); command
  buttons DROP 13300@(186,130), SPLIT 13302@(186,142), MORE
  13303@(255,159), SELL 13304@(255,59) (faces: ICON 13006 40x12);
  bottom party strip at y=181.
- **13501 container pick** 137x85: six 18x18 cells 11213-11218 at
  (37/59/81, 24/46) over APFM/13201.
- **14000/14001/14002 popups**: 93x9 line buttons 14003-14007, X close.
- **15500 examine** (16x15 arrows 15301-15303 + INFO 15304), **15502
  view item** (18x18 15305@(75,11)), **15503 spell info** (EBOX/15400).
- **16500 preferences** 210x116: 16x16 toggles 16300-16303, 9x8
  steppers 16304-16309 (ICON 16104/16105).
- **17500 spell memorize** 189x117 (border BMP 17000): EXIT
  17301@(121,102), placeholder 17300@(23,102); 21x 18x18 cells
  11213-11233 at x=28..142, y=24/44/64. **17501 psionic train**
  (BMP 17001): same grid, x=13..127, y=10/30/50. **17502 dual-class**
  (BMP 17002): EXIT 17302@(126,99) + 7 list lines 17303-17310.
- **3001** region-entry HUD, **3004** click-catcher, **3020** interact,
  **3500** text entry (EBOX/4500).

border_bmp ids bound in headers: 3012/3013->BMP 20087, 15503->15002,
17500->17000, 17501->17001, 17502->17002 (plate size == window size).
All other furniture = APFM items. Engine open-sites for every screen
are in docs/screen-flow.md section 2 (e.g. inventory 0x6C243, sheet
0x7E90B).

### 2.2 Art (292 ICON + 105 BMP, fully classified)

- **Button frames are STATES, not animation**: 3-frame faces = one
  glyph mask with ink swaps (frame 0 normal ink, 1 highlight, 2
  pressed/alternate); 4-frame faces = 0 normal, 1 hover, 2 blink/blank
  (often a 1x1 dummy: ICON 2049/2050/2051/17100), 3 lit/selected;
  click flashes 1<->2 briefly. Upstream pins: ICON 11100 (party slots)
  f0 normal/f2 empty/f3 selected; ICON 11111 (AI toggle) f0 off/f1 on.
  menu.gd currently plays the menu buttons as a 4-frame flicker loop:
  fix to the state model.
- **Spell icons**: ICON 21000-21137, keyed by arithmetic 20999 +
  spell_id (DSUN 0x71007); 138 spell ids; 21082 is 15x15, the rest
  16x16. **Power icons** (psionic/stat): the 3000-family (3000-3033,
  3044-3047, 3100-3106) keyed by the +3000 list-type-3 selector
  (0x897D0). The 18x18 BMP 13007/20088 multi-frame family is the
  selection box drawn at (icon.x-1, icon.y-1).
- **Portraits**: 32 painted 186x139 BMPs (20122-20165, gaps listed),
  11 busts 38x50 (20048-20058), 112 PORT 32x32 (GPLDATA, dialogs and
  the inventory 90x125 parchment area).
- **Combat HUD furniture**: the unreferenced 60xx ICON block (6001-6010,
  6030-6041) + RESOURCE BMP 5012/5013/5014/5015/5016 (engine debug
  strings name BMP_CmbtInfoBar and BMP_pCmbtInfoBa2; upstream binds
  5016 = combat status panel, 5014 = damage-number sprites).
- **No cursors, no CURS/GUIF chunks**: the cursor is engine-drawn; the
  port draws its own.
- ICON 2041 frame 2 is the corpus's one malformed frame (decode as
  blank). ICON 2049/2050/2051 frame 2 and 11109/11110/16102 frame 2
  ship blank/dummy on purpose.

### 2.3 Font (FONT/100, RESOURCE.GFF, both games byte-identical,
8,299 bytes, sha256 dbc5528a...)

Layout: u16 num=256; u16 height=9; u16 bg=0; u16 flags=0;
u8 colors[256] (identity); u16 char_offset[256]@264 (from chunk start);
glyphs@776: u16 width + width*9 bytes row-major. Proportional
(space=4, i/l=2, most letters=6); no kerning, no bearings, advance =
width. Glyph bytes are palette indices: 0x00 skip, 0xFE = black ink,
0x14 = dark-blue relief under/right (baked emboss). Under PAL/1000:
0xFE=(0,0,0), 0x14=(56,56,85). Line pitch 9. There is no second size,
no bold, no color remap shipped. Do NOT copy libgff's colors-as-alpha
blending; blit palette indices directly. Render recipe for "STR: 17":
38x9 px, caps at rows 2-7. The engine loads FONT/100 at DS1 0x2A809
(pointer chain ds:0xA113).

Text placement in windows: (a) BUTN inline text at +textx/texty;
(b) frame title (unused); (c) everything dynamic drawn by GPL through
the print service (10x51 dialog line array at ds:0x5537, cmd service
0x7CE83) into EBOXes. TEXT chunks are random-name banks, not UI labels.
Story scroll text is baked into BMA bitmaps.

### 2.4 Data wiring (what feeds each screen)

- **Screen opens**: GPL only opens dialogs (0x2C/0x4F-51 -> 3007;
  0x48 MENU -> dynamic menu inside 3007; 0x42-44 input -> 3500/3004/
  3008) and shop mode (0x24 = inventory 13500 with SELL enabled). ALL
  other screens are engine input handlers (open-sites in
  docs/screen-flow.md section 2).
- **Inventory model**: one global item-instance array, DGROUP [0x165d],
  400 rows x 21 B (object-formats.md 4.1: id -n, qty, next, value,
  pack_index, IT1R index, icon, charges, qty-mirror, special, slot,
  name_idx, bonus). 26 slots per character: 14 paperdoll + 12 backpack
  (engine loop `cmp si,0x1a` at 0x71088; slot byte +17, 0xFF =
  unequipped; disk ships all-unequipped). Slot legality = IT1R +9
  placement code (1 chest, 2 waist, 3 arm, 4 foot, 5 hand, 6 head,
  7 neck, 8 cloak, 9 finger, 10 legs, 11 ammo, 12 missile). Equipment
  shortcuts: combat +8/+10/+12 (ready/weapon/pack). Item icon on the
  screen = the base object's OJFF bmp_id; name = GPLDATA NAME pool via
  +18. Readout formats verified live: '%d%s*%dD%d%+d' (0x4a6a6),
  '%+d %Fs' (0x4a69e), 'AC: %2d' (0x497c0). Carry caps exist: strings
  'TOO BIG TO CARRY' 0x4a6f7, 'TOO MANY ITEMS TO CARRY' 0x4a708.
- **Spells**: known = SPST 138 bytes (1 per spell id) + PSST 34
  psionics + PSIN discipline; per-level castable counts exist as UI
  ("N LEVEL n SPELLS TO CAST") but the slot tables are an OPEN HOLE.
  Menu groups by level via the 138x7-byte array at 0x4512C (byte 0 =
  level); psionics by discipline; cleric spells by sphere. Icons =
  20999+spell_id. Casting is engine-native (ovr32 stub1, 6x14B queue).
- **Character sheet fields** (records = combat 58 B / charrec 71 B):
  name combat+40..55; abilities combat+34..39 (charrec+27..32
  authoritative); HP combat+0/charrec+10; PSP combat+2/charrec+12;
  AC combat+26 (recomputed charrec+39 + equipment); THAC0 combat+31;
  move combat+27/charrec+40; level charrec+36..38; class +33..35
  (29-name table at 0x49b3a); XP charrec+0/+4; race/gender/alignment
  +24/25/26; saves +55..59 (write-only in play); status combat+28;
  weapon = combat+8/10/12 into the item array; effects list = the
  condition table at 0x4a94c-0x4abf6 ('CURRENT SPELL EFFECTS'
  0x4bc48).
- **Combat HUD**: no WIND exists. Two info bars (BMP 5012-5016 band),
  party sidebar = 34x34 boxes at x=12, y=4+48*i (ICON 11100 frame,
  world sprite centered, 11106 leader flag, 11111 AI toggle --
  upstream corroboration, confirm by capture). HUD text:
  '%C%C%C%s%C/%C%s%C/%C%s' name+HP+PSP (0x4a6c2), attack readout,
  damage floats. Single-actor token machine, no round banner.
- **Save/load**: DARKSAVE.GFF's SAVE chunks = the same combat/charrec
  layouts (file-formats.md 3.3/3.4); save-inspect already parses them.

### 2.5 Open holes (mine DURING the blitz, one agent early)

1. Spell memorization slot tables + the memorized-vs-castable runtime
   arrays (DS2 symbol leads: PCMaxSpells, ClassMaxSpells,
   SpellSlotTransfer, classSpellProg).
2. The runtime equipment-slot writer (disk is all 0xFF; DS2 name
   InventoryInitChar) and hand0/hand1/missile mapping into combat
   +8/+10/+12.
3. Carry-limit constants behind the two TOO BIG/TOO MANY strings.
4. PSP max storage (charrec has base only).
5. Combat HUD element->BMP id binding for 5012-5016 + sidebar-face
   confirmation by capture.
6. Shop stock source (GPL stub 0x98) and the 0x48 MENU post-selection
   tail.
7. IT1R column re-pin (asset-bindings.md section 6 anomalies).

## 3. Wave plan (each wave: build -> 320x200 screenshot diff vs oracle
-> fix -> judge -> commit)

**Wave 0 -- the oracle.** Set up the DOSBox capture rig (scratch copy
of .games/ds1, SOUND.CFG from tools/repro/bugs/ds1-smoke/, grim crops
of the dosbox window scaled to exact 320x200 -- remember dosbox-staging
renders 320x200 at 1:1.2 pixel aspect, crop then resize by measured
game-area geometry, not the window box). Capture: creation screen
(fresh boot, C), inventory + character sheet + spell screen (load the
factory DARKSAVE, party has items), combat HUD (walk into a fight),
game menu, preferences, load screen. Save all as
port-spike/oracle/<screen>.png. These are the parity targets; commit
them. Also capture 2-3 seconds of button-hover/click video for the
state model.

**Wave 1 -- exporters + the WindScreen framework.**
- export_font.py: FONT/100 -> generated/ui/font_atlas.png + metrics
  json + a TextBlitter GDScript class (blit string -> texture at 1:1,
  palette indices baked with PAL/1000's 0xFE/0x14 colors).
- export_ui.py: extend to dump EVERY WIND to generated/ui/winds.json
  (per window: size, pos, border_bmp, items[] with type/id/pos/size/
  icon/text) and export all referenced art (ICON faces per frame
  WITHOUT state-flattening, BMP plates, APFM has no art). Keep the
  index-0 transparency + top-down flip corrections already there.
- A WindScreen scene class in Godot: 320x200 board (the menu already
  has the board pattern in menu.gd -- generalize it): draws border_bmp
  plate or APFM bevels (colors sampled from the oracle captures),
  BUTNs as stateful buttons (state textures per section 2.2, hover =
  frame 1, click flash), EBOXes as TextBlitter boxes, full keyboard
  (ACCL tables) + mouse. One screen = one json = one scene, no
  hand-layout.
**Wave 2 -- screens, in mission order** (creation, inventory, sheet,
spells, chrome). For each: build from winds.json, screenshot, diff vs
oracle crop, fix, then a visual-judge pass on the pair, then wire it
into the real game flow (ESC opens 10500; I opens 13500; etc. -- use
the original's keybinds where the ACCL/strings prove them).
**Wave 3 -- playability wiring.** Item instances (pickup/drop/equip/
split/sell with the 26-slot model + placement legality + carry caps),
sheet reads live records, spell memorization from the wave- mined slot
tables, REAL save/load through DARKSAVE-format SAVE chunks, combat HUD
(bars + sidebar + text formats) replacing the demo's custom overlay.
**Wave 4 -- parity audit + the intro/menu polish list.** Side-by-side
videos (DOSBox vs Godot) for every surface watched end to end;
remaining intro gaps after that: dissolve effects, music/sfx binding
by ear, ember palette-cycle.

## 4. Standing rules (do not rediscover these)

- Subagents: max 4 concurrent, research/read-only, no nesting, Explore
  (GLM-5.3-Flash) for breadth, general-purpose (GLM-5.3) for RE and
  judgment agents that gate work; documents:visual-judge (multimodal)
  for every screenshot comparison. Prompts self-contained; relay
  findings in your own words.
- QC medium is VIDEO (Godot Movie Maker --write-movie avi --fixed-fps
  30, ffmpeg to mp4, watch it) plus oracle stills for layout diffs.
  Regenerated assets require `godot --headless --import` before running.
- DOSBox ground truth: never mount .games/ds1 writable; use a full
  scratch copy in /tmp + SOUND.CFG from the smoke fixture (overlay
  mounts fail the DARKSAVE->DARKRUN copy).
- Python stdlib-only by default; the ruff pin is 0.15.20
  (`uvx ruff@0.15.20`); Pillow is already in use in export_ui.py for
  PNG post-fixes, keep new image work in exporters (which feed PNGs),
  not new runtime deps.
- No new Godot addons/third-party deps without asking. No em-dashes in
  any prose. Do not push without explicit approval; commit per wave
  with informative messages.
- The games' install and .games/ stay read-only. generated/ is
  gitignored; oracle/ captures are committed (small PNGs, they are the
  parity spec).
- GFF parsing: tools/gff-edit/scripts/extract-catalogue.py via
  importlib (hyphenated filename; pattern in port-spike/export_ui.py);
  Python 3.14 (tomllib floor). image-extract binary at
  target/debug/image-extract.
- Brandon watches demos live and reports mid-run; video QC every wave;
  never trust Hyprland window sizes in stills.
