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
