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

## What `gpl-disasm v0.3.1` ships

**`gpl else` edge fix.** v0.3.0's CFG routed the if-not-taken
edge to the else opcode itself, which the runtime treats as a
no-op when entered by jump; the actual control flow continues
past the opcode bytes into the else-body. v0.3.1 redirects any
branch target landing on a `gpl else` to `else_offset +
else_length` and introduces a `target_aliases` map so that
renderers can still resolve raw branch params pointing at the
else opcode. 5,471 / 20,281 (27%) of DS1+DS2 conditionals were
affected. See patchnotes for full details.

## What `gpl-disasm v0.3.0` ships

**Control-flow analysis.** Every disassembled chunk now carries a
`Cfg` of basic blocks, entry points, and labeled successors. The
text listing renders branch targets as label names
(`gpl if label_0x0020`) and prepends `label_*:` / `entry_*:` lines
to every block leader. The CFG is exposed via three new CLI flags
(`--entries`, `--cfg <path>`, `--no-labels`) and an additive
`cfg` field in JSON output.

The walker's load-bearing assumption was verified in a
pre-implementation spike: the first parameter of every branch
opcode is the absolute byte offset of the target instruction
within the same GPL chunk. Sources, hand-trace evidence, and the
per-opcode table live in
[`../../docs/gpl-bytecode.md` §5a](../../docs/gpl-bytecode.md).
The one wrinkle: `gpl ifcompare` (0x27) takes 2 params where the
**second** is the target offset (the first is the comparison
value).

**Corpus verification.** 600 / 600 DS1+DS2 GPL/MAS chunks build a
CFG where every one of the 71,403 successor edges resolves to a
known instruction boundary. 0 computed-target edges, 1,384
cross-chunk `gpl global sub` call sites are recorded for v0.4.0+
inter-chunk analysis. The new
`every_cfg_successor_resolves_to_instruction_boundary` integration
test enforces this invariant.

## What `gpl-disasm v0.2.1` ships

**The deferred cases are closed.** v0.2.0 deferred `GPL_RETVAL`
(nested function calls), the `GPL_COMPLEX_*` range (record-field
access via `gpl_access_complex`), `gpl_setrecord`, and the
`0xb3` "passive flag" special case as opaque best-effort. v0.2.1
ports them faithfully:

- `gpl_access_complex` (libgff `parse.c` 235-288): word obj_name
  + byte depth + depth bytes of element data. Decoded as
  `Expression::ComplexAccess { tag, obj_name, depth, elements }`
  with the `obj_name >= 0x8000` keyword set (POV, ACTIVE,
  PASSIVE, OTHER, OTHER1, THING) rendered by name.
- `GPL_RETVAL` (libgff `parse.c` 1791-1826): recursively
  dispatches to the inner opcode's `ParamSpec` if the inner
  opcode is in libgff's safe-subset (21 opcodes). Bounded by
  `MAX_RETVAL_DEPTH = 4`.
- `gpl_setrecord` (opcode `0x40`): now a first-class
  `ParamSpec::SetRecord` reading `access_complex + read_number`.
- `gpl_load_variable` (opcode `0x16`): the complex-write path
  now decodes via `access_complex` instead of bailing.

**Corpus alignment: 100%.** All 600 GPL/MAS chunks across DS1
and DS2 GPLDATA.GFF now disassemble fully aligned with no
best-effort fallback. (v0.2.0 was 10.7%.)

## v0.2.0 baseline

**Parameter decoding**. Each opcode consumes its variable-length
parameter bytes, so output is **one row per instruction** rather
than one per byte. Parameters render as a short infix
expression: `gpl print string  115, "Free! Finally free!..."`,
`gpl load accum  GNUM[1] == 0i8`, `gpl tport NAME(-22), 255,
99i8, 99i8, 0i8`.

The decoder is a port of libgff's `gpl_read_number` (the
variable-length expression decoder), `gpl_read_simple_num_var`
(variable references with `EXTENDED_VAR`), `gpl_access_complex`
(record-field access), and the 7-bit packed string decoder from
soloscuro-archive's `gpl-string.c`. All ports MIT-licensed and
attributed inline in [`src/lib.rs`](src/lib.rs) and in
[`../../CREDITS.md`](../../CREDITS.md).

Structural handlers also decode:

- `gpl_load_variable` (0x16): load_accum + datatype + 1/2 byte
  variable id (simple case) or deferred complex write.
- `gpl_menu` (0x48): menu name + a loop of three-expression
  entries terminated by `0x4A`.
- `gpl_search` (0x33): expression + 2 bytes + a do-while loop
  matching libgff's `parse.c` 901-955.
- `gpl_log` (0x2C): one packed-string payload.

Still best-effort (`Custom` ParamSpec) in v0.2.1:

- `gpl_unknown` handlers: bytes the engine reserves but libgff
  treats as unknown. Soloscuro-archive's parallel implementation
  in `gpl-lua.c` fills in `0x5F music` (1 parameter); the rest
  remain unimplemented in both upstream repos. These don't
  appear in real game scripts so they don't hurt corpus
  alignment, but a chunk that uses one would still misalign.

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

## Roadmap

- v0.1.0 — byte-annotation pass.
- v0.2.0 — parameter decoding. True instruction boundaries on
  the common path; `--json` output. Inline string decoding via
  the 7-bit packed-string port.
- v0.2.1 — close the deferred cases: nested RETVAL recursion,
  `gpl_access_complex` (COMPLEX_* range and the `0xb3` special
  case), `gpl_setrecord`, and the complex-write path of
  `gpl_load_variable`. Corpus alignment hits 100% on all 600
  DS1+DS2 GPL/MAS chunks.
- v0.3.0 — recursive-descent CFG. Basic-block graph,
  entry-point discovery, labeled jump targets, Graphviz DOT
  output. Initial corpus: 71,403 edges, 1,384 cross-chunk
  call sites.
- **v0.3.1 (current)** — `gpl else` edge fix. v0.3.0 routed
  if-not-taken edges to the else opcode itself, missing the
  else-body on 27% of corpus conditionals. v0.3.1 redirects
  past the else opcode and adds a `target_aliases` map for
  raw-target-to-label rendering. 66,028 edges resolved on the
  corpus (the ~5,400 difference is Fallthrough edges absorbed
  into the now-merged blocks). See patchnotes for details.
- v0.4.0+ — DSO debug-symbol import; inter-chunk CFG following
  `global sub` edges; integration with `opcode-fuzz` (Phase 5)
  for opcode discovery.

## Build

```sh
cd /path/to/opends
cargo build -p gpl-disasm --release
./target/release/gpl-disasm .games/ds1/GPLDATA.GFF --kind 'GPL ' --id 1 | head
```
