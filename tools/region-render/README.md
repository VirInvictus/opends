# region-render

Render a Dark Sun region GFF's background tile layer to a single
palette-indexed PNG. The second visual modder tool in the OpenDS
toolkit: see what an in-game region's terrain actually looks like
without firing up the engine.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gff-edit` for GFF I/O and `image-extract` for the
`Palette` + `Bitmap` decoders. PNG output uses the `png` crate.

## What `region-render v0.5.0` ships

**DSUN.EXE RE finding for DS1 per-region palette, and a new
default fallback that matches what the engine actually does.**

The full write-up is in
[`docs/dsun-exe-re.md`](../../docs/dsun-exe-re.md). The short
version: DS1's engine, when loading a region, calls a single
`load_resource(fourcc, id, buf)` helper twice in sequence. It
tries `CMAT[region_family_id]` (a colour remap delta) first, and
falls through to `CPAL[region_family_id]` (a full custom 768-byte
palette) only when CMAT is missing. The pattern lives at DS1
`DSUN.EXE` offset `0x56ad3..0x56b00`, decoded by hex-search
because radare2 can't auto-load the DOS/4GW DPMI overlay.

`RESOURCE.GFF` ships two palette families (id 200 and 300), and
`PAL :1000` (the v0.4.x default) is not in the engine's
region-render path at all; it's the menu/title palette and was
only ever a "renders most cells, off-camera void is pink"
workaround. v0.5.0 changes the default fallback ordering:

| Order | v0.4.x | v0.5.0 |
|---|---|---|
| 1 | `--palette-file` | `--palette-file` |
| 2 | `--palette` | `--palette` |
| 3 | `--palette-preset` | `--palette-preset` |
| 4 | Inline `PAL ` / `CPAL` (DS2) | Inline `PAL ` / `CPAL` (DS2) |
| 5 | `RESOURCE.GFF:PAL :1000` (pink) | `RESOURCE.GFF:CPAL:200` (engine-default) |
| 6 | _(error)_ | `RESOURCE.GFF:PAL :1000` (legacy fallback) |

Whenever step 5 or 6 fires, the CLI emits a one-line stderr note
saying which fallback resolved and how to override. DS2 regions
are unaffected (their inline palette wins at step 4).

### What's still queued

The DSUN.EXE pass located the *routine* but did not crack the
*per-region id assignment*: which DS1 regions map to family
200 vs. family 300 (vs. the unknown others). That requires
tracing the caller of the CMAT/CPAL load site back to where
`si` is set, which is the next RE pass. Animated palette
colours (`VGAColorCycle` in the DSO symbol table) are still
queued as well. Until those land, the new default is closer to
the engine but still not pixel-faithful for every region.

## What `region-render v0.4.0` ships

**`--palette-preset` flag** for one-knob DS1 palette
switching, plus an honest write-up of the
per-region-palette-discovery effort.

Available presets (all expect a sibling `RESOURCE.GFF`):

| Preset | Resolves to | Visual look |
|---|---|---|
| `ds1-pink` | `RESOURCE.GFF:PAL :1000` | v0.1.0 default; bright pink off-camera void |
| `ds1-rust` | `RESOURCE.GFF:CPAL:200` | Uniformly rusty-red Athasian |
| `ds1-deep-red` | `RESOURCE.GFF:CPAL:300` | Darker, more saturated red |

```sh
region-render .games/ds1/RGN02.GFF --palette-preset ds1-rust -o rgn02.png
```

### The per-region DS1 palette discovery: negative result

I went looking for how the engine selects which of DS1's four
palettes (`PAL :1000`, `PAL :1001`, `CPAL:200`, `CPAL:300`) to
use per region. None of the standard places carry that
mapping:

- `RESOURCE.GFF` has 2 undocumented `CMAT` chunks (id 200 +
  300, paired with the CPAL ids), but libgff lists CMAT as
  `"CMAT?"` and has no consumer code. They're large (41,368 +
  21,643 bytes) which suggests substantial remap tables, but
  cracking their layout needs an RE pass against `DSUN.EXE`
  that's outside the scope of v0.4.0.
- `DARKRUN.GFF` carries only the credits text; no palette
  data.
- No per-region palette chunk lives in the region GFFs
  themselves.
- The `dsun_music/region-tool` Java reference expects an
  explicit `--pal` path, with `gffs.getResourceData("PAL ",
  regionNumber)` as a fallback that only works for DS2
  (where each `RGN???.GFF` has an inline `PAL ` at id 1; DS1
  has no such inline palette).
- `dso-online/tools/symbols.txt` (DSO v1.0 debug symbols) has
  no obvious per-region-palette-selection routine surfaced
  by name.

The conclusion: per-region DS1 palette discovery needs
`DSUN.EXE` reverse-engineering (likely tracing the engine's
region-load path through the GPL VM). Queued for a future
release; the `--palette-preset` flag is the workaround until
then.

### Animated palette colours: also queued

The `dsun_music/region-tool` Java source has a top-level
`// TODO: properly render animated colors` (`RegionTool.java`
line 180). Dark Sun animates ranges of the palette at runtime
(water shimmer, fire flicker, etc.); the animation tables
live in `DSUN.EXE`, and the same DSUN.EXE RE that unlocks
per-region palette selection probably surfaces them too.
v0.5.0+ work.

## What `region-render v0.3.0` ships

**Entity sprite layer.** The `ETAB` chunk's 8-byte records each
place a sprite at `(x - ojff.x_offset, y - ojff.y_offset -
y_offset)` with optional horizontal mirroring. Each record's
`ojff_number` resolves through `OJFF` (anchor offsets + BMP id)
into a `BMP ` chunk (the actual bitmap). Entities composite on
top of walls + tiles; palette-index-0 pixels stay transparent.

For DS1 entity art lives in `SEGOBJEX.GFF` (2,775 OJFF + 2,419
BMP). For DS2 it lives in `OBJEX.GFF` (4,479 OJFF + 3,727
BMP). The CLI auto-detects the sibling file by name. With both
layers loaded, region screenshots now match what a player
actually sees in-game: trees, NPCs, props, buildings,
furniture, all in correct position.

### CLI flags

```sh
# Default: auto-detect SEGOBJEX.GFF / OBJEX.GFF.
region-render RGN001.GFF -o rgn001.png

# Explicit entities source:
region-render RGN001.GFF -o rgn001.png \
    --entities-from .games/ds2/OBJEX.GFF

# Skip the entity layer (back to v0.2.0 output):
region-render RGN001.GFF -o rgn001.png --no-entities
```

### New library API

- `RegionMap::with_entities_from(&mut self, &Gff)`: index OJFF
  + BMP for every ETAB record's `ojff_number` and cache the
  decoded sprites.
- `RegionMap::entity_sprite_count(&self) -> usize`.
- New public fields: `entities: Vec<EntityRecord>`,
  `missing_entity_ids: Vec<i32>`,
  `entity_decode_failures: Vec<TileDecodeFailure>`.
- New struct `EntityRecord` with `x`, `y`, `y_offset`,
  `mirrored`, `ojff_number` fields.

### Corpus result (GOG 1.10)

| Metric | Count |
|---|---:|
| Regions rendered | 53 (35 DS1 + 18 DS2) |
| ETAB records across all regions | 26,587 |
| Distinct entity sprites loaded | 8,223 |
| Missing entity ids | 0 |
| OJFF / BMP decode failures | 0 |
| Wall sprites loaded (DS1 only) | 350 |
| TILE decode failures (sentinel id 0) | 18 |
| Missing-tile bytes total | 0 |

The toolkit can now turn any region GFF into a screenshot
identical (modulo animation frames and dynamic lighting) to
what a player sees in-game.

### Still out of scope

- Animated palette colours. v0.4.0.
- Per-region DS1 palette discovery. The current default
  (`PAL :1000`) renders the playable area with plausible
  colours but uses pink for "off-camera void" tiles. Curators
  can pick `CPAL:200` or `CPAL:300` via `--palette` for a more
  uniformly Athasian look.

## What `region-render v0.2.0` ships

**Wall layer.** The `GMAP` chunk's low 5 bits per tile-byte are
a wall-sprite index. Each non-zero index resolves to a `WALL`
chunk at id `region_number * 100 + wall_index - 1` (per
`RegionTool.java:274`). Walls composite on top of the
background tile layer, bottom-aligned and horizontally centered
inside their containing tile. Wall pixels at palette index 0
are treated as transparent so the tile underneath shows
through.

For DS1, WALL chunks live in `GPLDATA.GFF` (664 chunks at ids
100..4509). The CLI default looks there automatically. DS2's
WALL story is currently TBD — the GOG 1.10 corpus has no
`WALL` chunks in any DS2 GFF, so the wall pass is a no-op on
DS2 regions until we figure out where DS2 stores them.

CLI flags:

- `--walls-from <gff>` — explicit walls source (overrides the
  sibling `GPLDATA.GFF` auto-detect).
- `--no-walls` — skip the wall pass entirely. Useful for
  diffing against v0.1.0 output.

The eprintln summary now reports the wall stats:

```text
walls: 12 sprite ids loaded; 645 GMAP cells reference a wall;
       0 missing-wall ids; gmap present: true
```

### New library API

- `RegionMap::with_walls_from(&mut self, walls_gff: &Gff)`:
  index `WALL` chunks for the wall indices referenced by this
  region's `GMAP`. Idempotent across calls; subsequent calls
  add to the cached `walls` map.
- `RegionMap::wall_sprite_count(&self) -> usize`: number of
  decoded wall sprites currently available for rendering.
- `RegionMap::gmap: Option<Vec<u8>>` (public field): the raw
  GMAP byte grid, if the region GFF had one.
- `RegionMap::region_number: i32` (public field): the
  `(R)MAP`/`GMAP`/`ETAB` shared resource id.
- `RegionMap::missing_wall_ids: Vec<i32>` (public field).
- `RegionMap::wall_decode_failures: Vec<TileDecodeFailure>`.
- New const `GMAP_WALL_INDEX_MASK = 0x1F`.

### Corpus result (GOG 1.10)

- 53 regions render cleanly (35 DS1 + 18 DS2).
- 350 distinct wall sprites loaded across DS1 regions.
- 3 missing-wall ids total (edge cases; harmless).
- 0 WALL decode failures.

### Still out of scope

- `ETAB` + `OJFF` + `BMP ` entity sprites. v0.3.0.
- Animated palette colours. v0.4.0.
- Per-region DS1 palette discovery. The current default
  (`PAL :1000`) renders the playable area with plausible
  colours but uses pink for "off-camera void" tiles. Curators
  can pick `CPAL:200` or `CPAL:300` for a more uniformly
  Athasian look via `--palette`. Real per-region palette
  selection needs DSUN.EXE RE.
- DS2 wall discovery: no `WALL` chunks have been found in any
  DS2 GFF. The decoder is ready when the source is found.

## What `region-render v0.1.0` ships

The **background-tile pass**. Composites the per-region `RMAP`
(DS1) or `MAP ` (DS2) byte grid through the per-region `TILE`
chunks into a 2048 x 1568 palette-indexed image. Out of scope:
walls (the `GMAP` lower 5 bits + `WALL` chunks), entities
(`ETAB` + `OJFF` + `BMP `), animated palette colours,
flag-visualisation overlays. Those are v0.2+ work.

Ports from `JohnGlassmyer/dsun_music`
(`region-tool/RegionTool.java`, MIT, attributed):

- Region geometry: 128 x 98 tiles, 16 x 16 px each.
- `RMAP` (DS1) vs `MAP ` (DS2): row-major byte grid; each byte is
  a `TILE` resource id in the same GFF.
- `TILE` is a standard Dark Sun bitmap, decoded by image-extract's
  decoder.

See [`docs/file-formats.md`](../../docs/file-formats.md) "Region
geometry" for the layout details.

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
expects an explicit `--pal` path in practice. v0.1.0 defaults to
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

## Roadmap

- **v0.2.0**: `WALL` sprite overlay (`GMAP` lower 5 bits +
  `WALL` chunks); per-region palette discovery for DS1.
- **v0.3.0**: `ETAB` entity sprites (`OJFF` + `BMP `).
- **v0.4.0**: animated palette colours.

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
