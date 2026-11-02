//! Overlay flattening for Borland VROOM executables (Dark Sun `DSUN.EXE`).
//!
//! REA/Ghidra's MZ lane maps only the initialized module, which excludes the
//! Borland overlay area where most of the games' code lives. `ovr-carve`
//! rewrites an overlaid executable into an *analysis* MZ whose initialized
//! module spans the whole file, so overlay code decompiles alongside the
//! resident image. The transform (docs/overlay-formats.md sections 2-5):
//!
//! 1. Every byte keeps its original file offset, so every file offset the
//!    rest of the toolkit publishes (syms catalogues, fix writeups, ovr-map
//!    output) stays valid in the carved image.
//! 2. Each overlay module's per-module relocation table is applied in place.
//!    A stored word is a segtab BYTE offset (record = v >> 3, low 3 bits
//!    tag, bit0 = the overlay marker the runtime slow path would need; never
//!    set in the shipped corpus, and refused here because the slow path's
//!    pattern rewrite has no static equivalent). The word is rewritten to
//!    `load_segment + segtab[record].start_para`, the same value the runtime
//!    applier (`module[e] = segtab_word[v & ~7]`) would leave under REA's
//!    fixed load segment 0x1000.
//! 3. The MZ header's page fields (`e_cblp`/`e_cp`) are extended so the
//!    initialized module spans the file; the FBOV header, descriptor chain,
//!    stub blocks and the now-spent relocation tables stay mapped as data.
//!    The resident image's own relocation table is untouched.
//!
//! The output is an analysis artifact only: not runnable, not shipped. The
//! module map comes from `ovr-map --json` (one descriptor-walk
//! implementation, the same contract `exe-patch` consumes); the exeinfo
//! segtab arrives in that JSON since ovr-map 0.4.0.

use std::collections::BTreeMap;
use std::path::Path;
use std::process::Command;

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// REA's fixed MZ load segment; the value rewritten relocation words assume.
pub const DEFAULT_LOAD_SEGMENT: u16 = 0x1000;

#[derive(Debug, Error)]
pub enum CarveError {
    #[error("module {module}: relocation entry {entry} is outside its module (size {size})")]
    RelocEntryOutOfRange {
        module: usize,
        entry: u64,
        size: u64,
    },
    #[error("module {module}: relocation table byte count {raw} is odd")]
    OddRelocTableSize { module: usize, raw: u64 },
    #[error(
        "module {module}: relocation word at entry offset {entry} is {value:#06x}; \
         the overlay-marker bit (bit0) is set and the runtime slow path has no \
         static equivalent, so the word cannot be resolved"
    )]
    MarkerBitSet {
        module: usize,
        entry: u64,
        value: u16,
    },
    #[error(
        "module {module}: relocation word at entry offset {entry} is {value:#06x}; \
         segtab record {record} is out of range (segnum {segnum}). Was the input \
         already carved?"
    )]
    RelocRecordOutOfRange {
        module: usize,
        entry: u64,
        value: u16,
        record: u64,
        segnum: u64,
    },
    #[error(
        "relocation word in module {module} resolves to segment \
         {load_segment:#06x}+{start_para:#06x}, which does not fit 16 bits"
    )]
    RelocOverflow {
        module: usize,
        load_segment: u16,
        start_para: u16,
    },
    #[error(
        "MZ image end 0x{image_end:x} already covers the file length 0x{len:x}; \
         the input looks already carved (or is not an overlaid image)"
    )]
    AlreadyFlat { image_end: u64, len: u64 },
    #[error(
        "module {module}: payload file offset 0x{file_start:x} minus the MZ header \
         0x{header_size:x} is not a multiple of 16; linear addressing would be wrong"
    )]
    UnalignedPayload {
        module: usize,
        file_start: u64,
        header_size: u64,
    },
    #[error("file length {len} does not fit the MZ page fields (max 33554431)")]
    TooLarge { len: u64 },
    #[error(
        "segtab has {have} records but fbov.segnum says {want}; the map JSON \
             predates ovr-map 0.4.0 or is inconsistent"
    )]
    SegtabCountMismatch { have: usize, want: u64 },
    #[error("module {module} file range 0x{start:x}..0x{end:x} runs past EOF 0x{len:x}")]
    ModulePastEof {
        module: usize,
        start: u64,
        end: u64,
        len: u64,
    },
    #[error("relocation table for module {module} runs past EOF")]
    TablePastEof { module: usize },
    #[error("verify: expected length {expected}, found {found}")]
    VerifyLengthMismatch { expected: u64, found: u64 },
    #[error("verify: byte 0x{offset:x} differs (expected 0x{expected:02x}, found 0x{found:02x})")]
    VerifyMismatch {
        offset: u64,
        expected: u8,
        found: u8,
    },
}

/// The `ovr-map --json` subset ovr-carve consumes. Unknown keys are ignored,
/// so minor ovr-map additions never break the reader.
#[derive(Debug, Deserialize)]
pub struct OvrMap {
    pub mz: Mz,
    pub fbov: Fbov,
    /// exeinfo segment load table; `#[serde(default)]` so a pre-0.4.0 map
    /// produces our typed mismatch error instead of serde's.
    #[serde(default)]
    pub segtab: Vec<SegtabRecord>,
    pub segments: Vec<Module>,
}

#[derive(Debug, Deserialize)]
pub struct Mz {
    pub header_size: u64,
    pub image_end: u64,
}

#[derive(Debug, Deserialize)]
pub struct Fbov {
    pub exeinfo: u64,
    pub segnum: u64,
}

#[derive(Debug, Deserialize)]
pub struct SegtabRecord {
    pub start_para: u16,
    pub cls: u16,
}

#[derive(Debug, Deserialize)]
pub struct StubEntry {
    pub entry_offset: u64,
    pub file_offset: u64,
}

#[derive(Debug, Deserialize)]
pub struct Module {
    pub index: usize,
    pub size: u64,
    pub relocation_count: u64,
    pub file_start: u64,
    pub file_end: u64,
    pub empty: bool,
    #[serde(default)]
    pub entries: Vec<StubEntry>,
}

/// What the carve changed, per module and in aggregate. The per-game totals
/// are corpus constants (DS1 8,232 entries, DS2 8,262) the tests pin.
#[derive(Debug, Default, PartialEq, Serialize)]
pub struct Stats {
    pub applied: u64,
    pub markers: u64,
    pub per_module: Vec<(usize, u64)>,
    pub tag_histogram: BTreeMap<u16, u64>,
    pub target_classes: BTreeMap<u16, u64>,
}

/// Address mapping of the carved image: every module and entry stub in both
/// coordinate systems (original file offsets, and the synthetic segment /
/// linear addresses REA reports under the fixed load segment).
#[derive(Debug, PartialEq, Serialize)]
pub struct Mapping {
    pub load_segment: u16,
    pub header_size: u64,
    pub modules: Vec<ModuleMapping>,
}

#[derive(Debug, PartialEq, Serialize)]
pub struct ModuleMapping {
    pub index: usize,
    pub file_start: u64,
    pub size: u64,
    pub segment: u16,
    pub linear_start: u32,
    pub entries: Vec<EntryMapping>,
}

#[derive(Debug, PartialEq, Serialize)]
pub struct EntryMapping {
    /// Entry offset within the module (the stub's `entry_offset`).
    pub offset: u64,
    /// File offset in the pristine image (entries keep their offsets).
    pub file_offset: u64,
    pub linear: u32,
}

#[derive(Debug, PartialEq)]
pub struct Carved {
    pub output: Vec<u8>,
    pub mapping: Mapping,
    pub stats: Stats,
}

fn read_u16(data: &[u8], pos: u64) -> u16 {
    u16::from_le_bytes([data[pos as usize], data[pos as usize + 1]])
}

fn write_u16(data: &mut [u8], pos: u64, value: u16) {
    let bytes = value.to_le_bytes();
    data[pos as usize] = bytes[0];
    data[pos as usize + 1] = bytes[1];
}

/// Apply the flatten transform. `pristine` must be the untouched image the
/// map was generated from; the map's file offsets index into it directly.
pub fn carve(pristine: &[u8], map: &OvrMap, load_segment: u16) -> Result<Carved, CarveError> {
    let header_size = map.mz.header_size;
    let len = pristine.len() as u64;
    if map.mz.image_end >= len {
        return Err(CarveError::AlreadyFlat {
            image_end: map.mz.image_end,
            len,
        });
    }
    if map.segtab.len() as u64 != map.fbov.segnum {
        return Err(CarveError::SegtabCountMismatch {
            have: map.segtab.len(),
            want: map.fbov.segnum,
        });
    }

    let mut out = pristine.to_vec();
    let mut stats = Stats::default();
    let mut modules = Vec::new();

    for module in &map.segments {
        if module.empty {
            stats.per_module.push((module.index, 0));
            continue;
        }
        if module.file_end > len {
            return Err(CarveError::ModulePastEof {
                module: module.index,
                start: module.file_start,
                end: module.file_end,
                len,
            });
        }
        if !(module.file_start - header_size).is_multiple_of(16) {
            return Err(CarveError::UnalignedPayload {
                module: module.index,
                file_start: module.file_start,
                header_size,
            });
        }
        if module.relocation_count % 2 != 0 {
            return Err(CarveError::OddRelocTableSize {
                module: module.index,
                raw: module.relocation_count,
            });
        }
        let table = module.file_start + module.size;
        if table + module.relocation_count > len {
            return Err(CarveError::TablePastEof {
                module: module.index,
            });
        }

        let count = module.relocation_count / 2;
        for i in 0..count {
            let entry = read_u16(pristine, table + 2 * i) as u64;
            if entry >= module.size {
                return Err(CarveError::RelocEntryOutOfRange {
                    module: module.index,
                    entry,
                    size: module.size,
                });
            }
            let pos = module.file_start + entry;
            let value = read_u16(pristine, pos);
            let tag = value & 7;
            if tag & 1 != 0 {
                return Err(CarveError::MarkerBitSet {
                    module: module.index,
                    entry,
                    value,
                });
            }
            *stats.tag_histogram.entry(tag).or_default() += 1;
            let record = (value >> 3) as u64;
            let rec = map.segtab.get(record as usize).ok_or({
                CarveError::RelocRecordOutOfRange {
                    module: module.index,
                    entry,
                    value,
                    record,
                    segnum: map.fbov.segnum,
                }
            })?;
            let new = u16::try_from(load_segment as u32 + rec.start_para as u32).map_err(|_| {
                CarveError::RelocOverflow {
                    module: module.index,
                    load_segment,
                    start_para: rec.start_para,
                }
            })?;
            write_u16(&mut out, pos, new);
            *stats.target_classes.entry(rec.cls).or_default() += 1;
            stats.applied += 1;
        }
        stats.per_module.push((module.index, count));

        let module_base = (module.file_start - header_size) as u32;
        let segment = u16::try_from(load_segment as u32 + module_base / 16).map_err(|_| {
            CarveError::RelocOverflow {
                module: module.index,
                load_segment,
                start_para: (module_base / 16) as u16,
            }
        })?;
        // Entry stubs live in the resident image (the descriptor chain), so
        // their offsets are already file offsets in the pristine layout.
        let entries = module
            .entries
            .iter()
            .map(|e| EntryMapping {
                offset: e.entry_offset,
                file_offset: e.file_offset,
                linear: (load_segment as u32) * 16 + (e.file_offset - header_size) as u32,
            })
            .collect();
        modules.push(ModuleMapping {
            index: module.index,
            file_start: module.file_start,
            size: module.size,
            segment,
            linear_start: (load_segment as u32) * 16 + module_base,
            entries,
        });
    }

    // e_cblp = bytes on the last page (0 means the page is full); e_cp = pages.
    let (e_cblp, e_cp) = if len.is_multiple_of(512) {
        (0u64, len / 512)
    } else {
        (len % 512, len / 512 + 1)
    };
    let e_cblp = u16::try_from(e_cblp).map_err(|_| CarveError::TooLarge { len })?;
    let e_cp = u16::try_from(e_cp).map_err(|_| CarveError::TooLarge { len })?;
    write_u16(&mut out, 2, e_cblp);
    write_u16(&mut out, 4, e_cp);

    let mapping = Mapping {
        load_segment,
        header_size,
        modules,
    };
    Ok(Carved {
        output: out,
        mapping,
        stats,
    })
}

/// Byte-exact check that `carved` is what carving `pristine` produces.
pub fn verify(
    pristine: &[u8],
    map: &OvrMap,
    carved: &[u8],
    load_segment: u16,
) -> Result<(), CarveError> {
    let expected = carve(pristine, map, load_segment)?;
    if expected.output.len() as u64 != carved.len() as u64 {
        return Err(CarveError::VerifyLengthMismatch {
            expected: expected.output.len() as u64,
            found: carved.len() as u64,
        });
    }
    for (i, (e, f)) in expected.output.iter().zip(carved).enumerate() {
        if e != f {
            return Err(CarveError::VerifyMismatch {
                offset: i as u64,
                expected: *e,
                found: *f,
            });
        }
    }
    Ok(())
}

#[derive(Debug, Error)]
pub enum MapError {
    #[error("ovr-map script not found at {path}: run it from a repo checkout or pass --ovr-map")]
    ScriptMissing { path: std::path::PathBuf },
    #[error("ovr-map failed on {exe}: {stderr}")]
    OvrMapFailed {
        exe: std::path::PathBuf,
        stderr: String,
    },
    #[error("ovr-map emitted invalid JSON: {0}")]
    InvalidJson(#[from] serde_json::Error),
    #[error("ovr-map subprocess failed: {0}")]
    Spawn(#[from] std::io::Error),
}

/// Run `ovr-map --json` on `exe` (the same contract `exe-patch` consumes)
/// and parse the map. The script defaults to the repo-tree sibling next to
/// this crate; override with `--ovr-map` or `$OVR_MAP_PY`.
pub fn fetch_map(exe: &Path, ovr_map_py: &Path) -> Result<OvrMap, MapError> {
    if !ovr_map_py.is_file() {
        return Err(MapError::ScriptMissing {
            path: ovr_map_py.to_path_buf(),
        });
    }
    let out = Command::new("python3")
        .arg(ovr_map_py)
        .arg(exe)
        .arg("--json")
        .output()?;
    if !out.status.success() {
        return Err(MapError::OvrMapFailed {
            exe: exe.to_path_buf(),
            stderr: String::from_utf8_lossy(&out.stderr).trim().to_string(),
        });
    }
    Ok(serde_json::from_slice(&out.stdout)?)
}

/// Default ovr-map.py location: the sibling tool in the repo tree, the same
/// assumption `exe-patch` makes. `$OVR_MAP_PY` overrides.
pub fn default_ovr_map_path() -> std::path::PathBuf {
    if let Some(p) = std::env::var_os("OVR_MAP_PY") {
        return std::path::PathBuf::from(p);
    }
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../ovr-map/ovr-map.py")
}

/// A minimal Borland-overlaid MZ mirroring `exe-patch`'s fixture builder,
/// extended with the exeinfo segtab and MZ relocations the carve resolves.
/// Layout (all offsets are file offsets):
///
/// - `0x00..0x20` MZ header: image 0x20..0x200, 2 relocations at 0x1c
/// - `0x20..0x40` resident code (nops)
/// - `0x40..0x50` segtab: record 0 (start_para 0x10, class 1 code),
///   record 1 (start_para 0x11, class 3 stub block)
/// - `0x50`       a relocated code word (MZ reloc target)
/// - `0x60`       descriptor 0: payload 0x000, size 0x10, 1 relocation,
///   1 stub (entry 0)
/// - `0x90`       descriptor 1: payload 0x020, size 0x08, no relocations,
///   1 stub (entry 0)
/// - `0x200`      FBOV header (ovrsize 0x28, exeinfo 0x40, segnum 2)
/// - `0x210..0x220` module 0 code: two far calls whose segment words are
///   the segtab byte offsets 0x0000 (record 0) and 0x0008 (record 1)
/// - `0x220..0x224` module 0 relocation table: entries 3 and 8
/// - `0x230..0x238` module 1 code
pub fn fixture() -> Vec<u8> {
    let mut b = vec![0u8; 0x238];
    b[0..2].copy_from_slice(b"MZ");
    b[2..4].copy_from_slice(&0x200u16.to_le_bytes()); // e_cblp
    b[4..6].copy_from_slice(&1u16.to_le_bytes()); // e_cp -> image_end 0x200
    b[6..8].copy_from_slice(&2u16.to_le_bytes()); // e_crlc
    b[8..10].copy_from_slice(&2u16.to_le_bytes()); // e_cparhdr -> header 0x20
    b[0x18..0x1a].copy_from_slice(&0x1Cu16.to_le_bytes()); // e_lfarlc
    // MZ relocations: a code word at 0x50, and segtab record 0's word0 at
    // 0x40 (docs/overlay-formats.md section 2: every record word0 is the
    // target of exactly one MZ relocation).
    b[0x1c..0x20].copy_from_slice(&[0x30, 0x00, 0x00, 0x00]);
    b[0x20..0x24].copy_from_slice(&[0x00, 0x00, 0x02, 0x00]);
    b[0x20..0x40].fill(0x90);
    let segtab: [(u16, u16, u16, u16); 2] = [(0x10, 0x100, 1, 0), (0x11, 0x80, 3, 0)];
    for (i, (start_para, size, cls, x)) in segtab.iter().enumerate() {
        let pos = 0x40 + 8 * i as u64;
        for (field, value) in [start_para, size, cls, x].iter().enumerate() {
            let at = pos + 2 * field as u64;
            b[at as usize..at as usize + 2].copy_from_slice(&value.to_le_bytes());
        }
    }
    b[0x50..0x52].copy_from_slice(&0x1234u16.to_le_bytes());
    b[0x52..0x60].fill(0x90);

    let desc = |payload: u32, size: u16, nrelocs: u16, entries: &[u16]| -> Vec<u8> {
        let mut d = Vec::new();
        d.extend_from_slice(b"\xcd\x3f\x00\x00");
        d.extend_from_slice(&payload.to_le_bytes());
        d.extend_from_slice(&size.to_le_bytes());
        d.extend_from_slice(&nrelocs.to_le_bytes());
        d.extend_from_slice(&1u32.to_le_bytes());
        d.extend_from_slice(&[0u8; 16]);
        for eo in entries {
            d.extend_from_slice(b"\xcd\x3f");
            d.extend_from_slice(&eo.to_le_bytes());
            d.push(0);
        }
        d
    };
    b[0x60..0x60 + 37].copy_from_slice(&desc(0x000, 0x10, 2, &[0]));
    b[0x90..0x90 + 37].copy_from_slice(&desc(0x020, 0x08, 0, &[0]));

    b[0x200..0x204].copy_from_slice(b"FBOV");
    b[0x204..0x208].copy_from_slice(&0x28u32.to_le_bytes());
    b[0x208..0x20c].copy_from_slice(&0x40u32.to_le_bytes());
    b[0x20c..0x210].copy_from_slice(&2u32.to_le_bytes());

    // Module 0: two far calls; segment words are segtab byte offsets.
    b[0x210] = 0x9a;
    b[0x211..0x213].copy_from_slice(&0x0034u16.to_le_bytes());
    b[0x213..0x215].copy_from_slice(&0x0000u16.to_le_bytes());
    b[0x215] = 0x9a;
    b[0x216..0x218].copy_from_slice(&0x0011u16.to_le_bytes());
    b[0x218..0x21a].copy_from_slice(&0x0008u16.to_le_bytes());
    b[0x21a..0x220].fill(0x90);
    // Module 0 relocation table: the two segment words, at module offsets 3 and 8.
    b[0x220..0x222].copy_from_slice(&3u16.to_le_bytes());
    b[0x222..0x224].copy_from_slice(&8u16.to_le_bytes());
    // Module 1: a bare retf.
    b[0x230] = 0xcb;
    b[0x231..0x238].fill(0x90);
    b
}

/// The ovr-map JSON for [`fixture`], so tests need no subprocess.
pub fn fixture_map() -> OvrMap {
    serde_json::from_str(
        r##"
    {
      "mz": {"header_size": 32, "image_end": 512, "relocation_count": 2, "relocation_table": 28},
      "fbov": {"ovrsize": 40, "exeinfo": 64, "segnum": 2, "overlay_base": 528},
      "segtab": [
        {"start_para": 16, "size": 256, "cls": 1, "x": 0},
        {"start_para": 17, "size": 128, "cls": 3, "x": 0}
      ],
      "segments": [
        {"index": 0, "descriptor_offset": 96, "payload_offset": 0, "size": 16,
         "relocation_count": 4, "file_start": 528, "file_end": 544, "empty": false,
         "entries": [{"stub_offset": 128, "entry_offset": 0, "file_offset": 528, "overlay": 0}]},
        {"index": 1, "descriptor_offset": 144, "payload_offset": 32, "size": 8,
         "relocation_count": 0, "file_start": 560, "file_end": 568, "empty": false,
         "entries": [{"stub_offset": 176, "entry_offset": 0, "file_offset": 560, "overlay": 0}]}
      ]
    }
    "##,
    )
    .expect("fixture map parses")
}
