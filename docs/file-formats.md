# File Formats

*Reference, not a tutorial. Read this when a cookbook entry or a
tool's output names a chunk type and you need its exact layout.
For a guided first look at a GFF, `opends inspect <file>` and
`gff-cat what <kind> <id>` will route you here with context.*

The Dark Sun engine packs nearly everything into a single container
format, **GFF** (Game/Generic File Format), and uses a small number of
external file types alongside it.

> **Don't confuse GFF with BioWare GFF.** BioWare's "Generic File Format"
> (Aurora / NWN / Dragon Age) shares only the abbreviation. SSI's GFF
> predates BioWare's by years and is structurally unrelated.

The authoritative public reference is `dsoageofheroes/libgff`'s
`include/gff/gfftypes.h`. Cross-check against `JohnGlassmyer/dsun_music`
when in doubt.

## 1. GFF container

### Header

The file header is **28 bytes** (`0x1C`), a fixed sequence of
seven little-endian `uint32_t` fields. Verified locally against
DS1 `DARKRUN.GFF`, `RGN02.GFF`, `RESOURCE.GFF` and DS2
`CHARSAVE.GFF`, cross-checked with libgff's `gff_file_header_t`
in `dsoageofheroes/libgff` `include/gff/common.h`.

```
offset  size  field            notes
  0      4    identity         "GFFI" magic (0x47 0x46 0x46 0x49)
  4      4    version          0x00030000 on every observed file. (version >> 16) == 3.
  8      4    data_location    First chunk data offset. Always 28 (= header size).
 12      4    toc_location     Byte offset from file start to the TOC.
 16      4    toc_length       TOC byte length.
 20      4    file_flags       Observed: 0 on most GFFs, 8 on CHARSAVE.GFF. Semantics TBD.
 24      4    data0            Per-file sentinel. Observed: 1, 3, 117. Likely a next-id or count; not load-bearing for read.
```

The chunk data area runs from `data_location` (= 28) up to
`toc_location`.

### Table of Contents

At `toc_location`, the TOC starts with an 8-byte header, then a
list of types and their chunk entries, then a free list. Cross-
checked with libgff's `gff_open()` loader in `src/gff.c`.

```
struct gff_toc_header {
    uint32_t types_offset;     // byte offset from TOC start to the type list. Observed: always 8.
    uint32_t free_list_offset; // byte offset from TOC start to the free list.
};
```

At `toc_location + types_offset` the type list begins:

```
uint16_t num_types;

for each type (num_types entries):
    uint32_t chunk_type;       // four ASCII bytes spelling the FOURCC at offset 0..3
    uint32_t chunk_count;      // number of resources of this type

    if (chunk_count & 0x80000000) {
        // Segmented chunk list. The actual count is in the low 31
        // bits. Per-chunk (offset, length) records live in a
        // separate secondary table inside the file's GFFI chunk
        // (see "Segmented chunk resolution" below).
        int32_t seg_count;        // total chunks (often duplicates the low 31 bits above)
        int32_t seg_loc_id;       // index into the GFFI type's chunks; that chunk holds the secondary table
        uint32_t num_runs;        // number of segment runs that follow
        for (i = 0; i < num_runs; i++) {
            int32_t first_id;     // first resource id in this run
            int32_t num_chunks;   // count of consecutive resource ids
        }
    } else {
        // Indexed chunk list. The default and dominant case.
        for (i = 0; i < chunk_count; i++) {
            int32_t  id;        // resource id within this type
            uint32_t location;  // byte offset in file where chunk data lives
            uint32_t length;    // chunk byte length
        }
    }
```

At `toc_location + free_list_offset` the free list begins. On
every shipped GFF inspected the free list is empty
(`free_list_offset == toc_length`, leaving zero bytes). When
populated, libgff's writer is the reference; document layout
when we first need it.

The high bit of **`chunk_count`** (`GFFSEGFLAGMASK = 0x80000000`)
selects between indexed and segmented chunk lists. The chunk
type's FOURCC is unchanged across the two cases. libgff names
this `GFFSEGFLAGMASK`; `chunk_count & 0x7FFFFFFF`
(`GFFMAXCHUNKMASK`) gives the canonical chunk count.

### Segmented chunk resolution

Segmented types do not list per-chunk `(id, location, length)`
records inline. Instead, the type's TOC entry carries:

- `seg_loc_id` — an **index** into the chunks of the file's
  `GFFI` type (i.e. the `seg_loc_id`-th `gff_chunk_header_t`
  emitted by the GFFI type in the type list above).
- A list of **segment runs**, each `(first_id, num_chunks)`,
  describing the resource ids the type owns.

The chunk indexed by `seg_loc_id` in the GFFI type points at a
**secondary table** sitting inside the GFFI chunk's data. Its
layout:

```
uint32 entry_count
entry_count × { uint32 offset, uint32 size }   // 8 bytes each
```

Resource ids are not stored in the secondary table. They are
reconstructed by walking the type's segment runs in order: the
i-th secondary-table entry's resource id is
`runs[r].first_id + (i - start_index_of_run_r)`, where `r` is
the run that contains entry `i`. The sum of all `num_chunks`
across runs equals `entry_count`.

Cross-checked against:

- libgff's `gff_find_chunk_header` in
  `dsoageofheroes/libgff/src/gff.c`.
- dsun_music's `GffFile.createTables` and `SecondaryGffiTable`
  in `JohnGlassmyer/dsun_music`
  (`common/src/main/java/net/johnglassmyer/dsun/common/gff/`).

### Writer policy

When replacing a chunk's bytes, we follow dsun_music's
`replaceResource` policy:

- If the new bytes fit in the existing slot
  (`new_length <= old_length`), write them at the chunk's
  original `location` and rewrite the `(location, length)`
  record so `length` reflects the new size. Trailing bytes
  within the old slot become unreferenced dead space; the
  parser will not see them because it follows the TOC.
- If the new bytes are larger, append them at end-of-file and
  rewrite the `(location, length)` record to point there. The
  TOC's own `toc_location` and `toc_length` in the file header
  are unchanged; the appended chunk lives past the TOC. Both
  libgff and our reader follow the TOC, so a chunk past the
  TOC parses correctly.

For indexed chunks the `(location, length)` record sits in the
TOC; for segmented chunks it sits in the secondary table inside
the GFFI chunk. Our writer tracks each chunk's metadata file
offset (`ChunkRef::meta_offset`) so a single code path handles
both cases.

**Worked example, DARKRUN.GFF (991 bytes total):**

| Offset    | Bytes               | Decoded                              |
|----------:|---------------------|--------------------------------------|
| 0..3      | `47 46 46 49`       | identity = `GFFI`                    |
| 4..7      | `00 00 03 00`       | version = `0x00030000` (major 3)     |
| 8..11     | `1c 00 00 00`       | data_location = 28                   |
| 12..15    | `bf 03 00 00`       | toc_location = 959                   |
| 16..19    | `20 00 00 00`       | toc_length = 32                      |
| 20..23    | `00 00 00 00`       | file_flags = 0                       |
| 24..27    | `01 00 00 00`       | data0 = 1                            |
| 959..962  | `08 00 00 00`       | toc.types_offset = 8                 |
| 963..966  | `1e 00 00 00`       | toc.free_list_offset = 30            |
| 967..968  | `01 00`             | num_types = 1                        |
| 969..972  | `45 54 4d 45`       | chunk_type = `ETME`                  |
| 973..976  | `01 00 00 00`       | chunk_count = 1                      |
| 977..980  | `00 00 00 00`       | id = 0                               |
| 981..984  | `1c 00 00 00`       | location = 28                        |
| 985..988  | `a3 03 00 00`       | length = 931                         |
| 989..990  | `00 00`             | free list (empty)                    |

`28 + 931 = 959 = toc_location`, so the single chunk fills the
entire data region between header and TOC.

### Chunk type catalog

Source: libgff's `gfftypes.h`. Categorized for readability.

#### Structural

| FOURCC | Purpose                                    |
|--------|--------------------------------------------|
| `GFFI` | Magic                                      |
| `FORM` | Form chunk (IFF-like grouping)             |
| `GFRE` | Free / freelist (deleted entries)          |
| `GTOC` | Table of contents                          |

#### Graphics

| FOURCC  | Purpose                                          |
|---------|--------------------------------------------------|
| `PAL `  | VGA 256-color palette (768 bytes, 6-bit RGB)     |
| `BMP `  | Bitmap, one or more frames                       |
| `BMAP`  | Bump map                                         |
| `PORT`  | Character portrait                               |
| `WALL`  | Wall graphic                                     |
| `ICON`  | Icon (1–4 frames)                                |
| `TILE`  | Tile graphic                                     |
| `TMAP`  | Texture map                                      |
| `TXRF`  | Texture reference                                |
| `OMAP`  | Opacity map                                      |
| `CMAP`  | Color map / remap table                          |
| `CBMP`  | Color bitmap                                     |
| `FONT`  | Font (uses palette)                              |
| `BMA `  | Cinematic binary file                            |
| `ACF `  | Cinematic binary script                          |

Frame layout, palette indexing, RLE encoding (if any) — to be confirmed
during `opends-image` implementation against libgff's `gff_image*.c`.

#### Maps and world

| FOURCC | Purpose                                                   |
|--------|-----------------------------------------------------------|
| `RMAP` | Region tile map (DS1, also `MAP ` with trailing space)    |
| `MAP ` | Region tile map (DS2; same layout as `RMAP`)              |
| `GMAP` | Region map flags (wall index + passability/flag bits)     |
| `ETAB` | Object entry table (entities placed in region)            |
| `OJFF` | Object definition (used by ETAB to resolve sprite bitmaps)|
| `WALL` | Wall sprite bitmap (referenced by GMAP wall index)        |
| `MONR` | Monsters by region IDs and level                          |

##### Region geometry

Every region in both DS1 and DS2 uses the same on-screen grid:

| Quantity              | Value          | Source                       |
|-----------------------|----------------|------------------------------|
| Tiles wide            | 128            | `RegionTool.java:167`        |
| Tiles tall            | 98             | `RegionTool.java:168`        |
| Tile size             | 16 x 16 pixels | `RegionTool.java:169`        |
| Region width (px)     | 2048           | derived                      |
| Region height (px)    | 1568           | derived                      |

A region GFF contains exactly one each of `RMAP` / `MAP `, `GMAP`,
and `ETAB`, plus the per-region `TILE` chunks for the background
art and (sometimes) a `PAL ` chunk. The `RMAP`/`GMAP`/`ETAB`
chunks share the same resource id, which is the region number.

##### `RMAP` / `MAP ` (background tile grid)

Exactly 12,544 bytes (`128 * 98`). One byte per tile, row-major
(`map[y * 128 + x]`), value is the resource id of a `TILE` chunk
in the same GFF.

DS1 region GFFs (`RGN??.GFF`) use `RMAP`; DS2 region GFFs
(`RGN???.GFF`) use `MAP ` (with a trailing space). Layout is
identical; a reader picks whichever the GFF actually has.

Indices that do not correspond to a `TILE` chunk in the GFF are
treated as "no tile here." The reference Java tool throws NPE in
that case; `region-render` v0.1 fills the affected 16x16 cell
with palette index 0 (typically pure black or transparent on the
DS palettes) and counts the misses for the summary.

##### `GMAP` (wall + flags grid)

Also 12,544 bytes, row-major like `RMAP`. Each byte packs two
fields:

| Bits | Field            | Notes                                                     |
|------|------------------|-----------------------------------------------------------|
| 0-4  | Wall sprite index | `0` = no wall; `>0` indexes a `WALL` chunk (see below).  |
| 5-7  | Flag bits         | Passability / height / interaction (not modelled in v0.1).|

`GMAP_WALL_INDEX_BITMASK = 0x1F` (`RegionTool.java:172`). Wall
sprite resolution uses `regionNumber * 100 + wallIndex - 1` to
build the global `WALL` chunk id, looked up across the merged
GFF set (`RegionTool.java:274`-`276`). `region-render` v0.1
ignores `GMAP` entirely; the wall layer is v0.2+ work.

##### `TILE` chunks (background tile bitmaps)

Standard Dark Sun bitmap container with one or more frames; the
`image-extract` v0.1 decoder handles the DS1 RLE and PLNR frame
formats. `region-render` consumes frame 0 of each `TILE` and
expects the dimensions to be exactly `16 x 16`.

##### `PAL ` (palette source)

Standard 768-byte VGA palette (`PAL ` and `CPAL` are identical
on disk; `image-extract`'s `Palette::from_bytes` decodes either).
DS1 and DS2 differ in where the palette ships:

| Game | Inline `PAL ` in `RGN??.GFF`? | Resolution                                |
|------|-------------------------------|-------------------------------------------|
| DS1  | No.                           | Use `RESOURCE.GFF:PAL :1000` by default.  |
| DS2  | Yes (id `1`).                 | Use the inline chunk.                     |

`RegionTool.java:196`-`198` follows the same rule, with the
`--pal <path>` CLI flag as an explicit override.

##### `ETAB` (entity placements)

8-byte records, little-endian
(`RegionTool.java:300`-`317`):

| Offset | Type   | Field           |
|--------|--------|-----------------|
| 0      | s16    | `x`             |
| 2      | s16    | `y`             |
| 4      | s8     | `y_offset`      |
| 5      | u8     | `byte5` (bit 7 = `mirrored`) |
| 6      | s16    | `ojff_number`   |

Each record places an `OJFF`-defined sprite at `(x, y - yOffset)`
with optional horizontal mirroring. v0.1 of `region-render` does
not draw entities; this row is here so future readers do not
mistake the format. Entities (with `WALL`s) come in v0.2+.

#### Audio

| FOURCC  | Purpose                                              |
|---------|------------------------------------------------------|
| `MSEQ`  | XMIDI sequence file (the "master" XMI)               |
| `PSEQ`  | XMI variant for PC Speaker                           |
| `FSEQ`  | XMI variant for FM (AdLib / Sound Blaster OPL)       |
| `LSEQ`  | XMI variant for Roland LAPC / MT-32                  |
| `GSEQ`  | XMI variant for General MIDI                         |
| `CSEQ`  | Clock sequence                                       |
| `MGTL`  | Global timbre library                                |
| `BVOC`  | Background-play sample (VOC)                         |
| `FVOC`  | Foreground-play sample (VOC)                         |
| `SINF`  | Sound card info                                      |
| `ADV `  | AIL/MEL driver                                       |
| `DADV`  | Dynamic AIL driver (MEL 1.x)                         |
| `DRV `  | Generic driver                                       |

#### UI

| FOURCC | Purpose                                       |
|--------|-----------------------------------------------|
| `WIND` | Window definition                             |
| `DBOX` | Dialog box                                    |
| `EBOX` | Edit box                                      |
| `BUTN` | Button                                        |
| `MENU` | Menu                                          |
| `SBAR` | Scroll bar                                    |
| `APFM` | (Likely "application form" — TBD)             |
| `ACCL` | Accelerator (keyboard shortcut table)         |

#### Game data and objects

| FOURCC | Purpose                                                    |
|--------|------------------------------------------------------------|
| `IT1R` | Items                                                      |
| `OJFF` | Object data (general)                                      |
| `RDFF` | Record data — distinct schemas per game (DS1/DS2/DSO) for: |
|        |  item, combat, char, mini, player, entity records          |
| `FNFO` | Object data table                                          |
| `RDAT` | Names                                                      |
| `NAME` | Names                                                      |
| `TEXT` | Generic text resources                                     |
| `MERR` | Error messages                                             |
| `ETME` | Copyright / credits text                                   |
| `SPIN` | Spell text                                                 |
| `SCMD` | Animation script command table                             |
| `SJMP` | Animation script jump table                                |
| `POBJ` | Polymesh object database                                   |

#### Scripting (the GPL VM, see `scripting-gpl.md`)

| FOURCC | Purpose                                  |
|--------|------------------------------------------|
| `GPL ` | Compiled GPL bytecode                    |
| `MAS ` | Compiled GPL master script               |
| `GPLI` | GPL "I" data (incompletely documented)   |
| `GPLX` | GPL index file                           |

#### Save / character

| FOURCC | Purpose                                      |
|--------|----------------------------------------------|
| `CHAR` | Saved character slot                         |
| `SPST` | Spell list bitmask                           |
| `PSST` | Psionic list bytes                           |
| `PSIN` | Psionic and sphere selection                 |
| `CACT` | Valid character ID flag                      |
| `STXT` | Save text                                    |
| `SAVE` | Save metadata                                |

`CHARSAVE.GFF` (the save file) is the same container with these chunks.

## 2. Schema versioning between DS1, DS2, and DSO

The `RDFF` chunk type's note in libgff calls out per-game record-schema
variants. This means: an `IT1R` or `RDFF` chunk in DS1 is **not**
byte-compatible with the same chunk type in DS2 — the field layouts
differ. OpenDS must carry a schema version per game.

Practical implication for `opends-region` and `opends-rules`: load the
source game's variant explicitly and treat the schemas as separate
data types with a common interface.

## 3. Save files (DS1 specifics)

Save state in DS1 is split across multiple files; the structure
isn't intuitive from the filenames. RE'd 2026-05-18 while
shipping `tools/save-inspect/scripts/ds1-party-edit.py`. The DS2
story is different and largely lives in `CHARSAVE.GFF`; see
§3.5 for the DS2/DS1 contrast.

### 3.1 File roles in DS1

| File                | What it holds                                          |
|---------------------|--------------------------------------------------------|
| `CHARSAVE.GFF`      | **NOT the active party in DS1.** Holds 8 CHAR records that appear to be unrelated character templates (e.g., starter NPCs or pre-generated characters); the names there do not overlap with the player's actual party. (In DS2 by contrast, `CHARSAVE.GFF` *does* hold the active party. The two games diverge here.) |
| `DARKRUN.GFF`       | Live world state during play. Contains the active party PC records (as detailed below), plus per-region state in other SAVE chunks. Engine writes this continuously while playing. |
| `SAVE0N.SAV`        | Snapshot of `DARKRUN.GFF` at save time. Engine reads this on load. **Byte-identical to `DARKRUN.GFF` when both come from the same save.** |
| `DARKSAVE.GFF`      | Factory default for `DARKRUN.GFF`. Small (1 KB) and contains the `ETME` template descriptor only. |
| `BACKSAVE.GFF`      | Engine's auto-backup pointer (very small; not investigated). |

The `SAVE0N.SAV == DARKRUN.GFF` relationship was found in
save-inspect v0.6.0; the DARKRUN-side party records were found
in the v0.7.0 SAVE-chunk decode work and validated by
end-to-end editing.

### 3.2 DARKRUN.GFF `SAVE` chunks

The DS1 `DARKRUN.GFF` carries ~60 `SAVE` chunks. Each is an
opaque byte blob in the GFF; the chunk id assigns its
semantics. Known assignments (DS1 GOG 1.10):

| Chunk     | Size     | Contents                                        |
|-----------|---------:|-------------------------------------------------|
| `SAVE/1`  | ~10 KB   | Largest; structure not yet RE'd                 |
| `SAVE/5`  | ~2.4 KB  | **Party combat sub-blocks** (see §3.3)          |
| `SAVE/6`  | ~1.2 KB  | **Party character sub-blocks** (see §3.4)       |
| `SAVE/10..17` | 2 B each | u16 LE values; counters / region pointers (semantic TBD) |
| `SAVE/18` | ~51 B    | Boolean array (all `0x01` in a played save)     |
| `SAVE/2..4, 7..9, 19+` | varies | Various per-region state; not yet RE'd |

### 3.3 `SAVE/5` — party combat sub-blocks

`SAVE/5` is an array of **DS1 combat sub-blocks**, 58 bytes
each, one per active party PC in display order. The layout
matches libgff's `ds1_combat_t` byte-for-byte (sourced from
`dsoageofheroes/libgff` `include/gff/object.h`).

| Offset | Type    | Field                |
|-------:|---------|----------------------|
| 0..1   | i16     | hp                   |
| 2..3   | i16     | psp                  |
| 4..5   | i16     | char_index           |
| 6..7   | i16     | id                   |
| 8..9   | i16     | ready_item_index     |
| 10..11 | i16     | weapon_index         |
| 12..13 | i16     | pack_index           |
| 14..21 | u8[8]   | data_block (opaque)  |
| 22     | u8      | special_attack       |
| 23     | u8      | special_defense      |
| 24..25 | i16     | icon                 |
| 26     | i8      | ac                   |
| 27     | u8      | move                 |
| 28     | u8      | status               |
| 29     | u8      | allegiance           |
| 30     | u8      | data                 |
| 31     | i8      | thac0                |
| 32     | u8      | priority             |
| 33     | u8      | flags                |
| 34..39 | u8[6]   | **stats** (STR DEX CON INT WIS CHR) |
| 40..57 | char[18]| **name** (NUL-padded; variable-length string in fixed 18-byte field) |

The name being at offset 40 (not 0) is the **non-obvious
gotcha** that bit us: searching the chunk for "Gerakis" finds
it at SAVE-5 offset 40, which is the **end** of record 0, not
the start. Record stride is 58 bytes, so subsequent names
appear at offsets 40, 98, 156, 214 (each + 58).

Brandon's DS1 played save (`SAVE/5`, 4 party PCs):

```
record 0 (offset 0..57):   Gerakis      stats 24 15 22 13 15 14
record 1 (offset 58..115): K'ratchek    stats 19 21 19 16 19 15
record 2 (offset 116..173): Cermak      stats 19 21 17 18 18 16
record 3 (offset 174..231): Cilla       stats 19 21 17 18 18 16
```

### 3.4 `SAVE/6` — party character sub-blocks

`SAVE/6` is an array of **DS1 character sub-blocks**, 71-72
bytes each (the trailing palette byte is sometimes absent),
same order as SAVE/5. Layout matches libgff's `ds1_character_t`:

| Offset | Type    | Field                |
|-------:|---------|----------------------|
| 0..3   | u32     | current_xp           |
| 4..7   | u32     | high_xp              |
| 8..9   | u16     | base_hp              |
| 10..11 | u16     | high_hp              |
| 12..13 | u16     | base_psp             |
| 14..15 | u16     | id                   |
| 16..17 | u8[2]   | _data1 (opaque)      |
| 18..19 | u16     | legal_class          |
| 20..23 | u8[4]   | _data2 (opaque)      |
| 24     | u8      | race                 |
| 25     | u8      | gender               |
| 26     | u8      | alignment            |
| 27..32 | u8[6]   | **stats** (STR DEX CON INT WIS CHR) |
| 33..35 | i8[3]   | real_class           |
| 36..38 | u8[3]   | level                |
| 39     | i8      | base_ac              |
| 40     | u8      | base_move            |
| 41     | u8      | magic_resistance     |
| 42     | u8      | num_blows            |
| 43..45 | u8[3]   | num_attacks          |
| 46..48 | u8[3]   | **num_dice** (weapon dmg dice) |
| 49..51 | u8[3]   | **num_sides** (die size) |
| 52..54 | u8[3]   | **num_bonuses** (flat dmg bonus) |
| 55..59 | u8[5]   | saving_throw         |
| 60     | u8      | allegiance           |
| 61     | u8      | size                 |
| 62     | u8      | spell_group          |
| 63..65 | u8[3]   | high_level           |
| 66..67 | u16     | sound_fx             |
| 68..69 | u16     | attack_sound         |
| 70     | u8      | psi_group            |
| 71     | u8      | palette (optional)   |

**SAVE/6 is the engine-authoritative copy of stats** for
combat math. SAVE/5's stats are read for display; SAVE/6's are
read for calculations. Editing only SAVE/5 updates the
character sheet but doesn't change combat behaviour. Editing
both keeps display + engine in sync.

The `num_dice` / `num_sides` / `num_bonuses` arrays carry
**cached weapon damage**: `damage = num_dice[0] × dN_sides[0]
+ num_bonuses[0] + (STR table bonus)`. The "STR table bonus"
is computed at attack time from the current STR byte against
the 2e exceptional-strength table; if STR is out of the
table's range (>25-ish) the bonus is 0.

### 3.5 DS2 contrast

DS2's `CHARSAVE.GFF` *is* the active party file (records 29+
were Brandon's played PCs in his DS2 testing). DS2's
`DARKRUN.GFF` carries SAVE chunks that haven't been RE'd to
the same depth as DS1's. We don't yet know whether DS2 stores
a redundant party copy in DARKRUN-side SAVE chunks the way
DS1 does, or whether DS2 keeps everything in CHARSAVE.

Practical tooling implication: `save-inspect edit-pc /
list-pcs / list-items / edit-item / give-item` (CHARSAVE-based)
work for **DS2 active party**, and for **DS1 inactive
templates**, but **not** for the DS1 active party.
`ds1-party-edit.py` (DARKRUN-based) is the DS1 active-party
tool.

## 4. External (non-GFF) files

| File                  | Format                                          |
|-----------------------|-------------------------------------------------|
| `*.FLI`               | Autodesk Animator FLIC (used in DS2 cinematics) |
| `MUSIC/Track*.ogg`    | Vorbis (GOG re-encode of original CD redbook)   |
| `*.VOC`               | Creative Voice (PCM digital sound)              |
| `GM1.BNK`, `GM2.BNK`  | Roland sound banks (DS1)                        |
| `STDPATCH.AD`         | AdLib FM patch table                            |
| `*.INI`               | Plain DOS INI                                   |
| `*.BAT`               | DOS batch (launch scripts)                      |
| `game.gog` (DS2)      | CD-ROM image, Mode 2/2352 data track            |
| `game.ins` (DS2)      | CD cuesheet referencing the OGG music tracks    |
| `*.RTP`, `PATCH.EXE`  | RTPatch artifacts (residual from CD assembly)   |

`*.FLI` is well-documented (Autodesk Animator FLIC); existing Rust crates
like `flic` may suffice. `*.VOC` is Creative's spec, also well-known.

## 5. XMI specifics

XMI ("eXtended MIDI") is John Miles' own MIDI dialect. Notable points:

- Uses **two** delta-time bytes per event (not standard MIDI's variable
  length), interpreted as 1/120 second ticks.
- Includes a `TIMB` ("timbre list") chunk per song: which MT-32 patches
  the song wants pre-loaded.
- Includes RBRN ("RhythmTRack" or similar — needs verification) chunks
  for branch points (used by adaptive music).

Conversion to standard MIDI is implemented by the public-domain
`xmi2mid` (libgff bundles it). OpenDS will port this rather than depend
on a runtime library.

The same XMI source is rendered into per-driver chunks (PSEQ/FSEQ/LSEQ/
GSEQ) at content-build time — i.e., the driver-specific re-renders are
authored, not synthesized live. Each chunk contains the same musical
content adapted to the target hardware's timbre map.

## 6. Open questions

Resolved questions are documented inline. These remain.

- ~~The exact layout of segmented chunk lists.~~ Resolved (see
  "Segmented chunk resolution" above). Verified on the full DS1
  and DS2 corpus.
- The exact layout of a **non-empty free list**. Every shipped
  GFF inspected has `free_list_offset == toc_length`, leaving
  zero bytes. libgff's writer is the reference for when it
  matters.
- Semantics of `file_flags` (observed: 0 and 8) and `data0`
  (observed: 1, 3, 117). Not load-bearing for read; document
  when the writer needs to set them correctly.
- **Compression**: is any chunk type stored compressed? The
  DOS-era expectation is "no" (disk format = in-memory format),
  but large GFFs (5.7 MB+) may have RLE bitmaps internally.
  Unanswered.
