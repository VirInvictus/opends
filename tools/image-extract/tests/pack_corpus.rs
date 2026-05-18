//! Pack-corpus property test (v0.4.0): for every DS1 RLE frame in
//! the corpus that decodes cleanly, re-encode through
//! `encode_bitmap_rle` and decode again. Assert the second decode is
//! pixel-identical to the first.
//!
//! The encoder doesn't have to produce the *original* bytes (a real
//! game-shipped chunk uses libgff's own encoder choices, including
//! span splits and PLNR / PLAN formats). It does have to produce
//! bytes the decoder reads as the same image. This test is the
//! safety net.
//!
//! PLNR and PLAN frames are skipped; v0.4.0 only ships an RLE
//! encoder (per the encode_bitmap_rle doc).

use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use image_extract::{Bitmap, FrameType, encode_bitmap_rle};

const CORPUS: &[&str] = &[
    "/home/bdkl/.gitrepos/opends/.games/ds1/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds1/RESOURCE.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/GPLDATA.GFF",
    "/home/bdkl/.gitrepos/opends/.games/ds2/RESOURCE.GFF",
];

fn is_bitmap(kind: FourCC) -> bool {
    matches!(
        kind.as_bytes(),
        b"BMP " | b"PORT" | b"ICON" | b"BMAP" | b"OMAP" | b"TILE"
    )
}

#[test]
fn every_ds1_rle_frame_packs_unpacks_pixel_identical() {
    let mut total_frames = 0usize;
    let mut roundtripped = 0usize;
    let mut skipped_plnr = 0usize;
    let mut skipped_plan = 0usize;
    let mut skipped_other = 0usize;
    let mut decode_errors = 0usize;
    let mut failures: Vec<String> = Vec::new();

    for path in CORPUS {
        let p = Path::new(path);
        if !p.is_file() {
            continue;
        }
        let bytes = fs::read(p).unwrap_or_else(|e| panic!("reading {path}: {e}"));
        let gff = Gff::from_bytes(bytes).unwrap_or_else(|e| panic!("parsing {path}: {e}"));

        for c in gff.chunks() {
            if !is_bitmap(c.kind) {
                continue;
            }
            let chunk_bytes = gff.read_chunk(c);
            let bmp = match Bitmap::from_bytes(chunk_bytes) {
                Ok(b) => b,
                Err(_) => continue,
            };
            for frame_id in 0..bmp.frame_count as usize {
                let original = match bmp.decode_frame(frame_id) {
                    Ok(f) => f,
                    Err(_) => {
                        decode_errors += 1;
                        continue;
                    }
                };
                total_frames += 1;
                match original.frame_type {
                    FrameType::Ds1Rle => {}
                    FrameType::Plnr => {
                        skipped_plnr += 1;
                        continue;
                    }
                    FrameType::Plan => {
                        skipped_plan += 1;
                        continue;
                    }
                    FrameType::Unknown(_) => {
                        skipped_other += 1;
                        continue;
                    }
                }

                // Round-trip: encode_bitmap_rle wraps the single
                // frame in a fresh chunk; re-parse and decode the
                // same frame.
                let packed = match encode_bitmap_rle(std::slice::from_ref(&original)) {
                    Ok(b) => b,
                    Err(e) => {
                        failures.push(format!(
                            "{path}:{:?}/{} frame {}: encode failed: {}",
                            c.kind,
                            c.id,
                            frame_id,
                            e
                        ));
                        continue;
                    }
                };
                let repacked = match Bitmap::from_bytes(&packed) {
                    Ok(b) => b,
                    Err(e) => {
                        failures.push(format!(
                            "{path}:{:?}/{} frame {}: re-parse failed: {}",
                            c.kind,
                            c.id,
                            frame_id,
                            e
                        ));
                        continue;
                    }
                };
                let redecoded = match repacked.decode_frame(0) {
                    Ok(f) => f,
                    Err(e) => {
                        failures.push(format!(
                            "{path}:{:?}/{} frame {}: re-decode failed: {}",
                            c.kind,
                            c.id,
                            frame_id,
                            e
                        ));
                        continue;
                    }
                };
                if redecoded.width != original.width
                    || redecoded.height != original.height
                    || redecoded.indices != original.indices
                {
                    failures.push(format!(
                        "{path}:{:?}/{} frame {}: pixel mismatch ({}x{} vs {}x{})",
                        c.kind,
                        c.id,
                        frame_id,
                        original.width,
                        original.height,
                        redecoded.width,
                        redecoded.height,
                    ));
                    continue;
                }
                roundtripped += 1;
            }
        }
    }

    eprintln!(
        "pack_corpus: total frames {} (ds1_rle round-tripped {}, plnr skipped {}, plan skipped {}, other skipped {}, decode errors {})",
        total_frames, roundtripped, skipped_plnr, skipped_plan, skipped_other, decode_errors,
    );
    if !failures.is_empty() {
        for f in failures.iter().take(20) {
            eprintln!("  FAIL: {f}");
        }
        panic!(
            "{} frames failed pack/unpack round-trip (first 20 above)",
            failures.len(),
        );
    }
    assert!(
        roundtripped > 0,
        "no DS1 RLE frames round-tripped (corpus missing?)"
    );
}
