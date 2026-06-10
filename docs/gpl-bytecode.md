# GPL Bytecode

*Reference. Read [`research.md`](research.md) first if you're new
to the engine. This page explains the language and its encoding;
the per-opcode table lives in [`gpl-opcodes.md`](gpl-opcodes.md);
the tools that operate on all of this are
[`gpl-disasm`](../tools/gpl-disasm/) and
[`gpl-asm`](../tools/gpl-asm/).*

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

Lives at `tools/gpl-disasm/` (Rust crate; workspace member).
Depends on `gff-edit` for GFF I/O. Per [`../spec.md`](../spec.md)
§7a, heavy-lifting tools are Rust; `gpl-disasm` is the
keystone tool that everything else in this corner relies on.

### Inputs

- A GFF file. We use the `gff-edit` library to find `GPL ` /
  `MAS ` chunks by `(kind, id)` and borrow their bytes.
- Optional in later versions: a symbol file (`syms.toml`)
  mapping known function ids to names, bootstrapped from
  greg-kennedy's DSO debug symbols.

### Outputs

- Per-chunk text dump with:
  - One row per instruction (v0.2.0+).
  - Each row: offset, opcode byte, mnemonic, formatted
    parameters (decoded values, variable references, infix
    operators, parens).
  - Cross-references: every jump target labeled (v0.3.0+).
  - Strings: embedded ASCII runs auto-detected and shown
    inline as a comment.
  - Unknown opcodes: `db 0xNN ; ??`.
- JSON output mode (v0.2.0+): structured `DisasmResult` with
  alignment metadata and full Instruction / Expression tree.

### Versioning

**v0.1.0 — byte-annotation pass.** Each byte was treated as a
potential opcode. We looked up its mnemonic in the 129-entry
catalogue sourced from libgff's `gpl_commands` table (sourced
under MIT with attribution). v0.1.0 did *not* decode parameter
bytes; every byte got its own line. Useful for grepping
mnemonics and strings, but instruction boundaries were not
aligned with the real program flow.

**v0.2.0 — parameter decoding (current).** Port of libgff's
`gpl_read_number` (the variable-length expression decoder), the
`gpl_read_simple_num_var` helper, and the 7-bit packed-string
decoder (`read_compressed`, from soloscuro-archive). Output is
now **one row per instruction**, with parameters formatted in an
infix syntax (`GFLAG[12] == 1i8`, `"Free! Finally free!..."`,
`NAME(-22)`). Structural handlers (`gpl_load_variable`,
`gpl_search`, `gpl_menu`, `gpl_log`) decode their custom layouts
too. Adds a `--json` output mode for tools downstream
(`dialog-extract` v0.2.0 will consume it).

**v0.2.1** closes the deferred cases. Nested `GPL_RETVAL | 0x80`
recursively dispatches the inner opcode's parameter shape (when
the opcode is in libgff's safe-subset of 21 opcodes), bounded
at four levels of nesting. `GPL_COMPLEX_*` and the `0xb3`
"passive flag" special case decode via a port of
`gpl_access_complex` (word obj_name + byte depth + depth bytes
elements). `gpl_setrecord` (0x40) is a first-class
`access_complex + read_number`. `gpl_load_variable` (0x16)'s
complex-write path now decodes too. Corpus alignment: **100% on
all 600 DS1+DS2 GPL/MAS chunks**.

**v0.3.0 — control flow.** Every disassembled chunk
carries a [`Cfg`] of basic blocks, entry points, and
labeled successors. **v0.3.1 (current)** corrects the
`gpl else` (0x3F) edge model: branch targets that land on
an else opcode are redirected past it to the else-body
start, with a new `target_aliases` map preserving the
raw-target-to-label resolution for rendering. See the
v0.3.1 patchnote entry for the rationale and corpus impact. The default text listing renders
`gpl if label_0x0020` instead of `gpl if 32`, with `label_*:` /
`entry_*:` lines preceding each block leader. New CLI flags:
`--entries`, `--cfg <path>`, `--no-labels`. JSON output gains
an additive `cfg` field. Verified on the full DS1+DS2 corpus:
**600 / 600 chunks build a CFG where every successor offset
(71,403 edges) resolves to a known instruction boundary, with
0 computed-target edges and 1,384 cross-chunk `global sub`
call sites recorded for v0.4.0+ inter-chunk analysis.** The
underlying jump semantics for the eight branch opcodes were
verified in a pre-implementation spike; the findings are in
§5a below.

**v0.4.0+ — symbol import** (DSO debug symbols), opcode
discovery via `opcode-fuzz` (Phase 5), MAS/GPLX cross-
reference, inter-chunk CFG following `global sub` edges.

### §5a — Branch opcode semantics (v0.3.0 spike)

Before committing to a recursive-descent walker, we verified
what the first parameter of each branch opcode actually means.
The question: is it an absolute byte offset into the chunk, a
relative offset, a label id, or something else?

**Sources consulted.**

1. `.dsoageofheroes/soloscuro-archive/src/gpl/gpl-lua.c` (MIT).
   The closest public runtime: paulofthewest's Lua emitter.
   It does not execute jumps directly (it lowers GPL to Lua
   control flow) but its bookkeeping reveals the unit:
   - `print_label()` (line 265) computes `label = data_ptr -
     gpl_lua_start_ptr`, i.e. **bytes since chunk start**.
   - `lua_goto(str)` (line 218) parses the stringified
     parameter into an integer and uses it as a label index
     in the same unit.
   - `gpl_lua_if` (1111) and `gpl_lua_else` (1119) both
     consume one parameter via `gpl_lua_get_parameters(1)`
     and comment "in the original it probably was the address
     to jump to if the if was not taken."
   - `gpl_lua_local_sub` (1528) emits `if func<N>() then
     return true end`, treating the parameter as a function
     identifier (effectively the function's start offset).
   - `gpl_lua_global_sub` (1534) consumes two parameters and
     comments `// Jump to addr %s in file %s`: the first is
     the address, the second is the GPL file id.
   - `gpl_lua_jump` (1524) is `lua_exit("jump not
     implemented!\n")` — paulofthewest never lowered the
     unconditional jump opcode. Not a blocker; the consistent
     unit ("bytes since chunk start") still applies.

2. `.dsoageofheroes/libgff/src/gpl/parse.c` (MIT). libgff is a
   pure parser, not a runtime, but it confirms each branch
   opcode's parameter count:
   - `gpl_jump` (0x12) → 1 param.
   - `gpl_call_local` (0x13, "local sub") → 1 param.
   - `gpl_call_global` (0x14, "global sub") → 2 params; the
     printf at line 1320 literally labels them `(ADDR, FILE)`.
   - `gpl_local_ret` (0x15) → 0 params.
   - `gpl_if` (0x3E) → 1 param.
   - `gpl_else` (0x3F) → 1 param.
   - `gpl_while` (0x63) → 1 param.
   - `gpl_wend` (0x64) → 1 param.

   Matches our `PARAM_COUNTS` table in
   `tools/gpl-disasm/src/lib.rs`.

3. **Hand-trace of DS1 GPLDATA.GFF GPL chunk 9** (554 bytes;
   the smallest GPL chunk in DS1). Eight branch instructions:

   | Branch at offset | Param value | Target offset | Lands on |
   |------------------|-------------|---------------|----------|
   | `if` @ 0x000E    | 32  (0x020) | 0x0020        | `endif` |
   | `if` @ 0x0031    | 98  (0x062) | 0x0062        | `endif` |
   | `if` @ 0x003F    | 80  (0x050) | 0x0050        | `else`  |
   | `else` @ 0x0050  | 97  (0x061) | 0x0061        | `endif` |
   | `if` @ 0x0069    | 109 (0x06D) | 0x006D        | `endif` |
   | `if` @ 0x0128    | 300 (0x12C) | 0x012C        | `endif` |
   | `if` @ 0x013B    | 324 (0x144) | 0x0144        | `endif` |
   | `if` @ 0x0156    | 478 (0x1DE) | 0x01DE        | `endif` |

   8 / 8 land exactly on a sibling instruction boundary; every
   `if` targets its matching `else` or `endif`, every `else`
   targets its matching `endif`. No off-by-one, no relative
   encoding, no extra bias byte.

4. **Cross-trace on DS1 GPLDATA.GFF GPL chunk 3** for the
   `local sub` path. Two distinct call sites both target two
   real function entry points:

   | Call at offset    | Param value  | Target offset | Lands on |
   |-------------------|--------------|---------------|----------|
   | `local sub` @ 0x0171 | 1 (0x001) | 0x0001        | `load accum` (chunk's first real instruction; `local ret` at 0x0043) |
   | `local sub` @ 0x06F0 | 1984 (0x7C0) | 0x07C0    | `clearpic` (`local ret` at 0x084E) |
   | `local sub` @ 0x0751 | 1984 (0x7C0) | 0x07C0    | same target as above (the same function called twice) |

   Confirms the parameter is an absolute byte offset of a
   function entry within the same chunk, terminated by
   `local ret` (0x15).

**Conclusion.** The first parameter of every branch opcode is
the **absolute byte offset of the target instruction within
the same GPL chunk**, parsed via the standard
`gpl_read_number` expression decoder. Per-opcode semantics:

| Opcode | First param meaning |
|--------|---------------------|
| `gpl jump` (0x12) | unconditional target |
| `gpl local sub` (0x13) | function entry; matching `local ret` (0x15) returns |
| `gpl global sub` (0x14) | function entry; second param is the GPL file id (cross-chunk) |
| `gpl local ret` (0x15) | (no params; returns from local sub) |
| `gpl global ret` (0x19) | (no params; returns from global sub) |
| `gpl if` (0x3E) | fallthrough target when accum is false (the matching `else` or `endif`) |
| `gpl else` (0x3F) | fallthrough target when reaching `else` from the true branch (matching `endif`) |
| `gpl while` (0x63) | fallthrough target when accum is false (past the matching `wend`) |
| `gpl wend` (0x64) | backward target: matching `while` |

**Implication for v0.3.0.** The recursive-descent walker is
unblocked. Entry points = chunk start + every observed `local
sub` / `global sub` target inside the chunk. Successors at a
branch instruction = the target offset (in the first param)
plus the fallthrough offset (next instruction) for conditional
branches, target-only for unconditional `jump` and `wend`.
Backward edges via `wend` are expected and not an error.

**Open follow-ups (not blocking v0.3.0).**

- Whether `chunk[0]` is always `gpl global ret` (0x19) as a
  one-byte epilogue placeholder, and whether the *real* entry
  is `chunk[1]`. Both chunks in this spike began that way. The
  v0.3.0 walker should treat both offsets 0 and 1 as candidate
  entries until a wider corpus confirms.
- `gpl global sub` (0x14) crosses chunks; v0.3.0 doesn't need
  to follow those edges (the second param's GPL file id is
  enough to *list* the call). Inter-chunk CFG is v0.4.0+ work.
- `gpl ifcompare` (0x27) **verified** in a follow-up
  hand-trace (DS1 GPLDATA GPL chunk 199): 2 parameters where
  param[0] is the comparison value (the case label) and
  param[1] is the jump target taken **on mismatch**. The
  pattern emits a fall-through switch:
  ```
  0251  27  gpl ifcompare  2i8, 609   ; if accum != 2: jump 0x261
  0256  ...  case-2 body
  0261  27  gpl ifcompare  3i8, 625   ; if accum != 3: jump 0x271
  ```
  All five chained mismatch-targets land on the next
  ifcompare's offset; the chain terminates at `gpl cmpend`
  (0x61). CFG model: 2 successors — fallthrough (match) +
  param[1] (mismatch). Important: the target is **param[1]**,
  not param[0], unlike the single-param branches above.

### Opcode discovery loop

We grow the catalogue by:

- Reading libgff's `gpl_commands` table (the seed) and the
  per-handler functions in `src/gpl/parse.c`.
- Cross-checking against soloscuro-archive's `src/gpl/`.
- Cross-referencing with the DSO v1.0 debug-symbol function
  names from greg-kennedy's DSO wiki (e.g. a name like
  `gpl_op_set_flag` is highly suggestive).
- For each unknown opcode, finding a chunk that uses it,
  running the original game in DOSBox to that point, and
  observing state changes to infer the opcode's effect.
  (This is `opcode-fuzz`; see Phase 5.)

## 6. Authoring a GPL fix

End-to-end, once `gpl-disasm` exists:

1. Reproduce the bug in DOSBox (saved-game library helps).
2. Run `gpl-disasm .games/dsN/GPLDATA.GFF > /tmp/dump.gpl.s`.
3. Locate the chunk responsible — usually by the dialog
   text the buggy NPC speaks (search for the string in the
   disassembly).
4. Identify the bug (missing branch, wrong flag, etc.).
5. Compute the byte-level edit required to fix it.
6. Patch via the per-fix script (Python; opens the GFF, finds
   the chunk by `(kind, id)`, edits bytes at offset N, writes
   back. Today the script shells out to `gff-cat replace` from
   `gff-edit` v0.3.0+; a Python binding to `gff_edit` is
   future work).
7. Verify: re-extract, re-run `gpl-disasm`, confirm the
   disassembly reads correctly. Run the bug repro; bug should
   not fire.

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
