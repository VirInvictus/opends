<!-- The release post for the mining-completion-2026-10-06 batch;
mirrors the body of the GitHub Release
https://github.com/VirInvictus/opends/releases/tag/mining-completion-2026-10-06 -->

# The mining release: a guide to the documents

This release posts the annotated inventory of OpenDS's static-mining
campaign: every document the campaign produced or rewrote, tagged,
described, and explained. The campaign's assignment was to mine SSI's
Dark Sun CRPGs (Shattered Lands 1993, Wake of the Ravager 1994)
until nothing was left to dig: every chunk kind documented with
offset-level evidence, every named reverse-engineering hole resolved
or closed as a written negative. The bar was mechanical, and it is
met: the format-coverage gap list is empty, 57 of the 78 catalogued
chunk kinds appear in the corpus and every one of them is documented,
and the other 21 are proven never to have shipped as
chunk kinds in any held artifact.

Two things make this batch trustworthy rather than merely voluminous.
First, every document cites its evidence: file paths, byte offsets,
instruction dumps, and corpus counts that anyone with the GOG install
can re-derive. Second, before release, four independent
claim-verification passes re-ran the corpus counts, re-decoded the
cited bytes and tables, and re-executed the tools from scratch. They
confirmed every headline finding and caught eleven wrong secondary
details (a converter bug that failed 41 of 83 music files, a sample
rate generalized from half the corpus, a song pool off by one, two
miscounts, three offset slips, and a version bump that never reached
the build file). Everything below reflects the corrected state. Where
a claim is still open or a guess, the document says so in those
words; this guide preserves those flags.

All documents live in the repo at the tag this release points to;
links below resolve to that exact tree.

---

## The inventory (every mined document, tagged)

| Document | Tags | One line |
|---|---|---|
| [`docs/port-digs-2026-10-06.md`](../../blob/mining-completion-2026-10-06/docs/port-digs-2026-10-06.md) | NEW · dig record | The campaign's lab notebook: ten sections, one per closed question, each with the decisive offsets. |
| [`docs/audio-cues.md`](../../blob/mining-completion-2026-10-06/docs/audio-cues.md) | NEW · audio | Which script requests which sound: 684 call sites across both games, with durations and context-derived meaning guesses. |
| [`docs/format-coverage.md`](../../blob/mining-completion-2026-10-06/docs/format-coverage.md) | NEW · regenerated | The completion bar itself: machine-generated, gap list empty, 57/78 kinds in corpus. |
| [`docs/file-formats.md`](../../blob/mining-completion-2026-10-06/docs/file-formats.md) | EXTENDED · CORRECTED | The format reference. Twelve new or rewritten sections; two long-standing claims corrected. |
| [`docs/audio-routing.md`](../../blob/mining-completion-2026-10-06/docs/audio-routing.md) | CORRECTED | The id-to-sound routing model; DJ.DAT's layout description fixed. |
| [`docs/object-formats.md`](../../blob/mining-completion-2026-10-06/docs/object-formats.md) | EXTENDED · CORRECTED | The record layouts; the combat block's special-attack machinery resolved on both sides. |
| [`docs/rules-tables.md`](../../blob/mining-completion-2026-10-06/docs/rules-tables.md) | EXTENDED | The AD&D-rules layer; the derived-stats question closed and overlay 46 named. |
| [`docs/bestiary-ds1.md`](../../blob/mining-completion-2026-10-06/docs/bestiary-ds1.md), [`docs/bestiary-ds2.md`](../../blob/mining-completion-2026-10-06/docs/bestiary-ds2.md) | CORRECTED | The per-creature catalogues; their "enum candidates, not shown" era ends. |
| [`docs/spell-effects.md`](../../blob/mining-completion-2026-10-06/docs/spell-effects.md) | EXTENDED · CORRECTED | The spell engine; gains the corrected special list and DS2's fire gate. |
| [`docs/combat-flow.md`](../../blob/mining-completion-2026-10-06/docs/combat-flow.md) | EXTENDED | The combat loop; the "behind the frame wall" note resolves into named code. |
| [`docs/screen-flow.md`](../../blob/mining-completion-2026-10-06/docs/screen-flow.md) | CORRECTED | The screens; the 14-byte PREF claim fixed at 11/9 bytes. |
| [`docs/exploration-flow.md`](../../blob/mining-completion-2026-10-06/docs/exploration-flow.md) | CORRECTED | The movement layer; the trigger-table cells are list heads, not function pointers. |
| [`docs/dso-symbols.md`](../../blob/mining-completion-2026-10-06/docs/dso-symbols.md) | EXTENDED | The Dark Sun Online symbol index; coverage snapshot and the adoption ledger. |
| [`tools/audio-extract/`](../../blob/mining-completion-2026-10-06/tools/audio-extract/) | NEW · tool v0.1.0 | Opens every audio box: WAVs, payload dumps, inventories, and the cue sweep. |
| [`tools/xmi2mid/`](../../blob/mining-completion-2026-10-06/tools/xmi2mid/) | NEW · tool v0.1.0 | Branch-aware XMI-to-MIDI conversion with the adaptive-music sidecar. |
| [`tools/gff-edit/`](../../blob/mining-completion-2026-10-06/tools/gff-edit/) | tool v0.6.3 | The container foundation; its kind catalogue now matches the corpus exactly. |
| [`tools/ovr-map/`](../../blob/mining-completion-2026-10-06/tools/ovr-map/) | tool v0.3.5 | The overlay mapper; twelve new verified DS1 symbols from the trigger digs. |

---

## Part 1: the maps (start with these three)

### `docs/format-coverage.md`: the completion bar, zeroed

Every Dark Sun data file is a GFF container: a table of contents
listing chunk types by FOURCC, then the chunks themselves. The
campaign's mechanical bar was that a machine-generated report,
`format-coverage.py`, finds no chunk kind in the shipped games that
our documentation does not describe. This release regenerates that
report against a 78-kind catalogue: 57 kinds appear in the corpus and
all 57 are documented; the other 21 are the subject of Part 4 below.
The report also pins the corpus itself: 120 GFF containers across the
GOG installs and the Internet Archive release-lineage trees, and 584
other files (binaries, patches, media) accounted for. When someone
asks "is there anything left to dig?", this file is the answer, and
the answer is no.

### `docs/port-digs-2026-10-06.md`: the lab notebook

Ten sections, one per closed question, each written the day the dig
concluded and each carrying its decisive evidence (the instruction
bytes, the table dumps, the caller chains). It is the document to
read when a summary here is not enough. In order:

1. **DATA** (the DS2 spell-system file, below in Part 3).
2. **RBRN** (the adaptive-music tables, Part 2).
3. **The capability lists** (the steal/talk/give machinery, Part 4).
4. **The never-shipped census** (Part 5).
5. **The wave-2 kind decodes**: MAP, VECT, CMAT, CPAL (Part 3).
6. **Armour overlays, disproven** (Part 4).
7. **The bestiary special-attack enums** (Part 4).
8. **Combat +8/+10/+12 and overlay 46** (Part 4).
9. **The save-kind quartet**: PLYL, ALL, GREQ, PREF (Part 5).
10. **Session state**, the running index.

### `docs/file-formats.md`: the reference itself

The document a tool author actually reads. This release adds twelve
sections and corrects two claims. The additions: DATA (Part 3), VECT
(the 256-direction circle, Part 3), CMAT and CPAL (the DS1 still
frames and their palettes, Part 3), PLYL / ALL / GREQ / PREF (Part 5),
the full XMI container hierarchy with the adaptive-music machinery
(Part 2), the BVOC payload structure (Part 2), the never-shipped
census (Part 5), and the measured identifications of every external
file (Part 5). The corrections: the old text claimed XMI delta times
were "two bytes per event"; the corpus says they are runs of bytes
under 0x80 summed up to the next status byte. And the old audio
presence table implied all samples were 8000 Hz; the corpus holds two
rates (Part 2).

---

## Part 2: the audio documents (sound, music, and the machinery that plays them)

### `docs/audio-cues.md`: who asks for which sound

The games play sounds two ways: the script VM requests them by id
(`gpl sound`), and the engine fires some by itself (UI clicks, combat
resolution). This document is the complete map of the first kind. A
sweep of the disassembled bytecode found 251 sound requests in DS1
covering 55 distinct ids, and 433 in DS2 covering 127 distinct ids
plus one computed at runtime, all of them in each game's GPLDATA.GFF.
For every id the table gives: the matching digital-sample chunk (DS1
sound id equals its BVOC chunk id; DS2's mapping adds one), its
duration, how many scripts call it, and a meaning guess derived from
the strings the calling script prints nearby ("bashes down the door!",
"Soldiers, cover my retreat!"). Three facts fall out: `gpl music` is
never emitted in either game, so music ids have no static binding
(the engine will not contradict whatever a port chooses); four
scripted DS1 ids point at samples that do not ship (19, 30, 87, 127:
those call sites are silent in a stock install); and 56 of DS1's 111
samples are never script-referenced at all, meaning they are engine-
driven and their naming needs the planned ear pass. Every meaning in
the table is labelled a guess; the ear pass remains the confirmation
step.

### The BVOC facts (`docs/file-formats.md`, BVOC section)

The 815 digital-sound chunks across every release decode completely:
499 samples at 8000 Hz and 316 at 10989 Hz (the 10989 set is DS2's
resource file and its byte-identical CD twin), all 8-bit unsigned
mono, 1386.9 seconds total, zero failures. Each payload is a
well-formed Creative Voice File with exactly one sound-data block;
two carry repeat markers. The tool behind this is `tools/audio-extract`
(v0.1.0), which also produced 815 WAVs and a machine-readable
inventory.

### The music: XMI, RBRN, and the adaptive loop (`docs/file-formats.md`, XMI section; `port-digs` 2)

Each music chunk is an XMI: a FORM/XDIR directory wrapping a song
form of TIMB (patch requests), RBRN (branch points), and EVNT (the
events). The headline: **DS1's music is adaptive at runtime.** 63
branch tables ship (one per sequence kind for every track except the
two short cues 7 and 17); each table's entries match one-to-one with
Sequence Branch Index events in the song; the engine's embedded Mel
library (the version string "Mel Real Mode Version 2.0.9b, 08/30/93"
sits in DSUN.EXE) wraps each song in FOR/NEXT loops and re-enters at
whichever branch point the game selects. This is live machinery, not
a dormant dialect feature, and it is exactly what a port's music
director must reproduce. DS2 ships no RBRN at all: its floppy builds
carried plain MIDI music (18 of GSEQ 1..20 plus 17 of FSEQ 1..19),
and the CD build replaced music with redbook audio.

`tools/xmi2mid` (v0.1.0) converts every sequence chunk to a standard
MIDI file at 120 Hz plus a JSON sidecar carrying the branch tables,
loop spans, and patch lists. The classic public-domain converter
flattens all of this away (it skips every non-event chunk); this one
keeps the linear song playable in any sequencer and hands the
adaptive behaviour to the port as data. All 83 DS1 sequences and all
36 floppy-tree DS2 sequences convert. Conversion also pinned two
undocumented container quirks, now in the format reference: the
XDIR's declared size covers only its INFO block, and EVNT streams may
carry pad bytes after their end-of-track marker.

### `docs/audio-routing.md`: corrected

The routing model (which service answers which id, and through which
chunk kind) was already decoded; this release fixes its DJ.DAT
description: the 231-byte file is a header plus 38 six-byte records
filling it exactly, with no trailing field (the "trailer slot count"
an earlier revision described was the last record's own tail), and
its state-3 combat pool is ten songs, ids 1..10.

---

## Part 3: the data documents (what the shipped files hold)

### DATA: the DS2 spell system is a file (`docs/file-formats.md`, DATA section; `port-digs` 1)

The largest gap in the old coverage report, 1,292 chunks, turned out
to be one file shipped four times: DS2's RESOURCE.GFF and its floppy/
HotU/CD twins carry 323 DATA chunks each. Ids 0..319 are uniform
73-byte spell records: a 32-byte binary descriptor, a 32-character
long name, and a 9-character short name, running from ARMOR and
BURNING HANDS through the alphabetized wizard, cleric, and
psionicist lists, ending in 51 summoned-monster placeholders
(MONS269..MONS319). Ids 1000..1002 are auxiliary tables (level-up XP
ramps, a sparse flag matrix, an XP pair table). Every release from
floppy 1.0 through GOG 1.10 ships them byte-identically except for
exactly five bytes, and those five are the official 1.10 patch's own
work: PRAYER's descriptor byte 1 becomes 20, and a broken XP
progression is repaired. The descriptor bytes themselves are not yet
decoded; the document says so and gives the tests that would settle
it. The payoff: a port can generate its spell table from this file
instead of transcribing the cluebook by hand.

### The wave-2 kind decodes (`docs/file-formats.md`; `port-digs` 5)

- **MAP** (the DS2 background tile grid): already documented, now
  byte-verified across all 60 shipped chunks. Every cell is a valid
  tile id in its own file, the layer is independent of the wall map,
  and the loader requests it by name between the other two grids.
- **VECT**: a 1024-byte lookup shared byte-identically by both games:
  256 (x, y) step vectors forming the unit circle at radius 256, the
  direction table behind the engine's 256-angle convention (loaded
  explicitly by both executables; whether it serves movement or
  aiming is flagged open).
- **CMAT**: two DS1-only still images (320x200 and 318x198) in the
  cinematics' own codec, each walking byte-exact to its final byte,
  each paired with a **CPAL** palette in the standard palette format.
  What the two pictures depict is open (they render, but nothing yet
  names them).

### `docs/dso-symbols.md`: the name index, measured

Dark Sun Online shipped debug symbols for the same codebase, giving
us 3,527 function names as cross-references (offsets do not transfer;
every adoption needs per-function verification). This release adds a
coverage snapshot (132 DS2 locations named by us, 3 with verified DSO
names) and ships twelve new verified DS1 symbols in `tools/ovr-map`
v0.3.5: the capability machinery and the trigger-table plumbing named
function by function.

---

## Part 4: the engine documents (how the machine actually behaves)

### The steal/talk/give lists are data, not mysteries (`port-digs` 3; `exploration-flow` corrected)

Why can you talk to this creature but not steal from that one? The
answer is a table the scripts write: the GPL trigger opcodes (pick
up, talk, attack, look, use, use-with) each append a 13-byte record
naming a creature to a per-action list, and the examine window lights
its buttons by walking those lists. A baseline set is registered from
a global script at session start; anything a region's scripts add is
stripped when you leave. The full record layout, allocator, and flush
order are in the dig, and twelve of these functions are now named in
the ovr-map catalogue. For a port this is the best possible answer:
engine-true capabilities fall out of one data structure.

### Armour overlays do not exist (`port-digs` 6; a negative result)

The mining prompt asked where the worn-gear overlay art lives. The
verified answer: nowhere. The paperdoll figure is a single sprite
chosen at character creation from a stored index; equipping anything
never redraws it; and no art outside the fourteen base figures is
referenced anywhere in the executable. Gear renders exclusively as
icons in the fourteen equipment cells. The dig also settled how the
index works, with a twist: the stored index is primary, and race and
gender are derived from it at creation (index 13 is the extra race,
K'tarchek; one race/gender combination has no art). Any gear-on-
figure rendering in a port would be an invention, not parity.

### The bestiary's secret bytes, decoded (`port-digs` 7; `object-formats`, `bestiary-ds1/2` corrected)

The creature catalogues used to say "special-attack bytes are enum
candidates and are not shown." Both sides are now decoded. DS1: the
combat block carries a word whose low byte indexes a capability
bitmask table inside the executable; eleven of its bits fire probe
attacks at 25 percent per round, named through the game's own power
table (FIREBALL, two breath weapons, HOLD PERSON, DETONATE, FEAR, a
poison bite, ranged innates), and one special value (41, carried only
by the mage Balkazar) means "casting blocked." The old "DISPEL MAGIC"
label was off by one; the corrected target is FIREBALL. DS2: the low
byte selects through four phase-keyed jump tables with per-creature
fire conditions (the drakes breathe only below half health; the
disguised yuan-ti always poison; the Mindflayer's mind blast always
fires while unengaged), and the high byte indexes a two-table
defense profile: an immunity table (damage becomes zero) and a
halving table consumed only for the first seven profiles. Each
creature's special is now nameable per row.

### Combat +8/+10/+12: closing a hole by emptying it (`port-digs` 8; `rules-tables` 5)

One hole had resisted three campaigns: what derives the combat
block's +8/+10/+12 "derived stats," computed (the old note said)
behind runtime-resolved segments. The exhaustive re-decode found no
derivation because there is nothing to derive: the three words are
ready/weapon/pack item-index slots that both engines only ever clear
to 9999 and never read (real weapon state lives in a separate
belt/scheduler structure, fully traced). The "unreachable" family is
overlay 46, resolved through the overlay table and named stub by
stub: it computes usability, base HP, class count, PSP, THAC0, saves,
and level-ups, and never touches these fields. The nonzero values in
shipped save files are SSI authoring-session residue pointing outside
the 400-row arrays: inert, and documented as carry-through-untouched.

---

## Part 5: the saves, the dead data, and the census

### The save-file kinds (`port-digs` 9; `file-formats` GREQ/PREF sections)

`GREQ`: ten 9-byte chunks in each DS2 save, one per save slot
(chunk id = slot + 1), holding the saved camera scroll bounds in
region pixels plus a picture index into a 25-per-page art pool,
with the writer and reader functions cited (including the engine's
own quirk of reading one byte past the buffer). `PREF`: the
preferences screen's persisted state, 11 bytes in DS1 and 9 in DS2,
byte-mapped field by field from the writer code; the old note
claiming 14 bytes is corrected.

### The dead data (`port-digs` 9; `file-formats` PLYL/ALL sections)

Not everything shipped is alive. `PLYL` is a playlist of (song, flag)
pairs whose nine songs are a subset of DJ.DAT's ten-song combat pool;
no executable in any release lineage references the chunk type, so
it is a frozen pre-CD leftover and a port should not read it. `ALL`
is five fixed-stride digest tables inside the object database,
unreferenced by either engine: creature summaries that join our
bestiary on all 352 rows (AC, name, THAC0), named-special tables,
and three partially decoded aggregates. They are documentation-grade
snapshots of SSI's build process, and the docs say to treat them as
such.

### The never-shipped census (`port-digs` 4; `file-formats` census section)

The catalogue names 78 chunk kinds; 57 ship. The other 21 were swept
everywhere we hold material (both installs, every archive tree, every
zip member, checked as directory entries, as chunk markers, and as
file magics): none ever shipped. Three survive only as code constants
inside DSUN.EXE (the engine could load FVOC foreground sounds, STXT
save text, and CMAP color maps; SSI never shipped one), one (FORM)
exists only as the IFF marker inside music chunks, and the remaining
seventeen leave no trace anywhere. The same sweep confirmed no save,
XMI, or standalone MIDI file ever shipped either, and it produced the
external-file identifications now in the format reference: the AdLib
patch table's full layout (232-entry directory plus 233 timbre
blobs), the two DS1 banks as Aria (not Roland) patch sets, ITEMS.BIN
as 234 id pairs, the CD image as a raw Mode 2 sector dump of volume
WAKE1_0, the 40-track audio mapping, and the five FLIC cinematics
with their frame counts.

---

## The tools (how to re-derive all of this)

- `tools/audio-extract` 0.1.0: dumps every audio chunk kind from any
  GFF container; BVOC/FVOC decode to WAV, sequences dump verbatim,
  and the inventory JSON reconciles every published count. Its cue
  sweep produces the raw evidence for audio-cues.md.
- `tools/xmi2mid` 0.1.0: every music chunk to standard MIDI plus the
  adaptive-music sidecar.
- `tools/gff-edit` 0.6.3: the container foundation; its chunk-kind
  catalogue now registers all ten newly documented kinds, which is
  the mechanical act that drove the coverage report to zero.
- `tools/ovr-map` 0.3.5: twelve new verified DS1 symbols from the
  trigger digs, plus five corrected addresses.

Each tool's selftest runs without the games and executes in CI; the
corpus-dependent checks skip gracefully when the installs are absent.

---

## What remains, stated plainly

Three things keep this from being the campaign's final page. The
ear pass: naming DS1's music by listening and identifying the
56 engine-referenced samples, which needs human ears and is
Brandon-assisted by design. The open-question sweep: 25 flagged
lines across the older documents, each to be driven to a resolution
or a written closure (the new documents carry none). And
`docs/mining-complete.md`, the campaign's final record, written when
those two land. Until then, this release is the complete, verified
map of everything the games ship, and the documents above are the
map's legend.
