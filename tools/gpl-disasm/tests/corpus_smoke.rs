//! Corpus smoke test: disassemble every `GPL ` and `MAS ` chunk
//! across DS1 and DS2 `GPLDATA.GFF`. v0.1.0 emits one annotation
//! per input byte, so success = "doesn't panic and produces the
//! right number of rows."
//!
//! Paths are hardcoded to Brandon's pristine innoextract trees.

use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use gpl_disasm::disassemble;

const CORPUS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/GPLDATA.GFF",
];

#[test]
fn every_gpl_and_mas_chunk_disassembles() {
    let mut total_chunks = 0usize;
    let mut total_bytes = 0usize;
    let mut total_rows = 0usize;

    for path in CORPUS {
        let p = Path::new(path);
        if !p.is_file() {
            continue;
        }
        let bytes = fs::read(p).unwrap_or_else(|e| panic!("reading {path}: {e}"));
        let gff = Gff::from_bytes(bytes).unwrap_or_else(|e| panic!("parsing {path}: {e}"));

        for c in gff.chunks() {
            if c.kind != FourCC(*b"GPL ") && c.kind != FourCC(*b"MAS ") {
                continue;
            }
            let chunk_bytes = gff.read_chunk(c);
            let anns = disassemble(chunk_bytes);
            assert_eq!(
                anns.len(),
                chunk_bytes.len(),
                "annotation count mismatch for {}:{}-{} ({} bytes, {} annotations)",
                path,
                c.kind,
                c.id,
                chunk_bytes.len(),
                anns.len()
            );
            total_chunks += 1;
            total_bytes += chunk_bytes.len();
            total_rows += anns.len();
        }
    }

    assert!(total_chunks > 0, "no GPL/MAS chunks found; check CORPUS paths");
    eprintln!(
        "disassembled {total_chunks} GPL/MAS chunks; {total_bytes} input bytes, {total_rows} rows"
    );
}
