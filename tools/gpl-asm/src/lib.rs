//! gpl-asm: reassembler for SSI's GPL bytecode (Dark Sun).
//!
//! v0.1.0 ships the **round-trip reassembler**: takes a
//! [`DisasmResult`] (produced by `gpl-disasm`) and emits
//! byte-identical bytecode. The load-bearing test is the
//! same shape as `gff-edit`'s writer: every aligned GPL/MAS
//! chunk in DS1+DS2 round-trips byte-for-byte through
//! `disassemble -> encode`.
//!
//! Text-input parsing, structural edits (insert/delete with
//! label re-resolution), and a higher-level authoring DSL roll
//! into later versions; v0.1.0 is the encoder foundation.
//!
//! Ports the inverse of every decoder case in `gpl-disasm`'s
//! `src/lib.rs`: high-bit dispatch, 14-bit immediates, byte /
//! bignum / name / string immediates (the 7-bit packed encoder
//! is in `pack_compressed_string` below), variable encoding
//! with `EXTENDED_VAR`, infix operators, parens,
//! `gpl_access_complex` blocks, nested `GPL_RETVAL`, and the
//! special-shape opcodes (`gpl_menu`, `gpl_setrecord`,
//! `gpl_load_variable`).
//!
//! Out of scope for v0.1.0: `ParamSpec::Search` (0x33; 0
//! occurrences in DS1, 2 in DS2 — chunks containing them are
//! flagged unencodable rather than handled), `best_effort`
//! instructions (their params may not faithfully reproduce
//! the source).

use gpl_disasm::{
    DisasmResult, EXTENDED_VAR, Expression, GPL_ACCM, GPL_COMPLEX_LOW, GPL_HI_CLOSE_PAREN,
    GPL_HI_OPEN_PAREN, GPL_IMMED_BIGNUM, GPL_IMMED_BYTE, GPL_IMMED_NAME, GPL_IMMED_STRING,
    GPL_IMMED_WORD, GPL_RETVAL, Instruction, MAX_KNOWN_OPCODE, PARAM_COUNTS, ParamSpec,
    STRING_COMPRESSED, STRING_INTRODUCE, STRING_TERMINATOR, STRING_UNCOMPRESSED, StringSubType,
};
use thiserror::Error;

pub mod parse;
pub use parse::{ParseError, error_line, error_span, format_with_caret, parse};

pub mod edit;
pub use edit::{EditError, Editor, can_edit_opcode, retarget_branches};

pub mod validate;
pub use validate::{ValidationError, ValidationReport, validate};

#[derive(Debug, Error)]
pub enum EncodeError {
    #[error("instruction at offset {offset} (opcode 0x{opcode:02x}) is best-effort; encoder cannot reproduce its bytes faithfully")]
    BestEffortInstruction { offset: usize, opcode: u8 },
    #[error("instruction at offset {offset} uses unsupported opcode 0x{opcode:02x} ({reason})")]
    UnsupportedOpcode {
        offset: usize,
        opcode: u8,
        reason: &'static str,
    },
    #[error("instruction at offset {offset} (opcode 0x{opcode:02x}): param[{param_index}] shape doesn't match opcode's expected layout: {detail}")]
    BadParamShape {
        offset: usize,
        opcode: u8,
        param_index: usize,
        detail: &'static str,
    },
    #[error("Unknown token encountered in instruction at offset {offset}; the source disassembly bailed mid-parse")]
    UnknownToken { offset: usize },
    #[error("encoded output is {actual} bytes but DisasmResult reported {expected}")]
    LengthMismatch { expected: usize, actual: usize },
}

pub type Result<T> = std::result::Result<T, EncodeError>;

/// Re-encode an aligned [`DisasmResult`] to bytes.
///
/// Returns [`EncodeError::BestEffortInstruction`] for any chunk
/// that contains a best-effort instruction: those have lossy
/// param data and re-encoding would silently produce different
/// bytes than the source.
pub fn encode(result: &DisasmResult) -> Result<Vec<u8>> {
    let mut out = Vec::with_capacity(result.total_bytes);
    for instr in &result.instructions {
        encode_instruction(&mut out, instr)?;
    }
    // The length sanity-check used to be a hard error here, but
    // it makes the encoder over-strict for inputs whose
    // `total_bytes` field comes from a downstream consumer
    // (e.g. the v0.2.0 text parser, which can only estimate the
    // length until it actually encodes). Verification at the
    // corpus-roundtrip level (`encoded == source_bytes`) catches
    // real encoder bugs; this check was redundant.
    if result.total_bytes > 0 && out.len() != result.total_bytes {
        // Honest debug-time signal without rejecting valid output.
        debug_assert_eq!(
            out.len(),
            result.total_bytes,
            "DisasmResult.total_bytes does not match encoded length",
        );
    }
    Ok(out)
}

/// Append one instruction's bytes to `out`.
pub fn encode_instruction(out: &mut Vec<u8>, instr: &Instruction) -> Result<()> {
    if instr.best_effort {
        return Err(EncodeError::BestEffortInstruction {
            offset: instr.offset,
            opcode: instr.opcode,
        });
    }
    out.push(instr.opcode);
    let spec = if (instr.opcode as usize) <= MAX_KNOWN_OPCODE as usize {
        PARAM_COUNTS[instr.opcode as usize]
    } else {
        ParamSpec::Custom
    };
    match spec {
        ParamSpec::None => {}
        ParamSpec::Fixed(n) => {
            if instr.params.len() != n as usize {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 0,
                    detail: "fixed-param count mismatch",
                });
            }
            for param in &instr.params {
                encode_param(out, instr.offset, param)?;
            }
        }
        ParamSpec::Log => {
            // 1 packed-string payload (no marker/wrapper byte before
            // the sub-type marker; the sub-type byte itself is the
            // marker, written by encode_packed_string_inline).
            if instr.params.len() != 1 || instr.params[0].len() != 1 {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 0,
                    detail: "gpl_log expects a single immediate_string param",
                });
            }
            match &instr.params[0][0] {
                Expression::ImmediateString { sub_type, value } => {
                    encode_string_payload(out, *sub_type, value);
                }
                _ => {
                    return Err(EncodeError::BadParamShape {
                        offset: instr.offset,
                        opcode: instr.opcode,
                        param_index: 0,
                        detail: "gpl_log param 0 must be ImmediateString",
                    });
                }
            }
        }
        ParamSpec::LoadVar => {
            // gpl_load_variable: load_accum (1 expression) +
            // datatype byte + (simple-var id-bytes | access_complex).
            if instr.params.len() != 2 {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 0,
                    detail: "gpl_load_variable expects 2 params",
                });
            }
            encode_param(out, instr.offset, &instr.params[0])?;
            // param[1] is either Variable (simple) or ComplexAccess
            // (record-field write).
            let target = &instr.params[1];
            if target.len() != 1 {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 1,
                    detail: "gpl_load_variable param 1 must be a single token",
                });
            }
            match &target[0] {
                Expression::Variable {
                    var_kind,
                    id,
                    extended,
                } => {
                    let datatype = var_kind.to_tag() | if *extended { EXTENDED_VAR } else { 0 };
                    // Match libgff convention: high bit set on the
                    // datatype byte (consistent with corpus encoding).
                    out.push(datatype | 0x80);
                    encode_var_id(out, *id, *extended);
                }
                Expression::ComplexAccess {
                    tag,
                    obj_name,
                    depth,
                    elements,
                } => {
                    out.push(*tag | 0x80);
                    encode_complex_body(out, *obj_name, *depth, elements);
                }
                _ => {
                    return Err(EncodeError::BadParamShape {
                        offset: instr.offset,
                        opcode: instr.opcode,
                        param_index: 1,
                        detail: "gpl_load_variable param 1 must be Variable or ComplexAccess",
                    });
                }
            }
        }
        ParamSpec::Menu => {
            // gpl_menu: 1 expression (menu name) followed by 3-expression
            // entries, terminated by byte 0x4A.
            if instr.params.is_empty() {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 0,
                    detail: "gpl_menu needs at least the name param",
                });
            }
            for param in &instr.params {
                encode_param(out, instr.offset, param)?;
            }
            out.push(0x4A);
        }
        ParamSpec::SetRecord => {
            // gpl_setrecord: access_complex + 1 expression.
            if instr.params.len() != 2 {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 0,
                    detail: "gpl_setrecord expects 2 params",
                });
            }
            if instr.params[0].len() != 1 {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 0,
                    detail: "gpl_setrecord param 0 must be a single ComplexAccess token",
                });
            }
            match &instr.params[0][0] {
                Expression::ComplexAccess {
                    obj_name,
                    depth,
                    elements,
                    ..
                } => {
                    // SetRecord doesn't write a leading dispatch byte;
                    // the access_complex body is read raw after the
                    // opcode (per the decoder's ParamSpec::SetRecord
                    // case at lib.rs ~1729).
                    encode_complex_body(out, *obj_name, *depth, elements);
                }
                _ => {
                    return Err(EncodeError::BadParamShape {
                        offset: instr.offset,
                        opcode: instr.opcode,
                        param_index: 0,
                        detail: "gpl_setrecord param 0 must be ComplexAccess",
                    });
                }
            }
            encode_param(out, instr.offset, &instr.params[1])?;
        }
        ParamSpec::Search => {
            // gpl_search: param[0] is the search target, captured as
            // a normal expression. The remaining side bytes (2-byte
            // range argument + per-iteration optional-0x53 + field +
            // type markers + any conditional trailing expressions)
            // live in `raw_tail`. Encode param[0] then append
            // raw_tail verbatim.
            if instr.params.is_empty() {
                return Err(EncodeError::BadParamShape {
                    offset: instr.offset,
                    opcode: instr.opcode,
                    param_index: 0,
                    detail: "gpl_search expects at least the target param",
                });
            }
            encode_param(out, instr.offset, &instr.params[0])?;
            match &instr.raw_tail {
                Some(tail) => out.extend_from_slice(tail),
                None => {
                    return Err(EncodeError::UnsupportedOpcode {
                        offset: instr.offset,
                        opcode: instr.opcode,
                        reason: "gpl_search instruction has no raw_tail; needs gpl-disasm v0.4.5+",
                    });
                }
            }
        }
        ParamSpec::Custom => {
            return Err(EncodeError::UnsupportedOpcode {
                offset: instr.offset,
                opcode: instr.opcode,
                reason: "Custom-shape opcodes are not modelled by v0.1.0",
            });
        }
    }
    Ok(())
}

/// Encode one parameter (a sequence of [`Expression`] tokens).
fn encode_param(out: &mut Vec<u8>, instr_offset: usize, tokens: &[Expression]) -> Result<()> {
    for tok in tokens {
        encode_expression(out, instr_offset, tok)?;
    }
    Ok(())
}

/// Encode a single [`Expression`] token. Inverse of the body of
/// `read_expression_with_depth` in `gpl-disasm`'s lib.rs.
pub fn encode_expression(out: &mut Vec<u8>, instr_offset: usize, expr: &Expression) -> Result<()> {
    match expr {
        Expression::Immediate14 { value } => {
            // Two bytes: high (< 0x80) then low. Reconstruct from
            // value such that ((hi << 8) | lo) == value.
            // libgff's range: cop < 0x80 => 14-bit. So hi MUST be < 0x80.
            let hi = (value >> 8) as u8;
            let lo = (value & 0xFF) as u8;
            // Defensive: top bit of hi must be 0 for this to round-trip.
            debug_assert!(hi < 0x80, "Immediate14 value {value:#x} has hi >= 0x80");
            out.push(hi);
            out.push(lo);
        }
        Expression::ImmediateByte { value } => {
            out.push(GPL_IMMED_BYTE | 0x80);
            out.push(*value as u8);
        }
        Expression::ImmediateBigNum { value } => {
            out.push(GPL_IMMED_BIGNUM | 0x80);
            // libgff decoder: cval = ((hi << 16) | lo_zero_extended)
            // where hi = ((bytes[0] << 8) | bytes[1]) as u16
            // and lo = ((bytes[2] << 8) | bytes[3]) as u16.
            // Inverse: split value into hi (top 16 bits, signed) and
            // lo (bottom 16 bits, unsigned).
            let hi = ((*value as i32 >> 16) as u16).to_be_bytes();
            let lo = (*value as u32 & 0xFFFF) as u16;
            let lo = lo.to_be_bytes();
            out.extend_from_slice(&hi);
            out.extend_from_slice(&lo);
        }
        Expression::ImmediateName { value } => {
            out.push(GPL_IMMED_NAME | 0x80);
            // libgff decoder: cval = -(h as i32) where h = u16 BE.
            // Inverse: h = (-value) as u16.
            let h: u16 = (-(*value)) as u16;
            out.extend_from_slice(&h.to_be_bytes());
        }
        Expression::ImmediateString { sub_type, value } => {
            out.push(GPL_IMMED_STRING | 0x80);
            encode_string_payload(out, *sub_type, value);
        }
        Expression::Variable {
            var_kind,
            id,
            extended,
        } => {
            let dispatch = var_kind.to_tag() | if *extended { EXTENDED_VAR } else { 0 } | 0x80;
            out.push(dispatch);
            encode_var_id(out, *id, *extended);
        }
        Expression::BinaryOp { op } => {
            out.push(op.to_byte());
        }
        Expression::OpenParen => {
            out.push(GPL_HI_OPEN_PAREN);
        }
        Expression::CloseParen => {
            out.push(GPL_HI_CLOSE_PAREN);
        }
        Expression::RetVal {
            inner_opcode,
            inner_params,
            inner_raw_tail,
            ..
        } => {
            out.push(GPL_RETVAL | 0x80);
            out.push(*inner_opcode);
            // The inner opcode's params follow, encoded with the
            // same per-opcode logic as a top-level instruction
            // (minus the leading opcode byte).
            let spec = if (*inner_opcode as usize) <= MAX_KNOWN_OPCODE as usize {
                PARAM_COUNTS[*inner_opcode as usize]
            } else {
                ParamSpec::Custom
            };
            match spec {
                ParamSpec::None => {}
                ParamSpec::Fixed(n) => {
                    if inner_params.len() != n as usize {
                        return Err(EncodeError::BadParamShape {
                            offset: instr_offset,
                            opcode: *inner_opcode,
                            param_index: 0,
                            detail: "RETVAL inner-param count mismatch",
                        });
                    }
                    for param in inner_params {
                        encode_param(out, instr_offset, param)?;
                    }
                }
                ParamSpec::Search => {
                    // Same shape as a top-level Search: encode the
                    // first param (the target expression) then
                    // append the captured `inner_raw_tail`.
                    if inner_params.is_empty() {
                        return Err(EncodeError::BadParamShape {
                            offset: instr_offset,
                            opcode: *inner_opcode,
                            param_index: 0,
                            detail: "RETVAL+search expects at least the target param",
                        });
                    }
                    encode_param(out, instr_offset, &inner_params[0])?;
                    match inner_raw_tail {
                        Some(tail) => out.extend_from_slice(tail),
                        None => {
                            return Err(EncodeError::UnsupportedOpcode {
                                offset: instr_offset,
                                opcode: *inner_opcode,
                                reason: "RETVAL+search has no inner_raw_tail; needs gpl-disasm v0.4.5+",
                            });
                        }
                    }
                }
                _ => {
                    return Err(EncodeError::UnsupportedOpcode {
                        offset: instr_offset,
                        opcode: *inner_opcode,
                        reason: "RETVAL inner opcodes with non-Fixed/Search specs not supported in v0.1.1",
                    });
                }
            }
        }
        Expression::ComplexAccess {
            tag,
            obj_name,
            depth,
            elements,
        } => {
            // Standalone ComplexAccess (not under LoadVar/SetRecord)
            // appears as a typed token, dispatch byte = tag | 0x80,
            // followed by the access_complex body.
            out.push((*tag & 0x7F) | 0x80);
            encode_complex_body(out, *obj_name, *depth, elements);
        }
        Expression::AccmError => {
            // libgff aborts on this; our decoder marks best_effort
            // already, which we reject upstream. Defensive emit.
            out.push(GPL_ACCM | 0x80);
        }
        Expression::ImmediWordUnimplemented => {
            out.push(GPL_IMMED_WORD | 0x80);
        }
        Expression::Unknown { byte } => {
            let _ = byte;
            return Err(EncodeError::UnknownToken {
                offset: instr_offset,
            });
        }
    }
    let _ = GPL_COMPLEX_LOW; // silence "unused import" if features ever drop one
    Ok(())
}

/// Encode a variable-id (1 byte without `extended`, 2 bytes BE with).
fn encode_var_id(out: &mut Vec<u8>, id: u16, extended: bool) {
    if extended {
        out.push((id >> 8) as u8);
        out.push((id & 0xFF) as u8);
    } else {
        out.push((id & 0xFF) as u8);
    }
}

/// Encode an access_complex body: word obj_name (big-endian) + byte
/// depth + depth bytes of elements.
fn encode_complex_body(out: &mut Vec<u8>, obj_name: i32, depth: u8, elements: &[u8]) {
    let on = obj_name as u16;
    out.push((on >> 8) as u8);
    out.push((on & 0xFF) as u8);
    out.push(depth);
    out.extend_from_slice(elements);
}

/// Encode the body of an `IMMED_STRING` (or `ParamSpec::Log`): one
/// sub-type marker byte (`STRING_INTRODUCE` / `STRING_UNCOMPRESSED`
/// / `STRING_COMPRESSED`) optionally followed by the payload.
fn encode_string_payload(out: &mut Vec<u8>, sub_type: StringSubType, value: &str) {
    match sub_type {
        StringSubType::Introduce => {
            out.push(STRING_INTRODUCE);
        }
        StringSubType::Uncompressed => {
            // The decoder emits a placeholder string for this case
            // (`<uncompressed; decoder not implemented>`), so we can
            // only safely write the marker byte. The corpus has zero
            // occurrences.
            out.push(STRING_UNCOMPRESSED);
        }
        StringSubType::Compressed => {
            out.push(STRING_COMPRESSED);
            pack_compressed_string(out, value);
        }
    }
}

/// Pack `value`'s characters into the 7-bit MSB-first bitstream
/// terminated by `STRING_TERMINATOR` (0x03). Inverse of
/// `decode_compressed` in `gpl-disasm`'s lib.rs.
///
/// Each character contributes 7 bits, packed MSB-first. After the
/// terminator (7 more bits = 0x03), trailing bits are left-aligned
/// into a final byte. The decoder ignores bits past the terminator
/// (it returns as soon as it sees 0x03), so the padding bits we
/// emit don't affect a re-decode.
pub fn pack_compressed_string(out: &mut Vec<u8>, value: &str) {
    let mut buffer: u32 = 0;
    let mut nbits: u32 = 0;
    let push_seven = |out: &mut Vec<u8>, buffer: &mut u32, nbits: &mut u32, v: u8| {
        *buffer = (*buffer << 7) | (v as u32 & 0x7F);
        *nbits += 7;
        while *nbits >= 8 {
            *nbits -= 8;
            out.push(((*buffer >> *nbits) & 0xFF) as u8);
            *buffer &= (1u32 << *nbits) - 1;
        }
    };
    for c in value.bytes() {
        push_seven(out, &mut buffer, &mut nbits, c);
    }
    push_seven(out, &mut buffer, &mut nbits, STRING_TERMINATOR);
    if nbits > 0 {
        // Left-justify the trailing bits into one final byte.
        out.push(((buffer << (8 - nbits)) & 0xFF) as u8);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use gpl_disasm::{Op, VarKind, disassemble};

    /// Helper: round-trip a chunk through disassemble + encode and
    /// assert byte-identical.
    fn roundtrip(bytes: &[u8]) {
        let result = disassemble(bytes);
        assert!(
            result.aligned,
            "disassembly was not aligned: {:?}",
            result.instructions
        );
        let encoded = encode(&result).expect("encode");
        assert_eq!(
            encoded, bytes,
            "round-trip mismatch\n  orig: {:02x?}\n  ours: {:02x?}",
            bytes, encoded
        );
    }

    #[test]
    fn roundtrip_no_param_opcodes() {
        // 0x67 gpl endif, 0x31 gpl exit gpl, 0x51 gpl printnl.
        roundtrip(&[0x67, 0x31, 0x51]);
    }

    #[test]
    fn roundtrip_immediate14() {
        // gpl jump (0x12) with 14-bit immediate 0x1234.
        roundtrip(&[0x12, 0x12, 0x34]);
    }

    #[test]
    fn roundtrip_immediate_byte() {
        // gpl jump (0x12) with IMMED_BYTE param value = 42 (0x2A).
        roundtrip(&[0x12, 0x8F, 0x2A]);
    }

    #[test]
    fn roundtrip_immediate_bignum() {
        // gpl jump with IMMED_BIGNUM value = 0x12345678.
        roundtrip(&[0x12, 0x8B, 0x12, 0x34, 0x56, 0x78]);
    }

    #[test]
    fn roundtrip_immediate_name() {
        // gpl jump with IMMED_NAME h=0x100 -> value=-256.
        roundtrip(&[0x12, 0x91, 0x01, 0x00]);
    }

    #[test]
    fn roundtrip_variable_simple_and_extended() {
        // gpl jump with GNUM[0x07] (simple, 1-byte id).
        roundtrip(&[0x12, 0x80 | gpl_disasm::GPL_GNUM, 0x07]);
        // gpl jump with GNUM+[0x0102] (extended, 2-byte id).
        roundtrip(&[
            0x12,
            0x80 | gpl_disasm::EXTENDED_VAR | gpl_disasm::GPL_GNUM,
            0x01,
            0x02,
        ]);
    }

    #[test]
    fn roundtrip_binary_op_and_parens() {
        // gpl jump with (gnum[1] + 5).
        // bytes: 0x12 [open] [gnum tag] 1 [op_add] [imm14 0x05] [close]
        // imm14(5): hi=0, lo=5.
        roundtrip(&[
            0x12,
            GPL_HI_OPEN_PAREN,
            0x80 | gpl_disasm::GPL_GNUM,
            0x01,
            0xD1, // OP_ADD
            0x00,
            0x05,
            GPL_HI_CLOSE_PAREN,
        ]);
    }

    #[test]
    fn pack_compressed_string_roundtrip() {
        // Pack "Hi" then re-decode via gpl_disasm's read_text path
        // (through disassemble of a gpl print string instruction).
        // gpl print string (0x4F) takes 2 params.
        let mut payload = Vec::new();
        pack_compressed_string(&mut payload, "Hi");
        // Build: 0x4F (gpl print string), param0 = imm14(0), param1 = IMMED_STRING marker + COMPRESSED + payload.
        let mut bytes = vec![0x4F, 0x00, 0x00, GPL_IMMED_STRING | 0x80, STRING_COMPRESSED];
        bytes.extend(payload);
        roundtrip(&bytes);
    }

    #[test]
    fn pack_compressed_string_preserves_tab() {
        // Encoder must emit bytes that decode back to "\t" not " ".
        // After v0.4.3 the decoder is lossless; the encoder relies on
        // that contract.
        let mut payload = Vec::new();
        pack_compressed_string(&mut payload, "\tA");
        // Manually decode (just shift bits) to confirm.
        let r = disassemble(&[
            0x4F,
            0x00,
            0x00,
            GPL_IMMED_STRING | 0x80,
            STRING_COMPRESSED,
            payload[0],
            payload[1],
            payload[2],
        ]);
        assert!(r.aligned);
        match &r.instructions[0].params[1][0] {
            Expression::ImmediateString { value, .. } => {
                assert_eq!(value.as_bytes(), b"\tA");
            }
            other => panic!("expected ImmediateString, got {other:?}"),
        }
    }

    #[test]
    fn op_to_byte_inverse_of_from_byte() {
        for byte in 0xD1u8..=0xDF {
            let op = Op::from_byte(byte).unwrap();
            assert_eq!(op.to_byte(), byte);
        }
    }

    #[test]
    fn var_kind_to_tag_inverse_of_from_tag() {
        for tag in 0x01u8..=0x0E {
            if let Some(vk) = VarKind::from_tag(tag) {
                assert_eq!(vk.to_tag(), tag);
            }
        }
    }
}
