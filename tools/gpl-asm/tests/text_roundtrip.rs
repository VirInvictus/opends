//! Text-mode round-trip: every aligned GPL/MAS chunk in
//! DS1+DS2 GPLDATA goes through:
//!     bytes -> disassemble -> render labelled text -> parse
//!         -> encode
//! and the final bytes are asserted byte-identical. v0.2.1
//! handles label declarations, label-form branch params, and
//! `; raw_tail=HEX` trailers, so Search-containing chunks
//! round-trip too. Target: 600/600.

use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use gpl_asm::{encode, parse};
use gpl_disasm::{disassemble, render_text};

const CORPUS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/GPLDATA.GFF",
];

fn is_script(kind: FourCC) -> bool {
    matches!(kind.as_bytes(), b"GPL " | b"MAS ")
}

#[test]
fn every_aligned_chunk_roundtrips_through_text() {
    let mut tested = 0usize;
    let mut roundtripped = 0usize;
    let mut mismatched = 0usize;
    let mut parse_failures: Vec<(String, String)> = Vec::new();
    let mut encode_failures: Vec<(String, String)> = Vec::new();
    let mut mismatch_samples: Vec<String> = Vec::new();
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
            let text = render_text(&result, true);
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
            // The parser's per-instruction length estimates must sum
            // to the true chunk size. Encoded-bytes equality below
            // can't catch estimate drift (encoding ignores the
            // estimates), and the debug_assert in encode() only
            // fires in debug builds; assert it here so release CI
            // catches it too.
            assert_eq!(
                parsed.total_bytes,
                src.len(),
                "parsed total_bytes disagrees with source length for {chunk_id}"
            );
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
         unaligned_skipped={skipped_unaligned}",
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
