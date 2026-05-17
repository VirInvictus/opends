//! region-render: composite a Dark Sun region GFF's background
//! tile layer (and optionally its wall layer) into a single
//! palette-indexed PNG.
//!
//! The grid is 128 x 98 tiles, each 16 x 16 pixels, so a region
//! is exactly 2048 x 1568 pixels. The `RMAP` (DS1) or `MAP `
//! (DS2) chunk supplies a row-major byte array of tile resource
//! ids; each id resolves to a `TILE` chunk in the same GFF,
//! whose frame 0 is the 16x16 bitmap.
//!
//! v0.2.0 adds the wall layer. The `GMAP` chunk's low 5 bits per
//! tile-byte are a wall sprite index; each non-zero index looks
//! up a `WALL` chunk at id `region_number * 100 + wall_index -
//! 1` (per `RegionTool.java:274`). The wall is composited on
//! top of the tile layer, bottom-aligned and horizontally
//! centered inside its containing tile. Wall bitmaps' palette-
//! index-0 pixels are treated as transparent, so they don't
//! overwrite the tile underneath.
//!
//! For DS1, WALL chunks live in `GPLDATA.GFF`; the CLI default
//! is to look there. DS2's WALL story is TBD (no `WALL` chunks
//! observed in any DS2 GFF as of the GOG 1.10 corpus), so the
//! wall pass is currently a no-op on DS2 regions.
//!
//! Out of scope for v0.2: entities (`ETAB` + `OJFF` + `BMP `),
//! animated palette colors, GMAP flag visualisation, DS2 wall
//! discovery, per-region DS1 palette selection.
//!
//! See `docs/file-formats.md` "Maps and world > Region geometry"
//! for the layout this implements, ported from
//! `dsun_music/region-tool/RegionTool.java` (MIT, attributed).

use std::collections::BTreeMap;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use image_extract::{Bitmap, ImageError, Palette};
use thiserror::Error;

/// Tiles across the region grid (`RegionTool.java:167`).
pub const REGION_TILE_WIDTH: usize = 128;
/// Tiles tall (`RegionTool.java:168`).
pub const REGION_TILE_HEIGHT: usize = 98;
/// Each tile is 16 x 16 pixels (`RegionTool.java:169`).
pub const TILE_PIXEL_SIZE: usize = 16;
/// Region rendered width in pixels: 2048.
pub const REGION_PIXEL_WIDTH: usize = REGION_TILE_WIDTH * TILE_PIXEL_SIZE;
/// Region rendered height in pixels: 1568.
pub const REGION_PIXEL_HEIGHT: usize = REGION_TILE_HEIGHT * TILE_PIXEL_SIZE;
/// Total bytes in an `RMAP` / `MAP ` chunk: 12,544.
pub const REGION_MAP_BYTES: usize = REGION_TILE_WIDTH * REGION_TILE_HEIGHT;

const RMAP_KIND: FourCC = FourCC(*b"RMAP");
const MAP_KIND: FourCC = FourCC(*b"MAP ");
const TILE_KIND: FourCC = FourCC(*b"TILE");
const GMAP_KIND: FourCC = FourCC(*b"GMAP");
const WALL_KIND: FourCC = FourCC(*b"WALL");
const ETAB_KIND: FourCC = FourCC(*b"ETAB");
const OJFF_KIND: FourCC = FourCC(*b"OJFF");
const BMP_KIND: FourCC = FourCC(*b"BMP ");
const PAL_KIND: FourCC = FourCC(*b"PAL ");
const CPAL_KIND: FourCC = FourCC(*b"CPAL");

/// Low 5 bits of each `GMAP` byte = wall sprite index. The
/// upper 3 bits are flags (passability / height / interaction).
/// `RegionTool.java:172`.
pub const GMAP_WALL_INDEX_MASK: u8 = 0x1F;

#[derive(Debug, Error)]
pub enum RegionError {
    #[error("no RMAP or MAP chunk in region GFF")]
    MissingMap,
    #[error("RMAP/MAP chunk has wrong length: expected {expected}, got {actual}")]
    BadMapLength { expected: usize, actual: usize },
    #[error("no inline PAL/CPAL chunk in region GFF; supply one via --palette")]
    MissingPalette,
    #[error("decoding inline palette: {0}")]
    Palette(#[from] ImageError),
    #[error("png write: {0}")]
    Png(#[from] png::EncodingError),
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, RegionError>;

/// One 16x16 tile worth of palette indices, row-major top-down.
#[derive(Debug, Clone)]
struct Tile {
    pixels: [u8; TILE_PIXEL_SIZE * TILE_PIXEL_SIZE],
}

/// A region's background-tile state: the grid, the palette, and the
/// decoded tile bitmaps keyed by their `TILE` resource id.
pub struct RegionMap {
    /// Row-major grid; each byte is a `TILE` resource id. Length is
    /// always [`REGION_MAP_BYTES`].
    pub map: Vec<u8>,
    /// Whether the source chunk was `MAP ` (`true`, DS2) or `RMAP`
    /// (`false`, DS1). Cosmetic; both layouts are identical.
    pub used_map_kind: bool,
    /// Palette resolved by the caller (`from_gff` accepts an
    /// optional inline-preferred `Palette`, or the caller can pass
    /// `None` and let `region-render` try the GFF first).
    pub palette: Palette,
    /// Tile bitmaps keyed by resource id. Missing ids in this map
    /// are rendered as palette-index-0 cells.
    tiles: BTreeMap<i32, Tile>,
    /// How many bytes in `map` referenced an id with no usable
    /// `TILE` chunk in the GFF (either no chunk with that id, or
    /// the chunk failed to decode). Cosmetic; reported by the CLI.
    pub missing_tile_byte_count: u32,
    /// Distinct tile ids that `map` references but `tiles` does not
    /// have. Includes both "no chunk" and "decode failed" cases.
    pub missing_tile_ids: Vec<i32>,
    /// Decode failures recorded during `from_gff`. These TILE
    /// chunks exist in the GFF but couldn't be turned into a 16x16
    /// indexed bitmap. The corresponding ids are also in
    /// `missing_tile_ids` when referenced by the RMAP.
    pub tile_decode_failures: Vec<TileDecodeFailure>,
    /// Optional wall grid (the `GMAP` chunk). Per-tile byte; low
    /// 5 bits are the wall sprite index, upper 3 bits are flags.
    /// `None` when the region GFF had no `GMAP` chunk.
    pub gmap: Option<Vec<u8>>,
    /// The region's number (from `RMAP`/`MAP `/`GMAP`'s shared
    /// resource id). Used for `WALL` chunk lookup:
    /// `wall_id = region_number * 100 + wall_index - 1`.
    pub region_number: i32,
    /// Decoded wall sprites keyed by their `WALL` resource id.
    /// Variable dimensions (not 16x16 like tiles). Populated by
    /// `with_walls_from(...)`.
    walls: BTreeMap<i32, WallSprite>,
    /// Distinct wall ids referenced by GMAP that couldn't be
    /// resolved against the walls source GFF.
    pub missing_wall_ids: Vec<i32>,
    /// Per-WALL decode failures, same idea as
    /// `tile_decode_failures`.
    pub wall_decode_failures: Vec<TileDecodeFailure>,
    /// Parsed ETAB records (8 bytes each). Each places a
    /// sprite at `(x, y)` resolved through the `OJFF` table.
    /// Populated when the region GFF has an `ETAB` chunk.
    pub entities: Vec<EntityRecord>,
    /// Decoded entity sprites keyed by OJFF id. Populated by
    /// `with_entities_from(...)`. Sprites use whatever palette
    /// the region's tile layer is using; palette-index-0
    /// pixels render as transparent.
    entity_sprites: BTreeMap<i32, WallSprite>,
    /// OJFF ids referenced by ETAB but not found in the
    /// entities-source GFF.
    pub missing_entity_ids: Vec<i32>,
    /// Per-OJFF / per-BMP decode failures.
    pub entity_decode_failures: Vec<TileDecodeFailure>,
}

/// One entry from a region's `ETAB` chunk (8 bytes). Resolved
/// through OJFF to a sprite placed at `(x - ojff.x_offset,
/// y - ojff.y_offset - y_offset)`.
#[derive(Debug, Clone)]
pub struct EntityRecord {
    pub x: i16,
    pub y: i16,
    pub y_offset: i8,
    pub mirrored: bool,
    pub ojff_number: i16,
}

/// One decoded sprite, used for both walls and entities.
/// Variable dimensions, palette-index-0 pixels are
/// transparent. For entity sprites `x_offset` / `y_offset`
/// come from the OJFF chunk's anchor metadata (subtracted from
/// the ETAB record's position to find the top-left of the
/// sprite); walls leave both at 0.
#[derive(Debug, Clone)]
struct WallSprite {
    width: u16,
    height: u16,
    pixels: Vec<u8>,
    x_offset: i16,
    y_offset: i16,
}

/// Reason a `TILE` chunk couldn't be turned into a 16x16 tile.
#[derive(Debug, Clone)]
pub struct TileDecodeFailure {
    pub tile_id: i32,
    pub reason: String,
}

impl RegionMap {
    /// Read a region's tile grid + tile bitmaps from `gff`. The
    /// caller supplies the palette explicitly. Resolving the
    /// palette (inline `PAL ` vs external `RESOURCE.GFF`) is the
    /// CLI's job; the library stays pure.
    pub fn from_gff(gff: &Gff, palette: Palette) -> Result<Self> {
        // Pick whichever map chunk is present. Some DS2 regions
        // carry both kinds; in that case DS2-style `MAP ` wins
        // because that's what the engine actually reads on DS2.
        let (map_bytes, used_map_kind, region_number) =
            if let Some((b, id)) = read_first_with_id(gff, MAP_KIND) {
                (b, true, id)
            } else if let Some((b, id)) = read_first_with_id(gff, RMAP_KIND) {
                (b, false, id)
            } else {
                return Err(RegionError::MissingMap);
            };
        if map_bytes.len() != REGION_MAP_BYTES {
            return Err(RegionError::BadMapLength {
                expected: REGION_MAP_BYTES,
                actual: map_bytes.len(),
            });
        }
        let gmap = read_first(gff, GMAP_KIND).map(|b| b.to_vec());
        let entities: Vec<EntityRecord> = read_first(gff, ETAB_KIND)
            .map(parse_etab)
            .unwrap_or_default();

        // Index every TILE chunk in the GFF. Decode frame 0 once
        // per id (tiles in the corpus only have one frame anyway).
        // Per-tile decode failures are recorded but don't fail the
        // whole region: real corpus chunks include short sentinel
        // TILE entries (e.g. DS2 RGN001 TILE id=0 is 15 bytes) that
        // aren't actually referenced by the RMAP grid.
        let mut tiles: BTreeMap<i32, Tile> = BTreeMap::new();
        let mut tile_decode_failures: Vec<TileDecodeFailure> = Vec::new();
        for c in gff.chunks() {
            if c.kind != TILE_KIND {
                continue;
            }
            let bytes = gff.read_chunk(c);
            match decode_tile(c.id, bytes) {
                Ok(tile) => {
                    tiles.insert(c.id, tile);
                }
                Err(failure) => {
                    tile_decode_failures.push(failure);
                }
            }
        }

        // Summarise misses up front so the caller can report them.
        let mut missing_set: std::collections::BTreeSet<i32> = std::collections::BTreeSet::new();
        let mut missing_bytes = 0u32;
        for &b in map_bytes.iter() {
            let id = b as i32;
            if !tiles.contains_key(&id) {
                missing_bytes += 1;
                missing_set.insert(id);
            }
        }

        Ok(RegionMap {
            map: map_bytes.to_vec(),
            used_map_kind,
            palette,
            tiles,
            missing_tile_byte_count: missing_bytes,
            missing_tile_ids: missing_set.into_iter().collect(),
            tile_decode_failures,
            gmap,
            region_number,
            walls: BTreeMap::new(),
            missing_wall_ids: Vec::new(),
            wall_decode_failures: Vec::new(),
            entities,
            entity_sprites: BTreeMap::new(),
            missing_entity_ids: Vec::new(),
            entity_decode_failures: Vec::new(),
        })
    }

    /// Count of decoded wall sprites available for rendering.
    pub fn wall_sprite_count(&self) -> usize {
        self.walls.len()
    }

    /// Count of decoded entity sprites available for rendering.
    pub fn entity_sprite_count(&self) -> usize {
        self.entity_sprites.len()
    }

    /// Index `OJFF` + `BMP ` chunks from `entities_gff` for the
    /// OJFF ids referenced by this region's `ETAB`. Each
    /// `EntityRecord.ojff_number` resolves through `OJFF` to a
    /// `bmp_number` + sprite x/y offsets; the matching `BMP `
    /// chunk supplies the bitmap. `render_indexed` then
    /// composites those sprites on top of the wall layer.
    ///
    /// DS1 entity art lives in `SEGOBJEX.GFF` (2,775 OJFF +
    /// 2,419 BMP). DS2 entity art lives in `OBJEX.GFF` (4,479
    /// OJFF + 3,727 BMP).
    pub fn with_entities_from(&mut self, entities_gff: &Gff) -> Result<()> {
        if self.entities.is_empty() {
            return Ok(());
        }
        let mut needed: std::collections::BTreeSet<i32> = std::collections::BTreeSet::new();
        for ent in &self.entities {
            // The Java tool uses `ojffNumber < 0 ? -ojffNumber :
            // ojffNumber`; mirror that.
            let id = if ent.ojff_number < 0 {
                -(ent.ojff_number as i32)
            } else {
                ent.ojff_number as i32
            };
            needed.insert(id);
        }
        let mut missing: std::collections::BTreeSet<i32> =
            std::collections::BTreeSet::new();
        for ojff_id in needed {
            let Some(ojff_chunk) = entities_gff.find(OJFF_KIND, ojff_id) else {
                missing.insert(ojff_id);
                continue;
            };
            let ojff_bytes = entities_gff.read_chunk(ojff_chunk);
            let Some((bmp_number, x_off, y_off)) = parse_ojff(ojff_bytes) else {
                self.entity_decode_failures.push(TileDecodeFailure {
                    tile_id: ojff_id,
                    reason: format!("OJFF too short ({} bytes)", ojff_bytes.len()),
                });
                missing.insert(ojff_id);
                continue;
            };
            let Some(bmp_chunk) = entities_gff.find(BMP_KIND, bmp_number as i32)
            else {
                self.entity_decode_failures.push(TileDecodeFailure {
                    tile_id: ojff_id,
                    reason: format!("BMP id {bmp_number} not in entities GFF"),
                });
                missing.insert(ojff_id);
                continue;
            };
            let bmp_bytes = entities_gff.read_chunk(bmp_chunk);
            match decode_wall(ojff_id, bmp_bytes) {
                Ok(mut sprite) => {
                    // Reuse WallSprite shape, but stash the
                    // x/y offsets in two unused bits by
                    // smuggling through a side table. Simpler:
                    // expand WallSprite to carry offsets too.
                    sprite.x_offset = x_off;
                    sprite.y_offset = y_off;
                    self.entity_sprites.insert(ojff_id, sprite);
                }
                Err(mut failure) => {
                    failure.reason = format!("BMP id {bmp_number}: {}", failure.reason);
                    self.entity_decode_failures.push(failure);
                    missing.insert(ojff_id);
                }
            }
        }
        self.missing_entity_ids = missing.into_iter().collect();
        Ok(())
    }

    /// Index `WALL` chunks from `walls_gff` for the wall sprite
    /// ids referenced by this region's `GMAP`. Each non-zero
    /// wall_index `w` in `gmap` resolves to
    /// `WALL[region_number * 100 + w - 1]`.
    ///
    /// On DS1 the canonical `walls_gff` is the sibling
    /// `GPLDATA.GFF` (664 WALL chunks at ids 100..4509). On DS2
    /// no WALL chunks have been observed in the GOG 1.10 corpus;
    /// passing any GFF without matching ids is harmless and
    /// leaves `walls` empty / `missing_wall_ids` filled.
    pub fn with_walls_from(&mut self, walls_gff: &Gff) -> Result<()> {
        let Some(ref gmap) = self.gmap else {
            return Ok(()); // no GMAP -> no walls to draw
        };
        let mut needed: std::collections::BTreeSet<u8> = std::collections::BTreeSet::new();
        for &b in gmap.iter() {
            let idx = b & GMAP_WALL_INDEX_MASK;
            if idx != 0 {
                needed.insert(idx);
            }
        }
        let mut missing: std::collections::BTreeSet<i32> = std::collections::BTreeSet::new();
        for wall_index in needed {
            let wall_id = self.region_number * 100 + wall_index as i32 - 1;
            let Some(chunk) = walls_gff.find(WALL_KIND, wall_id) else {
                missing.insert(wall_id);
                continue;
            };
            let bytes = walls_gff.read_chunk(chunk);
            match decode_wall(wall_id, bytes) {
                Ok(sprite) => {
                    self.walls.insert(wall_id, sprite);
                }
                Err(failure) => {
                    self.wall_decode_failures.push(failure);
                    missing.insert(wall_id);
                }
            }
        }
        self.missing_wall_ids = missing.into_iter().collect();
        Ok(())
    }

    /// Render the background-tile layer (and wall layer, if
    /// `with_walls_from` populated any sprites) into a fresh
    /// palette-indexed buffer of size `REGION_PIXEL_WIDTH *
    /// REGION_PIXEL_HEIGHT`. Tiles referenced by id that don't
    /// exist in the GFF are drawn as palette index 0; walls are
    /// composited on top, with palette-index-0 wall pixels
    /// treated as transparent.
    pub fn render_indexed(&self) -> Vec<u8> {
        let mut out = vec![0u8; REGION_PIXEL_WIDTH * REGION_PIXEL_HEIGHT];
        // 1. Background tiles.
        for map_y in 0..REGION_TILE_HEIGHT {
            for map_x in 0..REGION_TILE_WIDTH {
                let tile_id = self.map[map_y * REGION_TILE_WIDTH + map_x] as i32;
                let Some(tile) = self.tiles.get(&tile_id) else {
                    continue;
                };
                let dst_x0 = map_x * TILE_PIXEL_SIZE;
                let dst_y0 = map_y * TILE_PIXEL_SIZE;
                for ty in 0..TILE_PIXEL_SIZE {
                    let src_row = ty * TILE_PIXEL_SIZE;
                    let dst_row = (dst_y0 + ty) * REGION_PIXEL_WIDTH + dst_x0;
                    out[dst_row..dst_row + TILE_PIXEL_SIZE]
                        .copy_from_slice(&tile.pixels[src_row..src_row + TILE_PIXEL_SIZE]);
                }
            }
        }
        // 2. Wall sprites (overlay; transparent at palette 0).
        if let Some(ref gmap) = self.gmap {
            for map_y in 0..REGION_TILE_HEIGHT {
                for map_x in 0..REGION_TILE_WIDTH {
                    let wall_index = gmap[map_y * REGION_TILE_WIDTH + map_x]
                        & GMAP_WALL_INDEX_MASK;
                    if wall_index == 0 {
                        continue;
                    }
                    let wall_id = self.region_number * 100 + wall_index as i32 - 1;
                    let Some(sprite) = self.walls.get(&wall_id) else {
                        continue;
                    };
                    // Position: centered horizontally in the
                    // tile, bottom-aligned (the sprite's bottom
                    // edge sits at the tile's bottom edge).
                    // Per RegionTool.java:289-290.
                    let sprite_x = (map_x * TILE_PIXEL_SIZE) as i32
                        + 8
                        - (sprite.width as i32 / 2);
                    let sprite_y = (map_y * TILE_PIXEL_SIZE) as i32 + 16
                        - sprite.height as i32;
                    overlay_sprite(&mut out, sprite, sprite_x, sprite_y);
                }
            }
        }
        // 3. Entity sprites (top of stack; ETAB-defined NPCs,
        // props, trees, etc.). Position per RegionTool.java:264-267:
        //   x = etab.x - ojff.x_offset
        //   y = etab.y - ojff.y_offset - etab.y_offset
        for ent in &self.entities {
            let id = if ent.ojff_number < 0 {
                -(ent.ojff_number as i32)
            } else {
                ent.ojff_number as i32
            };
            let Some(sprite) = self.entity_sprites.get(&id) else {
                continue;
            };
            let dst_x = ent.x as i32 - sprite.x_offset as i32;
            let dst_y = ent.y as i32 - sprite.y_offset as i32 - ent.y_offset as i32;
            if ent.mirrored {
                overlay_sprite_mirrored(&mut out, sprite, dst_x, dst_y);
            } else {
                overlay_sprite(&mut out, sprite, dst_x, dst_y);
            }
        }
        out
    }

    /// Write the rendered tile layer to a PNG file at `path`. Output
    /// is 8-bit palette-indexed, matching `image-extract`'s policy
    /// for the per-tile bitmaps.
    pub fn write_png(&self, path: &Path) -> Result<()> {
        let pixels = self.render_indexed();
        let file = std::fs::File::create(path)?;
        let w = std::io::BufWriter::new(file);
        let mut encoder =
            png::Encoder::new(w, REGION_PIXEL_WIDTH as u32, REGION_PIXEL_HEIGHT as u32);
        encoder.set_color(png::ColorType::Indexed);
        encoder.set_depth(png::BitDepth::Eight);
        encoder.set_palette(self.palette.as_rgb_bytes().to_vec());
        let mut writer = encoder.write_header()?;
        writer.write_image_data(&pixels)?;
        Ok(())
    }
}

/// Try to pull a `PAL ` / `CPAL` palette out of `gff` directly.
/// Mirrors `image-extract`'s default rule: prefer the lowest-id
/// `PAL `, then the lowest-id `CPAL`. Returns `None` if neither
/// chunk type appears.
pub fn inline_palette(gff: &Gff) -> Result<Option<Palette>> {
    let pal = lowest_id_chunk(gff, PAL_KIND).or_else(|| lowest_id_chunk(gff, CPAL_KIND));
    let Some(bytes) = pal else {
        return Ok(None);
    };
    let palette = Palette::from_bytes(bytes)?;
    Ok(Some(palette))
}

fn lowest_id_chunk<'a>(gff: &'a Gff, kind: FourCC) -> Option<&'a [u8]> {
    gff.chunks()
        .iter()
        .filter(|c| c.kind == kind)
        .min_by_key(|c| c.id)
        .map(|c| gff.read_chunk(c))
}

fn read_first<'a>(gff: &'a Gff, kind: FourCC) -> Option<&'a [u8]> {
    gff.chunks()
        .iter()
        .find(|c| c.kind == kind)
        .map(|c| gff.read_chunk(c))
}

fn read_first_with_id<'a>(gff: &'a Gff, kind: FourCC) -> Option<(&'a [u8], i32)> {
    gff.chunks()
        .iter()
        .find(|c| c.kind == kind)
        .map(|c| (gff.read_chunk(c), c.id))
}

/// Decode a `WALL` chunk to a wall sprite. Walls are standard
/// Dark Sun bitmaps, same format as `TILE`s, but with variable
/// dimensions. Mirrors `decode_tile` without the 16x16 size
/// check.
fn decode_wall(wall_id: i32, bytes: &[u8]) -> std::result::Result<WallSprite, TileDecodeFailure> {
    let fail = |reason: String| TileDecodeFailure {
        tile_id: wall_id,
        reason,
    };
    let bmp = Bitmap::from_bytes(bytes).map_err(|e| fail(format!("header: {e}")))?;
    if bmp.frame_count == 0 {
        return Err(fail("frame_count = 0".to_string()));
    }
    let frame = bmp
        .decode_frame(0)
        .map_err(|e| fail(format!("frame 0: {e}")))?;
    Ok(WallSprite {
        width: frame.width,
        height: frame.height,
        pixels: frame.indices,
        x_offset: 0,
        y_offset: 0,
    })
}

/// Parse one region's `ETAB` chunk into a list of records. Each
/// record is 8 bytes (`RegionTool.java:300`-`317`):
///
/// | offset | type | field           |
/// |--------|------|-----------------|
/// | 0      | s16  | x               |
/// | 2      | s16  | y               |
/// | 4      | s8   | y_offset        |
/// | 5      | u8   | byte5 (bit 7 = mirrored) |
/// | 6      | s16  | ojff_number     |
fn parse_etab(bytes: &[u8]) -> Vec<EntityRecord> {
    let mut out = Vec::with_capacity(bytes.len() / 8);
    for chunk in bytes.chunks_exact(8) {
        let x = i16::from_le_bytes([chunk[0], chunk[1]]);
        let y = i16::from_le_bytes([chunk[2], chunk[3]]);
        let y_offset = chunk[4] as i8;
        let mirrored = (chunk[5] & 0x80) != 0;
        let ojff_number = i16::from_le_bytes([chunk[6], chunk[7]]);
        out.push(EntityRecord {
            x,
            y,
            y_offset,
            mirrored,
            ojff_number,
        });
    }
    out
}

/// Parse an `OJFF` chunk's anchor metadata.
/// Returns `(bmp_number, x_offset, y_offset)` per
/// `RegionTool.java:319`-`331`:
///
/// | offset | type | field    |
/// |--------|------|----------|
/// | 0x02   | s16  | x_offset |
/// | 0x04   | s16  | y_offset |
/// | 0x0C   | u16  | bmp_number |
fn parse_ojff(bytes: &[u8]) -> Option<(u16, i16, i16)> {
    if bytes.len() < 0x0E {
        return None;
    }
    let x_off = i16::from_le_bytes([bytes[0x02], bytes[0x03]]);
    let y_off = i16::from_le_bytes([bytes[0x04], bytes[0x05]]);
    let bmp_number = u16::from_le_bytes([bytes[0x0C], bytes[0x0D]]);
    Some((bmp_number, x_off, y_off))
}

/// Composite a sprite onto the rendered buffer at
/// `(dst_x, dst_y)`. Palette-index-0 pixels are skipped
/// (transparent). Coordinates can be negative or extend past the
/// image; out-of-bounds pixels are clipped.
fn overlay_sprite(buf: &mut [u8], sprite: &WallSprite, dst_x: i32, dst_y: i32) {
    let w = sprite.width as i32;
    let h = sprite.height as i32;
    for sy in 0..h {
        let dy = dst_y + sy;
        if dy < 0 || dy >= REGION_PIXEL_HEIGHT as i32 {
            continue;
        }
        for sx in 0..w {
            let dx = dst_x + sx;
            if dx < 0 || dx >= REGION_PIXEL_WIDTH as i32 {
                continue;
            }
            let value = sprite.pixels[(sy * w + sx) as usize];
            if value == 0 {
                continue; // transparent
            }
            buf[dy as usize * REGION_PIXEL_WIDTH + dx as usize] = value;
        }
    }
}

/// Like [`overlay_sprite`] but flips the sprite horizontally
/// during compositing. Per `RegionTool.java:346`: when
/// `etab.byte5 & 0x80` is set, the sprite is drawn mirrored.
fn overlay_sprite_mirrored(buf: &mut [u8], sprite: &WallSprite, dst_x: i32, dst_y: i32) {
    let w = sprite.width as i32;
    let h = sprite.height as i32;
    for sy in 0..h {
        let dy = dst_y + sy;
        if dy < 0 || dy >= REGION_PIXEL_HEIGHT as i32 {
            continue;
        }
        for sx in 0..w {
            let dx = dst_x + (w - 1 - sx);
            if dx < 0 || dx >= REGION_PIXEL_WIDTH as i32 {
                continue;
            }
            let value = sprite.pixels[(sy * w + sx) as usize];
            if value == 0 {
                continue;
            }
            buf[dy as usize * REGION_PIXEL_WIDTH + dx as usize] = value;
        }
    }
}

/// Decode one TILE chunk. Validates dimensions are 16x16 and that
/// the frame body fits. Any failure becomes a soft
/// [`TileDecodeFailure`] rather than an error: sentinel chunks
/// (e.g. DS2 RGN001's 15-byte TILE id=0) are normal corpus state.
fn decode_tile(tile_id: i32, bytes: &[u8]) -> std::result::Result<Tile, TileDecodeFailure> {
    let fail = |reason: String| TileDecodeFailure { tile_id, reason };
    let bmp = Bitmap::from_bytes(bytes).map_err(|e| fail(format!("header: {e}")))?;
    if bmp.frame_count == 0 {
        return Err(fail("frame_count = 0".to_string()));
    }
    let frame = bmp
        .decode_frame(0)
        .map_err(|e| fail(format!("frame 0: {e}")))?;
    if frame.width as usize != TILE_PIXEL_SIZE || frame.height as usize != TILE_PIXEL_SIZE {
        return Err(fail(format!(
            "expected 16x16, got {}x{}",
            frame.width, frame.height
        )));
    }
    let mut pixels = [0u8; TILE_PIXEL_SIZE * TILE_PIXEL_SIZE];
    pixels.copy_from_slice(&frame.indices);
    Ok(Tile { pixels })
}

#[cfg(test)]
mod tests {
    use super::*;
    use image_extract::Color;

    fn tiny_palette() -> Palette {
        // 256 distinct colors so test assertions can recognise
        // palette indices unambiguously. Channels are 8-bit here
        // since Palette stores post-multiplier values.
        let mut colors = [Color { r: 0, g: 0, b: 0 }; image_extract::PALETTE_SIZE];
        for i in 0..image_extract::PALETTE_SIZE {
            colors[i] = Color {
                r: i as u8,
                g: i as u8,
                b: i as u8,
            };
        }
        Palette { colors }
    }

    fn solid_tile(idx: u8) -> Tile {
        Tile {
            pixels: [idx; TILE_PIXEL_SIZE * TILE_PIXEL_SIZE],
        }
    }

    fn empty_region(palette: Palette) -> RegionMap {
        RegionMap {
            map: vec![0u8; REGION_MAP_BYTES],
            used_map_kind: false,
            palette,
            tiles: BTreeMap::new(),
            missing_tile_byte_count: REGION_MAP_BYTES as u32,
            missing_tile_ids: vec![0],
            tile_decode_failures: vec![],
            gmap: None,
            region_number: 0,
            walls: BTreeMap::new(),
            missing_wall_ids: vec![],
            wall_decode_failures: vec![],
            entities: vec![],
            entity_sprites: BTreeMap::new(),
            missing_entity_ids: vec![],
            entity_decode_failures: vec![],
        }
    }

    #[test]
    fn region_dims_match_regiontool_constants() {
        assert_eq!(REGION_TILE_WIDTH, 128);
        assert_eq!(REGION_TILE_HEIGHT, 98);
        assert_eq!(TILE_PIXEL_SIZE, 16);
        assert_eq!(REGION_PIXEL_WIDTH, 2048);
        assert_eq!(REGION_PIXEL_HEIGHT, 1568);
        assert_eq!(REGION_MAP_BYTES, 12_544);
    }

    #[test]
    fn render_indexed_returns_full_image() {
        let r = empty_region(tiny_palette());
        let buf = r.render_indexed();
        assert_eq!(buf.len(), REGION_PIXEL_WIDTH * REGION_PIXEL_HEIGHT);
        // No tiles available, so every pixel stays at palette 0.
        assert!(buf.iter().all(|&b| b == 0));
    }

    #[test]
    fn missing_tile_cells_stay_at_palette_zero() {
        let mut r = empty_region(tiny_palette());
        // Plant a non-zero tile id at (0, 0) that doesn't exist.
        r.map[0] = 42;
        let buf = r.render_indexed();
        // Top-left 16x16 should still be zeros.
        for ty in 0..TILE_PIXEL_SIZE {
            for tx in 0..TILE_PIXEL_SIZE {
                assert_eq!(buf[ty * REGION_PIXEL_WIDTH + tx], 0, "({tx},{ty})");
            }
        }
    }

    #[test]
    fn present_tile_paints_its_cell_only() {
        let mut r = empty_region(tiny_palette());
        r.tiles.insert(7, solid_tile(99));
        r.map[0] = 7; // top-left cell now points at tile 7
        let buf = r.render_indexed();
        // Cell (0, 0) is solid palette 99.
        for ty in 0..TILE_PIXEL_SIZE {
            for tx in 0..TILE_PIXEL_SIZE {
                assert_eq!(buf[ty * REGION_PIXEL_WIDTH + tx], 99);
            }
        }
        // Cell (1, 0) is untouched (palette 0).
        assert_eq!(buf[TILE_PIXEL_SIZE], 0);
        // Cell (0, 1) is untouched.
        assert_eq!(buf[TILE_PIXEL_SIZE * REGION_PIXEL_WIDTH], 0);
    }

    #[test]
    fn decode_tile_rejects_short_chunk_softly() {
        // 5 bytes is well below the 6-byte header threshold; the
        // helper should yield a TileDecodeFailure, not panic.
        let result = decode_tile(99, &[0, 0, 0, 0, 0]);
        assert!(result.is_err());
        let failure = result.unwrap_err();
        assert_eq!(failure.tile_id, 99);
        assert!(failure.reason.starts_with("header:"));
    }

    #[test]
    fn tile_rows_align_top_down() {
        // Build a tile whose 16 rows are 0, 1, 2, ..., 15. Placing
        // it at map cell (0, 0) should produce rows of 0..=15 in
        // pixel y = 0..=15 of the rendered image.
        let mut pixels = [0u8; TILE_PIXEL_SIZE * TILE_PIXEL_SIZE];
        for ty in 0..TILE_PIXEL_SIZE {
            for tx in 0..TILE_PIXEL_SIZE {
                pixels[ty * TILE_PIXEL_SIZE + tx] = ty as u8;
            }
        }
        let mut r = empty_region(tiny_palette());
        r.tiles.insert(3, Tile { pixels });
        r.map[0] = 3;
        let buf = r.render_indexed();
        for ty in 0..TILE_PIXEL_SIZE {
            assert_eq!(buf[ty * REGION_PIXEL_WIDTH], ty as u8, "row {ty}");
        }
    }
}
