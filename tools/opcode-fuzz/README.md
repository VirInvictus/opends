# opcode-fuzz

OpenDS opcode-fuzz harness. v0.1.0.

The Phase 5 tool that closes the GPL reverse-engineering arc.
`gpl-disasm` reads GPL bytecode; `gpl-asm` writes it; this tool
will eventually run swapped-in test chunks under DOSBox-Staging
to **observe** what individual opcodes do, turning "guess from
context" into "watch the engine react." That's the v0.2.0+
shape; v0.1.0 ships the chunk-patchwork pipeline the discovery
loop sits on.

## What v0.1.0 ships

The chunk plumbing. No DOSBox-side discovery yet.

- **`opcode-fuzz extract <gff> <kind> <id> -o <work-dir>`**:
  stage a single GPL / MAS chunk for editing. Produces
  `original.bin` (the raw chunk bytes; reference for diff),
  `chunk.json` (gpl-disasm JSON; edit for surgical changes),
  `chunk.asm` (gpl-disasm text listing; edit for hand-written
  work), and `meta.json` (the source GFF + chunk coordinate so
  `pack` doesn't need them re-specified).
- **`opcode-fuzz pack <work-dir> -o <new.gff>`**: read the
  work-dir's `meta.json`, encode the (possibly edited)
  `chunk.json` via `gpl-asm`, replace the chunk in the source
  GFF, write the result to `--output`.
- **`opcode-fuzz roundtrip <gff>`**: corpus self-test. For
  every GPL / MAS chunk in the input GFF:
  `disasm -> JSON -> reassemble -> replace -> compare GFF`.
  Catches three classes of regression: gpl-asm encode bugs
  surfacing in the GFF-replace path, gff-cat replace
  regressions, and any non-aligned chunk that the per-chunk
  corpus tests skip but would surface here as a mismatch.

Current corpus baseline (DS1 + DS2 GOG 1.10):

| Source | Chunks | Matched | Mismatched | Encode failures | Skipped |
|---|---|---|---|---|---|
| `ds1/GPLDATA.GFF` | 250 | 250 | 0 | 0 | 0 |
| `ds2/GPLDATA.GFF` | 350 | 350 | 0 | 0 | 0 |

## Why this exists (the Phase 5 vision)

GPL is the Dark Sun engine's embedded bytecode VM. We have a
sound disassembler (`gpl-disasm`, 100% corpus alignment) and a
sound reassembler (`gpl-asm`, 600 / 600 byte-identical), but
**most of the 129-entry opcode catalogue is named from libgff's
seed listing**, not verified from observed behaviour. Each
opcode's actual side effects (which globals it reads, which
stack slot it writes, whether it consumes additional bytes
from the byte stream) are still inferred rather than measured.

The eventual `opcode-fuzz` flow:

1. **Author a test chunk**. Encode a tiny chunk via `gpl-asm`
   with a known prologue (load known values into globals),
   the opcode under test, and a known epilogue (write the
   resulting state to a sentinel global).
2. **Swap it in**. Use `pack` to replace a known-runs-on-boot
   GPL chunk with the test chunk. Stage the patched
   `GPLDATA.GFF` into a `repro` overlay so the live install
   stays clean.
3. **Run under DOSBox**. Use `repro` (likely a new
   `play-once` or per-chunk fixture) to boot the engine, let
   it execute the test chunk, and capture the post-state.
4. **Diff observable state**. Read `DARKRUN.GFF` /
   `SAVE0N.SAV` (same file format; documented in
   save-inspect v0.6.0) via `save-inspect` and diff against
   the pre-run baseline. Look for changes in the sentinel
   global to confirm the opcode ran; correlate other state
   changes with the opcode's effect.
5. **Iterate**. Bisect parameters to verify what each byte in
   the opcode's payload controls. Record the findings in
   `docs/gpl-opcodes.md`.

## Open problems / dependencies (queued for v0.2.0+)

- **Which chunks run on game boot?** The discovery loop needs
  a chunk that runs deterministically and early, before any
  user input. `dialog-extract`'s CFG might help identify
  boot-time entry points; otherwise it's `gpl-disasm`'s
  cross-chunk callgraph (`--global-cfg`) plus inspection of
  the engine's main loop in DSUN.EXE.
- **GPL VM state addresses inside DSUN.EXE**. We need to know
  where the engine keeps the accumulator, the local-variable
  stack, and the global-variable arrays so the test chunk can
  write to a location whose change is visible in
  `DARKRUN.GFF` after the run. The 0x230e5 GMAP / entity-
  render finding in `dsun-exe-re.md` §4.4 hints at where some
  engine state lives; more work needed.
- **A deterministic-launch path through `repro`**. The
  current `--play` mode is interactive (user quits the game
  to close DOSBox). Per-opcode fuzzing wants "run for N
  ticks, then exit" semantics, which means input automation
  (ydotool) or DOSBox config tricks that auto-quit the
  engine. That's already queued for `repro` v0.3.0.
- **DOSBox-Staging debugger interface**. DOSBox-X has
  scripting; DOSBox-Staging has an interactive debugger only
  (Ctrl+F1). For v0.1.0 we observe state through saved files,
  not through a debugger. That stays the cheap path; the
  debugger-IPC route is a v0.3.0+ stretch.

## Adding a new manual edit

Workflow today (without the run-and-observe parts):

```sh
# Stage a chunk for editing.
python3 tools/opcode-fuzz/opcode-fuzz.py extract \
    .games/ds1/GPLDATA.GFF "GPL " 199 -o /tmp/chunk-199

# Edit /tmp/chunk-199/chunk.json (or .asm) by hand.
# `gpl-asm validate` is your friend; the pack step runs it
# automatically and aborts on validation errors.

# Re-pack into a patched GFF.
python3 tools/opcode-fuzz/opcode-fuzz.py pack \
    /tmp/chunk-199 -o /tmp/GPLDATA.patched.gff
```

The patched GFF is suitable for staging into a `repro`
overlay via the bug fixture's `[setup].copy_files`. End-to-end
"swap and run" automation lands in v0.2.0.

## Requirements

- Python 3.11+ (uses `tomllib` indirectly through the shared
  driver patterns).
- The release builds of `gff-cat`, `gpl-disasm`, and `gpl-asm`
  under `target/release/`. Run `cargo build --release` from
  the repo root if missing; opcode-fuzz checks and bails with
  a clear error.
