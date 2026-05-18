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
            FrameType::Plan => {
                let indices = decode_plan(self.bytes, frame_offset, width, height)?;
                Ok(Frame {
                    width,
                    height,
                    frame_type,
                    indices,
                })
            }
            FrameType::Unknown(bytes) => Err(ImageError::UnsupportedFrameType {
                frame: frame_id,
                kind: String::from_utf8_lossy(&bytes).into_owned(),
            }),
        }
    }

    /// Decode every frame in declared order. Each entry is the
    /// `Result` from [`Bitmap::decode_frame`] for that frame
    /// index, so callers see per-frame failures without losing
    /// the rest of the strip (DS1 `RESOURCE.GFF:ICON/0x7f9`
    /// frame 2 is the one known malformed frame in the corpus;
    /// every other frame decodes cleanly).
    pub fn decode_all_frames(&self) -> Vec<Result<Frame>> {
        (0..self.frame_count as usize)
            .map(|i| self.decode_frame(i))
            .collect()
    }
}

/// Composite a sequence of decoded frames into a single
/// horizontal-strip [`Frame`] suitable for `write_png`. Frames
/// are placed left-to-right in input order; the strip's height
/// is the max of all frame heights. Shorter frames are top-
/// aligned and padded with palette index 0 (the standard DS
/// "background" index; in the BMP / ICON paths this is what
/// libgff defaults uninitialised pixels to as well).
///
/// `frame_type` on the composite is set to
/// `FrameType::Unknown(b"STRP")` so a caller can distinguish a
/// spritesheet from a real game-encoded frame; downstream tools
/// that branch on frame_type should treat it as "rendered" and
/// not try to re-encode it.
///
/// Returns `None` if `frames` is empty or if the strip would
/// exceed `u16::MAX` in either dimension.
pub fn composite_horizontal_strip(frames: &[Frame]) -> Option<Frame> {
    if frames.is_empty() {
        return None;
    }
    let total_width: u32 = frames.iter().map(|f| f.width as u32).sum();
    let max_height: u32 = frames.iter().map(|f| f.height as u32).max().unwrap_or(0);
    if total_width == 0 || max_height == 0 {
        return None;
    }
    let strip_w = u16::try_from(total_width).ok()?;
    let strip_h = u16::try_from(max_height).ok()?;

    let mut indices = vec![0u8; strip_w as usize * strip_h as usize];
    let mut cursor_x = 0usize;
    for f in frames {
        let fw = f.width as usize;
        let fh = f.height as usize;
        for row in 0..fh {
            let src_start = row * fw;
            let dst_start = row * strip_w as usize + cursor_x;
            indices[dst_start..dst_start + fw]
                .copy_from_slice(&f.indices[src_start..src_start + fw]);
        }
        cursor_x += fw;
    }
    Some(Frame {
        width: strip_w,
        height: strip_h,
        frame_type: FrameType::Unknown(*b"STRP"),
        indices,
    })
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

// ---------- DS1 RLE encoder (v0.4.0) ----------

/// Maximum run length per RLE code, in pixels.
///
/// The DS1 RLE per-pixel-run code is one byte: `code / 2 + 1` is the
/// run length, in `0..=127 → 1..=128`. So both the direct and
/// repeated forms cap at 128 pixels per code byte.
const RLE_MAX_RUN: usize = 128;

/// Maximum span payload, in bytes (one-byte `compressed_length`
/// field caps it). Wide rows are emitted as multiple spans.
const RLE_MAX_SPAN_PAYLOAD: usize = 0xFF;

/// One RLE code with metadata about how many input pixels it covers.
/// Used during multi-span emission so the encoder can compute each
/// span's `startx` precisely.
struct RleCode {
    bytes: Vec<u8>,
    pixels: usize,
}

/// Encode `pixels` into a sequence of RLE codes. Greedy strategy:
/// when the next pixel matches the current one, emit a repeated run
/// (one byte saved over the direct form); otherwise extend a direct
/// run until the next repeated pair or the 128-pixel cap.
fn rle_codes_for(pixels: &[u8]) -> Vec<RleCode> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < pixels.len() {
        // Probe for a repeated run starting at i.
        let mut run_len = 1;
        while i + run_len < pixels.len()
            && pixels[i + run_len] == pixels[i]
            && run_len < RLE_MAX_RUN
        {
            run_len += 1;
        }

        if run_len >= 2 {
            // Repeated form: odd code byte + one data byte.
            let code = ((run_len - 1) as u8) * 2 + 1;
            out.push(RleCode {
                bytes: vec![code, pixels[i]],
                pixels: run_len,
            });
            i += run_len;
        } else {
            // Direct form: scan forward until the next repeated pair
            // or the 128-pixel cap. Stop before a repeated pair so
            // the next iteration emits it as a repeated run.
            let mut direct_len = 1;
            while i + direct_len < pixels.len() && direct_len < RLE_MAX_RUN {
                let next = i + direct_len;
                if next + 1 < pixels.len() && pixels[next] == pixels[next + 1] {
                    break;
                }
                direct_len += 1;
            }
            let mut code_bytes = Vec::with_capacity(1 + direct_len);
            code_bytes.push(((direct_len - 1) as u8) * 2);
            code_bytes.extend_from_slice(&pixels[i..i + direct_len]);
            out.push(RleCode {
                bytes: code_bytes,
                pixels: direct_len,
            });
            i += direct_len;
        }
    }
    out
}

/// Convenience: concatenate the bytes of a code sequence. Used in
/// unit tests that inspect a single-span row's payload directly.
#[cfg(test)]
fn encode_ds1_rle_payload(pixels: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    for c in rle_codes_for(pixels) {
        out.extend_from_slice(&c.bytes);
    }
    out
}

/// Encode one row of pixels as one or more spans
/// `(startx, flags, unknown, length, payload...)`. Returns `None`
/// when every pixel is palette index 0 (the caller skips emitting
/// the row; the decoder default-fills uninitialised pixels with 0).
///
/// Wide rows (e.g. 320-pixel DS sprite rows whose RLE payload
/// exceeds 255 bytes) emit as multiple back-to-back spans with
/// distinct `startx` values; only the final span has the
/// `0x80` last-span flag set. The `flags & 0x01` bit handles
/// `startx >= 256` (the engine stores startx as 9 bits split
/// across the two bytes).
fn encode_ds1_rle_row(row_pixels: &[u8]) -> Option<Vec<u8>> {
    if row_pixels.iter().all(|&p| p == 0) {
        return None;
    }
    let codes = rle_codes_for(row_pixels);

    // Group codes into spans. A new span starts whenever adding the
    // next code would push the current span's payload past 255
    // bytes. Each span gets its own startx (cumulative pixel
    // count of all preceding spans on this row).
    let mut spans: Vec<(usize, Vec<u8>)> = Vec::new();
    let mut current_startx: usize = 0;
    let mut current_payload: Vec<u8> = Vec::new();
    let mut current_pixels: usize = 0;
    for c in codes {
        if !current_payload.is_empty()
            && current_payload.len() + c.bytes.len() > RLE_MAX_SPAN_PAYLOAD
        {
            spans.push((current_startx, std::mem::take(&mut current_payload)));
            current_startx += current_pixels;
            current_pixels = 0;
        }
        current_payload.extend_from_slice(&c.bytes);
        current_pixels += c.pixels;
    }
    if !current_payload.is_empty() {
        spans.push((current_startx, current_payload));
    }

    // Serialise: each span gets a 4-byte header. Only the final
    // span's flags include the `last-span` bit.
    let mut out = Vec::new();
    let last_idx = spans.len() - 1;
    for (i, (startx, payload)) in spans.iter().enumerate() {
        let mut flags: u8 = 0;
        if *startx >= 256 {
            flags |= 0x01;
        }
        if i == last_idx {
            flags |= 0x80;
        }
        out.push((*startx & 0xFF) as u8);
        out.push(flags);
        out.push(0u8); // unknown (libgff doesn't read)
        out.push(payload.len() as u8);
        out.extend_from_slice(payload);
    }
    Some(out)
}

/// Encode a [`Frame`] as a DS1 RLE frame body: `width (u16) + height
/// (u16) + RLE bytes (terminated by 0xFF row marker)`. Rows that are
/// entirely palette index 0 are skipped (the decoder default-fills
/// uninitialised pixels with 0, so skipping is lossless).
///
/// Row order: the original engine stores rows bottom-up. We re-flip
/// from PNG top-down here so that decoded output matches the input
/// pixel-for-pixel.
fn encode_ds1_rle_frame(frame: &Frame) -> Vec<u8> {
    let w = frame.width as usize;
    let h = frame.height as usize;
    debug_assert_eq!(frame.indices.len(), w * h);

    let mut body = Vec::with_capacity(4 + w * h / 4);
    body.extend_from_slice(&frame.width.to_le_bytes());
    body.extend_from_slice(&frame.height.to_le_bytes());

    // For each stored row (bottom-up), check if the corresponding
    // PNG row (top-down) has any non-zero pixel and emit. row_num
    // here is the storage-side row number; the decoder maps it back
    // via `img_row_idx = h - row_num - 1`.
    for row_num in 0..h {
        let png_row = h - row_num - 1;
        let row_start = png_row * w;
        let row_slice = &frame.indices[row_start..row_start + w];
        if let Some(span) = encode_ds1_rle_row(row_slice) {
            body.push(row_num as u8);
            body.extend_from_slice(&span);
        }
    }
    body.push(0xFF); // frame terminator

    // The decoder requires at least 9 bytes from frame_offset
    // (4 for w/h + 5 for the type-tag check area that overlaps
    // the start of the RLE stream). For a near-empty body (e.g.
    // an all-zero frame: 4 header bytes + 0xFF terminator = 5
    // bytes), pad with zeros after the terminator. The decoder's
    // RLE loop exits at the 0xFF row marker before reading them.
    while body.len() < 9 {
        body.push(0);
    }
    body
}

/// Encode a sequence of [`Frame`]s as a complete bitmap chunk
/// (BMP / PORT / ICON shape): `u32 chunk_size + u16 frame_count +
/// u32 × frame_count frame_offsets + per-frame DS1 RLE bodies`.
///
/// Every frame is encoded as DS1 RLE regardless of the input
/// `frame_type`; v0.4.0 doesn't ship a PLNR or PLAN encoder, and the
/// game engine reads all three transparently from chunks of any kind.
/// Frames whose `frame_type` is the composited `STRP` marker are
/// rejected (those aren't real game frames; the caller asked for the
/// wrong thing).
pub fn encode_bitmap_rle(frames: &[Frame]) -> Result<Vec<u8>> {
    if frames.is_empty() {
        return Err(ImageError::UnsupportedFrameType {
            frame: 0,
            kind: "empty frame list".to_string(),
        });
    }
    for (i, f) in frames.iter().enumerate() {
        if matches!(f.frame_type, FrameType::Unknown(t) if &t == b"STRP") {
            return Err(ImageError::UnsupportedFrameType {
                frame: i,
                kind: "STRP".to_string(),
            });
        }
    }

    let frame_count = frames.len() as u16;
    let header_size = 4 + 2 + 4 * frames.len(); // chunk_size + frame_count + offsets
    let mut bodies: Vec<Vec<u8>> = Vec::with_capacity(frames.len());
    for f in frames {
        bodies.push(encode_ds1_rle_frame(f));
    }

    // Compute per-frame offset into the chunk.
    let mut offsets: Vec<u32> = Vec::with_capacity(frames.len());
    let mut cursor = header_size;
    for body in &bodies {
        offsets.push(cursor as u32);
        cursor += body.len();
    }
    let chunk_size = cursor;

    let mut out = Vec::with_capacity(chunk_size);
    out.extend_from_slice(&(chunk_size as u32).to_le_bytes());
    out.extend_from_slice(&frame_count.to_le_bytes());
    for o in &offsets {
        out.extend_from_slice(&o.to_le_bytes());
    }
    for body in &bodies {
        out.extend_from_slice(body);
    }
    debug_assert_eq!(out.len(), chunk_size);
    Ok(out)
}

// ---------- end DS1 RLE encoder ----------

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

    // v0.2.0 switches PLNR to the same big-endian bit chomper
    // that PLAN uses (dsun_music BitChomper, MIT). libgff's
    // own decoder used a 4-bit "rotated" chomp that fails on
    // boundary-crossing reads (it printed "split bits!" and
    // returned 0). Empirically the rotated chomp rejected 410
    // of 855 corpus PLNR frames; the big-endian chomp lets
    // every one of them decode cleanly.
    let mut chomper = BigEndianBitChomper::new(data, 0);
    let mut state = PlnrRleState::default();
    let mut out = vec![0u8; width as usize * height as usize];
    for y in 0..height as usize {
        for x in 0..width as usize {
            let pal_dict_index =
                plnr_get_next(&mut state, &mut chomper, bits_per_symbol).ok_or(
                    ImageError::FrameOutOfBounds {
                        offset: frame_offset,
                    },
                )?;
            let pal_index = dictionary.get(pal_dict_index).copied().unwrap_or(0);
            out[y * width as usize + x] = pal_index;
        }
    }
    Ok(out)
}

/// PLNR RLE state. PLNR layers run-length encoding on top of the
/// PLAN-style dictionary symbol stream: a leading `0` symbol
/// introduces a run, the next symbol is the run length (or `0`
/// for a single zero-pixel), and a non-zero first symbol is its
/// own single-pixel run.
#[derive(Debug, Default)]
struct PlnrRleState {
    last_value: usize,
    remaining: usize,
}

fn plnr_get_next(
    state: &mut PlnrRleState,
    chomper: &mut BigEndianBitChomper,
    bits_per_symbol: usize,
) -> Option<usize> {
    if state.remaining == 0 {
        let first = chomper.chomp(bits_per_symbol)? as usize;
        if first == 0 {
            let second = chomper.chomp(bits_per_symbol)? as usize;
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
    Some(state.last_value)
}

// ---------- PLAN decoder (image-extract v0.2.0) ----------

/// Decode a `PLAN`-encoded frame body into palette indices.
///
/// Format (per `dsun_music`'s
/// `ImageReading.readPlanarImageFrame`, MIT, RE'd from DSUN.EXE
/// offset 0x1A1B0):
///
/// ```text
/// frame_offset + 0:    u16 LE width
/// frame_offset + 2:    u16 LE height
/// frame_offset + 4:    0xFF marker
/// frame_offset + 5:    4-byte tag "PLAN"
/// frame_offset + 9:    u8 bits_per_symbol
/// frame_offset + 10:   dictionary[2^bits_per_symbol] u8
/// (after dict):        bit-packed symbol stream (BE bit order)
/// ```
///
/// Each pixel reads `bits_per_symbol` bits from the stream
/// (MSB-first across byte boundaries) and indexes into the
/// dictionary; the dictionary value is the palette index for
/// that pixel. Dictionary value 0 means "no pixel" (transparent);
/// we emit palette index 0, which is the conventional
/// transparent / void index in DS palettes.
///
/// PLAN differs from PLNR in two ways:
/// 1. No RLE on the symbol stream (each pixel is one symbol).
/// 2. Standard big-endian bit chomp instead of libgff's 4-bit
///    rotated chomp.
fn decode_plan(bytes: &[u8], frame_offset: usize, width: u16, height: u16) -> Result<Vec<u8>> {
    if frame_offset + 10 > bytes.len() {
        return Err(ImageError::FrameOutOfBounds {
            offset: frame_offset,
        });
    }
    let bits_per_symbol = bytes[frame_offset + 9] as usize;
    let w = width as usize;
    let h = height as usize;
    if bits_per_symbol == 0 {
        // Empty image frame (no dictionary, no data); per
        // dsun_music's reference implementation.
        return Ok(vec![0u8; w * h]);
    }
    if bits_per_symbol > 8 {
        return Err(ImageError::UnsupportedFrameType {
            frame: frame_offset,
            kind: format!("PLAN with bits_per_symbol={bits_per_symbol}"),
        });
    }
    let dict_size = 1usize << bits_per_symbol;
    let dict_start = frame_offset + 10;
    if dict_start + dict_size > bytes.len() {
        return Err(ImageError::FrameOutOfBounds {
            offset: frame_offset,
        });
    }
    let dictionary = &bytes[dict_start..dict_start + dict_size];
    let data_start = dict_start + dict_size;

    let mut chomper = BigEndianBitChomper::new(bytes, data_start);
    let mut out = vec![0u8; w * h];
    for y in 0..h {
        for x in 0..w {
            let symbol = chomper
                .chomp(bits_per_symbol)
                .ok_or(ImageError::FrameOutOfBounds {
                    offset: frame_offset,
                })?;
            let value = dictionary.get(symbol as usize).copied().unwrap_or(0);
            // dictionary value == 0 means "transparent" per the
            // dsun_music reference; we leave the index as 0,
            // which is what the buffer was initialised to.
            if value != 0 {
                out[y * w + x] = value;
            }
        }
    }
    Ok(out)
}

/// Standard big-endian bit chomper. Mirrors
/// `dsun_music.BitChomper` with `ByteOrder.BIG_ENDIAN`: each
/// call to [`chomp`] returns the next `n` bits MSB-first
/// across byte boundaries.
struct BigEndianBitChomper<'a> {
    bytes: &'a [u8],
    bit_pos: usize,
}

impl<'a> BigEndianBitChomper<'a> {
    fn new(bytes: &'a [u8], start_byte: usize) -> Self {
        Self {
            bytes,
            bit_pos: start_byte * 8,
        }
    }

    /// Read `n` bits (1..=16 typical) and return them right-
    /// justified. Returns `None` if `n` bits aren't available.
    fn chomp(&mut self, n: usize) -> Option<u32> {
        let mut value = 0u32;
        let mut bits_filled = 0;
        while bits_filled < n {
            let byte_offset = self.bit_pos / 8;
            let bit_offset = self.bit_pos % 8;
            if byte_offset >= self.bytes.len() {
                return None;
            }
            let bits_from = (n - bits_filled).min(8 - bit_offset);
            let mask_shift = 8 - bit_offset - bits_from;
            let value_shift = n - bits_filled - bits_from;
            let mask = ((1u32 << bits_from) - 1) << mask_shift;
            let value_from_byte = (self.bytes[byte_offset] as u32 & mask) >> mask_shift;
            value |= value_from_byte << value_shift;
            bits_filled += bits_from;
            self.bit_pos += bits_from;
        }
        Some(value)
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

    // ---------- encoder tests (v0.4.0) ----------

    fn frame(width: u16, height: u16, indices: Vec<u8>) -> Frame {
        assert_eq!(indices.len(), width as usize * height as usize);
        Frame {
            width,
            height,
            frame_type: FrameType::Ds1Rle,
            indices,
        }
    }

    fn pack_unpack_frame(f: &Frame) -> Frame {
        let chunk = encode_bitmap_rle(std::slice::from_ref(f)).expect("encode");
        let bmp = Bitmap::from_bytes(&chunk).expect("re-parse chunk");
        assert_eq!(bmp.frame_count, 1);
        bmp.decode_frame(0).expect("decode")
    }

    #[test]
    fn rle_payload_single_pixel_emits_direct_code_zero() {
        // 1 byte → direct run of 1 → code = 0, payload byte = value.
        assert_eq!(encode_ds1_rle_payload(&[42]), vec![0, 42]);
    }

    #[test]
    fn rle_payload_pair_of_identical_emits_repeated_code_three() {
        // Two equal bytes → repeated run of 2 → code = 3, value = byte.
        assert_eq!(encode_ds1_rle_payload(&[7, 7]), vec![3, 7]);
    }

    #[test]
    fn rle_payload_mixed_run() {
        // [1, 2, 3, 5, 5, 5, 9]:
        //   direct(1,2,3) → code = 4, then 1, 2, 3
        //   repeated(5)*3 → code = 5, then 5
        //   direct(9) → code = 0, then 9
        assert_eq!(
            encode_ds1_rle_payload(&[1, 2, 3, 5, 5, 5, 9]),
            vec![4, 1, 2, 3, 5, 5, 0, 9],
        );
    }

    #[test]
    fn rle_payload_long_repeated_run_caps_at_128() {
        let pixels: Vec<u8> = vec![3; 200];
        let encoded = encode_ds1_rle_payload(&pixels);
        // First run: max 128 → code = 127*2 + 1 = 255, value = 3
        // Then run of 72: code = 71*2 + 1 = 143, value = 3
        assert_eq!(encoded, vec![255, 3, 143, 3]);
    }

    #[test]
    fn rle_payload_long_direct_run_caps_at_128() {
        // 130 distinct alternating bytes; can't form a repeated run
        // (the encoder breaks direct runs before a repeated pair, but
        // here no two consecutive pixels match).
        let pixels: Vec<u8> = (0..130).map(|i| (i % 250) as u8).collect();
        let encoded = encode_ds1_rle_payload(&pixels);
        // First direct run: 128 pixels → code = 254, then 128 data bytes.
        // Then second direct run: 2 pixels → code = 2, then 2 data bytes.
        assert_eq!(encoded[0], 254);
        assert_eq!(&encoded[1..129], &pixels[..128]);
        assert_eq!(encoded[129], 2);
        assert_eq!(&encoded[130..132], &pixels[128..130]);
    }

    #[test]
    fn encode_decode_roundtrip_single_pixel() {
        let f = frame(1, 1, vec![42]);
        assert_eq!(pack_unpack_frame(&f).indices, f.indices);
    }

    #[test]
    fn encode_decode_roundtrip_single_row() {
        // Mixed: direct + repeated + direct.
        let f = frame(8, 1, vec![1, 2, 3, 5, 5, 5, 9, 7]);
        assert_eq!(pack_unpack_frame(&f).indices, f.indices);
    }

    #[test]
    fn encode_decode_roundtrip_multi_row_with_empty_rows() {
        // 4x4: top row non-zero, middle two rows zero (skipped by
        // encoder), bottom row non-zero. Decoder fills zeros.
        #[rustfmt::skip]
        let pixels = vec![
            10, 11, 12, 13,
            0,  0,  0,  0,
            0,  0,  0,  0,
            20, 21, 22, 23,
        ];
        let f = frame(4, 4, pixels.clone());
        let decoded = pack_unpack_frame(&f);
        assert_eq!(decoded.indices, pixels);
    }

    #[test]
    fn encode_decode_roundtrip_all_zero_frame() {
        let f = frame(4, 4, vec![0; 16]);
        assert_eq!(pack_unpack_frame(&f).indices, vec![0; 16]);
    }

    #[test]
    fn encode_decode_roundtrip_multi_frame() {
        let f0 = frame(2, 2, vec![1, 2, 3, 4]);
        let f1 = frame(3, 1, vec![7, 7, 8]);
        let chunk = encode_bitmap_rle(&[f0.clone(), f1.clone()]).unwrap();
        let bmp = Bitmap::from_bytes(&chunk).unwrap();
        assert_eq!(bmp.frame_count, 2);
        let d0 = bmp.decode_frame(0).unwrap();
        let d1 = bmp.decode_frame(1).unwrap();
        assert_eq!(d0.indices, f0.indices);
        assert_eq!(d0.width, 2);
        assert_eq!(d0.height, 2);
        assert_eq!(d1.indices, f1.indices);
        assert_eq!(d1.width, 3);
        assert_eq!(d1.height, 1);
    }

    #[test]
    fn encode_rejects_empty_frame_list() {
        assert!(encode_bitmap_rle(&[]).is_err());
    }

    #[test]
    fn encode_rejects_strp_composite() {
        let f = Frame {
            width: 2,
            height: 1,
            frame_type: FrameType::Unknown(*b"STRP"),
            indices: vec![1, 2],
        };
        assert!(encode_bitmap_rle(&[f]).is_err());
    }
}
