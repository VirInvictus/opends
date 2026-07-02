use std::io::Write;
use std::path::PathBuf;

use anyhow::{Context, Result, anyhow, bail};
use clap::{Parser, Subcommand};
use gff_edit::{FourCC, Gff};
use serde::Serialize;

// Embedded chunk-type catalogue. Mirrored from
// `docs/file-formats.md` §1.
const KIND_CATALOGUE: &[(&[u8; 4], &str)] = &[
    // Structural
    (
        b"GFFI",
        "Magic / structural; also wraps the file's primary cross-reference table.",
    ),
    (b"FORM", "Form chunk (IFF-like grouping)."),
    (b"GFRE", "Free / freelist (deleted entries)."),
    (b"GTOC", "Table of contents."),
    // Graphics
    (b"PAL ", "VGA 256-color palette (768 bytes, 6-bit RGB)."),
    (b"BMP ", "Bitmap, one or more frames."),
    (b"BMAP", "Bump map."),
    (b"PORT", "Character portrait."),
    (b"WALL", "Wall graphic."),
    (b"ICON", "Icon (1 to 4 frames)."),
    (b"TILE", "Tile graphic."),
    (b"TMAP", "Texture map."),
    (b"TXRF", "Texture reference."),
    (b"OMAP", "Opacity map."),
    (b"CMAP", "Color map / remap table."),
    (b"CBMP", "Color bitmap."),
    (b"FONT", "Font (uses palette)."),
    (b"BMA ", "Cinematic binary file."),
    (b"ACF ", "Cinematic binary script."),
    // Maps and world
    (b"RMAP", "Region tile map."),
    (b"GMAP", "Region map flags (passability, height, etc.)."),
    (b"ETAB", "Object entry table (entities placed in region)."),
    (b"MONR", "Monsters by region IDs and level."),
    // Audio
    (b"MSEQ", "XMIDI sequence file (master XMI)."),
    (b"PSEQ", "XMI variant for PC Speaker."),
    (b"FSEQ", "XMI variant for FM (AdLib / Sound Blaster OPL)."),
    (b"LSEQ", "XMI variant for Roland LAPC / MT-32."),
    (b"GSEQ", "XMI variant for General MIDI."),
    (b"CSEQ", "Clock sequence."),
    (b"MGTL", "Global timbre library."),
    (b"BVOC", "Background-play sample (VOC)."),
    (b"FVOC", "Foreground-play sample (VOC)."),
    (b"SINF", "Sound card info."),
    (b"ADV ", "AIL/MEL driver."),
    (b"DADV", "Dynamic AIL driver (MEL 1.x)."),
    (b"DRV ", "Generic driver."),
    // UI
    (b"WIND", "Window definition."),
    (b"DBOX", "Dialog box."),
    (b"EBOX", "Edit box."),
    (b"BUTN", "Button."),
    (b"MENU", "Menu."),
    (b"SBAR", "Scroll bar."),
    (b"APFM", "Application form (likely; TBD)."),
    (b"ACCL", "Accelerator (keyboard shortcut table)."),
    // Game data and objects
    (b"IT1R", "Items."),
    (b"OJFF", "Object data (general)."),
    (
        b"RDFF",
        "Record data; distinct schemas per game (DS1/DS2/DSO) for item, combat, char, mini, player, entity records.",
    ),
    (b"FNFO", "Object data table."),
    (b"RDAT", "Names."),
    (b"NAME", "Names."),
    (b"TEXT", "Generic text resources."),
    (b"MERR", "Error messages."),
    (b"ETME", "Copyright / credits text."),
    (b"SPIN", "Spell text."),
    (b"SCMD", "Animation script command table."),
    (b"SJMP", "Animation script jump table."),
    (b"POBJ", "Polymesh object database."),
    // Scripting
    (b"GPL ", "Compiled GPL bytecode."),
    (b"MAS ", "Compiled GPL master script."),
    (b"GPLI", "GPL 'I' data (incompletely documented)."),
    (b"GPLX", "GPL index file."),
    // Save / character
    (b"CHAR", "Saved character slot."),
    (b"SPST", "Spell list bitmask."),
    (b"PSST", "Psionic list bytes."),
    (b"PSIN", "Psionic and sphere selection."),
    (b"CACT", "Valid character ID flag."),
    (b"STXT", "Save text."),
    (b"SAVE", "Save metadata."),
];

/// Chunk kinds whose payload is plain CRLF-delimited DOS text.
/// Eligible for `dump-text` / `pack-text`.
const TEXT_KINDS: &[&[u8; 4]] = &[b"TEXT", b"ETME", b"MERR", b"NAME", b"SPIN"];

fn is_text_kind(kind: FourCC) -> bool {
    TEXT_KINDS
        .iter()
        .any(|k| k.as_slice() == kind.as_bytes().as_slice())
}

fn kind_description(kind: FourCC) -> Option<&'static str> {
    KIND_CATALOGUE
        .iter()
        .find(|(k, _)| k.as_slice() == kind.as_bytes().as_slice())
        .map(|(_, d)| *d)
}

/// FOURCC formatted for use in a filename: trailing spaces stripped.
/// `GPL ` becomes `GPL`; `TEXT` stays `TEXT`.
fn kind_filename(kind: FourCC) -> String {
    String::from_utf8_lossy(kind.as_bytes())
        .trim_end()
        .to_string()
}

/// Parse a 3- or 4-char FOURCC string, padding with a trailing space
/// for 3-char inputs (matches the DOS convention: `GPL` → `"GPL "`).
fn parse_kind_padded(s: &str) -> Result<FourCC> {
    let bytes = s.as_bytes();
    if bytes.len() < 3 || bytes.len() > 4 {
        bail!("FOURCC must be 3 or 4 characters: {s:?}");
    }
    let mut padded = [b' '; 4];
    padded[..bytes.len()].copy_from_slice(bytes);
    Ok(FourCC::new(padded))
}

#[derive(Parser)]
#[command(
    name = "gff-cat",
    version,
    about = "Inspect, edit, and dump SSI's GFF files (Dark Sun)."
)]
struct Cli {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Print the file header and a TOC summary.
    Info {
        file: PathBuf,
        /// Emit JSON instead of human-readable text.
        #[arg(long)]
        json: bool,
    },
    /// List every chunk: kind, id, offset, length.
    List {
        file: PathBuf,
        /// Emit a JSON array instead of a fixed-width table.
        #[arg(long)]
        json: bool,
    },
    /// Extract a chunk's bytes to stdout / a file, or every chunk to a
    /// directory with `--all`.
    Extract {
        /// Path to a GFF file.
        file: PathBuf,
        /// Four-character chunk kind (omit when `--all` is set).
        kind: Option<String>,
        /// Resource id of the chunk to extract (omit when `--all`).
        id: Option<i32>,
        /// Output path. Single-chunk mode: file or `-` for stdout
        /// (default stdout). `--all` mode: required output directory.
        #[arg(short = 'o', long = "output")]
        output: Option<PathBuf>,
        /// Dump every chunk to `<output>/<kind>-<id>.bin`. Requires
        /// `-o <dir>`.
        #[arg(long, requires = "output")]
        all: bool,
    },
    /// Replace a chunk's bytes and write the modified GFF to `--output`.
    Replace {
        file: PathBuf,
        kind: String,
        id: i32,
        bytes_file: PathBuf,
        #[arg(short = 'o', long = "output")]
        output: PathBuf,
    },
    /// Dump TEXT/ETME/MERR/NAME/SPIN chunks as `<kind>-<id>.txt`
    /// files. Bytes are written verbatim (DOS CRLF preserved).
    DumpText {
        file: PathBuf,
        /// Output directory; created if missing.
        #[arg(short = 'o', long = "output")]
        output: PathBuf,
    },
    /// Read every `<kind>-<id>.txt` in `<dir>` and replace the
    /// matching chunks in `<file>`, writing the result to `--output`.
    PackText {
        file: PathBuf,
        dir: PathBuf,
        #[arg(short = 'o', long = "output")]
        output: PathBuf,
    },
    /// Look up a FOURCC's description in the embedded catalogue.
    Kind {
        /// A 3- or 4-character FOURCC (e.g. `TEXT`, `GPL`, `BMP`).
        fourcc: Option<String>,
        /// Print every entry in the catalogue.
        #[arg(long)]
        list: bool,
    },
    /// Per-chunk describer: kind purpose + size + chunk-specific
    /// facts (bitmap dimensions, text preview, etc.). Combines
    /// what a user would otherwise get by running `kind` +
    /// `info` + `extract` separately.
    What {
        file: PathBuf,
        /// 3- or 4-character chunk kind (e.g. `BMP`, `GPL`,
        /// `TEXT`).
        kind: String,
        id: i32,
    },
}

fn main() -> Result<()> {
    install_pipe_exit_hook();
    let cli = Cli::parse();
    match cli.command {
        Cmd::Info { file, json } => cmd_info(file, json),
        Cmd::List { file, json } => cmd_list(file, json),
        Cmd::Extract {
            file,
            kind,
            id,
            output,
            all,
        } => cmd_extract(file, kind, id, output, all),
        Cmd::Replace {
            file,
            kind,
            id,
            bytes_file,
            output,
        } => cmd_replace(file, kind, id, bytes_file, output),
        Cmd::DumpText { file, output } => cmd_dump_text(file, output),
        Cmd::PackText { file, dir, output } => cmd_pack_text(file, dir, output),
        Cmd::Kind { fourcc, list } => cmd_kind(fourcc, list),
        Cmd::What { file, kind, id } => cmd_what(file, kind, id),
    }
}

fn install_pipe_exit_hook() {
    let prev = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let message = info
            .payload()
            .downcast_ref::<String>()
            .map(String::as_str)
            .or_else(|| info.payload().downcast_ref::<&str>().copied())
            .unwrap_or("");
        if message.contains("Broken pipe") {
            std::process::exit(0);
        }
        prev(info);
    }));
}

#[derive(Serialize)]
struct InfoJson<'a> {
    size: usize,
    header: &'a gff_edit::FileHeader,
    types: &'a [gff_edit::TypeInfo],
}

fn cmd_info(file: PathBuf, json: bool) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;

    if json {
        let payload = InfoJson {
            size: gff.len(),
            header: gff.header(),
            types: gff.types(),
        };
        serde_json::to_writer_pretty(std::io::stdout().lock(), &payload).context("writing JSON")?;
        println!();
        return Ok(());
    }

    let h = gff.header();
    let identity = std::str::from_utf8(&h.identity).unwrap_or("?");
    println!("file:           {}", file.display());
    println!("size:           {} bytes", gff.len());
    println!("identity:       {:?}", identity);
    println!(
        "version:        {:#010x}  (major {})",
        h.version,
        h.major_version()
    );
    println!("data_location:  {}", h.data_location);
    println!("toc_location:   {}", h.toc_location);
    println!("toc_length:     {}", h.toc_length);
    println!("file_flags:     {:#x}", h.file_flags);
    println!("data0:          {}", h.data0);

    let total_types = gff.types().len();
    let seg_types = gff.types().iter().filter(|t| t.is_segmented()).count();
    let total_chunks = gff.chunks().len();
    let segmented_chunks: usize = gff
        .types()
        .iter()
        .filter_map(|t| t.is_segmented().then_some(t.chunk_count))
        .sum();
    let indexed_chunks = total_chunks - segmented_chunks;

    println!(
        "types:          {} total ({} indexed, {} segmented)",
        total_types,
        total_types - seg_types,
        seg_types
    );
    println!(
        "chunks:         {} total ({} indexed, {} resolved segmented)",
        total_chunks, indexed_chunks, segmented_chunks
    );
    for t in gff.types() {
        let tag = if t.is_segmented() {
            "  (segmented)"
        } else {
            ""
        };
        println!("  '{:<4}' × {}{}", t.kind, t.chunk_count, tag);
    }
    Ok(())
}

fn cmd_list(file: PathBuf, json: bool) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;
    if json {
        serde_json::to_writer_pretty(std::io::stdout().lock(), gff.chunks())
            .context("writing JSON")?;
        println!();
        return Ok(());
    }
    println!(
        "{:<6}  {:>10}  {:>10}  {:>10}",
        "kind", "id", "offset", "length"
    );
    for c in gff.chunks() {
        println!(
            "{:<6}  {:>10}  {:>10}  {:>10}",
            format!("'{}'", c.kind),
            c.id,
            c.location,
            c.length
        );
    }
    Ok(())
}

fn cmd_extract(
    file: PathBuf,
    kind: Option<String>,
    id: Option<i32>,
    output: Option<PathBuf>,
    all: bool,
) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;

    if all {
        let out_dir = output.ok_or_else(|| anyhow!("--all requires -o <dir>"))?;
        std::fs::create_dir_all(&out_dir)
            .with_context(|| format!("creating {}", out_dir.display()))?;
        for c in gff.chunks() {
            let name = format!("{}-{}.bin", kind_filename(c.kind), c.id);
            let path = out_dir.join(&name);
            std::fs::write(&path, gff.read_chunk(c))
                .with_context(|| format!("writing {}", path.display()))?;
        }
        eprintln!(
            "wrote {} chunks to {}",
            gff.chunks().len(),
            out_dir.display()
        );
        return Ok(());
    }

    let kind = kind.ok_or_else(|| anyhow!("kind is required (or pass --all)"))?;
    let id = id.ok_or_else(|| anyhow!("id is required (or pass --all)"))?;
    let fourcc = parse_kind_padded(&kind)?;
    let bytes = gff
        .read(fourcc, id)
        .ok_or_else(|| anyhow!("no chunk '{}' id={} in {}", fourcc, id, file.display()))?;

    match output {
        Some(path) if path.as_os_str() != "-" => {
            std::fs::write(&path, bytes)
                .with_context(|| format!("writing chunk bytes to {}", path.display()))?;
        }
        _ => {
            std::io::stdout()
                .write_all(bytes)
                .context("writing chunk bytes to stdout")?;
        }
    }
    Ok(())
}

fn cmd_replace(
    file: PathBuf,
    kind: String,
    id: i32,
    bytes_file: PathBuf,
    output: PathBuf,
) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;
    let fourcc = parse_kind_padded(&kind)?;
    let new_bytes = std::fs::read(&bytes_file)
        .with_context(|| format!("reading replacement bytes from {}", bytes_file.display()))?;
    let result = gff
        .replace_chunk(fourcc, id, &new_bytes)
        .with_context(|| format!("replacing '{}' id={} in {}", fourcc, id, file.display()))?;
    std::fs::write(&output, &result)
        .with_context(|| format!("writing modified GFF to {}", output.display()))?;
    Ok(())
}

fn cmd_dump_text(file: PathBuf, output: PathBuf) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;
    std::fs::create_dir_all(&output).with_context(|| format!("creating {}", output.display()))?;
    let mut count = 0usize;
    for c in gff.chunks() {
        if !is_text_kind(c.kind) {
            continue;
        }
        let name = format!("{}-{}.txt", kind_filename(c.kind), c.id);
        let path = output.join(&name);
        std::fs::write(&path, gff.read_chunk(c))
            .with_context(|| format!("writing {}", path.display()))?;
        count += 1;
    }
    eprintln!("wrote {count} text chunks to {}", output.display());
    Ok(())
}

fn cmd_pack_text(file: PathBuf, dir: PathBuf, output: PathBuf) -> Result<()> {
    let original = std::fs::read(&file).with_context(|| format!("reading {}", file.display()))?;
    let mut current = original;

    let mut replacements: Vec<(FourCC, i32, Vec<u8>)> = Vec::new();
    for entry in std::fs::read_dir(&dir).with_context(|| format!("reading {}", dir.display()))? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("txt") {
            continue;
        }
        let stem = path
            .file_stem()
            .and_then(|s| s.to_str())
            .ok_or_else(|| anyhow!("non-utf8 filename: {}", path.display()))?;
        let (kind_str, id_str) = stem
            .rsplit_once('-')
            .ok_or_else(|| anyhow!("filename must be <kind>-<id>.txt: {}", path.display()))?;
        let id: i32 = id_str
            .parse()
            .with_context(|| format!("parsing id from {}", path.display()))?;
        let kind = parse_kind_padded(kind_str)
            .with_context(|| format!("parsing kind from {}", path.display()))?;
        let bytes = std::fs::read(&path).with_context(|| format!("reading {}", path.display()))?;
        replacements.push((kind, id, bytes));
    }

    if replacements.is_empty() {
        eprintln!("note: no <kind>-<id>.txt files found in {}", dir.display());
    }

    // Sort for deterministic output ordering.
    replacements.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()).then(a.1.cmp(&b.1)));

    for (kind, id, bytes) in &replacements {
        let gff = Gff::from_bytes(current.clone())?;
        current = gff
            .replace_chunk(*kind, *id, bytes)
            .with_context(|| format!("replacing '{}' id={}", kind, id))?;
    }

    std::fs::write(&output, &current)
        .with_context(|| format!("writing to {}", output.display()))?;
    eprintln!(
        "packed {} text chunks into {}",
        replacements.len(),
        output.display()
    );
    Ok(())
}

fn cmd_what(file: PathBuf, kind: String, id: i32) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;
    let fc = parse_kind_padded(&kind)?;
    let bytes = gff
        .read(fc, id)
        .ok_or_else(|| anyhow!("no chunk '{}' id={} in {}", fc, id, file.display()))?;
    let kind_desc = kind_description(fc).unwrap_or("(no catalogue entry)");
    println!("{fc} id={id}  ({len} bytes)", len = bytes.len());
    println!("  purpose: {kind_desc}");
    // Per-kind chunk-specific facts. Best-effort: surface
    // whatever the chunk's header makes cheaply available without
    // calling the per-tool decoders. This is the entry point a
    // modder uses to decide whether to invoke image-extract,
    // gpl-disasm, save-inspect, etc.
    let fc_bytes = fc.as_bytes();
    match fc_bytes {
        b"BMP " | b"PORT" | b"ICON" | b"BMAP" | b"OMAP" | b"TILE" => {
            // Bitmap header: u32 chunk_size + u16 frame_count +
            // u32 × frame_count frame_offsets + per-frame u16 w +
            // u16 h. Reads via the documented offsets without
            // pulling image-extract as a dep.
            if bytes.len() >= 6 {
                let frame_count = u16::from_le_bytes([bytes[4], bytes[5]]);
                println!("  bitmap: {frame_count} frame(s)");
                let table_end = 6 + 4 * frame_count as usize;
                if frame_count >= 1 && bytes.len() >= table_end + 4 {
                    let off = u32::from_le_bytes([bytes[6], bytes[7], bytes[8], bytes[9]]) as usize;
                    if off + 4 <= bytes.len() {
                        let w = u16::from_le_bytes([bytes[off], bytes[off + 1]]);
                        let h = u16::from_le_bytes([bytes[off + 2], bytes[off + 3]]);
                        println!("  frame 0 size: {w} x {h}");
                    }
                }
            }
            println!(
                "  next step: `image-extract {} --kind {} --id {} -o sprite.png`",
                file.display(),
                kind.trim_end(),
                id
            );
        }
        b"PAL " | b"CPAL" => {
            println!("  palette: 256 entries (768 bytes 6-bit RGB)");
            println!(
                "  next step: pass via `--palette {}:{kind}:{id}` to image-extract / region-render",
                file.display()
            );
        }
        b"GPL " | b"MAS " => {
            println!("  GPL bytecode chunk");
            println!(
                "  next step: `gpl-disasm {} --kind {} --id {}`",
                file.display(),
                kind.trim_end(),
                id
            );
        }
        b"TEXT" | b"ETME" | b"MERR" | b"NAME" | b"SPIN" => {
            // Plain DOS text (CRLF). Show the first ~80 chars,
            // CRLF normalised, as a preview.
            let preview_end = bytes.len().min(160);
            let preview = String::from_utf8_lossy(&bytes[..preview_end])
                .replace("\r\n", "  ")
                .replace('\n', "  ");
            let truncated = preview.len() > 80;
            let head: String = preview.chars().take(80).collect();
            println!(
                "  text preview: {head:?}{}",
                if truncated { " ..." } else { "" }
            );
            println!(
                "  next step: `gff-cat dump-text {} -o text-dir/`",
                file.display()
            );
        }
        b"CHAR" | b"SAVE" | b"STXT" | b"PSIN" | b"PSST" | b"SPST" | b"CACT" | b"PREF" | b"GREQ"
        | b"ETAB" => {
            println!("  save-game record");
            println!(
                "  next step: `python3 tools/save-inspect/save-inspect.py {}`",
                file.display()
            );
        }
        b"RMAP" | b"GMAP" => {
            println!("  region tile / passability map");
            println!(
                "  next step: `region-render {} -o region.png`",
                file.display()
            );
        }
        _ => {
            // No tool dispatch hint; the user is on their own.
            // The kind description above is the best signpost.
        }
    }
    Ok(())
}

fn cmd_kind(fourcc: Option<String>, list: bool) -> Result<()> {
    if list {
        for (k, desc) in KIND_CATALOGUE {
            println!("{}  {desc}", String::from_utf8_lossy(*k));
        }
        return Ok(());
    }
    let fourcc = fourcc.ok_or_else(|| anyhow!("provide a FOURCC or pass --list"))?;
    let fc = parse_kind_padded(&fourcc)?;
    match kind_description(fc) {
        Some(desc) => println!("{fc}  {desc}"),
        None => println!("{fc}  (no catalogue entry)"),
    }
    Ok(())
}
