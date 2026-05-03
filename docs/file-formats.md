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

Verified locally on every GFF in both games:

```
offset  size  field
  0      4    magic = "GFFI"  (0x47 0x46 0x46 0x49)
  4      2    version = 3     (little-endian)
  6      2    header size = 0x1C
  8      4    offset of TOC (in bytes from start of file, little-endian)
  ...   ...   (further header fields TBD; total 0x1C bytes)
```

After the header comes the chunk data area, then the TOC at the offset
recorded in bytes 8–11.

The TOC is an indexed list of (chunk-type FOURCC, resource ID, offset,
length) entries — exact layout to be confirmed against libgff's
`gff_load_index()` implementation when we begin writing the parser.

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

These are answered by reading libgff source rather than guessing:

- Exact TOC entry layout (we know the offset; we don't know the size of
  each TOC entry yet).
- Whether DS1 and DS2 use identical TOC encodings (likely yes; needs
  confirmation).
- Compression: is any chunk type stored compressed? The DOS-era
  expectation is "no" (the disk format is the in-memory format), but
  large GFFs (5.7 MB+) may have RLE bitmaps internally.
- The exact contents of `DARKRUN.GFF` (991 bytes — too small to be
  game-state; likely a runtime configuration stub).
