# QA save suite: the bug-capture campaign (2026-11-20)

The companion to the playthrough guide
([playthrough-qa-guide-2026-11-20.md](playthrough-qa-guide-2026-11-20.md)):
the guide validates the darkfix fixes and rides the route; this suite
captures engine-level regression and community-bug evidence that the
route would otherwise merely avoid or mention. Save names here coexist
with the guide's `QA-<letter>-pre` checkpoint saves.

Three tiers:

- **Tier 1** rides the main run (a save + one observation at a site the
  route already visits).
- **Tier 2** is a dedicated reproduction branch: fired on a separate
  save/copy, NEVER on the main playthrough state.
- **Tier 3** is opportunistic forensics for intermittent or poorly
  understood failures.

Discipline for every card: community-reported behavior is a lead, not
proof. Reproduce against this exact build (GOG 1.10 + darkfix) before
classifying anything as a defect, and keep known limitations,
intentional behavior, exploits, and genuine regressions separate in the
final report.

**Two result classes, kept separate in every report**: **fix
validation** (does the enabled repair behave correctly: the guide's QA
checkpoints) and **game regression testing** (does unrelated original
behavior still hold: this suite's 1.1 README set and community cards).
A passing checkpoint establishes the first only: passing the Darkhold
dead-trigger checks confirms those repaired registrations, not that the
whole Darkhold sequence is sound.

---

## 1. DS2: the SSI 1.1 README regression set (all 20 items)

The fix list SSI documented in the README.TXT shipped with 1.10
(known-bugs.md section 1) is the baseline; known-bugs.md section 4
records that no separate DS2 1.02 artifact ever surfaced, so this is
the pre-1.10 accumulated fix list, historically mislabeled "1.02". The
1.10 build should retain every one of these fixes. One save each.

| Save | Route anchor | 1.1 README item | Evidence to record |
|---|---|---|---|
| `DS2-SORROWS-chest-pre` | Sorrows, before the trapped chest | 3 | does a character transform into a chest? |
| `DS2-PYR-rest-pre` | Kalak's Pyramid entry | 1 | rest lockup? repeat after reload |
| `DS2-MF-door-pre` | Mind Flayer Underdark secret door | 2 | crosses freely in both directions? |
| `DS2-CHARM-clear-pre` | any combat with a caster | 4 | charm and fear cleared after combat? |
| `DS2-YUANTI-party-pre` | Yaunti caves transition | 5 | party intact through the caves? |
| `DS2-SNAGGLE-potion-pre` | Snaggle + the Potion of Heroism | 6 | XP delta; reward exactly once |
| `DS2-TAPESTRY-transition-pre` | the mosaic regions | 7 | no trapped party; return trip clean |
| `DS2-VOLCANO-map-pre` | Volcano north and south wings | 8 | each wing's overhead map correct (Ctrl+F5) |
| `DS2-TYR-guard-talk-pre` | the Tyrian guard (Tyr) | 9 | dialog completes, no crash; keep the dosbox log |
| `DS2-TRANSFER-pre` | several ordinary transitions | 10 | no lockups outside the (known) elevator |
| `DS2-MUSIC-combat-pre` | a long combat | 11 | music dropout/stutter? (audio rides GOG's OGG remap under staging) |
| `DS2-PRAYER-cast-pre` | damaged-party combat | 12 | Prayer effect on party and enemies |
| `DS2-SPEED-config-pre` | the Preferences screen | 13 | CAUTION: the walkthrough reports opening Preferences via Tab hangs when closed early in DS2. Attempt with a fresh save + backup; if it hangs, that IS the evidence (a 1.1-README regression datum). Do not force it. |
| `DS2-MAGNOLIA-second-pre` | second Magnolia rescue | 14 | no teleport off-screen |
| `DS2-UMB-HULK-combat-pre` | Sorrows umber hulks | 15 | hulks engage and behave |
| `DS2-LW-finale-pre` | before the Lord Warrior | 16 | speech plays, combat begins |
| `DS2-CRASH-<n>-pre` | before a few substantial encounters | 17 | non-deterministic: pre-encounter saves + dosbox logs + video; no single save guarantees reproduction |
| `DS2-CHAND-quest-pre` | before the chandelier repair | 18 | quest advances after the repair |
| `DS2-RANGER-XP-pre` | ranger XP tracking | 19 | SCOPED: the level-15 cap and the XP bank clamp (chargen-flow section 3) make 1,440,000 practically unreachable in this run; record N/A unless the party approaches the figure. Do not manufacture the test through save editing: a documented limitation beats an artificial result. |
| `DS2-PENDANT-DARIYA-pre` | before the pendant goes to Dariya | 20 | no freeze |

**Difficulty note**: the imported party forces Hideous. Record it with
every combat regression so different HP totals are not mistaken for a
bug. Tier 1 of these: PYR-rest, SNAGGLE, MAGNOLIA-second, CHAND,
PRAYER (+CHARM-clear), UMB-HULK; the rest ride opportunistically.

## 2. DS2 community-bug investigation cards

All from the community walkthroughs (lead, not proof). Tier 2 unless
noted.

### High priority: Jumah / Crypt black-wall failure

`DS2-JUMAH-combat-pre`. Triggering combat around Jumah reportedly turns
the walls north of him into black segments and can break the western
exit niche; saving and reloading reportedly does not repair it.

1. Capture the clean state before speaking to Jumah.
2. Copy the save immediately before provoking combat (separate branch).
3. Trigger combat without securing his cooperation.
4. Inspect the walls and both niches; screenshots before/after.
5. Preserve the save, party position, and dosbox log either way.

Never fired on the main playthrough state.

### High priority: Tyrian Mines S24 map-wide NO PATH

`DS2-MINES-S24-pre`. Entering S24 (Mines Level 1 <-> Humbleton Forest)
reportedly renders the whole map `NO PATH FROM HERE`. Distinct from the
elevator freeze.

1. Record map state, party location, pathfinding before entering.
2. Enter S24; attempt several movement destinations.
3. Leave and re-enter if possible.
4. Preserve the save even without reproduction (baseline for engine
   state comparisons).

### Worth investigating: Volcano shop and Temple soft-lock

`DS2-VOLCANO-shop-pre`, `DS2-VOLCANO-fight-pre`. Merchant
potion-purchase problems and a potential fight soft-lock. Record
merchant identity, potion type, price/quantity, inventory before and
after; for the fight, the exact lock sequence. Note: the walkthrough
flags Volcano content as Easy-difficulty-only and the import forces
Hideous: if the content is absent, record that instead.

### Worth investigating: Sinking Stones maze

`DS2-SINKING-STONES-pre`. Route, timing, cycles; whether a failed jump
strands the party. A normal timing failure is not an engine defect; the
useful evidence is a repeatable state where no valid route remains.

### Worth investigating: Humbleton east chamber

`DS2-HUMBLETON-east-chamber-pre`. One eastern chamber reportedly stays
inaccessible after the wall interaction: fixed map defect vs
progression failure. Capture the wall interaction, the map, movement
attempts, visible geometry vs actual pathing.

### Worth investigating: Crypt alcoves disappearing

`DS2-CRYPT-alcoves-pre`. Count bodies, dropped items, and opened
containers; test the same alcove before and after clearing objects by
leaving and returning. Excess region objects are a proposed cause, not
a proven one: no conclusion without a repeatable comparison.

### Worth investigating: Veiled Alliance scribing-book loop

`DS2-VA-book-reset-pre`. Entering the psurlon dimension (or leaving and
returning) reportedly resets the book's read count. Exploit-class, not
a blocker: record read count and XP before and after the transition
(quest-state persistence evidence).

## 3. DS1 investigation cards

### High priority: saving during scripted activity

`DS1-SEWERS-idle-pre`, `DS1-SEWERS-event-pre`. The guide says never to
save mid-event; this card collects the evidence the avoidance skips.
Branch off the main run:

1. Save before the active encounter or moving-object sequence.
2. Copy the save (separate branch).
3. Save DURING the activity on that branch.
4. Reload and compare interactable objects.
5. Record missing doors, containers, pickups, and access items.
6. Preserve both branches' `SAVE*.SAV` and `DARKRUN.GFF`.

### High priority: Gem Fields dome behavior

`DS1-GEMFIELDS-domes-pre`. The triage doc (row 1) narrowed the item
limit to data: the 3-gem ceiling matches the three shared opened-dome
records (2007/2026/2027, count 1 each) — same-id domes may share one
count — and the lost-gem case matches the unchecked clone ladder
(GPL-164@0x2e1-0x340 consuming the count even when the clone fails).
One observation picks between the two data fixes:

1. Open two domes of the same type, one at a time; record gem count,
   object state, and inventory after each.
2. Repeat with different dome types if possible.
3. Map captures before and after each opening.

### High priority: Swiftbite chest reward collision

`DS1-SWIFTBITE-reward-pre`. Triage row 8 replaced the "fixed container
reference" guess with a mechanism: the reward machinery
(GPL-183@0xe3e + GPL-184 subs 0x32a/0x416) clones rewards at FIXED
TILES, (107-109,61)/(113-116,61)/(107,64), and region 11 places the
player-hut chests exactly along that strip; the engine's placement
routing into the nearby chest is the wipe path (the retry ladder even
tports blockers to Limbo between attempts).

1. Put a few disposable, identifiable items in the chest.
2. Copy the save before the alliance reward event (separate branch).
3. Trigger the reward; inspect the chest.
4. Compare contents, count, and object placements.

The static candidate fix (move the six clone tiles to the script's own
fallback row, y 61 -> 63/64) rides this evidence.

### Worth investigating: Wyrm Temple Magera spawner

`DS1-WYRMTEMPLE-spawner-pre`. Triage row 9: the chamber machine
(GPL-75@0x563) clones the next slave at the party's own arrival tile
(38,3) while a SECOND counter (GPL-162@0xde5/0xe19) range-counts any
slave within 400 and tports it to Limbo without the escort,
desynchronizing gnum[63] and firing the clone out of context. Two
candidate fixes exist; one capture picks between them. Record party
coordinates before the chamber sequence, whether Magera appears out of
context, the slave count, and escort sync; preserve the save
immediately before the second counter/spawner sequence.

### Worth investigating: Keldar fight extras

`DS1-KELDAR-encounter-pre`. Party position, combat initiator, enemy
roster, whether Dagolar and the ten slimes join from different initiation
positions; positioning/clone-location candidate.

### Worth investigating: Hound Necklace prisoner damage

`DS1-HOUNDNECKLACE-talk-pre`. Clean A/B: carry the necklace, record
prisoner HP, talk, inspect damage; reload; remove the necklace, repeat.
Only on a prisoner not needed for progression. The FAQ reports ~1000
damage.

### Worth investigating: charm re-entry

`DS1-CHARM-reentry-pre`. Charm an enemy whose conversation starts a
scripted fight; talk again after the fight; record whether the battle
script re-fires and whether the enemy survives (2009 FAQ class).

### Additional DS1 tests

| Save | Test |
|---|---|
| `DS1-MINDHOME-reask-pre` | After the spider quest, talk to the leader again: record the repeated question AND the XP. Extends the guide's W checkpoint, which tests only the award half; the re-ask half (the GPL-204 router never consulting GF695) is in no shipped fix. |
| `DS1-SLAVER-alarm-pre` | Followers fighting near the slaver camp: does the alarm state leak into other regions? |
| `DS1-ELVEN-branch-pre` | Preserve the Elven slaver leader conversation before denial/goodbye options; record which branches lead to the slave-pen consent scene. |
| `DS1-SEMYON-order-pre` | Give-water / refuse-water / free-first on separate branches; record GF28 and the dialog outcomes. TRIAGE CONTRADICTION on record: sweep-triage row 3 finds freed-first EXPLICITLY HANDLED (no static fault; GF28 set even on the refuse path at 0x8b1, a coin-flip exit at 1797, the clone field72 question at 0x575). This A/B arbitrates the community warning against the 1.10 data. |
| `DS1-INVENTORY-ghost-pre` | Forensic baseline for the ghost-slot report: clean inventory + container state preserved; record odd item ids, prices, equipment behavior. Not a deterministic repro. |

## 4. Charged-weapon disappearance (DS2)

`DS2-CHARGEDWEAPON-lastcharge-pre`. Tier 2. The outcome should be
unambiguous:

1. Take a Beast Club or Life Stealer to exactly one charge.
2. Record inventory before use.
3. Use the final charge; record inventory immediately.
4. Save/reload and inspect again.
5. Determine: disappears, changes id, or reverts to a normal weapon.

## 5. Tier checklists

Tier 1 (ride the main run):

- [ ] DS2: Pyramid resting (`DS2-PYR-rest-pre`)
- [ ] DS2: Snaggle potion XP (`DS2-SNAGGLE-potion-pre`)
- [ ] DS2: Magnolia second rescue (`DS2-MAGNOLIA-second-pre`)
- [ ] DS2: Chandelier completion (`DS2-CHAND-quest-pre`)
- [ ] DS2: Prayer + charm/fear clearing (`DS2-PRAYER-cast-pre`, `DS2-CHARM-clear-pre`)
- [ ] DS2: Umber Hulk behavior (`DS2-UMB-HULK-combat-pre`)
- [ ] DS1: Mindhome re-ask (`DS1-MINDHOME-reask-pre`)
- [ ] DS1: Gem Fields domes (`DS1-GEMFIELDS-domes-pre`)
- [ ] DS1: Keldar encounter (`DS1-KELDAR-encounter-pre`)
- [ ] DS1: Magera spawner (`DS1-WYRMTEMPLE-spawner-pre`)

Tier 2 (dedicated branches, never the main state):

- [ ] DS2: Jumah black wall
- [ ] DS2: Mines S24 pathfinding
- [ ] DS2: Volcano shop + Temple soft-lock
- [ ] DS2: Crypt alcoves
- [ ] DS2: charged-weapon exhaustion
- [ ] DS1: Sewer mid-event save
- [ ] DS1: Swiftbite chest collision
- [ ] DS1: Hound Necklace A/B

Tier 3 (opportunistic forensics):

- [ ] DS2: doorway/item graphics disappearing
- [ ] DS2: combat music stutter
- [ ] DS2: random combat crashes
- [ ] DS1: ghost inventory slots
- [ ] DS1: global slaver alarm
- [ ] DS1: charm re-entry
- [ ] DS1: random crashes/lockups

## 6. Evidence strategy

Every investigation save preserves three states:

1. **Pre-trigger**: the untouched save immediately before the action.
2. **Evidence**: the save or runtime files immediately after the
   failure, BEFORE reloading or attempting a workaround.
3. **Control**: a second save where exactly one variable changes
   (party size, inventory load, position, dialogue choice).

DS2: `DARKRUN.GFF` travels with its save set, always. For any freeze,
the untouched runtime file is copied out before restarting (the
elevator card in the playthrough guide is the model).

Investigation metadata template:

```text
bug_id:
game_version:
patch_version:
region:
party:
difficulty:
trigger:
expected:
actual:
dosbox_cycles:
reproduced:
screenshots:
save_filename:
save_slot:
runtime_files:
baseline_save:
control_save:
steps_to_reproduce:
workaround_attempted:
workaround_result:
related_issue:
report_class:
```

## 7. References

- Shattered Lands FAQ: https://gamefaqs.gamespot.com/pc/564606-dark-sun-shattered-lands/faqs/58639
- Wake of the Ravager walkthrough: https://gamefaqs.gamespot.com/pc/564927-dark-sun-wake-of-the-ravager/faqs/81038
- Crypt walkthrough: https://classicgames.sorcerers.net/darksun2/23crypt.php
- Repo: known-bugs.md sections 1 and 3; ds1-sweep-triage-2026-10-07.md
  rows 1, 3, 8, 9; playthrough-qa-guide-2026-11-20.md.
