use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use gff_edit::Gff;

#[derive(Parser)]
#[command(
    name = "gff-cat",
    version,
    about = "Inspect SSI's GFF files (Dark Sun).",
    long_about = "Inspect and dump SSI's GFF container files. \
                  Part of the OpenDS toolkit; see the project's \
                  docs/file-formats.md for the on-disk layout."
)]
struct Cli {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Print the file header and a TOC summary.
    Info {
        /// Path to a GFF file.
        file: PathBuf,
    },
    /// List every indexed chunk: kind, id, offset, length.
    List {
        /// Path to a GFF file.
        file: PathBuf,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Cmd::Info { file } => cmd_info(file),
        Cmd::List { file } => cmd_list(file),
    }
}

fn cmd_info(file: PathBuf) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;
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
    let indexed_chunks = gff.chunks().len();
    let segmented_chunks: usize = gff
        .types()
        .iter()
        .filter_map(|t| t.is_segmented().then_some(t.chunk_count))
        .sum();

    println!(
        "types:          {} total ({} indexed, {} segmented)",
        total_types,
        total_types - seg_types,
        seg_types
    );
    println!(
        "chunks:         {} indexed, {} segmented (not yet resolvable)",
        indexed_chunks, segmented_chunks
    );
    for t in gff.types() {
        let tag = if t.is_segmented() { "  (segmented)" } else { "" };
        println!("  '{:<4}' × {}{}", t.kind, t.chunk_count, tag);
    }
    Ok(())
}

fn cmd_list(file: PathBuf) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;
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
    let seg: Vec<_> = gff.types().iter().filter(|t| t.is_segmented()).collect();
    if !seg.is_empty() {
        eprintln!();
        eprintln!(
            "note: {} segmented type(s) not listed (v0.1 limitation):",
            seg.len()
        );
        for t in &seg {
            let s = t.segmented.as_ref().unwrap();
            eprintln!(
                "  '{}' × {} chunks across {} seg entries",
                t.kind,
                t.chunk_count,
                s.seg_entries.len()
            );
        }
    }
    Ok(())
}
