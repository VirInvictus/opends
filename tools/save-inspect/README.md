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

## What v0.9.x ships

The **modder-altitude surface** layered on top of the v0.8.0
write path. v0.9.0 - v0.9.4 added subcommands that target the
high-leverage common cases without requiring hand-edits to the
v0.8.0 JSON tree:

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

### `scripts/ds1-party-edit.py` — the DS1 active-party tool

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

## What v0.8.0 ships

**The write path: `save-edit` plus a `roundtrip` regression
harness.** v0.1.0 - v0.7.0 read; v0.8.0 closes the loop and
delivers the first true mod workflow on the toolkit. Edit a
character's HP from a JSON file, run `save-edit`, the game
loads the modified save.

```sh
# Decode → edit → encode → game-ready GFF.
python3 save-inspect.py CHARSAVE.GFF -o save.json
# ...edit save.json (e.g. change combat.hp from 54 to 999)...
python3 save-inspect.py save-edit save.json CHARSAVE.GFF \
    -o patched.gff
# patched.gff now loads in the game with HP=999.
```

Backup-before-write (`patched.gff.bak.<mtime>` next to the
output), `--dry-run` mode, `--no-backup` opt-out. Refuses to
add or remove chunks (the count must match the original).

### Built-in round-trip test

```sh
python3 save-inspect.py roundtrip CHARSAVE.GFF
```

Decodes every chunk, re-encodes, asserts byte-identical;
exit 0 if every chunk round-trips, exit 1 if any fail.

Corpus results at v0.8.0:

| Save                                   | Result    |
|----------------------------------------|-----------|
| DS1 factory CHARSAVE.GFF               | 27 / 27   |
| DS2 factory CHARSAVE.GFF               | 98 / 98   |
| DS1 factory DARKSAVE.GFF               | 1 / 1     |
| DS1 played DARKRUN.GFF (Brandon's)     | 63 / 63   |

**100% chunk-level byte-identity across every save in the
corpus.** File-level output is smaller than the original
(the original carries 1.6 KB of pre-allocated gap space
between chunks; the writer packs contiguously);
engine-equivalent, just compacted.

### Encoders shipped

Every existing decoder gets a sibling encoder, same field
ordering, same `struct.pack` format:

- `_encode_combat` / `_encode_combat_ds2` (58 / 49 bytes)
- `_encode_character` / `_encode_character_ds2` (71-72 / 66)
- `_encode_item` (21 / 23 bytes; dispatches by `_format`)
- `_encode_stats`, `_encode_saving_throw` (sub-helpers)
- Chunk-level paths for CHAR / PSIN / PSST / TEXT / STXT /
  SAVE / ETME / ETAB.

Plus a pure-Python `write_gff(parsed, chunk_bytes)` that
inverts `parse_gff`: 28-byte header, contiguous chunk data
starting at offset 28, TOC at the end.

### Fidelity fixes (the messy real-world bytes)

Three issues surfaced during corpus round-trip and were
fixed without changing the JSON output schema for v0.6.0
consumers:

- **Combat name padding**. Real saves leave non-zero
  garbage in the trailing bytes of the 16-char name field
  (the engine doesn't always zero the buffer). The
  decoder now captures `_name_raw_hex` alongside `name`;
  the encoder uses the raw hex for byte-identical
  round-trip. When the user edits `name` and deletes
  `_name_raw_hex` from the JSON, the encoder falls back
  to clean null-padding (engine-valid; not byte-identical
  with the original).
- **DS1 item truncation**. DS1's 21-byte items truncate
  the decoder at the 2-byte `priority` field with 1 byte
  remaining. The decoder now captures the leftover in
  `_trailing_hex`; the encoder re-emits it.
- **Opaque-chunk full bytes**. SAVE / ETAB / SPST / CACT /
  PREF / GREQ decoders emit `_raw_bytes_hex` (full
  bytes) alongside the truncated `raw_hex` preview.
  Necessary because DARKRUN SAVE chunks hit 10 KB and the
  128-byte preview cap would lose the tail on re-encode.

### What v0.8.0 does NOT ship

- **Edit-time validation against game schemas**. The
  encoder validates byte ranges (u8 fits in 0..255) but
  doesn't know that, e.g., a Cleric character can't have
  alignment Chaotic Evil. Game-rule validation is a
  separate feature; for now, the engine catches
  inconsistencies at load time.
- **Adding or removing chunks**. The chunk count must
  match the original. Adding inventory beyond the original
  count is a v0.9.0 candidate.
- **Per-region SAVE chunk structured editing**. SAVE
  chunks are still opaque hex (v0.7.0 surface); editing
  party position or quest state requires hand-editing the
  hex. Field-level decoding is multi-session RE work.

---

## What v0.7.0 ships

**SAVE-chunk structural decode + `save-diff` subcommand.**
v0.1.0 - v0.6.0 closed CHARSAVE.GFF (every PC sub-block now
decodes). v0.7.0 opens the DARKRUN side: per-region world
state inside `DARKRUN.GFF` (or its byte-identical twin
`SAVE0N.SAV`), ~60 SAVE chunks per saved game.

The schema is empirically incomplete (no public docs; no game
source). v0.7.0 ships the **harness the RE runs through**, not
the full schema:

- **`decode_chunk` now handles four new kinds**: `SAVE` (world
  state; `_format: ds1_save_chunk`; the 2-byte family at chunk
  ids 10..17 decodes as `u16_value`; rest as opaque hex),
  `STXT` (save name, null-terminated ASCII padded; the "FUCK"
  save's name surfaces as `{"name": "FUCK", "length_used": 4,
  "length_total": 45}`), `ETAB` (engine entity table; opaque
  hex + leading-zero-byte fingerprint), `ETME` (engine-template
  text, present in both factory DARKSAVE.GFF and played
  DARKRUN.GFF).
- **`save-diff` subcommand**:

  ```sh
  python3 save-inspect.py save-diff factory.gff played.gff --pretty
  ```

  Operates at the chunk-byte level (unlike the existing `diff`,
  which walks decoded summaries field-by-field). Per-chunk
  `byte_diff_count` plus `first_diff_offset` plus 64-byte hex
  previews of both sides. Default: SAVE chunks only;
  `--all-chunks` includes ETAB / STXT / ETME / etc.

  Intended workflow for working out world-state semantics
  empirically: do an action in-game, save, run `save-diff`
  against the pre-action save, see exactly which bytes changed
  in which chunk.

### What's known about SAVE-chunk structure

Based on one DS1 played save (the "FUCK" save at
`~/.wine/drive_c/GOG Games/Dark Sun/DARKRUN.GFF`):

| Chunk id   | Size           | Speculation                          |
|------------|----------------|--------------------------------------|
| 1          | 10240 bytes    | Largest. Almost certainly party / PCs.|
| 2-9        | 100-3000 bytes | Per-region world state (varies).     |
| 10-17      | 2 bytes (u16)  | Counters / coords / region pointers. |
| 18         | 51 bytes       | Boolean array (all 0x01 in sample).  |
| 19-60      | 100-2000 bytes | More per-region or per-NPC blobs.    |

DS2 likely shares the wire format (engine code is the same
shape per `docs/dso-symbols.md`) but no played DS2 sample
exists yet to verify. The `_format` tag stays `ds1_save_chunk`
until that data lands.

### What v0.7.0 does NOT ship

- **Per-field decode of the SAVE bodies**. Schema is unmapped
  beyond the structural shape above. Field discovery is a
  multi-session empirical RE thread that needs more played
  saves (and ideally the `repro v0.4.0` input automation to
  reproduce specific game states deterministically).
- **DS2 SAVE schema**. Same wire format suspected, no
  validation data yet.
- **`save-edit` write path**. That's v0.8.0; v0.7.0 is
  read-only.

---

## What v0.6.0 ships

**DS2 item sub-block validation, plus per-item `_format` tag.**
v0.5.0 closed the DS2 character schema; v0.6.0 closes the
last remaining DS2 sub-block. The good news: libgff's
`ds1_item_t` schema (which the existing `_decode_item` already
implements) is byte-for-byte the DS2 layout. v0.6.0 is the
validation pass and the `_format` plumbing that makes the
match explicit, not a decoder rewrite.

### Validation corpus

Three independent corpora, all clean:

| Corpus | Items | Size | `_format` | Truncations |
|---|---|---|---|---|
| DS1 played save (3-PC party, mid character creation) | 34 | 21 bytes | `ds1_item` | `priority` (expected; DS1 doesn't ship those bytes) |
| DS2 played save (`ds2-smoke --play` capture) | 151 | 23 bytes | `ds2_item` | **none** |
| DS2 factory `__support/save/CHARSAVE.GFF` | 151 | 23 bytes | `ds2_item` | **none** |

DS2 items hit every field through the trailing `priority` +
`data0` pair without a single short read. The "Not confirmed
at all" comment libgff carries on those two fields no longer
applies on the DS2 side (we now have 151 example points and
zero anomalies).

### Schema (DS2 23-byte item)

Same field layout as DS1; the extra 2 bytes at the tail are
the `priority` u16 + `data0` i8 that DS1 omits.

```json
"decoded": {
  "_format": "ds2_item",
  "id": -746,
  "quantity": 20,
  "next": 33,
  "value": 650,
  "pack_index": 9999,
  "item_index": 6,
  "icon": 0,
  "charges": 0,
  "special": 0,
  "slot": {"value": 0, "name": "ARM"},
  "name_idx": 6,
  "bonus": 1,
  "priority": 30,
  "data0": 2
}
```

DS1 records emit `"_format": "ds1_item"` and continue to read
through `bonus`, after which `_truncated_at: "priority"`
surfaces (this is the correct DS1 behaviour, not a decoder
gap).

### Bonus discovery: `DARKRUN.GFF` == `SAVE0N.SAV`

While the v0.6.0 fixtures landed, the save-slot system also
came into focus. When the user saves to a named slot, the
engine snapshots `DARKRUN.GFF` to `SAVE0N.SAV` byte-for-byte
(confirmed by SHA-256 match on both games' Wine installs after
a real save). Both files are standard GFF containers; the
existing save-inspect decoder reads `SAVE0N.SAV` directly with
no changes. Contents (~60 `SAVE` chunks, an `STXT` save-name
chunk, an `ETME` event-table-metadata chunk, plus DS1's
`ETAB` entity table) are now visible end-to-end.

### Out of scope (queued)

- A `SAVE` chunk decoder. Each region the player has visited
  emits a `SAVE` chunk inside `DARKRUN.GFF` / `SAVE0N.SAV`,
  and the format isn't decoded yet. That's a different
  schema RE thread; queued without a version target.

## What v0.5.0 ships

**DS2 character sub-block schema** (66 bytes). v0.4.0 fully
decoded DS2 combat but still emitted the character sub-block
as opaque hex. v0.5.0 closes that: every CHAR record in DS2
GOG 1.10's `CHARSAVE.GFF` now decodes with full `current_xp`,
`high_xp`, `base_hp`, `high_hp`, `base_psp`, `id`, `alignment`,
`stats`, `real_class`, `level`, AC, movement, saving throws,
and the trailing sound / palette fields.

The DS2 layout is **DS1's 72-byte layout minus 6 bytes**:
drops `_data2` (4 bytes) and two of `(race, gender, alignment)`
(2 bytes), keeping a single pre-stats byte that pattern-matches
DS1's `alignment` field. The remaining trailing 17 bytes
(saving throws, allegiance / size / spell-group, high-level,
sound-fx / attack-sound, psi-group, palette) match DS1's
layout one-for-one. The empirical fit was confirmed across
all 19 DS2 CHAR records: every stat in the 3..25 D&D 2e
range, every alignment in the documented 0..8 set, HP / PSP
matching the combat sub-block.

```json
"decoded": {
  "_format": "ds2_character",
  "current_xp": 122690,
  "high_xp": 122690,
  "base_hp": 81,
  "high_hp": 127,
  "base_psp": 144,
  "id": -32766,
  "_data1": "0007",
  "legal_class": 519,
  "alignment": {"value": 7, "name": "NEUTRAL_EVIL"},
  "stats": {"str": 20, "dex": 21, "con": 19, "intel": 20, "wis": 20, "cha": 17},
  "real_class": [12, 17, 16],
  "level": [8, 9, 7],
  "base_ac": 10,
  "base_move": 12,
  "magic_resistance": 0,
  "num_blows": 4,
  "num_attacks": [4, 0, 0],
  "num_dice": [1, 0, 0],
  "num_sides": [1, 0, 0],
  "num_bonuses": [0, 0, 0],
  "saving_throw": {"paralysis": 11, "wand": 10, "petrify": 10, "breath": 13, "spell": 11},
  "allegiance": 0,
  "size": 0,
  "spell_group": 8,
  "high_level": [9, 7, 67],
  "sound_fx": 0,
  "attack_sound": 0,
  "psi_group": 0,
  "palette": 0
}
```

What's open: the `alignment`-at-offset-20 identification is
empirical (it pattern-matches the byte position in DS1's
layout where alignment lives, and all observed values are
inside `ALIGNMENT_NAMES`). The byte could plausibly be a
`class_or_alignment` aggregate. DSUN.EXE RE of the
`SaveCharRec` analog would lock it down.

DS2 **item** sub-blocks are next; queued for v0.6.0.

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
