# fix.ds1.alhena-campfire

Alhena never materializes at the endgame campfire.

## Symptom

After the final battle, Alhena is supposed to appear at the
campfire (register a LOS trigger and spawn at 74,95). Players
report she has never materialized.

## Cause

Statically provable unreachable branch (ds1-sweep-triage row 2).
The caravan-arrival script (GPL-28@0x298) exits when GF[123] == 1
-- the caravan-raid flag, set at GPL-21@0x28a and never cleared --
BEFORE the post-war GF[138] branch that leads to Alhena's
registration and spawn (-212, the corpus's only spawn site at
GPL-28@0x51c). GF[138] is set only after the final battle
(GPL-62@0x1685), so every normal endgame arrival has GF[123] set:
the exit fires and Alhena's spawn is unreachable.

## Fix

Guard the exit: it fires only when GF[123] == 1 AND GF[138] == 0
(war not won). The detour body replaces the 10-byte
condition + exit block:

```
gpl load accum  GF[123] == 1i8
gpl if          endif        ; GF123 != 1: skip the exit
gpl load accum  GF[138] != 1i8
gpl if          endif        ; GF138 == 1: skip the exit
gpl exit gpl                 ; GF123==1 and GF138==0: exit fires
gpl endif
```

Both branch words relocate to the detour's end (applier-handled).
The shipped bytes at the range check that follows (0x2a3) are
untouched.

## Verification

Expect fingerprint verified against the canonical GOG 1.10 chunk;
the patched GPL-28 disassembles aligned with the GF[138] guard
present and reassembles byte-identically through gpl-asm.

## Status

DISABLED by default, per the beta QA gate (#18). QA check: reach
the endgame with the caravan raided earlier in the run, win the
final battle, then arrive at the campfire -- Alhena should spawn
and greet.

## Authoring notes

The triage called this a control-flow edit needing "if-depth
rebalancing"; the movable assembler made the flat two-guard form
authorable without any depth bookkeeping (both `if`s jump to the
same endif label; the CFG walker pairs each with the shared
endif). The selftest corpus (250/250) plus the patched-chunk
round-trip cover the structural side.
