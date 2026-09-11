# fix.ds1.deadtriggers

**Bug**: In the Darkhold endgame (regions 30/31), several creatures
stop responding once their story beats have run: the portcullis
guard no longer fights when engaged, and the queen's-chamber
creatures lose their look text. This is the concrete DS1 instance
of the community's "enemies refuse to engage" reports.

**Repro**: Play the main quest to Darkhold. After the story moment
where the portcullis guard is driven off (GPL-195's guarded block
runs), engaging the guard produces no combat response. In the
queen's chamber, after the "Worms!" encounter block has executed,
looking at the guardian creatures (-2263, -1209) produces no text.

**Cause**: Six entity trigger registrations point at GPL-200 entry
0x909, a handler SSI emptied: the entry is a single orphan
`gpl exit gpl` byte wedged between unrelated instructions, not a
discovered entry, and three independently written chunks target it
identically (a deliberately emptied handler, not an offset typo).
When a region script re-registers a trigger for an object, the new
registration occludes the object's earlier one, so each of these
registrations silently disables the working handler registered
earlier:

| Registration | Object | Disables |
|---|---|---|
| `GPL-195@0x2b` attacktrigger | -255 (portcullis guard) | combat handler `GPL-200@0x33b` (registered by MAS-30) |
| `GPL-203@0x3fe` looktrigger | -2263 (queen's chamber) | look handler `GPL-203@0x389` |
| `GPL-203@0x406` looktrigger | -1209 (queen's chamber) | look handler `GPL-203@0x389` |
| `GPL-41@0x1d` looktrigger | -2248 (wyvern scene) | look handler `GPL-41@entry 1` (registered by GPL-39 and MAS-31) |

Two further registrations (`GPL-203@0x3a2` and `@0x40e`) also
target the stub, but name their object through `GNAME[39]`, a
runtime variable. No static analysis can pin what object they
name, so this fix leaves them untouched: their handler is already
inert and repointing them could only invent behavior.

**Fix**: Repoint each of the four static registrations from the
emptied stub (GPL-200 entry 0x909) to the object's own working
handler, i.e. exactly what the engine already had registered for
that object before the occluding registration ran. After the fix
each story beat re-registers the same working handler instead of
the stub, which is a no-op if the engine keeps the first
registration and a restoration if it keeps the last, so the fix
cannot regress either engine semantics. Eleven bytes change, all
in `GPLDATA.GFF`; chunk lengths are untouched.

Before (GPL-195@0x2b):

```
065 0909 00c8 9100ff67   attacktrigger 2313, 200, NAME(-255)
```

After:

```
065 033b 00c8 9100ff67   attacktrigger 827, 200, NAME(-255)
```

The other three sites are the same shape: the 16-bit entry
immediate and (where the handler lives in a different chunk than
the stub) the 16-bit chunk immediate change; the opcode and the
NAME(-object) operand are preserved. Full authoring record: the
per-chunk `gpl-asm --patch` scripts, disassembly evidence, and
byte diffs live in the Phase 6 boxes of `roadmap.md` and in
`docs/known-bugs.md` 3.5.

**Surface**: GPL data (`GPLDATA.GFF`, chunks GPL-41, GPL-195,
GPL-203).

**Verified on**: GOG 1.10 (DS1).

**Default**: on.

## Details

Authoring pipeline (what proved the bytes before they became
EDITS): each chunk was extracted with `gff-edit`, edited with a
`gpl-asm --patch` script (label-anchored, fingerprint-checked),
reinserted with `gff-cat replace`, and the patched `GPLDATA.GFF`
re-disassembled end to end: all 250 chunks still decode aligned,
the four repointed registrations name their new handlers, and the
dead-trigger sweep (gpl-disasm 0.8.0) reports exactly the two
known GNAME[39] rows as its remaining dead triggers, down from
six. The shipped EDITS below are those verified bytes at absolute
`GPLDATA.GFF` offsets; the fingerprints make them refuse to apply
to any other build.

Patched-file hash (records the hash test, patch-workflow 5.1):

```
sha256(GPLDATA.GFF) after fix.ds1.deadtriggers:
e6b163bd446637c6c68f6897c01b59518b513054c90b4a7d7439d900e14142f0
```

Edge cases this fix does not handle: the two GNAME[39]
registrations still point at the stub (see Cause); if the engine
turns out to run both registrations for an object rather than
keeping one, this fix changes nothing observable (and needs
nothing): the occluding registration already resolves to an inert
handler in that case. The in-game confirmation at the bug site
rides the played-save sessions (roadmap gate): the shipped
verification is the hash/byte proof plus the differential boot
capture (`tools/repro/bugs/ds1-deadtriggers/`).
