# OpenDS documentation

Everything we learn gets written down here. The directory splits by
purpose: **[`reference/`](reference/)** (formats, opcodes, engine
flows; dense, written to be consulted), **[`catalogues/`](catalogues/)**
(machine-generated data dumps; regenerated, never edited by hand),
**[`reports/`](reports/)** (dated campaign dig records; the lab
notebooks behind the reference), **[`qa/`](qa/)** (runtime QA plans
and rig notes), **[`cookbook/`](cookbook/)** (tested walkthroughs,
followed top to bottom), and **[`source-hashes/`](source-hashes/)**
(the canonical SHA256 manifests every patch verifies against). The
tables below say which is which.

## Start here, by goal

**"I want to mod the games."**
Start with the [cookbook](cookbook/): each entry is a complete,
tested walkthrough of one modding task (edit a PC's HP, give an
item, edit the DS1 active party). Keep
[`engine-quirks.md`](reference/engine-quirks.md) open while you
work; it lists the behaviors that will otherwise eat an afternoon.
When a walkthrough mentions a chunk or field you want to dig into,
[`file-formats.md`](reference/file-formats.md) is the authoritative
layout reference.

**"I want to understand the engine."**
Read [`research.md`](reference/research.md) first for the short
version: lineage, architecture, what GPL is. Then
[`dsun-exe-survey.md`](reference/dsun-exe-survey.md) for the
measured whole-binary structure of both engines, then
[`dsun-exe-re.md`](reference/dsun-exe-re.md) for the
disassembly-level detail of `DSUN.EXE`.
[`format-coverage.md`](reference/format-coverage.md) says which
chunk kinds the corpus ships but the docs do not yet describe. For
the scripting VM specifically:
[`gpl-bytecode.md`](reference/gpl-bytecode.md) explains the
language and encoding, [`gpl-opcodes.md`](reference/gpl-opcodes.md)
is the opcode table, and
[`dso-symbols.md`](reference/dso-symbols.md) documents the
debug-symbol trove that names 3,527 engine functions.

**"I want to author or apply patches."**
[`patch-workflow.md`](reference/patch-workflow.md) is the
end-to-end fix authoring guide (GPL edit or binary patch, and how
to choose); [`fix-format.md`](reference/fix-format.md) is the
authoritative patch artifact specification (what the applier
runs). The appliers are real: [`../ds1-patch/`](../ds1-patch/)
(darkfix-ds1, at 0.2.0-beta.4: the deadtrigger and script-repair
families enabled, plus the beta script repairs adopted from
yuan-ti and the sweep-triage fixes, runtime-gated by
[QA](qa/)) and [`../ds2-patch/`](../ds2-patch/) (darkfix-ds2, at
0.1.2: the 37-row deadtrigger repoint). Both verify an install
against the canonical hashes, back up, apply, journal, and
unapply; `apply.py --selftest` proves the whole cycle.
[`binary-patching.md`](reference/binary-patching.md) covers the
EXE-patching path in detail.
[`known-bugs.md`](reference/known-bugs.md) is the target list.
[`source-hashes/`](source-hashes/) holds the canonical SHA256
manifests every patch verifies against, and
[`install-variants.md`](reference/install-variants.md) explains
why those manifests target the GOG CD 1.10 base (and what the
floppy variant changes).

**"I want to contribute tooling."**
[`build-environment.md`](reference/build-environment.md) gets a
Fedora dev box from zero to running the corpus tests.
[`versioning.md`](reference/versioning.md) is the per-tool release
policy. [`upstream-projects.md`](reference/upstream-projects.md)
catalogs the prior reverse-engineering efforts we build on (and
the attribute-everything policy; see also the repo-root
[`CREDITS.md`](../CREDITS.md)).

**"I want to run the runtime QA."**
Everything for the issue-#18 QA campaign lives in
[`qa/`](qa/): the rig report, the DS1+DS2 playthrough guide, the
save suite, and the per-site test packet for the beta script
repairs.

## reference/ — the evergreen reference

### Formats and data

| Document | What it holds |
|---|---|
| [`file-formats.md`](reference/file-formats.md) | The GFF container and every chunk layout we've locked. |
| [`object-formats.md`](reference/object-formats.md) | Object database records (creatures, items, OJFF), the spell power tables, MONR. |
| [`region-formats.md`](reference/region-formats.md) | Maps and geography: RMAP/GMAP bits, ETAB placements, trigger registrations. |
| [`overlay-formats.md`](reference/overlay-formats.md) | The Borland overlay apparatus: segment load table, module descriptors, relocation tables, the INT 3Fh dispatcher, static far-pointer resolution. |
| [`presentation-formats.md`](reference/presentation-formats.md) | The asset census (images, UI resources, audio, cinematics); its deep sections are superseded by asset-bindings and cinematics-ds1. |
| [`asset-bindings.md`](reference/asset-bindings.md) | Engine-side asset bindings: item/spell icons, portraits, palette cycling, CBMP. |
| [`audio-routing.md`](reference/audio-routing.md) | How ids become sound and music: DJ.DAT, the driver dispatch, SFX id spaces, speech. |
| [`audio-cues.md`](reference/audio-cues.md) | Which sounds the scripts actually request: ids, durations, context-derived meaning guesses. |
| [`dialogs.md`](reference/dialogs.md) | The dialog machinery, the full text corpus census, and the conversion shape. |
| [`cinematics-ds1.md`](reference/cinematics-ds1.md) | The DS1 BMA frame codec, the ACF script opcodes, and the cinematic player chain. |
| [`rules-tables.md`](reference/rules-tables.md) | The AD&D 2E rules data: the rules block, saving throws, THAC0 derivation, XP tables, ability-score tables. |
| [`gff-data-reference.md`](reference/gff-data-reference.md) | The complex-access keyword set rendered inside COMPLEX operands. |

### Engine flows

| Document | What it holds |
|---|---|
| [`combat-flow.md`](reference/combat-flow.md) | The native combat loop: entry, rounds, initiative, attack resolution, death, XP, morale. |
| [`spell-effects.md`](reference/spell-effects.md) | The spell/effect machinery: cast path, dispatch surfaces, the active-effect list, saves, special attacks, durations. |
| [`chargen-flow.md`](reference/chargen-flow.md) | Character creation, dual/multi-class, level-up, rest and memorization, the RNG, the DATA chunks. |
| [`exploration-flow.md`](reference/exploration-flow.md) | Exploration movement: click-to-move, blocking, pathfinding, line of sight, triggers, region transitions, viewport. |
| [`screen-flow.md`](reference/screen-flow.md) | The window manager, the screen inventory, mode transitions, input dispatch, the dialog print service. |
| [`engine-quirks.md`](reference/engine-quirks.md) | Surprising engine behaviors that affect modding. |

### GPL scripting

| Document | What it holds |
|---|---|
| [`gpl-bytecode.md`](reference/gpl-bytecode.md) | The GPL scripting language and its bytecode encoding. |
| [`gpl-opcodes.md`](reference/gpl-opcodes.md) | The 129-entry GPL opcode table. |
| [`gpl-vm.md`](reference/gpl-vm.md) | The GPL VM execution and data-model spec (the reimplementation keystone). |
| [`gplx-field-map.md`](reference/gplx-field-map.md) | The Script object field map, decoded from yuan-ti's traced notes. |
| [`dispatch-table-ds1.md`](reference/dispatch-table-ds1.md) | Resolved DS1 GPL dispatch table (machine-generated). |
| [`dispatch-table-ds2.md`](reference/dispatch-table-ds2.md) | Resolved DS2 GPL dispatch table (machine-generated). |
| [`dso-symbols.md`](reference/dso-symbols.md) | Dark Sun Online debug symbols and the curation process. |
| [`format-coverage.md`](reference/format-coverage.md) | Machine-generated: chunk kinds present vs documented. |

### Engine RE

| Document | What it holds |
|---|---|
| [`research.md`](reference/research.md) | The short engine overview: lineage, architecture, GPL at a glance. |
| [`dsun-exe-survey.md`](reference/dsun-exe-survey.md) | Whole-binary measured survey of both engines. |
| [`dsun-exe-re.md`](reference/dsun-exe-re.md) | `DSUN.EXE` reverse-engineering index. |
| [`re-tooling.md`](reference/re-tooling.md) | Host RE tooling (Ghidra, REA, JDK, pwntools): setup and recipes. |

### Patching

| Document | What it holds |
|---|---|
| [`patch-workflow.md`](reference/patch-workflow.md) | Authoring a fix end to end. |
| [`fix-format.md`](reference/fix-format.md) | The darkfix patch artifact specification. |
| [`binary-patching.md`](reference/binary-patching.md) | The `DSUN.EXE` binary-patch path. |
| [`detour-repairs.md`](reference/detour-repairs.md) | Design note for length-changing script repairs (the mechanism yuan-ti uses; contract and adoption gate, both halves shipped: the applier's REPAIRS path and gpl-asm 0.10.0's assemble_movable). |
| [`known-bugs.md`](reference/known-bugs.md) | The bug catalog and the bug-site census. |
| [`install-variants.md`](reference/install-variants.md) | Release lineages and the patch-base rationale. |

### Project and tooling

| Document | What it holds |
|---|---|
| [`versioning.md`](reference/versioning.md) | Per-tool semver policy, `VERSION` files, tag format. |
| [`build-environment.md`](reference/build-environment.md) | Dev setup on Fedora: deps, game extraction, corpus layout. |
| [`upstream-projects.md`](reference/upstream-projects.md) | Prior Dark Sun RE projects and attribution. |
| [`symbol-backlog-ds2.md`](reference/symbol-backlog-ds2.md) | DS2 symbol-coverage backlog for gpl-disasm, built from dso-online. |
| [`godot-port-readiness.md`](reference/godot-port-readiness.md) | Layer-by-layer checklist of what a Godot port consumes and its state. |

## catalogues/ — machine-generated data dumps

Every file below is regenerated by
`python3 tools/gff-edit/scripts/extract-catalogue.py` (reads the
canonical installs under `.games/`); each carries a
"do not edit" footer and a verification footer that fails loudly on
a data regression. Hand edits die on the next regeneration.

| Document | What it holds |
|---|---|
| [`bestiary-ds1.md`](catalogues/bestiary-ds1.md) / [`bestiary-ds2.md`](catalogues/bestiary-ds2.md) | Every creature record, per game. |
| [`item-catalogue-ds1.md`](catalogues/item-catalogue-ds1.md) / [`item-catalogue-ds2.md`](catalogues/item-catalogue-ds2.md) | Every item record, per game. |
| [`spell-catalogue-ds1.md`](catalogues/spell-catalogue-ds1.md) / [`spell-catalogue-ds2.md`](catalogues/spell-catalogue-ds2.md) | Every spell power record, per game. |
| [`creature-inventories-ds1.md`](catalogues/creature-inventories-ds1.md) / [`creature-inventories-ds2.md`](catalogues/creature-inventories-ds2.md) | What every creature carries, per game. |
| [`container-contents-ds1.md`](catalogues/container-contents-ds1.md) / [`container-contents-ds2.md`](catalogues/container-contents-ds2.md) | Every chest/container's contents, per game. |
| [`world-dump-ds1.md`](catalogues/world-dump-ds1.md) / [`world-dump-ds2.md`](catalogues/world-dump-ds2.md) | Every region's placements, grids, and triggers, per game. |

## reports/ — dated campaign dig records

The lab notebooks behind the reference. Each records one mining or
triage campaign with the evidence that fed (or will feed) the
evergreen docs; the dates are in the filenames.

| Document | What it holds |
|---|---|
| [`PROMPT-mineout.md`](reports/PROMPT-mineout.md) | The mineout campaign's mission prompt (campaign closed with mining-complete). |
| [`attribution-audit-2026-09-20.md`](reports/attribution-audit-2026-09-20.md) | Agent-wave attribution audit of the three upstream checkouts against CREDITS.md. |
| [`opends-sweeps-2026-09-20.md`](reports/opends-sweeps-2026-09-20.md) | Debt census and static test-coverage map from the 2026-09-20 sweep stack. |
| [`port-digs-2026-09-20.md`](reports/port-digs-2026-09-20.md) | Four EXE/data mining waves for the Godot port (pits/UI-parity evidence). |
| [`port-digs-2026-09-21.md`](reports/port-digs-2026-09-21.md) | The 15500/3020 dispatcher, capability masks, steal/give evidence. |
| [`port-digs-2026-10-06.md`](reports/port-digs-2026-10-06.md) | Mineout wave 1: DATA, RBRN, capability lists. |
| [`port-digs-2026-10-07.md`](reports/port-digs-2026-10-07.md) | Mineout closure sweep: every open hole driven to a verdict. |
| [`ds1-sweep-triage-2026-10-07.md`](reports/ds1-sweep-triage-2026-10-07.md) | Phase 9 triage: every catalogued DS1 bug driven to a verdict; feeds the ds1-patch fixes. |
| [`mining-complete.md`](reports/mining-complete.md) | Final record of the static-mining campaign (per-phase, chunk table, audio inventory). |
| [`mining-release-post-2026-10-06.md`](reports/mining-release-post-2026-10-06.md) | Reader's guide to the mining-completion release documents (links pinned to the tag). |
| [`elevator-digs-2026-11-02.md`](reports/elevator-digs-2026-11-02.md) | DS2 mines-elevator overnight dig: the Request machinery and the ride chain. |
| [`community-crossread-2026-11-13.md`](reports/community-crossread-2026-11-13.md) | Community knowledge cross-read (yuan-ti mining batch 1). |
| [`exchange-yuan-ti-2026-11-13.md`](reports/exchange-yuan-ti-2026-11-13.md) | Four exchange briefs prepared for yuan-ti. |
| [`gate-review-yuan-ti-2026-11-13.md`](reports/gate-review-yuan-ti-2026-11-13.md) | Adoption-gate record for yuan-ti's 29 GplRepairs (static gates pass; runtime QA pending). |
| [`yuan-ti-mining-2026-11-17.md`](reports/yuan-ti-mining-2026-11-17.md) | yuan-ti mining batch 2: remaining instruction and Scripting files. |

## qa/ — runtime QA

| Document | What it holds |
|---|---|
| [`QA_REPORT.md`](qa/QA_REPORT.md) | The QA rig as deployed (machine-local): hosts, DOSBox config, overlay discipline, patch state, patched GPLDATA hashes. |
| [`playthrough-qa-guide-2026-11-20.md`](qa/playthrough-qa-guide-2026-11-20.md) | The full DS1+DS2 runtime QA playthrough plan (the issue-#18 packet). |
| [`qa-save-suite-2026-11-20.md`](qa/qa-save-suite-2026-11-20.md) | The bug-capture save suite: the SSI 1.1 README regression set and community-bug investigation cards. |
| [`qa-packet-ds1-script-repairs-beta.md`](qa/qa-packet-ds1-script-repairs-beta.md) | Per-site how-to-test packet for the beta script-repair fixes. |

## cookbook/ — tested walkthroughs

Start at [`cookbook/README.md`](cookbook/README.md); five complete
entries from authoring a first darkfix to editing party PCs.

## The repo root

The project-level documents live at the root:
[`spec.md`](../spec.md) (the contract; read before changing
semantics), [`roadmap.md`](../roadmap.md) (phase status, the
single source of planning truth), [`patchnotes.md`](../patchnotes.md)
(per-tool release history, newest first), [`AGENTS.md`](../AGENTS.md)
(guidance for coding agents), and [`CREDITS.md`](../CREDITS.md)
(the per-feature attribution manifest). The per-tool overview lives
in [`../tools/README.md`](../tools/README.md).
