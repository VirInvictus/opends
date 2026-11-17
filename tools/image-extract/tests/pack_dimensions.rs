//! Encoder dimension bounds and malformed-PLNR refusals (2026-11-17,
//! issues #27/#28): DS1 RLE row numbers are u8 with 0xFF reserved as
//! the frame terminator, span columns are 9-bit, and a PLNR frame's
//! `bits_per_symbol` is an untrusted byte feeding a shift.

use image_extract::{Bitmap, Frame, FrameType, ImageError, encode_bitmap_rle};

fn frame(width: u16, height: u16) -> Frame {
    Frame {
        width,
        height,
        frame_type: FrameType::Ds1Rle,
        indices: vec![0u8; width as usize * height as usize],
    }
}

#[test]
fn encode_accepts_maximum_dimensions() {
    // h=255: rows 0..=254, no 0xFF collision. w=512: max span startx
    // 511 still fits the 9-bit column encoding.
    let frames = vec![frame(512, 255)];
    encode_bitmap_rle(&frames).expect("maximum dimensions encode");
}

#[test]
fn encode_rejects_height_256() {
    // Row 255 would emit as the 0xFF frame terminator, truncating
    // the frame; taller heights wrap modulo 256 instead.
    let err = encode_bitmap_rle(&[frame(16, 256)]).unwrap_err();
    let ImageError::UnsupportedFrameType { frame: 0, kind } = err else {
        panic!("expected UnsupportedFrameType, got {err:?}");
    };
    assert!(kind.contains("height 256"), "{kind}");
}

#[test]
fn encode_rejects_width_513() {
    // Span column 512 would wrap onto column 0 via the 9-bit field.
    let err = encode_bitmap_rle(&[frame(513, 16)]).unwrap_err();
    let ImageError::UnsupportedFrameType { frame: 0, kind } = err else {
        panic!("expected UnsupportedFrameType, got {err:?}");
    };
    assert!(kind.contains("width 513"), "{kind}");
}

#[test]
fn encoded_maximum_dimensions_round_trip() {
    // The bounds are exactly the format's limits: a 512x255 frame
    // with live pixels must encode and decode pixel-identically.
    let mut f = frame(512, 255);
    for i in (0..f.indices.len()).step_by(97) {
        f.indices[i] = (i % 251) as u8 + 1;
    }
    let chunk = encode_bitmap_rle(&[f.clone()]).expect("encode");
    let decoded = Bitmap::from_bytes(&chunk)
        .expect("parse own chunk")
        .decode_frame(0)
        .expect("decode own chunk");
    assert_eq!(decoded.indices, f.indices);
    assert_eq!(decoded.width, 512);
    assert_eq!(decoded.height, 255);
}

/// A one-frame bitmap chunk body around a synthetic PLNR frame.
fn plnr_chunk(bits_per_symbol: u8) -> Vec<u8> {
    let mut b = Vec::new();
    b.extend_from_slice(&0u32.to_le_bytes()); // chunk_size, patched below
    b.extend_from_slice(&1u16.to_le_bytes()); // frame_count
    b.extend_from_slice(&10u32.to_le_bytes()); // frame offset
    // Frame: w u16 + h u16 + 1 unknown + "PLNR" + bits_per_symbol +
    // dictionary + a few symbol bytes.
    b.extend_from_slice(&4u16.to_le_bytes()); // width
    b.extend_from_slice(&2u16.to_le_bytes()); // height
    b.push(0);
    b.extend_from_slice(b"PLNR");
    b.push(bits_per_symbol);
    let dict_len = if bits_per_symbol < 7 {
        1usize << bits_per_symbol
    } else {
        0
    };
    b.extend(std::iter::repeat_n(0x11u8, dict_len));
    // Symbol stream: 4x2 = 8 pixels of 4 bits = 4 bytes minimum;
    // give 8 so the chomper never runs dry.
    b.extend(std::iter::repeat_n(0x11u8, 8));
    let size = b.len() as u32;
    b[0..4].copy_from_slice(&size.to_le_bytes());
    b
}

#[test]
fn decode_plnr_rejects_overflowing_bits_per_symbol() {
    // 64 would panic on `1usize << 64` before any bounds check in
    // the pre-#27 code.
    let chunk = plnr_chunk(64);
    let err = Bitmap::from_bytes(&chunk)
        .expect("parse")
        .decode_frame(0)
        .unwrap_err();
    let ImageError::UnsupportedFrameType { kind, .. } = err else {
        panic!("expected UnsupportedFrameType, got {err:?}");
    };
    assert!(kind.contains("bits_per_symbol=64"), "{kind}");
}

#[test]
fn decode_plnr_rejects_zero_bits_per_symbol() {
    let chunk = plnr_chunk(0);
    let err = Bitmap::from_bytes(&chunk)
        .expect("parse")
        .decode_frame(0)
        .unwrap_err();
    let ImageError::UnsupportedFrameType { kind, .. } = err else {
        panic!("expected UnsupportedFrameType, got {err:?}");
    };
    assert!(kind.contains("bits_per_symbol=0"), "{kind}");
}

#[test]
fn decode_plnr_still_decodes_a_valid_frame() {
    // bits_per_symbol=4: the guard must not reject the corpus
    // shape (shipped frames only use 4..=7).
    let chunk = plnr_chunk(4);
    let decoded = Bitmap::from_bytes(&chunk)
        .expect("parse")
        .decode_frame(0)
        .expect("valid PLNR frame decodes");
    assert_eq!(decoded.width, 4);
    assert_eq!(decoded.height, 2);
}
