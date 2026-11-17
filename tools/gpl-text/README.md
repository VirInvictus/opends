# gpl-text

Fixed-length GPL string editing for *Dark Sun: Shattered Lands* and
*Wake of the Ravager*: list the string operands inside a GPL/MAS
chunk with their exact packed spans, validate a same-length
replacement against the format's rules, and splice it in place.

Part of the [OpenDS](../../README.md) community toolkit. The
editing rules are a port of TimQuester's DarkSunTools
`GPLDocument` validate/apply layer (Apache-2.0; credited in
[`../../CREDITS.md`](../../CREDITS.md)): same character count
implies the same packed byte count, only 7-bit symbols are
representable, and the 0x03 terminator may never appear in text.
Length changes are refused by design -- a length-changing edit is
a `gpl-asm` detour job (see
[`../../docs/detour-repairs.md`](../../docs/detour-repairs.md)),
not a string edit.

## Usage

List the strings of a chunk:

```sh
gpl-text list /path/to/GPLDATA.GFF --kind GPL --id 141
#0    offset 0x0201 packed  55B chars 61 Compressed "Give us a good show -- draw the battle out enough to make it "
...
```

Edit one string (exactly the original's character count):

```sh
gpl-text edit /path/to/GPLDATA.GFF --kind GPL --id 141 \
  --index 4 --text "I see you made it. Well, back to the 'pens until the next bout!"
```

`edit` validates before writing (character count, 7-bit, no
terminator), splices the repacked payload at the recorded offset,
and writes the GFF in place. Chunks whose walk is untrusted (a
best-effort instruction such as `gpl menu`, after which spans
would be mislocated) list only the strings before that point and
print a warning.

## Tests

```sh
cargo test -p gpl-text
```

Unit tests cover the fixed-length validation refusals, the splice
round-trip, and disassembler re-reading of the patched chunk.
