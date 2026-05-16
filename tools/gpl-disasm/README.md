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

## What `gpl-disasm v0.4.6` ships

Text-format tweaks that make the human-readable listing
round-trippable through `gpl-asm` v0.2.1's parser.

- **`render_text(&DisasmResult, labels_on: bool) -> String`** is
  now a public library function. The binary's local copy was
  moved here so both the binary and downstream consumers go
  through the same path.
- **Branch params drop the function-name decoration**: a label
  like `entry_0x0001 (iniya_first_meeting)` renders as
  `gpl if entry_0x0001` in a branch-param position. The label
  DECLARATION line keeps the full decorated form so modders see
  the function name there.
- **`target_aliases`-redirected branches** (where a `gpl if`
  targets a `gpl else` opcode) now render as raw integers in
  the param. The labelled form was lossy for those cases; the
  integer is the round-trippable byte-level source of truth.
- **`raw_tail` is emitted** as a `; raw_tail=HEX` trailer on
  instructions where it's populated (currently only top-level
  `gpl_search`).
- **`Expression::RetVal`'s Display** emits a ` raw_tail=HEX`
  sentinel inside the `RETVAL(...)` body when
  `inner_raw_tail` is set, so the nested-Search case round-trips
  too.

After v0.4.6, every aligned GPL/MAS chunk in the DS1+DS2 corpus
round-trips through `bytes -> disassemble -> render labelled
text -> gpl-asm parse -> encode` byte-identical: **600 / 600**.

## What `gpl-disasm v0.4.5` ships

**Side-byte preservation for `gpl_search` (0x33).** Closes the
last v0.1.0-era gap in the reassembler: with v0.4.5, every
aligned GPL/MAS chunk in DS1+DS2 GPLDATA round-trips
byte-identical through `disassemble -> encode`. The corpus
metric: **600 / 600**.

New optional fields:

- `Instruction.raw_tail: Option<Vec<u8>>` — populated for the
  top-level `gpl_search` case with the bytes consumed past
  `params[0]` (the 2-byte range argument plus per-loop-iteration
  field / type / 0x53 markers).
- `Expression::RetVal::inner_raw_tail: Option<Vec<u8>>` — same,
  for `gpl_search` nested inside a `GPL_RETVAL`. 143 corpus
  chunks have this shape.

Both fields are `#[serde(default, skip_serializing_if =
"Option::is_none")]`, so JSON output for non-Search instructions
is byte-identical to v0.4.4. The `params` vec still gets the
trailing expressions from Search's conditional-expression loop
populated for downstream consumers (dialog-extract, text
listings); the reassembler uses only `params[0] + raw_tail`.

This is purely additive on the public API. Pattern-match users
of `Expression::RetVal { .. }` need to add a `..` rest pattern
or name the new field (the type-system error is helpful).

## What `gpl-disasm v0.4.4` ships

**`Deserialize` impls on every public Serialize-able type**, so
`gpl-asm` (the round-trip reassembler) can consume the same JSON
this crate emits. Additive across `DisasmResult`, `Instruction`,
`Expression`, `Cfg`, `BasicBlock`, `Edge`, `TerminatorKind`,
`EdgeKind`, `CrossChunkCall`, `UnresolvedEdge`, `GlobalCfg`,
`ChunkNode`, `CrossEdge`, plus the leaf enums `VarKind`, `Op`,
`StringSubType`.

Two side changes that come with this:

- `Instruction.mnemonic`'s mate inside `Expression::RetVal` —
  `inner_mnemonic` — changes from `Option<&'static str>` to
  `Option<Cow<'static, str>>`. Mirrors the v0.4.2 change to the
  outer `mnemonic` field. Zero-allocation default path remains
  via `Cow::Borrowed`. JSON output shape is unchanged (serde
  serialises `Cow` as a plain string).
- `UnresolvedEdge.reason` changes from `&'static str` to
  `Cow<'static, str>` for the same reason. Internal constructors
  use `Cow::Borrowed("...")`; downstream consumers (the DOT
  writer and JSON output) work unchanged.

`VarKind::from_tag` / `VarKind::to_tag` and `Op::from_byte` /
`Op::to_byte` are now `pub` so the encoder can use them as a
symmetric inverse pair. `to_tag` and `to_byte` are new this
release.

## What `gpl-disasm v0.4.3` ships

**Lossless 7-bit packed-string decoder**, prerequisite for the
gpl-asm v0.1.0 round-trip reassembler coming next.

`decode_compressed` previously mapped every 7-bit value outside
`0x20..=0x7E` to `0x20` (space) for display safety. The original
chunks ship real formatting codes (TAB, line feed, etc.) inside
packed-string payloads; the lossy mapping made byte-identical
re-encoding impossible. A pre-implementation spike for gpl-asm
found 19 such strings across DS1+DS2 GPLDATA where the encoder's
output would have legitimately differed from the source bytes.

v0.4.3 emits every byte verbatim. Strings whose source contains
non-printable formatting codes now decode to those exact bytes;
JSON consumers see `\u00XX` escapes for them, and the gpl-asm
v0.1.0 corpus round-trip will hit 100% on `ImmediateString` once
that crate lands.

Affected strings (DS1 4, DS2 15) make up 0.05% of the corpus.
Visible-text decode behaviour is otherwise unchanged.

New unit test: `read_text_compressed_preserves_non_printable_bytes`.

## What `gpl-disasm v0.4.2` ships

**Opcode-mnemonic overrides.** The `syms/opcodes.toml` catalogue
loaded since v0.4.0 is now applied to the rendered output. A row
like

```toml
[opcodes."0x12"]
name = "gpl jmp"
verified_by = "..."
```

replaces the libgff default mnemonic for opcode `0x12` in both
the text listing and the JSON output's `Instruction.mnemonic`
field. Defaults stay for any byte without an entry. Downstream
consumers (`dialog-extract`) continue to key on the `opcode`
byte, not the mnemonic text, so they're unaffected.

The override is plumbed through every disassembly path
(`--all`, `--global-cfg`, and single-chunk). No new CLI flags;
the existing `--syms` / `--no-syms` flags control the catalogue
lookup.

The shipped `opcodes.toml` is **empty by design**. See the file
header for the curation rule: a row lands only when the libgff
mnemonic is unambiguously wrong, or when the alternate name is
materially clearer and still accurate. Cosmetic aliases are not
sufficient. Curation grows when evidence exists.

**Internal change**: `Instruction.mnemonic` is now
`Option<Cow<'static, str>>` (was `Option<&'static str>`).
Zero-allocation in the default path (`Cow::Borrowed` from the
static `OPCODES` table); `Cow::Owned` after an override applies.
JSON shape is unchanged. Inner mnemonics inside
`Expression::RetVal::inner_mnemonic` are intentionally left as
`&'static str` for v0.4.2; extending overrides there is a small
follow-up if curation needs it.

## What `gpl-disasm v0.4.1` ships

**Inter-chunk control-flow graph (global callgraph).** Builds a
whole-file graph where nodes are GPL/MAS chunks and edges are
`gpl global sub` (0x14) call sites. Each chunk node carries
inbound / outbound call counts; each edge optionally carries the
symbol-derived names for the caller (nearest enclosing entry)
and callee.

New CLI flag:

```sh
gpl-disasm GPLDATA.GFF --global-cfg out.dot          # DOT
gpl-disasm GPLDATA.GFF --global-cfg out.json --json  # structured JSON
gpl-disasm GPLDATA.GFF --global-cfg -                # stdout
```

Mutually exclusive with the single-chunk path; consumes the
whole GFF.

**Corpus results** (GOG 1.10): DS1 GPLDATA has 250 chunks and
587 inter-chunk edges; DS2 GPLDATA has 350 chunks and 797 edges.
The most-called chunk in DS1 is GPL-74 (169 inbound calls,
2 outbound) — a heavily-shared utility. The 1,384 total edges
match the per-chunk `cross_chunk_calls` count reported by the
corpus soundness test from v0.3.0+.

## What `gpl-disasm v0.4.0` ships

**Symbol import plumbing.** Hand-curated catalogues at
`tools/gpl-disasm/syms/` decorate function-entry labels in both
text and JSON output. `entry_0x0001` becomes
`entry_0x0001 (iniya_first_meeting)` when the matching row is
present in `functions.toml`. Downstream consumers
(`dialog-extract` etc.) pick up the enriched labels through the
JSON automatically.

TOML schemas (see the files themselves for the full comments):

```toml
# syms/opcodes.toml — opcode mnemonic overrides
# (applied to output starting in v0.4.2; ships empty by default)
[opcodes."0x4F"]
name = "print_string_v2"
dso_source = "DSO::gpl_op_print_string"

# syms/functions.toml — function entry names
[[function]]
file = "GPLDATA.GFF"
kind = "GPL "            # 4-char FOURCC, trailing space preserved
chunk_id = 1
offset = 0x0001
name = "iniya_first_meeting"
notes = "Reasoning / provenance"
```

New CLI flags:

- `--syms <dir>` — explicit catalogue path. Defaults to
  `tools/gpl-disasm/syms/` next to the binary (walks up to 8
  directories looking for it).
- `--no-syms` — disable the catalogue lookup entirely (useful
  for diff-friendly output when curation is in flux).

Starter catalogue: two verified entries for DS1 GPLDATA chunk 1
(Iniya's dialog). `opcodes.toml` shipped empty in v0.4.0;
mnemonic-override wiring lands in v0.4.2.

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

Whole-file inter-chunk callgraph (v0.4.1+):

```sh
gpl-disasm .games/ds1/GPLDATA.GFF --global-cfg - | dot -Tpng -o ds1-callgraph.png
gpl-disasm .games/ds1/GPLDATA.GFF --global-cfg gcfg.json --json
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
- v0.3.1 — `gpl else` edge fix. v0.3.0 routed if-not-taken
  edges to the else opcode itself, missing the else-body on
  27% of corpus conditionals. v0.3.1 redirects past the else
  opcode and adds a `target_aliases` map for raw-target-to-
  label rendering. 66,028 edges resolved on the corpus.
- v0.4.0 — symbol import plumbing. Hand-curated
  `tools/gpl-disasm/syms/{opcodes,functions}.toml` decorate
  function-entry labels in both text and JSON output. New
  `--syms <dir>` and `--no-syms` flags. Starter catalogue ships
  with 2 verified entries (DS1 chunk 1 Iniya).
- **v0.4.1 (current)** — inter-chunk CFG. `--global-cfg <path>`
  emits a whole-file callgraph following the `gpl global sub`
  (0x14) cross-chunk call sites. 587 edges across 250 DS1
  chunks; 797 edges across 350 DS2 chunks. Symbol annotations
  flow through: when caller / callee offsets match entries in
  `functions.toml`, the edge metadata names them.
- v0.4.0+ — DSO debug-symbol import; inter-chunk CFG following
  `global sub` edges; integration with `opcode-fuzz` (Phase 5)
  for opcode discovery.

## Build

```sh
cd /path/to/opends
cargo build -p gpl-disasm --release
./target/release/gpl-disasm .games/ds1/GPLDATA.GFF --kind 'GPL ' --id 1 | head
```
