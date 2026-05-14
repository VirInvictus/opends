# Patchnotes

Released versions appear here, newest first.

## Unreleased

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
