# dialog-extract

Pull GPL inline strings out of a GFF file as JSON. Modder-facing
tool for browsing NPC dialog, prompts, and other strings embedded
directly in `GPL ` and `MAS ` bytecode chunks.

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+; `gff-cat` (from `gff-edit`) on `$PATH`
  or at `../../target/release/gff-cat` relative to this script.
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## What v0.1.0 does

v0.1.0 is a **heuristic** byte-scan. Walks every `GPL ` and `MAS `
chunk in the input GFF, scans for the `GPL_IMMED_STRING` marker
byte (`0x92` = `GPL_IMMED_STRING | 0x80` per libgff
`include/gpl/var.h`), then for each marker checks the following
type byte:

| Type | Meaning |
|------|---------|
| `0x01` | INTRODUCE: placeholder for active character name |
| `0x02` | UNCOMPRESSED: not yet supported by soloscuro-archive; treated as placeholder |
| `0x05` | COMPRESSED: 7-bit packed ASCII terminated by `0x03` |

Strings of type `0x05` are decoded via a Python port of
soloscuro-archive's `read_compressed`
(`src/gpl/gpl-string.c`, MIT-licensed, Paul E. West et al.).

## Limitations of the heuristic

- **False positives possible**. Any parameter byte that happens
  to equal `0x92` followed by `0x01`/`0x02`/`0x05` will be
  decoded as if it were a string. Garbled outputs (mostly spaces
  due to the printable-replacement rule) are filtered by a
  minimum-length threshold but some noise still slips through.
- **False negatives possible**. Strings referenced by id
  (`gpl_get_gstr(id)`, `gpl_get_lstr(id)`) load from external
  `TEXT` chunks rather than being inlined; v0.1.0 does not
  resolve those references.

## v0.2.0 plan

When `gpl-disasm` v0.2.0 ships (proper instruction-boundary
decoding via libgff's `gpl_read_number`), this tool will be
upgraded to consume `gpl-disasm --json`. The heuristic byte-scan
will be replaced by an instruction-aware extractor, eliminating
both false positives (byte boundaries are real) and false
negatives (`gpl_print_string` calls with text-id references
become resolvable).

## Usage

```sh
python3 dialog-extract.py /path/to/GPLDATA.GFF
python3 dialog-extract.py /path/to/GPLDATA.GFF --pretty -o dialog.json
python3 dialog-extract.py /path/to/GPLDATA.GFF --grep 'Garn'
```

`--grep <regex>` filters output to only chunks whose strings
match the pattern. Useful for finding chunks by NPC name or
dialog snippet.

JSON shape:

```json
{
  "tool": "dialog-extract",
  "version": "0.1.0",
  "source": "...",
  "chunk_count": 42,
  "string_count": 137,
  "chunks": [
    {
      "chunk": "GPL-7",
      "kind": "GPL ",
      "id": 7,
      "string_count": 3,
      "strings": [
        { "offset": 12, "type": "COMPRESSED", "string": "Welcome..." }
      ]
    }
  ]
}
```

## Implementation note

The script shells out to `gff-cat extract --all` to dump every
chunk into a temp directory, then reads back only `GPL-*.bin` and
`MAS-*.bin` files for scanning. `GPLDATA.GFF` uses segmented
chunks for GPL/MAS types, and re-implementing segmented chunk
resolution in Python would duplicate `gff-edit`'s work; the
subprocess hop is much cheaper than that duplication.
