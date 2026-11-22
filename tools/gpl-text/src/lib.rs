//! Fixed-length GPL string editing: the validate/apply layer behind
//! the `gpl-text` tool.
//!
//! The design ports `TimQuester/DarkSunTools`
//! `DarkSunRE/Models/GPLDocument.cs` (Apache-2.0; credited in the
//! repo `CREDITS.md`): GPL strings are inline in the instruction
//! stream, so an edit may only change characters -- same character
//! count implies the same packed byte count, no padding may follow
//! the terminator, and only 7-bit symbols are representable. The
//! layer here tracks every string operand's packed span (chunk byte
//! offset + payload length), validates a replacement against those
//! rules, and splices the repacked payload in place. Length
//! changes are refused by design; a length-changing edit is a
//! gpl-asm job (see `docs/reference/detour-repairs.md`), not a string edit.

use gpl_disasm::{StringSubType, parse_string_operand_spans};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum TextEditError {
    #[error("string index {index} out of range (chunk carries {count})")]
    IndexOutOfRange { index: usize, count: usize },
    #[error(
        "replacement must have exactly {expected} characters to keep the packed length at {packed_len} bytes, got {got}"
    )]
    LengthMismatch {
        index: usize,
        expected: usize,
        packed_len: usize,
        got: usize,
    },
    #[error("string {index}: replacement carries a non-7-bit character {chars:?}")]
    NonSevenBit { index: usize, chars: Vec<char> },
    #[error("string {index}: replacement carries the 0x03 terminator")]
    TerminatorChar { index: usize },
    #[error("string {index}: this operand ({sub_type:?}) is not editable")]
    NotEditable {
        index: usize,
        sub_type: StringSubType,
    },
    #[error("chunk is not aligned ({unaligned_reason}); string spans need aligned instructions")]
    Unaligned { unaligned_reason: String },
}

/// One editable string operand and its exact location in the chunk.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StringSpan {
    /// Operand index in disassembly order.
    pub index: usize,
    /// Byte offset of the packed payload (just past the sub-type
    /// marker) inside the chunk.
    pub payload_offset: usize,
    /// Packed payload length in bytes (through the terminator).
    pub packed_len: usize,
    pub sub_type: StringSubType,
    /// The decoded text as the tools render it.
    pub text: String,
}

/// Collect the string spans of a chunk. Uses gpl-disasm's span
/// walker, which reports each string operand's payload offset and
/// packed length for aligned instructions; best-effort instructions
/// (menus and other custom handlers) make the chunk's spans
/// incomplete, so the walk refuses them rather than mislocating
/// edits.
pub fn collect_spans(chunk: &[u8]) -> Result<(Vec<StringSpan>, Option<String>), TextEditError> {
    let (spans, warning) = parse_string_operand_spans(chunk);
    let spans = spans
        .into_iter()
        .map(
            |(index, payload_offset, packed_len, sub_type, text)| StringSpan {
                index,
                payload_offset,
                packed_len,
                sub_type,
                text,
            },
        )
        .collect();
    Ok((spans, warning))
}

/// Validate a replacement against the fixed-length rules. Returns
/// the packed replacement bytes on success.
pub fn validate_replacement(
    span: &StringSpan,
    replacement: &str,
) -> Result<Vec<u8>, TextEditError> {
    if span.sub_type != StringSubType::Compressed && span.sub_type != StringSubType::Uncompressed {
        return Err(TextEditError::NotEditable {
            index: span.index,
            sub_type: span.sub_type,
        });
    }
    let chars: Vec<char> = replacement.chars().collect();
    if span.sub_type == StringSubType::Compressed {
        let non_ascii: Vec<char> = chars.iter().copied().filter(|c| *c > '\x7f').collect();
        if let Some(bad) = non_ascii.first().copied() {
            return Err(TextEditError::NonSevenBit {
                index: span.index,
                chars: vec![bad],
            });
        }
        if chars.contains(&'\x03') {
            return Err(TextEditError::TerminatorChar { index: span.index });
        }
    }
    if chars.len() != span.text.chars().count() {
        return Err(TextEditError::LengthMismatch {
            index: span.index,
            expected: span.text.chars().count(),
            packed_len: span.packed_len,
            got: chars.len(),
        });
    }
    Ok(repack(span, replacement))
}

/// Repack the replacement payload. The compressed form packs chars
/// plus the 0x03 terminator into exactly `packed_len` bytes; the
/// uncompressed form stores each char rotated right 2 plus the 0xC0
/// terminator.
fn repack(span: &StringSpan, replacement: &str) -> Vec<u8> {
    let mut out = Vec::with_capacity(span.packed_len);
    match span.sub_type {
        StringSubType::Uncompressed => {
            for c in replacement.chars() {
                out.push((c as u8).rotate_right(2));
            }
            out.push(gpl_disasm::STRING_UNCOMPRESSED_TERMINATOR);
        }
        _ => {
            // The same packer gpl-asm uses for corpus round trips.
            let mut buffer: u32 = 0;
            let mut bits: u32 = 0;
            let push7 = |out: &mut Vec<u8>, buffer: &mut u32, bits: &mut u32, v: u8| {
                *buffer = (*buffer << 7) | (v as u32 & 0x7F);
                *bits += 7;
                while *bits >= 8 {
                    *bits -= 8;
                    out.push(((*buffer >> *bits) & 0xFF) as u8);
                    *buffer &= (1u32 << *bits) - 1;
                }
            };
            for c in replacement.chars() {
                push7(&mut out, &mut buffer, &mut bits, c as u8);
            }
            push7(&mut out, &mut buffer, &mut bits, 0x03);
            if bits > 0 {
                out.push(((buffer << (8 - bits)) & 0xFF) as u8);
            }
        }
    }
    out
}

/// Apply a validated replacement: splice the packed bytes into the
/// chunk and return the patched chunk. Callers re-verify the
/// result (disassemble + compare) before writing.
pub fn apply(chunk: &[u8], span: &StringSpan, replacement_bytes: &[u8]) -> Vec<u8> {
    let mut out = chunk.to_vec();
    out[span.payload_offset..span.payload_offset + span.packed_len]
        .copy_from_slice(replacement_bytes);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use gpl_disasm::disassemble;

    /// A synthetic chunk: `gpl print string 115, "Hi"` packed.
    fn synth_chunk(text: &str) -> Vec<u8> {
        let mut chunk = vec![0x4F];
        chunk.push(0x8F);
        chunk.push(115);
        let mut buffer: u32 = 0;
        let mut bits: u32 = 0;
        let put = |chunk: &mut Vec<u8>, buffer: &mut u32, bits: &mut u32, v: u8| {
            *buffer = (*buffer << 7) | (v as u32 & 0x7F);
            *bits += 7;
            while *bits >= 8 {
                *bits -= 8;
                chunk.push(((*buffer >> *bits) & 0xFF) as u8);
                *buffer &= (1 << *bits) - 1;
            }
        };
        chunk.push(0x92);
        chunk.push(0x05);
        for c in text.bytes() {
            put(&mut chunk, &mut buffer, &mut bits, c);
        }
        put(&mut chunk, &mut buffer, &mut bits, 0x03);
        if bits > 0 {
            chunk.push(((buffer << (8 - bits)) & 0xFF) as u8);
        }
        chunk.push(0x67);
        chunk
    }

    #[test]
    fn collect_and_edit_round_trip() {
        let chunk = synth_chunk("Hi");
        let (spans, _warn) = collect_spans(&chunk).expect("spans");
        assert_eq!(spans.len(), 1);
        assert_eq!(spans[0].text, "Hi");

        let replacement = validate_replacement(&spans[0], "Jo").expect("validate");
        let patched = apply(&chunk, &spans[0], &replacement);
        let (spans2, _warn) = collect_spans(&patched).expect("spans after");
        assert_eq!(spans2[0].text, "Jo");
        // Same length by construction: the chunk size never moves.
        assert_eq!(patched.len(), chunk.len());
    }

    #[test]
    fn length_change_is_refused() {
        let chunk = synth_chunk("Hi");
        let (spans, _warn) = collect_spans(&chunk).unwrap();
        let err = validate_replacement(&spans[0], "Too long").unwrap_err();
        assert!(matches!(
            err,
            TextEditError::LengthMismatch {
                expected: 2,
                got: 8,
                ..
            }
        ));
    }

    #[test]
    fn eight_bit_replacement_is_refused() {
        let chunk = synth_chunk("Hi");
        let (spans, _warn) = collect_spans(&chunk).unwrap();
        let err = validate_replacement(&spans[0], "Hé").unwrap_err();
        assert!(matches!(err, TextEditError::NonSevenBit { .. }));
    }

    #[test]
    fn terminator_character_is_refused() {
        let chunk = synth_chunk("Hi");
        let (spans, _warn) = collect_spans(&chunk).unwrap();
        let err = validate_replacement(&spans[0], "\u{3}i").unwrap_err();
        assert!(matches!(err, TextEditError::TerminatorChar { .. }));
    }

    #[test]
    fn disassembler_reads_the_patched_chunk() {
        let chunk = synth_chunk("Hi");
        let (spans, _warn) = collect_spans(&chunk).unwrap();
        let replacement = validate_replacement(&spans[0], "Jo").unwrap();
        let patched = apply(&chunk, &spans[0], &replacement);
        let result = disassemble(&patched);
        assert!(result.aligned);
        let rendered = format!("{}", result.instructions[0]);
        assert!(rendered.contains("\"Jo\""), "{rendered}");
    }
}
