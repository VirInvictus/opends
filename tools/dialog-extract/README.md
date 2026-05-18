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

## What v0.6.0 ships

**CFG-distance-ordered `possible_writers`.** v0.5.0 attached
the array but it was unordered; v0.6.0 sorts it by graph
distance so the closest writer comes first, making the
human-or-tool reader's first guess the most likely one.

### Each writer carries a `distance`

```json
{
  "source": "text:lstring",
  "text_id": 0,
  "unresolved": true,
  "possible_writers": [
    {"chunk": "GPL-166", "kind": "GPL ", "id": 166,
     "offset": 412, "source": "inline",
     "value": "  Welcome, traveller.", "sub_type": "compressed",
     "distance": 0},
    {"chunk": "GPL-100", "kind": "GPL ", "id": 100,
     "offset": 18,  "source": "inline",
     "value": "  Default greeting.", "sub_type": "compressed",
     "distance": 1}
  ],
  "possible_writers_filter": "callgraph-reachable"
}
```

- `distance: 0` = writer is in the same chunk as the read.
- `distance: 1` = writer's chunk is an immediate
  `gpl global sub` caller of the read site.
- `distance: N` = N hops on the reverse callgraph.
- `distance: null` = no static path (the global-fallback
  case; writers exist somewhere but the BFS doesn't connect
  them to the read site).

Records sort ascending by `(distance, kind, id, offset)`;
`null` distances sort last.

### `--quick-resolve`

```sh
dialog-extract DS1 GPLDATA.GFF --text-source RESOURCE.GFF --quick-resolve
```

Restricts each `possible_writers` list to `distance <= 1`
(same-chunk + direct callers). Useful for the common case
where the LSTR is set by the immediate caller and the
longer ancestor tail is noise. The `possible_writers_filter`
label becomes `callgraph-reachable+quick-resolve` (or the
matching fallback variant). LSTR reads whose only candidates
were further-away callers move from `possible_resolved` to
`no_writers` in `lstr_stats` under this mode.

### Corpus signal (DS1 `GPLDATA.GFF`)

Without `--quick-resolve`: 255 LSTR reads, 230 resolved
exactly (90.2%), 25 via `possible_writers`. Distance
histogram across the writer records on those 25 reads:

| distance | count |
|---------:|------:|
| 0        |    31 |
| `null` (global-fallback) | 68 |

The bimodal distribution surfaces a real corpus property:
when the static callgraph *does* connect a writer to a
read, that writer tends to be in the same chunk; the
common cross-chunk caller-writes-then-callee-reads idiom
is dominated by *exact* resolution (the path-aware tracker
in v0.4.0 catches those), leaving only same-chunk and
truly-disconnected writers behind. `--quick-resolve` drops
to 23 reads with writers (the 2 global-fallback cases
become `no_writers`).

## What v0.5.0 ships

The **LSTR tail closer**. v0.4.0 left 32 LSTR reads
unresolved (~9% of LSTR refs, ~0.07% of all strings) because
the slots were populated by upstream callers in different
chunks. v0.5.0 surfaces every statically-reachable writer for
those reads, narrowed by the inter-chunk callgraph.

### `possible_writers` array

Every unresolved `text:lstring` record now carries:

```json
{
  "source": "text:lstring",
  "text_id": 0,
  "value": null,
  "unresolved": true,
  "possible_writers": [
    {"chunk": "GPL-116", "kind": "GPL ", "id": 116,
     "offset": 155, "source": "inline",
     "value": "  Where would I find this Mikquetzl?",
     "sub_type": "compressed"},
    {"chunk": "GPL-118", "kind": "GPL ", "id": 118,
     "offset": 859, "source": "inline",
     "value": "  Okay, I'm leaving.",
     "sub_type": "compressed"}
  ],
  "possible_writers_filter": "callgraph-reachable"
}
```

The `source` field on each writer mirrors the original
`gpl_string_copy` payload kind: `inline` (the literal value
is carried verbatim), `gstring` (a `text_id` against the
sibling resource GFF), `lstring` (another LSTR slot to walk
back through), or `computed` (anything else; accumulator
math, complex-record access, etc.; opaque).

### Callgraph-narrowed by default

The writer set is filtered through the `gpl global sub`
callgraph (gpl-disasm's `cross_chunk_calls`): only writers
in chunks that statically reach the read site are emitted.
The same-chunk case is always included (the linear flat-scan
tracker may miss a writer via a CFG quirk). When the
callgraph leaves zero matches, v0.5.0 falls back to the
global writer set so the user always sees *something*.

`possible_writers_filter` reports which path applied:
`callgraph-reachable` (the narrow set), `global-fallback`
(callgraph empty, returning all writers), or `global` (no
callgraph available; shouldn't happen with the standard
flow).

### Corpus numbers

| Game | LSTR reads | Exact resolved | possible_writers | No writers |
|------|------------|----------------|------------------|------------|
| DS1  | 255        | 230 (90.2%)    | 25               | 0          |
| DS2  | 99         | 92 (92.9%)     | 7                | 0          |
| **Total** | **354** | **322 (91.0%)** | **32**       | **0**      |

The `no writers` column is the one that mattered: **zero
LSTR reads across the corpus lack at least one
statically-reachable writer**. Every previously-unresolved
read in v0.4 now surfaces a candidate set. Average set size:
4.0 writers per unresolved read in DS1, 6.7 in DS2 (after
callgraph filtering). Before filtering, the average was ~95
writers per read; the callgraph narrowing is what makes the
output usable.

### New JSON top-level field

`lstr_stats` summary at the top of the output:

```json
"lstr_stats": {
  "total_reads": 255,
  "exact_resolved": 230,
  "possible_resolved": 25,
  "no_writers": 0
}
```

Plus a stderr stats line at end of run:

```text
dialog-extract: 255 LSTR reads, 230 exact (90.2%), 25 via
possible_writers, 0 with no writers
```

### Out of scope (queued for v0.6.0+)

- **Path-aware caller picking**. Today every reachable
  writer goes into `possible_writers`; the user has to pick
  which one fires for a given dynamic call path. A
  CFG-distance-ordered list is the cheap improvement;
  proper symbolic call-path tracing is the deep one.
- **Resolution through `gpl_search` raw_tail rewrites**.
  The 0x33 opcode can mutate LSTR slots indirectly.

## What v0.4.0 ships

Two structural upgrades. The combined effect across the GOG 1.10
corpus is **893 unresolved LSTRING refs (v0.3.0) down to 32
unresolved (v0.4.0), a 96.4% reduction**.

### LSTR slot resolution

The runtime keeps 10 "local string" (`LSTR`) slots
(`MAXLSTRINGS = 10` per libgff `include/gff/str.h`). Scripts
populate the slots via `gpl_string_copy` (0x0A): `param[0]` is
the LSTR destination, `param[1]` is the source (an inline string
in ~96-97% of corpus occurrences). Later instructions like
`gpl_menu` (0x48) and `gpl_print_string` (0x4F) read the slots
back as menu choices, prompts, and screen text.

v0.3.0 surfaced LSTR reads as `unresolved: true`. v0.4.0:

- **Fixes an over-count bug**: v0.3.0 also emitted the `LSTR`
  *destination* of each `gpl_string_copy` as an "unresolved
  LSTRING ref". That's a write target, not a read. Skipped now.
  The flat-`strings` list shrinks by exactly the number of LSTR
  writes (~539 in DS1+DS2 combined).
- **Path-aware LSTR tracking** in the `dialog_tree` walk: each
  CFG path carries a per-slot `{kind, value | text_id |
  source_id, ...}` snapshot updated on every
  `gpl_string_copy` write. At branch points each path receives a
  `dict(lstr_state)` copy. Reads inside string-bearing opcodes
  resolve to the most-recently-written source on the active path.
- **Linear-scan LSTR baseline** for the flat `strings` list:
  a single forward pass over each chunk's instructions builds a
  chunk-level snapshot used when the flat list extracts strings.
  Less accurate than the path-aware tree (~80% vs ~95%) but
  needs no CFG context.
- **Source kinds**:
  - `inline`: param[1] was an immediate literal. Direct
    resolution.
  - `gstring`: param[1] was a `GSTRING[id]` variable. Resolves
    via `--text-source` like a normal GSTRING ref.
  - `lstring`: param[1] was another LSTR slot. Chained
    resolution with cycle protection.
  - `computed`: anything else (accumulator math, record-field
    access). Read resolves to `None` (still flagged
    `unresolved: true`).

Each `block` node in the tree now carries a `lstr_state_entry`
snapshot alongside `speaker_state_entry`, so curators can see
what was in each slot at block entry.

### Inter-chunk dialog tree walking

`gpl global sub` (0x14) calls now expand inline as
`cross_chunk_call` subtrees under the calling block's
`children`, using `gpl-disasm`'s per-chunk `cross_chunk_calls`
metadata (v0.3.0+) and the in-memory chunks index built from
all `GPL ` / `MAS ` chunks in the input GFF.

Each `cross_chunk_call` node carries:

- `at` — call-site offset in the caller.
- `target_chunk` — `"GPL-N"` / `"MAS-N"` shorthand.
- `target_offset`, `target_file_id` — exact destination.
- `target_label` — the callee's entry label (decorated with the
  function name from `gpl-disasm`'s `syms/functions.toml` when
  available).
- `subtree` — the recursive walk of the callee from
  `target_offset`, OR
- `unresolved: true` with a `reason`:
  - `cycle`: the callee is already on the active call chain.
  - `callee_not_loaded`: the callee chunk wasn't in the input
    GFF (calls between separate `*.GFF` files).
  - `callee_unaligned`: the callee disasm failed alignment.
  - `target_offset_not_a_block_leader`: the call points into
    the middle of a function.
  - `depth_cut`: MAX_TREE_DEPTH = 32 hit.

The caller's path-local `lstr_state` flows into the callee
(shallow copy). The engine LSTR table is global, so this is
the truthful semantics. Modifications inside the callee do NOT
propagate back to the caller's continuation: dialog-extract is
not a runtime simulator, and over-claiming would mislead.

**Corpus result**: DS1 expands 889 `cross_chunk_call` nodes (662
resolved + 223 cycle/non-leader/depth markers); DS2 expands
1,014 (806 + 208).

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

In v0.2.0, `LSTRING` references were surfaced but never resolved:
they're per-context strings populated by the engine at runtime
and not present in `--text-source`'s `TEXT` chunks. They appeared
as `unresolved: true` with the `text_id` captured. v0.4.0
resolves them via path-aware LSTR-slot tracking; see the v0.4.0
section above.

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
