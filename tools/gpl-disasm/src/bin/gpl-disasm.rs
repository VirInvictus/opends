use std::io::Write;
use std::path::PathBuf;

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gff_edit::{FourCC, Gff};
use gpl_disasm::{
    Cfg, ChunkSummary, DisasmResult, EdgeKind, OPCODES, Symbols, build_global_cfg, disassemble,
    render_text, write_dot, write_global_cfg_dot,
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
    /// Directory containing hand-curated `opcodes.toml` /
    /// `functions.toml`. When provided, function-entry labels in
    /// both text and JSON output are decorated with the matching
    /// symbol name (`entry_0x0001 (iniya_dialog_start)`). Default:
    /// `tools/gpl-disasm/syms/` next to the binary if present,
    /// else no symbols are loaded.
    #[arg(long)]
    syms: Option<PathBuf>,
    /// Disable the default `tools/gpl-disasm/syms/` lookup. Useful
    /// for diff-friendly output when the curation catalogue is in
    /// flux.
    #[arg(long = "no-syms")]
    no_syms: bool,
    /// Emit a whole-file inter-chunk control-flow graph: nodes
    /// are GPL/MAS chunks, edges are `gpl global sub` (0x14) call
    /// sites. Argument is the output path (or `-` for stdout).
    /// Output format follows `--json`: DOT by default, JSON when
    /// `--json` is set. Mutually exclusive with the single-chunk
    /// (`--kind`/`--id`) path.
    #[arg(long = "global-cfg")]
    global_cfg: Option<PathBuf>,
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
    let file_basename = file
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("")
        .to_string();
    let symbols = load_symbols(cli.syms.as_deref(), cli.no_syms)?;

    if let Some(ref out_path) = cli.global_cfg {
        // Whole-file inter-chunk callgraph mode. Disassemble every
        // GPL/MAS chunk, collect cross-chunk calls, build the
        // GlobalCfg, render DOT (or JSON).
        let mut chunks: Vec<(String, i32, DisasmResult)> = Vec::new();
        for c in gff.chunks() {
            if c.kind != FourCC(*b"GPL ") && c.kind != FourCC(*b"MAS ") {
                continue;
            }
            let bytes = gff.read_chunk(c);
            let mut result = disassemble(bytes);
            let kind_str_padded = String::from_utf8_lossy(c.kind.as_bytes()).into_owned();
            if let Some(syms) = symbols.as_ref() {
                if let Some(cfg) = result.cfg.as_mut() {
                    syms.apply_to_labels(cfg, &file_basename, &kind_str_padded, c.id);
                }
                syms.apply_to_mnemonics(&mut result);
                syms.apply_to_variables(&mut result);
                syms.apply_to_locals(&mut result, &file_basename, &kind_str_padded, c.id);
            }
            chunks.push((kind_str_padded, c.id, result));
        }
        let summaries: Vec<ChunkSummary> = chunks
            .iter()
            .filter_map(|(kind, id, res)| {
                res.cfg.as_ref().map(|cfg| ChunkSummary {
                    kind: kind.clone(),
                    chunk_id: *id,
                    cfg,
                    cross_chunk_calls: &res.cross_chunk_calls,
                })
            })
            .collect();
        let gcfg = build_global_cfg(&file_basename, &summaries, symbols.as_ref());
        let body = if cli.json {
            serde_json::to_string_pretty(&gcfg)? + "\n"
        } else {
            let mut buf: Vec<u8> = Vec::new();
            write_global_cfg_dot(&gcfg, &mut buf).context("rendering global CFG DOT")?;
            String::from_utf8(buf).context("DOT bytes not utf-8")?
        };
        if out_path.as_os_str() == "-" {
            std::io::stdout()
                .write_all(body.as_bytes())
                .context("writing global CFG to stdout")?;
        } else {
            std::fs::write(out_path, body)
                .with_context(|| format!("writing global CFG to {}", out_path.display()))?;
        }
        eprintln!(
            "global CFG: {} chunks, {} cross-chunk edges from {}",
            gcfg.nodes.len(),
            gcfg.edges.len(),
            file_basename
        );
        return Ok(());
    }

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
            let mut result = disassemble(bytes);
            if let Some(syms) = symbols.as_ref() {
                let kind_str_padded =
                    String::from_utf8_lossy(c.kind.as_bytes()).into_owned();
                if let Some(cfg) = result.cfg.as_mut() {
                    syms.apply_to_labels(cfg, &file_basename, &kind_str_padded, c.id);
                }
                syms.apply_to_mnemonics(&mut result);
                syms.apply_to_variables(&mut result);
                syms.apply_to_locals(&mut result, &file_basename, &kind_str_padded, c.id);
            }
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
    let mut result = disassemble(bytes);
    if let Some(syms) = symbols.as_ref() {
        let kind_str_padded = String::from_utf8_lossy(fourcc.as_bytes()).into_owned();
        if let Some(cfg) = result.cfg.as_mut() {
            syms.apply_to_labels(cfg, &file_basename, &kind_str_padded, id);
        }
        syms.apply_to_mnemonics(&mut result);
        syms.apply_to_variables(&mut result);
        syms.apply_to_locals(&mut result, &file_basename, &kind_str_padded, id);
    }

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

// Text rendering moved into the gpl-disasm library (see
// `render_text`). The binary just calls it; both the binary
// output and the gpl-asm round-trip test go through the same
// path.

#[allow(dead_code)] // keep `Cfg` and `EdgeKind` re-exports compile-time-reachable
fn _ensure_imports(_c: &Cfg, _e: EdgeKind) {}

/// Resolve the symbols directory and load the catalogue. Precedence:
/// 1. `--no-syms`: skip entirely (returns `None`).
/// 2. `--syms <path>`: required to exist; loads from there.
/// 3. Default: `tools/gpl-disasm/syms/` next to the running binary
///    (one workspace level up from `target/release/`), if present.
fn load_symbols(
    explicit: Option<&std::path::Path>,
    no_syms: bool,
) -> Result<Option<Symbols>> {
    if no_syms {
        return Ok(None);
    }
    let dir = if let Some(p) = explicit {
        if !p.is_dir() {
            return Err(anyhow!(
                "--syms directory does not exist: {}",
                p.display()
            ));
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
    if syms.opcodes.is_empty()
        && syms.functions.is_empty()
        && syms.variables.is_empty()
        && syms.locals.is_empty()
    {
        return Ok(None);
    }
    Ok(Some(syms))
}

/// Walk up from the binary's directory looking for a sibling
/// `tools/gpl-disasm/syms/` directory. Returns `None` if not
/// found, which is the expected case when running outside the
/// workspace.
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
