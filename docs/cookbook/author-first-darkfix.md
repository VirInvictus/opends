# Cookbook: author your first darkfix

The workflow for taking a Dark Sun bug from "it reproduces" to
"shipped fix in a `darkfix-<game>` release", written as steps you
can follow. Each step carries a worked example from the first real
fix, `fix.ds1.deadtriggers` (darkfix-ds1 0.1.0, 2026-09-11): the
Darkhold dead-trigger family. The full analysis lives in
[`../../ds1-patch/fixes/001-deadtriggers.md`](../../ds1-patch/fixes/001-deadtriggers.md);
the examples here are the command-level trail.

## The pipeline at a glance

1. **Pick and scope the bug** (`docs/known-bugs.md`).
2. **Build the repro fixture** (`tools/repro/`).
3. **Characterize it** (baseline run + the census table).
4. **Locate the site** (data side: `gpl-disasm` + `gff-edit`;
   binary side: `ovr-map` + a written site report).
5. **Author the fix** (`gpl-asm --patch` for bytecode,
   `exe-patch` for EXE bytes, `gff-edit` for data files).
6. **Prove it** (`repro --diff`).
7. **Package it** (manifest + fix script + writeup in
   `dsN-patch/`).
8. **Release it** (tag `darkfix-<game>-vX.Y.Z`).

## 1. Pick and scope the bug

- Source list: `docs/known-bugs.md` (the community list and the
  bug-site census at §3a).
- Prefer, in order: a data-surface bug (GPL script or GFF data;
  no EXE work), a bug whose site the census already
  characterizes, everything else.
- A binary-surface fix needs a written site report BEFORE the fix
  is authored (function, evidence chain, before/after
  disassembly). No site report, no patch (roadmap policy).
- Record the choice: the bug gets a stable id
  (`fix.dsN.<short-name>`) the day it is picked.

*Worked example (fix.ds1.deadtriggers):* picked from the sweep
evidence, not a community report: `dead-trigger-sweep.py` over the
DS1 dump showed six trigger registrations pointing at one emptied
handler (`GPL-200@0x909`), and the correlation dig tied all six to
Darkhold endgame content. Id assigned on pick day; the pick is
recorded in the Phase 6 pick box of `roadmap.md` with the decision
provenance.

## 2. Build the repro fixture

- `tools/repro/bugs/<id>/bug.toml` declares the fixture: game,
  setup files to stage, trigger commands, the run budget, and
  pass/fail expectations (`require_files` / `forbid_files`
  sentinels on the D: drive).
- The harness overlay-mounts the install, so nothing in the game
  folder is ever written.
- Verify the fixture FAILS on the unpatched game in the way that
  demonstrates the bug (sentinels, DARKRUN state, video).

```sh
python3 tools/repro/repro.py <bug-id>
```

*Worked example (fix.ds1.deadtriggers):* the bug scene is
endgame-only, so the fixture ships in two legs: the harness leg
(`bugs/ds1-deadtriggers/bug.toml`: boot, run the budget, no scene)
proves the patched tree boots clean under `--diff` today, and the
scene leg (a played DARKSAVE.GFF plus a keystroke load-save
schedule) is documented in the fixture for when the played-save
gate opens. Ship the leg you can prove; document the one you
cannot.

## 3. Characterize it

- Run the fixture a few times; note what differs (the
  `--keep-scratch` tree has every engine write).
- Update the census row (located / named / root cause) as the
  picture sharpens. The row is the checklist the rest of this
  cookbook consumes.

## 4. Locate the site

Data surface: disassemble the owning GPL chunk
(`gpl-disasm <gff> --kind GPL --id N`), find the wrong branch /
flag / constant, and note the exact byte positions (the
disassembly's offset annotations are byte-accurate).

Binary surface: `ovr-map --disasm <seg>` names entry points; a
site report in `docs/dsun-exe-re.md` (or the fix writeup) is
mandatory before authoring. `ovr-map --syms` catalogue names and
string-xref anchors (via `scripts/xref-string.py`) are the
evidence chain.

*Worked example (fix.ds1.deadtriggers):* site location was
corpus-wide, not single-chunk: dump the whole file
(`gpl-disasm .games/ds1/GPLDATA.GFF --all -o dump/ --json`), run
`dead-trigger-sweep.py dump/` for the dead rows, then sweep every
chunk for other registrations of the same objects to find each
object's working handler. The registration map (who registers
what, alive vs dead) is what turns "this handler is empty" into
"this registration occludes that one".

## 5. Author the fix

Bytecode: a `gpl-asm --patch` script. Label-relative `at`,
mandatory `bytes_old` fingerprint per edit, `--dry-run` first.

```sh
gpl-asm --patch fix.toml chunk.bin --dry-run
gpl-asm --patch fix.toml chunk.bin -o chunk.fixed.bin
```

EXE bytes: an `exe-patch` script. `ovr:`/symbol addressing,
mandatory `bytes_old`, and `--verify` is the last gate (it
refuses drift, segment straddles, padding, and any length
change; EXE patches are in-place only).

```sh
exe-patch.py .games/ds1/DSUN.EXE --verify fix.toml
exe-patch.py .games/ds1/DSUN.EXE --patch fix.toml -o DSUN-fixed.exe
```

16-bit assembly for replacement bytes:
`exe-patch.py --asm "mov ax, 0x4b75"` (nasm, `bits 16`).

GFF data: `gff-edit`'s write path (`gff-cat replace`) for whole
chunks; the fix script wraps it
(`darkfix.patcher.apply_gff_chunk`).

*Worked example (fix.ds1.deadtriggers):* all three tools in one
pass. Extract each owning chunk (`gff-cat extract .games/ds1/GPLDATA.GFF GPL 195 -o gpl-195.bin`),
edit with a label-anchored patch script (`gpl-asm --patch
fix-gpl195.patch gpl-195.bin --dry-run`, then `-o`), reinsert
(`gff-cat replace ... GPL 195 gpl-195.patched.bin -o ...`), and
byte-diff the result: the authored file must differ from the
original at exactly the intended bytes (here: eleven, across
three chunks). The shipped fix script then embeds the same bytes
as absolute-offset EDITS so the player-side applier needs no
tools.

## 6. Prove it

`repro --diff` runs the fixture twice (baseline vs patched) and
emits a structured delta; FIX CONFIRMED (baseline FAIL, patched
PASS) is the shape you want.

```sh
python3 tools/repro/repro.py <bug-id> --diff path/to/patched-files/
```

*Worked example (fix.ds1.deadtriggers):* the scene is not
reachable from a cold boot, so the capture proves the
non-regression half: both legs PASS with identical DARKRUN.GFF
world-state fingerprints and no sentinel delta. The behavioral
half is claimed by the static proofs instead (re-disassembly +
sweep delta, the hash-pinned selftest cycle) and is documented as
riding the played-save gate. Say plainly which half your capture
proves; do not let NO VERDICT DELTA read as a pass it is not.

## 7. Package it

In `dsN-patch/`:

- `fixes/<id>.md`: the writeup (symptom, root cause, the fix).
- `fixes/<id>.py`: the fix script (`ID`, `TARGET`,
  `SOURCE_SHA256`, `EDITS` or the chunk-level apply function).
- `manifest.toml`: add the fix under `[[fixes]]` with its
  default on/off state (on for clear bugs, off for
  balance-affecting ones).
- The manifest's `[target.files]` must hash every file the fix
  touches.

## 8. Release it

- Bump `dsN-patch/VERSION`, add the `patchnotes.md` entry
  (newest first), tick the roadmap boxes.
- Tag `darkfix-<game>-vX.Y.Z` at the release commit (message =
  the patchnotes entry, verbatim).
- The player README install section in `dsN-patch/README.md`
  stays true to what shipped.

*Worked example (fix.ds1.deadtriggers):* releasing as
darkfix-ds1 0.1.0: VERSION bumped, patchnotes entry added,
roadmap Phase 6 boxes ticked with the evidence; the
`darkfix-ds1-v0.1.0` tag is cut by the verbatim procedure
(message = the patchnotes entry) on Brandon's go, per the
tag-approval habit.
