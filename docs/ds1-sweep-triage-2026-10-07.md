# DS1 sweep triage, 2026-10-07 (Phase 9: every catalogued bug to a verdict)

The Phase 9 "fix each" box over known-bugs.md section 3's ~25
entries, driven by three research agents over the full 250-chunk
DS1 GPL/MAS dumps (main thread wrote the fixes and this record).
Verdict classes: **FIXED** (shipped in darkfix-ds1 0.1.2,
`fix.ds1.script-repairs`, disabled by default under the spec-5
one-enabled-fix-per-file rule); **FIX-CANDIDATE** (site proven,
fix authorable but gated on a runtime confirm, a chunk-growth
path, or a content decision); **ENGINE-SIDE** (the fault is in
DSUN.EXE, out of data-fix scope, with the evidence); **NO STATIC
SITE** (the reported mechanism has no GPL data half; the negatives
are as load-bearing as the fixes).

The finale map everything in 3.1 hangs on (new, agent-verified):
region 10 (RGN0A) is the White Sands overland and final-battle
map; the genie bottle is GPL-66 (3 wishes, GNUM54); the
"ready to face Draj's army" path sets gflag270 and tpors the
party to (85,20); on region entry MAS-10@0x1F sees gflag270 and
arms `noorders(239, GPL-62, -1297)`; **GPL-62@239 is the battle
driver** (ally tally over gflags 179/137/277/252/188/205/265/278/
136/134/268/65/267 into GNUM50, then stage clones gated on
GNUM49 = 0/1/2/3); stage advances ride the post-combat noorders
handlers (gated on gflag10 and GNAME32==0); alliance scoring is
GPL-86 entry 1 over gflag136 (riders), gflag137 (Gedron), and the
failure markers gflag179/gflag182 (GNUM72==51 = "no major
allies").

## 3.1 The final-battle family

| # | Variant | Verdict |
|---|---|---|
| 1 | Messenger's scroll not carried | **NO STATIC SITE.** The scroll (-30116) is referenced exactly three times corpus-wide (give from the corpse, ground-clone fallback, use-to-reread setting gflag407); no GPL code reads its presence, and the battle chain reads gflags 267/270/293/294/296/297, never 406-408. If the correlation is real, the check lives in DSUN.EXE. |
| 2 | Ally NPC leaves too early | **NO STATIC SITE / ENGINE-SIDE.** The endgame ssurran exit (GPL-78 entry 1) carries no state and Laussa is not in the driver's ally tally; the reported trigger-lifetime/region-transition race is engine-side. Corroborating asymmetry found: GPL-80/73 carry an explicit Wyrmias-walk rescue (gflag313 cleanup + GNUM52 bit 0x80) on some exits, and the Gedron region exits lack it. |
| 3 | Statue Wyrmias mishandled | **MECHANISM PROVEN, FIX NOT WARRANTED.** The "fled properly" bit (GNUM52 0x80) is settable only through the completed walk-off chain; stranding gflag313 (leave mid-walk) makes it unreachable. But bit 0x80 gates ONLY the climax TEXT (two flavor branches converge on the same `gpl fight`); no roster, stage, or flag depends on it. A dead-mask repair candidate exists (GPL-62@0x13CD's re-test uses the same 0x0080 mask, making its else branch dead code; mask bytes at abs 0x3FE97 would become 0x0030/0x0040) but it changes climax text only. |
| 4 | Enemies never load in the arena | **ENGINE-SIDE.** All population code is present and unconditional once the driver fires (stage clones at GPL-62@0x3D0/entry 3921/entry 4190); every battle tile is passable (GMAP flags 0x00 verified at the landing, spawn column, and wave positions). The failure is noorders firing cadence on item -1299/-1297 and the mode cells: DSUN.EXE scheduling. The MAS-10 entry-time-only arming is the data-side observation a runtime capture should confirm. |
| 5 | Stage cleared too quickly breaks the next | **FIXED (in 0.1.2, toggled).** The gate sub 4323 arms `noorders 4345`; entry 4345 checks `(GBIGNUM4+1) > (GNAME41/(60/3))` and exits WITHOUT re-arming when the window has not elapsed, stranding the chain permanently. Fix: the arm's entry 4345 -> 239 (the handler the gate would eventually re-arm), removing the strand at the cost of the intended inter-stage pause. ds1-patch/fixes/002-script-repairs.md. |
| 6 | "Army still gathering" with all alliances | **DOCUMENTED, NOT PATCHED.** The display chain is sound (GPL-86@1 recomputes GNUM35/GNUM72 from gflag136/137 plus failure markers); the failure markers gflag179/182 are set on failure paths and NEVER cleared by any of the 250 chunks, so one failure permanently depresses the score. Clearing them on a re-alliance path invents behavior with no no-op-or-restoration argument. The r/DarkSun "wandering at the well" warning also resolves engine-side: gflag276 (sands shifted) is written by no GPL chunk at all. |

## 3.2 Quest and NPC scripting

| # | Bug | Verdict |
|---|---|---|
| 1a | Draj serf duplicate obelisk gem | **FIX-CANDIDATE (needs chunk growth).** The deal guard is clone-local (`readorders(GNAME[39])==11`); MAS-10 clones a FRESH serf and zeroes GF260 on region re-entry, so the guard fails and the full deal block re-runs (second gem -1352). A persistent-flag guard or a follow-order re-issue needs inserted instructions; no same-length edit exists. Balance-class (item duplication): off by default per policy when authored. |
| 1b | Battlefield slave stops following | **FIX-CANDIDATE (needs chunk growth).** `follow GNAME[37];NAME(-198)` exists exactly once (GPL-132@0x38b); nothing re-issues it after a zone transition. Candidate carrier: MAS-9@0x9e-0xbe's ~40 bytes ordering already-departed elves, subject to gpl-asm byte accounting. |
| 1c | Dagger event never fires | **FIX-CANDIDATE (needs chunk growth).** MAS-9@0x63 registers the first-band trigger only when GF245 is already set at region-9 load, but GF245 flips mid-stay at GPL-58@0x1a/0x99/0xcc; players who never re-enter region 9 never get the registration. Fix: register the LOS trigger from GPL-58 when GF245 flips. |
| 2 | Alhena never at the campfire | **FIX-CANDIDATE (needs control-flow edit).** Statically provable unreachable condition: the caravan arrival script GPL-28@0x298 exits when GF123==1 (the caravan-raid flag, set at GPL-21@0x28a, never cleared), BEFORE the post-war GF138 branch that registers Alhena's LOS trigger and spawns her (-212, the corpus's only spawn site at GPL-28@0x51c). GF138 is set only after the final battle (GPL-62@0x1685), so every normal endgame has GF123 set and Alhena can never appear: the report ("has never materialized") is exactly this. The fix neutralizes the GF123 exit for the post-war case; needs if-depth rebalancing at authoring time. |
| 3 | Semyon freed before water | **NO STATIC FAULT.** Freed-first is explicitly handled (dedicated clone + water usewith + talk paths at GPL-5@1018/6530/560). Residual anomalies needing one runtime capture: GF28 set even on the refuse path (0x8b1), the coin-flip exit at 1797 (`rand(1)<1`), and the clone field72 question at 0x575. |
| 4 | Rebel Mindhome re-asks the spider quest | **FIX-CANDIDATE.** The router GPL-204@0xb2/0xd2 never consults its own completion flag GF695 (set at 0x5d6, read only by GPL-196/202); in the peace ending the spiders are alive, GF683 is 0, and the re-ask is permanent. A same-length varnum swap (683 -> 695) exists but drops the swore-peace suppression; the correct fix is a +2-byte expression through the chunk-grow path. Bonus finding: sub 830 re-awards GNUM16 += 5000 per re-talk once the spiders are dead; check for an XP loop in the Phase 10 playthrough. |
| 5 | Linara/Jasmine spellbook topic | **FIXED (in 0.1.2, toggled).** GPL-68@0xaa routes GNUM55==2 to `local sub 4942`, a one-line dead end with no menu; the fix repoints it to 209, the general menu (the delivered-extract entries stay hidden via LFLAG recomputation). ds1-patch/fixes/002-script-repairs.md. |
| 6 | Elven slaver leader wrong branch | **FIX-CANDIDATE (one content decision).** Three menu entries at GPL-46@0x58d ("No! Ally against Draj!", the denial, and the plain goodbye) all target 2200, the "Guards! Take these strangers to the slave pen!" consent scene; a goodbye routing to slave-pen consent is the reported wrong branch. Same-length menu-target repoint (e.g. to the loop-exit local-ret at 1590), pending the decision of which entries besides the goodbye leave 2200. |
| 7 | Undermountain prince body-block | **ENGINE/DESIGN-SIDE.** The move request (GPL-202@576, `flee -38`) works until the escort's catch-up handler (GPL-74@1644: clear-los + follow) orders him back within ten tiles; suppressing it breaks the escort everywhere. Sites recorded. |
| 8 | Swiftbite chest wipe | **FIX-CANDIDATE.** The "fixed container reference" guess is wrong in mechanism: the reward machinery (GPL-183@0xe3e + GPL-184 subs 0x32a/0x416) clones rewards at FIXED TILES, (107-109,61)/(113-116,61)/(107,64), and region 11 places the player-hut chests exactly along that strip (1326 at (107,59)/(114,59), 1328 at (105,59), 1328/1330 at (109-113,66-69)); the engine's placement routing into the nearby chest is the wipe path (the retry ladder even tports blockers to Limbo between attempts). Fix: move the six clone tiles 2-4 tiles south (the script's own fallback row, y 61 -> 63/64); six same-length immediate edits. |
| 9 | Wyrm Temple Magera spawner | **FIX-CANDIDATE (needs one runtime observation).** The chamber machine (GPL-75@0x563) clones the next slave at the party's own arrival tile (38,3), and a SECOND counter (GPL-162@0xde5/0xe19) range-counts any slave within 400 and tports it to Limbo without the escort: desynchronizing gnum[63] and firing the clone out of context. Two candidate fixes (decouple tiles vs drop the second counter); one capture picks between them. |
| 10 | Hound Necklace kills prisoners | **FIX-CANDIDATE (balance-gated).** Single site corpus-wide: GPL-55@0x155-0x1c6, a party-wide worn-item search (item 2019, the same raw-tail form as the Door-of-Eyes worn check) then `p damage GNAME[39], 1000`: flat 1000 kills any prisoner, gated on nothing else. Data fix: the 0x3e8 immediate to a wounding value; balance change, off by default per policy. |
| 11 | Keldar fight drags in Dagolar + slimes | **FIX-CANDIDATE.** The reveal chain (GPL-48@0xd0/0x1fe) checks nothing about the attacker and clones Dagolar AT THE PARTY'S TILE (0x393/0x442/0x47e), then the LOS finale clones TEN slimes at fixed (16,26) with `hunt` across the map. Fix: retarget the three clone-at-party sites to the script's own fixed-sanctum variant (16,24); same-length operand swaps. |
| 12 | Hermit/ranger dialog loop | **FIXED (in 0.1.2, toggled).** The ranger-leave re-arm at GPL-100@0x684 arms entry 86, the HERMIT's handler, occluding the ranger's own MAS-27 registration (100@445); the endless loop and the duplicate Iron Necklace (the corpus's only give site, with a ground-drop fallback) follow. Fix: entry 86 -> 445, the deadtrigger occlusion design exactly. |
| 13 | Charm re-entry | **PARKED (engine-shaped, no named offender).** Registrations persist until overwritten or explicitly deregistered; battle scripts do not auto-clear their own talk registrations. Per-script fixes are possible; the 2009 report names no object. |
| 14 | Slaver-camp alarm everywhere | **FIX-CANDIDATE (needs one runtime capture).** The alarm is one GLOBAL pair (GF20/gnum91) written by GPL-137@0x1084-0x1151 after a yard-box check that never asks WHO attacked; the globals are read by chunks in other regions (the "everywhere"). Fix: attacker-gate the write (GNAME38 is already in scope at 0xf7f); the byte choice needs one capture of the attacker register at the attacktrigger. |

## 3.3 Engine-level items

| # | Bug | Verdict |
|---|---|---|
| 1 | Area item limit (Gem Fields) | **PARTIAL, data-shaped after all.** The suspected engine map-object cap is NOT supported by any documented cap (1050 visible-object slots, 400 instance rows). The 3-gem ceiling matches the three shared opened-dome records (2007/2026/2027, count 1 each): if the count field is record-scoped, all opened domes of one id share one count. And the lost-gem case matches the unchecked clone ladder (GPL-164@0x2e1-0x340 consumes the count even when the clone fails). One runtime observation (open two same-id domes, use both) picks between the two data fixes. |
| 2 | Ghost inventory slot | **ENGINE-SIDE.** Slot-byte machinery (screen-flow 8.3: the 0x69DF0 load fixer, the 0x6F8B9 unequip strip) plus shipped authoring-residue instance indices (object-formats 4.1) is exactly the ghost-slot shape. |
| 3 | Save mid-event deletes objects | **ENGINE-SIDE.** The save writer (DS1 ovr13+0x7cc, census row 3a) snapshots live DARKRUN state verbatim (engine-quirks 3); mid-script Limbo tports become permanent. No GPL half to patch generically. |
| 4 | Stat-boost gear while carried | **ENGINE-SIDE.** Grant keyed to possession, strip keyed to slot removal (unequip -> item +15 -> 0x5B8:0x115/0x7F at 0x6F8B9); genie rest is engine request 1/4. No GPL site. |
| 5 | Random crashes | **ENGINE-SIDE** (no static anchor); stays on the played-save loop. |

## 3.4 Minor rule deviations (one line each)

- Fire elemental +1 immunity: the resistance rows live in the EXE-side enum record (+0xa8/+0xd2/+0xda, read at ovr32 0x7b4be); the SEGOBJEX byte that selects the enum also drives specials, so the data key is not clean. Engine-side value, data-side key.
- Psionic Blast real HP: the power table is in DSUN.EXE (file 0x41F70; record 170); EXE patch, outside data scope.
- Gladiator AC without armor: no gladiator exception exists in the rules block (rules-tables.md); engine recompute (0x4E0:0x7F / ovr46 family).
- Firewall double damage: combat tile-effect service; no GPL wall script owns per-entry damage in DS1.
- Difficulty affects only new spawns: spawn-time scaling; live objects never re-read it. Arguably by design.
- Bodies vanish on reload: corpses are runtime visible-object state (engine-quirks 12); no persistence path.
- Silt Sea North pull inconsistency: two authored paths (per-guard sight pull GPL-92@0xe vs group aggro `request 18` at 0x107b); sight-vs-attack, not a bug. Not worth fixing.

## Shipped in darkfix-ds1 0.1.2, enabled by default from 0.1.3

`fix.ds1.script-repairs` (fixes/002-script-repairs.md): the
hermit/ranger entry repoint, the Linara menu repoint, and the
final-battle stage-gate repoint. 0.1.2 shipped it disabled under
the old spec-5 one-enabled-fix-per-file rule; the rule was amended
the same day (disjoint same-file fixes compose), and 0.1.3 ships
both GPLDATA fixes enabled, the applier composing them into one
write with the merged hash pinned in the selftest.

## What the box still owes

The FIX-CANDIDATE rows split three ways: chunk-growth edits
(1a/1b/1c, 2, 4) wait on the gpl-asm grow path or a per-file
composition decision; capture-gated edits (9, 14, 3.3-1) need one
DOSBox observation each; content-gated edits (6, 10, 11, 8) are
same-length and ready, pending the balance/default decisions
policy already answers (off by default) and one branch-choice
call (6). The ENGINE-SIDE and NO STATIC SITE rows are closed as
written verdicts with their evidence above.
