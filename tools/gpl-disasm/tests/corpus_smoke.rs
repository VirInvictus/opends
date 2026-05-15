//! Corpus smoke test: disassemble every `GPL ` and `MAS ` chunk
//! across DS1 and DS2 `GPLDATA.GFF`. v0.2.0 tracks two metrics:
//!
//! 1. **Total bytes consumed**: every byte of every chunk should
//!    be accounted for. We assert `bytes_consumed == total_bytes`
//!    when the chunk aligns; otherwise the misalignment is
//!    bounded by best-effort skipping.
//! 2. **Aligned percentage**: fraction of chunks where
//!    `aligned == true` (no `best_effort` instruction encountered,
//!    full byte coverage). pick-it-up.md targets `>= 95%`.
//!
//! Paths are hardcoded to Brandon's pristine innoextract trees.

use std::fs;
use std::path::Path;

use std::collections::BTreeSet;

use gff_edit::{FourCC, Gff};
use gpl_disasm::disassemble;

const CORPUS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/GPLDATA.GFF",
];

#[test]
fn every_gpl_and_mas_chunk_disassembles() {
    let mut total_chunks = 0usize;
    let mut aligned_chunks = 0usize;
    let mut total_bytes = 0usize;
    let mut total_consumed = 0usize;
    let mut total_instructions = 0usize;

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
            let result = disassemble(chunk_bytes);

            // Every byte must be accounted for: linear scan always
            // consumes the whole chunk (best-effort instructions
            // consume only their opcode byte, but the loop keeps
            // scanning).
            assert_eq!(
                result.bytes_consumed,
                chunk_bytes.len(),
                "bytes_consumed != len for {}:{}-{} ({} consumed, {} bytes)",
                path,
                c.kind,
                c.id,
                result.bytes_consumed,
                chunk_bytes.len()
            );

            total_chunks += 1;
            total_bytes += chunk_bytes.len();
            total_consumed += result.bytes_consumed;
            total_instructions += result.instructions.len();
            if result.aligned {
                aligned_chunks += 1;
            }
        }
    }

    assert!(total_chunks > 0, "no GPL/MAS chunks found; check CORPUS paths");
    let aligned_pct = (aligned_chunks as f64 / total_chunks as f64) * 100.0;
    eprintln!(
        "disassembled {total_chunks} GPL/MAS chunks ({aligned_chunks} aligned, {aligned_pct:.1}%); \
         {total_bytes} input bytes -> {total_instructions} instructions ({total_consumed} bytes consumed)"
    );
    // We don't enforce the 95% threshold yet — v0.2.0's deferred
    // cases (RETVAL, COMPLEX, custom handlers) may bring the
    // percentage lower than target. Document the measurement, fix
    // in v0.2.1.
}

/// v0.3.0: for every aligned chunk, every CFG successor offset must
/// resolve to a known instruction boundary OR to the chunk's end
/// (i.e., `total_bytes`). Misses indicate a branch instruction
/// whose target falls between two instructions, which would mean
/// either our instruction-boundary alignment is wrong or the
/// branch-target semantics differ from those in
/// `docs/gpl-bytecode.md` §5a.
#[test]
fn every_cfg_successor_resolves_to_instruction_boundary() {
    let mut total_chunks = 0usize;
    let mut total_edges = 0usize;
    let mut unresolved_count = 0usize;
    let mut cross_chunk_calls = 0usize;

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
            let result = disassemble(chunk_bytes);
            let Some(cfg) = &result.cfg else {
                continue;
            };

            let boundaries: BTreeSet<usize> = result
                .instructions
                .iter()
                .map(|i| i.offset)
                .chain(std::iter::once(result.total_bytes))
                .collect();

            total_chunks += 1;
            cross_chunk_calls += result.cross_chunk_calls.len();
            unresolved_count += cfg.unresolved.len();

            for block in &cfg.blocks {
                for edge in &block.successors {
                    total_edges += 1;
                    assert!(
                        boundaries.contains(&edge.target_offset),
                        "{}:{}-{}: edge from block 0x{:x} to offset 0x{:x} doesn't land \
                         on an instruction boundary (chunk_len=0x{:x})",
                        path,
                        c.kind,
                        c.id,
                        block.start_offset,
                        edge.target_offset,
                        result.total_bytes
                    );
                }
            }
        }
    }

    assert!(total_chunks > 0, "no aligned GPL/MAS chunks; check CORPUS paths");
    eprintln!(
        "CFG soundness: {total_chunks} aligned chunks, {total_edges} edges resolved, \
         {cross_chunk_calls} global-sub call sites recorded, {unresolved_count} computed-target edges"
    );
}
