# Cookbook: Bootstrap the items.toml catalogue

How to learn what an item id represents — by giving a PC the
mystery item and looking at it in-game. Builds
`tools/save-inspect/syms/items.toml` one row at a time. No RE
needed.

**Time per item**: 30 seconds in the toolkit + however long
DOSBox takes you to alt-tab and check the inventory.
**Risk**: low. Edits land in `quantity=0` slots only; backups
are automatic.

## Prerequisites

- `save-inspect v0.9.2` or later.
- A working DOSBox + DS1/DS2 install (so you can load a
  modified save and look at it).
- A copy of your `CHARSAVE.GFF` you don't mind editing
  (`save-inspect` backs up before write, but starting from a
  spare is a belt-and-suspenders move).

## 1. Find a safe slot

Empty slots (`quantity = 0`) are safe swap targets. Changing
them doesn't displace anything the player is carrying.

```sh
$ python3 tools/save-inspect/save-inspect.py find-empty-slots \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF"
87 empty slot(s) in ...:

  PC  Slot Current-ID SlotKind   PC name
  ------------------------------------------------------------
    0    0       -822 ARM        Caron the Unsur
    0    1       -817 ARM        Caron the Unsur
    ...
    1    1       -824 ARM        Anathea
    1    7       -811 ARM        Anathea
    ...
```

Pick one. Anathea (PC 1) is the test-bed party member in
this walkthrough; her slot 7 is empty and a normal ARM slot.

## 2. Pick a candidate item id

You see an id in some other PC's inventory you can't identify,
or you want to try a hand-picked number. Item ids in Dark Sun
are i16 (range -32768..32767). Known-active ids in your save
already appear in `list-items` output.

For this walkthrough let's identify item id `-746` (the one in
Anathea's slot 0):

```sh
$ python3 tools/save-inspect/save-inspect.py list-items \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF" --pc 1 | head
PC 1 'Anathea' (CHAR 30) inventory (27 item(s)):

  Slot     ID  Qty  Chg SlotKind   Name (from syms/items.toml)
  --------------------------------------------------------------
     0   -746   20    0 ARM        ?     ← unknown id; let's identify it
     1   -824    0    0 ARM        ?
     ...
```

## 3. Plant the mystery id in an empty slot

```sh
$ python3 tools/save-inspect/save-inspect.py edit-item \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF" \
    --pc 1 --slot 7 --item-id -746 --quantity 1
PC 1 'Anathea' slot 7:
  id: -811 -> -746
  quantity: 0 -> 1

wrote 10061 bytes to /home/bdkl/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF
backup at /home/bdkl/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF.bak.1779134603
```

Slot 7 was an empty placeholder (id -811, qty 0); now it holds
a quantity-1 instance of id -746.

## 4. Load and observe

Boot DOSBox; load this save; open Anathea's inventory screen.
Slot 7 (or whatever the engine labels as the 8th item slot)
now shows... whatever id -746 is. Note the name, sprite, and
any stats the inventory tooltip shows.

## 5. Record it in items.toml

```sh
$ $EDITOR tools/save-inspect/syms/items.toml
```

Add the row:

```toml
[[item]]
id    = -746
name  = "Iron Sword"  # or whatever you actually saw
notes = "DS2; found in Anathea's slot 0 default loadout"
```

## 6. Re-run list-items

```sh
$ python3 tools/save-inspect/save-inspect.py list-items \
    "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF" --pc 1 | head -5
PC 1 'Anathea' (CHAR 30) inventory (27 item(s)):

  Slot     ID  Qty  Chg SlotKind   Name (from syms/items.toml)
  --------------------------------------------------------------
     0   -746   20    0 ARM        Iron Sword
```

The catalogue takes effect immediately.

## 7. Roll back the test edit

You don't want to keep the test item in Anathea's slot 7
forever:

```sh
$ cp "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF.bak.1779134603" \
     "$HOME/.wine/drive_c/GOG Games/Dark Sun 2/CHARSAVE.GFF"
```

Or `edit-item --slot 7 --item-id -811 --quantity 0` to restore
the original placeholder by hand.

## Scaling up

A loop of [find-empty-slots, edit-item, observe, record, roll
back] tags one id per cycle. To tag faster, fill multiple
empty slots in one pass (each PC has plenty), load DOSBox
once, observe many items, then update `items.toml` in a single
edit.

Eventually the high-frequency ids (weapons, armour pieces,
potions, scroll types) get tagged. The long tail (rare quest
items, unique magical items) gets tagged opportunistically as
you encounter unknown ids in `list-items`.

## Why this beats RE'ing the binary

The alternative is dumping the engine's item table from
`DSUN.EXE` via radare2 / Ghidra and pairing each entry's name
string with its id. That works but: it requires deep
disassembly skill, the item table's structure is undocumented,
and a lot of items have names assembled from multiple strings
("Iron" + "Sword" via two pointers in different tables).

The empirical bootstrap is shallower work — anyone who can
play the game can run it — and the catalogue gets validated
against the player-visible truth in one step. The two
approaches converge to the same `items.toml` either way.

## Related cookbook entries

- [`edit-pc-hp.md`](edit-pc-hp.md) for editing PC stats /
  HP / XP.
- (planned) `add-inventory-slot.md` once `give-item` lands and
  the chunk-growth path is RE'd.
