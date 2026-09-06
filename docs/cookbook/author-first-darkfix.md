# Cookbook: author your first darkfix

The workflow for taking a Dark Sun bug from "it reproduces" to
"shipped fix in a `darkfix-<game>` release", written as steps you
can follow. This file is a skeleton: the pipeline pieces below all
exist and are linked; the narrative walk-through gets filled in as
Phase 6 authors the first real fix (each step then gains a worked
example with real commands and real output).

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

*Worked example: pending the first Phase 6 fix.*

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

*Worked example: pending.*

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

## 6. Prove it

`repro --diff` runs the fixture twice (baseline vs patched) and
emits a structured delta; FIX CONFIRMED (baseline FAIL, patched
PASS) is the shape you want.

```sh
python3 tools/repro/repro.py <bug-id> --diff path/to/patched-files/
```

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

*Worked example: pending.*
