# Object database formats: RDFF records, OJFF, items, spells, encounters

The verified schema reference for the games' object data, the
substrate of the bestiary and item/spell catalogues
(`bestiary.md`, `item-catalogue.md`, `spell-catalogue.md`, all
machine-generated). Established 2026-09-16 in a four-agent
extraction wave; every layout below was read off the shipped
bytes of both canonical files, with anchors cross-checked
against played saves, the in-install SSI clue books (facts
only), and the reference clones. Nothing here is guessed
silently: each field carries a confidence mark.

Confidence marks:

- **VB**: verified on bytes (corpus-wide invariant or
  byte-exact anchor match).
- **XC**: externally corroborated (clue book stat, AD&D 2e
  stat, or the played-save layouts of `file-formats.md`
  3.3/3.4).
- **LA**: libgff authority (`libgff/include/gff/*.h` struct
  names; positions measured, names taken on faith).
- **H**: hypothesis, explicitly unresolved.

Files (canonical installs):

- DS1: `.games/ds1/SEGOBJEX.GFF` (objects), `.games/ds1/GPLDATA.GFF`
  (item base stats + name pool), `.games/ds1/RESOURCE.GFF`
  (spell text, MONR), `.games/ds1/DSUN.EXE` (spell power table).
- DS2: `.games/ds2/OBJEX.GFF` (objects incl. inline item
  stat blocks), `.games/ds2/RESOURCE.GFF` (item names, spell
  text, spell power table, MONR).

## 1. The RDFF chain model

Both games' object databases store every object as one `RDFF`
chunk: a chain of blocks. Each block is a 10-byte header
followed by `len` payload bytes; the chain ends at a header
with `load_action = -1` (the walk consumes the chunk
byte-exactly in 1,046/1,046 DS1 and 1,642/1,643 DS2 chunks;
the one DS2 exception, id 500, carries stale bytes of a
deleted NPC after its terminator: in-place-writer residue).

Block header (10 bytes, identical in both games):

| Off | Type | Field | Notes | Conf |
|---:|---|---|---|---|
| 0 | i8 | load_action | 1 OBJECT, 2 CONTAINER (container owns following item), 3 DATA, 4 NEXT (next inventory entry), -1 END | VB + LA |
| 1 | u8 | blocknum | 0 on head records; DS1 pack entries step 2,5,8,11,... (+3 each) | VB, semantics H |
| 2 | i16 | type | 1 item, 2 combat, 3 charrec (DS2) / marker (DS1), 4 charrec (DS1) / item template (DS2), 5 mini | VB |
| 4 | i16 | index | sprite/BMP ref on OBJECT records; charrec/template row id on DATA records | VB |
| 6 | i16 | from | 71/79 (DS1 heads), 15/5 (DS2), small values on markers; destination-slot hypothesis | VB values, semantics H |
| 8 | i16 | len | payload length | VB |

Observed chain shapes:

| Shape (la/type/len) | Meaning | Count |
|---|---|---:|
| DS1 `(1,2,58)+(3,4,71)` [+ item chains] | creature | 291 |
| DS2 `(1,2,49)+(3,3,66)` [+ containers] | creature | 352 |
| DS1 `(1,1,21)+(3,5,0)+(3,3,0)` | item or scenery object | 664+ |
| DS2 `(1,1,23)+(3,4,15)` | item or scenery object | 1,216 |
| DS2 `(1,5,23)` | mini (named non-combat entity) | 58 |

The type codes swap meaning for DATA blocks between games:
charrec is type 4 in DS1 and type 3 in DS2; the DS2-only 15-byte
item template is type 4. Items, creatures, doors, and scenery
share one id space per game (DS1: 5..32003; DS2: 1..32003); a
block's own object id is stored negated in its payload (see
below). GPL `NAME(-N)` operands are these ids.

DS1's 8900..8913 combat-id band holds mostly empty records;
8901 carries a combat block with no character block (empty
name and hp) and is excluded from the generated catalogue as a
stub (290 decoded + 1 stub = 291 combat records).

The roadmap's 2026-09-05 note "every RDFF record carries its
own id negated as i16 at offset 14" is corrected here: the
negated id sits in the combat payload at +6 (chunk offset +16
after the 10-byte header), the item payload at +0, the mini
payload at +0. Verified 291/291 (DS1 combat), 352/352 (DS2
combat), 755/755 + 1,233/1,233 (items), 58/58 (minis). The
"+14" figure reproduces nothing corpus-wide.

## 2. Creature records

A creature is a combat block plus a charrec block; the combat
block's `char_index` links to the charrec's header `index`
(290/290 DS1, 352/352 DS2). These are the same records the
party uses: DS1's layout matches the SAVE/5 + SAVE/6 pair and
DS2's matches CHARSAVE CHAR chunks (`file-formats.md` 3.3-3.5),
which is the engine-reuse confirmation that a bestiary can be
read straight from the shipped data.

### 2.1 DS1 combat block (type 2, 58 bytes)

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0 | i16 | hp (current) | VB (== charrec base_hp in 205/290 pairs) |
| 2 | i16 | psp (current) | VB+LA |
| 4 | i16 | char_index (into charrec blocks) | VB |
| 6 | i16 | own id, negated | VB 291/291 |
| 8/10/12 | i16 x3 | ready item / weapon / pack (0 = none in DS1) | LA+VB |
| 14..21 | u8[8] | data_block (all zero on disk; runtime-filled) | LA |
| 22 | u8 | special_attack enum (0,4,5,12,13,14,16,17,19,23,24,25,31 observed) | LA + XC-qualitative |
| 23 | u8 | special_defense (0 in all 291) | LA |
| 24..25 | i16 | icon (0 in 273/291) | LA |
| 26 | i8 | AC (current) | VB+XC (Bulette -2) |
| 27 | u8 | move (current) | VB (Silt Runner 48) |
| 28 | u8 | status (1 = active, 276/291) | VB |
| 29 | u8 | allegiance (1 PC, 2, 4) | VB, enum H |
| 30 | u8 | data (2 dominant) | LA |
| 31 | i8 | THAC0 | VB+XC (tracks level inversely) |
| 32 | u8 | priority (5/6/7) | LA |
| 33 | u8 | flags (0x20 in 255/291) | LA |
| 34..39 | u8[6] | stats STR DEX CON INT WIS CHA | VB (Cilla == played save) |
| 40..55 | char[16] | name, NUL-padded (14 + 2 spill; tail bytes past NUL can hold stale bytes) | VB |

### 2.2 DS2 combat block (type 2, 49 bytes)

Same head as DS1 (offsets 0..13 identical; the null marker for
ready/weapon/pack is 9999; PCs in CHARSAVE carry `0x8000|n` at
+6 instead of -id). Then:

| Off | Type | Field | Conf |
|---:|---|---|---|
| 14..15 | u16 | unresolved (0/15/12/14 pattern; special-attack candidate) | H |
| 16..17 | u16 | data remnant (0 in 336/352) | H |
| 18 | i8 | AC (current) | VB+XC (drakes -2/-4/-3 == charrec base) |
| 19 | u8 | move (current) | VB |
| 20 | u8 | status (1 in 347/352) | VB |
| 21 | u8 | allegiance (0..7) | VB, enum H |
| 22 | u8 | special_attack candidate | H |
| 23 | u8 | special_defense candidate (6 in 307/352) | H |
| 24 | u8 | flags (0/0x20, mirrors DS1 +33) | VB |
| 25..30 | u8[6] | stats STR DEX CON INT WIS CHA | VB (== charrec stats, all sampled pairs) |
| 31..32 | u16 | constant 4 in 335/352; unknown | H |
| 33..48 | char[16] | name, NUL-terminated (352/352) | VB |

There is no THAC0 byte in DS2's block; the engine derives it
(runtime derivation from level is the standing hypothesis, one
EXE read from settled: the `fight` handler DS2 0xd70c).

### 2.3 DS1 charrec block (type 4, 71 bytes)

Matches libgff `ds_character_t` minus its trailing palette
byte, and matches `file-formats.md` 3.4 (SAVE/6).

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0 | u32 | XP value | XC-partial (several filler-1000 rows) |
| 4 | u32 | high/next XP | LA |
| 8 | u16 | base HP | VB (== combat hp) |
| 10 | u16 | high HP | VB |
| 12 | u16 | base PSP | VB |
| 14 | u16 | constant-band (2000 x198, 1500 x45, 1000/2500/8000/0) | LA names it "id"; NOT the object id; semantics open |
| 16 | i16 | negative; an existing RDFF id in 224/289 cases (inter-object link: corpse item? spawn template?) | H |
| 18 | u16 | legal_class bitmask (0x20 dominant) | LA |
| 20..23 | u8[4] | data2 (0) | LA |
| 24 | u8 | race (PCs 1-8; monsters 9/10/12/14 category codes) | LA, monster codes H |
| 25 | u8 | gender | LA |
| 26 | u8 | alignment (0..9; enum open; Vrock 9, Slaad 8, Zombie 5) | LA + H |
| 27..32 | u8[6] | stats STR DEX CON INT WIS CHA | VB |
| 33..35 | u8[3] | real_class[3] | VB |
| 36..38 | u8[3] | level[3]; level[0] is the monster's hit dice | VB+XC |
| 39 | i8 | base AC | VB+XC (Bulette -2) |
| 40 | u8 | base move | VB |
| 41 | u8 | magic resistance % | XC (Blue Slaad 40, So-ut 25, Vrock 70: clue book exact) |
| 42 | u8 | num_blows | LA |
| 43..45 | u8[3] | attacks per slot, in half-rounds (value/2 = attacks/round) | XC (3 corroborations; runtime /2 unconfirmed) |
| 46..48 | u8[3] | damage dice per slot | XC |
| 49..51 | u8[3] | damage sides per slot | XC |
| 52..54 | u8[3] | damage bonus per slot | XC |
| 55..59 | u8[5] | saving throws: paralyzation, wand, petrification, breath, spell | LA+VB |
| 60 | u8 | allegiance (== combat +29 in 249/290) | VB |
| 61 | u8 | size | LA |
| 62 | u8 | spell_group | LA |
| 63..65 | u8[3] | high_level[3] | LA |
| 66..67 | u16 | sound_fx | LA |
| 68..69 | u16 | attack_sound | LA |
| 70 | u8 | psi_group | LA |

### 2.4 DS2 charrec block (type 3, 66 bytes)

The DS1 layout with 5 bytes removed before the stats. Offsets
0..13 are identical to DS1 (XP, next XP, base HP, high HP, base
PSP). Then:

| Off | Type | Field | Conf |
|---:|---|---|---|
| 14 | u16 | tagged index: `0x80xx` PCs, `0xe4xx` disk records (byte 15 = 0xE4 constant in 352/352) | H |
| 16 | u16 | legal_class bitmask (same 0x20-dominant distribution as DS1 +18) | LA-positional |
| 18 | u8 | race | H positional |
| 19 | u8 | gender | H positional |
| 20 | u8 | alignment | H positional |
| 21..26 | u8[6] | stats STR DEX CON INT WIS CHA | VB (== combat stats) |
| 27..29 | u8[3] | real_class[3] | XC |
| 30..32 | u8[3] | level[3]; level[0] = hit dice (Umber Hulk 8, Mindflayer 8, Lord Warrior 15) | VB+XC |
| 33 | i8 | base AC | XC (Mindflayer 5, Umber Hulk 2) |
| 34 | u8 | base move | XC |
| 35 | u8 | magic resistance % | XC (Mindflayer 90: clue book exact) |
| 36 | u8 | num_blows | XC-shape |
| 37..39 | u8[3] | attacks, half-rounds | XC (Mindflayer 8 = 4 tentacles) |
| 40..42 / 43..45 / 46..48 | u8[3] x3 | damage dice / sides / bonus | XC |
| 49..53 | u8[5] | saving throws (same order as DS1) | XC |
| 54 | u8 | allegiance | H |
| 55..65 | u8[11] | tail: size, spell_group, high_level, sound slots | H positional |

### 2.5 DS2 mini block (type 5, 23 bytes)

Named non-combat entities: id i16 negated +0, next u16 +2
(9999 = none), priority u8 +4, name char[16] +5..20, flags +21,
data +22. Matches libgff `mini_t` exactly; verified ("Helmine"
id 1, "Miner" id 500). DS1 type-5 DATA blocks are 0-length
markers; DS1 minis do not exist.

## 3. OJFF (placement/graphics, 16 bytes, both games)

One OJFF per object id (2,775 DS1 / 4,479 DS2; a superset of
the RDFF id space). ETAB placements in the region files
reference these ids (negated). Layout (`gff_ojff_t`):

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0..1 | u16 | flags (DS1: 0 or 0x10; DS2: 0x10 / 0x02 / 0; bit names from libgff OBJECT_*, semantics H) | VB values |
| 2..3 | i16 | xoffset (0..63) | VB |
| 4..5 | i16 | yoffset (0..63; 3 DS2 negatives) | VB |
| 6..7 | u16 | xpos: little-endian in DS1, **byte-swapped (big-endian) in DS2** | VB empirical (DS2 max_y 1945 only under BE; reason unknown) |
| 8..9 | u16 | ypos (same per-game byte order) | VB |
| 10 | i8 | zpos (0..64) | VB |
| 11 | u8 | object_index (0 in all 2,775 DS1) | VB |
| 12..13 | u16 | bmp_id (in the file's BMP id set, or 0) | VB 100% both games |
| 14..15 | u16 | script_id (SCMD id, or 0) | VB 100% both games |

## 4. Items

### 4.1 DS1 item instance (type 1 payload, 21 bytes)

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0 | i16 | object id, negated (== OJFF id) | VB 755/755 |
| 2 | u16 | quantity | VB |
| 4 | i16 | next (runtime link; 0 on disk) | VB |
| 6 | u16 | value in ceramic (9999 and 65000 = quest/priceless sentinels) | VB |
| 8 | i16 | pack_index (0 on disk) | VB |
| 10 | i16 | item_index into the IT1R base-stat table (see 4.3); EXE stride `imul ax,20` | VB |
| 12 | i16 | icon (rarely nonzero) | H |
| 14 | u8 | charges | VB+XC (shop wands match the clue book treasure guide) |
| 15 | u8 | quantity mirror | VB |
| 16 | u8 | special class (4 mundane, 5 container/wand, 6 magic/shop-stock tendency) | VB pattern, semantics partial |
| 17 | u8 | slot (0xFF = unequipped) | VB |
| 18 | u8 | name index into the NAME pool (GPLDATA.GFF NAME id 1, 322 x 25-byte records) | VB (hundreds of coherent joins) |
| 19 | i8 | bonus (39 on bags only; capacity?) | H |
| 20 | u8 | trailing (0) | VB |

### 4.2 DS2 item instance (type 1 payload, 23 bytes)

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0 | i16 | object id, negated | VB 1,233/1,233 |
| 2 | u16 | quantity | VB |
| 4 | u16 | 9999 sentinel in all observed (max charges? "none"?) | H |
| 6 | u16 | value in ceramic (9999/65000 sentinels; 20000/20800 = +2/+3 enchant tiers, matching the clue book) | VB |
| 8 | u16 | 9999 sentinel (pack_index per libgff) | H |
| 10 | i16 | stats index: matches the header `index` of the chunk's (la=3, type=4, 15-byte) template block | VB 1,931/1,931 |
| 12 | i16 | 0 (icon per libgff) | H |
| 14 | u16 | charges-ish (0..9 observed; 9 on Life Stealer) | H |
| 16 | u16 | quantity/charges mirror (equals quantity on named weapons) | partial |
| 18 | u8 | special class (same 4/5/6 scheme as DS1) | VB pattern |
| 19 | u8 | slot (0xFF = unequipped) | VB pattern |
| 20 | u8 | name index into RESOURCE.GFF TEXT id 1000 (a CRLF-separated pool, 1-based) | VB (100+ verified joins) |
| 21 | u8 | 0 | H |
| 22 | u8 | flags (0..3) | H |

### 4.3 Base-stat tables

DS1: `GPLDATA.GFF` chunk `IT1R` id 1 (the corpus's only IT1R),
115 records x 20 bytes. The EXE caches it by pushing FOURCC
`IT1R` res id 1 and `NAME` id 1 (loader at DS1 EXE file
0x565f5ff.; libgff `gff_manager_ds1_read_name` agrees).

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0 | u8 | weapon/armor class bits (bit0 melee, 1 missile, 2 shield, 3 use-ammo, 4 thrown) | VB+LA |
| 1 | u8 | 0 always (alignment per libgff) | VB |
| 2 | u16 | damage type bits (8 blunt, 0x10 slash, 0x20 pierce; magic weapons OR extra bits) | VB |
| 4 | u8 | weight | VB+XC |
| 5 | u8 | 0 | VB |
| 7 | u8 | base_hp (0 everywhere in DS1) | VB |
| 8 | u8 | material (0..5, 64, 69, 80, 96, 128, 131..133; bit7 = metal/jewel variant flag?) | VB, semantics H |
| 9 | u8 | placement/slot (1 chest, 3 arm, 5 hand/shield, 6 head, 7 neck, 8 cloak, 9 finger, 10 legs, 11 ammo, 12 missile weapon) | VB |
| 10 | u8 | range (launcher and ammo rows use different scales) | VB, units H |
| 11 | u8 | attacks (sling 2, bow 4) | VB |
| 12 | u8 | die sides | VB+XC |
| 13 | u8 | dice count | VB+XC |
| 14 | i8 | damage/to-hit bonus (matches the clue book's "+N to hit & damage") | VB+XC |
| 15 | u8 | flags (0x80 armor, 0x40 two-handed, 0x02 missile; doors/chests reuse) | VB |
| 16 | u16 | legal_class bitmask (bit-to-class map open) | VB |
| 18 | i8 | base AC (armor rows; doors 10) | VB+XC |
| 19 | u8 | 0 | VB |

DS2: no IT1R; the 15-byte (la=3, type=4) template blocks inside
OBJEX.GFF carry the base stats; only 82 distinct payloads exist
for 1,216 uses (the shared-property pattern; the top template
row is the six mines props'). Layout:

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0 | u8 | weapon class bits (same scheme) | VB (cross-game joins: Quarterstaff/Longsword/Cahulaks identical to DS1 rows) |
| 1 | u8 | damage type bits | VB |
| 2 | u8 | weight? | H |
| 3 | u8 | unresolved (5/10/50/80/250) | H |
| 4 | u8 | material | VB (import mapping preserves it) |
| 5 | u8 | placement/slot | VB |
| 6/7 | u8 x2 | range / attacks pair, unresolved split | H |
| 8 | u8 | die sides | VB+XC |
| 9 | u8 | dice count | VB+XC |
| 10 | i8 | damage/to-hit bonus | VB+XC |
| 11 | u8 | flags | VB |
| 12..13 | u16 | legal_class bitmask | VB |
| 14 | i8 | base AC | VB+XC |

### 4.4 DS1-to-DS2 import table

`.games/ds2/ITEMS.BIN` (936 bytes) is 234 (u16, u16) pairs
mapping DS1 item ids to DS2 successors for party import
(1010 Chatkcha -> 704 Chatchka, 1014 -> 603 Longsword, material
byte preserved). Not referenced by DSUN.EXE strings; loaded by
the import screen.

## 5. Names

- Creatures: the name lives inside the combat block itself
  (DS1 +40, DS2 +33). Verified end-to-end on all 13 mines
  tport anchors (Melody, Wren, Mug, the Miners, Zeegrat,
  Winchester, Umber Hulk, Mindflayer, Int.Devourer).
- DS1 items: `GPLDATA.GFF` NAME id 1, 322 x 25-byte
  NUL-padded records; the item's +18 byte indexes the pool.
- DS2 items: `RESOURCE.GFF` TEXT id 1000, one CRLF-separated
  pool of 255 strings; the item's +20 byte indexes it 1-based.
- DS2 minis: inline 16-byte name.
- No object names are hardcoded in either EXE beyond the
  chunk FOURCCs and the 9999 sentinel.

## 6. Spells

Spell text: `SPIN` chunks in each game's RESOURCE.GFF
(DS1: 180 chunks, ids 1..172 + 249..255 stat powers + 1000
TURN UNDEAD; DS2: 269 chunks, ids 1..269). Text is raw ASCII
`NAME:  description`, CRLF line breaks, no length prefix.
The DS2 1.10 fill (ids 93-115, 232-235, names only) matches
the roadmap's 1.02-delta finding. SPIN 93/103 (DS2) contain
SSI's leaked build command naming the per-spell `.spn` source
files; SPIN 95's text is a stale CHARM PERSON copy while the
engine table says MASS CHARM (the engine table is
authoritative).

Mechanical stats live in engine power tables, NOT in GPL
scripts (casting is engine-native; the DSO symbol inventory
names CastSpell/DoMagicAndPsi). Both tables share a 32-byte
record; the per-record layout (field order and damage formula
from `.dsoageofheroes/soloscuro-archive` `extract.c`, offsets
measured here):

```
+0  u8  data0          (low 2 bits ai-type, high 6 repeat count)
+1  i16 range          (feet; -2 touch, -1 self)
+3  u8  range_per_level
+4  u8  duration packed (low nibble dice, high nibble sides)
+5  u16 dur_per_level
+7  i16 dur_multiplier (0 instant, -9999 indefinite, 60 rounds/level, ...)
+9  u16 area (feet)
+11 u8  area_per_level
+12 u8  target (0 none,1 single,2 line,3 ally,4 enemy,5 anyone,6 cone,7 self,8 two)
+13 i16 cast FX ref
+15 u8  cast_sound
+16 i8  thrown
+17 u16 special bitmask (1 summon, 2 enchant, 4 charm, 8 illusion,
       0x10 wis-save, 0x20 mind/wis roll, 0x40 roll-to-hit, 0x80 gaze,
       0x100 fear, 0x400..0x2000 element-immune, 0x4000 is-attack)
+19 u8  thrown_sound
+20 i16 hit
+22 u8  hit_sound
+23 i8  aoe_id
+24 u8  data1
+25 i8  effect (engine effect-handler id; jump table unmapped)
+26 u16 effect_type (damage-type bitmask: 1 poison, 2 fire, 4 cold,
       8 blunt, 0x10 cutting, 0x20 piercing, 0x40 acid, 0x80 electric,
       0x100 draining, 0x200 magic, 0x400 mental, 0x800 death, ...)
+28 u32 damage packed:
       byte0 plus(5) | dice_plus(3); byte1 div(3) | dice(5);
       byte2 sides(4) | level(4); byte3 savable(1) | save_mod(4s)
             | save_type(3: 1 poison, 2 wands, 3 petr, 4 breath,
                        5 spells, 6 paral, 7 death, 8 magic)
```

- DS2 table: 320 records x 73 bytes (32 stat + 32 long name +
  9 short name) at file offset 0x120E8 of RESOURCE.GFF.
  Records 0..114 wizard, 115..234 cleric, 235..268 psionics,
  269..319 innate monster powers. Level boundaries are the
  engine's own arrays: `aFirstWizSpellAtLevel` at DS2 EXE
  DGROUP 0x656 (file 0x4D656), `aFirstClSpellAtLevel` at
  DGROUP 0x661.
- DS1 table: 196 records x 32 bytes (no names appended) at
  file offset 0x41F70 of DSUN.EXE. Record index = SPIN id - 1
  for ids 1..172; 172..178 are the stat powers (SPIN 249..255);
  179..195 innate. Level boundaries independently confirmed by
  the 138 x 7-byte per-spell record array at DS1 EXE 0x4512C
  (byte 0 = level), fingerprint-matched uniquely.
- Signature anchors: record 0 name ARMOR (DS2), BLESS at DS1
  record 69 / DS2 record 115, DETONATE records byte-identical
  across games except sound ids, MONSTER SUMMONING I via
  extract.c's `ds1powers[35]`.
- PSP costs: the DSO 3-byte-stride table (mdark.bin 0x10AA59)
  covers the shared 34-power psionic list; treat as prior-art
  context, not DS1/DS2 ground truth.

Known-spells-per-character (save side, for completeness):
DS1 SPST = 138 bytes, one byte per spell id 1..138, 1 = known.
DS2 SPST = LSB-first bitmask, bit (id-1). PSST = 34 bytes, one
per psionic power (nonzero = known, bit 0 masked). PSIN: DS1
7 discipline bytes; DS2 1 bitmask byte.

## 7. MONR (random encounters)

`RESOURCE.GFF` MONR id 1 in each game; N x 42-byte records:
`i16 region_id` + 10 x (`i16 creature_id`, `i16 weight`).
DS1's is live encounter data (29 region rows; every referenced
id resolves to a DS1 combat record). DS2's is stale DS1
carryover: it lists DS1 region ids and references creature ids
absent from DS2's OBJEX; DS2 encounters are GPL-scripted. The
second i16 behaves like a frequency weight (libgff calls it
"level"; Rampager carries 96 at 14 HD, so it is not hit dice).

## 8. Provenance

Established 2026-09-16 by four read-only extraction agents
(schemas; items; spells; creatures) working from the canonical
installs, cross-checked against `.dsoageofheroes/libgff` (cite
`rdff.h`, `object.h`, `item.h`, `common.h`), soloscuro-archive's
`extract.c`, the played-save layouts in `file-formats.md`, and
the SSI clue books shipped in the install dirs (facts only).
Corrections recorded here supersede earlier prose in the
roadmap's historical notes (the "+14" id anchor; the
DS2-scoping of the SPIN 1.10 fills). Regenerate the catalogues
with `tools/gff-edit/scripts/extract-catalogue.py`.
