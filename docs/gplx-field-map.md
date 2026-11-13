# GPLX 1: the script object-field map

Decoded 2026-11-13 from yuan-ti's traced notes
([`yuan-ti`](https://github.com/CalvinRodo/yuan-ti)
`.github/instructions/dsun-exe-reference.md` §"Object fields" and
`engine/src/DarkSun.Game/Scripting/GplFieldMap.cs`, MIT; credited
in [`../CREDITS.md`](../CREDITS.md)). The facts below close the
open note in [`gate-review-yuan-ti-2026-11-13.md`](gate-review-yuan-ti-2026-11-13.md):
the field paths the yuan-ti repairs touch now have meanings, and
the repair mechanisms read as fully explained.

## The chunk

`GPLX` 1 (DS1 `GPLDATA.GFF`) is the field map behind every
`obj(id).f` and `obj_special(n).f` access: five groups of 99
little-endian words (0..494), the field's byte offset in each
group's record (−1 where the field does not exist), then at
`0x3DE` one type byte per field, then the five record sizes:
item 21, combat 58, name 25, character 71, item type 20.

Group order: item (0), combat (1), name (2), character (3),
item type (4). Type bytes: 16 signed byte, 18 object id, 19 and
22 word, 20 long, 21 unsigned word, 0x80+ an inline string of
(type & 0x7F) bytes; 3, 4 and 5 are pointers into the name,
character and item-type records (the engine follows them on
read). The five-word groups mean one field id reads different
records depending on the object's kind: field 43 is the
character record's most-hit-points when the object has a sheet,
and reads 0 on an item (the item group's entry for 43 does not
exist). That single fact is the sewer-grate attack bug's whole
mechanism: `field[43] < 220` on the grate item is always true
because an item has no field 43.

## Fields the repair sites touch

| Field id | Meaning | Record, offset | Where our docs meet it |
|---|---|---|---|
| 2 | pointer to the name record | name group | the weapon-name print `obj.2.94` (GPL 137) |
| 17 | usable-class bits | character +0x12 | the tracking ranger test (GPL 210): reading it off the combat record instead of the sheet is the bug; 0x200 is the ranger bit |
| 19 | name (18 bytes) | combat +0x28 | |
| 20 / 21 / 22 | race / sex / alignment | character +0x18 / +0x19 / +0x1A | the halfling greeting/insult fix (`.71.20`), the his/her fix (`.71.21`) |
| 23-28 | Str, Dex, Con, Int, Wis, Cha | combat +0x22-0x27 | the grate attack fix reads field 23 (Str of the active member) |
| 29-34 | the six abilities | character +0x1B-0x20 | |
| 35-40 | class codes, levels | character +0x21-0x26 | the tracking level bonus tests 35/36/37 (class codes 13-16 are ranger) |
| 43 / 45 | most hit points / psionic points | character +8 / +0x0C | the grate attack bug (field 43 on an item reads 0) |
| 62-66 | saving throws | character +0x37-0x3B | |
| 67 / 68 | current hit points / psionic points | combat +0 / +2 | GPL 49 fills a member's: `.68 = .71.45` |
| 71 | pointer to the character record | combat +4 | every `.71.x` path (the sheet) |
| 72 | id (what `name(-n)` matches) | item +0, combat +6 | |
| 73 | status (`.73 > 2`: down or dead) | combat +0x1C | |
| 74 | allegiance | combat +0x1D | `REQUEST(18)` sets it |
| 75 | AI disposition | combat +0x1E | `SETRECORD .75 = 2` after `REQUEST(18, ..., 2)`: fight |
| 89 | special attack (word, +0x17 special defense) | combat +0x16 | GPL 81 sets Balkazar's to 0 |
| 94 | name (inline string) | name record | the weapon-name print (GPL 137, obj.2.94) |
| 95 | facing | combat +0x38 | |
| 0 / 82 / 85 / 86 | flags (a door's state) / quantity / slot / charges | item +0x0F / +2 / +0x11 / +0x0E | |

The two keyword-ish helpers scripts use around these reads:
`GETPARTY` sets "other" (`gname[8]`, DSUN.EXE `043D:1468`) to the
member it returns; `SETTHING` (`1A0A:261E`) walks an object's
items making each the "thing" (`gname[11]`), from the first again
when n is 9999 or the owner changes. The 0x8000-flagged operand
forms our decoder renders as `obj_name 32805/32806/32812` in the
repair sites are these keyword objects seen through complex
access; their per-value identities (0x25 / 0x26 / 0x0C) are not
named in yuan-ti's notes either and stay open here.

## Class bits (character +0x12, field 17's target)

One bit per class code, from `38D4:00ED` + class x 4 + sphere
(the codes: 1-4 cleric of air/earth/fire/water, 5-8 druid, 9
fighter, 10 gladiator, 11 preserver, 12 psionicist, 13-16
ranger, 17 thief): bits 1/2/4/8 the four clerics, 0x10 druid,
0x20 fighter, 0x40 gladiator, 0x80 preserver, 0x100 psionicist,
0x200 ranger, 0x400 thief. 0x800 and 0x1000 belong to no player
class (wands and scrolls carry 0x880: likely defiler and
templar). Wearing an item needs a bit in common with the item's
own class word (`6466:0854`); 44 of 115 item types are 0x1FFF
(anyone). Source: yuan-ti exe-reference §"Items" (`IT1R` +0x12).

This resolves the tracking bug's two halves exactly: the ranger
test bit-tests field 17 (the class-bits word) for 0x200, which is
correct semantics read from the wrong record; the level bonus
bit-tests fields 35/36/37 (class CODES 13-16) against the same
0x200, which is always false because a code is not a bitmask.
