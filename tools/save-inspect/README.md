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

## What v0.4.0 ships

**DS2 combat full structured decode.** v0.3.0 surfaced the
DS1-shared 24-byte prefix and heuristically located the stats
block 8 bytes before the name. v0.4.0 locks the entire 49-byte
DS2 combat layout (corpus-validated on every CHAR record in
`.games/ds2/__support/save/CHARSAVE.GFF`):

| Offset | Field |
|--------|-------|
| 0..23  | DS1-shared prefix (hp, psp, char_index, id, ready_item_index, weapon_index, pack_index, data_block[8], special_attack, special_defense) |
| 24     | `_reserved_0` (always 0x00 observed) |
| 25..30 | `stats` (str, dex, con, intel, wis, cha) |
| 31     | `_slot_31` (small range 0..6; alignment / class / flags candidate, semantics open) |
| 32     | `_reserved_1` (always 0x00 observed) |
| 33..48 | `name[16]` (NUL-padded) |

The output schema swaps `_format = "ds2_partial_combat"` for
`_format = "ds2_combat"` and replaces the `_likely_*` heuristic
keys with first-class `stats` + `name` fields. Three positions
(24, 31, 32) carry placeholder field names because their
semantics aren't yet pinned to DSUN.EXE source; they're
surfaced as opaque bytes rather than guessed.

```json
"decoded": {
  "_format": "ds2_combat",
  "hp": 81,
  "psp": 144,
  "char_index": 3,
  "id": -32766,
  "ready_item_index": 476,
  "weapon_index": 485,
  "pack_index": 491,
  "data_block_hex": "0000070000000a0c",
  "special_attack": 14,
  "special_defense": 7,
  "_reserved_0": 0,
  "stats": {"str": 20, "dex": 21, "con": 19, "intel": 20, "wis": 20, "cha": 17},
  "_slot_31": 2,
  "_reserved_1": 0,
  "name": "Anathea"
}
```

**Out of scope for v0.4.0** (queued for v0.5.0):

- DS2 **character** sub-block (66 bytes vs DS1's 71). Drops 5
  bytes vs DS1 in some combination of `palette`, the trailing
  `legal_class_ext` byte, or shorter `real_class` arrays. Still
  emitted as opaque hex.
- Pin down the three placeholder fields (`_reserved_0`,
  `_slot_31`, `_reserved_1`). Best path is DSUN.EXE RE of the
  `SaveCharRec` analog: DSO's symbol table names it at offset
  `0x0002C45F` in the DSO binary, so the DS2-DSUN.EXE
  counterpart is locatable by call-graph shape against the
  CHARSAVE I/O strings (`CHARSAVE.GFF`, `charsave.gff`).

## What v0.3.0 ships

**DS2 combat partial decode.** v0.2.0 surfaced the character
name and raw hex for DS2 combat sub-blocks; v0.3.0 also decodes
the DS1-shared prefix (the first ~24 bytes — HP, PSP,
char_index, id, ready/weapon/pack item indices, data_block,
special_attack, special_defense) and heuristically locates the
stats block 8 bytes before the character-name field. Empirical:
the stats anchor matches every DS2 CHARSAVE record we've tested
(D&D 2e range 1..30 on six consecutive bytes).

```json
"decoded": {
  "_format": "ds2_partial_combat",
  "hp": 81,
  "psp": 144,
  "special_attack": 14,
  "_likely_stats": {
    "str": 20, "dex": 21, "con": 19,
    "intel": 20, "wis": 20, "cha": 17
  },
  "_likely_name": "Anathea"
}
```

Full DS2 schema RE (the remaining ~7 bytes of combat + the
66-byte character record) is queued for v0.4.0; needs more
saves to cross-reference.

**Save diff subcommand.** Compare two `CHARSAVE.GFF`s and report
what changed:

```sh
save-inspect.py diff a.GFF b.GFF --pretty
```

Output is structured JSON: every changed field carries a `path`
(e.g. `["chunks[CHAR-30]", "body", "sub_blocks", 0, "decoded",
"hp"]`), the old value, and the new. Added / removed chunks
get their own kinds. The diff goes through `summarise` so
DS1-fully-decoded fields show field-level diffs, and DS2's
partial-decode fields show the same partial surface.

```json
{
  "summary": {
    "changed_chunk_count": 1,
    "added_chunk_count": 0,
    "removed_chunk_count": 0,
    "change_count": 3
  },
  "changes": [
    {
      "path": ["chunks[CHAR-30]", "body", "sub_blocks", 0, "rdff_header", "blocknum"],
      "kind": "value_changed",
      "from": 29, "to": 30
    },
    ...
  ]
}
```

Usage:

```sh
save-inspect.py diff a.GFF b.GFF                 # JSON to stdout
save-inspect.py diff a.GFF b.GFF --pretty        # indented
save-inspect.py diff a.GFF b.GFF -o diff.json    # to file
```

## What v0.2.0 ships

v0.2.0 decodes the CHAR record body into structured combat /
character / item sub-blocks for DS1 (full schema) and surfaces
the character name + raw hex for DS2 (heuristic until the DS2
schema is fully RE'd).

| Chunk | Decoded as | Source |
|-------|------------|--------|
| `CHAR` | RDFF header + walked sub-blocks (combat/character/items, per-game) | libgff `include/gff/rdff.h` + `object.h` + `item.h`; libsoloscuro `src/entity.c` |
| `PSIN` | 7-element `types[]` array (psionic disciplines) | libgff `include/gff/psionic.h` |
| `PSST` | 34-element `psionics[]` array (psionic mastery) | libgff `include/gff/psionic.h` |
| `SPST` | hex preview (spell-list bitmask; bit layout TBD) | libgff (TBD) |
| `CACT` | hex preview (valid character ID flags; TBD) | libgff (TBD) |
| `TEXT` | plain ASCII (CRLF normalised to `\n` in JSON) | OpenDS `docs/file-formats.md` |
| `PREF` | hex preview (user preferences; TBD) | TBD |
| `GREQ` | hex preview (DS2-only; group/quest? TBD) | TBD |

### CHAR body shape

The CHAR body is a sequence of RDFF-headed sub-blocks. The
first sub-block's `blocknum` field gives the total sub-block
count. Per libsoloscuro's `sol_entity_load_from_gff`, the order
is **positional**: sub[0] is combat, sub[1] is the character
record, sub[2..N-1] are item slots, optionally followed by an
`RDFF_END` terminator (`load_action == -1`, `len == 0`).

```json
"body": {
  "expected_sub_block_count": 7,
  "sub_blocks": [
    {
      "role": "combat",
      "rdff_header": { ... },
      "decoded": {
        "hp": 21, "psp": 28, "ac": 6, "thac0": 18,
        "stats": { "str": 17, "dex": 16, "con": 18, ... },
        "name": "Garn"
      }
    },
    {
      "role": "character",
      "decoded": {
        "current_xp": 4321, "race": { "value": 1, "name": "HUMAN" },
        "gender": { "value": 0, "name": "MALE" },
        "alignment": { "value": 4, "name": "TRUE_NEUTRAL" },
        "real_class": [3, -1, -1], "level": [5, 0, 0], ...
      }
    },
    { "role": "item", "decoded": { "slot": { "value": 3, "name": "HAND0" }, "item_index": 81, ... } }
  ]
}
```

### Per-game schema status

| Sub-block | DS1 length | DS2 length | DS1 decode | DS2 decode |
|-----------|-----------:|-----------:|------------|------------|
| combat    | 58 bytes   | 49 bytes   | full       | name only (heuristic ASCII scan), raw hex otherwise |
| character | 71 bytes   | 66 bytes   | full       | raw hex (layout differs from libgff struct) |
| item      | 21 bytes   | 23 bytes   | full minus trailing `priority`+`data0` | full |

DS2 combat and character sub-blocks land in v0.3.0 once their
exact field layouts are RE'd; v0.2.0 marks them
`_format: "ds2_or_unknown_..._layout"` so consumers can detect
the partial decode.

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
