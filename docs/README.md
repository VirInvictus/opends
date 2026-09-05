# OpenDS documentation

Everything we learn gets written down here. Two kinds of document
live in this directory: **reference** (formats, opcodes, catalogs;
dense, written to be consulted) and **walkthrough** (cookbook
entries and workflow guides; written to be followed top to
bottom). The tables below say which is which.

## Start here, by goal

**"I want to mod the games."**
Start with the [cookbook](cookbook/): each entry is a complete,
tested walkthrough of one modding task (edit a PC's HP, give an
item, edit the DS1 active party). Keep
[`engine-quirks.md`](engine-quirks.md) open while you work; it
lists the behaviors that will otherwise eat an afternoon. When a
walkthrough mentions a chunk or field you want to dig into,
[`file-formats.md`](file-formats.md) is the authoritative layout
reference.

**"I want to understand the engine."**
Read [`research.md`](research.md) first for the short version:
lineage, architecture, what GPL is. Then
[`dsun-exe-survey.md`](dsun-exe-survey.md) for the measured
whole-binary structure of both engines, then
[`dsun-exe-re.md`](dsun-exe-re.md) for the disassembly-level
detail of `DSUN.EXE`. [`format-coverage.md`](format-coverage.md)
says which chunk kinds the corpus ships but the docs do not yet
describe. For the
scripting VM specifically:
[`gpl-bytecode.md`](gpl-bytecode.md) explains the language and
encoding, [`gpl-opcodes.md`](gpl-opcodes.md) is the opcode table,
and [`dso-symbols.md`](dso-symbols.md) documents the debug-symbol
trove that names 3,530 engine functions.

**"I want to author or apply patches."**
[`patch-workflow.md`](patch-workflow.md) is the end-to-end fix
authoring guide (GPL edit or binary patch, and how to choose);
[`fix-format.md`](fix-format.md) is the authoritative patch
artifact specification (what the applier runs).
The applier is real: [`../ds1-patch/`](../ds1-patch/)
(v0.0.1) ships `apply.py` + the `darkfix` engine that verify an
install against the canonical hashes, back up, apply, journal,
and unapply; `apply.py --selftest` proves the whole cycle.
[`binary-patching.md`](binary-patching.md) covers the
EXE-patching path in detail. [`known-bugs.md`](known-bugs.md) is
the target list. [`source-hashes/`](source-hashes/) holds the
canonical SHA256 manifests every patch verifies against, and
[`install-variants.md`](install-variants.md) explains why those
manifests target the GOG CD 1.10 base (and what the floppy
variant changes).

**"I want to contribute tooling."**
[`build-environment.md`](build-environment.md) gets a Fedora dev
box from zero to running the corpus tests.
[`versioning.md`](versioning.md) is the per-tool release policy.
[`upstream-projects.md`](upstream-projects.md) catalogs the prior
reverse-engineering efforts we build on (and the
attribute-everything policy; see also the repo-root
[`CREDITS.md`](../CREDITS.md)).

## Every document

### Reference (formats, opcodes, catalogs; dense, consulted)

| Document | What it holds |
|---|---|
| [`file-formats.md`](file-formats.md) | The GFF container and every chunk layout we've locked. |
| [`engine-quirks.md`](engine-quirks.md) | Surprising engine behaviors that affect modding. |
| [`gpl-bytecode.md`](gpl-bytecode.md) | The GPL scripting language and its bytecode encoding. |
| [`gpl-opcodes.md`](gpl-opcodes.md) | The 129-entry GPL opcode table. |
| [`dso-symbols.md`](dso-symbols.md) | Dark Sun Online debug symbols and the curation process. |
| [`format-coverage.md`](format-coverage.md) | Machine-generated: chunk kinds present vs documented. |
| [`source-hashes/`](source-hashes/) | Canonical SHA256 manifests for the GOG 1.10 installs. |
| [`versioning.md`](versioning.md) | Per-tool semver policy, `VERSION` files, tag format. |
| [`dispatch-table-ds1.md`](dispatch-table-ds1.md) | Resolved DS1 GPL dispatch table. |
| [`dispatch-table-ds2.md`](dispatch-table-ds2.md) | Resolved DS2 GPL dispatch table. |
| [`fix-format.md`](fix-format.md) | The darkfix patch artifact specification. |

### Engine RE (reverse-engineering notes; read in order)

| Document | What it holds |
|---|---|
| [`research.md`](research.md) | The short engine overview: lineage, architecture, GPL at a glance. |
| [`dsun-exe-survey.md`](dsun-exe-survey.md) | Whole-binary measured survey of both engines. |
| [`dsun-exe-re.md`](dsun-exe-re.md) | `DSUN.EXE` reverse-engineering index. |
| [`re-tooling.md`](re-tooling.md) | Host RE tooling (Ghidra, JDK, pwntools): setup and recipes. |

### Patching (authoring and applying fixes)

| Document | What it holds |
|---|---|
| [`patch-workflow.md`](patch-workflow.md) | Authoring a fix end to end. |
| [`fix-format.md`](fix-format.md) | The darkfix patch artifact specification. |
| [`binary-patching.md`](binary-patching.md) | The `DSUN.EXE` binary-patch path. |
| [`known-bugs.md`](known-bugs.md) | The bug catalog and the bug-site census. |
| [`install-variants.md`](install-variants.md) | Release lineages and the patch-base rationale. |
| [`upstream-projects.md`](upstream-projects.md) | Prior Dark Sun RE projects and attribution. |

### Contributing (getting started)

| Document | What it holds |
|---|---|
| [`build-environment.md`](build-environment.md) | Dev setup on Fedora: deps, game extraction, corpus layout. |
| [`cookbook/`](cookbook/) | Tested end-to-end modding recipes; start at its README. |

The repo root holds the project-level documents:
[`spec.md`](../spec.md) (the contract; read before changing
semantics), [`roadmap.md`](../roadmap.md) (phase status, the
single source of planning truth), and
[`patchnotes.md`](../patchnotes.md) (per-tool release history,
newest first). The per-tool overview lives in
[`../tools/README.md`](../tools/README.md).

The repo root holds the
project-level documents:
[`spec.md`](../spec.md) (the contract; read before changing
semantics), [`roadmap.md`](../roadmap.md) (phase status, the
single source of planning truth), and
[`patchnotes.md`](../patchnotes.md) (per-tool release history,
newest first).
