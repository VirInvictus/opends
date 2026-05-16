use std::path::PathBuf;

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gpl_asm::encode;
use gpl_disasm::DisasmResult;

#[derive(Parser)]
#[command(
    name = "gpl-asm",
    version,
    about = "Reassemble SSI's GPL bytecode from a gpl-disasm JSON file."
)]
struct Cli {
    /// Path to a `gpl-disasm --json` output file (one chunk).
    /// Use `--all-from <dir>` to bulk-encode every `*.json` in a
    /// directory.
    input: Option<PathBuf>,
    /// Bulk mode: read every `*.json` in this directory and write a
    /// matching `*.bin` per chunk into `--output <dir>`.
    #[arg(long = "all-from", requires = "output")]
    all_from: Option<PathBuf>,
    /// Output path: file in single-chunk mode, directory in
    /// `--all-from` mode. Single-chunk default is stdout.
    #[arg(short = 'o', long = "output")]
    output: Option<PathBuf>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    if let Some(src_dir) = cli.all_from {
        let out_dir = cli
            .output
            .ok_or_else(|| anyhow!("--all-from requires -o <dir>"))?;
        std::fs::create_dir_all(&out_dir)
            .with_context(|| format!("creating {}", out_dir.display()))?;
        let mut encoded_count = 0usize;
        let mut skipped_count = 0usize;
        let mut entries: Vec<PathBuf> = std::fs::read_dir(&src_dir)
            .with_context(|| format!("reading {}", src_dir.display()))?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("json"))
            .collect();
        entries.sort();
        for path in entries {
            let body = std::fs::read_to_string(&path)
                .with_context(|| format!("reading {}", path.display()))?;
            let result: DisasmResult = serde_json::from_str(&body)
                .with_context(|| format!("parsing {}", path.display()))?;
            let stem = path
                .file_stem()
                .and_then(|s| s.to_str())
                .ok_or_else(|| anyhow!("bad stem on {}", path.display()))?;
            let out_path = out_dir.join(format!("{stem}.bin"));
            match encode(&result) {
                Ok(bytes) => {
                    std::fs::write(&out_path, bytes)
                        .with_context(|| format!("writing {}", out_path.display()))?;
                    encoded_count += 1;
                }
                Err(e) => {
                    eprintln!("skip {}: {e}", path.display());
                    skipped_count += 1;
                }
            }
        }
        eprintln!(
            "encoded {encoded_count} chunks into {} ({skipped_count} skipped)",
            out_dir.display()
        );
        return Ok(());
    }

    let input = cli
        .input
        .ok_or_else(|| anyhow!("path to gpl-disasm JSON is required (or pass --all-from <dir>)"))?;
    let body = std::fs::read_to_string(&input)
        .with_context(|| format!("reading {}", input.display()))?;
    let result: DisasmResult = serde_json::from_str(&body)
        .with_context(|| format!("parsing {}", input.display()))?;
    let bytes = encode(&result).with_context(|| format!("encoding {}", input.display()))?;
    match cli.output.as_deref() {
        Some(p) if p.as_os_str() == "-" => {
            use std::io::Write;
            std::io::stdout()
                .write_all(&bytes)
                .context("writing bytecode to stdout")?;
        }
        Some(p) => {
            std::fs::write(p, &bytes).with_context(|| format!("writing {}", p.display()))?;
        }
        None => {
            use std::io::Write;
            std::io::stdout()
                .write_all(&bytes)
                .context("writing bytecode to stdout")?;
        }
    }
    Ok(())
}
