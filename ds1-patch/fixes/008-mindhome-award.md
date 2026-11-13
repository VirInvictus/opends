# fix.ds1.mindhome-award (BETA: UNTESTED)

**Status**: beta, disabled by default, untested at runtime (gate
steps 1-3 passed; the DOSBox QA packet is pending).

**Bug** (our triage 3.2(4) bonus finding): the Rebel Mindhome's
5000 XP for the spiders re-awards on every re-talk once the
spiders are dead; nothing reads gflag[695], which the first
award sets. (The re-ask half of the same triage row - the GPL-204
router never consulting GF695 - is NOT fixed by this fix and
stays queued.)

**Cause and fix**: Calvin Rodo's fix gates the award (the
`gnum[16] = 5000` store and its GPL 74 call) on
`gflag[695] == 0`. GF695 is set just after the site (0x5d6, per
our triage), so the award fires once.

| Site | Kind | Change |
|---|---|---|
| GPL-204@0x5C9 | detour | award behind `IF gflag[695] == 0`, label relocated |

**Expected patched chunk**: GPL 204, 6699 -> 6724 bytes, sha256
`1bd8d11267d264c56ce95679ce5d07541d8921860d07d48f34ba3cd0940a553d`.

**Credit**: finding ours (triage 3.2(4) bonus); implementation
Calvin Rodo, yuan-ti (`GplRepairs.cs`, MIT). QA: the packet,
docs/qa-packet-ds1-script-repairs-beta.md (site W).
