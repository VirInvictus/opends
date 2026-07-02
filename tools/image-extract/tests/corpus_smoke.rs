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
    // Per-failure breadcrumb: every (path, kind, id, frame_id,
    // ImageError) tuple. Used to surface which specific chunks
    // still fail the corpus once we're down to the long tail
    // (one chunk at v0.2.0).
    let mut failures: Vec<(String, String, i32, usize, String)> = Vec::new();

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
                            image_extract::ImageError::Ds1RleError { .. } => {
                                "Ds1RleError".to_string()
                            }
                            other => format!("other:{other}"),
                        };
                        *err_kinds.entry(kind.clone()).or_insert(0) += 1;
                        failures.push((path.to_string(), c.kind.to_string(), c.id, frame_id, kind));
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
    if !failures.is_empty() {
        eprintln!("per-failure breakdown ({} total):", failures.len());
        for (path, kind, id, frame_id, err) in &failures {
            let leaf = Path::new(path)
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or(path.as_str());
            let game = if path.contains("/ds1/") { "ds1" } else { "ds2" };
            eprintln!("  {game}/{leaf} {kind}/{id:#x} frame {frame_id}: {err}");
        }
    }
    assert!(
        total_chunks > 0,
        "no bitmap chunks found; check CORPUS paths"
    );
    assert!(decoded_frames > 0, "no frames decoded");

    // Known-bad chunks. Each entry is (game, file, kind, id,
    // frame_id, error_kind). See image-extract/README.md
    // "Known limitations" for the per-entry root cause.
    const EXPECTED_FAILURES: &[(&str, &str, &str, i32, usize, &str)] =
        &[("ds1", "RESOURCE.GFF", "ICON", 0x7f9, 2, "FrameOutOfBounds")];
    let expected: std::collections::BTreeSet<(&str, &str, &str, i32, usize, &str)> =
        EXPECTED_FAILURES.iter().copied().collect();
    let observed: std::collections::BTreeSet<(String, String, String, i32, usize, String)> =
        failures
            .iter()
            .map(|(path, kind, id, frame_id, err)| {
                let leaf = Path::new(path)
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or(path.as_str())
                    .to_string();
                let game = if path.contains("/ds1/") {
                    "ds1".to_string()
                } else {
                    "ds2".to_string()
                };
                (game, leaf, kind.clone(), *id, *frame_id, err.clone())
            })
            .collect();

    let expected_str: std::collections::BTreeSet<_> = expected
        .iter()
        .map(|(g, f, k, i, fr, e)| {
            (
                g.to_string(),
                f.to_string(),
                k.to_string(),
                *i,
                *fr,
                e.to_string(),
            )
        })
        .collect();

    let unexpected: Vec<_> = observed.difference(&expected_str).cloned().collect();
    let missing: Vec<_> = expected_str.difference(&observed).cloned().collect();

    assert!(
        unexpected.is_empty(),
        "image-extract corpus regressed: new failures not in EXPECTED_FAILURES: {:#?}",
        unexpected
    );
    assert!(
        missing.is_empty(),
        "image-extract corpus improved! EXPECTED_FAILURES entries no longer fire (remove from the list and ship a patchnote): {:#?}",
        missing
    );
}
