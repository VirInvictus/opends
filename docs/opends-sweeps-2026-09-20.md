# Opends fleet sweeps, 2026-09-20

Debt census and static test-coverage map for this repo, run as part
of the 2026-09-20 sweep stack. The census's load-bearing items were
fixed same day (commit "ci + docs: debt-census fixes"); the rest is
the dated worklist.

## Debt census (post-fix remainder)

- `port-spike/main.gd:623` `pass  # per-frame combat upkeep
  placeholder` - deliberate spike shortcut; revisit if the port
  takes real per-frame upkeep.
- Test-suite note from the same wave: the release path
  (`release.yml`, darkfix tag push) runs no tests at all, and
  `build-release.sh --selftest` exists but nothing invokes it. A
  tag cut from an untested commit ships with zero test execution.
  Candidate: add the selftest (or cargo test) as a release-job step.
- Local cruft (not repo debt): `port-spike/red_drawer.gd.uid`
  (deleted; the script never existed on disk), `scratch/`,
  `testing_facility/`, root `OvrMap.java`/`OvrRename.java`
  regenerated Ghidra scripts, `project.done`.

## Test-gap map

Discovery: `cargo test --workspace` sees everything; all corpus
tests skip silently without `.games/` (by design), and
`gif_assembly.rs` skips without ffmpeg, so CI never exercises the
GIF pipeline. The Python gate has the holes:

- **No `--selftest` at all**: save-inspect.py (3,162 lines,
  write-adjacent), dialog-extract.py, atlas.py, opcode-fuzz.py -
  9,408 lines gated only by ruff + compileall.
- `tools/gff-edit/scripts/extract-catalogue.py` HAS a real selftest
  (line 1520) but is not in the CI step.
- `tools/save-inspect/test-saves/{ds1-fuck,ds2-fuck}/` are
  referenced by nothing (orphaned fixtures).

Top 10 gaps by risk, each with the test that should exist:

1. **save-inspect write verbs** (`edit-pc`/`edit-item`/`add-item`):
   synthetic CHARSAVE-shaped GFF, edit, reparse, assert the field
   and byte-preservation of untouched fields, and that
   `.bak.<ts>` holds the exact pre-edit bytes.
2. save-inspect parser round-trip over the tracked test-saves
   fixtures (parse, re-encode, byte-identical) - also un-orphans
   them.
3. gpl-disasm `--json` text contract: a golden JSON fixture + a
   Python selftest consuming it fixes the silent-break class for
   dialog-extract, opcode-fuzz, and both sweeps at once (they all
   read with `.get()` defaults).
4. gff-cat Replace/Extract bin glue via `CARGO_BIN_EXE_gff-cat`:
   the code that actually mutates GFFs on disk; only the lib is
   covered.
5. Minimal happy-path selftests for the four gate-orphaned tools +
   one ci.yml line for extract-catalogue.
6. opends `detect()` dispatch table test (magics to tools).
7. verify-install drift detection (synthetic manifest + doctored
   tree, non-zero exit).
8. ovr-map synthetic MZ+FBOV fixture so its six structural
   invariants run on CI (port exe-patch's `build_fixture()`).
9. region-render animated-entity loading/frame composition.
10. Enforce the 95% aligned-percentage floor that
    `gpl-disasm/tests/corpus_smoke.rs` currently only prints.

Suite health: corpus plumbing duplicated ~8x (candidate for a dev
shared crate); `gpl-disasm/src/lib.rs` at 4,294 lines with 1,200+
lines of tail tests; the strongest tests in the repo are the two
darkfix appliers (hash-pinned per game).
