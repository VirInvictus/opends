# Audio routing: how ids become sound and music

The binding layer between engine ids and audio files, decoded (port-mining
wave 2, 2026-09-19). The file FORMATS are presentation-formats.md section 3;
this document owns the routing model a port's audio director reproduces.
Verified on the GOG 1.10 corpus. Addressing: DS1 resident file offset =
seg*16 + 0x5400, DS2 = seg*16 + 0x5200.

## 1. DS2 music: the DJ.DAT state machine (fully decoded)

File layout (`.games/ds2/DJ.DAT`, 231 bytes): `u8 num_records = 38`;
`u16 repick_delay = 1000`; 38 six-byte records; trailer `u16 slot_count =
35`. Record fields, pinned from the consumer code:

| field | values | meaning |
|---|---|---|
| A (+0) | 0xFF, 0x01, 0x38, 0x42 | region/context id the song themes; 0xFF = generic ambient pool. Context 56..58 clamp to 56 (RGN038/039/03A share a theme) |
| B (+1) | 10, 8, 5, 3 | playback probability in tenths via the gate at 0x1878:0x0d59 (10 = always; the 9-case is an off-by-one that also always fires; 8 = 90%; 1 = 20%) |
| C (+2) | 1, 2, 3 | combat subclass (state 3 only): three shuffle lists, selected by ranges <4 / 3..7 / >=8 |
| D (+3 word) | 1..3 | state class: 1 = explore/ambient pool (word == 1); state-3 records match the mode |
| E (+5) | 1..34 | song number for the DJ play service; slots 29, 32, 34 have two records each (38 = 35 + 3 probability/subclass variants) |

Consumer chain: loader 0x1878:0x007b (file 0x1D97B) opens "dj.dat",
mallocs count*6, stores the table at ds:0x424e (failure prints the "Wowo-
wowowowow... Mel DJ failed" string at 0x4da0b). State machine 0x1834:0x000c
(file 0x1D54C): globals [0x8bc] mode (0 idle, 1 play-one-then-hold, 2
stopped, 3 combat), [0x8ba] one-shot latch, [0x43f8] tick counter vs
[0x4253] (the header's 1000) before re-picking. Play wrapper 0x1878:0x04a5
-> 0x3a32:0x0011 (per-song enable flags at 0x3a32:0x217a + id, bit 2;
zero on disk, filler not found: a port can treat all as enabled) ->
0x37e5:0x01c4.

The universal music dispatcher 0x37e5:0x01c4 (file 0x3D214) reads the
device descriptor [0x3411] field +0x32 = driver class: 0 -> chunk `PSEQ`,
1/2 -> `FSEQ`, 3 -> `LSEQ`, 4 -> `GSEQ` (id = song number, via
load_resource); class >= 5 (the CD build) -> 0x37b9:0x0002 = MEL DJ
redbook play. The same dispatch shape (DS1 twin at file 0x33681..0x3371D)
is what makes the floppy line and DS1 work.

CD track mapping is inside MEL's CD layer (symbol names visible in
`.games/ds2/SOUND_DS.EXE`: _gMelNumberOfTracks, _gMelCurrentTrack,
trackNumber, start/end fudge factors): NOT statically pinned in DSUN.EXE.
Arithmetic hint: 34 gameplay songs + non-gameplay tracks = 41 = game.ins
(TRACK 01 data + AUDIO 02..41); test `track = song + 7` or `song + 1`
first with one capture.

DS2 has NO GPL music: the VM Music service 0x1d40:0x00b0f is literally
`push bp; mov bp,sp; pop bp; retf`. A port's DS2 music director = the
DJ.DAT state machine + the region-context table; ignore GSEQ entirely.

## 2. DS1 music: no static mapping exists (proved negative)

The GPL Music opcode (0x5F) handler is at file 0xB351 (dispatch-table-ds1
row confirmed); the service body (0x1a0a:0x672, file 0x1FB03) guards
[0x1162] (music toggle), caches the same id at [0x1671], then calls
0x35d1:0x0265 (MEL sequence play; second arg 5000). The seg:off pair
occurs EXACTLY ONCE in the image: the VM stub is the only caller. A full
gpl-disasm sweep of all 217 DS1 + 330 DS2 GPL chunks shows `gpl music` is
NEVER EMITTED in shipped bytecode of either game (while `gpl sound` fires
~600 times). There is no static region-to-song table in the EXE.

Consequence: DS1 music ids 1..23 (plus 26..29 cinematic, engine-driven
from CINE.GFF) must be bound to contexts by listening; the engine will
not contradict a port's choice. Renditions: the dispatcher picks the
FOURCC per driver class from device descriptor [0x3d04]+0x32 (PSEQ/FSEQ/
LSEQ/GSEQ push sites DS1 0x33681/0x336C5/0x336F1/0x3371D); one sequence
per song id, rendered per driver; select by config, not by id. ADV chunks
identified by embedded strings (Miles Design AIL, 1991/1992): 1 Ad Lib,
2 MT-32/LAPC via MPU, 3/4 PAS, 5 PC speaker, 6/7 SB, 8/9/11 SB Pro, 10
DIGPAK speaker, 12/13 Ad Lib Gold, 17 GUS, 18 UltraSound, 19 MT-32 (2nd),
20 Aria. GM1/GM2.BNK feed the MIDI TSR chain; STDPATCH.AD loads per the
embedded "stdpatch" strings (DS1 0x4C6E5, DS2 0x503F2).

## 3. SFX routing (pinned for both games)

DS2: sound id N -> BVOC chunk id N+1. The descriptor table 0x40c3:0x0d2f
holds 260 six-byte far pointers (ids 0..259, id 242 null) into 14-byte
descriptors whose every field derives from id+1. Resolver 0x37e5:0x02b6
(file 0x3D0C6): reads the descriptor; device config branch [0x3411+0x3a]
loads chunk 'BVOC' id word[desc+9] (or the FVOC foreground variant via
word[desc+6]) through loader 0x37e5:0x0378 -> load_resource 0x28ff:0x05b5,
played via MEL digital 0x3ab9. External fallback (file 0x22260): if the
BVOC load fails, `sprintf("%sSOUND%03u.VOC", path, id)`: GFF first, file
fallback, SAME NUMBER. Shipped SOUNDnnn.VOC files cover 30 gap ids.
Dead rows: ids 231..239.

Speech (same module, file 0x1D0EA): guards [0x13f7]/[0x14e3]/[0x14e4]/
[0x1439]; id < 50 -> `%c:\INTR\INTR%u.VOC` on CD; id >= 50 ->
`%sSPCH%u.VOC` local, else `%c:\SPEECH\SPCH%u.VOC` on CD. Shipped SPCH
ids: 50..165, 200..213, 300. Speech ids are dialog-side, a separate space
from Sound.

DS1: parallel older structure. Sound service 0x1a0a:0x0663 (guards
[0x1162], id 0xFF = no-op, [0x11a8] audio-ready) -> 0x3172:0x04F1 (device
checks, PC-speaker branch on device word 0x68) -> 0x3172:0x0573: per-id
6-byte records in the runtime table at 0x3a98:0x08A3 -> descriptor ->
BVOC/FVOC load. DS1 BVOC ids 1..130 (111 present; 19 gap ids are dead in
the GOG resource); GPL Sound args observed 1..130: IDENTITY MAPPING
(sound id = BVOC chunk id). The MEL data area carries ".VOC"/"PC"/"%d"
external-fallback templates, never fired by the shipped install.

Known/likely contexts: sound 7 = combat miss (combat-flow.md); DS1 id 72
is the most emitted (~50+ sites: almost certainly the generic UI blip),
then 53, 4, 26, 30, 59, 62, 92, 76; DS2's most emitted: 221 (~15 sites,
likely UI/abort), then 8, 12, 7, 40, 30, 34/35/41 (combat-heavy chunks).
Exact per-effect names are a listening pass.

## 4. Service entry points (the stub chain)

| link | DS1 | DS2 |
|---|---|---|
| GPL Sound (0x5D) handler | file 0xB33B | service 0x1d40:0x00b00 |
| GPL Music (0x5F) handler | file 0xB351 | NO-OP (retf stub) |
| Sound resolve/play | 0x1a0a:0x0663 -> 0x3172:0x04f1 -> 0x3172:0x0573 | 0x37e5:0x02b6 -> 0x37e5:0x0378 |
| Music dispatch (per-driver FOURCC) | 0x33681..0x3371D sites | 0x37e5:0x01c4 |
| DJ (CD music) | none | loader 0x1878:0x007b; state machine 0x1834:0x000c; mode setter 0x1834:0x0001; prob gate 0x1878:0x0d59; play 0x3a32:0x0011; stop 0x3a32:0x0185; CD play 0x37b9:0x0002 |
| VOC file layer | MEL-internal templates (unused) | sound 0x1D060; speech 0x1D0EA; sprintf 0x2150:0x000e; exists 0x46bd:0x0034; play-file 0x3611:0x0177; stop-speech 0x46ef:0x00f7 |

Volume/loop policy: DS1 Music passes a fixed 5000 second word (scale
unknown); the DJ state machine owns looping (pick -> play -> hold ->
re-pick after 1000 ticks, with field B as the variety gate and same-id
caches preventing restarts); combat music = mode 3 + subclass argument.
Fine looping lives inside MEL/AIL, invisible at this boundary.

## 5. Open items

1. DJ song number -> CD track (inside MEL's CD module; one capture or a
   game.gog TOC parse settles it).
2. DS1 music id -> context (no static table exists; played-capture or
   manual binding).
3. The DS2 per-song enable flags' runtime writer (BSS-filled; port can
   ignore).
4. The FVOC "foreground" trigger condition ([0x3411+0x3a] device flag).
5. Which overlay callers set DJ mode 1 vs 3 and the combat subclass
   argument (the state machine itself is fully decoded).
