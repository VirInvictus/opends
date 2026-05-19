# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

OpenDS is a community toolkit for SSI's Dark Sun CRPGs (Shattered Lands 1993, Wake of the Ravager 1994). Three product surfaces, ordered by priority:

1. **Tools** under `tools/` (MIT, public). Each ships independently with its own `README`, `VERSION`, and tagged release.
2. **darkfix patches** under `ds1-patch/` and `ds2-patch/` (forthcoming). Applied to a player's GOG install; the game still launches via DOSBox under the original engine.
3. **Documentation** under `docs/`. Every RE finding gets written down.

Read [`spec.md`](spec.md) before changing semantics, and [`roadmap.md`](roadmap.md) for current phase status. The name `OpenDS` carries an aspirational engine reimplementation; that is not a v1 deliverable. See spec.md §12.

**Tools come before patches.** Do not propose patch-authoring work (Phase 6 onward in roadmap.md) until the toolkit phases are mature. Anything that makes the digging easier wins.

## Repository layout

- **Cargo workspace** at the repo root. Members live under `tools/<name>/` for Rust tools (`gff-edit`, `gpl-disasm`, `gpl-asm`, `image-extract`, `region-render`). `Cargo.toml` defines the shared dependency set (`clap`, `anyhow`, `thiserror`, `serde`, `serde_json`, `toml`, `png`); new workspace deps need per-tool justification per spec §7a.
- **Python tools** under `tools/<name>/` are single-file scripts, stdlib-only by default. Python target is 3.11+ (uses `tomllib`). Pre-approved exceptions: `bsdiff4` for the eventual applier.
- **Hand-curated TOML catalogues** live alongside the tool that consumes them: `tools/gpl-disasm/syms/{opcodes,functions,variables}.toml` and `docs/source-hashes/{ds1,ds2}-gog-1.10.toml`.
- **`docs/`** is the canonical reference for formats (`file-formats.md`), opcodes (`gpl-opcodes.md`), the bug catalog (`known-bugs.md`), and upstream attribution (`upstream-projects.md`).
- **`CREDITS.md`** is the per-feature attribution manifest mapping each OpenDS feature to the specific upstream file or function it was ported from. Update it any time you port a new piece of logic.

## Build and test

```sh
cargo build                                       # all Rust tools
cargo build -p gff-edit                           # one tool
cargo test                                        # all
cargo test -p gpl-disasm                          # one tool
cargo test -p gpl-disasm corpus_alignment         # one test (substring match)
cargo test --release                              # gpl-asm has a known-flaky debug_assert_eq in lib.rs:91; release passes
```

Many Rust tools have **corpus tests** that walk every shipped GFF in `.games/ds1/` and `.games/ds2/` and assert a round-trip / parse / decode invariant (e.g. `gff-edit/tests/corpus_roundtrip.rs`). These need the games extracted under `.games/` (see below); without them the corpus tests skip.

Python tools run directly:

```sh
python3 tools/verify-install/verify-install.py --game ds1
python3 tools/save-inspect/save-inspect.py <save.gff>
python3 tools/dialog-extract/dialog-extract.py <gpldata.gff>
python3 tools/repro/repro.py ds1-smoke --play --session main
```

## Game-install paths

- **`.games/ds1/`**, **`.games/ds2/`**: dev-side innoextract output. The Rust corpus tests read from here. Gitignored.
- **`~/.wine/drive_c/GOG Games/Dark Sun/`** and **`Dark Sun 2/`**: Brandon's pristine recovery installs and the source of in-game saves used by `save-inspect` and `repro --play`.
- **`.games/setup_*.exe`**: GOG installer EXEs used by `verify-install --repair` (shells to `innoextract`).

The canonical SHA256 manifest for each game ships at `docs/source-hashes/{ds1,ds2}-gog-1.10.toml`. `verify-install` checks against these; future patch `manifest.toml` files cite them.

### Never break the install

DOSBox runs that launch the actual game must use **overlay mounts** so writes never reach the install. `DSUN.EXE` zeros `DARKRUN.GFF` on boot if it can write to the install directory; one careless run on the pristine install erases its world state. `tools/repro/` already enforces this via `c-overlay/` mounting. Match that pattern in any new DOSBox-launching code.

## Reference checkouts

Three upstream RE projects are cloned into dot-prefixed directories (gitignored) for cross-reference. They are read-only research material, not modifiable:

- **`.dsun_music/`**: John Glassmyer's tools. Source of the GFF *writer* policy (in-place if it fits, append otherwise), the GFFI segmented-chunk cross-reference layout, and the PLAN frame decoder.
- **`.dsoageofheroes/`**: paulofthewest's organization. `libgff` is the deepest public GFF/GPL reverse-engineering; the 129-entry opcode catalogue, GPL_* constants, and 7-bit packed inline string decoder all come from here. `soloscuro-archive` is the closest public partial GPL VM.
- **`.dso-online/`**: greg-kennedy's DSO research mirror (AGPL-3.0; research-only, do not vendor). Hosts `tools/symbols.txt` with 3,530 named functions from DS2's shared codebase; primary source for `tools/gpl-disasm/syms/functions.toml`.

When porting logic from any of these, cite the upstream file/function in a code comment AND add a row to `CREDITS.md`. We follow attribute-everything as policy.

The "DSO Emulator" sometimes discussed in the community is a multiplayer Crimson Sands project on a private Discord; it is unrelated to OpenDS's singleplayer DS1/DS2 toolkit.

## Versioning

Per [`docs/versioning.md`](docs/versioning.md): every tool and every patch versions independently. Each tool's directory contains a plain-text `VERSION` (one line, no leading `v`). For Rust tools, `Cargo.toml`'s `version =` must match the `VERSION` file. Python single-file tools read their `VERSION` at runtime. Tags are `<tool>-vMAJOR.MINOR.PATCH` (e.g. `gpl-disasm-v0.5.0`). The umbrella repo itself is not versioned.

When bumping a tool: update `VERSION`, update its `Cargo.toml`/script version, add a `patchnotes.md` entry (newest at top), tick the relevant roadmap box.

## House style (this repo)

- **No em-dashes in prose** anywhere a human reader will see it (READMEs, spec, roadmap, patchnotes, commit messages, PR descriptions). Use periods, semicolons, colons, commas, or parentheses. EN-dashes in numeric ranges and hyphens in compound modifiers are fine. Comments inside source code are exempt.
- **Match what's there.** Read a neighbour before writing. Each tool has its own established README shape and test layout; respect it.
- **Comments sparingly.** Comment when explaining a workaround, citing upstream attribution, or noting a non-obvious invariant. Otherwise let the code speak.
- **No new third-party deps without asking.** Especially in Python tools, which are stdlib-only by default.
- **Don't push without explicit approval.** Don't force-push without explicit approval.

## Inter-tool data flow

The Rust tools form a stack; later tools consume earlier ones via the workspace:

- `gff-edit` is the foundation; every GFF read/write goes through it.
- `gpl-disasm` reads GPL/MAS chunks via `gff-edit` and emits JSON or annotated text. Its `--json` output is the contract that `gpl-asm`, `dialog-extract`, and `opcode-fuzz` consume.
- `gpl-asm` round-trips `gpl-disasm` output back to bytecode. 600/600 corpus chunks are byte-identical; preserve that invariant.
- `image-extract` decodes bitmap chunks; `region-render` composites tiles + walls + entity sprites and (as of v0.6.0) animates entities via `image-extract`'s multi-frame decoder.
- Python tools (`dialog-extract`, `save-inspect`, `opcode-fuzz`) consume Rust JSON output where they interface with the disassembler.

When changing a Rust tool's JSON schema, expect downstream Python consumers to break. Coordinate the bump or land a compatibility shim.
