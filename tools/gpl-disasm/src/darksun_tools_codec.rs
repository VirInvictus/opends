//! Cross-check implementation of the GPL 7-bit packed string codec.
//!
//! Ported from TimQuester/DarkSunTools
//! `Common/Gpl/GplStringCodec.cs` (Apache-2.0; adoption credited in
//! `CREDITS.md`). DarkSunTools ships this codec as the translation
//! invariant behind its script editor: same character count implies
//! same encoded byte count, and no padding may follow the 0x03
//! terminator because the next instruction starts immediately after
//! it. This module is an *independent* implementation of the same
//! format our own decoder (`read_text`/`decode_compressed` in
//! `lib.rs`, soloscuro lineage) already handles; the corpus test in
//! `tests/string_codec_crosscheck.rs` runs both against every
//! candidate string in both games and asserts decode agreement plus
//! byte-exact re-encode, so a bug in either implementation shows up
//! as a corpus failure rather than a silent divergence.

/// The 0x03 terminator symbol, shared by both implementations.
pub const TERMINATOR: u8 = 0x03;

/// Safety cap shared with DarkSunTools' `MaxChars`: a payload that
/// runs this long without a terminator is treated as malformed
/// rather than scanned to chunk end.
pub const MAX_CHARS: usize = 300;

/// Minimal packed length, in bytes, for `char_count` characters.
/// `((n + 1) * 7 + 7) / 8`: seven bits per character plus the
/// terminator symbol, rounded up to whole bytes. `None` past the
/// safety cap.
pub fn packed_length(char_count: usize) -> Option<usize> {
    if char_count > MAX_CHARS {
        return None;
    }
    Some(((char_count + 1) * 7).div_ceil(8))
}

/// Decode the 7-bit packed payload starting at `content_start`.
/// Returns `(text, bytes_consumed)` where the consumed count runs
/// through the byte holding the terminator. `None` when the payload
/// starts outside `data`, exceeds [`MAX_CHARS`] characters, or runs
/// off the end without a terminator (the same shapes
/// `TryDecodeCompressed` rejects).
pub fn decode(data: &[u8], content_start: usize) -> Option<(String, usize)> {
    if content_start >= data.len() {
        return None;
    }
    let mut buffer: u16 = 0;
    let mut shift: u8 = 1;
    let mut pos = content_start;
    let mut chars: Vec<u8> = Vec::with_capacity(64);
    while pos < data.len() && chars.len() < MAX_CHARS {
        if shift > 0 {
            buffer = (((buffer << 8) as u32 | data[pos] as u32) & 0xFFFF) as u16;
            pos += 1;
        }
        let ch = ((buffer >> shift) & 0x7F) as u8;
        if ch == TERMINATOR {
            let text = chars.iter().map(|&b| b as char).collect();
            return Some((text, pos - content_start));
        }
        chars.push(ch);
        shift = (shift + 1) & 7;
    }
    None
}

/// Pack `text` into exactly [`packed_length`] bytes. `None` when any
/// character is outside the 7-bit symbol range or is the terminator
/// itself (DarkSunTools rejects both rather than silently corrupting
/// the instruction stream).
pub fn pack(text: &str) -> Option<Vec<u8>> {
    let mut buffer: u32 = 0;
    let mut bits: u8 = 0;
    let mut out = Vec::new();
    let mut put = |value: u8| -> Option<()> {
        if value > 0x7F {
            return None;
        }
        buffer = (buffer << 7) | value as u32;
        bits += 7;
        while bits >= 8 {
            bits -= 8;
            out.push(((buffer >> bits) & 0xFF) as u8);
            buffer &= (1 << bits) - 1;
        }
        Some(())
    };
    for c in text.chars() {
        let b = c as u32;
        if b > 0x7F || b == TERMINATOR as u32 {
            return None;
        }
        put(b as u8)?;
    }
    put(TERMINATOR)?;
    if bits > 0 {
        out.push((buffer << (8 - bits)) as u8);
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packed_length_matches_the_invariant() {
        // ((n+1)*7+7)/8, straight from the DarkSunTools doc comment.
        assert_eq!(packed_length(0), Some(1));
        assert_eq!(packed_length(1), Some(2));
        assert_eq!(packed_length(6), Some(7));
        assert_eq!(packed_length(300), Some(264));
        assert_eq!(packed_length(301), None);
    }

    #[test]
    fn pack_decode_round_trip() {
        // Decoded with one trailing context byte, the way the codec
        // always runs inside a chunk stream: a payload whose bit
        // count is an exact multiple of 8 ends its terminator
        // extraction on a non-consuming step, and the loop gate
        // (`pos < len`) still demands one more byte to be present.
        // Upstream C# has the same shape; the engine's chunk always
        // provides the continuation.
        for text in ["", "Hello!", "TYRGAR MINE LEVEL 1", "tab\tand\nnewline"] {
            let packed = pack(text).expect("pack");
            assert_eq!(packed.len(), packed_length(text.chars().count()).unwrap());
            let mut with_context = packed.clone();
            with_context.push(0x00);
            let (decoded, consumed) = decode(&with_context, 0).expect("decode");
            assert_eq!(decoded, text);
            assert_eq!(consumed, packed.len());
        }
    }

    #[test]
    fn pack_rejects_terminator_and_wide_chars() {
        assert_eq!(pack("\u{3}"), None);
        assert_eq!(pack("\u{80}"), None);
    }
}
