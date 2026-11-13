# Patch Workflow

The end-to-end process for authoring one fix, from "this bug
exists" to "this bug is gone in the shipped patch."

This is the doc to read before sitting down to fix a specific
bug. Skim once. Refer back as needed.

## 0. Prerequisites

- Fedora dev environment set up: see
  [`build-environment.md`](build-environment.md).
- Both games extracted to `.games/ds1/` and `.games/ds2/`.
- DOSBox-Staging configured to run them.
- A clean save before the bug-trigger point (build a save library
  per game; reuse across fixes).

## 1. Confirm the bug

Don't fix what you can't reproduce.

1. Run the game in DOSBox-Staging on a clean install.
2. Take the save state to the bug-trigger point.
3. Trigger the bug. Capture screen + audio if relevant
   (DOSBox `capture` keybind, or `obs-studio`).
4. Note exact party composition, inventory state, and recent
   actions. Some bugs only fire under specific preconditions.
5. Save the captured material to `scratch/<bug-id>/repro/`
   (`scratch/` is gitignored).

If you can't reproduce reliably, stop here. Document what you
saw in [`known-bugs.md`](known-bugs.md) as "not yet reproducible"
and move on.

## 2. Classify the surface

Quickly decide: GPL data fix or DSUN.EXE binary fix?

Heuristics:

- Quest-progression bug, dialog bug, flag bug, item-give bug,
  trigger-fires-twice bug → **GPL**, almost certainly.
- Combat AI bug, rendering bug, input bug, save/load corruption,
  audio glitch → **DSUN.EXE**, almost certainly.
- Item-state bug (charged weapon vanishing) → could be either;
  start with GPL.

If wrong, you'll know within an hour of investigation. Switch
surfaces and try again.

## 3a. GPL path

Workflow detail in [`gpl-bytecode.md`](gpl-bytecode.md).
Quick version:

1. `gpl-disasm .games/dsN/GPLDATA.GFF > scratch/<bug-id>/dump.gpl.s`
2. Locate the chunk responsible (search for dialog strings,
   item names, NPC names: they tend to be embedded in or
   adjacent to the relevant chunk).
3. Read the chunk's disassembly in `nvim` or `e`.
4. Find the bug. Often a wrong jump target, missing flag clear,
   or off-by-one.
5. Compute the byte-level edit. Most fixes are 1–3 bytes.

## 3b. Binary path

Workflow detail in [`binary-patching.md`](binary-patching.md).
Quick version:

1. `r2 -A .games/dsN/DSUN.EXE`
2. `/r <symptom-string>` to find the function.
3. Read the function with `pdf` or `VV`.
4. Set a DOSBox-debugger breakpoint, trigger the bug, watch state.
5. Compute the byte-level edit. Most fixes are 1–3 bytes.

## 4. Author the fix

Two artifacts per fix:

### 4.1. Writeup: `dsN-patch/fixes/NNN-<short-id>.md`

```markdown
# fix.dsN.<short-id>

**Bug**: One-line statement of the symptom.

**Repro**: How to make the bug fire on a clean install.

**Cause**: What's wrong, mechanically.

**Fix**: What we change.

**Surface**: GPL / DSUN.EXE

**Verified on**: GOG 1.10 (DS1 / DS2)

**Default**: on / off

## Details

Long-form analysis. Include:

- The disassembly snippet (before / after) for GPL fixes
- The r2 listing (before / after) for binary fixes
- Why this fix is correct (not just "it makes the bug stop")
- Any edge cases the fix doesn't handle
```

### 4.2. Patch script: `dsN-patch/fixes/NNN-<short-id>.py`

Python 3, stdlib-only. One fix per module; idempotent by
construction (the applier's journal and `AlreadyApplied`
bookkeeping mean running twice does not double-apply).

The authoritative skeleton and contract live in
[`fix-format.md`](fix-format.md) (one canonical copy, so it
cannot drift): a fix module declares `ID`, `TARGET`,
`SOURCE_SHA256`, `EDITS` (fingerprint-checked, in-place byte
edits), and an `apply(source_path, dest_path)` function the
applier loads. `ds1-patch/fixes/000-noop.py` is the live
example; the engine behind it is `darkfix.patcher`
(`ds1-patch/scripts/darkfix/`: byte edits, GFF chunk
replacement, backup, journal) and the umbrella applier
`ds1-patch/scripts/apply.py` (verify, backup, apply,
`--unapply`). GPL data fixes use `apply_gff_chunk` from the
same module: extract via `gff-edit`, edit via `gpl-asm`'s
verified `--patch` output, reinsert.

Length-changing GPL repairs (detours) go through
`apply_gpl_repairs` with `GplRepair` records instead: each repair
is addressed chunk-relative (`kind`, `chunk_id`, `offset`),
carries the same fingerprint discipline (`expect` checked on the
pristine chunk before any write), and a `replace` longer than
`expect` becomes a detour: the applier appends
`[EXIT_GPL][replace][JUMP back]` after the chunk end, overwrites
the expect range with a JUMP to it (EXIT_GPL fill for any
remainder), and rebases the 15-bit big-endian label words listed
in `relocate`. Mechanism and gate: `detour-repairs.md`; the
adoption review that confirmed the encodings:
`gate-review-yuan-ti-2026-11-13.md`. Composition: the applier
composes EDITS and REPAIRS fixes on one file (EDITS apply in file
space first; repaired chunks are then extracted from the composed
bytes, so an absolute site inside a repaired chunk is already in
place when the repair's fingerprints are checked, and the chunk
replacement carries both). `relocate` follows yuan-ti's
convention (index of the label word's first byte inside
`replace`). The selftest's detour block exercises the math, the
gff-cat end-to-end on a synthetic GFF (when `gff-cat` is
available), and the mixed EDITS+REPAIRS composition with verify
and unapply. One residual rule: the standalone
`apply_gpl_repairs` path (a fix module calling it directly,
outside the applier's compose flow) must not share its target
file with an absolute-offset fix applied afterwards, because a
grown chunk moves file bytes.

## 5. Test the fix

Three layers:

### 5.1. Hash test

The hash gate is the applier's selftest: its real-install cycle
applies the shipped fix set to copies of every `[target.files]`
entry, asserts the patched-file hash recorded in the fix writeup
(any EDITS drift fails the run), verifies, and unapplies
byte-identically:

```sh
python3 ds1-patch/scripts/apply.py --selftest
```

(The fix scripts define an `apply()` function for the applier to
load, not a CLI, so they are not run directly.) The recorded
value lives in the fix's writeup under `fixes/`; add it there
when you author the fix.

### 5.2. In-game test

1. Apply the patch to a fresh DOSBox install.
2. Load the bug-trigger save.
3. Run through the trigger. The bug should not fire.
4. Run through any nearby triggers (the same NPC, the same
   region, the same item) to verify nothing else broke.

### 5.3. Playthrough test

Periodically: at minor-version boundaries: do a longer
playthrough with all enabled fixes on. Log anything unusual.
This is the catch-net for "fix A interacts badly with fix B."

## 6. Land the fix

1. Add the writeup and script to `dsN-patch/fixes/`.
2. Update `dsN-patch/manifest.toml` with the new fix entry.
3. Update [`known-bugs.md`](known-bugs.md): mark the bug
   "fixed in vN.M".
4. Update [`patchnotes.md`](../patchnotes.md) under the
   current "Unreleased" section.
5. Commit. Suggested message:
   `dsN: fix.dsN.<short-id>: one-line summary`.

(Per house rule, see `CLAUDE.md` under "Git habits": never push
without explicit approval, and show the commit message first.)

## 7. Ship

When the next minor version is ready:

1. Bump `dsN-patch/VERSION` (the single source of truth;
   `manifest.toml` never carries the version, per spec.md §4).
2. Move "Unreleased" content in `patchnotes.md` under a new
   version heading.
3. Build the distribution zip:
   `tools/build-release.sh dsN <version>`. The script assembles
   the flattened zip spec.md §4 defines (manifest.toml, VERSION,
   apply.py, darkfix/, fixes/, the player README), gates it
   through the fix-contract checks, a compile pass, and the
   staged applier's `--selftest`, then writes
   `darkfix-dsN-v<version>.zip` (default output
   `scratch/releases/`, override with `--out`; rebuilding an
   unchanged tree is byte-identical).
4. Tag the release commit (annotated; the message is that
   release's full patchnotes entry, not a summary): extract the
   entry verbatim into a file, then
   `git tag -a darkfix-dsN-vMAJOR.MINOR.PATCH --cleanup=verbatim -F <file> <release-commit>`.
5. Push. Create a GitHub release and attach the zip. From the
   next darkfix tag onward the `release zip` workflow does this
   automatically on the tag push (and on a manual dispatch with a
   tag input, for a release that already exists).

## 8. When stuck

- **Ask in the dsoageofheroes Discord**:
  https://discord.gg/W942xHN72S
- **Re-read** [`upstream-projects.md`](upstream-projects.md) ;
  the answer is often already in libgff or soloscuro-archive's
  source.
- **Sleep on it.** Half of the genuinely-hard bugs in projects
  like this resolve overnight, in the shower, on a walk.
