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
    /// Explicit palette from a raw 768-byte PAL/CPAL file. Wins
    /// over `--palette` if both are set.
    #[arg(long = "palette-file")]
    palette_file: Option<PathBuf>,
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
    )?;

    let region = RegionMap::from_gff(&gff, palette)
        .with_context(|| format!("building RegionMap from {}", cli.file.display()))?;
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
///    GFF, chunk `PAL :1000` (the DS1 convention).
/// 5. Error with a discoverability hint.
fn resolve_palette(
    region_gff: &Gff,
    region_path: &Path,
    palette_spec: Option<&str>,
    palette_file: Option<&Path>,
) -> Result<Palette> {
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

    // 4. Default fallback: sibling RESOURCE.GFF / PAL :1000.
    let mut sibling = region_path.to_path_buf();
    sibling.set_file_name("RESOURCE.GFF");
    if sibling.is_file() {
        let resource_gff = Gff::open(&sibling)
            .with_context(|| format!("opening fallback palette source {}", sibling.display()))?;
        let kind = FourCC(*b"PAL ");
        if let Some(bytes) = resource_gff.read(kind, 1000) {
            return Ok(Palette::from_bytes(bytes)?);
        }
    }

    Err(anyhow!(
        "no palette source: the region GFF has no inline PAL/CPAL chunk \
         and a fallback RESOURCE.GFF:PAL:1000 was not found. Pass \
         --palette <gff>:PAL:<id> or --palette-file <raw-768-byte-file>."
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

fn parse_kind_padded(s: &str) -> Result<FourCC> {
    let bytes = s.as_bytes();
    if bytes.len() < 3 || bytes.len() > 4 {
        return Err(anyhow!("palette kind must be 3 or 4 chars: {s:?}"));
    }
    let mut padded = [b' '; 4];
    padded[..bytes.len()].copy_from_slice(bytes);
    Ok(FourCC(padded))
}
