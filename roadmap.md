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
- [ ] **Tool**: `tools/extract.sh` — GOG installer (.exe or .rar
      + .exe) → `extracted/ds1/` or `extracted/ds2/`.
- [ ] **Tool**: `tools/verify-install.py` — hash a player's
      install, identify GOG 1.10 / original CD / unknown.
- [ ] Source-hash manifest: SHA256 of every shipped DS1 and DS2
      file, baked into the patch manifests.

**Done when**: a fresh clone + a GOG installer + one script call →
a fully populated `extracted/` tree with file inventory and hash
manifest. Both tools have their own READMEs and are listed in
`tools/README.md`.

## Phase 1 — `gff-edit` + `gff-cat` (the foundation)

**Goal**: a pure-Python GFF reader/writer in our own code, so we
don't depend on a JVM tool for the most basic operation. Every
later phase reads or writes GFFs through this.

**Ships**: `tools/gff-edit/` (library) + `tools/gff-cat/` (CLI).
Tagged release: `gff-edit-v0.1`.

- [ ] Parse the GFFI header, version 3, TOC.
- [ ] Iterator API: `for chunk in gff.chunks(): chunk.type, chunk.id, chunk.bytes`.
- [ ] Extract a chunk to a file by `(type, id)`.
- [ ] Replace a chunk in-place; rewrite the GFF with a valid TOC.
- [ ] Round-trip test: read → write → byte-identical for at
      least one GFF in each game.
- [ ] CLI: `gff-cat list <file>`, `gff-cat extract <file> <type> <id>`,
      `gff-cat info <file>`, `gff-cat replace <file> <type> <id> <bytes>`.
- [ ] Tested against every shipped GFF in both DS1 and DS2 with
      no parse errors.

**Done when**: every GFF in `extracted/ds1/` and `extracted/ds2/`
opens, lists, and round-trips cleanly without a Java dependency.

## Phase 2 — DOSBox repro harness

**Goal**: any bug from the known-bugs list can be reproduced on
the local machine in under five minutes. Validation infrastructure
for everything that follows.

**Ships**: `tools/repro/` — DOSBox configs, save library,
recording wrapper.

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

**Ships**: `tools/gpl-disasm/`. Tagged release: `gpl-disasm-v0.1`.

- [ ] Read GPL chunks via our `gff-edit` library.
- [ ] Identify entry points and basic-block boundaries.
- [ ] Print annotated assembly with offset markers.
- [ ] String detection: embedded ASCII auto-shown next to the
      bytes that reference it.
- [ ] Cross-reference with `the-dark-lens` and DSO v1.0 debug
      symbols where available; emit a `syms.toml` we curate by
      hand and grow over time.
- [ ] Document the opcode table as we learn it
      (`docs/gpl-opcodes.md`).
- [ ] Tool README with usage examples on real game files.

**Done when**: `gpl-disasm extracted/ds1/GPLDATA.GFF` produces
output that lets a reader locate a quest-script function by
name (or by nearby string reference) and read its control flow.

## Phase 4 — Exploration tools

**Goal**: the digging surface widens. Tools that let us locate
which chunk a bug lives in, see the state a fix changes, and
look at the maps directly.

**Ships**: three tools, each with its own tag.

### `tools/dialog-extract/`

- [ ] Pull every NPC dialog tree out of the GPL/RDFF/text
      chunks as structured JSON.
- [ ] Output: `<chunk-id>: { speaker, lines, branches, gpl_refs }`.
- [ ] Search-friendly: `dialog-extract --grep "Magnolia"` finds
      every chunk that references the NPC.
- [ ] Useful for fan docs and for any future engine project,
      not just for patches.

### `tools/save-inspect/`

- [ ] Read `CHARSAVE.GFF` and dump character data as JSON.
- [ ] Diff two saves: party state, inventory, flags.
- [ ] Half-step toward writable saves; v0 is read-only.

### `tools/region-view/`

- [ ] Minimal SDL2 window that opens a single region GFF and
      draws the tilemap + sprite layer + entities.
- [ ] No interaction yet — just a view.
- [ ] Camera pan + zoom for inspection.
- [ ] Useful for "what does this region actually look like" and
      "is this entity placed where I think it is."

**Done when**: all three tools exist with their own READMEs,
each tagged `<tool>-v0.1`, and `tools/README.md` indexes them.

## Phase 5 — `gpl-asm` + `opcode-fuzz`

**Goal**: close the GPL loop. Be able to write GPL bytecode, not
just read it. Be able to discover unknown opcodes systematically.

**Ships**: two tools.

### `tools/gpl-asm/`

- [ ] Round-trip reassembler: `gpl-disasm` output → bytecode.
- [ ] Unblocks fixes that need to insert or delete bytes
      (currently we'd work around with no-op padding only).
- [ ] Tagged: `gpl-asm-v0.1`.

### `tools/opcode-fuzz/`

- [ ] Harness that runs the original game in DOSBox with a
      single GPL chunk swapped to a one-opcode test.
- [ ] Records the engine state delta (memory regions, register
      state via DOSBox debugger).
- [ ] The fastest path to filling in unknown opcodes — turns
      "guess from context" into "observe the effect."
- [ ] Tagged: `opcode-fuzz-v0.1`.

**Done when**: we can author and verify a synthetic GPL chunk
end-to-end, and `opcode-fuzz` can discover at least one
previously-unknown opcode and add it to `docs/gpl-opcodes.md`.

## Phase 6 — First DS1 fix shipped (pipeline proof)

**Goal**: prove the patch pipeline end-to-end on the smallest
possible DS1 bug. By this point the toolkit is sharp enough that
authoring should feel like routine work.

**Ships**: `darkfix-ds1-v0.1`.

- [ ] Pick one trivial DS1 bug (identified during Phase 2 repro
      work).
- [ ] Author the fix using `gpl-disasm` + `gff-edit`.
- [ ] Author the test (hash before/after, in-game repro via
      `tools/repro/`).
- [ ] Tag `darkfix-ds1-v0.1`, push GitHub release.
- [ ] Player-facing README explaining install.

**Done when**: a stranger could download the v0.1 zip, run
`apply.py`, launch DS1 in DOSBox, and the bug is gone.

## Phase 7 — DS2 mines elevator (the headline)

**Goal**: fix the most famous DS2 bug — the one that broke the
late game in 1994 and has never been fixed.

**Ships**: `darkfix-ds2-v0.1`.

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

**Ships**: `darkfix-ds2-v0.5`.

- [ ] Charged-weapon disappearance.
- [ ] Doorway / item graphics layering.
- [ ] Save/exit bug.
- [ ] Audio static (verify no-op for OPL/MT-32 emulation paths).
- [ ] MEL DSP detect (verify no-op for DOSBox).

## Phase 9 — DS1 sweep

**Goal**: same as Phase 8, for DS1's known issues.

**Ships**: `darkfix-ds1-v0.5`.

- [ ] Compile a more thorough DS1 bug list (DS1 is less
      documented; we will find issues during this phase).
- [ ] Fix each.

## Phase 10 — v1.0 for both games

**Goal**: the patches reach a state where they can be
recommended to fellow Dark Sun players in good conscience.

**Ships**: `darkfix-ds1-v1.0` and `darkfix-ds2-v1.0`.

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
