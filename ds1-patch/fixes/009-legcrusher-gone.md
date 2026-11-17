# fix.ds1.legcrusher-gone

The slave pens stop speaking of Legcrusher as if he were about
once he is dead or gone.

## Symptom

The party can kill Legcrusher (object -326, the half-giant monster
trainer) in the slave pens. The scripts never expected that: Kurzak
keeps calling for him at the arena gate, greets the party three
different ways about him, answers the "who is the half-giant?"
question in the present tense, and Dinos still warns the party that
Kurzak will send him out.

## Cause

All six lines are unconditional `gpl print string` instructions.
Nothing checks whether Legcrusher is still on the map, so every
line plays exactly as written regardless of his fate.

## Fix

A detour guard at each of the six sites (discovery: Calvin Rodo's
yuan-ti, `GplRepairs.cs`, MIT; issue #20; static gate passed
2026-11-13, `docs/gate-review-yuan-ti-2026-11-13.md`):

```
gpl load accum  (RETVAL(gpl get range GNAME[37], NAME(-326))) < 999
gpl if          else_start
<the shipped line(s), byte-identical>
else_start:
gpl else        block_end
<the replacement line(s)>
block_end:
gpl endif
```

`RANGE(GNAME[37], NAME(-326)) < 999` is true while Legcrusher is on
the map (the same alive-test idiom the chunks themselves use: GPL
139 @0x275 and @0x29d ask it of -182; the corpus carries 367
`get range GNAME[37]` uses and zero `GNAME[5]`). The applier
appends `[EXIT_GPL][body][JUMP back]` past each chunk's end and
jumps to it from the site, so no shipped address moves
(`docs/detour-repairs.md`).

### Notation note: gname[5] and GNAME[37] are the same register

Yuan-ti's source gates on `gname[5]`; our assembly reads
`GNAME[37]`. These are the same register -- raw gname index 0x25,
the POV/active-character slot: yuan-ti displays gname indices minus
0x20 (raw 0x25 -> 5), our decoder keeps the raw byte (0x25 -> 37).
The corpus agrees: the register does the active-member work in 367
`get range` alive-checks (GPL 139 @0x275 is the model). The design
is Calvin's throughout; the identity table is
`docs/gff-data-reference.md` (issue #26).

### The replacement lines

These invent dialog text, by the recorded 2026-11-13 decision
(known-bugs.md 3.6 row 4). The lines are Calvin's, lightly keeping
his voice:

- Kurzak's call (GPL 136 @0x130): "Legcrusher! ... Legcrusher? Bah!
  Gladiators, get up here before I come down and drag you up!"
- Kurzak's greeting (GPL 141 @0x6B4): "Good thing you got here.
  With Legcrusher gone, I'd have had to come down and fetch you
  myself. "
- Kurzak, having sent him (GPL 141 @0x70B): "I sent Legcrusher
  after you, and he never came back. I don't suppose you'd know
  why. "
- Kurzak, Legcrusher having found them (GPL 141 @0x766): "So
  Legcrusher found you. Then why didn't he come back with you? "
- The half-giant answer (GPL 141 @0xF29): "That was Legcrusher, the
  monster trainer. Nobody has seen him lately.  He's not too
  bright, but he's good with monsters. "
- Dinos's warning (GPL 139 @0x218): "Kurzak's looking for you. You
  better go fight before he comes down here himself. "

## Authoring and verification

The detour sources were authored against base 0 and assembled by
`gpl-asm` (0.10.0's movable-assembly machinery, issue #19); every
`expect` fingerprint was verified against the canonical GOG 1.10
chunk bytes before anything shipped, every detour's label words
were read back from the encoded bytes, all three patched chunks
disassemble aligned with the guard and both branches present, and
each reassembles byte-identically through gpl-asm (the gate
review's bar). The applier selftest stays green with the composed
default set unchanged (this fix ships disabled).

## Status

DISABLED by default, per the beta QA gate (#18): every beta fix
waits for a recorded runtime result before flipping to enabled. QA
check for this fix: kill Legcrusher in the slave pens, then walk
the arena gate and talk to Kurzak and Dinos; each replacement line
above should play where the shipped line used to.
