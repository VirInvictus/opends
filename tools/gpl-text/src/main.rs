//! `gpl-text`: fixed-length GPL string editing. List the string
//! operands of a chunk (with exact packed spans), validate and
//! apply a same-length replacement, and verify the result. The
//! editing rules are GPLDocument's (DarkSunTools, Apache-2.0):
//! same character count implies the same packed byte count, 7-bit
//! symbols only, and no length changes (those are gpl-asm detour
//! territory, see docs/reference/detour-repairs.md).

use anyhow::{Context, Result};
use clap::Parser;
use gff_edit::{FourCC, Gff};
use gpl_text::{apply, collect_spans, validate_replacement};
use std::fs;
use std::path::PathBuf;

#[derive(Parser)]
#[command(about = "Fixed-length GPL string editing for Dark Sun chunks")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(clap::Subcommand)]
enum Command {
    /// List every editable string operand with its packed span.
    List {
        /// GFF file (typically GPLDATA.GFF).
        gff: PathBuf,
        /// Chunk kind (GPL or MAS).
        #[arg(long, default_value = "GPL")]
        kind: String,
        /// Chunk id.
        #[arg(long)]
        id: i32,
    },
    /// Validate and apply a same-length replacement for one string.
    Edit {
        /// GFF file to modify.
        gff: PathBuf,
        /// Chunk kind (GPL or MAS).
        #[arg(long, default_value = "GPL")]
        kind: String,
        /// Chunk id.
        #[arg(long)]
        id: i32,
        /// The string operand's index (from `list`).
        #[arg(long)]
        index: usize,
        /// The replacement text: exactly the original's character
        /// count, 7-bit symbols, no 0x03.
        #[arg(long)]
        text: String,
    },
}

fn kind_fourcc(kind: &str) -> Result<FourCC> {
    let bytes = kind.as_bytes();
    let four = match bytes.len() {
        3 => [bytes[0], bytes[1], bytes[2], b' '],
        4 => [bytes[0], bytes[1], bytes[2], bytes[3]],
        _ => anyhow::bail!("kind must be 3 or 4 characters (GPL or MAS)"),
    };
    Ok(FourCC(four))
}

fn load_chunk(gff: &PathBuf, kind: &str, id: i32) -> Result<(Gff, Vec<u8>, usize)> {
    let four = kind_fourcc(kind)?;
    let bytes = fs::read(gff).with_context(|| format!("reading {}", gff.display()))?;
    let parsed = Gff::from_bytes(bytes).with_context(|| format!("parsing {}", gff.display()))?;
    let body = parsed
        .read(four, id)
        .with_context(|| format!("no {kind} chunk with id {id} in {}", gff.display()))?
        .to_vec();
    let index = parsed
        .chunks()
        .iter()
        .position(|c| c.kind == four && c.id == id)
        .with_context(|| format!("no {kind} chunk with id {id} in {}", gff.display()))?;
    Ok((parsed, body, index))
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::List { gff, kind, id } => {
            let (_, chunk, _) = load_chunk(&gff, &kind, id)?;
            let (spans, warning) = collect_spans(&chunk).context("collecting string spans")?;
            for span in &spans {
                println!(
                    "#{:<4} offset {:#06x} packed {:>3}B chars {:>2} {:?} {:?}",
                    span.index,
                    span.payload_offset,
                    span.packed_len,
                    span.text.chars().count(),
                    span.sub_type,
                    span.text
                );
            }
            if let Some(w) = &warning {
                println!("warning: {w}");
            }
            println!("{} string(s)", spans.len());
        }
        Command::Edit {
            gff,
            kind,
            id,
            index,
            text,
        } => {
            let (parsed, chunk, chunk_index) = load_chunk(&gff, &kind, id)?;
            let (spans, warning) = collect_spans(&chunk).context("collecting string spans")?;
            if let Some(w) = &warning {
                println!("warning: {w}");
            }
            let span = spans.get(index).with_context(|| {
                format!("string index {index} out of range ({} spans)", spans.len())
            })?;
            let replacement = validate_replacement(span, &text)?;
            let patched_chunk = apply(&chunk, span, &replacement);
            let patched_gff = parsed
                .replace_chunk(kind_fourcc(&kind)?, id, &patched_chunk)
                .with_context(|| format!("replacing {kind} {id}"))?;
            fs::write(&gff, patched_gff).with_context(|| format!("writing {}", gff.display()))?;
            let _ = chunk_index;
            println!(
                "string #{index} in {kind} {id}: {:?} -> {:?} (packed {}B at {:#x}); {} written",
                span.text,
                text,
                replacement.len(),
                span.payload_offset,
                gff.display()
            );
        }
    }
    Ok(())
}
