# ovr-carve

Flatten a Borland VROOM executable (Dark Sun `DSUN.EXE`) into a single
*analysis* MZ whose initialized module spans the whole file, so overlay
code decompiles in [REA](https://github.com/morluto/rea)/Ghidra beside
the resident image. REA's MZ lane maps only the initialized module,
which excludes the overlay area, where ~93% of the games' overlaid code
lives. The transform is documented in `docs/overlay-formats.md`
(sections 2-5); the module map comes from `ovr-map --json`.

The output is an **analysis artifact only**: not runnable, not a patch
target, not shipped. Every byte keeps its original file offset, so every
offset the rest of the toolkit publishes (the `syms/` catalogues, fix
writeups, `ovr-map` output) stays valid in the carved image.

## What it does

1. Applies each overlay module's per-module relocation table in place. A
   stored word is a segtab byte offset (record = `v >> 3`, low 3 bits
   tag, bit0 = the overlay marker the runtime slow path would need). The
   word is rewritten to `load-segment + segtab[record].start_para`, the
   same value the runtime applier would leave under REA's fixed load
   segment `0x1000`.
2. Extends the MZ header page fields so the initialized module covers
   the file; the FBOV header, descriptor chain, stub blocks, and the
   now-spent relocation tables stay mapped as data. The resident image's
   own relocations are untouched.

Refusals (loud, before any write): overlay-marker words (bit0 set; the
runtime slow path's pattern rewrite has no static equivalent), odd
relocation table sizes, entries outside their module, records outside
the segtab (the "already carved" shape), already-carved inputs,
unaligned payloads, and inputs whose map disagrees with the segtab.

## Usage

```sh
cargo build -p ovr-carve
target/debug/ovr-carve carve .games/ds2/DSUN.EXE          # -> DSUN.ovrflat.exe
target/debug/ovr-carve carve .games/ds1/DSUN.EXE --json   # + report and mapping
target/debug/ovr-carve verify .games/ds2/DSUN.EXE DSUN.ovrflat.exe
```

Then point REA (or Ghidra) at the carved file:

```sh
rea inspect-native-load-image DSUN.ovrflat.exe   # attests dos-mz, overlay_bytes 0
rea decompile DSUN.ovrflat.exe --file-offset 0x70713
```

`--json` prints the carve report plus the module/entry mapping in both
coordinate systems (original file offsets, and the segment/linear
addresses REA reports under the load segment), which feeds symbol
annotation.

## Flags

| Flag | Meaning |
|---|---|
| `-o, --output <FILE>` | Output path (default `<stem>.ovrflat.exe` beside the input) |
| `--force` | Overwrite an existing output |
| `--map <FILE>` | Pre-generated `ovr-map --json` instead of running ovr-map |
| `--ovr-map <PATH>` | Path to `ovr-map.py` (default: the repo-tree sibling; `$OVR_MAP_PY` overrides) |
| `--load-segment <N>` | MZ load segment the rewritten words assume (default `0x1000`) |
| `--json` | Machine-readable report on stdout |

## Tests

`cargo test -p ovr-carve` runs a fixture round-trip plus every refusal
on a synthetic overlaid MZ (no game files needed), and, when
`.games/ds1` / `.games/ds2` are present, the corpus carve asserting the
documented totals (DS1 8,232 / DS2 8,262 relocations, zero overlay
markers) and a verify round-trip per game.

## Known limits

- The carved image is load-segment-dependent (`0x1000` for REA); it is
  not relocatable and would not run even under an emulator that accepted
  it.
- Overlay-to-overlay references still go through the resident stub
  blocks (that is the only form the shipped games use), so every far
  call resolves to a real address; no runtime dispatch is modeled.
- The reloc table position assumes the documented layout
  (`code | table | pad`, table directly after the code); the corpus
  validation in `docs/overlay-formats.md` section 4 covers all 101
  modules of both games.
