# Patchnotes

Released versions appear here, newest first.

## Unreleased

- **`tools/region-render/` v0.1.0** ships (new Rust crate; closes
  Phase 4). Renders a region GFF's background tile layer
  (`RMAP` for DS1 or `MAP ` for DS2) as a 2048 x 1568
  palette-indexed PNG. Walls (`GMAP` lower 5 bits + `WALL`
  chunks), entities (`ETAB` + `OJFF`), animated colours, and
  GMAP flag visualisation are all v0.2+ work.
  - **Ports from `JohnGlassmyer/dsun_music`** (MIT,
    `region-tool/RegionTool.java`):
    - Region geometry constants (128 x 98 tiles, 16 x 16 px).
    - `RMAP` / `MAP ` layout (row-major byte grid, each byte =
      TILE resource id).
    - Palette discovery rule (inline first, explicit `--pal`
      override second).
  - **Reuses `image-extract`**: `Palette::from_bytes` for the
    768-byte `PAL `/`CPAL` chunks; `Bitmap::from_bytes` +
    `decode_frame(0)` for each `TILE`. v0.1 expects 16 x 16
    frames and treats anything else as a soft decode failure.
  - **Soft-decode of malformed TILEs**: DS2 region GFFs ship a
    15-byte sentinel `TILE` id `0` that can't be parsed as a
    bitmap. v0.1 records these as `TileDecodeFailure` rows
    rather than hard-failing; the sentinel isn't referenced by
    `MAP ` so it has no visible effect.
  - **CLI**: `region-render <RGN.GFF> -o out.png` with optional
    `--palette <gff>:<KIND>:<id>` or `--palette-file <raw>`. The
    DS1 default fallback is `RESOURCE.GFF:PAL :1000` in the same
    directory as the input.
  - **Library**: `RegionMap::from_gff(&Gff, Palette)`,
    `RegionMap::render_indexed() -> Vec<u8>`,
    `RegionMap::write_png(path)`, plus `inline_palette(&Gff) ->
    Option<Palette>` for callers building their own resolution.
  - **Tests**: 6 unit + 1 corpus smoke. The corpus test renders
    every `RGN*.GFF` in DS1+DS2 and asserts the rendered buffer
    is exactly `REGION_PIXEL_WIDTH * REGION_PIXEL_HEIGHT` bytes;
    no panics required.
  - **Corpus results** (GOG 1.10): 53 regions rendered (35 DS1 +
    18 DS2). **0 missing-tile bytes** across the whole corpus
    (every RMAP / MAP byte resolved to a present TILE chunk in
    the same GFF). 18 soft TILE decode failures, one per DS2
    region (the sentinel id 0 case).
  - **DS1 palette caveat surfaced**: DS1 stores only four
    palettes in `RESOURCE.GFF` and none are keyed on region
    number. v0.1 defaults to `PAL :1000`; the rendered output is
    structurally correct but the "off-camera" tile cells use the
    palette's high-index colours (visibly pink/magenta). The
    interior playable area renders with plausible terrain
    colours. Per-region palette discovery is queued for v0.2+.
  - **Docs**: `docs/file-formats.md` expanded with a "Region
    geometry" subsection covering RMAP/MAP/GMAP/TILE/PAL/ETAB
    layouts (deferred sections are flagged for v0.2+).
  - Roadmap Phase 4 region-render bullet ticked; Phase 4 is now
    done.

- **`tools/gpl-disasm/` v0.4.2** wires opcode-mnemonic overrides
  through to text and JSON output. The `syms/opcodes.toml`
  catalogue loaded since v0.4.0 is now applied: a row of the form
  `[opcodes."0xNN"] name = "..."` replaces the libgff default
  mnemonic for that opcode byte everywhere the disassembler
  emits a mnemonic. Defaults remain for any byte without an
  entry. No new CLI flags; existing `--syms` / `--no-syms` still
  control catalogue loading.
  - **Internal change**: `Instruction.mnemonic` is now
    `Option<Cow<'static, str>>` (was `Option<&'static str>`).
    Default path is zero-allocation (`Cow::Borrowed` from the
    static `OPCODES` table); `Cow::Owned` after an override
    applies. JSON shape is unchanged (serde serializes Cow as a
    string). The inner-mnemonic field inside `Expression::RetVal`
    stays `&'static str` for v0.4.2; extending overrides there
    is a follow-up if curation needs it.
  - **New API**: `Symbols::apply_to_mnemonics(&mut DisasmResult)`
    iterates instructions, looks up `format!("0x{:02x}", opcode)`
    in `self.opcodes`, and rewrites the mnemonic on hit. The
    binary calls it right after `apply_to_labels` in all three
    paths (`single-chunk`, `--all`, `--global-cfg`).
  - **`syms/opcodes.toml` ships empty by design.** The file
    header now documents the curation rule explicitly: a row
    lands only when the libgff mnemonic is unambiguously wrong
    (cross-checked against in-game behavior or DSO debug-symbol
    context), or when the alternate name is materially clearer
    and still accurate. Cosmetic aliases (e.g. `gpl tport` →
    `gpl teleport`) do not meet the bar. Honest finding from
    this release: libgff's `gpl_commands` and soloscuro-archive's
    `gpl_lua_operations[]` are character-identical, and the DSO
    v1.0 symbol table names callbacks (`ExecuteGpl`,
    `GplTileCheck`), not opcode-byte handlers. The plumbing
    lands without seed rows; the unit tests prove the override
    pipe works.
  - **Tests**: 4 new unit tests
    (`symbols_apply_to_mnemonics_overrides_known_opcode`,
    `_leaves_unrelated_alone`,
    `_preserves_none_for_unknown_byte`,
    `symbols_load_opcodes_from_toml`). gpl-disasm test count: 44
    unit + 2 integration (was 40 + 2).
  - **VERSION file**: bumped from `0.2.1` to `0.4.2`. The
    `VERSION` file silently fell behind `Cargo.toml` between
    v0.3.0 and v0.4.1; per `docs/versioning.md` it is the single
    source of truth, so this release catches it back up. No
    behavioural change.
  - Roadmap Phase 3 opcode-mnemonic-override bullet ticked.

- **`tools/gpl-disasm/` v0.4.1** adds inter-chunk control-flow
  analysis. New `--global-cfg <path>` flag emits a whole-file
  callgraph where nodes are GPL/MAS chunks and edges are the
  `gpl global sub` (0x14) cross-chunk call sites we've been
  indexing since v0.3.0. Output is DOT by default or JSON with
  `--json`; `-` writes to stdout. Mutually exclusive with the
  single-chunk path.
  - **New types** (`lib.rs`): `GlobalCfg` (source, nodes, edges),
    `ChunkNode` (kind, chunk_id, entry/block/in/out counts),
    `CrossEdge` (from_kind, from_chunk, from_offset, to_chunk,
    to_offset, optional from/to function names), `ChunkSummary`
    (per-chunk input to the builder).
  - **Symbol propagation**: when the caller's `from_offset`
    falls inside an entry-point range whose `functions.toml`
    row exists, that name is set as `from_function_name`. When
    the callee's `to_offset` matches an entry point in the
    destination chunk and a symbol exists, `to_function_name`
    is set. JSON consumers see the resolved names directly.
  - **Corpus** (GOG 1.10):
    - DS1 GPLDATA: 250 chunks, 587 inter-chunk edges.
    - DS2 GPLDATA: 350 chunks, 797 inter-chunk edges.
    - Combined: 1,384 edges — exactly the figure the v0.3.0
      corpus soundness test has been reporting since the cross-
      chunk indexing landed.
  - **Most-called chunk in DS1**: GPL-74 with 169 inbound
    calls and 2 outbound. The shape suggests it's a heavily-
    shared utility worth naming first in the curation backlog.
  - **Tests**: 2 new unit tests
    (`global_cfg_aggregates_inbound_outbound_counts`,
    `global_cfg_annotates_edges_with_symbols`). gpl-disasm
    test count: 40 unit + 2 integration.
  - **DOT renderer**: self-loops (a chunk calling itself via
    `global sub` — we observe a few of these, e.g. GPL-106 /
    GPL-107 in DS1) get a dashed-gray style to distinguish them
    from inter-chunk edges. Each chunk node carries inbound /
    outbound counts in its label.
  - Roadmap Phase 3 inter-chunk-CFG bullet ticked.

- **`tools/gpl-disasm/` v0.4.0** ships symbol-import plumbing.
  Hand-curated TOML catalogues at `tools/gpl-disasm/syms/`
  decorate function-entry labels in both text and JSON output.
  When a `functions.toml` row matches a chunk's entry point,
  the rendered label becomes `entry_0xNNNN (function_name)`.
  Downstream consumers (`dialog-extract` in particular) inherit
  the enriched labels through the JSON without code changes.
  - **Schema**: `syms/functions.toml` is a list of `[[function]]`
    tables with `file` (GFF basename, case-insensitive),
    `kind` (4-char FOURCC), `chunk_id`, `offset`, `name`, and
    optional `notes`. `syms/opcodes.toml` reserves the opcode-
    override slot for v0.4.1+; the loader reads it but the
    renderer does not yet rewrite mnemonics.
  - **CLI**: new `--syms <dir>` flag (explicit catalogue path)
    and `--no-syms` flag (disable lookup entirely). Default
    resolves `tools/gpl-disasm/syms/` next to the binary by
    walking up the workspace tree.
  - **Starter catalogue**: 2 verified entries for DS1 GPLDATA
    chunk 1 (`iniya_first_meeting` at 0x0001 and
    `iniya_dialog_menu` at 0x0095), seeded from the
    unambiguous "Free! Finally free!" cross-reference. The
    catalogue grows over time as more function purposes are
    cross-checked.
  - **New types** (`lib.rs`): `Symbols`, `OpcodeSymbol`,
    `FunctionSymbol`, `SymbolsLoadError`, plus
    `Symbols::load_from_dir`, `Symbols::function_name`, and
    `Symbols::apply_to_labels` for mutating a `Cfg` in place.
  - **Tests**: 2 new unit tests
    (`symbols_apply_to_entry_labels_only`,
    `symbols_case_insensitive_file_match`); gpl-disasm test
    count: 38 unit + 2 integration.
  - **Workspace**: adds `toml = "0.8"` as a workspace dep
    (pre-approved per spec §7a as format I/O).
  - Roadmap Phase 3 v0.4.0 symbol-import bullet ticked.

- **`tools/dialog-extract/` v0.3.0** adds a CFG-aware
  `dialog_tree` field per chunk alongside the existing flat
  `strings` list. Built on top of `gpl-disasm v0.3.1`'s CFG. The
  tree is a recursive structure of `block`, `if`, `ifcompare`,
  `loop`, `goto`, `revisit`, and `depth_cut` nodes mirroring the
  chunk's control flow.
  - **Block nodes** carry `lines` (the same string records v0.2.0
    emits, now also tagged with a `speaker_state` snapshot),
    `gpl_refs` (`local sub` / `global sub` call sites with
    `at` / `target` / `target_label` / `file_id`), a
    `speaker_state_entry` snapshot, and `children` for the
    block's terminator.
  - **If detection** picks up the if-with-else case by checking
    whether the then-path ends in a `gpl else` terminator;
    when it does, the matching endif (the else's own param
    target) becomes the join offset for an `else` subtree
    walked from the if's not-taken edge.
  - **Ifcompare nodes** surface `gpl ifcompare`'s case-value
    pattern (the comparison literal as a rendered param). The
    chained switch dispatch in DS scripts (e.g. DS1 GPL-199)
    now reads as nested `ifcompare` nodes with `match` and
    `miss` subtrees.
  - **Loop nodes** wrap `gpl while` bodies; the implicit
    backward `gpl wend` edge is not modelled as a child (just
    stops the recursive walk).
  - **Discovered entries**: each chunk's `cfg.entry_points`
    only includes the chunk start and locally-observed
    `gpl local sub` targets. Most block leaders are reached
    instead by `gpl global sub` from another chunk; the v0.3.0
    walker discovers these as additional top-level entries
    after the declared walks finish, so every block leader's
    dialog is visible. (Full inter-chunk CFG walking is
    `gpl-disasm v0.4.1` work.)
  - **Speaker-state tracking** is deliberately heuristic:
    only `gpl setother` (0x41) and `gpl setthing` (0x49) are
    tracked. We do NOT claim a line is spoken by anyone; the
    snapshot just surfaces the engine context (which NPC was
    last set) at the time of each line.
  - **Corpus** (GOG 1.10): 600 / 600 chunks build a tree.
    46,611 lines total across 4,229 declared + 15,027
    discovered entry-point walks (exact match to v0.2.0's
    flat-strings count, confirming the tree captures every
    line). 7,438 `revisit` cuts (shared sub-paths between
    entries). 0 invariant violations (every line / gpl_ref
    offset resolves to a chunk instruction).
  - **Back-compat**: the existing `strings` per-chunk field
    stays byte-identical. v0.2.0 consumers parse the new JSON
    unchanged; the `dialog_tree` field is additive.
  - Stdlib-only Python; no new dependencies. The walker is in
    `tools/dialog-extract/dialog-extract.py` as `build_dialog_tree`
    and `_walk_tree`. Tested via inline corpus validation
    (run-once script in the README's empirical-results notes;
    no formal test framework — matches the other Python tools
    in this repo).
  - Roadmap Phase 4 dialog-extract v0.3.0 box ticked.

- **`tools/gpl-disasm/` v0.3.1** fixes the `gpl else` (0x3F)
  control-flow edge. v0.3.0's CFG treated the else opcode's
  offset as a first-class block leader and routed `gpl if` /
  `gpl ifcompare` / `gpl while` not-taken edges directly to it.
  In the real runtime the else opcode is dual-mode: when reached
  by jump (the if-false path), it behaves as a no-op and
  control continues past the opcode bytes into the else-body;
  when reached by fall-through (from the matching then-block),
  it executes an unconditional jump to its param (the matching
  endif). v0.3.0's model missed the entire else-body on the
  false path.
  - **Scope of impact**: 5,471 of 20,281 conditional branches
    in the DS1+DS2 corpus (27%) landed on a `gpl else` opcode
    and were affected. dialog-extract v0.2.0's flat-string
    output was unaffected (no CFG dependency yet);
    dialog-extract v0.3.0+ depends on this fix.
  - **CFG model**: a new `redirect_past_else` helper rewrites
    any branch target whose offset equals a `gpl else` opcode
    to `else_offset + else_length`. The else opcode is no
    longer a block leader; it becomes the terminator
    instruction of its preceding block (with
    `TerminatorKind::UnconditionalElse` → param). Applied to
    leader collection AND to `successors_for` edge wiring so
    both views stay consistent.
  - **Rendering**: a new `Cfg.target_aliases` map preserves the
    "raw branch param → labeled name" lookup. `gpl if 80` (when
    80 is the offset of a `gpl else`) renders as
    `gpl if label_0x0053` (the else-body offset). The else
    opcode itself does NOT get a spurious `label_*:` line
    prepended; only true block leaders do.
  - **Corpus**: 600 / 600 chunks remain aligned; 66,028
    successor edges now resolve to instruction boundaries (was
    71,403; the difference is the ~5,400 Fallthrough edges that
    formerly entered the else-as-its-own-block and are now
    absorbed into the preceding block's terminator). Still 0
    computed-target edges and 1,384 cross-chunk `global sub`
    call sites recorded.
  - **Tests**: 1 new unit test
    (`cfg_redirects_if_target_past_else_opcode`) covers the
    redirect, the suppressed leader, and the `target_aliases`
    population. Total gpl-disasm test count: 36 unit + 2
    integration.

- **`tools/gpl-disasm/` v0.3.0** ships control-flow analysis.
  Each disassembled chunk now carries a `Cfg` of basic blocks,
  entry points, and labeled successors. The text listing
  renders `gpl if label_0x0020` instead of `gpl if 32`, with
  `label_*:` / `entry_*:` lines preceding every block leader.
  - **Pre-implementation spike** verified the load-bearing
    assumption against three independent sources
    (soloscuro-archive's Lua emitter, libgff's parser, and a
    hand-trace of two DS1 GPLDATA chunks): the first parameter
    of every branch opcode is the absolute byte offset of the
    target instruction within the same chunk. The semantics
    table and the trace evidence land in
    [`docs/gpl-bytecode.md` §5a](docs/gpl-bytecode.md). The
    spike caught one wrinkle worth surfacing: `gpl ifcompare`
    (0x27) takes 2 parameters where the *second* param is the
    target offset (param[0] is the comparison value); this is
    different from the single-param branches (`if`, `else`,
    `while`, `wend`, `jump`, `local sub`).
  - **Branch classification** for the CFG covers `gpl jump`
    (0x12), `gpl local sub` (0x13), `gpl global sub` (0x14),
    `gpl local ret` (0x15), `gpl global ret` (0x19), `gpl
    ifcompare` (0x27), `gpl exit gpl` (0x31), `gpl if` (0x3E),
    `gpl else` (0x3F), `gpl while` (0x63), `gpl wend` (0x64),
    plus `gpl zero` / EXIT_GPL (0x00) and the
    `endif`/`cmpend` markers (0x67/0x61).
  - **Entry points** = chunk start (offset 0), offset 1 when a
    real instruction lives there (every chunk we have begins
    with the `gpl global ret` epilogue placeholder at offset 0),
    plus every observed `gpl local sub` target inside the same
    chunk. `gpl global sub` cross-chunk targets are recorded in
    a new `cross_chunk_calls` list for v0.4.0+ inter-chunk work
    but are not added as CFG edges in v0.3.0.
  - **New CLI flags**: `--entries` (list discovered entry
    points, one offset per line), `--cfg <path>` (Graphviz DOT
    of the per-chunk CFG; supports `-` for stdout in
    single-chunk mode; writes `<kind>-<id>.dot` files in
    `--all` mode), `--no-labels` (revert to integer targets in
    the text listing for diff-friendly output).
  - **JSON output** gains an additive `cfg` field
    (entry_points, blocks, labels, unresolved) plus a top-level
    `cross_chunk_calls` list. Existing consumers
    (`dialog-extract` v0.2.0) parse the new shape without
    modification.
  - **Corpus verification**: 600 / 600 DS1+DS2 GPL/MAS chunks
    build a CFG where every one of the 71,403 successor edges
    resolves to a known instruction boundary. 0 computed-target
    edges, 1,384 `global sub` cross-chunk call sites recorded.
    A new integration test
    (`every_cfg_successor_resolves_to_instruction_boundary` in
    `tests/corpus_smoke.rs`) enforces this invariant.
  - **Tests**: 10 new unit tests in `src/lib.rs` cover each
    branch classification, entry-point promotion via `local
    sub`, cross-chunk call recording, label formatting, and the
    `cfg = None` fallback for misaligned disassembly. Total
    gpl-disasm test count: 35 unit + 2 integration.
  - Ported from `.dsoageofheroes/soloscuro-archive/src/gpl/gpl-lua.c`
    (MIT, attributed) and `.dsoageofheroes/libgff/src/gpl/parse.c`
    (MIT, attributed). No new third-party crate deps; the DOT
    writer uses `std::io::Write` only.
  - Roadmap Phase 3 "Identify entry points and basic-block
    boundaries" box ticked.

- **`tools/image-extract/` v0.1.0** ships (new Rust crate;
  Phase 4 Goal-1 deliverable, the first **visual** modder tool
  in the toolkit). Extracts Dark Sun bitmap chunks (`BMP `,
  `PORT`, `ICON`, `BMAP`, `OMAP`, `TILE`) as palette-indexed
  PNG.
  - **Ports from `dsoageofheroes/libgff` (MIT, attributed)**:
    - **Palette** (`PAL ` / `CPAL` chunks): 768 bytes = 256 × RGB
      6-bit, scaled to 8-bit by libgff's `intensity_multiplier = 4`.
    - **Bitmap header**: 6-byte preamble + u16 `frame_count` at
      +4 + u32 per-frame offset table at +6; per-frame `u16 width`
      + `u16 height` + 1 unknown byte + 4-byte frame_type tag
      ("PLNR" / "PLAN" / DS1 RLE).
    - **DS1 RLE pixel decoder**: per-row spans with even/odd
      code split (even = direct palette indices, odd =
      repeat-single). Image stored bottom-up; rows flipped to
      PNG top-down on output.
    - **PLNR bit-packed dictionary decoder**: per-symbol
      bit-packed indices into a chunk-local dictionary; 4-bit
      rotated bit-extraction order.
  - **PNG output** via the `png` crate (MIT/Apache 2.0; new
    workspace dep `png = "0.17"`, pre-approved per spec §7a as
    format I/O). PNGs are 8-bit palette-indexed, preserving the
    source format's compact representation.
  - **CLI**: `image-extract <file> --kind PORT --id N -o out.png`
    for single-frame; `--frame N` for multi-frame chunks;
    `--all -o <dir>` for bulk dump; `--palette N --palette-kind
    PAL` for explicit palette selection (default: lowest-id
    `PAL `, falling back to lowest-id `CPAL`).
  - **Library**: `Palette::from_bytes`, `Bitmap::from_bytes`,
    `Bitmap::decode_frame -> Frame`, `write_png(path, frame,
    palette)`.
  - **Empirical** (GOG 1.10): DS1 GPLDATA.GFF's 112 `PORT`
    frames extract cleanly (100%). Combined DS1+DS2 corpus:
    1,334 bitmap chunks, 1,976 frames, **1,328 decoded (67%)**:
    883 DS1 RLE + 445 PLNR. The 648 skipped frames are mostly
    PLAN (libgff itself doesn't implement it) and other
    variants pending RE.
  - **Tests**: 5 unit tests covering palette scaling, bitmap
    header parsing, DS1 RLE direct + repeat. Corpus smoke test
    iterates all bitmap chunks across DS1+DS2 GPLDATA.GFF and
    RESOURCE.GFF without panicking, verifies pixel counts match
    width × height, and reports decoded percentages per type.
  - Roadmap Phase 4 image-extract v0.1.0 added and ticked.
- **`tools/save-inspect/` v0.2.0** ships CHAR record body
  decoding. v0.1.0 emitted an opaque hex preview of every
  CHAR's data; v0.2.0 walks the RDFF sub-blocks and decodes
  combat / character / item records to structured JSON.
  - **CHAR body shape** (per libsoloscuro `src/entity.c`
    `sol_entity_load_from_gff`, MIT): a sequence of
    RDFF-headed sub-blocks in positional order: `sub[0]` is
    combat, `sub[1]` is the character record, `sub[2..N-1]` are
    item slots, optionally followed by an `RDFF_END` terminator
    (`load_action == -1`, `len == 0`). The first sub-block's
    `blocknum` field gives the total count.
  - **DS1 schemas**: `ds1_combat_t` (58 bytes; hp / psp / AC /
    THAC0 / stats / 18-char name), `ds_character_t` (71 bytes;
    XP / HP / PSP / race / gender / alignment / stats / class /
    level / saves / sound IDs), `ds1_item_t` (21 bytes; slot /
    item_index / quantity / value / charges / bonus). Ported
    from `libgff` `include/gff/object.h` + `item.h` (MIT;
    annotated `Not confirmed at all` for the item struct by
    upstream).
  - **DS2 schemas differ** (combat 49 bytes, character 66 bytes,
    item 23 bytes). v0.2.0 decodes DS2 items fully and surfaces
    DS2 character names via an ASCII-run heuristic
    (`_likely_name`), but emits combat and character bodies as
    raw hex with `_format: "ds2_or_unknown_..._layout"` rather
    than producing wrong-looking field values. Full DS2 schemas
    are v0.3.0 work.
  - **Enum lookups** added: `gff_race_e` (MONSTER / HUMAN /
    DWARF / ELF / HALFELF / HALFGIANT / HALFLING / MUL /
    THRIKREEN), gender, alignment (9-cell D&D 2e), item slot
    (ARM / AMMO / MISSILE / HAND0..HAND1 / FINGER0..FINGER1 /
    WAIST / LEGS / HEAD / NECK / CHEST / CLOAK / FOOT). Each
    field renders as `{ "value": N, "name": "ENUM" }`.
  - **Back-compat**: the existing `rdff_header`,
    `body_length`, `body_hex_preview` keys still appear on
    every CHAR chunk. The new `body` key is additive.
  - **Empirical** (GOG 1.10): DS1 CHARSAVE.GFF decodes 5/5
    CHARs cleanly (Garn, Aticus, Seneca, Deestan, plus PC).
    DS2 CHARSAVE.GFF decodes 19 CHARs with full item slots;
    DS2 character names surface ("Caron the Unsur", "Anathea",
    "Cermak", "Frin'kal", ...) via the heuristic.
  - Stdlib-only Python; no new dependencies.
  - Roadmap Phase 4 save-inspect v0.2.0 box ticked.
- **`tools/gpl-disasm/` v0.2.1** closes every case v0.2.0
  deferred. The 600 DS1+DS2 GPL/MAS chunks now disassemble at
  **100% alignment** (was 10.7% in v0.2.0).
  - **`gpl_access_complex` ported** (libgff `parse.c` 235-288):
    word `obj_name` + byte `depth` + `depth` bytes of element
    data. `obj_name >= 0x8000` keyword set (POV / ACTIVE /
    PASSIVE / OTHER / OTHER1 / THING) rendered by name.
  - **`GPL_COMPLEX_*` range (`0xB0..=0xBF`)** decodes as
    `Expression::ComplexAccess { tag, obj_name, depth,
    elements }`. The `0xb3` special case is now just one entry
    in that range.
  - **`GPL_RETVAL | 0x80` (`0x8C`)** recursively dispatches the
    inner opcode's parameter shape, using a 21-entry safe-subset
    matching libgff's `gpl_retval` switch
    (`parse.c` 1791-1826). Inner params land in
    `Expression::RetVal { inner_opcode, inner_mnemonic,
    inner_params }`. Recursion bounded by `MAX_RETVAL_DEPTH = 4`.
  - **`gpl_setrecord` (0x40)** promoted from `ParamSpec::Custom`
    to `ParamSpec::SetRecord`: `access_complex + read_number`
    per all three branches of libgff's handler.
  - **`gpl_load_variable` (0x16)** complex-write path now
    decodes via `access_complex` instead of bailing.
  - **Display impl**: ComplexAccess renders as
    `COMPLEX(0x31, POV, depth=2, [4,7])`; RetVal as
    `RETVAL(gpl rand 5)`.
  - **Tests**: 25 unit tests (4 new in v0.2.1 for the new
    cases). Corpus smoke test reports `600/600 aligned`.
  - **Downstream**: `dialog-extract` v0.2.0 picks up 1,194 more
    strings (DS1 17,560 → 17,926; DS2 27,857 → 28,685;
    combined 45,417 → **46,611**). Every dialog-bearing chunk
    now reports `aligned: true`.
  - The factoring also extracted `read_instruction_params_with_depth`
    as a helper shared between the top-level `disassemble()` and
    the RETVAL recursion path.
- **`tools/dialog-extract/` v0.2.0** ships an instruction-aware
  rewrite that consumes `gpl-disasm --json` (gpl-disasm v0.2.0+).
  The heuristic byte-scan from v0.1.0 is retired; byte boundaries
  are now real, eliminating false positives, and text-id
  references resolve via a new `--text-source <RESOURCE.GFF>`
  flag.
  - **New surface**: `GSTRING[id]` references in
    `gpl print string`, `gpl menu`, etc. now resolve to the
    corresponding TEXT chunk in the sibling GFF. NPC names
    ("Garn", "Dag", "Halton", "Sarthana") and dialog snippets
    that lived in `RESOURCE.GFF` rather than inline now surface
    in the JSON.
  - **Surfaced opcodes**: `0x2C gpl log`, `0x42 gpl input string`,
    `0x48 gpl menu`, `0x4F gpl print string`,
    `0x5A gpl string compare`, `0x0A gpl string copy`.
  - **`LSTRING[id]` refs** are captured with `text_id` but
    emitted as `unresolved: true`; resolving them needs a
    per-region / per-script text source that v0.3.0+ will add.
  - **Output shape** gains `source` (`"inline"` /
    `"text:gstring"` / `"text:lstring"`), `text_id` (for refs),
    `unresolved` (true when a ref couldn't be resolved),
    `opcode` and `opcode_name` (the consuming opcode), and
    per-chunk `aligned` (mirrors gpl-disasm's `aligned` flag so
    consumers can filter on best-effort chunks).
  - **Empirical**: DS1 GPLDATA = 17,560 strings (up from
    13,938); DS2 GPLDATA = 27,857 (up from 22,431). Combined
    **45,417** (up from 36,369). The v0.1 inline count was
    slightly higher than v0.2's inline count because v0.1's
    heuristic accepted misaligned-byte garbage decodes; v0.2
    drops those while picking up far more legitimate strings
    via GSTRING resolution.
  - Stdlib-only Python. Shells out to `gpl-disasm --all -o
    <tmpdir> --json` to produce per-chunk JSON files, and to
    `gff-cat extract --all` (only when `--text-source` is used)
    to load the TEXT chunks.
  - CLI: `dialog-extract <file> [--pretty] [-o <out>]
    [--grep <regex>] [--text-source <gff>] [--gpl-disasm <path>]
    [--gff-cat <path>]`. Renamed `--gff-cat` semantics: it's now
    a fallback locator for the text-source workflow, no longer
    the primary extractor.
  - Roadmap Phase 4 dialog-extract v0.2.0 box ticked.
- **`.dso-online/` reference checkout** lands.
  [`greg-kennedy/DarkSunOnline`](https://github.com/greg-kennedy/DarkSunOnline)
  cloned at depth 1 (~2.3 MB) to `.dso-online/` (gitignored).
  License is AGPL-3.0, so this is a research-only mirror; we
  cite individual symbol names from
  `tools/symbols.txt` (3,530 functions, 2,247 globals/labels;
  extracted by Greg from the DSO v1.0 client's Watcom debug
  symbols) as facts, not source code we port. The symbols
  cover most of the engine internals shared between DSO and
  WotR: `ExecuteGpl`, the `Gpl{Tile,Talk,Door,Pickup,Attack,
  Look,Use,UseWith}Check` trigger family, `GplChangeRegion`
  (relevant to the DS2 mines-elevator bug),
  `GplUpdatePsionics`, and the `Gff*` API. **[`docs/dso-symbols.md`](docs/dso-symbols.md)**
  lands as the curation surface: how the symbols were
  extracted, the format, the highest-value candidates for
  `gpl-disasm v0.4.0+` symbol import, and a hand-verified
  catalogue table that grows as we cross-check each name
  against `DSUN.EXE`. Memory note `dso_online_reference` saved.
  Cited from `CREDITS.md` and `docs/upstream-projects.md` §3.
- **`tools/gpl-disasm/` v0.2.0** ships parameter decoding.
  Output is now **one row per instruction** (was one row per
  byte) with formatted parameters: `gpl print string  115,
  "Free! Finally free! I will destroy you all!..."`,
  `gpl load accum  GNUM[1] == 0i8`, `gpl tport  NAME(-22), 255,
  99i8, 99i8, 0i8`. Decoded inline strings now surface
  directly in the disassembly without the v0.1.0 ASCII-run
  heuristic.
  - **Ports** from `dsoageofheroes/libgff` (MIT, attributed
    inline and in `CREDITS.md`):
    - `gpl_read_number` (the variable-length expression
      decoder): 14-bit immediates, `GPL_IMMED_BYTE` / `BIGNUM` /
      `NAME` / `STRING`, variable references with
      `EXTENDED_VAR`, infix operators (`0xD1..=0xDF`), and
      parens. Mirrors libgff's `do_next` operator-loop semantics.
    - `gpl_read_simple_num_var` (variable reference id, 1 or 2
      bytes per `EXTENDED_VAR`).
    - Per-opcode parameter-count table `PARAM_COUNTS[0x81]`,
      derived by reading every handler body in
      `parse.c`.
  - **Port** from `dsoageofheroes/soloscuro-archive` (MIT,
    same author): the 7-bit packed string decoder
    (`read_compressed`) so `GPL_IMMED_STRING` payloads decode
    directly. Same algorithm as the existing Python port in
    `tools/dialog-extract/`.
  - **Structural handlers**: `gpl_load_variable` (0x16, simple
    path; complex-write deferred), `gpl_menu` (0x48, three-
    expression entries terminated by 0x4A), `gpl_search` (0x33,
    SEARCH_QUAL loop), `gpl_log` (0x2C, packed-string only).
  - **Deferred to v0.2.1** (decoded as opaque, marked
    `best_effort`): nested `GPL_RETVAL | 0x80`,
    `GPL_COMPLEX_*` (`0xB0..0xBF`), `gpl_setrecord` (uses
    `access_complex`), and the `0xb3` "passive flag" special
    case. The decoder records the dispatch byte and continues
    best-effort; subsequent instructions inside the same chunk
    may misalign past the deferred case.
  - **New types** (all `serde::Serialize`-derived):
    `DisasmResult` (`{ instructions, bytes_consumed, total_bytes,
    aligned }`), `Instruction` (`{ offset, length, opcode,
    mnemonic, params, best_effort, string_run }`), `Expression`
    (a token in one `gpl_read_number` result), plus `VarKind`,
    `Op`, `StringSubType`, `ParamSpec`.
  - **CLI `--json` flag** emits structured output for downstream
    tools (`dialog-extract` v0.2.0 will consume it).
  - **Workspace**: `serde` and `serde_json` added to
    `tools/gpl-disasm/Cargo.toml` (both already in
    `workspace.dependencies` per spec §7a).
  - **Tests**: 21 unit tests (each Expression case, helpers,
    end-to-end small programs). Corpus integration test now
    tracks two metrics: `bytes_consumed` (every byte must be
    accounted for; asserted equal to `chunk_bytes.len()`) and
    `aligned` percentage (fraction of chunks where no
    `best_effort` was hit and the whole chunk parses cleanly).
    Current corpus: **600 GPL/MAS chunks**, 2.37 M input bytes
    decode into **198,744 instructions** (vs. v0.1.0's 2.37 M
    annotation rows). 10.7% of chunks parse fully aligned;
    the rest hit at least one deferred case (mostly nested
    RETVAL on `gpl_search` / `gpl_clone` / `gpl_request`, or
    a `GPL_COMPLEX_*` record-field access). v0.2.1 closes the
    gap.
  - `docs/gpl-opcodes.md` adds a per-opcode `Params` column
    backed by the new `PARAM_COUNTS` table.
  - `docs/gpl-bytecode.md` §5: v0.2.0 description updated
    (parameter decoding shipped); v0.2.1 carries the deferred
    cases.
  - Roadmap Phase 3 v0.2.0 box ticked.
  - `pick-it-up.md` retired (transient handoff primer).
- **[`CREDITS.md`](CREDITS.md)** lands as a per-feature
  attribution manifest. Each OpenDS feature (FileHeader, TOC
  layout, segmented chunk resolution, writer policy, chunk-type
  catalogue, GPL opcode catalogue, GPL_* constants, 7-bit
  packed-string decoder, RDFF header, PSIN/PSST structs)
  maps to the specific upstream file or function it was
  ported from in `dsoageofheroes/libgff`,
  `dsoageofheroes/soloscuro-archive`, or
  `JohnGlassmyer/dsun_music`. README.md Credits section
  expanded to point at CREDITS.md. Inline citations added
  alongside save-inspect's PSIN / PSST / RDFF-header
  decoders. Existing inline citations in gff-edit, gpl-disasm,
  and dialog-extract verified.
- **`tools/dialog-extract/` v0.1.0** ships (new Python tool;
  Phase 4 Goal-1 deliverable). Pulls inline NPC dialog strings
  from `GPL ` and `MAS ` chunks as JSON.
  - **The headline find from the dsoageofheroes research**:
    GPL inline strings are *not* plain ASCII; they use a
    1-byte type marker (`0x01` INTRODUCE / `0x02` UNCOMPRESSED
    / `0x05` COMPRESSED) followed by a 7-bit packed payload
    terminated by `0x03`. Decoder ported from
    `dsoageofheroes/soloscuro-archive`
    `src/gpl/gpl-string.c` `read_compressed`
    (MIT, Paul E. West et al.; attributed in the script's
    comments). That's why v0.1 byte-mode ASCII-run detection
    didn't surface the dialog text on its own.
  - **v0.1.0 is heuristic**: scans GPL/MAS chunk bytes for
    `GPL_IMMED_STRING | 0x80` (`0x92`) followed by a known
    type byte, then decodes. False positives possible (param
    byte that happens to equal `0x92`); false negatives
    possible (strings referenced via `gpl_get_gstr(id)` from
    external `TEXT` chunks are not yet resolved). README
    documents the limitations.
  - **v0.2.0 plan**: replace the heuristic with
    `gpl-disasm --json` consumption once gpl-disasm v0.2.0
    ships proper instruction-boundary decoding; the 7-bit
    string decoder itself stays.
  - Stdlib-only Python. Shells out to `gff-cat extract --all`
    to handle segmented GPL/MAS chunks rather than
    re-implementing segmented chunk resolution.
  - CLI: `dialog-extract <file> [--pretty] [-o <out>]
    [--grep <regex>] [--gff-cat <path>]`.
  - **Empirical results**: DS1 `GPLDATA.GFF` yields 215
    chunks / **13,938 dialog strings**; DS2 `GPLDATA.GFF`
    yields 316 chunks / **22,431 strings**. Total across both
    games: **36,369 NPC dialog strings**, fully readable
    today. Sample DS1 strings: "Free! Finally free! I will
    destroy you all!", "By the lost gods of Athas, set me
    free!", "I am A'Poss, master of this temple."
- **`.dsoageofheroes/` reference checkout** lands. All 7 repos
  from the dsoageofheroes GitHub org cloned at depth 1
  (~8.7 MB total): `libgff`, `libsoloscuro`, `soloscuro`,
  `soloscuro-archive`, `soloscuro-oldgo`, `soloscuro-orx`,
  `the-dark-lens`. Mostly MIT-licensed. The 7-bit packed
  string format was discovered in soloscuro-archive's
  `gpl-string.c` during this research pass. Memory note
  `dsoageofheroes_reference` saved for future sessions.
  `.gitignore` updated.
- Roadmap Phase 4: dialog-extract v0.1.0 boxes ticked
  (inline strings + `--grep`); text-id reference resolution
  and structured dialog trees roll forward to v0.2.0 and
  v0.3.0.
- **`tools/save-inspect/` v0.1.0** ships (new Python tool;
  Phase 4 Goal-1 deliverable). Dumps a `CHARSAVE.GFF` as JSON
  with per-chunk decoding:
  - `PSIN` chunks decode as a 7-element `types[]` array
    (psionic discipline byte codes; per libgff
    `include/gff/psionic.h` `gff_psin_t`).
  - `PSST` chunks decode as a 34-element `psionics[]` array
    (psionic mastery; per `gff_psionic_list_t`).
  - `TEXT` chunks decode as plain text (CRLF normalised to
    `\n` in JSON output).
  - `CHAR` chunks decode the leading 10-byte
    `gff_rdff_header_t` (load_action, blocknum, type, index,
    from, len) and emit the remaining body as an opaque hex
    preview. Full record schema decoding is per-game (DS1 vs
    DS2 byte layouts differ per `docs/file-formats.md` §2)
    and lands in save-inspect v0.2.0.
  - `SPST`, `CACT`, `PREF`, `GREQ` (DS2-only) chunks emit
    hex previews until their layouts are documented.
  - Stdlib-only Python (no dependency on `gff-cat`
    subprocess). Embedded GFF parser handles indexed chunks
    only; `CHARSAVE.GFF` never uses segmented types, so the
    simplification is sound for this tool.
  - CLI: `save-inspect <file> [-o out.json] [--pretty]`.
    JSON to stdout by default.
  - Verified against DS1 (4.4 KB, 42 chunks, 8 character
    slots) and DS2 (11.7 KB, 98 chunks, 19 character slots);
    "Caron the Unsur..." surfaces as plain bytes in the first
    DS2 CHAR body, confirming the underlying record format is
    a mix of fixed fields and ASCII names.
- Roadmap Phase 4: save-inspect v0.1.0 box ticked; the
  per-game CHAR decoding work and save diffing roll forward
  to v0.2.0 and v0.3.0.
- **`tools/gpl-disasm/` v0.1.0** ships (new Rust crate, the
  Phase 3 keystone). Byte-annotation pass: each byte of a GPL
  or MAS chunk gets a row tagged with libgff's opcode name.
  Parameter decoding is deferred to v0.2.0 (the v0.1.0 output
  treats every byte as a potential opcode, so instruction
  boundaries are not yet aligned with the real program flow).
  CLI subcommands: single-chunk to stdout/file, `--all` bulk
  dump to a directory as `<kind>-<id>.asm`, and `--opcodes` to
  print the embedded catalogue.
  - Opcode catalogue: 129 entries covering bytes `0x00`..`0x80`,
    sourced verbatim from libgff's `gpl_commands` table
    (`dsoageofheroes/libgff` `src/gpl/parse.c` lines
    1554-1684, MIT-licensed, attributed in code).
  - Inline ASCII detection: runs of ≥4 printable bytes get
    a `; "..."` comment annotation on the row that starts them.
  - SIGPIPE-safe (`gpl-disasm ... | head` exits cleanly).
  - 6 unit tests; new corpus integration test
    `tests/corpus_smoke.rs` disassembles every `GPL ` and
    `MAS ` chunk in DS1+DS2 `GPLDATA.GFF` (600 chunks; 2.37M
    input bytes -> 2.37M annotation rows) without panics.
- **`docs/gpl-opcodes.md`** lands: the catalogue table with
  source citation. "Safe in RETVAL context" annotations
  preserved from libgff `gpl_retval` switch (parse.c lines
  1791-1826).
- **`docs/gpl-bytecode.md`** refreshed: Rust (was Python),
  depends on `gff-edit` library (was `gff-tool` JVM jar),
  per-version scope documented (v0.1 byte-annotation → v0.2
  parameter decoding → v0.3 control flow → v0.4 symbols).
- Workspace gains `tools/gpl-disasm` as a member crate;
  depends on `gff-edit` via local path. tools/README.md
  "Shipped" table extended; "Planned" entry for gpl-disasm
  removed.
- Roadmap Phase 3: v0.1.0 boxes ticked (GFF integration,
  annotation, string detection, opcode catalogue, README).
  Parameter decoding and control flow annotated as v0.2.0 /
  v0.3.0 followups.
- **`tools/gff-edit/` v0.4.0**: modder readability layer.
  - `gff-cat extract --all -o <dir>` bulk-dumps every chunk as
    `<kind>-<id>.bin` under a directory.
  - `gff-cat info --json` / `list --json` emit machine-readable
    output. `FourCC`, `FileHeader`, `ChunkRef`, `TypeInfo`,
    `SegmentedInfo`, and `SegEntry` derive (or implement)
    `serde::Serialize`. `ChunkRef::meta_offset` is excluded
    from the JSON surface via `#[serde(skip)]`.
  - `gff-cat dump-text <file> -o <dir>` writes each
    TEXT/ETME/MERR/NAME/SPIN chunk as `<kind>-<id>.txt`. Bytes
    are verbatim (DOS CRLF preserved on disk; modders can edit
    in any editor that handles CRLF, which is most).
  - `gff-cat pack-text <file> <dir> -o <out>` reads every
    `<kind>-<id>.txt` in `<dir>` and re-injects matching chunks
    into the source GFF via `Gff::replace_chunk`.
    Demonstrated end-to-end: dump-text on RESOURCE.GFF
    produces 271 .txt files; pack-text on those files produces
    a GFF byte-identical to the original. Across the full
    corpus, 17/17 text-bearing GFFs round-trip byte-identical.
  - `gff-cat kind <FOURCC>` looks up an embedded catalogue
    sourced from [`docs/file-formats.md`](docs/file-formats.md).
    `gff-cat kind --list` dumps the whole catalogue.
  - Workspace gains `serde` and `serde_json` as pre-approved
    deps per [`spec.md`](spec.md) §7a (format I/O).
  - 16 unit tests (2 new for JSON shape). All Phase 1 tests
    (incl. the byte-identical no-op replace corpus integration
    test) continue to pass.
- **Project priority pivot**: the modding toolkit is now
  framed explicitly as Goal 1, with darkfix patches as Goal 2.
  [`spec.md`](spec.md) §1 reordered to put the toolkit first;
  §1b's tools-first paragraph reframed to say the toolkit
  serves *any* mod author and that our own patch authoring is
  one consumer among many. Memory updated to match. The
  underlying tools-first ordering of the roadmap is unchanged;
  this is a framing pass, not a re-plan.
- **`tools/gff-edit/` v0.3.0**: writer lands. `Gff::replace_chunk`
  in the library; `gff-cat replace <file> <kind> <id>
  <bytes-file> -o <out>` in the CLI. Replacement policy matches
  dsun_music's `GffFile.replaceResource`: in-place if the new
  bytes fit, append at end-of-file otherwise. The chunk's
  `(location, length)` record is rewritten wherever it lives,
  TOC for indexed chunks or the secondary table inside the
  `GFFI` chunk for segmented chunks. `ChunkRef` carries a new
  `meta_offset` field tracking that location during parse. New
  error variants: `ChunkNotFound`, `ChunkTooLarge`. 14 unit
  tests passing (up from 8): in-place same-size, in-place
  shrink, append-grow, segmented replace, no-op-is-identity,
  not-found error. Corpus integration test
  (`tests/corpus_roundtrip.rs`) verifies no-op replace is
  byte-identical on all 128 GFFs in DS1+DS2 (pristine
  innoextract + deployed Wine installs).
- [`docs/file-formats.md`](docs/file-formats.md) §1: documents
  the writer policy (in-place vs append) and how the writer
  uses each chunk's metadata file offset.
- **Phase 1 closed**: the GFF foundation is read-and-write
  complete. Toolkit gains `verify-install` (Python) and
  `gff-edit` (Rust); patches start at Phase 6 or are deferred
  in favour of Phase 4's modder-facing tools per Goal 1.
- **`tools/gff-edit/` v0.2.0**: segmented chunks fully resolved.
  The parser now reads each segmented type's secondary table
  inside the GFFI chunk, reconstructs resource ids from the
  type's segment runs, and appends the resolved `ChunkRef`s to
  `Gff::chunks()` in TOC declaration order. `Gff::find()` and
  `Gff::read()` work for both indexed and segmented chunks
  with no API change. New CLI subcommand: `gff-cat extract
  <file> <kind> <id> [-o <out>]` writes chunk bytes to stdout
  or a file. v0.1's "segmented not listed" caveat removed from
  `gff-cat list`. SIGPIPE-safe (`gff-cat list | head` no
  longer panics). Smoke-tested against 128 GFFs in DS1 and DS2
  with 63,080 chunks resolved; integrity spot-checked against
  manual `dd` slices. New error variants: `MissingGffiType`,
  `SegLocIdOutOfRange`, `SecondaryTableOutOfBounds`,
  `SecondaryTableMismatch`. `dsun_music` and `libgff` cited as
  the format references for segmented resolution.
- `docs/file-formats.md` §1 expanded: documents segmented chunk
  resolution (primary GFFI table, secondary table layout,
  resource-id reconstruction from segment runs). §5 open
  question on segmented chunk layout struck through; resolved.
- **Reference checkout**: `JohnGlassmyer/dsun_music` cloned to
  `.dsun_music/` (gitignored). MIT-licensed Java/Maven project
  with four CLI tools (gff/image/region/xmi) and a shared
  `common` library. Its `GffFile.replaceResource` is the
  source-of-truth reference for our writer's in-place-or-append
  policy; its `PrimaryGffiTable` + `SecondaryGffiTable` confirm
  the segmented chunk resolution layout. Future reference for
  Phase 4 region-view and image extraction work too.
- **`tools/gff-edit/` v0.1.0** ships (Rust crate + `gff-cat`
  binary). Read-only first pass: parses the 28-byte GFF file
  header and the full TOC, including both indexed and segmented
  chunk lists. Library exposes `Gff::open`, `Gff::types`,
  `Gff::chunks`, `Gff::find`, `Gff::read`. CLI subcommands:
  `gff-cat info <file>` (header + TOC summary), `gff-cat list
  <file>` (indexed chunks). Smoke-tested clean against every
  GFF in both pristine innoextract trees (61/61) and both
  deployed Wine installs including save files (67/67).
  Resolving segmented-chunk locations (requires `GFFI`
  cross-reference) and the writer roll forward to v0.2.0 and
  v0.3.0; see [`tools/gff-edit/README.md`](tools/gff-edit/README.md)
  for the crate-level roadmap.
- **Cargo workspace** lands at the repo root. `Cargo.toml`
  declares `tools/gff-edit` as the first member, plus shared
  edition / license / repo metadata and a minimal
  `[workspace.dependencies]` block (clap, anyhow, thiserror).
  Per [`docs/versioning.md`](docs/versioning.md), tools version
  independently; the workspace does **not** carry a shared
  `version.workspace`.
- [`docs/file-formats.md`](docs/file-formats.md) §1 fills in the
  authoritative GFF layout: 7-field file header, TOC header,
  num_types + chunk_list_header + (indexed entry | segmented
  entry) pattern, segmented-flag mask `0x80000000` on
  `chunk_count` (not `chunk_type`). Cross-checked against
  libgff's `gff_open()` loader. §5 open questions updated to
  carry only the genuinely-unresolved items (segmented chunk
  resolution, non-empty free-list layout, `file_flags`/`data0`
  semantics, internal compression).
- **`tools/verify-install/` v0.1.0** ships. Stdlib-only Python.
  Default mode verifies an install against the canonical
  per-game hash manifest; `--capture` mode regenerates the
  manifest from a pristine source.
- Canonical source-hash manifests captured at
  `docs/source-hashes/ds1-gog-1.10.toml` (60 files) and
  `docs/source-hashes/ds2-gog-1.10.toml` (238 files). Captured
  from innoextract of the GOG 1.10 installer RARs in `.games/`.
  Each manifest's `[runtime_state]` block covers saves, audio
  config, DOSBox redistributable, GOG client artifacts, and the
  cloud-saves directory. `[runtime_state]` patterns can override
  `[files]` entries so runtime-mutated files (e.g.
  `DARKRUN.GFF`, `SOUND.CFG`) carry pristine hashes for
  reference without failing verification on a played install.
- [`docs/versioning.md`](docs/versioning.md) lands. Each tool
  and patch carries its own `VERSION` file; tag format
  `<item>-vMAJOR.MINOR.PATCH`. Build descriptors
  (`Cargo.toml` / `pyproject.toml` / `manifest.toml`) read from
  `VERSION`; nothing duplicates it. Items start at 0.1.0; 1.0.0
  is a back-compat commitment, not an automatic milestone.
- [`tools/README.md`](tools/README.md) lands as the toolkit
  index. One line per tool: language, version, purpose.
- Implementation-language policy formalised in
  [`spec.md`](spec.md) §7a: Rust for foundation libraries and
  heavy-lifting tools (`gff-edit`, `gpl-disasm`, `gpl-asm`,
  `region-view`); Python for CLI utilities, patch authoring
  scripts, and the applier. Single-language alternatives were
  considered and rejected. Python target 3.11+, Rust edition
  2024.
- Roadmap annotated per-tool with implementation language and
  full-semver tag format (`v0.1.0`, not `v0.1`).
- Spec §10 and §4 zip / directory examples normalised to
  full-semver tag format.
- `tools/extract.sh` deferred out of Phase 0: developers who
  run the GOG installer already produce the same extracted file
  tree, so the script is not blocking. Reinstated if a
  contributor needs from-installer extraction without running
  the installer.
- Spec §13 / §14 numbering bug fixed (two §13 sections; "Open
  questions" renumbered to §14).
- Initial project skeleton: README, spec, roadmap, docs, per-game
  patch folders (`ds1-patch/`, `ds2-patch/`), logo.
- Project framed as **OpenDS — a community toolkit**: tools,
  patches, and documentation as three first-class deliverables.
  Patches ship as **darkfix-ds1** and **darkfix-ds2**. The full
  engine reimplementation remains the aspiration encoded in the
  project name; not a roadmap commitment ([`spec.md`](spec.md)
  §12).
- Tools-first ordering established
  ([`spec.md`](spec.md) §1b, [`roadmap.md`](roadmap.md)): every
  digging-tool ships before the patches that depend on it.
  Patches start at Phase 6.
- Engine research dossier compiled from public reverse-engineering work.
- GFF file-format catalog documented.
- GPL bytecode editing strategy documented
  ([`docs/gpl-bytecode.md`](docs/gpl-bytecode.md)).
- DSUN.EXE binary patching strategy documented
  ([`docs/binary-patching.md`](docs/binary-patching.md)).
- End-to-end fix authoring workflow documented
  ([`docs/patch-workflow.md`](docs/patch-workflow.md)).
- GOG installer extraction verified locally on Fedora 43.
