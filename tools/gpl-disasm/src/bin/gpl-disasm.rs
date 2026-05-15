use std::io::Write;
use std::path::PathBuf;

use anyhow::{Context, Result, anyhow};
use clap::Parser;
use gff_edit::{FourCC, Gff};
use gpl_disasm::{DisasmResult, Instruction, OPCODES, disassemble};

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
                render_text(&result)
            };
            let name = format!(
                "{}-{}.{}",
                String::from_utf8_lossy(c.kind.as_bytes()).trim_end(),
                c.id,
                ext
            );
            let path = out_dir.join(&name);
            std::fs::write(&path, body)
                .with_context(|| format!("writing {}", path.display()))?;
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
    let body = if cli.json {
        serde_json::to_string_pretty(&result)? + "\n"
    } else {
        render_text(&result)
    };

    match cli.output {
        Some(path) if path.as_os_str() != "-" => {
            std::fs::write(&path, body)
                .with_context(|| format!("writing listing to {}", path.display()))?;
        }
        _ => {
            std::io::stdout()
                .write_all(body.as_bytes())
                .context("writing listing to stdout")?;
        }
    }
    Ok(())
}

fn render_text(result: &DisasmResult) -> String {
    let mut out = String::with_capacity(result.instructions.len() * 48);
    for instr in &result.instructions {
        render_instruction(&mut out, instr);
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

fn render_instruction(out: &mut String, instr: &Instruction) {
    out.push_str(&format!("{}", instr));
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
