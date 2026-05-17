# image-extract

Extract Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`, `BMAP`,
`OMAP`, `TILE`) as palette-indexed PNG. The first visual modder
tool in the OpenDS toolkit: see what's inside the game's image
chunks without firing up the engine.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gff-edit` for GFF I/O and `png` for PNG encoding.

## What `image-extract v0.3.0` ships

Multi-frame export. v0.2.0 / v0.2.1 decoded every frame of every
multi-frame chunk under the existing `--all` path, but the
single-chunk path only emitted `--frame N`. v0.3.0 adds two
explicit multi-frame entry points and a new library helper that
downstream tools (region-render v0.6.0's animated entities) can
call directly.

### Library

```rust
let frames: Vec<Result<Frame>> = bmp.decode_all_frames();
let strip: Option<Frame> = composite_horizontal_strip(&frames_ok);
```

`decode_all_frames` returns one `Result<Frame>` per frame index
so callers can keep the good frames when one frame is malformed
(the DS1 `RESOURCE.GFF:ICON/0x7f9` frame-2 case).

`composite_horizontal_strip` lays frames out left-to-right, top-
aligned, padded with palette index 0; the composite is itself a
`Frame` with `frame_type = Unknown("STRP")` so a caller can
tell a spritesheet apart from a real game-encoded frame.

### CLI

```sh
# Single chunk, every frame as a separate PNG:
image-extract <file> --kind ICON --id 2000 --frames-all -o out-dir/
# wrote 4 frames into out-dir/ as ICON-2000-frame-{0..3}.png

# Single chunk composited into a horizontal spritesheet:
image-extract <file> --kind ICON --id 2000 --spritesheet \
    -o icon-2000-sheet.png
# wrote icon-2000-sheet.png (236x18, 4 frames)

# Bulk: every chunk gets its own spritesheet:
image-extract <file> --all --spritesheet -o sheets-dir/
```

`--frames-all` and `--spritesheet` are mutually exclusive on a
single chunk. With `--all`, `--spritesheet` switches the bulk
emitter from per-frame PNGs to one spritesheet per chunk.

Corpus stats unchanged from v0.2.1: 1,975 / 1,976 frames decode
across the DS1 + DS2 corpus (one expected failure pinned in
`tests/corpus_smoke.rs`).

## What `image-extract v0.2.1` ships

Diagnostic + regression test, no decoder change. The single
remaining `FrameOutOfBounds` failure has been root-caused, the
test pins it as the only expected failure, and the README
documents it as a known limitation. The decoder is still at the
v0.2.0 99.95% decode rate.

### Known limitation: DS1 `RESOURCE.GFF` `ICON / 0x7f9` frame 2

This is the one chunk of 1,976 corpus frames that fails. The
chunk is 734 bytes; its header declares 3 frames, with frame
offsets `0x12 / 0x17 / 0x2d9` (18, 23, 729). Frames 0 and 1
decode normally (90 x 7 Ds1Rle). Frame 2's declared offset
(729) leaves only 5 bytes for the 9-byte frame header. The
chunk is **malformed in the GOG ship**: it claims a frame the
data doesn't fit. The engine almost certainly never reads frame
2 (or it'd crash), so this is dead data that survived into the
1.10 build.

The decoder behaviour is correct: report `FrameOutOfBounds` for
frame 2, decode frames 0 and 1 fine. v0.2.1 strengthens
`tests/corpus_smoke.rs` to pin this as the *only* expected
failure; any new chunk that fails the decoder breaks the test.
Removing the `EXPECTED_FAILURES` entry would also break the
test, which is the right behaviour if a future decoder
improvement makes this chunk decode (the patchnote moment
that demotes this to "no known limitations").

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
