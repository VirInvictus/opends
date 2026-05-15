# GPL Opcode Catalogue

The opcode table embedded in
[`tools/gpl-disasm`](../tools/gpl-disasm/). Each row maps a byte
value (`0x00`..`0x80`) to libgff's mnemonic for that opcode and
to its parameter shape. Sourced verbatim from libgff's
`gpl_commands` table at `dsoageofheroes/libgff` `src/gpl/parse.c`
lines 1554-1684 (MIT-licensed). Parameter counts derived from
the per-handler bodies in the same file; see
[`docs/gpl-bytecode.md`](gpl-bytecode.md) for the encoding rules.

**Coverage status**:

- 129 entries cover bytes `0x00`..`0x80`. Bytes `0x81`..`0xFF`
  are not in libgff's handler table; `gpl-disasm` emits them as
  `db 0xNN ; ??` with one row per byte (no parameter decoding).
- Many entries are libgff's "gpl default" or "gpl unknown" stub
  names, meaning the engine reserves the byte but libgff's
  handler is a placeholder. We list those as the libgff name for
  honesty.
- **Params column** indicates how the opcode's bytes are consumed
  after the opcode byte:
  - **N** (integer): N expressions read via `gpl_read_number`.
  - **0**: no parameters.
  - **log**: one packed-string payload (no expression read).
  - **var**: `gpl_load_variable`: one expression (load_accum) +
    a datatype byte + 1 or 2 varnum bytes, or a deferred complex
    write.
  - **menu**: one expression (menu name) + a loop of three
    expressions per entry terminated by `0x4A`.
  - **search**: one expression + two bytes + a do-while loop
    reading optional `0x53` (SEARCH_QUAL), field byte, type byte,
    and a conditional expression when type is in `0x04..=0x06`.
  - **custom**: libgff handler is `gpl_unknown` or has a custom
    shape we have not yet modelled (`gpl_setrecord`). The
    disassembler consumes only the opcode byte and marks the
    instruction `best_effort`; later instructions may misalign.

## Table

| Byte | Mnemonic                | Params | Notes |
|------|-------------------------|--------|-------|
| 0x00 | gpl zero                | 0      |       |
| 0x01 | gpl long divide equal   | 2      |       |
| 0x02 | gpl byte dec            | 1      |       |
| 0x03 | gpl word dec            | 1      |       |
| 0x04 | gpl long dec            | 1      |       |
| 0x05 | gpl byte inc            | 1      |       |
| 0x06 | gpl word inc            | 1      |       |
| 0x07 | gpl long inc            | 1      |       |
| 0x08 | gpl hunt                | 1      |       |
| 0x09 | gpl getxy               | 1      |       |
| 0x0A | gpl string copy         | 2      |       |
| 0x0B | gpl p damage            | 2      |       |
| 0x0C | gpl changemoney         | 1      |       |
| 0x0D | gpl setvar              | custom | libgff handler is `gpl_unknown` |
| 0x0E | gpl toggle accum        | 0      |       |
| 0x0F | gpl getstatus           | 1      | safe in RETVAL context |
| 0x10 | gpl getlos              | 3      | safe in RETVAL context |
| 0x11 | gpl long times equal    | 2      |       |
| 0x12 | gpl jump                | 1      | control flow |
| 0x13 | gpl local sub           | 1      | control flow |
| 0x14 | gpl global sub          | 2      | control flow |
| 0x15 | gpl local ret           | 0      | control flow |
| 0x16 | gpl load variable       | var    |       |
| 0x17 | gpl compare             | 1      |       |
| 0x18 | gpl load accum          | 1      |       |
| 0x19 | gpl global ret          | 0      | control flow |
| 0x1A | gpl nextto              | 2      | "global return?" per libgff |
| 0x1B | gpl inlostrigger        | 4      |       |
| 0x1C | gpl notinlostrigger     | 4      |       |
| 0x1D | gpl clear los           | 1      |       |
| 0x1E | gpl nametonum           | 1      | safe in RETVAL context |
| 0x1F | gpl numtoname           | 1      | safe in RETVAL context |
| 0x20 | gpl bitsnoop            | 2      | safe in RETVAL context |
| 0x21 | gpl award               | 2      |       |
| 0x22 | gpl request             | 4      | safe in RETVAL context |
| 0x23 | gpl source trace        | custom | libgff handler is `gpl_unknown` |
| 0x24 | gpl shop                | 1      |       |
| 0x25 | gpl clone               | 6      | safe in RETVAL context |
| 0x26 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x27 | gpl ifcompare           | 2      |       |
| 0x28 | gpl trace var           | custom | libgff handler is `gpl_unknown` |
| 0x29 | gpl orelse              | 1      |       |
| 0x2A | gpl clearpic            | 0      |       |
| 0x2B | gpl continue            | 0      |       |
| 0x2C | gpl log                 | log    |       |
| 0x2D | gpl damage              | 2      |       |
| 0x2E | gpl source line num     | custom | libgff handler is `gpl_unknown` |
| 0x2F | gpl drop                | 3      | safe in RETVAL context |
| 0x30 | gpl passtime            | 1      |       |
| 0x31 | gpl exit gpl            | 0      | control flow |
| 0x32 | gpl fetch               | 2      |       |
| 0x33 | gpl search              | search | safe in RETVAL context |
| 0x34 | gpl getparty            | 1      | safe in RETVAL context |
| 0x35 | gpl fight               | 0      |       |
| 0x36 | gpl flee                | 1      |       |
| 0x37 | gpl follow              | 2      |       |
| 0x38 | gpl getyn               | 0      | safe in RETVAL context (yes/no prompt) |
| 0x39 | gpl give                | 4      | safe in RETVAL context |
| 0x3A | gpl go                  | 2      |       |
| 0x3B | gpl input bignum        | custom | libgff handler is `gpl_unknown` |
| 0x3C | gpl goxy                | 3      |       |
| 0x3D | gpl readorders          | 1      | safe in RETVAL context |
| 0x3E | gpl if                  | 1      | control flow |
| 0x3F | gpl else                | 1      | control flow |
| 0x40 | gpl setrecord           | custom | uses `access_complex`; deferred |
| 0x41 | gpl setother            | 1      | safe in RETVAL context |
| 0x42 | gpl input string        | 1      |       |
| 0x43 | gpl input number        | 1      |       |
| 0x44 | gpl input money         | 1      |       |
| 0x45 | gpl joinparty           | custom | libgff handler is `gpl_unknown` |
| 0x46 | gpl leaveparty          | custom | libgff handler is `gpl_unknown` |
| 0x47 | gpl lockdoor            | custom | libgff handler is `gpl_unknown` |
| 0x48 | gpl menu                | menu   |       |
| 0x49 | gpl setthing            | 2      | safe in RETVAL context |
| 0x4A | gpl default             | custom | also terminates the menu loop |
| 0x4B | gpl local sub trace     | custom | libgff handler is `gpl_unknown` |
| 0x4C | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x4D | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x4E | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x4F | gpl print string        | 2      |       |
| 0x50 | gpl print number        | 2      |       |
| 0x51 | gpl printnl             | 0      | libgff's `get_params(2)` call is commented out |
| 0x52 | gpl rand                | 1      | safe in RETVAL context |
| 0x53 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x54 | gpl showpic             | 1      |       |
| 0x55 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x56 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x57 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x58 | gpl skillroll           | custom | libgff handler is `gpl_unknown` |
| 0x59 | gpl statroll            | 3      | safe in RETVAL context |
| 0x5A | gpl string compare      | 2      | safe in RETVAL context |
| 0x5B | gpl match string        | custom | libgff handler is `gpl_unknown` |
| 0x5C | gpl take                | 4      | safe in RETVAL context |
| 0x5D | gpl sound               | 1      |       |
| 0x5E | gpl tport               | 5      |       |
| 0x5F | gpl music               | 1      | libgff `gpl_unknown`; soloscuro-archive reads 1 expression |
| 0x60 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x61 | gpl cmpend              | 0      |       |
| 0x62 | gpl wait                | 1      |       |
| 0x63 | gpl while               | 1      | control flow |
| 0x64 | gpl wend                | 1      | control flow |
| 0x65 | gpl attacktrigger       | 3      |       |
| 0x66 | gpl looktrigger         | 3      |       |
| 0x67 | gpl endif               | 0      | control flow |
| 0x68 | gpl move tiletrigger    | 5      |       |
| 0x69 | gpl door tiletrigger    | 5      |       |
| 0x6A | gpl move boxtrigger     | 7      |       |
| 0x6B | gpl door boxtrigger     | 7      |       |
| 0x6C | gpl pickup itemtrigger  | 3      |       |
| 0x6D | gpl usetrigger          | 3      |       |
| 0x6E | gpl talktotrigger       | 3      |       |
| 0x6F | gpl noorderstrigger     | 3      |       |
| 0x70 | gpl usewithtrigger      | 4      |       |
| 0x71 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x72 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x73 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x74 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x75 | gpl default             | custom | libgff handler is `gpl_unknown` |
| 0x76 | gpl byte plus equal     | 2      |       |
| 0x77 | gpl byte minus equal    | 2      |       |
| 0x78 | gpl byte times equal    | 2      |       |
| 0x79 | gpl byte divide equal   | 2      |       |
| 0x7A | gpl word plus equal     | 2      |       |
| 0x7B | gpl word minus equal    | 2      |       |
| 0x7C | gpl word times equal    | 2      |       |
| 0x7D | gpl word divide equal   | 2      |       |
| 0x7E | gpl long plus equal     | 2      |       |
| 0x7F | gpl long minus equal    | 2      |       |
| 0x80 | gpl get range           | 2      | safe in RETVAL context |

## Sources

- libgff `src/gpl/parse.c` `gpl_commands` table (lines
  1554-1684): the per-byte handler + name list. Primary
  source.
- libgff `src/gpl/parse.c` `gpl_retval` switch (lines
  1791-1826): the "safe in RETVAL context" annotations.
- libgff `src/gpl/parse.c` per-handler bodies (lines 660-1552):
  the parameter-count source. Each `gpl_get_parameters(gpl, N)`
  contributes `N`; direct `gpl_read_number(gpl)` and
  `load_accum(gpl)` calls each contribute 1. Wrappers
  (`gpl_template`, `gpl_type_op_equal`) expand inline.
- soloscuro-archive `src/gpl/gpl-lua.c`: secondary cross-
  reference. Fills in the one libgff-`gpl_unknown` handler with
  a known parameter shape (`0x5F music` reads 1 expression).

## Discovery loop

We grow this table by:

1. Reading the per-handler functions in libgff `parse.c` to
   pin down parameter shape per opcode (the `Params` column
   above).
2. Cross-referencing with the DSO v1.0 client debug-symbol
   function names from greg-kennedy's `DarkSunOnline` wiki:
   names like `gpl_op_set_flag` confirm or refine the libgff
   mnemonic.
3. Running `opcode-fuzz` (Phase 5): swap a chunk to a one-byte
   probe, observe engine state delta in DOSBox.
