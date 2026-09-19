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
