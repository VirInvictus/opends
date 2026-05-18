# gpl-asm

Reassembler for SSI's **GPL** (Game Programming Language)
bytecode, the embedded scripting language inside `GPL ` and
`MAS ` chunks. Takes the output of `gpl-disasm --json` and emits
byte-identical bytecode. The inverse of `gpl-disasm`'s decoder.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gpl-disasm` for the [`DisasmResult`] type (and the
`Deserialize` impls added there in v0.4.4 specifically so this
crate can consume the same JSON the disassembler emits).

## What `gpl-asm v0.7.0` ships

Two real authoring features on top of v0.6.0's directive
infrastructure. Both are pure preprocessor work: the bytecode
the encoder produces is unchanged, and the corpus round-trip
stays at 600 / 600.

### Parameterised macros

`%define <name>(<params>) <body>` registers a textual,
function-like macro. A call `<name>(actual1, actual2)` at
identifier positions expands to `<body>` with `<params>` bound
to the actuals.

```text
%define mark_visited(slot) GBYTE[slot]

0000  3a  gpl_immed             mark_visited(47)
; expands to: 0000  3a  gpl_immed             GBYTE[47]
```

Parameter names follow the same `is_valid_define_name` rule as
plain `%define`. Duplicate params (`%define bad(a, a) ...`) are
a hard error. A wrong-arity call surfaces as `MacroParamCount`
with the expected vs found counts.

Arguments are pre-expanded against the outer `%define` / macro
table before binding to the parameter, so a plain define cleanly
flows into a macro:

```text
%define SLOT 9
%define wrap(id) GBYTE[id]

0000  3a  gpl_immed             wrap(SLOT)
; expands to: 0000  3a  gpl_immed             GBYTE[9]
```

Substitution is textual (no type checking, no hygiene): a
parameter name shadows the global `%define` namespace inside
the macro body, which is the natural shape for text-substitution.
Macro names share the global namespace with plain `%define`;
declaring both is a `DuplicateDefine` error.

### `@include "path/file.asm"`

Textual include relative to the current file. Useful for
splitting common macro / define libraries out of an
instruction file.

```text
@include "macros/common.asm"
@include "syms/region-flags.asm"

0000  3a  gpl_immed             wrap(SLOT)
```

The included file goes through the same preprocessor
recursively; defines and macros declared inside it are visible
after the `@include` directive. A canonical-path circular-
include guard rejects `a.asm` -> `b.asm` -> `a.asm`; an
absolute `INCLUDE_DEPTH_LIMIT = 16` cap is the fallback
circuit-breaker.

Errors surface as `BadIncludeSyntax`, `IncludeIo`,
`CircularInclude`, or `IncludeDepthExceeded` per the
respective failure mode.

### Round-trip safety

All 600 / 600 corpus chunks still encode byte-identical under
`gpl-asm` (release-mode `text_roundtrip` test). The
preprocessor expands directives entirely in the preprocessor
pass; the instruction-parsing stage sees post-expansion text
and is unchanged from v0.6.0.

## What `gpl-asm v0.6.0` ships

Authoring conveniences for hand-written GPL listings. The
text-listing parser now understands two preprocessor
directives that make authoring less tedious without changing
the bytecode the encoder produces. v0.5.0's validator pass
+ caret-style errors remain in place; v0.6.0 adds plumbing
on top.

### `%define <name> <replacement>`

Token substitution applied to every subsequent non-directive
line:

```text
%define ROOM_FLAG 47
%define WORLD_GREETING 0x4200

0000  3a  gpl_immed             ROOM_FLAG
0003  12  gpl jump              WORLD_GREETING
```

is equivalent to writing `47` and `0x4200` directly in the
param slots. `%define` is identifier-shaped only (letters /
digits / underscore, leading letter or `_`) and **cannot
shadow** reserved tokens: operator words (`and`, `or`),
variable shorts (`GNUM`, `GBYTE`, `LSTR`, ...), keyword
tokens (`RETVAL`, `INTRODUCE`, `ACCUM`, ...), or mnemonic
words (`gpl`, `jump`, `endif`, `else`, `while`, ...).
Substitution skips quoted regions (`"..."`) and the
per-line `  ; trailer` comment portion, so a `%define` name
appearing inside a string literal stays literal.

Duplicate `%define` is an error
(`ParseError::DuplicateDefine`); collision with a reserved
name is an error (`ParseError::BadDefineName`); missing
replacement is an error (`ParseError::BadDefineSyntax`).

### `%search-tail <hex-bytes>`

Attaches `raw_tail` bytes to the next `gpl_search` (`0x33`)
instruction line:

```text
%search-tail 01 00 02 ff
0000  33  gpl_search            GBYTE[0]
```

is equivalent to writing the disassembler-emitted form:

```text
0000  33  gpl_search            GBYTE[0]  ; raw_tail=010002ff
```

Both produce the same `Instruction.raw_tail = [0x01, 0x00,
0x02, 0xff]`. The directive form is easier to author by
hand because the bytes are space-separated instead of
needing to be packed in a single hex run.

If both forms appear on the same instruction, the parser
errors with `ParseError::DuplicateSearchTail` rather than
silently picking one.

### Source-line preservation

Directive lines are **blank-replaced** during preprocessing
(not removed) so line numbers in caret-style error messages
continue to match the user's source. A `%define` on line 7
of an authored listing still surfaces a parse error on line
9 as `line 9`, not `line 8`.

### What's the same

- The `gpl-disasm`-emitted text listing path is unchanged;
  the disassembler doesn't emit `%define` or
  `%search-tail`, so the corpus 600 / 600 round-trip stays
  byte-identical.
- `--validate-only` and `--no-validate` still work the
  same way.
- All v0.5.0 error variants still exist and still produce
  caret output via `format_with_caret`.

### Out of scope (queued for v0.7.0+)

- **Parameterised macros** (`%define foo(arg1, arg2) ...`).
  v0.6.0 is name -> text substitution only.
- **`@include` directives** (multi-file authoring).
- **A `.const` keyword** distinct from `%define`. They'd be
  aliases under the hood; `%define` covers both use cases
  for now.

## What `gpl-asm v0.5.0` ships

The **author safety net**. Two pieces that improve the
modder's experience when a hand-edited listing is wrong:

### Caret-style parse errors

The text-listing parser already tracked line numbers; v0.5.0
extends every `ParseError` with a column and renders failures
in a `rustc`-shaped format. New public surface in
[`gpl_asm::parse`](src/parse.rs):

- `pub fn error_line(err: &ParseError) -> usize`.
- `pub fn error_span(err: &ParseError, source: &str) -> (usize, usize)`.
- `pub fn format_with_caret(err: &ParseError, source: &str) -> String`.

The `gpl-asm` binary wires `format_with_caret` into its
text-mode parse path, so a typo lands with a pointer:

```text
parse error: line 12: bad opcode "ZZ"
  --> input:12:7
  |
12 | 0024  ZZ  gpl_immed
  |       ^^
```

For `BadExpression` (the most common authoring failure), the
caret finds the offending token in the source line and
underlines it.

### Static validation pass

New [`gpl_asm::validate`](src/validate.rs) catches whole
classes of authoring mistakes before encoding, so the encoder
doesn't have to surface them one at a time (or, worse,
silently encode broken bytecode):

- **Branch target bounds**: `gpl jump` / `gpl local sub` /
  `gpl if` / `gpl while` / `gpl else` / `gpl wend` /
  `gpl ifcompare` whose literal target falls outside
  `[0, total_bytes)`. `gpl global sub` is skipped (cross-chunk
  by design).
- **`Immediate14` overflow**: the on-wire encoding is actually
  15 bits (`(cop & 0x7F) << 8 | b`), ceiling 32767. Hand-edits
  that push beyond that are flagged.
- **`RetVal` nesting depth**: capped at
  `gpl_disasm::MAX_RETVAL_DEPTH` (= 4). Deeper hand-built
  programs are guaranteed unencodable.

CLI:

```text
gpl-asm --validate-only chunk.asm   # exit 0 = clean, 1 = errors
gpl-asm --no-validate chunk.asm     # bypass; encode anyway
gpl-asm chunk.asm                   # default: validate then encode
```

Default mode runs the validator before every encode and aborts
the run if any error fires, so a broken listing doesn't write
broken bytecode to disk. The corpus passes 600 / 600 with zero
false positives (`tests/validate_smoke.rs::corpus_chunks_validate_clean`).

### Out of scope (queued for v0.6.0+)

- Macros / forward-reference convenience syntax beyond `label:`.
- Auto-resolution of `gpl_search` raw_tail in user-authored text.
- Patch-manifest tooling (lives alongside `ds1-patch/` /
  `ds2-patch/` Phase 6+ work, not in `gpl-asm` itself).
- Cross-instruction sanity (e.g. `gpl if` paired with
  `gpl endif`); needs CFG-level reasoning the validator
  doesn't have.

## What `gpl-asm v0.4.0` ships

Two pieces for the modder-authoring workflow:

### Label-relative `Editor` API

`Editor::from_result` now seeds a `name -> offset` label map
from the source `DisasmResult.cfg.labels`. New methods:

- `Editor::label_offset(name)` — current offset of a label.
- `Editor::insert_before_label(name, instr)` — splice before
  whatever instruction the label points at.
- `Editor::delete_at_label(name)` — delete the instruction
  labelled `name`.
- `Editor::replace_at_label(name, with)` — swap the labelled
  instruction.
- `Editor::add_label(name, at_offset)` — pin a user-chosen
  name to an existing instruction. Persists through edits.

The label map shifts through every edit: a label that was at
offset N before an insert at offset M (M <= N) ends up at
offset `N + insert_length`. This lets a patch script reference
the same label across multiple edits without manual tracking.

### Parser accepts user-chosen label names

`label_0xNNNN:` and `entry_0xNNNN:` declarations still work
exactly as before. v0.4.0 additionally accepts any
ASCII-identifier-shaped name (letter or underscore head, then
alphanumerics or underscores), and resolves branch params that
name those labels. The label's value is the byte offset of the
next instruction line in the source.

Names that collide with operator words (`and`, `or`),
keyword tokens (`NAME`, `RETVAL`, `COMPLEX`,
`INTRODUCE`, `UNCOMPRESSED`, `ACCM_ERROR`, `IMMED_WORD_UNIMPL`),
or variable shorts (`GNUM`, `LSTR`, ...) are rejected at
label-declaration time so they don't shadow real tokens during
param parsing.

### Patch-author workflow

```text
gpl-disasm GPLDATA.GFF --kind GPL --id 199 --no-syms -o chunk.asm
# Edit chunk.asm: add a `bug_fix:` label, write `gpl if bug_fix`
# wherever you want to skip a bad block.
gpl-asm chunk.asm -o chunk.bin
gff-cat replace GPLDATA.GFF GPL 199 chunk.bin -o GPLDATA.patched.GFF
```

The library `Editor` is the programmatic equivalent for
scripted patches.

### Out of scope (queued for v0.5.0)

- Macros / forward-reference convenience syntax beyond `label:`.
- Auto-resolution of `gpl_search` raw_tail in user-authored text
  (current modder has to compose the hex by hand or paraphrase
  via JSON).
- Patch-manifest tooling (will live alongside the `ds1-patch/` /
  `ds2-patch/` Phase 6+ work, not in `gpl-asm` itself).

## What `gpl-asm v0.3.0` ships

**Structural edits.** The `Editor` API in
[`gpl_asm::edit`](src/edit.rs) wraps a `DisasmResult` and exposes:

- `insert_instruction(before_offset, instr)` — splice an
  instruction in. Subsequent offsets shift by the new
  instruction's encoded length. **Branch targets `>=
  before_offset` shift by the same amount.**
- `delete_instruction(at_offset)` — remove an instruction.
  Subsequent offsets and branch targets `> at_offset` shift
  down.
- `replace_instruction(at_offset, with)` — swap one instruction
  for another. `delta = new.length - old.length`; subsequent
  offsets and branch targets shift by `delta`.
- `Editor::make_instruction(opcode, params, raw_tail)` and
  `make_simple(opcode)` — build new instructions with their
  length computed via the encoder.

Branch instructions handled for retargeting: `gpl jump`
(0x12), `gpl local sub` (0x13), `gpl ifcompare` (0x27), `gpl
if` (0x3E), `gpl else` (0x3F), `gpl while` (0x63), `gpl wend`
(0x64). `gpl global sub` (0x14) targets a chunk in another
GPL file, so its parameters aren't shifted.

**Workflow** (patch authoring):

```rust
use gpl_asm::{Editor, encode};
use gpl_disasm::disassemble;

let result = disassemble(&chunk_bytes);
let mut ed = Editor::from_result(result);
let endif = Editor::make_simple(0x67)?;
ed.insert_instruction(0x0011, endif)?;
let new_bytes = encode(&ed.into_result())?;
```

After edit, the encoded bytes can be written back via
`gff-edit`'s replace-chunk pipeline (`gff-cat replace`) — same
shape as the v1 darkfix patch authoring story in `spec.md` §3.1.

Out of scope for v0.3.0:
- Label-relative inserts (modder says "insert before
  label_0x0011"): for now, look up the label's offset manually
  and call `insert_instruction(offset, ...)`. v0.4.0 will add a
  label-relative API.
- Inserting Search-shaped instructions with raw_tail: the
  encoder accepts them, but constructing valid raw_tail bytes
  is the modder's responsibility (no DSL for it yet).

## What `gpl-asm v0.2.1` ships

**Full labelled-text round-trip.** Closes the v0.2.0 gaps:

- **Label declarations**: `label_0xNNNN:` and
  `entry_0xNNNN[ (function_name)]:` lines are pre-scanned into
  a `name -> offset` map. Branch params that name a label
  resolve through the map to an `Immediate14` token with the
  matching offset.
- **`; raw_tail=HEX` trailers**: the per-instruction trailer
  emitted by `gpl-disasm` v0.4.6 (for top-level `gpl_search`)
  is parsed into `Instruction.raw_tail`.
- **Inner `raw_tail` inside RETVAL**: the
  ` raw_tail=HEX` sentinel `gpl-disasm` v0.4.6 emits inside
  `RETVAL(...)` for the nested-Search case is parsed into
  `Expression::RetVal::inner_raw_tail`.
- **Sign-vs-op heuristic for `-`** is now state-aware: after a
  value-producing token, `-DIGIT` is an op followed by a
  positive value; only at the start of an expression (or after
  an open-paren / op) does `-DIGIT` form a signed literal. This
  matches the renderer's both spaced and unspaced forms.

**Corpus result** (GOG 1.10 DS1+DS2 GPLDATA, 600 aligned
chunks): `bytes -> disassemble -> render labelled text ->
parse -> encode` is byte-identical for **600 / 600**.

## What `gpl-asm v0.2.0` ships

**Text-listing parser.** Consume `gpl-disasm`'s human-readable
listing as input, alongside the existing `--json` path. Modder
workflow:

```sh
gpl-disasm GPLDATA.GFF --kind GPL --id 199 --no-labels --no-syms \
    -o chunk.asm
# Edit chunk.asm in your editor.
gpl-asm chunk.asm -o chunk.bin
```

The parser is **strict about format** — it accepts exactly the
output `gpl-disasm` produces with `--no-labels`. Future v0.2.x
releases will resolve label-form branch targets so modders can
work with the labelled listing too.

**Corpus** (GOG 1.10 DS1+DS2 GPLDATA, 600 aligned chunks):
v0.2.0 hit **456 / 456 non-Search chunks** byte-identical
through `bytes -> disasm --no-labels -> text -> parse ->
encode`. The 144 Search-containing chunks were skipped because
the text format didn't preserve their `raw_tail` side bytes.
v0.2.1 closes that gap with the `; raw_tail=HEX` trailer
(see below); the labelled form hits 600 / 600.

CLI:

| Input | How it's detected |
|-------|-------------------|
| `chunk.json` | extension `.json` |
| `chunk.asm` / `chunk.txt` / any other | text by default |
| any extension | `--json` or `--text` overrides |

`--all-from <dir>` works for both: each file is parsed using
its own extension-detected mode.

## What `gpl-asm v0.1.1` ships

**Full 600/600 corpus round-trip.** Closes the v0.1.0 gap by
consuming the `raw_tail` / `inner_raw_tail` preservation fields
that `gpl-disasm` v0.4.5 added on `Instruction` and
`Expression::RetVal`.

| Game | Chunks | Round-tripped | Skipped |
|------|-------:|---------------:|--------:|
| DS1+DS2 GPLDATA | 600 | **600** | 0 |

For `gpl_search` (0x33) at the top level: the encoder writes
`opcode + encode(param[0]) + raw_tail`. For `gpl_search` nested
inside `GPL_RETVAL`: same pattern, using `inner_raw_tail`. The
two cases together cover the 144 chunks v0.1.0 had to skip.

No CLI or public-API changes; v0.1.0 callers don't have to do
anything to pick up the broader coverage.

## What `gpl-asm v0.1.0` ships

The **round-trip reassembler**. Given a `DisasmResult` parsed
from `gpl-disasm --json`, [`encode`] returns the original chunk
bytes. The load-bearing test is the same shape as `gff-edit`'s
writer corpus test: every aligned GPL/MAS chunk in DS1+DS2
GPLDATA must round-trip byte-for-byte through `disassemble ->
encode`.

**Corpus result** (GOG 1.10):

| Game | Chunks | Round-tripped | Search-skipped |
|------|-------:|---------------:|----------------:|
| DS1+DS2 GPLDATA | 600 | **456** | 144 |

100% of non-`gpl_search`-containing chunks round-trip
byte-identical. The 144 skipped chunks contain `gpl_search`
(0x33) either at the top level or nested inside `GPL_RETVAL`;
that opcode has side bytes (a 2-byte range argument plus
per-loop-iteration field / type tag bytes) that `gpl-disasm`'s
current IR doesn't preserve. v0.1.1 closes the gap by consuming
the new `raw_tail` field on `Instruction` and
`Expression::RetVal::inner_raw_tail`.

## Usage

```sh
# Round-trip one chunk:
gpl-disasm GPLDATA.GFF --kind GPL --id 199 --json -o chunk.json
gpl-asm chunk.json -o chunk.bin

# Bulk re-encode every chunk gpl-disasm produced:
gpl-disasm GPLDATA.GFF --all -o disasm/ --json
gpl-asm --all-from disasm/ -o asm/
```

## Library

```rust
use gpl_disasm::{disassemble, DisasmResult};
use gpl_asm::encode;

let chunk_bytes: &[u8] = /* ... */;
let result: DisasmResult = disassemble(chunk_bytes);
assert!(result.aligned);
let encoded = encode(&result).unwrap();
assert_eq!(encoded, chunk_bytes);
```

The library exposes one top-level `encode` plus
`encode_instruction` and `encode_expression` for piecewise use,
and `pack_compressed_string` for the 7-bit packed string
encoder.

## How it works

For each instruction, the encoder writes:

1. The opcode byte.
2. Parameters according to the opcode's `ParamSpec`
   (re-exported from `gpl-disasm`'s `PARAM_COUNTS` table):
   - `Fixed(n)`: encode each of the `n` parameters as a stream
     of `Expression` tokens.
   - `Log` (0x2C): one packed-string payload.
   - `LoadVar` (0x16): one expression + a 1-byte datatype marker
     + (simple-var id-bytes | access-complex body).
   - `Menu` (0x48): one expression + N x 3 entries + 0x4A
     terminator.
   - `SetRecord` (0x40): an access-complex body + one expression.
   - `Search` (0x33): rejected (side bytes not in v0.1.0 IR).
   - `Custom`: rejected.

Per `Expression` token:

- `Immediate14`: 2 bytes BE (top bit clear on byte 0).
- `ImmediateByte`: `0x8F | 0x80` marker + 1 signed byte.
- `ImmediateBigNum`: `0x8B | 0x80` marker + 4 bytes (hi:u16 BE,
  lo:u16 BE; value = `(hi as i32) << 16 + lo`).
- `ImmediateName`: `0x91 | 0x80` marker + 2 bytes BE
  (`h = (-value) as u16`).
- `ImmediateString`: `0x92 | 0x80` marker + sub-type marker
  (`0x01` / `0x02` / `0x05`) + optional payload (the 7-bit
  packed bitstream terminated by `0x03`).
- `Variable`: `0x80 | extended_bit | var_kind_tag` dispatch byte
  + 1 or 2 bytes for the id.
- `BinaryOp`: 1 byte `0xD1..=0xDF`.
- `OpenParen` / `CloseParen`: `0xE2` / `0xE1`.
- `RetVal`: `0x8C` marker + inner opcode byte + recursive params
  encoded per the inner opcode's `ParamSpec` (Fixed only for
  v0.1.0; Search-inner triggers `UnsupportedOpcode`).
- `ComplexAccess`: dispatch byte `(tag & 0x7F) | 0x80` + word
  `obj_name` BE + `depth` byte + `depth` element bytes.
- `AccmError` / `ImmediWordUnimplemented` / `Unknown`: defensive
  encoders; `Unknown` errors because it only appears in
  best-effort disassemblies (which `encode` already rejects).

The 7-bit packed-string encoder (`pack_compressed_string`)
emits 7 bits per character MSB-first into a bitstream, appends
the `0x03` terminator (also 7 bits), and left-justifies any
trailing partial bits into a final byte. Inverse of
`gpl-disasm`'s `decode_compressed`. The decoder was made
lossless in `gpl-disasm` v0.4.3 specifically so this encoder
can round-trip non-printable formatting codes (`\t`, `\n`, ...)
that the original chunks ship inside dialog strings.

## Roadmap

- **v0.1.1**: preservation field for `gpl_search` side bytes;
  JSON-mode corpus round-trip 600/600.
- **v0.2.0**: text-listing parser for the `--no-labels` form;
  text-mode round-trip 456/456 non-Search.
- **v0.2.1**: labelled form support + `raw_tail` trailers.
  600/600 byte-identical text round-trip.
- **v0.3.0**: structural edits. Insert / delete / replace
  instructions with automatic branch-target recompute.
- **v0.4.0** (this release): label-relative editing API
  (`insert_before_label` etc.) and parser support for
  user-chosen label names.
- **v0.5.0**: authoring conveniences (macros, forward-ref
  syntax, `gpl_search` raw_tail composition).
- **v0.3.0**: structural edits. `insert_instruction(at, instr)`
  / `delete_instruction(at, length)` APIs that recompute branch
  targets and labels.
- **v0.4.0**: high-level authoring DSL with named labels,
  comments, macros, and forward references.

## Build

Workspace member of the OpenDS toolkit:

```sh
cargo build --release -p gpl-asm
cargo test --release -p gpl-asm
```

## Credits

The encoder is the formal inverse of `gpl-disasm`'s decoder; all
format details ultimately trace back to `dsoageofheroes/libgff`
(MIT) and `dsoageofheroes/soloscuro-archive` `gpl-string.c`
(MIT) which `gpl-disasm` ports from. See
[`../../CREDITS.md`](../../CREDITS.md) for per-feature attribution.
