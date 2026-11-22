# OpenDS Roadmap

Phased plan. Each phase has a single shippable artifact; later
phases depend on earlier ones.

**This file is forward-looking.** The 2026-08-28 rewrite ruled
the file out of the changelog business (~85% of it annotated
already-shipped work, duplicating
[`patchnotes.md`](patchnotes.md)); shipped phases condensed to
one short section each, with per-tool `VERSION` files plus a
`patchnotes.md` entry as the release record. Re-condensed
2026-11-17: the seven dated campaign sections (2026-09 audit
through the 2026-11-17 release campaigns) compressed into the
campaign ledger below, and the ticked progress quotes from
phases 5.6-6 dropped. The full narratives live in git history
(`git log -p roadmap.md`), `patchnotes.md`, and the dated docs
under `docs/`.

**Tools come before patches.** Anything that makes the digging
easier is priority over any specific fix. Every digging-tool
ships before the patch that depends on it. The patch phases
(Phase 6 onward) start when the toolkit is sharp enough that
authoring fixes is plumbing, not archaeology.

Each phase ships a deliverable that is useful on its own,
independent of whether later phases happen.

## Where we are (snapshot 2026-11-17)

All phases through 5.7 and the phase-6 pipeline are shipped.
The patch program is live: darkfix-ds1 0.2.0-beta.4 carries four
beta families (16 disabled fixes across the yuan-ti catalog, our
sweep-triage rows, and the Detour/messenger repairs) gated by
runtime QA (#18); darkfix-ds2 0.1.x carries the dead-trigger
round. The community lane is fully adopted (yuan-ti catalog
complete; DarkSunTools Apache-2.0 with three ports shipped:
string codec, FONT codec, GPLDocument editing layer). The 2026
audit/mining campaigns are closed; their records live in
patchnotes.md and docs/. Open work: the backlog below, phase 7-10
(runtime-gated), and the issue queue (#18 QA, #21 held, #13/#14
threads).

## Phases 0-5.7 (shipped, condensed)

Detail for every shipped item lives in `patchnotes.md`, each
tool's README, and the dated campaign docs (the audit/mining
records in `docs/` carry the RE findings). What follows is the
one-line record per phase plus anything still open.

- **Phase 0, documentation + extraction**: docs corpus,
  source-hash manifests, `verify-install`. Open: nothing (the
  per-tool tag question closed forward-only 2026-09-04).
- **Phase 1, `gff-edit`**: pure-Rust GFF read/write, 128/128
  corpus round-trip, bulk extract, text codec, `gff-cat what`,
  indexed builder. Open (backlog): segmented-type build.
- **Phase 2, `repro`**: DOSBox-Staging harness with overlay-mount
  discipline, smoke fixtures, `--play --session` continuity,
  keystrokes, video. Open (backlog): bug-triggering save
  curation.
- **Phase 3, `gpl-disasm`**: recursive-descent CFG, callgraph,
  curated syms catalogues (now incl. REQUEST codes + the
  DarkSunTools codec cross-check), DSO importer.
- **Phase 4, exploration tools**: `dialog-extract`,
  `save-inspect`, `image-extract` (+`image-pack`),
  `region-render` (now with `--annotate`), `atlas`.
- **Phase 4.5, human-friendliness sprint**: `opends` umbrella
  CLI, write paths, `atlas`.
- **Phase 5, `gpl-asm` + `opcode-fuzz`**: 600/600 byte-identical
  round-trip, structural edits, `--patch`, movable assembly
  (0.10.x, the detour enabler). Open (backlog): macros;
  opcode-fuzz semantics discovery (DOSBox calendar).
- **Phase 5.5, `ovr-map`**: overlay segment map for both
  binaries, 935/854 entry stubs, syms catalogues, Ghidra
  pipeline.
- **Phase 5.6, name the binary**: COMPLETE. Dispatch tables
  resolved (129 handlers each), 21 DSO anchors, gpldisk fully
  mapped, region-change machine read, official-patch diff
  characterized, formats/saves decoded (SAVE/1, SAVE/7), the
  bug-site census compiled into known-bugs. The 2026-09-04
  premise correction, the subagent results, and the
  elevator/region-change machine reads live in git history and
  the dated campaign docs.
- **Phase 5.6.2/5.6.3 residuals**: SAVE/2-/4, /8, /9, u16 family,
  SAVE/18 stay deferred in the backlog; the runtime-capture
  instruments are built.
- **Phase 5.7, `exe-patch`**: SHIPPED 2026-09-06 (v0.1.0):
  `ovr:SEG+OFF`/symbol addressing, mandatory fingerprints,
  `--verify`, in-place-only enforcement, nasm authoring
  (keystone declined; pwntools rejected i386/16 outright),
  selftest-proven on synthetic + real binaries.
- **Phase 6, first DS1 fix**: darkfix-ds1 0.1.0 shipped
  2026-09-11 (fix.ds1.deadtriggers); the applier is
  Wine-proven (stdlib-only; real-Windows run still open,
  Brandon's side); composition amendment shipped 0.1.3.

The 2026-08-28 "can we patch the EXE yet?" assessment is
superseded: the answer became yes (Phase 5.7 shipped), and
nothing in the patch program waits on binary knowledge anymore.


## Phase 7 — DS2 mines elevator (the headline)

**Goal**: fix the most famous DS2 bug, the one that broke the
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
      the elevator transition. New leverage since this phase
      was written: Phase 5.6's official-patch diff may show
      whether SSI themselves touched the transition code
      between 1.0 and 1.10, and the DSO symbol table likely
      names the region-transition functions outright (DSO
      inherited the whole WotR codebase). Use both before
      hand-digging.
- [ ] Diagnose the race / state bug.
- [ ] Author the fix (data or binary, whichever it lives in).
- [ ] Verify a full DS2 playthrough does not reproduce the
      original behavior.

**Done when**: a player who hits the elevator gets to the next
region, with a full party, on a clean install with the patch
applied.

## Phase 8 — DS2 sweep

**Goal**: every bug in [`docs/reference/known-bugs.md`](docs/reference/known-bugs.md)
section 2 (community-reported, post-1.10) has either a fix or an
explicit "won't fix" note with rationale.

**Ships**: `darkfix-ds2-v0.5.0`.

- [ ] Charged-weapon disappearance.
- [ ] Doorway / item graphics layering.
- [ ] Save/exit bug.
- [x] Audio static (verify no-op for OPL/MT-32 emulation paths).
      (VERDICT 2026-09-10, won't fix / no-op under the GOG
      install: the static is a redbook mastering defect on some
      pressings' tracks 2-3, reproducible outside the game and
      documented on real hardware in 1996 (VOGONS t=9726 /
      t=10893); GOG's OGG re-encodes bypass the defective
      masters. The box's OPL/MT-32 framing was a category
      error: the DS2 CD line has no MIDI music, so those
      synthesis paths are never in the chain. known-bugs.md
      2.5 rewritten with the corrected origin (the old "AIL
      driver mismatch" note was wrong). Residual: one in-game
      ear test, which rides the Phase 10 playthrough.)
- [x] MEL DSP detect (verify no-op for DOSBox).
      (VERDICT 2026-09-10, won't fix / config, not engine:
      community-confirmed IRQ mismatch; the game's SOUND.INI
      defaults the SB Pro II/III and SB16-class cards to IRQ 5,
      stock DOSBox defaults 7, and AIL's probe verifies the IRQ
      with a test interrupt, so a mismatch aborts startup with
      the MEL fatal. The GOG conf pins irq=5, verified against
      the real file, so the shipped path cannot trigger it; a
      hand-rolled IRQ-7 conf still can, which is exactly how
      the VOGONS reports happened. known-bugs.md 2.6 carries
      the full rationale. Residual: one in-game launch
      confirm, rides the Phase 10 playthrough.)

## Phase 9 — DS1 sweep

**Goal**: same as Phase 8, for DS1's known issues.

**Ships**: `darkfix-ds1-v0.5.0`.

- [x] Compile a more thorough DS1 bug list (DS1 is less
      documented; we will find issues during this phase).
      (COMPILED 2026-09-10: known-bugs.md §3 now carries the
      compiled catalogue, ~25 entries grouped into the
      final-battle trigger family (the headline DS1
      game-breaker, six variants, 2011-2025 reports), quest/NPC
      scripting, engine-level items (area item limit, ghost
      inventory slot, save-mid-event object loss, stat-boost
      asymmetry), and minor rule deviations; every entry has
      sources and a surface guess, and the dead-trigger finding
      is cross-referenced as the first root-cause candidate for
      the enemies-refuse-to-engage class. Dead ends recorded
      for the next pass: powelltown unarchived, Reddit bodies
      unfetchable, athas.org unreachable, no public DS1 1.1
      fix list. One install-variants lead rode along: an
      unverified GameFAQs claim of separate CD and floppy 1.1
      variants.)
- [ ] Fix each.
      (TRIAGED 2026-10-07: every catalogued entry carries a verdict
      in docs/reports/ds1-sweep-triage-2026-10-07.md: three FIXED via
      darkfix-ds1 0.1.2's `fix.ds1.script-repairs` (hermit/ranger
      occlusion, Linara dead-end, final-battle stage-gate strand;
      shipped toggled off under the old one-enabled-fix-per-file
      rule, ENABLED by default same-day in 0.1.3 when Brandon
      approved the spec 5 composition amendment: disjoint
      same-file fixes apply together, the applier merges them into
      one write, overlaps still refuse), nine fix-candidates gated
      on chunk growth, one runtime capture each, or content
      decisions, and the rest closed as engine-side or
      no-static-site verdicts with evidence. The headline: the
      final-battle family's stage-strand is a proven faulty datum
      with a shipped repair; the scroll (variant 1) and the
      early-exit race (variant 2) have NO static site at all.)

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

If the toolkit accumulates enough, `gpl-disasm` with most
opcodes documented, working `gpl-asm`, native GFF read/write,
region viewer, save inspector, then **OpenDS the engine**
becomes plumbing rather than reverse-engineering. At that
point spinning it up makes sense.

We do not commit to a date. We commit to building the toolkit
that makes it possible. If someone else picks up the toolkit
and ships an engine first, that is a successful outcome.

## Backlog (deferred items with triggers)
  *(RATIFIED 2026-09-12 (Brandon): the 2026-09-10 disposition drafts stand as drafted: six keep-deferred with their triggers, the repro save-curation folds into the shipped bug pick, opcode-fuzz reframes to JSON recipes, and extract.sh stays deferred (its deletion declined).)*

Everything still open from the shipped phases, each with the
condition that promotes it into scheduled work. Nothing here is
abandoned; nothing here is scheduled.

- [x] **Cut the per-tool git tags, or drop the requirement.**
      `docs/reference/versioning.md` says each release ships a
      `<tool>-vX.Y.Z` tag; `git tag` returns nothing, so no
      release has ever complied. Two honest resolutions:
      backfill tags against the commits that bumped each
      `VERSION` (a one-off script walking `git log -- VERSION`
      makes this mechanical), or amend `docs/reference/versioning.md` to
      name `VERSION` + `patchnotes.md` as the whole release
      record and drop tags. Open since the 2026-07-23
      reconciliation sweep. **Decide before the first darkfix
      release**, so patches do not inherit the ambiguity.
      (Decided 2026-09-04: tags are cut, forward-only. First
      two: `ovr-map-v0.3.0` and `save-inspect-v0.9.5` at their
      release commits. Backfilling the 14 tools' older
      releases stays open as an optional one-off; the audit's
      audit's tag-policy ruling is satisfied by forward-only
      tagging.)
- [ ] **`gff-edit` segmented-type build.** Builder covers
      indexed GFFs only; the secondary-table + `GFFI`
      cross-reference dance is unwritten. Promote when a
      downstream consumer needs to *construct* a segmented
      GFF from scratch (reading and replacing already work).
- [ ] **`repro` bug-triggering save curation.** Per-bug saves
      placed just before the trigger, indexed by bug ID.
      Ongoing alongside every fix; promote to a focused push
      when Phase 6 picks its first bug (it needs one).
- [x] **`image-extract` animated sprite export (GIF / APNG).**
      The still half shipped in v0.3.0 (`--frames-all`,
      `--spritesheet`). Needs an encoder decision first: no
      in-tree GIF/APNG writer, and a new dep needs sign-off
      per spec §7a. Note `region-render` v0.7.0 already
      shells to ffmpeg for `--gif`; the same trick applies
      here and probably settles the question.
      (Shipped 2026-09-06 in v0.5.0: the decision went to the
      ffmpeg shell-out, exactly as the box predicted. `--gif`
      (with `--frames-all`) bundles the frame PNGs into
      `<KIND>-<ID>.gif` via the same two-pass palettegen/
      paletteuse pipeline as `region-render --gif`; no new
      crates. APNG stays deferred; ffmpeg's `-f apng` muxer is
      the named route. Regression test: a real two-pass encode
      asserting the GIF signature, skipped when ffmpeg is
      absent like the corpus tests are when .games/ is.)
- [x] **`region-render` animated palette colours.** VGA
      colour cycling; blocked on EXE RE of the cycle-table
      layout. Phase 5.6 is the unblocker; candidates
      (`VGAColorCycle`, `gCycleColor`) are already named in
      the DSO symbol table.
      > FULLY UNBLOCKED 2026-09-06 (dsun-exe-re.md 4.5.6):
      > the registration source is found and it is boot-time:
      > StartCycle(slot, first, count, delay) at DS1 0x28707 /
      > DS2 0x2cee7, called exactly four times at init with
      > (0, 1, 5, 2), (1, 6, 5, 2), (2, 11, 5, 2),
      > (3, 240, 9, 2). DS1 colour cycling is four fixed
      > global ranges, active from boot; there is no
      > per-region cycle configuration. region-render can now
      > implement the mechanism plus these four ranges for a
      > game-accurate animated palette.
      > (Ticked 2026-09-06: both named-consumer conditions
      > above are met; the VGA work shipped as ovr-map 0.3.2 /
      > 0.3.3 syms rows + dsun-exe-re 4.5.5-4.5.6.)
      > (IMPLEMENTATION SHIPPED 2026-09-10, region-render
      > 0.8.0: `--animate-palette` renders one frame per pump
      > pass with the decoded 16x8 record semantics
      > (`PaletteCycle`, rotate-toward-higher-indices, delay
      > counters), defaulting to DS1's four boot-time ranges;
      > composes with `--animate-entities` and `--gif`.
      > DS2's init site stays open, so DS2 approximates with
      > the DS1 set, documented in the README. Proven on
      > RGN02: frames 0/1 pixel-identical (delay 2), 236,783
      > pixels shift at the frame-2 first rotation. Rider:
      > the README palette-precedence table, stale since the
      > v0.5.0 preset flag and CPAL:200-first fallback, is
      > repaired in the same release.)
- [x] **`region-render --annotate`.** Entity-name overlays on
      rendered maps. SHIPPED in region-render 0.9.0 (2026-11-17)
      after the embedded-font blocker fell away; the box was
      left unticked against the ledger below until the
      2026-11-22 docs sweep caught it.
- [ ] **`dialog-extract` path-aware caller picking.** For the
      32 LSTR reads resolved via `possible_writers` arrays:
      CFG-distance ordering or symbolic trace instead of the
      current narrowing. Queued since v0.5.0; promote when an
      unresolved dialog actually misleads someone.
- [ ] **`gpl-asm` parameterised macros and `@include`.**
      Queued since v0.6.0. Promote when a darkfix script
      gets repetitive enough to want them; the `--patch` TOML
      mode may obsolete the need instead. Re-evaluate at
      Phase 6.
- [ ] **`opcode-fuzz` first opcode-semantics discovery (JSON
      recipes).** The harness runs a swapped chunk through DOSBox
      and diffs `DARKRUN.GFF`; what remains is the loop that
      walks candidate opcodes and the discovery work itself.
      (Ratified 2026-09-12: reframed from "discover a
      previously-unknown opcode", whose original shape died when
      the 15 unknown dispatch slots were proven unimplemented,
      so only semantics discovery can meet it; the recipe-format
      call is made, JSON recipes matching the `gpl-disasm
      --json` contract the other tools speak; the work
      schedules with the DOSBox session calendar. Keep this box
      alive until a semantics discovery lands or the box is
      explicitly closed.)
- [ ] **`save-inspect` DARKRUN SAVE chunk RE.** (Ratified
      2026-09-12, partially absorbed: SAVE/1 and SAVE/7 are
      decoded into the field catalogue as of 0.9.6; the
      remaining ids stay deferred on the original trigger, a
      fix that must READ a save field.) Still open: SAVE/2-/4,
      /8, /9, the u16 scalar family at ids 10..17, and the
      51-byte SAVE/18 boolean array. Bootstrap with the
      v0.7.0 `save-diff` harness: snapshot, one in-game
      action, snapshot, diff. Quest and world-state fixes
      need this; promote when the first such fix is chosen
      (the dead-trigger pick reads GPL chunks, not saves, so
      it does not pull this forward).
- [ ] **`extract.sh`.** From-installer extraction wrapper.
      Deferred; `innoextract` is one command and
      `verify-install --repair` already shells out. Reinstate
      only if a contributor needs it.
- [x] **Python test harness decision.** The repo has none;
      Python tools gate on ruff + `compileall` in CI and ship
      `--selftest` flags (`ovr-map`). Options: keep the flag
      idiom, or standardise on stdlib `unittest` discovery in
      CI. Decide the next time a third Python tool grows a
      selftest.
      (Decided 2026-09-06, trigger met: keep the flag idiom.
      Six tools carry selftests (ovr-map, exe-patch, repro,
      apply.py, global-state-sweep, dead-trigger-sweep); the
      tests are heterogeneous (synthetic fixtures, refusal
      paths, skip-when-absent corpus parts), which a unittest
      discovery layer would wrap without adding coverage. CI
      now RUNS all six selftests in the python job, so the
      flags actually gate instead of living on the dev
      machine.)

## Tooling inventory and gaps

Checked on the dev host 2026-08-28; capabilities updated
2026-09-05 (dispatch tables, OBJEX sprite pipeline, symbol
catalogue). **Everything the docs cite is installed.** Nothing
blocks any phase.

| Tool | Status | Used by |
|---|---|---|
| Ghidra 12.1.2 | installed (`~/.local/share/ghidra_12.1.2_PUBLIC/`; `analyzeHeadless` not on `$PATH`, invoke by full path) | Phase 5.6; `ovr-map --ghidra` |
| radare2 5.9.8 (incl. `radiff2`, `rabin2`, `rahash2`) | installed | Phase 5.6 official-patch diffing; `dsun-exe-re.md` §6 |
| `ndisasm` / `nasm` | installed | `ovr-map --disasm`; patch byte authoring |
| DOSBox-Staging 0.82.2 (as `dosbox`) | installed | `repro`, `opcode-fuzz` |
| `ffmpeg` | installed | `repro` video capture; `region-render --gif` |
| `innoextract` | installed | `verify-install --repair` |
| `ydotool` | installed | `repro` keystroke automation |
| `wine` | installed | Phase 6 applier testing |
| `pwndbg` | installed; **not for this project** (gdb plugin for live Linux ELF; these binaries run under DOSBox) | nothing |

Optional, only if a phase asks for it:

- **DOSBox-X**: a second emulator with a deeper built-in
  debugger (instruction tracing, more breakpoint/logging
  surface than Staging's). `opcode-fuzz` and hard-to-catch
  races are the plausible consumers. Staging's debugger plus
  the `DARKRUN.GFF` diff loop has sufficed so far; install
  when the first bug defeats both.
- ~~**`keystone-engine` + `bsdiff4`** in the applier venv.~~
  RESOLVED 2026-09-06, neither adopted: the applier is pure
  stdlib (in-place offset-keyed edits need no diff library),
  and assembly goes through system nasm (`tools/exe-patch
  --asm`, round-tripped against ndisasm; pwntools cannot
  assemble 16-bit x86 at all). `docs/reference/build-environment.md` §2
  carries the full reasoning.

Not needed, for the record: LE/LX Ghidra loaders (the DOS/4GW
model was disproved, `dsun-exe-re.md` §1), decompilers beyond
Ghidra (16-bit real-mode support elsewhere is worse), and any
Windows-cross toolchain (patches are data + Python, not
compiled code).

2026-09-05 session findings promoted to the durable docs (one
line each here; the evidence chains live at the targets):

- Freeze-mechanism candidates and the complete mines dossier
  (scheduler deadlock, dangling GF[647-652], the intra-region
  floor system, the freeze window, the capture recipes):
  `docs/reference/engine-quirks.md` section 6.
- GF flags are GPL-layer-only; the EXE never reads individual
  flags: `docs/reference/engine-quirks.md` section 7.
- GPLI-1's real format (and the retracted dispatch-index
  theory): `docs/reference/engine-quirks.md` section 8 and the
  `docs/reference/file-formats.md` GPLI row.
- DS1 has no region names; RDAT is config, not names:
  `docs/reference/engine-quirks.md` section 9.
- The DS2 GPL request dispatcher map, the DGROUP BSS layout,
  and the scheduler's 0x100:0x2 character-output function:
  `docs/reference/engine-quirks.md` sections 10-11 (the scheduler also
  appears in section 6 as freeze candidate A).
- DS2 overlay manager at file 0x404c4 and FBOV segnum =
  exeinfo record count: already durable in
  `docs/reference/dsun-exe-re.md` / `docs/reference/dsun-exe-survey.md`
  (corrected 2026-09-05; the syms row fixed in ovr-map 0.3.1).

The elevator site-report narrative inside the 5.6.1 box is the
Phase 7 site report's draft; it assembles into
`ds2-patch/fixes/fix.ds2.mines-elevator.md` when Phase 7 opens,
from this ledger, `docs/reference/engine-quirks.md` 6, and the census row.


## Campaign ledger (condensed 2026-11-17)

The dated campaign narratives (2026-09-12 audit, 2026-09-14/15
final audit + blitz, 2026-09-16 bestiary, 2026-09-19 port-mining,
2026-10-06 mineout, 2026-11-16 community lane, 2026-11-17 release
campaign) are condensed here; the full narratives live in git
history (`git log -p roadmap.md`) and the dated docs under `docs/`.
Each line names what the campaign shipped and where its record
lives.


- **Six-lens audit (2026-09-12)**: full report at
  `audit/FULL-AUDIT-2026-09-12.md`; findings fed the final blitz.
- **Final audit + blitz (2026-09-14/15)**: all 10 blitz items
  shipped, `audit-final/opends/FINAL-REPORT.md`; darkfix-ds2 0.1.0
  (first DS2 fix) and 7 tool releases in one day.
- **Bestiary campaign (2026-09-16/17)**: complete world-data
  mining (bestiary/items/spells/inventories/world-dumps, 12
  anchor-gated docs), complete GPL VM spec, presentation stack,
  dialogs; verdict: static bulk mining done. Record:
  `docs/catalogues/bestiary-ds1.md` + kin.
- **Port-mining campaign (2026-09-19)**: the Godot-readiness lane
  mined out; the Draj demo built; record:
  `docs/reference/godot-port-readiness.md` + `docs/port-digs-*.md`.
- **Mineout campaign (2026-10-06/07)**: format-coverage gap list
  driven to zero; audio-extract + xmi2mid shipped; DS2 dead
  triggers 37/39; sweep verdicts in
  `docs/reports/port-digs-2026-10-07.md`; `docs/reports/mining-complete.md`.
- **Community lane (2026-11-13/16)**: yuan-ti + DarkSunTools
  adoption opened; gate review, exchange briefs, contributor
  surfaces; the DarkSunTools Apache-2.0 license landed 11-16.
  Record: `docs/reports/community-crossread-2026-11-13.md` +
  `docs/reports/exchange-yuan-ti-2026-11-13.md` + `docs/reference/detour-repairs.md`.
- **Release campaigns (2026-11-17)**: issues #19/#20/#22/#23/#24/
  #25/#26 closed; 12 releases (five tool hardening patches,
  gpl-disasm 0.9.0 codec port + REQUEST catalogue + BITSNOOP
  evidence, gpl-asm 0.10.0 movable assembly, darkfix beta.2
  REPAIRS migration + beta.3 Legcrusher/Trustee + beta.4 triage
  rows, region-render 0.9.0 --annotate, gpl-text 0.1.0, font-extract
  0.1.0); yuan-ti mining batch 2 (23 findings, 4 digs) +
  DarkSunTools portability survey landed as docs. Record:
  `patchnotes.md` + `docs/reports/yuan-ti-mining-2026-11-17.md`.

