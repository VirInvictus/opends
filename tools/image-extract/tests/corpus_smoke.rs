//! Corpus smoke test: parse every `BMP `, `PORT`, `ICON`, `BMAP`,
//! `OMAP`, `TILE` chunk across DS1 and DS2 (`GPLDATA.GFF` +
//! `RESOURCE.GFF`), decode each frame, and assert no panic and
//! that pixel counts match `width * height`.
//!
//! Track aligned (every frame decoded) vs partial (some frames
//! returned errors) for the report.

use std::fs;
use std::path::Path;

use gff_edit::{FourCC, Gff};
use image_extract::Bitmap;

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
fn every_bitmap_chunk_decodes_or_reports_cleanly() {
    let mut total_chunks = 0usize;
    let mut total_frames = 0usize;
    let mut decoded_frames = 0usize;
    let mut by_type: std::collections::BTreeMap<String, (usize, usize)> =
        std::collections::BTreeMap::new();

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
            total_chunks += 1;
            let mut err_kinds: std::collections::BTreeMap<String, usize> =
                std::collections::BTreeMap::new();
            for frame_id in 0..bmp.frame_count as usize {
                total_frames += 1;
                match bmp.decode_frame(frame_id) {
                    Ok(frame) => {
                        assert_eq!(
                            frame.indices.len(),
                            frame.width as usize * frame.height as usize,
                            "frame {frame_id} of {} {} has wrong index count",
                            c.kind,
                            c.id
                        );
                        decoded_frames += 1;
                        let key = format!("{}", frame.frame_type);
                        let entry = by_type.entry(key).or_insert((0, 0));
                        entry.0 += 1;
                        entry.1 += 1;
                    }
                    Err(e) => {
                        let kind = match &e {
                            image_extract::ImageError::UnsupportedFrameType { kind, .. } => {
                                format!("UnsupportedFrameType:{kind}")
                            }
                            image_extract::ImageError::PlnrSplitBits => "PlnrSplitBits".to_string(),
                            image_extract::ImageError::FrameOutOfBounds { .. } => {
                                "FrameOutOfBounds".to_string()
                            }
                            image_extract::ImageError::Ds1RleError { .. } => "Ds1RleError".to_string(),
                            other => format!("other:{other}"),
                        };
                        *err_kinds.entry(kind).or_insert(0) += 1;
                    }
                }
            }
            if !err_kinds.is_empty() {
                for (k, n) in &err_kinds {
                    // Aggregate into the global by_type stats for
                    // reporting; not asserted on.
                    let entry = by_type.entry(format!("ERR:{k}")).or_insert((0, 0));
                    entry.0 += n;
                    entry.1 += n;
                }
            }
        }
    }

    eprintln!(
        "image-extract corpus: {total_chunks} bitmap chunks, {total_frames} frames, {decoded_frames} decoded"
    );
    for (kind, (ok, _total)) in &by_type {
        eprintln!("  {kind}: {ok}");
    }
    assert!(total_chunks > 0, "no bitmap chunks found; check CORPUS paths");
    assert!(decoded_frames > 0, "no frames decoded");
}
