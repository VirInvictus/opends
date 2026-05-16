//! Text-mode round-trip: every aligned, non-Search GPL/MAS
//! chunk in DS1+DS2 GPLDATA goes through:
//!     bytes -> disassemble -> render text -> parse -> encode
//! and the final bytes are asserted byte-identical against the
//! original. Search-containing chunks are skipped: the v0.2.0
//! text format doesn't preserve `raw_tail`.

use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use gpl_asm::{encode, parse};
use gpl_disasm::{Expression, Instruction, disassemble};

const CORPUS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/GPLDATA.GFF",
];

fn is_script(kind: FourCC) -> bool {
    matches!(kind.as_bytes(), b"GPL " | b"MAS ")
}

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

/// Render the disassembly to text using the same `Instruction::Display`
/// implementation that `gpl-disasm` uses with `--no-labels`. One line
/// per instruction.
fn render_text(result: &gpl_disasm::DisasmResult) -> String {
    let mut out = String::new();
    for instr in &result.instructions {
        out.push_str(&format!("{instr}"));
        out.push('\n');
    }
    out
}

#[test]
fn every_aligned_chunk_roundtrips_through_text() {
    let mut tested = 0usize;
    let mut roundtripped = 0usize;
    let mut mismatched = 0usize;
    let mut parse_failures: Vec<(String, String)> = Vec::new();
    let mut encode_failures: Vec<(String, String)> = Vec::new();
    let mut mismatch_samples: Vec<String> = Vec::new();
    let mut skipped_search = 0usize;
    let mut skipped_unaligned = 0usize;

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
            if result.instructions.iter().any(contains_search) {
                skipped_search += 1;
                continue;
            }
            let text = render_text(&result);
            let chunk_id = format!(
                "{}{}:{}-{}",
                path,
                "",
                String::from_utf8_lossy(c.kind.as_bytes()).trim_end(),
                c.id
            );
            let parsed = match parse(&text) {
                Ok(r) => r,
                Err(e) => {
                    parse_failures.push((chunk_id.clone(), e.to_string()));
                    continue;
                }
            };
            match encode(&parsed) {
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
                                "{chunk_id}: src_len={} enc_len={} first_diff@{:#x}",
                                src.len(),
                                encoded.len(),
                                first_diff,
                            ));
                        }
                    }
                }
                Err(e) => {
                    encode_failures.push((chunk_id, e.to_string()));
                }
            }
        }
    }

    eprintln!(
        "gpl-asm text-roundtrip: tested={tested} roundtripped={roundtripped} \
         mismatched={mismatched} parse_failures={} encode_failures={} \
         search_skipped={skipped_search} unaligned_skipped={skipped_unaligned}",
        parse_failures.len(),
        encode_failures.len()
    );
    for s in &mismatch_samples {
        eprintln!("  mismatch: {s}");
    }
    for (chunk, err) in parse_failures.iter().take(10) {
        eprintln!("  parse-fail [{chunk}]: {err}");
    }
    for (chunk, err) in encode_failures.iter().take(10) {
        eprintln!("  encode-fail [{chunk}]: {err}");
    }
    if !Path::new(CORPUS[0]).is_file() {
        return;
    }
    assert!(tested > 0);
    assert_eq!(
        mismatched, 0,
        "{mismatched} chunks did not round-trip byte-identical"
    );
    assert!(
        parse_failures.is_empty(),
        "{} chunks failed to parse",
        parse_failures.len()
    );
    assert!(
        encode_failures.is_empty(),
        "{} chunks failed to encode after parse",
        encode_failures.len()
    );
}
