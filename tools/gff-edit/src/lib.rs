//! gff-edit: pure-Rust reader for SSI's GFF container format.
//!
//! Foundation library for the OpenDS toolkit. See the repository's
//! `docs/file-formats.md` §1 for the on-disk layout implemented here.
//!
//! # Example
//!
//! ```no_run
//! use gff_edit::Gff;
//!
//! let gff = Gff::open("RGN02.GFF")?;
//! println!("{} types, {} indexed chunks, {} bytes",
//!     gff.types().len(), gff.chunks().len(), gff.len());
//! for chunk in gff.chunks() {
//!     println!("{} id={} offset={} len={}",
//!         chunk.kind, chunk.id, chunk.location, chunk.length);
//! }
//! # Ok::<(), gff_edit::GffError>(())
//! ```
//!
//! # Coverage of GFF features in this version (v0.2)
//!
//! - **Indexed chunk lists** are fully parsed; their `ChunkRef`s
//!   appear in [`Gff::chunks`] and chunk bytes can be read via
//!   [`Gff::read`].
//! - **Segmented chunk lists** are fully resolved via the `GFFI`
//!   cross-reference: the parser reads each type's secondary
//!   table from the file offset given by the `seg_loc_id`-th
//!   GFFI chunk, reconstructs resource numbers from the type's
//!   segment runs, and appends the resulting `ChunkRef`s to
//!   [`Gff::chunks`] in TOC declaration order.
//! - **Writer** (round-trip read → edit → write byte-identical):
//!   lands in v0.3.0.

use std::fmt;
use std::fs;
use std::path::Path;

use serde::{Serialize, Serializer};
use thiserror::Error;

mod builder;
pub use builder::{builder_from_gff, GffBuilder};

/// Bit mask for the segmented-list flag stored in the high bit of
/// a TOC type entry's `chunk_count` field.
pub const SEGMENTED_FLAG: u32 = 0x8000_0000;

/// Bit mask for the canonical chunk-count value (the low 31 bits
/// of the `chunk_count` field).
pub const CHUNK_COUNT_MASK: u32 = 0x7FFF_FFFF;

/// SSI's GFF container loaded into memory.
#[derive(Debug)]
pub struct Gff {
    bytes: Vec<u8>,
    header: FileHeader,
    types: Vec<TypeInfo>,
    chunks: Vec<ChunkRef>,
}

impl Gff {
    /// Read and parse a GFF file from disk.
    pub fn open(path: impl AsRef<Path>) -> Result<Self, GffError> {
        let path_ref = path.as_ref();
        let bytes = fs::read(path_ref).map_err(|err| GffError::Io {
            path: path_ref.display().to_string(),
            source: err,
        })?;
        Self::from_bytes(bytes)
    }

    /// Parse a GFF from an in-memory byte buffer.
    pub fn from_bytes(bytes: Vec<u8>) -> Result<Self, GffError> {
        let header = FileHeader::parse(&bytes)?;
        let (types, chunks) = parse_toc(&bytes, &header)?;
        Ok(Self {
            bytes,
            header,
            types,
            chunks,
        })
    }

    /// Total file size in bytes.
    pub fn len(&self) -> usize {
        self.bytes.len()
    }

    /// Returns true if the underlying byte buffer is empty.
    pub fn is_empty(&self) -> bool {
        self.bytes.is_empty()
    }

    /// File header.
    pub fn header(&self) -> &FileHeader {
        &self.header
    }

    /// Per-type metadata in TOC order. Includes both indexed and
    /// segmented types.
    pub fn types(&self) -> &[TypeInfo] {
        &self.types
    }

    /// Flat list of every chunk reference in TOC declaration order.
    /// Includes both indexed chunks and resolved segmented chunks.
    pub fn chunks(&self) -> &[ChunkRef] {
        &self.chunks
    }

    /// Find a chunk by FOURCC and resource id. Works for both indexed
    /// and segmented chunks.
    pub fn find(&self, kind: FourCC, id: i32) -> Option<&ChunkRef> {
        self.chunks.iter().find(|c| c.kind == kind && c.id == id)
    }

    /// Borrow the raw bytes of a chunk by (kind, id). Works for both
    /// indexed and segmented chunks.
    pub fn read(&self, kind: FourCC, id: i32) -> Option<&[u8]> {
        let c = self.find(kind, id)?;
        let start = c.location as usize;
        let end = start + c.length as usize;
        Some(&self.bytes[start..end])
    }

    /// Borrow the raw bytes of a chunk by direct `ChunkRef`.
    pub fn read_chunk(&self, chunk: &ChunkRef) -> &[u8] {
        let start = chunk.location as usize;
        let end = start + chunk.length as usize;
        &self.bytes[start..end]
    }

    /// Borrow the entire underlying file byte buffer.
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// Produce a new GFF byte buffer with the named chunk's payload
    /// replaced. Returns the new file bytes; does not mutate `self`.
    ///
    /// Replacement policy (matches JohnGlassmyer/dsun_music's
    /// `GffFile.replaceResource`):
    /// - If the new bytes fit in the existing slot
    ///   (`new_bytes.len() <= chunk.length`), they are written in
    ///   place at the chunk's original `location`. The chunk's
    ///   `(location, length)` metadata is rewritten so the length
    ///   reflects the new size; trailing bytes of the old payload
    ///   become unreferenced dead space.
    /// - Otherwise the new bytes are appended at end-of-file and the
    ///   chunk's `(location, length)` metadata is rewritten to point
    ///   there. The TOC's own `toc_location`/`toc_length` in the
    ///   file header are unchanged.
    ///
    /// Works for both indexed and segmented chunks; the writer
    /// updates whichever of the TOC or the secondary table holds
    /// the chunk's `(location, length)` record, as identified by
    /// [`ChunkRef::meta_offset`].
    ///
    /// To stage multiple edits, re-parse the returned bytes between
    /// calls. `replace_chunk` does not consume `self`, so the same
    /// parsed `Gff` cannot be used to perform a sequence of edits.
    pub fn replace_chunk(
        &self,
        kind: FourCC,
        id: i32,
        new_bytes: &[u8],
    ) -> Result<Vec<u8>, GffError> {
        let chunk = self
            .find(kind, id)
            .ok_or(GffError::ChunkNotFound { kind, id })?;

        let new_length_u32 = u32::try_from(new_bytes.len()).map_err(|_| {
            GffError::ChunkTooLarge {
                kind,
                id,
                length: new_bytes.len(),
            }
        })?;

        let mut out = self.bytes.clone();

        let new_location = if new_bytes.len() <= chunk.length as usize {
            // In-place: overwrite at the chunk's existing location.
            // Bytes past new_length within the old slot become
            // unreferenced (matching dsun_music's policy).
            let start = chunk.location as usize;
            out[start..start + new_bytes.len()].copy_from_slice(new_bytes);
            chunk.location
        } else {
            // Append: write at end-of-file.
            let new_loc = u32::try_from(out.len()).map_err(|_| {
                GffError::ChunkTooLarge {
                    kind,
                    id,
                    length: out.len() + new_bytes.len(),
                }
            })?;
            out.extend_from_slice(new_bytes);
            new_loc
        };

        // Rewrite the chunk's (location, length) record.
        let m = chunk.meta_offset as usize;
        out[m..m + 4].copy_from_slice(&new_location.to_le_bytes());
        out[m + 4..m + 8].copy_from_slice(&new_length_u32.to_le_bytes());

        Ok(out)
    }
}

fn serialize_identity<S: Serializer>(id: &[u8; 4], s: S) -> Result<S::Ok, S::Error> {
    s.serialize_str(std::str::from_utf8(id).unwrap_or("?"))
}

/// GFF file header (28 bytes). See docs/file-formats.md §1.
#[derive(Debug, Clone, Copy, Serialize)]
pub struct FileHeader {
    /// Magic bytes; always "GFFI" for a valid file.
    #[serde(serialize_with = "serialize_identity")]
    pub identity: [u8; 4],
    /// Version word. The major version is `(version >> 16) & 0xFFFF`,
    /// which is 3 on every shipped Dark Sun GFF.
    pub version: u32,
    /// Offset of the chunk data area. Always 28 (= header size).
    pub data_location: u32,
    /// Offset of the TOC.
    pub toc_location: u32,
    /// Byte length of the TOC.
    pub toc_length: u32,
    /// Per-file flags. Observed: 0 on most files; 8 on `CHARSAVE.GFF`.
    pub file_flags: u32,
    /// Per-file sentinel. Observed: 1, 3, 117. Treated as opaque
    /// here; preserve verbatim on round-trip.
    pub data0: u32,
}

impl FileHeader {
    pub const SIZE: usize = 28;

    /// Major version derived from the upper 16 bits of `version`.
    pub fn major_version(&self) -> u16 {
        ((self.version >> 16) & 0xFFFF) as u16
    }

    fn parse(bytes: &[u8]) -> Result<Self, GffError> {
        if bytes.len() < Self::SIZE {
            return Err(GffError::Truncated {
                what: "file header",
                expected: Self::SIZE,
                actual: bytes.len(),
            });
        }
        let identity: [u8; 4] = bytes[0..4].try_into().unwrap();
        if &identity != b"GFFI" {
            return Err(GffError::BadMagic(identity));
        }
        let version = u32_le(&bytes[4..8]);
        let major = ((version >> 16) & 0xFFFF) as u16;
        if major != 3 {
            return Err(GffError::UnsupportedVersion(version));
        }
        Ok(Self {
            identity,
            version,
            data_location: u32_le(&bytes[8..12]),
            toc_location: u32_le(&bytes[12..16]),
            toc_length: u32_le(&bytes[16..20]),
            file_flags: u32_le(&bytes[20..24]),
            data0: u32_le(&bytes[24..28]),
        })
    }
}

/// Metadata for one chunk type's TOC entry.
#[derive(Debug, Clone, Serialize)]
pub struct TypeInfo {
    pub kind: FourCC,
    /// Logical chunk count (the on-disk field with its high bit
    /// masked off).
    pub chunk_count: usize,
    /// Segmented-list details, present iff the type is segmented.
    pub segmented: Option<SegmentedInfo>,
}

impl TypeInfo {
    pub fn is_segmented(&self) -> bool {
        self.segmented.is_some()
    }
}

/// On-disk metadata for a segmented chunk list. Resolution to
/// individual chunks via the GFFI cross-reference happens in
/// [`Gff::from_bytes`].
#[derive(Debug, Clone, Serialize)]
pub struct SegmentedInfo {
    pub seg_count: i32,
    pub seg_loc_id: i32,
    pub seg_entries: Vec<SegEntry>,
}

/// One entry in a segmented type's segment-reference table.
#[derive(Debug, Clone, Copy, Serialize)]
pub struct SegEntry {
    pub first_id: i32,
    pub num_chunks: i32,
}

/// A reference to a chunk in the GFF: its kind, id, on-disk offset,
/// and byte length. Borrowing the chunk data lives on `Gff::read`.
#[derive(Debug, Clone, Copy, Serialize)]
pub struct ChunkRef {
    pub kind: FourCC,
    pub id: i32,
    pub location: u32,
    pub length: u32,
    /// File offset of this chunk's `(location, length)` record (8
    /// bytes, little-endian). For indexed types this sits in the TOC;
    /// for segmented types it sits in the secondary table inside the
    /// `GFFI` chunk. Used by [`Gff::replace_chunk`] to update the
    /// metadata when bytes change. Treat as opaque; not serialized.
    #[serde(skip)]
    pub meta_offset: u32,
}

/// Four-byte tag identifying a chunk's type. Stored verbatim as
/// four bytes; the first ASCII chars spell the FOURCC (e.g. "GPL ",
/// "ETME", "BMP ").
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct FourCC(pub [u8; 4]);

impl FourCC {
    pub const fn new(bytes: [u8; 4]) -> Self {
        Self(bytes)
    }

    /// Parse a 4-character ASCII string into a FOURCC. Accepts
    /// strings of exactly four bytes; trailing spaces are common
    /// in the format ("GPL ", "ADV ").
    pub fn from_str(s: &str) -> Result<Self, GffError> {
        let bytes = s.as_bytes();
        if bytes.len() != 4 {
            return Err(GffError::BadFourCC(s.to_string()));
        }
        Ok(Self([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    pub fn as_bytes(&self) -> &[u8; 4] {
        &self.0
    }

    /// Raw u32 representation as stored on disk (little-endian
    /// interpretation of the four bytes).
    pub fn as_u32_le(&self) -> u32 {
        u32::from_le_bytes(self.0)
    }
}

impl fmt::Display for FourCC {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // FOURCCs are conventionally 4 ASCII chars but the format
        // permits arbitrary bytes; render printables as ASCII and
        // non-printables as a hex escape.
        for &b in &self.0 {
            if (0x20..0x7F).contains(&b) {
                write!(f, "{}", b as char)?;
            } else {
                write!(f, "\\x{:02x}", b)?;
            }
        }
        Ok(())
    }
}

impl Serialize for FourCC {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.collect_str(self)
    }
}

/// Errors raised by the gff-edit library.
#[derive(Debug, Error)]
pub enum GffError {
    #[error("io error reading {path}: {source}")]
    Io {
        path: String,
        #[source]
        source: std::io::Error,
    },

    #[error("{what} truncated: expected {expected} bytes, got {actual}")]
    Truncated {
        what: &'static str,
        expected: usize,
        actual: usize,
    },

    #[error("bad GFF magic: expected 'GFFI', got {0:02x?}")]
    BadMagic([u8; 4]),

    #[error("unsupported GFF version: {0:#010x} (only major version 3 is supported)")]
    UnsupportedVersion(u32),

    #[error("TOC out of bounds: location={location} length={length} file_size={file_size}")]
    TocOutOfBounds {
        location: usize,
        length: usize,
        file_size: usize,
    },

    #[error("chunk {kind} id={id} out of bounds: location={location} length={length} file_size={file_size}")]
    ChunkOutOfBounds {
        kind: FourCC,
        id: i32,
        location: usize,
        length: usize,
        file_size: usize,
    },

    #[error("TOC truncated parsing types (num_types={num_types}, byte offset {offset})")]
    TocTypesTruncated { num_types: usize, offset: usize },

    #[error("FOURCC must be exactly 4 bytes: got {0:?}")]
    BadFourCC(String),

    #[error("segmented type {kind} requires a GFFI type but none is present in the TOC")]
    MissingGffiType { kind: FourCC },

    #[error("segmented type {kind}: seg_loc_id {seg_loc_id} out of range (GFFI has {gffi_count} chunks)")]
    SegLocIdOutOfRange {
        kind: FourCC,
        seg_loc_id: i32,
        gffi_count: usize,
    },

    #[error("secondary table for {kind} out of bounds: offset={offset} entry_count={entry_count} file_size={file_size}")]
    SecondaryTableOutOfBounds {
        kind: FourCC,
        offset: usize,
        entry_count: usize,
        file_size: usize,
    },

    #[error("secondary table for {kind} declares {table_count} entries but segment runs sum to {runs_total}")]
    SecondaryTableMismatch {
        kind: FourCC,
        table_count: usize,
        runs_total: usize,
    },

    #[error("no chunk '{kind}' id={id} found")]
    ChunkNotFound { kind: FourCC, id: i32 },

    #[error("chunk '{kind}' id={id} new length {length} exceeds u32::MAX")]
    ChunkTooLarge {
        kind: FourCC,
        id: i32,
        length: usize,
    },
}

fn parse_toc(
    bytes: &[u8],
    header: &FileHeader,
) -> Result<(Vec<TypeInfo>, Vec<ChunkRef>), GffError> {
    let toc_start = header.toc_location as usize;
    let toc_len = header.toc_length as usize;
    let toc_end = toc_start
        .checked_add(toc_len)
        .filter(|end| *end <= bytes.len())
        .ok_or(GffError::TocOutOfBounds {
            location: toc_start,
            length: toc_len,
            file_size: bytes.len(),
        })?;
    let toc = &bytes[toc_start..toc_end];

    if toc.len() < 8 {
        return Err(GffError::Truncated {
            what: "TOC header",
            expected: 8,
            actual: toc.len(),
        });
    }
    let types_offset = u32_le(&toc[0..4]) as usize;
    let _free_list_offset = u32_le(&toc[4..8]) as usize;

    if types_offset + 2 > toc.len() {
        return Err(GffError::TocTypesTruncated {
            num_types: 0,
            offset: types_offset,
        });
    }
    let num_types = u16_le(&toc[types_offset..types_offset + 2]) as usize;
    let mut cursor = types_offset + 2;

    // First pass: parse each type's TOC region linearly. Indexed chunks
    // are stashed per-type so we can preserve TOC order when we later
    // interleave resolved segmented chunks.
    let mut builds: Vec<TypeBuild> = Vec::with_capacity(num_types);

    for _ in 0..num_types {
        if cursor + 8 > toc.len() {
            return Err(GffError::TocTypesTruncated { num_types, offset: cursor });
        }
        let kind = FourCC([
            toc[cursor],
            toc[cursor + 1],
            toc[cursor + 2],
            toc[cursor + 3],
        ]);
        let raw_count = u32_le(&toc[cursor + 4..cursor + 8]);
        cursor += 8;

        let segmented = raw_count & SEGMENTED_FLAG != 0;
        let chunk_count = (raw_count & CHUNK_COUNT_MASK) as usize;

        if segmented {
            if cursor + 12 > toc.len() {
                return Err(GffError::TocTypesTruncated { num_types, offset: cursor });
            }
            let seg_count = i32_le(&toc[cursor..cursor + 4]);
            let seg_loc_id = i32_le(&toc[cursor + 4..cursor + 8]);
            let num_entries = u32_le(&toc[cursor + 8..cursor + 12]) as usize;
            cursor += 12;

            let entries_size = num_entries
                .checked_mul(8)
                .ok_or(GffError::TocTypesTruncated { num_types, offset: cursor })?;
            if cursor + entries_size > toc.len() {
                return Err(GffError::TocTypesTruncated { num_types, offset: cursor });
            }
            let mut seg_entries = Vec::with_capacity(num_entries);
            for _ in 0..num_entries {
                let first_id = i32_le(&toc[cursor..cursor + 4]);
                let num_chunks = i32_le(&toc[cursor + 4..cursor + 8]);
                cursor += 8;
                seg_entries.push(SegEntry { first_id, num_chunks });
            }
            builds.push(TypeBuild {
                info: TypeInfo {
                    kind,
                    chunk_count,
                    segmented: Some(SegmentedInfo {
                        seg_count,
                        seg_loc_id,
                        seg_entries,
                    }),
                },
                indexed: Vec::new(),
            });
        } else {
            let entries_size = chunk_count
                .checked_mul(12)
                .ok_or(GffError::TocTypesTruncated { num_types, offset: cursor })?;
            if cursor + entries_size > toc.len() {
                return Err(GffError::TocTypesTruncated { num_types, offset: cursor });
            }
            let mut indexed = Vec::with_capacity(chunk_count);
            for _ in 0..chunk_count {
                let entry_start = cursor;
                let id = i32_le(&toc[cursor..cursor + 4]);
                let location = u32_le(&toc[cursor + 4..cursor + 8]);
                let length = u32_le(&toc[cursor + 8..cursor + 12]);
                cursor += 12;

                (location as usize)
                    .checked_add(length as usize)
                    .filter(|e| *e <= bytes.len())
                    .ok_or(GffError::ChunkOutOfBounds {
                        kind,
                        id,
                        location: location as usize,
                        length: length as usize,
                        file_size: bytes.len(),
                    })?;
                // Metadata (location, length) sits 4 bytes past the
                // entry start (after the id field), in file
                // coordinates.
                let meta_offset = (toc_start + entry_start + 4) as u32;
                indexed.push(ChunkRef {
                    kind,
                    id,
                    location,
                    length,
                    meta_offset,
                });
            }
            builds.push(TypeBuild {
                info: TypeInfo {
                    kind,
                    chunk_count,
                    segmented: None,
                },
                indexed,
            });
        }
    }

    // Second pass: resolve segmented types via the GFFI primary table.
    // Snapshot the GFFI type's indexed chunks (cloned) so the per-type
    // resolution can borrow without conflicting with the in-progress
    // assembly of the flat chunks vec.
    let gffi_chunks: Vec<ChunkRef> = builds
        .iter()
        .find(|b| b.info.kind == GFFI_KIND)
        .map(|b| b.indexed.clone())
        .unwrap_or_default();

    let mut chunks = Vec::new();
    for build in &builds {
        if let Some(seg) = &build.info.segmented {
            let resolved = resolve_segmented_type(bytes, build.info.kind, seg, &gffi_chunks)?;
            chunks.extend(resolved);
        } else {
            chunks.extend(build.indexed.iter().copied());
        }
    }

    let types = builds.into_iter().map(|b| b.info).collect();
    Ok((types, chunks))
}

/// Internal builder: a type's metadata plus, for indexed types, the
/// raw chunk references we stash so the final flat list can be
/// assembled in TOC order after segmented resolution.
struct TypeBuild {
    info: TypeInfo,
    indexed: Vec<ChunkRef>,
}

/// `GFFI` FOURCC constant (kept private to avoid leaking into the API).
const GFFI_KIND: FourCC = FourCC(*b"GFFI");

/// Resolve a segmented type into concrete `ChunkRef`s.
///
/// Reads the type's secondary table at the offset given by the
/// `seg_loc_id`-th GFFI chunk, then walks the type's segment runs
/// to reconstruct resource numbers for each entry. Confirmed against
/// both `libgff` (`gff_find_chunk_header`) and `dsun_music`
/// (`SecondaryGffiTable`) format references.
fn resolve_segmented_type(
    bytes: &[u8],
    kind: FourCC,
    seg: &SegmentedInfo,
    gffi_chunks: &[ChunkRef],
) -> Result<Vec<ChunkRef>, GffError> {
    if gffi_chunks.is_empty() {
        return Err(GffError::MissingGffiType { kind });
    }
    if seg.seg_loc_id < 0 || (seg.seg_loc_id as usize) >= gffi_chunks.len() {
        return Err(GffError::SegLocIdOutOfRange {
            kind,
            seg_loc_id: seg.seg_loc_id,
            gffi_count: gffi_chunks.len(),
        });
    }
    let gffi_chunk = &gffi_chunks[seg.seg_loc_id as usize];

    let table_start = gffi_chunk.location as usize;
    if table_start.checked_add(4).filter(|e| *e <= bytes.len()).is_none() {
        return Err(GffError::SecondaryTableOutOfBounds {
            kind,
            offset: table_start,
            entry_count: 0,
            file_size: bytes.len(),
        });
    }
    let entry_count = u32_le(&bytes[table_start..table_start + 4]) as usize;
    let entries_start = table_start + 4;
    let entries_size = entry_count
        .checked_mul(8)
        .filter(|sz| entries_start.checked_add(*sz).filter(|e| *e <= bytes.len()).is_some())
        .ok_or(GffError::SecondaryTableOutOfBounds {
            kind,
            offset: table_start,
            entry_count,
            file_size: bytes.len(),
        })?;
    let _ = entries_size;

    let runs_total: usize = seg
        .seg_entries
        .iter()
        .map(|s| s.num_chunks.max(0) as usize)
        .sum();
    if runs_total != entry_count {
        return Err(GffError::SecondaryTableMismatch {
            kind,
            table_count: entry_count,
            runs_total,
        });
    }

    let mut resolved = Vec::with_capacity(entry_count);
    let mut entry_index = 0usize;
    for run in &seg.seg_entries {
        if run.num_chunks <= 0 {
            continue;
        }
        for k in 0..run.num_chunks {
            let id = run.first_id.wrapping_add(k);
            let entry_pos = entries_start + entry_index * 8;
            let location = u32_le(&bytes[entry_pos..entry_pos + 4]);
            let length = u32_le(&bytes[entry_pos + 4..entry_pos + 8]);

            (location as usize)
                .checked_add(length as usize)
                .filter(|e| *e <= bytes.len())
                .ok_or(GffError::ChunkOutOfBounds {
                    kind,
                    id,
                    location: location as usize,
                    length: length as usize,
                    file_size: bytes.len(),
                })?;

            // For segmented chunks the (location, length) lives in the
            // secondary table, not the TOC; entry_pos is already a
            // file-relative offset.
            resolved.push(ChunkRef {
                kind,
                id,
                location,
                length,
                meta_offset: entry_pos as u32,
            });
            entry_index += 1;
        }
    }

    Ok(resolved)
}

#[inline]
fn u32_le(b: &[u8]) -> u32 {
    u32::from_le_bytes([b[0], b[1], b[2], b[3]])
}

#[inline]
fn u16_le(b: &[u8]) -> u16 {
    u16::from_le_bytes([b[0], b[1]])
}

#[inline]
fn i32_le(b: &[u8]) -> i32 {
    i32::from_le_bytes([b[0], b[1], b[2], b[3]])
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Minimal hand-built GFF: one indexed ETME chunk, 4 bytes payload.
    fn minimal_gff() -> Vec<u8> {
        let mut v = Vec::new();
        v.extend_from_slice(b"GFFI");
        v.extend_from_slice(&0x0003_0000u32.to_le_bytes()); // version
        v.extend_from_slice(&28u32.to_le_bytes()); // data_location
        v.extend_from_slice(&32u32.to_le_bytes()); // toc_location
        v.extend_from_slice(&32u32.to_le_bytes()); // toc_length
        v.extend_from_slice(&0u32.to_le_bytes()); // file_flags
        v.extend_from_slice(&1u32.to_le_bytes()); // data0
        v.extend_from_slice(b"hi!\0"); // 4 bytes chunk data
        // TOC (32 bytes total)
        v.extend_from_slice(&8u32.to_le_bytes()); // types_offset
        v.extend_from_slice(&30u32.to_le_bytes()); // free_list_offset
        v.extend_from_slice(&1u16.to_le_bytes()); // num_types
        v.extend_from_slice(b"ETME"); // chunk_type
        v.extend_from_slice(&1u32.to_le_bytes()); // chunk_count
        v.extend_from_slice(&7i32.to_le_bytes()); // id
        v.extend_from_slice(&28u32.to_le_bytes()); // location
        v.extend_from_slice(&4u32.to_le_bytes()); // length
        v.extend_from_slice(&0u16.to_le_bytes()); // free list (empty)
        v
    }

    /// Hand-built GFF with a segmented TILE type but no GFFI type to
    /// resolve it. Expected to fail with `MissingGffiType` once we
    /// attempt segmented resolution.
    fn mixed_gff_missing_gffi() -> Vec<u8> {
        let mut v = Vec::new();
        v.extend_from_slice(b"GFFI");
        v.extend_from_slice(&0x0003_0000u32.to_le_bytes()); // version
        v.extend_from_slice(&28u32.to_le_bytes()); // data_location
        v.extend_from_slice(&32u32.to_le_bytes()); // toc_location
        v.extend_from_slice(&60u32.to_le_bytes()); // toc_length
        v.extend_from_slice(&0u32.to_le_bytes()); // file_flags
        v.extend_from_slice(&2u32.to_le_bytes()); // data0
        v.extend_from_slice(b"hi!\0"); // 4 bytes ETME data
        // TOC
        v.extend_from_slice(&8u32.to_le_bytes()); // types_offset
        v.extend_from_slice(&58u32.to_le_bytes()); // free_list_offset
        v.extend_from_slice(&2u16.to_le_bytes()); // num_types
        // Type 1: ETME indexed, 1 chunk
        v.extend_from_slice(b"ETME");
        v.extend_from_slice(&1u32.to_le_bytes());
        v.extend_from_slice(&3i32.to_le_bytes());
        v.extend_from_slice(&28u32.to_le_bytes());
        v.extend_from_slice(&4u32.to_le_bytes());
        // Type 2: TILE segmented, 5 chunks, 1 seg entry
        v.extend_from_slice(b"TILE");
        v.extend_from_slice(&(5u32 | SEGMENTED_FLAG).to_le_bytes());
        v.extend_from_slice(&5i32.to_le_bytes());
        v.extend_from_slice(&0i32.to_le_bytes());
        v.extend_from_slice(&1u32.to_le_bytes());
        v.extend_from_slice(&100i32.to_le_bytes());
        v.extend_from_slice(&5i32.to_le_bytes());
        v.extend_from_slice(&0u16.to_le_bytes()); // free list
        v
    }

    /// Hand-built GFF exercising the full segmented-chunk path:
    ///
    /// - One indexed ETME chunk (id 3, 4 bytes).
    /// - One indexed GFFI chunk holding a 2-entry secondary table.
    /// - One segmented TILE type with one segment run mapping resource
    ///   ids 100..=101 to entries 0..=1 of the GFFI secondary table.
    ///
    /// File layout:
    /// ```
    /// 0..28    file header
    /// 28..32   ETME-3 data ("hi!\0")
    /// 32..36   TILE-100 data ("til0")
    /// 36..40   TILE-101 data ("til1")
    /// 40..60   GFFI-0 data: 4-byte entryCount=2, then 2x (offset,size)
    /// 60..140  TOC (80 bytes)
    /// ```
    fn full_segmented_gff() -> Vec<u8> {
        let mut v = Vec::new();
        // Header.
        v.extend_from_slice(b"GFFI");
        v.extend_from_slice(&0x0003_0000u32.to_le_bytes());
        v.extend_from_slice(&28u32.to_le_bytes()); // data_location
        v.extend_from_slice(&60u32.to_le_bytes()); // toc_location
        v.extend_from_slice(&80u32.to_le_bytes()); // toc_length
        v.extend_from_slice(&0u32.to_le_bytes()); // file_flags
        v.extend_from_slice(&3u32.to_le_bytes()); // data0
        // Chunk data area (32 bytes).
        v.extend_from_slice(b"hi!\0"); // ETME-3
        v.extend_from_slice(b"til0"); // TILE-100
        v.extend_from_slice(b"til1"); // TILE-101
        // GFFI-0 (secondary table for TILE) at offset 40.
        v.extend_from_slice(&2u32.to_le_bytes()); // entryCount = 2
        v.extend_from_slice(&32u32.to_le_bytes()); // entry 0 offset
        v.extend_from_slice(&4u32.to_le_bytes()); //  entry 0 size
        v.extend_from_slice(&36u32.to_le_bytes()); // entry 1 offset
        v.extend_from_slice(&4u32.to_le_bytes()); //  entry 1 size
        // TOC at offset 60 (80 bytes).
        v.extend_from_slice(&8u32.to_le_bytes()); // types_offset
        v.extend_from_slice(&78u32.to_le_bytes()); // free_list_offset
        v.extend_from_slice(&3u16.to_le_bytes()); // num_types
        // Type 1: ETME indexed (20 bytes: 4 + 4 + 12).
        v.extend_from_slice(b"ETME");
        v.extend_from_slice(&1u32.to_le_bytes()); // chunk_count
        v.extend_from_slice(&3i32.to_le_bytes()); // id
        v.extend_from_slice(&28u32.to_le_bytes()); // location
        v.extend_from_slice(&4u32.to_le_bytes()); // length
        // Type 2: GFFI indexed (20 bytes).
        v.extend_from_slice(b"GFFI");
        v.extend_from_slice(&1u32.to_le_bytes());
        v.extend_from_slice(&0i32.to_le_bytes());
        v.extend_from_slice(&40u32.to_le_bytes());
        v.extend_from_slice(&20u32.to_le_bytes());
        // Type 3: TILE segmented (28 bytes: 4 + 4 + 12 + 8).
        v.extend_from_slice(b"TILE");
        v.extend_from_slice(&(2u32 | SEGMENTED_FLAG).to_le_bytes());
        v.extend_from_slice(&2i32.to_le_bytes()); // seg_count
        v.extend_from_slice(&0i32.to_le_bytes()); // seg_loc_id → GFFI chunk 0
        v.extend_from_slice(&1u32.to_le_bytes()); // num_entries
        v.extend_from_slice(&100i32.to_le_bytes()); // run.first_id
        v.extend_from_slice(&2i32.to_le_bytes()); // run.num_chunks
        v.extend_from_slice(&0u16.to_le_bytes()); // free list
        v
    }

    /// Like `full_segmented_gff` but with two segment runs:
    /// (first_id=200, n=2) and (first_id=900, n=1). Three resolved
    /// TILE chunks total.
    fn full_segmented_gff_multi_run() -> Vec<u8> {
        let mut v = Vec::new();
        v.extend_from_slice(b"GFFI");
        v.extend_from_slice(&0x0003_0000u32.to_le_bytes());
        v.extend_from_slice(&28u32.to_le_bytes());
        v.extend_from_slice(&72u32.to_le_bytes()); // toc_location
        v.extend_from_slice(&88u32.to_le_bytes()); // toc_length
        v.extend_from_slice(&0u32.to_le_bytes());
        v.extend_from_slice(&4u32.to_le_bytes());
        // ETME-3 data (4 bytes) at 28.
        v.extend_from_slice(b"hi!\0");
        // TILE-200 (4), TILE-201 (4), TILE-900 (4) at 32, 36, 40.
        v.extend_from_slice(b"t200");
        v.extend_from_slice(b"t201");
        v.extend_from_slice(b"t900");
        // GFFI-0 at offset 44, 28 bytes: 4 + 3*(4+4).
        v.extend_from_slice(&3u32.to_le_bytes()); // entryCount = 3
        v.extend_from_slice(&32u32.to_le_bytes()); v.extend_from_slice(&4u32.to_le_bytes());
        v.extend_from_slice(&36u32.to_le_bytes()); v.extend_from_slice(&4u32.to_le_bytes());
        v.extend_from_slice(&40u32.to_le_bytes()); v.extend_from_slice(&4u32.to_le_bytes());
        // TOC at offset 72 (28 bytes data + 16 bytes secondary table = 44; 44+28=72 — wait recompute).
        // 28 header + 4 ETME + 4*3 TILE data + 4 entryCount + 3*8 entries = 28+4+12+4+24 = 72. ✓
        v.extend_from_slice(&8u32.to_le_bytes()); // types_offset
        v.extend_from_slice(&86u32.to_le_bytes()); // free_list_offset
        v.extend_from_slice(&3u16.to_le_bytes()); // num_types
        // ETME (20 bytes)
        v.extend_from_slice(b"ETME");
        v.extend_from_slice(&1u32.to_le_bytes());
        v.extend_from_slice(&3i32.to_le_bytes());
        v.extend_from_slice(&28u32.to_le_bytes());
        v.extend_from_slice(&4u32.to_le_bytes());
        // GFFI (20 bytes)
        v.extend_from_slice(b"GFFI");
        v.extend_from_slice(&1u32.to_le_bytes());
        v.extend_from_slice(&0i32.to_le_bytes());
        v.extend_from_slice(&44u32.to_le_bytes());
        v.extend_from_slice(&28u32.to_le_bytes());
        // TILE segmented (4 + 4 + 12 + 16 = 36 bytes)
        v.extend_from_slice(b"TILE");
        v.extend_from_slice(&(3u32 | SEGMENTED_FLAG).to_le_bytes());
        v.extend_from_slice(&3i32.to_le_bytes());
        v.extend_from_slice(&0i32.to_le_bytes());
        v.extend_from_slice(&2u32.to_le_bytes()); // num_entries = 2 runs
        v.extend_from_slice(&200i32.to_le_bytes()); v.extend_from_slice(&2i32.to_le_bytes());
        v.extend_from_slice(&900i32.to_le_bytes()); v.extend_from_slice(&1i32.to_le_bytes());
        v.extend_from_slice(&0u16.to_le_bytes()); // free list
        v
    }

    #[test]
    fn parses_minimal_gff() {
        let bytes = minimal_gff();
        let gff = Gff::from_bytes(bytes).expect("parses");
        assert_eq!(gff.header().major_version(), 3);
        assert_eq!(gff.types().len(), 1);
        assert_eq!(gff.chunks().len(), 1);
        let c = &gff.chunks()[0];
        assert_eq!(c.kind, FourCC(*b"ETME"));
        assert_eq!(c.id, 7);
        assert_eq!(gff.read(FourCC(*b"ETME"), 7), Some(b"hi!\0".as_ref()));
        assert_eq!(gff.read(FourCC(*b"ETME"), 99), None);
    }

    #[test]
    fn rejects_segmented_without_gffi() {
        let bytes = mixed_gff_missing_gffi();
        let err = Gff::from_bytes(bytes).unwrap_err();
        assert!(
            matches!(err, GffError::MissingGffiType { kind } if kind == FourCC(*b"TILE")),
            "got: {err:?}"
        );
    }

    #[test]
    fn resolves_segmented_with_gffi() {
        let bytes = full_segmented_gff();
        let gff = Gff::from_bytes(bytes).expect("parses");
        assert_eq!(gff.types().len(), 3);
        // Chunks in TOC order: ETME-3, GFFI-0, TILE-100, TILE-101.
        let kinds: Vec<_> = gff.chunks().iter().map(|c| (c.kind, c.id)).collect();
        assert_eq!(
            kinds,
            vec![
                (FourCC(*b"ETME"), 3),
                (FourCC(*b"GFFI"), 0),
                (FourCC(*b"TILE"), 100),
                (FourCC(*b"TILE"), 101),
            ]
        );
        // Reading a segmented chunk by (kind, id) works through the
        // same API as indexed chunks.
        assert_eq!(gff.read(FourCC(*b"TILE"), 100), Some(b"til0".as_ref()));
        assert_eq!(gff.read(FourCC(*b"TILE"), 101), Some(b"til1".as_ref()));
        assert_eq!(gff.read(FourCC(*b"TILE"), 999), None);
    }

    #[test]
    fn resolves_segmented_multi_run() {
        let bytes = full_segmented_gff_multi_run();
        let gff = Gff::from_bytes(bytes).expect("parses");
        let kinds: Vec<_> = gff.chunks().iter().map(|c| (c.kind, c.id)).collect();
        assert_eq!(
            kinds,
            vec![
                (FourCC(*b"ETME"), 3),
                (FourCC(*b"GFFI"), 0),
                (FourCC(*b"TILE"), 200),
                (FourCC(*b"TILE"), 201),
                (FourCC(*b"TILE"), 900),
            ]
        );
        assert_eq!(gff.read(FourCC(*b"TILE"), 200), Some(b"t200".as_ref()));
        assert_eq!(gff.read(FourCC(*b"TILE"), 900), Some(b"t900".as_ref()));
    }

    #[test]
    fn rejects_bad_magic() {
        let mut bytes = minimal_gff();
        bytes[0] = b'X';
        let err = Gff::from_bytes(bytes).unwrap_err();
        assert!(matches!(err, GffError::BadMagic(_)), "got: {err:?}");
    }

    #[test]
    fn rejects_short_file() {
        let err = Gff::from_bytes(vec![0; 10]).unwrap_err();
        assert!(matches!(err, GffError::Truncated { .. }), "got: {err:?}");
    }

    #[test]
    fn fourcc_display() {
        assert_eq!(FourCC(*b"GPL ").to_string(), "GPL ");
        assert_eq!(FourCC(*b"ETME").to_string(), "ETME");
        assert_eq!(FourCC([0x01, b'A', 0x80, b'Z']).to_string(), "\\x01A\\x80Z");
    }

    #[test]
    fn fourcc_from_str() {
        assert_eq!(FourCC::from_str("GPL ").unwrap(), FourCC(*b"GPL "));
        assert!(matches!(
            FourCC::from_str("GPL").unwrap_err(),
            GffError::BadFourCC(_)
        ));
    }

    #[test]
    fn replace_same_size_in_place() {
        // 4-byte chunk replaced with 4 different bytes. File size
        // unchanged; (location, length) record unchanged.
        let original = minimal_gff();
        let gff = Gff::from_bytes(original.clone()).unwrap();
        let new = gff
            .replace_chunk(FourCC(*b"ETME"), 7, b"BYE!")
            .expect("replace");
        assert_eq!(new.len(), original.len());
        let reparsed = Gff::from_bytes(new).unwrap();
        assert_eq!(reparsed.read(FourCC(*b"ETME"), 7), Some(b"BYE!".as_ref()));
        assert_eq!(reparsed.chunks()[0].location, 28);
        assert_eq!(reparsed.chunks()[0].length, 4);
    }

    #[test]
    fn replace_smaller_fits_in_place() {
        // 4-byte chunk shrunk to 2 bytes; location stays, length
        // drops, bytes after the new content become dead.
        let gff = Gff::from_bytes(minimal_gff()).unwrap();
        let new = gff
            .replace_chunk(FourCC(*b"ETME"), 7, b"hi")
            .expect("replace");
        let reparsed = Gff::from_bytes(new).unwrap();
        assert_eq!(reparsed.read(FourCC(*b"ETME"), 7), Some(b"hi".as_ref()));
        assert_eq!(reparsed.chunks()[0].location, 28);
        assert_eq!(reparsed.chunks()[0].length, 2);
    }

    #[test]
    fn replace_larger_appends_to_end() {
        // 4-byte chunk grown to 8 bytes; new bytes appended past
        // original file end; (location, length) updated.
        let original = minimal_gff();
        let gff = Gff::from_bytes(original.clone()).unwrap();
        let new = gff
            .replace_chunk(FourCC(*b"ETME"), 7, b"longer!!")
            .expect("replace");
        assert_eq!(new.len(), original.len() + 8);
        let reparsed = Gff::from_bytes(new).unwrap();
        assert_eq!(
            reparsed.read(FourCC(*b"ETME"), 7),
            Some(b"longer!!".as_ref())
        );
        assert_eq!(reparsed.chunks()[0].location, original.len() as u32);
        assert_eq!(reparsed.chunks()[0].length, 8);
    }

    #[test]
    fn replace_segmented_chunk_updates_secondary_table() {
        // Segmented TILE chunk replaced with a same-size value. The
        // chunk's secondary-table (offset, length) entry should be
        // unchanged (same location, same length).
        let original = full_segmented_gff();
        let gff = Gff::from_bytes(original.clone()).unwrap();
        let new = gff
            .replace_chunk(FourCC(*b"TILE"), 101, b"XXXX")
            .expect("replace");
        let reparsed = Gff::from_bytes(new).unwrap();
        assert_eq!(
            reparsed.read(FourCC(*b"TILE"), 101),
            Some(b"XXXX".as_ref())
        );
        // TILE 100 untouched.
        assert_eq!(
            reparsed.read(FourCC(*b"TILE"), 100),
            Some(b"til0".as_ref())
        );
    }

    #[test]
    fn replace_nonexistent_chunk_errors() {
        let gff = Gff::from_bytes(minimal_gff()).unwrap();
        let err = gff
            .replace_chunk(FourCC(*b"ETME"), 99, b"nope")
            .unwrap_err();
        assert!(matches!(err, GffError::ChunkNotFound { .. }));
    }

    #[test]
    fn fourcc_serializes_as_display_string() {
        let json = serde_json::to_string(&FourCC(*b"GPL ")).unwrap();
        assert_eq!(json, "\"GPL \"");
        let json_escape = serde_json::to_string(&FourCC([0x01, b'A', 0x80, b'Z'])).unwrap();
        assert_eq!(json_escape, "\"\\\\x01A\\\\x80Z\"");
    }

    #[test]
    fn chunk_ref_serializes_without_meta_offset() {
        let chunk = ChunkRef {
            kind: FourCC(*b"ETME"),
            id: 7,
            location: 28,
            length: 4,
            meta_offset: 999, // should be absent from JSON
        };
        let json = serde_json::to_string(&chunk).unwrap();
        assert!(json.contains("\"kind\":\"ETME\""), "got: {json}");
        assert!(json.contains("\"id\":7"), "got: {json}");
        assert!(!json.contains("meta_offset"), "got: {json}");
        assert!(!json.contains("999"), "got: {json}");
    }

    #[test]
    fn replace_with_same_bytes_is_byte_identical() {
        // No-op round-trip: replace a chunk with its own bytes and
        // verify the result is byte-identical to the input.
        let original = minimal_gff();
        let gff = Gff::from_bytes(original.clone()).unwrap();
        let chunk = &gff.chunks()[0];
        let same: Vec<u8> = gff.read_chunk(chunk).to_vec();
        let kind = chunk.kind;
        let id = chunk.id;
        let new = gff.replace_chunk(kind, id, &same).expect("replace");
        assert_eq!(new, original);
    }
}
