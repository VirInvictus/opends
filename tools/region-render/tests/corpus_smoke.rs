//! Corpus smoke test: render every `RGN*.GFF` in DS1 and DS2
//! into a palette-indexed buffer. Asserts no panic, that the
//! buffer length is exactly `REGION_PIXEL_WIDTH *
//! REGION_PIXEL_HEIGHT`, and reports aggregate missing-tile and
//! decode-failure counts.
//!
//! Skipped silently when the `.games/` corpus isn't on disk
//! (CI / fresh clone) — same shape as the image-extract corpus
//! smoke test.

use std::path::{Path, PathBuf};

use gff_edit::{FourCC, Gff};
use image_extract::Palette;
use region_render::{
    REGION_PIXEL_HEIGHT, REGION_PIXEL_WIDTH, RegionMap, inline_palette,
};

const CORPUS_ROOTS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1",
    "/home/bdkl/.gitrepos/opends/.games/ds2",
];

fn collect_region_gffs(dir: &Path) -> Vec<PathBuf> {
    let Ok(read_dir) = std::fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut out: Vec<PathBuf> = Vec::new();
    for entry in read_dir.flatten() {
        let p = entry.path();
        let name = p
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_ascii_uppercase();
        if name.starts_with("RGN") && name.ends_with(".GFF") {
            out.push(p);
        }
    }
    out.sort();
    out
}

fn fallback_palette(region_path: &Path) -> Option<Palette> {
    let mut sibling = region_path.to_path_buf();
    sibling.set_file_name("RESOURCE.GFF");
    if !sibling.is_file() {
        return None;
    }
    let gff = Gff::open(&sibling).ok()?;
    let bytes = gff.read(FourCC(*b"PAL "), 1000)?;
    Palette::from_bytes(bytes).ok()
}

#[test]
fn every_region_renders_clean() {
    let mut total_regions = 0usize;
    let mut total_missing_bytes: u64 = 0;
    let mut total_decode_failures = 0usize;
    let mut regions_with_misses = 0usize;
    let mut regions_with_decode_fails = 0usize;
    let mut skipped_no_palette = 0usize;

    for root in CORPUS_ROOTS {
        let root_path = Path::new(root);
        if !root_path.is_dir() {
            continue;
        }
        for region_path in collect_region_gffs(root_path) {
            let gff = Gff::open(&region_path)
                .unwrap_or_else(|e| panic!("opening {}: {e}", region_path.display()));

            let palette = match inline_palette(&gff) {
                Ok(Some(p)) => p,
                Ok(None) => match fallback_palette(&region_path) {
                    Some(p) => p,
                    None => {
                        skipped_no_palette += 1;
                        continue;
                    }
                },
                Err(e) => panic!("scanning palette in {}: {e}", region_path.display()),
            };

            let region = RegionMap::from_gff(&gff, palette).unwrap_or_else(|e| {
                panic!("RegionMap::from_gff({}): {e}", region_path.display())
            });
            let pixels = region.render_indexed();
            assert_eq!(
                pixels.len(),
                REGION_PIXEL_WIDTH * REGION_PIXEL_HEIGHT,
                "{} has wrong rendered pixel count",
                region_path.display()
            );

            total_regions += 1;
            total_missing_bytes += region.missing_tile_byte_count as u64;
            total_decode_failures += region.tile_decode_failures.len();
            if region.missing_tile_byte_count > 0 {
                regions_with_misses += 1;
            }
            if !region.tile_decode_failures.is_empty() {
                regions_with_decode_fails += 1;
            }
        }
    }

    eprintln!(
        "region-render corpus: {total_regions} regions rendered, \
         {total_missing_bytes} missing-tile bytes \
         ({regions_with_misses} regions affected), \
         {total_decode_failures} TILE decode failures \
         ({regions_with_decode_fails} regions affected), \
         {skipped_no_palette} regions skipped (no palette source)"
    );
    // We expect the in-tree corpus to give us non-zero rendered
    // regions when .games/ exists. CI without .games/ skips here.
    if Path::new(CORPUS_ROOTS[0]).is_dir() {
        assert!(total_regions > 0, "no regions rendered from on-disk corpus");
    }
}
