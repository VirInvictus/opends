use std::path::PathBuf;

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gff_edit::{FourCC, Gff};
use image_extract::{Bitmap, Palette, write_png};

#[derive(Parser)]
#[command(
    name = "image-extract",
    version,
    about = "Extract Dark Sun bitmap chunks (BMP / PORT / ICON) as PNG."
)]
struct Cli {
    /// Path to a GFF file containing bitmap and palette chunks.
    file: PathBuf,
    /// FOURCC of the bitmap chunk to extract. Defaults to `BMP `.
    /// Accepts 3- or 4-character forms; 3-char inputs are padded
    /// with a trailing space (DOS convention).
    #[arg(long, default_value = "BMP")]
    kind: String,
    /// Resource id of the chunk. Required unless `--all` is set.
    #[arg(long)]
    id: Option<i32>,
    /// Frame number within the chunk (default 0 = first frame).
    #[arg(long, default_value_t = 0)]
    frame: usize,
    /// Resource id of the palette chunk to apply. Defaults to the
    /// lowest-id `PAL ` chunk in the same GFF, or the lowest-id
    /// `CPAL` chunk if no `PAL ` is present.
    #[arg(long)]
    palette: Option<i32>,
    /// FOURCC of the palette chunk. Defaults to `PAL `.
    #[arg(long, default_value = "PAL")]
    palette_kind: String,
    /// Extract every `BMP `, `PORT`, and `ICON` chunk; write
    /// each frame as `<kind>-<id>-<frame>.png` under `<output>`.
    /// Requires `-o <dir>`.
    #[arg(long, requires = "output")]
    all: bool,
    /// Output path. Single-frame mode: a file. `--all` mode: a
    /// directory.
    #[arg(short = 'o', long = "output")]
    output: Option<PathBuf>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let gff = Gff::open(&cli.file)
        .with_context(|| format!("opening {}", cli.file.display()))?;

    let palette = load_palette(&gff, &cli.palette_kind, cli.palette)?;

    if cli.all {
        let out_dir = cli
            .output
            .as_ref()
            .ok_or_else(|| anyhow!("--all requires -o <dir>"))?;
        std::fs::create_dir_all(out_dir)
            .with_context(|| format!("creating {}", out_dir.display()))?;
        let mut frames_written = 0usize;
        let mut frames_skipped = 0usize;
        for c in gff.chunks() {
            if !is_bitmap_kind(c.kind) {
                continue;
            }
            let bytes = gff.read_chunk(c);
            let bmp = match Bitmap::from_bytes(bytes) {
                Ok(b) => b,
                Err(e) => {
                    eprintln!(
                        "warn: {} {} header parse failed: {}",
                        c.kind, c.id, e
                    );
                    frames_skipped += 1;
                    continue;
                }
            };
            for frame_id in 0..bmp.frame_count as usize {
                match bmp.decode_frame(frame_id) {
                    Ok(frame) => {
                        let name = format!(
                            "{}-{}-{}.png",
                            String::from_utf8_lossy(c.kind.as_bytes()).trim_end(),
                            c.id,
                            frame_id
                        );
                        let path = out_dir.join(&name);
                        if let Err(e) = write_png(&path, &frame, &palette) {
                            eprintln!("warn: {} write failed: {}", path.display(), e);
                            frames_skipped += 1;
                        } else {
                            frames_written += 1;
                        }
                    }
                    Err(e) => {
                        eprintln!(
                            "warn: {} {} frame {} decode failed: {}",
                            c.kind, c.id, frame_id, e
                        );
                        frames_skipped += 1;
                    }
                }
            }
        }
        eprintln!(
            "wrote {frames_written} frames ({frames_skipped} skipped) into {}",
            out_dir.display()
        );
        return Ok(());
    }

    let id = cli.id.ok_or_else(|| anyhow!("--id is required (or pass --all)"))?;
    let kind = parse_fourcc(&cli.kind)?;
    let bytes = gff
        .read(kind, id)
        .ok_or_else(|| anyhow!("no chunk '{}' id={} in {}", kind, id, cli.file.display()))?;
    let bmp = Bitmap::from_bytes(bytes)
        .with_context(|| format!("parsing bitmap header for {} {}", kind, id))?;
    let frame = bmp
        .decode_frame(cli.frame)
        .with_context(|| format!("decoding frame {} of {} {}", cli.frame, kind, id))?;
    let out = cli
        .output
        .unwrap_or_else(|| PathBuf::from(format!(
            "{}-{}-{}.png",
            String::from_utf8_lossy(kind.as_bytes()).trim_end(),
            id,
            cli.frame
        )));
    write_png(&out, &frame, &palette).with_context(|| format!("writing {}", out.display()))?;
    eprintln!(
        "wrote {} ({}x{}, {})",
        out.display(),
        frame.width,
        frame.height,
        frame.frame_type
    );
    Ok(())
}

fn parse_fourcc(s: &str) -> Result<FourCC> {
    let bytes = s.as_bytes();
    if bytes.len() < 3 || bytes.len() > 4 {
        return Err(anyhow!("FOURCC must be 3 or 4 characters: {s:?}"));
    }
    let mut padded = [b' '; 4];
    padded[..bytes.len()].copy_from_slice(bytes);
    Ok(FourCC::new(padded))
}

fn is_bitmap_kind(kind: FourCC) -> bool {
    matches!(
        kind.as_bytes(),
        b"BMP " | b"PORT" | b"ICON" | b"BMAP" | b"OMAP" | b"TILE"
    )
}

fn load_palette(gff: &Gff, kind: &str, id: Option<i32>) -> Result<Palette> {
    let primary = parse_fourcc(kind)?;
    let cpal = FourCC::new(*b"CPAL");
    let candidates: Vec<&gff_edit::ChunkRef> = gff
        .chunks()
        .iter()
        .filter(|c| c.kind == primary || c.kind == cpal)
        .collect();
    if candidates.is_empty() {
        return Err(anyhow!(
            "no palette chunks found in this GFF (looked for '{}' and 'CPAL')",
            primary
        ));
    }
    let chosen = if let Some(want) = id {
        candidates
            .iter()
            .find(|c| c.id == want)
            .copied()
            .ok_or_else(|| anyhow!("palette chunk id={} not found", want))?
    } else {
        // Prefer 'PAL ' over 'CPAL'; within each kind, pick lowest id.
        let mut sorted = candidates.clone();
        sorted.sort_by_key(|c| (c.kind != primary, c.id));
        sorted[0]
    };
    let bytes = gff.read_chunk(chosen);
    Palette::from_bytes(bytes)
        .with_context(|| format!("parsing palette {} {}", chosen.kind, chosen.id))
}
