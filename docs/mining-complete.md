# Mining complete: the final record

The static-mining campaign for SSI's Dark Sun CRPGs is complete.
This file is the record PROMPT-mineout.md section 4 asked for: one
page per phase, the full chunk-kind table with per-game presence,
the audio inventory, and the list of things proven NOT statically
minable, each with the evidence that justifies leaving it.

The completion bar (PROMPT-mineout section 1) is met:

1. `format-coverage.py` reports **zero** undocumented kinds; the
   known-kind table agrees with reality per game (file-formats.md
   1's census also closes the 21 documented-but-never-shipped
   kinds).
2. The open-hole sweep returns only written closures. The live
   grep (`rg -n -i "open question|unresolved|unverified|unproven|
   not shown|needs verification|enum candidate|NOT statically
   reachable|untraced" docs/`) still matches a handful of lines,
   and every one of them is a past-tense or quoted mention of a
   closed item: the ledger headers that say "driven to verdicts"
   (overlay-formats.md 8, gpl-vm.md 6), the dialogs census label
   with its written closure paragraph, and the dig files quoting
   the older eras they closed. Nothing matches as an open
   question.
3. Every phase deliverable is committed; the campaign shipped
   audio-extract 0.1.0, xmi2mid 0.1.0, gff-edit 0.6.3, ovr-map
   0.3.5 and 0.3.6, and darkfix-ds2 0.1.1 along the way.
4. This file exists.

The one remainder is human-gated by design: **the ear pass**
(Brandon-assisted): binding DS1's 23 music tracks to contexts by
listening (proved to have no static cue, twice) and naming the 56
never-scripted BVOC samples. Nothing else in the games' shipped
data is undug.

## Phase A: audio

Mined 2026-09-21 through 2026-10-06; documented in
docs/audio-cues.md, docs/audio-routing.md, docs/file-formats.md 5,
docs/port-digs-2026-10-06.md 2.

- **Inventory**: 815 BVOC digital samples corpus-wide (DS1 111,
  ids 1..130 with gaps; DS2 the rest), 499 at 8000 Hz and 316 at
  10989 Hz, 1,386.9 seconds, zero decode failures. Music: DS1
  ships 23 tracks as GSEQ/LSEQ/PSEQ triples (ids 1..23, cues 7 and
  17 short) plus CSEQ 1000 and 4 CINE.GFF themes (ids 26..29); DS2
  ships no sequenced music (the redbook CD went to GOG's
  TrackNN.ogg re-encodes; the floppy lineage's 36 XMIs are
  TIMB+EVNT only). DS1 ships no MSEQ and no FSEQ.
- **The adaptive-music discovery**: 63 RBRN branch tables (one per
  sequence kind per track except the two short cues) make DS1's
  music adaptive at runtime: XMIDI controller 0x78 selects the
  branch, the embedded Mel library follows it
  (port-digs-2026-10-06.md 2 and 2026-10-07.md 1 name the library
  end to end). Every branched song is a FOR/NEXT loop re-entered
  at the selected branch point.
- **The cue sweep** (audio-cues.md): DS1 251 `gpl sound` call
  sites over 55 distinct ids (sound id = BVOC id); DS2 433 call
  sites over 127 numeric ids plus one computed operand (sound id
  = BVOC id - 1). `gpl music` is **never emitted** by any script
  in either game: a proved negative, twice; music binding is
  engine-side (the ear pass).
- **Tools**: `audio-extract` 0.1.0 (BVOC/FVOC to WAV, verbatim
  *SEQ dumps, inventory JSON, the cue sweep) and `xmi2mid` 0.1.0
  (branch-aware conversion to standard MIDI plus the adaptive-data
  sidecar; 83 DS1 + 36 floppy sequences convert).

## Phase B: the named RE holes (all closed)

Each was a named hole in PROMPT-mineout section 2; every one is
resolved or closed as a written negative in
docs/port-digs-2026-10-06.md:

- **Armour overlays** (B.1): do not exist. DS1 has no
  armour-overlay mechanism; the inventory figure is one base
  sprite drawn once (index persisted at chargen, race/gender
  derived FROM it), gear renders only as item icons. Closed as a
  negative at the code level (section 6).
- **The capability permission-list populator** (B.2): the six
  entity-trigger lists are written by the GPL interpreter's
  trigger-opcode handlers through a sorted insert into the shared
  13-byte trigger table; lifecycle fully traced (section 3).
- **Bestiary special-attack/defense enums** (B.3): decoded on both
  sides from the consumer code (section 7).
- **Combat +8/+10/+12 "derived stats"** (B.4): dead persistence
  slots; no derivation exists; the "unreachable" 0x628 family is
  overlay 46 and fully named (section 8).
- **RBRN branch chunks** (B.5): resolved; see Phase A.
- **The 15503 icon bands and SPST default** (B.6): already
  modelled pre-campaign; nothing surfaced.

## Phase C: the corpus sweep (the gap list to zero)

- **DATA** is the DS2 spell-system file: 320 uniform 73-byte
  spell records (descriptor + names, ARMOR through the MONS
  summon placeholders) plus three auxiliary tables, byte-identical
  from floppy 1.0 to GOG 1.10 except exactly the official patch's
  5 bytes (port-digs-2026-10-06.md 1). Its 32-byte descriptor
  remains the one corpus datum documented as partially decoded
  (byte 0 histogram + confirm/refute tests are on record).
- **The never-shipped kinds**: all 21 (BMAP through TXRF) are
  closed by a full census over both GOG trees, saves included,
  every archive tree, and every zip member: none ever shipped as
  a chunk kind; three exist as code constants only (FVOC, STXT,
  CMAP); FORM exists only as the nested IFF marker inside *SEQ
  payloads (section 4).
- **Every non-GFF file is identified** (file-formats.md 4):
  STDPATCH.AD, GM1/GM2.BNK (Aria, not Roland), the UltraMID INI
  family, ITEMS.BIN, game.gog/game.ins (40 audio tracks, not 25),
  the PATCH.RTP family, the five FLICs.
- **Region-adjacent kinds** closed: MAP byte-verified across all
  60 shipped chunks; VECT is the 256-entry unit-circle table;
  CMAT/CPAL are the two BMA stills and their palettes; the
  save-kind quartet PLYL/ALL/GREQ/PREF decoded (PLYL a dead pre-CD
  playlist; ALL stale build digests that join the bestiary;
  GREQ/PREF the save-slot view and preference layouts)
  (port-digs-2026-10-06.md 5 and 9).
- **Symbols**: the Mel batch landed (ovr-map 0.3.6; 143 DS2
  locations, 135 verified, 14 DSO-sourced); the trigger-plumbing
  dozen landed 2026-10-06 (ovr-map 0.3.5); the DSO offset-mapping
  question was settled by disassembling mdark.bin itself
  (port-digs-2026-10-07.md 1).

## Phase D: recording

Everything landed the day it was proven: dated dig files
(port-digs-2026-09-20/21, 2026-10-06, 2026-10-07), the format docs
updated in place with corrected rows (file-formats, gpl-vm,
overlay-formats, object-formats, screen-flow, asset-bindings,
spell-effects, dsun-exe-re/survey, engine-quirks), the coverage
report regenerated at zero, roadmap boxes ticked, patchnotes per
release, CREDITS.md rows for ported logic, and the release post
(docs/mining-release-post-2026-10-06.md) plus five release pages.

## The closure pass (2026-10-07, mineout sessions 2-3)

The sweep's remaining hits went to verdicts via seven research
digs (docs/port-digs-2026-10-07.md): the GPL VM behavior holes
(Rand's Borland LCG and true range; Skillroll/Statroll formulas;
Menu's ring-push tail; Passtime's clock add; the stop-flag writer
census; the resume-path refutation), the VM data model (GNAME is
static; the stream selector; all six register producers; the DS2
Request arms corrected), the overlay-loader ledger (INT 3Fh
installer, base formula, buffer policy, word3 rules), the UI-mode
service named (GuiSetCursorMode), the DS2 item templates resolved
(weight, breakage threshold via the 'ALL '/4 engine table, range,
half-round attacks), the UI-lane residuals closed (automap is a
fixed whole-region BMP; 14002 is the quick-cast strip; the LEVEL
bar is the browse page; no per-spell memorization), and three
refutations (CBMP composition, the combat +24 icon label, the
Menu/accum mechanism). The same pass shipped darkfix-ds2 0.1.1
(ten more dead-trigger rows repointed on attested correlations;
the two -900 pickup rows closed with a corpus-wide no-handler
proof).

## The chunk-kind table (canonical GOG installs, per game)

Machine census over `.games/ds1` and `.games/ds2` (37 + 21 GFF
containers, one `gff-cat list` pass each; counts are TOC entries,
so segmented and interleaved chunks count every occurrence):

| FOURCC | DS1 chunks | DS2 chunks |
|---|---:|---:|
| `ACCL` | 54 | 0 |
| `ACF ` | 60150 | 0 |
| `ADV ` | 299287 | 165062 |
| `ALL ` | 0 | 59196 |
| `APFM` | 11252 | 11252 |
| `BMA ` | 2484342 | 0 |
| `BMP ` | 6148086 | 7068874 |
| `BUTN` | 16236 | 16183 |
| `BVOC` | 1472015 | 3039343 |
| `CBMP` | 0 | 1415572 |
| `CMAT` | 63011 | 0 |
| `CPAL` | 1536 | 0 |
| `CSEQ` | 152 | 78 |
| `DATA` | 0 | 24424 |
| `EBOX` | 1008 | 1176 |
| `ETAB` | 104224 | 108472 |
| `ETME` | 931 | 0 |
| `FNFO` | 0 | 1088 |
| `FONT` | 8299 | 8299 |
| `GFFI` | 120964 | 103272 |
| `GMAP` | 413952 | 250880 |
| `GPL ` | 877202 | 1462845 |
| `GPLI` | 6834 | 7896 |
| `GPLX` | 1269 | 0 |
| `GSEQ` | 212102 | 0 |
| `ICON` | 214387 | 117396 |
| `IT1R` | 2300 | 0 |
| `LSEQ` | 216496 | 0 |
| `MAP ` | 0 | 250880 |
| `MAS ` | 14566 | 18750 |
| `MERR` | 2078 | 1039 |
| `MONR` | 1218 | 1134 |
| `NAME` | 8050 | 0 |
| `OJFF` | 44400 | 71664 |
| `PAL ` | 42240 | 30720 |
| `PLYL` | 0 | 28 |
| `PORT` | 126774 | 684561 |
| `PSEQ` | 10992 | 0 |
| `RDAT` | 2205 | 0 |
| `RDFF` | 121818 | 160089 |
| `RMAP` | 413952 | 0 |
| `RNME` | 0 | 190 |
| `SCMD` | 47728 | 154936 |
| `SPIN` | 19753 | 29566 |
| `TEXT` | 579 | 3000 |
| `TILE` | 2206589 | 960096 |
| `VECT` | 1024 | 1024 |
| `WALL` | 298531 | 0 |
| `WIND` | 19077 | 19368 |

The eight kinds outside this table (CHAR, PSIN, PSST, SPST, GREQ,
PREF, FSEQ, CACT) live in the save/CHARSAVE surfaces and the
floppy lineage, not the shipped GOG trees; their layouts are in
file-formats.md 3.3/3.4 and the save-kind rows, and
format-coverage.md is the machine-generated corpus table (57
documented kinds, gap list empty).

## The audio inventory (summary; audio-cues.md is the detail)

- Music: DS1 23 tracks x (GSEQ + LSEQ) + PSEQ percussion + CSEQ
  1000 + 4 CINE themes; branch tables per track in RBRN; no DS2
  sequenced music.
- Samples: DS1 111 BVOCs, 56 of them never referenced by any
  script (engine-driven or dead; the ear pass names them); DS2
  704 BVOCs across the resource lineage, 127 ids script-referenced.
- The full DS1/DS2 sound tables (id, BVOC, sites, duration,
  context guess) are audio-cues.md sections 2.

## Proven NOT statically minable (the runtime-only list)

Each item below is closed as a written negative with the capture
that would settle it; none is a gap in the docs.

1. **The GPL complex-variable field numbering.** The grammar is
   VB in both games (gpl-vm.md 0xB1), but the field-offset,
   stride and datatype tables are built at runtime into BSS; no
   static image carries the concrete field ids. Capture: any
   session dumping the tables post-init (opcode-fuzz's rig).
2. **The prototype-table word0 fills per template**
   (asset-bindings.md 7): semantics proven, source is engine BSS
   written at object-load/reset; same capture class.
3. **The DS1 cast-counter filler** (port-digs-2026-10-07.md 8):
   who writes [0x4B08]/[0x4B11 + member*30 + level] at
   rest/level-up writes through computed pointers no static
   form-shape scan can pin. Capture: a watchpoint on DGROUP:0x4B08
   across one rest, or a before/after-rest played-save pair.
4. **DS1 music id -> context bindings**: no static cue exists
   (proved twice: `gpl music` never emitted, no engine table
   found); binding is by listening. The ear pass.
5. **The 56 never-scripted DS1 BVOCs**: engine-driven or dead;
   names come from the ear pass, not the data.
6. **The BSS-resident behavior list** (godot-port-readiness.md A,
   as amended 2026-10-07): walk speed, animation frame timing and
   scroll hysteresis, the cinematic tick rate, the ~35 unpinned
   status/effect bits, the morale-flee transition, loot creation
   inside the rec7 placement services, order kinds 2..9/12/14/16
   and the negated-kind encoding, region-load save/restore
   contents, and the small fry (DS2 rest handler body, the
   wild-talent draw, DATA:1002's consumer, the DS2 Tport twin's
   extra call, per-frame input-callback registration). Each needs
   one DOSBox capture; none blocks starting the port.

## What mining completion does not claim

- Not that the patches are done: darkfix-ds2 0.1.1 and
  darkfix-ds1 0.1.1 are early fixes; the mines-elevator headline
  and the DS1 final-battle family still stand
  (docs/known-bugs.md).
- Not that runtime behavior is captured: the list above is the
  honest boundary, and the played-save sessions and Phase 7
  live-install verification remain Brandon-gated.
- Not that the port exists: the zero-new-RE starting point is the
  one-region render spike (godot-port-readiness.md); the pits
  lock is Brandon's to lift.

*Sessions: the 2026-09-16/17 bestiary waves, the 2026-09-20/21
sweep and UI-parity days, mineout sessions 1-3 (2026-10-06/07).
Final state at commit time: coverage gap list zero, sweep clean,
every phase deliverable committed.*
