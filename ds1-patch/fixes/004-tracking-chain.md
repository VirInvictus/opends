# fix.ds1.tracking (BETA: UNTESTED)

**Status**: beta, disabled by default, untested at runtime (gate
steps 1-3 passed; the DOSBox QA packet is pending).

**Bug** (new discovery, Calvin Rodo / yuan-ti): the ranger
tracking roll over region 8's bodies (GPL 210) can never succeed.
Three stacked faults: the ranger test reads the class-bits word
off the combat record instead of the sheet; the three class-slot
bonus tests bit-test class codes (13-16) against the 0x200
ranger bit, which is always false because a code is not a
bitmask; and the roll is inverted (success required the score
under the roll, so high Wisdom made it harder).

**Cause and fix**: the ranger test follows to the sheet's
class-bits field (the 0x200 bit is then the correct ranger
semantics); the three bonus tests become (code > 12) and
(code < 17), reusing the same embedded 0x20 form as the AND; the
roll swap is same-length. Four detours + one same-length edit;
no address moves.

| Site | Kind | Change |
|---|---|---|
| GPL-210@0x5FD | detour | ranger class read: combat record -> sheet |
| GPL-210@0x60C | detour | class slot 1: bit test -> 13-16 range |
| GPL-210@0x622 | detour | class slot 2: bit test -> 13-16 range |
| GPL-210@0x638 | detour | class slot 3: bit test -> 13-16 range |
| GPL-210@0x6CC | same-length | roll direction: RAND(20) < score |

**Expected patched chunk**: GPL 210, 1869 -> 1973 bytes, sha256
`f1d6d94f4df1a1025327a80dacee708bb25dd87a288a9d5a605bf74476ddef24`.

**Credit**: Calvin Rodo, yuan-ti (`GplRepairs.cs`, MIT); field
meanings and the class-bit table per docs/gplx-field-map.md. QA:
the packet, docs/qa-packet-ds1-script-repairs-beta.md (site T).
