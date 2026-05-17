# image-extract

Extract Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`, `BMAP`,
`OMAP`, `TILE`) as palette-indexed PNG. The first visual modder
tool in the OpenDS toolkit: see what's inside the game's image
chunks without firing up the engine.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gff-edit` for GFF I/O and `png` for PNG encoding.

## What `image-extract v0.2.0` ships

**PLAN frame format**, plus a fix to PLNR's bit-chomp that
unblocks the cross-byte cases libgff's "split bits!" check
rejected. Corpus coverage jumps from 67% (1,328 / 1,976 frames)
to **99.95% (1,975 / 1,976)**.

PLAN format (RE'd by `dsun_music`, MIT, from DSUN.EXE offset
0x1A1B0):

```text
frame_offset + 0:    u16 LE width
frame_offset + 2:    u16 LE height
frame_offset + 4:    0xFF marker
frame_offset + 5:    4-byte tag "PLAN"
frame_offset + 9:    u8 bits_per_symbol
frame_offset + 10:   dictionary[1 << bits_per_symbol] u8
(after dict):        bit-packed symbol stream, big-endian
```

Each pixel reads `bits_per_symbol` bits from the stream as a
dictionary index; the dictionary value is the palette index.
Dictionary value 0 means "transparent" — the output buffer
keeps palette index 0 there (the conventional void index in DS
palettes). PLAN has no RLE on the symbol stream (each pixel is
one symbol), unlike PLNR.

PLNR fix: v0.1.0 used libgff's 4-bit "rotated" chomp which
fails (returns 0 + a "split bits!" error) when a symbol read
crosses a byte boundary. v0.2.0 routes PLNR through the same
standard big-endian bit chomper PLAN uses — the chomper happily
crosses byte boundaries, and 410 previously-skipped PLNR frames
now decode cleanly.

| frame type | v0.1.0 decoded | v0.2.0 decoded |
|------------|---------------:|---------------:|
| DS1_RLE    | 883            | 883            |
| PLNR       | 445            | 855            |
| PLAN       | 0              | 237            |
| **total**  | **1,328**      | **1,975**      |

The single remaining frame is a malformed chunk that fails
header parsing (`FrameOutOfBounds`). The decoder reports it
cleanly rather than panicking.

## What `image-extract v0.1.0` ships

Ports libgff's bitmap and palette code to Rust:

- **Palette parser** for `PAL ` and `CPAL` chunks (768 bytes =
  256 × RGB 6-bit, scaled to 8-bit by libgff's
  `intensity_multiplier = 4`).
- **Bitmap header parser**: 6-byte preamble + `u16 frame_count`
  at +4 + `u32` per-frame offset table at +6.
- **DS1 RLE decoder**: per-row spans with even/odd code split
  (direct palette indices vs. repeat-single). The common case
  for PORT chunks (NPC portraits).
- **PLNR decoder**: bit-packed dictionary-coded format. Less
  common; used for some BMP / region tiles.
- **PNG writer**: 8-bit palette-indexed PNG via the `png` crate.

`PLAN` frames (libgff's `printf("PLAN not implemented!")`) are
not yet supported and return `UnsupportedFrameType`.

## Empirical results

Running against the GOG 1.10 release:

| Source | bitmap chunks | total frames | decoded |
|--------|--------------:|-------------:|--------:|
| DS1 GPLDATA.GFF | 112 PORT chunks | 112 | 112 (100%) |
| DS1+DS2 combined corpus | 1,334 | 1,976 | 1,328 (67%) |

The 648 skipped frames are mostly `PLAN` and other variants not
yet implemented; v0.2.0 will add support as the formats are RE'd.

## Usage

```sh
# Extract one frame:
image-extract <file> --kind PORT --id 1 -o port-1.png

# Extract a specific frame from a multi-frame chunk:
image-extract <file> --kind BMP --id 200 --frame 3 -o frame-3.png

# Pick a specific palette:
image-extract <file> --kind PORT --id 1 \
    --palette 200 --palette-kind PAL -o port-1.png

# Bulk extract every bitmap chunk under a directory:
image-extract <file> --all -o out-dir/
```

CLI defaults:

- `--kind BMP` (FOURCC; pads `BMP` → `"BMP "`).
- `--palette-kind PAL` (also pads). If `--palette` isn't given,
  picks the lowest-id `PAL ` chunk in the same GFF, falling back
  to the lowest-id `CPAL` chunk.
- `--frame 0` (the first frame).

Single-frame mode: `-o` is a file path (defaults to
`<KIND>-<ID>-<FRAME>.png` in the cwd if omitted).

`--all` mode: `-o` is a directory; each frame writes as
`<KIND>-<ID>-<FRAME>.png` under it. Errors per-frame are
logged to stderr; the run continues.

## Library

```rust
use image_extract::{Bitmap, Palette, write_png};

let chunk = gff.read(FourCC(*b"PORT"), 1).unwrap();
let pal_bytes = gff.read(FourCC(*b"PAL "), 200).unwrap();
let palette = Palette::from_bytes(pal_bytes)?;
let bmp = Bitmap::from_bytes(chunk)?;
let frame = bmp.decode_frame(0)?;
write_png("port-1.png".as_ref(), &frame, &palette)?;
```

## Build

```sh
cd /path/to/opends
cargo build -p image-extract --release
./target/release/image-extract .games/ds1/GPLDATA.GFF \
    --kind PORT --id 1 -o /tmp/port-1.png
```
