# opends

Umbrella CLI for the OpenDS toolkit. The "I have this file, what
is it?" entry point a new contributor reaches for before they
know the names of the underlying tools. Auto-dispatches by file
magic; never reimplements logic.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Shells out to the existing toolkit (`gff-cat`, `gpl-disasm`,
`save-inspect.py`, `dialog-extract.py`, `region-render`,
`image-pack`). Prefers in-tree `target/release/` binaries over
`$PATH`, so a contributor running `cargo build --release` lands
on their own builds automatically.

## Day 1 walkthrough

You cloned the repo. You have a GOG install. You want to look
at the game.

```sh
# Build the workspace once.
cargo build --release

# What's installed? Versions, where each tool lives, what's
# present / missing.
./target/release/opends tools

# You have a file. Skip thinking about which tool reads it.
opends inspect .games/ds1/RESOURCE.GFF       # → gff-cat info
opends inspect .games/ds1/DARKRUN.GFF        # → save-inspect
opends inspect .games/ds1/SAVE00.SAV         # → save-inspect
opends inspect /path/to/sprite.png           # → PNG metadata + pack hint

# Bulk operations.
opends extract .games/ds1/RESOURCE.GFF       # → gff-cat bulk-extract
opends render .games/ds1/RGN02.GFF -o map.png
opends find "Magnolia" .games/ds1/GPLDATA.GFF
```

## Subcommand dispatch

| `opends inspect <file>`                | Detected as | Dispatches to            |
|----------------------------------------|-------------|--------------------------|
| Magic bytes `GFFI`                     | GFF         | `gff-cat info`           |
| Filename `DARKRUN.GFF` / `CHARSAVE.GFF` / `DARKSAVE.GFF` / `SAVE??.SAV` | Save | `save-inspect.py`     |
| PNG signature, ColorType Indexed       | indexed PNG | inline summary + `image-pack` pointer |
| PNG signature, other ColorType         | non-indexed PNG | inline summary + conversion hint |
| Anything else                          | unknown     | prints magic bytes, exits |

Other subcommands are thin wrappers:

| Subcommand                       | Wrapper for                                   |
|----------------------------------|----------------------------------------------|
| `opends render <gff> -o <png>`   | `region-render <gff> -o <png>`               |
| `opends find <pattern> <gff>`    | `python3 dialog-extract.py --grep ...`       |
| `opends extract <gff> -o <dir>`  | `gff-cat bulk-extract <gff> -o <dir>`        |
| `opends tools`                   | reads every `tools/*/VERSION` and prints     |

## Tool discovery

`opends` looks for each underlying binary in this order:

1. `<workspace-root>/target/release/<name>`
2. `<workspace-root>/target/debug/<name>`
3. `$PATH`

Workspace root = nearest ancestor of the running `opends` binary
that contains both `Cargo.lock` and a `tools/` directory. If
none is found (e.g. `opends` installed via a system package),
only `$PATH` is consulted.

Python tools (`*.py`) resolve to `<workspace-root>/tools/<crate>/<name>.py`
directly and are invoked via `python3`. The dispatcher errors
out clearly if a tool is missing.

## What v0.1.0 does NOT ship

- **Interactive / TUI mode**. v0.1.0 is plain CLI.
- **Editor integration** (drop into a disassembler with the
  right chunk pre-loaded). Modder UX experiment for v0.2.0.
- **Magic detection beyond GFF / PNG / save-by-filename**.
  Bitmap chunks inside a GFF still need
  `opends inspect <gff>` followed by reading the chunk list;
  there's no auto-render of an embedded sprite yet.
- **Cross-GFF search** (`opends find` is single-GFF). A
  whole-`.games/` sweep is a v0.2.0 candidate.
