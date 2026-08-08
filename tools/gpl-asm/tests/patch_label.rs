//! Label-relative `--patch` addressing (v0.9.0). Synthetic
//! chunk, no `.games/` dependency: drives the built binary via
//! `CARGO_BIN_EXE_gpl-asm` against a hand-crafted 6-byte
//! program whose jump target creates a block-leader label.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::SystemTime;

use gpl_disasm::{build_cfg, disassemble};

const BIN: &str = env!("CARGO_BIN_EXE_gpl-asm");

/// `gpl jump -> 0x0003; gpl endif; gpl endif; gpl endif`.
/// Offsets: jump 0..3 (opcode + Immediate14 hi/lo), endifs at
/// 3, 4, 5. The jump target makes offset 3 a block leader, so
/// the chunk disassembles with a label there.
const CHUNK: &[u8] = &[0x12, 0x00, 0x03, 0x67, 0x67, 0x67];

fn tempdir(tag: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let dir = std::env::temp_dir().join(format!("gpl-asm-patch-{tag}-{nanos}"));
    fs::create_dir_all(&dir).expect("create tempdir");
    dir
}

/// The label name the disassembler actually assigns to offset 3.
fn label_at_3() -> String {
    let result = disassemble(CHUNK);
    assert!(result.aligned, "synthetic chunk must disassemble aligned");
    let (cfg, _) = build_cfg(&result.instructions, CHUNK.len());
    cfg.labels
        .get(&3)
        .unwrap_or_else(|| panic!("no label at offset 3; labels: {:?}", cfg.labels))
        .clone()
}

fn run_patch(dir: &Path, patch_toml: &str, extra_args: &[&str]) -> (bool, String, Vec<u8>) {
    let chunk_path = dir.join("chunk.bin");
    let patch_path = dir.join("patch.toml");
    let out_path = dir.join("out.bin");
    fs::write(&chunk_path, CHUNK).expect("write chunk");
    fs::write(&patch_path, patch_toml).expect("write patch");
    let output = Command::new(BIN)
        .arg(&chunk_path)
        .arg("--patch")
        .arg(&patch_path)
        .arg("-o")
        .arg(&out_path)
        .args(extra_args)
        .output()
        .expect("run gpl-asm");
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    let out_bytes = fs::read(&out_path).unwrap_or_default();
    (output.status.success(), stderr, out_bytes)
}

#[test]
fn label_form_resolves_and_applies() {
    let dir = tempdir("label");
    let label = label_at_3();
    let toml = format!(
        r#"
[[edit]]
at = "{label}"
bytes_old = "67"
bytes_new = "00"
reason = "test: patch the labelled endif"
"#
    );
    let (ok, stderr, out) = run_patch(&dir, &toml, &[]);
    assert!(ok, "patch should apply: {stderr}");
    assert_eq!(out[3], 0x00, "byte at the label offset patched");
    assert_eq!(&out[..3], &CHUNK[..3], "bytes before the label untouched");
    assert_eq!(&out[4..], &CHUNK[4..], "bytes after the edit untouched");
    let _ = fs::remove_dir_all(&dir);
}

#[test]
fn label_plus_delta_resolves_and_applies() {
    let dir = tempdir("delta");
    let label = label_at_3();
    let toml = format!(
        r#"
[[edit]]
at = "{label} + 2"
bytes_old = "67"
bytes_new = "01"
"#
    );
    let (ok, stderr, out) = run_patch(&dir, &toml, &[]);
    assert!(ok, "patch should apply: {stderr}");
    assert_eq!(out[5], 0x01, "byte at label+2 patched");
    assert_eq!(
        &out[..5],
        &CHUNK[..5],
        "everything before label+2 untouched"
    );
    let _ = fs::remove_dir_all(&dir);
}

#[test]
fn function_name_resolves_via_syms_dir() {
    let dir = tempdir("syms");
    let syms_dir = dir.join("syms");
    fs::create_dir_all(&syms_dir).expect("create syms dir");
    fs::write(
        syms_dir.join("functions.toml"),
        r#"
[[function]]
file = "TEST.GFF"
kind = "GPL "
chunk_id = 1
offset = 0x0003
name = "after_jump"
"#,
    )
    .expect("write functions.toml");
    let toml = r#"
[[edit]]
at = "after_jump + 1"
bytes_old = "67"
bytes_new = "02"
"#;
    let syms_arg = syms_dir.display().to_string();
    let (ok, stderr, out) = run_patch(&dir, toml, &["--syms", &syms_arg]);
    assert!(ok, "patch should apply: {stderr}");
    assert_eq!(out[4], 0x02, "byte at after_jump+1 patched");
    let _ = fs::remove_dir_all(&dir);
}

#[test]
fn fingerprint_stays_mandatory_for_label_edits() {
    let dir = tempdir("fingerprint");
    let label = label_at_3();
    let toml = format!(
        r#"
[[edit]]
at = "{label}"
bytes_old = "00"
bytes_new = "01"
"#
    );
    let (ok, stderr, out) = run_patch(&dir, &toml, &[]);
    assert!(!ok, "wrong bytes_old must refuse to apply");
    assert!(
        stderr.contains("fingerprint mismatch"),
        "stderr should name the fingerprint check: {stderr}"
    );
    assert!(out.is_empty(), "no output written on refusal");
    let _ = fs::remove_dir_all(&dir);
}

#[test]
fn unknown_name_is_an_error() {
    let dir = tempdir("unknown");
    let toml = r#"
[[edit]]
at = "no_such_label"
bytes_old = "67"
bytes_new = "00"
"#;
    let (ok, stderr, _) = run_patch(&dir, toml, &[]);
    assert!(!ok, "unknown label/name must refuse");
    assert!(
        stderr.contains("no_such_label"),
        "error should name the unresolved base: {stderr}"
    );
    let _ = fs::remove_dir_all(&dir);
}

#[test]
fn at_and_at_offset_together_are_rejected() {
    let dir = tempdir("both");
    let label = label_at_3();
    let toml = format!(
        r#"
[[edit]]
at = "{label}"
at_offset = 3
bytes_old = "67"
bytes_new = "00"
"#
    );
    let (ok, stderr, _) = run_patch(&dir, &toml, &[]);
    assert!(!ok, "at + at_offset together must refuse");
    assert!(
        stderr.contains("exactly one"),
        "error should state the exactly-one rule: {stderr}"
    );
    let _ = fs::remove_dir_all(&dir);
}

#[test]
fn neither_at_nor_at_offset_is_rejected() {
    let dir = tempdir("neither");
    let toml = r#"
[[edit]]
bytes_old = "67"
bytes_new = "00"
"#;
    let (ok, stderr, _) = run_patch(&dir, toml, &[]);
    assert!(!ok, "an edit with no addressing must refuse");
    assert!(
        stderr.contains("exactly one"),
        "error should state the exactly-one rule: {stderr}"
    );
    let _ = fs::remove_dir_all(&dir);
}

#[test]
fn absolute_offset_edits_still_work() {
    let dir = tempdir("absolute");
    let toml = r#"
[[edit]]
at_offset = 0x0004
bytes_old = "67"
bytes_new = "03"
"#;
    let (ok, stderr, out) = run_patch(&dir, toml, &[]);
    assert!(ok, "v0.8-style absolute edits must keep working: {stderr}");
    assert_eq!(out[4], 0x03);
    let _ = fs::remove_dir_all(&dir);
}
