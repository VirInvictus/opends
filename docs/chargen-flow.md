# Character creation, advancement, and rest: the pipeline

How both engines make and advance a party (port-mining wave 3, 2026-09-19).
The math substrate is rules-tables.md; this document owns the pipeline that
applies it. Verified on the GOG 1.10 corpus. Offsets are file offsets in
DSUN.EXE (DS1 / DS2 = `.games/ds2/DSUN.EXE`, "DS2.EXE" in older docs).

## 0. The class-id substrate

Two distinct id spaces:

- The CREATION class enum 1..8: 1 Cleric, 2 Druid, 3 Fighter, 4 Gladiator,
  5 Preserver, 6 Psionicist, 7 Ranger, 8 Thief. Creation code indexes XP
  rows directly with it (DS1 0x645f7: `imul ax,ax,0x28` on the class
  byte).
- The ENGINE real_class enum (charrec/combat rows): 1..4 Cleric (elemental
  sphere variants), 5..8 Druid (sphere variants), 9 Fighter, 10 Gladiator,
  11 Preserver, 12 Psionicist, 13..16 Ranger band, 17 Thief, 18 generic
  "MAGE", 19 generic "CLERIC", 20 generic "PSlONlC" (NPC shorthand; 18/19
  remap to the never-level row).

The DGROUP 0x11dc pointer table (rules-tables open item, RESOLVED): a
DISPLAY-NAME table at file 0x49b3a (DS2 twin DGROUP 0x1483), 29 far
pointers, indexed by the level-up message at [real_class + 8] (DS1
0x87bf0). Entries 0..8 are condition strings (New, Okay, Stunned, Out
Cold, Dying, Dead, Animated, Petrified, Gone); 9..12 "Cleric" x4; 13..16
"Druid" x4; 17 Fighter; 18 Gladiator; 19 Preserver; 20 Psionic; 21..24
"Ranger" x4; 25 Thief; 26 " MAGE"; 27 "CLERIC"; 28 "PSlONlC". The same
band runs explain the x4 sphere families.

The class remap (engine id -> XP row), stride-2 bytes at DS1 record 103
+0xca (frame 0x338) / DS2 record 108 +0x9d (frame 0x360, consumed
1-BASED): rows 0,1,1,1,1,2,2,2,2,3,4,5,6,7,7,7,... so classes 1..4 -> row
1, 5..8 -> row 2, 9 -> 3, 10 -> 4, 11 -> 5, 12 -> 6, 13..16 -> 7, 17 -> 8,
18/19 -> 0 (never level), 20 -> 2. The odd bytes of each pair (0x80/0x40/
0x20/0x10 patterns) are an unexplained parallel field (suspected
legal_class bit contributions).

## 1. The XP tables (CORRECTED labels; supersedes rules-tables.md section 3's first version)

DS1: a 10-row table at file 0x3e57c..0x3e70c (record 104 + 0x27c), 20 u16
per row, values x100, entry k = the minimum XP for LEVEL k+1 (proven: the
level-up gate promotes when T[row][current_level] <= XP at 0x87ba5, and
creation sets level 3 with XP = T[class][2] exactly at 0x64601):

```
row0  filler (256,1,257,...)            classless / never-level bands 18,19
row1  cleric:     0,15,30,60,130,275,550,1100,2250,4500,6750,9000,...,27000
row2  druid:      0,20,40,75,125,200,350,600,900,1250,6750,9000,...,27000
row3  fighter:    0,20,40,80,160,320,640,1250,2500,5000,7500,10000,...,30000
row4  gladiator:  identical to row3
row5  preserver:  0,25,50,100,200,400,600,900,1350,2500,3750,7500,11250,...,37500
row6  psionicist: 0,22,44,88,165,300,550,1000,2000,4000,6000,8000,10000,12000,15000,18000,21000,14000,17000,30000
row7  ranger:     0,22,45,90,180,360,750,1500,3000,6000,9000,12000,15000,18000,21000,14000,17000,30000,33000,36000
row8  thief:      0,12,25,50,100,200,400,700,1100,1600,2200,4400,6600,8800,11000,13200,15400,17600,19800,22000
row9  all 0xFFFF  (the never-level band the remap's 9..12 rows reach)
```

The NON-MONOTONIC dips (level-19 threshold below level-18's) sit in the
PSIONICIST and RANGER rows of DS1. (Earlier notes blaming "preserver/
defiler" rows had the labels shifted by the row-order mistake.)

DS2: RESOURCE.GFF FOURCC `DATA` id 1000 (320 bytes = 8 rows x 20 u16 at
RESOURCE offset 0x1858b), consumed 1-based through the same remap values:
row 0 cleric, 1 druid, 2 fighter, 3 GLADIATOR (an own DS2 curve: 0,22,45,
90,180,360,750,1500,3000,6000,9000,12000,15000,18000,21000,20000,22500,
25000,27500,30000), 4 preserver, 5 PSIONICIST (the 21000 -> 14000 dip is
PRESERVED here), 6 ranger (the dip is FIXED: 21000 -> 24000), 7 thief.
So DS2 re-cut its table: fixed ranger tail, own gladiator curve, kept the
psionicist bug. AddXP: party-split, clamps at 2,000,000,000 (DS1
0x6b817..0x6b8ff; DS2 0x7452e).

## 2. Creation (windows 3011/3012/3013 DS1 = modules 16/17/19; 19503/19504/19505 DS2 = modules 15/17/14)

The character under construction is a full charrec (DS1 DGROUP [0x119c]);
on finalize it copies into the party arrays [0x1661] (charrec) / [0x1665]
(combat), 4 slots.

- Race/gender: UI list 0..13 -> race (idx>>1)+1, gender (idx&1)+1; idx
  12/13 are the two thri-kreen entries. Races 1..8 = human, dwarf, elf,
  half-elf, half-giant, mul, kreen-a, kreen-b (DS2 adds race 9).
- Stat generation (engine-proven): BEST OF 4 ATTEMPTS of (4d4 + racial
  modifier + 4) per stat, floored at the class minimum. Reroll service
  DS1 0x6490d (roll loop 0x64978..0x6499d, dice helper 0x648c1, RNG =
  Borland rand at 0x822, deterministic: see section 5). Racial modifiers
  are signed bytes at DS1 record 103 +0x14d + race*6 + stat (DS2: record
  108 +0x120): human all 0; dwarf +1/-1/+2/0/0/-2; elf 0/+2/-2/+1/-1/0;
  half-elf 0/+1/-1/0/0/0; half-giant +4/-5/+2/-5/-3/-3; mul -2/+2/-1/0/
  +2/-1; kreen-a +2/0/+1/-1/0/-2; kreen-b 0/+2/0/-1/+1/-2 (STR DEX CON
  INT WIS CHA). Manual adjust clamps to [class_min, racial_mod + 20].
- Class stat minimums (record 103 +0x180, rows {u16 prime_stat, i8 min}):
  Cleric WIS 9, Druid WIS 12, Fighter STR 9, Gladiator STR 13, Preserver
  INT 9, Psionicist WIS 12, Ranger WIS 14, Thief DEX 9; max over selected
  classes, and a queried stat that IS a selected class's prime stat is
  forced to minimum 17 (0x673c3). So a rerolled prime stat never lands
  below 17.
- Race/class legality: a u16 mask per race (DS1 record 104 +2*(race-1) =
  file 0x3e300; DS2 record 109): bit (0x80 >> (c-1)) = creation class c.
  Human 0xFF; dwarf 0xB5; elf 0xBF; half-elf 0xFF; half-giant 0xB6; mul
  0xF7; kreen-a 0xF5; kreen-b 0xF6; DS2 race 9 = 0x0201.
- Multi-class: the race x classA x classB legality grid is DATA:1001
  (RESOLVED; 576 B, byte at [race-1]*0x48 + (classA-1)*9 + classB, classB
  = 0 while single-class): a bitmask of classes that may still be ADDED.
  The human row is all zeros in both games: HUMANS CANNOT MULTI-CLASS at
  creation. Demihumans multi-class up to 3 slots (toggle at DS1 0x63c95).
  Cleric/druid rows are largely zero; preserver rows zero.
- Starting level/XP (class-set switch DS1 0x64575):
  - single: level 3, XP = T[class][2] * 100.
  - dual: levels 2/2, XP = max(T[c1][1], T[c2][1]) * 100, then ANY class
    whose T[c][2] <= XP is bumped to level 3 (psionicist+thief starts
    3/2).
  - triple: 2/2/2, XP = max of three T[c][1], same bump.
  - DS2: START AT LEVEL 7 (single) / 6 (multi, same per-class bump to 7);
    XP = DATA:1000[class][6 or 5] * 100 (0x6c397..0x6c4ea).
- HP/PSP init: finalize (DS1 0x66bd0..0x66cea; kreen get 4 attacks 1d4,
  move 15) chains the recompute: base-HP variant -> PSP -> THAC0 -> saves
  (the 0x628:{0x2a,0x39,0x3e,0x4d} family of rules-tables.md; saves init
  to 99 at 0x87813).
- Psionics: race selection initializes psionic state (DS1 helpers
  0x63efa/0x63fee); the wild-talent draw lives in the 3012 page (module
  19) and was not fully isolated.
- Preset party: the "Start" path loads authored charrec templates from
  SEGOBJEX.GFF (Cermak, Saria/Cilla, K'ratchek: hand-authored XP and
  19/21/17-tier stats, NOT creation-math output).

## 3. Dual-class and the level-up path

Dual-class (window 17502, DS1 module 45 0x866d9): eligibility (0x86e94) =
race 1 (HUMAN ONLY); current class prime stat >= 15 and new class prime
stat >= 17; real_class[2] == 0 (single-class only); level >= 2. The AD&D
dual rule with SSI's stat gates. Multi vs dual at level-up: BOTH games'
gates skip class slots > 0 for humans (DS1 0x87b59; DS2 0x9587f): a human
advances only slot 0; demihumans advance all slots from the shared XP
pool.

Level-up (DS1 gate 0x87af6, wrappers 0x87cdf/0x87cf0; DS2 mirror module
41, gate 0x9581c): preconditions party state 2, combat status <= 2,
charrec +0x10 != 0 (the "negative link" byte doubles as a liveness gate),
and the human/slot rule. Promotion when T[row][level] * 100 <= XP. Caps:
DS1 LEVEL 9 (`cmp byte [level],9` at 0x87be6) with NO BYPASS anywhere
(resolved: the only other level writers are creation and preset data);
DS2 LEVEL 15 (0x9595a5) plus an XP BANK CAP: XP above T[row][level+3] *
100 is clamped down before promoting (0x958bd). Applier (DS1 0x879b5):
level++, raise high_level, HP roll (group die, max(roll, CON floor)), PSP
recompute, THAC0 derive -> combat, saves walk; message with the 0x11fc
name table. Player choices at level-up: NONE except class hooks:
Preserver -> new-spell-circle notice (0x620:0x5c, feeds the 17500 study
window); Psionicist -> pick-count from the new level -> the 17501 train
window (0x620:0x57). No proficiency or attribute UI exists.

## 4. Rest and memorization

Rest (DS1 module 38 stub 0, file 0x8066d): combat flag set -> prints
'NO RESTING DURING COMBAT' (0x4ae84) and aborts; otherwise prints 'THE
PARTY RESTS' (0x4ae9d; screen-flow.md's addresses were swapped, now
fixed); per member: status resets, rest-quality cures at cleric/druid/
preserver level bands (>= 5, >= 7) via effect codes 0x60/0x67/0x69/0x76;
heals hp/psp to base, restores drained STR, removes effects 0x23 and 1;
advances the clock: hours -> 0x5a8:0x57 adds minutes*60 SECONDS to the
master clock at frame-0x2c0 +0x35b (THE MASTER CLOCK IS IN SECONDS); the
engine-native caller (module 15, 0x62c32) rests 8 HOURS (0x80000). DS2
mirrors both strings (0x4f8da/0x4f8f7); its handler body was not
pinpointed.

Memorization: spell/psionic knowledge = the SPST/PSST/PSIN chunks (SAVE
side only: none exist in any shipped GFF; DS1 reader copies 138 B, DS2
copies 15 B SPST + 34 B PSST + 1 B PSIN per class slot; see
spell-effects.md 1). Windows 17500/17501 are the study/train pickers, fed
by the level-up hooks. The per-level slot-count table and the
memorized-vs-castable runtime arrays were not located (open).

## 5. The RNG (engine-proven, port-critical)

All 22 (DS1) / 29 (DS2) `call far 0:0x822` sites are one MZ-relocated far
call to Borland's C library rand() at file 0x5c22 (DS1) / 0x5a22 (DS2):
`seed = seed*0x15A4E35 + 1; return (seed >> 16) & 0x7FFF`. RANGE: 0..32767
inclusive, so the roll contract's /0x8000 is exactly unbiased. srand
exists at seg0:0xc11 with ZERO CALLERS: no timer seed; the stream is
DETERMINISTIC FROM 0 per run. A port that replays the same call order
reproduces the same dice in both games.

## 6. DATA chunks (DS2 RESOURCE.GFF)

- DATA:1000: the XP table (section 1).
- DATA:1001: the race x first-class x second-class legality grid
  (section 2).
- DATA:1002 (168 B): 21 pairs (u32 83000..270000, u32 id) with ids = {1}
  + {50..69} = SPIN spell ids (ARMOR plus the level 4..6 wizard
  area/persistent spells). Confident negative: no instruction pushes
  DATA id 1002; it is either consumed through the generic resident
  DATA-chunk cache (DS2 0x217f3) or shipped-but-dead. The (value, spell)
  shape fits a per-spell effect lifetime in ticks (100000 ticks ~ 92
  minutes), but that is hypothesis.

## 7. Open items

1. DATA:1002's consumer (strong negative on a direct one).
2. Creation-time initial SPST known-spell initialization (the runtime
   buffer is the vehicle; no writer isolated in the creation modules).
3. The memorized-slot-count model and where "memorized" state lives.
4. DS1 wild-talent draw specifics (module 19).
5. The GPL Request 0x22 rest arm mapping in module 15's request table.
6. DS2's rest handler body and its creation finalize chain call sites.
7. The remap table's odd bytes.
8. Which kreen variant is male vs female (presentation-side).
