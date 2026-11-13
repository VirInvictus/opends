# Detour repairs: length-changing script fixes for darkfix

Design note, 2026-11-13. The mechanism is Calvin Rodo's, published
in [`yuan-ti`](https://github.com/CalvinRodo/yuan-ti)
`engine/src/DarkSun.Game/Scripting/GplRepairs.cs` (MIT; design
adopted with credit in [`../CREDITS.md`](../CREDITS.md), not a C#
port). Nothing here is implemented yet; this note is the contract
the implementation must satisfy, and the adoption gate every
borrowed or newly authored repair must pass before it ships.

## 1. The problem it solves

Every darkfix shipped so far is a same-length edit: the replace
bytes are exactly the expect bytes' size, so no address moves and
no chunk grows. The 2026-10-07 DS1 sweep triage kept hitting fixes
that need inserted instructions and parking them as
FIX-CANDIDATE (needs chunk growth):

- 3.2(1b) Battlefield rescued slave stops following: re-issue the
  follow order after a zone transition.
- 3.2(2) Alhena never appears: neutralize the GF123 early exit for
  the post-war case (if-depth rebalancing).
- 3.2(4) Rebel Mindhome re-ask: +2-byte `gflag[695]` expression in
  the GPL-204 router.

Detour repairs lift exactly this constraint: a repair may inject
arbitrary new GPL code appended after the script's own bytes, with
the original site becoming a JUMP into the injection.

## 2. The mechanism, as published

Calvin's `GplRepair` record: `(Id, File, Offset, Expect, Replace,
OnByDefault, What)` plus `Relocate`, a list of offsets inside
`Replace` where a big-endian 15-bit address counts from the
detour's start (an IF's or ELSE's target written by a movable
assembler pass).

`Apply(file, code, repairs)` walks the repairs for one GPL chunk:

1. Skip the repair when `Offset + Expect.Length` exceeds the
   script, when the bytes at `Offset` differ from `Expect` (another
   release, a mod: leave the script alone), when `Replace` is
   shorter than `Expect`, or when `Replace` is longer but `Expect`
   is shorter than 3 bytes (a JUMP cannot fit).
2. Same-length repair: copy `Replace` over `Offset` in place.
3. Detour repair: the detour area starts as one `EXIT_GPL` sentinel
   byte (so a script that runs off its end still stops), then each
   detour appends `[Replace][JUMP back to Offset + Expect.Length]`,
   with every `Relocate` word rebased from detour-relative to
   absolute (target = word value + detour's start address). The
   expect range is filled with `EXIT_GPL`, then the first 3 bytes
   become `JUMP detour-start`. Script code length is unchanged;
   the appended block is new bytes at the tail.

Detours stack: several per chunk accumulate in stable order, each
JUMPing back to just after its own expect range, so disjoint
repairs compose and no two JUMPs interact.

Only `GPL`-kind files get repairs in their embedding (their
`RepairedScripts` gates on `GplFileKind.Gpl`); JUMP addressing is
chunk-relative, so MAS chunks would need their own decision if ever
targeted.

Why this is sound: JUMP targets are absolute byte offsets within
the chunk (our branch-semantics verification, `gpl-bytecode.md` §5a);
the appended block lives inside the same chunk, so every existing
address keeps meaning what it meant; and 15-bit addressing (max
32767) dwarfs any realistic chunk plus detours.

## 3. What changes for us

Their engine patches scripts at load time, in memory; our darkfix
patches `GPLDATA.GFF` on disk. Three consequences:

1. **Chunk-relative addressing replaces absolute offsets for
   detour-carrying fixes.** A grown chunk moves later chunks (or,
   under `gff-edit`'s writer policy, the grown data is appended at
   end-of-file with the TOC entry updated), so any fix expressed in
   absolute file offsets can no longer share a manifest with a
   detour fix naively. The applier resolves detour repairs through
   `gff-edit`'s chunk lookup (one implementation, same as
   `exe-patch` consuming `ovr-map --json`), and fingerprints stay
   on original bytes: expect matches the chunk's bytes at
   chunk-relative offset before anything grows.
2. **Apply order**: same-length fixes first (their offsets and
   fingerprints are computed against the original layout), detours
   last (each detour's appended block must not disturb another
   chunk's resolved location). The existing composition rule
   (disjoint ranges, refuse overlap at check time) extends to
   detours unchanged: expect ranges are what must be disjoint.
3. **`gpl-asm` grows a movable assembly mode.** Our `patch_label`
   test already rewrites label words after assembly; the detour
   form is the same operation generalized: assemble the detour
   source once to learn label offsets, then emit with each label
   word rebased to `detour_start + label_offset`. Their
   `AssembleMovable` proves the shape; our implementation follows
   our own assembler's idiom.

Guard rails we add beyond theirs:

- Detours only on chunks whose final length stays under 0x8000
  (15-bit JUMP reach). All DS1 GPL/MAS chunks are far below this.
- The appended block's layout is fixed:
  `EXIT_GPL | detour 1 | JUMP back | detour 2 | JUMP back | ...`,
  detour order = manifest order, so the patched file is
  deterministic and re-verifiable.
- A detour fix's `.md` documents the disassembly of the detoured
  region and the new block, same bar as the same-length fixes'
  analysis sections.
- The selftest applies each detour fix to the canonical file and
  re-disassembles the patched chunk with `gpl-disasm`: the result
  must decode cleanly (no unknown bytes), and every branch target
  inside the patched chunk must land on an instruction boundary.

## 4. Adoption gate (every repair, borrowed or ours)

Brandon's rule from the 2026-11-13 decision: double-check and
confirm everything before it becomes opends canon. Concretely, a
repair ships only after all five:

1. **Fingerprint check**: expect bytes match the canonical GOG 1.10
   file at the claimed site. (Done for all 23 yuan-ti sites,
   2026-11-13.)
2. **Semantic review**: the operand-level change is re-derived
   independently from our own disassembly and agrees with the
   claimed game behavior (what reads/writes which variable, which
   handler the target address belongs to). A fix whose rationale we
   cannot re-derive does not ship, however clean its fingerprint.
3. **Assemble check**: the patched chunk reassembles and
   re-disassembles cleanly through `gpl-asm`/`gpl-disasm`.
4. **Runtime QA**: a DOSBox session reproduces the bug on the
   unpatched install and observes the fixed behavior on the
   patched one (the oracle rig: overlay mounts, sound on, capture
   per site).
5. **Credit**: the fix's `.md` and the darkfix-ds1 patchnotes entry
   name the source; the tag message carries the entry verbatim, so
   the release itself carries the credit.

## 5. Gate status (updated 2026-11-13, same day)

Steps 1-3 ran the same day the repairs were classified; the record
is [`gate-review-yuan-ti-2026-11-13.md`](gate-review-yuan-ti-2026-11-13.md):

1. Fingerprints: 23/23 static sites clean (the 6 Legcrusher guards
   are runtime-assembled upstream; their six PRINT_STRING sites
   verified as the exact shipped lines instead).
2. Semantic review: 29/29 confirmed against our own disassembly,
   zero disagreements. Every named flag, handler, and mirrored
   code path cross-checked in the corpus (MAS 9's registration and
   gates, GPL 137's pick and rip paths, the GF695/GF505/GF339
   writers).
3. Assemble check: 250/250 chunks reassemble byte-identical
   through `gpl-asm` with validation on (patched chunks to the
   expected patched bytes, untouched chunks to originals).
4. Runtime QA: pending (Brandon's DOSBox sessions; the checklist
   is exchange-yuan-ti-2026-11-13.md §4).
5. Credit: the v0.1.4 release carries the names; per-fix credit
   rides each shipping release.

## 6. Implementation status

The applier half landed 2026-11-13 (gate steps 1-3 all green
before any of it was written): `darkfix.patcher` gains `GplRepair`
(chunk-relative, fingerprint-checked) and `apply_gpl_repairs`
(extract via `gff-cat extract`, compute all chunks all-or-nothing,
replace through the existing `apply_gff_chunk` append policy),
with the reviewed `Apply` algorithm as the contract. Proof: the
seven published fixes applied chunk-relatively produce
byte-identical output to the existing absolute path
(differential test), the gate-confirmed mindhome detour produces
byte-identical patched-chunk bytes to the review pipeline's
independent construction, and the selftest's detour block covers
the pure math (in-place, JUMP+fill site, relocated label, JUMP
back, oversize and overlap refusals) plus the full
extract/replace round trip on a synthetic GFF when `gff-cat` is
available. The existing 001/002 fixes stay absolute-offset until
a reviewed migration (their selftest hashes are the regression
net); a detour fix must not share its target file with an
absolute-offset fix until then (documented in
`patch-workflow.md` §4.2). Still to come: the `gpl-asm` movable
assembly mode, landing with the first source-authored detour fix
(the byte+relocate format is enough to adopt the reviewed
yuan-ti encodings).

## 7. What this unblocks

- **Re-opened triage rows** (ours to author once the applier
  supports detours): 3.2(1b), 3.2(2), and the re-ask half of
  3.2(4).
- **yuan-ti implementations to review** under the same gate:
  3.2(1a) (Calvin's range-widening design vs our persistent-flag
  candidate; balance-class, off by default either way), 3.2(1c)
  (his three messenger detours at our named sites), 3.2(4)'s bonus
  half (his XP-award gate).
- **The 17 yuan-ti discoveries** ([`known-bugs.md`](known-bugs.md)
  §3.6): reviewed, then authored as our fixes with credit, at the
  cadence the runtime QA sessions allow. The dialog-inventing class
  (Legcrusher guards) ships only with the deliberate
  no-invented-behavior exception recorded there.
