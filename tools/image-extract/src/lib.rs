//! image-extract: Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`,
//! `BMAP`, `OMAP`) decoded to PNG with palette applied.
//!
//! v0.1.0 ports libgff's bitmap and palette code:
//!
//! - **Palette** (`PAL ` / `CPAL` chunks): 768 bytes = 256 × RGB
//!   6-bit channels. libgff multiplies by 4 (`intensity_multiplier`)
//!   to map 6-bit values onto 8-bit output.
//! - **Bitmap chunk header**: 6 bytes preamble + u16 `frame_count`
//!   at +4 + u32 per-frame offset table at +6. Each frame at its
//!   offset is `u16 width + u16 height + 1 unknown byte + 4 bytes
//!   `frame_type` ("PLNR" / "PLAN" / DS1 RLE)`.
//! - **DS1 RLE** (the common case for PORT chunks): per-row
//!   `byte row_num` (0xFF terminates), then sub-spans of `startx /
//!   flags / 1 unknown / compressed_length / RLE codes`. Each RLE
//!   code's low bit picks even (direct palette indices) or odd
//!   (repeated single index). Image is stored bottom-up; rows
//!   placed at `height - row_num - 1`.
//! - **PLNR** (bit-packed dictionary, less common): `bits_per_symbol`
//!   byte + dictionary + bit-packed symbol stream via
//!   `plnr_get_next` (4-bit-rotated bit-order).
//! - **PLAN**: libgff says "not implemented"; we surface an error.
//!
//! All ports MIT-licensed from `dsoageofheroes/libgff`
//! `src/gpl/image.c`. See [`../../CREDITS.md`](../../CREDITS.md)
//! for the per-feature attribution.

use std::fmt;
use std::path::Path;

use thiserror::Error;

/// Number of palette entries in a single `PAL ` / `CPAL` chunk.
pub const PALETTE_SIZE: usize = 256;

/// libgff's intensity_multiplier: 6-bit palette values (0..=63)
/// scale to 8-bit output by × 4.
pub const INTENSITY_MULTIPLIER: u8 = 4;

/// Size in bytes of a single PAL/CPAL chunk (256 × RGB).
pub const PALETTE_CHUNK_LEN: usize = PALETTE_SIZE * 3;

#[derive(Debug, Error)]
pub enum ImageError {
    #[error("palette chunk has wrong length: expected {expected}, got {actual}")]
    PaletteLength { expected: usize, actual: usize },
    #[error("bitmap chunk too short to read header: {len} bytes")]
    HeaderTruncated { len: usize },
    #[error("frame {frame} out of range (count={count})")]
    FrameOutOfRange { frame: usize, count: usize },
    #[error("frame offset table truncated")]
    FrameTableTruncated,
    #[error("frame body out of bounds at offset {offset}")]
    FrameOutOfBounds { offset: usize },
    #[error("frame {frame} type '{kind}' is not yet supported")]
    UnsupportedFrameType { frame: usize, kind: String },
    #[error("PLNR bit slice spans byte boundary; libgff doesn't implement this either")]
    PlnrSplitBits,
    #[error("ds1 RLE decode error at row offset {row_offset}")]
    Ds1RleError { row_offset: usize },
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("png encoding: {0}")]
    Png(#[from] png::EncodingError),
}

pub type Result<T> = std::result::Result<T, ImageError>;

/// One RGB color entry. 8-bit channels after the 6-bit → 8-bit
/// `INTENSITY_MULTIPLIER` scaling that libgff applies on load.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Color {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

/// A 256-entry palette parsed from a `PAL ` or `CPAL` chunk.
#[derive(Debug, Clone)]
pub struct Palette {
    pub colors: [Color; PALETTE_SIZE],
}

impl Palette {
    /// Parse a palette chunk (768 bytes of 6-bit RGB triples,
    /// scaled by `INTENSITY_MULTIPLIER`).
    ///
    /// Ported from `dsoageofheroes/libgff` `src/gpl/image.c`
    /// `gff_palettes_read_type` (MIT).
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        if bytes.len() != PALETTE_CHUNK_LEN {
            return Err(ImageError::PaletteLength {
                expected: PALETTE_CHUNK_LEN,
                actual: bytes.len(),
            });
        }
        let mut colors = [Color { r: 0, g: 0, b: 0 }; PALETTE_SIZE];
        for i in 0..PALETTE_SIZE {
            colors[i] = Color {
                r: bytes[i * 3].saturating_mul(INTENSITY_MULTIPLIER),
                g: bytes[i * 3 + 1].saturating_mul(INTENSITY_MULTIPLIER),
                b: bytes[i * 3 + 2].saturating_mul(INTENSITY_MULTIPLIER),
            };
        }
        Ok(Palette { colors })
    }

    /// Flat `[u8; 768]` of RGB triples for PNG palette chunks.
    pub fn as_rgb_bytes(&self) -> [u8; PALETTE_CHUNK_LEN] {
        let mut out = [0u8; PALETTE_CHUNK_LEN];
        for (i, c) in self.colors.iter().enumerate() {
            out[i * 3] = c.r;
            out[i * 3 + 1] = c.g;
            out[i * 3 + 2] = c.b;
        }
        out
    }
}

/// A decoded bitmap frame: palette indices laid out top-to-bottom,
/// left-to-right (PNG conventional order; the original game
/// stores rows bottom-up but `decode_frame` flips them back to
/// match libgff's `create_ds1_rgba` output).
#[derive(Debug, Clone)]
pub struct Frame {
    pub width: u16,
    pub height: u16,
    pub frame_type: FrameType,
    /// Palette indices, length = width * height.
    pub indices: Vec<u8>,
}

/// Encoding variants we recognise inside a frame.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameType {
    Ds1Rle,
    Plnr,
    Plan,
    Unknown([u8; 4]),
}

impl fmt::Display for FrameType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FrameType::Ds1Rle => write!(f, "DS1_RLE"),
            FrameType::Plnr => write!(f, "PLNR"),
            FrameType::Plan => write!(f, "PLAN"),
            FrameType::Unknown(bytes) => {
                write!(
                    f,
                    "UNKNOWN({})",
                    String::from_utf8_lossy(bytes).trim_end()
                )
            }
        }
    }
}

/// Top-level bitmap chunk header: frame count + offsets into the
/// chunk bytes.
#[derive(Debug, Clone)]
pub struct Bitmap<'a> {
    pub frame_count: u16,
    pub frame_offsets: Vec<u32>,
    /// The raw chunk bytes; frames are looked up by offset.
    pub bytes: &'a [u8],
}

impl<'a> Bitmap<'a> {
    /// Parse a bitmap chunk header. The frame count is at byte
    /// offset 4 (u16, LE); the frame offset table starts at byte
    /// offset 6 (u32 × frame_count, LE).
    pub fn from_bytes(bytes: &'a [u8]) -> Result<Self> {
        if bytes.len() < 6 {
            return Err(ImageError::HeaderTruncated { len: bytes.len() });
        }
        let frame_count = u16::from_le_bytes([bytes[4], bytes[5]]);
        let table_end = 6 + 4 * frame_count as usize;
        if bytes.len() < table_end {
            return Err(ImageError::FrameTableTruncated);
        }
        let mut frame_offsets = Vec::with_capacity(frame_count as usize);
        for i in 0..frame_count as usize {
            let off = u32::from_le_bytes([
                bytes[6 + i * 4],
                bytes[6 + i * 4 + 1],
                bytes[6 + i * 4 + 2],
                bytes[6 + i * 4 + 3],
            ]);
            frame_offsets.push(off);
        }
        Ok(Bitmap {
            frame_count,
            frame_offsets,
            bytes,
        })
    }

    /// Decode a single frame into palette indices. Returns
    /// `(Frame, used_palette_or_none)`. Frames whose type is
    /// `PLAN` or otherwise unknown return `UnsupportedFrameType`.
    pub fn decode_frame(&self, frame_id: usize) -> Result<Frame> {
        if frame_id >= self.frame_count as usize {
            return Err(ImageError::FrameOutOfRange {
                frame: frame_id,
                count: self.frame_count as usize,
            });
        }
        let frame_offset = self.frame_offsets[frame_id] as usize;
        // Per libgff: frame header is w (u16) + h (u16) + 1 byte + 4
        // bytes type. So we need at least 9 bytes after frame_offset
        // to even read the type.
        if frame_offset + 9 > self.bytes.len() {
            return Err(ImageError::FrameOutOfBounds {
                offset: frame_offset,
            });
        }
        let width = u16::from_le_bytes([
            self.bytes[frame_offset],
            self.bytes[frame_offset + 1],
        ]);
        let height = u16::from_le_bytes([
            self.bytes[frame_offset + 2],
            self.bytes[frame_offset + 3],
        ]);
        // Type tag is at frame_offset + 5..+9. Byte at +4 is a
        // flag/unknown that libgff doesn't read into a field;
        // pixel data for DS1_RLE starts at frame_offset + 4 (NOT
        // + 9 — DS1 RLE doesn't store the "PLNR"/"PLAN" tag, the
        // 4 bytes at +5..+9 are part of the RLE stream).
        let type_bytes = [
            self.bytes[frame_offset + 5],
            self.bytes[frame_offset + 6],
            self.bytes[frame_offset + 7],
            self.bytes[frame_offset + 8],
        ];
        let frame_type = match &type_bytes {
            b"PLNR" => FrameType::Plnr,
            b"PLAN" => FrameType::Plan,
            _ => FrameType::Ds1Rle,
        };

        match frame_type {
            FrameType::Ds1Rle => {
                let indices = decode_ds1_rle(self.bytes, frame_offset + 4, width, height)?;
                Ok(Frame {
                    width,
                    height,
                    frame_type,
                    indices,
                })
            }
            FrameType::Plnr => {
                let indices = decode_plnr(self.bytes, frame_offset, width, height)?;
                Ok(Frame {
                    width,
                    height,
                    frame_type,
                    indices,
                })
            }
            FrameType::Plan => Err(ImageError::UnsupportedFrameType {
                frame: frame_id,
                kind: "PLAN".to_string(),
            }),
            FrameType::Unknown(bytes) => Err(ImageError::UnsupportedFrameType {
                frame: frame_id,
                kind: String::from_utf8_lossy(&bytes).into_owned(),
            }),
        }
    }
}

/// Decode a DS1-RLE-encoded frame body into palette indices.
///
/// Ported from `dsoageofheroes/libgff` `src/gpl/image.c`
/// `create_ds1_rgba` (MIT). The image is stored bottom-up; we
/// reverse rows to match PNG top-down convention. Pixels not
/// touched by RLE spans default to 0 (palette index 0).
fn decode_ds1_rle(bytes: &[u8], start: usize, width: u16, height: u16) -> Result<Vec<u8>> {
    let w = width as usize;
    let h = height as usize;
    let mut img = vec![0u8; w * h];
    let mut cpos = start;
    let mut rows_decoded = 0usize;

    while rows_decoded < h {
        if cpos >= bytes.len() {
            return Err(ImageError::Ds1RleError { row_offset: cpos });
        }
        let row_num = bytes[cpos] as usize;
        cpos += 1;
        if row_num == 0xFF {
            break;
        }
        if row_num >= h {
            return Err(ImageError::Ds1RleError { row_offset: cpos });
        }
        // Flip vertically: PNG top-down vs. libgff's bottom-up.
        let img_row_idx = h - row_num - 1;
        let row_base = img_row_idx * w;
        rows_decoded += 1;

        loop {
            if cpos + 4 > bytes.len() {
                return Err(ImageError::Ds1RleError { row_offset: cpos });
            }
            let mut startx = bytes[cpos] as usize;
            let flags = bytes[cpos + 1];
            // One unknown byte; libgff reads but doesn't use it.
            let _unknown = bytes[cpos + 2];
            let compressed_length = bytes[cpos + 3] as usize;
            cpos += 4;
            if flags & 0x01 != 0 {
                startx += 256;
            }
            let payload_end = cpos + compressed_length;
            if payload_end > bytes.len() {
                return Err(ImageError::Ds1RleError { row_offset: cpos });
            }
            // Decode RLE codes inside this span.
            let mut i = 0;
            while i < compressed_length {
                if cpos + i >= bytes.len() {
                    return Err(ImageError::Ds1RleError { row_offset: cpos + i });
                }
                let code = bytes[cpos + i] as usize;
                i += 1;
                let run_len = code / 2 + 1;
                if code % 2 == 0 {
                    // Even: run_len direct palette indices.
                    for _ in 0..run_len {
                        if cpos + i >= bytes.len() {
                            return Err(ImageError::Ds1RleError {
                                row_offset: cpos + i,
                            });
                        }
                        let pal_index = bytes[cpos + i];
                        i += 1;
                        if startx < w {
                            img[row_base + startx] = pal_index;
                        }
                        startx += 1;
                    }
                } else {
                    // Odd: one palette index repeated run_len times.
                    if cpos + i >= bytes.len() {
                        return Err(ImageError::Ds1RleError {
                            row_offset: cpos + i,
                        });
                    }
                    let repeated = bytes[cpos + i];
                    i += 1;
                    for _ in 0..run_len {
                        if startx < w {
                            img[row_base + startx] = repeated;
                        }
                        startx += 1;
                    }
                }
            }
            cpos = payload_end;
            if flags & 0x80 != 0 {
                break;
            }
        }
    }
    Ok(img)
}

/// Decode a PLNR-encoded frame body into palette indices.
///
/// Ported from `dsoageofheroes/libgff` `src/gpl/image.c`
/// `plnr_get_next` + `plnr_get_bits` + `gff_get_frame_rgba_palette_img`
/// (MIT). Frame body at `frame_offset` is laid out as: w (u16) +
/// h (u16) + 1 unknown byte + 4-byte "PLNR" tag + u8
/// `bits_per_symbol` + `(1 << bits_per_symbol)` byte dictionary +
/// bit-packed symbol stream.
fn decode_plnr(bytes: &[u8], frame_offset: usize, width: u16, height: u16) -> Result<Vec<u8>> {
    if frame_offset + 10 > bytes.len() {
        return Err(ImageError::FrameOutOfBounds {
            offset: frame_offset,
        });
    }
    let bits_per_symbol = bytes[frame_offset + 9] as usize;
    let dict_size = 1usize << bits_per_symbol;
    let dict_start = frame_offset + 10;
    if dict_start + dict_size > bytes.len() {
        return Err(ImageError::FrameOutOfBounds {
            offset: frame_offset,
        });
    }
    let dictionary = &bytes[dict_start..dict_start + dict_size];
    let data_start = dict_start + dict_size;
    let data = &bytes[data_start..];

    let mut state = PlnrState::default();
    let mut out = vec![0u8; width as usize * height as usize];
    for y in 0..height as usize {
        for x in 0..width as usize {
            let pal_dict_index = plnr_get_next(&mut state, data, bits_per_symbol)?;
            let pal_index = dictionary
                .get(pal_dict_index)
                .copied()
                .unwrap_or(0);
            out[y * width as usize + x] = pal_index;
        }
    }
    Ok(out)
}

#[derive(Debug, Default)]
struct PlnrState {
    last_value: usize,
    remaining: usize,
    num_bits_read: usize,
}

fn plnr_get_next(state: &mut PlnrState, data: &[u8], bits_per_symbol: usize) -> Result<usize> {
    if state.remaining == 0 {
        let first = plnr_get_bits(data, state.num_bits_read, bits_per_symbol)?;
        state.num_bits_read += bits_per_symbol;
        if first == 0 {
            let second = plnr_get_bits(data, state.num_bits_read, bits_per_symbol)?;
            state.num_bits_read += bits_per_symbol;
            if second == 0 {
                state.last_value = 0;
                state.remaining = 1;
            } else {
                state.remaining = second + 2;
            }
        } else {
            state.last_value = first;
            state.remaining = 1;
        }
    }
    state.remaining -= 1;
    Ok(state.last_value)
}

fn plnr_get_bits(data: &[u8], bits_read: usize, bits_to_read: usize) -> Result<usize> {
    let byte_offset = bits_read / 8;
    let bit_offset = 4_i32 - (bits_read % 8) as i32;
    let mask: usize = match bits_to_read {
        1 => 0x01,
        2 => 0x03,
        3 => 0x07,
        4 => 0x0F,
        5 => 0x1F,
        6 => 0x3F,
        7 => 0x7F,
        8 => 0xFF,
        _ => 0xFF,
    };
    if byte_offset >= data.len() {
        return Err(ImageError::PlnrSplitBits);
    }
    let byte = data[byte_offset] as usize;
    if bit_offset >= 0 && bit_offset as usize + bits_to_read <= 8 {
        let shifted = byte >> bit_offset as usize;
        Ok(shifted & mask)
    } else {
        // libgff prints "split bits!" and returns 0; mirror with a
        // typed error so callers can surface it.
        Err(ImageError::PlnrSplitBits)
    }
}

// ---------- PNG writer ----------

/// Write a [`Frame`] to a PNG file at `path`, using the given
/// palette. The PNG is palette-indexed (8 bits per pixel) for
/// fidelity with the source format.
pub fn write_png(path: &Path, frame: &Frame, palette: &Palette) -> Result<()> {
    let file = std::fs::File::create(path)?;
    let w = std::io::BufWriter::new(file);
    let mut encoder = png::Encoder::new(w, frame.width as u32, frame.height as u32);
    encoder.set_color(png::ColorType::Indexed);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.set_palette(palette.as_rgb_bytes().to_vec());
    let mut writer = encoder.write_header()?;
    writer.write_image_data(&frame.indices)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn palette_scales_by_intensity_multiplier() {
        let mut bytes = vec![0u8; PALETTE_CHUNK_LEN];
        bytes[0] = 1; // r
        bytes[1] = 2; // g
        bytes[2] = 3; // b
        bytes[3] = 63; // r saturates? 63 * 4 = 252
        let pal = Palette::from_bytes(&bytes).unwrap();
        assert_eq!(pal.colors[0], Color { r: 4, g: 8, b: 12 });
        assert_eq!(pal.colors[1].r, 252);
    }

    #[test]
    fn palette_rejects_bad_length() {
        let bytes = vec![0u8; 100];
        assert!(matches!(
            Palette::from_bytes(&bytes),
            Err(ImageError::PaletteLength { .. })
        ));
    }

    #[test]
    fn bitmap_header_parses_frame_count() {
        // 6 header bytes + frame_count=2 + two u32 offsets.
        let mut bytes = vec![0u8; 6];
        bytes[4] = 2;
        bytes[5] = 0;
        bytes.extend_from_slice(&100u32.to_le_bytes());
        bytes.extend_from_slice(&200u32.to_le_bytes());
        let bmp = Bitmap::from_bytes(&bytes).unwrap();
        assert_eq!(bmp.frame_count, 2);
        assert_eq!(bmp.frame_offsets, vec![100, 200]);
    }

    #[test]
    fn ds1_rle_decode_one_pixel() {
        // Minimal RLE: 1x1 image, palette index 42.
        // Frame body starts at frame_offset+4 per libgff.
        // Layout: row_num=0, startx=0, flags=0x80 (last run), unknown, len=2,
        //         RLE code=0 (even, run_len=1), palette index 42.
        // Then row_num=0xFF terminates.
        let body = vec![
            0, // row_num = 0
            0, 0x80, 0, 2, // startx, flags=last_run, unknown, compressed_length
            0, 42, // RLE: code=0 (run_len=1, direct), palette index 42
            0xFF, // row terminator
        ];
        let indices = decode_ds1_rle(&body, 0, 1, 1).unwrap();
        assert_eq!(indices, vec![42]);
    }

    #[test]
    fn ds1_rle_repeated_pixels() {
        // 4x1 image, 4 repetitions of palette index 7 via odd code.
        // code = (run_len - 1) * 2 + 1 = 7 for run_len=4 → code=7
        let body = vec![
            0, // row_num
            0, 0x80, 0, 2, // startx, flags=last_run, unknown, compressed_length=2
            7, 7, // odd code=7 (run_len=4), repeated palette index 7
            0xFF,
        ];
        let indices = decode_ds1_rle(&body, 0, 4, 1).unwrap();
        assert_eq!(indices, vec![7, 7, 7, 7]);
    }
}
