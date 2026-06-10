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
    /// layer. DS1 stores entities in `SEGOBJEX.GFF` (2,775 OJFF +
    /// 2,419 BMP). DS2 stores them in `OBJEX.GFF` (4,479 OJFF +
    /// 3,727 BMP). Default: auto-detect sibling `SEGOBJEX.GFF`
    /// or `OBJEX.GFF` next to the region GFF. Pass
    /// `--no-entities` to disable the entity pass.
    #[arg(long = "entities-from")]
    entities_from: Option<PathBuf>,
    /// Skip the entity layer.
    #[arg(long = "no-entities", conflicts_with = "entities_from")]
    no_entities: bool,
    /// Animate the entity layer: decode every frame of each
    /// ETAB-referenced BMP and emit a numbered PNG sequence
    /// stepping through the cycles. `-o` becomes a directory;
    /// each frame writes as `<output>/<output_stem>-frame-
    /// <N>.png`. Single-frame rendering (the default) is
    /// unchanged.
    #[arg(long = "animate-entities", conflicts_with = "no_entities")]
    animate_entities: bool,
    /// Number of frames to render in `--animate-entities`
    /// mode. Default: the max frame_count across all entity
    /// sprites loaded for this region (every entity cycles
    /// through at least once). Pass an explicit value to
    /// cap or extend the sequence.
    #[arg(long = "frame-count", requires = "animate_entities")]
    frame_count: Option<usize>,
    /// With --animate-entities: bundle the PNG sequence into a
    /// single animated GIF via `ffmpeg`. The output path passed
    /// to `-o` becomes the GIF file (the per-frame PNGs land in
    /// a sibling `<output>-frames/` directory you can keep or
    /// delete). Requires `ffmpeg` on `$PATH`.
    #[arg(long = "gif", requires = "animate_entities")]
    gif: bool,
    /// With --gif: target frame rate in frames per second.
    /// Default: 8 (slow enough to read; fast enough that wallpaper
    /// flicker tiles look animated).
    #[arg(long = "gif-fps", requires = "gif", default_value_t = 8)]
    gif_fps: u32,
}

/// Bundle the per-frame PNGs in `frames_dir` (with `<stem>-frame-N.png`
/// naming) into a single animated GIF at `output`. Shells to
/// ffmpeg; the palette pre-pass step gives noticeably better
/// colour fidelity on pixel-art than the single-pass default.
///
/// ffmpeg is detected lazily; a missing binary is a clear error
/// message rather than a silent skip (the caller asked for a GIF
/// explicitly).
fn assemble_gif(
    frames_dir: &std::path::Path,
    stem: &str,
    output: &std::path::Path,
    fps: u32,
) -> Result<()> {
    let ffmpeg = which::find("ffmpeg")
        .ok_or_else(|| anyhow!(
            "--gif requires `ffmpeg` on $PATH. Install via `dnf install ffmpeg`."
        ))?;
    let frame_pattern = frames_dir.join(format!("{stem}-frame-%d.png"));
    // Park the palette in $TMPDIR so ffmpeg's image2 demuxer
    // doesn't try to read it as part of the frame sequence
    // (which prints a noisy warning even though the encode
    // succeeds).
    let palette_path = std::env::temp_dir().join(format!(
        "region-render-palette-{}-{}.png",
        stem,
        std::process::id(),
    ));

    // Pre-pass: generate an optimised palette from the frame
    // sequence. Without this, ffmpeg's single-pass GIF encoder
    // produces dithered output that looks terrible on pixel art.
    // Stderr captured (not inherited) so the image2 demuxer's
    // "filename doesn't match sequence pattern" warning doesn't
    // clutter the user's output. Surfaced only on encode failure.
    let pal_out = std::process::Command::new(&ffmpeg)
        .args(["-y", "-loglevel", "error", "-framerate"])
        .arg(fps.to_string())
        .args(["-i"])
        .arg(&frame_pattern)
        .args(["-vf", "palettegen=stats_mode=diff"])
        .arg(&palette_path)
        .output()
        .with_context(|| format!("running {}", ffmpeg.display()))?;
    if !pal_out.status.success() {
        return Err(anyhow!(
            "ffmpeg palettegen failed (exit {}): {}",
            pal_out.status,
            String::from_utf8_lossy(&pal_out.stderr),
        ));
    }

    // Encode the GIF using the generated palette.
    let enc_out = std::process::Command::new(&ffmpeg)
        .args(["-y", "-loglevel", "error", "-framerate"])
        .arg(fps.to_string())
        .args(["-i"])
        .arg(&frame_pattern)
        .args(["-i"])
        .arg(&palette_path)
        .args([
            "-filter_complex",
            "[0:v][1:v]paletteuse=dither=none",
        ])
        .arg(output)
        .output()
        .with_context(|| format!("running {}", ffmpeg.display()))?;
    let status = enc_out.status;
    if !status.success() {
        return Err(anyhow!(
            "ffmpeg paletteuse failed (exit {}): {}",
            status,
            String::from_utf8_lossy(&enc_out.stderr),
        ));
    }
    // Tidy up the intermediate palette.
    let _ = std::fs::remove_file(&palette_path);
    let size = std::fs::metadata(output).map(|m| m.len()).unwrap_or(0);
    eprintln!("wrote animated GIF to {} ({} bytes, {fps} fps)",
        output.display(), size);
    Ok(())
}

mod which {
    use std::path::PathBuf;

    /// Stdlib-only $PATH lookup; mirrors `shutil.which`. Kept in
    /// a private module so the binary doesn't need a separate
    /// crate dep for this one function.
    pub fn find(name: &str) -> Option<PathBuf> {
        let path = std::env::var_os("PATH")?;
        for dir in std::env::split_paths(&path) {
            let candidate = dir.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
        None
    }
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
    if !cli.no_walls
        && let Some(walls_path) = resolve_walls_gff_path(cli.walls_from.as_deref(), cli.file.as_path()) {
            let walls_gff = Gff::open(&walls_path)
                .with_context(|| format!("opening walls source {}", walls_path.display()))?;
            region
                .with_walls_from(&walls_gff)
                .with_context(|| format!("indexing WALL chunks from {}", walls_path.display()))?;
        }
    if !cli.no_entities
        && let Some(entities_path) = resolve_entities_gff_path(
            cli.entities_from.as_deref(),
            cli.file.as_path(),
        ) {
            let entities_gff = Gff::open(&entities_path)
                .with_context(|| format!("opening entities source {}", entities_path.display()))?;
            if cli.animate_entities {
                region
                    .with_animated_entities_from(&entities_gff)
                    .with_context(|| format!("indexing OJFF/BMP (animated) from {}", entities_path.display()))?;
            } else {
                region
                    .with_entities_from(&entities_gff)
                    .with_context(|| format!("indexing OJFF/BMP from {}", entities_path.display()))?;
            }
        }

    if cli.animate_entities {
        let n_frames = cli.frame_count.unwrap_or_else(|| region.max_entity_frame_count());
        if n_frames == 0 {
            return Err(anyhow!("--frame-count must be at least 1"));
        }
        // GIF mode: output path is the .gif file; PNG frames
        // land in a sibling `<gif-path>-frames/` directory so
        // the user can keep or delete them. Non-GIF mode keeps
        // the v0.6.0 behaviour where -o is the PNG directory.
        let frames_dir = if cli.gif {
            let mut d = cli.output.clone();
            let stem = d
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("region")
                .to_string();
            let parent = d.parent().map(|p| p.to_path_buf()).unwrap_or_default();
            d = parent.join(format!("{stem}-frames"));
            d
        } else {
            cli.output.clone()
        };
        std::fs::create_dir_all(&frames_dir)
            .with_context(|| format!("creating frames dir {}", frames_dir.display()))?;
        let stem = cli
            .file
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("region");
        for frame_idx in 0..n_frames {
            let frame_path = frames_dir.join(format!("{stem}-frame-{frame_idx}.png"));
            region
                .write_png_frame(&frame_path, frame_idx)
                .with_context(|| format!("writing frame {} to {}", frame_idx, frame_path.display()))?;
        }
        eprintln!(
            "wrote {n_frames} frame(s) ({}x{}, source map: {}) into {}",
            region_render::REGION_PIXEL_WIDTH,
            region_render::REGION_PIXEL_HEIGHT,
            if region.used_map_kind { "MAP " } else { "RMAP" },
            frames_dir.display(),
        );
        eprintln!(
            "  entities: {} ETAB records; {} animated sprite ids loaded; \
             max entity frame_count {}; {} missing-entity ids; {} entity decode failures",
            region.entities.len(),
            region.entity_sprite_frames_count(),
            region.max_entity_frame_count(),
            region.missing_entity_ids.len(),
            region.entity_decode_failures.len(),
        );
        if cli.gif {
            assemble_gif(&frames_dir, stem, &cli.output, cli.gif_fps)?;
        }
        return Ok(());
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
