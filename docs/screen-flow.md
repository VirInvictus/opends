# UI screen flow: the window manager, the screen inventory, mode transitions, input

How both engines decide which window shows when, decoded (port-mining wave
2, 2026-09-19). The UI RESOURCES are presentation-formats.md section 2; this
document owns the flow layer. Verified on the GOG 1.10 corpus. Unless
written seg:off, offsets are file offsets in that game's DSUN.EXE. DS2's
window-manager family is DS1's code shifted by +0x4815 (verified on the
fourcc tables and count sites). Resident mapping: file = seg*16 + 0x5400
(DS1) / + 0x5200 (DS2).

## 1. The window manager

Core in resident segment 0x25EC (DS1) / 0x2A8E (DS2); resource reader in
seg 0x2531 (DS1 0x2531:0x49E = file 0x2ABAE) and its DS2 mirror.

| op | DS1 | DS2 | semantics |
|---|---|---|---|
| chunk lookup in open GFF | 0x2531:0x49E | +0x4815 | (handle, fourcc, id); special-cases 'MENU' (builder 0x2705:0xA7B) |
| load WIND | 0x2BEF4 | 0x30709 | pushes 'WIND' + id to the reader |
| ACTIVATE/SHOW | 0x2B57E | 0x2FD93 | per-item loads ACCL -> 0x2705:0xCC, APFM -> 0x2A1D:0x3, BUTN -> 0x2AF5:0x6, MENU, EBOX (5-fourcc table cs:0x5FA = file 0x2B8BA); links the window at the HEAD of ds:0xA12F list, count++, flags = (flags & ~0x1F) \| 0x2, installs event vectors at win+0xF5; repaints all active windows in z-order |
| DEACTIVATE | 0x2BBC6 | 0x303DB | flags \| 0x4, moves the window to the TAIL |
| DESTROY | 0x2BCF1 | 0x30506 | frees sprite (flags & 0x4000), unlinks, count--, per-item frees (table cs:0xC1E = file 0x2BEDA) |
| open API used by screens | 0x530:0x3E | 0x5B0:0x48 | args (id, dw_arg, w, h) -> far handle; every screen caches its handle in a dedicated global |

The model is NOT a push/pop stack: an explicit active list, LIFO by
activation order (activate = prepend = topmost; deactivate = append to
tail). Globals: head ds:0xA12F, count ds:0xA12D (DS1). Window struct: +0x08
id, +0x9E flags (0x2 active, 0x4 deactivated, 0x40 titled-APFM, 0x80
has-BUTN, 0x4000 sprite at +0xA0), +0x96/+0x98 pos, +0xBE/+0xC0 size,
+0xEE next, +0xF2/+0xF3 item offset/count, items at +0x105 stride 0x1E
(matches libgff gff_gui_item_t), +0xF5 event vector. Activation is driven
from overlay screen-flow code via INT 3Fh stubs (no static far callers).

## 2. The screen inventory

Names cross-checked against soloscuro's `enum ds1_windows_e`
(.dsoageofheroes/soloscuro-orx/include/soloscuro/window.h) and engine
strings ('FATAL: Error loading WIND_MAINMENU' DS1 0x4A788, 'WIND_GAMEMENU'
0x4969C, 'WIND_VIEWITEM' 0x4BD1E). All 55 window trees re-validated
((len-261) == 30*itemCount). "Open site" = the push id + call to the open
API.

| WIND id (DS1 / DS2) | screen | conf | notes |
|---|---|---|---|
| 3000 / 19500 | MAIN MENU (title) | high | ACCL8100 + BUTN2048-2051 (DS2 19300-19xx); open 0x77F7F, clears GSTATE:0x19 = 0 |
| 3001 (DS1) / 19501 | region-entry HUD frame | medium | APFM1000+1001; open 0x1CC7C (resident bootstrap) / 0x69A21 |
| 3004 (DS1) / 19502 | input/prompt (1 button) | medium | 0x7E226, 0x7E477 / 0x89858, 0x89BEE |
| 3007 (DS1) / 12500 | DIALOG/narration | high | BUTN12300+2093+2094, EBOX4002/12400; open 0x7D0A2 and 0x7D3CE (= dialog-print cmd 3) |
| 3008 (DS1) / 12501+12503 | dialog choice/input subwindow | medium | arrows BUTN2076-2080; DS2 splits in two |
| 3009 / 18500 | LOAD/SAVE list | high | BUTN2056-2068 (13 slots); open 0x7454F / 0x7D5AF |
| 3024 / 18501 | LOAD/RESTART page 2 | high | + scroll BUTN10314/10315 |
| 3011 / 19503 | NEW CHARACTER creation | high | 22 items; open 0x65D33 / 0x6D95B |
| 3012 / 19504 | char-gen PSIONICS page | high | 0x67BFB / 0x6FA45 |
| 3013 / 19505 | char-gen SPHERES page | high | 0x6336D, 0x6413B / 0x6B0FD, 0x6BEC2 |
| 3020 (both) | INTERACT (thief/interact) | high | 0x5F08C |
| 3500 (DS1) / 12502 | text-entry box (EBOX; GPL 0x42) | medium | 0x7D279 / 0x8811D |
| 10500 (both) | GAME MENU (ESC) | high | 30 items; open 0x61B26 |
| 10501 (both) | MESSAGE window (log) | high | 0x5542D, 0x561E9 |
| 11500 (both) | VIEW CHARACTER sheet | high | 86 items; open 0x7E90B + two more cache slots |
| 13500 (both) | INVENTORY | high | 89 items incl. DROP/SPLIT/MORE/SELL; open 0x6C243; state serialized to DARKSAVE at 0x8D344 |
| 13501 (both) | container pick-list | medium | 0x5B10C |
| 14000/14001/14002 (both) | POPUP / INSPECT / ALERT | high | `mov di,0x36B0/0x36B1` at 0x54DB8/0x54E00/0x54F29 |
| 15500 (both) | INSPECT (examine) | high | 0x5EFC5 |
| 15502 (both) | VIEW ITEM detail | high | 0x8AF59 |
| 15503 (both) | SPELL INFO popup | high | 0x8C634 |
| 16500 (both) | PREFERENCES | high | 0x7F422 |
| 17500/17501/17502 (both) | SPELL memorize / PSIONIC train / DUAL toggle lists | high | 0x85814, 0x85FF4, 0x86779 |

Confident negatives (no WIND exists): the combat HUD (engine-drawn
bitmaps; BMP_CmbtInfoBar strings at DS1 0x4A653/0x4A678); the overhead map
(a game-menu action; maps render from GMAP/RMAP fullscreen); the shop
(Request 0x24 = the 13500 inventory window with SELL enabled); rest
(message text only). ACCL: DS1 ships exactly one (ACCL/8100 on the main
menu: S/s Start, C/c Create, L/l Load, E/e Exit); DS2 ships ZERO ACCL
chunks (input is restructured). BUTN hotkey bytes are all 0 in shipped
data; hotkeys are the ACCL's job.

## 3. Mode transitions

Exploration/combat flag: GSTATE 0x2B8:0x19 (DS1) / 0x2E0:0x19 (DS2), word.
Writers: DS1 set 1 at 0x58579 / 0x6A6DD / 0x75592, set 0 at 0x6AF2A
(teardown) and 0x77FCD (main menu); DS2 set 1 at 0x5CBD2 / 0x7336A
(fight_enter, which first calls UI-mode 0xB0:0x2535(1) at 0x73345) /
0x7E81E, set 0 at 0x73BAE and 0x81626.

UI-mode service (second axis): DS2 0xB0:0x2535 with enum {1..5}: mode 1
(exploration/default) sites 0x5B141 / 0x69FC7 / 0x73345 / 0x7A9B6 /
0x8C1B5; mode 3 (immediately followed by the +0x5208 spell-icon math =
spell/power targeting UI) at 0x60880 / 0x633B9 / 0x63C06 / 0x7549F; modes
2/4 branch at 0x68150; mode 5 at 0x5A24A. DS1 analogs: 0x4F8:0x84 (37
sites, modes 1-4; per-screen switch cluster 0x7BE63..0x7BF07) and
0x508:0x57 (7 sites). Reading: 1 = walk/default, 3 = spell/power select;
MEDIUM confidence, exact enum names unproven.

Typical flow: boot -> 3000; 3000 -> 3011..3013 (create) / 3009 (load);
region load -> 3001 + exploration; ESC -> 10500 -> {3009/3024, 16500, map,
restart, exit}; party sheet 11500 -> 13500 -> 15500/15502/15503 ->
17500/17501; NPC click -> 3020 -> GPL dialog -> 3007 (+3008/3500/3004);
Request 0x35 -> GSTATE = 1 + engine-drawn combat HUD; victory -> GSTATE =
0; popups 14000/14001/14002 from anywhere.

## 4. GPL Request codes' UI arms

- 0x48 Menu: builds a dynamic 'MENU' chunk (format string 'MENU %u' DS1
  0x4C56C / DS2 0x502F2; builder 0x2705:0xA7B) rendered INSIDE the dialog
  window 3007/12500: the only non-static window content.
- 0x2C Log and 0x4F/0x50/0x51 prints: the 10x51 dialog-line array
  (ds:0x5537 DS1 / ds:0x6356 DS2) via the print service -> opens 3007/12500.
- 0x42/0x43/0x44 input: the EBOX windows 3500/12502 and 3004/19502 +
  3008/12501 (pairing medium confidence).
- 0x24 Shop: opens no window; shop mode = 13500 with SELL/DROP/SPLIT/MORE
  enabled.
- 0x22 codes 1/4 rest: message strings only ('THE PARTY RESTS' is DS1
  0x4ae9d; 0x4ae84 is 'NO RESTING DURING COMBAT' - wave 3 correction,
  chargen-flow.md 4 has the rest pipeline); no rest screen.
- 0x35 Fight / 0x39 elevator / picture codes: engine state, no windows.

## 5. Input dispatch (data-driven end to end)

1. Registration at ACTIVATE: each ACCL item -> 0x2705:0xCC stores {event
   char, userid, bounds} into the accelerator record (rect widened by
   +3/+2). BUTN hotkey bytes are 0 everywhere; item flags bit0 triggers
   0x980:0x599E(0x20).
2. Event pump (DS2 0x32BD0+0x4815 family; DS1 0x32BD0): polls hardware,
   walks the active-window list, classifies the window by fourcc (WIND vs
   MENU switch, tables cs:0x509 / cs:0x4F1), then per class: button
   hit-test 0x2BA6:0xFA4(win, count, x, y), EBOX text-edit 0x309B:0x100E,
   damage/draw calls with dirty-rect codes. Keyboard events match ACCL
   event chars -> dispatch the userid to the owning window's callback
   vector (win+0xF5, installed from ds:0xA11B; item handlers +0xF9/+0xFD).
   Redraw latch ds:0xA193.

A port can drive the screens from these tables; no input logic is
hardcoded per screen beyond the callbacks the windows register.

## 6. Dialog print service command indices (resolved)

DS1 service at 0x7CE83 (overlay seg base 0x7CC30): `shl bx,1; jmp near
[cs:bx+0x9E6]`, table at file 0x7D616. DS2 service at 0x87BA0 (seg base
0x87900), table at file 0x884B7.

| cmd | semantics |
|---|---|
| 0 | append line to the 10x51 dialog-line array (count ds:0x5503/0x6322; truncates at 50 chars) |
| 1 | PORTRAIT case: `push word [bp+0xC]; call GetPortrait` (0x7DEDF / 0x88E67) |
| 2 | append with word-wrap/font measurement |
| 3 | open/refresh the dialog window: flags 0x11B2/0x573D/0x1F0D then OpenWindow WIND/3007 (DS1 0x7D3CE) / 12500 |
| 4 | alias of cmd 2 |

This resolves asset-bindings.md's portrait-command open item: the
portrait command index is 1. Dialog module home segments: DS1 overlay seg
34 (0x7CC30..0x7DF80), DS2 overlay seg 30 (0x87900..0x88F11).

## 7. Open items

1. The OpenWindow arg triple's dw_arg semantics (observed: 0, 0x90000,
   0xA0000, 0x8C0000, 0x5800D2, packed 0x2A0037-style pairs; likely a
   flags/size union).
2. The UI-mode enum names (values {1..5} pinned; labels inferred).
3. A few low service thunks (0x530:0x3E DS1, 0xB0:0x2535 DS2) are not
   reachable under the constant seg->file delta (group alignment
   padding); identity established by call-site shape.
4. DS2's dual counters: the rewritten WM increments ds:0xA103 while the
   event pump reads ds:0xA12D/0xA12F (two lists or refactor leftover;
   runtime capture settles it).
5. Per-trigger attribution for the 10501/1400x popups (tooltip vs click
   vs engine alert).
6. Menu post-selection routing back through the pump's MENU window class
   (carried from gpl-vm.md).

## 8. The screen behavior layer (UI-parity blitz, 2026-09-20)

How each screen actually behaves, mined for the Godot port. All offsets
are DS1 file offsets; DGROUP base 0x48960, DGROUP runtime segment
0x4356. Where a claim rests on disassembly, the load-bearing offset is
cited; the full evidence trails live in the blitz session transcript.

### 8.1 Event dispatch (corrects section 1/5)

- Open API (0x530:0x3E, body 0x62182) is `OpenWindow(id,
  packed_xy_dword, handler_far)`: it sets the window xy from the dword
  ((y<<16)|x fits every observed site), then stores the far handler at
  win+0xF5 (`66 26 89 87 F5 00` at 0x2BFCD). The handler is an
  argument; the ds:0xA11B copy at 0x2B89C is a separate capture-time
  path. The observed "dw_arg" values in section 7 item 1 are xy pairs.
- Event record (24 bytes, built by 0x2B075, dispatched through
  0x2AE17/0x2AE4A, `call far [es:bx+0xf5]` at 0x2AEFA): +0 word event
  type (1 = unmatched raw input, 2 = item activated, 3 = repeat,
  6 = keyboard), +2 userid, +6..0x13 a 14-byte raw input record copy,
  +0xC key code (scan<<8|ascii; 0x011B = ESC, checked 0x2B10C), +0x12
  mouse button state word inside the raw block, +0x14 dword item
  private data (from item record +0xC).
- Item handler vectors: WindProc [0xA11B], item handler [0xA11F];
  setters 0x2AB2D/0x2AB42; item dispatch `call far [0xa11f]` at
  0x2AE7E.
- Button state API: 0x2FCEA(win, uid, cmd) (stub 0x140:0x71A): cmd 0/1
  clear/set disabled ([+0x58] bit 1, [+0xc] bit 0x4000), cmd 2/3
  set/clear selected ([+0xc] bit 0x8000), cmd 4/5 press-flash
  ([+0x58] bit 0). IsBStateOn = 0x640B7 (state == 2).
- Screens that take per-item actions run a userid switch: a count +
  linear-scan id table paired with a handler jump table (3011's at
  file 0x663AB/0x663D7, dispatcher 0x6620E).

### 8.2 Character creation (3011/3012/3013)

Open 0x65D2A: `OpenWindow(0xbc3, 0, handler 0x540:0x43 = 0x6620E)`,
handle cached [0x11A4/0x11A6]. Dispatcher 0x6620E: event 1 -> reject,
event 6 -> only ESC (0x011B -> EXIT path), event 2 -> 22-entry userid
switch.

| id | role | handler / notes |
|---|---|---|
| 2001 + 2027 | race/gender cycle (invisible zone over the figure; left +1, right -1 via event+0x12 < 8) | 0x66277 -> 0x63263; scratch+0x18 wraps 0..13; race = idx>>1+1, gender = idx&1+1 |
| 2002-2009 | class list toggles (ICON faces carry the names) | classSelect 0x63C95 fills/empties charrec+0x21..23 with race-mask + multi-grid legality; every class click re-runs DONE-enable 0x66403 (second switch 0x66377 for uids 2001..2009) |
| 2010 | the stat reroll die | 0x6435A: 5-frame flip animation, then `rand()%6` resting face, then ShowStatClass(1) rerolls all six stats (GetStat 0x6490D x6, best of 4) |
| 2011 | alignment stepper (charrec+0x1a cycles 1..9; druid forced N) | 0x66333 -> 0x63799 -> 0x649D4 |
| 2012-2017 | six ability +/- steppers, clamp [class_min, racial+20], HP re-clamp | 0x66347 -> 0x637F8 -> 0x65480; row table 0x63A18 |
| 2018 | HP stepper (charrec+8 wraps in [HPmin,HPmax] = [0x4998,0x4996]) | 0x6635B -> 0x63A24 |
| 4003 | name entry (EBOX editor; buffer = combat+0x28, 16 bytes, max 15; empty seed = "Default Name" ds:0xE04) | 0x63AC8; "NAME:" label printed at (4,125) by the open routine |
| 2000/2058 | DONE / EXIT: press-flash cmds 4,5 then 0x649C(slot, flag 1|0) | DONE runs the finalize chain (0x66AC4 sphere remap + party copy, 0x66CF1 discipline marker, 0x67016 free-slot find); EXIT (and ESC) frees the reserved slot unless editing ([0xE9C] != -1) |

DONE legality (Enable 0x66403, sets BUTN 2000 cmd 0/1): a class slot
is filled AND psionic discipline mask [0x4980] != 0; no cleric/druid
slot with sphere mask [0x4982] == 0; psionicist selected requires
[0x4980] == 0xE0 (all three disciplines).

Pages: 3012 disciplines (open 0x67BD7, dispatcher 0x642F7: rows
2038 psychokinesis/2039 psychometabolism/2040 telepathy -> PsiEvent
0x63698 toggling bits 0x80/0x40/0x20 of [0x4980]; 2041
psychoportation disabled at creation; 2046 VIEW SPHERES -> 0x640E4)
and 3013 spheres (open inside 0x640E4 at (210,88), dispatcher
0x64296: rows 2042-2045 air/earth/fire/water -> SphEvent 0x6373F
toggling 0x80/0x40/0x20/0x10 of [0x4982]; 2047 VIEW PSIONICS reopens
3012). No DONE on the pages; finalize derives real_class spheres from
[0x4982] (0x66AC4, table 0x338:[creation_class*4+sphere+0xED], file
0x3E140) and the discipline marker from [0x4980] (0x66CF1, writes the
7-word array at 0x2F0:[slot*7+si]).

Keyboard: ESC only (EXIT); typing goes to the name EBOX while it holds
editor capture (editor family prologue 0x36B2F, instance table
ds:0x16D4 stride 0x14). Everything else is mouse-driven; steppers
direction = left/right via event+0x12 < 8 (+1) else -1.

UI-state globals: [0x119C/0x119E] pending charrec (0x338:0x48),
[0x11A0/0x11A2] pending combat (0x338:0x8F), [0x4980] discipline mask
(init 0x80), [0x4982] sphere mask, [0x4996]/[0x4998] HP max/min,
[0xE9C] -1 = creating new, else the slot being edited.

### 8.3 Inventory (13500/13501/15500/15502)

Open 0x6C243 (module 24/25). Cell arithmetic (GetCellRect 0x6F4DC):
`APFM id = cell + 11212`; cell content = word [0x540C + cell*2]
(-1 empty); slot byte on the 21-byte item row (+0x11) = cell - 4
(write 0x6D7A5, read 0x6D8B8).

| ids | cells | role |
|---|---|---|
| 11216-11229 | 4-17 | 14 paperdoll slots; body-slot table = 14 bytes at file 0x40A70: arm(3), ammo(11), missile(12), hand1(5), finger(9), waist(2), legs(10), head(6), neck(7), chest(1), hand2(5), finger2(9), cloak(8), foot(4); hands are cells 7 and 14 (legality 0x6EF52 reads exactly those), grasp triple {6,7,14} protected in pickup/place |
| 11230-11241 | 18-29 | the 12 backpack slots (slots 14..25; CountUsedBackpackSlots 0x73B99) |
| 11242-11247 | 30-35 | container contents display (only when opened on a container; placing refused 0x6E4D7) |
| 11248-11259 | 36-47 | two 6-cell selection zones (A/B; enable 0x5C335/0x5C327, art 0x2BF0..0x2BFB), fed by items whose IT1R+15 & 0x8 (quick-item), zone A if IT1R+8 & 0xF == 5 |

Buttons: 11300-11303 = party select (NOT paperdoll; si = di + 0xD43F
wraps 11201..11204 and `sub ax,0x2c24` maps 11300); 11309-11312 =
leader flags (ICON 11106), 11313-11316 = AI toggles (ICON 11111), one
pair per member at (2,5/53/101/149) and (2,14/62/110/158); 13300
DROP, 13302 SPLIT (stackable IT1R+15 & 0x2, qty > 1, halves via
0x6F6C5), 13303 MORE (pages the container pick-list, [0x2ED0]),
13304 SELL (only when 0x588:0x43() != 0, then 0x608:0x20 shop
module), 11318 name plate over EBOX 4003.

Click model: hands-empty click on a filled cell picks the item to the
cursor (held row [0x17A0], legality 0x6F44B; grasp cells blocked for
class/race codes {0x31,0x46,0x47,0x48}); click with a held item
places/swaps (legality 0x6EF52 placement, carry 0x8:0x33F, swap
worker 0x6ECFC; unequip strips granted effects via item +15 ->
0x5B8:0x115/0x7F at 0x6F8B9); same-item stack merge (0x6E6F5);
container cells refused. Party strip (or keys 1-4/SPACE) switches
character and transfers a held item to that member (0x588:0x61/0x6B).
Examine 15500 tracks the clicked instance via [0x360:0xC36+si*3]
trio (state 1 item -> 15500, state 2 creature -> 3020). Its three
glyph buttons are the interact strip's talk/steal/give, not arrows:
the shared dispatcher at 0x5F2B7 (jump table 0x5F7F9) maps 15301 ->
TALK 0x5F731, 15302 -> GIVE 0x5F754, 15303 -> STEAL 0x5F6BE, and
INFO 15304 -> toggle item plate vs description list ([0x846],
0x5F591); it does NOT open 15502 from here. 15502 still reads the
instance index directly (item +10 -> IT1R, effect byte +15, the
0x4a6a6/0x4a69e readouts) but its opener 0x8AF59 is reached from the
inventory flow. Capability gating and the steal/give paths:
port-digs-2026-09-21.md.

Keyboard dispatcher 0x71153: 33-entry (tag<<8)|ascii table at
0x71C1B: ESC, 1-4, SPACE, Q/W/S/G/H/M and more. Leftover debug cheat:
'T' (0x1454/0x1474, handler 0x71198) writes 10,000,000 XP to every
tracked entity with state 2 (`mov dword [es:bx],0x989680`).

Slot-byte writers (hole 2): the disk-load fixer 0x69DF0 (DS1's
GplDiskFixItemSlot) assigns placement to unequipped rows at load
(`mov [es:bx+0x11],al` 0x69EA6); the rebuild auto-assign 0x6D80B
writes cell = slot+4 (0x6D7A5) and clears to 0xFF; the ready-slot
module 0x5B8B9-0x5BF83 writes slot = cl+1 (0x5BA51) and
[bp+6]+1 (0x5BF77); unequip clears to 0xFF and strips effects
(0x6F8B9). Combat +8/+10/+12 derivation is NOT statically reachable
(the 0x628:* derived-stats family runs at runtime segment numbers;
leads: DS2 NpcReadyWeapon/GetMissileWeapon/usedhands/NumHands); the
ready-slot module publishes the readied item into
[0x360:0xC37+cur*3].

Carry limits (hole 3), both in GiveHeldToChar 0x73C40 (module 26):
'TOO BIG TO CARRY' (0x4A6F7) fires when IT1R+8 & 0x10 or & 0x20
(0x73CBD/0x73CEB; the same bits block equipping at 0x6EFD0); 'TOO
MANY ITEMS TO CARRY' (0x4A708) fires only when every party member
fails both the 12-slot check (slots 14..25) and the 80-row pack cap
(`cmp dx,0x50` 0x73D6D). There is no weight formula anywhere on this
path. DS2 keeps the model verbatim (0x7CA45/0x7CB31, same 0x50 cap).

### 8.4 Spell learn/train screens and the casting picker

WIND 17500 is the level-up LEARN screen (not memorize): open 0x85771
(highlight ICON 15104 cached at [0x348]:0x2F); cell list = 21 words
at MISC[0x348]:0x7 + cell*2, filled by OVR9 stub2 0x5DD71: ascending
SPST id per level group (level byte of the 7-byte spell table at
0x4512C, class byte 0x01 preserver / 0xFE divine), starting at the
char's max level = (OVR10 stub1(char)+1)>>1 stored at [0x4AEC].
Icons = 21000 + spell id. Item dispatcher 0x85920 (si = id - 0x2BCD):
hover draws the 15104 highlight + header 'LEARN <name>' (name = OVR9
stub13 0x5E556); click LEARNS via 0x500:0x43 (0x5E3D7), header '<name>
IS LEARNED!'; right-click opens 15503 with spell_id+1. EXIT 17301
confirms 'YOU HAVEN'T CHOSEN' / EXIT / CANCEL (0x85B76). Placeholder
17300 prints 'LEVEL %d' ([0x4AEC]) and CYCLES the level on click
(0x85BAC), refilling the cells.

WIND 17501 psionic train: open 0x85FF4; cell list = ds:0x9B86 +
cell*2 (0-terminated, count at [0x9B84]), filled by 0x86107 from the
34x8-byte power table at 0x44F90 (discipline = row byte 3 & 0x3F,
name word row+6), filtered by OVR8 stub5 and the PSST mirror byte
[0x2F0]:0x77+char*0x22+power; icons = 3000 + power id. BUTN 11319
text = '  %d' level, 11320 = discipline name (table ds:0x30FA:
Kinetics/Metabolic/Telepath/Psi-port; per-char discipline byte
ds:0x9CE2+char). Click enhances: 'ENHANCE TO LEVEL %d' (0x86491).

Casting picker (the 0x48 MENU in 3007): fill 0x89740, list type 1/2
-> OVR9 stub4 0x5DF12 (class_bits 1 preserver / 2 divine, level
[0x4AE0+char] / [0x4AE4+char]); type 3 -> 0x9A4F (psionics); row
type byte [0x4AE8+char]; icon base at 0x897D0: 0x5208 for spells,
0xBB8 for powers. Counts format '%d LEVEL %d SPELL%FsTO CAST'
(0x4BB0F; cleric twin 0x4BB4D; ZERO variant 0x4BB30; 'YOU NEED TO
REST' 0x4BB8D guarded on the cleric byte then GSTATE 0x19).

15503 spell info (OVR49 stub3 0x8C5F6): icon bands: < 138 ->
21000+id, [0x8A,0xAC) -> 3000+(id-0x8A), innate >= 0xF9 -> 3100+,
stat band [0xC4..) -> 3044+, else 11103. EBOX 15400 gets the SPIN
chunk verbatim (load_resource('SPIN', spell_id), 200-byte buffer,
text at +5; failure prints '     UNKNOWN'). RESOURCE ships 180 SPIN
chunks; name and description are one blob.

### 8.5 Print formats the screens reuse

Custom sprintf at 0x22932 (%d %u %s %2d %+d %03d %C %Fs); EBOX text
draw 0x30D0D `(win, x, y, fmt, %C-args..., str, [0x3270], 0x14,
[0x326E])`; universal scratch buffer 0x348:0x4B; width measure
0x1E9F1. Stat-block helpers (OVR16 stubs): HP '%d/%d' (0x497BA) via
0x64C6B (combat+0 vs charrec+8); PSP via 0x64CED (combat+2 vs
charrec+0xC); 'AC: %2d' (0x497C0) via 0x64D70 calling the recompute
0x4E0:0x7F; 'DAM: ' assembled by 0x64DB9: attacks = (charrec+0x2A)/2
with '.5' if odd, '*', IT1R dice count (+13), 'D', sides (+12),
bonus (+14 + instance+20). Name tables: ds:0xEAA = MALE/FEMALE,
8 races, 10 creation classes, STR:..CHA:, 9 alignments;
ds:0x11DC = 9 conditions then the real_class names (the sheet's
multi-class line printer is OVR25 stub20 0x72B91 with per-class
colors from 0x72D29; gender/race line 0x64B57; alignment 0x64BF8;
condition 0x71D8B; 'EXP: ' 0x67CD9 -> dword drawer 0x651E7).
Inventory right panel: abilities at x=260, y=53+7i (0x6F533); 'PSI:'
at (236,99) with the value from stub7; money =
dword [0x2C0]:0x357 drawn by 0x6DA12 with tiered '%d,%03d,%03d$'
family (0x4A1BC..0x4A1E8) right-aligned to 12 at (60,185). Combat
HUD 'Move : %d' (0x496E5) = CSTATE2 movement points / 10 (0x1EC49);
there is no 'MOVES: %d' string in either game.

### 8.6 Load/save slot lines (preview)

Slots are 125-byte records at [0x388]:(idx*0x7D): +2 = filename
('SAVE%.2d.SAV' via 0x746C1), +0x52 = 43-byte display label pushed
verbatim to the BUTN text setter (0x140:0x7FA) for buttons
2059+i by 0x74E36; occupied flag = byte at record+2. The label blob
rides a PERF fourcc chunk id 100 (11 bytes across [0x11AE],
[0x232E..0x2330], [0x11A8/0x11AA/0x11AC]; field split not fully
proven).

### 8.7 Chrome screens (game menu, preferences, load/save, message box, popups, shop)

Game menu 10500 (ovr14, open 0x61AF7, OpenWindow at 0x61B26 with
dw_arg 0x2A0037, handle [0x11A4]). Event proc = ovr14 cs:0; item
dispatch is a 14-entry scan (id table cs:0x46F, handlers cs:0x48B):

| id | icon | action | handler |
|---|---|---|---|
| 10300 | 10100 | VIEW CHARACTER: opens 11500 for the leader (combat*0x3a + charrec*0x47) | 0x8A492 |
| 11304 | 11102 | VIEW INVENTORY: opens 13500 with literal 9999 = no shop | 0x6C1AB |
| 11305 | 11103 | CAST SPELLS/USE PSIONICS: 11500 spell-select mode, [0x4C2B]=3 | 0x88015 |
| 11306 | 11104 | CURRENT SPELL/EFFECTS: 11500 effects mode | 0x7E8A7 |
| 10301 | 10101 | EXIT: popup; peace = 'EXIT: SAVE GAME?' SAVE/QUIT/CANCEL, combat = 'EXIT GAME?' QUIT/CANCEL; SAVE -> save screen + quit-after, QUIT -> quit | 0x4D0:0x25 popup |
| 10302 | 10102 | LOAD/SAVE: popup LOAD/SAVE/RESTART (combat: LOAD/RESTART); RESTART sets [0x116A]=1 | |
| 10303 | 10103 | SET PREFERENCES -> PrefsOpen | 0x7F422 |
| 10305 | 10105 | OVERHEAD MAP (no WIND) | 0x7E204 |
| 10306 | 10106 | COLLAPSE PARTY (regroup on leader) | 0x420 |
| 10310/10311/10312 | - | cursor modes move/look/attack = 1/2/4 via 0x88:0x2927 | 0x2BD+ |
| 10313 | 10113 | CENTER ON LEADER: hard-disabled while GSTATE 0x2B8:0x19 != 0 (combat) | 0x93 |
| 10308 | 10108 | X close | 0x407 |

Hover tooltips: the APFM underlays 10202-10219 index a DGROUP far
table at ds:0x0C4A ('EXIT TO DOS', 'LOAD/SAVE GAME', 'SET
PREFERENCES', 'MOVE CURSOR', 'LOOK CURSOR', 'ATTACK CURSOR', 'COLLAPSE
PARTY', '', 'OVERHEAD MAP', 'CENTER ON LEADER'), printed into item
11270. Mouse-only; ESC closes.

Preferences 16500 (ovr37, open 0x7F422): 16300 music toggle
([0x11AA]), 16301 sound toggle ([0x11A8]), 16304/16305 music volume
step 6 ([0x232E], max [0x2330]), 16306/16307 sound volume step 7
range 0..127 ([0x232F]), 16308/16309 text speed 0..3 ([0x11AE],
labels 'EASY'... table ds:0x2331), 16303 mouse toggle ([0x11AC],
applies (16,16) vs (4,4) through 0x530:0x5C), 16302 = the credits
page (9 copyright lines + '1.10'), 11308 = back to game menu
(reopens 10500), 10308 close. State persists as the 14-byte 'PREF'
chunk (id 100) inside each save; F4/F5/F6 hotkeys DO NOT EXIST in
DS1 (binary-wide scan: no F-key handlers).

Load/save (ovr27): LOAD and SAVE both open WIND 3009 (0x7454F);
LOAD additionally binds title art 6030/6031 onto buttons
2056/2057. **WIND 3024 is never opened in DS1** (zero references to
0xBC8 or its scroll buttons) - it is dead shipped data; RESTART
lives in the game-menu popup. Slots are DOS FILES, not DARKSAVE
chunks: a 'SAVE??.SAV' findfirst scan fills records at
[0x388]:(slot*0x7D+2); the display name comes from the save file's
STXT chunk into +0x52 and is pushed verbatim to button 2059+si;
empty slots dim in LOAD mode. Keys: ESC cancel, ENTER confirm,
UP/DOWN move over occupied slots. SAVE confirm runs the modal name
edit (EBOX 4001, 44 chars) then 0x560:0x89; LOAD runs 0x560:0x8E;
both read/write the PREF chunk. F1/F2 hotkeys DO NOT EXIST.

Message box 10501 is the engine's transient message strip (the whole
192x28 face is BUTN 10309; click acknowledges), fed by 0x520:0x34
('GAME SAVED', 'NO RESTING DURING COMBAT', ...) - not the GPL 0x2C
log, which is the 3007 dialog array.

Popups 14000/14001/14002: 14001 is the low-memory fallback of 14000
(picked at 0x54DB0 when free < 0x2D20). One shared modal proc
(0x55258) serves every generic popup: click table maps 10308->0 and
the line buttons to 1..3; the keyboard path is CASE-INSENSITIVE
FIRST-LETTER per line (letters cached at [0x493C..0x493E]) and ESC
cancels only when the caller passed allow-ESC. So EXIT GAME accepts
S/Q/C like any other popup; a first-letter miss means a flag or a
colliding handler, not a different input model. 14002 is not a text
popup: it is the party ADD/DROP slot picker (six 18x18 cells +
11305 + X, opened at 0x55718 when a clicked member has combat+0x1C
!= 1).

Shop (hole 6): GPL opcode 0x24 stub (0xA962) calls 0x4251:0x98 ->
ovr22 cs:0x8D2: resolves the operand to a STATE slot, then calls
InventoryOpen(leader, shop) - the same 13500 opener with a real shop
id ([0x179C]; 9999 = none, [0x11B2] = doingshop). Stock source: the
STATE slot table at 0x360:0xC36 (3 bytes/slot {type, combat_idx}) ->
the shopkeeper creature's combat record -> its item rows in the
global instance array. There is no separate shop-stock chunk. SELL
and MORE are dimmed to state 1 outside shop mode.

MENU opcode 0x48 post-selection tail: the handler (0xCB5B) stores
(id, flag) pairs at VMCFG+0x27D/+0x2F9, appends lines via dialog cmd
0x5C8:0x25 (building the dynamic 'MENU %u' chunk, ds:0x3C0C), and
after the pick fetches the 1-based selection (0x5C8:0x34), bounds it,
and PUSHES THE STORED ID BACK ONTO THE GPL OPERAND STACK (0x99D5) -
that number is what the script then tests.
