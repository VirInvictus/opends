# region-render

Render a Dark Sun region GFF's full visual stack: background
tiles, walls, and entity sprites: to a single palette-indexed
PNG, optionally animated and bundled as a GIF. See what an
in-game region actually looks like without firing up the engine.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gff-edit` for GFF I/O and `image-extract` for the
`Palette` + `Bitmap` decoders. PNG output uses the `png` crate.

## What it renders

- **Tiles** (`RMAP`/`MAP ` + `TILE`): the background terrain.
- **Walls** (`GMAP` lower 5 bits + `WALL` chunks, `--walls`):
  the occluding wall sprites, composited per row.
- **Entities** (`ETAB` + `OJFF`/`BMP `, `--entities`): the
  region's placed objects and monsters at their coordinates.
- **Animation** (`--animate-entities`, `--frame-count N`):
  renders the entity layer as a frame sequence; `--gif` bundles
  it into a single animated GIF via `ffmpeg` (default 8 fps,
  `--gif-fps N` overrides). Frames stay in a sibling
  `<stem>-frames/` directory for editing reuse.

## Usage

```sh
# Render a DS2 region (palette comes from the inline `PAL ` chunk):
region-render .games/ds2/RGN001.GFF -o rgn001.png

# Render a DS1 region (default falls back to RESOURCE.GFF:PAL:1000):
region-render .games/ds1/RGN02.GFF -o rgn02.png

# Pick a different palette explicitly:
region-render .games/ds1/RGN02.GFF -o rgn02.png \
    --palette .games/ds1/RESOURCE.GFF:CPAL:200

# Load a raw 768-byte palette file:
region-render .games/ds1/RGN02.GFF -o rgn02.png \
    --palette-file scratch/custom.pal
```

The CLI prints a summary on stderr: rendered dimensions, source
map chunk kind (`RMAP` or `MAP `), how many `RMAP` bytes
referenced a missing `TILE` id, and how many `TILE` chunks failed
to decode.

## Palette source rules

| Precedence | Source                                              |
|------------|-----------------------------------------------------|
| 1          | `--palette-file <path>` (raw 768 bytes)             |
| 2          | `--palette <gff>:<KIND>:<id>` (explicit GFF chunk)  |
| 3          | Inline `PAL ` (lowest id) in the region GFF         |
| 4          | Inline `CPAL` (lowest id) in the region GFF         |
| 5          | Sibling `RESOURCE.GFF:PAL :1000` (DS1 fallback)     |
| 6          | Error with a discoverability hint                   |

DS2 region GFFs ship an inline `PAL ` (typically id `1`), so the
default just works. DS1 region GFFs ship no inline palette and
fall through to the `RESOURCE.GFF` lookup.

## Empirical results

GOG 1.10 corpus (53 region GFFs total):

| Game | Regions | Default palette source             | Notes                                            |
|------|--------:|------------------------------------|--------------------------------------------------|
| DS1  | 35      | `RESOURCE.GFF:PAL :1000` fallback  | See palette caveat below.                        |
| DS2  | 18      | Inline `PAL ` (id `1`)             | Renders cleanly with recognisable terrain.       |

The corpus smoke test ran `RegionMap::from_gff` + `render_indexed`
on every region: 0 missing-tile bytes across the full corpus
(every `RMAP` / `MAP ` byte resolved to a present `TILE` chunk),
18 soft `TILE` decode failures across 18 DS2 regions (sentinel
`TILE` id `0` of 15 bytes; not referenced by `MAP `, so harmless).

### DS1 palette caveat

DS1 stores only four palettes in `RESOURCE.GFF`: `PAL :1000`,
`PAL :1001`, `CPAL:200`, `CPAL:300`. None are keyed on region
number, and the reference Java tool (`dsun_music/region-tool`)
expects an explicit `--pal` path in practice. the default falls back to
`PAL :1000`; the rendered output is structurally correct but the
"off-camera" tile cells render with the palette's high-index
colours (visibly pink/magenta on `PAL :1000`). The interior
playable area of the region renders with plausible terrain
colours.

Curators chasing DS1 region screenshots should try the
`--palette` overrides above; `CPAL:200` and `CPAL:300` give a
more uniformly Athasian look at the cost of less colour
variation. Per-region palette selection is a known unknown for
v0.2+.

## Library

```rust
use gff_edit::Gff;
use region_render::{RegionMap, inline_palette};

let gff = Gff::open("RGN001.GFF")?;
let palette = inline_palette(&gff)?
    .expect("DS2 regions ship an inline PAL chunk");
let region = RegionMap::from_gff(&gff, palette)?;
region.write_png(std::path::Path::new("rgn001.png"))?;
```

`RegionMap::render_indexed()` returns a `Vec<u8>` of length
`2048 * 1568` (palette indices) if you want to composite further
before encoding.

## Build

Workspace member of the OpenDS toolkit:

```sh
cargo build --release -p region-render
```

Run `cargo test --release -p region-render` for unit tests plus
the corpus smoke test (the latter no-ops if `.games/` is absent).

## Credits

`RegionTool.java` from `JohnGlassmyer/dsun_music` (MIT) is the
authoritative reference for region geometry and chunk roles;
constants (`128`, `98`, `16`) come straight from there. See
[`../../CREDITS.md`](../../CREDITS.md) for per-feature attribution.
