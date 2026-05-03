# GPL Bytecode

GPL — "Game Programming Language" — is the engine's embedded
scripting language. Quest logic, dialogue trees, NPC AI hooks,
event triggers, item-use callbacks, and most of what makes the
game "the game" are expressed in compiled GPL bytecode.

For darkfix, GPL is the **primary editing surface**. The bulk of
the SSI 1.02 fix list and the bulk of the surviving bugs are
GPL-script bugs — flag/state bugs, missing branches, off-by-one
guards. Fix one GPL bug → fix one quest. Fix every GPL bug → fix
the game.

## 1. Where GPL lives

In the GFF container (see [`file-formats.md`](file-formats.md)):

| FOURCC | Purpose                                   |
|--------|-------------------------------------------|
| `GPL ` | Compiled GPL bytecode                     |
| `MAS ` | Compiled GPL master script                |
| `GPLI` | GPL "I" data (incompletely documented)    |
| `GPLX` | GPL index file                            |

Both DS1 and DS2 ship a single `GPLDATA.GFF` containing all of
these — DS1's is 1.4 MB, DS2's is 2.2 MB. Region-specific scripts
may also live inside the per-region `RGN*.GFF` files; that needs
verification by chunk-counting once we have a reader running.

## 2. Where GPL came from

The Crimson Sands postmortem on Gamasutra/Game Developer is the
only first-person account that names the language. The team
adapting WotR to a multiplayer client describes "GPL" as the
in-engine designer-facing scripting language used to author
quests. No public spec. No public compiler. No published opcode
table.

## 3. What we know publicly

- **Bytecode**: compact byte-stream with embedded jump targets;
  not register-based as far as anyone has documented.
- **Function-shaped**: master scripts (`MAS `) call into other
  GPL chunks by ID; an index chunk (`GPLX`) maps names → IDs.
- **The interpreter is in `DSUN.EXE`**: there is no separate VM
  binary. The dispatch loop is somewhere inside the executable;
  identifying it is part of the work.

The most useful prior art:

- **`soloscuro-archive`'s `src/gpl/`** — the closest thing to a
  partial GPL VM that exists publicly. Implements some opcodes;
  many remain stubs. Worth reading before disassembly work.
- **`libgff`'s `gff_chunk_gpl*`** — produces raw chunk bytes plus
  some structural metadata, but does not interpret.
- **`the-dark-lens`** — DSO documentation; mentions GPL in
  passing.
- **`greg-kennedy/DarkSunOnline` wiki** — the highest-value
  cross-reference: the DSO v1.0 client shipped with debug symbols
  that include GPL function names. DSO inherited the WotR
  codebase, so those names map (with care) onto the same
  functions in DS2's `DSUN.EXE`.

## 4. The plan: disassemble first, interpret never

darkfix does **not** need a full GPL VM. We never execute the
bytecode in our own process. We only need to:

1. **Disassemble** GPL chunks into mnemonic form so a human can
   read what a quest script does.
2. **Locate** the buggy region (the off-by-one, the wrong jump
   target, the missing flag-set).
3. **Patch** specific bytes in the chunk to fix it.
4. **Repackage** the patched chunk back into the GFF.

The original engine in DOSBox executes the patched bytecode. We
piggyback on its interpreter rather than rewriting it.

This is a critical scope decision: a real GPL VM is multi-year
work. A disassembler good enough to author surgical patches is
a few weeks.

## 5. `gpl-disasm` design

Located at `tools/gpl-disasm/` (TBD). Python 3 first; can be
ported to Rust if we ever spin up the engine project.

### Inputs

- A GFF file (we extract `GPL ` / `MAS ` chunks ourselves rather
  than going through `gff-tool`, so we can iterate quickly).
- Optional: a symbol file (`syms.toml`) mapping known function
  IDs to names — bootstrapped from greg-kennedy's DSO debug
  symbols and grown by hand.

### Outputs

- Per-chunk text dump with:
  - Header comment: chunk type, ID, size, optional symbol name.
  - Annotated bytes: address, hex, mnemonic, operands.
  - Cross-references: every jump target labeled.
  - Strings: any embedded ASCII auto-detected and shown.
  - Unknown opcodes: emitted as `db 0xNN` with a TODO marker.
- An overall summary: counts of opcodes, biggest functions,
  longest-running chunks.

### Bootstrap order

1. Parse the chunk wrapper, find the entry-point byte.
2. Linear sweep: assume opcodes are sequential, decode what we
   know, emit `db` for the rest.
3. After enough opcodes are known, switch to a recursive-descent
   pass that follows jumps and produces basic blocks.
4. After basic blocks work, add symbolic labels.

### Opcode discovery loop

We discover opcodes by:

- Reading `soloscuro-archive`'s partial parser and hand-translating.
- Reading `DSUN.EXE` in radare2 to find the dispatch table — once
  located, the table itself enumerates the opcodes.
- Cross-referencing with the DSO debug-symbol function names
  (e.g., a function called `gpl_op_set_flag` is highly suggestive).
- For each unknown opcode, finding a chunk that uses it, running
  the original game in DOSBox to that point, and observing
  state changes to infer the opcode's effect.

## 6. Authoring a GPL fix

End-to-end, once `gpl-disasm` exists:

1. Reproduce the bug in DOSBox (saved-game library helps).
2. Run `gpl-disasm extracted/dsN/GPLDATA.GFF > /tmp/dump.gpl.s`.
3. Locate the chunk responsible — usually by the dialog
   text the buggy NPC speaks (search for the string in the
   disassembly).
4. Identify the bug (missing branch, wrong flag, etc.).
5. Compute the byte-level edit required to fix it.
6. Patch via the per-fix script (Python — opens the GFF, finds
   the chunk by (type, id), edits bytes at offset N, writes back
   via `gff-tool` or a direct GFF writer once we have one).
7. Verify: re-extract, re-run `gpl-disasm`, confirm the disassembly
   reads correctly. Run the bug repro — bug should not fire.

## 7. The reassembler ("`gpl-asm`") — not in v1

A reassembler that takes our disassembly format back to bytecode
is desirable but not required for v1. v1 patches edit specific
bytes in a chunk; the disassembly is read-only. Reassembly only
becomes necessary if a fix needs to insert or delete bytes
(changing chunk size, requiring offset shifts).

If a fix requires shifting offsets, we either:

- Find a no-op padding region inside the chunk to absorb the
  delta, or
- Defer the fix until `gpl-asm` exists.

## 8. Risks

- **Some bugs may be unfixable in GPL alone.** The combat AI
  randomly-crashing-in-combat bug is likely a `DSUN.EXE` bug, not
  a GPL bug. We document, we move on.
- **Some GPL chunks may be truly opaque** until we know more
  opcodes. Those bugs wait for the disassembler to mature.
- **WotC IP risk.** Disassembly of code is generally treated as
  fair use for interoperability under most jurisdictions, but we
  publish disassembly carefully. The patches themselves only ship
  the *byte-level edits*, not the full disassembly.

## 9. Resources to mine

- soloscuro-archive — https://github.com/dsoageofheroes/soloscuro-archive
- libgff — https://github.com/dsoageofheroes/libgff
- the-dark-lens — https://github.com/dsoageofheroes/the-dark-lens
- DarkSunOnline — https://github.com/greg-kennedy/DarkSunOnline
- Crimson Sands postmortem — https://www.gamedeveloper.com/design/postmortem-ssi-s-i-dark-sun-online-crimson-sands-i-
- dsoageofheroes Discord — https://discord.gg/W942xHN72S

When a GPL question stalls us, ask in that Discord before
spending days on it.
