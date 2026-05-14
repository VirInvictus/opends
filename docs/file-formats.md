# File Formats

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

| FOURCC | Purpose                                       |
|--------|-----------------------------------------------|
| `RMAP` | Region tile map                               |
| `GMAP` | Region map flags (passability, height, etc.) |
| `ETAB` | Object entry table (entities placed in region)|
| `MONR` | Monsters by region IDs and level             |

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

## 3. External (non-GFF) files

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

## 4. XMI specifics

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

## 5. Open questions

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
