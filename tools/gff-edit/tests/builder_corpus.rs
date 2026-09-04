//! Builder corpus round-trip.
//!
//! For every GFF under the developer's pristine innoextract +
//! deployed Wine install paths that consists *only* of indexed
//! types (no segmented), parse it, feed the chunks back into
//! [`gff_edit::GffBuilder`], rebuild, re-parse, and verify the
//! reparsed GFF has the same chunks (kind / id / payload bytes)
//! as the original.
//!
//! Byte-identical rebuild is **not** the goal here: existing
//! GFFs are not in a single canonical byte layout (types-list
//! ordering, dead space from prior edits, free-list shape all
//! vary across the corpus), so the test asserts *structural*
//! equivalence at the chunk level instead.
//!
//! Files with one or more segmented types are silently skipped
//! (segmented build is v0.6.0+). The test reports the
//! indexed-only vs skipped split via stderr so a regression
//! in segmented-recognition is observable.

use std::fs;
use std::path::{Path, PathBuf};

use gff_edit::{Gff, builder_from_gff};

/// Corpus roots: the in-tree innoextract trees, plus the recovery
/// installs under $HOME/.wine (absent on other machines, where those
/// two entries simply skip).
fn corpus_dirs() -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = ["ds1", "ds2"]
        .iter()
        .map(|g| Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.games").join(g))
        .collect();
    if let Some(home) = std::env::var_os("HOME") {
        let home = PathBuf::from(home);
        dirs.push(home.join(".wine/drive_c/GOG Games/Dark Sun"));
        dirs.push(home.join(".wine/drive_c/GOG Games/Dark Sun 2"));
    }
    dirs
}

fn gff_files(dir: &Path) -> Vec<PathBuf> {
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for entry in entries.flatten() {
        let p = entry.path();
        if p.is_file() && p.extension().is_some_and(|e| e.eq_ignore_ascii_case("gff")) {
            out.push(p);
        }
    }
    out
}

#[test]
fn builder_round_trip_preserves_chunks() {
    let mut tested = 0usize;
    let mut skipped_segmented = 0usize;
    let mut failed: Vec<String> = Vec::new();

    // Skip when the corpus is absent (CI / fresh clone), matching the gpl-asm
    // corpus tests.
    if corpus_dirs()
        .iter()
        .all(|d| gff_files(d).is_empty())
    {
        eprintln!("skipping builder corpus: no GFFs under the corpus dirs (.games absent)");
        return;
    }

    for dir in corpus_dirs() {
        for path in gff_files(&dir) {
            let bytes = fs::read(&path).expect("read");
            let gff = Gff::from_bytes(bytes).expect("parse");
            let Some(b) = builder_from_gff(&gff) else {
                skipped_segmented += 1;
                continue;
            };
            let rebuilt_bytes = b.build().expect("build");
            let rebuilt = match Gff::from_bytes(rebuilt_bytes) {
                Ok(g) => g,
                Err(e) => {
                    failed.push(format!("{}: rebuild reparse failed: {e}", path.display()));
                    continue;
                }
            };

            if gff.chunks().len() != rebuilt.chunks().len() {
                failed.push(format!(
                    "{}: chunk count differs: original={}, rebuilt={}",
                    path.display(),
                    gff.chunks().len(),
                    rebuilt.chunks().len()
                ));
                continue;
            }

            let mut mismatch_in_file = false;
            for (a, b) in gff.chunks().iter().zip(rebuilt.chunks().iter()) {
                if a.kind != b.kind || a.id != b.id {
                    failed.push(format!(
                        "{}: chunk metadata differs: original ({},{}) vs rebuilt ({},{})",
                        path.display(),
                        a.kind,
                        a.id,
                        b.kind,
                        b.id
                    ));
                    mismatch_in_file = true;
                    break;
                }
                if gff.read_chunk(a) != rebuilt.read_chunk(b) {
                    failed.push(format!(
                        "{}: payload differs for ({},{})",
                        path.display(),
                        a.kind,
                        a.id
                    ));
                    mismatch_in_file = true;
                    break;
                }
            }
            if !mismatch_in_file {
                tested += 1;
            }
        }
    }

    assert!(
        tested + skipped_segmented > 0,
        "no corpus GFFs found; check the corpus dirs"
    );
    assert!(
        failed.is_empty(),
        "builder round-trip failed in {} files: {:#?}",
        failed.len(),
        failed
    );
    eprintln!(
        "builder round-trip verified structural equivalence on {tested} \
         indexed-only GFFs; {skipped_segmented} segmented-type GFFs \
         skipped (segmented build is v0.6.0+)"
    );
}
