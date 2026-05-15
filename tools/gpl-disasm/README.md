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

## What `gpl-disasm v0.1.0` ships

A **byte-annotation pass**: every byte of a GPL chunk gets a
line tagged with libgff's opcode name. We do *not* yet decode
parameter bytes; the output treats each byte as a potential
opcode, so instruction boundaries are not aligned with the real
program flow. Modders can still:

- Grep mnemonics across `GPLDATA.GFF` to find quest scripts by
  the kind of work they do (e.g. `gpl print string`,
  `gpl talktotrigger`, `gpl if`).
- Spot ASCII strings inline (NPC names, dialog text snippets
  embedded directly in bytecode).
- Identify byte-level patch targets by offset.

True instruction-boundary decoding (consuming each opcode's
variable-length parameters) lands in v0.2.0 once we port
libgff's `gpl_read_number` / `gpl_get_parameters` logic.

The opcode catalogue is sourced from libgff's `gpl_commands`
table (`dsoageofheroes/libgff` `src/gpl/parse.c`, MIT-licensed,
attributed in code comments).

## Library

```rust
use gpl_disasm::{disassemble, Annotation};

let bytes = gff.read(FourCC(*b"GPL "), 42).unwrap();
for ann in disassemble(bytes) {
    println!("{:04x}  {:02x}  {}", ann.offset, ann.byte, ann.mnemonic);
}
```

## CLI: `gpl-disasm`

```sh
gpl-disasm <file> --kind GPL --id N         # one chunk to stdout
gpl-disasm <file> --kind MAS --id N
gpl-disasm <file> --all -o <dir>            # every GPL/MAS chunk → <kind>-<id>.asm
gpl-disasm --opcodes                        # dump the embedded opcode catalogue
```

`--kind` accepts `GPL` (compiled bytecode) or `MAS` (compiled
master scripts). Both are flat byte streams.

## Roadmap

- **v0.1.0 (current)** — byte-annotation pass. Each byte tagged
  with its libgff opcode name; ASCII strings annotated.
- v0.2.0 — parameter decoding. True instruction boundaries.
  Port libgff's `gpl_read_number` and friends.
- v0.3.0 — recursive descent. Follow jumps and calls; emit
  basic blocks and labels.
- v0.4.0+ — DSO debug-symbol import; integration with
  `opcode-fuzz` (Phase 5) for opcode discovery.

## Build

```sh
cd /path/to/opends
cargo build -p gpl-disasm --release
./target/release/gpl-disasm .games/ds1/GPLDATA.GFF --kind 'MAS ' --id 0 | head
```
