use std::io::Write;
use std::path::PathBuf;

use anyhow::{Context, Result, anyhow};
use clap::{Parser, Subcommand};
use gff_edit::{FourCC, Gff};

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
    /// List every chunk: kind, id, offset, length.
    List {
        /// Path to a GFF file.
        file: PathBuf,
    },
    /// Write a chunk's raw bytes to stdout (or a file via -o).
    Extract {
        /// Path to a GFF file.
        file: PathBuf,
        /// Four-character chunk kind (e.g. "GPL ", "ETME", "TILE").
        kind: String,
        /// Resource id of the chunk to extract.
        id: i32,
        /// Output path. Defaults to stdout when omitted or "-".
        #[arg(short = 'o', long = "output")]
        output: Option<PathBuf>,
    },
}

fn main() -> Result<()> {
    install_pipe_exit_hook();
    let cli = Cli::parse();
    match cli.command {
        Cmd::Info { file } => cmd_info(file),
        Cmd::List { file } => cmd_list(file),
        Cmd::Extract { file, kind, id, output } => cmd_extract(file, kind, id, output),
    }
}

/// Rust's `println!` panics when stdout is a closed pipe (e.g. piping
/// through `head` or `less`). Convert that specific panic into a clean
/// exit so shell pipelines work. Stdlib-only; no signal handling.
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
    Ok(())
}

fn cmd_extract(file: PathBuf, kind: String, id: i32, output: Option<PathBuf>) -> Result<()> {
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;
    let fourcc = FourCC::from_str(&kind)
        .with_context(|| format!("parsing FOURCC {kind:?} (must be exactly 4 characters)"))?;
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
