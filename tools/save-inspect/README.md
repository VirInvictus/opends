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

## What v0.1.0 decodes

`CHARSAVE.GFF` ships seven chunk types (DS1) or eight (DS2).
v0.1.0 covers them as follows:

| Chunk | Decoded as | Source |
|-------|------------|--------|
| `CHAR` | `gff_rdff_header_t` (10 bytes) + opaque hex preview | libgff `include/gff/rdff.h` |
| `PSIN` | 7-element `types[]` array (psionic disciplines) | libgff `include/gff/psionic.h` |
| `PSST` | 34-element `psionics[]` array (psionic mastery) | libgff `include/gff/psionic.h` |
| `SPST` | hex preview (spell-list bitmask; bit layout TBD) | libgff (TBD) |
| `CACT` | hex preview (valid character ID flags; TBD) | libgff (TBD) |
| `TEXT` | plain ASCII (CRLF normalised to `\n` in JSON) | OpenDS `docs/file-formats.md` |
| `PREF` | hex preview (user preferences; TBD) | TBD |
| `GREQ` | hex preview (DS2-only; group/quest? TBD) | TBD |

CHAR records carry full character data (stats, inventory, spells
slotted) in their opaque `data[]` field, but the record schema
differs between DS1 and DS2 per `docs/file-formats.md` §2.
Decoding that requires per-game RDFF schemas, which is v0.2.0
research; v0.1.0 just hands you the header + raw bytes for
manual inspection.

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
