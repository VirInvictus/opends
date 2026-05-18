# Cookbook: Edit a PC's HP, max HP, and stats

End-to-end walkthrough. Uses Brandon's GOG-Wine install paths;
substitute your own. Three real commands, real before/after
output, real backups taken.

**Time**: 60 seconds.
**Risk**: low. Backups are automatic. Roll back is one `cp`.

## Prerequisites

- `save-inspect v0.9.0` or later. Build with `cargo build
  --release` (Rust workspace) — the Python script itself needs
  no build step, but it shells to `gff-cat` for chunk-level
  writes, which is a Rust binary.
- Your game install. This walkthrough uses
  `~/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF` (an
  active DS2 playthrough). Any `CHARSAVE.GFF` works.

## 1. See who's in the party

```sh
$ python3 tools/save-inspect/save-inspect.py list-pcs \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF"
19 PC(s) in /home/bdkl/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF:

  PC  CHAR  Name               HP/ Max   PSP/ Max        XP  Items
  ----------------------------------------------------------------------
    0    29 Caron the Unsur    21/  21    28/  28     64000  5
    1    30 Anathea            81/  81   144/ 144    122690  27
    ...
   15    50 Ar'Anda            34/  57   162/ 202   1400000  11
   18    53 Terrannus          88/ 113    11/  91   2475000  10
```

The PC column is your handle (`--pc N`). Note the active party
typically shows up at higher PC indices (15-18 here) with the
high XP totals. Caron, Anathea, etc. at the top are spare /
unused character slots.

## 2. Preview the edit (dry-run)

Bring Ar'Anda (PC 15) back to full HP and bump her stats:

```sh
$ python3 tools/save-inspect/save-inspect.py edit-pc \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF" \
    --pc 15 --hp 57 --max-hp 60 --str 18 --con 18 --dry-run
PC 15 'Ar'Anda' (CHAR 50):
  hp: 34 -> 57
  max_hp (character.base_hp): 57 -> 60
  combat.stats.str: 17 -> 18
  character.stats.str: 17 -> 18
  combat.stats.con: 14 -> 18
  character.stats.con: 14 -> 18

dry-run: no file written.
```

`--dry-run` shows exactly what would change, including the
combat / character sub-block routing. STR and CON write to both
sub-blocks so the values stay consistent (the engine reads from
both at different times).

## 3. Apply for real

Drop `--dry-run`:

```sh
$ python3 tools/save-inspect/save-inspect.py edit-pc \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF" \
    --pc 15 --hp 57 --max-hp 60 --str 18 --con 18
PC 15 'Ar'Anda' (CHAR 50):
  hp: 34 -> 57
  max_hp (character.base_hp): 57 -> 60
  combat.stats.str: 17 -> 18
  character.stats.str: 17 -> 18
  combat.stats.con: 14 -> 18
  character.stats.con: 14 -> 18

wrote 10061 bytes to /home/bdkl/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF
backup at /home/bdkl/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF.bak.1779134466
```

A `.bak.<mtime>` backup is taken next to the original. Skip it
with `--no-backup` if you have a separate backup discipline.

## 4. Verify the change stuck

```sh
$ python3 tools/save-inspect/save-inspect.py list-pcs \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF" | grep -E '^ +15 '
   15    50 Ar'Anda            57/  60   162/ 202   1400000  11
```

HP went 34 → 57, max-HP 57 → 60, ready to load in DOSBox.

## 5. Load in DOSBox

Boot the game normally; load this save slot. Open the character
sheet for Ar'Anda. The new HP / stats should be visible. If
they aren't, the engine probably re-derived something from
class / level (some fields are computed on load); see
`Caveats` below.

## Roll back

If something looks wrong in-game and you want the original:

```sh
$ cp "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF.bak.1779134466" \
     "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF"
```

The `.bak.<mtime>` filename uses the original file's mtime, so
backups across multiple edits don't collide.

## Available `edit-pc` flags

| Flag         | Field                                       |
|--------------|---------------------------------------------|
| `--hp N`     | current HP (combat.hp)                      |
| `--psp N`    | current PSP (combat.psp)                    |
| `--max-hp N` | max HP (character.base_hp)                  |
| `--max-psp N`| max PSP (character.base_psp)                |
| `--xp N`     | current XP (character.current_xp)           |
| `--str / --dex / --con / --int / --wis / --cha N` | stats |

D&D 2e stat range is 3-25 (with rare exceptions). The encoder
validates u8 range (0-255) but doesn't enforce the 3-25 rule;
out-of-range values may get clamped in-engine or cause display
glitches.

## Caveats

- **Derived fields**: HP at level-up, base AC, attack rolls,
  and saving throws are derived from class / level / stats at
  load time. Editing stats may not change those derived values
  until the engine re-derives (often on next region transition
  or rest).
- **Class change**: not supported by `edit-pc` (touches
  `legal_class` / `real_class` / `level` arrays + recomputes
  HP / spell tables — too easy to corrupt). Use a character-
  generation save and re-import if you want a different class.
- **Adding items**: `edit-pc` doesn't grow inventory. Use
  `edit-item` to overwrite an existing empty slot (`save-inspect
  list-items --pc N` first to see slot indices).
- **DS1 vs DS2**: the same `--pc N` index works for both games
  (the PC index is the CHAR record order in the file). Combat
  / character sub-block schemas differ between games but
  `edit-pc` handles the dispatch transparently.

## What's next

- `edit-item --pc N --slot K --item-id X --quantity Q`: change
  any existing slot's contents in place. Use this to bootstrap
  the `tools/save-inspect/syms/items.toml` catalogue — set a
  spare slot to a candidate id, load in DOSBox, see what shows
  up, tag the id with a name.
- `list-items --pc N`: see slot indices and current ids before
  editing.
- This cookbook covers single-PC stat / HP edits. Cookbook
  entries for items, save-state surgery, and bytecode patches
  land as the underlying tools settle.
