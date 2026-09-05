# gpl-disasm

Disassembler for SSI's **GPL** (Game Programming Language)
bytecode, the embedded scripting language that powers every
quest, NPC dialog branch, and region transition in SSI's Dark Sun CRPGs. Part of the OpenDS toolkit's
modding stack: `gff-edit` exposes the GFF container, and
`gpl-disasm` exposes the bytecode inside `GPL ` and `MAS `
chunks so modders can read what a script does.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.


## What it does

- **Full GPL/MAS disassembly** at 100% corpus alignment (all 600
  DS1+DS2 chunks): true instruction boundaries, parameter decoding,
  and the lossless 7-bit packed-inline-string decoder.
- **Recursive-descent CFG**: basic blocks, entry-point discovery,
  labeled jump targets, Graphviz DOT via `--global-cfg` (whole-file
  inter-chunk callgraph; 587 edges / 250 DS1 chunks, 797 / 350 DS2).
- **Curated symbol catalogues** under `syms/` (functions, opcodes,
  variables, per-chunk locals) decorate labels and mnemonics in both
  text and JSON output. Load an alternate set with `--syms <dir>`;
  skip with `--no-syms`.
- **JSON output** (`--json`) is the machine contract consumed by
  `gpl-asm`, `dialog-extract` and `opcode-fuzz`.
- **Round-trippable text rendering** via the public
  `render_text` API, which `gpl-asm`'s text path depends on.

DSO debug-symbol import proposals: see
`scripts/import-dso-symbols.py` (emits review-ready rename
proposals; never writes `syms/` directly).

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
gpl-disasm <file> --kind GPL --id N           # one chunk to stdout (labels on)
gpl-disasm <file> --kind MAS --id N
gpl-disasm <file> --kind GPL --id N --json    # structured JSON, incl. cfg
gpl-disasm <file> --kind GPL --id N --no-labels   # integer targets
gpl-disasm <file> --kind GPL --id N --entries     # list entry-point offsets
gpl-disasm <file> --kind GPL --id N --cfg -       # DOT to stdout
gpl-disasm <file> --kind GPL --id N --cfg out.dot # DOT to file
gpl-disasm <file> --all -o <dir>              # every GPL/MAS chunk → <kind>-<id>.asm
gpl-disasm <file> --all -o <dir> --json       # ... → <kind>-<id>.json
gpl-disasm <file> --all -o <dir> --cfg <dir>  # ... → <kind>-<id>.dot in cfg dir
gpl-disasm <file> --all -o <dir> --entries    # ... → <kind>-<id>.entries beside .asm
gpl-disasm --opcodes                          # dump the embedded opcode catalogue
```

`--kind` accepts `GPL` (compiled bytecode) or `MAS` (compiled
master scripts). Both are flat byte streams.

### Example (v0.3.0 labeled output)

```
$ gpl-disasm .games/ds1/GPLDATA.GFF --kind GPL --id 9 | head -12
entry_0x0000:
0000  19  gpl global ret
entry_0x0001:
0001  18  gpl load accum          (GF[34]) and (GF[36] == 0i8)
000e  3e  gpl if                  label_0x0020
label_0x0011:
0011  22  gpl request             5i8, NAME(-2002), 0i8, 0i8
001b  16  gpl load variable       1i8, GF[36]
label_0x0020:
0020  67  gpl endif
0021  18  gpl load accum          (GF[58] == 1i8) and (GF[56] == 0i8)
0031  3e  gpl if                  label_0x0062
```

Pipe `--cfg -` into Graphviz `dot` for a visual:

```sh
gpl-disasm .games/ds1/GPLDATA.GFF --kind GPL --id 9 --cfg - | dot -Tpng -o chunk9.png
```

Whole-file inter-chunk callgraph (v0.4.1+):

```sh
gpl-disasm .games/ds1/GPLDATA.GFF --global-cfg - | dot -Tpng -o ds1-callgraph.png
gpl-disasm .games/ds1/GPLDATA.GFF --global-cfg gcfg.json --json
```

## Build

```sh
cd /path/to/opends
cargo build -p gpl-disasm --release
./target/release/gpl-disasm .games/ds1/GPLDATA.GFF --kind 'GPL ' --id 1 | head
```
