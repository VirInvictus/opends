# Known Bugs

A catalog of the engine bugs we are committing to fix. Three sources:

1. **SSI's official 1.02 README** for *Wake of the Ravager*, preserved
   verbatim in section 1 below: that's twenty bugs SSI fixed between
   the 1.0 release and the 1.02 patch. We must not regress these.
2. **The 1.10 → present** residual bugs documented on Wikipedia, VOGONS,
   GOG forums, the DOSBox compatibility list, and the Steam community
   threads.
3. **Bugs we discover during reimplementation.** Add as we go.

## 1. SSI's official 1.02 fix list (Wake of the Ravager)

Reproduced from `.games/ds2/README.TXT` shipped in the GOG installer.
The README is dated 1994-12-14 and accompanies the 1.10 build. Each
item below was a 1.02-era fix; they are all expected to remain fixed
in OpenDS:

1. The game should no longer lock up when resting in the Pyramid.
2. The secret door to Mind Flayer Underdark should allow players to
   move freely between it.
3. The chest in the Sorrows will no longer change a character into a
   chest when the trap goes off.
4. Charmed or Fear will no longer stay on a character after combat.
5. The party will no longer disappear when moving through the caves
   of the Yaunti.
6. When you talk to Snaggle and give him the Potion of Heroism, you
   will now get experience for returning the potion only once.
7. Tapestry will no longer trap the character in one region while
   moving through the mosaic regions.
8. The volcano regions now show the correct overhead maps when
   entering the south and north wings.
9. The game should no longer crash when talking to the Tyrian guard
   in Tyr.
10. The game locking up when transferring regions should be fixed.
11. Music playing for 1–2 seconds (combat only) then stopping for
    same amount of time should be fixed.
12. The prayer spell works correctly.
13. The game speed can now be changed by sliding the top bar in the
    preference screen.
14. Saving Magnolia for the second time will no longer teleport the
    party off the screen.
15. The Umber Hulks will no longer act strange in combat, they
    should attack the party.
16. At the end of the game, the Lord Warrior will give his speech
    and combat will begin.
17. Game shouldn't randomly crash in combat.
18. When the party fixes the chandelier, the quest should continue.
19. Ranger characters will know accumulate over 1,440,000 experience.
20. When the pendant is brought to Dariya, the game will not freeze.

These are all GPL-script-driven (mostly quest flag bugs, some animation
script bugs, some combat AI bugs). All of them ship pre-fixed inside
the GOG 1.10 binary; darkfix preserves them as the **baseline** and
must not regress them.

## 2. Bugs that survived 1.10 (documented community reports)

### 2.1. Mine elevator freeze

**Symptom**: in WotR, the mines elevator freezes the level-load screen,
blocking quest progression. Reproducible across save reloads.

**Current workaround**: dismiss all party members except one, ride the
elevator solo, re-hire below.

**Surface**: likely GPL (region-transition script) or DSUN.EXE
(transition state machine). Investigation needed.

**Status**: headline target for `darkfix-ds2-v0.1.0`. See
[`../roadmap.md`](../roadmap.md) Phase 7.

### 2.2. Doorway / item graphics disappearance

**Symptom**: graphics for doorways or items occasionally vanish as the
camera scrolls.

**Origin**: described as an engine limitation; appears to be a
sprite/tile layering or culling defect.

**Surface**: DSUN.EXE (renderer).

**Status**: deferred: the binary fix is more invasive than other
candidates. May be addressed in DS2 v0.5 sweep.

### 2.3. Charged-weapon disappearance

**Symptom**: weapons with charge counters (Beast Club, Life Stealer,
others) vanish from inventory after their charges are spent rather
than reverting to mundane state.

**Surface**: GPL (item-use callback) or DSUN.EXE (inventory render).
Try GPL first.

**Status**: candidate for DS2 v0.5 sweep.

### 2.4. "Saves but exits"

**Symptom**: in some configurations, the game terminates after saving;
the saved game is still loadable on next launch.

**Surface**: DSUN.EXE (save path) or DOSBox interaction (less likely
since the bug predates DOSBox).

**Status**: needs reproduction first; some reports may be DOSBox-config
rather than engine.

### 2.5. Audio static / "untuned radio" noise

**Symptom**: on some 1994 CD pressings, the intro music (redbook
tracks 2-3) plays as loud static, "like an untuned radio"; some
early reports phrase it as static during music playback generally.

**Origin**: a CD-mastering defect on those pressings, not an
engine or driver bug. The static reproduces entirely outside the
game: the same tracks play as noise in Windows Media Player and
on a standalone CD player, and 1996 usenet posts report it on
real hardware pre-dating DOSBox (VOGONS threads t=9726 and
t=10893; an original unbundled copy showed it too, so more than
one pressing may be affected). An earlier revision of this entry
blamed an "AIL driver mismatch"; the community record
contradicts that, and the correction is made 2026-09-10.

**DOSBox verdict (Phase 8 verify-no-op, 2026-09-10)**: no-op
under the GOG install. GOG remaps the 40 redbook tracks to its
own OGG re-encodes (`MUSIC/TrackNN.ogg`), so the defective
masters never reach the player. The roadmap box's "OPL/MT-32
emulation paths" framing was a category error and is retired:
DS2's CD line has no MIDI music at all (see
`docs/install-variants.md`), so those synthesis paths are never
in the audio chain, and no DOSBox-specific static report for
DS2 exists in the community record. Residual: one in-game ear
test on the GOG install, which can ride the Phase 10
playthrough.

### 2.6. MEL DSP detect fail (error #26, trap #16)

**Symptom**: WotR refuses to start. "MEL fatal error #: 26 Trap
#: 16 DSP detect fail."

**Origin**: SoundBlaster IRQ misconfiguration, community-confirmed
(VOGONS t=10893 reply 11). The game's `SOUND.INI` defaults the
SB Pro II/III and SB16-class cards to IRQ 5, while stock DOSBox
and D-Fend-era front-ends defaulted to IRQ 7. AIL's SB probe
does a DSP reset handshake and then verifies the configured IRQ
by firing a test interrupt, so a mismatched IRQ fails detection
and MEL aborts startup with this fatal.

**DOSBox verdict (Phase 8 verify-no-op, 2026-09-10)**: no-op
under the shipped GOG configuration. The bundled
`dosbox_darksun2.conf` pins `sbtype=sb16, sbbase=220, irq=5,
dma=1, hdma=5` (verified against the GOG tree), matching the
game's expectation, and the emulated SB16 implements both the
DSP handshake and the IRQ verification, so detection succeeds.
Scoped honestly: the bug is not unreachable under DOSBox in
general, a hand-rolled conf with stock IRQ 7 still triggers it
(which is exactly how the VOGONS reports happened); it is
config-level, trivially fixable in either direction, and out of
scope for a darkfix. Residual: one in-game launch confirm under
the GOG conf, which can ride the Phase 10 playthrough.

## 3. DS1 issues

*Shattered Lands* shipped in a "somewhat unfinished state" (Designers &
Dragons, Appelcline 2011) but received only one patch (1.10). The
short list this section carried originally (region-transition screen
blanking, "enemies refuse to engage", rare save corruption) is below,
expanded into a compiled catalogue (Phase 9 list compile, 2026-09-10).
Every entry is a community report against GOG's 1.10 build unless
noted; sources are cited, and the "surface" column is the repo's
guess (GPL script/data vs `DSUN.EXE`), not a finding. PHASE 9
TRIAGE (2026-10-07): every entry below now carries a verdict
(FIXED / fix-candidate / engine-side / no static site) with
evidence in docs/ds1-sweep-triage-2026-10-07.md; the three
shipped repairs ride darkfix-ds1's `fix.ds1.script-repairs`
(0.1.2, default-on from 0.1.3; see the triage doc).

### 3.1. The final battle fails to trigger (the headline family)

Multiple independent reports over 14 years (2011 to 2025) converge on
this as the DS1 game-breaker: after the third genie wish the party is
teleported out of the buried city, the final battle never fires, and
the game is unwinnable. Known trigger conditions and variants:

1. **The messenger's scroll is not carried.** If the scroll from the
   dead body at White Sands (game start) is left on the ground or
   dropped, the final battle does not trigger; it must be in inventory
   before returning to Teaquetzl after the last alliance.
   Sources: GameFAQs board "Solution to final battle not triggering",
   Steam "Final battle not loading?", the kibbitz walkthrough 3.6/3.34.
   Surface guess: GPL; the final-battle transition script reads an
   inventory quest item.
2. **An ally NPC left the region too early.** Leaving before the
   ssurran quest-giver finishes walking off-screen skips her exit
   script and locks the Final Battle; her scripted defeat (an intended
   party wipe) must play out first. Documented with unusual precision
   in GOG forum threads and the kibbitz walkthrough. Surface guess:
   GPL NPC-exit script plus region-transition race; structurally the
   DS1 sibling of the DS2 mines-elevator transition bug.
3. **Statue Wyrmias in Gedron mishandled.** Striking him without
   killing him (or without letting him walk off the map) breaks the
   final battle; letting him flee properly adds him to it. Sources:
   GOG threads, kibbitz 3.31. Surface guess: GPL quest flag.
4. **Enemies never load in the final battle arena.** The party
   arrives to an empty area with one character stuck in the corner.
   Workaround, multiply verified: start any combat, then use the
   genie bottle's "help me defeat an army" wish mid-combat; the
   battle initializes after the next turn. Sources: Steam thread,
   kibbitz 3.32, GOG "trigger the final battle". Surface guess: GPL
   teleport/encounter script or the engine's combat-init state
   machine (a combat-active flag suppressing the scripted encounter).
5. **A stage cleared too quickly breaks the next stage.** Dragging
   out each fight works around it. Source: kibbitz 3.33. Surface
   guess: GPL sequencing or GPL-VM scheduling.
   ROOT CAUSE + FIXED 2026-10-07 (darkfix-ds1 0.1.2,
   `fix.ds1.script-repairs`, default-on from 0.1.3): the stage gate GPL-62@4323
   arms entry 4345, which exits without re-arming when the window
   has not elapsed, stranding the chain; the fix arms the driver
   239 directly. See the triage doc 3.1(5).
6. **"Army still gathering" with all alliances formed.** Recent
   report, same family; the thread also warns against wandering back
   and forth at the well quest after the sands shift. Source:
   r/DarkSun "Shattered Lands bug". Confidence low on detail, high on
   family.

### 3.2. Quest and NPC scripting

1. **Escort/follower NPCs break when the player leaves the region
   first**, the walkthrough authors' general rule for "breaking the
   scripting": the Fields of Draj serf escort resets (duplicate
   obelisk gem), the Battlefield rescued slave stops following across
   zones, and the "Dagger" event apparently never fires for some
   players. Sources: kibbitz quick notes and 3.10/3.24, the 2009
   GameFAQs FAQ. Surface guess: GPL NPC-walk scripts keyed to region
   state.
2. **Alhena never appears at the Elven Caravan campfire**; the
   sorcerers.net walkthrough author reports the event "has never
   materialized" across GOG playthroughs, corroborated by the 2009
   FAQ's "a great number of events which do not seem to trigger with
   any reliability". Surface guess: GPL event script with an
   unreachable condition.
3. **Semyon (Slave Pens) bugs out if freed before being given water.**
   Source: kibbitz 3.1. Surface: GPL dialog/flag order.
4. **Rebel Mindhome quest state regresses**: NPCs re-ask the spider
   quest after completion. Source: kibbitz 3.21. Surface: GPL quest
   flags.
5. **Linara/Jasmine spellbook event (Gedron) breaks** after visiting
   Linara first; the topic never becomes discussable again. Source:
   kibbitz 3.15/3.17. Surface: GPL dialog tree/flag order.
   ROOT CAUSE + FIXED 2026-10-07 (darkfix-ds1 0.1.2,
   `fix.ds1.script-repairs`, default-on from 0.1.3): GPL-68@0xaa routes
   GNUM55==2 to a one-line dead end (sub 4942); the fix repoints
   it to the general menu (209). See the triage doc 3.2(5).
6. **Elven slaver leader conversation jumps to the wrong branch**
   (the "allow yourself to be enslaved" path). Source: kibbitz 3.11.
   Surface: GPL dialog tree.
7. **The Undermountain prince body-blocks the exit; asking him to
   move may not work**, a soft-lock (save-before warning). Source:
   kibbitz 3.21. Surface: GPL NPC script or engine collision.
8. **Teaquetzl alliance rewards spawn into the Swiftbite chest** and
   can wipe items stored there. Source: kibbitz 3.7. Surface: GPL
   reward-placement script with a fixed container reference.
9. **Wyrm Temple healing chamber spawner misfires**: slave Magera
   spawns out of context talking about the chamber. Source: kibbitz
   3.27. Surface: GPL spawner.
10. **Hound Necklaces kill prisoners when talked to** (scripted
   damage applies without checking its source). Source: kibbitz 3.4.
    Surface: GPL dialog-triggered damage.
11. **The Keldar fight sometimes drags in Dagolar and ten slimes**
    (suspected positioning-after-combat cause). Source: kibbitz 3.4.
    Surface: GPL encounter trigger.
12. **Hermit/ranger dialog loop (Lava Rifts)**: approaching the
    ranger plays the hermit's dialog endlessly (escape by clicking
    west), and yields a duplicate Iron Necklace. Source: kibbitz
    3.29. Surface: GPL dialog loop plus wrong NPC association.
    ROOT CAUSE + FIXED 2026-10-07 (darkfix-ds1 0.1.2,
    `fix.ds1.script-repairs`, default-on from 0.1.3): the ranger-leave re-arm at
    GPL-100@0x684 arms the hermit's entry (86), occluding the
    ranger's own registration (100@445); the fix repoints it. The
    duplicate necklace is the hermit give's ground-drop fallback.
    See the triage doc 3.2(12).
13. **Charm re-entry**: a charmed enemy that triggered a battle
    script stays alive and can re-trigger the same script by talking
    again. Source: 2009 FAQ. Surface: GPL combat-script dispatch.
14. **Slaver-camp alarm glitch**: followers fighting near the camp
    raise the alarm, "just about everywhere". Source: 2009 FAQ.
    Surface: GPL.

### 3.3. Engine-level items

1. **An area item limit makes items disappear**: Gem Fields reports
   of six opened lava domes yielding only three gems; some domes look
   intact and ignore picks (workaround: inspect directly for the gem).
   Sources: 2009 FAQ, kibbitz 3.30. Surface guess: `DSUN.EXE`
   map-object list cap; structurally parallel to DS2's §2.2/§2.3
   disappearance bugs.
2. **Inventory/chest items vanish, or a blank "ghost" inventory slot
   with an odd price appears**; worst case "can make the game
   unwinnable" (community advice: box and abandon the ghost item,
   never equip or sell it). Source: 2009 FAQ. Surface:
   `DSUN.EXE` inventory/object code; possibly the same root as the
   item limit above.
3. **Saving mid-event deletes objects needed to progress** (the
   Sewers example makes key items uncollectable). Source: 2009 FAQ.
   This refines the old "rare save-corruption" one-liner: the
   reported mechanism is save timing during scripted activity, not
   region-edge tiles. Surface: the save writer serializing live
   object state; DS1 save-path anchors are already catalogued (3a).
4. **Stat-boost gear applies permanently while carried, unequipped**
   (the +3 CON ring excepted: Dagolar's Dagger), and resting via the
   genie can erase all gear buffs until re-equip. Sources: kibbitz
   2.10 tip 9 and Nazca Lines section, sorcerers.net War page.
   Surface guess: `DSUN.EXE` item-effect apply/remove asymmetry.
5. **Random crashes/lockups**, reduced but not eliminated by 1.10
   ("properly patched versions should not experience this as often").
   Source: 2009 FAQ. Surface: unknown/engine.

### 3.4. Minor rule and implementation deviations

Lava Rifts lesser fire elementals immune to +1 weapons though the
cluebook says +1 suffices; Psionic Blast removes real HP instead of
temporary HP; the Gladiator AC bonus applies without armor; entering
a firewall twice in one move takes the damage twice; the difficulty
setting only affects not-yet-spawned creatures; bodies vanish on map
reload (breaking wand-of-metal-detection use); Silt Sea North guards
inconsistently pull one-by-one vs going hostile as a group. Sources:
kibbitz 2.5-2.8/3.29, sorcerers.net (Hot Springs, War, Silt Sea
North). Surface: mixed engine/data; low severity each.

### 3.5. Cross-references to the static work

- The original "enemies refuse to engage" line now has a concrete
  static candidate, correlated 2026-09-10: the dead-trigger sweep
  (gpl-disasm 0.8.0) found five looktriggers plus one ATTACKTRIGGER
  pointed at GPL-200 entry 0x909, which holds only `gpl exit gpl`: a
  stubbed actor handler. The correlation dig places all six in the
  Darkhold endgame (regions 30/31, `RGN1E`/`RGN1F`): the queen's
  chamber creatures (-2263, -1209), the portcullis guard (-255), and
  the wyvern-scene creature (-2248), all main-quest, normal-
  playthrough content. That is the leading Phase 6 pick's evidence
  chain (roadmap, Phase 6 bug-pick box), and it is plausibly the
  same class as final-battle variant 4 above.
  FIXED 2026-09-11 in darkfix-ds1 0.1.0 (`fix.ds1.deadtriggers`)
  for the four static rows: each occluding registration is
  repointed to the object's own working handler (guard combat ->
  `GPL-200@0x33b`, chamber looks -> `GPL-203@0x389`, wyvern look
  -> `GPL-41` entry 1), a no-op-or-restoration under either
  registration semantics. The two `GNAME[39]` rows stay as
  shipped (runtime-variable object, inert stub); see
  `ds1-patch/fixes/001-deadtriggers.md`. In-game scene
  confirmation rides the played-save sessions.
- (DS2) Dead triggers: the corrected sweep (gpl-disasm scripts fix,
  2026-09-15: the tool's table said `pickupitemtrigger` while the
  catalogue's real mnemonic is `gpl pickup itemtrigger`, and the
  use-with entry offset was read from the wrong parameter, so
  pickup and use-with rows went unswept in BOTH games) counts DS2
  at 1,915 registrations, 1,670 alive, 206 intentional
  null-handlers, 39 dead, all pointing at the shared NPC-chatter
  library's no-op `GPL-24` entry 0x1. The DS1 recount under the
  corrected tool: 1,539 registrations (was 1,449), dead count
  unchanged at the six rows `fix.ds1.deadtriggers` repaired.
  FIXED 2026-09-15 for 27 of the 39 in darkfix-ds2 0.1.0
  (`fix.ds2.deadtriggers`): each static row is repointed to the
  object's own working handler (21 same-chunk, 6 MAS-attested),
  the same no-op-or-restoration design as the DS1 fix. Ten of the
  12 rows left at 0.1.0 followed in darkfix-ds2 0.1.1
  (2026-10-07) after the correlation dig
  (docs/port-digs-2026-10-07.md 2): the tapestry look -1922, two
  more shared-prop use rows, and the seven GPL-98 use-with rows,
  whose entry immediates were already correct and only the chunk
  id wrong (alive twins in GPL-114 attest every pair). 2 rows
  stay, closed with a corpus-wide proof: the two pickup rows on
  -900 have no pickup handler anywhere in the shipped data; see
  `ds2-patch/fixes/001-deadtriggers.md`.
  In-game scene confirmation rides the played-save sessions.
- The region-transition screen-blanking line has no independent
  community trail; it predates the compiled list and stays untriaged
  until a report or a repro catches it.

Primary sources for the compiled list: the kibbitz GameFAQs
walkthrough (faqs/80958), the 2009 GameFAQs FAQ (faqs/58639), GOG
forum threads on the final battle, the Steam "Final battle not
loading?" thread, and the sorcerers.net DS1 walkthrough. Dead ends
recorded for the next pass: dsun.powelltown.com has no Wayback
snapshots; Reddit bodies are unfetchable (search snippets only);
athas.org timed out; no public DS1 1.1 fix list exists (GOG's DS1
tree ships no patch notes).

## 3a. The bug-site census (Phase 5.6.3)

The checklist that makes the distance from "bug list" to
"patchable bug" visible. Per bug: is the faulting code **located**
(any addressable anchor), is it **named** (a catalogue row or DSO
transfer), and do we have a **root cause**? Evidence chains live in
`tools/ovr-map/syms/<game>.toml` and the dispatch tables
(`dispatch-table-ds1.md` / `dispatch-table-ds2.md`). Updated as the
5.6.1 naming campaign advances; a bug is Phase-6/7-ready when all
three columns are yes plus a written site report.

| Bug (§) | Game | Site located | Site named | Root cause | Evidence so far |
|---|---|---|---|---|---|
| Mine elevator freeze (2.1) | DS2 | **yes** | **yes** | **candidate** | COMPLETE CHAIN: trigger = `usetrigger 3753, 287, NAME(-5807)` in MAS-57 (object 5807 = elevator shaft, sprite BMP 951 visually confirmed); handler = GPL-287 toggles GF[647] + sounds; machine = gpl_disk_change_region (ovr18+0x1132, fully read); freeze = scheduler deadlock candidate OR dangling switch state (GF[647] set but never read in the 1.10 GPL corpus). Regions: 56=Mines1, 57=Mines2, 58=Mines3. |
| Doorway/item graphics disappearance (2.2) | DS2 | no | no | no | Renderer surface only; nothing anchored yet. |
| Charged-weapon disappearance (2.3) | DS2 | **partial** | no | no | The item path's OBJEX lookup is catalogued (`ovr35+0x2327`, pushes "Failed, Not in Objex.gff"); the charge-decrement code is not. |
| "Saves but exits" (2.4) | DS2 | **partial** | **partial** | no | Both save-path anchors catalogued and verified: `LoadGameFromDisk` (DS2 ovr18+0xa6c, DS1 ovr21+0xdde, self-naming strings) and the slot path `SaveGameToDisk` (DS2 ovr11+0x8e5, DS1 ovr13+0x7cc). Caveat per the syms row: the function at DS2 ovr18+0xa6c WRITES SAVE-tagged records (boundary scan + gap read), so that row is the save writer, not the loader, despite the DSO name. The exit-after-save sequence is not traced. |
| Audio static (2.5) | DS2 | n/a | n/a | n/a | Out of scope (Phase 8 verdict 2026-09-10: redbook mastering defect on some pressings' tracks 2-3; GOG's OGG re-encodes bypass it; see 2.5). |
| MEL DSP detect fail (2.6) | DS2 | n/a | n/a | n/a | Out of scope (Phase 8 verdict 2026-09-10: IRQ-5-vs-7 config mismatch; the GOG conf pins IRQ 5, verified on disk; see 2.6). The MEL error path is incidentally anchored (`mel_dj_audio_init`, DS2 ovr11+0x26). |
| DS1 issues (§3) | DS1 | partial | partial | no | The compiled §3 catalogue (2026-09-10) supplies per-bug candidates with sources; the gpldisk.c module is anchored DS1-side (`ictrl_check`, `load_game_from_disk`, `gpl_disk_change_region`, `load_teleport`, `save_game_to_disk`), and the dead-trigger finding (GPL-200@0x909 stubbed actor handler) is the first concrete root-cause candidate, for the enemies-refuse-to-engage class. |

Module-level context that shortens every dig: the GPL VM dispatch
tables are resolved for both engines (all 15 unknown bytes proven
unimplemented), and the handler stubs call through far-pointer
tables: so a bug whose cause is a wrong opcode behavior can be
traced handler-to-implementation in two hops.

### 3.6. Scripting findings from the yuan-ti cross-read (2026-11-13)

Calvin Rodo's engine ([upstream-projects.md](upstream-projects.md)
§4) repairs 29 shipped-script bugs in `GplRepairs.cs`. Seven are our
published darkfix-ds1 fixes ported byte-for-byte; five implement
three of our own unshipped triage candidates (triage rows 3.2(1a),
(1c), and the bonus half of (4)); seventeen are Calvin's own
discoveries, absent from this catalog until now. All 23 distinct
fingerprints verified clean against `.games/ds1/GPLDATA.GFF` (GOG
1.10) on 2026-11-13. **None of these are adopted fixes yet**: each
needs the semantic review + runtime QA gate in
[detour-repairs.md](detour-repairs.md) before any becomes a
darkfix-ds1 fix. Recorded here as catalog rows with credit; sources
below are yuan-ti's `engine/src/DarkSun.Game/Scripting/GplRepairs.cs`.

1. **Halfling greeting/insult race test (Slave Pens)**: GPL 31's
   halfling reads the speaker's race from the combat record, which
   carries none (byte 0), so a halfling in the party is never
   greeted as one and the insult names no race. Calvin's fix reads
   the character sheet's race field (`.71.20`) instead. Sites: GPL 31
   @0x3B (greeting) and @0x254 (insult). NEW DISCOVERY (no kibbitz
   or FAQ source covers it).
2. **Ranger tracking chain (region 8 bodies)**: three stacked faults
   in GPL 210, per Calvin's analysis: the ranger test reads usable
   item classes from the combat record (`.17`, not the sheet's
   `.71.17`); the level bonus tests class codes as bit masks (a
   ranger's code is 13-16); and the roll is inverted (success
   requires the score under the roll: `lnum[4] < RAND(20)`, which
   high-Wisdom parties can never satisfy). Five edits, four detours
   and one same-length: GPL 210 @0x5FD, @0x60C, @0x622, @0x638,
   @0x6CC. NEW DISCOVERY.
3. **Sewer grate (Slave Pens) hack path dead**: in GPL 137 the
   weapon-in-hand search stops at once (tests `lflag[3] == 1` where
   it was just set to 0), so "hack the lock off" is never offered; a
   hack that succeeds never opens the grate; and attacking it tests
   `.43 < 220` against an item with no hit points (always breaks the
   lock). Calvin's fixes: @0xA65 (offer gate, same-length), @0xA14
   (open on success, detour: the pick path's own tail, printing
   "The grate opens." via lstring[0] and setting gflag[505] as the
   pick path does at 0x998), @0xB5C (Strength roll like ripping it
   open, detour), @0x9E0 (his/her line, detour with relocated
   labels). NEW DISCOVERY.
4. **Legcrusher-gone dialog guards (Slave Pens)**: the party can
   kill Legcrusher (-326), after which Kurzak keeps calling for him,
   greets the party as if he were about, and Dinos still warns of
   him. Six detour repairs (GPL 136 @0x130, GPL 139 @0x218, GPL 141
   @0x6B4/0x70B/0x766/0xF29) gate each line on
   `RANGE(GNAME[37], NAME(-326)) < 999` and substitute replacement
   dialog when he is gone (AUTHORED 2026-11-17 as
   `fix.ds1.legcrusher-gone`, disabled pending runtime QA, issue
   #20; correction on the record: yuan-ti's source reads
   `gname[5]`, which never appears in the shipped corpus -- the
   engine's own alive-checks use GNAME[37], the active-member
   register with 367 get-range uses, so our assembly reads that).
   NOTE: these invent new game dialog text; adopting them crosses
   our no-invented-behavior line deliberately (decision recorded
   2026-11-13). NEW DISCOVERY.
5. **Serf follow range (Fields of Draj)**: our triage 3.2(1a)
   concluded no same-length edit exists for the persistent-guard
   approach; Calvin's fix is a different design, a one-byte
   follow-distance widening (GPL 60 @0xCD8: immediate 14 -> 127
   cells, "however far behind"). Balance-class, off by default per
   §5 policy. Our persistent-flag candidate re-opens under detour
   support (see detour-repairs.md).
6. **Messenger trigger re-arms (region 9)**: our triage 3.2(1c)
   named the three GPL-58 sites (0x1A/0x99/0xCC); Calvin implemented
   the register-on-flip fix as three detours with identical
   structure: register MAS 9's sight trigger on the messenger
   (-1297) while `gflag[339] == 0`, gated on `gflag[245]` having
   flipped. Site ours, implementation his.
7. **Mindhome XP award loop (Rebel Mindhome)**: our triage 3.2(4)
   bonus finding (the +5000 XP re-awards on every re-talk once the
   spiders are dead); Calvin's fix gates the award on
   `gflag[695] == 0` via a detour at GPL 204 @0x5C9. The re-ask half
   of that bug (the GPL-204 router at 0xb2/0xd2 never consulting
   GF695) is still unimplemented by either project.
8. **The Trustee in the slave pens can stop for good**
   (VERIFIED + AUTHORED 2026-11-17 as `fix.ds1.trustee-rounds`,
   disabled pending runtime QA, issue #23): the trace confirms the
   relayed mechanism -- GPL 137's knock-fight path (@0x1740)
   subtracts 2 from the rounds state `GNUM[20]` unguarded, driving
   it negative from states 0 or 1; a negative state matches no
   corner arm in GPL 8's rounds switch, so on a fresh load (locals
   zeroed) the Trustee walks toward tile (0,0), never arrives,
   never advances, and the busy flag (cleared only by GPL 8's
   state-0 arm @0xedc) never lifts. The fix guards the writer:
   below 2, the knock clamps the state to 0. Trace record:
   [`../ds1-patch/fixes/010-trustee-rounds.md`](../ds1-patch/fixes/010-trustee-rounds.md).
   Relayed from the Obsidian Edition's findings via yuan-ti (see
   [community-crossread-2026-11-13.md](community-crossread-2026-11-13.md)
   §1).


### 3.7. Engine-side rows verified from the Obsidian relay (2026-11-17)

The Obsidian Edition's 15-row relay (issue #24; see
[`community-crossread-2026-11-13.md`](community-crossread-2026-11-13.md)
§1 for the original claims) verified by our own disassembly passes
over the DS1 image. Engine-side bugs are EXE patches, out of
darkfix's data scope; these rows are the verified documentation, not
fixes. Segment mapping for the overlay nodes: Obsidian's runtime
segment values resolve per-module (80F5 = the spell-effects module,
file base 0x78BA0, pinned by the image's unique `cmp ax,0x4B`
landing at exactly +0x1A2D; 6698/612E/8640 calibrated the same way,
each against multiple fingerprints from Calvin's reference).

1. **Mirror Image eats the caster's side's spells — CONFIRMED.**
   The image-block test (ovr32, file 0x7A539; the d100 gate at
   0x7A5CD: RND(1,100), `cmp ax,0x4b; jg` survives on > 75) has no
   caster-allegiance or self-cast exception: any spell landing on a
   mirrored character rolls and is lost on 1-75, consuming one
   image (countdown decrement + shatter FX). Blows never roll:
   melee damage bypasses the cast engine entirely, and innate
   attacks (spell id -1) exit before the mirror test.
2. **Protective effects burn on every landing — CONFIRMED, with
   corrected semantics.** The landing routine decrements the
   Armor-effect countdown (effect 2) for ANY spell landing on a
   protected character -- a friend's Bless included, even when the
   images then block it -- and the damage routine decrements again
   for all damage (file 0x79A3E; the relay's file offset 0x7743E
   was wrong). So a damaging spell costs 2 countdown units, a blow
   1, a non-damaging friendly spell 1. The relay's "charges" are
   active-effect timer countdowns, not item charges.
3. **Share Strength's end removes nothing — CORRECTED.** The relay
   said the ending loop removes the psionicist's records, skips
   after each removal, and counts to 192. The trace (psionics
   module, file 0x5CEBD, loop at exactly 0x5CEEC-0x5CF34) confirms
   two of three: the loop keys records to the caster argument (not
   per-record ownership) and its bound is the constant 192 rather
   than the live count at DS:1E24. But it never removes and never
   skips: the per-match call enters a pure getter 3 bytes past its
   prologue and the result is discarded; the only real state change
   is the PSST maintenance-bit clear. The genuine removal machinery
   lives elsewhere (the condition functions in the effects module).
4. **Thri-kreen claws are crushing — CONFIRMED.** The natural-attack
   branch (combat module, file 0x581DF: `c7 46 ec 08 00`) forces
   every weaponless blow's element word to 8 (bludgeoning) with no
   race or creature branch; crushing-immune creatures (mastyrials)
   take zero from all claws. Thri-kreen are player race 8, so their
   claws also never gain the magic bit the (level-2)/2 formula adds
   for non-player races.
5. **A click on the Effects screen ends a spell — CONFIRMED.** Both
   relayed bytes (ovr36, files 0x7F226 `7C 51` and 0x7F236
   `7D 41`) are the spell-vs-psionics band branch in the
   click-removal path: spells (id < 0x8A) take the jump straight to
   record removal exactly like powers; only the psionics band gets
   the extra mirror-byte clear. What a stray click loses is a
   running spell's active effect (Armor, Bless, ...), not a
   memorized uncast slot.
6. **Scare's elf/half-elf exception never fires — CONFIRMED.** The
   situational save modifier (effects module, file 0x79FA4-0x7A01B):
   spell id 21 (Scare) gives +100 to the save roll at target level
   >= 6 and -100 below 6, and its only no-modifier escape requires
   the target's race byte to be both 3 (elf) and 4 (half-elf) --
   one byte, two different compares, unreachable. Every elf rolls
   the same -100 as everyone else below level 6.
7. **Preserver's Dispel Magic sets the no-spells bit — CONFIRMED
   (data).** Spell record 26 (SPIN 27, preserver Dispel) carries
   effect byte +0x19 = 0x32 = 50, the spell-blocking status the
   Insect Plague handler applies; the priest Dispel (SPIN 99,
   record 98) carries 0x00 there. Both are target-point records
   with the area-walk aoe, so the bit lands on every creature in
   the radius, caster's party included. Sub-part not proven: the
   relay's "Dispel Magic cannot remove it" (the removal matcher was
   not traced).
8. **Cause Serious/Critical Wounds roll d9s — CONFIRMED (data).**
   SPIN 114 damage word 0xa0091100 = 2d9 and SPIN 129 0xa0091900 =
   3d9, while the matching Cure handlers pay 2d8+1 / 3d8+1 (and the
   Cure Critical game text promises 3d8+3, which the handler does
   not pay either -- a small text-vs-code discrepancy of its own).
9. **The elf Cilla draws the half-elf woman's figure — CONFIRMED
   (data).** Both her creature row (307) and pregen template (32003)
   carry base-figure index 7 = the half-elf female sprite while her
   character record says race 3 (elf). Corpus controls agree (elf
   female Saria carries 5, thri-kreen K'ratchek 13, human male
   Cermak 0).
10. **The acid corrosion checks — CONFIRMED, with the sites
    swapped.** The relay had the two rules at each other's
    addresses. The weapon check (file 0x7AA5A) rolls d20 against
    8 minus the item-template enchantment plus (+0x14) and destroys
    the weapon on failure; the armor check (file 0x7ABC4) tests the
    template's +0x0F spell byte, not the plus: a piece with no
    spell byte is destroyed outright with no roll, and one with a
    spell byte survives on d20 >= 10 minus that byte. (A third
    branch corrodes the lowest-+0x10 carried item on d20 <
    15 - its plus.)
11. **Hold Undead holds only the undead — REFUTED.** The relayed
    claim is contradicted by the code: the whom-it-takes filter
    (a 14-spell table in the effects module) routes Hold Undead and
    Turn Undead to a predicate testing character race == 9
    (undead), and both traced application routes enforce it (the
    cast engine skips filtered targets; area-target walks remove
    them from the list). yuan-ti's own reference agrees with the
    code, not the relay.
12. **Remaining unverified (searched, not traced)**: the roster
    DELETE-when-scrolled and new-character thief-skills-0 rows.
    Neither handler is documented in any corpus; the dig targets
    are now named (the "DELETE CHARS"/"DROP THIS CHARACTER?" string
    cluster at DSUN.EXE 0x4A4C9+ and 0x48CF1+; the sheet renderer
    for thief percentages -- which has no display string in the
    image at all). The Sling +1 blank-icon row resolved as data:
    no Sling +1 exists (the name pool has Sling, Staff Sling, and
    unused Sling +2 / magic sling names), every sling's picture
    reference resolves, and the closest real defect is the
    OJFF-less chest sling 2644, whose inventory icon computes to 0.

## 4. SSI patch lineage

| Game | Patch | Distribution                                  |
|------|-------|-----------------------------------------------|
| DS1  | 1.10  | Bundled in GOG release (the only DS1 patch)   |
| DS2  | 1.01  | Silent revision; referenced in SSI's 1.1 README ("ver 1.0 or 1.01"), no archived artifact known |
| DS2  | 1.10  | Three official builds: `WAKEC110` (CD; IA `WAKECD11_ZIP`; this is what GOG applied), `WAKE3110` (3.5" disk; IA `WAKEDK11_ZIP`), and a jewel-case build (Patches Scrolls `wake11jc.zip`) |

An earlier revision of this table listed a DS2 "1.02"; no such
patch surfaced in the 2026-06-10 sweep of Patches Scrolls, the
Internet Archive, and SSI's mirrored update pages, and SSI's own
1.1 README names only 1.0 and 1.01. See
[`install-variants.md`](install-variants.md) for the full
lineage evidence, including proof that GOG's DS2 tree is exactly
retail CD 1.0 plus `WAKEC110`, and that **no public path to a
floppy 1.10 install currently exists** (every archived disk
patch rejects the one public floppy 1.0 dump).

GOG ships the 1.10 binary inside DOSBox, with the 1.1 patch
README preserved as `README.TXT`. There is **no public
unofficial community patch** for either game.

## 5. Patch policy in darkfix

Each fix:

1. Ships with a stable identifier (e.g. `fix.ds2.mines-elevator`).
2. Is **on by default** if it is a clear bug.
3. Is toggleable in the patch's `manifest.toml` for purists.
4. Is documented here with the original report and the fix rationale.

Bug fixes that change balance (e.g., XP exploits, item duplication)
are **off by default**, on by toggle. See [`../spec.md`](../spec.md) §5.
Amended 2026-10-07: several enabled fixes may share one target file
when their edit ranges are disjoint; the applier composes them into
one write and refuses overlapping ranges at check time. (The old
one-enabled-fix-per-file rule briefly forced darkfix-ds1 0.1.2's
script repairs to ship disabled.)

## 6. Sources

- `.games/ds2/README.TXT`: SSI's verbatim 1.02 patchnotes.
- Wikipedia: https://en.wikipedia.org/wiki/Dark_Sun:_Wake_of_the_Ravager
- VOGONS thread: https://www.vogons.org/viewtopic.php?t=10893
- DOSBox compat list: https://www.dosbox.com/comp_list.php?showID=148&letter=D
- Internet Archive: https://archive.org/details/WAKEDK11_ZIP
- Internet Archive: https://archive.org/details/WAKECD11_ZIP
- Patches Scrolls: https://www.patches-scrolls.de/patch/1112/7/22585
