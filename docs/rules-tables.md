# The AD&D 2E rules tables in DSUN.EXE: the rules block, saves, THAC0, XP, abilities

The character-math data layer of both engines, decoded (port-mining wave 1,
2026-09-19). Verified on the GOG 1.10 corpus; every claim carries the file
offset or instruction site that pins it. This is what a from-scratch
reimplementation (the Godot port) reproduces character math from. The combat
flow that consumes these tables is combat-flow.md.

A mechanism note first: the rules CODE lives in overlay segments, and far
calls / absolute segment references inside overlay code carry link-time
placeholder segments (DS1 "0x420", DS2 "0x4d0", plus recurring pool constants
DS1 "0x338"/"0x360", DS2 "0x360"/"0x5c8"/"0x628"). These are segtab
byte-offsets / pool-frame constants, NOT load-linear addresses; see
overlay-formats.md for the resolution procedure and its one open caveat.
The rules DATA block, by contrast, is static resident data in both games.

## 1. The consolidated rules block

File DS1 0x45f10..0x45fb8, DS2 0x4ade0..0x4ae88: 168 bytes, byte-identical
logic in both games, sitting immediately before each game's overlay
descriptor region. Consumers: the DS1 "character-rules" overlay segment at
file 0x87250..0x87d01 (descriptor 0x48520); the DS2 mirror in the segment
containing 0x954a0..0x96000. Offsets within the block:

### +0x00: four 4-byte class-GROUP rows (hit_die, last_rolling_level, post_level_gain, thac0_rate)

| group | row | meaning |
|---|---|---|
| 0 priest | (8, 9, 2, 8) | d8 to L9, +2/level after, THAC0 improves 8/12 per level |
| 1 warrior | (10, 9, 3, 12) | d10 to L9, +3 after, THAC0 1/level |
| 2 wizard | (4, 10, 1, 4) | d4 to L10, +1 after, 1 per 3 levels |
| 3 rogue | (6, 9, 2, 6) | d6 to L9 (not 2E's 10), +2 after, 1 per 2 levels |

Consumers: level-up HP roll DS1 0x87296..0x8731b; THAC0 derivation DS1
0x87682..0x876a5.

### +0x10: 32-byte class-id -> save-group map

`[0,0,0,0,0,0,0,0,0, 1,1,2,3, 1,1,1,1, 3,2, 0,0, 1,1,1,1,1,1,1,1, 2,2, 4]`

Ids 0-8 = priest family (0 = classless/generic), 9 = fighter-class warrior
bucket. Ground truth: 9,10,13-16 -> warrior; 11,18 -> wizard (preserver /
defiler); 12,17 -> rogue (thief / bard); 19,20 -> priest; 21-28 -> warrior
(monster categories); 29,30 -> wizard (monster); 31 -> group 4. This map is
HOW "monsters use the warrior group" works: a monster's real_class maps to
group 1 and its level[0] (hit dice) becomes that group's level. Validated
against the charrec corpora (290 DS1 / 352 DS2 rows).

### +0x24: 20-byte class-id -> legal-item bit table

`00 01 01 01 01 01 01 01 01 02 02 04 08 02 02 02 02 10 04 01`, consumed by
the item-usability gate DS1 0x86f3f..0x86f9a.

### +0x30: 7 bytes `08 02 02 02 02 10 04`

RESOLVED (wave 2): not a separate table. The legal-item table ends
exactly at +0x38, and these bytes ARE legal-item entries 12..18 (the
monster/bard class band), consumed by the same usability gate (DS1
0x86f3f..0x86f9a), whose index is unclamped (class ids 20..31 read into
the CON-floor table, same bug family as the ability getters).

### +0x38: 26-entry CON-indexed HP floor

`+1` for CON 0-19, `+2` at 20, `+3` at 21-22, `+4` at 23-25. Level-up reads
`[block+0x38+CON]` (DS1 0x87323..0x8732a; DS2 0x95ce6..0x95cf3) and applies
HP gain = max(die roll, floor). THE ENGINE HAS NO 2E-STYLE ADDITIVE
PER-LEVEL CON BONUS: low CON never reduces a level-up roll, high CON only
raises the minimum.

### +0x52: 26-entry CON-indexed PSP table

Signed bytes, CON 0..25: 0-1 -> -3; 2-3 -> -2; 4-6 -> -1; 7-14 -> 0; 15 ->
+1; 16 -> +2; 17 -> +3; 18 -> +4; 19 -> +5; 20 -> +5; 21-23 -> +6; 24-25 ->
+7. PSP gain = `t[CON] x psionic_level + min(t[CON],2) x other_levels`
(DS1 0x875a8..0x875dc).

### +0x6c: saving-throw table, 4 groups x 5 categories x 3 bytes (base, step, cap)

Category order = the stored charrec order: paralyzation/poison,
rod-staff-wand, petrification, breath, spell. Row order: priest, warrior,
wizard, rogue (a 5th row is all-zero dead data; the cx==4 branch is
defensive).

```
priest : (10,45,2) (14,45,6) (13,45,5) (16,45,8) (15,45,7)
warrior: (14,69,3) (16,69,5) (15,69,4) (17,82,4) (17,69,6)
wizard : (14,30,8) (11,40,3) (13,40,5) (15,40,7) (12,40,4)
rogue  : (13,25,8) (14,50,4) (12,25,7) (16,25,11)(15,50,5)
```

Formula (instruction-proven, DS1 0x877eb..0x87943; DS2 0x954a0..0x95620):
`save = base - min(step*(level-1)/100, cap)`, applied per class group from
a per-group level array (helper DS1 0x876c3 fills it from real_class/level
via the +0x10 map), and the charrec's five stored bytes (DS1 +55..59, DS2
+49..53) take the MINIMUM across groups (initialized to 99 first). The
bases are exactly the 2E level-1 rows.

Dwarf/mul racial bonus (both games, identical): when computing the warrior
row and race (charrec race field) is 2 (dwarf) or 6 (mul), improvement +=
`CON*2/7` (integer div), the 2E CON/3.5 rule, uncapped.

DIVERGENCE, important for a faithful port: the engine formula improves saves
more slowly than the PHB tables (engine warrior paralyzation: L1 14, L4 12,
L8+ 11; PHB/bestiary-authored: L4 13, L8 10, L17+ 4). Shipped monster/NPC
save bytes were authored to PHB bands. A port using the engine table will
not reproduce the shipped data at level-up; both readings are documented,
the table is engine truth.

Spell save categories map onto the five stored bytes via the packed damage
word (object-formats.md save_type 1-8: poison/paral/death -> byte 0, wands
-> 1, petr -> 2, breath -> 3, spells/magic -> 4).

Save roll consumption (RESOLVED, wave 2): the five stored bytes have NO
reader in normal play (an exhaustive fixed-offset read scan of both
binaries confirms it; they are write-only outside level-up). The RUNTIME
save path uses a different byte: the default-save DESCRIPTOR at DS1
charrec +0x3d (61) / DS2 +0x37 (55), the byte object-formats.md labels
"size" (packed category + modifier; DS1 splits it &7 // 8, DS2 &0xf //
0x10). The d20 comparison itself lives in the spell/effect machinery
(spell-effects.md 4): gate on the savable bit, 1d20 vs the save number
(nat 1 auto-fails, nat 20 auto-saves), `special & 0x86` doubles the roll
as a penalty. The in-combat RDFF-keyed chains are DS1 ovr22 local 0xa44
(file 0x6adf4) and DS2 ovr19 local 0xc00 (file 0x73aa0).

## 2. THAC0

Derivation DS1 0x87666..0x876c2 (DS2 mirror): `THAC0 = 20 - max over
groups( thac0_rate * (group_level-1) / 12 )`. Warrior rate 12 gives
THAC0 = 21 - level exactly; priest 8/12; wizard 4/12 (L20 -> 14); rogue
6/12 (L20 -> 11). Best group wins for multiclass. No level cap in the
formula.

The "21-HD monster" mechanism: the group-levels helper maps real_class via
the +0x10 table and uses hit dice as the group's level, so monsters derive
warrior-style THAC0 AND warrior-row saves from HD. The derivation path
exists in-engine; the bestiary's "hand-tuned" reading was incomplete.

Store/read sites: DS1 writes combat+31 at 0x86d7e and 0x87a91, reads it at
0x5811f; DS2 writes combat+22 at 0x6e8f5, reads at 0x5c6e9 (confirming
object-formats.md). The level-up applier (DS1 0x87944..0x87ac0) chains: HP
roll (0x87250) -> PSP recompute (0x875df) -> THAC0 derive+store (0x87666)
-> saving-throw walk (0x877eb), plus class-0xb/0xc hook calls.

## 3. XP advancement

CORRECTED 2026-09-19 (wave 3; the authoritative version with the full
tables and DS2 differences is chargen-flow.md sections 0-1). Summary: DS1
carries a 10-row table at file 0x3e57c..0x3e70c (record 104 + 0x27c): row
0 filler, rows 1..8 = cleric, DRUID, FIGHTER, GLADIATOR (copy of the
fighter row), preserver, PSIONICIST, RANGER, thief, row 9 all-0xFFFF
(never level). Entry k = the minimum XP for LEVEL k+1 (not k+2). The
non-monotonic dips (level 19 below level 18) sit in the PSIONICIST and
RANGER rows. The earlier labels in this section's first table ("fighter/
gladiator/ranger/thief/preserver/defiler") were shifted by reading the
rows in the creation-class-name order instead of resolving them through
the class remap. DS2's table is RESOURCE.GFF `DATA` id 1000 (8 rows, own
order): cleric, druid, fighter, gladiator (own DS2 curve, tail 20000+),
preserver, psionicist (the 21000 -> 14000 dip PRESERVED), ranger (dip
FIXED: 21000 -> 24000), thief.

Consumers: character creation (DS1 0x645df..0x64870: single-class starts
at LEVEL 3 with XP = T[class][2] * 100; dual 2/2 with XP = max(T[c1][1],
T[c2][1]) * 100 plus a bump of any class whose T[c][2] <= XP to level 3;
DS2 starts at LEVEL 7/6) and the level-up gate (DS1 0x87b67..0x87c00,
promotes when T[row][current_level] * 100 <= XP). The level-up gate
indexes via the class remap (stride-2 bytes at DS1 record 103 + 0xca /
DS2 record 108 + 0x9d, consumed 1-BASED in DS2): classes 1..4 -> row 1,
5..8 -> row 2, 9 -> 3, 10 -> 4, 11 -> 5, 12 -> 6, 13..16 -> 7, 17 -> 8,
18/19 -> 0, 20 -> 2. AddXP (DS1 0x6b817..0x6b8ff): party-split XP,
clamps at 2,000,000,000, maintains charrec+4 >= charrec+0.

## 4. Ability-score tables

Cluster DS1 DGROUP 0x7a8..0x843 (file 0x49108..0x491a3); DS2 DGROUP
0x818..0x8b3 (file 0x4d818..). Six near-identical getters index them (DS1
0x5ea2d..0x5eaaa; DS2 0x1d2e0..0x1d3a0): each calls the stat helper (DS1
0x5ec1c) with stat mode (0=STR 1=DEX 2=CON 3=INT 4=WIS 5=CHA), then reads
`table[disp + stat]` with NO bounds check.

| table | disp DS1/DS2 | values (stat -> adj) |
|---|---|---|
| STR damage | 0x7a8/0x818 | 3-7: -1; 8-15: 0; 16-17: +1; 18: +4; 19: +7; 20: +8; 21: +9; 22: +10; 23: +11; 24: +12; 25: +14 |
| STR hit | 0x7c2/0x832 | 3: -3; 4-5: -2; 6-7: -1; 8-16: 0; 17: +1; 18: +2; 19-20: +3; 21-22: +4; 23: +5; 24: +6; 25: +7 |
| DEX missile | 0x7dc/0x84c | 3: -3; 4: -2; 5: -1; 6-15: 0; 16: +1; 17-18: +2; 19-20: +3; 21-22: +4; 23: +4; 24-25: +5 |
| DEX AC | 0x7f6/0x866 | 1: +5; 2: +5; 3: +4; 4: +3; 5: +2; 6: +1; 7-14: 0; 15: -1; 16: -2; 17: -3; 18-20: -4; 21-23: -5; 24-25: -6 |
| CON (mode 2) | 0x810/0x880 | 1: -2; 2: -1; 3-18: 0; 19-20: +1; 21-22: +2; 23-24: +3; 25: +4 |
| WIS (mode 4) | 0x82a/0x89a | 1: -6; 2: -4; 3: -3; 4: -2; 5-7: -1; 8-14: 0; 15: +1; 16: +2; 17: +3; 18-25: +4 |

Consequences: (a) the getters are unclamped, so a stat of 99 reads into the
NEIGHBORING table (STR 99 damage lands in the DEX AC table at -3..-5): this
corrects engine-quirks.md's "+0 above 25" reading, and the observed
"1 damage with 1d1" is the damage floor, not a zero lookup. (b) The mode-2
CON table is near-zero in the playable range because CON's real effect is
the +0x38 floor (section 1), not an additive bonus. (c) The mode-4
(WIS-by-stat-order) table is shaped exactly like a warrior CON-HP column;
its consumer beyond the getter was not located. Stat order at the CHARREC
level is confirmed (level-up reads charrec+29 as CON), so mode 4 = WIS by
that order; whether the engine truly grants WIS a CON-style bonus (a
psionic-defense reading fits Dark Sun) is a one-shot runtime check.

Also present, no consumer found: u16 power-of-two arrays at DGROUP 0x718/
0x730 (class-bit progressions) and 26 (min,max) u16 pairs at 0x740..0x7a8.

## 5. Level-1 / starting HP

Creation sets level 3 (or 2/2 dual) and XP from the table (section 3). The
base-HP helper is RESOLVED (wave 2): ovr46 stub 2, entry 0x260, file
0x874b0:

```
base_hp(si):
  A  = sum of the 3 signed level bytes at charrec+0x24
  B  = sum of the 3 signed high_level bytes at +0x3f
  hp = (A * charrec[si].high_HP(+0xa)) / B
  hp /= class_count(si)            ; race==1 -> 1; else count of nonzero real_class[3]
  hp += additive(si)               ; the shared helper at 0x8757c: the +0x52 PSP-formula shape
  return max(hp, B)
```

The multiclass HP division is explicit. The per-level gain rule stands:
group die rolled once per level, max(roll, CON floor), flat
post_level_gain after the row's last_rolling_level. The recompute chain
0x628:{0x2a, 0x39, 0x3e, 0x4d} = base-HP, PSP, THAC0, saves in order.

## 6. Open items

1. ~~Save-roll consumption~~ RESOLVED (section 5 note + spell-effects.md 4):
   descriptor byte, not the five stored saves.
2. ~~DS2 XP helper~~ RESOLVED (section 3): DATA:1000 + the ovr16 lookup.
3. ~~Rules-block +0x30~~ RESOLVED (section 1): legal-item entries 12..18.
4. ~~Exact DS1 class-id -> name binding~~ RESOLVED (wave 3,
   chargen-flow.md 0): DGROUP 0x11dc is the display-NAME table indexed
   [real_class + 8]; the x4 band runs are the sphere variants and the
   first 9 entries are condition strings.
5. ~~Level-9 gate bypass~~ RESOLVED (wave 3, chargen-flow.md 3): no
   bypass exists; the DS2 cap is level 15 plus an XP bank cap at
   T[row][level+3].
6. The mode-4 (WIS) table's true consumer.
7. ~~DATA:1002's consumer~~ strong negative (wave 3, chargen-flow.md 6):
   no instruction pushes id 1002; resident-cache or dead; its contents
   key SPIN ids {1, 50..69} to u32 values.
8. Pool placeholder semantics across builds (cosmetic; noted so nobody
   re-derives address math against them). Note: the PSP citation in
   section 1 ("DS1 0x875a8..0x875dc") lands inside the shared additive
   helper at 0x8757c..0x875de, which both the PSP recompute and the
   base-HP additive use.
