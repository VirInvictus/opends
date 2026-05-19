# Cookbook: Edit DS1 party PCs (HP, stats, weapon damage)

End-to-end walkthrough for the `ds1-party-edit.py` script. This
is the surface a modder actually uses; the underlying SAVE-chunk
RE is documented in
[`docs/file-formats.md`](../file-formats.md) §3.

**Audience**: DS1 player who wants to mod their active party.
**Risk**: low. Auto-backup on every edit; `restore` rolls back.
**Time**: 60 seconds per edit.

## Why this isn't `save-inspect edit-pc`

In DS1, `CHARSAVE.GFF` does **not** contain the playing party.
The active party (Gerakis, K'ratchek, Cermak, Cilla in
Brandon's save) lives inside `DARKRUN.GFF` as records in the
`SAVE-5` (combat sub-blocks) and `SAVE-6` (character
sub-blocks) chunks. `save-inspect edit-pc` operates on
`CHARSAVE.GFF`, which is the wrong altitude for DS1 active-party
edits.

`ds1-party-edit.py` is the DS1-specific tool that operates on
`DARKRUN.GFF` and `SAVE01.SAV` together (engine reads SAVE01
on load, writes DARKRUN during play; both need the same edits
to survive a reload).

DS2 active-party edits via `save-inspect edit-pc` still work
because DS2 stores party stats in `CHARSAVE.GFF`. The two games
diverge here.

## Prerequisites

- Your DS1 install with at least one save (the script defaults
  to `~/.wine/drive_c/GOG Games/Dark Sun/DARKRUN.GFF` and
  `SAVE01.SAV`).
- Python 3.11+ (stdlib-only; no Rust binaries required for
  this script).

## 1. See who's in your party

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py list
4 party PC(s) in /home/bdkl/.wine/drive_c/GOG Games/Dark Sun/DARKRUN.GFF:
  0  Gerakis         HP=  54  stats=[24, 15, 22, 13, 15, 14]
  1  K'ratchek       HP=  19  stats=[19, 21, 19, 16, 19, 15]
  2  Cermak          HP=  45  stats=[19, 18, 19, 18, 17, 18]
  3  Cilla           HP=  15  stats=[19, 21, 17, 18, 18, 16]
```

The index (0..3) and the name (case-insensitive substring
match) both work as `--pc` / `<pc>` arguments.

## 2. See one PC's full record

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py show Gerakis
PC 0: Gerakis
  combat record at abs offset 25027
  char record   at abs offset 27463
  combat HP=54 PSP=27 stats=[24, 15, 22, 13, 15, 14] (STR DEX CON INT WIS CHR)
  char   XP=4000 max_hp=54 max_psp=27
  char   stats=[24, 15, 22, 13, 15, 14]
  char   weapon: 1d1+0 (num_dice/sides/bonuses [0..2] = [1, 0, 0] / [1, 0, 0] / [0, 0, 0])
```

Note the `weapon: 1d1+0` — Gerakis's CACHED weapon damage is
`1d1` (= always 1 damage). The 2e damage bonus from STR is
computed at attack time from the engine's table; if you set STR
above 25 the table returns +0, so this weapon would do 1 damage
per hit. See "Engine quirks" below.

## 3. Edit fields

### Make a PC literally invincible

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py edit Gerakis \
    --hp 999 --max-hp 999 --psp 200 --max-psp 200
PC 0: Gerakis
  combat.hp -> 999: 36 00 -> e7 03
  char.base_hp -> 999: 36 00 -> e7 03
  ...

wrote .../DARKRUN.GFF
wrote .../SAVE01.SAV
backups: .../DARKRUN.GFF.bak.ds1-party-edit.1779148235
         .../SAVE01.SAV.bak.ds1-party-edit.1779148235
```

### Give a PC a real weapon

The "1 damage" problem is fixed by editing the cached weapon
fields directly (`num_dice` / `num_sides` / `num_bonuses`):

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py edit Gerakis \
    --weapon-dice 5 --weapon-sides 20 --weapon-bonus 50
# 5d20+50 = 55..150 damage per hit
```

`num_dice[0]` / `num_sides[0]` / `num_bonuses[0]` are at offsets
46 / 49 / 52 of the character sub-block (per libgff's
`ds1_character_t`). The character record holds three weapon
slots; the script edits slot 0 only.

### Bump stats (sanely)

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py edit Gerakis \
    --str 24 --con 25
# half-giant max STR; CON above 19 gives extra HP regen in 2e
```

Stats edit both the combat sub-block (display) AND the character
sub-block (engine-authoritative) so the values stay consistent.

Keep stats **at or below 25** to stay inside the 2e table the
engine uses. STR 99 worked visually in the character sheet but
made damage drop to 1 (see Engine quirks).

### Level-up via XP

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py edit Gerakis --xp 50000
```

The engine recomputes level on next reload from the XP table.
Whether HP / spell slots / etc. update at that moment is engine-
specific; in 2e they typically do.

### Always preview first

`--dry-run` shows what would change without writing:

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py edit Gerakis \
    --weapon-dice 5 --weapon-sides 20 --weapon-bonus 50 --dry-run
PC 0: Gerakis
  char.num_dice[0] -> 5: 01 -> 05
  char.num_sides[0] -> 20: 01 -> 14
  char.num_bonuses[0] -> 50: 00 -> 32

dry-run: no file written.
```

## 4. Roll back

If anything looks wrong in-game:

```sh
$ python3 tools/save-inspect/scripts/ds1-party-edit.py restore
restored from:
  .../DARKRUN.GFF.bak.ds1-party-edit.1779148235
  .../SAVE01.SAV.bak.ds1-party-edit.1779148235
```

`restore` picks the most recent `.bak.ds1-party-edit.<ts>` pair.
For older states, copy the specific backup files manually.

## Engine quirks

Things we learned by reading the engine's responses:

### 1. Stats above 25 break the damage-bonus table

D&D 2e's STR table tops out at 25 (with the "exceptional
strength" 18/00-18/100 sub-range above 18). The engine indexes
that table by your STR byte. Above 25, the index is out of
range; the engine returns +0 damage bonus.

Brandon's first test set Gerakis's stats to 99 each. His
character sheet correctly showed 99/99/99/99/99/99 (the engine
displayed what was in the byte). But his damage dropped to 1
per hit because his weapon was `1d1` and STR 99 added +0
bonus.

**Practical**: set stats to realistic values (≤ 25) and let the
table bonuses work, OR edit the weapon's `num_dice` /
`num_sides` / `num_bonuses` directly to get the damage you
want regardless of the bonus table.

### 2. SAVE-5 is the display copy; SAVE-6 is the source of truth

Stats appear in BOTH SAVE-5 (combat sub-block, 58 bytes) and
SAVE-6 (character sub-block, 71-72 bytes). The first edit
attempt only modified SAVE-5 stats and saw the character sheet
update visually — but combat math reads from SAVE-6. The
script writes to both so visual and engine stay in sync.

### 3. DARKRUN.GFF and SAVE01.SAV must match

Per v0.6.0's save-inspect finding: `SAVE0N.SAV` is byte-
identical to `DARKRUN.GFF` at save time. The engine loads from
`SAVE01.SAV`; `DARKRUN.GFF` tracks live state during play. An
edit to only `DARKRUN.GFF` gets wiped on reload because the
engine reloads SAVE01 over it. The script writes to both.

## Available flags reference

| Flag | Field edited | Range |
|---|---|---|
| `--hp N` | combat.hp | i16 |
| `--psp N` | combat.psp | i16 |
| `--max-hp N` | character.base_hp | u16 |
| `--max-psp N` | character.base_psp | u16 |
| `--xp N` | character.current_xp | u32 |
| `--str / --dex / --con / --int / --wis / --cha N` | combat + character stats[i] | u8; recommend ≤ 25 |
| `--weapon-dice N` | character.num_dice[0] | u8 |
| `--weapon-sides N` | character.num_sides[0] | u8 |
| `--weapon-bonus N` | character.num_bonuses[0] | u8 |
| `--dry-run` | preview without writing | |
| `--no-backup` | skip the auto-backup | |

## What this cookbook deliberately leaves out

- **Race / class / alignment edits**. Changing race or class
  affects derived fields (HP at level-up, spell tables, save
  matrices) that the engine recomputes; raw byte edits can
  desync those and produce a broken character. If you want a
  different race / class, use character re-creation in-game.
- **Inventory edits**. Items live in CHARSAVE.GFF (see the
  `save-inspect list-items` / `edit-item` / `give-item`
  commands and the `bootstrap-items.md` cookbook entry); they
  aren't part of the active-party flow this script targets.
- **Adding party members**. The script edits existing slots
  only. Adding a fifth PC would mean inserting a new record
  into SAVE-5 and SAVE-6 plus updating any per-region count
  fields the engine reads; not yet RE'd.

## See also

- [`edit-pc-hp.md`](edit-pc-hp.md) — the equivalent for DS2
  CHARSAVE.GFF (works for DS2 active party; DS1 only for
  inactive char templates)
- [`bootstrap-items.md`](bootstrap-items.md) — the items.toml
  catalogue bootstrap loop
- [`../file-formats.md`](../file-formats.md) §3 — the SAVE-5 /
  SAVE-6 layout details
