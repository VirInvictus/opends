# fix.ds1.script-repairs

**Bug**: three script-level defects from the 2026-10-07 DS1 sweep
triage (docs/ds1-sweep-triage-2026-10-07.md): a trigger re-arm in
the Lava Rifts occludes the ranger's own handler with the hermit's
(the endless-dialog-loop and duplicate Iron Necklace bug); a
Linara conversation route dead-ends with no menu after the extract
delivery (the Jasmine spellbook topic never becomes discussable);
and the final battle's inter-stage time gate strands the battle
permanently when a stage is cleared too quickly.

**Repro**: the static proofs are in the triage doc (byte-level
readings of the three sites plus the flag/registration censuses
behind them); the in-game scene confirmations ride the Phase 10
playthrough, as with 001.

**Cause and fix**, one edit each (all same-length: only the 2-byte
entry/operand immediate changes, opcode and chunk bytes ride in
the fingerprint):

1. **Hermit/ranger occlusion** (`GPL-100@0x684`): the ranger-leave
   re-arm executes `inlostrigger 86, 100, NAME(-21), 7`, arming
   entry 86, which is written entirely for the HERMIT (hermit
   lines, the Iron Necklace give at 0x195). The region master
   (MAS-27) already registers the ranger -21 to 100@445; the
   re-arm occludes it, so every approach replays the hermit scene
   and the drop fallback spawns a duplicate necklace. Fix: entry
   86 -> 445. Safety: identical to the `fix.ds1.deadtriggers`
   design: under keep-first registration semantics the edit is a
   no-op (the correct registration stands), under keep-last it is
   a restoration.

2. **Linara dead-end** (`GPL-68@0xaa`): the router sends
   `GNUM[55]==2` (extract delivered) to `local sub 4942`, a single
   thank-you line with `local ret`: no menu, no exit branch. A
   player who delivered the extract before rescuing Jasmine is
   locked out of the spellbook topic. Fix: sub 4942 -> 209, the
   general menu every other branch of the same conversation uses;
   LFLAG recomputation at entry keeps the already-delivered
   entries hidden. Safety: if the bug theory were wrong, the
   observable delta is the full menu appearing where a dead end
   stood; the thank-you line is the only content lost.

3. **Final-battle stage-gate strand** (`GPL-62@0x10f1`): each
   stage-advance handler records the clock and arms `noorder-
   strigger 4345, 62, -1297`; entry 4345 checks whether a full
   window (clock/20) has elapsed and, if not, executes
   `gpl exit gpl` WITHOUT re-arming anything: the driver chain is
   dead and the next stage never spawns. This matches the
   community mechanism exactly ("dragging out each fight works
   around it": a slow clear fires the gate after the window, and
   the re-arm happens). Fix: the arm's entry 4345 -> 239, the very
   driver handler the gate would eventually re-arm, so the chain
   advances immediately and the stranding path is unreachable.
   Safety: if the bug theory were wrong, the observable delta is
   the loss of the intended inter-stage pause. This repair is the
   one member of the final-battle family with a proven faulty
   datum; the other five variants are triaged in the sweep doc
   (two no-static-site negatives, one engine-side, one text-only,
   one documented-not-patched).

**Surface**: GPL (`GPLDATA.GFF`)

**Verified on**: GOG 1.10 (DS1)

**Default**: off (see below)

## Why this fix ships disabled

The applier refuses two enabled fixes sharing one target file
(spec 5), and `fix.ds1.deadtriggers` owns `GPLDATA.GFF` in the
default configuration. The three repairs are independent of the
deadtrigger rows (disjoint offsets), but composing per-file fixes
is a spec-level question, not an applier flag, so v0.1.2 ships
this fix toggled off: enable `fix.ds1.script-repairs` and set
`fix.ds1.deadtriggers` to `enabled = false` in `manifest.toml`
(or the copy in your zip) to take it. The three sites were chosen
over the triage's other candidates precisely because they are
same-length edits with no-op-or-restoration (1) or bounded,
documented (2, 3) safety arguments; the triage's chunk-growth
candidates (Alhena's unreachable condition, the escort-family
guards, Rebel Mindhome's router) wait for either a composition
decision or the gpl-asm grow path.

## Details

Authoring ran the standard data-surface pipeline: every edit's
`expect` bytes were verified against the canonical install; the
patched file re-disassembles 250/250 chunks aligned and the three
sites decode as intended (the orphaned gate body at GPL-62@0x10f9
is never called). The applier selftest pins the patched
`GPLDATA.GFF` hash for the DEFAULT enabled set (001 only); with
this fix enabled instead, the patched hash is
`482796e3da9f27b1feee5dce5cc8db59ecfaf2b5e75b8ff760180f7578111a95`.
