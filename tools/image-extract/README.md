# image-extract

Extract Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`, `BMAP`,
`OMAP`, `TILE`) as palette-indexed PNG. The first visual modder
tool in the OpenDS toolkit: see what's inside the game's image
chunks without firing up the engine.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gff-edit` for GFF I/O and `png` for PNG encoding.

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
