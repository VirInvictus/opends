# fix.ds1.messenger-trigger (BETA: UNTESTED)

**Status**: beta, disabled by default, untested at runtime (gate
steps 1-3 passed; the DOSBox QA packet is pending).

**Bug** (our triage 3.2(1c), the "Dagger event never fires"
family): region 9's messenger never arrives for players who stay
in the region through the elves' departure. MAS 9 registers his
sight trigger (GPL 133 entry 1 on object -1297) only when
gflag[245] is already set at region load, but gflag[245] flips
mid-stay at GPL 58; without a re-entry the registration never
happens.

**Cause and fix**: our triage named the three GPL-58 sites where
gflag[245] is set (0x1A, 0x99, 0xCC) and prescribed registering
the trigger on the flip; Calvin Rodo implemented exactly that as
three identical detours. Each preserves the original store, then
re-arms MAS 9's own registration (verified operand-for-operand
against MAS 9 @0x76: `inlostrigger(1, 133, -1297, 15)`) behind
MAS 9's own `gflag[339] == 0` guard (the flag GPL 133 and GPL 132
set once the messenger has fired).

| Site | Kind | Change |
|---|---|---|
| GPL-58@0x1A | detour | register on flip, guarded on gflag[339] == 0 |
| GPL-58@0x99 | detour | same |
| GPL-58@0xCC | detour | same |

**Expected patched chunk**: GPL 58, 2436 -> 2524 bytes, sha256
`f82e099eec88b17e45f715bfecf342170200c33aa507ae58c9b163372e182554`.

**Credit**: site ours (triage 3.2(1c)); implementation Calvin
Rodo, yuan-ti (`GplRepairs.cs`, MIT). QA: the packet,
docs/qa-packet-ds1-script-repairs-beta.md (site M).
