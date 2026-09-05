# gpl-asm

Reassembler for SSI's **GPL** (Game Programming Language)
bytecode, the embedded scripting language inside `GPL ` and
`MAS ` chunks. Takes the output of `gpl-disasm --json` and emits
byte-identical bytecode. The inverse of `gpl-disasm`'s decoder.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Depends on `gpl-disasm` for the [`DisasmResult`] type and its
`Deserialize` impls, so this crate consumes the same JSON the
disassembler emits.

## Patch scripts (`--patch`)

Patch scripts address their targets relative to labels or
curated names, never hand-counted bytes.

```toml
[[edit]]
at = "label_0x0042 + 3"      # or: at = "iniya_first_meeting + 3"
bytes_old = "3a"             # fingerprint check, still mandatory
bytes_new = "3b"
reason = "example: retarget the immediate after the label"
```

- `at` takes `"<base>"` or `"<base> + N"` (N decimal or `0x` hex).
  The base is either a `label_0xNNNN` / `entry_0xNNNN` block-leader
  label, or a name resolved from `syms/functions.toml` (the
  `gpl-disasm` catalogue; `--syms <dir>` overrides the default
  workspace lookup, `--no-syms` disables it).
- The resolver disassembles the target chunk and requires the base
  to be a real block leader **in that chunk**, so a patch cannot
  silently address into the wrong chunk. An ambiguous name (two
  catalogue rows) is a hard error naming the candidates.
- Exactly one of `at` / `at_offset` per edit; absolute byte
  offsets keep working unchanged, and the `bytes_old` fingerprint
  stays mandatory for both.


## Usage

```sh
gpl-asm <input> [-o <output>]           # assemble text or JSON to bytecode
gpl-asm --patch fix.patch chunk.bin -o new.bin   # apply a patch script
gpl-asm --patch fix.patch chunk.bin --dry-run    # validate without writing
```

`--dry-run` validates every edit in the patch script (fingerprint
check, address resolution) and prints `dry-run: N edit(s) would
apply cleanly` without writing any output.

### Preprocessor directives

`@include <file>` pastes another listing's contents at the
directive's position (nested includes supported, depth-limited).
Paths are relative to the including file. Shipped with the
v0.7.0 text-parser rewrite.

### Symbol catalogue lookup

`--syms <dir>` overrides the default symbol-catalogue directory
(walked up from the binary to `tools/gpl-disasm/syms/`; silently
loads nothing if absent). `--no-syms` disables the lookup
entirely.

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
- `ImmediateByte`: `0x8F` (bit 7 already set) marker + 1 signed byte.
- `ImmediateBigNum`: `0x8B` (bit 7 already set) marker + 4 bytes (hi:u16 BE,
  lo:u16 BE; value = `((hi as i32) << 16) + lo`).
- `ImmediateName`: `0x91` (bit 7 already set) marker + 2 bytes BE
  (`h = (-value) as u16`).
- `ImmediateString`: `0x92` (bit 7 already set) marker + sub-type marker
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
