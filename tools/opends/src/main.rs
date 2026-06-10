//! `opends` — umbrella CLI for the OpenDS toolkit.
//!
//! A small dispatcher that reads file magic and shells out to the
//! right tool. The single entry point a new contributor can run
//! without first picking the right tool by name. Auto-detects
//! `BMP` / `PORT` / `ICON` / etc. inside a GFF, palette-indexed
//! PNG (already-extracted sprite), DARKRUN-shaped save GFFs, and
//! plain GPL bytecode chunks.
//!
//! Never reimplements logic; always shells to the underlying tool.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode, Stdio};

use anyhow::{Context, Result, anyhow};
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(
    name = "opends",
    version,
    about = "Umbrella CLI for the OpenDS toolkit.",
    long_about = "Auto-dispatches to the right tool by file magic. Run \
        `opends tools` for the list of wrapped tools and their versions, \
        or `opends help <subcommand>` for per-subcommand usage."
)]
struct Cli {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Auto-detect a file's type and run the right inspector.
    ///
    /// GFF containers go to `gff-cat info`; bitmap PNGs land with
    /// a one-line summary plus a pointer to `image-pack`; save
    /// files (CHARSAVE.GFF, DARKRUN.GFF, SAVE0?.SAV) go to
    /// `save-inspect`. Anything else: print the magic bytes and
    /// exit.
    Inspect {
        /// Path to inspect.
        file: PathBuf,
    },
    /// Render a region GFF as a single PNG. Thin wrapper over
    /// `region-render`.
    Render {
        /// Path to a region GFF (RGN*.GFF).
        file: PathBuf,
        /// Output PNG path.
        #[arg(short = 'o', long = "output", default_value = "region.png")]
        output: PathBuf,
    },
    /// Search NPC dialog / GPL strings for a pattern. Thin wrapper
    /// over `dialog-extract --grep`.
    Find {
        /// Substring to search for (case-sensitive).
        pattern: String,
        /// GPL-bearing GFF (typically GPLDATA.GFF).
        gff: PathBuf,
    },
    /// Bulk-extract every chunk in a GFF to a sibling directory.
    /// Thin wrapper over `gff-cat bulk-extract`.
    Extract {
        /// Path to the GFF.
        file: PathBuf,
        /// Output directory (default: alongside the GFF as
        /// `<gff-name>-extracted/`).
        #[arg(short = 'o', long = "output")]
        output: Option<PathBuf>,
    },
    /// Print a table of every wrapped tool and its `VERSION`.
    Tools,
}

/// The names of the underlying tools opends dispatches to. Kept in
/// one place so `opends tools` and the dispatcher reference the
/// same set. Each entry is `(binary_name, crate_dir_under_tools)`.
const WRAPPED_TOOLS: &[(&str, &str)] = &[
    ("gff-cat", "gff-edit"),
    ("gpl-disasm", "gpl-disasm"),
    ("gpl-asm", "gpl-asm"),
    ("image-extract", "image-extract"),
    ("image-pack", "image-extract"),
    ("region-render", "region-render"),
    ("save-inspect.py", "save-inspect"),
    ("dialog-extract.py", "dialog-extract"),
    ("verify-install.py", "verify-install"),
    ("repro.py", "repro"),
    ("opcode-fuzz.py", "opcode-fuzz"),
];

fn main() -> ExitCode {
    let cli = Cli::parse();
    match run(cli) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("opends: {e:#}");
            ExitCode::from(1)
        }
    }
}

fn run(cli: Cli) -> Result<()> {
    match cli.command {
        Cmd::Inspect { file } => cmd_inspect(&file),
        Cmd::Render { file, output } => cmd_render(&file, &output),
        Cmd::Find { pattern, gff } => cmd_find(&pattern, &gff),
        Cmd::Extract { file, output } => cmd_extract(&file, output.as_deref()),
        Cmd::Tools => cmd_tools(),
    }
}

// ---------- subcommands ----------

fn cmd_inspect(path: &Path) -> Result<()> {
    if !path.exists() {
        return Err(anyhow!("{} does not exist", path.display()));
    }
    let kind = detect(path)?;
    match kind {
        FileKind::Gff => {
            eprintln!("opends: {} looks like a GFF container; dispatching to gff-cat info", path.display());
            run_tool("gff-cat", &["info".as_ref(), path.as_os_str()])
        }
        FileKind::Save { name } => {
            eprintln!(
                "opends: {} looks like a save file ({}); dispatching to save-inspect",
                path.display(),
                name
            );
            run_python_tool("save-inspect", "save-inspect.py", &[path.as_os_str()])
        }
        FileKind::Png { width, height, indexed } => {
            println!("PNG: {}x{}, ColorType::{}", width, height, if indexed { "Indexed" } else { "Other" });
            if indexed {
                println!("To pack this back into a chunk: image-pack {} -o new-chunk.bin", path.display());
                println!("Then replace via: gff-cat replace <gff> <KIND> <id> new-chunk.bin -o patched.gff");
            } else {
                println!("Not palette-indexed; image-pack requires palette-indexed input.");
                println!("Re-save with e.g. `convert {} PNG8:indexed.png`.", path.display());
            }
            Ok(())
        }
        FileKind::Other { magic } => {
            println!(
                "{}: unrecognised magic bytes: {:02x} {:02x} {:02x} {:02x}",
                path.display(),
                magic[0], magic[1], magic[2], magic[3]
            );
            println!("opends doesn't recognise this file type.");
            Ok(())
        }
    }
}

fn cmd_render(file: &Path, output: &Path) -> Result<()> {
    run_tool(
        "region-render",
        &[file.as_os_str(), "-o".as_ref(), output.as_os_str()],
    )
}

fn cmd_find(pattern: &str, gff: &Path) -> Result<()> {
    run_python_tool(
        "dialog-extract",
        "dialog-extract.py",
        &["--grep".as_ref(), pattern.as_ref(), gff.as_os_str()],
    )
}

fn cmd_extract(file: &Path, output: Option<&Path>) -> Result<()> {
    let default_out;
    let out_path = match output {
        Some(p) => p,
        None => {
            let stem = file.file_stem().and_then(|s| s.to_str()).unwrap_or("chunks");
            let parent = file.parent().unwrap_or_else(|| Path::new("."));
            default_out = parent.join(format!("{stem}-extracted"));
            &default_out
        }
    };
    run_tool(
        "gff-cat",
        &[
            "bulk-extract".as_ref(),
            file.as_os_str(),
            "-o".as_ref(),
            out_path.as_os_str(),
        ],
    )
}

fn cmd_tools() -> Result<()> {
    let root = workspace_root();
    println!("OpenDS toolkit (umbrella v{})", env!("CARGO_PKG_VERSION"));
    println!();
    println!("{:<22} {:<10} Where", "Tool", "Version");
    println!("{:-<22} {:-<10} {:-<40}", "", "", "");
    for (binary, crate_dir) in WRAPPED_TOOLS {
        let version_path = root
            .as_ref()
            .map(|r| r.join("tools").join(crate_dir).join("VERSION"))
            .unwrap_or_else(|| PathBuf::from(format!("tools/{crate_dir}/VERSION")));
        let version = read_version(&version_path).unwrap_or_else(|_| "?".to_string());
        let resolved = resolve_tool(binary);
        let where_ = resolved
            .map(|p| p.display().to_string())
            .unwrap_or_else(|_| format!("(not found; check tools/{crate_dir}/)"));
        println!("{:<22} {:<10} {}", binary, version, where_);
    }
    Ok(())
}

// ---------- file magic detection ----------

enum FileKind {
    Gff,
    Save { name: String },
    Png { width: u32, height: u32, indexed: bool },
    Other { magic: [u8; 4] },
}

fn detect(path: &Path) -> Result<FileKind> {
    // First trust filename hints for the save-family (DARKRUN.GFF,
    // CHARSAVE.GFF, SAVE0?.SAV); the underlying tool reads them
    // all as GFFs.
    if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
        let upper = name.to_ascii_uppercase();
        if upper == "DARKRUN.GFF"
            || upper == "CHARSAVE.GFF"
            || upper == "DARKSAVE.GFF"
            || (upper.starts_with("SAVE") && upper.ends_with(".SAV"))
        {
            return Ok(FileKind::Save { name: name.to_string() });
        }
    }

    let bytes = fs::read(path)
        .with_context(|| format!("reading first bytes of {}", path.display()))?;
    if bytes.len() < 4 {
        return Ok(FileKind::Other {
            magic: [0, 0, 0, 0],
        });
    }
    let magic = [bytes[0], bytes[1], bytes[2], bytes[3]];

    if &magic == b"GFFI" {
        return Ok(FileKind::Gff);
    }
    // PNG signature.
    if bytes.len() >= 8 && &bytes[..8] == b"\x89PNG\r\n\x1a\n" {
        return Ok(parse_png_header(&bytes).unwrap_or(FileKind::Other { magic }));
    }
    Ok(FileKind::Other { magic })
}

fn parse_png_header(bytes: &[u8]) -> Option<FileKind> {
    // PNG: 8-byte signature, then IHDR chunk: length(4) + "IHDR"(4)
    // + width(4) + height(4) + bit_depth(1) + color_type(1) + ...
    // Width/height are big-endian. ColorType 3 == Indexed.
    if bytes.len() < 24 {
        return None;
    }
    if &bytes[12..16] != b"IHDR" {
        return None;
    }
    let width = u32::from_be_bytes([bytes[16], bytes[17], bytes[18], bytes[19]]);
    let height = u32::from_be_bytes([bytes[20], bytes[21], bytes[22], bytes[23]]);
    let color_type = bytes[25];
    Some(FileKind::Png {
        width,
        height,
        indexed: color_type == 3,
    })
}

// ---------- subprocess plumbing ----------

fn run_tool(binary: &str, args: &[&std::ffi::OsStr]) -> Result<()> {
    let path = resolve_tool(binary).with_context(|| format!("locating {binary}"))?;
    let status = Command::new(&path)
        .args(args)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .stdin(Stdio::inherit())
        .status()
        .with_context(|| format!("invoking {}", path.display()))?;
    if !status.success() {
        return Err(anyhow!(
            "{} exited with status {}",
            path.display(),
            status.code().map(|c| c.to_string()).unwrap_or_else(|| "?".into())
        ));
    }
    Ok(())
}

fn run_python_tool(
    crate_dir: &str,
    script_name: &str,
    args: &[&std::ffi::OsStr],
) -> Result<()> {
    let root = workspace_root()
        .ok_or_else(|| anyhow!("can't locate the opends workspace root"))?;
    let script = root.join("tools").join(crate_dir).join(script_name);
    if !script.is_file() {
        return Err(anyhow!(
            "{} not found at {}",
            script_name,
            script.display()
        ));
    }
    let status = Command::new("python3")
        .arg(&script)
        .args(args)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .stdin(Stdio::inherit())
        .status()
        .with_context(|| format!("running python3 {}", script.display()))?;
    if !status.success() {
        return Err(anyhow!(
            "python3 {} exited with status {}",
            script.display(),
            status.code().map(|c| c.to_string()).unwrap_or_else(|| "?".into())
        ));
    }
    Ok(())
}

// ---------- tool discovery ----------

/// Find the path to a wrapped binary. Prefer in-tree
/// `target/release/<name>` (a contributor running `cargo build
/// --release` lands here), then `target/debug/<name>`, then
/// `$PATH`. Python scripts (`*.py`) resolve to
/// `tools/<crate>/<name>` directly.
fn resolve_tool(binary: &str) -> Result<PathBuf> {
    if binary.ends_with(".py") {
        let root = workspace_root()
            .ok_or_else(|| anyhow!("can't locate workspace root"))?;
        for (script, crate_dir) in WRAPPED_TOOLS {
            if *script == binary {
                let path = root.join("tools").join(crate_dir).join(script);
                if path.is_file() {
                    return Ok(path);
                }
            }
        }
        return Err(anyhow!("python script {} not found in any tools/ dir", binary));
    }

    let root = workspace_root();
    if let Some(root) = root.as_ref() {
        for profile in ["release", "debug"] {
            let candidate = root.join("target").join(profile).join(binary);
            if candidate.is_file() {
                return Ok(candidate);
            }
        }
    }
    // Fall back to $PATH.
    if let Ok(path) = env::var("PATH") {
        for dir in env::split_paths(&path) {
            let candidate = dir.join(binary);
            if candidate.is_file() {
                return Ok(candidate);
            }
        }
    }
    Err(anyhow!(
        "{} not found in target/release/, target/debug/, or $PATH; \
         build with `cargo build --release` from the workspace root",
        binary
    ))
}

/// Walk up from the current binary's directory looking for a
/// `Cargo.lock` (the workspace root marker). Returns `None` if no
/// Cargo.lock is found within 8 levels (opends installed via
/// system package, etc.).
fn workspace_root() -> Option<PathBuf> {
    let exe = env::current_exe().ok()?;
    let mut dir = exe.parent()?.to_path_buf();
    for _ in 0..8 {
        if dir.join("Cargo.lock").is_file() && dir.join("tools").is_dir() {
            return Some(dir);
        }
        if !dir.pop() {
            break;
        }
    }
    None
}

fn read_version(path: &Path) -> Result<String> {
    let text = fs::read_to_string(path)
        .with_context(|| format!("reading {}", path.display()))?;
    Ok(text.trim().to_string())
}
