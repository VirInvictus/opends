# OpenDS — Roadmap

Phased plan. Each phase has a single shippable artifact; later
phases depend on earlier ones. Solo-dev pacing — phases are
sized to fit a weekend or a week, not a quarter.

**Tools come before patches.** Anything that makes the digging
easier is priority over any specific fix. Every digging-tool
ships before the patch that depends on it. The patch phases
(Phase 6 onward) start when the toolkit is sharp enough that
authoring fixes is plumbing, not archaeology.

Each phase ships a deliverable that is useful on its own,
independent of whether later phases happen.

## Phase 0 — Documentation & extraction (current)

**Goal**: every fact we know is written down; both games' files
are extractable on Fedora.

**Ships**: docs + first two tools (`extract.sh`, `verify-install.py`).

- [x] Project skeleton, `.gitignore`, README, spec, roadmap, logo.
- [x] Engine research dossier ([`docs/research.md`](docs/research.md)).
- [x] Format catalog ([`docs/file-formats.md`](docs/file-formats.md)).
- [x] Known-bugs catalog ([`docs/known-bugs.md`](docs/known-bugs.md)).
- [x] Upstream-projects map ([`docs/upstream-projects.md`](docs/upstream-projects.md)).
- [x] GPL bytecode strategy ([`docs/gpl-bytecode.md`](docs/gpl-bytecode.md)).
- [x] Binary patching strategy ([`docs/binary-patching.md`](docs/binary-patching.md)).
- [x] Patch authoring workflow ([`docs/patch-workflow.md`](docs/patch-workflow.md)).
- [x] **Tool**: `tools/verify-install/` (Python, stdlib-only) —
      hashes a player's install, identifies GOG 1.10 / original
      CD / unknown, supports a capture mode for regenerating the
      manifest. Tagged: `verify-install-v0.1.0`. **v0.2.0** adds
      `--json` (stable machine-readable report for CI / the repro
      harness) and `--repair <installer.exe>` (shells to
      `innoextract` to restore canonical bytes; backs up the
      pre-repair files to `__verify-install-backup/<path>`;
      `--dry-run` previews the plan). Tagged:
      `verify-install-v0.2.0`. **v0.3.0** adds `--rollback`
      (inverse of `--repair`; restores every file in the
      `__verify-install-backup/` dir and removes it; pairs
      with `--dry-run`) and `--summary` (one-line plain-
      English status for the common-case modder check; frames
      next-step advice so the user doesn't have to remember
      which flag does what). Tagged: `verify-install-v0.3.0`.
- [x] Source-hash manifests at
      `docs/source-hashes/ds1-gog-1.10.toml` and
      `ds2-gog-1.10.toml` — SHA256 of every shipped file per
      game. Canonical reference; `verify-install` checks against
      these, and future patch `manifest.toml` files cite them.
      Captured from the pristine innoextract of the GOG
      installers under `.games/`.
- [ ] **Tool (deferred)**: `tools/extract.sh` — GOG installer
      (.exe or .rar + .exe) → `.games/ds1/` or `.games/ds2/`.
      Not blocking: developers who run the GOG installer (under
      Wine, on Windows, or natively) already have the same file
      tree. Reinstated if a contributor needs from-installer
      extraction without running the installer.

**Done when**: a working game install + one command →
`verify-install` reports a clean match against the canonical
source-hash manifest for that game. The tool has its own README
and VERSION and is listed in `tools/README.md`.

## Phase 1 — `gff-edit` + `gff-cat` (the foundation)

**Goal**: a pure-Rust GFF reader/writer crate in our own code,
so we don't depend on a JVM tool for the most basic operation.
Every later phase reads or writes GFFs through this.

**Ships**: `tools/gff-edit/` (Rust) as a workspace member crate;
library plus `gff-cat` binary. Tagged release:
`gff-edit-v0.1.0`.

- [x] Parse the 28-byte file header and the TOC per the layout
      documented in
      [`docs/file-formats.md`](docs/file-formats.md) §1.
      (gff-edit v0.1.0; both indexed and segmented TOC types are
      parsed at the type level.)
- [x] Iterator API on the library: `gff.chunks()` returns a slice
      of indexed `ChunkRef`s; `gff.types()` exposes per-type
      metadata including segmented-list details; `gff.find(kind, id)`
      and `gff.read(kind, id)` for targeted access. (gff-edit
      v0.1.0)
- [x] Resolve individual segmented-chunk locations via GFFI
      cross-reference. (gff-edit v0.2.0; 63,080 chunks across
      128 GFFs in DS1+DS2 resolved cleanly.)
- [x] Extract a chunk (indexed or segmented) to a file by
      `(kind, id)`. (gff-edit v0.2.0, `gff-cat extract`.)
- [x] Replace a chunk in-place (or append on grow); rewrite
      the (location, length) record in TOC or secondary table.
      (gff-edit v0.3.0; works for indexed and segmented.)
- [x] Round-trip test: no-op replace produces byte-identical
      output for every GFF in DS1 and DS2 (128/128 corpus
      pass). (gff-edit v0.3.0)
- [x] CLI: `gff-cat info <file>`, `gff-cat list <file>`.
      (gff-edit v0.1.0)
- [x] CLI: `gff-cat extract <file> <kind> <id> [-o <out>]`.
      (gff-edit v0.2.0)
- [x] CLI: `gff-cat replace <file> <kind> <id> <bytes-file>
      -o <out>`. (gff-edit v0.3.0)
- [x] Tested against every shipped GFF in both DS1 and DS2 with
      no parse errors. (gff-edit v0.1.0: 61/61 pristine,
      67/67 deployed.)
- [x] Construction from scratch: `GffBuilder` library type with
      `add_chunk(kind, id, payload)` and `build()`. Indexed-only
      for v0.5.0; corpus round-trip verified structural
      equivalence on 50 indexed-only GFFs (78 segmented skipped
      pending v0.6.0). Tagged: `gff-edit-v0.5.0`.
- [ ] Segmented-type build (the secondary-table + `GFFI`
      cross-reference dance) so the builder covers the full GFF
      feature set. Originally targeted for `gff-edit-v0.6.0`;
      deferred to v0.6.1+ once a downstream consumer needs it.
      v0.6.0 instead landed `gff-cat what` (per-chunk describer
      with tool-dispatch hints) as the higher-value
      human-friendliness piece.

**Done when**: every GFF under `.games/ds1/` and `.games/ds2/`
opens, lists, and round-trips cleanly through the Rust crate
with no Java dependency.

## Phase 2 — DOSBox repro harness

**Goal**: any bug from the known-bugs list can be reproduced on
the local machine in under five minutes. Validation infrastructure
for everything that follows.

**Ships**: `tools/repro/` (Shell + Python) — DOSBox configs,
save library, recording wrapper.

- [x] DOSBox-Staging configured to run DS1 and DS2 reliably on
      Fedora. (repro v0.1.0: `tools/repro/configs/ds[12].conf`,
      overlay-mount discipline so writes never reach the install,
      MEL audio detect gotcha documented and bypassed via a
      sound_ds-derived `SOUND.CFG` staged from the fixture.
      repro v0.2.0 adds the DS2 path via the `ds2-smoke` fixture
      with `imgmount` of `game.ins` for CD audio.)
- [~] Save-state library: per-bug, a save-game placed just
      before the bug-triggering action. Indexed by bug ID. (Two
      smoke fixtures shipped (`ds1-smoke`, `ds2-smoke`) plus a
      `bugs/README.md` catalogue. repro v0.3.0 adds `--play
      --session <name>` so in-game saves persist across runs
      under `$XDG_STATE_HOME/opends-repro/play-<game>-<session>/`
      plus `--list-sessions` and `--reset-session`. Real
      bug-triggering save curation continues alongside input
      automation in v0.3.x / v0.4.0+.)
- [x] Recording wrapper + input automation (repro v0.4.0):
      `[expected].record_video = true` enables `ffmpeg -f
      x11grab` capture to `<scratch>/repro.mp4` (libx264,
      24fps, mute; XWayland surface is visible so GNOME-
      Wayland works without a portal). `[[trigger.keystrokes]]`
      schedule fires `ydotool key`/`type` at scheduled
      offsets from a daemon thread. Both gracefully degrade
      when the dep is missing (log warning, skip automation,
      run still completes). README documents the one-time
      Fedora setup. v0.4.0 unblocks the deterministic-
      execution half of `opcode-fuzz v0.3.0`.
- [ ] Differential capture: run-with-patch and run-without-patch
      side-by-side helper. (v0.4.0+.)

**Done when**: every known bug we plan to fix has a saved game
and a one-command repro. New bugs we discover get added to the
library as we find them. v0.1.0 ships the harness pattern; bug
curation continues in v0.2.0+ as fixtures get added.

## Phase 3 — `gpl-disasm` v0 (the keystone)

**Goal**: every byte of every `GPL ` chunk in DS1 disassembles
into mnemonic form, even if many opcodes are still `db`. This is
the single most important tool — the bulk of patch authoring
runs through it.

**Ships**: `tools/gpl-disasm/` (Rust). Tagged release:
`gpl-disasm-v0.1.0`.

- [x] Read GPL and MAS chunks via our `gff-edit` library.
      (gpl-disasm v0.1.0; smoke-tested against 600 chunks in
      DS1+DS2 GPLDATA.GFF.)
- [x] Print annotated assembly with offset markers.
      (gpl-disasm v0.1.0; byte-annotation pass.)
- [x] String detection: embedded ASCII auto-shown next to the
      bytes that reference it. (gpl-disasm v0.1.0; runs of
      ≥4 printable bytes annotated inline.)
- [x] Document the opcode table as we learn it
      (`docs/gpl-opcodes.md`). (Seed catalogue of 129 entries
      0x00..0x80 from libgff `gpl_commands`; gpl-disasm
      v0.1.0.)
- [x] Tool README with usage examples on real game files.
      (gpl-disasm v0.1.0.)
- [x] Identify entry points and basic-block boundaries.
      (gpl-disasm v0.3.0; recursive-descent CFG with labeled
      successors, `--entries` / `--cfg` / `--no-labels` flags.
      Verified on 600 / 600 DS1+DS2 chunks: 71,403 edges, 1,384
      cross-chunk `global sub` call sites, 0 computed-target
      edges.)
- [x] Decode each opcode's parameters (port libgff's
      `gpl_read_number` / `gpl_get_parameters`). True
      instruction-boundary alignment for the common path
      (gpl-disasm v0.2.0); deferred cases (RETVAL recursion,
      COMPLEX_*, `gpl_setrecord`, complex-write of
      `gpl_load_variable`) closed in v0.2.1. **100% corpus
      alignment on all 600 DS1+DS2 GPL/MAS chunks.**
- [x] Cross-reference with `the-dark-lens` and DSO v1.0 debug
      symbols; emit a `syms.toml` we curate by hand and grow
      over time. (gpl-disasm v0.4.0: `tools/gpl-disasm/syms/`
      with `opcodes.toml` + `functions.toml` schemas; function-
      entry decoration wired through text and JSON output;
      starter catalogue ships 2 verified entries. v0.4.2 ships
      opcode-mnemonic override wiring; variable naming remains
      a follow-up.)
- [x] Inter-chunk control-flow graph (gpl-disasm v0.4.1):
      `--global-cfg <path>` aggregates per-chunk
      `cross_chunk_calls` into a whole-GFF callgraph. 250 nodes
      / 587 edges for DS1; 350 nodes / 797 edges for DS2;
      combined 1,384 edges matches the v0.3.0 corpus soundness
      count exactly. Symbol-derived caller/callee names flow
      through edge metadata.
- [x] Opcode-mnemonic overrides (gpl-disasm v0.4.2):
      `syms/opcodes.toml` rows rewrite `Instruction.mnemonic` in
      both text and JSON output via
      `Symbols::apply_to_mnemonics`. Ships with the catalogue
      empty by design and a documented curation rule.
- [x] Per-chunk local-variable overlays (gpl-disasm v0.6.0):
      `syms/locals.toml` with per-kind tables
      (`[[lbyte]]` / `[[lnum]]` / ...) keyed by `(file, kind,
      chunk_id, id, name)`. `Symbols::apply_to_locals` walker
      mirrors the v0.5.0 globals path with chunk context;
      catalogue ships empty by design.
- [x] DSO-symbol importer (gpl-disasm v0.6.0):
      `scripts/import-dso-symbols.py` (stdlib-only) parses
      `.dso-online/tools/symbols.txt` and emits review-ready
      proposals: 100 opcode-byte rename candidates by libgff /
      DSO PascalCase equivalence, plus 15 unmatched DSO
      `Decode*` handlers (candidates for libgff's
      `gpl default` rows). Script is the review surface; no
      automatic commits.

**Done when**: `gpl-disasm .games/ds1/GPLDATA.GFF` produces
output that lets a reader locate a quest-script function by
name (or by nearby string reference) and read its control
flow. v0.1.0 shipped the byte-annotation foundation; v0.2.0
ships true instruction boundaries on the common path; control
flow comes in v0.3.0.

## Phase 4 — Exploration tools

**Goal**: the digging surface widens. Tools that let us locate
which chunk a bug lives in, see the state a fix changes, and
look at the maps directly.

**Ships**: three tools, each with its own tag.

### `tools/dialog-extract/` (Python)

- [x] Pull inline NPC dialog strings from GPL/MAS chunks as
      structured JSON. (dialog-extract v0.1.0; heuristic
      IMMED_STRING scan + 7-bit decoder ported from
      soloscuro-archive. 13,938 strings from DS1 GPLDATA, 22,431
      from DS2, total 36,369.)
- [x] Search-friendly: `dialog-extract --grep "Magnolia"` finds
      chunks whose inline strings match the pattern.
      (dialog-extract v0.1.0.)
- [x] Resolve text-id references (`gpl_get_gstr(id)`,
      `gpl_get_lstr(id)`) into the matching TEXT chunks for a
      complete dialog set. (dialog-extract v0.2.0: GSTRING refs
      resolve against `--text-source RESOURCE.GFF`. LSTRING refs
      resolve via path-aware LSTR-slot tracking in
      dialog-extract v0.4.0: 96.4% of corpus reads now resolve;
      the remaining 32 reads are caller-populated slots resolved
      via inter-chunk expansion.)
- [x] Output a richer `{ speaker, lines, branches, gpl_refs }`
      tree once instruction boundaries from gpl-disasm v0.2.0
      let us correlate strings to the surrounding control flow.
      (dialog-extract v0.3.0: CFG-aware `dialog_tree` built on
      `gpl-disasm v0.3.1`'s CFG. 46,611 lines across 4,229
      declared + 15,027 discovered entry-point walks; 0
      invariant violations on the DS1+DS2 corpus.)
- [x] Inter-chunk dialog tree walking: `gpl global sub` call
      sites expand inline under the calling block as
      `cross_chunk_call` subtrees, using `gpl-disasm`'s per-
      chunk `cross_chunk_calls` metadata. (dialog-extract
      v0.4.0: 889 DS1 + 1,014 DS2 expansions; 666 + 806 fully
      resolved; cycles, mid-function calls, and cross-GFF calls
      surface as explicit unresolved markers with reasons.)
- [x] LSTR tail closer (dialog-extract v0.5.0): the 32
      previously-unresolved LSTR reads each now carry a
      `possible_writers` array drawn from the global LSTR-write
      index and narrowed by the inter-chunk callgraph
      (`gpl global sub`). DS1 + DS2 average 4.0 / 6.7 writers
      per unresolved read after narrowing; **zero** corpus LSTR
      reads lack a statically-reachable writer. New `lstr_stats`
      top-level field + stderr stats line. Path-aware caller
      picking (CFG-distance ordering or symbolic trace) is
      queued for v0.6.0+.
- [x] **Human-readable output** (dialog-extract v0.7.0):
      `--format transcript` (per-NPC plain-text listing; DS1
      GPLDATA emits 18349 lines covering 215 chunks / 17699
      strings) and `--format html` (single-file static page
      with embedded CSS, collapsible `<details>` per chunk,
      colour-coded unresolved strings). New
      `syms/speakers.toml` curated chunk-id → NPC name
      catalogue; missing rows fall back to "GPL chunk N".
      `--format json` (default) unchanged for back-compat.
- [x] Tagged: `dialog-extract-v0.1.0`. (this release)

### `tools/save-inspect/` (Python)

- [x] Read `CHARSAVE.GFF` and dump as JSON. (save-inspect
      v0.1.0; decodes PSIN/PSST/TEXT plus the CHAR RDFF header;
      opaque hex preview for CHAR body, SPST, CACT, PREF, GREQ.)
- [x] Decode CHAR record body per DS1 RDFF schemas (combat,
      character, item sub-blocks): hp/psp/stats/AC/THAC0, race/
      alignment/class/level enums, item slots and indices.
      (save-inspect v0.2.0; DS1 fully decoded, DS2 surfaces
      names + raw hex as a heuristic until DS2 schema is
      fully RE'd in v0.3.0+.)
- [x] Diff two saves: structured JSON diff with `path` /
      `kind` / `from` / `to` records per change.
      (save-inspect v0.3.0: `save-inspect.py diff a.GFF
      b.GFF`.)
- [x] DS2 combat partial decode: DS1-shared prefix bytes
      (HP, PSP, ids, item indices, special_*) plus heuristic
      stats lookup 8 bytes before the name. (save-inspect
      v0.3.0.)
- [x] DS2 combat **full** structured schema. v0.4.0 locks the
      49-byte layout (shared 24-byte prefix, `_reserved_0`,
      `stats[6]`, `_slot_31`, `_reserved_1`, `name[16]`), with
      first-class `stats` + `name` fields replacing v0.3.0's
      `_likely_*` heuristics. Three positions (24, 31, 32)
      still ship as opaque bytes pending DSUN.EXE RE.
- [x] DS2 **character** sub-block (66 bytes). save-inspect
      v0.5.0 locks the layout: DS1's 72-byte structure minus
      `_data2` (4 bytes) and two of `(race, gender, alignment)`
      (2 bytes). All 19 DS2 CHAR records decode with stats in
      the 3..25 D&D 2e range, alignments in the documented
      0..8 set, HP / PSP matching the combat sub-block.
- [x] DS2 **item** sub-block (23 bytes). save-inspect v0.6.0
      validates that libgff's `ds1_item_t` schema is exactly
      DS2's wire format: 151 items across played + factory
      DS2 CHARSAVEs decode with zero truncations, including
      the trailing `priority` + `data0` pair that DS1 omits.
      Per-item `_format` tag (`ds1_item` / `ds2_item`) added.
      Save-slot files (`SAVE0N.SAV`) discovered to be
      byte-identical snapshots of `DARKRUN.GFF`; save-inspect
      reads them natively.
- [x] **Save-edit write path** (save-inspect v0.8.0): every
      existing decoder gets a sibling encoder (combat /
      character / item DS1+DS2; PSIN/PSST/TEXT/STXT/SAVE/
      ETME/ETAB) plus a pure-Python `write_gff` that inverts
      `parse_gff`. New `save-edit` subcommand (JSON-in,
      GFF-out, backup + dry-run) plus a `roundtrip`
      regression test that hits 100% chunk-level
      byte-identity on every CHARSAVE / DARKSAVE / DARKRUN
      in the corpus (27/27 + 98/98 + 1/1 + 63/63).
      End-to-end smoke proves the modder workflow: edit a
      PC's HP field in the JSON, save-edit, re-decode, HP
      updated. The first true mod workflow on the toolkit.
- [~] **SAVE chunk structural decode** (save-inspect v0.7.0):
      per-region world state inside `DARKRUN.GFF` (~60 per
      save). Schema is empirically incomplete, so v0.7.0
      surfaces what's locked (chunk-id-keyed shape; u16
      scalars in the 2-byte chunk family at ids 10..17; ETME
      template text; STXT save name) and leaves the rest as
      opaque hex with the per-game tag `_format:
      ds1_save_chunk`. New `save-diff` subcommand operates at
      the chunk-byte level: per-chunk byte-diff counts plus
      first-diff offsets, defaulting to SAVE chunks only.
      Field-by-field RE continues as more played saves
      surface; the v0.7.0 deliverable is the harness the RE
      runs through, not the full schema.
- [~] **SAVE chunk decode for DS1 party records**
      (`tools/save-inspect/scripts/ds1-party-edit.py`,
      2026-05-18): SAVE/5 RE'd as an array of DS1 combat
      sub-blocks (58 bytes each, libgff `ds1_combat_t`
      layout); SAVE/6 RE'd as DS1 character sub-blocks
      (71-72 bytes, libgff `ds1_character_t`). One per
      active party PC in display order. End-to-end edit
      tested against Brandon's played save (stats, HP,
      weapon damage). Full layout documented in
      `docs/file-formats.md` §3. The other ~58 SAVE chunks
      remain opaque; this opens the modder-facing path for
      DS1 active-party edits without requiring full
      per-chunk RE.
- [ ] RE the remaining `DARKRUN.GFF` SAVE chunks: SAVE/1 (the
      largest at ~10 KB; probably the master per-region state
      table), SAVE/2-/4 and /7-/9, the u16 scalar family at ids
      10..17 (identify what each counter / pointer represents),
      and the 51-byte SAVE/18 boolean array (all 0x01 in the
      reference played save; region-visited flags?). Bootstrap
      empirically with the v0.7.0 `save-diff` harness: snapshot,
      do one in-game action, snapshot, diff. Document each
      locked layout in `docs/file-formats.md` §3 and extend
      `ds1-party-edit.py` (or a sibling `ds1-world-edit.py`)
      with editable accessors. Quest and world-state fixes
      need this; without it they're raw byte edits with no
      schema safety.
- [x] **Modder-altitude PC edit surface** (save-inspect
      v0.9.0 - v0.9.4): `list-pcs`, `list-items`, `edit-pc`,
      `edit-item`, `give-item`, `find-empty-slots` for
      CHARSAVE-based edits (works for DS2 active party + DS1
      inactive char templates). Plus `scripts/ds1-party-
      edit.py` for DS1 active-party edits via DARKRUN.
      Cookbook entries at `docs/cookbook/`.
- [x] Tagged: `save-inspect-v0.1.0`. (this release)

### `tools/image-extract/` (Rust)

- [x] Pull bitmap chunks (`BMP `, `PORT`, `ICON`, `BMAP`, `OMAP`,
      `TILE`) out as palette-indexed PNG. Decodes DS1 RLE
      (per-row spans with even/odd code split) and PLNR
      (bit-packed dictionary) frame formats. Palette parser
      for `PAL ` / `CPAL` chunks with libgff's 6-bit → 8-bit
      `intensity_multiplier`. (image-extract v0.1.0; 1,328 of
      1,976 frames across DS1+DS2 decode cleanly; the
      remaining ~648 were PLAN frames + 410 PLNR frames that
      hit libgff's lossy "split bits!" chomp.)
- [x] PLAN frame format support. (image-extract v0.2.0: PLAN
      decoder ported from `dsun_music`'s `ImageReading`;
      simultaneously fixed PLNR's chomp by switching to the
      same big-endian chomper. Corpus now decodes 1,975 / 1,976
      frames = **99.95%**; image-extract v0.2.1 root-causes
      the lone non-decoded frame as DS1
      `RESOURCE.GFF:ICON/0x7f9` frame 2, a malformed chunk in
      the GOG 1.10 ship (3 frames declared, space for ~2.5).
      The decoder reports `FrameOutOfBounds` and the corpus
      test pins it as the only expected failure.)
- [ ] Sprite-frame animation export (multi-frame BMPs as GIF /
      animated PNG / spritesheet).
- [x] Tagged: `image-extract-v0.1.0` (initial); `image-extract-v0.2.0`
      (PLAN + PLNR fix); `image-extract-v0.3.0` (multi-frame
      export); `image-extract-v0.4.0` (`image-pack` companion
      binary: palette-indexed PNG → DS1 RLE BMP chunk; 883 / 883
      corpus DS1 RLE frames round-trip pixel-identical;
      multi-span row emission handles 320-pixel sprite rows
      that exceed the single-span 255-byte cap).

### `tools/region-render/` (Rust)

The interactive SDL2 viewer was descoped in favour of a static
PNG emitter for v0.1.0: ships sooner, fits the "screenshot first,
interactive later" pattern the toolkit follows elsewhere, and
gives modders the visual artifact without an SDL2 dependency.
Interactive viewing rolls into a future `region-view` release if
the friction is felt.

- [x] Open a single region GFF and composite the background-tile
      layer (`RMAP` for DS1, `MAP ` for DS2 + per-region `TILE`
      bitmaps) into a 2048 x 1568 palette-indexed PNG.
      (region-render v0.1.0; corpus smoke renders 35 DS1 + 18
      DS2 regions cleanly, 0 missing-tile bytes across the
      corpus.)
- [x] Palette discovery for DS2 (inline `PAL ` chunk).
- [x] Palette fallback for DS1 (sibling
      `RESOURCE.GFF:PAL :1000`) plus `--palette <gff>:<kind>:<id>`
      and `--palette-file <raw>` override flags.
- [x] Walls (`GMAP` lower 5 bits + per-region `WALL` chunks).
      (region-render v0.2.0: DS1 walls load from sibling
      `GPLDATA.GFF`; corpus has 350 sprites across 35 regions
      with 0 decode failures. DS2 storage TBD.)
- [x] Entity sprites (`ETAB` + `OJFF` + `BMP `). (region-render
      v0.3.0: DS1 entities load from sibling `SEGOBJEX.GFF`,
      DS2 from `OBJEX.GFF`. Corpus: 26,587 ETAB records,
      8,223 distinct sprites, 0 missing ids, 0 decode failures.)
- [ ] Animated palette colours. Needs `DSUN.EXE` RE; the
      `dsun_music/region-tool` Java reference has a TODO at
      line 180. v0.5.0 RE pass located `VGAColorCycle` and
      `gCycleColor` candidates in the DSO symbol table but
      hasn't decoded the cycle-table layout yet; still queued.
- [~] Per-region palette discovery for DS1. **Partial.** v0.5.0
      RE pass located the engine routine: at DS1 `DSUN.EXE`
      file offset `0x56ad3..0x56b00`, the engine calls
      `load_resource('CMAT', si, &cmat_buf)` then (on failure)
      `load_resource('CPAL', si, &cpal_buf)` with the same
      region-derived family id `si`, which resolves to 200 or
      300 in `RESOURCE.GFF`. Default fallback updated from
      `PAL :1000` (menu palette, never used for regions) to
      `CPAL:200` (engine-default). What's still open: tracing
      the caller to find the region-number-to-family-id map.
      Write-up at `docs/dsun-exe-re.md`.
- [x] **Animated GIF output** (region-render v0.7.0): new
      `--gif` flag bundles the `--animate-entities` PNG
      sequence into a single shareable GIF via a two-pass
      ffmpeg pipeline (palettegen + paletteuse with
      `dither=none` for clean pixel-art colour fidelity).
      Default 8 fps; `--gif-fps N` overrides. Frames stay in
      a sibling `<stem>-frames/` directory for editing reuse.
      ffmpeg detected via stdlib-only `$PATH` lookup; missing
      dep gets a clear error. Text annotations
      (`--annotate` entity-name overlays) deferred to v0.7.1
      (no in-tree Rust font without a new dep).
- [x] Tagged: `region-render-v0.1.0`. (this release)

**Done when**: dialog-extract, save-inspect, image-extract, and
region-render all exist with their own READMEs, each tagged at
`v0.1.0`, and `tools/README.md` indexes them.

## Phase 5 — `gpl-asm` + `opcode-fuzz`

**Goal**: close the GPL loop. Be able to write GPL bytecode, not
just read it. Be able to discover unknown opcodes systematically.

**Ships**: two tools.

### `tools/gpl-asm/` (Rust)

- [x] Round-trip reassembler: `gpl-disasm --json` → bytecode.
      (gpl-asm v0.1.0; 456/600 DS1+DS2 chunks round-trip
      byte-identical out of the box.)
- [x] Preservation field for `gpl_search` (0x33) side bytes:
      raw payload bytes captured on `Instruction` and on
      `Expression::RetVal::inner_raw_tail` so the encoder can
      reproduce them. **(gpl-disasm v0.4.5 + gpl-asm v0.1.1:
      corpus round-trip is now 600/600 byte-identical.)**
- [x] Text-listing parser: consume `gpl-disasm`'s text output
      as input alongside the JSON path. (gpl-asm v0.2.0:
      456/456 non-Search chunks via `--no-labels`. v0.2.1 +
      `gpl-disasm` v0.4.6: labelled form + `; raw_tail=HEX`
      trailers, **600 / 600** chunks round-trip byte-identical
      through `bytes -> disasm -> labelled text -> parse ->
      encode`. CLI auto-detects JSON vs text from extension.)
- [x] Structural edits: `Editor::insert_instruction(at, instr)`
      / `delete_instruction(at)` / `replace_instruction(at,
      with)` API that recomputes branch targets and offsets.
      (gpl-asm v0.3.0; 6 new unit tests cover insert / delete /
      replace + branch retargeting.) Unblocks fixes that need
      to insert or delete bytes without no-op padding.
- [x] Label-relative editing API
      (`Editor::insert_before_label("label_0x...", instr)`) +
      parser support for arbitrary user-chosen label names so
      modders can name their own branch targets. (gpl-asm
      v0.4.0; 6 new unit tests cover both halves.)
- [x] Author safety net (gpl-asm v0.5.0): rustc-style caret
      parse errors (`format_with_caret`, `error_line`,
      `error_span`) anchor `ParseError` variants in the source,
      and a static `validate()` pass (branch-target bounds,
      `Immediate14` 15-bit overflow, RetVal depth) wired as the
      default pre-encode check (`--validate-only`,
      `--no-validate`). Corpus validates 600 / 600 clean.
- [x] Authoring conveniences (gpl-asm v0.6.0): `%define
      <name> <replacement>` for token substitution and
      `%search-tail <hex-bytes>` for ergonomic raw-tail
      composition on `gpl_search`. Reject lists on `%define`
      names cover operator words, variable shorts, keyword
      tokens, and mnemonic words. Directive lines blank-
      replace so caret error line numbers still match the
      user's source. Corpus stays at 600 / 600. Parameterised
      macros and `@include` directives are queued for v0.7.0+.
- [x] **Declarative patch-script mode** (gpl-asm v0.8.0):
      `gpl-asm --patch fix.patch chunk.bin -o new.bin`
      applies offset-based byte edits from a TOML script. Each
      `[[edit]]` carries `at_offset`, `bytes_old`
      (fingerprint-verified; refuses to apply on mismatch),
      `bytes_new` (same length), and an optional `reason`.
      `--dry-run` previews. The authoring surface darkfix
      patches will use for 1-3 byte tweaks once Phase 6
      starts. Label-relative addressing
      (`at = "label_0x42 + 3"`) deferred (see below).
- [ ] Label-relative patch addressing for `--patch` scripts:
      `at = "label_0x42 + 3"` and `at = "<name> + N"` with
      names resolved from `syms/functions.toml`, so darkfix
      authoring doesn't require hand-counted byte offsets.
      Resolver disassembles the target chunk, resolves the
      label, computes the absolute offset; the `bytes_old`
      fingerprint check stays mandatory. Was pencilled in as
      v0.8.1; lands as v0.9.0 (v0.8.1 shipped as the
      text-parser length-accounting bugfix instead).
- [x] Tagged: `gpl-asm-v0.1.0`. (this release)

### `tools/opcode-fuzz/` (Python; drives DOSBox debugger over IPC)

- [x] Chunk-patchwork pipeline (opcode-fuzz v0.1.0): `extract`
      stages a GPL/MAS chunk for editing; `pack` re-encodes
      the (possibly edited) work-dir back into a patched GFF;
      `roundtrip` corpus self-test verifies every GPL/MAS
      chunk in DS1 (250 / 250) and DS2 (350 / 350) survives
      `extract -> disasm -> reasm -> replace` byte-identical.
      The foundation v0.2.0+ builds on.
- [~] Harness that runs the original game in DOSBox with a
      single GPL chunk swapped to a one-opcode test.
      (opcode-fuzz v0.2.0: `run` subcommand packs a work-dir,
      synthesises a repro fixture that stages the patched
      GPLDATA.GFF, launches DOSBox via `repro.py --play
      --session`, snapshots c-overlay/DARKRUN.GFF before and
      after, emits a JSON byte-level diff. Sessions live in
      the same XDG state path as `repro --play`; resumable.
      What's still required for the full discovery loop:
      input automation (`repro v0.3.x` ydotool integration)
      to drive the engine to the state where the chunk fires,
      plus identification of which chunks the engine invokes
      on boot via `DSUN.EXE` RE.)
- [~] Records the engine state delta (memory regions, register
      state via DOSBox debugger). (opcode-fuzz v0.2.0: byte-
      level diff against `DARKRUN.GFF` pre/post; the cheap path
      observing `DARKRUN.GFF` / `SAVE0N.SAV` diffs rather than
      live debugger inspection, leveraging save-inspect v0.6.0.)
- [ ] The fastest path to filling in unknown opcodes; turns
      "guess from context" into "observe the effect."
- [x] **Boot-chunk identification** (opcode-fuzz v0.3.0): new
      `boot-chunks <gff>` subcommand drives `gpl-disasm
      --global-cfg --json` and surfaces every chunk with zero
      inbound `gpl global sub` edges (the engine must dispatch
      them directly; safest swap targets for fuzz runs). DS1
      GPLDATA: 129 boot candidates / 250 chunks; DS2: 196 /
      350. `recipes/` scaffold lands as forward-looking
      documentation; recipe-driven `fuzz` ships in v0.3.1+
      once the recipe format (short-form mnemonics vs JSON vs
      gpl-asm extension) settles.
- [x] Tagged: `opcode-fuzz-v0.1.0`. (chunk pipeline)

**Done when**: we can author and verify a synthetic GPL chunk
end-to-end, and `opcode-fuzz` can discover at least one
previously-unknown opcode and add it to `docs/gpl-opcodes.md`.

## Phase 6 — First DS1 fix shipped (pipeline proof)

**Goal**: prove the patch pipeline end-to-end on the smallest
possible DS1 bug. By this point the toolkit is sharp enough that
authoring should feel like routine work.

**Ships**: `darkfix-ds1-v0.1.0`.

- [ ] Darkfix distribution format per `spec.md` §4:
      `manifest.toml` schema (target hashes, fix list, on/off
      state), `apply.py` applier (verify install hashes against
      the manifest, back up to `darkfix-backup/`, apply each
      enabled fix, write `darkfix-applied.json`), and `apply.py
      --unapply` restore. Prove the package shape with a no-op
      fix that applies and unapplies cleanly before any real
      fix ships.
- [ ] Pick one trivial DS1 bug (identified during Phase 2 repro
      work).
- [ ] Repro fixture for the chosen bug
      (`tools/repro/bugs/<id>/bug.toml`) so the fix is
      verifiable. Requires ydotool installed locally; repro
      v0.4.0 already integrates the input automation.
- [ ] Author the fix using `gpl-disasm` + `gff-edit`.
- [ ] Author the test (hash before/after, in-game repro via
      `tools/repro/`).
- [ ] Tag `darkfix-ds1-v0.1.0`, push GitHub release.
- [ ] Player-facing README explaining install.
- [ ] Cookbook entry: `docs/cookbook/author-first-darkfix.md`,
      the workflow written down while it's fresh.

**Done when**: a stranger could download the v0.1 zip, run
`apply.py`, launch DS1 in DOSBox, and the bug is gone.

## Phase 7 — DS2 mines elevator (the headline)

**Goal**: fix the most famous DS2 bug — the one that broke the
late game in 1994 and has never been fixed.

**Ships**: `darkfix-ds2-v0.1.0`.

- [ ] DS2 active-party edit surface, verified end-to-end:
      confirm in a loaded game that CHARSAVE edits via
      `save-inspect` cover the DS2 active party (the v0.6.0
      finding says DS2 CHARSAVE *is* the active party, but
      this has only been exercised via `repro.py --play`
      session saves, never a live install). If DS2 turns out
      to have a DARKRUN-side layout like DS1's SAVE/5-/6,
      RE it and build the sibling tooling. Cookbook entry
      mirroring `edit-ds1-party.md` either way; darkfix-ds2
      authoring needs this fluency.
- [ ] Reproduce in DOSBox via `tools/repro/`.
- [ ] Locate the GPL function or DSUN.EXE routine controlling
      the elevator transition (use `dialog-extract` and
      `gpl-disasm` to narrow it down).
- [ ] Diagnose the race / state bug.
- [ ] Author the fix (data or binary, whichever it lives in).
- [ ] Verify a full DS2 playthrough does not reproduce the
      original behavior.

**Done when**: a player who hits the elevator gets to the next
region, with a full party, on a clean install with the patch
applied.

## Phase 8 — DS2 sweep

**Goal**: every bug in [`docs/known-bugs.md`](docs/known-bugs.md)
section 2 (community-reported, post-1.10) has either a fix or an
explicit "won't fix" note with rationale.

**Ships**: `darkfix-ds2-v0.5.0`.

- [ ] Charged-weapon disappearance.
- [ ] Doorway / item graphics layering.
- [ ] Save/exit bug.
- [ ] Audio static (verify no-op for OPL/MT-32 emulation paths).
- [ ] MEL DSP detect (verify no-op for DOSBox).

## Phase 9 — DS1 sweep

**Goal**: same as Phase 8, for DS1's known issues.

**Ships**: `darkfix-ds1-v0.5.0`.

- [ ] Compile a more thorough DS1 bug list (DS1 is less
      documented; we will find issues during this phase).
- [ ] Fix each.

## Phase 10 — v1.0 for both games

**Goal**: the patches reach a state where they can be
recommended to fellow Dark Sun players in good conscience.

**Ships**: `darkfix-ds1-v1.0.0` and `darkfix-ds2-v1.0.0`.

- [ ] Full playthrough of DS1 with the patch on; no workaround
      needed.
- [ ] Full playthrough of DS2 with the patch on; no workaround
      needed.
- [ ] Player-facing documentation: how to install, how to
      verify, how to report a bug.
- [ ] Public announcement.

## Phase 11+ — Engine plausibility (deferred)

If the toolkit accumulates enough — `gpl-disasm` with most
opcodes documented, working `gpl-asm`, native GFF read/write,
region viewer, save inspector — then **OpenDS the engine**
becomes plumbing rather than reverse-engineering. At that point
spinning it up makes sense.

We do not commit to a date. We commit to building the toolkit
that makes it possible. If someone else picks up the toolkit
and ships an engine first, that is a successful outcome.
