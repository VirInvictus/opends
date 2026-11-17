//! FONT chunk codec for SSI's Dark Sun CRPGs, plus the GPL
//! transliteration mapping used by fan translations.
//!
//! The FONT codec is a port of `TimQuester/DarkSunTools`
//! `Common/Font/FontResourceCodec.cs` (Apache-2.0; adoption credited
//! in the repo `CREDITS.md`). The layout was verified against the
//! corpus before the port: a 264-byte header whose byte +2 is the
//! glyph height (9 on the shipped fonts), 256 u16 LE glyph offsets
//! starting at 264, and each glyph a u16 LE width followed by
//! width x height raw pixel bytes. The offset table is strictly
//! increasing and the last glyph runs to chunk end, so the chunk
//! length validates the final width. The header is kept opaque
//! exactly as upstream keeps it: only byte +2 is interpreted.
//!
//! The transliteration module ports
//! `Common/Gpl/GplTransliteration.cs` (same license): display-to-
//! game character mapping for fan translations. GPL strings are
//! 7-bit, so translated text must be stored as the ASCII glyph
//! codes whose bitmaps the FONT resource replaced. Only 1:1 rules
//! apply; multi-character replacements would change the string
//! length and GPL string spans are fixed-length. The bundled
//! Cyrillic rules are upstream's committed mapping
//! (`FontTool/CyrillicOutput/cyrillic_rules.txt`), redistributed
//! under Apache-2.0.

use thiserror::Error;

pub mod translit;

pub const GLYPH_COUNT: usize = 256;
pub const GLYPH_HEIGHT: usize = 9;
pub const OFFSET_TABLE_START: usize = 264;
pub const GLYPH_DATA_START: usize = OFFSET_TABLE_START + GLYPH_COUNT * 2;

/// One glyph: its character code (0..255, the index in the offset
/// table), pixel width, and `width x height` raw pixel bytes
/// (row-major, one byte per pixel).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FontGlyph {
    pub code: usize,
    pub width: usize,
    /// Row-major pixels, `width * GLYPH_HEIGHT` bytes.
    pub pixels: Vec<u8>,
}

/// A parsed FONT resource: the opaque 776-byte header and the 256
/// glyphs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FontResource {
    pub header: Vec<u8>,
    pub glyphs: Vec<FontGlyph>,
}

#[derive(Debug, Error)]
pub enum FontError {
    #[error("FONT resource is truncated: expected at least {expected} bytes, got {got}")]
    Truncated { expected: usize, got: usize },
    #[error("unsupported FONT glyph height {got}; expected {expected}")]
    BadHeight { got: u8, expected: u8 },
    #[error("FONT glyph {glyph} has an invalid offset {offset}")]
    BadOffset { glyph: usize, offset: usize },
    #[error("FONT glyph offsets are not strictly increasing at glyph {glyph}")]
    NotIncreasing { glyph: usize },
    #[error("FONT glyph {glyph} has {got} bytes, but width {width} requires {expected}")]
    BadGlyphLength {
        glyph: usize,
        got: usize,
        width: usize,
        expected: usize,
    },
    #[error("FONT header must contain exactly {expected} bytes, got {got}")]
    BadHeader { expected: usize, got: usize },
    #[error("FONT requires exactly {expected} glyphs, got {got}")]
    BadGlyphCount { expected: usize, got: usize },
    #[error("FONT glyph codes must uniquely cover the range 0 through {max}")]
    BadCodeCoverage { max: usize },
    #[error("FONT glyph {glyph} pixel dimensions do not match its width {width}")]
    BadPixelDims { glyph: usize, width: usize },
    #[error("FONT glyph data exceeds the 16-bit offset table capacity")]
    Oversize,
}

/// Parse a FONT chunk body. Mirrors upstream `Parse`'s validation:
/// length, header height byte, offset range and strict increase,
/// and each glyph's byte count against its declared width.
pub fn parse(data: &[u8]) -> Result<FontResource, FontError> {
    if data.len() < GLYPH_DATA_START {
        return Err(FontError::Truncated {
            expected: GLYPH_DATA_START,
            got: data.len(),
        });
    }
    if data[2] != GLYPH_HEIGHT as u8 {
        return Err(FontError::BadHeight {
            got: data[2],
            expected: GLYPH_HEIGHT as u8,
        });
    }

    let mut offsets = [0usize; GLYPH_COUNT];
    for i in 0..GLYPH_COUNT {
        let at = OFFSET_TABLE_START + i * 2;
        let offset = u16::from_le_bytes([data[at], data[at + 1]]) as usize;
        if offset < GLYPH_DATA_START || offset > data.len().saturating_sub(2) {
            return Err(FontError::BadOffset { glyph: i, offset });
        }
        if i > 0 && offset <= offsets[i - 1] {
            return Err(FontError::NotIncreasing { glyph: i });
        }
        offsets[i] = offset;
    }

    let mut glyphs = Vec::with_capacity(GLYPH_COUNT);
    for (i, &start) in offsets.iter().enumerate() {
        let end = if i + 1 < GLYPH_COUNT {
            offsets[i + 1]
        } else {
            data.len()
        };
        let width = u16::from_le_bytes([data[start], data[start + 1]]) as usize;
        let expected = 2 + width * GLYPH_HEIGHT;
        if end - start != expected {
            return Err(FontError::BadGlyphLength {
                glyph: i,
                got: end - start,
                width,
                expected,
            });
        }
        let mut pixels = Vec::with_capacity(width * GLYPH_HEIGHT);
        for y in 0..GLYPH_HEIGHT {
            for x in 0..width {
                pixels.push(data[start + 2 + y * width + x]);
            }
        }
        glyphs.push(FontGlyph {
            code: i,
            width,
            pixels,
        });
    }

    Ok(FontResource {
        header: data[..GLYPH_DATA_START].to_vec(),
        glyphs,
    })
}

/// Build FONT chunk bytes. Mirrors upstream `Build`'s validation:
/// exact header size, exactly 256 uniquely-coded glyphs with
/// matching pixel dimensions, and the 16-bit offset ceiling.
pub fn build(font: &FontResource) -> Result<Vec<u8>, FontError> {
    if font.header.len() != GLYPH_DATA_START {
        return Err(FontError::BadHeader {
            expected: GLYPH_DATA_START,
            got: font.header.len(),
        });
    }
    if font.glyphs.len() != GLYPH_COUNT {
        return Err(FontError::BadGlyphCount {
            expected: GLYPH_COUNT,
            got: font.glyphs.len(),
        });
    }

    let mut glyphs: Vec<Option<&FontGlyph>> = vec![None; GLYPH_COUNT];
    for glyph in &font.glyphs {
        if glyph.code >= GLYPH_COUNT || glyphs[glyph.code].is_some() {
            return Err(FontError::BadCodeCoverage {
                max: GLYPH_COUNT - 1,
            });
        }
        if glyph.pixels.len() != glyph.width * GLYPH_HEIGHT {
            return Err(FontError::BadPixelDims {
                glyph: glyph.code,
                width: glyph.width,
            });
        }
        glyphs[glyph.code] = Some(glyph);
    }
    if glyphs.iter().any(Option::is_none) {
        return Err(FontError::BadCodeCoverage {
            max: GLYPH_COUNT - 1,
        });
    }

    let mut header = font.header.clone();
    let mut offset = GLYPH_DATA_START;
    for (i, slot) in glyphs.iter().enumerate() {
        let glyph = slot.as_ref().expect("coverage checked above");
        if offset > u16::MAX as usize {
            return Err(FontError::Oversize);
        }
        header[OFFSET_TABLE_START + i * 2..OFFSET_TABLE_START + i * 2 + 2]
            .copy_from_slice(&(offset as u16).to_le_bytes());
        offset += 2 + glyph.width * GLYPH_HEIGHT;
    }

    let mut out = header;
    for glyph in glyphs.iter().flatten() {
        out.extend_from_slice(&(glyph.width as u16).to_le_bytes());
        out.extend_from_slice(&glyph.pixels);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A synthetic font with a few distinct glyphs.
    fn synth() -> FontResource {
        let mut header = vec![0u8; GLYPH_DATA_START];
        header[2] = GLYPH_HEIGHT as u8;
        let mut glyphs = Vec::new();
        for code in 0..GLYPH_COUNT {
            let width = 1 + code % 7;
            let pixels: Vec<u8> = (0..width * GLYPH_HEIGHT)
                .map(|i| ((code + i) % 256) as u8)
                .collect();
            glyphs.push(FontGlyph {
                code,
                width,
                pixels,
            });
        }
        FontResource { header, glyphs }
    }

    #[test]
    fn synthetic_round_trip() {
        // The byte-level contract: build -> parse -> build is
        // stable, and parse recovers exactly the glyphs that went
        // in. (The parsed header carries the computed offset table,
        // so it only equals the input header when that table was
        // already consistent -- the corpus test pins byte identity
        // on real fonts whose tables are.)
        let font = synth();
        let bytes = build(&font).expect("build");
        let parsed = parse(&bytes).expect("parse");
        assert_eq!(parsed.glyphs, font.glyphs);
        let bytes2 = build(&parsed).expect("rebuild");
        assert_eq!(bytes2, bytes);
    }

    #[test]
    fn header_height_is_enforced() {
        let mut font = synth();
        font.header[2] = 8;
        let err = build(&font).err();
        // Build itself doesn't read the height byte; parse does.
        assert!(err.is_none());
        let bytes = build(&font).unwrap();
        assert!(matches!(
            parse(&bytes),
            Err(FontError::BadHeight {
                got: 8,
                expected: 9
            })
        ));
    }

    #[test]
    fn parse_refuses_non_increasing_offsets() {
        let mut bytes = build(&synth()).unwrap();
        // Glyph 1's offset := glyph 0's offset (not strictly greater).
        let at = OFFSET_TABLE_START + 2;
        let prev = u16::from_le_bytes([bytes[at - 2], bytes[at - 1]]);
        bytes[at..at + 2].copy_from_slice(&prev.to_le_bytes());
        assert!(matches!(
            parse(&bytes),
            Err(FontError::NotIncreasing { glyph: 1 })
        ));
    }

    #[test]
    fn parse_refuses_truncated_chunk() {
        let bytes = build(&synth()).unwrap();
        assert!(matches!(
            parse(&bytes[..GLYPH_DATA_START - 1]),
            Err(FontError::Truncated { .. })
        ));
    }

    #[test]
    fn build_refuses_wrong_glyph_count() {
        let mut font = synth();
        font.glyphs.pop();
        assert!(matches!(
            build(&font),
            Err(FontError::BadGlyphCount {
                expected: 256,
                got: 255
            })
        ));
    }

    #[test]
    fn build_refuses_duplicate_codes() {
        let mut font = synth();
        font.glyphs[1].code = 0;
        assert!(matches!(
            build(&font),
            Err(FontError::BadCodeCoverage { max: 255 })
        ));
    }

    #[test]
    fn build_refuses_bad_pixel_dims() {
        let mut font = synth();
        font.glyphs[3].pixels.pop();
        assert!(matches!(
            build(&font),
            Err(FontError::BadPixelDims { glyph: 3, .. })
        ));
    }
}
