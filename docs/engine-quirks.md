# Engine quirks

Surprising behaviors of the Dark Sun engines that bit us during
RE / modding. Each entry: what happens, when we noticed, where it
matters for OpenDS tooling.

## 1. Stats above 25 produce +0 damage bonus

**What**: Setting a PC's STR (or DEX, presumably) above the
top of the D&D 2e exceptional-strength table causes the engine
to return a `+0` damage bonus instead of the expected high
bonus. The character sheet correctly displays the raw STR byte
value (e.g. 99), but combat damage doesn't reflect it.

**Noticed**: 2026-05-18 while editing Gerakis in Brandon's DS1
save. His stats all set to 99 displayed as 99 on the sheet,
but he did 1 damage per hit. The cached weapon was `1d1`; STR
99 → bonus +0; damage = 1d1 + 0 = 1.

**Why**: 2e's STR table tops out at STR 25 (with the
`18/00`-`18/100` "exceptional strength" sub-range from 18 to
19). The engine indexes that table by the STR byte. Above
the top index, the lookup likely returns 0 or hits whatever's
at that memory location (which evaluated to 0 in this case).

**Where it matters**:
- `ds1-party-edit.py` documents this in the cookbook.
- `save-inspect edit-pc` could grow a warning if a stat flag is
  > 25 (not implemented yet; pure docs for now).
- Modders who want "godmode": prefer editing weapon damage
  fields directly (`num_dice` / `num_sides` / `num_bonuses`)
  over inflating stats.

## 2. DS1 active party lives in DARKRUN.GFF, not CHARSAVE.GFF

**What**: `CHARSAVE.GFF` in DS1 contains 8 PC records that
**are not the active party**. The active party (e.g. Brandon's
Gerakis / K'ratchek / Cermak / Cilla) is stored inside
`DARKRUN.GFF` as records in `SAVE/5` (combat sub-blocks) and
`SAVE/6` (character sub-blocks).

**Noticed**: 2026-05-18 when `save-inspect list-pcs` on
Brandon's DS1 save returned 8 unrecognised names and the
modder said "those aren't my party."

**Why**: Speculation. The 8 records in DS1 CHARSAVE may be
character-creation templates, recruitable NPCs, or hard-coded
roster entries we haven't identified. Whatever they are,
they're not the active party.

**Where it matters**:
- DS1 active-party edits go through `ds1-party-edit.py`
  (DARKRUN-based), not `save-inspect edit-pc` (CHARSAVE-based).
- DS2 by contrast *does* keep its active party in CHARSAVE.
  `save-inspect edit-pc` works for DS2.
- `docs/file-formats.md` §3 documents the file-role split.

## 3. SAVE0N.SAV is byte-identical to DARKRUN.GFF at save time

**What**: When the engine writes a save (file menu → save),
the on-disk save slot file (`SAVE01.SAV` etc.) is a verbatim
copy of `DARKRUN.GFF`'s contents at that moment.

**Noticed**: save-inspect v0.6.0 (2026-05-16) on
DS2 played save; reconfirmed v0.9.x on DS1.

**Why**: The engine appears to use `DARKRUN.GFF` as the live
in-memory snapshot of world state, then writes it verbatim
to the chosen slot file on Save. On Load, the engine reads
the slot file into memory and (presumably) writes
`DARKRUN.GFF` back from the load.

**Where it matters**:
- Persistent save edits must hit BOTH files together; a write
  to only `DARKRUN.GFF` gets wiped on next reload because the
  engine reads from `SAVE0N.SAV`.
- `ds1-party-edit.py` writes both files automatically.
- `save-inspect roundtrip` works on either file directly
  (both are valid GFFs with the same content).

## 4. DARKRUN.GFF auto-overwrites on game launch

**What**: Launching `DSUN.EXE` overwrites `DARKRUN.GFF` (zeros
it out, or reverts to a fresh state) before any save is
loaded. Modders who edit `DARKRUN.GFF` and then start the game
without loading a save will lose their edits.

**Noticed**: `tools/repro/`'s overlay-mount discipline grew out
of an early loss of `DARKRUN.GFF` content on a non-overlay
DOSBox run. Documented in repro v0.1.0 patchnote.

**Why**: The engine probably initializes new-game state on
launch and writes it to `DARKRUN.GFF` as the starting point.

**Where it matters**:
- Always either use `tools/repro/`'s overlay-mount harness
  (DOSBox writes go to an overlay dir, not the install) OR
  load a save immediately after launch (which restores from
  `SAVE0N.SAV`).
- `ds1-party-edit.py`'s edits to `DARKRUN.GFF` only matter if
  the user loads a save before doing anything else; the
  `SAVE01.SAV` edit is the persistent one. The DARKRUN edit
  is essentially a hot-cache poison for the in-memory state
  on next load.

## 5. SAVE/5 records put NAME at offset 40, not offset 0

**What**: The 58-byte DS1 combat sub-block layout (per libgff's
`ds1_combat_t`) places the NAME field at byte offset 40 of
each record, not at the start. A naive scan of the chunk for
"Gerakis" returns offset 40 (the start of his name) but
treating that as the start of his record yields nonsense
field values and writes to the wrong PC.

**Noticed**: 2026-05-18 when Brandon's edit to "Gerakis's
stats" (computed from name-offset + 52..57) ended up setting
K'ratchek's stats to 99. The 6-byte slot 52..57 of "record
starting at Gerakis's name" is actually bytes 12..17 of
K'ratchek's record-1 header.

**Why**: libgff schema. Stats[6] at offset 34..39; name[18]
at offset 40..57. Records are 58 bytes. Records start at
SAVE/5 offset 0; names are 40 bytes into each record.

**Where it matters**:
- `ds1-party-edit.py` parses records by stride (58 bytes from
  chunk start), not by name search.
- `docs/file-formats.md` §3.3 documents the full layout.

## 6. The mines-elevator freeze: what we actually know

**What**: The famous late-game freeze: use the mines elevator in
Wake of the Ravager and the game can hang. As of the 2026-09-05
sessions the bug's site is located and named (census row in
`known-bugs.md` 3a), the mechanism has two live candidate shapes,
and one runtime capture closes the question. This entry is the
durable dossier; the Phase 7 site report assembles from it.

**The trigger chain**: MAS-57 (Mines2's master script) registers
`gpl usetrigger 3753, 287, NAME(-5807)`. NAME(-5807) is OBJEX
object 5807, sprite BMP 951: the rendered elevator shaft
(visually confirmed). GPL-287 handles the use: toggles GF[647],
plays sounds. Nothing in the 1.10 GPL corpus ever reads
GF[647-650] or GF[652]: the railhead switch states are dangling.

**The floors are not regions**: all mine floors are ONE region
(57, Mines2). The 17 `gpl tport` instructions in GPL-287 use the
32766 same-region sentinel with different coordinates: floor
changes are intra-region tports, not inter-region loads. Two call
pads (east 0x03f8, west 0x0494) set GNUM[139]=floor and
GNUM[140]=tick timer; the arrival tick dispatches to 14 floor
handlers via GNUM[139]. GPL request numbers decoded along the
way: 5=activate, 9=set state, 11=place, 37=operate elevator,
39=move elevator, 49=set quantity.

**Candidate A, the scheduler deadlock**: `0x100:0x2` is a
per-character text-mode writer inside the engine's cooperative
scheduler, not a per-record operation. The region-change sweep
calls it per record to write loading-progress text; its common
tail yields via `jmp 0xFFDE` (context save against a TCB). If the
scheduler fails to reschedule the calling task, the call blocks
forever: a freeze shaped exactly like the elevator's.

**Candidate B, the dangling switches**: the script toggles
GF[647]; no script issues the tport; the ride waits on a
transition nothing initiates. The sub-theory "the EXE reads
GF[647] and drives the tport" is DEAD (entry 7 below: the EXE
never reads individual GF flags). Live: the intra-region tport
path itself hanging, or the link living in the rebuilt 1.02-era
EXE segments we cannot yet compare function-by-function. Working
consequence: the fix is GPL-layer (add the missing tport to
GPL-287's handler); no EXE patching needed.

**The freeze window**: `gpl_disk_change_region` (DS2 ovr18+0x1132)
runs phase 1 (0x5b0:0xc0) -> one-shot sweep -> validators -> save
writer -> region id update -> the presentation orchestrator
(ovr18+0x1e63: speech prefetch, map draw, entry cinematics) ->
phase 2 -> cleanup. The orchestrator runs BETWEEN the save and
the load: a hang there freezes with the save written and the new
region unloaded. The relocation inside 0x5b0:0xc0 does int 21h
lseek/read/write on DARKRUN.GFF through a close/reopen handle
cycle: a hang there is file I/O against a missing or invalid
region, which a played-save pair shows directly as the
half-committed DARKRUN bytes at the freeze point. The 'Invalid
save' fatal is literally a save-validation failure on region
change.

**The capture recipe**: the record arrays are BSS (zero on disk,
populated during play), which is why static digging dead-ends.
The 37-byte records at DS:0x6874 (= 0x67bb + 5*0x25: the NPC
portion of the party-record array; records 0-4 = party, 5+ = NPCs,
indexed by region id, sweep range di=5..319) and the sibling
8-byte flag array behind the pointer cell DGROUP:0x67b7 (+0 x,
+2 y, +4 byte, +5 flags 0x20 active/0x40 dirty, +6 owner word)
serialize into the save files via the ovr18 trio (0x70b66 /
0x709b8 / 0x71099). So the cheap capture is a save just before
and just after the elevator ride: the save diff shows the flag
changes with no debugger. Debugger equivalent: write-watchpoint
on `DGROUP:0x6874+(id-5)*37+0x16`.

**The mines inventory**: regions 56/57/58 = Mines1/Mines2/Mines3
(the RGN files carry their own name strings); MAS chunk id equals
region id; the masters are instruction-identical 1.0 vs 1.10
after GF renumbering, so the freeze is not in the 1.10 delta.
Scripts GPL 76-85 plus GPL-287. Quest flags (GPL 76-79):
GNUM[58] bits (1=wheel, 2=car, 8=lock, 16=probe, 32=gas, 128=Blink,
256=miner dead, 4096=cover-up), GNUM[59] foreman stage, GNUM[60]
zone id, GNUM[61] fan bits, GF[125/126/189/191/193-198].
`gpl global sub 228, 27` = call offset 0xe4 in GPL chunk 27, a
bulk state reset (GBN[3], 13 GNUMs, 13 GFs) MAS-57 runs on every
Mines2 entry. NAME(-N) is a negative-encoded OBJEX object id
(NOT a string pool): GPL-81's NAME tports send NPCs/monsters to
Limbo (-74 Melody, -75 Wren, -77 Mug, -78/-79/-116/-117/-119
miners, -80 Zeegrat, -187 Winchester, -405 Umber Hulk, -416
Mindflayer, -526 Intellect Devourer); GPL-80's GNAME[38] tport is
Blick's own exit, not the party ride. Interactive objects
(OBJEX:BMP, all visually confirmed): 5801:402 rubble, 5802:405
coins, 5803:637 bulkhead, 5804:632 sluice, 5805:578/5806:577 ore
pair, 5807:951 elevator shaft, 5808:952 door, 5809:953 cart,
5810:954 loaded cart, 5811:955 rubble pile, 5812:956 trigger
marker, 5813:957 cave-in debris, 5814:958 pebbles, 5815:130
strut.

**Where it matters**: Phase 7's site report and fix; the
played-save-pair session design; `save-inspect`'s semantic
differ (the flag rows it will annotate).

## 7. GF flags are GPL-layer state; the EXE never reads them

**What**: No engine code reads an individual GF flag. GF access
is a bit array (byte N/8, bit N%8) at VM-segment 0x3c13:0x33b,
reached only through the generic runtime getter/setter (the index
arrives from bytecode at runtime) or whole-array save/restore.
Targeted scans for hardcoded 647-652 access: zero hits.

**Noticed**: 2026-09-05, hunting the elevator freeze's "the EXE
drives the tport from GF[647]" branch.

**Why**: the flags are a GPL VM resource; the engine treats them
as opaque bulk state.

**Where it matters**: a quest-flag fix is always a GPL-layer fix;
and no engine bug can be "waiting on flag N" except through the
generic path. Killed the EXE branch of freeze candidate B (entry
6).

## 8. GPLI-1: format decoded, purpose still open

**What**: GPLI-1 (7,896 bytes at file 0x1f8f7f, one per game) is
1,316 records of three little-endian u16s, no header:
(entry_no, entry_point_byte_offset, owning_gpl_chunk_id). Field A
is a permutation of 0..1315; sorting by A yields chunk ids in
perfectly non-decreasing runs, and every B is < the owning
chunk's size (verified all 1,316).

**Noticed**: 2026-09-05, chasing the mines NAME references.

**Why it is subtle**: one reading got published and retracted the
same day. "GPLI-1 is the `gpl global sub` dispatch index" is
WRONG: `gpl global sub P0, P1` means "call byte offset P0 in
chunk P1" (797/797 call sites land on decoded instruction
boundaries under the direct reading; 171/797 fail under the GPLI
reading, and entry numbers exceed 1315). The standing reading:
GPLI-1 maps dense entry numbers to real function starts, probably
an engine-side export table for some other lookup.

**Where it matters**: `file-formats.md`'s GPLI row now carries
the real layout; do not re-derive the dispatch-index theory (it
is falsified); the table is implementable in gpl-disasm if a
consumer appears.

## 9. DS1 has no region names

**What**: DS1 identifies regions by numeric id only; no name
table ships in the game. RDAT (45 records in RESOURCE.GFF) is
per-region binary config, not names (the file-formats "Names"
label came from libgff's guess annotation). DS1 regions contain
exactly {GFFI, ETAB, GMAP, RMAP, TILE}: no MAP, PAL, or RNME
(DS2-era additions).

**Noticed**: 2026-09-05, sweeping for a DS1 name table.

**Why**: DS1 predates the RNME mechanism; its palette comes from
the RESOURCE fallback and its region list is id-keyed.

**Where it matters**: any DS1 tooling that wants to show region
names must bring its own id-to-name map; `region-render`/`atlas`
labels for DS1 are a curation problem, not a data problem.

## 10. The DGROUP BSS map

**What**: The resident data group's initialized image ends and
its BSS begins at DGROUP 0x39c4 (file 0x509c4); BSS runs to
0xa570 (27,564 bytes), and the DGROUP image ends exactly at
(SS-DGROUP)<<4 + SP. Everything in that range is zero on disk and
populated at runtime, which is why static analysis of live state
(region id, party arrays, transition records) dead-ends and the
play-save/d debugger loop is the honest route.

**Named BSS variables** (established 2026-09-05): 0x55b8, 0x6578
(table body reached from 0x655e-0x6573), 0x67b7 (flag-array
pointer cell), 0x67bb (party-record array base), 0x67b9,
0x19c9 (97 refs), 0x36ff, 0x3b66, 0x3e80-0x3e83, 0x40a9,
0x40c0-0x40c4, 0x424e, 0x4261, 0x426d, 0x4689-0x468d (hottest
cluster), 0x4789-0x478b, 0x47c7, 0x5588, 0x5756, 0x5ec4, 0x5f8b,
0x60eb (current region, 24 refs), 0x6600, 0x6650, 0x669d.

**Noticed**: 2026-09-05, mapping the region-change state.

**Where it matters**: every watchpoint or instrumentation
address for live engine state lands in this range; the zero-on-
disk property is the reason `docs/engine-quirks.md` entry 6
prescribes save-diff or debugger capture instead of static
reads.

## 11. The DS2 GPL request dispatcher

**What**: The engine service behind the `gpl request` opcode maps
53 request numbers through a jump table at overlay file 0x8c487
(ovl 0x6c7). Requests 16, 42 and 43 are unimplemented (fall
through to nothing). Decoded members: 37 (elevator operate) has
three modes on (p1, p2); 33 is a camera/viewport setter (packed
x*1000+y coordinates, x16 scale, clamped to 2048x1568); 38 is
move/scroll to tile coordinates; 34 and 35 are mode-byte setters.

**Noticed**: 2026-09-05, reading the request path toward the
elevator.

**Where it matters**: any tool or patch that wants engine
services from GPL scripts can consult this map instead of
guessing request numbers; unimplemented requests are a trap for
mod authors (a script issuing 16/42/43 does nothing, silently).

## See also

- [`file-formats.md`](file-formats.md) §3: save-file layout
  details
- [`cookbook/edit-ds1-party.md`](cookbook/edit-ds1-party.md)
 : modder-facing workflow that touches all of these
