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
      manifest. Tagged: `verify-install-v0.1.0`.
- [x] Source-hash manifests at
      `docs/source-hashes/ds1-gog-1.10.toml` and
      `ds2-gog-1.10.toml` — SHA256 of every shipped file per
      game. Canonical reference; `verify-install` checks against
      these, and future patch `manifest.toml` files cite them.
      Captured from the pristine innoextract of the GOG
      installers under `.games/`.
- [ ] **Tool (deferred)**: `tools/extract.sh` — GOG installer
      (.exe or .rar + .exe) → `extracted/ds1/` or `extracted/ds2/`.
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
      [`docs/file-formats.md`](../docs/file-formats.md) §1.
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

**Done when**: every GFF under `.games/ds1/` and `.games/ds2/`
opens, lists, and round-trips cleanly through the Rust crate
with no Java dependency.

## Phase 2 — DOSBox repro harness

**Goal**: any bug from the known-bugs list can be reproduced on
the local machine in under five minutes. Validation infrastructure
for everything that follows.

**Ships**: `tools/repro/` (Shell + Python) — DOSBox configs,
save library, recording wrapper.

- [ ] DOSBox-Staging configured to run DS1 and DS2 reliably on
      Fedora.
- [ ] Save-state library: per-bug, a save-game placed just
      before the bug-triggering action. Indexed by bug ID.
- [ ] Recording wrapper: one command, one bug ID → DOSBox
      launches at the right save, records video to
      `scratch/<bug-id>/repro.mp4`.
- [ ] Differential capture: run-with-patch and run-without-patch
      side-by-side helper.

**Done when**: every known bug we plan to fix has a saved game
and a one-command repro. New bugs we discover get added to the
library as we find them.

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
- [ ] Identify entry points and basic-block boundaries.
      (gpl-disasm v0.3.0; needs parameter decoding first.)
- [ ] Decode each opcode's parameters (port libgff's
      `gpl_read_number` / `gpl_get_parameters`). True
      instruction-boundary alignment. (gpl-disasm v0.2.0)
- [ ] Cross-reference with `the-dark-lens` and DSO v1.0 debug
      symbols; emit a `syms.toml` we curate by hand and grow
      over time. (gpl-disasm v0.4.0+)

**Done when**: `gpl-disasm extracted/ds1/GPLDATA.GFF` produces
output that lets a reader locate a quest-script function by
name (or by nearby string reference) and read its control
flow. v0.1.0 ships the byte-annotation foundation;
true-boundaries-and-control-flow comes in v0.2.0 and v0.3.0.

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
- [ ] Resolve text-id references (`gpl_get_gstr(id)`,
      `gpl_get_lstr(id)`) into the matching TEXT chunks for a
      complete dialog set. Currently only inline strings are
      captured. (dialog-extract v0.2.0; depends on gpl-disasm
      v0.2.0 + cross-chunk reference resolution.)
- [ ] Output a richer `{ speaker, lines, branches, gpl_refs }`
      tree once instruction boundaries from gpl-disasm v0.2.0
      let us correlate strings to the surrounding control flow.
      (dialog-extract v0.3.0.)
- [x] Tagged: `dialog-extract-v0.1.0`. (this release)

### `tools/save-inspect/` (Python)

- [x] Read `CHARSAVE.GFF` and dump as JSON. (save-inspect
      v0.1.0; decodes PSIN/PSST/TEXT plus the CHAR RDFF header;
      opaque hex preview for CHAR body, SPST, CACT, PREF, GREQ.)
- [ ] Decode CHAR record body per DS1 / DS2 RDFF schemas
      (stats, inventory, spell slots). Per-game work blocked
      on `docs/file-formats.md` §2's per-game schema research.
      (save-inspect v0.2.0)
- [ ] Diff two saves: party state, inventory, flags.
      (save-inspect v0.3.0)
- [x] Tagged: `save-inspect-v0.1.0`. (this release)

### `tools/region-view/` (Rust + sdl2)

- [ ] Minimal SDL2 window that opens a single region GFF and
      draws the tilemap + sprite layer + entities.
- [ ] No interaction yet — just a view.
- [ ] Camera pan + zoom for inspection.
- [ ] Useful for "what does this region actually look like" and
      "is this entity placed where I think it is."
- [ ] Tagged: `region-view-v0.1.0`.

**Done when**: all three tools exist with their own READMEs,
each tagged at `v0.1.0`, and `tools/README.md` indexes them.

## Phase 5 — `gpl-asm` + `opcode-fuzz`

**Goal**: close the GPL loop. Be able to write GPL bytecode, not
just read it. Be able to discover unknown opcodes systematically.

**Ships**: two tools.

### `tools/gpl-asm/` (Rust)

- [ ] Round-trip reassembler: `gpl-disasm` output → bytecode.
- [ ] Unblocks fixes that need to insert or delete bytes
      (currently we'd work around with no-op padding only).
- [ ] Tagged: `gpl-asm-v0.1.0`.

### `tools/opcode-fuzz/` (Python; drives DOSBox debugger over IPC)

- [ ] Harness that runs the original game in DOSBox with a
      single GPL chunk swapped to a one-opcode test.
- [ ] Records the engine state delta (memory regions, register
      state via DOSBox debugger).
- [ ] The fastest path to filling in unknown opcodes; turns
      "guess from context" into "observe the effect."
- [ ] Tagged: `opcode-fuzz-v0.1.0`.

**Done when**: we can author and verify a synthetic GPL chunk
end-to-end, and `opcode-fuzz` can discover at least one
previously-unknown opcode and add it to `docs/gpl-opcodes.md`.

## Phase 6 — First DS1 fix shipped (pipeline proof)

**Goal**: prove the patch pipeline end-to-end on the smallest
possible DS1 bug. By this point the toolkit is sharp enough that
authoring should feel like routine work.

**Ships**: `darkfix-ds1-v0.1.0`.

- [ ] Pick one trivial DS1 bug (identified during Phase 2 repro
      work).
- [ ] Author the fix using `gpl-disasm` + `gff-edit`.
- [ ] Author the test (hash before/after, in-game repro via
      `tools/repro/`).
- [ ] Tag `darkfix-ds1-v0.1.0`, push GitHub release.
- [ ] Player-facing README explaining install.

**Done when**: a stranger could download the v0.1 zip, run
`apply.py`, launch DS1 in DOSBox, and the bug is gone.

## Phase 7 — DS2 mines elevator (the headline)

**Goal**: fix the most famous DS2 bug — the one that broke the
late game in 1994 and has never been fixed.

**Ships**: `darkfix-ds2-v0.1.0`.

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
