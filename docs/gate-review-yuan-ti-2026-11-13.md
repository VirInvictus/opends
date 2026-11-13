# Adoption-gate review: yuan-ti's GplRepairs.cs (2026-11-13)

The gate record for the 29 repairs in Calvin Rodo's
[`yuan-ti`](https://github.com/CalvinRodo/yuan-ti)
`engine/src/DarkSun.Game/Scripting/GplRepairs.cs`, run through the
five-step adoption gate defined in
[`detour-repairs.md`](detour-repairs.md) §4. Verdict bottom line:
**steps 1-3 pass for all 29; step 4 (runtime QA) is pending with
Brandon's DOSBox sessions; nothing ships until it passes.** Every
conclusion below was re-derived from our own tooling
(`gpl-disasm --json`, `gpl-asm` round-trip) against the canonical
`.games/ds1/GPLDATA.GFF` (GOG 1.10), never from yuan-ti's own
decoder.

## Method

Scratch pipeline (not repo code): reimplement `GplRepairs.Apply`
faithfully in Python from the C# source, build a patched copy of
`GPLDATA.GFF` (same-length edits in place; detour edits append the
`EXIT_GPL | detour | JUMP-back` block at the chunk tail under the
`gff-edit` append writer policy), then:

1. `gpl-disasm --all --json` over original and patched copies
   (250/250 chunks decode in both, detour tails included: the
   appended blocks are valid instruction streams with no unknown
   bytes).
2. Per-site diff of the instruction stream at each repair site
   (site + appended block).
3. Corpus cross-checks for every named flag, handler, and mirrored
   code path (MAS 9, GPL 132/133, GPL 137's pick and rip paths).
4. `gpl-asm --all-from` over the patched disassembly and byte
   comparison against the expected patched chunks (and originals
   for untouched chunks).

## Gate step 1: fingerprints

23/23 static repair sites match the canonical file exactly
(verified 2026-11-13, the scratch verifier). The remaining 6
(Legcrusher guards) are assembled at runtime by their engine from
GPL source and have no shipped bytes to fingerprint; for them the
six PRINT_STRING sites were verified instead: all six decode as
exactly the shipped lines Calvin's replacement gates (GPL 136
@0x130, GPL 139 @0x218, GPL 141 @0x6B4/0x70B/0x766/0xF29, channel
115 speech).

## Gate step 2: semantic review (29/29 confirmed)

Our seven ported fixes (4 deadtriggers, ranger, Linara, stage
gate): the patched disassembly reproduces our own fix documents
exactly (entry/file repoints land on the documented handlers).
Nothing to add.

Calvin's implementations of our triage candidates (5 repairs):

- **Serf follow range** (GPL 60 @0xCD8): one immediate in the
  `RANGE(gname[37], -259) < 14` guard changes 14 -> 127; every
  other byte identical. As claimed; balance-class, off by default
  per §5 policy.
- **Messenger re-arms x3** (GPL 58 @0x1A/0x99/0xCC): the three
  sites are exactly the three `gflag[245] = 1` instructions our
  triage named. Each detour preserves the original store, then
  registers `inlostrigger(1, 133, -1297, 15)` guarded on
  `gflag[339] == 0`. This is MAS 9's own registration, verbatim:
  MAS 9 @0x76 arms the same trigger with the same four operands,
  behind the same two gates (`gflag[245] == 1` @0x63, then
  `gflag[339] == 0` @0x6C). `gflag[339]` is set by the messenger's
  own script (GPL 133 @0x1B5) and GPL 132, so the guard prevents
  duplicate registration. Faithful to the triage's prescribed fix.
- **Mindhome XP award-once** (GPL 204 @0x5C9): the `gnum[16] =
  5000` award (plus its GPL 74 call) moves behind
  `IF gflag[695] == 0`. GF695 is set just after the site (our
  triage: set at 0x5d6, read only by GPL-196/202), so the award
  fires once. As claimed.

Calvin's own discoveries (17 repairs):

- **Halfling greeting/insult** (GPL 31 @0x3B/0x254): the race test
  moves from the combat record's field path (depth-1 elements
  `[20]`) to the character sheet's (depth-2 `[71, 20]`), same
  keyword subject (obj 0x8025), same race code (== 6). The insult
  is the same change in its `compare` form. As claimed.
- **Tracking chain** (GPL 210): the ranger test reads the sheet's
  class summary (depth-2 `[71, 17]`) where the original read the
  combat record's (`[17]`); the three class-slot bonus tests
  become `(class > 12) and (class < 17)` where the original tested
  bit 512 of the class code (always 0 for codes 13-16, so the
  bonus could never fire); and the roll inverts to
  `RAND(20) < lnum[4]` (roll under the score, the D&D direction;
  the original `lnum[4] < RAND(20)` made high Wisdom harder).
  Four of the five are detours; the roll swap is same-length. All
  as claimed.
- **Sewer grate** (GPL 137): the offer gate becomes
  `lflag[3] == 0`, which matches the code: the sub sets
  `lflag[3] = 0` at 0xA60 immediately before testing `== 1` at
  0xA65, so "hack the lock off" was unreachable. The attack fix
  replaces the item hit-point test (`field[43] < 220`, always true
  for an item) with `RAND(30) < sheet Str`, the same form the
  rip-open path uses at 0xA97/0xAA6. The his/her detour splits the
  shipped line and adds `IF sheet gender ([71, 21]) == 1 'his '
  ELSE 'her '`, with both Relocate targets verified in-frame. The
  opens detour appends exactly the pick-success tail: after the
  sentence's period it prints `lstring[0]` (which the scene's
  string copy at 0x8BA loads with "The grate opens. ") and sets
  `gflag[505]`, the flag the pick path itself sets at 0x998.
- **Legcrusher guards x6**: source-level review (runtime-assembled
  upstream). The detour source gates each line on
  `RANGE(gname[5], name(-326)) < 999` (Legcrusher's object) and
  substitutes replacement lines when he is gone; the gated lines
  are the exact shipped strings above. Behavior-inventing by
  design (recorded decision, known-bugs.md §3.6 row 4).

## Gate step 3: assemble check (250/250)

`gpl-asm --all-from` reassembled all 250 chunks of the patched
disassembly with validation on (branch bounds, Immediate14, RetVal
depth): zero skips, zero failures. Byte comparison: every patched
chunk reassembles byte-identical to the expected patched bytes, and
every one of the 238 untouched chunks to its original bytes. The
detour blocks, relocated IF/ELSE targets, and jump-backs all
survive our encoder's validator.

## Notes raised by the review

- Our mnemonic `gpl bitsnoop` (0x20) reads as a bitwise-and
  between its parameters in these sites (the original
  `bitsnoop(class_field, 512)` is the always-false bit test; the
  fixes reuse the same embedded form as the AND of the range
  comparisons). The libgff-derived name may be misleading;
  candidate for the `opcodes.toml` curation rule, pending handler
  evidence.
- Keyword objects 0x8025/0x8026/0x800C carry our complex-access
  keyword form (`obj_name >= 0x8000`) but their specific keyword
  identities (speaker/party member/ready item, by usage here) are
  unmapped in our docs; recorded for the next `gff-data-reference`
  pass. (Update, same-day mining pass: the field meanings behind
  every repair path are now decoded in
  [`gplx-field-map.md`](gplx-field-map.md), credited to yuan-ti;
  the keyword identities themselves stay unmapped on their side
  too.)
- Correction landed with this review: known-bugs.md §3.6 rows 2-3
  previously called most of the tracking and grate edits
  "same-length"; they are detours (only tracking-roll and
  grate-offered are same-length among those families). The rows
  are fixed here.

## Remaining before canon

Gate step 4, runtime QA: the per-site checklist in
[`exchange-yuan-ti-2026-11-13.md`](exchange-yuan-ti-2026-11-13.md)
§4, run in DOSBox by Brandon (overlay mounts; capture is his).
Step 5, per-fix credit, rides the shipping release. Only then do
any of these become darkfix-ds1 fixes.
