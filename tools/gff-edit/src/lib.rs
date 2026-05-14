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
//! # Coverage of GFF features in this version (v0.1)
//!
//! - **Indexed chunk lists** are fully parsed; their `ChunkRef`s
//!   appear in [`Gff::chunks`] and chunk bytes can be read via
//!   [`Gff::read`].
//! - **Segmented chunk lists** are parsed at the type level
//!   (kind, chunk count, seg_count, seg_loc_id, seg_entries) and
//!   surfaced via [`Gff::types`], but their individual chunk
//!   locations are not yet resolved. Resolving requires a
//!   cross-reference into the file's `GFFI` chunk; that lands in
//!   v0.2 along with `gff-cat extract`. Segmented types contribute
//!   nothing to [`Gff::chunks`] in v0.1.

use std::fmt;
use std::fs;
use std::path::Path;

use thiserror::Error;

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

    /// Flat list of chunk references for **indexed** types. In v0.1,
    /// chunks belonging to segmented types do not appear here.
    pub fn chunks(&self) -> &[ChunkRef] {
        &self.chunks
    }

    /// Find an indexed chunk by FOURCC and resource id.
    pub fn find(&self, kind: FourCC, id: i32) -> Option<&ChunkRef> {
        self.chunks.iter().find(|c| c.kind == kind && c.id == id)
    }

    /// Borrow the raw bytes of an indexed chunk by (kind, id).
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
}

/// GFF file header (28 bytes). See docs/file-formats.md §1.
#[derive(Debug, Clone, Copy)]
pub struct FileHeader {
    /// Magic bytes; always "GFFI" for a valid file.
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
#[derive(Debug, Clone)]
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

/// On-disk metadata for a segmented chunk list. Individual chunk
/// locations require a `GFFI` cross-reference, deferred to v0.2.
#[derive(Debug, Clone)]
pub struct SegmentedInfo {
    pub seg_count: i32,
    pub seg_loc_id: i32,
    pub seg_entries: Vec<SegEntry>,
}

/// One entry in a segmented type's segment-reference table.
#[derive(Debug, Clone, Copy)]
pub struct SegEntry {
    pub first_id: i32,
    pub num_chunks: i32,
}

/// A reference to a chunk in the GFF: its kind, id, on-disk offset,
/// and byte length. Borrowing the chunk data lives on `Gff::read`.
#[derive(Debug, Clone, Copy)]
pub struct ChunkRef {
    pub kind: FourCC,
    pub id: i32,
    pub location: u32,
    pub length: u32,
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

    let mut types = Vec::with_capacity(num_types);
    let mut chunks = Vec::new();

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
            types.push(TypeInfo {
                kind,
                chunk_count,
                segmented: Some(SegmentedInfo {
                    seg_count,
                    seg_loc_id,
                    seg_entries,
                }),
            });
        } else {
            let entries_size = chunk_count
                .checked_mul(12)
                .ok_or(GffError::TocTypesTruncated { num_types, offset: cursor })?;
            if cursor + entries_size > toc.len() {
                return Err(GffError::TocTypesTruncated { num_types, offset: cursor });
            }
            for _ in 0..chunk_count {
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
                chunks.push(ChunkRef {
                    kind,
                    id,
                    location,
                    length,
                });
            }
            types.push(TypeInfo {
                kind,
                chunk_count,
                segmented: None,
            });
        }
    }

    Ok((types, chunks))
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

    /// Hand-built GFF with one indexed type and one segmented type.
    fn mixed_gff() -> Vec<u8> {
        // 4 bytes of "indexed" chunk data + 0 bytes for segmented (no
        // real data needed; we only test the TOC parse).
        let mut v = Vec::new();
        v.extend_from_slice(b"GFFI");
        v.extend_from_slice(&0x0003_0000u32.to_le_bytes()); // version
        v.extend_from_slice(&28u32.to_le_bytes()); // data_location
        v.extend_from_slice(&32u32.to_le_bytes()); // toc_location
        // TOC = 8 (header) + 2 (num_types) + (8 + 12) (indexed) + (8 + 12 + 8) (segmented) + 2 (free) = 60
        v.extend_from_slice(&60u32.to_le_bytes()); // toc_length
        v.extend_from_slice(&0u32.to_le_bytes()); // file_flags
        v.extend_from_slice(&2u32.to_le_bytes()); // data0
        v.extend_from_slice(b"hi!\0"); // 4 bytes
        // TOC
        v.extend_from_slice(&8u32.to_le_bytes()); // types_offset
        v.extend_from_slice(&58u32.to_le_bytes()); // free_list_offset
        v.extend_from_slice(&2u16.to_le_bytes()); // num_types
        // Type 1: ETME indexed, 1 chunk
        v.extend_from_slice(b"ETME");
        v.extend_from_slice(&1u32.to_le_bytes()); // chunk_count
        v.extend_from_slice(&3i32.to_le_bytes()); // id
        v.extend_from_slice(&28u32.to_le_bytes()); // location
        v.extend_from_slice(&4u32.to_le_bytes()); // length
        // Type 2: TILE segmented, 5 chunks, 1 seg entry
        v.extend_from_slice(b"TILE");
        v.extend_from_slice(&(5u32 | SEGMENTED_FLAG).to_le_bytes()); // chunk_count with seg flag
        v.extend_from_slice(&5i32.to_le_bytes()); // seg_count
        v.extend_from_slice(&0i32.to_le_bytes()); // seg_loc_id
        v.extend_from_slice(&1u32.to_le_bytes()); // num_entries
        v.extend_from_slice(&100i32.to_le_bytes()); // first_id
        v.extend_from_slice(&5i32.to_le_bytes()); // num_chunks
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
    fn parses_mixed_indexed_and_segmented() {
        let bytes = mixed_gff();
        let gff = Gff::from_bytes(bytes).expect("parses");
        assert_eq!(gff.types().len(), 2);
        // Indexed type contributes to chunks().
        assert_eq!(gff.chunks().len(), 1);
        // Type 1: indexed ETME with 1 chunk.
        assert_eq!(gff.types()[0].kind, FourCC(*b"ETME"));
        assert_eq!(gff.types()[0].chunk_count, 1);
        assert!(!gff.types()[0].is_segmented());
        // Type 2: segmented TILE with 5 logical chunks (high bit stripped),
        // 1 seg entry mapping id 100..=104.
        assert_eq!(gff.types()[1].kind, FourCC(*b"TILE"));
        assert_eq!(gff.types()[1].chunk_count, 5);
        assert!(gff.types()[1].is_segmented());
        let seg = gff.types()[1].segmented.as_ref().unwrap();
        assert_eq!(seg.seg_count, 5);
        assert_eq!(seg.seg_loc_id, 0);
        assert_eq!(seg.seg_entries.len(), 1);
        assert_eq!(seg.seg_entries[0].first_id, 100);
        assert_eq!(seg.seg_entries[0].num_chunks, 5);
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
}
