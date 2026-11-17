# font-extract

FONT chunk codec for *Dark Sun: Shattered Lands* and *Wake of the
Ravager*: extract the game's bitmap fonts into editable glyph PNGs,
pack edited glyphs back byte-exactly, and preview translated text
through a transliteration mapping.

Part of the [OpenDS](../../README.md) community toolkit. The codec
is a port of TimQuester's DarkSunTools `FontResourceCodec` and
`GplTransliteration` (Apache-2.0; credited in
[`../../CREDITS.md`](../../CREDITS.md)), with the format facts
verified against the shipped corpus.

## The format

A FONT chunk (both games ship `RESOURCE.GFF` FONT 100, 8,299
bytes) is a 264-byte header whose byte +2 is the glyph height (9),
256 u16 LE glyph offsets starting at 264, then per glyph a u16 LE
width followed by `width x height` raw pixel bytes. The offset
table is strictly increasing; the last glyph runs to chunk end.
Zero-width glyphs are legal (a 2-byte entry holding only the
width). The header outside the height byte and the offset table is
carried opaquely, exactly as upstream treats it.

## Usage

Extract (writes `glyphs/*.png`, `manifest.json` with the per-glyph
widths, and a `preview.png` grid of all 256 glyphs):

```sh
font-extract /path/to/RESOURCE.GFF --output font-out
```

Preview translated text through a transliteration rules file
(`data/cyrillic_rules.txt` ships with the tool; the rules map game
glyph codes to the characters they display, and rendering walks the
reverse direction):

```sh
font-extract /path/to/RESOURCE.GFF --output font-out \
  --render-text "ТЕСТ ТРАНСЛИТ" --rules data/cyrillic_rules.txt
```

Edit the glyph PNGs (any 8-bit grayscale editor), then verify and
write back:

```sh
font-pack font-out /path/to/RESOURCE.GFF          # verify round-trip
font-pack font-out /path/to/RESOURCE.GFF --write  # replace the chunk
```

`font-pack` refuses to write anything until the packed chunk
matches expectations, and glyph edits must keep each glyph's width
(as recorded in `manifest.json`) so the chunk stays the same size
and lands in place. The header is never edited: it is carried over
from the shipped chunk.

## Tests

```sh
cargo test -p font-extract
```

Unit tests cover the codec's validation refusals and the
transliteration mapping; the corpus test pins both shipped FONT 100
chunks (DS1 and DS2) through parse -> build byte-identically
(skips when `.games/` is absent).
