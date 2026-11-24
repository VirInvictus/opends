# daaki85 cross-read (2026-11-23)

The mining pass over daaki85's two repos, on the day both landed
in the workspace as reference checkouts (`.darksun-recompiled/`,
`.darksun-obsidian-edition/`; catalogs in
[`../reference/upstream-projects.md`](../reference/upstream-projects.md)
§6). Method: two read-only researchers over the fresh clones with
our own docs open beside them, sharing one scratch ledger; every
finding below carries path:line evidence on both sides. Policy
context: `darksun-recompiled` ships no license, so it is read as a
facts-only reference; `darksun-obsidian-edition` is GPL-3.0 but
this pass still takes facts and mechanisms only, no code. Nothing
was copied.

Headline: **our overlay-format spec is darksun-recompiled's build
recipe, byte for byte** (he credits us in his README), and **the
Obsidian Edition's own patches corroborate nearly every address we
verified in the 2026-11-17 relay**, including the 0x79A3E
correction both sides had to make against the relayed notes. Three
genuine disagreements surfaced; they are the follow-up worklist at
the end.

## 1. darksun-recompiled (the static recompilation)

### 1.1. Corroborations (his numbers, our numbers, same)

- **Overlay machinery.** `tools/build_image.py:167-267` walks the
  FBOV chain exactly per
  [`../reference/overlay-formats.md`](../reference/overlay-formats.md)
  51-101: desc+4 payload, +8 size, +0xA BYTE reloc count, +0xC
  stub count, stubs at +0x20 rewritten `CD 3F` to `EA entry:seg`,
  relocations `v & ~7` as a segtab byte offset. His hard error on
  marker-form relocations (build_image.py:248-249) re-confirms our
  "bit0 never fires" reading (overlay-formats.md:146-150). He
  credits OpenDS: his README.md:132-137, DESIGN.md:13-15.
- **Counts.** DS1 52 live overlay modules + 935 stubs (his
  STATUS.md:20-22) = overlay-formats.md:98-99; DS2 49 modules;
  DSUN.EXE 611,408 (DS1) and 634,416 (DS2) = our
  [`../reference/install-variants.md`](../reference/install-variants.md)
  37-38. Our six empty DS1 module slots are skipped by his loader
  too (build_image.py:235-236).
- **GPL dispatch tables** on three independent numbers: his
  find_funcs.py:38-41 near-table constants (DS1 0xC0/0x81/0x0C4D,
  DS2 0x30A/0x81/0x0F3C) = gpl-vm.md 52-56, and his runtime
  paragraph 0x0C4D minus load 0x810 = the file paragraph 0x43D in
  dispatch-table-ds1.md, 129/129 entries.
- **DS2 CD handling:** runtime/iso.c and tools/cd_extract.py
  (2352-to-2048 at offset 24, ISO9660 PVD at sector 16) = our
  install-variants.md §8 recipe verbatim.
- **Boot save copy:** DARKSAVE-to-DARKRUN at boot (STATUS.md:25-26)
  = file-formats.md:684 and the QA guide. DS2's party lives in
  CHARSAVE.GFF (STATUS.md:484) = engine-quirks.md 62-63. The
  "Miles Design" ADV signature (lift_drivers.py:159) =
  audio-routing.md:73-74.

### 1.2. New to us (facts our docs lack)

- **The `__support/save` gap.** innoextract skips GOG's
  `__support/save` starting saves; without them the game quits at
  START GAME (both games) and CHARTRAN finds no roster
  (his README.md:40-42, STATUS.md:408-410). Our
  build-environment/verify-install docs never mention `__support`.
  Worth a line in build-environment.md.
- **Boot sequence observed live:** Borland C0 startup, VMEM on
  XMS, GFF files open, the DARKSAVE-to-DARKRUN copy, mode 13h,
  keyboard and mouse hooks (STATUS.md:25-26). "VMEM on XMS" is
  new (we only had the strings); it refines the speculative prose
  in engine-quirks.md 90-97, which our file-formats.md:684 already
  reads correctly.
- **Overlay neutralization:** all 52 modules preloaded at
  C000..FDE3 (room exists only because XMS yes / EMS no), and
  three overlay-manager entry points answered natively so INT 3Fh
  never installs (STATUS.md:20-22, DESIGN.md:99-105).
- **Function discovery beyond our ovr-map** (~2,370 functions,
  ~178k instructions, 134 jump tables): seeds `55 8B EC` prologues
  AND Borland's frameless stack-check prologue, recovers `_INIT_`
  tables by decoding C0's `mov si/mov di` pairs, seeds AH=25h
  handler installs and call/jmp-through-register immediates, and
  converges on a misses list (find_funcs.py:87-122,124-155,
  310-337,340-356). Our 935-entry map + 142 curated names lack
  the prologue/stack-check/init-table harvest.
- **CHARTRAN.EXE decoded:** LZEXE 0.91 (`LZ91` at 0x1C), 303
  functions, plain EXE segments from relocations, mounts
  C:\DSUN / C:\RAVAGER (unlzexe.py:36-100, build_image.py:287-294,
  STATUS.md:71-144). Our docs name the file only.
- **AIL driver chunk internals:** driver image is a function table
  of (AIL fn number, offset), 64 entries max, 0xFFFF-terminated;
  CRC-32 of the first 256 bytes as runtime ID; the OPL detect is a
  timer handshake (status C0h, T1 x80 us, T2 x320 us); SB Pro
  detect via mixer register 0x0A bits 1-2; FM driver runs at
  120 Hz; digital speech is SB DSP + DMA ch1 + IRQ5 at 8 kHz
  (aildrv.c:34-59, opl.c:5-99, audio.c:6). Our audio docs cover
  the XMI side, not the driver binaries.
- **DS2 title music is CD Track 37**, sample-verified against
  GOG's OGG (STATUS.md:461-463). Our audio-routing.md open item 1
  has zero song-to-track bindings; his MSCDEX-emulation route
  (MEL reads the emulated TOC) sidesteps the static pin entirely.
- **Engine odds and ends:** intro cutscene advances on an XMIDI
  callback 0x7F (DESIGN.md:111-113); dice seed from time-of-day
  once at the main menu, so a clock-pinned DOSBox comparison rolls
  identical dice (STATUS.md:58-63); DS2 skips the intro on Shift
  via BIOS shift state 0040:0017; GOG launches DS2 as
  `DSUN -W0 -L`; GOG's SOUND.CFG selects MT-32 whose instrument
  file GOG does not ship; the game polls INT 33h so presses and
  releases between polls are lost.
- **Catalogue-quality note for ovr-map, audited same-day:** his
  tools consume our syms TOMLs, and his frame classifier notes
  that "OpenDS names some functions at the stack check". The
  2026-11-23 byte audit of all 291 rows found his shift fires on
  ZERO rows in either game: every stack-check-anchored row is his
  own 'at' frameless case (DS1 `39 26 9C 00` after a ret; DS2
  `6A nn E8` thunks), all 106 gpl_handler rows are byte-exact
  dispatch-table entries a 3-4-byte shift would move OFF their
  targets, and the 59 rows his tool notes as "interior" are
  accounted for (dispatch entries plus documented data cells).
  The audit did surface one unrelated correction, applied in
  ds1.toml: gpl_opcode_dispatch 0x99c5 -> 0x9998 (the true far
  frame, carrying both near callers; the old offset sat 44 bytes
  in). Credit for the prompt: daaki85's frame_kind critique.

### 1.3. Tooling notes

- `converge.sh` rebuilds with the misses list until its md5
  stabilizes; `entries/<tag>/misses.txt` is kept per build.
- `difftest` lifts every distinct instruction alone and checks it
  against Unicorn on random register states (128 DS1 / 127 DS2
  segments); it caught one real lifter bug (`imul r32,imm`
  sign-extension).
- `dosbox_compare.sh` runs the same scripted fight under DOSBox
  0.74 and the recompilation under Xvfb with clocks pinned and
  compares roll-for-roll. That is a test-oracle pattern worth
  copying into our QA rig (compare
  [`../reference/re-tooling.md`](../reference/re-tooling.md)).
- Windows-only pitfalls recorded: text-mode file opens stop at
  Ctrl-Z inside GFF reads; `tmpfile()` needs a drive root; SDL
  logical-size doubles mouse scaling.

## 2. darksun-obsidian-edition (the relay's primary source)

### 2.1. The 15 relayed rows against primary source

Our verified catalog (known-bugs §3.7) holds up: the primary
source carries the same bytes at the same addresses for Mirror
Image (0x7A5CD `cmp ax,4Bh`, landing 7A539h), the armor
double-charge (7A557h / our corrected 0x79A3E), the effects-screen
jumps (0x7F226 `7c51`, 0x7F236 `7d41`), thri-kreen claws
(58019h / `[BP-14h]` = 8), Scare's unreachable elf exception, the
DELETE-when-scrolled roster row math (0x54ADF), thief-skill
slots (0x44F70 = slots 6,1,10,3,13), Cilla's figure, and the
Trustee's script-8 rounds machinery. Extensions our rows gain when
we fold them in: effect 25 and the 50%-vs-75% Reflected Image
distinction; single-creature spells only for Mirror Image;
"charges" = effect record +8 / timed event kind 7 at DS:2FBEh; the
psionic band is 8Ah-ABh specifically; the save-modifier frame at
79D3Ch; spell records are 20h bytes with a flags word at +11h;
and the acid-check primary statement (armour reads the power byte
not the plus; with every such armour in the game the check always
succeeds, Tanelyv's Armor +2 named).

Three disagreements:

1. **Share Strength's end: does the loop remove?** Their
   code-read asserts the 598:48h per-match call removes records
   (and the bug is the caster-as-owner argument), while our trace
   reads the same call as a pure getter with the result discarded.
   Same call, two readings; ours is a trace, theirs is a fix that
   assumes removal. Re-examination target.
2. **Sling +1's name.** Their ITEMS.md calls the broken-icon chest
   item in the Teaquetzl temple a real "Sling +1"; our name-pool
   scan says no such name exists (our §3.7 resolved the closest
   defect as the OJFF-less chest sling 2644). One SEGOBJEX re-read
   settles it; our scan is the side to re-check.
3. **Cure dice, text vs code (minor):** their docs say the Cure
   spells heal 2d8+1/3d8+3; our trace paid Cure Critical 3d8+1.
   They patch cause dice only and likely never traced the cure
   handler. Unresolved, low stakes.

Both sides also independently refute the relay's Hold Undead
claim, and their DEVELOPMENT-CONTENT.md explains the misreading's
origin (non-undead fall through to the generic landing path), with
landing 7A333h, immunity exit 7A1F0h, HD-limit site 7A345h.

Numbering note for future citations: OE's spell numbers are
0-based; our SPIN record numbers are OE + 1 (their 113/128 = our
114/129).

### 2.2. The dice-log oracle, corrected

Our re-tooling.md and the 2026-11-13 crossread describe the
oracle as "replay a golden fight from the same seed and diff the
roll order". The actual implementation is none of that: it is a
live labeled log. The RNG call at 0x5C22 is byte-patched to an INT
60h TSR that returns the identical number and records caller and
frame args into a 63-entry HMA ring; purpose labels come from
Loader-side caller fingerprinting (decoding the `rand()*N/32768`
shapes around the recorded return address), with 16 kind labels
and probes at the save/AC/to-hit compares. The replay-enabling
property is real ("the replacement produces identical numbers"),
but there is no seed capture or set, no replay, no diff, and no
persisted machine-readable log. The instrument our re-tooling.md
names remains unbuilt on both sides; building ours needs the 0x5C22
hook (proven viable by their patch), caller fingerprinting, a
guest-memory ring, and the seed capture/set at DS:4124h (their
patch bytes imply the state address; unverified) plus a diff step.
Re-tooling.md's oracle paragraph should be reworded when we touch
it next; the fix is left as a finding here.

### 2.3. Rules facts

- **Our open item resolved:** the mode-4 WIS ability table's
  consumer is the save modifier vs mind-affecting/charm/hold/
  fear/illusion; the CON table's is the para/poison/death save
  modifier. Their tables are byte-identical to ours in
  rules-tables.md, and dwarves/halflings add CON x2/7 on saves,
  corroborating our rules-block reading.
- **The game caps class levels at 9** (level-up compare at 87BE6h,
  View Character at 67D08h) even though the XP/HP/THAC0/saves
  formulas continue past 9 into the 20-level tables.
  rules-tables.md documented the gate but no cap.
- **Save routine frame:** unsigned final compare at 79BBD, natural
  20 saves before modifiers at 79B5F, sum clamp at ±110, DEX
  defensive adjustment present as dead code; `special & 0x86`
  doubles the save roll for exactly fire/cold/electricity; of the
  five save kinds, the spell save is never used by any spell.
- **PSP recompute at 873B2h** carries INT/WIS terms and
  psionicist bonuses vs our CON-only gain formula at 0x875a8;
  plausibly gain-vs-recompute sites. Re-check candidate.
- Corroborated wholesale: gladiator = fighter copy, XP tables in
  hundreds, sheet class rows at +0CAh / XP table at +27Ch,
  creature THAC0 = warrior table, sheet saves = warrior row,
  priest THAC0 rate, initiative d200 tie-break.
- Two smaller extensions: the PSP bonus tables end too early for
  scores 22-25 (engine-quirks §1 family), and the graphics-
  disappearance mechanism is 300 picture slots never freed until
  the next area (extends known-bugs §2.2).

### 2.4. The loader vs our darkfix applier

Nothing of the install is ever modified: each start regenerates a
patched copy (`prepare_patched_game`, launch.py:596-676), DOSBox
boots a TSR chain with the copy as drive D, and data mods arrive
through an INT 21h hook that opens the Loader's copy at file-open.
Safety shapes worth stealing: per-patch original-byte fingerprints
checked even when a switch is off, partial-failure reporting that
names what was left out and still runs the game, atomic
whole-or-nothing settings writes, and the TSR layer that makes
rule switches free at runtime. Our darkfix mutates in place with a
manifest, journal, and `--unapply`; their regenerate-idempotently
shape is the right answer to a different constraint (their rule
switches are per-launch, ours are per-install). The overlay-coverage
argument for file patching ("covered every time it loads") is
worth a citation in fix-format.md's rationale when next touched.

## 3. Follow-up worklist — EXECUTED 2026-11-23

All eight items worked the same day; each landed as follows.

1. Share Strength re-trace: DONE -- OE vindicated; known-bugs
   §3.7 row 3 rewritten (the per-match call is a full remover;
   the caster-as-target argument is the bug; the "skip" is
   compaction plus the loop's index increment).
2. Sling +1 re-check: DONE -- both sides half right; the display
   name is pool "Sling" plus the newly decoded enchantment byte
   (object-formats.md item +20); known-bugs row 12 rewritten.
3. Mirror-image reconciliation: DONE -- combat-flow.md's sentence
   described the wrong branch (it is Fire Shield retaliation,
   deterministic, no roll); rewritten, and apply_hit's file
   address corrected 0x5873a -> 0x5883a.
4. Dice-log oracle reword: DONE -- re-tooling.md now describes
   the live labeled log and names the missing pieces.
5. ovr-map hygiene: DONE -- zero rows shift (see §1.2); one
   unrelated correction applied (gpl_opcode_dispatch 0x99c5 ->
   0x9998, with the callers as evidence).
6. §3.7 extension fold-in: DONE -- rows 1, 2, 4-8, 10, and 12
   extended from the primary source, each marked OE-sourced where
   we did not independently trace it.
7. __support/save note: DONE -- build-environment.md's extraction
   section carries the copy step and the START GAME failure mode.
8. PSP sites: DONE -- OE's 0x873B2 confirmed as the only PSP
   routine (formula byte-verified; monotonic ratchet; the
   [0x11a0] scratch-pointer quirk noted); our 0x875a8 claim was
   the CON HP additive, and 0x875df is the attacks-per-round
   derivation. rules-tables.md's +0x52 section rewritten, the
   PSP recompute section added, lines 141/216/223/242/272
   corrected; chargen-flow.md's init chain relabeled.
