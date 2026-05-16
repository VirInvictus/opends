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
- **v0.2.1** (this release): labelled form support
  (`label_0x...:` / `entry_0x...:` declarations + label-form
  branch params) and `raw_tail` trailer parsing. Full corpus
  round-trip 600/600.
- **v0.3.0**: structural edits. `insert_instruction(at, instr)`
  / `delete_instruction(at, length)` API that recomputes branch
  targets and labels.
- **v0.4.0**: high-level authoring DSL with named labels,
  comments, macros, and forward references.
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
