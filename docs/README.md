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
(darkfix-ds1, now at 0.1.0) ships `apply.py` + the `darkfix`
engine that verify an install against the canonical hashes, back
up, apply, journal, and unapply; `apply.py --selftest` proves the
whole cycle, and v0.1.0 shipped the first real fix
(`fix.ds1.deadtriggers`, 2026-09-11).
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
| [`object-formats.md`](object-formats.md) | Object database records (creatures, items, OJFF), the spell power tables, MONR. |
| [`region-formats.md`](region-formats.md) | Maps and geography: RMAP/GMAP bits, ETAB placements, trigger registrations. |
| [`overlay-formats.md`](overlay-formats.md) | The Borland overlay apparatus: segment load table, module descriptors, relocation tables, the INT 3Fh dispatcher, static far-pointer resolution. |
| [`rules-tables.md`](rules-tables.md) | The AD&D 2E rules data: the rules block, saving throws, THAC0 derivation, XP tables, ability-score tables. |
| [`combat-flow.md`](combat-flow.md) | The native combat loop: entry, rounds, initiative, attack resolution, death, XP, morale. |
| [`spell-effects.md`](spell-effects.md) | The spell/effect machinery: cast path, dispatch surfaces, the active-effect list, saves, special attacks, durations. |
| [`chargen-flow.md`](chargen-flow.md) | Character creation, dual/multi-class, level-up, rest and memorization, the RNG, the DATA chunks. |
| [`exploration-flow.md`](exploration-flow.md) | Exploration movement: click-to-move, blocking, pathfinding, line of sight, triggers, region transitions, viewport. |
| [`cinematics-ds1.md`](cinematics-ds1.md) | The DS1 BMA frame codec, the ACF script opcodes, and the cinematic player chain. |
| [`asset-bindings.md`](asset-bindings.md) | Engine-side asset bindings: item/spell icons, portraits, palette cycling, CBMP. |
| [`audio-routing.md`](audio-routing.md) | How ids become sound and music: DJ.DAT, the driver dispatch, SFX id spaces, speech. |
| [`screen-flow.md`](screen-flow.md) | The window manager, the screen inventory, mode transitions, input dispatch, the dialog print service. |
| [`gpl-vm.md`](gpl-vm.md) | The GPL VM execution and data-model spec (the reimplementation keystone). |
| [`presentation-formats.md`](presentation-formats.md) | Images, UI resources (BUTN/WIND/APFM/FONT), audio, cinematics; the asset census. |
| [`dialogs.md`](dialogs.md) | The dialog machinery, the full text corpus census, and the conversion shape. |
| [`bestiary-ds1.md`](bestiary-ds1.md) / [`bestiary-ds2.md`](bestiary-ds2.md) | Machine-generated: every creature record, per game. |
| [`item-catalogue-ds1.md`](item-catalogue-ds1.md) / [`item-catalogue-ds2.md`](item-catalogue-ds2.md) | Machine-generated: every item record, per game. |
| [`container-contents-ds1.md`](container-contents-ds1.md) / [`container-contents-ds2.md`](container-contents-ds2.md) | Machine-generated: every chest/container's contents. |
| [`creature-inventories-ds1.md`](creature-inventories-ds1.md) / [`creature-inventories-ds2.md`](creature-inventories-ds2.md) | Machine-generated: what every creature carries. |
| [`spell-catalogue-ds1.md`](spell-catalogue-ds1.md) / [`spell-catalogue-ds2.md`](spell-catalogue-ds2.md) | Machine-generated: every spell power record, per game. |
| [`world-dump-ds1.md`](world-dump-ds1.md) / [`world-dump-ds2.md`](world-dump-ds2.md) | Machine-generated: every region's placements, grids, and triggers. |
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
