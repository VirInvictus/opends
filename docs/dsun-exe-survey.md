# DSUN.EXE Full-Structure Survey

A whole-binary structural survey of both engines: DS1
(*Shattered Lands*, GOG 1.10, 611,408 bytes) and DS2 (*Wake of
the Ravager*, GOG 1.10, 634,416 bytes). Produced 2026-08-28.
This is the report the roadmap's EXE-readiness assessment asked
for: what we can now say about the binary from measurement, what
remains dark, and what each finding unblocks.

Companion documents: [`dsun-exe-re.md`](dsun-exe-re.md) is the
behavioural index (resource loader, palette, overlay mechanics);
[`dso-symbols.md`](dso-symbols.md) indexes the DSO debug-symbol
table. This page is the measured structure of both binaries as a
whole. Everything here was extracted with `ovr-map` (Phase 5.5)
as a library plus small ad-hoc scans; the key byte patterns are
inline so every number is reproducible.

## 1. Executive summary

1. **The resident image is the OS-service and runtime layer;
   the overlays are pure game logic.** Across 92,948 (DS1) and
   94,837 (DS2) disassembled overlay instructions there are
   effectively zero `INT` instructions (DS1: none; DS2: three
   single sites consistent with misaligned decode). All DOS file
   I/O, keyboard, mouse, video and DAC access lives in the
   resident image. A bug's *symptom* may be overlay logic, but
   the syscall surface it uses is all in one place.
2. **The overlay-to-resident call census gives us the engine's
   real API surface: ~340 resident functions.** 4,865 (DS1) /
   5,067 (DS2) direct `9A` far calls from overlay segments land
   on only 336 / 345 distinct resident targets. Naming those
   ~340 functions names the majority of what overlays do, by
   weight.
3. **The Borland overlay manager is located.** Exactly one
   `INT 3Fh` instruction exists outside the descriptor/stub
   region: DS1 at file `0x466e0`, DS2 at `0x404c4 (corrected 2026-09-05; see roadmap)`. That is the
   handler body of the overlay loader; the `'Runtime overlay
   error'` string rides with it in both binaries.
4. **`load_resource` is never called from an overlay.** The
   known FOURCC loader (`0001:04a4` DS1, `0128:04ab` DS2) has
   all 96 call sites in the resident image. Chunk loading is a
   resident service; overlays request, resident fetches.
5. **The chunk-vocabulary census weights the format docs by
   runtime load frequency.** The engine pushes ~30 distinct
   ASCII FOURCC immediates (`66 68` + 4 printable bytes): `BMP`
   x47, `ICON` x22, `APFM` x21, `BUTN`, `EBOX`, `CACT`, `RDFF`,
   `ETAB`, `RGTP`, `OJFF`, `GPLI`, `SPST`, `PSST`, `PSIN`,
   `STXT`, `PREF`, `SCMD`, `MENU`, `WIND`, `IT1R`, `FNFO`,
   `BVOC`, `GREQ` and more, per game (section 5). Most are
   already catalogued in `file-formats.md`; the census adds
   which ones the engine actually requests (`BMP` by an order
   of magnitude) and surfaces three the docs do not mention
   (`RGTP`, `PREF`, `GREQ`).
6. **Source-file breadcrumbs survive in the string table.**
   `'Bad iCtrl in gpldisk.c'` names the save/region module's
   source file; `'Failed Uncompress in Loadgamefromdisk'`
   proves saves are stored compressed; a tight cluster of
   region-change failure strings (`'Fatal error: Region
   change, Invalid save'`, `'Failed to move to region #%Fs'`)
   anchors the exact subsystem Phase 7 needs (section 7).
7. **The official-patch delta is measured.** The CD 1.0
   `DSUN.EXE` (`e73f79c3...`) was confirmed from an independent
   source against the `install-variants.md` record and diffed
   against GOG 1.10: 5 overlay segments byte-identical, 44
   changed, 117,566 differing bytes, and several segments with
   fix-sized localized changes (segment 0: 10 bytes). SSI's
   own bug sites are now enumerable (section 8). Earlier
   same-day text claiming the diff was "blocked" was wrong; it
   compared only against the floppy line.
8. **The DSO symbol table is directly usable as a naming
   target list.** 3,530 named functions whose prefixes map onto
   engine subsystems (`GUI` x190, `Combat`/`_AI`, `Gpl*`,
   `Save*`/`Load*`, `MEL`, `VGA`), including every check
   function the mines-elevator question touches: `GplTileCheck`,
   `GplDoorCheck`, `GplChangeRegion` (section 9).

## 2. Ground rules established

- **Entry point.** Both binaries enter at `CS:IP = 0:0`, i.e.
  the first byte of the load image: DS1 file `0x5400`, DS2 file
  `0x5200` (that is also each header size). The first
  instructions are the Borland C++ startup: set `DS` from an
  absolute, `mov ah,0x30 / int 21h` (DOS version), then the
  environment scan (`repne scasb`). Verified by disassembly.
- **Header sizes.** DS1 `0x5400`, DS2 `0x5200` (DS2's was not
  previously recorded; the -0x5400 constant in
  `dsun-exe-re.md` 3.5 is DS1-specific).
- **Runtime-linear arithmetic** used throughout: a far pointer
  `seg:off` inside the load image corresponds to file offset
  `header_size + seg*16 + off`.
- **Overlay segments begin directly with code.** The first two
  bytes of segment 1 in both games are `00 00`, but every other
  segment begins `55 8B EC` (`push bp; mov bp,sp`); there is no
  per-segment relocation table at the segment start. Where the
  per-segment relocation tables named by the descriptors live
  is still open (section 10).
- **Entry points are functions.** The count of `55 8B EC`
  prologues per segment equals or slightly exceeds the
  descriptor's entry-stub count in every segment surveyed
  (appendix A/B), confirming entries are function starts, not
  arbitrary labels.

## 3. The resident image

The resident image is the program proper: DS1 339 KB, DS2 356
KB before the overlay area. It contains the Borland C++
runtime (startup, `VDISK`/`VMEM` virtual-memory manager with
its `'VMEM: ...'` and `'ABEND: ...'` message tables, `'Null
pointer assignment'`), the overlay manager, and the engine's
OS-service layer.

### 3.1 Interrupt usage (raw byte counts, resident image)

| Bytes | Meaning | DS1 | DS2 |
|---|---|---|---|
| `cd 21` | DOS services | 103 | 100 |
| `cd 16` | keyboard | 5 | 4 |
| `cd 33` | mouse | 12 | 29 |
| `cd 10` | BIOS video | 2 | 12 |
| `cd 08` | IRQ0 timer | 0 | 1 |
| `cd 1c` | user timer hook | 0 | 0 |
| `cd 3f` | overlay calls (stubs, descriptors, one handler) | 994 | 904 |
| `ba c8 03` | `mov dx,0x3c8` (DAC write) | 4 | 4 + 1 overlay |

`int 21h / ah=25h` (set vector) does not occur; the overlay
handler is installed by writing the IVT directly (the c0
startup's `mov [cs:0x2c4],dx` pattern and neighbours). DS2
uses the mouse and BIOS video substantially more than DS1,
consistent with its interface work between the games.

### 3.2 The overlay manager

Exactly one `cd 3f` occurs outside the descriptor/stub region:

| Game | `INT 3Fh` handler body | Nearby marker |
|---|---|---|
| DS1 | file `0x466e0` | `'Runtime overlay error'` at `0x56c8` |
| DS2 | file `0x404c4 (corrected 2026-09-05; see roadmap)` | `'Runtime overlay error'` at `0x54c8` |

This is the function the 994 / 904 stub `INT 3Fh`s trap into.
It has not been read instruction-by-instruction yet; when it
is, we get the segment cache/swap policy, which bounds how
many overlay segments can be resident at once (relevant to
races like the mines elevator).

### 3.3 The resident API surface (the headline census)

> **Correction (2026-09-04, from the Phase 5.6.0 tooling).** This
> census keyed targets by the far-call's *segment base only*
> (`seg*16 + header`), dropping the call offset; the counts below
> are distinct called **segment values**, not distinct functions.
> The `propose-exe-symbols.py --census` worklist resolves exact
> `seg:off` pairs: DS1 4,953 sites / 760 candidate targets, DS2
> 5,111 / 746 (36 / 35 confirmed by a `55 8B EC` entry prologue).
> Two caveats carry over from the re-measurement: overlay far-call
> segment words predate the overlay manager's relocation pass
> (their per-descriptor relocation tables are still unlocated, §4),
> so a resolved target is a *candidate* until corroborated; and
> this census counts calls decoded in overlay code only, so a
> function with all callers resident-side (like `load_resource`)
> does not appear in the exact-target list at all.

Strict census: every disassembled overlay instruction whose
bytes are exactly `9A <off:2> <seg:2>` with target landing in
the resident image.

| | DS1 | DS2 |
|---|---|---|
| far-call sites into resident | 4,865 | 5,067 |
| distinct resident targets | 336 | 345 |
| hottest target (calls) | `0x5cc0` region, 172 | `0x5810` region, 237 |

The hottest targets cluster in the first resident code segment
(`0x5400`-`0x5e00` in DS1): the Borland runtime helpers (`rep
movsw` block movers, long arithmetic, heap). Below that sit
the engine's own resident services. The top targets are
disassembly-verified but not yet behaviourally named; a
naming pass over these ~340 functions (each is ~1-2 KB of
code at most) is the highest-value next RE work and is what
the DSO table should be shape-matched against first.

`load_resource` specifically (`0001:04a4` DS1 = file `0x58b4`;
`0128:04ab` DS2 = file `0x692b`) shows **zero** overlay
callers; its 96 call sites are all resident-side. Same
expected for the other low-level services: overlays consume
higher-level resident wrappers.

### 3.4 String-table breadcrumbs

The resident string table preserves source-level names and
messages (DS1: 706 strings >= 8 chars; DS2: 614). Highlights,
with file offsets:

| Game | Offset | String | What it proves |
|---|---|---|---|
| DS1 | `0x49d3d` | `Bad iCtrl in gpldisk.c` | the save/region module is `gpldisk.c` |
| DS1 | `0x49d94` | `Failed Uncompress in Loadgamefromdisk` | saves are stored compressed |
| DS1 | `0x49d56` | `gpldisk out of memory` | |
| DS1 | `0x49e43` | `Fatal error: Region change, Invalid save` | region-change module anchor |
| DS1 | `0x49e71` | ` Failed to move to region #%Fs ` | ditto; region ids are formatted strings |
| DS1 | `0x49e92` | `Error : Can't load Game data in load teleport` | teleport path shares the module |
| both | `0x494e9` / `0x4dd5e` | `SAVE%.2d.SAV` | slot save naming |
| both | `0x494f6` / `0x4dd6b` | `Maximum of %ld save games!` | |
| DS1 | `0x48daf` | `YOU CANNOT CAST SPELLS` | GUI/status string layer |
| DS2 | `0x4d77b` | `VERSION 1.1` | the 1.10 marker `install-variants.md` inferred |
| DS2 | `0x4da0b` | `Wowowowowowow... Mel DJ failed... Is CD.DAT in you dir?` | MEL/DJ audio depends on `CD.DAT` |
| DS2 | `0x4226c` | `Cannot Move` / `Cannot Use Psionics` | status-flag string layer |
| both | `0x46732` / `0x4b042` | `VDISK FAKE` | Borland VMEM debug path present |

The DS1 region-change cluster (`0x49d3d`-`0x49e92`) is the
concrete Phase 7 anchor: find code referencing these offsets
(the seg:off pair search from `dsun-exe-re.md` 4.5.1, with
linear = file - `0x5400`) and the save/region module is
located by string cross-reference instead of by shape.

## 4. The overlay area

Census totals (see appendix A/B for the per-segment tables):

| | DS1 | DS2 |
|---|---|---|
| overlay segments (live records) | 52 (+6 empty) | 49 (+0 empty) |
| entry points | 935 | 854 |
| overlaid bytes / coverage | 253,109 / 93.13% | 258,376 / 93.39% |
| disassembled instructions | 92,948 | 94,837 |
| `55 8B EC` prologues | ~= entries, per segment | same |
| `INT` instructions | 0 | 3 (decode-suspect) |
| DAC port writes | 0 | 1 (seg 46, `0x9ad33`) |

The zero-`INT` result is the section's headline: **overlay
code performs no DOS or BIOS calls at all.** Every syscall is
a resident-side service. Practical consequences:

- Overlay segments can be disassembled and understood without
  DOS semantics; the only environment they touch is memory
  passed in by callers.
- The single DS2 DAC site (segment 46, segment-local offset
  35, a 61-byte tail segment) is the one exception in either
  binary and deserves an individual read; it is either a
  deliberate special case or a misidentified byte run.
- The descriptor-table area before `image_end` also carries
  the per-segment relocation counts (`+0x0a`), but the tables
  themselves are not at segment start and not at padding
  start; their location is open (section 10).

### 4.1 Far-call topology

`ovr-map --callgraph` (relocation-filtered, targeting entry
stubs):

| | DS1 | DS2 |
|---|---|---|
| direct far-call edges to stubs | 210 | 216 |
| stubs with a direct caller | 115 (12.3%) | 121 (14.2%) |
| indirect far-call sites (`FF /2`) | 62 | 65 |

The indirect sites are highly concentrated: DS1 overlay
segment 25 holds 17 of them; DS2 segments 21 / 35 / 42 hold
17 / 4 / 1. Those segments are the engine's function-pointer
dispatchers (GPL dispatch is the prime suspect, given the
`GPLI` pushes in the census below). Reading DS1 segment 25 and
DS2 segment 21 in full would convert a large share of the
indirect-call mystery into ordinary edges.

## 5. Chunk-loading surface: the FOURCC push census

Pattern: `66 68` (`push dword`) followed by four printable
ASCII bytes, whole file. Counts are per game; a value can also
be a non-FOURCC constant, so treat this as vocabulary with a
small false-positive rate (all values below recur in ranges
that disassemble as code and most match known or plausible
chunk names).

| FOURCC | DS1 | DS2 | Notes |
|---|---|---|---|
| `BMP ` | 47 | 38 | bitmaps; by far the most loaded |
| `ICON` | 22 | 22 | |
| `APFM` | 21 | 21 | palette-family; undocumented in file-formats.md |
| `BUTN` | 10 | 10 | buttons |
| `EBOX` | 9 | 9 | edit boxes |
| `CACT` | 9 | 9 | |
| `RDFF` | 8 | 11 | record data; documented (per-game schemas) |
| `ETAB` | 6 | 3 | entry table (known) |
| `RGTP` | 5 | 5 | not in file-formats.md |
| `OJFF` | 4 | 5 | known |
| `PAL ` | 4 | 4 | known |
| `MENU` | 4 | 4 | known |
| `CHAR` | 3 | 4 | known |
| `GPLI` | 4 | 4 | GPL-related |
| `NAME`/`IT1R`/`SPST`/`PSST`/`PSIN`/`STXT`/`PREF` | 3-4 each | 2-3 each | spell/psionics/text families; `PREF` not in file-formats.md |
| `SCMD`/`GMAP`/`WIND`/`ADV ` | 2 | 2 | known + window/adv |
| `TEXT` | - | 5 | known |
| `FNFO`/`BVOC` | - | 3-4 | known |
| `GREQ`/`DATA` | - | 3 / 2 | `GREQ` not in file-formats.md |
| `CMAT`/`CPAL` | 1 / 1 | 0 | matches 3.4 of dsun-exe-re.md |

The vocabulary itself mostly corroborates `file-formats.md`;
what the census adds is weighting (`BMP` is loaded an order of
magnitude more than anything else, the GUI families next) and
three types the format doc lacks: `RGTP`, `PREF`, `GREQ`
(small counts; possibly non-FOURCC immediates, verify per
site before documenting). All of the confirmed types live in
`RESOURCE.GFF`-family containers we can already read
chunk-agnostically with `gff-cat list`.

## 6. File surface

DOS filename strings in the binaries (counts are string
occurrences):

| String | DS1 | DS2 | Reading |
|---|---|---|---|
| `DARKRUN.GFF` | 7 | 5 | live world state (known) |
| `DARKSAVE.GFF` | 4 | 3 | save writes; note lowercase `darksave.GFF` copies used in format strings |
| `CHARSAVE.GFF` | 3 | 3 | character store (known) |
| `RESOURCE.GFF` | 2 | 7 | CD resource container; DS2-heavier |
| `GPLDATA.GFF` | 2 | 1 | bytecode container (known) |
| `RGNFF.GFF` / `RGN0FF.GFF` | 2 | 1 | region filename template fragments |
| `RGNXX.GFF` / `RGN0XX.GFF` | 1 | 1 | ditto: the engine builds `RGN` + hex id + variant |
| `RESFLOP.GFF` | - | 1 | floppy-line resource container; CD build does not use it |
| `SEGOBJEX.GFF` / `OBJEX.GFF` | 1 / 1 | 2 | object stores (known) |
| `CINE.GFF` | 1 | - | cinematics container |
| `SOUND.CFG` | 2 | 2 | |
| `2D.SAV` | 2 | 2 | unknown; likely the video-mode/screen state sidecar |
| `SAVE%.2d.SAV` (format) | 1 | 1 | slot saves |
| `DARKCD.EXE` | 1 | - | the overlay's own recorded filename (DS1) |
| `DSMALL.EXE` | - | 1 | DS2 auxiliary executable |
| `CD.DAT` / `DJ.DAT` | - | 1 / 1 | DS2 CD-audio / DJ driver data |
| `*.FLI` (`U.FLI`, `D.FLI`, `2-5.FLI`) | - | yes | Autodesk FLIC cinematics by name |

`RESFLOP.GFF` is new information for `install-variants.md`: the
floppy line names its resource container differently, which is
independent confirmation that the floppy and CD builds diverge
at the source level (cf. section 8).

## 7. The DSO symbol table as a naming target list

`.dso-online/tools/symbols.txt`: 3,530 functions + 2,247
globals/locals. Offsets are DSO-relative and do not transfer;
the names are the payload. Prefix census of function names:
`GUI` 190, `GET` 159, `DEC` 121, `HAN` 77, `GAM` 76, `MEL` 67,
`_AI` 67, `_ME` 65, `CHE` 61, `SPI` 61; 140 functions carry
full subsystem names. The directly Phase-7-relevant set:

- Region transitions: `GplChangeRegion`, `GplDiskChangeRegion`,
  `GplTileCheck`, `GplDoorCheck`, `GplTalkCheck`,
  `GplPickupCheck`, `GplAttackCheck`, `GplLookCheck`,
  `GplUseCheck`, `GplUseWithCheck`, `combatGameCenterOnXY`.
- Save/load: `SaveGameToDisk`, `LoadGameFromDisk`,
  `SaveCurrentPCs`, `SaveCharRec`, `SaveObjectToDisk`,
  `SaveEntryTable`, `SaveObjectTable`, `LoadObjectTable`,
  `SavePsiSpells`, `LoadPsiSpells`, `SaveMouseItem`.
- Combat: `CombatEntry`, `CombatStartPhase`, `CombatAttack`,
  `CombatMove`, `CombatDropItems`.
- Palette: `VGASetCycle`, `VGAResetCycle`, `VGAColorCycle`,
  `cycleshow`, `gCycleColor` (already catalogued in
  `dsun-exe-re.md` 4.6).

Transfer method (unchanged in principle from
`dso-symbols.md`): pick a name, predict its DSUN.EXE shape
from what the function must do, find the resident or overlay
function by that shape, verify with a second observable
(string reference, call degree, constant). The section 3.3
census sharpens this: match resident targets first (only
~340 to choose from), overlays second.

## 8. The official-patch diff: done, with a correction

> **Correction (2026-08-28, same day).** This section first
> concluded the diff was "blocked" because the only old binary
> compared was the floppy 1.0 one. That verdict was wrong: the
> **CD 1.0 `DSUN.EXE`** was in hand the whole time -
> `install-variants.md` §3 records that `game.gog` (inside the
> GOG package) carries the 1.0 CD tree with `DSUN.EXE =
> e73f79c3...`, and an independently sourced public CD-tree zip
> has now been hash-verified against exactly that record
> (`DSUN.EXE = e73f79c3...`, `GPLDATA.GFF = 11fda691...`, both
> matching). The base is staged at
> `.games/archive-org/cd10-extracted/` (gitignored, dev-side).
> What follows is the corrected measurement.

The floppy-line comparison stands as recorded below: the floppy
1.0 build is a different *product line* (634,208 B, 866
entries, `RESFLOP.GFF`-based), not a stepping stone to the CD
build, and diffing against it is meaningless.

The meaningful comparison is **CD 1.0 (`e73f79c3...`) vs GOG
1.10 (`ce02ee1f...`)**: by `install-variants.md` §3, applying
SSI's official `WAKECD11` RTPatch to the CD 1.0 tree reproduces
the GOG tree byte-identically, so this diff is *exactly* the
official 1.02-to-1.10 fix delta (plus any packaging rebuild SSI
did). Measured, per overlay segment paired by index:

| Metric | Value |
|---|---|
| segments byte-identical | 5 (`1`, `45`, `46`, `47`, `48`) |
| segments changed | 44 |
| total differing bytes (overlays) | 117,566 |
| entry-count changes | 8 segments (mostly -1; seg 26 -3) |
| tightly-localized fixes | e.g. seg 0: 10 diff bytes in 7 clusters; seg 8: 70 bytes in 14-byte runs; seg 5: 69 bytes; seg 2: 143 bytes in 83 clusters |
| heavily rebuilt | segs 4, 6, 10, 11, 13, 14, 20, 21, 24, 26, 27, 28, 34, 35, 41 (30-98% of bytes, sizes shifted) |

Reading: SSI's 1.10 was a *recompile*, not a hex edit - most
segments moved. But the low-diff segments are direct evidence
of targeted fixes (a 10-byte, 7-cluster change in segment 0 is
a fix-sized edit), and the identical segments are alignment
anchors that make even the rebuilt segments cross-comparable
function-by-function.

Per-segment cluster listings: regenerated by diffing the two
binaries segment-wise (paired-index walk; recipe inline in this
section). The full cluster listing for this measurement is
retained in the authoring scratch (`scratch/exe-survey/`,
gitignored). Next step for Phase 5.6/7 value:
characterize the low-cluster segments (0, 5, 8, 9, 16, 36)
instruction-by-instruction against the 1.02 fix list in
`known-bugs.md` §1 - SSI's own bug sites, named.

`RESFLOP.GFF` (section 6) independently shows the floppy line
diverges at the source level, which is why floppy comparisons
stay dead. No DS1 1.0 artifact is known to exist; DS1 shows no
variant problem in practice (`install-variants.md` §1), and the
independently sourced DS1 tree's `DSUN.EXE` and `GPLDATA.GFF`
hash-match the GOG 1.10 records exactly.

## 9. Answers this survey gives the open-questions list

Against `dsun-exe-re.md` 5 ("What we still don't know"):

1. **Region-number-to-family map (DS1).** Unchanged (resolved
   2026-08-08: no such map), but the survey adds the better
   prize: the *save/region module* itself is now string-anchored
   (section 3.3 of this page), which is the path to
   `GplChangeRegion`'s DS1 counterpart.
2. **CMAT format.** No new data; CMAT/CPAL remain the 1/1
   pushes of the family-200/300 arms.
3. **Animated palette cycle.** Bounded further: overlay code
   writes the DAC in exactly one DS2 site and zero DS1 sites,
   so the cycle routine (if it exists as separate code) is in
   the resident image, within reach of the section 3.3 target
   list. `VGAColorCycle` shape-matching should start from the
   ~345-resident-target set, not the overlays.
4. **DS2 palette source.** The `PAL ` push sites are now
   segment-mappable in one pass (`ovr-map --verify` per push
   site); not yet done, listed as next work.
5. **DS2 `load_resource` segment.** Resolved as far as it can
   be statically: file `0x692b` (`header_size 0x5200` +
   `0x128*16 + 0x4ab`), all callers resident-side.

## 10. What is still dark, and next steps

1. **Name the ~340-resident-function API surface.** The single
   highest-value pass: for each target in the section 3.3
   census, disassemble, characterize (prologue size, string
   refs, int usage, callees), and match against the DSO name
   list. Even 100 named functions would transform binary RE
   into lookup.
2. **Read the overlay manager** (`0x466e0` / `0x404c4 (corrected 2026-09-05; see roadmap)`): cache
   policy, how many segments stay resident, eviction rules.
   Directly relevant to any region-transition race.
3. **Read the dispatcher segments**: DS1 overlay segment 25,
   DS2 segments 21 / 35 / 42 hold the concentrated indirect
   far-call sites; these are the function-pointer tables that
   hide the call graph's missing edges.
4. **Locate the per-segment relocation tables** named by the
   descriptors (`+0x0a`): not at segment start, not at padding
   start. Finding them completes the overlay-format picture
   and would let a future loader/applier reason about
   relocations when authoring EXE patches.
5. **Chunk-format work for the load-frequency heavyweights**
   (section 5): `BMP` is requested an order of magnitude more
   than anything else, and `APFM` (named in file-formats.md
   but layout TBD; 21 pushes in each game, palette-adjacent)
   is the likeliest key to the DS2 palette question.
6. **Read DS2 overlay segment 46** (61 bytes, the only DAC
   write outside any resident image).
7. **Ghidra headless bulk pass** over both binaries using the
   `ovr-map --ghidra` script (Phase 5.5's verified pipeline),
   exporting function lists to cross-check section 3.3's
   census.

## Appendix A: DS1 overlay segment census

| seg | file range | size | entries | instrs | `55 8B EC` |
|---|---|---|---|---|---|
| 0 | 0x52eb0-0x5351c | 1644 | 5 | 519 | 6 |
| 1 | 0x53600-0x53b95 | 1429 | 4 | 585 | 5 |
| 2 | 0x53ba0-0x54bbe | 4126 | 12 | 1425 | 12 |
| 3 | 0x54d90-0x56247 | 5303 | 14 | 1744 | 14 |
| 4 | 0x56490-0x56be0 | 1872 | 3 | 570 | 3 |
| 5 | 0x56cc0-0x5a031 | 13169 | 43 | 4906 | 43 |
| 6 | 0x5a320-0x5af22 | 3074 | 13 | 1179 | 13 |
| 7 | 0x5afb0-0x5c6ba | 5898 | 19 | 2036 | 19 |
| 8 | 0x5c8b0-0x5d8ad | 4093 | 26 | 1689 | 26 |
| 9 | 0x5d990-0x5e68b | 3323 | 21 | 1296 | 24 |
| 10 | 0x5e720-0x5ec6c | 1356 | 18 | 579 | 18 |
| 11 | 0x5ec90-0x5fd6f | 4319 | 10 | 1448 | 10 |
| 12 | 0x5fec0-0x60b49 | 3209 | 17 | 1208 | 17 |
| 13 | 0x60bc0-0x6152d | 2413 | 11 | 801 | 11 |
| 14 | 0x61650-0x61f1a | 2250 | 6 | 760 | 6 |
| 15 | 0x62030-0x6314c | 4380 | 32 | 1667 | 32 |
| 16 | 0x63250-0x6527f | 8239 | 47 | 2924 | 47 |
| 17 | 0x65480-0x67616 | 8598 | 20 | 2962 | 20 |
| 19 | 0x67890-0x67f63 | 1747 | 13 | 622 | 13 |
| 21 | 0x68000-0x6a1c6 | 8646 | 40 | 3163 | 40 |
| 22 | 0x6a3b0-0x6bb96 | 6118 | 49 | 2245 | 49 |
| 24 | 0x6bd80-0x6f8f3 | 15219 | 33 | 5349 | 33 |
| 25 | 0x6fdd0-0x731f0 | 13344 | 40 | 4781 | 40 |
| 26 | 0x73530-0x7423b | 3339 | 20 | 1244 | 20 |
| 27 | 0x74300-0x74f32 | 3122 | 7 | 1066 | 12 |
| 28 | 0x750e0-0x77a21 | 10561 | 48 | 4139 | 48 |
| 29 | 0x77c60-0x78033 | 979 | 3 | 317 | 3 |
| 30 | 0x780c0-0x78adc | 2588 | 12 | 966 | 14 |
| 32 | 0x78ba0-0x7c851 | 15537 | 83 | 6165 | 83 |
| 33 | 0x7cbb0-0x7cc23 | 115 | 1 | 42 | 1 |
| 34 | 0x7cc30-0x7df80 | 4944 | 14 | 1591 | 14 |
| 35 | 0x7e190-0x7e5a7 | 1047 | 7 | 346 | 7 |
| 36 | 0x7e620-0x7f2c2 | 3234 | 8 | 1086 | 8 |
| 37 | 0x7f3d0-0x7fe4a | 2682 | 9 | 899 | 9 |
| 38 | 0x7ff30-0x8133b | 5131 | 22 | 1941 | 22 |
| 40 | 0x81470-0x81c0d | 1949 | 14 | 759 | 14 |
| 41 | 0x81c90-0x82e35 | 4517 | 14 | 1699 | 14 |
| 42 | 0x82f20-0x83e56 | 3894 | 9 | 1312 | 9 |
| 43 | 0x83fa0-0x8467a | 1754 | 9 | 652 | 9 |
| 44 | 0x846d0-0x854de | 3598 | 14 | 1406 | 14 |
| 45 | 0x85560-0x87008 | 6824 | 18 | 2387 | 18 |
| 46 | 0x87250-0x87d01 | 2737 | 16 | 1142 | 16 |
| 47 | 0x87d60-0x89b89 | 7721 | 11 | 2518 | 11 |
| 48 | 0x89e70-0x8ad73 | 3843 | 8 | 1276 | 8 |
| 49 | 0x8aee0-0x8c7e4 | 6404 | 10 | 2168 | 10 |
| 50 | 0x8c970-0x8ce10 | 1184 | 6 | 397 | 6 |
| 51 | 0x8ce80-0x90a9b | 15387 | 36 | 5379 | 36 |
| 52 | 0x90fb0-0x91c53 | 3235 | 6 | 1127 | 6 |
| 53 | 0x91d10-0x92a7d | 3437 | 16 | 1187 | 16 |
| 54 | 0x92ba0-0x92c79 | 217 | 4 | 80 | 4 |
| 55 | 0x92ca0-0x94ea0 | 8704 | 6 | 2774 | 6 |
| 57 | 0x95180-0x95410 | 656 | 8 | 237 | 8 |file ranges are byte offsets in the shipped DSUN.EXE; size in bytes; `55 8B EC` counts standard function prologues.

## Appendix B: DS2 overlay segment census

| seg | file range | size | entries | instrs | `55 8B EC` |
|---|---|---|---|---|---|
| 0 | 0x57580-0x57b94 | 1556 | 5 | 495 | 6 |
| 1 | 0x57c70-0x58205 | 1429 | 4 | 585 | 5 |
| 2 | 0x58210-0x5925a | 4170 | 12 | 1442 | 12 |
| 3 | 0x59430-0x5a6fe | 4814 | 14 | 1594 | 14 |
| 4 | 0x5a920-0x5ea7c | 16732 | 45 | 6223 | 45 |
| 5 | 0x5ee00-0x5fb41 | 3393 | 13 | 1316 | 13 |
| 6 | 0x5fbe0-0x61347 | 5991 | 19 | 2074 | 19 |
| 7 | 0x61540-0x62067 | 2855 | 19 | 1158 | 19 |
| 8 | 0x62100-0x6300e | 3854 | 21 | 1525 | 21 |
| 9 | 0x630b0-0x64195 | 4325 | 9 | 1458 | 9 |
| 10 | 0x642e0-0x66f95 | 11445 | 27 | 4187 | 27 |
| 11 | 0x671e0-0x67d64 | 2948 | 13 | 1043 | 13 |
| 12 | 0x67eb0-0x6873c | 2188 | 5 | 734 | 5 |
| 13 | 0x68850-0x6ad08 | 9400 | 41 | 3222 | 41 |
| 14 | 0x6afe0-0x6ce93 | 7859 | 46 | 2816 | 46 |
| 15 | 0x6d090-0x6f3b0 | 8992 | 20 | 3079 | 20 |
| 16 | 0x6f640-0x6f6f9 | 185 | 1 | 64 | 1 |
| 17 | 0x6f700-0x6fdad | 1709 | 12 | 614 | 12 |
| 18 | 0x6fe30-0x72b8b | 11611 | 53 | 4235 | 53 |
| 19 | 0x72ea0-0x747e6 | 6470 | 48 | 2354 | 48 |
| 20 | 0x749b0-0x77f3a | 13706 | 30 | 4938 | 30 |
| 21 | 0x78340-0x7be16 | 15062 | 42 | 5330 | 42 |
| 22 | 0x7c1f0-0x7d212 | 4130 | 16 | 1538 | 16 |
| 23 | 0x7d300-0x7e160 | 3680 | 7 | 1265 | 12 |
| 24 | 0x7e2f0-0x80ece | 11230 | 44 | 4348 | 44 |
| 25 | 0x81130-0x816c9 | 1433 | 3 | 457 | 3 |
| 26 | 0x81770-0x82daa | 5690 | 14 | 2078 | 16 |
| 27 | 0x82f70-0x833c2 | 1106 | 9 | 381 | 9 |
| 28 | 0x83400-0x86f67 | 15207 | 38 | 5715 | 38 |
| 29 | 0x87310-0x878cc | 1468 | 5 | 583 | 5 |
| 30 | 0x87900-0x88f11 | 5649 | 15 | 1838 | 15 |
| 31 | 0x89160-0x8976e | 1550 | 8 | 503 | 8 |
| 32 | 0x897c0-0x8a368 | 2984 | 9 | 976 | 9 |
| 33 | 0x8a4a0-0x8b12b | 3211 | 8 | 1074 | 8 |
| 34 | 0x8b240-0x8bcc8 | 2696 | 9 | 913 | 9 |
| 35 | 0x8bdc0-0x8e660 | 10400 | 40 | 3885 | 40 |
| 36 | 0x8e8b0-0x8e948 | 152 | 2 | 75 | 2 |
| 37 | 0x8e950-0x9004c | 5884 | 16 | 2152 | 16 |
| 38 | 0x90180-0x916cb | 5451 | 12 | 1795 | 12 |
| 39 | 0x91890-0x93088 | 6136 | 24 | 2389 | 24 |
| 40 | 0x93160-0x94d09 | 7081 | 20 | 2491 | 20 |
| 41 | 0x94f60-0x95d9a | 3642 | 17 | 1464 | 17 |
| 42 | 0x95e10-0x97f00 | 8432 | 17 | 2866 | 17 |
| 43 | 0x98200-0x990ef | 3823 | 8 | 1271 | 8 |
| 44 | 0x99260-0x9ab3a | 6362 | 10 | 2148 | 10 |
| 45 | 0x9acd0-0x9ad07 | 55 | 1 | 35 | 1 |
| 46 | 0x9ad10-0x9ad4d | 61 | 1 | 42 | 1 |
| 47 | 0x9ad60-0x9adad | 77 | 1 | 45 | 1 |
| 48 | 0x9adc0-0x9ae1c | 92 | 1 | 53 | 1 |file ranges are byte offsets in the shipped DSUN.EXE; size in bytes; `55 8B EC` counts standard function prologues.
