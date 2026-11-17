//! `font-pack`: rebuild a FONT chunk from an extracted glyph
//! directory (glyph PNGs + manifest.json) and write the GFF with
//! the chunk replaced. Byte-exactness is the contract: packing
//! unedited glyphs reproduces the original chunk.

use anyhow::{Context, Result};
use clap::Parser;
use font_extract::{FontGlyph, FontResource, GLYPH_COUNT, GLYPH_HEIGHT, build, parse};
use gff_edit::{FourCC, Gff};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Parser)]
#[command(about = "Pack edited glyph PNGs back into a Dark Sun FONT chunk")]
struct Cli {
    /// Glyph directory as written by font-extract (manifest.json +
    /// glyphs/*.png).
    dir: PathBuf,
    /// GFF file whose FONT chunk gets the packed result (modified
    /// in place only with --write; otherwise the chunk bytes are
    /// just verified against the originals).
    gff: PathBuf,
    /// Font chunk id (the shipped fonts are FONT 100).
    #[arg(long, default_value_t = 100)]
    id: i32,
    /// Actually write the GFF. Without this the command verifies
    /// that the packed chunk matches what the GFF holds (the
    /// round-trip check to run before handing edits over).
    #[arg(long)]
    write: bool,
}

#[derive(serde::Deserialize)]
struct Manifest {
    #[allow(dead_code)]
    glyph_height: usize,
    glyphs: Vec<GlyphRow>,
}

#[derive(serde::Deserialize)]
struct GlyphRow {
    code: usize,
    width: usize,
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    let manifest_text = fs::read_to_string(cli.dir.join("manifest.json"))
        .with_context(|| format!("reading {}", cli.dir.join("manifest.json").display()))?;
    let manifest: Manifest =
        serde_json::from_str(&manifest_text).context("parsing manifest.json")?;
    if manifest.glyphs.len() != GLYPH_COUNT {
        anyhow::bail!(
            "manifest lists {} glyphs; a FONT chunk needs exactly {GLYPH_COUNT}",
            manifest.glyphs.len()
        );
    }

    let mut glyphs = Vec::with_capacity(GLYPH_COUNT);
    for row in &manifest.glyphs {
        // Zero-width glyphs have no PNG (see font-extract): the
        // manifest's width field is their whole representation.
        let png_pixels = if row.width == 0 {
            Vec::new()
        } else {
            let path = glyph_path(&cli.dir, row.code);
            let png_pixels = decode_png(&path)?;
            if png_pixels.len() != row.width * GLYPH_HEIGHT {
                anyhow::bail!(
                    "glyph {}: {} expects {}x{} ({} bytes), PNG holds {}",
                    row.code,
                    path.display(),
                    row.width,
                    GLYPH_HEIGHT,
                    row.width * GLYPH_HEIGHT,
                    png_pixels.len()
                );
            }
            png_pixels
        };
        if png_pixels.len() != row.width * GLYPH_HEIGHT {
            anyhow::bail!("glyph {}: zero-width glyphs carry no pixels", row.code);
        }
        glyphs.push(FontGlyph {
            code: row.code,
            width: row.width,
            pixels: png_pixels,
        });
    }

    let packed = build(&FontResource {
        header: read_original_header(&cli.gff, cli.id)?,
        glyphs,
    })?;

    let gff_bytes = fs::read(&cli.gff).with_context(|| format!("reading {}", cli.gff.display()))?;
    let gff =
        Gff::from_bytes(gff_bytes).with_context(|| format!("parsing {}", cli.gff.display()))?;
    let chunk = gff
        .find(FourCC(*b"FONT"), cli.id)
        .with_context(|| format!("no FONT chunk with id {} found", cli.id))?;
    let original = gff.read_chunk(chunk);

    // The original header must survive round-trips through the
    // packed output: edits are glyph edits, the header (including
    // the height byte and whatever the opaque fields mean) is
    // carried over from the shipped chunk.
    let reparsed = parse(&packed)?;
    if reparsed.header != parse(original)?.header {
        anyhow::bail!("internal error: packed header diverged from the original");
    }

    if cli.write {
        if packed == original {
            println!("chunk unchanged; nothing to write");
            return Ok(());
        }
        if packed.len() != original.len() {
            anyhow::bail!(
                "packed chunk is {} bytes but the original is {}; in-place glyph edits keep sizes equal",
                packed.len(),
                original.len()
            );
        }
        let patched = gff
            .replace_chunk(FourCC(*b"FONT"), cli.id, &packed)
            .context("replacing FONT chunk")?;
        fs::write(&cli.gff, patched).with_context(|| format!("writing {}", cli.gff.display()))?;
        println!("wrote {} (FONT {} replaced)", cli.gff.display(), cli.id);
    } else if packed == original {
        println!(
            "round-trip verified: pack(parse(FONT {})) is byte-identical",
            cli.id
        );
    } else {
        let first = packed
            .iter()
            .zip(original.iter())
            .position(|(a, b)| a != b)
            .unwrap_or(0);
        anyhow::bail!(
            "packed chunk differs from the GFF's FONT {} at byte {first:#x} ({} vs {} bytes); \
             run with --write only if the glyph edits are intended",
            cli.id,
            packed.len(),
            original.len()
        );
    }
    Ok(())
}

fn glyph_path(dir: &Path, code: usize) -> PathBuf {
    dir.join("glyphs").join(format!("glyph-{code:03}.png"))
}

fn decode_png(path: &Path) -> Result<Vec<u8>> {
    let file = fs::File::open(path).with_context(|| format!("reading {}", path.display()))?;
    let decoder = png::Decoder::new(std::io::BufReader::new(file));
    let mut reader = decoder.read_info().context("png info")?;
    let mut buf = vec![0u8; reader.output_buffer_size().expect("png buffer size")];
    let info = reader.next_frame(&mut buf).context("png frame")?;
    if info.color_type != png::ColorType::Grayscale || info.bit_depth != png::BitDepth::Eight {
        anyhow::bail!(
            "{}: expected 8-bit grayscale, got {:?}/{:?}",
            path.display(),
            info.color_type,
            info.bit_depth
        );
    }
    buf.truncate(info.buffer_size());
    Ok(buf)
}

/// The shipped header is what pack carries over: read it from the
/// GFF's current FONT chunk so glyph edits cannot touch it.
fn read_original_header(gff_path: &Path, id: i32) -> Result<Vec<u8>> {
    let bytes = fs::read(gff_path).with_context(|| format!("reading {}", gff_path.display()))?;
    let gff = Gff::from_bytes(bytes).with_context(|| format!("parsing {}", gff_path.display()))?;
    let chunk = gff
        .find(FourCC(*b"FONT"), id)
        .with_context(|| format!("no FONT chunk with id {id} found"))?;
    Ok(parse(gff.read_chunk(chunk))?.header)
}
