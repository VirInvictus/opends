# exe-patch

Author, verify, and apply in-place byte patches to `DSUN.EXE`: the EXE
half of what `gpl-asm --patch` does for bytecode. Addresses are written
the way the RE docs write them (`ovr:19+0x17a7`, a catalogued function
name, or a raw file offset), every edit carries a mandatory `bytes_old`
fingerprint, and anything the Borland overlay format cannot survive is
rejected before anything is written.

- **Language**: Python (stdlib only; shells out to `nasm` for `--asm`
  and to the sibling `ovr-map` for address resolution).
- **Requires**: Python 3.11+. `nasm` only for `--asm`.
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## The in-place-only rule

Every overlay descriptor stores its payload offset as an absolute file
position. One inserted byte anywhere before the last segment shifts
every following payload, and the game loads garbage as code. So every
edit is a **same-length byte replacement**: `bytes_new` shorter or
longer than `bytes_old` is a hard error, and the applier re-asserts the
output length before writing. This is spec.md §3.2 made enforceable.

## Patch scripts

```toml
game = "ds1"          # optional; hash-checks the target against the
                      # canonical GOG 1.10 manifest and refuses a wrong install

[[edit]]
at = "ovr:19+0x17a7"  # overlay segment 19, segment-local offset 0x17a7
bytes_old = "8b c8"   # mandatory fingerprint; refuse to apply on mismatch
bytes_new = "31 c0"   # same length as bytes_old, always
reason = "why this edit exists"
```

`at` takes three base forms, each with an optional trailing `+ N`:

| Form | Resolves to |
|---|---|
| `ovr:SEG+OFF` | segment `SEG`'s payload start + `OFF` (the `docs/dsun-exe-re.md` notation) |
| a catalogue name | the `ovr-map` syms row: resident file offset, or segment payload start + row offset |
| a bare number | an absolute file offset (header, resident image, anywhere) |

Names come from `tools/ovr-map/syms/<game>.toml` (auto-selected from the
script's `game` field, or pass `--syms FILE`). A name that resolves to
two catalogue rows is a hard error naming the candidates, matching the
bytecode resolver's rule. Catalogue names are the one address class
guaranteed to be a confirmed function entry; prefer them for bases.

## Usage

```sh
# The gate: resolve, classify, fingerprint-check; writes nothing.
python3 exe-patch.py .games/ds1/DSUN.EXE --verify fix.toml

# Apply to a NEW file (the tool never modifies its input):
python3 exe-patch.py .games/ds1/DSUN.EXE --patch fix.toml -o DSUN-fixed.exe

# Validate without writing:
python3 exe-patch.py .games/ds1/DSUN.EXE --patch fix.toml --dry-run

# Machine-readable report:
python3 exe-patch.py .games/ds1/DSUN.EXE --verify fix.toml --json

# Author replacement bytes (16-bit x86 via nasm):
python3 exe-patch.py --asm "mov ax, 0x4b75; xor cx, cx"
```

`--verify` fails a site which drifts from its fingerprint, straddles a
segment payload boundary, or lands in the inter-segment padding (or the
FBOV header, or past EOF). Edits must not overlap. Validation is
all-or-nothing: nothing is written unless every edit passes every check.
A no-op script applies byte-identically, so applying a script and then
its inverse restores the original file exactly; `--selftest` proves both
shapes plus every refusal.

### Why nasm and not `pwn asm`

The previously documented assembler fallback (`pwn asm` at
`arch='i386', bits=16`) does not work on pwntools 4.15: pwnlib rejects
the i386/16 combination outright (`Invalid arch/bits combination`),
confirmed 2026-09-06. `--asm` shells out to `nasm -f bin` in
`bits 16` mode instead: the assembler half of the same toolchain as
ovr-map's `ndisasm` disassembly, and the selftest round-trips one
instruction through `ndisasm -b 16` to keep the pair honest. See
`docs/re-tooling.md`.

## Self-test

```sh
python3 exe-patch.py --selftest
```

Builds a minimal Borland-overlaid fixture in memory (parsed by the real
`ovr-map`, so the inter-tool contract is exercised too) and proves:

- a no-op script applies byte-identically;
- an edit followed by its inverse restores the original bytes exactly;
- an off-by-one site past a payload end is rejected as padding;
- a straddle of a payload boundary is rejected;
- a fingerprint mismatch, a length change, a missing `bytes_old`,
  overlapping edits, a site in the FBOV header, and a script whose
  `game` hash does not match the target are all refused;
- symbolic `at` forms resolve to the documented file offsets;
- `--asm` output round-trips through `ndisasm -b 16` (when nasm is
  installed).

The same no-op and padding proofs then run against the real binaries in
`.games/ds1` and `.games/ds2`, skipping cleanly when they are absent.

## Relationship to the darkfix applier

`exe-patch` is the **authoring and verification** surface; it never
touches an install. The player-facing applier
(`ds1-patch/scripts/apply.py`) consumes absolute offsets and
fingerprints in a `manifest.toml`, which is exactly what a validated
script resolves to. `--json` emits the resolved offsets so packaging can
be mechanical when Phase 6 needs it.
