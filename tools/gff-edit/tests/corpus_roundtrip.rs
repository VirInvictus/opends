//! Corpus round-trip: for every GFF we can find under the developer's
//! pristine innoextract and deployed Wine install paths, perform a
//! no-op replace of the first chunk and verify the resulting file is
//! byte-identical to the input.
//!
//! Paths are hardcoded to Brandon's machine layout. The test gracefully
//! reports "no GFFs found" rather than silently passing if the corpus
//! is missing.

use std::fs;
use std::path::{Path, PathBuf};

use gff_edit::Gff;

const CORPUS_DIRS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1",
    "/home/bdkl/.gitrepos/opends/.games/ds2",
    "/home/bdkl/.wine/drive_c/GOG Games/Dark Sun",
    "/home/bdkl/.wine/drive_c/GOG Games/Dark Sun 2",
];

fn gff_files(dir: &Path) -> Vec<PathBuf> {
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for entry in entries.flatten() {
        let p = entry.path();
        if p.is_file()
            && p.extension()
                .is_some_and(|e| e.eq_ignore_ascii_case("gff"))
        {
            out.push(p);
        }
    }
    out
}

#[test]
fn no_op_replace_preserves_bytes() {
    let mut tested = 0usize;
    let mut failed: Vec<String> = Vec::new();
    for dir in CORPUS_DIRS {
        for path in gff_files(Path::new(dir)) {
            let original = fs::read(&path).expect("read");
            let gff = Gff::from_bytes(original.clone()).expect("parse");
            let Some(chunk) = gff.chunks().first() else {
                continue;
            };
            let same: Vec<u8> = gff.read_chunk(chunk).to_vec();
            let kind = chunk.kind;
            let id = chunk.id;
            let new = gff.replace_chunk(kind, id, &same).expect("replace");
            if new != original {
                failed.push(path.display().to_string());
            }
            tested += 1;
        }
    }
    assert!(tested > 0, "no corpus GFFs found; check CORPUS_DIRS");
    assert!(
        failed.is_empty(),
        "no-op replace mutated bytes in {} files: {:#?}",
        failed.len(),
        failed
    );
    eprintln!("no-op replace verified byte-identical on {tested} GFFs");
}
