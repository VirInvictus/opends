//! Corpus carve: run the flatten transform over the shipped DSUN.EXE
//! binaries and assert the documented totals (docs/overlay-formats.md
//! section 4: DS1 16,464 B = 8,232 entries; DS2 16,524 B = 8,262 entries;
//! zero overlay markers), then verify the output round-trips.
//!
//! Paths resolve from the checkout root (`CARGO_MANIFEST_DIR`/../..); the
//! tests skip cleanly when .games/ is absent, matching the other corpus
//! tests.

use std::path::{Path, PathBuf};

use ovr_carve::{DEFAULT_LOAD_SEGMENT, carve, fetch_map, verify};

fn game_exe(game: &str) -> Option<PathBuf> {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../.games")
        .join(game)
        .join("DSUN.EXE");
    path.is_file().then_some(path)
}

fn run_corpus(game: &str, expected_entries: u64) {
    let Some(exe) = game_exe(game) else {
        eprintln!("SKIP {game}: .games/{game}/DSUN.EXE not present");
        return;
    };
    let pristine = std::fs::read(&exe).expect("read DSUN.EXE");
    let map = fetch_map(
        &exe,
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("../ovr-map/ovr-map.py"),
    )
    .expect("ovr-map --json parses");

    let carved = carve(&pristine, &map, DEFAULT_LOAD_SEGMENT).expect("carve succeeds");
    assert_eq!(
        carved.stats.applied, expected_entries,
        "{game}: applied relocation count"
    );
    assert_eq!(
        carved.stats.markers, 0,
        "{game}: overlay markers (docs: bit0 never set)"
    );
    assert_eq!(
        carved.stats.tag_histogram.get(&0),
        Some(&expected_entries),
        "{game}: every stored word is tag 0"
    );
    assert_eq!(
        carved.stats.target_classes.values().sum::<u64>(),
        expected_entries,
        "{game}: class histogram sums to the applied total"
    );
    assert_eq!(
        carved.output.len(),
        pristine.len(),
        "{game}: length unchanged"
    );
    assert_eq!(
        carved.mapping.modules.len(),
        map.segments.iter().filter(|m| !m.empty).count(),
        "{game}: one mapping per live module"
    );
    verify(&pristine, &map, &carved.output, DEFAULT_LOAD_SEGMENT)
        .expect("{game}: verify accepts the carve's own output");

    // The two header words differ (page fields), everything else is either
    // pristine or a rewritten relocation word inside the overlay area.
    let header_end = map.mz.header_size as usize;
    let overlays_only: usize = carved
        .output
        .iter()
        .zip(&pristine)
        .skip(header_end)
        .filter(|(a, b)| a != b)
        .count();
    assert!(overlays_only > 0, "{game}: overlay words were rewritten");
    assert!(
        overlays_only <= 2 * expected_entries as usize,
        "{game}: overlay diff bytes within 2 per relocation"
    );
}

#[test]
fn corpus_ds1() {
    run_corpus("ds1", 8_232);
}

#[test]
fn corpus_ds2() {
    run_corpus("ds2", 8_262);
}
