# GPL Opcode Catalogue

The opcode table embedded in
[`tools/gpl-disasm`](../tools/gpl-disasm/) v0.1.0. Each row maps
a byte value (`0x00`..`0x80`) to libgff's mnemonic for that
opcode. Sourced verbatim from libgff's `gpl_commands` table at
`dsoageofheroes/libgff` `src/gpl/parse.c` lines 1554-1684, MIT-
licensed.

**Coverage status**:

- 129 entries cover bytes `0x00`..`0x80`. Bytes `0x81`..`0xFF`
  are emitted by `gpl-disasm` as `db 0xNN ; ??`.
- Many entries are libgff's "gpl default" or "gpl unknown" stub
  names, meaning the engine reserves the byte but libgff's
  handler is a placeholder. We list those as the libgff name for
  honesty.
- **Parameter encoding is not yet documented per opcode.**
  v0.1.0 of `gpl-disasm` ignores parameters; every byte gets one
  annotation row. v0.2.0 will port libgff's `gpl_read_number` /
  `gpl_get_parameters` and document each opcode's parameter
  shape here.

## Table

| Byte | Mnemonic                | Notes |
|------|-------------------------|-------|
| 0x00 | gpl zero                |       |
| 0x01 | gpl long divide equal   |       |
| 0x02 | gpl byte dec            |       |
| 0x03 | gpl word dec            |       |
| 0x04 | gpl long dec            |       |
| 0x05 | gpl byte inc            |       |
| 0x06 | gpl word inc            |       |
| 0x07 | gpl long inc            |       |
| 0x08 | gpl hunt                |       |
| 0x09 | gpl getxy               |       |
| 0x0A | gpl string copy         |       |
| 0x0B | gpl p damage            |       |
| 0x0C | gpl changemoney         |       |
| 0x0D | gpl setvar              | libgff handler is `gpl_unknown` |
| 0x0E | gpl toggle accum        |       |
| 0x0F | gpl getstatus           | safe in RETVAL context |
| 0x10 | gpl getlos              | safe in RETVAL context |
| 0x11 | gpl long times equal    |       |
| 0x12 | gpl jump                | control flow |
| 0x13 | gpl local sub           | control flow |
| 0x14 | gpl global sub          | control flow |
| 0x15 | gpl local ret           | control flow |
| 0x16 | gpl load variable       |       |
| 0x17 | gpl compare             |       |
| 0x18 | gpl load accum          |       |
| 0x19 | gpl global ret          | control flow |
| 0x1A | gpl nextto              | "global return?" per libgff |
| 0x1B | gpl inlostrigger        |       |
| 0x1C | gpl notinlostrigger     |       |
| 0x1D | gpl clear los           |       |
| 0x1E | gpl nametonum           | safe in RETVAL context |
| 0x1F | gpl numtoname           | safe in RETVAL context |
| 0x20 | gpl bitsnoop            | safe in RETVAL context |
| 0x21 | gpl award               |       |
| 0x22 | gpl request             | safe in RETVAL context |
| 0x23 | gpl source trace        | libgff handler is `gpl_unknown` |
| 0x24 | gpl shop                |       |
| 0x25 | gpl clone               | safe in RETVAL context |
| 0x26 | gpl default             | libgff handler is `gpl_unknown` |
| 0x27 | gpl ifcompare           |       |
| 0x28 | gpl trace var           | libgff handler is `gpl_unknown` |
| 0x29 | gpl orelse              |       |
| 0x2A | gpl clearpic            |       |
| 0x2B | gpl continue            |       |
| 0x2C | gpl log                 |       |
| 0x2D | gpl damage              |       |
| 0x2E | gpl source line num     | libgff handler is `gpl_unknown` |
| 0x2F | gpl drop                | safe in RETVAL context |
| 0x30 | gpl passtime            |       |
| 0x31 | gpl exit gpl            | control flow |
| 0x32 | gpl fetch               |       |
| 0x33 | gpl search              | safe in RETVAL context |
| 0x34 | gpl getparty            | safe in RETVAL context |
| 0x35 | gpl fight               |       |
| 0x36 | gpl flee                |       |
| 0x37 | gpl follow              |       |
| 0x38 | gpl getyn               | safe in RETVAL context (yes/no prompt) |
| 0x39 | gpl give                | safe in RETVAL context |
| 0x3A | gpl go                  |       |
| 0x3B | gpl input bignum        | libgff handler is `gpl_unknown` |
| 0x3C | gpl goxy                |       |
| 0x3D | gpl readorders          | safe in RETVAL context |
| 0x3E | gpl if                  | control flow |
| 0x3F | gpl else                | control flow |
| 0x40 | gpl setrecord           |       |
| 0x41 | gpl setother            | safe in RETVAL context |
| 0x42 | gpl input string        |       |
| 0x43 | gpl input number        |       |
| 0x44 | gpl input money         |       |
| 0x45 | gpl joinparty           | libgff handler is `gpl_unknown` |
| 0x46 | gpl leaveparty          | libgff handler is `gpl_unknown` |
| 0x47 | gpl lockdoor            | libgff handler is `gpl_unknown` |
| 0x48 | gpl menu                |       |
| 0x49 | gpl setthing            | safe in RETVAL context |
| 0x4A | gpl default             | libgff handler is `gpl_unknown` |
| 0x4B | gpl local sub trace     | libgff handler is `gpl_unknown` |
| 0x4C | gpl default             | libgff handler is `gpl_unknown` |
| 0x4D | gpl default             | libgff handler is `gpl_unknown` |
| 0x4E | gpl default             | libgff handler is `gpl_unknown` |
| 0x4F | gpl print string        |       |
| 0x50 | gpl print number        |       |
| 0x51 | gpl printnl             |       |
| 0x52 | gpl rand                | safe in RETVAL context |
| 0x53 | gpl default             | libgff handler is `gpl_unknown` |
| 0x54 | gpl showpic             |       |
| 0x55 | gpl default             | libgff handler is `gpl_unknown` |
| 0x56 | gpl default             | libgff handler is `gpl_unknown` |
| 0x57 | gpl default             | libgff handler is `gpl_unknown` |
| 0x58 | gpl skillroll           | libgff handler is `gpl_unknown` |
| 0x59 | gpl statroll            | safe in RETVAL context |
| 0x5A | gpl string compare      | safe in RETVAL context |
| 0x5B | gpl match string        | libgff handler is `gpl_unknown` |
| 0x5C | gpl take                | safe in RETVAL context |
| 0x5D | gpl sound               |       |
| 0x5E | gpl tport               |       |
| 0x5F | gpl music               | libgff handler is `gpl_unknown` |
| 0x60 | gpl default             | libgff handler is `gpl_unknown` |
| 0x61 | gpl cmpend              |       |
| 0x62 | gpl wait                |       |
| 0x63 | gpl while               | control flow |
| 0x64 | gpl wend                | control flow |
| 0x65 | gpl attacktrigger       |       |
| 0x66 | gpl looktrigger         |       |
| 0x67 | gpl endif               | control flow |
| 0x68 | gpl move tiletrigger    |       |
| 0x69 | gpl door tiletrigger    |       |
| 0x6A | gpl move boxtrigger     |       |
| 0x6B | gpl door boxtrigger     |       |
| 0x6C | gpl pickup itemtrigger  |       |
| 0x6D | gpl usetrigger          |       |
| 0x6E | gpl talktotrigger       |       |
| 0x6F | gpl noorderstrigger     |       |
| 0x70 | gpl usewithtrigger      |       |
| 0x71 | gpl default             | libgff handler is `gpl_unknown` |
| 0x72 | gpl default             | libgff handler is `gpl_unknown` |
| 0x73 | gpl default             | libgff handler is `gpl_unknown` |
| 0x74 | gpl default             | libgff handler is `gpl_unknown` |
| 0x75 | gpl default             | libgff handler is `gpl_unknown` |
| 0x76 | gpl byte plus equal     |       |
| 0x77 | gpl byte minus equal    |       |
| 0x78 | gpl byte times equal    |       |
| 0x79 | gpl byte divide equal   |       |
| 0x7A | gpl word plus equal     |       |
| 0x7B | gpl word minus equal    |       |
| 0x7C | gpl word times equal    |       |
| 0x7D | gpl word divide equal   |       |
| 0x7E | gpl long plus equal     |       |
| 0x7F | gpl long minus equal    |       |
| 0x80 | gpl get range           | safe in RETVAL context |

## Sources

- libgff `src/gpl/parse.c` `gpl_commands` table (lines
  1554-1684): the per-byte handler + name list. Primary
  source.
- libgff `src/gpl/parse.c` `gpl_retval` switch (lines
  1791-1826): the "safe in RETVAL context" annotations.
- soloscuro-archive `src/gpl/`: secondary cross-reference;
  splits parsing across multiple files. Worth reading when
  porting parameter encoding logic.

## Discovery loop

We grow this table by:

1. Reading the per-handler functions in libgff `parse.c` to
   pin down parameter shape per opcode (v0.2.0 work).
2. Cross-referencing with the DSO v1.0 client debug-symbol
   function names from greg-kennedy's `DarkSunOnline` wiki:
   names like `gpl_op_set_flag` confirm or refine the libgff
   mnemonic.
3. Running `opcode-fuzz` (Phase 5): swap a chunk to a one-byte
   probe, observe engine state delta in DOSBox.
