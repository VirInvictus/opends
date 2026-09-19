# The spell/effect machinery: cast path, dispatch surfaces, saves, special attacks, durations

How both engines cast spells and apply effects, decoded (port-mining wave 2,
2026-09-19). Companion to combat-flow.md (which owns the attack loop) and
rules-tables.md (which owns the math tables). All resolutions use the static
procedure of overlay-formats.md section 6; every far-call site named below
was validated as a member of its module's relocation table. Verified on the
GOG 1.10 corpus.

One tooling correction for anyone reusing the procedure: the per-module
relocation table sits at `module_file_start + code_size` directly (the
applier's `(size>>4):(size&15)` segment:offset form), not at the next
16-byte boundary.

## 1. Module ownership

| Role | DS1 | DS2 |
|---|---|---|
| Casting module (power-table consumer, cast engine + queue) | ovr32, file 0x78ba0..0x7c851, 83 stubs (frame constant 0x5b8) | not pinned (candidates: ovr13 spell UI, ovr4 AI rating) |
| Status/effect services + router + duration roller | ovr28, 0x750e0..0x77a21, 48 stubs (0x598) | ovr24, 0x7e2f0..0x80ece, 44 stubs (0x608); plus ovr10 (0x598) as second status module |
| Spell-effect applier band | ovr9 stub9 (0x5fa5) | ovr8 stub2 (via 0x588:0x2a) |
| Psionic applier band | ovr8 stub8 (0x5cb30) | ovr7 stub7 (via 0x580:0x43) |
| Special-attack probe | ovr6 stub8 (0x5a99e), frame 0x4e8 | ovr5 stub8 (0x5f64d), frame 0x570 |
| Special-attack enum tables | resident record 120 (file 0x43850) + ovr33 predicate | ovr29, frame 0x630 |
| Per-round effect processing | ovr30, 0x780c0..0x78adc, 12 stubs (0x5a8) | not read (same role, module not pinned) |
| Power table | resident record 118 (byte-offset 0x3b0), records at file 0x41f70, stride 32 | RESOURCE.GFF via the cached DATA-chunk getter at record 23 offset 3 (file 0x217f3); the real referent of the "0xb8:3" anchor: DS2-only, 80+ call sites, generic by chunk id |
| SPST/PSST/PSIN readers | ovr19 stub0 (0x67a46): 138 B SPST to 0x2f8:0x168+ci*0x8a; 34 B PSST; 7 B PSIN | ovr17 stub0 (0x6f8b6), position-identical twin |
| SPIN text reader | ovr49+0x1864 | ovr44+0x183b |
| Roll service (all dice) | ovr16 stub21 (0x648c1), frame 0x538 | via 0x568:0x66 (ovr4 stub14) |

Roll service contract: `roll(count, sides)` = sum over count of
`RNG()*sides/0x8000 + 1`; callers pass a packed dword (low word count, high
word sides): 0x140001=1d20, 0x640001=1d100, 0x60002=2d6, 0x80003=3d8.

## 2. The cast path (DS1 primary)

Confident negative: NO GPL OPCODE CASTS SPELLS. The 0x00..0x80 opcode table
has no cast entry; casting is engine-native end to end, entered from the
combat executor, the AI, periodic re-casts, and encounter spawns. The
SPST/SPIN chunk readers are save/load and text services.

Cast wrapper = ovr32 stub0 (`9A 20 00 B8 05`; 6 callers: ovr5+0x1e5f combat
executor, ovr28+0x10f0 effect-chain re-cast, ovr30+0x141/+0x907 periodic
re-cast, ovr38+0xabd/+0xc81 encounter spawn). Queue drainer = stub2, ticked
from ovr28+0x31 each round. Cast engine = stub1 (local 0x79, file 0x78c19):

1. Guards: caster special-attack word (+0x16) == 41 aborts; spell id 0xc0
   aborts; out-of-combat party caster (STATE type 1) counts and early-outs
   via 0x4e0:0x61.
2. `power.special(+17) & 0x200` requires GSTATE[0x19] outside {0,1}.
3. Positions via 0x598:0x25 for caster and target.
4. `effect = (i8)power[+25]`; id -1 (innate) yields 0.
5. Duration base: flag [0x5402] forces the -9999 sentinel, else 0x598:0x75
   (the duration roller, section 6).
6. stub70 resolves the real actor through 0xa0:0x32ef (charm/mirror
   redirect); failure aborts.
7. stub73: mirror-image retarget and area target walk.
8. stub71: target-validity gates, then the duration roll: effective caster
   level from the special-attack tables at record 120 (+0xa8 level
   override, +0xd2 element bitmask, +0xda element level, 4 slots, max
   wins) so elemental specialists cast at boosted level; target elemental
   resistance halves the result.
9. stub3 = the saving throw (section 4). Success: duration >>= 1, or = 0
   when `special & 0x8000` (is-attack bit).
10. effect != 0 and dur_mult != -1: 0x598:0x4d (remove existing copies),
    then 0x598:0x39 (insert into the active-effect list).
11. Target-count scaling: `count = count * duration / 100` (stub68), then
    stub46.
12. FX selection: hit word (+0x14) if != -1 else aoe_id (+0x17) indexes
    18-byte rows of the AoE shape table at record 121 (byte-offset 0x3a8)
    +3; hit_sound (+0x16) via 0x90:0xa6f.
13. Missile animation: 0x600:0x43 / 0x600:0x4d; innate attacks play
    charrec attack sound (+0x42) or sounds 4/5.
14. Cast queue: 6 slots x 14 bytes at record 119 (byte-offset 0x3b8),
    count byte [0x1e74]; overflow executes immediately.

Range/LOS: LOS services 0x58:0xdc and 0x58:0x114 (record 11), used
per-tile by the AoE walker; target-type legality stub6 with a 7-entry jump
table covering the record's 7 target classes. An explicit range-vs-power
comparison was not isolated (inside the stub70/stub73 chain).

## 3. Effect dispatch: two id spaces, no central table

Confirmed: no central effect-id jump table (wave 2 of the bestiary
campaign stands), but the dispatch is more tractable than "distributed" suggested:

- The CASTABLE id space (what the routers 0x598:0x89 / 0x608:0x89 switch
  on). DS1: [0,0x8a) = the 138 SPST spells, [0x8a,0xac) = the 34 PSST
  psionics (rebased 0..33), [0xac,0xc4) = 24 stat/innate records 172..195;
  >= 0xc4 no-op. DS2 router (ovr24 stub21, 0x2290): [0,0xeb) = 269 spells,
  [0xeb,0x10d) = 34 psionics, [0x10d,0x148) = innate band (records
  269..319); >= 0x148 no-op.
- The STATUS/EFFECT id space: the power record's effect byte (+25) doubles
  as a bit index into a per-target 10-byte (80-bit) status block, rebuilt
  on demand from the active-effect list (ovr28 local 0x1864 tail: ORs bit
  effect%8 into byte effect/8 per entry).

THE ACTIVE-EFFECT LIST (the heart of the system): DS1 segment byte-offset
0x390 (record 114), DS2 0x370 (record 110). 10-byte records at +0x106, max
192, count in DGROUP [0x1e24]: `+0 target, +2 caster, +4 spell id, +6
effect byte, +7 status byte, +8 timer countdown, +9 repeat count`.
Primitives in ovr28: stub5 insert (0x1301), stub9 remove-all-matching
(0x15cb, also cancels the timer and calls ovr30 stub8 to undo), stub4 bit
query (0x1ba1), stub16 sum of per-effect modifiers (0x1cc2).

Enumerated dispatch surfaces (DS1):

1. ovr32 local 0x5e6 (stub67): a 38-ENTRY PER-SPELL TABLE at 0xd96 (jump
   table 0xde2), keyed on castable id, plus a 5-entry miss-path subtable
   (ids {3, 62, 136, 139, 183}) and the generic default at 0xc90.
2. ovr30 stub7 (0x3c0): 10-entry periodic table at 0x647, ids {7, 9, 10,
   12, 17, 22, 33, 34, 47, 51}; re-applies fixed effects when status bits
   match (row 7 -> effect 12 when bit 0x10 of status byte 9; row 22 ->
   effect 47; row 47 -> effect 22).
3. ovr30 stub8 (0x66f): 6-entry tick/undo table at 0x8a3, ids {10, 65, 69,
   70, 71, 41}; case 10 re-applies effect 0x45 with 600 units per
   remaining count; case 65 restores combat allegiance from charrec;
   three cases play DGROUP strings 0x8ab6..0x8ab8; one strips a paired
   effect 0x40 from the same actor. For party members it maps effects
   {17, 10, 3, 11} onto combat flags +0x21 bits 0x20/0x40/0x60 (the
   fear/confusion/charm flag family).
4. ovr28 stub26 (0x78a): the AoE walker (tile list, per-tile LOS 0x58:0xdc,
   then stub18 = 0x2782 reading the AoE shape table, spawning per-tile
   world objects via 0xb8:0x55a; walls/clouds become world objects).
5. DS2's world layer: 0xf0:0x121 (resident 0x27121) maintains a 1500-entry
   x 37-byte world-effect record table at DGROUP 0x67bb, keyed by RDFF ids
   72..79, count [0x264e], with compaction when full.

Sample of the 38-table handlers (0-based castable rec, SPIN name where
known): 17 GLITTERDUST -> effect 0x17; 21/106/118 PROT-PARALYSIS family ->
strips effects 0x2f and 0x22; 24/149 STRENGTH -> 1d6 + insert; 27/122
DISPEL -> 1d100 + removals; 30 HASTE / 38 SLOW -> movement points
(CSTATE2+0x22b) doubled vs halved; 40 VAMPIRIC TOUCH -> die + effect 6;
61/108 SUMMON -> 1d20 gate + duration 0x3e8ffff; 72 CURE LIGHT -> 1d8
heal; 80/86/90 resist family -> area query + effects 0x48/0x46/0x47; 104
-> writes combat+0x22 (grants a special-attack word); 109 -> 2d6 + effect
0x22; 113/128 -> 2d8+1 / 3d8+1; 133 -> 1d60 + effect 0x32; 136 -> writes
combat status +0x1c; innate 6/14 -> apply_damage with 10000 (annihilate)
/ 1000 + effect 0x44; innate 22 -> walks all 74 status bits and mass-
strips via a 10-entry table at 0xd46. Roughly 60-70 distinct behavior
bodies are statically enumerable; the full 80-bit status space is about
0x50 live ids.

Damage word (packed dword at power+28), nibble orders pinned:
byte0 plus(5 low)|dice_plus(3); byte1 div(3)|dice(5); byte2 SIDES = LOW
nibble, SCALE = HIGH nibble (BURNING HANDS 0x03 = 1d3; MAGIC MISSILE 0x14
= sides 4, scale 1); byte3 savable(1)|save_mod(4 signed)|save_type(3).
dice_plus consumed at ovr28 stub16 (clamp 10); div at stub17 (floored at
1); scale sign-extended as the level adder (`shl 8, sar 12`), giving Magic
Missile's (lvl+1)/2. The final damage leaf (the arithmetic feeding
0x4e0:0x61) sits inside the 0x1991 area-walk chain or ovr9's tail: NOT yet
isolated.

## 4. Saving throws in the effect path

DS1 spell save = ovr32 stub3 (local 0xed1, file 0x79a71):
1. Gate on savable bit (byte3 & 1); save_type = byte3 >> 5 & 7 (6 = never
   saves).
2. Caster status bit 0x4 or dying target skips.
3. Column index from save_type; save number = charrec[row + 0x36 + idx]
   (the five stored saves at +0x37..0x3b for idx 1..5).
4. 1d20 via 0x538:0x89(0x140001); nat 1 auto-fails, nat 20 auto-saves.
5. `special & 0x86` doubles the roll (a penalty), plus the situational
   modifier (local 0x119c) and the signed save_mod nibble.
6. Saves when total >= save number.

DS1's in-combat RDFF-keyed chain = ovr22 local 0xa44 (file 0x6adf4): RDFF
lookup 0x560:0x25, actor resolve 0xa0:0x32ef, default save number =
(s8)charrec[row+0x3d], status modifier 0xa0:0x1c94, then placement and a
world-effect spawn. DS2's twin = ovr19 local 0xc00 (file 0x73aa0), whose
"check" (local 0xaa8) is NOT a die roll but a placement/scatter walk over
the 128x98 tile map seeded by the save number's bits; success spawns a
37-byte world-effect record and stores the index at MISC:0x363.

IMPORTANT FIELD CORRECTION: the runtime default-save byte is DS1 charrec
+61 / DS2 +55, the byte object-formats.md labels "size". The five stored
save bytes (+55..59 DS1 / +49..53 DS2) are WRITE-ONLY outside level-up:
an exhaustive fixed-offset read scan of both binaries finds no reader in
normal play (see rules-tables.md 1 for the mechanism note). A watchpoint
experiment should target the descriptor byte, not the five.

The level-up recompute (DS1 ovr46 local 0x59b, file 0x877eb) writes the
five saves from the class/level table at byte-offset 0x420 (record 132),
rows of 5 classes x 3 bytes, with a wisdom bonus (level*2/7) for clerics.

## 5. Special attacks

DS1 (the 33-value enum is two-level): the combat word at +0x16 indexes a
dword bitmask table at resident record 120 (file 0x43850). The probe (ovr6
stub8, 0x5a99e) fires only on 11 mapped bits (25% chance gate, RNG at
0x63b), tested via ovr33:stub0 against tables at DGROUP 0x5d0/0x5db:
bits {26, 20, 31, 30, 6, 12, 18, 19, 21, 22, 29} -> castable ids {0x1b
DISPEL MAGIC, 0xb5, 0xb9 innate 13, 0x1e HOLD PERSON, 0x8a psionic 0,
0xaf stat band, 0xb3..0xb7 innate 1..5, 0x2b FEAR}. Enum -> bit (first
match): 3->22, 9->20, 10->19, 12->29 (FEAR), 14->18, 16->21, 18/43/45/48/
50->26 (DISPEL), 21->31, 22->12 (stat 175), 28->29, 30->6. Most enum bits
are passive (defenses/on-hit); only these 11 produce probe attacks. Target
pick = ovr6 local 0x179 (enemy allegiance, current target word 0x348:0x1dd,
distance gate); on fire: 0x508:0x2a beam draw, then the router.

DS2 (the cb14 scheme): enum = combat+0xe low byte. Probe ovr5 stub8
(0x5f64d): effect = 0x630:0x20(enum, 0); target count = 0x98:0x154(actor)
clamped to 6 (multi-target specials, no DS1 twin); fires 0x608:0x89; then
post-action 0x630:0x34. ovr29 stub0 (0x87459) maps the enum through two
jump tables: category 0 (20 entries): 1->0x121, 2->0x122, 3->0x123,
4->0x124, 6->0x125, 7->0x120, 9->0x127, 10->0x12a, 12->0x12c, 15->0x130,
17->0x1b (same DISPEL slot as DS1), 19->0x13f, 20->0x120; {5,8,11,13,14,
16,18} unmapped. Category 1 (17 entries): 1-4->0x11e, 8->0x126, 16->0x13e.
All mapped ids sit in the innate band. Post-action stub4: enums 1-4 set
+0xe = 0x12 (a second phase); 6 and 17 clear it. No fire-chance gate found
in DS2 (unlike DS1's 25%).

## 6. Durations and timing

Formula (both games, instruction-identical): DS1 ovr28 stub17 (0x1bd3),
DS2 ovr24 local 0x1ec9. `duration = (roll(byte4&0xf dice, byte4>>4 sides)
+ (level + scale_nibble) * dur_per_level / max(div,1)) * dur_multiplier
(i16 at +7)`, clamped to 32767; multiplier -9999 returns the -10000
indefinite sentinel. The 60/600/3600/-1/1 unit multipliers are consumed
exactly here, and the damage word's div/scale fields are SHARED with the
duration formula (why Mirror Image and Stoneskin "group" by div).

Storage: the active-effect record's +8 countdown; timer enqueue
0xd0:0x20d(7, target, 0, clock + duration, 0) (ovr28 0x149f), cancel
0xd0:0xc (0x1667). Clock = the DGROUP dword [0x9b72] divided by the word
[0x9b70]. Round cadence: round init calls ovr30 stub5/stub6: a two-phase
divider at record 116 (byte-offset 0x3a0): byte 0 counts 0..9, each wrap
increments byte 1 toward 0x3c (60); the 60-per-round counter is fed by
ovr30 stub11 (adds arg*60 to MISC+0x35b).

## 7. Corrections issued to other docs

- combat-flow.md: the "0x88:0x34b6 AI spell probe x3" reading was wrong
  (it resolves to resident record 17, file 0x1e126: an object-walking
  animation/sprite-advance driver; the x3 loop is three animation ticks).
  DS2's real AI spell rating is the all-320 loop in ovr4 around local
  0x3540..0x3687; DS1's twin not pinned. The special-attack "parameter
  record" reading of 0x630:0x20 corrected (it is the enum-to-effect-id
  mapping).
- object-formats.md section 6: the "no table-indirect dispatch on the
  effect byte" wording was too strong: ovr30 stub8 dispatches on the
  effect/status id through a jump table, and ovr32/ovr29 dispatch on
  castable ids. The narrow conclusion (no single central table keyed on
  +25 alone) stands. Damage-word byte2 nibble order now pinned (sides
  low, scale high); div/scale shared with duration.

## 8. Still open

1. The generic damage-number leaf (plus + dice/sides feeding apply_damage).
2. DS1's AI actor spell-choice function (DS2's is ovr4 local 0x3540..0x3687).
3. DS2's cast-engine module identity and its per-round processor.
4. Semantics of ~35 remaining status/effect bit ids beyond the ~15 pinned.
5. Whether DS2's special-attack probe has any fire-chance gate.
6. The situational save modifier body (ovr32 local 0x119c).
7. The 0x45 re-application effect's identity (inferred, not proven).
8. Runtime confirmation items: the 10-byte status block refresh points,
   the special-attack current-target word, the DGROUP[0x86] hook, the
   absolute EXE load base (only needed for absolute runtime addresses).
