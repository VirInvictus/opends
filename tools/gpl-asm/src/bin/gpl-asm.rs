use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gpl_asm::{encode, format_with_caret, parse as parse_text, validate};
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
    /// Run the validator (branch bounds, Immediate14 range, RetVal
    /// depth) and exit; don't encode. Exits 0 on a clean program,
    /// 1 if any validation error fires.
    #[arg(long, conflicts_with_all = ["output", "all_from", "no_validate"])]
    validate_only: bool,
    /// Skip the pre-encode validator pass. Default: validate
    /// every chunk before encoding it; a failed validation aborts
    /// the run before any output is written.
    #[arg(long)]
    no_validate: bool,
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
        InputMode::Text => parse_text(&body).map_err(|e| {
            // Render the parse error with the same caret-style
            // pointer the v0.5.0 helpers produce. Far more useful
            // than the bare `line N: ...` string when authoring.
            let caret = format_with_caret(&e, &body);
            anyhow!("parsing text listing {}:\n{}", path.display(), caret)
        }),
    }
}

fn report_validation(disasm: &DisasmResult, label: &str) -> Result<()> {
    let report = validate(disasm);
    if report.is_ok() {
        return Ok(());
    }
    let mut buf = String::new();
    for err in &report.errors {
        buf.push_str("  ");
        buf.push_str(&err.to_string());
        buf.push('\n');
    }
    Err(anyhow!(
        "{label}: {} validation error(s):\n{buf}",
        report.len()
    ))
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    if cli.validate_only {
        let input = cli
            .input
            .as_ref()
            .ok_or_else(|| anyhow!("--validate-only requires an input path"))?
            .clone();
        let mode = detect_mode(&cli, &input);
        let result = load_disasm_result(&input, &mode)?;
        let report = validate(&result);
        if report.is_ok() {
            println!("{}: clean ({} instruction(s))", input.display(), result.instructions.len());
            return Ok(());
        }
        eprintln!(
            "{}: {} validation error(s):",
            input.display(),
            report.len()
        );
        for err in &report.errors {
            eprintln!("  {err}");
        }
        std::process::exit(1);
    }

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
            if !cli.no_validate {
                if let Err(e) = report_validation(&result, &path.display().to_string()) {
                    eprintln!("skip {}: {e}", path.display());
                    skipped_count += 1;
                    continue;
                }
            }
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
    if !cli.no_validate {
        report_validation(&result, &input.display().to_string())?;
    }
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
