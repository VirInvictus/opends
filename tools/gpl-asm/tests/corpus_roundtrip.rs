//! Corpus round-trip: every aligned GPL/MAS chunk in DS1+DS2
//! GPLDATA.GFF runs through `disassemble -> encode` and the
//! result is asserted byte-identical against the source chunk.
//!
//! Skipped silently when `.games/` is absent (CI / fresh clone),
//! same shape as the other crates' corpus smoke tests.

use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use gpl_asm::{EncodeError, encode};
use gpl_disasm::{Expression, Instruction, disassemble};

/// Returns true if `instr` is a `gpl_search` (0x33) call or
/// contains one nested inside a `GPL_RETVAL`. Search has side
/// bytes that the v0.4.3 disassembly IR doesn't capture, so the
/// encoder can't reproduce its bytes. Tracked as v0.1.x work.
fn contains_search(instr: &Instruction) -> bool {
    if instr.opcode == 0x33 {
        return true;
    }
    for param in &instr.params {
        if param_contains_search(param) {
            return true;
        }
    }
    false
}

fn param_contains_search(tokens: &[Expression]) -> bool {
    for tok in tokens {
        if let Expression::RetVal {
            inner_opcode,
            inner_params,
            ..
        } = tok
        {
            if *inner_opcode == 0x33 {
                return true;
            }
            for ip in inner_params {
                if param_contains_search(ip) {
                    return true;
                }
            }
        }
    }
    false
}

const CORPUS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/GPLDATA.GFF",
];

fn is_script(kind: FourCC) -> bool {
    matches!(kind.as_bytes(), b"GPL " | b"MAS ")
}

#[test]
fn every_aligned_gpl_chunk_roundtrips_byte_identical() {
    let mut tested = 0usize;
    let mut roundtripped = 0usize;
    let mut mismatched = 0usize;
    let mut encode_failures: Vec<(String, EncodeError)> = Vec::new();
    let mut mismatch_samples: Vec<String> = Vec::new();
    let mut skipped_unaligned = 0usize;
    let mut skipped_search = 0usize;
    let mut skipped_custom = 0usize;

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
            tested += 1;
            let src = gff.read_chunk(c);
            let result = disassemble(src);
            if !result.aligned {
                skipped_unaligned += 1;
                continue;
            }
            // Skip chunks containing gpl_search (0x33) anywhere
            // (top-level OR nested inside GPL_RETVAL) until
            // v0.1.x adds a preservation field for its side bytes.
            if result.instructions.iter().any(contains_search) {
                skipped_search += 1;
                continue;
            }
            match encode(&result) {
                Ok(encoded) => {
                    if encoded == src {
                        roundtripped += 1;
                    } else {
                        mismatched += 1;
                        if mismatch_samples.len() < 5 {
                            let first_diff = src
                                .iter()
                                .zip(encoded.iter())
                                .position(|(a, b)| a != b)
                                .unwrap_or(src.len().min(encoded.len()));
                            mismatch_samples.push(format!(
                                "{}{}: src_len={} enc_len={} first_diff@{:#x}",
                                path,
                                format!(":{}{}", String::from_utf8_lossy(c.kind.as_bytes()).trim_end(), c.id),
                                src.len(),
                                encoded.len(),
                                first_diff,
                            ));
                        }
                    }
                }
                Err(EncodeError::UnsupportedOpcode { reason, .. })
                    if reason.contains("Custom") =>
                {
                    skipped_custom += 1;
                }
                Err(e) => {
                    encode_failures.push((
                        format!(
                            "{}{}",
                            path,
                            format!(
                                ":{}{}",
                                String::from_utf8_lossy(c.kind.as_bytes()).trim_end(),
                                c.id
                            )
                        ),
                        e,
                    ));
                }
            }
        }
    }

    eprintln!(
        "gpl-asm corpus: tested={tested} roundtripped={roundtripped} mismatched={mismatched} \
         unaligned_skipped={skipped_unaligned} search_skipped={skipped_search} \
         custom_skipped={skipped_custom} encode_failures={}",
        encode_failures.len()
    );
    for s in &mismatch_samples {
        eprintln!("  mismatch: {s}");
    }
    for (chunk, err) in encode_failures.iter().take(10) {
        eprintln!("  encode-fail [{chunk}]: {err}");
    }
    if !Path::new(CORPUS[0]).is_file() {
        // Corpus not on disk; nothing to assert.
        return;
    }
    assert!(tested > 0, "no chunks tested");
    assert_eq!(
        mismatched, 0,
        "{mismatched} chunks did not round-trip byte-identical"
    );
    assert!(
        encode_failures.is_empty(),
        "{} chunks failed to encode",
        encode_failures.len()
    );
}
