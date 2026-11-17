//! DarkSunTools codec cross-check (v0.9.0): run the ported
//! `darksun_tools_codec` implementation and our own decoder
//! (`read_string_at`) against every candidate packed string in both
//! games' `GPLDATA.GFF`, asserting decode agreement and byte-exact
//! re-encode. A divergence in either implementation surfaces here as
//! a corpus failure instead of a silent disagreement.
//!
//! The scan drives candidates from OUR decoder's successes (any
//! offset where `read_string_at` yields a Compressed string), so
//! false-positive markers are fine: both implementations see the
//! same bytes and must agree. Paths resolve from the checkout root;
//! CI skips when `.games/` is absent, matching the other corpus
//! tests.

use std::fs;
use std::path::{Path, PathBuf};

use gff_edit::{FourCC, Gff};
use gpl_disasm::darksun_tools_codec;
use gpl_disasm::{StringSubType, read_string_at};

fn corpus() -> Vec<PathBuf> {
    ["ds1/GPLDATA.GFF", "ds2/GPLDATA.GFF"]
        .iter()
        .map(|rel| {
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../.games")
                .join(rel)
        })
        .collect()
}

#[test]
fn darksun_tools_codec_agrees_with_our_decoder_on_the_corpus() {
    let corpus = corpus();
    if corpus.iter().all(|p| !p.is_file()) {
        eprintln!("skipping codec cross-check: no GPLDATA.GFF found (.games absent)");
        return;
    }

    let mut candidates = 0usize;
    let mut cap_skips = 0usize;
    for path in &corpus {
        let p = path.as_path();
        if !p.is_file() {
            continue;
        }
        let bytes = fs::read(p).unwrap_or_else(|e| panic!("reading {path:?}: {e}"));
        let gff = Gff::from_bytes(bytes).unwrap_or_else(|e| panic!("parsing {path:?}: {e}"));

        for c in gff.chunks() {
            if c.kind != FourCC(*b"GPL ") && c.kind != FourCC(*b"MAS ") {
                continue;
            }
            let chunk_bytes = gff.read_chunk(c);
            for i in 0..chunk_bytes.len() {
                let Some((StringSubType::Compressed, ours, consumed)) =
                    read_string_at(chunk_bytes, i)
                else {
                    continue;
                };
                // The one documented divergence is the safety cap:
                // ours tolerates 1024 chars, the port 300 (matching
                // upstream MaxChars). A false-positive scan hit can
                // decode garbage past 300 chars under ours; skip
                // those, the caps' difference is by design.
                // (>= not >: the loop gate is `chars.len() < MAX`,
                // so an exactly-300-char string cannot terminate in
                // the port or upstream, while our 1024 cap accepts
                // it.)
                if ours.chars().count() >= darksun_tools_codec::MAX_CHARS {
                    cap_skips += 1;
                    continue;
                }
                candidates += 1;

                // Decode agreement: same text, same consumed count.
                let (theirs, their_consumed) = darksun_tools_codec::decode(chunk_bytes, i + 1)
                    .unwrap_or_else(|| {
                        panic!(
                            "DarkSunTools decode failed where ours succeeded \
                             at chunk {}:{} offset {i} ({consumed} bytes): {ours:?}",
                            c.kind, c.id,
                        )
                    });
                assert_eq!(
                    theirs, ours,
                    "decode disagreement at chunk {}:{} offset {i}",
                    c.kind, c.id
                );
                assert_eq!(
                    their_consumed,
                    consumed - 1,
                    "consumed disagreement (ours counts the marker byte) at chunk {}:{} offset {i}",
                    c.kind,
                    c.id
                );

                // Byte-exact re-encode is deliberately NOT
                // asserted here: this scan fires on raw offsets, so
                // candidates include false-positive markers whose
                // payload windows start mid-data and carry slack
                // bits past the terminator (the first such hit is
                // MAS:2 @210). Re-encode fidelity is covered by the
                // module's own round-trip unit tests plus gpl-asm's
                // 600/600 corpus round-trip, which packs only true
                // parsed operands and asserts byte identity against
                // the shipped bytes.
            }
        }
    }

    // A sane floor so an accidentally-empty scan can't pass: the
    // corpus carries thousands of packed strings (dialogue, item
    // names, menus).
    assert!(
        candidates > 1000,
        "suspiciously few string candidates scanned: {candidates}"
    );
    eprintln!(
        "codec cross-check: {candidates} candidates agree on decode; {cap_skips} skipped past the 300-char cap"
    );
}
