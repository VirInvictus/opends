use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gpl_asm::{encode, format_with_caret, parse as parse_text, validate};
use gpl_disasm::{DisasmResult, Symbols, build_cfg, disassemble};
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
    /// schema). Each edit addresses either an absolute
    /// `at_offset` (v0.8.0) or a label-relative `at` expression
    /// (v0.9.0: `at = "label_0x0042 + 3"` or `at = "<name> + N"`
    /// with names resolved from `syms/functions.toml`); the
    /// `bytes_old` fingerprint check applies to both forms.
    #[arg(long, conflicts_with_all = ["all_from", "validate_only", "json", "text"])]
    patch: Option<PathBuf>,
    /// With --patch: report what would change without writing.
    #[arg(long)]
    dry_run: bool,
    /// With --patch: directory containing `functions.toml` for
    /// resolving `at = "<name> + N"` edits. Default:
    /// `tools/gpl-disasm/syms/` next to the binary if present,
    /// else no symbols are loaded (the gpl-disasm precedent).
    #[arg(long, requires = "patch")]
    syms: Option<PathBuf>,
    /// Disable the default `tools/gpl-disasm/syms/` lookup for
    /// `--patch` name resolution.
    #[arg(long = "no-syms", requires = "patch")]
    no_syms: bool,
}

/// Patch-script schema (v0.8.0 offsets, v0.9.0 labels). Each
/// `[[edit]]` addresses a byte position (absolute `at_offset` or
/// label-relative `at`, exactly one), the expected original
/// bytes (for fingerprint verification), and the replacement
/// bytes. The patcher refuses to apply if `bytes_old` doesn't
/// match the chunk at the resolved offset — protects against
/// applying the wrong patch to the wrong chunk, and stays
/// mandatory for label-relative edits.
#[derive(Debug, Deserialize)]
struct PatchScript {
    #[serde(rename = "edit", default)]
    edits: Vec<EditRecord>,
}

#[derive(Debug, Deserialize)]
struct EditRecord {
    /// Absolute byte offset into the chunk. Accepts decimal or
    /// `0x`-prefixed hex (TOML's `0x42` integer form, or a
    /// decimal `66`). Exactly one of `at_offset` / `at`.
    #[serde(default)]
    at_offset: Option<i64>,
    /// Label-relative address (v0.9.0): `"label_0x0042"`,
    /// `"label_0x0042 + 3"`, or `"<name> + N"` where `<name>` is
    /// resolved from `syms/functions.toml`. The resolver
    /// disassembles the target chunk and requires the label (or
    /// the name's offset) to be a real block leader there, so a
    /// patch cannot silently address into the wrong chunk.
    /// Exactly one of `at_offset` / `at`.
    #[serde(default)]
    at: Option<String>,
    /// Original bytes the patcher EXPECTS to find at the
    /// resolved offset. Hex string (with or without `0x` prefix,
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

/// Split an `at` expression into its base and delta:
/// `"label_0x0042"` -> `("label_0x0042", 0)`,
/// `"iniya_first_meeting + 3"` -> `(name, 3)`. The delta is
/// decimal or `0x`-hex; only `+` is supported (patch authors
/// anchor on the label before the site, per the roadmap).
fn parse_at_expr(s: &str) -> Result<(String, u64)> {
    let s = s.trim();
    if s.is_empty() {
        return Err(anyhow!("at: empty expression"));
    }
    let (base, delta) = match s.split_once('+') {
        None => (s, 0u64),
        Some((base, delta_str)) => {
            let delta_str = delta_str.trim();
            let delta = if let Some(hex) = delta_str
                .strip_prefix("0x")
                .or_else(|| delta_str.strip_prefix("0X"))
            {
                u64::from_str_radix(hex, 16)
                    .with_context(|| format!("at: bad hex delta {delta_str:?}"))?
            } else {
                delta_str
                    .parse::<u64>()
                    .with_context(|| format!("at: bad delta {delta_str:?}"))?
            };
            (base, delta)
        }
    };
    let base = base.trim();
    if base.is_empty() {
        return Err(anyhow!("at: missing base before '+' in {s:?}"));
    }
    if base.chars().any(char::is_whitespace) {
        return Err(anyhow!(
            "at: unexpected whitespace in base {base:?} (expected \"<name>\" or \"<name> + N\")"
        ));
    }
    Ok((base.to_string(), delta))
}

/// Resolve a parsed `at` base + delta against the chunk's real
/// block-leader labels (and, for symbolic names, the
/// `functions.toml` catalogue). The base must land on a label
/// the disassembler actually produced for THIS chunk; that is
/// the wrong-chunk protection the roadmap requires, ahead of
/// the `bytes_old` fingerprint.
fn resolve_at(
    ctx: &str,
    base: &str,
    delta: u64,
    labels: &BTreeMap<usize, String>,
    syms: Option<&Symbols>,
) -> Result<usize> {
    let base_offset = if let Some((offset, _)) = labels.iter().find(|(_, name)| *name == base) {
        *offset
    } else if let Some(syms) = syms {
        let matches: Vec<_> = syms.functions.iter().filter(|f| f.name == base).collect();
        match matches.len() {
            0 => {
                return Err(anyhow!(
                    "{ctx}: {base:?} is not a label in this chunk and not a \
                     name in functions.toml"
                ));
            }
            1 => {
                let offset = matches[0].offset;
                if !labels.contains_key(&offset) {
                    return Err(anyhow!(
                        "{ctx}: {base:?} names offset 0x{offset:x} in functions.toml, \
                         but that offset is not a block leader in this chunk \
                         (is the patch targeting the right chunk?)"
                    ));
                }
                offset
            }
            n => {
                let rows: Vec<String> = matches
                    .iter()
                    .map(|f| {
                        format!(
                            "{} {} chunk {} offset 0x{:x}",
                            f.file,
                            f.kind.trim_end(),
                            f.chunk_id,
                            f.offset
                        )
                    })
                    .collect();
                return Err(anyhow!(
                    "{ctx}: {base:?} is ambiguous ({n} functions.toml rows: {}); \
                     use the label_0xNNNN form instead",
                    rows.join("; ")
                ));
            }
        }
    } else {
        return Err(anyhow!(
            "{ctx}: {base:?} is not a label in this chunk (and no functions.toml \
             is loaded for name resolution; pass --syms <dir>)"
        ));
    };
    Ok(base_offset + delta as usize)
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
    syms_dir: Option<&Path>,
    no_syms: bool,
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

    // Label resolution needs the chunk's real block-leader map;
    // build it once, and only when some edit actually uses `at`.
    let labels: Option<BTreeMap<usize, String>> = if script.edits.iter().any(|e| e.at.is_some()) {
        let result = disassemble(&chunk);
        if !result.aligned {
            return Err(anyhow!(
                "{}: chunk does not disassemble aligned, so labels cannot be \
                 resolved; use at_offset for this chunk",
                chunk_path.display()
            ));
        }
        let (cfg, _) = build_cfg(&result.instructions, chunk.len());
        Some(cfg.labels)
    } else {
        None
    };
    let symbols = load_symbols(syms_dir, no_syms)?;

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
        let offset = match (edit.at_offset, edit.at.as_deref()) {
            (Some(_), Some(_)) => {
                return Err(anyhow!(
                    "{label}: both at and at_offset are set; give exactly one"
                ));
            }
            (None, None) => {
                return Err(anyhow!(
                    "{label}: neither at nor at_offset is set; give exactly one"
                ));
            }
            (Some(at_offset), None) => {
                if at_offset < 0 {
                    return Err(anyhow!("{label}: at_offset must be >= 0, got {at_offset}"));
                }
                at_offset as usize
            }
            (None, Some(expr)) => {
                let (base, delta) =
                    parse_at_expr(expr).with_context(|| format!("{label}: parsing at"))?;
                let labels = labels
                    .as_ref()
                    .expect("labels built when any edit uses `at`");
                resolve_at(&label, &base, delta, labels, symbols.as_ref())?
            }
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

/// Load `functions.toml` symbols for `--patch` name resolution.
/// Mirrors gpl-disasm's CLI: an explicit `--syms` dir must
/// exist; otherwise walk up from the binary looking for
/// `tools/gpl-disasm/syms/`, silently loading nothing when
/// absent (the expected case outside the workspace).
fn load_symbols(explicit: Option<&Path>, no_syms: bool) -> Result<Option<Symbols>> {
    if no_syms {
        return Ok(None);
    }
    let dir = if let Some(p) = explicit {
        if !p.is_dir() {
            return Err(anyhow!("--syms directory does not exist: {}", p.display()));
        }
        Some(p.to_path_buf())
    } else {
        default_syms_dir()
    };
    let Some(dir) = dir else {
        return Ok(None);
    };
    let syms = Symbols::load_from_dir(&dir)
        .with_context(|| format!("loading symbols from {}", dir.display()))?;
    if syms.functions.is_empty() {
        return Ok(None);
    }
    Ok(Some(syms))
}

/// Walk up from the binary's directory looking for a sibling
/// `tools/gpl-disasm/syms/` directory (the gpl-disasm CLI's
/// default-lookup precedent). `None` when not found.
fn default_syms_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let mut dir = exe.parent()?.to_path_buf();
    for _ in 0..8 {
        let candidate = dir.join("tools/gpl-disasm/syms");
        if candidate.is_dir() {
            return Some(candidate);
        }
        if !dir.pop() {
            break;
        }
    }
    None
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
        return cmd_patch(
            patch_path,
            &chunk_path,
            cli.output.as_deref(),
            cli.dry_run,
            cli.syms.as_deref(),
            cli.no_syms,
        );
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

#[cfg(test)]
mod at_expr_tests {
    use super::*;
    use gpl_disasm::FunctionSymbol;

    fn labels() -> BTreeMap<usize, String> {
        BTreeMap::from([
            (0usize, "entry_0x0000".to_string()),
            (0x42usize, "label_0x0042".to_string()),
        ])
    }

    fn syms_with(name: &str, offset: usize) -> Symbols {
        Symbols {
            functions: vec![FunctionSymbol {
                file: "TEST.GFF".into(),
                kind: "GPL ".into(),
                chunk_id: 1,
                offset,
                name: name.into(),
                notes: None,
            }],
            ..Symbols::default()
        }
    }

    #[test]
    fn parse_bare_base() {
        assert_eq!(
            parse_at_expr("label_0x0042").unwrap(),
            ("label_0x0042".to_string(), 0)
        );
    }

    #[test]
    fn parse_base_plus_decimal() {
        assert_eq!(
            parse_at_expr("label_0x0042 + 3").unwrap(),
            ("label_0x0042".to_string(), 3)
        );
    }

    #[test]
    fn parse_base_plus_hex_and_tight_spacing() {
        assert_eq!(
            parse_at_expr("my_fn+0x10").unwrap(),
            ("my_fn".to_string(), 16)
        );
    }

    #[test]
    fn parse_rejects_empty_and_garbage() {
        assert!(parse_at_expr("").is_err());
        assert!(parse_at_expr("  ").is_err());
        assert!(parse_at_expr("+ 3").is_err());
        assert!(parse_at_expr("foo + bar").is_err());
        assert!(parse_at_expr("foo bar").is_err());
    }

    #[test]
    fn resolve_direct_label() {
        assert_eq!(
            resolve_at("edit[0]", "label_0x0042", 3, &labels(), None).unwrap(),
            0x45
        );
    }

    #[test]
    fn resolve_unknown_base_errors() {
        let err = resolve_at("edit[0]", "nope", 0, &labels(), None).unwrap_err();
        assert!(err.to_string().contains("nope"));
    }

    #[test]
    fn resolve_name_through_symbols() {
        let syms = syms_with("my_fn", 0x42);
        assert_eq!(
            resolve_at("edit[0]", "my_fn", 1, &labels(), Some(&syms)).unwrap(),
            0x43
        );
    }

    #[test]
    fn resolve_name_not_a_leader_errors() {
        // The name exists in functions.toml but its offset is not
        // a block leader in this chunk: the wrong-chunk guard.
        let syms = syms_with("my_fn", 0x99);
        let err = resolve_at("edit[0]", "my_fn", 0, &labels(), Some(&syms)).unwrap_err();
        assert!(err.to_string().contains("block leader"));
    }

    #[test]
    fn resolve_ambiguous_name_errors() {
        let mut syms = syms_with("my_fn", 0x42);
        syms.functions.push(FunctionSymbol {
            file: "OTHER.GFF".into(),
            kind: "GPL ".into(),
            chunk_id: 2,
            offset: 0,
            name: "my_fn".into(),
            notes: None,
        });
        let err = resolve_at("edit[0]", "my_fn", 0, &labels(), Some(&syms)).unwrap_err();
        assert!(err.to_string().contains("ambiguous"));
    }
}
