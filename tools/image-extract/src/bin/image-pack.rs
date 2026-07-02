use std::fs::File;
use std::io::Write;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use image_extract::{Frame, FrameType, encode_bitmap_rle};

/// Encode palette-indexed PNGs as a Dark Sun bitmap chunk
/// (`BMP `, `PORT`, `ICON`, `BMAP`, `OMAP`, or `TILE` shape; the
/// chunk-type FOURCC isn't part of the byte payload, so a single
/// encoder serves all six). Pipe the output into
/// `gff-cat replace <gff> <kind> <id> -` to slot the new bitmap
/// into a real game file.
///
/// v0.4.0 emits DS1 RLE for every frame. The game engine reads
/// PLNR and PLAN too, so RLE output is universally compatible.
#[derive(Parser)]
#[command(
    name = "image-pack",
    version,
    about = "Pack palette-indexed PNGs as a Dark Sun bitmap chunk."
)]
struct Cli {
    /// Input PNG path. Must be palette-indexed (PNG ColorType
    /// `Indexed`, bit depth 8). For multi-frame mode, pass a
    /// directory via `--frames-dir` instead and omit this.
    input: Option<PathBuf>,
    /// Pack every `*.png` file in this directory as a frame, in
    /// sorted-filename order. Useful for the round-trip with
    /// `image-extract --frames-all`.
    #[arg(long = "frames-dir", conflicts_with = "input")]
    frames_dir: Option<PathBuf>,
    /// Output path. `-` (the default) writes to stdout so the
    /// result can be piped directly into `gff-cat replace`.
    #[arg(short = 'o', long = "output", default_value = "-")]
    output: PathBuf,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let frames = if let Some(ref dir) = cli.frames_dir {
        read_frames_dir(dir)?
    } else if let Some(ref input) = cli.input {
        vec![read_png_indexed(input)?]
    } else {
        return Err(anyhow!(
            "either an input PNG path or --frames-dir <dir> is required"
        ));
    };

    let chunk = encode_bitmap_rle(&frames)
        .with_context(|| format!("encoding {} frame(s) as DS1 RLE", frames.len()))?;

    write_output(&cli.output, &chunk)?;
    eprintln!(
        "packed {} frame(s) into {} bytes",
        frames.len(),
        chunk.len(),
    );
    Ok(())
}

/// Decode a palette-indexed PNG (ColorType::Indexed, 8-bit depth)
/// into a `Frame` whose `indices` are the raw palette bytes. The
/// PNG's embedded palette is ignored; the modder's responsibility
/// is to use a PNG whose indices match the chunk's intended PAL /
/// CPAL chunk in the GFF.
fn read_png_indexed(path: &Path) -> Result<Frame> {
    let file = File::open(path).with_context(|| format!("opening {}", path.display()))?;
    let decoder = png::Decoder::new(file);
    let mut reader = decoder
        .read_info()
        .with_context(|| format!("reading PNG header of {}", path.display()))?;
    let info = reader.info();
    if info.color_type != png::ColorType::Indexed {
        return Err(anyhow!(
            "{}: expected palette-indexed PNG (ColorType::Indexed); got {:?}. \
             Convert with e.g. `convert input.png -dither None -map palette.png \
             PNG8:indexed.png`.",
            path.display(),
            info.color_type,
        ));
    }
    if info.bit_depth != png::BitDepth::Eight {
        return Err(anyhow!(
            "{}: expected 8-bit indexed PNG; got {:?}",
            path.display(),
            info.bit_depth,
        ));
    }
    let width = u16::try_from(info.width)
        .map_err(|_| anyhow!("{}: width {} exceeds u16", path.display(), info.width))?;
    let height = u16::try_from(info.height)
        .map_err(|_| anyhow!("{}: height {} exceeds u16", path.display(), info.height))?;

    let mut buf = vec![0u8; reader.output_buffer_size()];
    let out_info = reader
        .next_frame(&mut buf)
        .with_context(|| format!("reading PNG pixels of {}", path.display()))?;
    buf.truncate(out_info.buffer_size());

    let expected = width as usize * height as usize;
    if buf.len() != expected {
        return Err(anyhow!(
            "{}: PNG pixel buffer is {} bytes, expected {} ({}x{})",
            path.display(),
            buf.len(),
            expected,
            width,
            height,
        ));
    }
    Ok(Frame {
        width,
        height,
        frame_type: FrameType::Ds1Rle,
        indices: buf,
    })
}

/// Walk `dir`, collect every `*.png` file in sorted order, and
/// decode each as one frame. Empty directory is an error (an empty
/// frame list would otherwise hit a downstream rejection with a
/// less obvious message).
fn read_frames_dir(dir: &Path) -> Result<Vec<Frame>> {
    if !dir.is_dir() {
        return Err(anyhow!("--frames-dir {} is not a directory", dir.display()));
    }
    let mut png_paths: Vec<PathBuf> = std::fs::read_dir(dir)
        .with_context(|| format!("reading {}", dir.display()))?
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|p| {
            p.extension()
                .and_then(|e| e.to_str())
                .map(|e| e.eq_ignore_ascii_case("png"))
                .unwrap_or(false)
        })
        .collect();
    png_paths.sort();
    if png_paths.is_empty() {
        return Err(anyhow!("no .png files in {}", dir.display()));
    }
    let mut frames = Vec::with_capacity(png_paths.len());
    for p in &png_paths {
        frames.push(read_png_indexed(p)?);
    }
    Ok(frames)
}

fn write_output(path: &Path, bytes: &[u8]) -> Result<()> {
    if path.as_os_str() == "-" {
        std::io::stdout()
            .write_all(bytes)
            .context("writing chunk to stdout")?;
    } else {
        std::fs::write(path, bytes).with_context(|| format!("writing {}", path.display()))?;
    }
    Ok(())
}
