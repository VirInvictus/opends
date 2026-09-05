# save-inspect

Dump a Dark Sun `CHARSAVE.GFF` save file as JSON. Modder-facing
tool for inspecting what's in a save without firing up the game.

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+ (matches the rest of the toolkit).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## Usage

```sh
python3 save-inspect.py /path/to/CHARSAVE.GFF
python3 save-inspect.py /path/to/CHARSAVE.GFF --pretty
python3 save-inspect.py /path/to/CHARSAVE.GFF -o save.json
```

JSON is emitted to stdout by default; `-o <file>` writes to a
file instead.

## Subcommands

The high-leverage common cases, without hand-editing the JSON
tree of a full `save-edit`:

| Subcommand                                | Purpose                                         |
|-------------------------------------------|-------------------------------------------------|
| `list-pcs <save>`                         | Enumerate PCs with HP/PSP/XP/item count         |
| `list-items <save> --pc N`                | One PC's inventory with `syms/items.toml` names |
| `find-empty-slots <save>`                 | Safe `edit-item` targets (qty=0 slots)          |
| `edit-pc <save> --pc N ...`               | HP/PSP/stats/XP edits with combat ↔ character sync |
| `edit-item <save> --pc N --slot K ...`    | One slot's id/qty/charges (no chunk growth)     |
| `give-item <save> --pc N ...`             | Append a new item to a PC's chain (chain-invariant validated) |

These work for **DS2 active party** (CHARSAVE-based) and for
**DS1 inactive char templates**. They do **not** work for the
DS1 active party, which lives in `DARKRUN.GFF` (see next).

### `scripts/ds1-party-edit.py`: the DS1 active-party tool

DS1's active party (the PCs Brandon plays as) is stored in
`DARKRUN.GFF` SAVE/5 (combat sub-blocks) and SAVE/6 (character
sub-blocks), not in `CHARSAVE.GFF`. The
`scripts/ds1-party-edit.py` script edits party PCs directly
in those chunks, writing both `DARKRUN.GFF` and `SAVE01.SAV`
together so edits survive a reload.

```sh
ds1-party-edit.py list                                      # 4 party PCs
ds1-party-edit.py show Gerakis                              # full record
ds1-party-edit.py edit Gerakis --hp 999 --max-hp 999        # stat-bypass damage
ds1-party-edit.py edit Gerakis --weapon-dice 5 --weapon-sides 20 --weapon-bonus 50
ds1-party-edit.py restore                                   # roll back
```

Full walkthrough: [`docs/cookbook/edit-ds1-party.md`](
../../docs/cookbook/edit-ds1-party.md). The save-file layout
this rests on: [`docs/file-formats.md`](
../../docs/file-formats.md) §3. Engine quirks bystanders
should know about: [`docs/engine-quirks.md`](
../../docs/engine-quirks.md).

---

## Semantic diffs

`scripts/save-semantic-diff.py` diffs two DARKRUN-shape saves and
annotates each changed byte range with field meaning from
`syms/save-fields.toml` (confidence + evidence per row); uncovered
ranges print as UNKNOWN. Do an action in-game, save, diff against
the pre-action save, and confirmed findings become new catalogue
rows.

## What's known about SAVE-chunk structure

Based on one DS1 played save (see `syms/save-fields.toml` for the
row-level view):

| Chunk id   | Size           | Speculation                          |
|------------|----------------|--------------------------------------|
| 1          | 10240 bytes    | Largest. Almost certainly party / PCs.|
| 2-9        | 100-3000 bytes | Per-region world state (varies).     |
| 10-17      | 2 bytes (u16)  | Counters / coords / region pointers. |
| 18         | 51 bytes       | Boolean array (all 0x01 in sample).  |
| 19-60      | 100-2000 bytes | More per-region or per-NPC blobs.    |

SAVE/5 (58-byte combat records: stats at 34..39, name at 40..57)
and SAVE/6 (character sub-blocks) are verified via
`scripts/ds1-party-edit.py`. DS2 shares the wire format per the
engine's shape; treat unverified rows as questions.

## Roundtrip

```sh
python3 save-inspect.py roundtrip <file>   # decode -> re-encode -> verify byte-identical
```

## Smoke test

```sh
python3 save-inspect.py ~/.wine/drive_c/GOG\ Games/Dark\ Sun/CHARSAVE.GFF --pretty | head -40
```

## Implementation note

`save-inspect` parses GFF directly in Python rather than shelling
out to `gff-cat`. `CHARSAVE.GFF` only ever uses indexed chunks
(no `GFFI` segmented cross-reference), so a small embedded parser
is sufficient and avoids subprocess overhead. If we ever need to
inspect a save type that uses segmented chunks, the embedded
parser can be replaced with `gff-cat --json` calls or a Python
binding to the `gff-edit` Rust crate.
