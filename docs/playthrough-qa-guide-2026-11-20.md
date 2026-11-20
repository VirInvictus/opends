# Playthrough + runtime-QA guide: darkfix run, 2026-11-20

The full walkthrough for Brandon's QA playthrough: DS1 on darkfix-ds1
0.2.0-beta.4 with all 12 fixes enabled (the run IS the issue-#18 runtime
QA), then DS2 on darkfix-ds2 0.1.2 with the mines-elevator capture. The
rig, versions, and environment live in the repo root
[`QA_REPORT.md`](../QA_REPORT.md); this file owns the play plan itself.
Sources: the repo's own data docs (chargen-flow, rules-tables, both spell
catalogues, both item catalogues, container contents, known-bugs, the QA
packet) plus gibberishh's completionist walkthroughs on sorcerers.net for
route order and community-known behavior. Engine facts carry repo
section refs; community facts say "walkthrough".

---

## 0. Operating the rig

```sh
darksun          # picker; prints each install's patch identity
darksun ds1      # Shattered Lands, straight in
darksun ds2      # Wake of the Ravager, straight in
```

- Installs: `.testing_facility/ds1-patched/` (13 journal entries: noop +
  12 real fixes) and `.testing_facility/ds2-patched/` (1 entry:
  deadtriggers). Both applied 2026-11-20, both `apply.py --verify` OK.
- Saves: `.testing_facility/<game>-saves/` (the C: overlay). The install
  is mounted read-only under an overlay mount; DSUN.EXE can never touch
  it. Backup a save set by copying `Save*.sav` **plus `DARKRUN.GFF`**;
  DS2 restores them together or the party lands outside map bounds.
- DOSBox: dosbox-staging 0.82.2, per-game confs in
  `.testing_facility/dosbox/`. SB IRQ 7 (the staged SOUND.CFG records
  IRQ 7; pairing it with GOG's IRQ 5 self-exits the game in ~2.4 s),
  `mididevice = none`, `mpu401 = intelligent`, cycles fixed 30000,
  machine svga_s3, windowed, aspect on. Ctrl+F5 screenshots.
- Sound must stay ON: MEL aborts without a working audio stack.
- DS2's 40 CD tracks load from GOG's OGGs automatically (verified in the
  launch log); DS1 music rides the primary conf.

---

## 1. The party

### 1.1 Requirements (all enumerated first)

| # | Requirement | Source |
|---|---|---|
| R1 | A ranger (engine class band 13-16) in the party | QA site T (fix.ds1.tracking reads those codes) |
| R2 | Divine healing incl. Raise Dead: a druid leg (druids get full Cosmos; clerics cap at Cosmos 3, no Cure Serious/Raise Dead) | walkthrough + rules-tables.md |
| R3 | Preserver arcane coverage (Enlarge, Strength, Haste, Blink, Fireball, 2x Wall of Fire for the War) | walkthrough + spell-catalogue-ds1 |
| R4 | One dedicated thief leg (traps/locks; matters again in the DS2 import) | walkthrough |
| R5 | Gladiator frontline (-1 AC at level 5 per the walkthrough; XP row identical to fighter's) | walkthrough + chargen-flow §1 |
| R6 | A psionicist leg (Cell Adjustment self-heal, Biofeedback) | walkthrough |
| R7 | Every race/class combo legal per the decoded masks; dual gates met (current class prime >= 15, new class prime >= 17, human-only duals) | chargen-flow §2-3 |
| R8 | Level-9 cap discipline: the last class of each dual chain is the one pushed to 9; earlier classes stay <= 8 so they reactivate | chargen-flow §3 + walkthrough |
| R9 | Party of four (creation copies into 4 slots) | chargen-flow §2 |
| R10 | Halfling: NOT satisfiable; DS1 chargen creates seven races and skips halfling entirely. QA site H will be reported `not testable: no halfling creatable in DS1` | chargen-flow §2 (corrected 2026-11-17) |

### 1.2 The build

| Slot | Race/class | Sphere | Covers |
|---|---|---|---|
| 1 | Human **Preserver -> dual Thief -> Gladiator** | Metabolics | R3, R4 backup, R5 |
| 2 | Half-elf **Cleric/Psionicist/Thief** (multiclass 2/2/2 start) | Fire | R4 primary, R6, partial R2 |
| 3 | Human **Ranger -> dual Gladiator -> Water Druid** | Water | **R1**, R2, R5 |
| 4 | Human **Thief -> dual Gladiator -> Preserver** | Metabolics | R3, R5 |

All four True Neutral (walkthrough convention; keeps druid and sphere
choices clean). Legality (chargen-flow §2 masks, decoded): human 0xFF =
all classes; half-elf 0xFF = all; Ranger is legal for humans; the
Cleric/Psionicist/Thief triple is the walkthrough-confirmed half-elf
combo; Gladiator/Thief multiclass is NOT legal (why the dual chains run
Thief first, Gladiator later).

### 1.3 Exact stat targets (reroll spam; best-of-4 of 4d4+4+racial mod)

A rerolled stat that is the selected class's prime stat is engine-forced
to >= 17 (chargen-flow §2), so the 17s below are partly automatic. The
rest come from rerolling until they land. Everything else: push toward
19/20.

| Slot | Creation class (prime forced 17+) | Dual-gate stats needed |
|---|---|---|
| 1 | Preserver (INT 17+) | DEX 17+ (Thief gate), STR 17+ (Gladiator gate) |
| 2 | Cleric/Psionicist/Thief (WIS 17+ forced as max prime) | none (multiclass, no gates) |
| 3 | Ranger (WIS 17+ forced) | STR 17+ (Gladiator gate); WIS already 17+ = Druid gate |
| 4 | Thief (DEX 17+ forced) | STR 17+ (Gladiator gate), INT 17+ (Preserver gate) |

### 1.4 Dual order and XP discipline (DS1 XP table, x100; level cap 9)

Thresholds from chargen-flow §1 (entry k = minimum XP for level k+1):

| Class row | L2 | L3 | L4 | L5 | L6 | L8 | L9 |
|---|---|---|---|---|---|---|---|
| Cleric | 1,500 | 3,000 | 6,000 | 13,000 | 27,500 | 110,000 | 225,000 |
| Druid | 2,000 | 4,000 | 7,500 | 12,500 | 20,000 | 60,000 | 90,000 |
| Fighter/Gladiator | 2,000 | 4,000 | 8,000 | 16,000 | 32,000 | 125,000 | 250,000 |
| Preserver | 2,500 | 5,000 | 10,000 | 20,000 | 40,000 | 90,000 | 135,000 |
| Psionicist | 2,200 | 4,400 | 8,800 | 16,500 | 30,000 | 100,000 | 200,000 |
| Ranger | 2,200 | 4,500 | 9,000 | 18,000 | 36,000 | 150,000 | 300,000 |
| Thief | 1,200 | 2,500 | 5,000 | 10,000 | 20,000 | 70,000 | 110,000 |

- Creation: single-class starts at level 3 (XP = row entry 2 x100);
  the multiclass slot starts 2/2/2.
- Duals happen in play at level-up (human-only; gates in R7). Chain
  order per slot: 1) Preserver -> Thief -> Gladiator; 3) Ranger ->
  Gladiator -> Druid; 4) Thief -> Gladiator -> Preserver.
- The walkthrough's slot-1 anchor: Thief leg to ~1,250 XP (level 2 on
  row 8) before dualing to Gladiator.
- Slot 3's working milestones: Gladiator 5 (-1 AC, 16,000 XP on the
  warrior row) and Druid 5 (Raise Dead, 12,500 XP on the druid row,
  the cheapest L5 in the game). Ranger's class code sits in
  real_class slot 0 permanently, so the T check sees a ranger whenever
  region 8 is reached regardless of dual progress.
- 8-8-9 discipline: the LAST class of each chain is the one pushed to
  9; earlier classes stop at 8 so the final class can exceed and
  reactivate them (walkthrough; chargen-flow §3: humans advance slot
  0 only until duals open the later slots).
- XP is party-split (chargen-flow §1: AddXP splits across the party;
  multiclass legs split again, rounding down).

### 1.5 Level-up spell picks (spell ids = SPIN ids, spell-catalogue-ds1)

Slot 1 + 4 (Preserver):

- L1: MAGIC MISSILE (9); ENLARGE (6) only if the scroll (item 1413) is
  not yet found; ARMOR comes from the scroll (1400), do not spend a slot.
- L2: STRENGTH (24); MIRROR IMAGE (20, or scroll 1409).
- L3: HASTE (30), FIREBALL (28), BLINK (26); LIGHTNING BOLT (33) is
  scroll 1408.
- L4: WALL OF FIRE (55); STONESKIN via the scroll (1414, priced 400
  ceramic: grab on sight), MINOR GLOBE via scroll (1407).
- L5: keep two WALL OF FIRE memorizations reserved for the War.

Slot 2 (Cleric leg): BLESS (70), REMOVE FEAR (78), CURE LIGHT WOUNDS
(72); L2 AID (81), RESIST FIRE (88); L3 PRAYER (102), HOLD PERSON (87);
L4 CURE SERIOUS WOUNDS (113). The Thief leg does the traps; the
Psionicist leg trains: CELL ADJUSTMENT (152), BIOFEEDBACK (150),
ENHANCED STRENGTH (154), ID INSINUATION (165), SYNAPTIC STATIC (171),
EGO WHIP (164). MIND BLANK is universal at zero cost.

Slot 3 (Druid leg): BLESS (70), CURE LIGHT WOUNDS (72); L2 AID (81),
BARKSKIN (82), RESIST FIRE (88); L3 REMOVE PARALYSIS (106), CURE
BLINDNESS OR DEAFNESS (95); L4 FREE ACTION (118), PROTECTION FROM EVIL
10' RADIUS (122), CURE SERIOUS WOUNDS (113); L5 RAISE DEAD (136), CURE
CRITICAL WOUNDS (128).

Spell behavior warnings that shape these picks (known-bugs §3.7):
Mirror Image eats ANY spell landing on a mirrored character (1-75 lost,
burns an image); the preserver's DISPEL MAGIC (27) sets the no-spells
bit on everything in radius, party included (the priest's Dispel, 99,
is clean); PSIONIC BLAST (170) removes real HP; CAUSE SERIOUS/CRITICAL
roll d9s (2d9/3d9); Hold Undead/Turn Undead are undead-only and work.

### 1.6 One-each scrolls and bracelets (item ids, item-catalogue-ds1)

Exactly one of each scroll exists: 1400 ARMOR, 1401 DISPEL MAGIC,
1402 FIRE SHIELD, 1403 FLAME ARROW, 1404 COLOR SPRAY, 1405 HOLD
MONSTER, 1406 HOLD UNDEAD, 1407 MINOR GLOBE, 1408 LIGHTNING BOLT,
1409 MIRROR IMAGE, 1410 MONSTER SUMMONING III, 1411 RAINBOW PATTERN,
1412 SPIRIT ARMOR, 1413 ENLARGE, 1414 STONESKIN, 1415 SUMMON SHADOW,
1416 TURN PEBBLE TO BOULDER, 1418 WEB (1417 is the Wildwynd Wand).
Check this list before spending level-up slots.

Bracelets (psionic-power carriers, ids 1419-1430): Animal Affinity,
Graft Weapon, Life Draining, Mind Bar, Share Strength, Hero's Body and
kin. Keep them all.

Known chest contents (container-contents-ds1, exact):

| Chest/container | Contents |
|---|---|
| 1066 (Nazca) | A'poss's Heart (30050) + Flame Arrow scroll (1403) |
| 1208 | Nagi's Journal (30101) + Lightning Bolt scroll (1408) + Golden Pendant (30035) |
| 1360 (Lower Castle) | Dark Flame (30000) + Gems (1506, 1504) |
| 1517 | Color Spray scroll (1404) + Long Sword (1014) + Scroll 30115 |
| 1526 | Hound Necklace (2019) + Mirror Image scroll (1409) + Wand of Missiles (31007, 50 charges) |
| 1522 | Hound Necklace (2019) + skull |
| 2262 (skeleton) | Hold Monster scroll (1405) + Bag (1505) |
| 2293 | Cahulaks (30003) + Graft Weapon bracelet (1422) |
| 1570 (bag) | Wildwynd Wand (1417) |
| 2249 | Gem (1351) + Sling (2533) |

---

## 2. DS1 route, in order

Phases follow the walkthrough's chapter order. Every 🔊 block is a QA
checkpoint: save first with the exact name, run the check, note
pass/fail, file it (section 5).

### Phase 1: Arena and Slave Pens

- Grind the arena modestly: insult the ANNOUNCER for the next wave
  (never the king), rest in the pens between groups. Kill speed affects
  spectator gold and can trigger unsolicited second waves (walkthrough).
  Targets: humans at level 4 in their final class; slot 2 at 5/5/5.
- **Semyon: give him water BEFORE freeing him** or he bugs out
  (known-bugs §3.2.3). Fill the pot at the pens' water first
  (walkthrough 02arena).
- **Do not save during scripted activity** anywhere (known-bugs §3.3.3).

> ## 🔊 QA CHECKPOINT G — Sewer grate (fix.ds1.grate-hack, GPL 137)
> **Save:** `QA-G-pre` · weapon in hand, open the grate's use menu.
> **Pass:** "hack the lock off" is offered; a successful hack prints
> `<name> successfully hacks the lock off with his/her <weapon>. The
> grate opens.` and the grate opens; attacking it breaks the lock on a
> Strength-sized roll (sometimes fails). Unpatched: none of the three.

> ## 🔊 QA CHECKPOINT H — Halfling race test (fix.ds1.halfling-race, GPL 31)
> **Blocked by R10** (no halfling creatable in DS1). File:
> `H not testable: no halfling creatable in DS1 (chargen skips halfling)`.
> Decision on record 2026-11-20: report, do not save-edit a race.

### Phase 2: The Sewers

Churr and the Ratpack, the damsel, the temple. Save: `sewers-pre-temple`
at the entrance; no mid-event saves.

### Phase 3: Escape, then Return to the Slave Pens (walkthrough ch 10)

The return visit is the genocide/loot run (metal armor is the prize) and
carries two QA sites:

> ## 🔊 QA CHECKPOINT L — Legcrusher gone (fix.ds1.legcrusher-gone; GPL 136/139/141)
> **Save:** `QA-L-pre` · kill Legcrusher (half-giant trainer, -326),
> then walk to the arena gate and talk to Kurzak, then to Dinos.
> **Pass:** after he is dead, Kurzak's call, his three greetings, the
> half-giant answer, and Dinos's warning all use the replacement lines
> (fixes/009-legcrusher-gone.md lists each). Before he is dead, the
> shipped lines play unchanged. The invented dialog is the designed
> behavior (2026-11-13 decision), not corruption.

> ## 🔊 QA CHECKPOINT R — Trustee rounds (fix.ds1.trustee-rounds; GPL 137 @0x1740 -> GPL 8)
> **Save:** `QA-R-pre` · knock on the pen door and pick the fight path,
> watch the Trustee work, then talk to him.
> **Pass:** he keeps moving between his corners and his dialog is not
> stuck on "I'd love to talk more, but I have to get back to work"; he
> still opens for a bribe. Unpatched: the unguarded -= 2 on GNUM[20]
> drives the rounds state negative and he stalls at tile (0,0) on a
> fresh load.

### Phase 4: Fields of Draj

- Shops: fruit are single-cast components: green grapes = Bless, black
  grapes = Cure Blindness/Deafness, corn = Barkskin, pear = Cure Light
  (ids 31017-31031); never eat guavas (poison). Bracelets live here.
- Old One Eye (point 7): all his dialogue patiently, ask him to
  distract the guards, **stay behind him the whole way**, kill the
  guards when they leave. Reward: Armor scroll (1400).
- **MUST: the serf escort.** Point 9: take his proposition; he hands
  over the obelisk gem (deposit it at the obelisk, point 5; similar
  gems appear later, **never sell them**). Return to point 8 and wait
  for him to catch up before leaving through the gate.

> ## 🔊 QA CHECKPOINT S — Draj serf follow (fix.ds1.serf-follow, GPL 60 @0xCD8)
> **Save:** `QA-S-pre` · during the escort, walk more than 14 cells
> ahead of him, then exit through the region gate.
> **Pass:** the serf comes along anyway, and the obelisk gem is awarded
> exactly once (a later re-talk must not yield a second gem). This is
> the one balance-class fix; enabled for this run by decision.
- Activate the obelisk (activated obelisks teleport between visited
  regions: this is the fast travel).
- The item-multiplying exploit exists (walkthrough); SKIP it this run:
  it mutates inventory state in ways that can mask or fake QA
  observations.

### Phase 5: White Sands

Laussa & Ssovan, the obelisk. The dead body here carries the
**Messenger's Scroll (30058)**. Rule: in inventory from pickup until
after the final battle trigger; never drop it (known-bugs §3.1.1, no
fix exists). Save: `whitesands-scroll-in-inventory`.

### Phase 6: Teaquetzl

Chahl, the equipment merchant, the Visionary, the obelisk. **Never
store anything in the Swiftbite chest**: the alliance rewards later
spawn into it and can wipe stored items (known-bugs §3.2.8).

### Phase 7: Nazca Lines

Salt quest, the psionicist Maris. Chest 1066: **A'poss's Heart (30050,
quest item for Temple Ruins) + Flame Arrow scroll (1403)**.

### Phase 8: Red Sands Plateau

Obelisk; **Notaku, a merchant: sell spell components here, buy dye
later**; the Master of Mastyrials drops the Mastyrial Sting (1560).
Save: `redsands-post-obelisk`.

### Phase 9: Wagon Train, Sand Oasis, Elven Slavers

Wagon Train: **MUST, first allies**. Sand Oasis: Tyrian Butterfly
Wings (1558), A Dish Served Cold. Elven Slavers: the capture/release
arc, **MUST, second allies**.

### Phase 10: Elvish Caravan

Merchants, obelisk, the ambush, Drisana, Tidzio. **The caravan raid
here is the precondition for QA site A2 at the end: let it play out.**

### Phase 11: Messenger Route (region 9)

> ## 🔊 QA CHECKPOINT M — Region 9 messenger (fix.ds1.messenger-trigger, GPL 58 + MAS 9)
> **Save:** `QA-M-pre` · enter region 9 and stay through the elves'
> departure; do NOT leave the region.
> **Pass:** the messenger (-1297) arrives and his scene plays without a
> region re-entry. Unpatched he only ever arrives after a re-entry
> (the walkthrough's "return east and come back" is that workaround).

The messenger fight: kill him first (he summons a Blue Slaad next
round); his body holds the **Fire Shield scroll (1402)** and Pehtucl's
note (1,000 XP each for reading it once).

> ## 🔊 QA CHECKPOINT F — Battlefield slave (fix.ds1.slave-follow)
> **Save:** `QA-F-pre` · Hototo mistakes the party for Dagger (do not
> correct him; a female leader poses as the deputy); take custody of
> the slave, let Hototo walk off (killing the gang freezes the slave:
> let him leave), fight Dagger's gang, free Nirveli (3,000 XP each).
> Then leave region 9 entirely and come back.
> **Pass:** after the return he resumes following the party.

Elven Slavers Redux (Metiklt): clifftop slavers are reachable only by
summons/missiles/Hold Person (walkthrough). Sell components to Notaku
before teleporting to the caravan.

### Phase 12: Hot Springs, then Gedron

Hot Springs: copper mining (Metiklt's trick), patrol duty.

Gedron: deliver the extract, then:

> ## 🔊 QA CHECKPOINT D5 — Linara (fix.ds1.script-repairs, GPL-68 @0xaa)
> **Save:** `QA-D5-pre` · deliver the extract, then talk to Linara
> again.
> **Pass:** her menu opens (unpatched: a one-line dead end at sub 4942)
> and Jasmine's spellbook topic is discussable.

> ## 🔊 QA CHECKPOINT D4 — Lava Rifts ranger (fix.ds1.script-repairs, GPL-100 @0x684)
> **Save:** `QA-D4-pre` · approach the ranger, leave, return, twice.
> **Pass:** the ranger's own scene plays once, no endless hermit
> dialog (escape is clicking west), and **no duplicate Iron Necklace
> (31012)** lands in inventory. The Iron Necklace itself (12 charges)
  is the must-grab here.
- **Statue Wyrmias in Gedron: kill him outright or let him flee
  cleanly.** Half-striking him (neither kill nor clean escape) breaks
  the final battle; letting him flee properly adds him to it
  (known-bugs §3.1.3).

### Phase 13: Salt Oasis, Cedrilte, Undermountain, Castles

- Salt Oasis; Cedrilte (obelisk, Terror Bloom extract 1554, Uskuye:
  third-alliance material).
- **Undermountain: SAVE IMMEDIATELY FIRST** (`undermountain-pre-prince`):
  the prince can body-block the exit and asking him to move may not
  work; soft-lock (known-bugs §3.2.7). The Outcast, the Entity, the
  Queen, the Pact.
- Lower Castle: Serpent Boots; chest 1360 = **Dark Flame (30000)** +
  gems. The Keldar-fight caution (Dagolar + ten slimes dragging in,
  §3.2.11) belongs to the Dagolar chapter: save before it.
- Upper Castle: **MUST, third allies**, the Tara arc, return to
  Cedrilte.

### Phase 14: Temple Ruins, Lava Rift, Gem Fields

- Temple Ruins: Tynan's Heart (30030), Tristram-heart (30031), A'Poss
  (Heart from Nazca), The Lovers.
- Gem Fields: the labor chain, Ylakez & Ketzia, Makhlad, Hesutu, the
  lava domes. **An area item limit eats drops: inspect domes directly
  for the gem** (§3.3.1); six domes may yield only three gems.
- Charm re-entry caution (§3.2.13): a charmed enemy that triggered a
  battle script can re-trigger it by talking again.

### Phase 15: Silt Sea South/North, Ssurran Ruins, Wyrm chain, Wyrm School

- Silt Sea: Jasmine (she joins the War). Silt Sea North guards pull
  one-by-one vs going hostile as a group (cosmetic, §3.4).
- Ssurran Ruins: **MUST, the ssurran alliance. Let the quest-giver
  finish walking off-screen before leaving the region**, or the final
  battle locks (§3.1.2, no fix exists).
- Wyrm Belly, Wyrm Temple (expect the out-of-context slave Magera
  spawner quirk, §3.2.9; Hound Necklaces kill prisoners when talked
  to, §3.2.10: do not talk to prisoners while carrying one).
- Wyrm School: **Draketooth (30002, 1d8+1, 3 charges)**, Balkazar,
  **Terror Blade (2041, poison blade)**, Balk's Staff (30004).

### Phase 16: Captured Gladiators, Korbnor

War preparations. Korbnor: Cragg's body (reward: the +3 two-handed
Great Axe, 4,000 XP), the **Genie Bottle (30029)** and its **three
wishes**, the Orb of Knowledge (31014; save it, sell for 10,000 after
the War), the Shadow King's chain chest armor and +1 Blackmace. **No
resting in Korbnor** (walkthrough). Wish guidance: *genie's aid in the
war* is the standard pick (grants the Quicksilver Glove, 30021, and
shadows fight wave 1; it also sidesteps final-battle variant 4 by
skipping wave 1). Duplicate-a-weapon second (El's Drinker 30001 or
Dark Flame 30000; heavy weapons cannot be dual-wielded). Wealth is the
worst. The bottle dies after the War. Save: `korbnor-pre-wishes`.

### Phase 17: THE WAR (final battle)

Pre-trigger checklist (all MUST): Messenger's Scroll (30058) in
inventory; all three alliances formed; the ssurran quest-giver's exit
played out; Wyrmias handled correctly.

Pre-battle (walkthrough): Strength/Enlarge up, Blink + Haste on the
preservers, Resist Fire on everyone (your own walls), fruit consumed
to conserve slots, **both Walls of Fire pre-cast before entering
combat** (furthest wall first; allies will walk into them, leave
maneuvering room).

> ## 🔊 QA CHECKPOINT D6 — Final battle stage gate (fix.ds1.script-repairs, GPL-62 @4323)
> **Save:** `QA-D6-pre` immediately before the War triggers · clear a
> stage quickly, inside the inter-stage time window.
> **Pass:** the next stage still starts. Unpatched: the battle strands
> (the stage gate exits without re-arming). The old workaround,
> dragging out every fight, is what this fix retired.
> Variant 4 (empty arena): start any combat, use the genie bottle's
> "help me defeat an army" mid-combat; with the war-aid wish wave 1 is
> skipped entirely.

Victory: **Dragon's Bane (+4 long sword)** drops on the ground; the
commander's body has the +3 Great Axe and full metal armor. **Loot
everything before leaving: bodies vanish on map reload** (ground items
persist). 20,000 XP to the party.

### Phase 18: Epilogue

> ## 🔊 QA CHECKPOINT A2 — Alhena at the campfire (fix.ds1.alhena-campfire)
> **Save:** `QA-A2-pre` · with the caravan raided earlier in the run,
> after winning the final battle, arrive at the Elvish Caravan
> campfire.
> **Pass:** Alhena spawns and greets. Unpatched: she never
> materializes (the walkthrough author records the same bug
> independently).

Then the Teaquetzl war council (Chahl died; accept the chief offer,
1,000 XP each).

---

## 3. DS2 route, in order

Import the finished four (CharTran from DOSBox, both game dirs mounted;
forces Hideous difficulty; back up CharSave.gff first) or roll fresh
with Telepathy for everyone. Import notes: Helm of Contemplation and
Belt of Might become chest armor, leave equipped; cloaks/necklaces/
rings need re-equipping; bags of ceramics from conversion: do not
touch; extra heavy weapons enable dual-wielding.

1. **Tyr**: first battle; Notaku (merchant: dye, drake hides); Boric
   later (1,000 cp mine fee, haggles to 600). **Expected dead: the two
   Tyr thief-chase pickup rows on object -900** (no pickup handler
   exists in the shipped data; documented remainder, do not report).
   Attack row -418 is one of the 37 fixed rows: if fought, note the
   response.
2. **The Sorrows**: Shandel & Ladle, umber hulks, feyr teeth. The
   chest-transform trap is on the SSI 1.02 fixed list: a character
   turning into a chest is a REGRESSION report.
3. **Heist**: Arslan, Fayina, Acar, Boric, templars, Kalaobuta.
4. **Tapestry Puzzle 1**: the mosaic-region trap is 1.02-fixed.
5. **Magnolia**: ranger boots, rescue options.
6. **Jann Tribe**: Sultan's tent, the traitor. **Fixed row: the Jann
   talk pair -> GPL-69@1; talk to the Jann and note the scene plays.**
7. **Humbleton Forest**: Dariya, food run, pool of heroism, snake eggs.
   **Fixed rows: forest attack -146 -> GPL-29@1229 and forest look
   -445.** The pendant/Dariya freeze is a 1.02-fixed item: regression
   test. Charged-weapon caution starts here: **a Beast Club or Life
   Stealer whose charges run out VANISHES instead of reverting
   (known-bugs §2.3, unfixed): treat charge exhaustion as disposal.**
8. **Yuan-ti Temple**: Surrakina, Jestris, captives, Tantris, Solurnis.
   Party-disappearing-in-caves is a 1.02-fixed item: regression test.
9. **The Veiled Alliance**: Matthias, Aleka, Nnamdi; Tapestry puzzles
   2-3.
10. **Kalak's Pyramid**: Kovar's mansion, Abelard, Raenika. Resting
    here locking up is a 1.02-fixed item: regression test.
11. **VA HQ Assault**: the archives, four artifacts, Tapestry Puzzle 4.
    **Fixed rows: look -1923 and the tapestry look -1922 -> GPL-163@1800:
    LOOK at both.** Must-grabs: **Zorani's tunic (you are stuck and
    cannot finish the game without it; keep until the tapestry repair
    is done)**, the Ring of Strength (drain cover at 14, pushes STR to
    25), Coal Ember (brazier 16 -> opens Ringing Mountains), Feather
    Fan + Dye (chest 18), the torn tapestry (17). Cup of Life from
    Sylvain (ask anytime). Mine entrance: pay Boric (Boric is in Tyr,
    site 13); the mines sit northwest of Humbleton Forest, deliberately
    delayed until Notaku's drake-hide quest is done (walkthrough).
12. **Silt Sea Islands**: missions, Keign and Drisha, Generoe.
    **Fixed rows: the Silt Giants attack trio -418/-209/-406.**
13. **Cloud Tops**: half a flute, air drakes, **Lyre of the Winds**.
14. **Upper Mines**: Foreman Melody, the sick miner, **Blick (25,000
    XP; his note is the elevator key: read once, then droppable)**, the
    ore cars (wheel alignment: match the wheel's top-left corner to the
    axle), stone picks (campfire 3, sites 11/22/24), Winchester's
    whistle (keep), three ore veins at 18.

> ## 🔊 THE ELEVATOR CAPTURE (Card B route 1, cookbook/capture-sessions.md)
> The headline bug is UNFIXED in 0.1.2. Regions 56/57/58; the shaft is
> object 5807 (usetrigger 3753, 287 in MAS-57); the ride chain is
> GPL-287; the ride service (ovr35 + 0x1d2e) does
> `load_resource("PAL ", region)` inside the transition window, which
> is the freeze lead (elevator-digs-2026-11-02.md).
> **Save:** `elevator-pre-ride` to slot 1 immediately before using the
> switch; copy `before.SAV` out of the overlay. **Do:** ride.
> **If it freezes:** quit, copy the overlay's `DARKRUN.GFF` out
> untouched (its half-committed bytes at the freeze point are the
> evidence). **If it succeeds:** save slot 2, copy `after.SAV`.
> Either way run
> `save-inspect.py save-diff before.SAV after.SAV` +
> `save-semantic-diff.py` on the pair.
> **Workaround to keep playing:** dismiss all party members except
> one, ride solo, re-hire below. The walkthrough's alternate (drop
> enough items; the bug may be party weight) matches the engine's
> "Too heavy a load to carry" prompt on arm 37: worth one try, and
> whichever workaround works is itself a report datum.

15. **Lower Mines**: Black Furrow, Rattlenook, Hourglass, Spiderleg,
    the Chase, Old Digs.
16. **The Underdark**: soup kitchen, **the laboratory: the seven
    wizard-lab use-with pairs (-4413..-4419 with -4407 -> GPL-98@1) are
    fixed rows: use each pair and note the response.** Arena, Elder
    Brain, **Promere's Hammer**, interrogation.
17. **Ringing Mountains**: Draxans, Verini; the Fire Ruby (via the
    Coal Ember tapestry).
18. **Verini Temple**: the murder mystery, crafting.
19. **Volcano**: Galinix, Jumpin' Jack, the Seal. **Fixed row: attack
    -209.** Note: the walkthrough flags Volcano content as
    Easy-difficulty-only, and importing forces Hideous: if Volcano
    content is missing, that is one observation line, not a bug hunt.
20. **Cup of Life** -> **The Crypt**: grates, Kovar, Jumah, Hall of
    Heroes. **Fixed row: look -2994: LOOK at it.**
21. **Temple of the Cosmos**: Cosmic Scepter, the elemental gates, the
    Lord Warrior finale. "The Lord Warrior will give his speech and
    combat will begin" is a 1.02-fixed item: if he stands silent, that
    is a REGRESSION report.

Audio residuals that close with this run: one ear test of the OGG
music under the GOG conf (known-bugs §2.5; staging loads all 40 tracks,
so it can ride this rig), one clean-MEL launch confirm (§2.6, already
evidenced by every boot). One line each in the report.

---

## 4. Save discipline

- 10 slots; exceed via file copies (`Save*.sav` + `DARKRUN.GFF`; DS2
  restores DARKRUN with its saves, always).
- Titles, when the game takes them, follow `<game>-<area>-<why>`;
  keep a slot ledger in a scratch note regardless.
- Danger saves (irreversible or soft-lockable): `undermountain-pre-prince`,
  `pens-pre-trustee-fight`, pre-Dagolar before the Keldar fight,
  `korbnor-pre-wishes`, `QA-D6-pre`, `elevator-pre-ride`.
- QA saves: `QA-<letter>-pre` exactly as each banner says.
- Structural: at every region entry after a transition
  (`<area>-arrived`), and after every obelisk activation.
- Never save during scripted activity (dialog trees running, escorts
  in motion, events playing).
- Roster caution (unverified engine rows, §3.7.12): pause before any
  DELETE in the roster while scrolled; check thief skills on any newly
  created character (may spawn at 0).

## 5. Reporting

File issues at VirInvictus/opends titled `beta QA: <site letter(s)>
<pass/fail>` with:

```
site(s):       D1..D6, T, G, W, M, S, H, L, R, F, A2
result:        pass / fail per site
game version:  GOG 1.10
fixes enabled: darkfix-ds1 0.2.0-beta.4, all 12 (+noop); see
               .testing_facility/ds1-patched/darkfix-applied.json
environment:   QA_REPORT.md at the repo root (Fedora 45,
               dosbox-staging 0.82.2, SB IRQ 7 rig)
what happened: one or two sentences per site; Ctrl+F5 screenshots
```

A FAIL is as useful as a PASS. Anything unexpected (a crash, a wrong
line, a scene misbehaving nowhere near a fix) is worth reporting even
without a site letter. DS2 deadtrigger confirmations go in as their own
note (the fix doc's in-game scene proof rides these played sessions).
Issue #18 tracks the beta runtime QA.

## 6. Sources

Repo: known-bugs.md, qa-packet-ds1-script-repairs-beta.md,
chargen-flow.md, rules-tables.md, spell-catalogue-ds1.md,
spell-catalogue-ds2.md, item-catalogue-ds1.md,
container-contents-ds1.md, container-contents-ds2.md,
cookbook/capture-sessions.md, cookbook/edit-ds1-party.md,
elevator-digs-2026-11-02.md, QA_REPORT.md (repo root).

Community: gibberishh's completionist walkthroughs,
classicgames.sorcerers.net/darksun1/ (01gameinfo, 07fields,
16messenger, 34korbnor, 35war) and /darksun2/ (02party, 13vahq,
16minesup).
