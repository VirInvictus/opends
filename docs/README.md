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
[`dsun-exe-re.md`](dsun-exe-re.md) for the disassembly-level
detail of `DSUN.EXE`. For the scripting VM specifically:
[`gpl-bytecode.md`](gpl-bytecode.md) explains the language and
encoding, [`gpl-opcodes.md`](gpl-opcodes.md) is the opcode table,
and [`dso-symbols.md`](dso-symbols.md) documents the debug-symbol
trove that names 3,530 engine functions.

**"I want to author or apply patches."**
[`patch-workflow.md`](patch-workflow.md) is the end-to-end fix
authoring guide (GPL edit or binary patch, and how to choose).
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

| Document | Kind | What it holds |
|---|---|---|
| [`cookbook/`](cookbook/) | walkthrough | Tested end-to-end modding recipes; start at its [README](cookbook/README.md). |
| [`file-formats.md`](file-formats.md) | reference | The GFF container and every chunk layout we've locked (CHAR, SAVE, BMP, region, ...). |
| [`engine-quirks.md`](engine-quirks.md) | reference | Surprising engine behaviors that affect modding, each with why and where it bites. |
| [`known-bugs.md`](known-bugs.md) | reference | The bug catalog: SSI's official 1.02 fix list plus community-reported post-1.10 bugs. |
| [`research.md`](research.md) | context | The short engine overview: lineage, architecture, GPL at a glance. Read before `dsun-exe-re.md`. |
| [`dsun-exe-re.md`](dsun-exe-re.md) | reference | `DSUN.EXE` reverse-engineering index: functions, memory layout, segment offsets. |
| [`gpl-bytecode.md`](gpl-bytecode.md) | reference | The GPL scripting language and its bytecode encoding. |
| [`gpl-opcodes.md`](gpl-opcodes.md) | reference | The 129-entry GPL opcode table. |
| [`dso-symbols.md`](dso-symbols.md) | reference | Index into the Dark Sun Online debug symbols and how we curate names from them. |
| [`patch-workflow.md`](patch-workflow.md) | walkthrough | Authoring a fix end to end: repro, locate, edit, verify, package. |
| [`binary-patching.md`](binary-patching.md) | walkthrough | The `DSUN.EXE` binary-patch path: TOML patch format, r2 workflow, risks. |
| [`build-environment.md`](build-environment.md) | walkthrough | Dev setup on Fedora: deps, game extraction, corpus layout. |
| [`source-hashes/`](source-hashes/) | reference | Canonical SHA256 manifests for the GOG 1.10 installs (`verify-install` checks against these). |
| [`install-variants.md`](install-variants.md) | reference | DS1/DS2 release lineages (floppy vs CD), proof of what GOG ships, and the patch-base rationale. |
| [`upstream-projects.md`](upstream-projects.md) | reference | Catalog of prior Dark Sun RE projects and exactly what we use from each. |
| [`versioning.md`](versioning.md) | reference | Per-tool semver policy, `VERSION` files, tag format. |

The repo root holds the project-level documents:
[`spec.md`](../spec.md) (the contract; read before changing
semantics), [`roadmap.md`](../roadmap.md) (phase status, the
single source of planning truth), and
[`patchnotes.md`](../patchnotes.md) (per-tool release history,
newest first).
