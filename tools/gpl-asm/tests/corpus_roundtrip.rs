//! Corpus round-trip: every aligned GPL/MAS chunk in DS1+DS2
//! GPLDATA.GFF runs through `disassemble -> encode` and the
//! result is asserted byte-identical against the source chunk.
//!
//! Skipped silently when `.games/` is absent (CI / fresh clone),
//! same shape as the other crates' corpus smoke tests.

use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use gpl_asm::{encode, EncodeError};
use gpl_disasm::disassemble;

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
                                "{}:{}{}: src_len={} enc_len={} first_diff@{:#x}",
                                path,
                                String::from_utf8_lossy(c.kind.as_bytes()).trim_end(),
                                c.id,
                                src.len(),
                                encoded.len(),
                                first_diff,
                            ));
                        }
                    }
                }
                Err(EncodeError::UnsupportedOpcode { reason, .. }) if reason.contains("Custom") => {
                    skipped_custom += 1;
                }
                Err(e) => {
                    encode_failures.push((
                        format!(
                            "{}:{}{}",
                            path,
                            String::from_utf8_lossy(c.kind.as_bytes()).trim_end(),
                            c.id
                        ),
                        e,
                    ));
                }
            }
        }
    }

    eprintln!(
        "gpl-asm corpus: tested={tested} roundtripped={roundtripped} mismatched={mismatched} \
         unaligned_skipped={skipped_unaligned} custom_skipped={skipped_custom} \
         encode_failures={}",
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
