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
| 22 | u8 | special_attack: an ENUM index (not a bitfield), 33 distinct values corpus-wide; candidate ability map in the wave-2 ledger (poison 1/5/11/26, psionics 23/30, paralytic gaze 14, corrosive 12, chilling touch 13, spines 20, entangle 22, fire breath 9, sting 26 ...) | enum verdict high, per-value map partial |
| 23 | u8 | special_defense (0 in all 291; defenses live in magic_res and the item/equipment layer) | LA |
| 24..25 | i16 | icon (0 in 273/291) | LA |
| 26 | i8 | AC (current) | VB+XC (Bulette -2) |
| 27 | u8 | move (current) | VB (Silt Runner 48) |
| 28 | u8 | status (1 = active, 276/291) | VB |
| 29 | u8 | allegiance enum: 1 = party (PC templates + joinables), 2 = hostile placement, 4 = neutral/friendly default | VB + wave-2 census |
| 30 | u8 | data (2 dominant) | LA |
| 31 | i8 | THAC0 | VB+XC (tracks level inversely; DS1 Manual anchors: Dune Reaper 13, Mountain Stalker 11, Sand Howler 17) |
| 32 | u8 | priority (5/6/7); initiative-like: the per-tick act test compares it against a d20 (0..19), higher acts more often (combat-flow.md 4) | LA + instruction |
| 33 | u8 | flags (0x20 in 255/291) | LA |
| 34..39 | u8[6] | stats STR DEX CON INT WIS CHA | VB (Cilla == played save) |
| 40..55 | char[16] | name, NUL-padded (14 + 2 spill; tail bytes past NUL can hold stale bytes) | VB |

### 2.2 DS2 combat block (type 2, 49 bytes)

Same head as DS1 (offsets 0..13 identical; the null marker for
ready/weapon/pack is 9999; PCs in CHARSAVE carry `0x8000|n` at
+6 instead of -id). Then:

| Off | Type | Field | Conf |
|---:|---|---|---|
| 14..15 | u16 | special-attack candidate: low byte = index into the DS2 special-attack scheme, high byte = secondary parameter (1..16, present on multi-ability monsters); DS2 anchors: Mindflayers 12, Verini spit 15, Giant Skeleton 17, Umber Hulk 19, fear 8 | H-leaning (book-correlated rows) |
| 16..17 | u16 | data remnant (0 in 336/352) | H |
| 18 | i8 | AC (current) | VB+XC (drakes -2/-4/-3 == charrec base) |
| 19 | u8 | move (current) | VB |
| 20 | u8 | status (1 in 347/352) | VB |
| 21 | u8 | allegiance enum: 0 = party, 7 = hostile, 4 = friendly/neutral, 1 = placed-neutral (city faction / hostile-later), 5 = mercenaries/wild attackables; 3 and 6 singletons | VB + wave-2 census |
| 22 | i8 | **THAC0** (wave 2: the engine reads it at DS2 EXE file 0x5c6e9: `imul ax,ax,0x31; les bx,[0x19c9]; mov al,[es:bx+0x16]`, the byte-for-byte mirror of DS1's +31 read at 0x58113; warrior PCs carry 21 - level; Umber Hulk/Mindflayer 11 = the 2e Manual value; Tarrasque stores -5) | VB (instruction) + XC |
| 23 | u8 | priority (DS1's +32 byte relocated: same {5,6,7} domain, 6-dominant; 7 = PC templates, 5 = big monsters); same per-tick act-test role as DS1 (combat-flow.md 4) | VB distribution + instruction |
| 24 | u8 | flags (0/0x20, mirrors DS1 +33) | VB |
| 25..30 | u8[6] | stats STR DEX CON INT WIS CHA | VB (== charrec stats, all sampled pairs) |
| 31..32 | u16 | constant 4 in 335/352; unknown | H |
| 33..48 | char[16] | name, NUL-terminated (352/352) | VB |

The earlier "no THAC0 byte; derived from level" hypothesis is
refuted (wave 2): DS2 kept DS1's stored-byte design and moved it
to +22. THAC0 = 21 - HD holds for 193/347 monster rows; classed
NPCs follow class progressions (rogue L12 rows carry 15, mage L9
rows 18) and named monsters are hand-tuned.

### 2.3 DS1 charrec block (type 4, 71 bytes)

Matches libgff `ds_character_t` minus its trailing palette
byte, and matches `file-formats.md` 3.4 (SAVE/6).

| Off | Type | Field | Conf |
|---:|---|---|---|
| 0 | u32 | XP value | XC-partial (several filler-1000 rows); NEVER read on the combat XP-award path |
| 4 | u32 | high/next XP for PCs; for MONSTER rows this is the dword the engine awards on death, divided by party count (combat-flow.md 8; DS1 0x592c2, DS2 0x5d105..0x5d11c) | LA + instruction |
| 8 | u16 | base HP | VB (== combat hp) |
| 10 | u16 | high HP | VB |
| 12 | u16 | base PSP | VB |
| 14 | u16 | constant-band (2000 x198, 1500 x45, 1000/2500/8000/0) | LA names it "id"; NOT the object id; semantics open |
| 16 | i16 | negative; an existing RDFF id in 224/289 cases (inter-object link: corpse item? spawn template?) | H |
| 18 | u16 | legal_class bitmask (0x20 dominant) | LA |
| 20..23 | u8[4] | data2 (0) | LA |
| 24 | u8 | race (PCs 1-8; monsters 9/10/12/14 category codes) | LA, monster codes H |
| 25 | u8 | gender | LA |
| 26 | u8 | alignment, enum confirmed (see 2.6) | XC + wave-2 instruction evidence |
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
| 55..59 | u8[5] | saving throws: paralyzation, wand, petrification, breath, spell; WRITE-ONLY at runtime outside the level-up recompute (wave 2 read scan: no consumer in normal play) | LA+VB |
| 60 | u8 | allegiance (== combat +29 in 249/290) | VB |
| 61 | u8 | CORRECTED (wave 2, spell-effects.md 4): the DEFAULT SAVE DESCRIPTOR read by the in-combat effect chains (DS1 ovr22 local 0xa44: category = val & 7, count = val / 8), previously labeled "size" | LA + instruction |
| 62 | u8 | spell_group | LA |
| 63..65 | u8[3] | high_level[3] | LA |
| 66..67 | u16 | sound_fx | LA |
| 68..69 | u16 | attack_sound | LA |
| 70 | u8 | psi_group | LA |

### 2.4 DS2 charrec block (type 3, 66 bytes)

The DS1 layout with 6 bytes removed before the stats (the 2-byte
negative link and the 4-byte data2; every later field shifts by
6). Offsets 0..13 are identical to DS1 (XP, next XP, base HP,
high HP, base PSP). Then:

| Off | Type | Field | Conf |
|---:|---|---|---|
| 14 | u16 | tagged index: `0x80xx` PCs, `0xe4xx` disk records (byte 15 = 0xE4 constant in 352/352) | H |
| 16..17 | u16 | legal_class bitmask (the engine's class-anim selector tests 0x20/0x10/0x40/0x200/0xf/0x400/0x100/0x80 at DS2 EXE 0x6ef84; verified pairs: class 9 = 0x2000, 10 = 0x4000, 11 = 0x8000, 12 = 0x1, fighter = 0x20, thief = 0x400) | VB (instruction + data) |
| 18 | u8 | race (1 = human, 8 = thri-kreen with an engine special-case at 0x6ef94, 12 = generic monster category, 16 = mindflayer; 2..7 = the other PC races by elimination) | VB (instruction + data) |
| 19 | u8 | gender (1 male, 2 female, 0 none; selector at 0x8fef0) | VB (instruction + data) |
| 20 | u8 | alignment, enum confirmed (see 2.6; protection-from-alignment grid read at 0x83775) | VB (instruction) |
| 21..26 | u8[6] | stats STR DEX CON INT WIS CHA | VB (== combat stats) |
| 27..29 | u8[3] | real_class[3] | XC |
| 30..32 | u8[3] | level[3]; level[0] = hit dice (Umber Hulk 8, Mindflayer 8, Lord Warrior 15) | VB+XC |
| 33 | i8 | base AC | XC (Mindflayer 5, Umber Hulk 2) |
| 34 | u8 | base move | XC |
| 35 | u8 | magic resistance % | XC (Mindflayer 90: clue book exact) |
| 36 | u8 | num_blows | XC-shape |
| 37..39 | u8[3] | attacks, half-rounds | XC (Mindflayer 8 = 4 tentacles) |
| 40..42 / 43..45 / 46..48 | u8[3] x3 | damage dice / sides / bonus | XC |
| 49..53 | u8[5] | saving throws (same order as DS1); write-only at runtime outside level-up (wave 2) | XC |
| 54 | u8 | allegiance | H |
| 55 | u8 | CORRECTED (wave 2): the DEFAULT SAVE DESCRIPTOR (DS2 ovr19 local 0xc00: category = val & 0xf, count = val / 0x10), not "size" | H + instruction |
| 56..65 | u8[10] | tail: spell_group, high_level, sound slots | H positional |

### 2.5 DS2 mini block (type 5, 23 bytes)

Named non-combat entities: id i16 negated +0, next u16 +2
(9999 = none), priority u8 +4, name char[16] +5..20, flags +21,
data +22. Matches libgff `mini_t` exactly; verified ("Helmine"
id 1, "Miner" id 500). DS1 type-5 DATA blocks are 0-length
markers; DS1 minis do not exist.

### 2.6 The alignment and allegiance enums (wave 2)

Alignment (charrec: DS1 +26, DS2 +20), one enum both games,
column-major law-first:

| value | alignment | anchors |
|---:|---|---|
| 0 | none/unlisted | Fire Eel, Mastyrial ("ALIGNMENT: Nil" in the DS1 Manual) |
| 1 | Lawful Good | weak (pregens only) |
| 2 | Lawful Neutral | Magera ("lawful neutral or lawful evil") |
| 3 | Lawful Evil | Psurlon, all 15 DS2 Mindflayers |
| 4 | Neutral Good | Verini villagers, Jann ("Neutral Good", DS2 Manual) |
| 5 | Neutral (true) | Sand Howler, Strine, Dune Reaper ("ALIGNMENT: Neutral") |
| 6 | Neutral Evil | Mountain Stalker, Dagolar Slime |
| 7 | Chaotic Good | weak (pregens only) |
| 8 | Chaotic Neutral | slaadi, tohr-kreen |
| 9 | Chaotic Evil | Shadow, Vrock, Babau, Soulshard, Kartang, Umber Hulk |

The DS2 engine's protection-from-alignment bonus reads the
{3, 6, 9} column of the 3x3 grid at DS2 EXE 0x83775, confirming
the column-major order by instruction.

Allegiance is per-game and lives in the combat block (DS1 +29,
DS2 +21); the charrec copy is the default faction and the
combat copy the placed/current disposition (joinables carry
charrec 4 with combat 1). DS1: 1 = party, 2 = hostile
placement, 4 = neutral/friendly. DS2: 0 = party, 7 = hostile,
4 = friendly/neutral, 1 = placed-neutral (civilians and
hostile-later villains), 5 = mercenaries/wild attackables;
3 and 6 are singletons. The bitfield reading is dead in both
games (DS2's party value is 0; 7 = 1|2|4 appears 65 times).

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

> **Correction 2026-09-19** ([`asset-bindings.md`](asset-bindings.md)
> 6, byte audit of the shipped chunk): this table's column map
> needs re-pinning before item-editor work. Offset 6 is omitted
> from the table but exists in the data (heavily populated, 250
> dominant); col 5 is nonzero in 15 rows {1,2,7,11,15} (listed
> here as always-0); and the col 19 "0 (VB)" claim is wrong (45
> rows carry {0,1,2,6}). None of these columns is the icon index
> (that comes from the OJFF layer, asset-bindings.md 1).

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
record; the per-record field order is soloscuro-archive's
`extract.c`, with the offsets measured here and the damage
semantics corrected against the full description corpus (see
the damage-word note below the layout).

```
+0  u8  data0          (low 2 bits ai-type, high 6 repeat count)
+1  i16 range          (feet; -2 touch, -1 self)
+3  u8  range_per_level (real: Cone of Cold 0 + 20/lvl matches its text)
+4  u8  duration packed (low nibble dice, high nibble sides)
+5  u16 dur_per_level
+7  i16 dur_multiplier (0 instant, -9999 indefinite, 60 rounds,
       600 turns, 3600 hours, -1 event-based expiry, 1 handler tick)
+9  u16 area (feet)
+11 u8  area_per_level
+12 u8  target (1 point/place, 2 wall/line, 3 ally, 4 single enemy,
       5 anyone, 6 cone, 7 self; 0 and 8 unobserved in 516 records)
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
+25 i8  effect (special-behavior selector; see the dispatch note below)
+26 u16 effect_type (damage-type bitmask: 1 poison, 2 fire, 4 cold,
       8 blunt, 0x10 cutting, 0x20 piercing, 0x40 acid, 0x80 electric,
       0x100 draining, 0x200 magic, 0x400 mental, 0x800 death, ...)
+28 u32 damage packed:
       byte0 plus(5) | dice_plus(3); byte1 div(3) | dice(5);
       byte2 sides(4) | scale(4); byte3 savable(1) | save_mod(4s)
             | save_type(3: 1 poison, 2 wands, 3 petr, 4 breath,
                        5 spells, 6 paral, 7 death, 8 magic)
```

Damage word semantics (wave 2: corpus-confirmed against all 441
text-backed spell descriptions; 9/9 on per-level damage claims):

- `div == 0`: flat damage, `dice`d`sides` + flat `plus`.
- `div == 1`: count = `dice_plus`*level (+`dice`), and `plus`
  is the PER-CASTER-LEVEL bonus: Burning Hands = 1d3+2/lvl,
  Shocking Grasp = 1d8+1/lvl, Fireball = (1*lvl)d6, Delayed
  Blast Fireball = (1*lvl)d6+1/lvl.
- `div > 1` with the `scale` nibble set: grouped per-level,
  ((level+dice_plus)/div)d`sides`: Magic Missile = ((lvl+1)/2)d4+1.
  `div` also does non-damage grouping (Mirror Image 1 image per
  3 levels, Stoneskin 1 charge per 2 levels).
- `div > 1` without `scale`: flat `dice_plus` dice: Flame Arrow
  = 5d6 (upstream extract.c's multiplier formula predicts zero
  dice here and is corrected by this reading).
- `scale` is a 1-bit flag in practice (510/516 records are 0);
  with empty dice it marks handler-defined damage (Sunray, Air
  Lens, Psionic Damper, Spider Strand).

Duration = (NdS + dur_per_level/level) units of dur_multiplier
(Haste 3d1+1/lvl rounds, Strength 1/lvl hours; the -1 class is
event-expiry: Armor, Invisibility, Stoneskin).

The effect byte (+25) is NOT a central jump-table index: wave 2
enumerated every table-indirect call site in both binaries and
found none keyed on it. The dispatch is distributed compiled
case-chains plus overlay-runtime far-call indirection (the
runtime overlay segment map is the concrete blocker for
resolving the cast/apply handlers statically). Effect 0 (the
majority: Fireball, Magic Missile, Cure wounds, all the wall
spells) is the generic packed-word damage/duration path; the
nonzero ids select special behaviors (charm family, holds,
fear, invisibility, armor, ...). Live-id census: DS1 53
nonzero ids, DS2 75; the id space was renumbered between
engines (Charm 10 -> 20, Shield 46 -> 89), so handler maps do
not transfer.

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

Text-vs-data disagreements (wave 2 corpus cross-check; likely
SSI data bugs, each worth a darkfix-style note someday):
Stinking Cloud and Produce Fire carry 1d6 where their text
says 2-5 (1d4+1, same mean, wrong dice); Cause Fear's word is
1 round/level against the text's "1 to 4 rounds"; Delayed
Blast Fireball's delay reads as 1d3+2/level rounds against the
text's "2-5 rounds"; Melf's Minute Meteors stores only the
per-globe die (globe count is handler-side); Chaos's creature
count scaling is not in the word or area fields. Handler-side
damage with an intentionally empty word: Detonate, Sunray,
Vampiric Touch, the Cure family's heal dice, the stat-boost
family.

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
Wave 2 (same day, four more read-only agents) pinned the DS2
THAC0 byte and the DS2 charrec identity bytes by instruction
evidence, resolved the alignment and allegiance enums, settled
the damage-word and duration semantics corpus-wide against the
spell descriptions, and produced the effect-dispatch negative
result recorded in section 6. Corrections recorded here
supersede earlier prose in the roadmap's historical notes (the
"+14" id anchor; the DS2-scoping of the SPIN 1.10 fills; the
"DS2 THAC0 is derived" hypothesis). Regenerate the catalogues
with `tools/gff-edit/scripts/extract-catalogue.py`.
