# OpenDS — Roadmap

Phased plan. Each phase has a single shippable artifact; later
phases depend on earlier ones.

**This file is forward-looking.** Rewritten 2026-08-28 from the
2026-07-23 reconciled version. The old roadmap had become a
second changelog: ~85% of it annotated already-shipped work,
duplicating [`patchnotes.md`](patchnotes.md), and it twice failed
to notice whole bodies of work until after they shipped (Phase
4.5, `atlas`). Shipped phases are now condensed to one short
section each: what it delivered, what is still open, where the
detail lives. Per-tool `VERSION` files plus a `patchnotes.md`
entry remain the release record; the previous version of this
file (with all its per-release annotation and correction
history) is in git history.

**Tools come before patches.** Anything that makes the digging
easier is priority over any specific fix. Every digging-tool
ships before the patch that depends on it. The patch phases
(Phase 6 onward) start when the toolkit is sharp enough that
authoring fixes is plumbing, not archaeology.

Each phase ships a deliverable that is useful on its own,
independent of whether later phases happen.

## Where we are (snapshot 2026-09-04)

Phases 0 through 5.5 are shipped. The toolkit reads, writes,
round-trips, renders, and reassembles the games' data, and the
engine binary is segmented and addressable. Revised 2026-09-04
after a four-agent deep-dive of the whole collection (tooling,
binaries, formats, reference clones): the data side is as
described below, but the binary side has zero named functions
and the known-bug list is entirely symptom-level, so Phase 5.6
is expanded from four leverage points into the frontloaded
understanding campaign it should have been.

| Tool | Version | Status |
|---|---|---|
| `verify-install` | 0.3.0 | shipped |
| `gff-edit` | 0.6.0 | shipped; segmented-type builder deferred |
| `repro` | 0.4.0 | shipped; differential capture + bug-save curation open |
| `gpl-disasm` | 0.6.0 | shipped; 100% corpus alignment, CFG, callgraph, symbol catalogues |
| `dialog-extract` | 0.7.1 | shipped; path-aware caller picking queued |
| `save-inspect` | 0.9.4 | shipped; DARKRUN SAVE chunk RE continues |
| `image-extract` | 0.4.0 | shipped; GIF/APNG sprite export deferred |
| `region-render` | 0.7.1 | shipped; animated palette + `--annotate` deferred |
| `atlas` | 0.1.1 | shipped |
| `opends` | 0.1.0 | shipped |
| `gpl-asm` | 0.9.0 | shipped; 600/600 round-trip; macros queued |
| `opcode-fuzz` | 0.3.0 | shipped; recipe-driven fuzz + first opcode discovery open |
| `ovr-map` | 0.2.0 | shipped; `--ghidra` verified headless |

What the digging surface looks like today:

- **Data side is basically solved.** Every GFF in both games
  parses and round-trips; GPL bytecode disassembles at 100%
  corpus alignment and reassembles byte-identically; saves
  decode and edit; regions render (with entity animation and
  GIF output); dialogs extract as browsable trees.
- **The binary side just opened, and is still unnamed.**
  `ovr-map` turns `DSUN.EXE` from a 600 KB blob into 52 / 49
  overlay segments with **935 (DS1) / 854 (DS2)** confirmed
  function entry points, disassembled at correct bases and
  importable into Ghidra as labelled, correctly-based memory
  blocks. Honest caveat from the 2026-09-04 audit: the
  headless import was run once but left no persisted artifact
  (`scratch/ghidra_project/` is empty), and not one of the
  1,789 entry points carries a name. Structure: measured.
  Semantics: not started. That gap is Phase 5.6.
- **The patch pipeline has its first real surface.** Bytecode
  patches author by label-relative address with fingerprint
  checks (`gpl-asm --patch`), and the darkfix package shape
  (manifest, applier, journal, unapply) shipped under
  `ds1-patch/` v0.0.1, proven with a no-op fix (Phase 6,
  checkbox 1). The EXE patch-authoring surface does not exist
  yet; that is Phase 5.7.

Open items from the shipped phases are consolidated in the
[Backlog](#backlog-deferred-items-with-triggers) at the end,
each with the trigger that promotes it into real work.

## Phases 0-5.5 (shipped, condensed)

Detail for every shipped item lives in `patchnotes.md` and each
tool's README. What follows is the one-paragraph record plus
anything still open.

- **Phase 0, documentation + extraction**: docs corpus
  (`file-formats.md`, `known-bugs.md`, `gpl-bytecode.md`,
  `binary-patching.md`, `patch-workflow.md`, `research.md`,
  `install-variants.md`, `dso-symbols.md`, `dsun-exe-re.md`),
  source-hash manifests, `verify-install` v0.3.0.
  Open: the per-tool git tags (see Backlog).
- **Phase 1, `gff-edit`**: pure-Rust GFF read/write, 128/128
  corpus round-trip, bulk extract, text codec, `gff-cat what`
  describer, indexed builder. Open: segmented-type build.
- **Phase 2, `repro`**: DOSBox-Staging harness with overlay-mount
  discipline, smoke fixtures, `--play --session` continuity,
  scheduled keystrokes via ydotool, video capture.
  Open: differential capture; bug-triggering save curation.
- **Phase 3, `gpl-disasm`**: recursive-descent CFG, inter-chunk
  callgraph, curated
  `syms/{opcodes,functions,variables,locals}.toml`, DSO-symbol
  importer producing review-ready rename proposals.
- **Phase 4, exploration tools**: `dialog-extract`,
  `save-inspect`, `image-extract` (+`image-pack`),
  `region-render`, `atlas`.
- **Phase 4.5, human-friendliness sprint**: `opends` umbrella
  CLI, write paths across the toolkit, `atlas`. (This whole
  sprint shipped before the roadmap knew about it; see the
  rewrite note in the header.)
- **Phase 5, `gpl-asm` + `opcode-fuzz`**: 600/600 byte-identical
  round-trip through bytes, JSON, and labelled text; structural
  edit API; author safety net; declarative `--patch` mode with
  label-relative addressing (v0.9.0); chunk-patchwork pipeline
  and DOSBox-driven `run` harness in `opcode-fuzz`.
  Open: recipe-driven fuzz; the phase's done-when (discover at
  least one previously-unknown opcode) is not yet met.
- **Phase 5.5, `ovr-map`**: overlay segment map for both
  binaries; `--disasm`, `--callgraph`, `--verify`,
  `--selftest`, and the `--ghidra` script verified headless
  (52 blocks, 935 labels, dispatcher prologue reads
  correctly). Measured structure: DS1 52 segments / 247 KB /
  93.13% coverage / 935 stubs / 210 direct far-call edges;
  DS2 49 / 252 KB / 93.39% / 854 / 216. The "why this
  matters" section of the previous roadmap named two
  follow-on workstreams; they are now Phases 5.6 and 5.7
  below.

## Can we patch the EXE yet? (assessment, 2026-08-28)

Asked outright: do we understand `DSUN.EXE` well enough to write
a binary patch, or does a fix need a full exploration report
first? The honest split:

**Solved: mechanical safety.** The overlay map is complete and
verified (52 / 49 segments, 935 / 854 entry stubs, ~93%
coverage), any byte is addressable as `ovr:seg+off`, the Ghidra
import is verified headless (caveat, found 2026-09-04: that run
left no persisted artifact; 5.6.0 carries the re-prove-and-
persist box), and the applier layer refuses
fingerprint drift, length changes, and wrong installs. Authoring
a *safe* byte patch is already plumbing.

**Not solved: finding anything.** Almost nothing in the binary
is *named*: zero of the 1,789 entry stubs carry a name, the
curated symbol catalogues hold two entries, and the resident
image (all code before the overlays) has had no systematic
pass at all. The callgraph identifies direct callers for only
~12-14% of stubs and never scans overlay payloads for
far-calls. The official-patch diff is first-measured at
segment granularity (survey §8) but no changed segment has
been read instruction-by-instruction; the DSO symbol transfer
has a working matching precedent on the GPL side and a
do-nothing stub on the EXE side. "Where does the mines
elevator transition live?" is today a dig, not a lookup. That
gap is exactly what Phase 5.6 exists to close.

**Decision: no full-exploration gate.** Requiring a complete EXE
report before any patch attempt is the engine-first trap again
(spec §1a): it defers every fix behind a multi-month research
program, and most target bugs never touch the binary at all.
Instead, exploration is **targeted and per-fix**:

- A data-surface fix (most quest, flag, and dialog bugs) never
  touches the EXE and proceeds now. Phase 6 explicitly prefers
  one for exactly this reason.
- A binary-surface fix requires a written **site report** before
  the patch is authored, added to `docs/dsun-exe-re.md` (or the
  fix's own writeup): the function(s) involved, the evidence
  chain (string xrefs, DSO symbol match, a 1.0-vs-1.10
  official-patch diff hit, or call-shape match), and
  before/after disassembly. The report is the deliverable; the
  patch is its application. No site report, no patch.
- **Amended 2026-09-04, after the collection deep-dive:** the
  Phase 5.6 leverage points are no longer pull-forward-only.
  The deep-dive found zero named functions, an effectively
  empty symbol catalogue, and a known-bug list in which no bug
  has a located site or a root cause; "targeted and per-fix"
  from that baseline means every fix pays the full
  archaeology tax from zero. Phase 5.6 now runs as a
  frontloaded campaign (tooling, naming, formats, bug-site
  census) on its own schedule, and per-fix pulls happen on
  top of it. The no-full-exploration-gate ruling stands in
  this sense: the gate is and stays the per-bug site report,
  not a complete EXE report, and data-surface fixes proceed
  regardless.
- Phase 7 (the mines elevator) is the first plausible
  binary-surface fix. Its site report is the first test of this
  policy; if the evidence chain stalls, the honest fallback is
  another data-surface or deferred bug, not an open-ended dig.

## Phase 5.6 — Name the binary (EXE RE at scale)

**Goal**: turn 935 / 854 confirmed entry points into a *named*
function catalogue per game, so that "where does this bug live
in `DSUN.EXE`" becomes a lookup instead of a dig.

**Ships**: per-game EXE symbol catalogues under
`tools/ovr-map/syms/` (or a sibling), the Ghidra pipeline that
grows them, the investigatory tools in 5.6.0, and docs. The
2026-09-04 deep-dive corrected this phase's original premise:
the labour was not going to be doable with the existing tools
alone (no name store, no working EXE-side symbol matcher, no
GPL↔EXE cross-reference, no diff annotator), so the
instruments ship first.

> Progress 2026-08-28: the whole-binary structure survey
> ([`docs/dsun-exe-survey.md`](docs/dsun-exe-survey.md)) shipped.
> Headline: the overlay code calls only ~340 distinct resident
> functions (4,865 / 5,067 direct far-call sites, census in
> survey §3.3), the overlay manager body is located
> (`0x466e0` / `0x4aff0`), and the DSO name list has a concrete
> matching order: resident targets first, overlays second. The
> official-patch diffing leverage point below is updated: it is
> blocked without a CD 1.0 base.

> Expanded 2026-09-04 (the ground-truth frontload): a
> four-agent deep-dive of the whole collection (tooling,
> binaries, formats, reference clones) returned a simple
> scorecard. Measured and solid: the overlay container, the
> segmentation, the resident/overlay split, and the
> official-patch delta. Empty: names (0 / 1,789 entry stubs),
> opcode runtime semantics (no opcode's effect ever observed;
> ~40 of 129 catalogue rows are Custom), SAVE chunk meanings
> beyond SAVE/5-/6 (validated on a single played save), and
> bug sites (no known bug has a located site or root cause).
> The reference clones materially help: the DSO `Decode*`
> handler block is address-ordered and agrees with ~114/115
> of libgff's independently-derived opcode names, so the
> unknown opcodes are pinnable by elimination. The items
> below turn that scorecard into work: tooling first, then
> naming, then formats, then the bug-site census. Phase 5.7
> and Phase 6 start from what this phase produces.

Four original leverage points, in order of cost:

- [ ] **Ghidra headless workflow written down and run.** The
      `ovr-map --ghidra` script lands segments and entry-stub
      labels. What is missing is the working session recipe:
      a headless `analyzeHeadless` invocation (the binary
      ships with Ghidra at
      `~/.local/share/ghidra_12.1.2_PUBLIC/`; it is not on
      `$PATH`, which is fine), a script skeleton for bulk
      renaming from a TOML catalogue, and an export path back
      to text (decompiler listing or disassembly) checked
      into `docs/` as findings. Keep the Phase 5.5 caveat:
      the decompiler is weak on 16-bit segmented code; the
      deliverable is *navigable, correctly segmented, and
      named*, not *clean C*.
- [ ] **DSO symbol transfer.** `docs/dso-symbols.md`
      documents the 3,530-function Watcom symbol table from
      Dark Sun Online (which inherited the WotR codebase).
      The offsets do not map directly onto our binaries; the
      work is byte-pattern and call-shape matching, seeded by
      the `ovr-map --callgraph` edges and the `gpl-disasm`
      `import-dso-symbols.py` precedent (which already does
      this class of matching for GPL symbols). Produce
      review-ready proposals, curated by hand into the
      catalogue; never auto-committed, matching the existing
      curation rule.
- [ ] **Official-patch diffing.** ✅ **Unblocked and first-measured
      2026-08-28.** The CD 1.0 base exists and is hash-confirmed:
      `install-variants.md` §3 records `game.gog` carrying the
      1.0 CD tree (`DSUN.EXE = e73f79c3...`), and an
      independently sourced public CD-tree zip hash-matches that
      record exactly; the tree is staged dev-side at
      `.games/archive-org/cd10-extracted/`. The CD 1.0 vs GOG
      1.10 segment diff is the official fix delta: 5 segments
      byte-identical, 44 changed, 117,566 differing bytes, with
      fix-sized localized clusters in segments 0, 5, 8, 9, 16
      and 36. Measured evidence and reading in
      [`../docs/dsun-exe-survey.md`](docs/dsun-exe-survey.md) §8.
      Remaining: characterize the low-cluster segments
      instruction-by-instruction against the 1.02 fix list
      (`known-bugs.md` §1); cross-ref with the DSO symbol
      matches. (The floppy 1.0 line is a different product
      build and stays useless as a diff base; an earlier
      same-day note calling this item blocked was wrong and is
      corrected in the survey.)
- [ ] **First named consumers.** The catalogue is real when
      something else uses it: at minimum, the VGA
      colour-cycling routine (`VGAColorCycle` /
      `gCycleColor` candidates already located via the DSO
      table) decoded far enough to unblock `region-render`'s
      animated palette backlog item, and one known-bug site
      located by name as input to Phase 6 or 7.

### 5.6.0 — Investigatory tooling (build the instruments first)

- [x] **Land the in-flight ovr-map scripts.** Commit
      `tools/ovr-map/scripts/diff-official.py`, and replace
      the `import-dso-symbols.py` stub (it parses the DSO
      table and emits literal `*TBD*` columns for six
      hardcoded names; it performs no matching, and carries a
      dead statement where its argument group is immediately
      overwritten) with a real proposal generator modelled on
      the `gpl-disasm` importer. Gitignore or scratch-park
      the generated `OvrMap.java`.
      (Landed 2026-09-04 as `scripts/propose-exe-symbols.py`
      — the rename also resolves the same-filename-in-two-
      tools collision with gpl-disasm's importer. Three
      honest modes: `--census` (exact seg:off resident-target
      worklist with 55 8B EC evidence marks), `--strings`
      (source-file anchors; finds `gpldisk.c` at 0x49d3d and
      reproduces the corrected DSO prefix census: Save 12,
      Combat 6, Region 0), `--anchors` (renders curated rows
      into catalogue format). Finding: survey 3.3's "345
      targets" keyed targets by segment base, dropping the
      call offset; the exact census measures 746/760
      candidate targets (36/35 prologue-confirmed), and
      overlay far-call segment words predate the manager's
      relocation pass, so targets stay candidates until
      corroborated.)
- [x] **EXE symbol catalogue format and store.** A
      `tools/ovr-map/syms/<game>.toml` schema (name, segment,
      offset, evidence, confidence) plus loader support so
      `ovr-map --disasm` and `--callgraph` render names.
      Today there is nowhere to put a discovered name; every
      finding lives in prose.
      (Shipped 2026-09-04: schema + curation rule in the
      catalogue headers, `--syms` loader with loud validation,
      names in `--verify` / `--disasm` / `--callgraph`,
      selftest bound-checks rows; seeded with `load_resource`
      both games and the two overlay-manager bodies.)
- [ ] **Ghidra pipeline made real and persisted.** Re-run the
      headless import and keep the project plus exported
      function lists under `scratch/` (gitignored), with the
      `analyzeHeadless` recipe checked into `docs/`; add the
      bulk-rename-from-catalogue script (the rename half of
      this phase). The 2026-08-28 "verified headless" claim
      left no artifact; re-prove it once, then keep the
      proof.
      > Progress 2026-09-04: the recipe is now real and
      > corrected (the old one could not have run from this
      > checkout: Ghidra resolves bare script names against
      > $PWD and rejects every path element starting with
      > '.', which .gitrepos is). The bulk-rename half landed:
      > `ovr-map --ghidra-rename` generates the catalogue-
      > driven rename script from `syms/<game>.toml`, and
      > `tools/ovr-map/ghidra/OvrExport.java` is the checked-
      > in TSV export path. Import + analysis + persistence
      > re-proven: the analyzed DS1 project is kept under
      > `scratch/ghidra_project/ds1_proj.rep`. Still blocked,
      > host-side: Ghidra's OSGi script compiler broke on this
      > machine between 2026-08-29 (last successful compile)
      > and 2026-09-04 — every script, including a trivial
      > control, fails with "Failed to get OSGi bundle";
      > cache nuking does not help; manual javac against the
      > pinned JDK compiles our scripts clean. Full evidence
      > and the standing syntax-check recipe in
      > `docs/dsun-exe-re.md` 7. Until the host layer is
      > fixed, `propose-exe-symbols.py --census` stands in
      > for the Ghidra-side function list.
- [x] **Cluster-annotated official-patch differ.** Promote
      `diff-official.py` to a real tool: per-cluster file
      offsets, nearest entry stub, before/after `ndisasm`
      excerpts, and signature-checked segment pairing (the
      current index pairing silently misaligns if a segment
      was ever inserted). DS1 stays out of scope: no 1.0 base
      exists to diff against.
      (Promoted 2026-09-04. Signature pairing = size + entry-
      offset sequence: 19 of the 44 changed segments pair
      verified, 25 fall to flagged UNVERIFIED index pairing.
      First read: segment 16's two 1-byte clusters are SSI
      repointing an overlaid `load_resource` far-call from
      `0128:04a1` to `0128:04ab` — the documented 1.10 loader
      address — the exact fix shape the 5.6.3 census hunts.)
- [ ] **GPL↔EXE cross-reference index.** Join `gpl-disasm
      --global-cfg` edges and chunk entry points with
      `ovr-map --callgraph` far-call edges and the resident
      call-site census, so "which EXE code runs this GPL
      chunk" becomes a lookup. This is the missing link that
      makes the ~340-resident-function survey navigable, and
      the substrate the name catalogue grows on.
- [ ] **Format coverage report.** Walk every GFF in
      `.games/`, `.games/archive-org/`, and
      `testing_facility/`; tabulate chunks per FOURCC against
      `gff-cat kind --list` and `docs/file-formats.md`.
      Quantifies exactly which chunk kinds are undocumented
      (RNME, VECT, PLYL, ALL, DATA, RGTP, PREF, GREQ at
      minimum) and which containers no tool has ever touched.
- [ ] **DARKRUN SAVE semantic differ.** Layer field-level
      hypotheses (region id, party position, quest flags)
      onto `save-inspect save-diff`'s byte diffs, so each
      play-session diff accumulates understanding instead of
      scrollback.
- [ ] **Hygiene riders.** De-hardcode `/home/bdkl` from the
      five Rust corpus tests (portable root discovery; the
      current silent skips hide coverage loss from CI);
      resolve the duplicate `import-dso-symbols.py` naming
      collision (372-line matcher vs 66-line stub, same
      filename in two tools); give `ds2-patch/` its
      `manifest.toml` + `VERSION` and record the
      promote-vs-copy decision for the applier.

### 5.6.1 — The naming campaign

- [ ] **Verify the first DSO→DS2 address anchors** by the
      string-xref method `docs/dso-symbols.md` itself
      prescribes (about 20 verified rows before emitting a
      catalogue). This validates or kills the transfer
      premise before any scale matching; the honest fallback
      is behavioural naming without DSO names. Note the
      offsets are DSO-v1.0-client-relative (flat offsets into
      the extracted 32-bit image); only the names are claimed
      to transfer.
- [ ] **Name the resident API surface.** The ~340 distinct
      overlay→resident call targets (survey §3.3) are the
      highest-value naming set in either binary; the survey's
      own threshold is "even 100 named functions". The hot
      targets (0x5cc0, 0x5810) are already known.
- [ ] **Decode\* dispatch-order study.** `.dso-online`'s
      symbols.txt names 115 `Decode*` GPL handlers in a
      contiguous, address-ordered block, and ~114/115 agree
      with libgff's independently derived opcode names. Sort
      the block, align it against the 129-opcode table, and
      pin the unknown bytes (0x53, 0x55-0x57, 0x60, 0x71-0x75)
      by elimination; record the `DecodeIfis` (an 0x27
      semantics hint), `DecodeWend == DecodeJump`, and
      `DecodeNumtoname == DecodeNametonum` alias facts. Names
      and addresses are facts (cite the AGPL table); no code
      moves.
- [ ] **Locate the engine subsystems.** Combat, party, map,
      inventory, and the save path, via string anchors plus
      the callgraph. The DS1 save-string cluster at
      0x49d3d-0x49e92 is the seeded start; the DSO table
      names the persistence family outright
      (`SaveGameToDisk`/`LoadGameFromDisk` and kin).
- [ ] **Read the overlay manager and the dispatchers.** The
      manager bodies (0x466e0 / 0x4aff0) bound how many
      segments stay resident (directly relevant to the
      elevator race); the indirect-call dispatcher segments
      (DS1 25; DS2 21/35/42) hold the concentrated `FF /2`
      sites whose resolution turns them into ordinary
      callgraph edges.
- [ ] **Locate per-segment relocation tables; reconcile the
      FBOV segnum.** The descriptors imply relocations the
      survey has not found; reloc-safe EXE patching (Phase
      5.7) needs them. Reconcile FBOV's segnum field (220 /
      229) against the parsed descriptor records (58 / 49):
      either a second segment class exists or a field is
      misread.

### 5.6.2 — Formats and saves

- [ ] **Decode SAVE/1** (the ~10 KB probable master state
      table) against libgff's object/region structs, seeded
      by the `gpldisk.c` string anchors and the DSO
      Save*/Load* names.
- [ ] **Chunk-map played saves** via the `save-diff` loop
      (snapshot, one in-game action, snapshot) for each SAVE
      id family, converting the speculation rows in
      `save-inspect`'s README into per-id semantics. Needs
      play sessions (Brandon's).
- [ ] **Settle save compression.** Locate the
      `Failed Uncompress in Loadgamefromdisk` caller. Today
      every on-disk save parses as a plain GFF and the survey
      string says compression exists somewhere; which is
      true under all engine paths decides whether save
      diffing can be trusted.
- [ ] **Run the opcode-fuzz recipe loop to first discovery.**
      Phase 5's done-when (discover one previously-unknown
      opcode) is still open; settle the recipe format and
      meet it. The Decode\* study above narrows the
      candidates first.
- [ ] **Adopt the reference catalogues into the docs.**
      libgff's `gfftypes.h` defines 83 chunk types against
      our catalogue's gaps (BVOC/FVOC/OMAP/POBJ/SJMP/FNFO/
      RDAT/CACT/STXT at minimum); correct the free-list prose
      (all 61 measured files carry `toc_length − 2` plus a
      2-byte count, not an empty list at `toc_length`; a
      writer following the current prose produces malformed
      files); pin `file_flags` (8 on all DS2 regions and both
      CHARSAVEs) and the `data0` ordinals; fix
      `dso-symbols.md`'s prefix census (Save\* 12 not 24,
      Combat\* 6 not 11, Region\* 0 not 4, among others); and
      record the upstream-projects.md license drift
      (libsoloscuro ships no LICENSE file).

### 5.6.3 — The bug-site census

- [ ] **Stand up the census.** A table in or beside
      `docs/known-bugs.md`: per bug, site located / site
      named / root cause / evidence chain. Today every row
      starts at no; the table makes the distance to
      "patchable" visible and is the checklist the site-
      report rule consumes.
- [ ] **Read SSI's own fixes.** Characterize the low-cluster
      diff segments (0, 5, 8, 9, 16, 36)
      instruction-by-instruction against the 1.02 fix list
      (`known-bugs.md` §1). The diffing checkbox above covers
      the tooling; this is the reading, and SSI's fix sites
      are the only ground truth for what an engine-code fix
      looks like in this codebase.
- [ ] **Locate the mines-elevator transition.** The
      region-transition state machine (GPL side, EXE side, or
      both) is Phase 7's site report; the investigation lives
      here so Phase 7 starts from a site instead of a dig.
      The DSO candidates (`GplChangeRegion`, `GplTileCheck`,
      `GplDoorCheck`) and the official-patch diff are the
      first two levers.

**Done when**: a reader can ask "what is at `ovr:NN+0x...`"
and get a name with evidence for a meaningful fraction of the
catalogue (target: the ~200 most-called functions); at least
one downstream item (animated palette, or a Phase 6/7 site)
cites it; the coverage report and the census table exist and
are being consumed; and the first Phase 6/7 target bug has a
complete site report produced by this phase rather than
scrounged at fix time.

## Phase 5.7 — EXE patch authoring surface

**Goal**: give `DSUN.EXE` byte patches exactly what `gpl-asm`
v0.9.0 gave bytecode patches: authored by name, fingerprint-
checked, verified before it ships.

**Ships**: named addressing and a verify gate for EXE patches,
in whatever tool owns the job (decide: extend `gpl-asm
--patch` with a second target kind, or a sibling `exe-patch`;
decide by whether the TOML schema can stay shared).

Ordering note (2026-09-04): the authoring tooling below may be
built in parallel with Phase 5.6's tooling half, but an
EXE-surface fix needs both halves of that phase: the catalogue
(for symbol-relative addressing) and the target bug's site
report (5.6.3). Data-surface fixes do not wait on either.

- [ ] `at = "ovr:19+0x17a7"` addressing, resolved against the
      `ovr-map` segment map (file offset, segment-local
      offset, payload bounds). Symbol-relative addressing
      (`at = "<exe-symbol> + N"`) once Phase 5.6's catalogue
      exists; refuse non-block-leader bases, matching the
      bytecode resolver's rule.
- [ ] `bytes_old` fingerprint mandatory, as on the bytecode
      side; refuse to apply on mismatch.
- [ ] A `--verify` pass that fails a site which: drifts from
      its fingerprint, straddles a segment boundary, or lands
      in the ~7% inter-segment padding. Today nothing notices
      any of these.
- [ ] **In-place-only rule made enforceable and explained.**
      Every overlay descriptor stores its payload offset as
      an absolute position; one inserted byte anywhere before
      the last segment shifts every following payload and the
      game loads garbage as code. State this in `spec.md` §4
      in those terms (the previous roadmap's own suggestion,
      still undone), and have `--verify` reject any script
      that changes file length.
- [ ] Assembler for replacement bytes: `keystone-engine` is
      already named in `docs/build-environment.md` §2 for
      exactly this (16-bit x86). Confirm it assembles
      `arch=i386, mode=16` correctly against `ndisasm -b 16`
      round-trips before relying on it; `pwn asm` at
      `arch='i386', bits=16` is the documented fallback. The
      stdlib-only Python rule already has a pre-approved
      exception class for the applier (per
      `build-environment.md`, alongside `bsdiff4`); this fits
      it.
- [ ] Round-trip proof: a no-op EXE patch script applies and
      unapplies byte-identically; a deliberately wrong site
      (off-by-one into padding) is rejected by `--verify`.

**Done when**: Phase 6+ can author a two-byte EXE fix by
symbol name and `--verify` is the last gate before packaging.
This is the same soft-blocker shape as `gpl-asm` v0.9.0 was
for bytecode: not a hard blocker for a data-only first fix,
and must not hold one.

## Phase 6 — First DS1 fix shipped (pipeline proof)

**Goal**: prove the patch pipeline end-to-end on the smallest
possible DS1 bug. By this point the toolkit is sharp enough that
authoring should feel like routine work.

**Ships**: `darkfix-ds1-v0.1.0`.

- [x] Darkfix distribution format per `spec.md` §4:
      `manifest.toml` schema (target hashes, fix list, on/off
      state), `apply.py` applier (verify install hashes against
      the manifest, back up to `darkfix-backup/`, apply each
      enabled fix, write `darkfix-applied.json`), and `apply.py
      --unapply` restore. Proven with the `fix.ds1.noop` fix:
      applies and unapplies byte-identically against a copy of
      the real `DSUN.EXE`; wrong-fingerprint and tampered-target
      refusals covered by `apply.py --selftest` (2026-08-28).
- [ ] **Applier runs on the player platform.** The audience is
      Windows-first. Test `apply.py` under Wine and, ideally,
      real Windows Python before calling the package shape
      proven; a fix that only applies on Fedora is not a fix.
      Decide the dependency stance in the same breath: pure
      stdlib (preferred, matches spec §7a) versus the
      `bsdiff4`/`keystone` venv `build-environment.md`
      sketches.
- [ ] Pick one trivial DS1 bug (identified during Phase 2 repro
      work). Prefer a GPL-data fix if one is available: it
      exercises `gpl-asm --patch` + `gff-edit` and defers the
      EXE surface until Phase 5.7 exists. Prefer, second, a
      bug whose site the Phase 5.6.3 census has already
      characterized, so the fix proves the pipeline instead
      of paying the archaeology tax.
- [ ] Repro fixture for the chosen bug
      (`tools/repro/bugs/<id>/bug.toml`) so the fix is
      verifiable. Requires ydotool installed locally; repro
      v0.4.0 already integrates the input automation.
- [ ] **Differential capture** (promoted from the repro
      backlog, because it is the fix's proof): a
      run-with-patch and run-without-patch side-by-side
      helper, emitting both videos plus a structured
      pass/fail delta.
- [ ] Author the fix using `gpl-disasm` + `gff-edit` (plus the
      Phase 5.7 surface if it turns out to be an EXE fix).
- [ ] Author the test (hash before/after, in-game repro via
      `tools/repro/`).
- [ ] Tag `darkfix-ds1-v0.1.0`, push GitHub release.
- [ ] Player-facing README explaining install.
- [ ] Cookbook entry: `docs/cookbook/author-first-darkfix.md`,
      the workflow written down while it's fresh.

**Done when**: a stranger could download the v0.1 zip, run
`apply.py`, launch DS1 in DOSBox, and the bug is gone.

## Phase 7 — DS2 mines elevator (the headline)

**Goal**: fix the most famous DS2 bug, the one that broke the
late game in 1994 and has never been fixed.

**Ships**: `darkfix-ds2-v0.1.0`.

- [ ] DS2 active-party edit surface, verified end-to-end:
      confirm in a loaded game that CHARSAVE edits via
      `save-inspect` cover the DS2 active party (the v0.6.0
      finding says DS2 CHARSAVE *is* the active party, but
      this has only been exercised via `repro.py --play`
      session saves, never a live install). If DS2 turns out
      to have a DARKRUN-side layout like DS1's SAVE/5-/6,
      RE it and build the sibling tooling. Cookbook entry
      mirroring `edit-ds1-party.md` either way; darkfix-ds2
      authoring needs this fluency.
- [ ] Reproduce in DOSBox via `tools/repro/`.
- [ ] Locate the GPL function or DSUN.EXE routine controlling
      the elevator transition. New leverage since this phase
      was written: Phase 5.6's official-patch diff may show
      whether SSI themselves touched the transition code
      between 1.0 and 1.10, and the DSO symbol table likely
      names the region-transition functions outright (DSO
      inherited the whole WotR codebase). Use both before
      hand-digging.
- [ ] Diagnose the race / state bug.
- [ ] Author the fix (data or binary, whichever it lives in).
- [ ] Verify a full DS2 playthrough does not reproduce the
      original behavior.

**Done when**: a player who hits the elevator gets to the next
region, with a full party, on a clean install with the patch
applied.

## Phase 8 — DS2 sweep

**Goal**: every bug in [`docs/known-bugs.md`](docs/known-bugs.md)
section 2 (community-reported, post-1.10) has either a fix or an
explicit "won't fix" note with rationale.

**Ships**: `darkfix-ds2-v0.5.0`.

- [ ] Charged-weapon disappearance.
- [ ] Doorway / item graphics layering.
- [ ] Save/exit bug.
- [ ] Audio static (verify no-op for OPL/MT-32 emulation paths).
- [ ] MEL DSP detect (verify no-op for DOSBox).

## Phase 9 — DS1 sweep

**Goal**: same as Phase 8, for DS1's known issues.

**Ships**: `darkfix-ds1-v0.5.0`.

- [ ] Compile a more thorough DS1 bug list (DS1 is less
      documented; we will find issues during this phase).
- [ ] Fix each.

## Phase 10 — v1.0 for both games

**Goal**: the patches reach a state where they can be
recommended to fellow Dark Sun players in good conscience.

**Ships**: `darkfix-ds1-v1.0.0` and `darkfix-ds2-v1.0.0`.

- [ ] Full playthrough of DS1 with the patch on; no workaround
      needed.
- [ ] Full playthrough of DS2 with the patch on; no workaround
      needed.
- [ ] Player-facing documentation: how to install, how to
      verify, how to report a bug.
- [ ] Public announcement.

## Phase 11+ — Engine plausibility (deferred)

If the toolkit accumulates enough, `gpl-disasm` with most
opcodes documented, working `gpl-asm`, native GFF read/write,
region viewer, save inspector, then **OpenDS the engine**
becomes plumbing rather than reverse-engineering. At that
point spinning it up makes sense.

We do not commit to a date. We commit to building the toolkit
that makes it possible. If someone else picks up the toolkit
and ships an engine first, that is a successful outcome.

## Backlog (deferred items with triggers)

Everything still open from the shipped phases, each with the
condition that promotes it into scheduled work. Nothing here is
abandoned; nothing here is scheduled.

- [ ] **Cut the per-tool git tags, or drop the requirement.**
      `docs/versioning.md` says each release ships a
      `<tool>-vX.Y.Z` tag; `git tag` returns nothing, so no
      release has ever complied. Two honest resolutions:
      backfill tags against the commits that bumped each
      `VERSION` (a one-off script walking `git log -- VERSION`
      makes this mechanical), or amend `docs/versioning.md` to
      name `VERSION` + `patchnotes.md` as the whole release
      record and drop tags. Open since the 2026-07-23
      reconciliation sweep. **Decide before the first darkfix
      release**, so patches do not inherit the ambiguity.
- [ ] **`gff-edit` segmented-type build.** Builder covers
      indexed GFFs only; the secondary-table + `GFFI`
      cross-reference dance is unwritten. Promote when a
      downstream consumer needs to *construct* a segmented
      GFF from scratch (reading and replacing already work).
- [ ] **`repro` bug-triggering save curation.** Per-bug saves
      placed just before the trigger, indexed by bug ID.
      Ongoing alongside every fix; promote to a focused push
      when Phase 6 picks its first bug (it needs one).
- [ ] **`image-extract` animated sprite export (GIF / APNG).**
      The still half shipped in v0.3.0 (`--frames-all`,
      `--spritesheet`). Needs an encoder decision first: no
      in-tree GIF/APNG writer, and a new dep needs sign-off
      per spec §7a. Note `region-render` v0.7.0 already
      shells to ffmpeg for `--gif`; the same trick applies
      here and probably settles the question.
- [ ] **`region-render` animated palette colours.** VGA
      colour cycling; blocked on EXE RE of the cycle-table
      layout. Phase 5.6 is the unblocker; candidates
      (`VGAColorCycle`, `gCycleColor`) are already named in
      the DSO symbol table.
- [ ] **`region-render --annotate`.** Entity-name overlays on
      rendered maps; deferred for lack of an in-tree font
      without a new dep. Promote when atlas or a modder
      workflow wants labelled maps badly enough to revisit
      (SVG output or a tiny embedded bitmap font are the
      escape hatches).
- [ ] **`dialog-extract` path-aware caller picking.** For the
      32 LSTR reads resolved via `possible_writers` arrays:
      CFG-distance ordering or symbolic trace instead of the
      current narrowing. Queued since v0.5.0; promote when an
      unresolved dialog actually misleads someone.
- [ ] **`gpl-asm` parameterised macros and `@include`.**
      Queued since v0.6.0. Promote when a darkfix script
      gets repetitive enough to want them; the `--patch` TOML
      mode may obsolete the need instead. Re-evaluate at
      Phase 6.
- [ ] **`opcode-fuzz` recipe format decision + recipe-driven
      fuzz.** The harness runs a swapped chunk through DOSBox
      and diffs `DARKRUN.GFF`; what is missing is the settled
      recipe format (short-form mnemonics vs JSON vs gpl-asm
      extension) and the loop that walks candidate opcodes.
      Phase 5's done-when (discover at least one
      previously-unknown opcode, add it to
      `docs/gpl-opcodes.md`) is still open; keep this phase
      alive until it is met or explicitly closed.
- [ ] **`save-inspect` DARKRUN SAVE chunk RE.** SAVE/1 (the
      ~10 KB probable master per-region state table),
      SAVE/2-/4, /7-/9, the u16 scalar family at ids 10..17,
      the 51-byte SAVE/18 boolean array. Bootstrap with the
      v0.7.0 `save-diff` harness: snapshot, one in-game
      action, snapshot, diff. Quest and world-state fixes
      need this; promote when the first such fix is chosen.
- [ ] **`extract.sh`.** From-installer extraction wrapper.
      Deferred; `innoextract` is one command and
      `verify-install --repair` already shells out. Reinstate
      only if a contributor needs it.
- [ ] **Python test harness decision.** The repo has none;
      Python tools gate on ruff + `compileall` in CI and ship
      `--selftest` flags (`ovr-map`). Options: keep the flag
      idiom, or standardise on stdlib `unittest` discovery in
      CI. Decide the next time a third Python tool grows a
      selftest.

## Tooling inventory and gaps

Checked on the dev host 2026-08-28. **Everything the docs cite
is installed.** Nothing blocks any phase.

| Tool | Status | Used by |
|---|---|---|
| Ghidra 12.1.2 | installed (`~/.local/share/ghidra_12.1.2_PUBLIC/`; `analyzeHeadless` not on `$PATH`, invoke by full path) | Phase 5.6; `ovr-map --ghidra` |
| radare2 5.9.8 (incl. `radiff2`, `rabin2`, `rahash2`) | installed | Phase 5.6 official-patch diffing; `dsun-exe-re.md` §6 |
| `ndisasm` / `nasm` | installed | `ovr-map --disasm`; patch byte authoring |
| DOSBox-Staging 0.82.2 (as `dosbox`) | installed | `repro`, `opcode-fuzz` |
| `ffmpeg` | installed | `repro` video capture; `region-render --gif` |
| `innoextract` | installed | `verify-install --repair` |
| `ydotool` | installed | `repro` keystroke automation |
| `wine` | installed | Phase 6 applier testing |
| `pwndbg` | installed; **not for this project** (gdb plugin for live Linux ELF; these binaries run under DOSBox) | nothing |

Optional, only if a phase asks for it:

- **DOSBox-X**: a second emulator with a deeper built-in
  debugger (instruction tracing, more breakpoint/logging
  surface than Staging's). `opcode-fuzz` and hard-to-catch
  races are the plausible consumers. Staging's debugger plus
  the `DARKRUN.GFF` diff loop has sufficed so far; install
  when the first bug defeats both.
- **`keystone-engine` + `bsdiff4`** in the applier venv:
  already named in `docs/build-environment.md` §2 as the
  pre-approved Python non-stdlib exceptions. Install them
  when Phase 5.7 / Phase 6 begin, not before; no tool under
  `tools/` depends on them today.

Not needed, for the record: LE/LX Ghidra loaders (the DOS/4GW
model was disproved, `dsun-exe-re.md` §1), decompilers beyond
Ghidra (16-bit real-mode support elsewhere is worse), and any
Windows-cross toolchain (patches are data + Python, not
compiled code).
