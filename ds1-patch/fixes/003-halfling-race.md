# fix.ds1.halfling-race (BETA: UNTESTED)

**Status**: beta, disabled by default, untested at runtime (the
adoption gate's static steps 1-3 passed; step 4, the DOSBox QA
in docs/exchange-yuan-ti-2026-11-13.md, is pending).

**Bug** (new discovery, Calvin Rodo / yuan-ti): the slave pens'
halfling (GPL 31) reads the speaker's race from the combat
record's field path, which carries none (byte 0), so a halfling
in the party is never greeted as one and the insult names no
race.

**Cause and fix**: both sites compare the race against 6; the fix
swaps the depth-1 combat-record read for the depth-2 character
sheet path (the 71-byte record's +0x18 race field). Detours (+1
byte each); no address moves.

| Site | Kind | Change |
|---|---|---|
| GPL-31@0x3B | detour | greeting race test: combat record -> sheet |
| GPL-31@0x254 | detour | insult race test: combat record -> sheet |

**Expected patched chunk**: GPL 31, 2419 -> 2443 bytes, sha256
`ec19eda7f6aa2bea0bf7aac12adba51c02c4dceae6f9e3295bcd783418fcff5d`
(gate-verified encoding; the selftest's detour machinery plus the
gate review's assemble check cover the bytes).

**Credit**: Calvin Rodo, yuan-ti (`GplRepairs.cs`, MIT); field
meanings per docs/gplx-field-map.md. QA: the packet,
docs/qa-packet-ds1-script-repairs-beta.md (site H).
