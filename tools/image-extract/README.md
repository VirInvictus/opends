# image-extract

Extract and pack Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`,
`BMAP`, `OMAP`, `TILE`). The `image-extract` binary decodes any
frame of any bitmap chunk to a palette-indexed PNG; the
`image-pack` binary is the inverse encoder, turning an edited
PNG back into a DS1 RLE chunk you can replace into a real game
file. Together they are the sprite-modding loop.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gff-edit` for GFF I/O and `png` for PNG decoding /
encoding.

## Packing (`image-pack`)

The companion binary reads a palette-indexed 8-bit PNG and
writes a DS1 RLE-encoded bitmap chunk. The chunk
format is universal across `BMP `, `PORT`, `ICON`, `BMAP`,
`OMAP`, `TILE`; the engine reads PLNR and PLAN too, so DS1 RLE
output works for any of them.

```sh
# Extract a sprite for editing.
image-extract RESOURCE.GFF --kind ICON --id 2000 --frame 0 \
    -o sprite.png

# Open sprite.png in your editor of choice. Save as palette-
# indexed 8-bit PNG using the *same palette* as the chunk's
# PAL / CPAL source. For example, with ImageMagick:
#   convert sprite.png -dither None -map original-palette.png \
#       PNG8:sprite-edited.png

# Pack the edited PNG and pipe straight into gff-cat replace.
image-pack sprite-edited.png \
    | gff-cat replace RESOURCE.GFF ICON 2000 - -o patched.gff
```

`--frames-dir <dir>` packs every `*.png` in sorted-filename
order as a multi-frame chunk. Round-trips the v0.3.0
`image-extract --frames-all` output.

The encoder cap test: 883 / 883 DS1 RLE frames across the
DS1 + DS2 corpus pack → re-parse → decode pixel-identical to
the original. PLNR (855) and PLAN (237) frames are skipped at
the encoder; v0.4.0 doesn't ship encoders for those formats
(and doesn't need to: the engine reads all three).

### Library API

```rust
use image_extract::{encode_bitmap_rle, Frame, FrameType};

let frame = Frame {
    width: 32,
    height: 32,
    frame_type: FrameType::Ds1Rle,
    indices: my_palette_indices, // 32 * 32 bytes
};
let chunk_bytes: Vec<u8> = encode_bitmap_rle(&[frame])?;
```

### Caveats

- **Palette responsibility is the modder's.** The chunk
  doesn't store palette information; it stores indices into a
  separate `PAL ` / `CPAL` chunk. An edited PNG with the wrong
  palette will render in-game with wrong colours even when the
  indices are correct. Use ImageMagick's `-map` or your
  editor's "remap to palette X" to align before packing.
- **Composited spritesheets are rejected**. A frame with
  `frame_type == FrameType::Unknown(b"STRP")` is the
  v0.3.0 `composite_horizontal_strip` output; that's a
  rendered artefact, not a real game frame, and packing it
  would silently corrupt animation timing. Slice the
  spritesheet back into per-frame PNGs first, then use
  `--frames-dir`.
- **Wide rows split into multiple spans.** Rows whose RLE

## Limitations

- **Wide rows split into multiple spans.** Rows whose RLE
  payload exceeds 255 bytes (the single-span
  `compressed_length` cap) are split on code boundaries; the
  engine's decoder reads them transparently. Mentioned only
  for completeness; not something a modder ever sees.

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
