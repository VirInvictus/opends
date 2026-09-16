# fix.ds2.deadtriggers

**Bug**: 27 entity triggers across 18 region scripts are registered
to a no-op handler: look, use, talk-to, and attack interactions on
their objects silently do nothing, even where the same region
script defines a working handler for the same object.

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
across the corpus point at exactly that entry. The 27 static rows
this fix repoints are later or interleaved no-op re-registrations
sitting beside alive handlers for the same objects: if the engine
keeps the last registration for a target, the no-op occludes a
working handler; if it keeps the first, the rows are inert. (The
same occlusion shape is what `fix.ds1.deadtriggers` repaired in
Shattered Lands; which semantics the engine uses remains an open
EXE-side question, which is why the fix is designed to be
harmless under either.)

**Fix**: repoint each of the 27 registrations to the object's own
working handler: 24 repoint within their own chunk (18 of them
the shared prop object -2975 across 13 region scripts; the rest,
the Tyr/Silt Giants attack trio -418/-209/-406 and the VA
Headquarters, Crypt, and forest look rows -1923/-2994/-445, land
on that region's own alive handler for the object), and 3 repoint
across chunks to the handler the region's own registrations
attest (Jann's talk pair to `GPL-69@1` per MAS-59; the forest
attack row -146 to `GPL-29@1229` per MAS-1): the same
registration-attested cross-chunk repoint `fix.ds1.deadtriggers`
used for the portcullis guard. Every edit is 5 bytes: opcode +
handler entry immediate + chunk immediate. Chunk lengths are
untouched. 12 of the 39 dead rows are deliberately left: two
pickup rows on object -900, one look row on -1922, two use rows
on -2975, and seven use-with rows in GPL-98, none of which has a
statically provable correct handler.

**Surface**: GPL (`GPLDATA.GFF`)

**Verified on**: GOG 1.10 (DS2)

**Default**: on

## Details

The corrected census at the fix's HEAD (after the sweep tool's
pickup-mnemonic and use-with entry-position fixes): 1,915 trigger
registrations, 1,670 alive, 206 intentional null-handlers,
39 dead. Object census of the repointed rows: 18 use rows on one
shared prop object (-2975, OBJEX BMP 447, placed in Limbo); the
rest span story objects in Tyr (-418), the Silt Giant lands
(-406, -418), the Volcano (-209), the forest (-146, -445), Jann
(-106), the VA Headquarters (-1923), and the Crypt (-2994). All
main-quest, normal-playthrough content.

Authoring ran the standard data-surface pipeline: the sweep and a
per-row registration table produced the handler map; every edit's
`expect` bytes were verified against the canonical install; the
patched file re-disassembles 350/350 chunks aligned and the sweep
drops from 39 dead to 12 (exactly the rows left). The applier
selftest pins the patched `GPLDATA.GFF` hash
`0d974dd4d35d68f09a88c888335400744eaab932338d73999b632078a9def834`
(any EDITS drift fails) and round-trips byte-identically.
