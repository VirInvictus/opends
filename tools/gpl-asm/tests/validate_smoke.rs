//! Corpus + synthetic smoke tests for the v0.5.0 validator.
//!
//! Two assertions:
//!
//! 1. Every aligned GPL/MAS chunk in DS1+DS2 `GPLDATA.GFF`
//!    validates clean. The validator must not raise false
//!    positives on real-world data; if it does, downstream
//!    bulk-encode flows break and the corpus round-trip test
//!    starts skipping chunks.
//! 2. A hand-rolled `DisasmResult` with an out-of-bounds jump
//!    target fires exactly the `BranchTargetOutOfBounds`
//!    variant. Exercises validation through the public API the
//!    `gpl-asm` binary uses.
//!
//! Skipped silently when `.games/` is absent.

use std::borrow::Cow;
use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use gpl_asm::{ValidationError, validate};
use gpl_disasm::{DisasmResult, Expression, Instruction, disassemble};

const CORPUS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/GPLDATA.GFF",
];

fn is_script(kind: FourCC) -> bool {
    matches!(kind.as_bytes(), b"GPL " | b"MAS ")
}

#[test]
fn corpus_chunks_validate_clean() {
    let mut tested = 0usize;
    let mut clean = 0usize;
    let mut samples: Vec<String> = Vec::new();

    for path in CORPUS {
        let p = Path::new(path);
        if !p.is_file() {
            continue;
        }
        let bytes = fs::read(p).unwrap_or_else(|e| panic!("reading {path}: {e}"));
        let gff = Gff::from_bytes(bytes).unwrap_or_else(|e| panic!("parsing {path}: {e}"));
        for c in gff.chunks() {
            if !is_script(c.kind) {
                continue;
            }
            let chunk_bytes = gff
                .read(c.kind, c.id)
                .unwrap_or_else(|| panic!("reading {path} {} {}: missing", c.kind, c.id));
            let result = disassemble(chunk_bytes);
            if !result.aligned {
                continue;
            }
            tested += 1;
            let report = validate(&result);
            if report.is_ok() {
                clean += 1;
            } else if samples.len() < 5 {
                samples.push(format!(
                    "{} {}/{:#x}: {:?}",
                    path, c.kind, c.id, report.errors
                ));
            }
        }
    }

    if tested == 0 {
        eprintln!("validate corpus: 0 chunks (no .games/ present, skipping)");
        return;
    }

    assert_eq!(
        clean, tested,
        "validator must not flag any real corpus chunk. samples: {samples:#?}"
    );
    eprintln!("validate corpus: {clean} / {tested} chunks clean");
}

#[test]
fn hand_crafted_out_of_bounds_branch_is_flagged() {
    // One jump opcode (0x12) targeting beyond the total chunk
    // size. The validator should report exactly one
    // BranchTargetOutOfBounds error.
    let instrs = vec![Instruction {
        offset: 0,
        length: 3,
        opcode: 0x12,
        mnemonic: Some(Cow::Borrowed("gpl jump")),
        params: vec![vec![Expression::Immediate14 { value: 0x300 }]],
        best_effort: false,
        string_run: None,
        raw_tail: None,
    }];
    let result = DisasmResult {
        instructions: instrs,
        bytes_consumed: 3,
        total_bytes: 0x100,
        aligned: true,
        cfg: None,
        cross_chunk_calls: Vec::new(),
    };
    let report = validate(&result);
    assert_eq!(report.len(), 1);
    assert!(matches!(
        report.errors[0],
        ValidationError::BranchTargetOutOfBounds {
            offset: 0,
            opcode: 0x12,
            target: 0x300,
            total_bytes: 0x100,
            ..
        }
    ));
}
