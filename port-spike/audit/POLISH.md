# UI-parity audit: Wave 4 polish list (2026-09-20)

Method: each surface rendered by the port at integer scale, cropped to
the exact 320x200 board, and stacked against the committed DOSBox oracle
capture (`audit_sidebyside.py` rebuilds every sheet; watch the PNG
pairs). Live DOSBox driving was deferred this session at Brandon's
call, so the oracle stills are the parity spec; the side-by-side video
pass against a live game remains open (rig recipe: HANDOFF-wave3-4.md
plus the dosbox-oracle-rig memory).

## Fixed this pass (verified against the sheets)

1. Item cell icons: an item's icon is its base object's OJFF bmp_id
   sprite (asset-bindings.md 1), proven against the oracle: K'tarchek's
   blue cell icon is object 1010 Chatkcha. Icons now draw in every
   filled cell and ride the cursor when held.
2. Empty paperdoll cells show the engraved slot glyphs: BMP 13007
   frames 9..22 are the 14 slots in body-slot-table order (correlation
   1.00 against the oracle; f12/f19 and f13/f20 are the hand/finger
   pairs). Frame 4 is the yellow drop-target square, 6 the illegal X.
3. Inventory backdrop regenerated from the oracle capture
   (bg_13500.png): stone, leather, parchment, figure, party portraits
   and cell furniture baked; party HP/status, stat panel, money and
   name in-painted away and drawn live. Belt quick-cells and container
   cells stay unpainted as in the engine.
4. Party box art is the member's own world sprite (bmp 2097 =
   K'tarchek's bug matches the capture); wired into the inventory and
   sheet party boxes, with the selected box on the yellow frame.
5. Text weight: the engine double-strikes each glyph one pixel right;
   TextBlitter now does the same, matching the chunky oracle print.
6. Creation screen: stat/name/info rows re-pinned to the measured
   oracle tops (137+7i, name 127, class list 10+8i, disciplines
   104+8i); the leather regions under them are in-painted in bg_3011
   so live rows no longer ghost against baked text; per-row backings
   removed (at 7px pitch they erased descenders).
7. Sheet: PSP line added for casters (blue, shifts the status line),
   ink colours pinned to the oracle (white stats/origin/levels, gold
   EXP/HP/PSP/AC block).
8. Load screen binds the engine's LOAD title art (ICON 6030 onto the
   header plate, 6031 onto the confirm button); the 3009 chunk ships
   SAVE faces.
9. Game menu: collapse-party (10313) rests on its coloured frame 2;
   the silhouettes are the pressed art.
10. Combat HUD: format parity confirmed against the oracle panel
    (name / HP / condition / Move : N over BMP 5016, arc 5012); the
    QC harness board is now centred and integer-scaled.

## Open polish items (deferred, in build order)

1. Centre figure: every member shows K'tarchek's baked figure. The
   blank card is BMP 13005 but the per-member figure art source is
   still unpinned (needs an EXE dig; likely why the mining never
   attached it).
2. Spell casting (the USE picker's click-through into actual spell
   resolution in combat) is not wired; the grid and class/LEVEL
   cyclers are parity-only so far. Casting needs the engine's
   spell-effect runtime (docs/spell-effects.md).
3. Dialog 3007/3008 and interact 3020 are not built (oracle captures
   exist for 3007 variants). Dialogs are full GPL conversations
   (docs/dialogs.md); the pits loop needs the announcer sequence
   (portrait + lines) at minimum.
4. Message box 10501 (the transient GAME SAVED strip) is not built;
   the demo uses UI banners.
5. Sheet class line prints one ink; the engine colours each class
   separately (Fighter yellow, Druid red, Psionic yellow; table
   0x72D29). Needs multi-ink TextBlitter segments.
6. Combat detail rules not yet modelled: DEX reaction in the morale
   threshold, rear/flank THAC0-2 with direction tracking, crit
   blows adjust, monster damage bonus. Core structure (token
   machine, 20+d10+mods threshold with d200 tie-break, blows
   alternator, nat-20/nat-1 d20, 10/14 move costs) already matches
   docs/combat-flow.md sections 4-5.
7. Live side-by-side videos per surface (DOSBox left, Godot right):
   deferred; the stills here are the parity spec until that pass.
8. Damage splats are wired (hits: small/big red by damage, gold star
   on the kill, grey puff on a miss) and the fight loop is proven in
   the QC movie, but the 0.7s splat window landed between capture
   samples; confirm visually in the next live demo run.

## Covered by the second pass (2026-09-20 evening)

- Spell USE mode (sheet in spell-select mode): grid at the measured
  5x2 / (168,52) pitch (19,21), icons 21000+id, DRUID/LEVEL bars on
  the strip bars 11319/11320; oracle use_spells_ktarchek.png.
- EFFECTS mode (sheet, name-only panel); oracle
  effects_empty_ktarchek.png.
- Overhead map (O): BMP 10003 plate + region minimap 2:1 cropped to
  the interior from the region origin; oracle map_arena.png.
- Popups: WIND 14000 modal with first-letter/click dispatch; EXIT and
  LOAD/SAVE flows with combat/peace variants; oracle
  popup_14000_exitgame.png.
- Known-spell seeds per member (icon-matched from the oracle USE
  grid) on PartyData.
