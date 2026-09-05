# opcode-fuzz

- **Version**: see [`VERSION`](VERSION).

The Phase 5 tool that closes the GPL reverse-engineering arc.
`gpl-disasm` reads GPL bytecode; `gpl-asm` writes it; this tool
runs swapped-in test chunks under DOSBox-Staging to **observe**
what individual opcodes do, turning "guess from context" into
"watch the engine react."

The Phase 5 tool that closes the GPL reverse-engineering arc.
`gpl-disasm` reads GPL bytecode; `gpl-asm` writes it; this tool
runs swapped-in test chunks under DOSBox-Staging to **observe**
what individual opcodes do, turning "guess from context" into
"watch the engine react." v0.1.0 shipped the chunk-patchwork
pipeline; v0.2.0 added the run + observe loop; v0.3.0 ships
the boot-chunk discovery half.

## Boot-chunk discovery (`boot-chunks`)

**`opcode-fuzz boot-chunks <gff>`**: identifies the safest
chunks to swap. Drives `gpl-disasm --global-cfg --json` and
reports per-chunk inbound-call counts. Chunks with **zero
inbound `gpl global sub` edges** are pure entry points: the
engine's main loop must dispatch them directly (since no other
chunk does), so swapping in a test chunk is guaranteed to fire.

```sh
python3 opcode-fuzz.py boot-chunks .games/ds1/GPLDATA.GFF
# stderr: opcode-fuzz boot-chunks: 129 entry-point candidates out
# of 250 chunks (587 edges in the global CFG)
# stdout: JSON report with boot_candidates and most_called arrays
```

Corpus tallies:

| Game | Chunks | Boot candidates | Edges | Top utility |
|------|-------:|----------------:|------:|:-----------|
| DS1  |    250 |             129 |   587 | GPL/74 (169 inbound) |
| DS2  |    350 |             196 |   797 | GPL/27 (218 inbound) |

The top-utility chunks (highest inbound-call counts) are
engine-helper / shared-subroutine candidates worth curating
names for in `gpl-disasm/syms/functions.toml` once their role
is RE'd.


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

## Status

- **Recipe-driven `fuzz`** waits on a settled recipe format.
  `recipes/` holds the intended format and why it is not
  active yet: `gpl-asm` parses the full text-listing format,
  and a short-form mnemonic-only recipe needs either a
  preprocessor here or a `gpl-asm` extension.
- **GPL VM state addresses** in DSUN.EXE (accumulator, local
  stack, global arrays) are the remaining prerequisite for
  visible-in-`DARKRUN.GFF` probes; `dsun-exe-re.md` 4.4 hints
  where some state lives.
- Deterministic launch and input automation are shipped via
  `repro` v0.4.0's keystroke scheduler.

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
