use std::collections::BTreeMap;
use std::io::Write;
use std::path::PathBuf;

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gff_edit::{FourCC, Gff};
use gpl_disasm::{
    Cfg, DisasmResult, EdgeKind, Expression, Instruction, OPCODES, disassemble, write_dot,
};

#[derive(Parser)]
#[command(
    name = "gpl-disasm",
    version,
    about = "Disassemble SSI's GPL bytecode from a GFF file."
)]
struct Cli {
    /// Path to a GFF file (typically GPLDATA.GFF).
    file: Option<PathBuf>,
    /// Chunk kind to disassemble. Accepts 3- or 4-character
    /// FOURCC; common values: `GPL`, `MAS`. Required unless
    /// `--all` or `--opcodes` is set.
    #[arg(long)]
    kind: Option<String>,
    /// Resource id of the chunk. Required unless `--all` or
    /// `--opcodes` is set.
    #[arg(long)]
    id: Option<i32>,
    /// Disassemble every `GPL ` and `MAS ` chunk in the file
    /// and write each as `<kind>-<id>.asm` (or `.json` with
    /// `--json`) under `<output>`.
    #[arg(long, requires = "output")]
    all: bool,
    /// Output path. For single-chunk mode: file or `-` for
    /// stdout (default stdout). For `--all` mode: required
    /// output directory.
    #[arg(short = 'o', long = "output")]
    output: Option<PathBuf>,
    /// Print the embedded opcode catalogue (one row per byte
    /// 0x00..0x80) and exit.
    #[arg(long)]
    opcodes: bool,
    /// Emit the disassembly as JSON instead of the text listing.
    /// Same shape for single-chunk and `--all` mode.
    #[arg(long)]
    json: bool,
    /// List discovered entry points (one per line). In `--all`
    /// mode each chunk's entries are written to
    /// `<output>/<kind>-<id>.entries`. In single-chunk mode the
    /// list goes to stdout (or `-o <file>` when set).
    #[arg(long)]
    entries: bool,
    /// Emit a Graphviz DOT control-flow graph. In single-chunk
    /// mode the argument is the output path (or `-` for stdout).
    /// In `--all` mode it must be a directory; one
    /// `<kind>-<id>.dot` per chunk is written there.
    #[arg(long)]
    cfg: Option<PathBuf>,
    /// Disable label rendering in the text listing; jump targets
    /// remain as integer offsets. JSON output is unaffected (the
    /// `cfg` field is always present).
    #[arg(long = "no-labels")]
    no_labels: bool,
}

fn main() -> Result<()> {
    install_pipe_exit_hook();
    let cli = Cli::parse();

    if cli.opcodes {
        for (i, name) in OPCODES.iter().enumerate() {
            println!("0x{:02x}  {name}", i);
        }
        return Ok(());
    }

    let file = cli
        .file
        .ok_or_else(|| anyhow!("file path is required (or pass --opcodes)"))?;
    let gff = Gff::open(&file).with_context(|| format!("opening {}", file.display()))?;

    if cli.all {
        let out_dir = cli
            .output
            .ok_or_else(|| anyhow!("--all requires -o <dir>"))?;
        std::fs::create_dir_all(&out_dir)
            .with_context(|| format!("creating {}", out_dir.display()))?;
        if let Some(ref cfg_dir) = cli.cfg {
            std::fs::create_dir_all(cfg_dir)
                .with_context(|| format!("creating {}", cfg_dir.display()))?;
        }
        let ext = if cli.json { "json" } else { "asm" };
        let mut count = 0usize;
        let mut aligned_count = 0usize;
        for c in gff.chunks() {
            if c.kind != FourCC(*b"GPL ") && c.kind != FourCC(*b"MAS ") {
                continue;
            }
            let bytes = gff.read_chunk(c);
            let result = disassemble(bytes);
            if result.aligned {
                aligned_count += 1;
            }
            let body = if cli.json {
                serde_json::to_string_pretty(&result)? + "\n"
            } else {
                render_text(&result, !cli.no_labels)
            };
            let kind_str = String::from_utf8_lossy(c.kind.as_bytes())
                .trim_end()
                .to_string();
            let name = format!("{}-{}.{}", kind_str, c.id, ext);
            let path = out_dir.join(&name);
            std::fs::write(&path, body)
                .with_context(|| format!("writing {}", path.display()))?;
            if let Some(ref cfg_dir) = cli.cfg {
                if let Some(ref cfg) = result.cfg {
                    let dot_name = format!("{}-{}.dot", kind_str, c.id);
                    let dot_path = cfg_dir.join(&dot_name);
                    let mut f = std::fs::File::create(&dot_path)
                        .with_context(|| format!("creating {}", dot_path.display()))?;
                    write_dot(cfg, &result.instructions, &mut f)
                        .with_context(|| format!("writing {}", dot_path.display()))?;
                }
            }
            if cli.entries {
                let entries_name = format!("{}-{}.entries", kind_str, c.id);
                let entries_path = out_dir.join(&entries_name);
                let entries_body = if let Some(ref cfg) = result.cfg {
                    cfg.entry_points
                        .iter()
                        .map(|o| format!("{:#06x}\n", o))
                        .collect::<String>()
                } else {
                    String::new()
                };
                std::fs::write(&entries_path, entries_body)
                    .with_context(|| format!("writing {}", entries_path.display()))?;
            }
            count += 1;
        }
        eprintln!(
            "disassembled {count} GPL/MAS chunks ({aligned_count} aligned) into {}",
            out_dir.display()
        );
        return Ok(());
    }

    let kind = cli
        .kind
        .ok_or_else(|| anyhow!("--kind is required (or pass --all / --opcodes)"))?;
    let id = cli.id.ok_or_else(|| anyhow!("--id is required"))?;
    let fourcc = parse_kind_padded(&kind)?;
    let bytes = gff
        .read(fourcc, id)
        .ok_or_else(|| anyhow!("no chunk '{}' id={} in {}", fourcc, id, file.display()))?;
    let result = disassemble(bytes);

    if cli.entries {
        let body = result
            .cfg
            .as_ref()
            .map(|c| {
                c.entry_points
                    .iter()
                    .map(|o| format!("{:#06x}\n", o))
                    .collect::<String>()
            })
            .unwrap_or_default();
        write_or_stdout(cli.output.as_deref(), body.as_bytes(), "entries")?;
        return Ok(());
    }

    if let Some(ref cfg_path) = cli.cfg {
        let cfg = result
            .cfg
            .as_ref()
            .ok_or_else(|| anyhow!("--cfg requires an aligned disassembly (got best_effort)"))?;
        let mut buf: Vec<u8> = Vec::new();
        write_dot(cfg, &result.instructions, &mut buf).context("rendering DOT")?;
        if cfg_path.as_os_str() == "-" {
            std::io::stdout()
                .write_all(&buf)
                .context("writing DOT to stdout")?;
        } else {
            std::fs::write(cfg_path, &buf)
                .with_context(|| format!("writing DOT to {}", cfg_path.display()))?;
        }
        return Ok(());
    }

    let body = if cli.json {
        serde_json::to_string_pretty(&result)? + "\n"
    } else {
        render_text(&result, !cli.no_labels)
    };

    write_or_stdout(cli.output.as_deref(), body.as_bytes(), "listing")?;
    Ok(())
}

fn write_or_stdout(
    target: Option<&std::path::Path>,
    body: &[u8],
    label: &str,
) -> Result<()> {
    match target {
        Some(path) if path.as_os_str() != "-" => {
            std::fs::write(path, body)
                .with_context(|| format!("writing {label} to {}", path.display()))
        }
        _ => std::io::stdout()
            .write_all(body)
            .with_context(|| format!("writing {label} to stdout")),
    }
}

fn render_text(result: &DisasmResult, labels_on: bool) -> String {
    let mut out = String::with_capacity(result.instructions.len() * 48);
    let labels: Option<&BTreeMap<usize, String>> = if labels_on {
        result.cfg.as_ref().map(|c| &c.labels)
    } else {
        None
    };
    for instr in &result.instructions {
        if let Some(map) = labels {
            if let Some(name) = map.get(&instr.offset) {
                out.push_str(name);
                out.push_str(":\n");
            }
        }
        render_instruction(&mut out, instr, labels);
        out.push('\n');
    }
    let pct = if result.total_bytes > 0 {
        (result.bytes_consumed as f64 / result.total_bytes as f64) * 100.0
    } else {
        100.0
    };
    if !result.aligned {
        out.push_str(&format!(
            "; aligned=false bytes_consumed={}/{} ({pct:.1}%)\n",
            result.bytes_consumed, result.total_bytes
        ));
    }
    out
}

/// Render a single instruction. If `labels` is `Some`, replace
/// branch-instruction target parameters with the matching label
/// name from the map. Otherwise defers to [`Instruction`]'s
/// `Display` impl (integer targets).
fn render_instruction(
    out: &mut String,
    instr: &Instruction,
    labels: Option<&BTreeMap<usize, String>>,
) {
    if let Some(map) = labels {
        if let Some((target_param_idx, target_offset)) = branch_target_param(instr) {
            if let Some(label) = map.get(&target_offset) {
                let m = instr.mnemonic.unwrap_or("db");
                out.push_str(&format!(
                    "{:04x}  {:02x}  {:<22}",
                    instr.offset, instr.opcode, m
                ));
                for (i, param) in instr.params.iter().enumerate() {
                    out.push_str(if i == 0 { "  " } else { ", " });
                    if i == target_param_idx {
                        out.push_str(label);
                    } else {
                        out.push_str(&format_param(param));
                    }
                }
                if instr.best_effort {
                    out.push_str("  ; best-effort");
                }
                if let Some(ref s) = instr.string_run {
                    out.push_str("  ; \"");
                    out.push_str(&escape_for_comment(s));
                    out.push('"');
                }
                return;
            }
        }
    }
    out.push_str(&format!("{}", instr));
}

/// Render a parameter token list using the same convention as
/// `gpl_disasm`'s internal `write_param_tokens` (kept in sync
/// manually; if the lib renderer changes, mirror here).
fn format_param(tokens: &[Expression]) -> String {
    use std::fmt::Write;
    let mut s = String::new();
    let mut prev_was_value = false;
    for tok in tokens {
        let is_open = matches!(tok, Expression::OpenParen);
        let is_close = matches!(tok, Expression::CloseParen);
        let is_op = matches!(tok, Expression::BinaryOp { .. });
        if prev_was_value && !is_close && !is_op {
            s.push(' ');
        }
        if is_op {
            let _ = write!(s, " {tok} ");
        } else {
            let _ = write!(s, "{tok}");
        }
        prev_was_value = !is_open && !is_op;
    }
    s
}

fn escape_for_comment(input: &str) -> String {
    input
        .chars()
        .map(|c| match c {
            '\\' => "\\\\".to_string(),
            '\n' => "\\n".to_string(),
            '\r' => "\\r".to_string(),
            '\t' => "\\t".to_string(),
            '"' => "\\\"".to_string(),
            c if c.is_ascii_graphic() || c == ' ' => c.to_string(),
            c => format!("\\x{:02x}", c as u8),
        })
        .collect()
}

/// Return `(param_index, target_offset)` for branch instructions
/// whose first or second param is a literal target offset. The
/// returned `param_index` is which params slot to replace with the
/// label name (0 for most; 1 for `gpl ifcompare`).
fn branch_target_param(instr: &Instruction) -> Option<(usize, usize)> {
    let (idx, target_param) = match instr.opcode {
        0x12 | 0x13 | 0x3E | 0x3F | 0x63 | 0x64 => (0, instr.params.first()?),
        0x27 => (1, instr.params.get(1)?),
        _ => return None,
    };
    if target_param.len() != 1 {
        return None;
    }
    let v = match &target_param[0] {
        Expression::Immediate14 { value } => *value as i64,
        Expression::ImmediateByte { value } => *value as i64,
        Expression::ImmediateBigNum { value } => *value as i64,
        _ => return None,
    };
    if v < 0 {
        return None;
    }
    Some((idx, v as usize))
}

#[allow(dead_code)] // keep `Cfg` and `EdgeKind` re-exports compile-time-reachable
fn _ensure_imports(_c: &Cfg, _e: EdgeKind) {}

/// Parse a 3- or 4-character FOURCC string, padding with a
/// trailing space for 3-char inputs (DOS convention: `GPL` →
/// `"GPL "`).
fn parse_kind_padded(s: &str) -> Result<FourCC> {
    let bytes = s.as_bytes();
    if bytes.len() < 3 || bytes.len() > 4 {
        return Err(anyhow!("FOURCC must be 3 or 4 characters: {s:?}"));
    }
    let mut padded = [b' '; 4];
    padded[..bytes.len()].copy_from_slice(bytes);
    Ok(FourCC::new(padded))
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
