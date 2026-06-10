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
| `Load*`   | 28    | Persistence: save/load orchestration      |
| `Gff*`    | 27    | GFF container I/O (cross-check libgff)    |
| `Save*`   | 24    | Persistence: save-game orchestration      |
| `Gpl*`    | 24    | GPL bytecode lifecycle (`ExecuteGpl`, etc)|
| `Item*`   | 15    | Item handling                             |
| `Use*`    | 11    | Use / use-with action callbacks           |
| `Move*`   | 11    | Movement / region transitions             |
| `Combat*` | 11    | Combat orchestration                      |
| `Psi*`    | 10    | Psionics                                  |
| `Char*`   | 10    | Character management                      |
| `Spell*`  | 9     | Spellcasting                              |
| `Region*` | 4     | Region loader                             |

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

## Curated catalogue

Hand-verified cross-references. Empty for now; grows as we
verify each candidate against `DSUN.EXE`.

| DSO symbol | DS2 verified at | Notes |
|------------|-----------------|-------|
| _(none yet)_ | | |

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
