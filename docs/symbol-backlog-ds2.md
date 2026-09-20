# DS2 symbol coverage backlog for gpl-disasm

Built 2026-09-20 from `.dso-online/tools/symbols.txt` (3,530
functions + 2,247 labels; Watcom debug names from the DSO v1.0
`MDARK.EXE`) against the gpl-disasm symbol catalogues.

## Coverage numbers

- `syms/functions.toml` holds exactly 2 curated rows
  (`iniya_first_meeting`, `iniya_dialog_menu`), both hand-coined
  DS1 content names with 0 overlap against symbols.txt. That is
  correct, not a gap: functions.toml curates game-data chunk entry
  points (file/chunk_id/offset), while symbols.txt names engine
  functions in MDARK.EXE. The DSO-derived curation actually lives
  in `tools/ovr-map/syms/{ds1,ds2}.toml` (verified
  `dso_source = "DSO::LoadGameFromDisk"` / `"DSO::SaveGameToDisk"`
  rows) and `docs/dso-symbols.md`; `syms/opcodes.toml` and
  `syms/variables.toml` ship empty by curation policy.
- Cluster census of the 3,530: 1,302 plain-lowercase helpers, 328
  `_`-prefixed Watcom runtime/audio, 215 ALL-CAPS DOS shims, 189
  `Gui*`, 115 `Decode*` (GPL opcode handlers), 97 `Get*`, 72
  `Game*`, 66 `Mel*`, 34 `Spit*`, 26 `jv_*`, 40 mangled `W?$$`
  (low value), plus the combat/rules families (`Cnd*` 16, `Spell*`
  9, `Psionic*` 14, `Combat*` 6).

## The Decode* batch: proposals exist, the curation rule gates them

`tools/gpl-disasm/scripts/import-dso-symbols.py --opcodes-proposed`
emits ~100 ready rows; the dispatch-order study in
`docs/dso-symbols.md` did the identity homework (111/115 Decode*
names match libgff mnemonics with the systematic
`*check` -> `*trigger` rename; `DecodeJump`/`DecodeWend` and
`DecodeNumtoname`/`DecodeNametonum` are aliases proven by shared
handler addresses; `DecodeIfis` hints 0x27 semantics).

**But do not bulk-land them.** `syms/opcodes.toml`'s curation rule
(do not relax without surfacing it) says the DSO symbol table
"does not enumerate opcode-byte->handler-name mappings... useful
for correlating engine entry points, not opcode renames", and that
cosmetic aliases do not meet the override bar. The proposals are
aliases by construction, so a batch import would relax a written
contract for a naming pass - flagged here rather than done
(2026-09-20). Paths that WOULD satisfy rule 1 for specific rows:
cross-checking individual handler semantics against bytecode
behavior (the dead-trigger sweep outputs are exactly this shape
for the `Gpl*Check` triggers), or finding cases where libgff's
mnemonic is provably wrong rather than differently-styled.

## Tier A: highest per-name value (16 `Gpl*` names)

Already mapped to opcode families in `docs/dso-symbols.md`
("Highest-value GPL-related symbols"): `GplAttackCheck`=0x65,
`GplLookCheck`=0x66, `GplTileCheck`=0x68, `GplDoorCheck`=0x69/0x6B,
`GplPickupCheck`=0x6C, `GplUseCheck`=0x6D, `GplTalkCheck`=0x6E,
`GplUseWithCheck`=0x70, `GplDropItem`=0x2F, `GplGetInput`=0x42.
Evidence to satisfy the curation rule is half-assembled:
`ds2-patch/fixes/001-deadtriggers.md` is live bytecode proof of
trigger-registration semantics (39 dead registrations over
talk/look/use/attack/pickup rows). Region/save family:
`GplChangeRegion`, `GplDiskChangeRegion`, `ExecuteGpl`,
`GplShellInit`, `GplPlaceObject`, `GplUpdatePsionics` (psionic
strings anchor at DSUN.EXE 0x4D614/0x4D633).

## Tier C: save/load (save-inspect + ds2-patch)

`SaveGameData`, `SaveObjectTable`/`LoadObjectTable`,
`SaveCharRec`/`SaveCurrentPCs`/`LoadInDefaultPCs`,
`SavePsiSpells`/`LoadPsiSpells`,
`LoadGpl`/`LoadExternalGpl`/`LoadInternalGpl` (answers the
internal-vs-external GPL open question in file-formats docs).

## Tier D: rules math (high patch value, needs its own RE pass)

`CndThac0Mod`, `CndACMod`, `CndDamageMod`, `CndInitiativeMod`,
`CndMRMod`, `CndSaveMod`, `CndRecalculateStats`/`CndRecalculateHP`,
`CndCharacterHit`/`CndAvoidsHit`; `SpellUseableByClass`/
`SpellUseableByPC`, `SpellSlotsForFx` (anchored by the
"SPELLS TO CAST"/"SPELL LEVEL" strings), `PsionicCost`/
`PsionicSucceeds`/`PsionicDefense`. Verification = call-shape from
the combat path in DSUN disasm; the formulas these implement are
already spec'd in `docs/rules-tables.md` and `combat-flow.md`.

## Tier E: lower priority

`NarrateOpen`/`NarrateWindProc` ("narrate" string anchor),
`ItemInfoOpen`/`ItemInfoPopUp`, `TrainSpell`/`TrainingCamp`/
`TrainPC`, `QuickCast`, `GffOpen`/`GffGetChunk`/`GffLoadChunk`
(zero in-repo mentions today).

Surface rule of thumb: `Decode*` rows belong in `syms/opcodes.toml`;
EXE function names belong in `tools/ovr-map/syms/*.toml` (and the
`docs/dso-symbols.md` catalogue); only content-level names belong
in `syms/functions.toml` - per its header, rows land only after
bytecode-behavior cross-check.
