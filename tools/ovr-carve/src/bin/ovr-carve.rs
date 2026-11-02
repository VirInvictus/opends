//! ovr-carve: flatten Borland VROOM overlays into a single analysis MZ.
//!
//! See the crate docs (src/lib.rs) and README.md for the transform and its
//! limits. The output is an analysis artifact for REA/Ghidra, never a
//! runnable program, and never a patch target.

use std::path::{Path, PathBuf};
use std::process::exit;

use anyhow::{Context, bail};
use clap::{Parser, Subcommand};
use ovr_carve::{DEFAULT_LOAD_SEGMENT, MapError, OvrMap, default_ovr_map_path, verify};

#[derive(Parser)]
#[command(
    name = "ovr-carve",
    version,
    about = "Flatten Borland VROOM overlays into a single analysis MZ (Dark Sun DSUN.EXE)."
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Carve EXE into <stem>.ovrflat.exe (or --output).
    Carve {
        /// The pristine overlaid executable.
        exe: PathBuf,
        /// Output path (default: <exe stem>.ovrflat.exe beside the input).
        #[arg(short, long)]
        output: Option<PathBuf>,
        /// Overwrite an existing output file.
        #[arg(long)]
        force: bool,
        /// Pre-generated `ovr-map --json` file instead of running ovr-map.
        #[arg(long)]
        map: Option<PathBuf>,
        /// Path to ovr-map.py (default: the repo-tree sibling; $OVR_MAP_PY).
        #[arg(long)]
        ovr_map: Option<PathBuf>,
        /// MZ load segment the rewritten segment words assume.
        #[arg(long, default_value_t = DEFAULT_LOAD_SEGMENT)]
        load_segment: u16,
        /// Print the carve report and module mapping as JSON to stdout.
        #[arg(long)]
        json: bool,
    },
    /// Check that CARVED is byte-exactly what carving EXE produces.
    Verify {
        /// The pristine overlaid executable.
        exe: PathBuf,
        /// A previously carved output.
        carved: PathBuf,
        #[arg(long)]
        map: Option<PathBuf>,
        #[arg(long)]
        ovr_map: Option<PathBuf>,
        #[arg(long, default_value_t = DEFAULT_LOAD_SEGMENT)]
        load_segment: u16,
        #[arg(long)]
        json: bool,
    },
}

fn load_map(
    exe: &Path,
    map: &Option<PathBuf>,
    ovr_map: &Option<PathBuf>,
) -> anyhow::Result<OvrMap> {
    match map {
        Some(path) => {
            let text =
                std::fs::read(path).with_context(|| format!("reading {}", path.display()))?;
            Ok(serde_json::from_slice(&text)?)
        }
        None => {
            let script = ovr_map.clone().unwrap_or_else(default_ovr_map_path);
            ovr_carve::fetch_map(exe, &script).map_err(|e| match e {
                MapError::InvalidJson(inner) => inner.into(),
                MapError::Spawn(inner) => inner.into(),
                other => anyhow::Error::new(other),
            })
        }
    }
}

fn main() {
    let cli = Cli::parse();
    if let Err(e) = run(cli) {
        eprintln!("ovr-carve: {e:#}");
        exit(1);
    }
}

fn run(cli: Cli) -> anyhow::Result<()> {
    match cli.command {
        Command::Carve {
            exe,
            output,
            force,
            map,
            ovr_map,
            load_segment,
            json,
        } => {
            let pristine =
                std::fs::read(&exe).with_context(|| format!("reading {}", exe.display()))?;
            let map = load_map(&exe, &map, &ovr_map)?;
            let carved = ovr_carve::carve(&pristine, &map, load_segment)?;

            let out_path = output.unwrap_or_else(|| {
                let stem = exe
                    .file_stem()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|| "output".into());
                exe.with_file_name(format!("{stem}.ovrflat.exe"))
            });
            if out_path.exists() && !force {
                bail!(
                    "{} already exists; pass --force to overwrite",
                    out_path.display()
                );
            }
            std::fs::write(&out_path, &carved.output)
                .with_context(|| format!("writing {}", out_path.display()))?;

            if json {
                let report = serde_json::json!({
                    "tool": "ovr-carve",
                    "version": env!("CARGO_PKG_VERSION"),
                    "input": exe,
                    "output": out_path,
                    "load_segment": carved.mapping.load_segment,
                    "stats": {
                        "applied": carved.stats.applied,
                        "markers": carved.stats.markers,
                        "per_module": carved.stats.per_module,
                        "tag_histogram": carved.stats.tag_histogram,
                        "target_classes": carved.stats.target_classes,
                    },
                    "mapping": carved.mapping,
                });
                println!("{}", serde_json::to_string_pretty(&report)?);
            } else {
                println!(
                    "wrote {} ({} bytes; {} relocations applied across {} modules; \
                     overlay code now decompiles under load segment {:#06x})",
                    out_path.display(),
                    carved.output.len(),
                    carved.stats.applied,
                    carved.mapping.modules.len(),
                    load_segment,
                );
            }
        }
        Command::Verify {
            exe,
            carved,
            map,
            ovr_map,
            load_segment,
            json,
        } => {
            let pristine =
                std::fs::read(&exe).with_context(|| format!("reading {}", exe.display()))?;
            let carved_bytes =
                std::fs::read(&carved).with_context(|| format!("reading {}", carved.display()))?;
            let map = load_map(&exe, &map, &ovr_map)?;
            let result = verify(&pristine, &map, &carved_bytes, load_segment);
            if json {
                let report = match &result {
                    Ok(()) => serde_json::json!({
                        "tool": "ovr-carve",
                        "version": env!("CARGO_PKG_VERSION"),
                        "input": exe,
                        "carved": carved,
                        "verify": "ok",
                    }),
                    Err(e) => serde_json::json!({
                        "tool": "ovr-carve",
                        "version": env!("CARGO_PKG_VERSION"),
                        "input": exe,
                        "carved": carved,
                        "verify": "failed",
                        "detail": e.to_string(),
                    }),
                };
                println!("{}", serde_json::to_string_pretty(&report)?);
            }
            match result {
                Ok(()) => {
                    if !json {
                        println!(
                            "verify: OK ({} bytes match the carve of {})",
                            carved_bytes.len(),
                            exe.display()
                        );
                    }
                }
                Err(e) => {
                    if !json {
                        eprintln!("ovr-carve: {e}");
                    }
                    exit(1);
                }
            }
        }
    }
    Ok(())
}
