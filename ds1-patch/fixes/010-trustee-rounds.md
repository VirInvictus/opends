# fix.ds1.trustee-rounds

The Trustee in the slave pens can stop for good: his dialog sticks
at "I'd love to talk more, but I have to get back to work" and the
gate never gets opened.

## Symptom (relayed, then verified)

Relayed from the Obsidian Edition's findings via yuan-ti
(known-bugs.md 3.6 row 8): the Trustee's two scripted pauses take
their corner from numbers other pen scripts change, so he can set
off for a spot that does not exist and stay busy for good. This
trace is our own verification of that claim; it confirms the
mechanism and locates the invalid-state producer.

## The trace

The Trustee is object -89. His work rounds live in GPL 8 (the
gate-opening scene's script) as a state machine over the global
counter `GNUM[20]`:

- A corner-picking switch (GPL 8 @0xebc-0xf3a) maps the state to an
  (x, y) pair in the locals `LNUM[2]`/`LNUM[3]`:
  state 0 -> (111, 42) and clears the busy flag `GF[51]` (@0xedc,
  the only writer of 0 anywhere), 2 -> (91, 87), 3 -> (91, 42),
  4 -> (91, 87), 6 -> (111, 87), 7 -> `wait NAME(-89)` + arms the
  gate sight trigger (@0xf22 is the first scripted pause), 8 -> the
  gate-open scene. **States 1 and 5 have no arm**: they reuse the
  stale corner, which is benign because the previous corner was
  valid.
- A walk loop (@0x102e-0x10be): if the Trustee is not within +-1 of
  the corner (`getxy` vs the pair), `goxy LNUM[2], LNUM[3],
  NAME(-89)` (@0x1074) and leave; on arrival, advance the state
  with SSI's own clamps (`> 5 -> 0` on one path, `< 2 -> 5` on the
  other).

The external writers are exactly the "other pen scripts":

- GPL 147 @0x0005 (the bribe path GPL 8 calls at @0x89) sets the
  state to 8: handled, the scene plays.
- GPL 137 @0x1520 (the main door path) resets it to 0: fine.
- **GPL 137 @0x1740 (the knock-fight path) runs
  `word minus equal GNUM[20], 2` with no guard.** From state 0 or 1
  the state goes negative (-2 / -1).

A negative state matches no corner arm. On a fresh load the locals
are zero, so the corner pair is (0, 0): `goxy 0, 0` sends the
Trustee toward a tile outside the pens' walkable space, the +-1
arrival check can never succeed, the state never advances, the
state-0 arm never runs again, and `GF[51]` (cleared only there)
never lifts. GPL 146 (@0xe9) keeps answering with the busy line,
and the second pause -- GPL 137 @0x12ad's `wait NAME(-89)` -- sits
on the same stuck object. The relayed claim is real; the one
correction is that the "spot that does not exist" is the
uninitialized (0, 0) corner, not a stored one.

## Fix

Guard the writer. GPL 137 @0x1740's bare subtract becomes:

```
gpl load accum          GNUM[20] < 2i8
gpl if                  else_start
gpl load variable       0i8, GNUM[20]
else_start:
gpl else                block_end
gpl word minus equal    GNUM[20], 2i8
block_end:
gpl endif
```

Below 2 the knock clamps the state to 0, the same reset vocabulary
GPL 137's own door path uses at @0x1520; at 2 or more the shipped
subtract is byte-identical. One detour repair, chunk-relative; the
detour body was assembled by gpl-asm and the patched GPL 137
disassembles aligned and reassembles byte-identically.

An alternative shape (clamping negatives at GPL 8's switch head)
was considered and declined: it patches the symptom surface and
touches the engine-authored state machine, while the writer guard
fixes the only invalid-value producer at its source.

## Status

DISABLED by default, per the beta QA gate (#18). QA check: knock on
the pen door and pick the fight; then watch the Trustee -- he
should keep working his rounds and open for a bribe afterwards,
with his dialog not stuck on the busy line.
