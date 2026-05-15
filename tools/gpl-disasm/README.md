# gpl-disasm

Disassembler for SSI's **GPL** (Game Programming Language)
bytecode, the embedded scripting language that powers every
quest, NPC dialog branch, region transition, and combat-script
moment in SSI's Dark Sun CRPGs. Part of the OpenDS toolkit's
modding stack: `gff-edit` exposes the GFF container, and
`gpl-disasm` exposes the bytecode inside `GPL ` and `MAS `
chunks so modders can read what a script does.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gff-edit` for GFF I/O.

## What `gpl-disasm v0.2.0` ships

**Parameter decoding**. Each opcode now consumes its
variable-length parameter bytes, so output is **one row per
instruction** rather than one per byte. Parameters render as a
short infix expression: `gpl print string  115, "Free! Finally
free!..."`, `gpl load accum  GNUM[1] == 0i8`, `gpl tport
NAME(-22), 255, 99i8, 99i8, 0i8`.

The decoder is a port of libgff's `gpl_read_number` (the
variable-length expression decoder), `gpl_read_simple_num_var`
(variable references with `EXTENDED_VAR`), and the 7-bit packed
string decoder from soloscuro-archive's `gpl-string.c`. All
ports MIT-licensed and attributed inline in
[`src/lib.rs`](src/lib.rs) and in
[`../../CREDITS.md`](../../CREDITS.md).

Structural handlers also decode:

- `gpl_load_variable` (0x16): load_accum + datatype + 1/2 byte
  variable id (simple case) or deferred complex write.
- `gpl_menu` (0x48): menu name + a loop of three-expression
  entries terminated by `0x4A`.
- `gpl_search` (0x33): expression + 2 bytes + a do-while loop
  matching libgff's `parse.c` 901-955.
- `gpl_log` (0x2C): one packed-string payload.

Deferred to v0.2.1 (decoded as opaque, marked `best_effort`):

- Nested `GPL_RETVAL | 0x80` (recursive opcode dispatch).
- `GPL_COMPLEX_*` range (`0x30..=0x3F` after stripping the high
  bit) and the `0xb3` "passive flag" special case.
- `gpl_setrecord` (uses `access_complex`).
- `gpl_unknown` handlers: bytes the engine reserves but libgff
  treats as unknown. Soloscuro-archive's parallel implementation
  in `gpl-lua.c` fills in `0x5F music` (1 parameter); the rest
  remain unimplemented in both upstream repos.

## Library

```rust
use gpl_disasm::{disassemble, DisasmResult, Instruction};

let bytes = gff.read(FourCC(*b"GPL "), 1).unwrap();
let result: DisasmResult = disassemble(bytes);
for instr in &result.instructions {
    println!("{instr}");
}
eprintln!("aligned: {}", result.aligned);
```

Result types derive `serde::Serialize`; `--json` mode is a thin
wrapper around `serde_json::to_string_pretty`.

## CLI: `gpl-disasm`

```sh
gpl-disasm <file> --kind GPL --id N           # one chunk to stdout
gpl-disasm <file> --kind MAS --id N
gpl-disasm <file> --kind GPL --id N --json    # structured JSON
gpl-disasm <file> --all -o <dir>              # every GPL/MAS chunk → <kind>-<id>.asm
gpl-disasm <file> --all -o <dir> --json       # ... → <kind>-<id>.json
gpl-disasm --opcodes                          # dump the embedded opcode catalogue
```

`--kind` accepts `GPL` (compiled bytecode) or `MAS` (compiled
master scripts). Both are flat byte streams.

### Example

```
$ gpl-disasm .games/ds1/GPLDATA.GFF --kind 'GPL ' --id 1 | head
0000  19  gpl global ret
0001  16  gpl load variable     0i8, LNUM[0]
0006  16  gpl load variable     0i8, LNUM[1]
000b  54  gpl showpic           120i8
000e  18  gpl load accum        GF[1] == 1i8
0014  3e  gpl if                86
0017  4f  gpl print string      115, "Free! Finally free! I will destroy you all! Ha ha ha! "
004d  22  gpl request           16i8, GNAME[39], 3i8, 0i8
0056  3f  gpl else              137
0059  18  gpl load accum        GNUM[1] == 0i8
```

## Roadmap

- v0.1.0 — byte-annotation pass.
- **v0.2.0 (current)** — parameter decoding. True instruction
  boundaries on the common path; `--json` output. Inline string
  decoding via the 7-bit packed-string port.
- v0.2.1 — close the deferred cases: nested RETVAL, COMPLEX_*
  range, `gpl_setrecord`. Boost corpus alignment percentage.
- v0.3.0 — recursive descent. Follow jumps and calls; emit
  basic blocks and labels.
- v0.4.0+ — DSO debug-symbol import; integration with
  `opcode-fuzz` (Phase 5) for opcode discovery.

## Build

```sh
cd /path/to/opends
cargo build -p gpl-disasm --release
./target/release/gpl-disasm .games/ds1/GPLDATA.GFF --kind 'GPL ' --id 1 | head
```
