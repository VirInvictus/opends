//! GFF construction from scratch.
//!
//! [`Gff::from_bytes`] / [`Gff::replace_chunk`] cover read and
//! targeted in-place edits, but neither path can synthesise a
//! new GFF whose TOC structure does not already exist. The
//! builder fills that gap: it accepts a sequence of
//! `(kind, id, bytes)` records, emits a valid GFF byte buffer
//! that `Gff::from_bytes` parses, and is round-trip equivalent
//! at the *structural* level (same types, same chunks, same
//! payload bytes; byte layout is canonicalised).
//!
//! v0.5.0 is **indexed-only**. Segmented types require the
//! secondary-table + `GFFI` cross-reference dance and are
//! deferred to v0.6.0; calling [`GffBuilder::build`] on an
//! input that resolves to segmented chunks is currently a
//! programmer error (we don't yet have a way to express
//! "build this as a segmented type", so the question doesn't
//! arise: every builder-emitted GFF is indexed-only).
//!
//! ## On-disk layout produced
//!
//! ```text
//! +0       file header (28 bytes)
//! +28      data area: chunk payloads concatenated back-to-back
//! +28+D    TOC:
//!            +0   types_offset  (u32) = 8
//!            +4   free_list_off (u32) = TOC end - 2
//!            +8   num_types     (u16)
//!           +10   per-type blocks (4-byte kind + 4-byte
//!                 chunk_count + chunk_count*12 entries)
//!         +end-2  free list:    u16 entry count = 0
//! ```
//!
//! Types appear in the order their first chunk was added.
//! Chunks within each type appear in insertion order; ids are
//! preserved verbatim (no sort, no dedup).

use crate::{ChunkRef, FileHeader, FourCC, Gff, GffError, SegmentedInfo, SEGMENTED_FLAG};

/// In-progress construction of a GFF.
///
/// Built up by repeated [`add_chunk`] calls, finalised by
/// [`build`].
///
/// [`add_chunk`]: GffBuilder::add_chunk
/// [`build`]: GffBuilder::build
#[derive(Debug, Default)]
pub struct GffBuilder {
    /// Header `data0` sentinel. Defaults to 1 (the most
    /// common value across the DS1/DS2 corpus); override via
    /// [`with_data0`].
    ///
    /// [`with_data0`]: GffBuilder::with_data0
    data0: u32,
    /// Header `file_flags`. Defaults to 0; CHARSAVE.GFF is
    /// observed to use 8. Override via [`with_file_flags`].
    ///
    /// [`with_file_flags`]: GffBuilder::with_file_flags
    file_flags: u32,
    /// Chunks in insertion order. Each entry is
    /// `(kind, id, payload)`.
    chunks: Vec<(FourCC, i32, Vec<u8>)>,
}

impl GffBuilder {
    /// Empty builder. Defaults: major version 3, data0=1,
    /// file_flags=0, no chunks.
    pub fn new() -> Self {
        Self {
            data0: 1,
            file_flags: 0,
            chunks: Vec::new(),
        }
    }

    /// Override the header `data0` sentinel.
    pub fn with_data0(mut self, v: u32) -> Self {
        self.data0 = v;
        self
    }

    /// Override the header `file_flags`.
    pub fn with_file_flags(mut self, v: u32) -> Self {
        self.file_flags = v;
        self
    }

    /// Append one indexed chunk to the builder. Order is
    /// preserved; the first occurrence of a given kind
    /// determines its position in the TOC types list.
    pub fn add_chunk(&mut self, kind: FourCC, id: i32, payload: impl Into<Vec<u8>>) -> &mut Self {
        self.chunks.push((kind, id, payload.into()));
        self
    }

    /// Number of chunks added so far.
    pub fn len(&self) -> usize {
        self.chunks.len()
    }

    /// True iff no chunks have been added.
    pub fn is_empty(&self) -> bool {
        self.chunks.is_empty()
    }

    /// Finalise: emit the GFF byte buffer.
    ///
    /// Errors only if a chunk payload is so large its
    /// `(location, length)` would exceed `u32::MAX`. With the
    /// DOS-era format this is effectively unreachable, but the
    /// invariant is checked rather than asserted.
    pub fn build(&self) -> Result<Vec<u8>, GffError> {
        // Group chunks by kind in first-seen order so the TOC
        // types list reflects insertion order. Within each kind,
        // chunks stay in the order they were added.
        type ChunkEntry = (FourCC, i32, Vec<u8>);
        let mut kind_order: Vec<FourCC> = Vec::new();
        let mut by_kind: Vec<(FourCC, Vec<&ChunkEntry>)> = Vec::new();
        for entry in &self.chunks {
            let kind = entry.0;
            if let Some(pos) = kind_order.iter().position(|k| *k == kind) {
                by_kind[pos].1.push(entry);
            } else {
                kind_order.push(kind);
                by_kind.push((kind, vec![entry]));
            }
        }

        // 1. Lay out the data area: chunk payloads back-to-back
        //    starting at offset 28 (right after the header).
        let mut out = Vec::with_capacity(28 + self.chunks.iter().map(|c| c.2.len()).sum::<usize>());
        out.extend_from_slice(&[0u8; FileHeader::SIZE]);

        // location-of-each-chunk, indexed by the chunk's
        // position in `self.chunks` (the insertion order). The
        // type-block emitter looks these up by traversing
        // `by_kind` in the same order it grouped them.
        let mut locations: Vec<u32> = Vec::with_capacity(self.chunks.len());
        for (_, _, payload) in &self.chunks {
            let loc = u32::try_from(out.len()).map_err(|_| GffError::ChunkTooLarge {
                kind: FourCC([0; 4]),
                id: 0,
                length: out.len(),
            })?;
            locations.push(loc);
            out.extend_from_slice(payload);
        }

        // 2. TOC starts at the current end-of-data. Compute the
        //    size first so we can fill out the header up front.
        let toc_location = u32::try_from(out.len()).map_err(|_| GffError::ChunkTooLarge {
            kind: FourCC([0; 4]),
            id: 0,
            length: out.len(),
        })?;

        // Each type-block: 4-byte kind + 4-byte raw_count + 12
        // bytes per indexed entry. types_offset is 8 (after the
        // two u32 fixed fields); free list is the trailing u16=0.
        let types_block_size: usize = by_kind
            .iter()
            .map(|(_, entries)| 4 + 4 + entries.len() * 12)
            .sum();
        // 4 (types_offset) + 4 (free_list_offset) + 2
        // (num_types) + types_block + 2 (free-list count = 0).
        let toc_length = 4 + 4 + 2 + types_block_size + 2;
        let toc_length_u32 = u32::try_from(toc_length).map_err(|_| GffError::ChunkTooLarge {
            kind: FourCC([0; 4]),
            id: 0,
            length: toc_length,
        })?;

        // Re-populate the header now that we know toc_location
        // and toc_length.
        out[0..4].copy_from_slice(b"GFFI");
        out[4..8].copy_from_slice(&0x0003_0000u32.to_le_bytes());
        out[8..12].copy_from_slice(&28u32.to_le_bytes());
        out[12..16].copy_from_slice(&toc_location.to_le_bytes());
        out[16..20].copy_from_slice(&toc_length_u32.to_le_bytes());
        out[20..24].copy_from_slice(&self.file_flags.to_le_bytes());
        out[24..28].copy_from_slice(&self.data0.to_le_bytes());

        // 3. Emit the TOC.
        out.extend_from_slice(&8u32.to_le_bytes()); // types_offset
        let free_list_offset =
            u32::try_from(toc_length - 2).map_err(|_| GffError::ChunkTooLarge {
                kind: FourCC([0; 4]),
                id: 0,
                length: toc_length,
            })?;
        out.extend_from_slice(&free_list_offset.to_le_bytes()); // free_list_offset
        let num_types_u16 = u16::try_from(by_kind.len()).map_err(|_| GffError::ChunkTooLarge {
            kind: FourCC([0; 4]),
            id: 0,
            length: by_kind.len(),
        })?;
        out.extend_from_slice(&num_types_u16.to_le_bytes()); // num_types

        // We need to map each (FourCC, position-within-kind)
        // back to the position in `self.chunks`. Easiest: walk
        // `self.chunks` in order, increment a per-kind counter,
        // record the linear index.
        let mut indices_per_kind: Vec<Vec<usize>> = vec![Vec::new(); by_kind.len()];
        for (i, (kind, _, _)) in self.chunks.iter().enumerate() {
            let pos = kind_order.iter().position(|k| *k == *kind).unwrap();
            indices_per_kind[pos].push(i);
        }

        for (type_idx, (kind, entries)) in by_kind.iter().enumerate() {
            out.extend_from_slice(kind.as_bytes());
            let chunk_count =
                u32::try_from(entries.len()).map_err(|_| GffError::ChunkTooLarge {
                    kind: *kind,
                    id: 0,
                    length: entries.len(),
                })?;
            // raw_count: high bit clear means indexed.
            out.extend_from_slice(&chunk_count.to_le_bytes());

            for (chunk_pos, entry) in entries.iter().enumerate() {
                let linear = indices_per_kind[type_idx][chunk_pos];
                let id = entry.1;
                let location = locations[linear];
                let length = u32::try_from(entry.2.len()).map_err(|_| GffError::ChunkTooLarge {
                    kind: *kind,
                    id,
                    length: entry.2.len(),
                })?;
                out.extend_from_slice(&id.to_le_bytes());
                out.extend_from_slice(&location.to_le_bytes());
                out.extend_from_slice(&length.to_le_bytes());
            }
        }

        // 4. Free list: zero entries.
        out.extend_from_slice(&0u16.to_le_bytes());

        Ok(out)
    }
}

/// Convert a parsed [`Gff`] back into a builder, for indexed-only
/// inputs. Used by the corpus round-trip test to verify that
/// every (kind, id, payload) record we can read can be rebuilt
/// into a parseable GFF.
///
/// Returns `None` if the input has any segmented types; the
/// builder cannot yet emit segmented chunks, and silently
/// dropping them would produce a structurally-different GFF.
pub fn builder_from_gff(gff: &Gff) -> Option<GffBuilder> {
    if gff.types().iter().any(|t| t.is_segmented()) {
        return None;
    }
    let mut b = GffBuilder::new()
        .with_data0(gff.header().data0)
        .with_file_flags(gff.header().file_flags);
    for c in gff.chunks() {
        b.add_chunk(c.kind, c.id, gff.read_chunk(c).to_vec());
    }
    Some(b)
}

// Silence unused-import lints when Segmented-related items are
// referenced only in scope-out comments. Keep imports compact;
// the items will be needed in v0.6.0.
#[allow(dead_code)]
fn _segmented_imports_keep_alive(_: &ChunkRef, _: &SegmentedInfo) -> u32 {
    SEGMENTED_FLAG
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_minimal_two_chunk_gff() {
        let mut b = GffBuilder::new();
        b.add_chunk(FourCC::from_str("ETME").unwrap(), 7, b"hi!\0".to_vec())
            .add_chunk(
                FourCC::from_str("GPL ").unwrap(),
                0,
                b"\x00\x00\x00\x00".to_vec(),
            );
        let bytes = b.build().expect("build ok");

        let gff = Gff::from_bytes(bytes).expect("parses");
        assert_eq!(gff.types().len(), 2);
        assert_eq!(gff.chunks().len(), 2);

        let etme = gff
            .read(FourCC::from_str("ETME").unwrap(), 7)
            .expect("ETME 7");
        assert_eq!(etme, b"hi!\0");

        let gpl = gff
            .read(FourCC::from_str("GPL ").unwrap(), 0)
            .expect("GPL 0");
        assert_eq!(gpl, b"\x00\x00\x00\x00");
    }

    #[test]
    fn first_seen_kind_position_preserved() {
        let mut b = GffBuilder::new();
        b.add_chunk(FourCC::from_str("AAAA").unwrap(), 1, b"a1".to_vec());
        b.add_chunk(FourCC::from_str("BBBB").unwrap(), 1, b"b1".to_vec());
        b.add_chunk(FourCC::from_str("AAAA").unwrap(), 2, b"a2".to_vec());
        let bytes = b.build().expect("build ok");
        let gff = Gff::from_bytes(bytes).expect("parses");
        let kinds: Vec<_> = gff.types().iter().map(|t| t.kind).collect();
        assert_eq!(
            kinds,
            vec![
                FourCC::from_str("AAAA").unwrap(),
                FourCC::from_str("BBBB").unwrap()
            ]
        );
        assert_eq!(gff.types()[0].chunk_count, 2);
        assert_eq!(gff.types()[1].chunk_count, 1);
    }

    #[test]
    fn data0_and_file_flags_round_trip() {
        let mut b = GffBuilder::new().with_data0(117).with_file_flags(8);
        b.add_chunk(FourCC::from_str("ETME").unwrap(), 0, b"x".to_vec());
        let bytes = b.build().expect("build ok");
        let gff = Gff::from_bytes(bytes).expect("parses");
        assert_eq!(gff.header().data0, 117);
        assert_eq!(gff.header().file_flags, 8);
    }

    #[test]
    fn empty_builder_emits_parseable_empty_gff() {
        let bytes = GffBuilder::new().build().expect("build ok");
        let gff = Gff::from_bytes(bytes).expect("parses");
        assert_eq!(gff.types().len(), 0);
        assert_eq!(gff.chunks().len(), 0);
    }

    #[test]
    fn rebuild_from_parsed_gff_preserves_chunks() {
        let mut b = GffBuilder::new();
        b.add_chunk(FourCC::from_str("ETME").unwrap(), 3, b"hello".to_vec())
            .add_chunk(FourCC::from_str("ETME").unwrap(), 4, b"world".to_vec())
            .add_chunk(FourCC::from_str("GPL ").unwrap(), 0, b"abc".to_vec());
        let bytes = b.build().expect("build ok");
        let gff = Gff::from_bytes(bytes).expect("parses");

        let b2 = builder_from_gff(&gff).expect("indexed-only");
        let bytes2 = b2.build().expect("rebuild ok");
        let gff2 = Gff::from_bytes(bytes2).expect("reparses");

        assert_eq!(gff.chunks().len(), gff2.chunks().len());
        for (a, b) in gff.chunks().iter().zip(gff2.chunks().iter()) {
            assert_eq!(a.kind, b.kind);
            assert_eq!(a.id, b.id);
            assert_eq!(gff.read_chunk(a), gff2.read_chunk(b));
        }
    }
}
