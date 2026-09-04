# DSO Debug Symbols

The single most valuable public reference for naming functions
and variables inside DS2's `DSUN.EXE`. This page is the
maintainer's index into the symbol artifact and the
hand-curated catalogue we grow over time.

## Where the symbols come from

Dark Sun Online: Crimson Sands (1996) shipped a v1.0 client
(`MDARK.EXE`) that included Watcom debug symbols with function
and variable names. DSO inherited the *Wake of the Ravager*
codebase wholesale, so those names map (with care) onto the
same functions in WotR's `DSUN.EXE`.

Greg Kennedy's [`DarkSunOnline`](https://github.com/greg-kennedy/DarkSunOnline)
repository extracted the symbol table from the v1.0 client and
checks it into `tools/symbols.txt` (5,777 lines: 3,530 functions
+ 2,247 globals / locals). The extraction toolchain is in the
same directory: `dump2sym.pl` parses Watcom debug dumps,
`unwatcom.pl` is a Watcom-format helper, `mdark.bin` is an
artifact of the source binary.

Locally checked out at `.dso-online/` (shallow clone,
gitignored). License: AGPL-3.0. This is research-only mirroring;
we don't redistribute the upstream artifact. See
[CREDITS.md](../CREDITS.md) for the attribution chain.

## Format

The symbol file is one symbol per line, three space-separated
fields:

```
SymbolName  HexOffset  Kind
```

`Kind` is `f` (function) or `l` (label / data). Offsets are
into the v1.0 client's image; they do **not** map directly onto
DS2's `DSUN.EXE` offsets, since the two binaries were compiled
separately. Names are the cross-reference; offsets are useful
only inside the DSO client.

## How to use this

When `gpl-disasm` (v0.4.0+) or any future tool needs to name a
function or variable inside DS2's `DSUN.EXE`:

1. **Find a candidate symbol** in `.dso-online/tools/symbols.txt`
   by name pattern. Functions are `MixedCase` or `lowercase`;
   globals start with `g` (`gPartyLeader`, `gGplKiller`) and
   booleans with `b` (`bGplInitialized`).
2. **Verify the mapping holds** in DS2: open `DSUN.EXE` in
   radare2 or Ghidra, find the function by signature
   (string-cross-reference, call-graph shape, byte-pattern). If
   the candidate matches, record both names in the table below.
3. **Curate the entry** in the catalogue table. We grow this
   slowly and verifiably; no speculation.

## Symbol categories (function counts in `symbols.txt`)

A coarse picture of what the symbol file covers, by name prefix:

| Prefix    | Count | Coverage                                  |
|-----------|-------|-------------------------------------------|
| `Gff*`    | 27    | GFF container I/O (cross-check libgff)    |
| `Load*`   | 21    | Persistence: save/load orchestration      |
| `Gpl*`    | 21    | GPL bytecode lifecycle (`ExecuteGpl`, etc)|
| `Item*`   | 13    | Item handling                             |
| `Save*`   | 12    | Persistence: save-game orchestration      |
| `Spell*`  | 9     | Spellcasting                              |
| `Use*`    | 9     | Use / use-with action callbacks           |
| `Move*`   | 8     | Movement / region transitions             |
| `Psi*`    | 8     | Psionics                                  |
| `Char*`   | 8     | Character management                      |
| `Combat*` | 6     | Combat orchestration                      |
| `Region*` | 0     | (no `Region*` functions exist; region work lives under `Gpl*`/`Move*`) |

> **Corrected 2026-09-04.** The first published version of this
> table overcounted several rows (Save 24, Combat 11, Region 4,
> among others). The counts above are measured against the actual
> table (3,530 functions; `propose-exe-symbols.py --strings`
> reproduces them). The audit that caught this also noted the
> census here originally used 3-char prefixes, which fragments on
> Watcom's runtime prefixes; these rows use whole-word prefixes.

This is a partial slice; the symbol file covers UI, file I/O,
sprite rendering, animation, sound, networking (DSO-specific),
and engine plumbing as well.

## Highest-value GPL-related symbols

A first pass for the disassembler's symbol import. These are
the names we most want to verify map onto DS2's binary:

| DSO name             | What it likely does                                        |
|----------------------|------------------------------------------------------------|
| `ExecuteGpl`         | The GPL dispatch loop (per-byte handler invocation).       |
| `GPLLoadObjectData`  | Loads GPL chunks; counterpart of our `gff-edit` read path. |
| `GplShellInit`       | One-time initialiser; sets up the engine's GPL state.      |
| `GplGetInput`        | Input-bytecode interaction (matches `0x42` input string).  |
| `GplTileCheck`       | Tile trigger callbacks; matches our `0x68` opcode family.  |
| `GplTalkCheck`       | Talk-to trigger; matches our `0x6E` opcode.                |
| `GplDoorCheck`       | Door trigger; matches our `0x69` / `0x6B` opcode families. |
| `GplPickupCheck`     | Pickup-item trigger; matches our `0x6C` opcode.            |
| `GplAttackCheck`     | Attack trigger; matches our `0x65` opcode.                 |
| `GplLookCheck`       | Look trigger; matches our `0x66` opcode.                   |
| `GplUseCheck`        | Use trigger; matches our `0x6D` opcode.                    |
| `GplUseWithCheck`    | Use-with trigger; matches our `0x70` opcode.               |
| `GplChangeRegion`    | Region-transition hook; relevant to mines-elevator (DS2).  |
| `GplDropItem`        | Drop callback; matches our `0x2F` opcode.                  |
| `GplPlaceObject`     | Object placement; relevant to combat / region setup.       |
| `GplUpdatePsionics`  | Psionic state update; relevant to save-inspect v0.2.0.     |

These are *candidates*; each requires verification against DS2's
binary before being committed to a `syms.toml` symbol file. Do
not ship unverified mappings.

## The Decode* handler block (dispatch-order study, 2026-09-04)

`symbols.txt` names 115 `Decode*` functions spanning
`0x3aff2`..`0x3d914` (DSO v1.0 client offsets; addresses are facts
cited from the AGPL table, no code moves). This section records what
the study established, including one correction to the premise it
started from.

**Perfect name accounting with libgff.** 111 of the 115 handler
names match libgff's non-default opcode mnemonics under
case-insensitive PascalCase equivalence, plus one systematic rename:
DSO calls the 13 trigger handlers `*check` where libgff says
`*trigger` (`DecodeMoveTilecheck` / `gpl move tiletrigger`, the
`0x68`-`0x70` family, and `DecodeInloscheck` / `0x1b`, and kin). The
remaining four names: two are address-aliases (below), one is
`DecodeIfis` (below), and one is `DecodeDefault`. Adding those up,
**every one of the 114 non-default libgff bytes has exactly one DSO
handler name**, and DSO has no spare handler names left over.

**Alias facts (verified from shared addresses).** Two pairs of names
share one function address, confirming the source-level aliases:

| Address | Names | Consequence |
|---|---|---|
| `0x3bb55` | `DecodeJump`, `DecodeWend` | `0x64` (wend) is the same handler as `0x12` (jump). |
| `0x3c121` | `DecodeNumtoname`, `DecodeNametonum` | `0x1e`/`0x1f` are one handler in DSO. |

**`DecodeIfis` is the `0x27` semantics hint.** `0x3bc73` sits between
`DecodeCompare` (`0x3bc24`, our `0x17`) and `DecodeOrelse`
(`0x3bcb5`, our `0x29`), and is the only DSO name for the `0x27`
slot libgff calls `ifcompare`. The source-level name suggests the
condition form is "if (x) is (y)": a typed comparison, not a generic
branch. Treat as a hint until the DSUN handler is read.

**Correction: the block is NOT opcode-address-ordered.** The premise
this study started from said sorting the block by address gives
opcode order. It does not: the block opens `0x23, 0x4b, 0x15, 0x19`
before the `0x01`..`0x08` run, and only 56 of 108 adjacent pairs are
consecutive opcodes. The emission order is source order, locally
ordered within nine runs (the arithmetic families, the trigger
family, `0x76`..`0x7f`), globally not. Consequence, stated plainly:
**the unknown bytes cannot be pinned by elimination from this
block.** The 15 libgff-default bytes (`0x26`, `0x4a`, `0x4c`-`0x4e`,
`0x53`, `0x55`-`0x57`, `0x60`, `0x71`-`0x75`) have no DSO handler
names left to assign; the only unmapped DSO names are `DecodeIfis`
(`0x27`) and `DecodeDefault`. Pinning them needs the DSUN.EXE
dispatch table itself (a jump-table read against the
`ovr-map --syms` catalogue) or the DSO client binary's `ExecuteGpl`
jump table, which the symbol file alone cannot provide.

**Process note.** The matching above is reproducible from
`tools/gpl-disasm/scripts/import-dso-symbols.py`'s opcode table plus
the alias map in this section; the `--opcodes-proposed` output it
emits (100 rows) is consistent with these facts.

## Curated catalogue

Hand-verified cross-references. Coordinates are `ovr-map`
coordinates: resident functions by file offset, overlay functions by
(segment index, segment-local offset), matching
`tools/ovr-map/syms/<game>.toml`, which is the machine-readable copy
of these rows.

| DSO symbol | DS2 verified at | Notes |
|------------|-----------------|-------|
| `LoadGameFromDisk` | ovr18+0xa6c (file `0x7089c`) | Self-naming: the function pushes the error string "Failed Uncompress in Loadgamefromdisk". DS1 counterpart ovr21+0xdde. |
| `SaveGameToDisk` (slot path) | ovr11+0x8e5 (file `0x67ac5`) | Builds `SAVE%.2d.SAV` and enforces "Maximum of %ld save games!". DS1 counterpart ovr13+0x7cc. Family naming: the DSO table has several Save* functions, so the slot-path attribution is probable, not pinned to one name. |

**Reference-method note (verified 2026-09-04).** Strings are
referenced as bare 16-bit immediates relative to DGROUP, almost
always `push imm16`; the naive adjacent (off, seg) pair search this
file previously suggested finds nothing. DGROUP is read from the
entry point's `mov dx, imm16` (DS1 `0x4356`, DS2 `0x47e0`).
`tools/ovr-map/scripts/xref-string.py` automates all of it.

## Process for adding a row

1. Find the candidate in `.dso-online/tools/symbols.txt`.
2. Open DS2's `DSUN.EXE` in radare2: `r2 -A .games/ds2/DSUN.EXE`.
3. Locate the function by:
   - **String x-refs** (most reliable): the DSO symbol's purpose
     suggests a string it would emit; grep DSUN.EXE for that
     string and look at the function that references it.
   - **Call-graph shape**: how many callers, how many callees.
     The DSO symbol implies a shape; the DS2 candidate should
     match closely.
   - **Byte-pattern fingerprint**: the same source code
     compiled with the same Watcom version produces similar
     prologue/epilogue patterns.
4. Record the verified address (DS2 file offset) here, plus a
   one-line justification.
5. When we have ~20 verified rows, emit a `tools/gpl-disasm/syms.toml`
   for the disassembler to consume (v0.4.0+).

## Risks

- **Compiler reordering**: same source compiled twice may emit
  the same function at different addresses. We rely on names
  matching, not offsets.
- **DSO has multiplayer-specific code** that's absent from DS2
  (networking, packet handling). Roughly half the symbols are
  probably DSO-only.
- **Symbol names can mislead**: `GplUpdatePsionics` in DSO might
  do something subtly different in DS2 (e.g., per-player vs.
  per-party). Verify each.

## Related

- [`docs/upstream-projects.md`](upstream-projects.md) §3 covers
  the DarkSunOnline project in context.
- [`docs/gpl-bytecode.md`](gpl-bytecode.md) §5 says v0.4.0+
  is where this catalogue lands inside `gpl-disasm`.
- The DSO repo's
  [Client Disassembly wiki page](https://github.com/greg-kennedy/DarkSunOnline/wiki/Client-Disassembly)
  is the upstream's documentation of how the symbol file was
  produced and what it covers.
