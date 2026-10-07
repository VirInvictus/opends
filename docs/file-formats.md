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
 20      4    file_flags       Pinned 2026-09-05: 0 on most GFFs, 8 on every DS2 region GFF (all 20 RGN*.GFF). DS1 regions and CHARSAVEs carry 0.
 24      4    data0            Per-file sentinel. Pinned: 1 on non-region files, 3 on DS1 regions, sequential 3..22 on DS2 regions (file order, not hex id). Not load-bearing for read.
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

At `toc_location + free_list_offset` the free list begins:

```
uint16 free_count;                        // number of free slots
free_count × { uint32 offset, uint32 size }  // 8 bytes each
```

On most shipped GFFs the list is empty (`free_count = 0`, leaving
`toc_length − free_list_offset == 2`). **GPLDATA.GFF (DS2) carries
a populated list**: 16 entries pointing at freed slots in the
chunk-data area (offsets cluster at the file tail, sizes 1–861
bytes), left behind when SSI's 1.10 recompile replaced chunk
content in-place.

> **Corrected 2026-09-05.** The first published version claimed
> `free_list_offset == toc_length` on every shipped file. That is
> wrong: the last 2 bytes of the TOC are a u16 free-entry count,
> and `free_list_offset == toc_length − 2 − (free_count × 8)`.
> Verified against 61 corpus files (59 empty, GPLDATA.DS2
> populated with 16 entries).

The high bit of **`chunk_count`** (`GFFSEGFLAGMASK = 0x80000000`)
selects between indexed and segmented chunk lists. The chunk
type's FOURCC is unchanged across the two cases. libgff names
this `GFFSEGFLAGMASK`; `chunk_count & 0x7FFFFFFF`
(`GFFMAXCHUNKMASK`) gives the canonical chunk count.

### Segmented chunk resolution

Segmented types do not list per-chunk `(id, location, length)`
records inline. Instead, the type's TOC entry carries:

- `seg_loc_id`: an **index** into the chunks of the file's
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
| `CMAT`  | BMA-codec still container, DS1 only (see the CMAT section) |
| `CPAL`  | Per-still palette for CMAT, DS1 only (see the CPAL section) |
| `ACF `  | Cinematic binary script                          |

Frame layout, palette indexing, RLE encoding (if any): to be confirmed
during `opends-image` implementation against libgff's `gff_image*.c`.

#### Maps and world

| FOURCC | Purpose                                                   |
|--------|-----------------------------------------------------------|
| `RMAP` | Region tile map (DS1, also `MAP ` with trailing space)    |
| `MAP ` | Region tile map (DS2; same layout as `RMAP`)              |
| `GMAP` | Region map flags (wall index + passability/flag bits)     |
| `VECT` | 256-direction unit circle (see the VECT section below)    |
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

Byte-verified 2026-10-06 across all 60 shipped chunks (20 DS2
regions x GOG/floppy/HotU; cd10 ships no region GFFs): every cell
of every MAP is a TILE id that exists in the same file, the payload
is identical across all three release lineages, and no cell equals
the GMAP byte or wall index at the same offset (an independent
layer, as documented). In shipped DS2 data the missing-tile fallback
never fires (every region's minimum cell is 1; the blank 16x16 TILE
0 is never referenced). The DS2 region loader requests the layer by
name: `push 'MAP '` at DS2 DSUN.EXE 0x2b7bc, in the same block as
`push 'RMAP'` and `push 'GMAP'`.

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
| 6      | s16    | `ojff_number` (negative-encoded object id, see below) |

Each record places an `OJFF`-defined sprite at `(x, y - yOffset)`
with optional horizontal mirroring; `region-render` draws the
entity layer (since v0.5.0) and animates it (since v0.6.0).
Measured 2026-09-10 on DS1's `RGN1E`/`RGN1F` ETABs:
`ojff_number` values are negative (range observed -30106..-39),
and the entity's `OJFF` chunk id is the absolute value: the
field carries `NAME(-N)`, GPL's negative object-id encoding (the
same encoding the tport and trigger operands use).
`region-render` has always resolved it by negating when
negative; this prose now says so too.

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
| `APFM` | (Likely "application form": TBD)             |
| `ACCL` | Accelerator (keyboard shortcut table)         |

#### Game data and objects

| FOURCC | Purpose                                                    |
|--------|------------------------------------------------------------|
| `IT1R` | Items (DS1 base-stat table; see `object-formats.md`)      |
| `OJFF` | Object data (general)                                      |
| `RDFF` | Record data: per-game record chains (items, creatures,     |
|        | minis, templates; full layouts in `object-formats.md`)     |
| `FNFO` | Object data table                                          |
| `RDAT` | Per-region binary config (u16 pairs; NOT names, corrected 2026-09-05) |
| `DATA` | DS2 spell-system data: 320 spell records + 3 aux tables (see the DATA section below) |
| `NAME` | Names                                                      |
| `TEXT` | Generic text resources                                     |
| `MERR` | Error messages                                             |
| `ETME` | Copyright / credits text                                   |
| `SPIN` | Spell text                                                 |
| `SCMD` | Animation script command table                             |
| `SJMP` | Animation script jump table                                |
| `POBJ` | Polymesh object database                                   |
| `RNME` | Region name (per-region; see RNME section below)           |

### RNME (region name)

One `RNME` chunk per region GFF (id matches the region id), holding
the region's display name as plain ASCII terminated by a period
(e.g. `Mines1.` for RGN038, `UnderTyr.` for RGN045). Documented
2026-09-05 from the DS2 corpus (all 20 regions carry exactly one);
the DS2 region-id-to-name table:

| id | name | id | name |
|----|------|----|------|
| 1 | forest. | 56 | Mines1. |
| 50 | Tyr. | 57 | Mines2. |
| 51 | VA Headquarters. | 58 | Mines3. |
| 52 | Pyramid. | 59 | Jann. |
| 54 | Yuan-ti Tunnels. | 60 | Mosaic. |
| 55 | El's Temple. | 61/62/63 | Volcano Level 2/1/3. |
| | | 65-69 | Silt Giants., Cloud., Crypt., Cosmos., UnderTyr. |
| 255 | Limbo. (special) | | |

Prior to this the kind was undocumented (it appeared in the
format-coverage gap list). Note region 53 is absent from the
shipped corpus and 255 is a special-scope region (`Limbo.`),
matching its use as the same-region tport marker's neighbour.
DS1's region files predate RNME entirely (their type list is
GFFI/ETAB/GMAP/RMAP/TILE: no MAP, no PAL, no RNME: the DS1 palette
comes from the RESOURCE fallback and the name chunk is absent).

### DATA (DS2 spell-system data)

Documented 2026-10-06 (mineout wave 1; evidence and the release-
lineage comparison in `port-digs-2026-10-06.md` 1). DATA exists only
in DS2's RESOURCE.GFF lineage (GOG `RESOURCE.GFF` plus `RESFLOP.GFF`
in the floppy/HotU/cd10 trees; payload byte-identical across the
archive copies, GOG 1.10 differing by exactly 5 bytes). No DS1 file
carries DATA; DS1's RESOURCE.GFF fills the same slot with `RDAT`
(45 chunks). Always a segmented type with runs `[(0,320),(1000,3)]`.

| ids | count | size | content |
|-----|-------|------|---------|
| 0..319 | 320 | 73 B each | Spell records: bytes 0..31 binary descriptor (undecoded, open), 32..63 NUL-padded 32-char long name, 64..72 NUL-padded 9-char short name. Names are the DS2 spell list; ids 269..319 are `MONS269`..`MONS319` placeholders (summoned monsters as spells) |
| 1000 | 1 | 320 B | 8 rows x 20 LE u16, monotonic-from-0 ramps (read: per-class level-up XP tables; rows 3 and 5 keep non-monotonic steps in 1.10) |
| 1001 | 1 | 576 B | Sparse flag bytes, two self-similar halves (no clean record width; open) |
| 1002 | 1 | 168 B | 21 (u32, u32) pairs, lane 1 round XP-like values, lane 2 = 1 then 50..69 (open) |

The GOG 1.10 copy's 5-byte difference against every archive copy is
the official patch's data-table work: id 155 (`PRAYER`) descriptor
byte 1 `0x00 -> 0x14`, and id 1000 row 6 two steps `14000 -> 24000`,
`17000 -> 27000` (repairing a broken +3000 progression). A port can
generate its spell table from ids 0..319 directly.

#### Scripting (the GPL VM, see `gpl-bytecode.md`)

| FOURCC | Purpose                                  |
|--------|------------------------------------------|
| `GPL ` | Compiled GPL bytecode                    |
| `MAS ` | Compiled GPL master script               |
| `GPLI` | GPL entry index: 1,316 records of (u16 entry_no, u16 offset in chunk, u16 chunk id); purpose open, see engine-quirks.md §8 |
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

### Kinds the corpus never ships (census 2026-10-06)

The 21 kinds in format-coverage.md's documented-kinds-never-seen
list were swept as TOC types, chunk-body markers, and whole-file
magics across every held artifact (both GOG trees including saves,
all archive-org trees and zip members; evidence:
port-digs-2026-10-06.md 4). Verdict: none of them ever shipped as a
GFF chunk kind. Three classes:

- **Engine-known, never materialized**: `FVOC`, `STXT`, `CMAP` exist
  as code constants inside DSUN.EXE (the `push 'FVOC'` byte sequence
  at ds1 232449, `push 'STXT'` at 429492, and the ILBM reader's
  packed `BMHDCMAPBODY` string table at 83051, CMAP at 83055) but no
  shipped container carries any of them.
- **Nested-marker only**: `FORM` appears exclusively as the IFF form
  marker of XMI data embedded in *SEQ chunk bodies (file-formats.md
  5), never as a TOC type.
- **No trace anywhere** (no TOC type, no boundary marker, not even a
  code constant in the binaries we hold): `BMAP`, `DADV`, `DBOX`,
  `DRV`, `GFRE`, `GTOC`, `MENU`, `MGTL`, `MSEQ`, `OMAP`, `POBJ`,
  `SAVE`, `SBAR`, `SINF`, `SJMP`, `TMAP`, `TXRF`. Every raw byte hit
  for these classified as media payload, patch-entry filenames, or
  unrelated strings (e.g. `MENU` = `MENUS.C` debug names, `SAVE` =
  save-game format strings).

No `.SAV`, `.XMI`, or `.SEQ` file exists anywhere under `.games/`
(the engine's `SAVE%.2d.SAV` naming never shipped as files; the only
sequence data is XMI inside *SEQ chunks). `dsun2_midi_files.zip`
holds 35 plain standard-MIDI files (`MIDI/RESFL000.MID`..`034.MID`),
not XMI: third-party exports matching the DJ.DAT slot count
(35), useful future comparison material for DS2 music.

### VECT (256-direction unit circle)

Decoded 2026-10-06 (evidence in `port-digs-2026-10-06.md` 5). One
1024-byte chunk, id 1, in DS1 `RESOURCE.GFF` and the DS2
`RESOURCE.GFF`/`RESFLOP.GFF` lineage; all five corpus payloads are
byte-identical. Layout: 256 records of (LE i16 x, LE i16 y). Entry
k is the direction k/256 of a full turn (1.40625 degrees per step,
clockwise, k=0 = up / screen -y) at radius 256:
`x = trunc(256 * sin)`, `y = -trunc(256 * cos)`. The formula matches
254/256 entries exactly; the k=128 and k=192 axis entries are one
less than exact (the generating trig undershot). Both engines load
it with `push 1; push 'VECT'` (DS1 DSUN.EXE 0x60874, DS2 0x64c9e):
it is the direction-to-step-delta table for the engine's 256-angle
convention. Whether the caller applies it to movement or aiming is
open (a pass over the 0x60874 caller would settle it).

### CMAT (BMA-codec still container, DS1 only)

Decoded 2026-10-06. Two chunks in DS1 `RESOURCE.GFF` only: id 200
(41,368 B) and id 300 (21,643 B). Despite the name, the payload is
not a matrix: it is the standard bitmap container (u32 size ==
chunk length, u16 frame_count = 1, u32 offset table) holding a
single frame of the BMA codec (`cinematics-ds1.md` 1), the same
family as the CINE stills. CMAT 200 is 320x200 and covers all 200
rows; CMAT 300 is 318x198 (a 1-pixel inset). Both walks terminate
with the frame's 0xFF on the payload's final byte, zero RLE/span
mismatches. Engine: DS1 DSUN.EXE pushes 'CMAT' and 'CPAL' in the
same function (0x56ad5 / 0x56af2); DS2's EXE never references
either. Each chunk pairs with the same-id `CPAL` palette. What the
two stills depict is open (render against CPAL, or read the caller).

### CPAL (per-still palette, DS1 only)

Two 768-byte chunks in DS1 `RESOURCE.GFF`, ids 200 and 300, pairing
with the same-id CMAT stills. Format is exactly `PAL `: 256 entries
of 6-bit R,G,B (all bytes <= 0x3F; entry 0 black, entry 255 white),
so `Palette::from_bytes` decodes either. The content is distinct
per-still art: 751/768 bytes differ from PAL 1000 and 719/768 from
each other; CMAT 200's all-index-1 background is CPAL 200's entry 1
(a dark maroon), confirming the pairing. DS2 never references CPAL.

### PLYL (dead DS2 combat playlist)

Documented 2026-10-06 (port-digs-2026-10-06.md 9). Six chunks in
DS2's RESOURCE.GFF lineage (ids 0, 10, 50..53; lengths 3, 3, 3, 7,
7, 5 - id 50 is the 3-byte `07 ff 64`), byte-identical from
floppy 1.0 through GOG 1.10: N records of `(u8 song, u8 0xff)` plus
one trailing byte (0x00 on ids 0/10, 0x64 on 50..53). The nine song
values are a nine-song subset of DJ.DAT's state-3 combat pool
(that pool is songs 1..10 across ten records, audio-routing.md 1;
PLYL never references song 10). No shipped binary of any lineage references the
fourcc (every EXE scanned; the music dispatcher pushes only
PSEQ/FSEQ/LSEQ/GSEQ/redbook): the kind is dead data, plausibly a
pre-CD playlist frozen into the resource files. A port should not
read it.

### ALL (DS2 object-database digests)

Documented 2026-10-06. Five chunks in DS2's OBJEX.GFF (ids 1..5),
byte-identical across the release lineage and unreferenced by either
engine (no `ALL ` fourcc anywhere in the binaries): fixed-stride
aggregate tables over the object database, documentation-grade
digests rather than runtime data. id 5 (1725 = 75 x 23): `u16 id,
u16 9999 (none sentinel), u8 type, u8 len, char[] name` for every
named special entity (a superset of the bestiary's 58 minis). id 2
(18522 = 378 x 49): `u32 hp, u16 ?, u16 id, u16 9999 x3, u16 x2,
i8 AC, u8 MV, u8, u8, u8 THAC0, u8 6, u8 0, u8[6] stats, u8, u8,
u8 len, char[] name`; AC, name, and THAC0 join every one of
bestiary-ds2.md's 352 creature rows (AC and THAC0 as signed bytes;
Air Drake's 0xfe = -2 proves it). id 1 (1317 x 23) carries a
class byte (values 0/4/5/6); id 3 (108 x 66) holds per-creature long
blocks; id 4 (1530) is 0xFA-keyed 15-byte cells, undetermined. Treat
the kind as stale build artefacts.

### GREQ (DS2 per-save-slot view state)

Documented 2026-10-06. Ten 9-byte chunks, ids 1..10 (id = save slot
+ 1; writer DSUN.EXE 0x7D6FB, reader 0x7D8ED, both moving the fields
to/from globals 0x14d7/79/7b/7d and 0x4459), only in DS2
CHARSAVE.GFF: `u16 view_left, u16 view_top, u16 view_right,
u16 view_bottom, u8 picture_index`. The words are the saved
scroll/camera bounds in region pixels (checker at 0x219A2: 320x200
extent, 8-pixel snap; shipped rows mostly bound the full 2048x1568
region). The byte indexes a 25-per-page BMP pool
(`[0x140c]*25 + idx + 0x4E84`). Engine quirk worth knowing: the
reader copies one stack byte past the 9-byte buffer into 0x4458, so
that global is never actually restored. DS1 has no GREQ anywhere.

### PREF (preferences state, both games)

Documented 2026-10-06 (this corrects screen-flow.md's old
"14-byte PREF" note: the chunk is 11 bytes in DS1 and 9 in DS2, per
the TOCs and the writers' length immediates). Common prefix:
`u16 text_speed (0..3), u8 music_volume, u8 sound_volume (0..127),
u8 music_volume_scale` (scale 100 in DS1, 255 in DS2; volumes are
scale-relative). DS1 then stores three u16 toggles at +5/+7/+9
(sound, music, mouse; globals 0x11a8/aa/ac; writer DSUN.EXE 0x7468B,
reader 0x74821); the mouse toggle picks the (4,4) vs (16,16) cursor.
DS2 stores four u8 at +5..+8: sound, music, mouse (globals
0x1435/36/37) and one unnamed enable gate (0x1439); writer 0x7D6FB,
reader 0x7D8ED, 9-byte length literal.

## 2. Schema versioning between DS1, DS2, and DSO

The `RDFF` chunk type's note in libgff calls out per-game record-schema
variants. This means: an `IT1R` or `RDFF` chunk in DS1 is **not**
byte-compatible with the same chunk type in DS2: the field layouts
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

### 3.3 `SAVE/5`: party combat sub-blocks

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

### 3.4 `SAVE/6`: party character sub-blocks

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
| `MUSIC/Track*.ogg`    | Vorbis (GOG re-encode of original CD redbook; Track02..41, 40 audio tracks) |
| `*.VOC`               | Creative Voice (PCM digital sound)              |
| `GM1.BNK`, `GM2.BNK`  | Aria MIDI patch banks for MIDITSR.EXE (DS1 only; corrected 2026-10-06, not Roland) |
| `STDPATCH.AD`         | AdLib FM standard patch table (both games)      |
| `*.INI`               | Plain DOS INI (UltraMID GUS patch-assignment tables) |
| `*.BAT`               | DOS batch (launch scripts)                      |
| `game.gog` (DS2)      | CD-ROM image, Mode 2/2352 data track            |
| `game.ins` (DS2)      | CD cuesheet referencing the OGG music tracks    |
| `*.RTP`, `PATCH.EXE`  | RTPatch artifacts (residual from CD assembly)   |

`*.FLI` is well-documented (Autodesk Animator FLIC); existing Rust crates
like `flic` may suffice. `*.VOC` is Creative's spec, also well-known.

### Measured identifications (2026-10-06 census; evidence in port-digs-2026-10-06.md 4)

- **DJ.DAT** (231 B): DS2's music cue table, fully decoded in
  audio-routing.md 1 (38 six-byte records filling the 231-byte file
  exactly; the 'trailer' once described there is the last record's
  own tail);
  byte-identical from floppy 1.0 through GOG 1.10.
- **ITEMS.BIN** (936 B): exactly 234 little-endian u16 pairs, both
  columns from one id space (603..31990) in long consecutive runs,
  unchanged floppy through GOG. Most plausible reading: an item-id
  cross-reference for the character-transfer path (CHARTRAN.EXE);
  the literal name appears in no EXE, so exact semantics stay open.
- **game.gog / game.ins**: raw MODE2/2352 image of the Wake of the
  Ravager data track (ISO9660, volume `WAKE1_0`, 46,400 sectors,
  90.7 MiB, no audio inside). game.ins maps TRACK 01 to game.gog and
  audio tracks 02..41 to `MUSIC/TrackNN.ogg` (GOG's script labels
  the OGGs with the token `MP3`; every file is Ogg Vorbis).
- **PATCH.RTP family** (magic u32 `0x00C82A4B`): SSI's WERKS/RTPatch
  1.1x packages; space-padded DOS filenames in the entry table.
  GOG's CD package patches `CHARSAVE.GFF`; the dk11 disk package
  patches `DSUN.EXE` only; `patch-wake3511/payload.arj` carries an
  ARJ signature but does not parse (opaque blob; the record says its
  payload targets DSUN.EXE only).
- **STDPATCH.AD** (4,662 B, both games; DS1 and DS2 differ in blob
  content only): u16 pad + u16 1400 (data-area offset); directory of
  232 six-byte records (u16 blob offset, u16 0, u16 key) at 6..1397,
  keys 1..127 = GM melodic programs, then `0x7Fnn` keys = GM
  percussion notes; 0xFFFF sentinel; data area = 233 timbre blobs of
  14 bytes (u16 14 + 12 bytes of OPL2 register dump). 175 GM timbres
  inside the 233. The `stdpatch` string sits in both DSUN.EXEs.
- **GM1.BNK / GM2.BNK** (DS1 only, ~24 KB each): Aria MIDI patch
  banks consumed by MIDITSR.EXE per SOUND.BAT (`lh miditsr gm2.bnk
  /I`). Header: byte0 = 2, byte1 = 175 (= the GM instrument count,
  matching STDPATCH.AD's GM set; hypothesis), u16 area/directory
  offsets, then an increasing u16 offset table with 0 for unused
  slots. Not Roland; the old table row said Roland.
- **SSI1.INI / UM200.INI / UM206.INI / UM206A.INI** (DS1 only):
  UltraMID (Gravis UltraSound) patch-assignment tables, 200 lines of
  `Patch #, 256K, 512K, 768K, 1024K, Patch Name`; SOUND.BAT copies
  the one matching the detected GUS patch-set revision over
  ssi1.ini. Quirk: the GOG tree's SSI1.INI is the stale 06/22/93
  revision (UM200 07/26/93 remaps rows onto the newer library;
  UM206/UM206A rename three patches the launcher probes for).
- **MIDITSR.EXE** (DS1): Media Vision Aria MIDI TSR (plain MZ, aria
  strings). **GRAVIS.EXE** (DS1): LZ91-packed Gravis UltraSound
  detector run by DARKSUN.BAT purely for its errorlevel.
- **1.FLI..5.FLI** (DS2): vanilla FLIC 1.x (`AF11`), 320x200x8;
  frames 1175/373/575/284/1398, speed 7/7/7/7/5 (1/70 s ticks), the
  DS2 intro/outro cinematics.

## 5. XMI specifics

XMI ("eXtended MIDI") is John Miles' own MIDI dialect. Notable
points, verified 2026-10-06 against the full corpus (evidence:
port-digs-2026-10-06.md 2):

- Delta times are runs of bytes < 0x80 summed until the next status
  byte (zero deltas are simply omitted), at 1/120 second ticks;
  note-ons carry note, velocity, then a VLQ duration. (The older
  claim here, "two delta-time bytes per event", was wrong for this
  corpus.)
- Includes a `TIMB` ("timbre list") chunk per song: LE u16 patch
  count, then (patch, bank) pairs: which MT-32 patches the song
  wants pre-loaded. GSEQ/LSEQ only; PSEQ never carries TIMB.
- Includes RBRN chunks (the branch-point table for adaptive music;
  acronym expansion unconfirmed): LE u16 count, then per entry
  (LE u16 branch id, LE u32 tick), ids sequential from 1, ticks
  increasing 120 Hz positions in the EVNT stream.

### Sequence chunk layout (verified 2026-10-06)

Every *SEQ payload (GSEQ, LSEQ, PSEQ, CSEQ, FSEQ) walks as:

```
FORM "XDIR"              IFF sizes big-endian
  INFO (size 2)          LE u16 sequence count, always 1
  CAT "XMID"
    FORM "XMID"
      [TIMB]             GSEQ/LSEQ only
      [RBRN]             tracks with branch points
      EVNT               always present, always last
```

EVNT chunks may carry trailing pad bytes after the EOT meta
(observed on CSEQ/1000: `ff 2f 00 00`); parsers must stop at EOT,
not expect a status byte after the final delta run.

Playback follows the branches. The engine's Mel library ("Mel Real
Mode Version 2.0.9b" string in DSUN.EXE at file 0x4c76c; branch
functions `MelBranchTo` / `MelBreakLoopAndBranchTo` and state
`gMelCurrentBranch` / `gMelIndirectControlArray` in the DSO symbol
dump) wraps branched songs in XMIDI controller loops (0x74 FOR /
0x75 NEXT) and selects a loop-wrap point with controller 0x78
(Sequence Branch Index); every branched track's EVNT carries exactly
one 0x78 event per RBRN entry, values matching the ids. Controllers
0x73 / 0x77 (Indirect Control / Callback) are engine polls. The
sound drivers never see chunk names: Mel parses the forms itself.

DS1 ships this live: 63 RBRN chunks in RESOURCE.GFF (one per
sequence kind for each track 1..23 except the short cues 7 and 17;
none in the four CINE.GFF themes or the CSEQ clock). DS2 content
ships none: the floppy RESFLOP.GFF XMIs are TIMB+EVNT only and the
GOG build's music is redbook CD audio, though the DS2-lineage engine
retains the branch machinery.

Conversion to standard MIDI is implemented by the public-domain
`xmi2mid` (libgff bundles it; it skips every non-EVNT chunk, so a
straight port flattens the adaptive loops). OpenDS's converter is
`tools/xmi2mid/`: it emits the linear pass plus a JSON sidecar
(branches, loop spans, TIMB) instead of guessing, so a port's music
director can reproduce the adaptive behaviour.

The same XMI source is rendered into per-driver chunks (PSEQ/FSEQ/LSEQ/
GSEQ) at content-build time: i.e., the driver-specific re-renders are
authored, not synthesized live. Each chunk contains the same musical
content adapted to the target hardware's timbre map.

### Measured presence (2026-10-06, audio-extract over all 120 corpus containers)

Totals across the corpus: BVOC 815 chunks (11.5 MiB, 1386.9 s decoded
audio), GSEQ 63, FSEQ 34, LSEQ 27, PSEQ 27, CSEQ 6. Every *SEQ
payload observed (all 157) is a `FORM/XDIR` XMI directory wrapping
`CAT/XMID` song forms; CSEQ is the same directory shape at ~75 bytes.
Decoded rates: 499 of the 815 samples are 8000 Hz (SR byte 131)
and 316 are 10989 Hz (SR byte 165) - the 10989 set is DS2's
RESOURCE.GFF (158 samples) and its byte-identical cd10 twin - all
8-bit mono throughout.

| container | sequence chunks | digital samples | note |
|---|---|---|---|
| DS1 `RESOURCE.GFF` | GSEQ/LSEQ/PSEQ ids 1..23 (23 each) + CSEQ 1000 | BVOC ids 1..130, 111 present (260.5 s) | no MSEQ, no FSEQ, no FVOC anywhere in DS1 |
| DS1 `CINE.GFF` | GSEQ/LSEQ/PSEQ ids 26..29 + CSEQ 1000 | - | cinematic themes |
| DS2 GOG `RESOURCE.GFF` | CSEQ 1000 only | BVOC ids 0..231, 177 present (284.5 s) | music is CD redbook (audio-routing.md 1); no sequence chunks at all |
| DS2 floppy/HotU `RESFLOP.GFF` | GSEQ ids 1..20 (18 present) + FSEQ ids 1..19 (17 present) + CSEQ 1000 | BVOC ids 0..231, 175 present (278.7 s) | the floppy line's MIDI music; replaced by redbook on CD |

MSEQ is the only audio kind never seen in any held artifact (the
documented-kinds-never-seen list in format-coverage.md). Note DS1's
digital-sample ids are 1-based while DS2's start at 0; audio-routing.md
3's DS2 rule (sound id N -> BVOC id N+1) would leave BVOC 0
unreferenced by any sound id, so either 0 is a reserved slot or the
routing rule has a one-off edge: not settled here.

### BVOC payload structure (verified 2026-10-06, all 815 corpus chunks)

Every BVOC payload is a complete Creative Voice File: the 26-byte
header (`Creative Voice File\x1a`, data offset 26), then exactly one
type-1 sound-data block (pack byte 0 = 8-bit unsigned PCM, mono;
SR byte 131 = 8000 Hz on DS1 and 499 of DS2's samples, SR byte
165 = 10989 Hz on the other 316) and the type-0 terminator. Two
chunks across the GOG pairs additionally carry a type-6/type-7
repeat-start/end pair.
All 815 chunks decode cleanly (audio-extract 0.1.0; 1386.9 s of
audio total). No type-3 silence, type-9 new-format, or extended
blocks appear anywhere in the corpus.

## 6. Question ledger (all closed as of 2026-10-07)

Resolved questions are documented inline. None remain open.

- ~~The exact layout of segmented chunk lists.~~ Resolved (see
  "Segmented chunk resolution" above). Verified on the full DS1
  and DS2 corpus.
- ~~The exact layout of a **non-empty free list**.~~ Resolved
  (see "The free list" section above): the TOC's last 2 bytes
  are a u16 free-entry count and `free_list_offset ==
  toc_length − 2 − (free_count × 8)`. Most shipped files carry
  an empty list; GPLDATA.GFF (DS2) is the populated example
  (16 entries).
- ~~Semantics of `file_flags` and `data0`.~~ Pinned 2026-09-05
  (see the header-field table above): `file_flags` is 0 on
  most GFFs and 8 on every DS2 region GFF; `data0` is a
  per-file sentinel (1 non-region, 3 DS1 regions, sequential
  3..22 across the DS2 regions in file order). Both remain
  not load-bearing for read; a future writer should match
  the pinned per-corpus values.
- **Compression**: CLOSED 2026-10-07 as "no chunk-level
  compression exists". The evidence: every file in the corpus
  (both GOG trees, saves included, every archive-org tree) parses
  as a plain GFF with no decompression stage in any reader; the
  one "Uncompress" string in either binary
  ("Failed Uncompress in Loadgamefromdisk") was resolved
  2026-09-05 to the GPLI directory readers' allocation-failure
  message, not a compression path (roadmap 5.6.2); and the
  engine's chunk readers (load_resource and its consumers, traced
  across the overlay work) return raw payloads. What large files
  do carry is intra-chunk encoding: the RLE bitmap codecs inside
  BMP/CBMP and the packed-string codec inside GPL strings, both
  documented per kind. A writer never compresses.
