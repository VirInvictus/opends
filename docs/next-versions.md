% next-versions: sprint plan

The human-friendliness pivot sprint. Refreshed after the
10-tool deepening sprint shipped seven of ten ships
(verify-install / gff-edit / image-extract / region-render /
dialog-extract / gpl-disasm / gpl-asm; see `pick-it-up.md`
from 2026-05-17 for the per-tool roll-up). The prior plan
is preserved in git history at the commit that introduced
it.

The technical-depth sprint left three queued: S8
(save-inspect SAVE-chunk decode), S9 (repro v0.4.0 input
automation), S10 (opcode-fuzz v0.3.0 recipes). All three
inherit forward into this sprint, reordered.

## Theme

Pivot from "build the lens" to "make the lens usable by
someone other than Brandon." After the 10-tool sprint the
toolkit can see almost everything in DS1 + DS2. What it
can't do, day-one, for a stranger cloning the repo:

- **Discoverability**. No top-level entry point. A new
  contributor has to read `tools/README.md` and pick a tool
  by name; nothing dispatches.
- **Naming**. The symbol catalogues ship empty by design;
  every GBYTE, GNUM, and most opcode handlers are raw
  indices. The disassembly is correct but illegible without
  prior RE.
- **Write paths**. Nine read tools, ~two write tools
  (`gff-edit replace`, `gpl-asm`). "Change a sprite" /
  "change a stat" / "edit a save" aren't shippable
  workflows.
- **Higher-level views**. Every output is bytecode,
  deeply-nested JSON, or PNG. No transcript, no character
  sheet, no browsable site.

Audience priority for this sprint: **external mod author
who has never touched the engine.** That dominates the
calls below where Brandon-the-author and external-modder
preferences differ (e.g., a transcript view over a JSON
view; a write path over an even-deeper schema).

## Current state (start-of-sprint)

| Tool              | Version | Last shipped |
|-------------------|---------|--------------|
| `verify-install`  | 0.2.0   | `--json` + `--repair` + `--dry-run` |
| `gff-edit`        | 0.5.0   | `GffBuilder` (indexed-only) |
| `gpl-disasm`      | 0.5.0   | `syms/variables.toml` + decorated variable refs |
| `gpl-asm`         | 0.7.0   | parameterised macros + `@include` |
| `dialog-extract`  | 0.6.0   | CFG-distance-ordered `possible_writers` |
| `save-inspect`    | 0.6.0   | DS2 item validation + `_format` tags |
| `image-extract`   | 0.3.0   | multi-frame export (`--frames-all`, `--spritesheet`) |
| `region-render`   | 0.6.0   | animated entity sprites |
| `repro`           | 0.3.0   | `--play --session` continuity |
| `opcode-fuzz`     | 0.2.0   | `run` subcommand + DARKRUN diff |

Two new tools proposed this sprint:

| Tool      | What |
|-----------|------|
| `opends`  | Umbrella CLI. Wraps the rest with auto-dispatch by file magic / kind. New crate. |
| `atlas`   | Static HTML site generator. Ingests every tool's JSON output and produces a browsable site. New crate. |

## Sprint order

Sequenced by human-friendliness ROI, then by dependencies.
Items marked **(inherited)** carry forward from the prior
sprint's queue without scope change.

1. **`gpl-disasm v0.6.0`**: bulk DSO symbol import +
   per-chunk local-variable overlays. One session. Every
   downstream consumer (gpl-asm, dialog-extract,
   opcode-fuzz, atlas) sees the better names automatically.
2. **`image-extract v0.4.0`**: `image-pack` companion
   binary (PNG → palette-indexed BMP / PORT / ICON chunk).
   Unlocks sprite mods, the single most-asked-for thing in
   retro modding.
3. **`opends v0.1.0`** (new): umbrella CLI. One session.
   Discoverability win at low cost; just shells out to
   existing tools by file magic.
4. **`save-inspect v0.7.0`** (inherited as S8): SAVE chunk
   decode. RE-heavy but the prerequisite for end-to-end
   save edits.
5. **`save-inspect v0.8.0`**: `save-edit` write path.
   Pairs with v0.7.0; consumes the JSON schema we already
   emit, writes back through `gff-edit`'s replace-chunk
   path.
6. **`dialog-extract v0.7.0`**: `--transcript` per-NPC
   human-readable output + `--html` static-site mode.
   Transcript is the surface a player or writer-curious
   modder actually wants; HTML mode is the on-ramp to
   `atlas`.
7. **`atlas v0.1.0`** (new): static HTML site scaffold.
   First-pass: sprite gallery + region maps + dialog
   browser. Subsequent versions add save inspector, GPL
   chunk index, etc.
8. **`repro v0.4.0`** (inherited as S9): ydotool input
   automation + ffmpeg video capture. Deps approved
   2026-05-17.
9. **`opcode-fuzz v0.3.0`** (inherited as S10): recipe
   library + structured diff + boot-chunk identification.
   Depends on (4) (5) (8).

B-tier items, picked up opportunistically between A-tier
ships:

- **`verify-install v0.3.0`**: `--rollback` + `--summary`
  plain-English mode.
- **`gff-edit v0.6.0`**: segmented-type build (closes the
  v0.5.0 builder gap) + `gff-cat what <kind> <id>` chunk
  describer.
- **`gpl-asm v0.8.0`**: declarative patch-script mode
  (insert / delete / replace records) plus a starter
  snippet library.
- **`region-render v0.7.0`**: `--annotate` overlays
  (entity names, region ids, walkability grid) +
  animated-GIF output.

---

## `gpl-disasm v0.6.0`: bulk DSO symbol import + local-variable overlays

The current `syms/` catalogues ship effectively empty:
2 functions, 0 opcode overrides, 0 variables. v0.6.0
populates them mechanically from
`.dso-online/tools/symbols.txt` and adds the per-chunk
local-variable overlay surface that v0.5.0 deferred.

### Scope (in)

- **DSO symbols loader** (`tools/gpl-disasm/scripts/import-dso-symbols.py`,
  stdlib-only). Parses `.dso-online/tools/symbols.txt`
  rows of shape `<NAME> <HEX_ADDR> <KIND>` (`f` = function,
  `l` = local / global). Filters to candidates that are
  meaningful for the GPL bytecode lens.
- **Opcode-handler import**. The ~70 `Decode*` functions
  (`DecodeJump`, `DecodeLongDivideEqual`, `DecodeBitsnoop`,
  ...) map 1:1 to libgff's opcode table. The importer
  cross-references libgff's mnemonic names (already in
  `docs/gpl-opcodes.md`), writes proposed
  `syms/opcodes.toml` rows with `dso_source = "DSO::<name>"`
  and `verified_by = "name-equivalence"`. Brandon reviews
  before commit; the curation rule in v0.4.2 still applies
  (don't relax it).
- **Engine-global reference doc**. `~30` `gGpl*` globals
  (`gGplDestX`, `gGplSpellLevel`, `gGplKiller`, ...) get
  written to `docs/dso-globals.md` as a curated reference,
  *not* into `syms/variables.toml` (those need GBYTE/GNUM
  index recovery from DSUN.EXE before we can map a name to
  an id; see Risks).
- **Per-chunk local-variable overlays**: schema in
  `syms/locals.toml` keyed by `(file, kind, chunk_id,
  var_kind, var_id)`. Loader patches `Expression::Variable.name`
  the same way globals do. The catalogue ships with one
  worked example from `iniya_first_meeting` to anchor
  the schema; modder contributions grow it.
- **`gpl-disasm syms-import` subcommand**: runs the
  importer programmatically so contributors don't have to
  fish out the script. Refuses to overwrite existing
  curated rows; emits a diff to stdout.

### Scope (out)

- **Engine-global RE**: mapping `gGplSpellLevel`'s memory
  address back to a GBYTE/GNUM index requires running
  DSUN.EXE under DOSBox debugger and watching writes from
  known GPL chunks. That's an opcode-fuzz-shaped task;
  defer.
- **DS1-specific symbols**. DSO symbols are from the WotR-
  derived multiplayer codebase. They apply cleanly to
  DS2's `DSUN.EXE`; the DS1 mapping is best-effort
  (different binary, some functions added / removed). The
  importer tags every imported row with `applies_to = ["ds2"]`
  or `applies_to = ["ds1", "ds2"]` and gpl-disasm respects
  the tag when loading per-game.

### Implementation steps

1. Write the importer script. Use `tomllib` for parsing
   existing rows; emit canonical TOML by hand (no `tomli-w`
   dep) following the format `syms/opcodes.toml` already
   uses.
2. Hand-build the libgff-to-DSO name correspondence table.
   Some are obvious (`DecodeBitsnoop` ↔ libgff `gpl bitsnoop`);
   some need verification (`DecodeIfis` is opcode `0x28`?
   libgff says `gpl trace var` which is suspicious). Flag
   any disagreement as a candidate libgff correction.
3. Add the `applies_to` field to the `[opcodes."0xNN"]` and
   `[[function]]` schemas. Loader filters by game when a
   target game is known (gpl-disasm CLI grows
   `--game ds1|ds2` or auto-detects from the GFF path).
4. Wire `gpl-disasm syms-import --source .dso-online/tools/symbols.txt`
   subcommand.
5. Add `syms/locals.toml` loader; thread per-chunk overlay
   into `apply_to_variables` walker. Skip rows that don't
   match the current chunk (`file`, `kind`, `chunk_id`
   triple).
6. Run the importer over the corpus, hand-review the diff,
   commit the curated subset.

### Test plan

- Corpus round-trip stays at 600 / 600 (the decoration
  doesn't affect bytecode).
- Unit test: a hand-built 2-row `opcodes.toml` and
  `locals.toml` decorate as expected; absent rows leave
  variables untouched.
- Regression: rerunning the importer against an unchanged
  source emits zero new diff lines.
- Human-friendliness smoke: disassemble DS2 `GPLDATA.GFF`
  chunk 0x14 (a known dialog chunk) before and after.
  Eyeball the diff; opcode mnemonics should be readable
  CamelCase ("BitSnoop" / "LongDivideEqual") instead of
  libgff's spaced form.

### Risks

- **Name-equivalence isn't bytecode-equivalence**.
  `DecodeIfis` at the libgff `gpl trace var` slot would
  mean libgff's table is wrong, not the DSO symbol.
  Mitigation: surface disagreement as a curation TODO,
  don't auto-overwrite libgff's row. The
  `verified_by = "name-equivalence"` tag is honest about
  the proof strength.
- **DSO is AGPL-3.0**. We are not vendoring the symbols
  file or copying executable code; we're using the names
  as facts to anchor our MIT-licensed RE. Document this
  in `CREDITS.md` (DSO row already exists; extend the
  feature list).
- **Locals schema explosion**. ~7,000 GPL chunks across
  both games; each could have local-variable overlays.
  Mitigation: `syms/locals.toml` ships near-empty; the
  schema is the deliverable, population is community work.

### Effort estimate

One session. Mechanical bulk import.

---

## `image-extract v0.4.0`: `image-pack` companion binary

The inverse of `image-extract`. Encodes a palette-indexed
PNG back into a Dark Sun bitmap chunk (`BMP `, `PORT`,
`ICON`, `BMAP`, `OMAP`, `TILE`). The single feature that
takes "look at the sprite" from possible to "ship a
sprite mod" possible.

### Scope (in)

- **`image-pack` binary** in the same crate as
  `image-extract`. Reads a palette-indexed PNG plus a
  reference palette source (`--palette <gff>:<kind>:<id>`
  or `--palette-from <chunk.bin>`); emits a single-frame
  RLE-encoded BMP chunk to stdout or `-o <file>`.
- **Multi-frame input**: `--frames <dir>` accepts a
  directory of `<stem>-frame-<N>.png` files (the
  `image-extract --frames-all` shape) and emits a
  multi-frame chunk.
- **Spritesheet input**: `--spritesheet <png>
  --frame-size WxH` slices a horizontal-strip PNG back
  into individual frames; useful for round-tripping the
  v0.3.0 `--spritesheet` export.
- **RLE-only encoder** for v0.4.0. PLNR / PLAN encoders
  are deferred (the engine reads both but RLE is the
  "default" format and what most modder edits will
  target).
- **`gff-cat replace` integration**: stdout-by-default
  output pipes naturally into
  `gff-cat replace <file> BMP 1234 - -o patched.gff`.
- **Round-trip property test**: every RLE-format frame
  in the corpus that `image-extract` decoded cleanly,
  re-encode with `image-pack`, decode again, expect
  pixel-identical output. **The encoder doesn't have to
  produce the original bytes**; it has to produce *a*
  byte stream the decoder reads as the same pixels.

### Scope (out)

- **PLNR / PLAN encoding**. Defer; mods can use RLE for
  edits since the engine reads all three.
- **Palette quantization**. We require palette-indexed
  PNG input. The toolkit doesn't paint or pick a palette
  for the user; pair `image-pack` with `convert -dither
  None -map <palette.png>` documentation in the README.
- **Sprite-frame metadata recovery** (per-frame delays,
  hotspots). Lives in ETAB / OJFF, not in the bitmap
  chunks themselves.

### Implementation steps

1. Move the existing `image-extract` binary's palette /
   bitmap I/O code into `lib.rs`'s reusable surface
   (parts already are; this just finishes the
   refactor).
2. New `src/bin/image-pack.rs` that drives the encoder.
3. RLE encoder in `src/rle.rs`. Mirror the v0.1.0
   decoder's per-row span structure (even/odd code
   split). Generate spans greedily; round-trip property
   test catches deviations.
4. CLI surface mirroring `image-extract` for symmetry:
   same `--kind`, `--frames`, `--spritesheet --frame-size`
   shapes.
5. Round-trip test in `tests/pack_corpus.rs` that walks
   every RLE-decodable corpus chunk through pack → unpack.

### Test plan

- New `tests/pack_corpus.rs`. Asserts pixel-identical
  round-trip across the RLE subset of the corpus.
- Unit test: a hand-built 4x4 palette-indexed bitmap
  packs and unpacks to the same pixels.
- Manual smoke: edit one frame of a known sprite (DS1
  RGN02 NPC), pack, replace via `gff-cat replace`, run
  in DOSBox via `repro --play`, observe the edited
  sprite.

### Risks

- **RLE spec drift**. The v0.1.0 decoder was reverse-
  engineered from libgff; the encoder is our own work.
  Property test is the safety net.
- **Palette mismatch**. A PNG saved with a different
  palette than the chunk's source renders wrong colours
  even if the indices are right. Mitigation: REQUIRE
  `--palette` arg; refuse to encode without it; document
  the workflow.
- **Chunk-size growth**. RLE compression depends on the
  image's run structure. An edited sprite may compress
  worse than the original; `gff-edit replace` handles
  grow-on-append already.

### Effort estimate

Two sessions: one for the encoder + binary, one for the
round-trip property test and DOSBox smoke.

---

## `opends v0.1.0` (new): umbrella CLI

A single binary that dispatches to the right tool by
file magic. The discoverability layer the toolkit has
never had.

### Scope (in)

- **New crate** at `tools/opends/`. Rust; depends on the
  workspace's existing tools as binaries (`gff-cat`,
  `gpl-disasm`, etc.); doesn't link against them.
- **`opends inspect <file>`**: read the first 4 bytes,
  dispatch:
  - `GFFI` → `gff-cat info <file>`
  - GPL/MAS chunk magic (or `--kind GPL`) → `gpl-disasm`
  - PNG → metadata + "use `image-pack` to encode this
    back"
  - Save extension (`.SAV`, `CHARSAVE.GFF`,
    `DARKRUN.GFF`) → `save-inspect <file>`
- **`opends find <pattern>`**: cross-tool grep. Search
  every `GPL ` chunk's string table, every NPC dialog,
  every chunk type catalogue. Returns chunk references
  the user can hand to the right tool.
- **`opends extract <file>`**: smart bulk extract.
  - GFF + no other args: extract every chunk to a
    sibling directory.
  - GFF + `--kind BMP`: extract every BMP chunk as PNG
    via `image-extract --all`.
- **`opends render <region.gff>`**: shells to
  `region-render` with sensible defaults.
- **`opends help` / `opends --version`**: top-level
  help that lists every wrapped tool and their
  versions (read from each tool's `VERSION` file).
- **PATH discovery**: looks in `../target/release/`
  first (for in-tree dev), then `$PATH`. Reports
  missing tools with a clear "you need to build
  gff-edit first" message.

### Scope (out)

- **Re-implementing logic in the umbrella**. Always
  shells out. The umbrella is glue.
- **`opends mod <file>`** (drop into an editor).
  Editor-integration belongs in a v0.2.0+ pass once
  we've watched real modders use the basic dispatch.
- **TUI / interactive mode**. CLI-only for v0.1.0.

### Implementation steps

1. New crate, depends on `clap` and `anyhow` only.
2. File-magic dispatcher in `src/dispatch.rs`. Magic
   table sourced from `docs/file-formats.md` §1 and
   the FOURCC catalogue.
3. Subprocess runner with explicit
   `std::process::Command`. Capture stderr; on tool
   failure, surface the underlying command and its
   exit code.
4. Top-level `opends help` reads each tool's `VERSION`
   file and emits a table.
5. README on the umbrella with the "Day 1 walkthrough"
   for a new contributor: install → verify → inspect →
   find a thing → render it → modify it.

### Test plan

- Unit tests on the magic dispatcher (no subprocess).
- Integration test: invoke `opends inspect` on a fixture
  GFF; assert it dispatches to `gff-cat info` and
  surfaces its output.

### Risks

- **PATH contamination**. A user with another `opends`
  in `$PATH` would shadow this. Low-likelihood; the
  name is uncommon. Mitigation: prefer in-tree
  binaries over `$PATH`.
- **Stale dispatch tables**. New chunk types added to
  `gff-edit` would not auto-register here. Mitigation:
  the dispatcher table lives in a small `.toml` shared
  with `gff-edit`'s `KIND_CATALOGUE`, or we just live
  with the duplication and review at every release.

### Effort estimate

One session.

---

## `save-inspect v0.7.0`: SAVE chunk decode (inherited)

S8 from the prior sprint, carried forward unchanged.
The big un-decoded surface in save-inspect: each `SAVE`
chunk in `DARKRUN.GFF` (~60 per save) holds per-region
world state (entity positions, NPC activity, trigger
flags, quest progression). Decoding them gives modders
end-to-end visibility into a playthrough and is the
prerequisite for `save-edit` (v0.8.0 below).

### Scope (in)

- **`SaveChunk` decoder** in `save-inspect.py`.
  Identifies the chunk's region (probably from the
  chunk's id), walks the body via the schema we
  recover.
- **Field-by-field empirical decode** anchored to:
  - libgff's `gfftypes.h` (`SAVE` = "save entries",
    nothing more documented).
  - soloscuro-archive's `save-load.c` (a Lua dump
    format, not the original; useful as a reference
    for *what* the engine persists but not *how*).
  - Cross-comparison of `SAVE` chunks across the
    factory `DARKRUN.GFF` vs. the played
    `ds1-fuck` / DS2 `--play` fixtures.
- **Per-game schemas**: DS1 and DS2 may differ; ship
  per-game decoders if they diverge. Tag each record
  `_format: ds1_save_chunk` / `ds2_save_chunk`.
- **`save-inspect` schema output gains a `save_chunks`
  array** with structured per-region records.
- **`save-inspect save-diff <factory.gff> <played.gff>`**
  subcommand that lists which `SAVE` chunks differ and
  by how many bytes. Already on Brandon's note from
  yesterday.

### Scope (out)

- **Full RE of every world-state field**. Anchor what
  we can (entity positions, flag bytes); surface
  unknowns as opaque hex with `_slot_N` placeholders
  (same hygiene as the combat / character schemas).
- **DS1 `ETAB` chunk decode** (entity table inside
  `DARKRUN.GFF`). Separate thread.

### Implementation steps

1. Pull DS1 `DARKRUN.GFF` factory vs `ds1-fuck` played
   save. Identical pull for DS2.
2. Per-region diff of SAVE chunks. Same regions:
   byte-by-byte diff to identify which fields change
   with play.
3. Categorise the changing fields (XP values, party
   position, flag bits, ...).
4. Build the decoder in `save-inspect.py` with the
   per-game format tag.
5. Validate across both played saves with `repro --play`
   captures.

### Test plan

- Self-consistency: decode + re-encode (or a no-op
  compare) every SAVE chunk; field counts stable.
- `save-inspect diff` highlights only meaningful
  fields, not every byte.

### Effort estimate

Multi-session. RE-heavy. Treat like the DS2 character
schema work: ship what's locked, mark the rest as
opaque placeholders.

---

## `save-inspect v0.8.0`: `save-edit` write path

The companion to v0.7.0. Modders edit the JSON,
save-edit writes the file back. Pairs with v0.7.0 but
ships separately so the write path lands as soon as
the schemas are stable, not gated on every last SAVE
chunk being decoded.

### Scope (in)

- **`save-edit` command** (new sibling to
  `save-inspect`). Same file (`save-inspect.py`); the
  script grows a `save-inspect edit` or
  `save-inspect write` subcommand.
- **JSON-in, GFF-out**: takes a JSON file that matches
  `save-inspect`'s output schema; reconstructs the
  raw bytes per sub-block; writes the GFF back via
  `gff-cat replace` (shelled).
- **Edit-safe fields**: every field that v0.6.0 / v0.7.0
  decoded structurally. Opaque hex (`_slot_N`,
  `_reserved_*`) stays opaque; the writer accepts
  edited hex and passes it through unchanged.
- **Dry-run mode**: `--dry-run` reports what would
  change without writing.
- **Backup before write**: stages the original chunk
  to `<save>.gff.bak.<timestamp>` next to the file.
- **Schema validation**: refuse to write if the JSON
  doesn't match the schema (typo'd field name,
  wrong type, out-of-range enum value). The validation
  errors look like the user's mistake, not a Python
  traceback.

### Scope (out)

- **Web UI / TUI**. Same story as `image-pack`: text
  in, GFF out. Editor is the user's choice.
- **Cross-save merges**. "Take this PC from save A,
  put it in save B" is a power-user feature; defer.
- **SAVE-chunk writes** until v0.7.0 lands the schema.
  Until then, save-edit refuses to touch the
  `save_chunks` array (it stays opaque on write).

### Implementation steps

1. Refactor the v0.6.0 sub-block decoders so each
   `_decode_X` has a sibling `_encode_X`. Symmetric
   structure; the sub-blocks are fixed-length so the
   inverse is mechanical.
2. Schema-validator pass over the input JSON. Walks
   the same recursive structure the decoder emits.
3. Shell to `gff-cat replace` for the actual file
   write; backup-before-write wrapper around it.
4. CLI: `save-edit <input.json> <save.gff>` writes
   in place; `--out <new.gff>` to a copy; `--dry-run`
   prints the chunk-replacement plan.

### Test plan

- Round-trip: decode every CHARSAVE in the corpus,
  re-encode with `save-edit`, expect byte-identical
  GFF output.
- Edit smoke: decode a save, change a PC's HP from
  10 to 100, write back, load in DOSBox via
  `repro --play`, observe the HP change.
- Validation tests: hand-build a broken JSON
  (out-of-range alignment, typo'd field), assert the
  error message is human-readable.

### Risks

- **Round-trip equivalence is not guaranteed** for
  v0.7.0's still-being-decoded SAVE chunks. Mitigation:
  the writer refuses to touch unrecognised chunks
  (treats `save_chunks` opaque-hex slots as immutable
  until v0.7.0 lands structured edits).
- **Schema drift between save-inspect versions**.
  Mitigation: every output JSON gets a `_schema_version`
  header; save-edit refuses to write if it doesn't
  recognise the version.

### Effort estimate

Two sessions: one for the encoder + validator, one for
the corpus round-trip + DOSBox smoke.

---

## `dialog-extract v0.7.0`: `--transcript` + `--html`

JSON is for tools; humans want to read dialog as
conversations. v0.7.0 adds two human-readable output
shapes layered on the v0.6.0 CFG-aware dialog tree.

### Scope (in)

- **`--transcript` mode**: per-NPC plain-text output
  of every line attributable to that speaker, with
  speaker labels and branch annotations.

  ```
  ## Iniya (DS1 GPL chunk 1)

    [first meeting]
    Iniya: "Free! Finally free! I will destroy you all!"
      → if PARTY_LEVEL > 3:
          Iniya: "Hmph. You look strong enough."
      → otherwise:
          Iniya: "Pitiful. Begone."
  ```

  The branch arrows come from the v0.3.0 CFG tree;
  the speaker comes from a curated
  `dialog-extract/syms/speakers.toml` keyed by
  chunk id.
- **`--html` mode**: a single-file static HTML page
  per GPL/MAS file. NPCs as collapsible sections;
  dialog trees as nested `<details>` blocks; LSTR
  resolution status as colour-coded annotations
  (green = exact, yellow = single writer at
  distance 0, orange = multiple candidates, red =
  unresolved). Embedded CSS; no external assets;
  works opened directly via `file://`. This is the
  on-ramp to the `atlas` tool's dialog browser.
- **`speakers.toml`** curated catalogue mapping
  chunk id → NPC name. v0.7.0 ships with ~10
  rows (the named NPCs we know from
  `iniya_first_meeting` plus easily-identified
  others); contributions grow it.

### Scope (out)

- **Voice-acting / audio integration**. There are
  no per-dialog audio assets in either game.
- **Translation / locale support**. The games ship
  English-only.
- **Modder-editable transcript**. v0.7.0 is read-
  only; editing dialog still requires `gpl-asm`.
  A `--transcript-edit` round-trip is a future
  feature.

### Implementation steps

1. New emitter in `dialog-extract.py` keyed off
   `--format transcript|html|json` (default
   stays json for back-compat).
2. Speakers catalogue loader. Empty rows fall back
   to `"GPL chunk N"` as the speaker label.
3. HTML template as a Python triple-string in
   `dialog_extract/html.py` (stdlib only). Embedded
   CSS for collapsible sections; no JavaScript.
4. README walkthrough: "find the dialog for
   character X" using `--grep` then `--transcript`.

### Test plan

- Unit: hand-built dialog tree emits the expected
  transcript shape.
- Corpus smoke: emit transcripts for DS1
  `GPLDATA.GFF`; eyeball Iniya's chunk; confirm
  branch arrows correspond to disasm CFG.
- HTML smoke: open the emitted HTML in a browser;
  every `<details>` block expands; no JS errors.

### Risks

- **Mis-attribution**. The speaker for an unnamed
  chunk defaults to `"GPL chunk N"`, which is
  honest but ugly. Mitigation: tooling encourages
  curation by surfacing high-line-count anonymous
  chunks at the top of the transcript output (the
  community's hit list).

### Effort estimate

One to two sessions.

---

## `atlas v0.1.0` (new): static HTML site generator

The cap on the human-friendliness sprint: a single
command that ingests every other tool's JSON output
and emits a browsable static site. Drops on disk;
opened directly via `file://`; no server.

### Scope (in)

- **New crate** at `tools/atlas/`. Python (stdlib +
  Jinja2 if and only if Brandon approves; otherwise
  triple-string templates per the dialog-extract
  pattern).
- **Three browsers in v0.1.0**:
  - **Sprite gallery**. Walks
    `image-extract --all` output per GFF; renders a
    paginated grid of PNGs with chunk id /
    dimensions / frame count annotations.
  - **Region map browser**. Walks `region-render`
    output; renders one page per region with its
    PNG + a sidebar of resolved entity sprites
    (cross-linked to the gallery).
  - **Dialog browser**. Embeds `dialog-extract
    --html` output per GFF; links to the gallery's
    portrait when a speaker has a known PORT chunk.
- **CLI**: `atlas build --games-dir <dir>
  -o <site-dir>`. Drives the underlying tools as
  subprocesses (the same wrapping pattern `opends`
  uses).
- **Cross-references**. Each chunk page links to
  every other page that references it (a sprite's
  page lists which regions use it; a region's page
  lists which dialog chunks reference its NPCs).
- **`docs/known-bugs.md` cross-link**. Each entry
  in `known-bugs.md` gets a page link if we know
  the relevant chunk.

### Scope (out)

- **Server / search**. v0.1.0 is static. Future
  versions can add a JS search index.
- **Save-state inspector**. Deferred to v0.2.0 (will
  consume save-inspect v0.7.0 / v0.8.0 output).
- **GPL chunk index**. Deferred to v0.2.0 (will
  consume gpl-disasm --json + dialog-extract
  --html).
- **GitHub Pages publish**. Generates locally; CI
  publishing comes later.

### Implementation steps

1. New crate, single Python script + a `templates/`
   directory.
2. Subprocess each upstream tool against the games
   dir; cache JSON output to a working dir.
3. Render per-chunk pages from a template that
   knows nothing about Dark Sun specifically (just
   a generic "thing with metadata + image + links"
   shape).
4. Build cross-reference index by walking the
   collected JSON before rendering pages.
5. README on the atlas crate: "atlas as the
   front page of OpenDS" framing; screenshot;
   one-command quickstart.

### Test plan

- Smoke: `atlas build` against `.games/ds1/` and
  `.games/ds2/` produces a site that opens in a
  browser, every page loads, no broken links.
- Visual: scroll through the sprite gallery for a
  couple of minutes; gut-check that it looks like
  something a modder would want to read.

### Risks

- **Performance**. Two games' worth of every PNG
  could be a lot of files (thousands of sprites).
  Mitigation: paginate; lazy-load thumbnails;
  measure the v0.1.0 output size before committing
  to the format.
- **Jinja2 dep**. If Brandon greenlights, easier;
  otherwise the triple-string template approach
  works but is uglier. Default to stdlib-only for
  the first ship.

### Effort estimate

Two to three sessions for v0.1.0 (sprite +
regions + dialog).

---

## `repro v0.4.0`: ydotool input automation + video capture (inherited)

S9 from the prior sprint, carried forward unchanged.
Deps (ydotool + ffmpeg) approved 2026-05-17.

### Scope (in)

- **`ydotool` integration** for keystroke automation
  on Wayland. Daemon (`ydotoold`) setup documented
  in README; the harness detects ydotool availability
  and silently no-ops keystrokes when absent.
- **`[trigger.keystrokes]` schema** in `bug.toml`:

  ```toml
  [[trigger.keystrokes]]
  at_seconds = 8
  send = "Return"
  ```

  The harness spawns a Python thread that fires
  keystrokes on schedule after DOSBox starts.
- **Video capture** via ffmpeg + x11grab (or
  kmsgrab / wf-recorder on Wayland; pick during
  implementation). Output: `<session>/repro.webm`.
- **`[expected].record_video`** flag in `bug.toml`.
- **One-time setup doc**: the `uinput` permission
  for ydotool (likely a udev rule + group
  membership; Brandon may need to log out / back
  in).

### Scope (out)

- **Mouse input**. Keyboard only in v0.4.0.
- **Differential capture** (run-with-patch vs.
  without). v0.5.0.

### Implementation steps

1. Add ydotool detection + setup-doc shim.
2. `[trigger.keystrokes]` parser + scheduler
   thread in `repro.py`.
3. ffmpeg recorder subprocess; verify it captures
   DOSBox-Staging's GL surface on Wayland.
4. README updates: setup, ydotool group membership,
   capture mode usage.

### Test plan

- Smoke on `ds1-smoke`: a single keystroke schedule
  that hits Enter at the GOG splash screen and
  reaches the title screen; capture video; eyeball.
- Wayland focus: confirm keystrokes still land on
  DOSBox when the user alt-tabs away (or document
  that they don't).

### Risks

- **Wayland window focus**. Per pick-it-up.md, the
  surface may not be a normal X window even under
  XWayland. Mitigation: time-box the x11grab path;
  fall back to kmsgrab / wf-recorder if needed.
- **Daemon setup pain**. One-time, but real.
  Mitigation: README walkthrough; auto-detect and
  print actionable error.

### Effort estimate

One to two sessions per feature; gated on
implementation discovery, not dep approvals.

---

## `opcode-fuzz v0.3.0`: recipes + boot chunks + structured diff (inherited)

S10 from the prior sprint, carried forward. Depends
on (4) save-inspect v0.7.0 (SAVE chunk decode), (5)
save-inspect v0.8.0 (write path lets recipes
deterministically reset state), (8) repro v0.4.0
(input automation for deterministic execution), and
benefits from (1) gpl-disasm v0.6.0 (named globals
in the diff output).

### Scope (in)

- **`tools/opcode-fuzz/recipes/`** directory. Each
  recipe is a `.asm` template (uses `gpl-asm
  v0.7.0` parameterised macros) representing
  prologue + test-opcode + epilogue.
- **`opcode-fuzz fuzz <opcode>`** subcommand:
  instantiate the recipe with the target opcode,
  swap into a known boot-time chunk, run via
  `repro --play --session`, capture pre/post state.
- **Structured diff** via save-inspect v0.7.0:
  report which globals changed (by name from
  gpl-disasm v0.6.0's catalogue), not just byte
  offsets.
- **Boot-chunk identification helper**:
  `opcode-fuzz boot-chunks <game>` lists chunks the
  engine invokes before user input is required,
  based on `gpl-disasm --global-cfg` analysis +
  per-chunk shape heuristics.
- **First recipe**: the trivial `gpl byte inc`
  case. Sets a known global before, increments,
  asserts it's one larger after.

### Scope (out)

- **Automated bisection** of opcode parameters.
  v0.4.0.
- **Bulk fuzz across all unknown opcodes** with a
  result database. v0.4.0.

### Implementation steps

(All gated on the dependencies above.)

### Effort estimate

Multi-session; gated on the four dependencies above.

---

## B-tier items (opportunistic)

### `verify-install v0.3.0`

- **`--rollback`**: detect `__verify-install-backup/`,
  restore everything to its pre-repair state. Inverse
  of v0.2.0's `--repair`.
- **`--summary`**: plain-English line per status
  ("Your install looks good. 3 files in extras (probably
  saves). Run `verify-install --show-extras` to list
  them."). One-line for the common-case; full table
  stays available behind `--show-extras` /
  `--show-skipped`.

Half-session, no deps.

### `gff-edit v0.6.0`

- **Segmented-type build**: close the v0.5.0 gap; the
  `GffBuilder` covers the full GFF feature set
  (secondary-table + `GFFI` cross-reference dance).
  Already on the roadmap; ship when there's a forcing
  function from a downstream consumer.
- **`gff-cat what <kind> <id>`**: chunk describer. Reads
  the local `KIND_CATALOGUE` plus a new optional
  cross-reference (entity sprite → which regions use
  it, dialog chunk → which NPC, etc.) sourced from
  `docs/file-formats.md` and the curated symbol
  catalogues. Output: "BMP id 1234 is a sprite for
  NPC 'Iniya' (used in DS1 RGN02)."

One to two sessions.

### `gpl-asm v0.8.0`

- **Declarative patch-script mode**: `gpl-asm patch
  fix.patch orig.bin` consumes a `.patch` file with
  insert / delete / replace records keyed by
  label-relative offsets. Produces the patched chunk
  without requiring the modder to author the full
  reassembly. This is the natural authoring surface
  for darkfix fixes (mostly 1-3 byte edits).

  ```toml
  # fix.patch
  [[edit]]
  at = "label_0x42 + 3"
  action = "replace"
  bytes_old = "0x01"
  bytes_new = "0x02"
  reason = "off-by-one in flag check"
  ```

- **Starter snippet library** at `tools/gpl-asm/snippets/`:
  common idioms (`clear-flag.snippet`, `set-gold.snippet`,
  etc.) usable via `%include`. Empty-ish at v0.8.0; grows
  with the cookbook.

Two sessions.

### `region-render v0.7.0`

- **`--annotate`** overlays: entity names (from the v0.6.0
  catalogue), region id, walkability grid (from `GMAP`
  upper bits). Renders on top of the existing palette-
  indexed PNG path; output stays single-PNG.
- **Animated-GIF output**: bundle the `--animate-entities`
  PNG sequence into a single `.gif` via either the `gif`
  crate (new dep; needs approval) or `ffmpeg` shell-out
  (no new Rust dep). Default to ffmpeg path; surface a
  helpful error if it's missing.

One to two sessions.

---

## Dependency graph

```
gpl-disasm v0.6.0 ───── benefits ──┐
   (bulk DSO symbol import)         │
                                    ▼
image-extract v0.4.0                opcode-fuzz v0.3.0
   (image-pack)                       (structured diff)
       │                              ▲
       │                              │
       ▼                              │
opends v0.1.0 ────── wraps ─── (all)  │
   (umbrella CLI)                     │
                                      │
save-inspect v0.7.0 ──── enables ─────┤
   (SAVE chunk decode)                │
       │                              │
       ▼                              │
save-inspect v0.8.0 ──── enables ─────┤
   (save-edit write path)             │
                                      │
dialog-extract v0.7.0 ─── on-ramp ──┐ │
   (--transcript + --html)          │ │
                                    ▼ │
                          atlas v0.1.0│
                          (static site)
                                      │
repro v0.4.0 ───────── enables ───────┘
   (ydotool + ffmpeg)
```

The two convergence points: `atlas v0.1.0` depends on
`dialog-extract v0.7.0` for its dialog browser; the
sprite + region browsers depend only on existing
tools and can ship without it if scheduling pushes
dialog-extract later. `opcode-fuzz v0.3.0` is the
hardest convergence (depends on save-inspect v0.7.0,
v0.8.0, and repro v0.4.0) and stays at the back of
the sprint.

## What needs deciding

1. **`opends` and `atlas` naming**. Are these the right
   names for the new tools? Alternatives considered:
   `opends-cli` and `opends-atlas`; `darkfix-tool` and
   `darkfix-browser`. Current pick reads well on
   `tools/README.md` and `cargo run -p atlas`.
2. **Jinja2 for `atlas` templates**. Adds one dep
   (`jinja2`); alternative is stdlib-only Python
   triple-string templates (uglier, more verbose).
   Default to stdlib until friction proves the dep.
3. **Image-pack palette workflow**. The plan requires
   palette-indexed PNG input; the modder is expected to
   convert with `convert -dither None -map <palette>` or
   equivalent. Is that an acceptable seam, or should
   `image-pack` carry a built-in quantizer?
4. **Cookbook timing**. `docs/cookbook/` (end-to-end
   walkthroughs) is the natural companion to this sprint
   but not scoped as its own ship. Land it incrementally
   alongside each tool, or hold for a dedicated
   documentation pass at the end?

## Background research

- **DSO symbol coverage** (from `.dso-online/tools/symbols.txt`):
  3,530 functions + 2,247 globals; ~70 `Decode*`
  opcode-handler names map 1:1 to libgff's GPL opcode
  table; ~30 `gGpl*` globals identify engine state
  variables (GFF chunk pointers, current spell context,
  current region, ...).
- **DSO licence**. AGPL-3.0. Using the names as facts
  (not vendoring the symbols file, not copying engine
  code) keeps the OpenDS catalogues MIT. Document the
  attribution in `CREDITS.md`; the existing DSO row
  needs its feature list extended.
- **Existing write-path coverage**. The toolkit has
  exactly two write paths today: `gff-cat replace`
  (chunk-level GFF surgery) and `gpl-asm` (GPL
  bytecode authoring). `image-pack` (v0.4.0) and
  `save-edit` (v0.8.0) double that count and target
  the two highest-asked-for mod use cases.
- **`dsoageofheroes` state as of 2026-05-17**:
  unchanged from the prior sprint's check; no new
  public engine reimplementation has shipped. The DS2
  inheritance story (DSO symbols → DS2 `DSUN.EXE`)
  is the only meaningful new RE surface.
