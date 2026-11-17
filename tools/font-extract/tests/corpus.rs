//! Corpus round-trip: parse every shipped FONT chunk, rebuild it,
//! and require byte identity. Also pins the shipped fonts' shape
//! (256 glyphs, height 9, strictly increasing offsets). Paths
//! resolve from the checkout root; CI skips when `.games/` is
//! absent, matching the other corpus tests.

use std::path::{Path, PathBuf};

use font_extract::parse;
use gff_edit::{FourCC, Gff};

fn corpus() -> Vec<PathBuf> {
    ["ds1/RESOURCE.GFF", "ds2/RESOURCE.GFF"]
        .iter()
        .map(|rel| {
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../.games")
                .join(rel)
        })
        .collect()
}

#[test]
fn shipped_fonts_round_trip_byte_identical() {
    let corpus = corpus();
    if corpus.iter().all(|p| !p.is_file()) {
        eprintln!("skipping font corpus test: no RESOURCE.GFF found (.games absent)");
        return;
    }

    let mut checked = 0usize;
    for path in &corpus {
        if !path.is_file() {
            continue;
        }
        let bytes = fs_err(path);
        let gff =
            Gff::from_bytes(bytes.clone()).unwrap_or_else(|e| panic!("parsing {path:?}: {e}"));
        let chunk = gff
            .chunks()
            .iter()
            .find(|c| c.kind == FourCC(*b"FONT") && c.id == 100)
            .unwrap_or_else(|| panic!("{path:?}: no FONT 100"));
        let body = gff.read_chunk(chunk);

        let font = parse(body).unwrap_or_else(|e| panic!("{path:?}: {e}"));
        assert_eq!(font.glyphs.len(), 256, "{path:?}: glyph count");
        for glyph in &font.glyphs {
            assert_eq!(glyph.pixels.len(), glyph.width * 9);
        }

        let rebuilt = font_extract::build(&font).expect("build");
        assert_eq!(
            rebuilt, body,
            "{path:?}: rebuild differs from the shipped chunk"
        );
        checked += 1;
    }
    assert!(checked > 0, "no FONT chunks found in the corpus");
}

fn fs_err(path: &Path) -> Vec<u8> {
    std::fs::read(path).unwrap_or_else(|e| panic!("reading {path:?}: {e}"))
}
