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
| `save-inspect` | 0.9.5 | shipped; DARKRUN SAVE chunk RE continues (semantic differ landed) |
| `image-extract` | 0.4.0 | shipped; GIF/APNG sprite export deferred |
| `region-render` | 0.7.1 | shipped; animated palette + `--annotate` deferred |
| `atlas` | 0.1.1 | shipped |
| `opends` | 0.1.0 | shipped |
| `gpl-asm` | 0.9.0 | shipped; 600/600 round-trip; macros queued |
| `opcode-fuzz` | 0.3.0 | shipped; recipe-driven fuzz + first opcode discovery open |
| `ovr-map` | 0.3.0 | shipped; symbol catalogue, xref tools, Ghidra bridges (5.6.0 complete) |

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
  blocks. The 5.6.0 instruments are built (2026-09-04): the
  import is re-proven and persisted (`scratch/ghidra_project/`),
  the EXE symbol catalogue exists with its first five rows
  (`load_resource` both games, the overlay-manager bodies),
  the census / xref / differ / coverage tools are in place.
  Names: 5 rows of 1,789 entry points. Structure: measured.
  Semantics: started, barely. That gap is Phase 5.6.
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
      (Landed 2026-09-04 as `scripts/propose-exe-symbols.py`;
      the rename also resolves the same-filename-in-two-tools
      collision with gpl-disasm's importer. Three
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
      > and 2026-09-04: every script, including a trivial
      > control, fails with "Failed to get OSGi bundle";
      > cache nuking does not help; manual javac against the
      > pinned JDK compiles our scripts clean. Full evidence
      > and the standing syntax-check recipe in
      > `docs/re-tooling.md`. Until the host layer is
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
      `0128:04a1` to `0128:04ab`, the documented 1.10 loader
      address: the exact fix shape the 5.6.3 census hunts.)
- [x] **GPL↔EXE cross-reference index.** Join `gpl-disasm
      --global-cfg` edges and chunk entry points with
      `ovr-map --callgraph` far-call edges and the resident
      call-site census, so "which EXE code runs this GPL
      chunk" becomes a lookup. This is the missing link that
      makes the ~340-resident-function survey navigable, and
      the substrate the name catalogue grows on.
      (Built 2026-09-04: `scripts/gpl-xref.py`. The join key
      is the loader argument pair: a `66 68 <FOURCC>` push
      with an immediate id push behind it and the far call
      ahead. DS1 215 sites / DS2 209, 77 / 65 carrying
      immediate ids; the `add sp, 0xc` after the call
      confirms the three-argument loader contract. Headline
      finding: there are NO direct `GPL `/`MAS ` pushes in
      either binary; script chunks load through the
      GPLI/GPLX index chunks, so the per-chunk join resolves
      one level. The statically visible boot requests are
      exactly six DS1 (4x `GPLI[1]` from ovr21, 2x `GPLX[1]`
      from ovr22) and four DS2 (`GPLI[1]` from ovr18, two of
      whose loader calls resolve to the catalogued
      `load_resource` 0x692b); other region script loads must
      compute the index id at runtime. JSON index plus
      per-game snapshots under `scratch/gpl-xref/`.)
- [x] **Format coverage report.** Walk every GFF in
      `.games/`, `.games/archive-org/`, and
      `testing_facility/`; tabulate chunks per FOURCC against
      `gff-cat kind --list` and `docs/file-formats.md`.
      Quantifies exactly which chunk kinds are undocumented
      (RNME, VECT, PLYL, ALL, DATA, RGTP, PREF, GREQ at
      minimum) and which containers no tool has ever touched.
      (Done 2026-09-04: `tools/gff-edit/scripts/format-
      coverage.py` walks the corpus TOC-only (stdlib, 12-byte
      indexed entries, the 12-byte segmented trio per
      gff-edit's parse), and the snapshot lives at
      `docs/format-coverage.md`. Measured: 120 GFF containers,
      47 of 68 documented kinds present; gap list DATA (1,292
      chunks), MAP/RNME (60 each), PLYL, ALL, GREQ, VECT,
      CMAT, CPAL, PREF. RGTP does not appear in this corpus.)
- [x] **DARKRUN SAVE semantic differ.** Layer field-level
      hypotheses (region id, party position, quest flags)
      onto `save-inspect save-diff`'s byte diffs, so each
      play-session diff accumulates understanding instead of
      scrollback.
      (Built 2026-09-04: `save-inspect/scripts/save-semantic-
      diff.py` over the new `syms/save-fields.toml`. The TOML
      seeds only what the repo already knew: the verified
      SAVE/5 record layout (stats[6] at 34..39, name at
      40..57) and SAVE/6 blocks from ds1-party-edit, plus the
      README's one-save speculation rows for SAVE/1, /10 and
      /18. Clusters no row covers print as UNKNOWN and are
      the next session's RE target; confirmed findings become
      rows. Smoke: a synthetic stats mutation in SAVE/5
      record 2 annotates as `record 2 field+0x22, combat
      stats[6] [verified]`. Region-id / party-position /
      quest-flag rows wait on the played-save pairs only
      Brandon's play sessions produce.)
- [x] **Hygiene riders.** De-hardcode `/home/bdkl` from the
      five Rust corpus tests (portable root discovery; the
      current silent skips hide coverage loss from CI);
      resolve the duplicate `import-dso-symbols.py` naming
      collision (372-line matcher vs 66-line stub, same
      filename in two tools); give `ds2-patch/` its
      `manifest.toml` + `VERSION` and record the
      promote-vs-copy decision for the applier.
      (Done 2026-09-04. Nine corpus test files carried the
      hardcode, not five; all resolve from `CARGO_MANIFEST_DIR`
      now, with gff-edit's Wine install roots keyed off `$HOME`
      so coverage survives on any clone. Collision resolved by
      the rename to `scripts/propose-exe-symbols.py` (box 1).
      ds2-patch has `VERSION` 0.0.1 and a `manifest.toml`
      carrying the canonical GOG 1.10 `DSUN.EXE` hash and an
      empty fix list; promote-vs-copy for `scripts/darkfix/`
      stays an explicit Phase 7 decision per that README,
      not silently made.)

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
      > Progress 2026-09-04: the reference method is solved
      > and six new anchors are in the catalogues (10 rows
      > total). The naive seg:off pair search finds nothing;
      > strings are referenced as bare 16-bit push/mov
      > immediates relative to DGROUP, read from the entry
      > point's `mov dx, imm16` (DS1 0x4356, DS2 0x47e0).
      > `scripts/xref-string.py` automates it. Verified
      > (self-naming string inside the function):
      > `LoadGameFromDisk` DS1 ovr21+0xdde, DS2 ovr18+0xa6c.
      > Probable (string anchors the module; DSO family
      > naming): `SaveGameToDisk` slot path DS1 ovr13+0x7cc /
      > DS2 ovr11+0x8e5, the region-change module DS1
      > ovr21+0x1487 (two string refs now), and the teleport
      > loader DS1 ovr21+0x17d0; all confirmed entry stubs.
      > Second pass added four more: gpldisk iCtrl validator
      > (DS1 ovr21+0x0, the segment's first entry), MEL/DJ
      > audio init (DS2 ovr11+0x26), and the resident-side
      > version-banner check (DS2 resident 0x1cf85). Third
      > pass: the GPL VM's illegal-opcode handler in the
      > resident image (DS2 0x2660c, referencing
      > 'Illegal Op (gpl=%d)') is the dispatch-table
      > neighbourhood the Decode* study left open for pinning
      > the unknown bytes; plus the OBJEX item-lookup entry
      > (DS2 ovr35+0x2327) and the awaken path (DS1
      > ovr04+0x165). Catalogue: 17 rows. The transfer premise
      > holds across the persistence, status, dispatch and
      > audio layers. Fourth pass closed the threshold:
      > find_path and line_of_sight_check (both DS1 resident),
      > the combat save gate (DS1 ovr25+0x1383, in the
      > dispatcher segment), and the CD-drive check (DS2
      > ovr04+0x85d, two sibling stubs). Catalogue: 21 rows —
      > the anchors box's catalogue condition is met, and the
      > resident-side rows seed the resident-census box.
- [ ] **Name the resident API surface.** The ~340 distinct
      overlay→resident call targets (survey §3.3) are the
      highest-value naming set in either binary; the survey's
      own threshold is "even 100 named functions". The hot
      targets (0x5cc0, 0x5810) are already known.
      > MAJOR 2026-09-04: the DS2 GPL dispatch table is
      > FOUND. The interpreter's per-opcode dispatcher sits
      > at DS2 resident 0xc650 (proven: bounds-check <= 0x80,
      > a per-opcode TRACE HOOK at DGROUP:0x2f6 — call far
      > [0x2f6] — then `shl ax,1; call near [bx+0x30a]`), and
      > the table is at DGROUP:0x30a (file 0x4d30a): 129
      > segment-local code offsets, 115 distinct — matching
      > the DSO Decode* handler count. All 15 unknown bytes
      > share ONE entry (0x20a2, the default): **the DS2
      > engine implements no dedicated handlers for them** —
      > the pinning question dissolves from "which handler is
      > it" to "they are reserved and unimplemented",
      > provable from the table alone; any corpus chunk using
      > one hits the illegal-op path (`syms/ds2.toml`
      > gpl_dispatch). Segment base pinned at probable
      > 0x6500 (paragraph 0x130): it wins the decodability
      > test over 0x320/0x3e0 and, decisively, opcodes
      > 0x01-0x08 map to consecutive 0x14-0x30-byte handlers
      > (the arithmetic family in sequence) with Getxy
      > displaced out-of-band exactly as DSO's independent
      > order places it. Every named opcode now has a
      > candidate DS2 handler address; the full resolved
      > table is generated at `docs/dispatch-table-ds2.md`.
      > DS1 read DONE the same day, cleaner: the table is at
      > DGROUP:0xc0 (file `0x48a20`), the dispatcher at
      > `0x99cb` (`call near [bx+0xc0]`), and the segment
      > base 0x7900 is the UNIQUE survivor of the
      > tiny-vs-large filter, corroborated by the same
      > consecutive arithmetic-family structure and the
      > displaced Getxy. Same headline: all 15 unknown bytes
      > share the default entry (`0x264c` → file `0x9f4c`)
      > in BOTH engines — the GPL VMs never implemented
      > them. Resolved table: `docs/dispatch-table-ds1.md`.
      > Both bases remain probable until a semantic handler
      > read confirms; ByteDec (DS2) already marshals and
      > calls through the far-pointer table at 0xa4d4.

Site-report sketch (elevator, first read 2026-09-04): DS2's
      > `gpl_disk_change_region` (ovr18+0x1132, 826 bytes, 307
      > instructions) is the region-change state machine.
      > Confirmed in the first pass: far-call helpers into
      > segments 0x5f8/0x5b0/0x638, an optional entry hook, a
      > relocation call `0x5b0:0xc0` taking (0, 1, 0, arg),
      > and a region-entry one-shot sweep READ 2026-09-04
      > (supersedes both earlier guesses): `mov si,0x6874;
      > mov di,5` starts a scan of a ~315-record array of
      > 37-byte structs at cs:0x6874, indices 5..319. Per
      > record: call 0x100:0x2 with (1, 0:0, -1, index);
      > field word at +0x16 — if non-negative, negate it
      > (one-shot consumed marking) and use it x9 as an index
      > into a 9-byte-entry DGROUP table at 0x6578; also the
      > record's word at +0x01 << 3 indexes an 8-byte-stride
      > array at [0x67b7] whose byte +5 gets bit 0x40
      > cleared. Reading: on region change, consumed one-shot
      > trigger records are marked and region-entry flag bits
      > cleared. The region id (arg at bp+6) is saved to
      > DGROUP:0x140c. Two fatal exits jump to offset 0x1b0
      > when the 0xfe85/0xf7b1 validation calls return zero. The 'Fatal error: Region
      > change, Invalid save' path is at function offset
      > 0x1b0. Next reads: the 5-entry table contents, the
      > normal successor paths, and the failing elevator
      > caller.
      > Base-status detail: ByteDec at 0x6500 decodes as a
      > coherent marshalling stub (byte-masked argument, far
      > call through the 0xa4d4 pointer table, iret unwind —
      > an unusual VM discipline worth its own read), but the
      > default entry 0x20a2 does not decode cleanly at
      > 0x85a2 under any ±6 alignment: the table's tail may
      > hold a sentinel rather than the default handler.
      > Bases stay probable; settlement route is the trace
      > hook (DGROUP:0x2f6) live in a debugger, or resolving
      > the 0xa4d4 pointer table.
      > 0xa4d4 pointer-table probe result: the table is ALL
      > ZEROS on disk (entries around 0xa4d4 included) — it
      > is runtime-initialized by the VM's setup code, so
      > static resolution of the operation implementations
      > requires finding the init writer (search for stores
      > to 0xa4d4's range) or a runtime trace. Init-writer
      > hunt DONE, with a twist: the store into 0xa4d4 is at
      > 0x6fc6 — INSIDE the handler region, in opcode 0x04's
      > own handler (LongDec, 0x6fc1). The 0xa4d4 slot is not
      > an init-time table; it is a self-managed VM slot the
      > stubs read and write among themselves (ByteDec reads
      > it and calls far through it; LongDec stores it). The
      > handler stubs are the VM's per-opcode implementations,
      > and 0xa4d4 holds per-execution state (likely the
      > current-operation pointer). This strengthens the
      > base-0x6500 reading: the stub region IS the
      > implementation layer. Full interpretation wants the
      > runtime trace.
      > Fatal path read: prints the message (0x5a0:0x34),
      > resets UI/cursor state (0x14d7/0x14d9 = 0, 0x14db =
      > 0x800, 0x14dd = 0x620), calls 0x28:0xb with the
      > region id, then conditionally formats a follow-up
      > message from strings at 0x1787/0x178a.
      > Script family found (2026-09-04, evening): the
      > elevator lives in GPL chunks 76-85 (Blick the
      > elevator operator, Zeegrat, the miners; 'We can't
      > use the elevator until he's found' is the gate) with
      > later references in 268/273/283/284/295. Also: the
      > two fatal-exit validation calls resolved — routine
      > A (0xfb7) re-validates the 37-byte record array
      > (same stride at ds:0x67bc), routine B (0x8e3) builds
      > the string 'SAVE' and checks the save file: the
      > 'Invalid save' fatal is literally a save-validation
      > failure on region change.
      > Transition map (same evening): GPL-81 is the mines'
      > teleport HUB — ~75 `gpl tport` instructions in three
      > shapes: named-region tports `NAME(-N), 255, 99i8,
      > 99i8` (default arrival), same-region coordinate
      > tports `32766, x, y, 0`, and GPL-80's elevator dialog
      > riding `tport GNAME[38], 255, 99, 99`. The freeze
      > hypothesis sharpens: an elevator tport targets a
      > region whose level-load fails; the NAME(-N) packed
      > references are resolvable via dialog-extract's string
      > table, which names the exact destination regions.
      > Prereq discovered: NAME(-N) is a raw halfword index
      > (GPL_IMMED_NAME | 0x80, cval = h * -1 per
      > gpl-disasm's decoder) into the chunk's inline name
      > pool — whose layout is engine-side (the gplshell.c
      > module) and undecoded. RESOLVED 2026-09-05, and the answer kills the pool theory:
      > **NAME(-N) is a negative-encoded OBJEX object id.**
      > Evidence: libgff's GPL_GNAME handling shows GNAMES
      > are 13 runtime object-handle registers (not strings);
      > and OBJEX.GFF's RDFF records span ids up to 32003 —
      > exactly covering the NAME refs (up to -30028). The
      > 'pool' was never a string table: NAME(-5814) is
      > OBJEX object 5814. The tport destinations are
      > likewise object/location ids in OBJEX's id space.
      > The -58xx block decodes as 68-byte entity records
      > whose per-object u16 (402, 951, 958...) are
      > sprite/animation refs into OBJEX's own SCMD (max
      > 3943) / BMP (max 3953) space.
      > RENDERED 2026-09-05: **object 951's sprite is the
      > elevator shaft** — a 25x64 vertical shaft with
      > chevron bracing (scratch/spin-delta/obj951.png,
      > PLNR-encoded, 2 frames). Technique for rendering
      > OBJEX sprites (OBJEX ships palette-less): copy a
      > region GFF that has a PAL, overwrite a
      > bigger-than-target indexed chunk slot in place with
      > the BMP bytes (fits-in-place writer policy), fix the
      > TOC length, then image-extract with
      > --palette-kind/--palette matching the host region.
      > This opens the entire OBJEX object database to
      > visual identification.
      > First batch rendered (obj951-958): 952 = wooden
      > mine door, 957 = debris/ore pile (broken beams and
      > rock — a cave-in), alongside the elevator shaft.
      > The mines' object set is assembling visually: shaft,
      > door, cave-in debris — exactly the pieces the
      > freeze story touches.
      > Pool-location probe: GPL-81's 6,170 bytes are pure
      > bytecode (no local pool), and the remaining candidate
      > is **GPLI-1** (7,896 bytes at file 0x1f8f7f, one per
      > game): binary u16-structured from byte 0 (zero head,
      > then runs of increasing u16 values) — consistent with
      > an index table mapping the NAME halfwords to entries.
      > Its RE is the concrete next unit: assume u16 (or
      > paired-u16) indexing at NAME(-187) = entry 187 and
      > correlate against the 75 GPL-81 tports' expected
      > destinations (mine levels are known from the dialog:
      > 'Tyrgar Mine', levels 1-6, the Underdark door).
      > First test NEGATIVE: plain u16[N] indexing shows no
      > consecutive-region structure at the mine-level
      > indices (74-80 -> 30, 235, 1, 57, 347, 26, 83; the
      > 187/416/526 entries are equally scattered). Next
      > probes, in order: byte-shifted (+1) u16 alignment,
      > 4-byte entries, and the RGN-file region-id space
      > (DS2 has ~60 regions; the mine levels should be a
      > consecutive run wherever they live) as the
      > correlation target instead of raw GPLI values.
      > Probe results: P1 (byte-shifted u16) and P2 (4-byte
      > entries) both negative. P3 measured the region-id
      > space: DS2 ships 20 RGN files with ids {1, 50-63,
      > 65-69} (plus 255 as the same-region tport marker,
      > confirmed by the 32766-prefix tports' operand
      > pattern). NEW: the sweep-record +1 extraction at
      > cs:0x6874 yields garbage words (up to 65532), which
      > means the record base is wrong — either cs:0x6874 is
      > not seg_start+0x6874 (CS-base derivation needs the
      > overlay's real load paragraph) or the di=5..319 loop
      > does not start at record 0. RESOLVED 2026-09-05, differently than expected: the
      > extraction was reading the right address — the array
      > at DGROUP:0x6874 is 11,840 bytes of 100% zeros on
      > disk. It is BSS: runtime game state, populated as the
      > party plays. The record layout (+1 word index, +0x16
      > one-shot field) stands, the 320-record capacity is
      > real (the sweep's di=5..319 with records 0-4
      > permanent), and the structure is at a KNOWN address —
      > a debugger write-watchpoint on
      > DGROUP:0x6874+(n*37)+0x16 will catch every
      > transition-record creation, elevator included. The
      > freeze hunt is now a runtime-capture job (the
      > played-save/debugger loop), not a static dig.
      > Accessor web found (same session): the sibling
      > 8-byte-stride array is reached through a POINTER CELL
      > at DGROUP:0x67b7 (`mov ax,[0x67b7]` = load the
      > array base; the array is dynamically allocated), and
      > SEVENTEEN sites across the binary load that cell:
      > resident engine core (0x27045, 0x27791, 0x277ec,
      > 0x28207, 0x2af34, 0x2c94c), the gpldisk module
      > itself (ovr18 0x709b8, 0x70b66, 0x71099), and
      > overlay code at 0x807xx/0x809xx/0x80axx. The
      > region-entry flag array is shared core state; the
      > gpldisk trio sits inside the save/restore path,
      > consistent with the records being reconstructed from
      > the save at load. The 37-byte record array's only
      > static accessor remains the sweep.
      > COHERENT READING (late session): the records are
      > INDEXED BY REGION ID. The sweep's di=5..319 range is
      > the region-id space (RGN ids 50-69 fit inside; 0-4
      > are reserved/permanent), record N = region N's
      > transition record, and the +1 word is that region's
      > index into the 0x67b7 flag array. Everything in the
      > function now agrees: the per-region sweep, the flag
      > clearing, the save-file persistence, and the
      > 'Invalid save' gate. The mines' records are the
      > entries for whatever ids the upper/lower levels use
      > (two of 50-63/65-69). IDENTIFIED 2026-09-05:
      > the mines are region ids 56/57/58 (RGN038='Mines1',
      > RGN039='Mines2', RGN03A='Mines3' — the region files
      > carry their own name strings). Their transition
      > records sit at computable addresses
      > (DGROUP:0x6874+(id-5)*37), and their scripts are
      > GPL 76-85. MAPPING VERIFIED 2026-09-05: **the MAS
      > chunk id equals the region id** — MAS runs (1),
      > (50-52), (54-63), (65-69), (99) match the region set
      > exactly, and MAS-57 reads as Mines2's trigger-
      > registration surface (look/use triggers on entities
      > NAME(-5801)-(-5817), a boxtrigger at (26,90) 5x2,
      > opening requests). The three mines masters are
      > instruction-identical 1.0 vs 1.10 after GF
      > renumbering (MAS-56: 111 ins, MAS-57: 173, MAS-58:
      > 140), so the freeze is not in the 1.10 delta.
      > MAS-57 inventory (first read): registers Mines2's
      > look/use triggers on entities NAME(-5801)-(-5817)
      > and entity ids 268/287/289, a 5x2 boxtrigger at
      > (26,90), opens with `request 5, NAME(-5835/-5836)`;
      > the tail calls `gpl global sub 228, 27` (cross-
      > script call), spawns entities with `gpl clone
      > NAME(-74)/NAME(-137)`, moves a boxtrigger, and reads
      > `GF+[604]`/`GF+[608]` — the bracket form is a NEW
      > global-addressing mode for the disassembler's
      > documentation. The elevator's usetrigger is among
      > the registered triggers — and it is now NAMED:
      > `gpl usetrigger 3753, 287, NAME(-5807)` is the
      > elevator, because NAME(-5807) = OBJEX object 5807,
      > whose RDFF record's sprite ref (u16 at offset 4) is
      > BMP 951 — the rendered elevator shaft (visually
      > confirmed, scratch/spin-delta/obj951.png). The full
      > -58xx sprite map: 5801=402, 5802=405, 5803=637,
      > 5804=632, 5805=578, 5806=577, 5807=951 (elevator
      > shaft), 5808=952 (mine door), 5809=953, 5810=954,
      > 5811=955, 5812=956, 5813=957 (cave-in debris),
      > 5814=958, 5815=130. The site report's trigger is
      > named; the freeze hunt continues inside the
      > region-change machine it invokes.
      > MACHINE CORE READ (2026-09-05, fn+0x100-0x1b0):
      > after the sweep, the machine (1) marks the OLD
      > region's record consumed (reads the flag array at
      > +6, negates, writes 0xFFFF to [0x67cb] slot), (2)
      > scans the flag array for the next free 8-byte slot,
      > (3) calls 0xaf4 (a validator; on zero, prints
      > 'Error: Unable to close darkrun.gff' from DGROUP
      > 0x1739), (4) calls 0x58:0x4723 twice with (0) and
      > (1) — likely closing and reopening the save files,
      > (5) calls 0xd31 with the region id, then (6) calls
      > 0x5b0:0xc0 again with (1, 0, flags, region) — the
      > RELOCATION call that performs the actual move, whose
      > return value lands in [bp-2]. A failure AFTER the
      > darkrun close/reopen cycle — i.e. inside 0xd31 or
      > 0x5b0:0xc0 with the save files closed — is exactly
      > the shape of a level-load freeze. The elevator's
      > ride runs this same machine.
      > SUSPECTS READ (2026-09-05): (a) 0xd31 is the SAVE-
      > HEADER SNAPSHOT — twelve 32-bit stores of core state
      > (0x1596/0x159a/0x159e = the pointer trio from 0x70b66,
      > plus 0x19d1, and segment-0x2e8 cursor fields) into
      > DGROUP 0x1596-0x15fa, the save-header block; pure
      > copying, cannot hang. (b) 0x5b0:0xc0 is a REAL
      > relocation routine with error returns: it validates
      > (0x5f3:0x12e call), compares the region id against a
      > 14-byte-entry table at DGROUP 0x3eee (region id match
      + > a +1 check — fail = error 0xb via the 0x257 exit),
      > then proceeds to the move. THE SUSPECTS READ (2026-09-05): (a) 0x5f3:0x12e is a trivial
      > helper — a 32-bit pointer-arithmetic subroutine (add
      > + overflow check, retf in 12 bytes), not a validator;
      > its segment 0x5f3 is RESIDENT (file 0xB130). (b) The
      > 14-entry table at DGROUP 0x3eee is BSS zeros —
      > runtime-populated region-transition slots (the
      > relocation validates the region id against entries
      > filled during play). (c) 0xd31 is the save-header
      > snapshot (pure copying). The 0x5b0:0xc0 relocation
      > itself uses DOS int 21h AH=0x4200 (lseek) at its
      > core — file I/O on the save files. FREEZE SHAPE
      > final: the relocation does lseek/read/write on
      > DARKRUN.GFF with the handle state set up by the
      > close/reopen cycle; a hang there is file-I/O on a
      > handle opened against a missing/invalid region —
      > which the played-save pair will show directly (the
      > half-committed DARKRUN bytes at the freeze point).
      > CLOSURE (same session): the ovr18 trio SERIALIZES
      > the flag array into save files — 0x70b66 snapshots
      > three core pointers (0x19c1, 0x67b7, 0x55b8) into
      > DGROUP 0x1596-0x159e (the save header), 0x709b8
      > walks the array's 8-byte entries (+8 per iteration,
      > the save writer), and 0x71099 (inside
      > gpl_disk_change_region itself) walks it
      > post-validation. CONSEQUENCE: the region-entry flags
      > persist in DARKRUN/SAVE0N files, so the
      > played-save pair + save-semantic-diff WILL capture
      > the elevator's flag changes — the runtime-capture
      > instrument is the save diff after all, no debugger
      > required.
- [x] **Decode\* dispatch-order study.** `.dso-online`'s
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
      (Done 2026-09-04, with one premise corrected; full
      write-up in `docs/dso-symbols.md`'s Decode\* section.
      Verified: 111/115 names match libgff case-insensitively
      plus the systematic `*check`/`*trigger` rename for the
      13 trigger handlers; alias facts confirmed from shared
      addresses (`DecodeWend`+`DecodeJump` at 0x3bb55,
      `DecodeNumtoname`+`DecodeNametonum` at 0x3c121);
      `DecodeIfis` sits between Compare and Orelse as the
      0x27 handler. Accounting is exact: every non-default
      libgff byte has exactly one DSO handler name. Corrected:
      the block is NOT opcode-address-ordered (opens
      0x23 0x4b 0x15 0x19; only 56/108 adjacent pairs are
      consecutive), so the unknown bytes CANNOT be pinned by
      elimination; no spare DSO names exist. Next pinning
      route: the DSUN.EXE dispatch table or the DSO client's
      ExecuteGpl jump table.)
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

- [x] **Stand up the census.** A table in or beside
      `docs/known-bugs.md`: per bug, site located / site
      named / root cause / evidence chain. Today every row
      starts at no; the table makes the distance to
      "patchable" visible and is the checklist the site-
      report rule consumes.
      (Live 2026-09-04 at known-bugs.md 3a. First content:
      the headline mines-elevator bug's transition module is
      anchored in BOTH engines — DS2 `ovr18+0x1132` /
      `ovr18+0x146c` catalogued today, confirmed entry
      stubs in the same segment as DS2's
      `LoadGameFromDisk`, mirroring DS1's ovr21 module
      layout — and the save-path rows carry verified named
      anchors. No bug has a root cause yet; that is the gap
      the table tracks.)
- [ ] **Read SSI's own fixes.** Characterize the low-cluster
      diff segments (0, 5, 8, 9, 16, 36)
      instruction-by-instruction against the 1.02 fix list
      (`known-bugs.md` §1). The diffing checkbox above covers
      the tooling; this is the reading, and SSI's fix sites
      are the only ground truth for what an engine-code fix
      looks like in this codebase.
      > READ 2026-09-04, with a strategy-changing verdict:
      > **the low-cluster segments contain no behavioral
      > fixes.** All 183 clusters across segments 0, 5, 8, 9,
      > 16 and 36 were classified by normalized-instruction
      > comparison (decode both sides from their nearest
      > entry stub, compare with immediates normalized):
      > 179 are pure data-address rebiasing — SSI's 1.10
      > recompile shifted DGROUP/scratch structures (e.g.
      > segment 0's `es:0x4034` -> `es:0x40c0`, +0x8c; seg 36
      > is ONE byte changing a `mul` operand), and the
      > surrounding code is byte-identical. The 4 remaining
      > clusters (seg 5 x3, seg 9 x1) are instruction-boundary
      > desyncs at shifted addresses, not edits; seg 16's
      > famous pair is the loader pointer repoint. So the
      > behavioral 1.02 fixes live in the 25 REBUILT segments
      > (the UNVERIFIED-pairing class) — reading them needs
      > function-level pairing via the identical-signature
      > anchor segments, which is exactly what the promoted
      > differ's signature pairing was built for. This
      > retroactively recontextualizes survey 8's 'fix-sized
      > edit' reading of segment 0.
      > REDIRECT 2, same day, the bigger one: the verified
      > EXE pairs contain ZERO semantic changes (all 120
      > differing functions across 24 verified pairs are
      > address rebias; 85 are byte-identical) — consistent
      > with known-bugs §1's own note that the 1.02 fixes
      > are GPL-script-driven. And the GPLDATA.GFF delta
      > proves it: CD 1.0 vs GOG 1.10 GPLDATA is the same
      > size (2,191,945 B, in-place edits) with 2,066,888
      > differing bytes — a re-emitted tail plus a band of
      > small early clusters that are ±1 script-id shifts
      > (`5d 16 8f` -> `5e 16 8f`: local-label renumbering
      > around source edits) and a literal `1.10` version
      > stamp at 0x214182. **SSI's 1.02 fixes are GPL script
      > edits, and the diff against CD 1.0 isolates them.**
      > COMPLETED 2026-09-04 — the full SSI fix delta, all
      > three changed files, mapped with our tools:
      > (1) GPLDATA: all 350 chunk disassemblies diffed;
      > after normalizing global-flag renumbering, ZERO
      > behavioral script changes — the script band +-1
      > shifts are GF-id renumbering from inserted globals.
      > (2) RESOURCE: the fixes ARE here — BMP/CBMP 11001 +
      > 11002 shrank ~30% (fix 8: the volcano overhead maps,
      > redrawn), SPIN spell-text ids 94-114 grew from
      > 8-byte placeholders to real text (fix 12 family),
      > ICON 19115-19121 swapped (spell icons). (3) DSUN.EXE:
      > behavior-free recompile rebias. Verdict: SSI fixed
      > 1.02 via DATA (maps, spell text) — the script logic
      > fixes in the 1.02 list were apparently delivered in
      > the 1.02 build itself (GOG's 1.10 base differs from
      > CD 1.0 only in data + layout), or were engine-side in
      > the rebuilt EXE segments. Either way the delta is
      > now fully characterized, every changed chunk named,
      > and readable with image-extract/gff-cat.
      > READ 2026-09-05 (late session): the 20 SPIN entries
      > are high-level spell names/descriptions 1.0 left as
      > the placeholder "fooey!" — 1.10 filled them with
      > Incendiary Cloud, Charm Person, Mind Blank, Monster
      > Summoning VI/VII, Oteluke's Telekinetic Sphere,
      > Otto's Irresistible Dance, Power Word Blind, Prismatic
      > Wall/Sphere, Serten's Spell Immunity, Crystal Brittle,
      > Level Drain, Meteor Swarm, Mordenkainen's Disjunction,
      > Power Word Kill, Time Stop, Dome of Invulnerability,
      > Magical Plague, Rift. Easter egg: SPIN 103 contains a
      > shipped BUILD COMMAND — "copy c:foo.bat
      > ..\RES\text\BIGBYFST.spn" — SSI's packaging script
      > leaked into the spell-text table. Full extraction in
      > scratch/spin-delta/ (dev-side).
      > Elevator ride routing (same session): GPL-80's
      > GNAME[38] tport is BLICK's exit (noorderstrigger on
      > him, then 'Blick squeezes into the narrow opening'),
      > not the party ride. The party ride is engine-routed:
      > GPL-85 confirms the elevator is unusable until Blick
      > is found ('You're not going to get down to the lower
      > level without his help'), and the ride itself goes
      > through the engine's load-teleport path — the
      > anchored `load_teleport` (DS2 ovr18+0x146c) and the
      > region-change machine (ovr18+0x1132). The freeze
      > therefore happens inside the anchored module for the
      > lower-mine-level load. Site report is one
      > runtime-capture (or lower-level RGN read) from
      > complete.
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

- [x] **Cut the per-tool git tags, or drop the requirement.**
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
      (Decided 2026-09-04: tags are cut, forward-only. First
      two: `ovr-map-v0.3.0` and `save-inspect-v0.9.5` at their
      release commits. Backfilling the 13 tools' older
      releases stays open as an optional one-off; the audit's
      §5.21 ruling is satisfied by forward-only tagging.)
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
