# fix.ds1.slave-follow

The battlefield slave stops following the party after a zone
transition.

## Symptom

After the player leaves region 9 (the battlefield) and returns,
the freed slave (-198) stays where he was instead of following
the party.

## Cause

The follow order (`follow GNAME[37], NAME(-198)`) is issued
exactly once, at GPL-132@0x38b, when the slave is first freed.
Nothing re-issues it when region 9 reloads: the region-load
master script (MAS-9) re-registers the attack triggers on the
three slaves/elves (@0x46-0x5d) but carries no follow for -198.

## Fix

Append the follow to MAS-9's post-raid ordering block
(@0x9e-0xbe), which runs at region load once the raid flag
(GF[5]) is set -- the same window that already orders the two
departed elves (-199/-200) to their post-raid positions. The
detour body is the four shipped ordering instructions verbatim
plus the appended 6-byte follow (no branch words, so no
relocations). The triage's named carrier (row 1b,
ds1-sweep-triage-2026-10-07.md).

## Verification

Expect fingerprint verified against the canonical GOG 1.10 chunk;
the patched MAS-9 disassembles aligned with the follow present
and reassembles byte-identically through gpl-asm.

## Status

DISABLED by default, per the beta QA gate (#18). QA check: free
the battlefield slave, leave region 9, return, and walk away from
him -- he should resume following.

## Open question recorded

The GF[5] == 1 gate on the carrier block means the re-issue fires
in the post-raid window; whether GF[5] survives a zone
transition (persisted global) or is re-set by the raid script
mid-stay determines whether very-late re-entries are also
covered. A runtime pass settles it; the fix degrades to "no
re-issue" (the shipped behavior) if the gate never opens.
