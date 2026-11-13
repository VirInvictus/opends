# Community knowledge cross-read (2026-11-13)

The knowledge-mining pass over yuan-ti (Calvin Rodo) and its
Obsidian Edition relay, following the repair-lane gate review
([`gate-review-yuan-ti-2026-11-13.md`](gate-review-yuan-ti-2026-11-13.md)).
Everything here is traced upstream work, credited to its source;
facts land in our docs with citation, never as code. The GPLX
field map got its own doc ([`gplx-field-map.md`](gplx-field-map.md)).

## 1. Engine-bug catalog from the Obsidian Edition (via yuan-ti)

The Obsidian Edition project (a mod for the original game)
documented 15 original-engine bugs, each found in the DSUN.EXE
code and seen in fights, relayed in yuan-ti's
`.github/instructions/ref_notes_from_obsidian.md` §5 with
addresses. Credit: Obsidian Edition's findings, Calvin Rodo's
writeup. These are engine-side rows our catalog did not have
(known-bugs §3.3/3.4 territory); the Trustee row is a GPL-script
bug, squarely our lane.

| Bug | Site (per Obsidian) | What the game does |
|---|---|---|
| Mirror Image eats the caster's side's spells | `80F5:1999`, the d100 `cmp ax,4Bh` at `80F5:1A2D` | The images' 75% spell-block has no friendly exception; armor cast on oneself under Mirror Image is lost 3 times in 4 and takes an image with it. Blows skip the roll, so images stop none. |
| Armor spends two charges per hit | the `je` at `80F5:19B7`; damage routine `80F5:0E9E` | The landing routine spends a charge for any spell or blow (a friend's Bless included); the damage routine spends another for the damage. |
| Share Strength's end removes the wrong effects | the loop at `6698:063C`-`0684` | It removes each effect record owned by the psionicist instead of the record's own owner, skips the next record after each removal, and counts to 192 rather than the live count at `DS:1E24`. |
| Preserver's Dispel Magic (record 27) sets No Spells on everyone | the record's effect byte (+0x19) = 50 | Including the caster's party, and Dispel Magic cannot remove it; the cleric's Dispel (99) has no effect byte. |
| Hold Undead holds the living | (their §1.3) | |
| Cause Serious / Critical Wounds dice | records 114, 129 | 2d9 and 3d9 where the Cure spells heal 2d8+1 / 3d8+3. |
| Thri-kreen claws are crushing | `612E:151F` in the attack routine `612E:1359` | Every natural attack's damage kind is set to crushing (8), so crushing-immune creatures (mastyrials) are safe from claws. |
| Scare's elf/half-elf exception never fires | the Scare save code | It requires a creature that is both an elf AND a half-elf, so level 6+ always saves and below never can. |
| A click on the Effects screen ends a spell | `8640:0C06` and `8640:0C16` | A stray click loses a spell; powers are meant to end this way, spells probably are not. |
| The roster's DELETE deletes the wrong character when scrolled | Create Characters' roster | |
| A new character's thief skills show 0 | the Okay test | |
| The Trustee in the slave pens can stop for good | his GPL rounds | His two pauses take their corner from numbers other pen scripts change, so he can set off for a spot that does not exist and stay busy ("I'd love to talk more...") for good. |
| The elf Cilla has the half-elf woman's figure | data | |
| Sling +1 has a blank icon | data | Its picture is missing from the game's data. |

Also relayed, the **acid check**: a weapon corrodes on a d20
under 8 minus its plus (`80F5:2024`); armour is tested on its
+0x0F spell byte, not its plus (`80F5:1EBA`), so a piece with no
spell is destroyed outright (Tanelyv's Armor +2 goes as surely as
plain leather). yuan-ti's `CorrodeArmor` reads the same byte.

Dispositions here: recorded as relayed facts with addresses; none
are verified by us yet, and none become known-bugs canon rows
without the same treatment our own rows get (our own
decompilation pass over the named sites). The Trustee bug joins
the known-bugs queue as a GPL-script candidate (our lane, a real
site to trace).

## 2. Combat and rules facts (yuan-ti exe-reference §8)

Their traced combat chapters (2,548-line reference, Ghidra 12.1.4
via REA) cross-check against our known-bugs §3.4 verdicts:

- **Difficulty scaling, now traced**: creatures outside the party
  get the word at character +8 (hit points) multiplied by
  `((difficulty - 1) x 50 + 100) / 100` at load (creature size
  and records: `7372:0388`, `1A0A:2AB4`). Confirms our §3.4
  verdict "spawn-time scaling; live objects never re-read it",
  with the site named.
- **Fire elemental immunity**: Obsidian fixes the fire
  elementals' behavior (their list); yuan-ti's `CombatFixes`
  covers it too. Our §3.4 row (resistance rows in the EXE-side
  enum, data-side key unclean) gains two independent
  confirmations that the behavior is real and engine-side.
- **Their open gaps match ours**: resistances/immunities beyond
  the fire elemental are not traced on their side either;
  `OP_28` is unnamed on both sides (ours: `gpl trace var`,
  custom; theirs: `OP_28`, param string "EES").
- **Name cross-check** (`GplOpcodes.cs` vs our
  [`gpl-opcodes.md`](gpl-opcodes.md)): 129 entries both sides,
  same libgff ancestry; their param strings ("EE" for 0x20,
  "EES" for 0x28) agree with our parameter counts. Their
  BITSNOOP name is libgff-lineage, not semantic evidence; the
  bitwise-AND reading from the gate review stands, and the
  syms-curation note stays open.
- **REQUEST codes**: their `GplRequests.cs` names 117 REQUEST
  codes with summaries (REST_RAISE, SET_DOOR, SKILL_CHECK,
  TOGGLE_STATE, CINEMATIC, TRAP, RANDOM_MONSTER, TRANSFORM,
  BLOCK_CELL, BLOCK_SIGHT, ...) traced to their exe-reference §4.
  We have no REQUEST-name catalog; theirs is the decoration
  source for `gpl-disasm` symbol work, credited when used.
- **Starting gear** (`6ECD:1D48`): DONE on the creation screen
  gives one class's gear from a 29-entry table at `38CE:0000`,
  picked by first-set class bit in order fighter, gladiator,
  ranger, cleric, thief, psionicist, preserver, else druid; a
  thri-kreen (character +0x18 = 8) gets entry 28 alone. Objects
  1010 chatkcha through 1185 club, slots named. Format facts for
  our item docs when the item lane re-opens.

## 3. Region connectivity

yuan-ti's static region-connection tracer
(`src/region_connections.py`, served by their viewer) walks each
region's MAS startup through calls and registered triggers to
collect party-teleport destinations: DS1's full connectivity
graph with trigger coordinates, per-edge exit sides, and a
non-geographic exception list (Temple Ruins-Teaquetzl,
Teaquetzl-Korbnor, Korbnor-White Sands dashed; region 255 the
unconnected test map). We have no connectivity doc; theirs is the
citable source (MIT) if the world-data lane wants one, and their
README documents the layout choices. Our give-back brief already
offers the region-change machine; this is the complementary
fact set.

## 4. Al-Qadim: The Genie's Curse (first coverage we have)

yuan-ti's toolkit reads Al-Qadim partially; their AGENTS.md and
exe-reference note the format split, all new to our docs:

- **No GFF at all**: world data in `WORLDS/*.LIB`, images in
  `ENGINE/PIC.LIB` and `ENGINE/SYSFILE.LIB` (binary offset-table
  containers, not GFF-compatible; no public parser yet).
- **Standalone scripts**: `GPLS/GPLxx.COD` files, GPL bytecode
  outside a container (their gpl_parser reads them; the DS1/DS2
  GPLX field map does not apply).
- Their support is flagged work-in-progress (GFF-based routes
  404). For OpenDS this is a facts-only pointer: if the toolkit
  lane ever extends to Al-Qadim, yuan-ti's notes are the starting
  reference and the LIB format is the open dig.

## 5. Method mining (harness patterns)

Three yuan-ti harness designs worth borrowing, recorded in
[`re-tooling.md`](re-tooling.md) §"Patterns worth borrowing":

- **`DarkSun.ScriptRun`**: runs the new-game script, every region
  script and every trigger they register, headless. The natural
  model for a `gpl-disasm`/`gpl-asm`-driven "run every chunk
  through the interpreter's shape" audit.
- **`DarkSun.MoveCompare`**: A* against a port of DSUN.EXE's
  pathfinder per region, walking speeds against the walk scripts.
  Differential testing against the original, per system.
- **`engine-compare`**: the C# decode vs the Python decode must
  produce identical dumps or CI fails. Our two-implementation
  points (gpl-disasm vs their parser) used the same idea manually
  in the gate review; the CI-enforced version is the upgrade.
- **The dice-log oracle** (Obsidian Edition, relayed): a log of
  every call the original makes to its Borland RNG, each roll
  labeled by purpose and call site. "Golden fights": play a fight
  in the original with the log on, replay from the same seed, and
  compare the order and purpose of rolls. A rule-run-in-wrong-
  order detector that sees through identical totals. The natural
  instrument for our gate step 4 runtime QA and for any future
  rules work; Obsidian's Loader prints it (`python -m dsloader
  dicelog`).

## 6. What stays unmined

- DarkSunTools beyond the FONT facts (font glyph PNG pipeline,
  chunk-parser edge cases): facts-only until a license lands;
  the standing exchange offer covers it.
- yuan-ti's engine-side data files (map_terrain.json, lights,
  particle looks): modern reimplementation choices, not RE facts
  about the original; nothing to mine for OpenDS.
- Their Git history: our clone is depth-1; if a question ever
  needs their development history (why a decode changed), unshallow
  then.
