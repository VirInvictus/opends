# dialog-extract

Pull GPL strings out of a GFF file as JSON. Modder-facing tool
for browsing NPC dialog, prompts, NPC names, and other strings
that appear in `GPL ` and `MAS ` bytecode chunks.

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+; `gpl-disasm` (from `gpl-disasm`
  v0.2.0+) on `$PATH` or at `../../target/release/gpl-disasm`.
  `gff-cat` (from `gff-edit`) is required only when
  `--text-source` is passed.
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## What v0.2.0 ships

v0.2.0 is an **instruction-aware** extractor built on
`gpl-disasm --json` (gpl-disasm v0.2.0+). It shells out to the
disassembler, walks every decoded `Instruction`, and emits one
record per string-bearing parameter. The heuristic byte-scan
that v0.1.0 used is gone: byte boundaries are real, false
positives are eliminated, and string sources are correctly
identified per opcode.

Strings appear in two forms:

1. **Inline literals**. The disassembler decodes these from the
   7-bit packed-string format directly; we just lift the value.
2. **Text-id references**. `gpl_print_string` and friends often
   take a `GSTRING[id]` reference rather than an inline string;
   the id resolves against a `TEXT` chunk in a sibling GFF
   (typically `RESOURCE.GFF`). Pass `--text-source <RESOURCE.GFF>`
   to resolve them. Without the flag, these are emitted as
   `unresolved: true` so you still see where they live.

`LSTRING` references are surfaced but never resolved against
`--text-source`: they're per-context strings populated by the
engine at runtime from sources we don't yet model (per-region
GFFs, dynamic computations). They appear as `unresolved: true`
with the `text_id` captured.

Opcodes the extractor scans:

| Opcode | Mnemonic            | What it carries           |
|--------|---------------------|---------------------------|
| `0x2C` | `gpl log`           | inline packed string      |
| `0x42` | `gpl input string`  | prompt (1 param)          |
| `0x48` | `gpl menu`          | menu name + entry texts   |
| `0x4F` | `gpl print string`  | style + text (2 params)   |
| `0x5A` | `gpl string compare`| 2 params                  |
| `0x0A` | `gpl string copy`   | src + dst (2 params)      |

## Usage

```sh
# All inline strings, no text-id resolution:
python3 dialog-extract.py /path/to/GPLDATA.GFF

# With text-id resolution against RESOURCE.GFF (recommended):
python3 dialog-extract.py /path/to/GPLDATA.GFF \
    --text-source /path/to/RESOURCE.GFF -o dialog.json --pretty

# Find all chunks that reference an NPC by name:
python3 dialog-extract.py /path/to/GPLDATA.GFF \
    --text-source /path/to/RESOURCE.GFF --grep '^Garn$'
```

`--grep <regex>` filters output to chunks whose strings match
the pattern. Useful for finding chunks by NPC name or dialog
snippet.

## Output shape

```json
{
  "tool": "dialog-extract",
  "version": "0.2.0",
  "source": "/path/to/GPLDATA.GFF",
  "method": "gpl-disasm --json consumer",
  "text_source": "/path/to/RESOURCE.GFF",
  "text_chunk_count": 60,
  "chunk_count": 215,
  "string_count": 17560,
  "unresolved_count": 471,
  "chunks": [
    {
      "chunk": "GPL-1",
      "kind": "GPL ",
      "id": 1,
      "aligned": false,
      "string_count": 109,
      "strings": [
        {
          "offset": 23,
          "opcode": 79,
          "opcode_name": "gpl print string",
          "source": "inline",
          "sub_type": "compressed",
          "value": "Free! Finally free! I will destroy you all!..."
        },
        {
          "offset": 138,
          "opcode": 79,
          "opcode_name": "gpl print string",
          "source": "text:gstring",
          "text_id": 2,
          "value": "Dag"
        },
        {
          "offset": 841,
          "opcode": 79,
          "opcode_name": "gpl print string",
          "source": "text:lstring",
          "text_id": 32774,
          "value": null,
          "unresolved": true
        }
      ]
    }
  ]
}
```

## Empirical results

Running against the GOG 1.10 release:

| Game | v0.1.0 strings | v0.2.0 strings | Notable wins |
|------|----------------|----------------|--------------|
| DS1  | 13,938         | 17,560         | +3,468 gstring refs ("Garn", "Dag", "Halton", etc.) |
| DS2  | 22,431         | 27,857         | +5,755 gstring refs |
| Combined | 36,369     | **45,417**     | NPC names now surface, no false positives |

The v0.1.0 inline count was higher (~14k DS1, ~22k DS2) than
v0.2.0's because the heuristic counted misaligned-byte matches
that decoded as garbage; v0.2.0's instruction-aware path
eliminates those, while picking up far more legitimate strings
via text-id resolution.

## Implementation note

The script shells out to `gpl-disasm --all -o tmpdir --json` to
produce a per-chunk JSON file for every `GPL ` and `MAS ` chunk
in the input. We then load each JSON file and walk the
`instructions` array. With `--text-source` we additionally shell
out to `gff-cat extract --all` against the sibling GFF to load
its `TEXT` chunks for resolution. Both subprocess hops are
cheaper than reimplementing the GFF parser or the GPL decoder
in Python.

## What's deferred

- **LSTRING resolution**: needs a per-region or per-script text
  source map; defer to v0.3.0+.
- **gpl-disasm best-effort handling**: when the disassembler
  marks an instruction `best_effort` (RetVal, Complex, etc.),
  its params may be incomplete. The extractor reports the chunk
  as `aligned: false` in the per-chunk JSON; consumers can
  filter on that field.
- **Structured dialog trees**: the roadmap's v0.3.0 plan
  (`{speaker, lines, branches, gpl_refs}`). Needs control-flow
  analysis from `gpl-disasm v0.3.0`.
