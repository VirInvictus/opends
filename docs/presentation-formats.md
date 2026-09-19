# The presentation stack: images, UI resources, audio, cinematics

The asset layer of the mining campaign (wave 4, 2026-09-16),
verified on the GOG 1.10 corpus with the repo's own decoders as
the authority (tools/image-extract 0.5.0 implements the container
and all three frame codecs, corpus-tested; cite its
`src/lib.rs`). This is what a faithful Godot presentation layer
consumes and what it still has to decode itself.

## 1. Images

Universal bitmap container (BMP/CBMP/ICON/PORT/TILE/WALL and BMA
segments): `u32 size, u16 frame_count, u32 frame_offsets[]`,
then frames of `u16 width, u16 height` + codec tag (`PLNR`/
`PLAN`) or a DS1 RLE stream. Three codecs, all implemented and
round-trip proven (883/883 DS1 RLE frames pixel-identical
through the encoder):

- DS1 RLE: bottom-up rows, per-row spans, even-code literals /
  odd-code repeats (length code/2 + 1, cap 128).
- PLNR: bit-packed dictionary symbols with a leading-0 RLE
  escape (855/855 corpus frames decode).
- PLAN: plain dictionary bitmap (port of dsun_music's
  `readPlanarImageFrame`, RE'd at DSUN.EXE 0x1A1B0).

Palette: PAL/CPAL = 768 bytes of 6-bit RGB. One known bad frame
corpus-wide (DS1 RESOURCE ICON 0x7f9 frame 2, noted in
image-extract). VGA colour cycling is implemented in
region-render 0.8.0 (four boot-time ranges, DS1). DS2 has NO
palette cycling: the pump machinery ships but nothing ever
registers a range (asset-bindings.md 4).

Per-kind facts: BMP world sprites 2,543 DS1 / 3,974 DS2; TILE
16x16 tiles 6,370 / 3,043; WALL 664 DS1-only; ICON 292 / 400
(1-4 frames, mostly 16x16, plus some 300x10 bars); PORT
portraits 112 x 32x32 (DS1, RLE) vs 178 x 72x72 (DS2, PLNR);
CBMP 136 DS2-only (creature colour-map anims). The one
undecoded image family: BMA cinematic frames (section 4).

## 2. UI resources

Every UI chunk starts with a 12-byte resource header (`u32
type, u32 len, u32 id`) followed by a shared 72-byte frame
struct (flags, type, three rects, size, border_bmp, background
BMP, 24-byte title). The struct definitions are libgff
`gui.h`/`gui.c`, verified on bytes:

- **WIND** (27 DS1 / 28 DS2) is the window TREE: a 138-byte
  region block, window geometry, frame, then `itemCount` x 30
  -byte items naming the contained chunks by (type FOURCC, id,
  two rects, flags). Validated exactly on all 55 windows
  (`(len - 261) == 30 * itemCount`). Example: WIND/3000 =
  fullscreen + ACCL 8100 + four BUTNs; WIND/13500 holds 89
  items.
- **BUTN** (139 per game): frame + userid, icon/text offsets,
  icon_id (a verified ICON chunk reference: the button face),
  hotkey, and text ("DROP", "SPLIT", "SELL", "MORE", "INFO"...).
- **APFM** (97 per game, exactly 116 bytes): static
  panel/frame resources (event filter, snap rect) referenced by
  WIND items; the survey's "palette-family" speculation is
  wrong.
- **FONT**: one chunk per game, `RESOURCE.GFF FONT/100`, 8,299
  bytes, BYTE-IDENTICAL between DS1 and DS2: 256 entries, height
  9, char offsets at +264, glyphs (u16 width + width x height
  index bytes) from +776; ink palette indices 0xFE/0x14.
- EBOX (168 bytes) and ACCL (accelerator table) match libgff.

RESOLVED 2026-09-19 ([`asset-bindings.md`](asset-bindings.md)):
the item inventory ICON id is the OJFF record's `bmp_id` field
(numerically the item's world-sprite id, read from the ICON chunk
type and cached per template); spell icons are `20999 +
spell_id`; the PORT id is a per-dialog-line operand of the
dialog print service, sourced from the GPL opcode arguments, not
a field of any record table; CBMP ids share the BMP id space,
selected by a boolean load flag.

## 3. Audio

- **Music, DS1**: XMI sequences in-GFF: RESOURCE carries GSEQ/
  LSEQ/PSEQ ids 1..23 (three parallel per-driver renditions),
  CINE.GFF adds 26..29 plus a CSEQ timer track. The GPL music
  operand space is those ids.
- **Music, DS2**: the CD release replaced XMI with 40 redbook
  tracks (`MUSIC/Track02..41.ogg`, 99.1 MB; cuesheet
  `game.ins`). `DJ.DAT` (231 B, byte-identical floppy/CD) is
  the music-slot table: 38 six-byte records over 35 slots; the
  floppy's RESFLOP.GFF carries GSEQ 18 + FSEQ 17 and public
  MIDI conversions exist. Record field semantics open.
- **Timbre banks**: DS1 GM1/GM2.BNK are a custom SSI bank (not
  the Roland format): a special first record, ~33 patch records
  of ~66 bytes with offset tables into timbre data; consumed by
  the MIDI TSR chain. STDPATCH.AD is the AdLib/OPL patch table
  (both games). AIL/MEL drivers ship as `ADV ` chunks in the
  GFFs.
- **Sound effects**: BVOC chunks are raw Creative VOC files
  (verified: header, version 0x010A, 8-bit PCM blocks): DS1 111
  (1.5 MB); DS2 177 (3.0 MB) PLUS external VOCs: 30
  `SOUNDnnn.VOC` and 117 `SPCHnnn.VOC` speech files (29 MB,
  separate id space), loaded via DS2.EXE's `%sSOUND%03u.VOC` /
  `%sSPCH%u.VOC` templates. The GPL Sound/Music opcodes pass
  one word each to the audio services.

## 4. Cinematics

- **DS1**: CINE.GFF is self-contained: BMA 11 (2.5 MB, ids
  2..12), ACF scripts 13 (pairs with BMA N), 19 static
  320x200 stills, palettes, cinematic music (GSEQ 26..29). BMA
  structure pinned: each chunk is a chain of standard bitmap
  containers (1..92 frames of 320x200); frame bodies are a
  byte-opcode stream (keyframes + ~5-byte deltas) whose codec
  is the ONE undecoded piece of the image family, with ACF's
  script opcodes beside it (no public decoder exists; the
  engine path is the `CINE.GFF`/`BMA `/`ACF ` FOURCC use in
  DSUN.EXE).
- **DS2**: five external files verified as standard Autodesk
  FLI (magic 0xAF11, 320x200x8, ~10 fps, 284-1,398 frames,
  19.5 MB total), engine-driven from `%c:\CINE\%u.FLI`; the
  flagged `flic` crate handles them.

## 5. Asset census (counts / bytes)

| Class | DS1 | DS2 |
|---|---|---|
| World sprites (BMP) | 2,543 / 6.2 MB | 3,974 / 7.1 MB |
| CBMP anims | - | 136 / 1.4 MB |
| Tiles / walls | 6,370 / 2.2 MB + 664 / 0.3 MB | 3,043 / 1.0 MB + 0 |
| Icons / buttons / windows / frames | 292 + 139 + 27 + 97 | 400 + 139 + 28 + 97 |
| Font | 1 / 8.3 KB (identical both games) | same |
| Portraits | 112 / 127 KB (32x32) | 178 / 685 KB (72x72) |
| Music | 27 XMI slots x3 renditions / ~0.9 MB | 40 OGG / 99.1 MB + DJ.DAT |
| SFX | 111 BVOC / 1.5 MB | 177 BVOC / 3.0 MB + 147 VOC files / 34 MB |
| Cinematics | BMA 11 + ACF 13 + 19 stills / 2.9 MB | 5 FLI / 19.5 MB |

The one caveat this doc supersedes: `file-formats.md` section 1
still marks image frame layout/RLE as "to be confirmed";
image-extract 0.5.0's implementation is the confirmed answer.
