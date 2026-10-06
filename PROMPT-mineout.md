# PROMPT: mine-out — the prompt for finishing the games' mining

Read this whole file before doing anything. It is the mission, the
completion bar, the open work, and the rules. Today (2026-09-21) the
pits-parity session closed the last known UI-adjacent holes (HEAD
51e9e35, committed AND pushed). What remains is the full static
mining of DS1 and DS2: every chunk kind, every audio asset, every
named RE hole, documented in docs/ until there is nothing left to
dig. Expect this to take several sessions. This prompt is written to
be re-read at the start of each one.

## 0. Session rules (Brandon's, non-negotiable)

- ALL progress notes and summaries in ENGLISH. He reads everything.
- Subagents: max 4 concurrent, research/read-only, no nesting. GLM-5.3
  for RE and judgment, GLM-5.3-Flash for breadth sweeps. Say "do not
  spawn subagents" in every prompt. The MAIN THREAD writes all docs,
  code, and commits; subagents only gather and report.
- Never push. Commits are local. Commit per work item, informative
  messages, no em-dashes. Shared-tree trap: check `git log
  --oneline -5` before AND after every commit.
- Python tools are stdlib-only. Ruff pin 0.15.20 (`uvx
  ruff@0.15.20`) for anything in the CI gate.
- `.games/` and the wine installs are READ-ONLY forever. Extraction
  output goes to `port-spike/generated/` (gitignored) or /tmp;
  never into `.games/`, never committed as binaries.
- Reference checkouts are read-only research material:
  `.dsun_music/`, `.dsoageofheroes/`, `.dso-online/`. Porting logic
  from them requires a code citation AND a CREDITS.md row.
  Do not vendor their code.
- If a dig needs the DOSBox rig for verification, the AUTOTYPE
  hands-off pattern is the only input channel (recipe committed in
  port-spike/live-capture/; padded schedule proven 2026-09-21).
- No new third-party deps without asking. Host tools (Ghidra, r2,
  ffmpeg, fluidsynth if present) may be USED but are never repo
  dependencies.

## 1. The mission and the completion bar

"Mined out" is mechanical, not vibes. The loop is:

1. Regenerate the coverage report:
   `python3 tools/gff-edit/scripts/format-coverage.py` (writes
   docs/format-coverage.md). It lists every chunk FOURCC in the
   corpus, split into documented / undocumented / known-but-absent.
2. Work the gap list. A kind is done when file-formats.md (or a
   dedicated doc) documents its layout with offset-level evidence,
   and any enum/value tables it feeds are resolved or explicitly
   closed as runtime-only.
3. Re-run the open-hole sweep: `rg -n -i "open question|unresolved|
   unverified|unproven|not shown|needs verification|enum candidate|
   NOT statically reachable|untraced" docs/` and drive every hit to
   either a resolution (with address/count evidence) or a written
   closure stating why it is not statically minable.
4. Repeat until the report's undocumented list is empty, the sweep
   is clean, and every phase below has its deliverables committed.

Then write the final record (section 4) and stop. Do not stop early
because a phase "looks done"; the bar is the empty report.

## 2. The work list

### Phase A: Audio (the whole frontier is unmined)

Measured 2026-09-21, do not re-derive, extend instead:

- DS1 RESOURCE.GFF: 23 music tracks (GSEQ/LSEQ ids 1..23; GSEQ and
  LSEQ ~176 KiB each, PSEQ 10 KiB total) + 111 BVOC digital samples
  (ids 1..130 with gaps, 1437 KiB) + CSEQ id 1000. DS1 CINE.GFF:
  4 cinematic tracks (ids 26..29). DS1 ships NO MSEQ and NO FSEQ:
  the file-formats audio table should say so explicitly (small doc
  correction). DS1 GPLDATA.GFF has no audio chunks.
- DS2: MUSIC/Track02-26.ogg is GOG's re-encode of the CD redbook
  audio (done, just document it). DS2 RESOURCE.GFF audio chunks are
  UNENUMERATED: run the same enumeration (BVOC corpus total across
  all DS-side containers was 815 chunks in the 2026-09-04 report).

Deliverables:

1. An extractor (stdlib-only; suggest tools/audio-extract/ following
   the gff-edit script pattern or a port-spike exporter): dumps
   GSEQ/LSEQ/PSEQ payloads, BVOC to WAV (VOC block decode is simple
   and documented), and writes an inventory JSON (ids, sizes,
   durations). Output under port-spike/generated/audio/ (gitignored).
2. XMI to standard MIDI: port the public-domain xmi2mid logic
   (docs/file-formats.md 5 already notes the dialect: 2-byte delta
   times, TIMB, RBRN). Cite the reference in comments + CREDITS.md;
   Glassmyer's MIT xmi-tool (checkout .dsun_music/xmi-tool/) is the
   prior art for the chunk wrappers.
3. The cue mapping: GPL opcodes 0x5D (sound) and 0x5F (music) are
   known (docs/gpl-vm.md 309, docs/gpl-opcodes.md 149; DS1 audio
   services 0x1a0a:0x663/0x672). Sweep the disassembled GPL chunks
   (gpl-disasm --json) for every 0x5D/0x5F operand and document
   which script/region requests which track or sample id. Deliver
   docs/audio-cues.md (region themes, combat/victory stings, sfx
   table with BVOC id, guessed meaning, duration).
4. Format doc: extend docs/file-formats.md's audio section (or add
   docs/audio-formats.md) with the chunk layouts actually verified:
   BVOC block structure, GSEQ/LSEQ/PSEQ headers, CSEQ, and the
   presence matrix per game (which of MSEQ/FSEQ/MGTL/FVOC/SINF/
   ADV/DADV/DRV exist where; DS1 has none of them in its three
   containers).
5. BVOC labeling: 111 DS1 samples need names. Empirical pass first
   (duration + ear via the DOSBox rig or local playback), engine
   confirmation second (the 0x5D operand sweep gives canonical ids).

### Phase B: the named RE holes (each is a port-digs entry)

1. Armour overlays on the centre figure. Base art is pinned
   (RESOURCE BMP 20000-20013, 20000+(race-1)*2+(gender-1),
   port-digs-2026-09-20.md 1). Unknown: the worn-gear overlay
   art source (per-slot? per-armour-type?), offsets, and the
   compositing rule the engine uses to dress the figure. Start from
   the inventory screen's figure draw path and the IT1R equip
   effects chain (screen-flow.md 8.3; unequip strips effects via
   item +15 -> 0x5B8:0x115/0x7F).
2. The capability permission-list populator. port-digs-2026-09-21.md
   2 proved the consumer side: head indices at [0x377E]:+0xD (steal)
   +0xF (talk) +0x15 (give), 13-byte records via [0x4356]:[0x42CC],
   walker 0x9720. Untraced: who WRITES the lists (suspect region/
   script load). Finding it tells us whether demo creatures can get
   engine-true caps.
3. Bestiary special-attack / special-defense bytes. bestiary-ds1.md
   header: "enum candidates and are not shown". Resolve the enums
   (find the engine's switch tables) or prove they are never read.
4. DS1 combat +8/+10/+12 derived stats. screen-flow.md 8.5 hole 2:
   "NOT statically reachable (the 0x628:* derived-stats family runs
   at runtime segment numbers)". Leads: DS2 NpcReadyWeapon /
   GetMissileWeapon / usedhands / NumHands (named in the DSO
   symbols file). The goal is the derivation rule, documented in
   rules-tables.md.
5. RBRN branch chunks. file-formats.md 5: "needs verification". What
   they contain, whether the engine follows them, and whether the
   27 DS1 tracks use any.
6. The 15503 spell-info icon bands and the SPST 39-138 generic
   default (0xc90) are already modelled; nothing to do here unless
   the sweep surfaces new leads.

### Phase C: the corpus sweep (this is what drives the report to zero)

The 2026-09-04 report's undocumented kinds (regenerate first; RNME
was documented after that report, so expect it gone):

- `DATA` (1292 chunks, 4 files incl. .games/ds2 and archive-org
  extractions) — the single biggest unknown.
- `MAP` (60), `PLYL` (24), `ALL` (15), `GREQ` (10), `VECT` (5),
  `CMAT` (2), `CPAL` (2), `PREF` (2, prefs chunk already known from
  prefs screen work: verify the doc covers its on-disk layout).
- The known-but-absent kind list (BMAP, CMAP, DADV, DBOX, DRV, FORM,
  FVOC, GFRE, GTOC, MENU, MGTL, MSEQ, OMAP, POBJ, SAVE, SBAR, SINF,
  SJMP, STXT, TMAP, TXRF): for each, either find where it lives
  (DS2 containers, save files, the archive-org CD/floppy trees) and
  document it, or record that DS1/DS2 never ship it.

Also non-GFF files: DS2's DJ.DAT and ITEMS.BIN (identify format),
game.gog CD image contents beyond the cuesheet/oggs, PATCH.RTP,
STDPATCH.AD (AdLib patch table layout), GM1/GM2.BNK (Roland bank
format; document purpose and whether MGTL ever points at them),
SSI1.INI / UM200.INI / UM206.INI (one paragraph each).

And the symbol coverage check: tools/gpl-disasm/syms/functions.toml
against .dso-online/tools/symbols.txt (3,530 named DS2 functions).
Report coverage, extend the TOML with newly confident names from the
dig, never invent names.

### Phase D: recording (continuous, every phase)

Every finding lands in docs/ the same day it is proven:

- Dated dig files: docs/port-digs-YYYY-MM-DD.md (the established
  pattern: verdict, addressed evidence, what it means for the port).
- Format docs updated in place; format-coverage.py regenerated and
  committed after every wave so the gap list is the live progress
  metric.
- CREDITS.md row for anything ported or informed by upstream
  (Glassmyer xmi-tool, libgff, soloscuro-archive, DSO symbols).
- roadmap.md boxes ticked as phases close; patchnotes entries when
  a tool ships a release-worthy increment.
- The open-hole sweep (section 1 step 3) must come back clean.

## 3. Wave plan (the 4-subagent budget)

Sequencing that has worked: main thread enumerates and plans, then
dispatches up to 4 research agents per wave, writes up everything
they return, commits, and only then launches the next wave.

- Wave shape for a binary dig: one GLM-5.3 general-purpose agent per
  question (self-contained prompt: repo paths, install paths, prior
  addresses, expected evidence format, "do not spawn subagents,
  write nothing"). Two binary questions per wave max, so reports
  stay digestible.
- Wave shape for corpus breadth (chunk-kind layout work, symbol
  coverage, INI/file identification): GLM-5.3-Flash Explore agents,
  one per container family, conclusion-plus-evidence reports.
- The audio cue sweep and BVOC enumeration are TOOLING runs, not
  agent work: write the script, run it in the main thread, read the
  output. Agents are for the digs that need judgment.
- After each wave: update docs, regenerate format-coverage.py,
  commit, re-derive the next wave's prompts from what changed.

## 4. Definition of done and the final record

Done when ALL of these hold:

1. `format-coverage.py` reports zero undocumented kinds in the
   corpus, and the known-kind table agrees with reality per game.
2. The open-hole sweep returns nothing (or only closures written as
   closures, with reasons).
3. Every phase A-E deliverable above is committed.
4. docs/mining-complete.md exists: the final record. One page per
   phase (what was mined, the headline numbers, where it is
   documented), the full chunk-kind table with per-game presence,
   the audio inventory (tracks, samples, cues), and the list of
   things proven NOT statically minable (runtime-only structures),
   each with the evidence that justifies giving up on it.

Only then report completion to Brandon. The pits lock is HIS to
lift; mining completion does not change it.

## 5. Traps the hard way (do not re-learn)

- DSUN.EXE is the engine name in BOTH games; never write a script
  that pkills or greps "DSUN" broadly and expects DS1 only.
- Ghidra's OSGi cache breaks on this host intermittently (self-
  healed before); if analyzeHeadless fails, fall back to r2 +
  manual 16-bit disassembly and say so in the dig doc. The MZ
  loader picks x86:LE:16:Real Mode; raw imports need it manually
  and produce convincing nonsense if wrong. No LE/LX loader
  extension. Ghidra does not understand Borland overlays: pair it
  with tools/ovr-map (935 DS1 / 854 DS2 confirmed entries).
- RDFF walking with signed <h lengths never terminates on a bad
  chain; bound every walk (orphaned python from a dead subagent
  once spun at 100% CPU forever).
- `.games/archive-org/` trees are evidence for the release-lineage
  work (docs/install-variants.md); read them, do not re-download
  or "clean" them.
- pkill -f self-match: use `pkill dosbox` (name only) in scripts.
- The DOSBox rig needs sound ON or MEL kills the boot
  (Mel Fatal Error #26); the audio verification takes use the
  committed live-capture recipes.
- Ruff 0.15.20 exactly; system ruff refuses. uvx ruff@0.15.20.
- `git add` from the repo root; `-A` for untracked dirs.
