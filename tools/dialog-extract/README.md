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

## What v0.3.0 ships

**CFG-aware structured `dialog_tree`** alongside the existing
flat `strings` list. Per chunk, one subtree per entry point.
Each subtree is a recursive structure of:

- `block` nodes — straight-line instruction runs; carry their
  `lines` (the same string records v0.2.0 emits), `gpl_refs`
  (`local sub` / `global sub` call sites), a `speaker_state_entry`
  snapshot (observed `gpl setother` / `gpl setthing` state at
  block entry), and one or more `children` for the block's
  terminator.
- `if` nodes — synthesised from `gpl if` (0x3E) conditionals.
  Have `then` and `else` subtrees plus a `join_offset` (the
  matching endif). If-with-else is detected by checking whether
  the then-path ends with a `gpl else` terminator.
- `ifcompare` nodes — `gpl ifcompare` (0x27) switch-style
  branches. Carry `case_value` (the comparison literal) plus
  `match` and `miss` subtrees.
- `loop` nodes — `gpl while` (0x63) bodies. Single `body`
  subtree; the backward `gpl wend` edge is implicit.
- `goto` / `revisit` / `depth_cut` markers — explicit cut
  points where the walk stops (a `gpl jump`, a previously-
  visited block in a DAG-shaped tree, or the MAX_TREE_DEPTH=32
  limit).

Each chunk surfaces both **declared** entries (chunk start and
every `gpl local sub` target) and **discovered** entries
(locally-unreachable block leaders, almost always
externally-called functions invoked via `gpl global sub` from
another chunk). The discovered pass ensures every block leader's
dialog is visible even without inter-chunk CFG (which is
v0.4.1 work in gpl-disasm).

**Corpus**: 600 / 600 DS1+DS2 chunks build a tree containing
46,611 line records across 4,229 declared + 15,027 discovered
entry-point walks. 7,438 `revisit` cuts (shared sub-paths). 0
invariant violations (every line's offset resolves to an
instruction in its chunk; every gpl_ref's `at` resolves; every
subtree terminates).

Speaker-state tracking is **deliberately heuristic**: we only
track `gpl setother` (0x41) and `gpl setthing` (0x49) — the two
confirmed speaker-mutators — and emit the snapshot of which
NPC was most recently set in each slot. We do NOT claim a line
is "spoken by" anyone; the snapshot is the engine context at
the time of the line. v0.4.0+ work could expand the speaker
opcodes list and add `gpl setpov` / `gpl setactive` if
identified.

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
  source map; defer to v0.4.0+.
- **gpl-disasm best-effort handling**: when the disassembler
  marks an instruction `best_effort` (RetVal, Complex, etc.),
  its params may be incomplete. The extractor reports the chunk
  as `aligned: false` in the per-chunk JSON; consumers can
  filter on that field. Aligned chunks always get a
  `dialog_tree`; non-aligned chunks get an empty one.
- **Resolved speaker attribution**: v0.3.0 surfaces engine
  context (which NPC was last set as "other" / "thing") but
  does NOT claim who's speaking. Resolving "X says Y" needs a
  richer engine state model. v0.4.0+ candidate.
- **Inter-chunk tree walking**: `gpl global sub` call sites are
  recorded as `gpl_refs` entries but not followed across chunks.
  Inter-chunk CFG is `gpl-disasm v0.4.1`; once that lands,
  dialog-extract could weave full multi-chunk dialog flows.
