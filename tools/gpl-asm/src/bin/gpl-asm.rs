use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gpl_asm::{encode, parse as parse_text};
use gpl_disasm::DisasmResult;

#[derive(Parser)]
#[command(
    name = "gpl-asm",
    version,
    about = "Reassemble SSI's GPL bytecode from a gpl-disasm JSON or text listing."
)]
struct Cli {
    /// Path to a `gpl-disasm` output file. Format auto-detected
    /// from the file extension (`.json` -> JSON,
    /// `.asm`/`.txt`/anything else -> text listing). Override with
    /// `--text` or `--json`.
    input: Option<PathBuf>,
    /// Bulk mode: read every input file in this directory and
    /// write a matching `*.bin` per chunk into `--output <dir>`.
    /// Auto-detects format per file.
    #[arg(long = "all-from", requires = "output")]
    all_from: Option<PathBuf>,
    /// Output path: file in single-chunk mode, directory in
    /// `--all-from` mode. Single-chunk default is stdout.
    #[arg(short = 'o', long = "output")]
    output: Option<PathBuf>,
    /// Force JSON parsing (overrides auto-detect).
    #[arg(long, conflicts_with = "text")]
    json: bool,
    /// Force text-listing parsing (overrides auto-detect).
    #[arg(long, conflicts_with = "json")]
    text: bool,
}

enum InputMode {
    Json,
    Text,
}

fn detect_mode(cli: &Cli, path: &Path) -> InputMode {
    if cli.json {
        return InputMode::Json;
    }
    if cli.text {
        return InputMode::Text;
    }
    match path.extension().and_then(|e| e.to_str()) {
        Some("json") => InputMode::Json,
        _ => InputMode::Text,
    }
}

fn load_disasm_result(path: &Path, mode: &InputMode) -> Result<DisasmResult> {
    let body = std::fs::read_to_string(path)
        .with_context(|| format!("reading {}", path.display()))?;
    match mode {
        InputMode::Json => serde_json::from_str(&body)
            .with_context(|| format!("parsing JSON {}", path.display())),
        InputMode::Text => parse_text(&body)
            .with_context(|| format!("parsing text listing {}", path.display())),
    }
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    if let Some(src_dir) = cli.all_from.clone() {
        let out_dir = cli
            .output
            .as_ref()
            .ok_or_else(|| anyhow!("--all-from requires -o <dir>"))?
            .clone();
        std::fs::create_dir_all(&out_dir)
            .with_context(|| format!("creating {}", out_dir.display()))?;
        let mut encoded_count = 0usize;
        let mut skipped_count = 0usize;
        let mut entries: Vec<PathBuf> = std::fs::read_dir(&src_dir)
            .with_context(|| format!("reading {}", src_dir.display()))?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| {
                p.is_file()
                    && matches!(
                        p.extension().and_then(|e| e.to_str()),
                        Some("json") | Some("asm") | Some("txt")
                    )
            })
            .collect();
        entries.sort();
        for path in entries {
            let mode = detect_mode(&cli, &path);
            let result = match load_disasm_result(&path, &mode) {
                Ok(r) => r,
                Err(e) => {
                    eprintln!("skip {} (parse): {e}", path.display());
                    skipped_count += 1;
                    continue;
                }
            };
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
        .as_ref()
        .ok_or_else(|| {
            anyhow!("path to a gpl-disasm output file is required (or pass --all-from <dir>)")
        })?
        .clone();
    let mode = detect_mode(&cli, &input);
    let result = load_disasm_result(&input, &mode)?;
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
