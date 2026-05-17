//! Structural edits over a [`DisasmResult`]: insert / delete /
//! replace instructions with automatic offset shifting and
//! branch-target recompute.
//!
//! Workflow:
//!
//! ```ignore
//! let result = gpl_disasm::disassemble(&chunk_bytes);
//! let mut ed = gpl_asm::Editor::from_result(result);
//! let new_instr = ed.make_endif(/* offset placeholder */)?;
//! ed.insert_instruction(0x0011, new_instr)?;
//! let edited = ed.into_result();
//! let new_bytes = gpl_asm::encode(&edited)?;
//! ```
//!
//! All branch instructions whose target offset is `>=
//! insertion_offset` get their target shifted by the
//! insert's byte length. Same idea for delete / replace
//! (negative delta). The editor re-encodes each touched
//! instruction to compute its byte length authoritatively.

use crate::{EncodeError, encode_instruction};
use gpl_disasm::{
    DisasmResult, Expression, Instruction, MAX_KNOWN_OPCODE, OPCODES, PARAM_COUNTS, ParamSpec,
    opcode_name,
};
use std::borrow::Cow;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum EditError {
    #[error("no instruction at offset {offset:#x}")]
    NoInstructionAt { offset: usize },
    #[error("instruction at offset {offset:#x} fails to encode: {source}")]
    LengthComputation {
        offset: usize,
        #[source]
        source: EncodeError,
    },
    #[error("branch target overflows u16 after shift: {target}")]
    BranchOverflow { target: i64 },
}

pub type Result<T> = std::result::Result<T, EditError>;

/// In-memory edit buffer for one disassembled chunk. Tracks the
/// instruction list, recomputes total_bytes on every edit, and
/// shifts branch targets through inserts/deletes/replaces.
pub struct Editor {
    instructions: Vec<Instruction>,
    total_bytes: usize,
    /// CFG carried over from the source disassembly (read-only).
    /// Stale after any edit; downstream consumers needing CFG
    /// info should re-disassemble the edited bytes.
    aligned: bool,
}

impl Editor {
    /// Wrap a [`DisasmResult`] in an editor. The source result's
    /// CFG and cross-chunk metadata are dropped on `into_result`
    /// because they become stale after any structural edit; the
    /// caller can re-disassemble to rebuild them.
    pub fn from_result(result: DisasmResult) -> Self {
        Editor {
            instructions: result.instructions,
            total_bytes: result.total_bytes,
            aligned: result.aligned,
        }
    }

    pub fn instructions(&self) -> &[Instruction] {
        &self.instructions
    }

    pub fn total_bytes(&self) -> usize {
        self.total_bytes
    }

    /// Build a fresh instruction for `opcode` from `params`. The
    /// returned instruction has `offset = 0` (filled in by
    /// `insert_instruction`) and a computed `length`.
    pub fn make_instruction(
        opcode: u8,
        params: Vec<Vec<Expression>>,
        raw_tail: Option<Vec<u8>>,
    ) -> Result<Instruction> {
        let mut instr = Instruction {
            offset: 0,
            length: 0,
            opcode,
            mnemonic: opcode_name(opcode).map(Cow::Borrowed),
            params,
            best_effort: false,
            string_run: None,
            raw_tail,
        };
        instr.length = encoded_length(&instr)?;
        Ok(instr)
    }

    /// Convenience: build a parameterless instruction (most
    /// `ParamSpec::None` opcodes, e.g. `gpl endif` 0x67).
    pub fn make_simple(opcode: u8) -> Result<Instruction> {
        Self::make_instruction(opcode, Vec::new(), None)
    }

    /// Insert `instr` before the existing instruction at
    /// `before_offset`. Every subsequent instruction's `offset`
    /// shifts by the new instruction's `length`. Every branch
    /// target `>= before_offset` shifts by the same amount.
    pub fn insert_instruction(
        &mut self,
        before_offset: usize,
        mut instr: Instruction,
    ) -> Result<()> {
        let idx = self
            .find_index(before_offset)
            .ok_or(EditError::NoInstructionAt {
                offset: before_offset,
            })?;
        instr.offset = before_offset;
        if instr.length == 0 {
            instr.length = encoded_length(&instr)?;
        }
        let delta = instr.length as isize;
        // Shift subsequent instruction offsets.
        for later in &mut self.instructions[idx..] {
            later.offset = (later.offset as isize + delta) as usize;
        }
        // Shift branch targets >= before_offset.
        retarget_branches(&mut self.instructions, before_offset, delta)?;
        // Also retarget the inserted instruction's own branch
        // target if it's >= before_offset (e.g., a forward jump
        // around the newly inserted code).
        retarget_in(&mut std::slice::from_mut(&mut instr), before_offset, delta)?;
        self.instructions.insert(idx, instr);
        self.total_bytes = (self.total_bytes as isize + delta) as usize;
        Ok(())
    }

    /// Delete the instruction at `at_offset`. Subsequent
    /// instructions shift down by the deleted length; branch
    /// targets `> at_offset` shift by the same amount (a target
    /// equal to `at_offset` becomes invalid — the encoder will
    /// surface that downstream).
    pub fn delete_instruction(&mut self, at_offset: usize) -> Result<Instruction> {
        let idx = self.find_index(at_offset).ok_or(EditError::NoInstructionAt {
            offset: at_offset,
        })?;
        let removed = self.instructions.remove(idx);
        let delta = -(removed.length as isize);
        for later in &mut self.instructions[idx..] {
            later.offset = (later.offset as isize + delta) as usize;
        }
        // Branches that targeted offsets STRICTLY GREATER than
        // the deleted offset shift down. A branch that targeted
        // exactly the deleted offset is now dangling and stays
        // pointing at the byte that was at_offset (which now
        // belongs to the next instruction).
        retarget_branches(&mut self.instructions, at_offset + 1, delta)?;
        self.total_bytes = (self.total_bytes as isize + delta) as usize;
        Ok(removed)
    }

    /// Replace the instruction at `at_offset` with `new`. The
    /// new instruction's `length` is recomputed; subsequent
    /// instructions and branch targets shift by `(new.length -
    /// old.length)`.
    pub fn replace_instruction(
        &mut self,
        at_offset: usize,
        mut new: Instruction,
    ) -> Result<Instruction> {
        let idx = self.find_index(at_offset).ok_or(EditError::NoInstructionAt {
            offset: at_offset,
        })?;
        let old_len = self.instructions[idx].length;
        new.offset = at_offset;
        if new.length == 0 {
            new.length = encoded_length(&new)?;
        }
        let delta = new.length as isize - old_len as isize;
        // Order matters: swap the new instruction in first so
        // that its own branch params (if any) participate in
        // the retarget pass. Then shift offsets and retarget.
        let old = std::mem::replace(&mut self.instructions[idx], new);
        if delta != 0 {
            let after_offset = at_offset + old_len;
            for later in &mut self.instructions[idx + 1..] {
                later.offset = (later.offset as isize + delta) as usize;
            }
            retarget_branches(&mut self.instructions, after_offset, delta)?;
        }
        self.total_bytes = (self.total_bytes as isize + delta) as usize;
        Ok(old)
    }

    /// Materialize the edited state as a [`DisasmResult`]. The
    /// CFG and `cross_chunk_calls` are NOT carried over; they
    /// were stale after the first edit. Downstream consumers
    /// should re-disassemble the encoded bytes if they need
    /// fresh CFG info.
    pub fn into_result(self) -> DisasmResult {
        DisasmResult {
            instructions: self.instructions,
            bytes_consumed: self.total_bytes,
            total_bytes: self.total_bytes,
            aligned: self.aligned,
            cfg: None,
            cross_chunk_calls: Vec::new(),
        }
    }

    fn find_index(&self, offset: usize) -> Option<usize> {
        self.instructions.iter().position(|i| i.offset == offset)
    }
}

/// Compute the byte length of one instruction by re-encoding it
/// to a scratch buffer. Used by `Editor::make_instruction` and
/// every length-touching edit operation.
fn encoded_length(instr: &Instruction) -> Result<usize> {
    let mut buf = Vec::with_capacity(8);
    encode_instruction(&mut buf, instr).map_err(|e| EditError::LengthComputation {
        offset: instr.offset,
        source: e,
    })?;
    Ok(buf.len())
}

/// Shift branch targets `>= cutoff` by `delta` across all
/// instructions in `slice`.
pub fn retarget_branches(slice: &mut [Instruction], cutoff: usize, delta: isize) -> Result<()> {
    retarget_in(slice, cutoff, delta)
}

fn retarget_in(slice: &mut [Instruction], cutoff: usize, delta: isize) -> Result<()> {
    for instr in slice.iter_mut() {
        if let Some(param_idx) = branch_target_param_index(instr) {
            let Some(param) = instr.params.get_mut(param_idx) else {
                continue;
            };
            if param.len() != 1 {
                continue;
            }
            let target = match &param[0] {
                Expression::Immediate14 { value } => *value as i64,
                Expression::ImmediateByte { value } => *value as i64,
                Expression::ImmediateBigNum { value } => *value as i64,
                _ => continue,
            };
            if target < 0 || (target as usize) < cutoff {
                continue;
            }
            let new_target = target + delta as i64;
            if new_target < 0 || new_target > u16::MAX as i64 {
                return Err(EditError::BranchOverflow { target: new_target });
            }
            param[0] = Expression::Immediate14 {
                value: new_target as u16,
            };
        }
    }
    Ok(())
}

/// Which param index of a branch instruction holds the target
/// offset. Returns `None` for non-branch opcodes.
fn branch_target_param_index(instr: &Instruction) -> Option<usize> {
    match instr.opcode {
        0x12 | 0x13 | 0x3E | 0x3F | 0x63 | 0x64 => Some(0),
        0x27 => Some(1),
        _ => None,
    }
}

/// True if `opcode`'s `ParamSpec` is one the editor knows how to
/// re-encode safely (currently every variant except `Custom`).
pub fn can_edit_opcode(opcode: u8) -> bool {
    if (opcode as usize) > MAX_KNOWN_OPCODE as usize {
        return false;
    }
    !matches!(PARAM_COUNTS[opcode as usize], ParamSpec::Custom)
}

/// Convenience pretty-print of an opcode's mnemonic, used in
/// downstream error messages.
pub fn opcode_label(opcode: u8) -> &'static str {
    if (opcode as usize) <= MAX_KNOWN_OPCODE as usize {
        OPCODES[opcode as usize]
    } else {
        "?"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::encode;
    use gpl_disasm::disassemble;

    fn synth_chunk(bytes: &[u8]) -> DisasmResult {
        let r = disassemble(bytes);
        assert!(r.aligned, "synth chunk must disassemble cleanly");
        r
    }

    #[test]
    fn insert_endif_at_start_shifts_following() {
        // Source: just one `gpl endif` (0x67) at offset 0.
        let result = synth_chunk(&[0x67]);
        let mut ed = Editor::from_result(result);
        let endif = Editor::make_simple(0x67).unwrap();
        ed.insert_instruction(0, endif).unwrap();
        assert_eq!(ed.instructions().len(), 2);
        assert_eq!(ed.instructions()[0].offset, 0);
        assert_eq!(ed.instructions()[1].offset, 1);
        assert_eq!(ed.total_bytes(), 2);
        let bytes = encode(&ed.into_result()).unwrap();
        assert_eq!(bytes, vec![0x67, 0x67]);
    }

    #[test]
    fn insert_shifts_branch_target_after_insertion_point() {
        // Source:
        //   0000  3E  gpl if 5      (jump to offset 5 if false)
        //   0003  67  gpl endif
        //   0004  67  gpl endif
        //   0005  67  gpl endif  (target)
        // bytes: 3E 00 05 67 67 67
        let result = synth_chunk(&[0x3E, 0x00, 0x05, 0x67, 0x67, 0x67]);
        let mut ed = Editor::from_result(result);
        // Insert a `gpl endif` before offset 0x03 (between if
        // and first endif). The jump's target (0x05) is >= 0x03,
        // so it should shift to 0x06.
        let endif = Editor::make_simple(0x67).unwrap();
        ed.insert_instruction(0x03, endif).unwrap();
        let bytes = encode(&ed.into_result()).unwrap();
        // 3E 00 06 67 67 67 67
        assert_eq!(bytes, vec![0x3E, 0x00, 0x06, 0x67, 0x67, 0x67, 0x67]);
    }

    #[test]
    fn delete_shifts_branch_target_down() {
        // Source: 3E 00 05 67 67 67 67  (jump to offset 5; 4 endifs)
        let result = synth_chunk(&[0x3E, 0x00, 0x05, 0x67, 0x67, 0x67, 0x67]);
        let mut ed = Editor::from_result(result);
        // Delete the endif at offset 0x03.
        let _ = ed.delete_instruction(0x03).unwrap();
        let bytes = encode(&ed.into_result()).unwrap();
        // Target shifts 0x05 -> 0x04. Result: 3E 00 04 67 67 67.
        assert_eq!(bytes, vec![0x3E, 0x00, 0x04, 0x67, 0x67, 0x67]);
    }

    #[test]
    fn replace_with_same_length_keeps_offsets() {
        let result = synth_chunk(&[0x67, 0x67, 0x67]);
        let mut ed = Editor::from_result(result);
        let exit_gpl = Editor::make_simple(0x31).unwrap();
        let old = ed.replace_instruction(0x01, exit_gpl).unwrap();
        assert_eq!(old.opcode, 0x67);
        let bytes = encode(&ed.into_result()).unwrap();
        assert_eq!(bytes, vec![0x67, 0x31, 0x67]);
    }

    #[test]
    fn replace_with_longer_shifts_following_and_branches() {
        // Source: 67 67 67  (3x endif).
        let result = synth_chunk(&[0x67, 0x67, 0x67]);
        let mut ed = Editor::from_result(result);
        // Replace endif at offset 1 (1 byte) with a `gpl jump 0x02`
        // (3 bytes: 0x12 0x00 0x02). delta = +2.
        let mut new = Instruction {
            offset: 0,
            length: 0,
            opcode: 0x12,
            mnemonic: opcode_name(0x12).map(Cow::Borrowed),
            params: vec![vec![Expression::Immediate14 { value: 2 }]],
            best_effort: false,
            string_run: None,
            raw_tail: None,
        };
        new.length = encoded_length(&new).unwrap();
        ed.replace_instruction(0x01, new).unwrap();
        let bytes = encode(&ed.into_result()).unwrap();
        // 67 [12 00 04] 67  (jump's target 2 shifted to 4)
        assert_eq!(bytes, vec![0x67, 0x12, 0x00, 0x04, 0x67]);
    }

    #[test]
    fn missing_offset_errors() {
        let result = synth_chunk(&[0x67, 0x67]);
        let mut ed = Editor::from_result(result);
        let endif = Editor::make_simple(0x67).unwrap();
        let err = ed.insert_instruction(0x05, endif).unwrap_err();
        match err {
            EditError::NoInstructionAt { offset } => assert_eq!(offset, 0x05),
            other => panic!("unexpected: {other:?}"),
        }
    }
}
