# Engine-side asset bindings: icons, portraits, palette cycling, CBMP

How the engines bind content records to image chunk ids (port-mining wave
1, 2026-09-19). These bindings were the "Open" items in
presentation-formats.md section 2; this document supersedes that paragraph.
All offsets are file offsets in DSUN.EXE (DS1 = `.games/ds1/DSUN.EXE` 611,408 B;
DS2 = `.games/ds2/DSUN.EXE` 634,416 B, "DS2.EXE" in older docs). The GFF
read helper everywhere below is 0x0100:0x04a4 (DS1) / 0x0128:0x04ab (DS2),
signature approximately (far ptr to handle, id:i32, fourcc:u32); see
overlay-formats.md for the corrected file targets of those entries.

## 1. Item icons: icon = OJFF bmp_id (SOLVED)

An item's inventory ICON id is the `bmp_id` field (+12, u16) of the OJFF
record of the item's BASE OBJECT: numerically the same id as the item's
world sprite, read from the ICON chunk type. Computed once per item
template and cached. IT1R has no icon column, exactly as the docs
suspected; the icon comes from the OJFF layer.

The chain (identical algorithm both games):

1. `compute_icon(template_index)`: DS1 file 0x72B47, DS2 0x7B26F.
   `ax = template_index * 0x15` (DS1 stride 21) / `* 0x17` (DS2 stride 23)
   into the engine's item-prototype table (`[0x165d]` DS1 / `[0x19c1]`
   DS2); `ax = -word[es:bx+0]`: the row's first word is a NEGATED OJFF id
   (the NAME(-N) convention). Reads OJFF chunk ax into a 16-byte buffer;
   returns buffer+12 (bmp_id), or 0 on read failure.
2. The inventory icon builder (DS1 0x71088..0x71150) loops the 27 display
   slots (`cmp si,0x1a`), calls compute_icon, caches the result into the
   prototype row at +0xC (DS1 0x71109; cleared on template reset 0x59EC9;
   DS2 same offset), then reads `ICON <id>` into a 4-byte out record.
3. The prototype tables are engine-owned BSS: DS1 400 rows x 21 B
   allocated at 0x6A48C (row+4 init 1..400, last row +4 = 9999 sentinel),
   DS2 400 x 23 at [0x19c1]. Row word0 = -(base-object OJFF id), written
   per template at runtime (e.g. `mov word [es:bx],0xFB46` = -1210 at DS1
   0x59EDA).

Corpus validation (python parse of SEGOBJEX/OBJEX + RESOURCE): all 2,775
DS1 / 4,479 DS2 OJFF bmp_ids fall in the BMP id set, and the BMP-id
intersection with ICON ids is 29 ids in DS1, exactly the ICON 2000-family
(2000, 2002-2009, 2038-2051, 2057, 2058, 2090, 2093, 2097): the DS1 item
icons are precisely the items whose world-sprite BMP id doubles as an ICON
id. DS2's intersection is only 7 ids (100, 2007, 2038, 2041, 3045-3047):
DS2 kept the mechanism but most item sprites have no same-id ICON, so
those render iconless by this path.

## 2. Spell icons: 20999 + spell_id (SOLVED)

- DS1: `mov ax,[bx]; add ax,0x5208` (=21000) at 0x71007; `+0x5208` again
  at 0x85681; selector at 0x897D0: list type 1/2 -> base + 21000, type 3
  -> +3000. Corpus fit: ICON run 21000..21137 = 138 chunks = the SPST
  spell-id space 1..138; the DS1 "3000-family" (45 icons, 3000-3106)
  serves list type 3.
- DS2: `+0x5208` at 0x7958F and 0x93298; a second family adds 0x52F3
  (21235) at 0x795EF, 0x8AEF3, 0x93EA4/0x97967. Corpus fit: ICON run
  21000..21268 = 269 chunks = exactly DS2's 269 SPIN ids 1..269 (offset 0
  = spell id 1). 34 of DS2's 21235..21268 window matches the 34-power
  psionic list; the family's exact per-row key (likely class/skill/
  psionics tabs) is inferred, not proven.

## 3. Portraits: PORT id is a dialog-service operand (SOLVED)

`SetPortrait(id)`: DS1 file 0x7DE1A, DS2 0x88DA2. The argument IS the PORT
chunk id; id != 0 reads PORT through the GPLDATA.GFF handle context (ds:
0x5739 DS1 / 0x6558 DS2; GPLDATA is the only PORT carrier: DS1 ids 112,
DS2 178). id == 0 is a clear/default path (BMP 12000 probe). The last id
is cached (ds:0x1F0F / 0x25BD). `GetPortrait` (DS1 0x7DEDF, DS2 0x88E67)
re-loads on cache mismatch; its only callers are the dialog module (DS1
0x7CF4D/0x7D0E5/0x7D2BF; DS2 0x87C7E/0x87EEC/0x88163). The live call site
is the dialog display service (DS1 function at 0x7CE83): a command
dispatcher whose cases take (command, far string ptr, portrait id at
[bp+0xC]); the string cases append into the 10 x 51-byte dialog-line
array at ds:0x5537. So the portrait id is PER-DIALOG-LINE state sourced
from the GPL dialog opcode arguments at runtime (gpl-vm.md's 0x4F/0x50/0x51
print family: the style/portrait word travels in that argument block,
reached via the VM stub table, which is why no static near/far caller
exists). A port models it as dialog-line state, not a record field.

## 4. DS2 palette cycling: none (confident negative)

Both engines own the identical cycle pump + API: DS1 segment 0x22F8 (file
base 0x28380), DS2 segment 0x2796 (file base 0x2CB60). StartCycle
0x28707/0x2CEE7, StopCycle 0x2873F/0x2CF1F, pump 0x287FC/0x2CFCDC,
setdacrange 0x28894/0x2D074 (confirming dsun-exe-re.md 4.5.6's DS2
addresses). The pump is MAIN-LOOP POLLED in both games, not purely
task-scheduled: DS1 tick 0x25D18 sets word [0x1194] every 8th tick; main
loop 0x1A93C polls and calls the pump. DS2 tick 0x2A1A7 sets byte [0x1424]
every 8th tick; main loop 0x1CF15 polls and calls 0x2796:0x047C.

Registration: DS1 has exactly four boot StartCycle calls at
0x1CECF..0x1CF0B (the known ranges). DS2's static surface is exhausted:
no far calls or pointers to the segment's cycle entry points anywhere; the
only `mov ax,0x2796` in the image (0x1CA5F) writes a cheat-command gate
byte. The 16x8 range table is zero on disk and has no writer. VERDICT: DS2
ships the machinery but nothing ever registers a range, so the pump is a
no-op: DS2 has NO effective palette cycling. A port implements the pump +
DS1's four boot ranges only (region-render 0.8.0 already decodes those).

## 5. CBMP: same id space as BMP, selected by a boolean (SOLVED)

`LoadCreatureBitmap(id:word, use_cbmp:byte)`, DS2 file 0x2A568: the byte
argument selects FOURCC 'CBMP' vs 'BMP ' directly; no table. Maintains a
300-entry x 16-byte cache (0x42A2:0x0CA8, count ds:0x265D, entries {+0
id:u16, +2 handle:dword, +0xE flags}, flag bit 2 = CBMP). Its caller
0x2A388 (sprite/animation setup; near callers in the animation engine at
0x28BCF..0x29B42, far callers 0x21E0:0x3388 and 0x26F29) passes the flag
through after picking frame/state data. Corpus: DS2 CBMP ids all fall
inside OBJEX BMP id runs; creatures ship BOTH `BMP <n>` (normal sprite)
and `CBMP <n>` (colour-map anim) for the same n. DS1's same-slot function
0x25FA6 is the WALL twin ('WALL' vs 'BMP '): DS2 replaced DS1's
wall-vs-bmp selector with cbmp-vs-bmp (DS2 has no WALL chunks, DS1 no
CBMP). The three RESOURCE.GFF CBMPs (11001 x2, 11005 x3, 13009) look
composed (11000+n / 13000+n); exact composition unresolved.

## 6. Related correction: IT1R column map needs re-pinning

object-formats.md 4.3's IT1R layout mismatches the shipped chunk (2300 B =
115x20 at GPLDATA offset 0x149FED): the documented table omits offset 6
entirely; shipped bytes have col 5 nonzero in 15 rows {1,2,7,11,15}, col 6
heavily populated (250 dominant; also 255/200/150/100/50/40/20/18/10/5/2/
1/0, sentinel-like), and col 19 claimed "0 (VB)" is wrong: 45 rows carry
{0,1,2,6}. None of these is an icon index, so the conclusions stand, but
the column map should be re-pinned before anyone builds an item editor on
it.

## 7. Open items

- Provenance of the prototype-table word0 fills per template (engine BSS,
  written at object-load/reset time; semantics proven, static source not
  captured, runtime-built like the gpl-vm.md field tables).
- The per-row key of the DS1 3000-family / DS2 21235-family icon sites
  (structure offsets and bases pinned; the row key inferred).
- RESOLVED (screen-flow.md 6): the dialog command indices are pinned and
  the portrait case is command 1 (jump table file 0x7D616 DS1 / 0x884B7
  DS2).
- The DS2 RESOURCE CBMP 11001/11005/13009 id composition.
- The DS1 combat-block +24 "icon" field (18 nonzero rows per
  object-formats.md) could not be independently checked against the ICON
  id set (full RDFF walk timed out); the docs' reading stands unverified.
