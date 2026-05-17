use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gff_edit::{FourCC, Gff};
use image_extract::{Palette, PALETTE_CHUNK_LEN};
use region_render::{RegionMap, inline_palette};

#[derive(Parser)]
#[command(
    name = "region-render",
    version,
    about = "Render a Dark Sun region GFF's background-tile layer as a PNG."
)]
struct Cli {
    /// Path to a region GFF (e.g. `RGN02.GFF` for DS1 or
    /// `RGN001.GFF` for DS2).
    file: PathBuf,
    /// Output PNG path.
    #[arg(short = 'o', long = "output", required = true)]
    output: PathBuf,
    /// Explicit palette source from a GFF, formatted as
    /// `<path>:<KIND>:<id>` (e.g. `RESOURCE.GFF:PAL:1000`). KIND
    /// is 3 or 4 chars; 3-char forms are padded with trailing space.
    /// Takes precedence over inline-palette discovery.
    #[arg(long = "palette")]
    palette: Option<String>,
    /// Curated DS1 palette presets. Equivalent to `--palette
    /// <RESOURCE.GFF>:<kind>:<id>` with the matching values.
    /// Available: `ds1-pink` (PAL:1000, the v0.1.0 default,
    /// renders off-camera void as pink), `ds1-rust` (CPAL:200,
    /// uniformly rusty-red Athasian look), `ds1-deep-red`
    /// (CPAL:300, darker variant). Resolves a sibling
    /// RESOURCE.GFF.
    #[arg(long = "palette-preset", value_parser = ["ds1-pink", "ds1-rust", "ds1-deep-red"])]
    palette_preset: Option<String>,
    /// Explicit palette from a raw 768-byte PAL/CPAL file. Wins
    /// over `--palette` if both are set.
    #[arg(long = "palette-file")]
    palette_file: Option<PathBuf>,
    /// GFF to read `WALL` chunks from for the wall layer. DS1
    /// stores walls in `GPLDATA.GFF` (664 chunks). DS2 has no
    /// known WALL chunks in the GOG 1.10 corpus. Default:
    /// auto-detect sibling `GPLDATA.GFF` next to the region GFF.
    /// Pass `--no-walls` to disable the wall pass entirely.
    #[arg(long = "walls-from")]
    walls_from: Option<PathBuf>,
    /// Skip the wall layer. Useful for diffing against v0.1.0
    /// output or for regions where walls aren't desired.
    #[arg(long = "no-walls", conflicts_with = "walls_from")]
    no_walls: bool,
    /// GFF to read `OJFF` + `BMP ` chunks from for the entity
    /// layer. DS1 stores entities in `SEGOBJEX.GFF` (2,775 OJFF
    /// + 2,419 BMP). DS2 stores them in `OBJEX.GFF` (4,479
    /// OJFF + 3,727 BMP). Default: auto-detect sibling
    /// `SEGOBJEX.GFF` or `OBJEX.GFF` next to the region GFF.
    /// Pass `--no-entities` to disable the entity pass.
    #[arg(long = "entities-from")]
    entities_from: Option<PathBuf>,
    /// Skip the entity layer.
    #[arg(long = "no-entities", conflicts_with = "entities_from")]
    no_entities: bool,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let gff = Gff::open(&cli.file)
        .with_context(|| format!("opening {}", cli.file.display()))?;
    let palette = resolve_palette(
        &gff,
        cli.file.as_path(),
        cli.palette.as_deref(),
        cli.palette_file.as_deref(),
        cli.palette_preset.as_deref(),
    )?;

    let mut region = RegionMap::from_gff(&gff, palette)
        .with_context(|| format!("building RegionMap from {}", cli.file.display()))?;
    if !cli.no_walls {
        if let Some(walls_path) = resolve_walls_gff_path(cli.walls_from.as_deref(), cli.file.as_path()) {
            let walls_gff = Gff::open(&walls_path)
                .with_context(|| format!("opening walls source {}", walls_path.display()))?;
            region
                .with_walls_from(&walls_gff)
                .with_context(|| format!("indexing WALL chunks from {}", walls_path.display()))?;
        }
    }
    if !cli.no_entities {
        if let Some(entities_path) = resolve_entities_gff_path(
            cli.entities_from.as_deref(),
            cli.file.as_path(),
        ) {
            let entities_gff = Gff::open(&entities_path)
                .with_context(|| format!("opening entities source {}", entities_path.display()))?;
            region
                .with_entities_from(&entities_gff)
                .with_context(|| format!("indexing OJFF/BMP from {}", entities_path.display()))?;
        }
    }
    region
        .write_png(&cli.output)
        .with_context(|| format!("writing PNG to {}", cli.output.display()))?;

    eprintln!(
        "wrote {} ({}x{}, source map: {})",
        cli.output.display(),
        region_render::REGION_PIXEL_WIDTH,
        region_render::REGION_PIXEL_HEIGHT,
        if region.used_map_kind { "MAP " } else { "RMAP" },
    );
    eprintln!(
        "  missing-tile cells: {} bytes across {} distinct ids",
        region.missing_tile_byte_count,
        region.missing_tile_ids.len()
    );
    if !cli.no_walls {
        let walls_present = region.gmap.is_some();
        let wall_count: usize = region
            .gmap
            .as_ref()
            .map(|g| {
                g.iter()
                    .filter(|&&b| (b & region_render::GMAP_WALL_INDEX_MASK) != 0)
                    .count()
            })
            .unwrap_or(0);
        eprintln!(
            "  walls: {} sprite ids loaded; {} GMAP cells reference a wall; \
             {} missing-wall ids; gmap present: {}",
            region.wall_sprite_count(),
            wall_count,
            region.missing_wall_ids.len(),
            walls_present,
        );
        if !region.wall_decode_failures.is_empty() {
            eprintln!(
                "  WALL chunks that failed to decode: {}",
                region.wall_decode_failures.len()
            );
        }
    }
    if !cli.no_entities {
        eprintln!(
            "  entities: {} ETAB records; {} sprite ids loaded; \
             {} missing-entity ids; {} entity decode failures",
            region.entities.len(),
            region.entity_sprite_count(),
            region.missing_entity_ids.len(),
            region.entity_decode_failures.len(),
        );
    }
    if !region.tile_decode_failures.is_empty() {
        eprintln!(
            "  TILE chunks that failed to decode: {}",
            region.tile_decode_failures.len()
        );
        for f in region.tile_decode_failures.iter().take(5) {
            eprintln!("    id {}: {}", f.tile_id, f.reason);
        }
        if region.tile_decode_failures.len() > 5 {
            eprintln!(
                "    ... and {} more",
                region.tile_decode_failures.len() - 5
            );
        }
    }
    Ok(())
}

/// Resolve a palette. Precedence:
/// 1. `--palette-file <raw>` if set.
/// 2. `--palette <gff>:<kind>:<id>` if set.
/// 3. Inline `PAL ` / `CPAL` in the region GFF (DS2 case).
/// 4. Default: `RESOURCE.GFF` in the same directory as the region
///    GFF. Try `CPAL:200` first (matches what the engine does
///    per the DSUN.EXE RE in `docs/dsun-exe-re.md`: the engine
///    loads `CMAT[region_family_id]` with `CPAL[region_family_id]`
///    as the fallback, and CPAL:200 is the more common of the
///    two known family ids). If `CPAL:200` is missing, fall back
///    to `PAL :1000` (the v0.4.x default; renders off-camera
///    void as pink).
/// 5. Error with a discoverability hint.
fn resolve_palette(
    region_gff: &Gff,
    region_path: &Path,
    palette_spec: Option<&str>,
    palette_file: Option<&Path>,
    palette_preset: Option<&str>,
) -> Result<Palette> {
    // 0. --palette-preset (curated DS1 sibling RESOURCE.GFF
    //    lookups). Wins over --palette / --palette-file by
    //    intent; modders reach for `--palette-preset ds1-rust`
    //    as the obvious "make my DS1 region look right" knob.
    //    A simultaneous explicit `--palette` is honoured below
    //    only if the preset isn't set.
    if let Some(name) = palette_preset {
        let mut sibling = region_path.to_path_buf();
        sibling.set_file_name("RESOURCE.GFF");
        if !sibling.is_file() {
            return Err(anyhow!(
                "--palette-preset {name} expects a sibling RESOURCE.GFF next to {}",
                region_path.display()
            ));
        }
        let (kind, id) = match name {
            "ds1-pink" => (FourCC(*b"PAL "), 1000),
            "ds1-rust" => (FourCC(*b"CPAL"), 200),
            "ds1-deep-red" => (FourCC(*b"CPAL"), 300),
            other => {
                return Err(anyhow!("unknown --palette-preset: {other:?}"));
            }
        };
        let gff = Gff::open(&sibling)
            .with_context(|| format!("opening preset source {}", sibling.display()))?;
        let bytes = gff
            .read(kind, id)
            .ok_or_else(|| anyhow!("preset {name}: no {} {} in {}", kind, id, sibling.display()))?;
        return Palette::from_bytes(bytes).map_err(Into::into);
    }
    // 1. --palette-file
    if let Some(p) = palette_file {
        let bytes = std::fs::read(p)
            .with_context(|| format!("reading palette file {}", p.display()))?;
        if bytes.len() != PALETTE_CHUNK_LEN {
            return Err(anyhow!(
                "{}: expected {} bytes, got {}",
                p.display(),
                PALETTE_CHUNK_LEN,
                bytes.len()
            ));
        }
        return Palette::from_bytes(&bytes).map_err(Into::into);
    }

    // 2. --palette <gff>:<kind>:<id>
    if let Some(spec) = palette_spec {
        return load_palette_spec(spec);
    }

    // 3. Inline.
    if let Some(p) = inline_palette(region_gff)
        .context("scanning region GFF for inline PAL/CPAL")?
    {
        return Ok(p);
    }

    // 4. Default fallback: sibling RESOURCE.GFF. v0.5.0 prefers
    //    CPAL:200 (matches the engine's per-region behaviour per
    //    docs/dsun-exe-re.md) and falls back to PAL :1000 if the
    //    install doesn't carry CPAL:200.
    let mut sibling = region_path.to_path_buf();
    sibling.set_file_name("RESOURCE.GFF");
    if sibling.is_file() {
        let resource_gff = Gff::open(&sibling)
            .with_context(|| format!("opening fallback palette source {}", sibling.display()))?;
        if let Some(bytes) = resource_gff.read(FourCC(*b"CPAL"), 200) {
            eprintln!(
                "  palette: fallback to {}:CPAL:200 (engine-default; \
                 override with --palette-preset ds1-pink for the v0.4.x look)",
                sibling.display()
            );
            return Ok(Palette::from_bytes(bytes)?);
        }
        if let Some(bytes) = resource_gff.read(FourCC(*b"PAL "), 1000) {
            eprintln!(
                "  palette: fallback to {}:PAL :1000 (CPAL:200 not present \
                 in this install)",
                sibling.display()
            );
            return Ok(Palette::from_bytes(bytes)?);
        }
    }

    Err(anyhow!(
        "no palette source: the region GFF has no inline PAL/CPAL chunk \
         and neither RESOURCE.GFF:CPAL:200 nor RESOURCE.GFF:PAL:1000 was \
         found. Pass --palette <gff>:PAL:<id> or --palette-file \
         <raw-768-byte-file>."
    ))
}

fn load_palette_spec(spec: &str) -> Result<Palette> {
    let mut parts = spec.rsplitn(3, ':');
    let id_str = parts.next().ok_or_else(|| spec_error(spec))?;
    let kind_str = parts.next().ok_or_else(|| spec_error(spec))?;
    let path_str = parts.next().ok_or_else(|| spec_error(spec))?;
    let id: i32 = id_str
        .parse()
        .with_context(|| format!("parsing palette id in {spec:?}"))?;
    let kind = parse_kind_padded(kind_str)?;
    let path = PathBuf::from(path_str);
    let gff = Gff::open(&path)
        .with_context(|| format!("opening palette GFF {}", path.display()))?;
    let bytes = gff
        .read(kind, id)
        .ok_or_else(|| anyhow!("no chunk '{}' id={} in {}", kind, id, path.display()))?;
    Palette::from_bytes(bytes).map_err(Into::into)
}

fn spec_error(spec: &str) -> anyhow::Error {
    anyhow!(
        "--palette must be '<gff>:<kind>:<id>' (e.g. RESOURCE.GFF:PAL:1000); got {spec:?}"
    )
}

/// Resolve where to read WALL chunks from. Precedence:
/// 1. Explicit `--walls-from <path>`.
/// 2. Sibling `GPLDATA.GFF` next to the region GFF (DS1
///    convention; 664 WALL chunks live there on GOG 1.10).
/// 3. None (no walls drawn).
fn resolve_walls_gff_path(explicit: Option<&Path>, region_path: &Path) -> Option<PathBuf> {
    if let Some(p) = explicit {
        return Some(p.to_path_buf());
    }
    let mut sibling = region_path.to_path_buf();
    sibling.set_file_name("GPLDATA.GFF");
    if sibling.is_file() {
        return Some(sibling);
    }
    None
}

/// Resolve where to read OJFF + BMP chunks from. Precedence:
/// 1. Explicit `--entities-from <path>`.
/// 2. Sibling `SEGOBJEX.GFF` (DS1; 2,775 OJFF + 2,419 BMP).
/// 3. Sibling `OBJEX.GFF` (DS2; 4,479 OJFF + 3,727 BMP).
/// 4. None (no entities drawn).
fn resolve_entities_gff_path(explicit: Option<&Path>, region_path: &Path) -> Option<PathBuf> {
    if let Some(p) = explicit {
        return Some(p.to_path_buf());
    }
    for name in ["SEGOBJEX.GFF", "OBJEX.GFF"] {
        let mut sibling = region_path.to_path_buf();
        sibling.set_file_name(name);
        if sibling.is_file() {
            return Some(sibling);
        }
    }
    None
}

fn parse_kind_padded(s: &str) -> Result<FourCC> {
    let bytes = s.as_bytes();
    if bytes.len() < 3 || bytes.len() > 4 {
        return Err(anyhow!("palette kind must be 3 or 4 chars: {s:?}"));
    }
    let mut padded = [b' '; 4];
    padded[..bytes.len()].copy_from_slice(bytes);
    Ok(FourCC(padded))
}
