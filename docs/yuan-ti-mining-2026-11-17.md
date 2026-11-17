# yuan-ti mining batch 2 (2026-11-17)

Second pass over Calvin Rodo's yuan-ti, after the 2026-11-13 batch
([`community-crossread-2026-11-13.md`](community-crossread-2026-11-13.md))
which had mined `dsun-exe-reference.md` (partially), `GplRequests.cs`,
`GplRepairs.cs`, and `ref_notes_from_obsidian.md` §5. This pass read
the remaining `.github/instructions/` files in full, the six
Scripting files outside the adopted set, and swept for format facts
in the engine tree. Source repo (MIT): `CalvinRodo/yuan-ti`; facts
credited per [`../CREDITS.md`](../CREDITS.md).

Statuses: **NEW** = we did not have it (relayed until our own pass
confirms); **CONFIRMS** = independent agreement with our verified
facts; **DIG** = contradicts or extends something we hold, and a
targeted dig ran (results in §Verification digs).

## New findings (relayed, most valuable first)

1. **Save-format field semantics** (ref_notes §2): sheet +0x04 =
   the monster's XP-worth; +0x0A = summed hit points per class
   level; race values 9 = undead and 14 = summoned beyond 1-8;
   alignment rows LG LN LE / NG TN NE / CG CN CE; class codes
   grouped air/earth/fire/water per four; sheet +0x2A =
   attacks/round x 2; +0x43 unused (Obsidian's kit byte); engine
   far pointers DS:165D items, DS:1661 sheets, DS:1665 creatures,
   DS:1669 item types.
2. **Item instance fields + inventory quirks** (ref_notes §2):
   item +0x0F = one past the spell's number (0 = none); +0x11 worn
   slots 0-13 (arm, ammo, missile, right hand, finger, waist,
   legs, head, neck, chest, left hand, finger, cloak, foot) and
   backpack 14-25; +0x14 = the plus. Quirks: the game fights with
   EVERY weapon in the worn list whatever its slot byte says, and
   the shipped party starts with worn armour in the backpack list
   carrying worn slot numbers.
3. **Thief-skill rules** (ref_notes §4): base chances
   28/18/13/28/18/23/78/-4 CONFIRM our 2026-10-07 dig; +4 per
   thief level; DEX bands per skill; equipment penalty
   5/0/0/10/5/0/10/0 when anything is in legs, quiver or either
   hand (the manual's "anything but leather" is wrong); condition
   rules (blind thief still hears noise; Slowed stops all but
   pick pockets; Fire Shield stops pick pockets and hiding;
   Mirror Image stops hiding; Graft Weapon stops three;
   Feeblemind stops read languages; Enlarge divides hiding and
   multiplies climbing by (100+10xlevel)%; Detect Traps makes
   find-traps certain for anyone; Invisible makes hiding certain);
   usage census (13 script checks; 50 trap triggers in 16
   scripts); move silently, hide in shadows and read languages
   are never rolled in the original.
4. **Character rules** (ref_notes §3): XP-for-2nd-level deltas
   (gladiator 2,000, ranger 2,200, thief 1,200); clerics/druids
   3-2-1 spell slots at 5th level where AD&D gives 3-3-1
   (`6798:071C`, per-class `6798:0B32`); PSP formula
   (`8E77:0162`: CON/INT/WIS bonuses, +10 per psionicist level
   after the first, +1 per level per WIS point above 15); level-up
   HP = sheet +0x0A / class count + CON bonus per level, warrior
   CON full capped +2 for others, no automatic maximum at first
   level, half-giant hit dice doubled, reroll on sex/race change;
   fighter/gladiator/ranger get 3/2 attacks from level 1;
   multiclass takes the highest class floor (roll scheme itself
   CONFIRMS chargen-flow).
5. **Saving throws** (ref_notes §6): spell save kind 5 maps to the
   sheet's THIRD save through table DS:1E75 (new address); kind 1
   serves the clouds, Poison, Slay Living and psionic attacks; the
   spell save byte is never used; the d20 doubling CONFIRMS
   spell-effects §4 and adds the element mapping (fire/cold/
   electricity lists); CON bands on para/poison saves; druids +2
   vs fire/electric; psionicists +2 vs mind; unseen caster +4 vs
   single-target; Cloudkill no save at <=6th; Chaos saves to
   warriors only; Dismissal adds target level, subtracts caster
   level. The WIS table CONFIRMS rules-tables.
6. **Combat mechanics** (ref_notes §7): Wait sets initiative to 10
   (or -1 if already <=10); NO critical hits (nat 20 hits, nat 1
   misses, the d20 never reaches the damage routine; backstab is
   the only multiplier); caster level = highest level in a class
   sharing the spell's sphere, elemental spells cast by a priest
   of another element count as level 0; clerics never get the
   common 4th/5th-level priest spells (druid-only in the table);
   psionics rules (powers at psionicist level, others at 1; kept
   powers re-cost upkeep each round and drop at PSP exhaustion;
   defender raises the best defence mode it knows and can afford;
   Mind Bar adds 75% magic resistance vs mind spells); psionic
   cost table at load segment +3FB9h, 8 bytes/power (+1 use, +2
   upkeep, 63h = none, +5 FEh = defence mode).
7. **Facing dynamics** (ref_notes §1.1): the first attack on a
   creature in a round turns it to face that attacker for the
   whole round; its own attacks don't turn it; later far-side
   attackers get from-behind (+2, target loses DEX bonus and
   shield), attack frame `[BP+20h]`/`[BP+1Eh]` near 612E:16CA,
   dice-log verified.
8. **Backstab once per round** (ref_notes §1.2): the multiplier
   applies only while attacks-made-this-round `[BP-0Ah]` <= 1;
   x2/x3/x4/x5 at thief levels 1-4/5-8/9-12/13+. Formula CONFIRMS
   combat-flow 207; the once-per-round gate is new.
9. **Two-weapon fighting** (ref_notes §1.4): both hands attack at
   full rate; every attack of both hands gains the DEX reaction
   table (`6868:033F`) with sign flipped, never below 0 (a bonus,
   +6/+4/+3/+2/+1/0 at DEX 1/2/3/4/5/6+); rangers excluded
   (`612E:295F`); no off-hand penalty. Absent from all our docs.
10. **SCMD layout** (dark_sun-game-data): 0x48-byte header holding
    32 start indexes (facing N/E/S/W x 8 actions), then 8-byte
    records: frame, delay (96 Hz ticks), flags (jump, stop,
    mirror, ...), dx, dy, hot spot x, y, sound.
11. **RDFF load-action grammar** (dark_sun-game-data): 10-byte
    headers (load action, block, type, index, from, length) each
    followed by `length` bytes; type 1 item (21 B), type 2 combat
    (58 B), type 4 character (71 B, +0x3D size -- see the digs
    below), types 3/5 reference NAME/IT1R by index with length 0;
    0xFF ends the list; load actions 1 = own record, 2 = new
    object in a field of `block`, 3 = reference, 4 = linked after
    `block`. Census: 755 item chains, 291 creatures, 98 creatures
    carrying 479 items.
12. **UI record field maps** (dark_sun-game-data): BUTN 110 bytes
    (130/163 with text at +0x6E): +0x08 number, +0x28/+0x2A size,
    +0x58 alignment bits (icon 8-9/down 10-11; text 4-5/down 6-7),
    +0x64 ICON frames normal/highlighted/disabled/pressed. APFM
    116 bytes: +0x58 alignment. EBOX 168 bytes: +0x7E background
    colour (229 = transparent), +0x80 text colour (199).
13. **Screen-to-asset bindings**: dialogue WIND 3007 over BMP
    3007; menu WIND 3008; input WIND 3500 + EBOX 4500 at (0,140)
    (`84C9:0253`); inventory WIND 13500 over BMP 13001, member
    figure BMP 20000+look at (120,96) on parchment 13005
    (`74F1:175A`/`17AF`), slot n at APFM 11216+n, silhouette BMP
    13007 frame 9+n, shut art 20104/20105, store goods 11242-
    11247; item window WIND 15502 (`91F7:0C29`); container 13501
    (`6527:002C`); chargen 3011; learn/pick 17500/17501; dual
    17502; quick cast 14002 (`5F6D:08EC`); icon APFM 1001 + BMP
    5012; damage splash BMP 5014; missiles OJFF 8101/8117/8500;
    game over WIND 3004 + BMP 10004. Window ids CONFIRM
    screen-flow.
14. **DS1 music routing**: menu plays track 17; a region plays the
    track named in its RDAT record at +0x2F; music levels
    (REQUEST 16, 382 uses; fight start at the creature's RDAT
    level, end at level 1) select sections via branch markers and
    the indirect-controller table (361A:0000 / 3164:0033), capped
    by MusicTracks at DS:1675; per-track flags DS:1676 (bit 4
    allows start, bit 2 hands to a hook); FM cards play GSEQ in
    DSUN.EXE too (`3256:00D3`); sounds 131-180 never play
    (`3172:0573`).
15. **EXE-only creature tables**: special-ability masks by type at
    3E45:0000 (42 types; combat record +0x16); the 11 abilities
    the AI tries in order (DS:05D0/05DB); monster spell sets
    (3FB9:0110), psionic sets (37F0:001C), AI spell weights
    (37E5:0000); ability bits named (regeneration, poison, acid,
    cold, paralysis, disease, babau corrosion, charm/hold
    immunity, webs, burrow/fly immunity, see-invisible); bits 7,
    10, 11, 28 never tested (10/11 = hit only by +1/+2 weapons per
    the clue book).
16. **Spell engine counts**: the spell record set = 196 records,
    45 area templates, 34 power records; spell levels/spheres at
    DS:019C; cast-from-items at level 6, one charge per cast, gone
    at 0 (`78A9:2324`); ability items 0xFA-0xFF: +0x0F - 0xFA picks
    the ability, charges add below 16, set a floor 16-31, subtract
    at >=32 (`80F5:2BB8`).
17. **GPL world facts**: every trigger starts with the actor's
    cell in gname[1..3] (`1A0A:0256`); the game clock runs 1.5 s
    per real second on the map and one minute per combat round,
    and stands still while the Look pointer is chosen; CLONE makes
    the copy "other" (`7372:0A44`); GETPARTY fills gname[8]
    (`043D:1468`) (identities CONFIRM gplx-field-map); SEARCH
    internals (`0826:0344`: op 3 counts items not quantity,
    smallest-of-nothing = 99,999,999); dead-body loot at a random
    body within 7 pixels (`612E:1AAF` -> `896E:0C92` -> `612E:2659`);
    rest healing (`87B3:073D`: poisoned-at-rest-start dies); store
    mechanics (`8A89`: six slots at value, restock at two); FLEE
    target cell (`1A0A:2C86`).
18. **Search loot and arena script facts** (ref_notes §7): junk
    rolls 0-14, hay and wardrobes 0-10; 0-1 finds nothing in junk,
    0-2 in hay/wardrobes; after 6 finds nothing more. Arena: fight
    count is GPL global 12; count 1000 spawns El's Drinker +2 and
    Bone Gythka +3; count 5000 = war won (flag 10, global 49 = 3);
    Kurzak recalls after 8 h 05 min game time.
19. **GPL interpreter limits** (dsun-decompilation §6): 25 menu
    entries; IF nesting past 0x1F ends the script through
    `fn_7372:17a7` -> gpl_exit; invalid opcode sets `377C:0009 =
    -1` and stops; RAND calls rand() before evaluating n,
    `(int16)(((int32)rand x (n+1)) / 0x8000)`. The 50/16/8/299
    limits CONFIRM gpl-vm.
20. **Executable segment map** (dsun-decompilation §7): segment
    0000 = Borland C++ 3.0 medium-model runtime, fully named in
    their `tools/ghidra/symbols.tsv` (619 lines, 350 named
    functions incl. all 114 GPL handlers with C prototypes --
    adoptable asset); 3653 = the VROOMM overlay manager; 303C = a
    DOS wrapper library with its own error code at DS:3CD8; 13A7 =
    VMEM (EMS int 67h / XMS int 2Fh).
21. **Offset-conversion bridge** (ref_notes §0): a seven-row table
    pairing yuan-ti seg:off with DSUN.EXE file offsets (e.g.
    80F5:1999 = 7A539h, 612E:1359 = 58019h -- the melee resolver,
    matching our own combat-flow citation) plus the conversion
    recipe against their `ovl_unpack.py`.
22. **Cinematics**: ACF 1-8 intro, 9-10 arrival, 11-13 ending; op
    0x7F (9944:1AD7) is the ending's battlefield pan (extends our
    cinematics-ds1 "12-operand scene draw" reading).
23. **GPLI purpose**: a lookup table mapping GPL resource numbers
    to their scripts (closes engine-quirks §8's open question, at
    loader level).

## CONFIRMS (highlights)

GFF container reading; region geometry 128x98; GMAP bits; the
world counts (WALL 664, PORT 112, GPL 217 + MAS 33, NAME 322x25,
IT1R 115x20, OJFF 2775/RDFF 1046/BMP 2419 in SEGOBJEX); FONT 100
layout plus the answer to our open question (the 256-byte
pixel-to-palette map is IDENTITY, codes 0x80-0xFF are code page
437, and the game patches map[254] to the current text colour);
spell icons 20999+SPIN; IT1R tenths/bytes; palette 6-bit with the
RGNFF -> PAL 1 fallback (a NEW detail vs our viewer-layer default);
CINE composition; stat generation; THAC0 rates; spell-slot
counters; GPLX field map + load targets (1269 bytes: 0x000-0x3DD
-> DS:4D7A, 0x3DE-0x440 -> DS:537A, 10 bytes -> DS:53F7, 0xAA
tail); the acid checks; difficulty scaling. The GplAssembler
round-trips all 250 scripts byte-for-byte, matching our 217+33.

## Verification digs (run 2026-11-17, main thread)

Four findings contradicted or relabeled facts we hold; each got a
targeted dig before anything was adopted:

1. **Race 6 naming (mul vs halfling): CALVIN RIGHT, our labels
   fixed.** The chargen race-name far-pointer array (DSUN.EXE
   0x49812, DGROUP 0x4356-relative) lists race bytes 1..8 as
   HUMAN, DWARF, ELF, HALF-ELF, HALF-GIANT, HALFLING, MUL,
   THRI-KREEN (MALE/FEMALE sit right before it as the gender
   array). chargen-flow.md relabeled: our old "mul, kreen-a,
   kreen-b" for races 6/7/8 was wrong, and the UI's
   "(idx>>1)+1" formula only holds through half-giant -- DS1's
   chargen creates seven races and skips halfling, so pairs
   10-13 remap past it.
2. **charrec +0x3D (footprint vs save descriptor): OUR READING
   STANDS.** The whole image carries exactly two readers of the
   byte (0x6AAE0 and 0x6AE61), and both are the same
   save-descriptor path: `index x 0x47` (the 71-byte charrec
   stride) from DS:0x1661, value pushed into the in-combat
   effect/save chain. No footprint reader exists at +0x3D; their
   footprint table has no engine consumer at this byte.
3. **IT1R +15 bits: OUR ENGINE-PROVEN READING STANDS, their names
   recorded as leads.** The shipped IT1R carries the flags on
   115 items: 0x02's only bearer is "Dagolar's Wand" (our
   missile reading; their "stacks" has no data support), 0x40
   two-handed and 0x80 armor confirm with the item lists, their
   0x01 "usable" gets one supporting data point (Corn), their
   0x08 "container" one weak one (Lava Dome).
4. **Hold Undead: OUR REFUTATION REINFORCED.** Their claimed
   fall-through chain (80F5:1793 -> 17B9, file 0x7A333 -> 0x7A359)
   is real code, but the bytes show the undead predicate
   (`call 0x7BE20`, race == 9) gating the application call
   (`0x7B120`): `or al,al; je 0x7A359` routes NON-undead targets
   away from the hold path. Their reading has the jump polarity
   backwards. known-bugs.md 3.7 row 11 stands.

## Follow-up seams

The thief-skill condition/equipment rules, save-format field
semantics, character-rules chapter, saving-throw modifiers and the
combat facts above are relayed until each gets our own pass; they
land in rules-tables / combat-flow / object-formats territory.
Adoptable asset: their `tools/ghidra/symbols.tsv` (619 curated
DSUN.EXE symbols with C prototypes, incl. all 114 GPL handlers).
Their README aside that DSUN.EXE has only three psionic
disciplines is worth one line in a future psionics doc. The four
digs above are settled; the two known joint gaps stand (resistances
beyond the fire elemental; OP_28 unnamed).
