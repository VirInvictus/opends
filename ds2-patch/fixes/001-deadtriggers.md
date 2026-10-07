# fix.ds2.deadtriggers

**Bug**: 37 entity triggers across 20 region scripts are registered
to a no-op handler: look, use, talk-to, attack, pickup, and
use-with interactions on their objects silently do nothing, even
where the same region script (or an attesting script) defines a
working handler for the same object.

**Repro**: the static proof is the dead-trigger sweep
(`tools/gpl-disasm/scripts/dead-trigger-sweep.py` over
`gpl-disasm --all --json` dumps of the canonical `GPLDATA.GFF`):
39 dead registrations, all pointing at `GPL-24` entry 0x1 (a single
`gpl exit gpl`). The in-game scene proof (attack the portcullis
guard-class monsters; use the shared prop object) rides the
played-save sessions (roadmap gate).

**Cause**: `GPL-24` is Wake of the Ravager's shared NPC-chatter
library (bystander combat refusals, enemy taunts, party barks,
race names), alive through 104 `gpl global sub` call sites. Its
entry 0x1 is a deliberate no-op, and 37 trigger registrations
across the corpus point at exactly that entry. The 37 static rows
this fix repoints are later or interleaved no-op re-registrations
sitting beside alive handlers for the same objects: if the engine
keeps the last registration for a target, the no-op occludes a
working handler; if it keeps the first, the rows are inert. (The
same occlusion shape is what `fix.ds1.deadtriggers` repaired in
Shattered Lands; which semantics the engine uses remains an open
EXE-side question, which is why the fix is designed to be
harmless under either.)

**Fix**: repoint each of the 37 registrations to the object's own
working handler. The 27 of v0.1.0: 24 repoint within their own
chunk (18 of them the shared prop object -2975 across 13 region
scripts; the rest, the Tyr/Silt Giants attack trio -418/-209/-406
and the VA Headquarters, Crypt, and forest look rows
-1923/-2994/-445, land on that region's own alive handler for the
object), and 3 repoint across chunks to the handler the region's
own registrations attest (Jann's talk pair to `GPL-69@1` per
MAS-59; the forest attack row -146 to `GPL-29@1229` per MAS-1).
The 10 of v0.1.1 (the 2026-10-07 correlation dig,
docs/port-digs-2026-10-07.md 2): the VA Headquarters tapestry
look -1922 to `GPL-163@1800` (attested by MAS-51, and the same
target the sibling -1923 row already uses); two more shared-prop
use rows to their regions' attested handlers (`GPL-30` to
`GPL-45@1556` per GPL-40, the same attestation the v0.1.0 GPL-45
row used; `GPL-64` to `GPL-64@1` per GPL-74, the self-rearming
shape the v0.1.0 round restored seven times); and the seven
wizard-lab use-with rows in GPL-98 to `GPL-98@1`, whose entry
immediate was already correct on every dead row and only the
chunk id was wrong (their alive twins in GPL-114 register the
identical seven pairs, pair for pair in order, to exactly that
entry). Single-object edits are 5 bytes: opcode + handler entry
immediate + chunk immediate; use-with edits are 4 bytes (entry +
chunk: the opcode sits 9 bytes earlier, across the two 3-byte
NAME operands, and is already correct). Chunk lengths are
untouched. 2 of the 39 dead rows stay: the two pickup rows on
object -900, which provably have no handler anywhere in the
corpus (see Details).

**Surface**: GPL (`GPLDATA.GFF`)

**Verified on**: GOG 1.10 (DS2)

**Default**: on

## Details

The corrected census at the fix's HEAD (after the sweep tool's
pickup-mnemonic and use-with entry-position fixes): 1,915 trigger
registrations, 1,670 alive, 206 intentional null-handlers,
39 dead. Object census of the repointed rows: 20 use rows on one
shared prop object (-2975, OBJEX BMP 447, placed in Limbo); the
rest span story objects in Tyr (-418), the Silt Giant lands
(-406, -418), the Volcano (-209), the forest (-146, -445), Jann
(-106), the VA Headquarters (-1923, -1922), the Crypt (-2994),
and the wizard-lab ingredient pairs (-4413..-4419 with -4407).
All main-quest, normal-playthrough content.

The two rows v0.1.1 leaves, with the proof that closed them: the
pickup rows on -900 (the Tyr thief chase) have no handler
candidate corpus-wide. A full census of every pickup registration
(9 alive in the whole game) and every `NAME(-900)` reference finds
only one -900 handler on record, a look handler (`GPL-147@468`,
the chase-catch scene), which is scene-specific (hardcodes the
guard NPC -60 and ends in `fight`) and attested for look only;
borrowing another object's pickup handler fails the same way
(each existing pickup handler hardcodes its own object). Nothing
statically derivable points at a pickup handler for -900; if the
engine ever fired these rows, their handler is gone from the
shipped data.

Authoring ran the standard data-surface pipeline: the sweep and a
per-row registration table produced the handler map; every edit's
`expect` bytes were verified against the canonical install; the
patched file re-disassembles 350/350 chunks aligned and the sweep
drops from 39 dead to 2 (exactly the rows left). The applier
selftest pins the patched `GPLDATA.GFF` hash
`316bbe66b5a0cee9ab7b5451a59b9295115e925369e4a02bf12aaaa11f7a393a`
(any EDITS drift fails) and round-trips byte-identically.
