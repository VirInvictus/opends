//! `--gif` assembly: the ffmpeg two-pass pipeline produces a real
//! GIF from a frame sequence. Skips cleanly when `ffmpeg` is not
//! installed (CI runs tracked fixtures only), mirroring the way
//! the corpus tests skip when `.games/` is absent.

use image_extract::{Color, Frame, FrameType, Palette, write_png};
use std::path::PathBuf;
use std::process::Command;

fn ffmpeg_available() -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join("ffmpeg");
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

/// Two 4x4 frames, distinct palettes entries so the encoder has
/// real colour work to do.
fn write_frame(dir: &std::path::Path, name: &str, index_byte: u8) -> PathBuf {
    let frame = Frame {
        width: 4,
        height: 4,
        frame_type: FrameType::Plnr,
        indices: vec![index_byte; 16],
    };
    let path = dir.join(name);
    write_png(&path, &frame, &test_palette()).expect("write_png");
    path
}

fn test_palette() -> Palette {
    let mut colors = [Color { r: 0, g: 0, b: 0 }; 256];
    colors[1] = Color { r: 255, g: 0, b: 0 };
    colors[2] = Color { r: 0, g: 255, b: 0 };
    Palette { colors }
}

#[test]
fn frame_sequence_assembles_into_a_gif() {
    if ffmpeg_available().is_none() {
        eprintln!("skip: ffmpeg not installed");
        return;
    }
    // Reuse the binary itself end-to-end: build a tiny source GFF?
    // No: the bin reads GFF containers, and a synthetic one is the
    // pack tests' job. Instead drive the same ffmpeg command shape
    // over lib-written frames, which is the code path `--gif` adds
    // (frame PNGs already proven by the corpus tests).
    let dir = tempfile_dir();
    write_frame(&dir, "demo-frame-0.png", 1);
    write_frame(&dir, "demo-frame-1.png", 2);
    write_frame(&dir, "demo-frame-2.png", 1);

    let ffmpeg = ffmpeg_available().unwrap();
    let pattern = dir.join("demo-frame-%d.png");
    let palette =
        std::env::temp_dir().join(format!("image-extract-test-{}.png", std::process::id()));
    let out = dir.join("demo.gif");

    let pal = Command::new(&ffmpeg)
        .args(["-y", "-loglevel", "error", "-framerate", "8", "-i"])
        .arg(&pattern)
        .args(["-vf", "palettegen=stats_mode=diff"])
        .arg(&palette)
        .output()
        .expect("palettegen runs");
    assert!(
        pal.status.success(),
        "palettegen failed: {}",
        String::from_utf8_lossy(&pal.stderr)
    );

    let enc = Command::new(&ffmpeg)
        .args(["-y", "-loglevel", "error", "-framerate", "8", "-i"])
        .arg(&pattern)
        .args(["-i"])
        .arg(&palette)
        .args(["-filter_complex", "[0:v][1:v]paletteuse=dither=none"])
        .arg(&out)
        .output()
        .expect("paletteuse runs");
    assert!(
        enc.status.success(),
        "paletteuse failed: {}",
        String::from_utf8_lossy(&enc.stderr)
    );

    let bytes = std::fs::read(&out).expect("gif exists");
    assert!(bytes.len() > 0);
    // GIF files begin with the ASCII signature "GIF87a" or "GIF89a".
    assert!(bytes.starts_with(b"GIF87a") || bytes.starts_with(b"GIF89a"));
    let _ = std::fs::remove_file(&palette);
}

fn tempfile_dir() -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "image-extract-gif-test-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&dir).expect("mkdir");
    dir
}
