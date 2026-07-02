use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gpl_asm::{encode, format_with_caret, parse as parse_text, validate};
use gpl_disasm::DisasmResult;
use serde::Deserialize;

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
    /// Apply a declarative patch script to the original chunk
    /// bytes (the positional input). The patch is a TOML file
    /// with `[[edit]]` records (see the gpl-asm README for the
    /// schema). v0.8.0 supports absolute-offset edits with
    /// bytes_old fingerprint verification; label-relative edits
    /// land in v0.8.1+.
    #[arg(long, conflicts_with_all = ["all_from", "validate_only", "json", "text"])]
    patch: Option<PathBuf>,
    /// With --patch: report what would change without writing.
    #[arg(long)]
    dry_run: bool,
}

/// Patch-script schema (v0.8.0). Each `[[edit]]` carries an
/// absolute byte offset, the expected original bytes (for
/// fingerprint verification), and the replacement bytes. The
/// patcher refuses to apply if `bytes_old` doesn't match the
/// chunk at `at_offset` — protects against applying the wrong
/// patch to the wrong chunk.
#[derive(Debug, Deserialize)]
struct PatchScript {
    #[serde(rename = "edit", default)]
    edits: Vec<EditRecord>,
}

#[derive(Debug, Deserialize)]
struct EditRecord {
    /// Absolute byte offset into the chunk. Accepts decimal or
    /// `0x`-prefixed hex (TOML's `0x42` integer form, or a
    /// decimal `66`).
    at_offset: i64,
    /// Original bytes the patcher EXPECTS to find at
    /// `at_offset`. Hex string (with or without `0x` prefix,
    /// spaces allowed: `"01"`, `"0x01"`, `"01 02 03"`).
    bytes_old: String,
    /// Replacement bytes (same hex string format). Must be the
    /// same length as `bytes_old` (offset edits don't grow or
    /// shrink the chunk).
    bytes_new: String,
    /// Optional human-readable description; surfaces in the
    /// dry-run report.
    #[serde(default)]
    reason: Option<String>,
}

fn parse_hex_bytes(s: &str, ctx: &str) -> Result<Vec<u8>> {
    let cleaned: String = s
        .replace("0x", "")
        .replace("0X", "")
        .chars()
        .filter(|c| !c.is_whitespace())
        .collect();
    if !cleaned.len().is_multiple_of(2) {
        return Err(anyhow!(
            "{ctx}: hex string has odd nibble count ({})",
            cleaned.len(),
        ));
    }
    let mut out = Vec::with_capacity(cleaned.len() / 2);
    for i in (0..cleaned.len()).step_by(2) {
        let byte = u8::from_str_radix(&cleaned[i..i + 2], 16)
            .with_context(|| format!("{ctx}: bad hex byte {:?}", &cleaned[i..i + 2]))?;
        out.push(byte);
    }
    Ok(out)
}

fn cmd_patch(
    patch_path: &Path,
    chunk_path: &Path,
    output: Option<&Path>,
    dry_run: bool,
) -> Result<()> {
    let patch_text = std::fs::read_to_string(patch_path)
        .with_context(|| format!("reading {}", patch_path.display()))?;
    let script: PatchScript = toml::from_str(&patch_text)
        .with_context(|| format!("parsing TOML patch {}", patch_path.display()))?;
    let mut chunk =
        std::fs::read(chunk_path).with_context(|| format!("reading {}", chunk_path.display()))?;

    if script.edits.is_empty() {
        return Err(anyhow!(
            "{}: no [[edit]] records found",
            patch_path.display()
        ));
    }

    let mut applied = 0usize;
    for (i, edit) in script.edits.iter().enumerate() {
        let label = format!("edit[{i}]");
        let old_bytes = parse_hex_bytes(&edit.bytes_old, &format!("{label}/bytes_old"))?;
        let new_bytes = parse_hex_bytes(&edit.bytes_new, &format!("{label}/bytes_new"))?;
        if old_bytes.len() != new_bytes.len() {
            return Err(anyhow!(
                "{label}: bytes_old length {} != bytes_new length {} \
                 (offset edits don't grow or shrink the chunk)",
                old_bytes.len(),
                new_bytes.len(),
            ));
        }
        let offset = if edit.at_offset < 0 {
            return Err(anyhow!(
                "{label}: at_offset must be >= 0, got {}",
                edit.at_offset
            ));
        } else {
            edit.at_offset as usize
        };
        if offset + old_bytes.len() > chunk.len() {
            return Err(anyhow!(
                "{label}: edit at offset 0x{offset:x} length {} extends past chunk end ({})",
                old_bytes.len(),
                chunk.len(),
            ));
        }
        let actual = &chunk[offset..offset + old_bytes.len()];
        if actual != old_bytes.as_slice() {
            let actual_hex: String = actual
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<Vec<_>>()
                .join(" ");
            let expected_hex: String = old_bytes
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<Vec<_>>()
                .join(" ");
            return Err(anyhow!(
                "{label}: bytes_old fingerprint mismatch at offset 0x{offset:x}\n  \
                 expected: {expected_hex}\n  \
                 actual:   {actual_hex}\n  \
                 (refusing to apply; bytes_old verifies the patch targets the right chunk)",
            ));
        }
        let reason = edit.reason.as_deref().unwrap_or("(no reason given)");
        let new_hex: String = new_bytes
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<Vec<_>>()
            .join(" ");
        if dry_run {
            eprintln!(
                "would apply {label} at 0x{offset:x}: {} bytes -> {new_hex}  ({reason})",
                old_bytes.len()
            );
        } else {
            chunk[offset..offset + old_bytes.len()].copy_from_slice(&new_bytes);
            eprintln!(
                "applied {label} at 0x{offset:x}: {} bytes -> {new_hex}  ({reason})",
                old_bytes.len()
            );
        }
        applied += 1;
    }

    if dry_run {
        eprintln!("dry-run: {applied} edit(s) would apply cleanly. No output written.");
        return Ok(());
    }

    // Write output. Default: rewrite the input chunk path
    // (matches the `save-edit` pattern; backups are the user's
    // responsibility for now).
    let out = output.unwrap_or(chunk_path);
    std::fs::write(out, &chunk).with_context(|| format!("writing {}", out.display()))?;
    eprintln!("wrote {} bytes to {}", chunk.len(), out.display());
    Ok(())
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
    let body =
        std::fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))?;
    match mode {
        InputMode::Json => {
            serde_json::from_str(&body).with_context(|| format!("parsing JSON {}", path.display()))
        }
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

    if let Some(patch_path) = cli.patch.as_ref() {
        let chunk_path = cli
            .input
            .as_ref()
            .ok_or_else(|| anyhow!("--patch requires a chunk path as the positional input"))?
            .clone();
        return cmd_patch(patch_path, &chunk_path, cli.output.as_deref(), cli.dry_run);
    }

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
            println!(
                "{}: clean ({} instruction(s))",
                input.display(),
                result.instructions.len()
            );
            return Ok(());
        }
        eprintln!("{}: {} validation error(s):", input.display(), report.len());
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
            if !cli.no_validate
                && let Err(e) = report_validation(&result, &path.display().to_string())
            {
                eprintln!("skip {}: {e}", path.display());
                skipped_count += 1;
                continue;
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
