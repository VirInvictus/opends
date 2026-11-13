# fix.ds1.grate-hack (BETA: UNTESTED)

**Status**: beta, disabled by default, untested at runtime (gate
steps 1-3 passed; the DOSBox QA packet is pending).

**Bug** (new discovery, Calvin Rodo / yuan-ti): the slave pens'
sewer grate (GPL 137) hack path is dead three ways: the
weapon-in-hand test reads `lflag[3] == 1` where the code just set
it to 0 (0xA60), so "hack the lock off" is never offered; a
successful hack never opens the grate (the pick path's tail never
runs); and attacking the grate tests field 43 (most hit points,
which an item record does not carry and reads as 0) under 220, so
the lock always breaks.

**Cause and fix**: the offer gate flips to `== 0`, matching the
code's own invariant; the opens detour appends exactly the pick
path's success tail (print lstring[0], which the scene's string
copy at 0x8BA loads with "The grate opens. ", then set
gflag[505], the flag the pick path sets at 0x998); the attack fix
replaces the hit-point test with the rip-open path's own roll
form (`RAND(30) < Str`, as at 0xA97/0xAA6); the his/her detour
splits the shipped line and adds the sheet-gender pronoun with
two relocated label words.

| Site | Kind | Change |
|---|---|---|
| GPL-137@0xA65 | same-length | offer gate: `lflag[3] == 1` -> `== 0` |
| GPL-137@0x9E0 | detour | his/her pronoun, labels relocated |
| GPL-137@0xA14 | detour | success opens: pick tail (lstring[0], gflag[505]) |
| GPL-137@0xB5C | detour | attack: hit-point test -> Strength roll |

**Expected patched chunk**: GPL 137, 8238 -> 8357 bytes, sha256
`2ef1aa813e8647a4226506133927fdacbd860f6b52fa859448e54af5c5548069`.

**Credit**: Calvin Rodo, yuan-ti (`GplRepairs.cs`, MIT); field
meanings per docs/gplx-field-map.md. QA: the packet,
docs/qa-packet-ds1-script-repairs-beta.md (site G).
