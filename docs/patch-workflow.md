# Patch Workflow

The end-to-end process for authoring one fix, from "this bug
exists" to "this bug is gone in the shipped patch."

This is the doc to read before sitting down to fix a specific
bug. Skim once. Refer back as needed.

## 0. Prerequisites

- Fedora dev environment set up — see
  [`build-environment.md`](build-environment.md).
- Both games extracted to `extracted/ds1/` and `extracted/ds2/`.
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

1. `gpl-disasm extracted/dsN/GPLDATA.GFF > scratch/<bug-id>/dump.gpl.s`
2. Locate the chunk responsible (search for dialog strings,
   item names, NPC names — they tend to be embedded in or
   adjacent to the relevant chunk).
3. Read the chunk's disassembly in `nvim` or `e`.
4. Find the bug. Often a wrong jump target, missing flag clear,
   or off-by-one.
5. Compute the byte-level edit. Most fixes are 1–3 bytes.

## 3b. Binary path

Workflow detail in [`binary-patching.md`](binary-patching.md).
Quick version:

1. `r2 -A extracted/dsN/DSUN.EXE`
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

Python 3, no dependencies beyond stdlib + the project's tools.
Reads the original file, applies the edit, writes the output.
Idempotent: running twice does not double-apply.

Skeleton:

```python
"""fix.dsN.<short-id> — one-line summary"""

from darkfix.patcher import apply_bytes, apply_gff_chunk

ID = "fix.dsN.<short-id>"
TARGET = "DSUN.EXE"          # or "GPLDATA.GFF" etc.
SOURCE_SHA256 = "..."        # canonical 1.10 hash

# For binary fixes:
EDITS = [
    {"offset": 0x1234, "expect": b"\x74\x0a", "replace": b"\x75\x0a"},
]

def apply(source_path, dest_path):
    apply_bytes(source_path, dest_path, EDITS, expect_sha=SOURCE_SHA256)
```

For GPL data fixes, the script extracts the relevant chunk via
`gff-tool`, edits it, and reinserts it.

## 5. Test the fix

Three layers:

### 5.1. Hash test

```sh
python3 dsN-patch/fixes/NNN-<short-id>.py extracted/dsN/<file> /tmp/patched
sha256sum /tmp/patched
```

The hash should match a value recorded in the writeup. This
guards against regressions in the patch script itself.

### 5.2. In-game test

1. Apply the patch to a fresh DOSBox install.
2. Load the bug-trigger save.
3. Run through the trigger. The bug should not fire.
4. Run through any nearby triggers (the same NPC, the same
   region, the same item) to verify nothing else broke.

### 5.3. Playthrough test

Periodically — at minor-version boundaries — do a longer
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
   `dsN: fix.dsN.<short-id> — one-line summary`.

(Per `~/CLAUDE.md`: do not commit on the user's behalf without
being asked.)

## 7. Ship

When the next minor version is ready:

1. Bump version in `dsN-patch/manifest.toml`.
2. Move "Unreleased" content in `patchnotes.md` under a new
   version heading.
3. Build the distribution zip:
   `tools/build-release.sh dsN <version>`.
4. Tag the umbrella repo: `git tag darkfix-dsN-vMAJOR.MINOR.PATCH`.
5. Push. Create a GitHub release; attach the zip.

## 8. When stuck

- **Ask in the dsoageofheroes Discord**:
  https://discord.gg/W942xHN72S
- **Re-read** [`upstream-projects.md`](upstream-projects.md) —
  the answer is often already in libgff or soloscuro-archive's
  source.
- **Sleep on it.** Half of the genuinely-hard bugs in projects
  like this resolve overnight, in the shower, on a walk.
