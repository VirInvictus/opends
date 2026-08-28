# OpenDS — Roadmap

Phased plan. Each phase has a single shippable artifact; later
phases depend on earlier ones.

**This file is forward-looking.** Rewritten 2026-08-28 from the
2026-07-23 reconciled version. The old roadmap had become a
second changelog: ~85% of it annotated already-shipped work,
duplicating [`patchnotes.md`](patchnotes.md), and it twice failed
to notice whole bodies of work until after they shipped (Phase
4.5, `atlas`). Shipped phases are now condensed to one short
section each: what it delivered, what is still open, where the
detail lives. Per-tool `VERSION` files plus a `patchnotes.md`
entry remain the release record; the previous version of this
file (with all its per-release annotation and correction
history) is in git history.

**Tools come before patches.** Anything that makes the digging
easier is priority over any specific fix. Every digging-tool
ships before the patch that depends on it. The patch phases
(Phase 6 onward) start when the toolkit is sharp enough that
authoring fixes is plumbing, not archaeology.

Each phase ships a deliverable that is useful on its own,
independent of whether later phases happen.

## Where we are (snapshot 2026-08-28)

Phases 0 through 5.5 are shipped. The toolkit reads, writes,
round-trips, renders, and reassembles the games' data, and the
engine binary is segmented and addressable.

| Tool | Version | Status |
|---|---|---|
| `verify-install` | 0.3.0 | shipped |
| `gff-edit` | 0.6.0 | shipped; segmented-type builder deferred |
| `repro` | 0.4.0 | shipped; differential capture + bug-save curation open |
| `gpl-disasm` | 0.6.0 | shipped; 100% corpus alignment, CFG, callgraph, symbol catalogues |
| `dialog-extract` | 0.7.1 | shipped; path-aware caller picking queued |
| `save-inspect` | 0.9.4 | shipped; DARKRUN SAVE chunk RE continues |
| `image-extract` | 0.4.0 | shipped; GIF/APNG sprite export deferred |
| `region-render` | 0.7.1 | shipped; animated palette + `--annotate` deferred |
| `atlas` | 0.1.1 | shipped |
| `opends` | 0.1.0 | shipped |
| `gpl-asm` | 0.9.0 | shipped; 600/600 round-trip; macros queued |
| `opcode-fuzz` | 0.3.0 | shipped; recipe-driven fuzz + first opcode discovery open |
| `ovr-map` | 0.2.0 | shipped; `--ghidra` verified headless |

What the digging surface looks like today:

- **Data side is basically solved.** Every GFF in both games
  parses and round-trips; GPL bytecode disassembles at 100%
  corpus alignment and reassembles byte-identically; saves
  decode and edit; regions render (with entity animation and
  GIF output); dialogs extract as browsable trees.
- **The binary side just opened.** `ovr-map` turns `DSUN.EXE`
  from a 600 KB blob into 52 / 49 overlay segments with **935
  (DS1) / 854 (DS2)** confirmed function entry points,
  disassembled at correct bases, and importable into Ghidra as
  labelled, correctly-based memory blocks (verified headless,
  `ovr-map` v0.2.0).
- **The patch pipeline has its first real surface.** Bytecode
  patches author by label-relative address with fingerprint
  checks (`gpl-asm --patch`), and the darkfix package shape
  (manifest, applier, journal, unapply) shipped under
  `ds1-patch/` v0.0.1, proven with a no-op fix (Phase 6,
  checkbox 1). The EXE patch-authoring surface does not exist
  yet; that is Phase 5.7.

Open items from the shipped phases are consolidated in the
[Backlog](#backlog-deferred-items-with-triggers) at the end,
each with the trigger that promotes it into real work.

## Phases 0-5.5 (shipped, condensed)

Detail for every shipped item lives in `patchnotes.md` and each
tool's README. What follows is the one-paragraph record plus
anything still open.

- **Phase 0, documentation + extraction**: docs corpus
  (`file-formats.md`, `known-bugs.md`, `gpl-bytecode.md`,
  `binary-patching.md`, `patch-workflow.md`, `research.md`,
  `install-variants.md`, `dso-symbols.md`, `dsun-exe-re.md`),
  source-hash manifests, `verify-install` v0.3.0.
  Open: the per-tool git tags (see Backlog).
- **Phase 1, `gff-edit`**: pure-Rust GFF read/write, 128/128
  corpus round-trip, bulk extract, text codec, `gff-cat what`
  describer, indexed builder. Open: segmented-type build.
- **Phase 2, `repro`**: DOSBox-Staging harness with overlay-mount
  discipline, smoke fixtures, `--play --session` continuity,
  scheduled keystrokes via ydotool, video capture.
  Open: differential capture; bug-triggering save curation.
- **Phase 3, `gpl-disasm`**: recursive-descent CFG, inter-chunk
  callgraph, curated
  `syms/{opcodes,functions,variables,locals}.toml`, DSO-symbol
  importer producing review-ready rename proposals.
- **Phase 4, exploration tools**: `dialog-extract`,
  `save-inspect`, `image-extract` (+`image-pack`),
  `region-render`, `atlas`.
- **Phase 4.5, human-friendliness sprint**: `opends` umbrella
  CLI, write paths across the toolkit, `atlas`. (This whole
  sprint shipped before the roadmap knew about it; see the
  rewrite note in the header.)
- **Phase 5, `gpl-asm` + `opcode-fuzz`**: 600/600 byte-identical
  round-trip through bytes, JSON, and labelled text; structural
  edit API; author safety net; declarative `--patch` mode with
  label-relative addressing (v0.9.0); chunk-patchwork pipeline
  and DOSBox-driven `run` harness in `opcode-fuzz`.
  Open: recipe-driven fuzz; the phase's done-when (discover at
  least one previously-unknown opcode) is not yet met.
- **Phase 5.5, `ovr-map`**: overlay segment map for both
  binaries; `--disasm`, `--callgraph`, `--verify`,
  `--selftest`, and the `--ghidra` script verified headless
  (52 blocks, 935 labels, dispatcher prologue reads
  correctly). Measured structure: DS1 52 segments / 247 KB /
  93.13% coverage / 935 stubs / 210 direct far-call edges;
  DS2 49 / 252 KB / 93.39% / 854 / 216. The "why this
  matters" section of the previous roadmap named two
  follow-on workstreams; they are now Phases 5.6 and 5.7
  below.

## Can we patch the EXE yet? (assessment, 2026-08-28)

Asked outright: do we understand `DSUN.EXE` well enough to write
a binary patch, or does a fix need a full exploration report
first? The honest split:

**Solved: mechanical safety.** The overlay map is complete and
verified (52 / 49 segments, 935 / 854 entry stubs, ~93%
coverage), any byte is addressable as `ovr:seg+off`, the Ghidra
import is verified headless, and the applier layer refuses
fingerprint drift, length changes, and wrong installs. Authoring
a *safe* byte patch is already plumbing.

**Not solved: finding anything.** Almost nothing in the binary
is *named*. The DSO symbol transfer and the official-patch
diffing have not been run; the callgraph identifies direct
callers for only ~12-14% of stubs; the resident image (all code
before the overlays) has had no systematic pass at all. "Where
does the mines elevator transition live?" is today a dig, not a
lookup. That gap is exactly what Phase 5.6 exists to close.

**Decision: no full-exploration gate.** Requiring a complete EXE
report before any patch attempt is the engine-first trap again
(spec §1a): it defers every fix behind a multi-month research
program, and most target bugs never touch the binary at all.
Instead, exploration is **targeted and per-fix**:

- A data-surface fix (most quest, flag, and dialog bugs) never
  touches the EXE and proceeds now. Phase 6 explicitly prefers
  one for exactly this reason.
- A binary-surface fix requires a written **site report** before
  the patch is authored, added to `docs/dsun-exe-re.md` (or the
  fix's own writeup): the function(s) involved, the evidence
  chain (string xrefs, DSO symbol match, a 1.0-vs-1.10
  official-patch diff hit, or call-shape match), and
  before/after disassembly. The report is the deliverable; the
  patch is its application. No site report, no patch.
- The Phase 5.6 leverage points (DSO symbol transfer,
  official-patch diffing) are pulled forward only when a specific
  fix needs them. They are accelerators, not prerequisites.
- Phase 7 (the mines elevator) is the first plausible
  binary-surface fix. Its site report is the first test of this
  policy; if the evidence chain stalls, the honest fallback is
  another data-surface or deferred bug, not an open-ended dig.

## Phase 5.6 — Name the binary (EXE RE at scale)

**Goal**: turn 935 / 854 confirmed entry points into a *named*
function catalogue per game, so that "where does this bug live
in `DSUN.EXE`" becomes a lookup instead of a dig.

**Ships**: per-game EXE symbol catalogues under
`tools/ovr-map/syms/` (or a sibling), plus the Ghidra pipeline
that grows them, and docs. No new tool required; this is
labour with tooling that already exists.

> Progress 2026-08-28: the whole-binary structure survey
> ([`docs/dsun-exe-survey.md`](docs/dsun-exe-survey.md)) shipped.
> Headline: the overlay code calls only ~340 distinct resident
> functions (4,865 / 5,067 direct far-call sites, census in
> survey §3.3), the overlay manager body is located
> (`0x466e0` / `0x4aff0`), and the DSO name list has a concrete
> matching order: resident targets first, overlays second. The
> official-patch diffing leverage point below is updated: it is
> blocked without a CD 1.0 base.

Three leverage points, in order of cost:

- [ ] **Ghidra headless workflow written down and run.** The
      `ovr-map --ghidra` script lands segments and entry-stub
      labels. What is missing is the working session recipe:
      a headless `analyzeHeadless` invocation (the binary
      ships with Ghidra at
      `~/.local/share/ghidra_12.1.2_PUBLIC/`; it is not on
      `$PATH`, which is fine), a script skeleton for bulk
      renaming from a TOML catalogue, and an export path back
      to text (decompiler listing or disassembly) checked
      into `docs/` as findings. Keep the Phase 5.5 caveat:
      the decompiler is weak on 16-bit segmented code; the
      deliverable is *navigable, correctly segmented, and
      named*, not *clean C*.
- [ ] **DSO symbol transfer.** `docs/dso-symbols.md`
      documents the 3,530-function Watcom symbol table from
      Dark Sun Online (which inherited the WotR codebase).
      The offsets do not map directly onto our binaries; the
      work is byte-pattern and call-shape matching, seeded by
      the `ovr-map --callgraph` edges and the `gpl-disasm`
      `import-dso-symbols.py` precedent (which already does
      this class of matching for GPL symbols). Produce
      review-ready proposals, curated by hand into the
      catalogue; never auto-committed, matching the existing
      curation rule.
- [ ] **Official-patch diffing.** ⚠ **Update 2026-08-28: blocked
      as framed; the floppy 1.0 binary is a different build, not
      a near revision** (resident image +1,840 bytes, 866 vs 854
      entry points, 42 of 49 overlay segments differ materially
      when paired by index; `RESFLOP.GFF` shows the floppy line
      diverges at the source level). Measured evidence in
      [`../docs/dsun-exe-survey.md`](docs/dsun-exe-survey.md) §8.
      Reviving this item needs a **CD 1.0 `DSUN.EXE`** (a
      pre-patch CD-tree artifact; the `cd11` archive holds the
      RTPatch package, not a base tree), or a parser for
      RTPatch's own old-file fingerprints. `.games/archive-org/`
      artifacts remain on hand either way.
- [ ] **First named consumers.** The catalogue is real when
      something else uses it: at minimum, the VGA
      colour-cycling routine (`VGAColorCycle` /
      `gCycleColor` candidates already located via the DSO
      table) decoded far enough to unblock `region-render`'s
      animated palette backlog item, and one known-bug site
      located by name as input to Phase 6 or 7.

**Done when**: a reader can ask "what is at `ovr:NN+0x...`"
and get a name with evidence for a meaningful fraction of the
catalogue (target: the ~200 most-called functions), and at
least one downstream item (animated palette, or a Phase 6/7
site) cites it.

## Phase 5.7 — EXE patch authoring surface

**Goal**: give `DSUN.EXE` byte patches exactly what `gpl-asm`
v0.9.0 gave bytecode patches: authored by name, fingerprint-
checked, verified before it ships.

**Ships**: named addressing and a verify gate for EXE patches,
in whatever tool owns the job (decide: extend `gpl-asm
--patch` with a second target kind, or a sibling `exe-patch`;
decide by whether the TOML schema can stay shared).

- [ ] `at = "ovr:19+0x17a7"` addressing, resolved against the
      `ovr-map` segment map (file offset, segment-local
      offset, payload bounds). Symbol-relative addressing
      (`at = "<exe-symbol> + N"`) once Phase 5.6's catalogue
      exists; refuse non-block-leader bases, matching the
      bytecode resolver's rule.
- [ ] `bytes_old` fingerprint mandatory, as on the bytecode
      side; refuse to apply on mismatch.
- [ ] A `--verify` pass that fails a site which: drifts from
      its fingerprint, straddles a segment boundary, or lands
      in the ~7% inter-segment padding. Today nothing notices
      any of these.
- [ ] **In-place-only rule made enforceable and explained.**
      Every overlay descriptor stores its payload offset as
      an absolute position; one inserted byte anywhere before
      the last segment shifts every following payload and the
      game loads garbage as code. State this in `spec.md` §4
      in those terms (the previous roadmap's own suggestion,
      still undone), and have `--verify` reject any script
      that changes file length.
- [ ] Assembler for replacement bytes: `keystone-engine` is
      already named in `docs/build-environment.md` §2 for
      exactly this (16-bit x86). Confirm it assembles
      `arch=i386, mode=16` correctly against `ndisasm -b 16`
      round-trips before relying on it; `pwn asm` at
      `arch='i386', bits=16` is the documented fallback. The
      stdlib-only Python rule already has a pre-approved
      exception class for the applier (per
      `build-environment.md`, alongside `bsdiff4`); this fits
      it.
- [ ] Round-trip proof: a no-op EXE patch script applies and
      unapplies byte-identically; a deliberately wrong site
      (off-by-one into padding) is rejected by `--verify`.

**Done when**: Phase 6+ can author a two-byte EXE fix by
symbol name and `--verify` is the last gate before packaging.
This is the same soft-blocker shape as `gpl-asm` v0.9.0 was
for bytecode: not a hard blocker for a data-only first fix,
and must not hold one.

## Phase 6 — First DS1 fix shipped (pipeline proof)

**Goal**: prove the patch pipeline end-to-end on the smallest
possible DS1 bug. By this point the toolkit is sharp enough that
authoring should feel like routine work.

**Ships**: `darkfix-ds1-v0.1.0`.

- [x] Darkfix distribution format per `spec.md` §4:
      `manifest.toml` schema (target hashes, fix list, on/off
      state), `apply.py` applier (verify install hashes against
      the manifest, back up to `darkfix-backup/`, apply each
      enabled fix, write `darkfix-applied.json`), and `apply.py
      --unapply` restore. Proven with the `fix.ds1.noop` fix:
      applies and unapplies byte-identically against a copy of
      the real `DSUN.EXE`; wrong-fingerprint and tampered-target
      refusals covered by `apply.py --selftest` (2026-08-28).
- [ ] **Applier runs on the player platform.** The audience is
      Windows-first. Test `apply.py` under Wine and, ideally,
      real Windows Python before calling the package shape
      proven; a fix that only applies on Fedora is not a fix.
      Decide the dependency stance in the same breath: pure
      stdlib (preferred, matches spec §7a) versus the
      `bsdiff4`/`keystone` venv `build-environment.md`
      sketches.
- [ ] Pick one trivial DS1 bug (identified during Phase 2 repro
      work). Prefer a GPL-data fix if one is available: it
      exercises `gpl-asm --patch` + `gff-edit` and defers the
      EXE surface until Phase 5.7 exists.
- [ ] Repro fixture for the chosen bug
      (`tools/repro/bugs/<id>/bug.toml`) so the fix is
      verifiable. Requires ydotool installed locally; repro
      v0.4.0 already integrates the input automation.
- [ ] **Differential capture** (promoted from the repro
      backlog, because it is the fix's proof): a
      run-with-patch and run-without-patch side-by-side
      helper, emitting both videos plus a structured
      pass/fail delta.
- [ ] Author the fix using `gpl-disasm` + `gff-edit` (plus the
      Phase 5.7 surface if it turns out to be an EXE fix).
- [ ] Author the test (hash before/after, in-game repro via
      `tools/repro/`).
- [ ] Tag `darkfix-ds1-v0.1.0`, push GitHub release.
- [ ] Player-facing README explaining install.
- [ ] Cookbook entry: `docs/cookbook/author-first-darkfix.md`,
      the workflow written down while it's fresh.

**Done when**: a stranger could download the v0.1 zip, run
`apply.py`, launch DS1 in DOSBox, and the bug is gone.

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

If the toolkit accumulates enough, `gpl-disasm` with most
opcodes documented, working `gpl-asm`, native GFF read/write,
region viewer, save inspector, then **OpenDS the engine**
becomes plumbing rather than reverse-engineering. At that
point spinning it up makes sense.

We do not commit to a date. We commit to building the toolkit
that makes it possible. If someone else picks up the toolkit
and ships an engine first, that is a successful outcome.

## Backlog (deferred items with triggers)

Everything still open from the shipped phases, each with the
condition that promotes it into scheduled work. Nothing here is
abandoned; nothing here is scheduled.

- [ ] **Cut the per-tool git tags, or drop the requirement.**
      `docs/versioning.md` says each release ships a
      `<tool>-vX.Y.Z` tag; `git tag` returns nothing, so no
      release has ever complied. Two honest resolutions:
      backfill tags against the commits that bumped each
      `VERSION` (a one-off script walking `git log -- VERSION`
      makes this mechanical), or amend `docs/versioning.md` to
      name `VERSION` + `patchnotes.md` as the whole release
      record and drop tags. Open since the 2026-07-23
      reconciliation sweep. **Decide before the first darkfix
      release**, so patches do not inherit the ambiguity.
- [ ] **`gff-edit` segmented-type build.** Builder covers
      indexed GFFs only; the secondary-table + `GFFI`
      cross-reference dance is unwritten. Promote when a
      downstream consumer needs to *construct* a segmented
      GFF from scratch (reading and replacing already work).
- [ ] **`repro` bug-triggering save curation.** Per-bug saves
      placed just before the trigger, indexed by bug ID.
      Ongoing alongside every fix; promote to a focused push
      when Phase 6 picks its first bug (it needs one).
- [ ] **`image-extract` animated sprite export (GIF / APNG).**
      The still half shipped in v0.3.0 (`--frames-all`,
      `--spritesheet`). Needs an encoder decision first: no
      in-tree GIF/APNG writer, and a new dep needs sign-off
      per spec §7a. Note `region-render` v0.7.0 already
      shells to ffmpeg for `--gif`; the same trick applies
      here and probably settles the question.
- [ ] **`region-render` animated palette colours.** VGA
      colour cycling; blocked on EXE RE of the cycle-table
      layout. Phase 5.6 is the unblocker; candidates
      (`VGAColorCycle`, `gCycleColor`) are already named in
      the DSO symbol table.
- [ ] **`region-render --annotate`.** Entity-name overlays on
      rendered maps; deferred for lack of an in-tree font
      without a new dep. Promote when atlas or a modder
      workflow wants labelled maps badly enough to revisit
      (SVG output or a tiny embedded bitmap font are the
      escape hatches).
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
- [ ] **`opcode-fuzz` recipe format decision + recipe-driven
      fuzz.** The harness runs a swapped chunk through DOSBox
      and diffs `DARKRUN.GFF`; what is missing is the settled
      recipe format (short-form mnemonics vs JSON vs gpl-asm
      extension) and the loop that walks candidate opcodes.
      Phase 5's done-when (discover at least one
      previously-unknown opcode, add it to
      `docs/gpl-opcodes.md`) is still open; keep this phase
      alive until it is met or explicitly closed.
- [ ] **`save-inspect` DARKRUN SAVE chunk RE.** SAVE/1 (the
      ~10 KB probable master per-region state table),
      SAVE/2-/4, /7-/9, the u16 scalar family at ids 10..17,
      the 51-byte SAVE/18 boolean array. Bootstrap with the
      v0.7.0 `save-diff` harness: snapshot, one in-game
      action, snapshot, diff. Quest and world-state fixes
      need this; promote when the first such fix is chosen.
- [ ] **`extract.sh`.** From-installer extraction wrapper.
      Deferred; `innoextract` is one command and
      `verify-install --repair` already shells out. Reinstate
      only if a contributor needs it.
- [ ] **Python test harness decision.** The repo has none;
      Python tools gate on ruff + `compileall` in CI and ship
      `--selftest` flags (`ovr-map`). Options: keep the flag
      idiom, or standardise on stdlib `unittest` discovery in
      CI. Decide the next time a third Python tool grows a
      selftest.

## Tooling inventory and gaps

Checked on the dev host 2026-08-28. **Everything the docs cite
is installed.** Nothing blocks any phase.

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
- **`keystone-engine` + `bsdiff4`** in the applier venv:
  already named in `docs/build-environment.md` §2 as the
  pre-approved Python non-stdlib exceptions. Install them
  when Phase 5.7 / Phase 6 begin, not before; no tool under
  `tools/` depends on them today.

Not needed, for the record: LE/LX Ghidra loaders (the DOS/4GW
model was disproved, `dsun-exe-re.md` §1), decompilers beyond
Ghidra (16-bit real-mode support elsewhere is worse), and any
Windows-cross toolchain (patches are data + Python, not
compiled code).
