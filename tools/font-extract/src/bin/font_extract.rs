//! `font-extract`: pull a FONT chunk out of a GFF and write an
//! editable glyph sheet: one PNG per glyph plus a manifest of
//! widths, so `font-pack` can rebuild the chunk byte-exactly after
//! edits. Renders a preview grid of all 256 glyphs, and can render
//! a text string through a transliteration rules file to preview
//! how translated text looks with the font.

use anyhow::{Context, Result};
use clap::Parser;
use font_extract::{FontGlyph, FontResource, GLYPH_COUNT, GLYPH_HEIGHT, parse, translit};
use gff_edit::{FourCC, Gff};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Parser)]
#[command(about = "Extract a Dark Sun FONT chunk into editable glyph PNGs")]
struct Cli {
    /// GFF file holding the FONT chunk (typically RESOURCE.GFF).
    gff: PathBuf,
    /// Output directory (created if absent).
    #[arg(short, long, default_value = "font-out")]
    output: PathBuf,
    /// Font chunk id (the shipped fonts are FONT 100).
    #[arg(long, default_value_t = 100)]
    id: i32,
    /// Preview pixel scale.
    #[arg(long, default_value_t = 2)]
    scale: u32,
    /// Render TEXT through a transliteration rules file with this
    /// font, writing <output>/text.png. The rules map displayed
    /// characters to game glyph codes (see README).
    #[arg(long)]
    render_text: Option<String>,
    #[arg(long, requires = "render_text")]
    rules: Option<PathBuf>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let bytes = fs::read(&cli.gff).with_context(|| format!("reading {}", cli.gff.display()))?;
    let gff = Gff::from_bytes(bytes).with_context(|| format!("parsing {}", cli.gff.display()))?;
    let chunk = gff
        .find(FourCC(*b"FONT"), cli.id)
        .with_context(|| format!("no FONT chunk with id {} found", cli.id))?;
    let body = gff.read_chunk(chunk);
    let font = parse(body).context("parsing FONT chunk")?;

    fs::create_dir_all(&cli.output)?;
    write_manifest(&cli.output, &font)?;
    write_glyph_pngs(&cli.output, &font)?;
    write_preview(&cli.output.join("preview.png"), &font, cli.scale)?;
    if let Some(text) = &cli.render_text {
        let rules = match &cli.rules {
            Some(path) => {
                let text = fs::read_to_string(path)
                    .with_context(|| format!("reading {}", path.display()))?;
                Some(
                    translit::parse_rules(&text)
                        .with_context(|| format!("parsing {}", path.display()))?,
                )
            }
            None => None,
        };
        let png = render_text(&font, text, rules.as_deref(), cli.scale);
        write_gray_png(&cli.output.join("text.png"), &png.0, png.1, png.2)?;
    }

    println!(
        "extracted {} glyphs (font height {}) to {}",
        font.glyphs.len(),
        GLYPH_HEIGHT,
        cli.output.display()
    );
    Ok(())
}

fn write_manifest(out: &Path, font: &FontResource) -> Result<()> {
    #[derive(serde::Serialize)]
    struct GlyphRow {
        code: usize,
        width: usize,
    }
    #[derive(serde::Serialize)]
    struct Manifest {
        glyph_height: usize,
        glyph_count: usize,
        glyphs: Vec<GlyphRow>,
    }
    let manifest = Manifest {
        glyph_height: GLYPH_HEIGHT,
        glyph_count: GLYPH_COUNT,
        glyphs: font
            .glyphs
            .iter()
            .map(|g| GlyphRow {
                code: g.code,
                width: g.width,
            })
            .collect(),
    };
    fs::write(
        out.join("manifest.json"),
        serde_json::to_string_pretty(&manifest)? + "\n",
    )?;
    Ok(())
}

fn write_glyph_pngs(out: &Path, font: &FontResource) -> Result<()> {
    let dir = out.join("glyphs");
    fs::create_dir_all(&dir)?;
    for glyph in &font.glyphs {
        // Zero-width glyphs are legal in the format (a 2-byte entry
        // holding only the width); PNG cannot be zero-width, so the
        // manifest's width field is their whole representation.
        if glyph.width == 0 {
            continue;
        }
        write_gray_png(
            &dir.join(format!("glyph-{:03}.png", glyph.code)),
            &glyph.pixels,
            glyph.width as u32,
            GLYPH_HEIGHT as u32,
        )?;
    }
    Ok(())
}

/// Grayscale PNG writer shared by glyphs, previews, and text
/// renders. Pixel value 0 reads as background.
fn write_gray_png(path: &Path, pixels: &[u8], width: u32, height: u32) -> Result<()> {
    let file = fs::File::create(path).with_context(|| format!("creating {}", path.display()))?;
    let mut encoder = png::Encoder::new(std::io::BufWriter::new(file), width, height);
    encoder.set_color(png::ColorType::Grayscale);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header().context("png header")?;
    writer.write_image_data(pixels).context("png data")?;
    writer.finish().context("png finish")?;
    Ok(())
}

/// A 16x16 grid of all glyphs, scaled, one-pixel gutters.
fn write_preview(path: &Path, font: &FontResource, scale: u32) -> Result<()> {
    let cell_w = font
        .glyphs
        .iter()
        .map(|g| g.width)
        .max()
        .unwrap_or(1)
        .max(4) as u32;
    let cell_h = GLYPH_HEIGHT as u32;
    let cols = 16u32;
    let rows = GLYPH_COUNT as u32 / cols;
    let w = (cols * cell_w + cols + 1) * scale;
    let h = (rows * cell_h + rows + 1) * scale;

    let mut image = vec![255u8; (w * h) as usize];
    for (idx, glyph) in font.glyphs.iter().enumerate() {
        let gx = idx as u32 % cols;
        let gy = idx as u32 / cols;
        let cx = (gx * cell_w + gx + 1) * scale;
        let cy = (gy * cell_h + gy + 1) * scale;
        for y in 0..cell_h.min(GLYPH_HEIGHT as u32) {
            for x in 0..glyph.width as u32 {
                let value = glyph.pixels[y as usize * glyph.width + x as usize];
                if value == 0 {
                    continue;
                }
                for sy in 0..scale {
                    for sx in 0..scale {
                        let px = cx + x * scale + sx;
                        let py = cy + y * scale + sy;
                        if px < w && py < h {
                            image[(py * w + px) as usize] = value;
                        }
                    }
                }
            }
        }
    }
    write_gray_png(path, &image, w, h)
}

/// Render TEXT left to right through the font, optionally mapping
/// display characters to game glyph codes first. Returns
/// (pixels, width, height).
fn render_text(
    font: &FontResource,
    text: &str,
    rules: Option<&[translit::Rule]>,
    scale: u32,
) -> (Vec<u8>, u32, u32) {
    let encoded = match rules {
        Some(rules) => translit::encode_to_game_charset(text, rules),
        None => text.to_string(),
    };
    let glyphs: Vec<Option<&FontGlyph>> = encoded
        .chars()
        .map(|c| font.glyphs.get(c as usize).or_else(|| font.glyphs.first()))
        .collect();

    let advance = |g: &FontGlyph| (g.width as u32 + 1) * scale;
    let w_total: u32 = glyphs
        .iter()
        .map(|g| g.map(advance).unwrap_or(scale))
        .sum::<u32>()
        + scale;
    let h_total = (GLYPH_HEIGHT as u32 + 2) * scale;
    let mut image = vec![255u8; (w_total * h_total) as usize];

    let mut cursor = scale;
    for slot in &glyphs {
        if let Some(glyph) = slot {
            for y in 0..GLYPH_HEIGHT as u32 {
                for x in 0..glyph.width as u32 {
                    let value = glyph.pixels[y as usize * glyph.width + x as usize];
                    if value == 0 {
                        continue;
                    }
                    for sy in 0..scale {
                        for sx in 0..scale {
                            let px = cursor + x * scale + sx;
                            let py = scale + y * scale + sy;
                            if px < w_total && py < h_total {
                                image[(py * w_total + px) as usize] = value;
                            }
                        }
                    }
                }
            }
            cursor += advance(glyph);
        } else {
            cursor += scale;
        }
    }
    (image, w_total, h_total)
}
