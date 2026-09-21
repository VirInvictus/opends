# UI-parity audit: Wave 4 polish list (2026-09-20)

Method: each surface rendered by the port at integer scale, cropped to
the exact 320x200 board, and stacked against the committed DOSBox oracle
capture (`audit_sidebyside.py` rebuilds every sheet; watch the PNG
pairs). Live DOSBox driving was deferred this session at Brandon's
call, so the oracle stills are the parity spec; the pits live pair
landed 2026-09-21 (see the pits-parity pass section below).

## Covered by the pits-parity pass (2026-09-21)

- USE grid spell names: hovering a spell cell draws the engine's
  15104 highlight and prints the SPIN name into the header plate
  (the 17500 hover pattern, screen-flow.md 8.4). Engine-side proof
  in the live take: the AI's own USE hover prints the name on the
  message strip (take 3, ~130s), so both placements exist in the
  engine; the port uses the header. QC: SPIKE_HOVER=<cell>.
- Interact 3020 INFO opens the creature examine panel
  (creature_examine.gd on the 15500 plate): the clicked entity's ETAB
  object id through generated/ui/bestiary.json (export_bestiary.py,
  the extract-catalogue decoder; 290 DS1 rows). Region 42's one
  creature placement (318 Tied-up Prisoner) renders with art + row.
  Steal/give stay dimmed: the capability mask never offers them in
  the demo, and their handlers plus the mask source are unmined.
- Live pits pair: audit/videos/pits_live.mp4 (240s). Left: the real
  game driven by the padded AUTOTYPE recipe in live-capture/
  (ds1-pits3.conf + pits3_run.sh carry the schedule and the content
  map): story scroll, arena gate, announcer, exhibition fight, pens,
  Kurzak dialog with the WHAT DO YOU SAY choice strip. Right: the
  Godot cast demo (cast3.mp4) looped. Take 2's flat schedule died on
  the menu (all 580s idle); repeats around every transition fixed it.

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

1. Centre figure art is pinned and drawn per member (BMP 20000-20013,
   20000 + (race-1)*2 + (gender-1), port-digs 2026-09-20 1). Still
   open: per-character armour overlays (the engine layers worn gear
   onto the figure; needs another dig).
2. Spell casting from the USE picker is wired (2026-09-20 night, the
   mined ovr32 handlers; SPST 39-138 fall through to the engine's
   generic default). Remaining polish: the LEVEL cycler is still
   parity-only (the engine cycles level on click, 0x85BAC).
3. Interact 3020: TALK and INFO are wired (INFO -> creature examine,
   2026-09-21). Steal/give need the thief skill check and a transfer
   path; blocked on mining the capability-mask source (port-digs
   2026-09-20 3) and the two handlers.
4. Message box 10501 is built: save/load feedback ("GAME SAVED") now
   rides the 10001 plate strip with click/auto acknowledge.
5. Sheet class line: multi-ink segments are in (2026-09-20, e636163;
   the 0x72D29 group table in CLASS_INK, printed per class with pale
   separators).
6. Combat detail rules modelled (2026-09-20 night): DEX missile table
   in the round threshold (docs/rules-tables.md 0x7dc), rear/flank
   THAC0-2 with per-round direction memory (CSTATE2 +0x5b), crit roll
   4/1 doubling/halving the blow budget, and the monster damage bonus
   [0x11ae]-1 wired to the prefs text-speed setting. Live player
   attack input added: click an adjacent monster during the party's
   token (the attack cursor path).
7. Live side-by-side videos: the pits pair is cut (2026-09-21, see
   the pits-parity pass above). Still open: a paired Godot take of
   the SAME live stretch (story -> gate -> fight -> pens) so the two
   sides correspond event for event; and the damage-splat 0.7s window
   confirmation in a live Godot demo run.
8. Damage splats are wired (hits: small/big red by damage, gold star
   on the kill, grey puff on a miss) and the fight loop is proven in
   the QC movie, but the 0.7s splat window landed between capture
   samples; confirm visually in the next live demo run.
9. Examine strip 15500: the middle arrow (15302) is mapped as cycle
   forward pending the engine dispatcher dig (0x5EFC5 open); the RE
   verdict lands in port-digs when mined.

## Covered by the third pass (2026-09-20 night)

- DialogScreen (WIND 3007): stone plate regenerated from the oracle
  capture with the EBOX text in-painted (portrait frame + announcer
  face PORT 119 baked), wrapped FONT/100 lines at the measured
  (60,6)/9px pitch, Enter/Space/click paging, auto-advance for
  scripted QC. The scripted arena intro plays the real GPL-2
  announcer lines (citizens, gift, Celgor exhibition, do-not-worry,
  Monster Trainer, step forward) and victory says the
  go-back-to-the-pens line; audit/dialog.png.

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
