//! Static validation pass for a parsed `DisasmResult`. Runs
//! after [`crate::parse::parse`] (or after JSON deserialisation)
//! and before encoding, catching whole classes of authoring
//! mistakes that the encoder would otherwise surface one-at-a-
//! time (or, worse, silently encode into a broken chunk).
//!
//! The validator is deliberately conservative: every check is
//! something the encoder would reject anyway, just with a less
//! useful error. The point is to surface ALL such issues at once
//! and to anchor them on the instruction offset the author can
//! find by eye in the listing.
//!
//! v0.5.0 checks:
//!
//! - **Branch target bounds**: for every branch-class opcode
//!   (jump / local-sub / conditional / else / wend / ifcompare),
//!   if the target slot is a literal offset, it must fall inside
//!   `[0, total_bytes)`. `gpl global sub` (0x14) is skipped: its
//!   targets are cross-chunk by design and routinely point
//!   beyond this chunk.
//! - **`Immediate14` 15-bit range**: despite the historical
//!   name, the on-the-wire encoding is actually 15 bits (the
//!   opcode-low-7 + byte path: `(cop & 0x7F) << 8 | b`), so the
//!   value's hard ceiling is 0..=32767. `u16` lets bigger
//!   values round-trip through JSON, so check explicitly.
//! - **`RetVal` nesting depth**: capped at
//!   [`gpl_disasm::MAX_RETVAL_DEPTH`] (= 4). The disassembler
//!   refuses to recurse further, so a hand-edited listing that
//!   does is guaranteed unencodable.

use gpl_disasm::{DisasmResult, Expression, Instruction, MAX_RETVAL_DEPTH};
use thiserror::Error;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum ValidationError {
    #[error(
        "instruction at offset {offset:#06x} (opcode 0x{opcode:02x} {mnemonic}) branches to {target:#06x}, which is outside chunk bounds [0, {total_bytes:#06x})"
    )]
    BranchTargetOutOfBounds {
        offset: usize,
        opcode: u8,
        mnemonic: String,
        target: usize,
        total_bytes: usize,
    },

    #[error(
        "instruction at offset {offset:#06x}: Immediate14 value {value} exceeds the on-wire 15-bit unsigned range (0..=32767)"
    )]
    Immediate14Overflow { offset: usize, value: u16 },

    #[error(
        "instruction at offset {offset:#06x}: RetVal expression nests {depth} levels (max {max} per gpl_disasm::MAX_RETVAL_DEPTH)"
    )]
    RetValTooDeep {
        offset: usize,
        depth: usize,
        max: usize,
    },
}

/// Result of a [`validate`] pass: an empty `errors` vec means
/// the program is encode-ready.
#[derive(Debug, Default)]
pub struct ValidationReport {
    pub errors: Vec<ValidationError>,
}

impl ValidationReport {
    pub fn is_ok(&self) -> bool {
        self.errors.is_empty()
    }

    pub fn len(&self) -> usize {
        self.errors.len()
    }

    pub fn is_empty(&self) -> bool {
        self.errors.is_empty()
    }
}

/// Validate a parsed disassembly. See module-level docs for the
/// list of checks.
pub fn validate(disasm: &DisasmResult) -> ValidationReport {
    let mut errors = Vec::new();
    let total = disasm.total_bytes;
    for instr in &disasm.instructions {
        check_branch_target(instr, total, &mut errors);
        check_immediate14(instr, &mut errors);
        check_retval_depth(instr, &mut errors);
    }
    ValidationReport { errors }
}

/// For each branch-class opcode, which param slot holds the
/// target, and whether that target may legitimately fall outside
/// this chunk (`gpl global sub` only).
fn branch_slot(opcode: u8) -> Option<(usize, bool)> {
    match opcode {
        0x12 => Some((0, false)),        // gpl jump
        0x13 => Some((0, false)),        // gpl local sub
        0x14 => Some((0, true)),         // gpl global sub (cross-chunk)
        0x27 => Some((1, false)),        // gpl ifcompare
        0x3E | 0x63 => Some((0, false)), // gpl if, gpl while
        0x3F => Some((0, false)),        // gpl else
        0x64 => Some((0, false)),        // gpl wend
        _ => None,
    }
}

fn check_branch_target(instr: &Instruction, total: usize, errors: &mut Vec<ValidationError>) {
    let Some((slot, allow_oob)) = branch_slot(instr.opcode) else {
        return;
    };
    if allow_oob {
        return;
    }
    let Some(param) = instr.params.get(slot) else {
        return;
    };
    let Some(target) = literal_target(param) else {
        return;
    };
    if target < 0 || (target as usize) >= total {
        errors.push(ValidationError::BranchTargetOutOfBounds {
            offset: instr.offset,
            opcode: instr.opcode,
            mnemonic: instr.mnemonic.as_deref().unwrap_or("?").to_string(),
            target: target as usize,
            total_bytes: total,
        });
    }
}

fn check_immediate14(instr: &Instruction, errors: &mut Vec<ValidationError>) {
    for param in &instr.params {
        for expr in param {
            walk_immediate14(expr, instr.offset, errors);
        }
    }
}

fn walk_immediate14(expr: &Expression, offset: usize, errors: &mut Vec<ValidationError>) {
    match expr {
        Expression::Immediate14 { value } if *value > 32767 => {
            errors.push(ValidationError::Immediate14Overflow {
                offset,
                value: *value,
            });
        }
        Expression::RetVal { inner_params, .. } => {
            for param in inner_params {
                for inner in param {
                    walk_immediate14(inner, offset, errors);
                }
            }
        }
        _ => {}
    }
}

fn check_retval_depth(instr: &Instruction, errors: &mut Vec<ValidationError>) {
    let max = MAX_RETVAL_DEPTH as usize;
    for param in &instr.params {
        for expr in param {
            let d = retval_depth(expr);
            if d > max {
                errors.push(ValidationError::RetValTooDeep {
                    offset: instr.offset,
                    depth: d,
                    max,
                });
            }
        }
    }
}

fn retval_depth(expr: &Expression) -> usize {
    match expr {
        Expression::RetVal { inner_params, .. } => {
            1 + inner_params
                .iter()
                .flat_map(|p| p.iter())
                .map(retval_depth)
                .max()
                .unwrap_or(0)
        }
        _ => 0,
    }
}

/// Extract a literal target offset from a single-expression
/// param. Mirrors `gpl_disasm::literal_target` (which is
/// private to that crate) so the validator doesn't depend on
/// internal symbols.
fn literal_target(param: &[Expression]) -> Option<i64> {
    if param.len() != 1 {
        return None;
    }
    match &param[0] {
        Expression::Immediate14 { value } => Some(*value as i64),
        Expression::ImmediateByte { value } => Some(*value as i64),
        Expression::ImmediateBigNum { value } => Some(*value as i64),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use gpl_disasm::Instruction;
    use std::borrow::Cow;

    fn dr(instrs: Vec<Instruction>, total: usize) -> DisasmResult {
        DisasmResult {
            instructions: instrs,
            bytes_consumed: total,
            total_bytes: total,
            aligned: true,
            cfg: None,
            cross_chunk_calls: Vec::new(),
        }
    }

    fn jump(offset: usize, target: u16) -> Instruction {
        Instruction {
            offset,
            length: 3,
            opcode: 0x12,
            mnemonic: Some(Cow::Borrowed("gpl jump")),
            params: vec![vec![Expression::Immediate14 { value: target }]],
            best_effort: false,
            string_run: None,
            raw_tail: None,
        }
    }

    fn global_sub(offset: usize, target: u16) -> Instruction {
        Instruction {
            offset,
            length: 3,
            opcode: 0x14,
            mnemonic: Some(Cow::Borrowed("gpl global sub")),
            params: vec![vec![Expression::Immediate14 { value: target }]],
            best_effort: false,
            string_run: None,
            raw_tail: None,
        }
    }

    #[test]
    fn clean_program_validates() {
        let d = dr(vec![jump(0x00, 0x10)], 0x100);
        let r = validate(&d);
        assert!(r.is_ok(), "{:?}", r.errors);
    }

    #[test]
    fn jump_past_chunk_end_is_flagged() {
        let d = dr(vec![jump(0x00, 0x200)], 0x100);
        let r = validate(&d);
        assert_eq!(r.len(), 1);
        assert!(matches!(
            r.errors[0],
            ValidationError::BranchTargetOutOfBounds {
                offset: 0,
                opcode: 0x12,
                target: 0x200,
                total_bytes: 0x100,
                ..
            }
        ));
    }

    #[test]
    fn global_sub_target_outside_chunk_is_allowed() {
        // 0x14 = gpl global sub; cross-chunk targets are expected.
        // Use 0x500 (inside the 14-bit range so the Immediate14
        // overflow check doesn't fire) but well outside the
        // 0x100-byte chunk.
        let d = dr(vec![global_sub(0x00, 0x500)], 0x100);
        let r = validate(&d);
        assert!(r.is_ok(), "{:?}", r.errors);
    }

    #[test]
    fn overflowing_immediate14_is_flagged() {
        // The on-wire ceiling is 32767 (cop_low_7 << 8 | b);
        // 40000 is well past it.
        let instr = Instruction {
            offset: 0x10,
            length: 3,
            opcode: 0x3A, // gpl_immed (non-branch)
            mnemonic: Some(Cow::Borrowed("gpl_immed")),
            params: vec![vec![Expression::Immediate14 { value: 40000 }]],
            best_effort: false,
            string_run: None,
            raw_tail: None,
        };
        let d = dr(vec![instr], 0x100);
        let r = validate(&d);
        assert_eq!(r.len(), 1);
        assert!(matches!(
            r.errors[0],
            ValidationError::Immediate14Overflow {
                offset: 0x10,
                value: 40000
            }
        ));
    }

    #[test]
    fn immediate14_at_ceiling_is_ok() {
        // Real corpus chunks (DS1 MAS/0x3 etc.) carry values up
        // to 32767 verbatim. Make sure validate accepts them.
        let instr = Instruction {
            offset: 0x10,
            length: 3,
            opcode: 0x3A,
            mnemonic: Some(Cow::Borrowed("gpl_immed")),
            params: vec![vec![Expression::Immediate14 { value: 32767 }]],
            best_effort: false,
            string_run: None,
            raw_tail: None,
        };
        let r = validate(&dr(vec![instr], 0x100));
        assert!(r.is_ok(), "{:?}", r.errors);
    }

    #[test]
    fn retval_at_max_depth_is_ok_but_one_beyond_is_flagged() {
        // Build a RetVal chain at depth MAX_RETVAL_DEPTH (= 4):
        // RetVal(RetVal(RetVal(RetVal(<leaf>)))).
        fn nest(depth: usize) -> Expression {
            let inner = if depth == 0 {
                Expression::Immediate14 { value: 1 }
            } else {
                nest(depth - 1)
            };
            Expression::RetVal {
                inner_opcode: 0x3A,
                inner_mnemonic: Some(Cow::Borrowed("gpl_immed")),
                inner_params: vec![vec![inner]],
                inner_raw_tail: None,
            }
        }

        let at_max = Instruction {
            offset: 0x00,
            length: 3,
            opcode: 0x3A,
            mnemonic: Some(Cow::Borrowed("gpl_immed")),
            params: vec![vec![nest(MAX_RETVAL_DEPTH as usize - 1)]],
            best_effort: false,
            string_run: None,
            raw_tail: None,
        };
        let r = validate(&dr(vec![at_max.clone()], 0x100));
        assert!(r.is_ok(), "at-max should pass: {:?}", r.errors);

        let too_deep = Instruction {
            params: vec![vec![nest(MAX_RETVAL_DEPTH as usize)]],
            ..at_max
        };
        let r = validate(&dr(vec![too_deep], 0x100));
        assert_eq!(r.len(), 1);
        assert!(matches!(r.errors[0], ValidationError::RetValTooDeep { .. }));
    }
}
