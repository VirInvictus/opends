# Patchnotes

Released versions appear here, newest first.

## Unreleased

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
