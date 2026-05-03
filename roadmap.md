# darkfix — Roadmap

Phased plan. Each phase has a single shippable artifact; later
phases depend on earlier ones. Solo-dev pacing — phases are
sized to fit a weekend or a week, not a quarter.

## Phase 0 — Documentation & extraction (current)

**Goal**: every fact we know is written down; both games' files
are extractable on Fedora.

- [x] Project skeleton, `.gitignore`, README, spec, roadmap.
- [x] Engine research dossier ([`docs/research.md`](docs/research.md)).
- [x] Format catalog ([`docs/file-formats.md`](docs/file-formats.md)).
- [x] Known-bugs catalog ([`docs/known-bugs.md`](docs/known-bugs.md)).
- [x] Upstream-projects map ([`docs/upstream-projects.md`](docs/upstream-projects.md)).
- [ ] Reproducible extraction script: `tools/extract.sh` that
      takes a GOG installer and emits `extracted/ds1/` or
      `extracted/ds2/`.
- [ ] Source-hash manifest: SHA256 of every shipped DS1 and DS2
      file, baked into the patch manifests.
- [ ] `tools/verify-install.py`: hash a player's install, identify
      whether it is GOG 1.10, original CD, or unknown.

**Done when**: a fresh clone + a GOG installer + one script call →
a fully populated `extracted/` tree, with file inventory and hash
manifest.

## Phase 1 — DOSBox repro harness

**Goal**: any bug from the known-bugs list can be reproduced on
the local machine in under five minutes.

- [ ] DOSBox-Staging configured to run DS1 and DS2 reliably on
      Fedora.
- [ ] Save-state library: per-bug, a save-game placed just before
      the bug-triggering action.
- [ ] Recording: SDL screen-cap of the bug fire (via DOSBox's
      built-in `capture` or external `obs-studio`).

**Done when**: every bug we plan to fix has a saved game and a
short script that takes the player to the moment of failure.

## Phase 2 — `gpl-disasm` v0

**Goal**: every byte of every `GPL ` chunk in DS1 disassembles
into mnemonic form, even if many opcodes are still `db`.

- [ ] Read GPL chunks via libgff or our own GFF reader.
- [ ] Identify entry points and basic-block boundaries.
- [ ] Print annotated assembly with offset markers.
- [ ] Cross-reference with `the-dark-lens` and DSO v1.0 debug
      symbols where available.

**Done when**: `gpl-disasm extracted/ds1/GPLDATA.GFF` produces
output that lets us locate a quest-script function by name (or by
nearby string reference).

## Phase 3 — First DS1 fix shipped

**Goal**: prove the patch pipeline end-to-end on the smallest
possible bug.

- [ ] Pick one trivial DS1 bug (TBD — needs Phase 1 repro work
      to identify candidates).
- [ ] Author the fix.
- [ ] Author the test (hash before/after, in-game repro).
- [ ] Tag `darkfix-ds1-v0.1`, push GitHub release.
- [ ] Player-facing README explaining install.

**Done when**: a stranger could download the v0.1 zip, run
`apply.py`, launch DS1 in DOSBox, and the bug is gone.

## Phase 4 — DS2 mines elevator

**Goal**: fix the most famous DS2 bug — the one that broke the
late game in 1994 and has never been fixed.

- [ ] Reproduce in DOSBox.
- [ ] Locate the GPL function or DSUN.EXE routine controlling the
      elevator transition.
- [ ] Diagnose the race / state bug.
- [ ] Author the fix (data or binary, whichever it lives in).
- [ ] Verify a full DS2 playthrough does not reproduce the
      original behavior.
- [ ] Ship as `darkfix-ds2-v0.1`.

**Done when**: a player who hits the elevator gets to the next
region, with a full party, on a clean install with the patch
applied.

## Phase 5 — Sweep DS2's "survived 1.10" list

**Goal**: every bug in [`docs/known-bugs.md`](docs/known-bugs.md)
section 2 (community-reported, post-1.10) has either a fix or an
explicit "won't fix" note with rationale.

- [ ] Charged-weapon disappearance.
- [ ] Doorway / item graphics layering.
- [ ] Save/exit bug.
- [ ] Audio static (verify no-op for OPL/MT-32 emulation paths).
- [ ] MEL DSP detect (verify no-op for DOSBox).

**Done when**: `darkfix-ds2-v0.5` or thereabouts ships with that
sweep.

## Phase 6 — DS1 sweep

**Goal**: same as Phase 5, for DS1's known issues.

- [ ] Compile a more thorough DS1 bug list (DS1 is less
      documented; we'll find issues during this phase).
- [ ] Fix each.

**Done when**: `darkfix-ds1-v0.5`.

## Phase 7 — v1.0 for both games

**Goal**: the patches reach a state where Brandon can recommend
them to fellow Dark Sun players in good conscience.

- [ ] Full playthrough of DS1 with the patch on; no workaround
      needed.
- [ ] Full playthrough of DS2 with the patch on; no workaround
      needed.
- [ ] Player-facing documentation: how to install, how to verify,
      how to report a bug.
- [ ] Tag `darkfix-ds1-v1.0` and `darkfix-ds2-v1.0`.

**Done when**: both v1.0 tags exist and a public announcement
goes out.

## Phase 8 — Stretch / aspirational

These are not on the patch roadmap; they're the engine project's
foothills. Listed here so they aren't forgotten.

- [ ] `gpl-asm` — round-trip reassembler for our disassembly format.
- [ ] Scripted tools to extract every NPC dialog tree as text
      (useful for both fan documentation and for OpenDS later).
- [ ] First experimental rendering of a region GFF in an SDL
      window (the OpenDS Phase 4 spike, ahead of the engine).
- [ ] Save-game format reverse-engineering deep enough to write
      saves, not just read.

If darkfix is healthy and we still have appetite, the engine
project ("OpenDS") spins up — but not before darkfix v1.0.
