# dialog-extract

Pull GPL strings out of a GFF file as JSON. Modder-facing tool
for browsing NPC dialog, prompts, NPC names, and other strings
that appear in `GPL ` and `MAS ` bytecode chunks.

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+; `gpl-disasm` on `$PATH` or at
  `../../target/release/gpl-disasm`. `gff-cat` (from `gff-edit`)
  is required only when `--text-source` is passed. Pin either
  binary explicitly with `--gpl-disasm <path>` / `--gff-cat <path>`.
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## Output formats

`--format` selects the output surface: `json` (default, for
tools), or two human-readable forms.

### `--format transcript`

Per-NPC plain-text listing of every dialog string in source
order. Speaker labels resolved from
`syms/speakers.toml` (curated chunk-id → NPC name; v0.7.0
ships with one verified entry, grows organically).

```sh
python3 dialog-extract.py GPLDATA.GFF --text-source RESOURCE.GFF \
    --format transcript -o ds1-dialog.txt
```

Output:

```
## GPL-1: Iniya
  (DS1 starting cell-block; the imprisoned mage NPC.)

  Iniya: Free! Finally free! I will destroy you all! Ha ha ha!
  Iniya: Please help me. I was betrayed and locked in my own dungeon.
  ...
```

DS1 GPLDATA full transcript: 18349 lines covering 215 chunks /
17699 strings.

### `--format html`

Single-file static HTML browser. Embedded CSS, collapsible
`<details>` per chunk, colour-coded unresolved strings. Drops
on disk; opens directly via `file://` on any browser; no
JavaScript, no external assets.

```sh
python3 dialog-extract.py GPLDATA.GFF --text-source RESOURCE.GFF \
    --format html -o ds1-dialog.html
```

DS1 GPLDATA full output: ~1.9 MB single file. The on-ramp to
the `atlas` tool's dialog browser.

### `syms/speakers.toml`

```toml
[[speaker]]
chunk_id = 1
name = "Iniya"
notes = "DS1 starting cell-block; the imprisoned mage NPC."
```

Curated. Missing rows fall back to `"GPL chunk N"` as the
speaker label; the renderer doesn't invent attribution. Add
rows only after confirming the speaker from the chunk's
dialog content.

### `--format json` (default)

Stays exactly as v0.6.0 for back-compat with downstream
consumers (`opends find`, `opcode-fuzz`). The transcript and
HTML formats are pure read-only derivations of the same
summary tree.

---

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
  "version": "0.7.1",
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

## Limitations and deferred

- **LSTRING resolution for caller-populated slots**: 32 reads
  across the DS1+DS2 corpus (mostly LSTR[0] in DS1 chunks 8,
  166, 174 and DS2 chunks 165, 299, 331) have no upstream write
  inside their own chunk. They're populated by a caller before
  the chunk is invoked, and the v0.4.0 inter-chunk walker passes
  the caller's `lstr_state` into the callee at the call site,
  so they're resolved when the chunk is *reached via the
  expansion*. They show as `unresolved: true` only when extracted
  through a chunk's declared/discovered entry points without a
  caller context. Cross-chunk LSTR liveness analysis is a
  candidate for v0.5.0.
- **gpl-disasm best-effort handling**: when the disassembler
  marks an instruction `best_effort` (RetVal, Complex, etc.),
  its params may be incomplete. The extractor reports the chunk
  as `aligned: false` in the per-chunk JSON; consumers can
  filter on that field. Aligned chunks always get a
  `dialog_tree`; non-aligned chunks get an empty one.
- **Resolved speaker attribution**: v0.3.0+ surfaces engine
  context (which NPC was last set as "other" / "thing") but does
  NOT claim who's speaking. Resolving "X says Y" needs a richer
  engine state model. Candidate for v0.5.0+.
- **Cross-GFF call resolution**: a `gpl global sub` whose
  `file_id` references a chunk not present in the input GFF
  (e.g. calls between separate `*.GFF` files) emits
  `unresolved: "callee_not_loaded"`. Multi-GFF input is a
  candidate for v0.5.0+ if the curation backlog asks for it.
