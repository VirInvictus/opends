//! Fixture round-trip and every refusal, on the synthetic overlaid MZ
//! (mirrors exe-patch's selftest shape: the invariants hold with no
//! .games/ present).

use ovr_carve::{CarveError, DEFAULT_LOAD_SEGMENT, carve, fixture, fixture_map, verify};

#[test]
fn carve_fixture_expected_bytes() {
    let pristine = fixture();
    let map = fixture_map();
    let carved = carve(&pristine, &map, DEFAULT_LOAD_SEGMENT).expect("carve succeeds");

    assert_eq!(carved.output.len(), pristine.len());
    // Exactly four u16 words differ: the two MZ page fields and the two
    // far-call segment words. Hand-specified, not derived from carve().
    let mut expected = pristine.clone();
    let patch = [
        (2u64, 56u16),   // e_cblp: 0x238 % 512
        (4, 2),          // e_cp: 0x238 / 512 + 1
        (0x213, 0x1010), // record 0 (class 1, start_para 0x10)
        (0x218, 0x1011), // record 1 (class 3, start_para 0x11)
    ];
    for (pos, value) in patch {
        expected[pos as usize] = value as u8;
        expected[pos as usize + 1] = (value >> 8) as u8;
    }
    assert_eq!(carved.output, expected);
}

#[test]
fn carve_fixture_stats_and_mapping() {
    let pristine = fixture();
    let map = fixture_map();
    let carved = carve(&pristine, &map, DEFAULT_LOAD_SEGMENT).expect("carve succeeds");

    assert_eq!(carved.stats.applied, 2);
    assert_eq!(carved.stats.markers, 0);
    assert_eq!(carved.stats.tag_histogram, [(0, 2)].into_iter().collect());
    assert_eq!(
        carved.stats.target_classes,
        [(1, 1), (3, 1)].into_iter().collect()
    );
    assert_eq!(carved.stats.per_module, vec![(0, 2), (1, 0)]);

    let m0 = &carved.mapping.modules[0];
    // Module base: file 0x210 - header 0x20 = 0x1f0 -> segment 0x101f.
    assert_eq!(m0.segment, 0x101f);
    assert_eq!(m0.linear_start, 0x10000 + 0x1f0);
    let e0 = &carved.mapping.modules[1].entries[0];
    assert_eq!(e0.file_offset, 560);
    assert_eq!(e0.linear, 0x10000 + (560 - 32));
}

#[test]
fn verify_accepts_own_output_and_rejects_tampering() {
    let pristine = fixture();
    let map = fixture_map();
    let carved = carve(&pristine, &map, DEFAULT_LOAD_SEGMENT).expect("carve succeeds");
    verify(&pristine, &map, &carved.output, DEFAULT_LOAD_SEGMENT)
        .expect("verify accepts the carve's own output");

    let mut tampered = carved.output.clone();
    let last = tampered.len() - 1;
    tampered[last] ^= 0xff;
    match verify(&pristine, &map, &tampered, DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::VerifyMismatch { offset, .. }) => assert_eq!(offset as usize, last),
        other => panic!("expected VerifyMismatch, got {other:?}"),
    }
}

#[test]
fn refuse_already_carved_input() {
    let pristine = fixture();
    let map = fixture_map();
    let carved = carve(&pristine, &map, DEFAULT_LOAD_SEGMENT).expect("carve succeeds");
    // With the ORIGINAL map, the rewritten far-call words (0x1010) read as
    // out-of-range segtab records; the message names that shape.
    match carve(&carved.output, &map, DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::RelocRecordOutOfRange { value, .. }) => {
            assert_eq!(value, 0x1010);
        }
        other => panic!("expected RelocRecordOutOfRange, got {other:?}"),
    }
    // A re-run of ovr-map on the carved file computes image_end = EOF (the
    // page fields now cover everything); that shape refuses as AlreadyFlat.
    let mut remapped = fixture_map();
    remapped.mz.image_end = carved.output.len() as u64;
    match carve(&carved.output, &remapped, DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::AlreadyFlat { image_end, len }) => {
            assert_eq!(image_end, 0x238);
            assert_eq!(len, 0x238);
        }
        other => panic!("expected AlreadyFlat, got {other:?}"),
    }
}

fn rebind_segment_word(v: u16) -> Vec<u8> {
    let mut b = fixture();
    b[0x218] = v as u8;
    b[0x219] = (v >> 8) as u8;
    b
}

#[test]
fn refuse_marker_bit() {
    // bit0 set: the runtime slow path's territory, refused statically.
    let b = rebind_segment_word(0x0009);
    match carve(&b, &fixture_map(), DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::MarkerBitSet { value, .. }) => assert_eq!(value, 9),
        other => panic!("expected MarkerBitSet, got {other:?}"),
    }
}

#[test]
fn refuse_record_out_of_range() {
    // 0x748 >> 3 = 233, past segnum 2: the "already carved" word shape.
    let b = rebind_segment_word(0x0748);
    match carve(&b, &fixture_map(), DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::RelocRecordOutOfRange { record, segnum, .. }) => {
            assert_eq!(record, 233);
            assert_eq!(segnum, 2);
        }
        other => panic!("expected RelocRecordOutOfRange, got {other:?}"),
    }
}

#[test]
fn refuse_odd_reloc_table_size() {
    // The carve reads the table size from the MAP (the descriptor's +0x0a
    // word, a byte count), not from the fixture bytes.
    let mut map = fixture_map();
    map.segments[0].relocation_count = 3;
    let b = fixture();
    match carve(&b, &map, DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::OddRelocTableSize { raw, .. }) => assert_eq!(raw, 3),
        other => panic!("expected OddRelocTableSize, got {other:?}"),
    }
}

#[test]
fn refuse_entry_out_of_range() {
    let mut b = fixture();
    // First relocation table entry: 3 -> 0xffff, past module size 0x10.
    b[0x220] = 0xff;
    b[0x221] = 0xff;
    match carve(&b, &fixture_map(), DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::RelocEntryOutOfRange { entry, size, .. }) => {
            assert_eq!(entry, 0xffff);
            assert_eq!(size, 0x10);
        }
        other => panic!("expected RelocEntryOutOfRange, got {other:?}"),
    }
}

#[test]
fn refuse_reloc_overflow() {
    // load segment 0xf000 + start_para 0x1010-equivalent would not fit;
    // use a start_para that overflows against a large load segment.
    let b = fixture();
    let map = fixture_map();
    match carve(&b, &map, 0xfff0) {
        Err(CarveError::RelocOverflow { .. }) => {}
        other => panic!("expected RelocOverflow, got {other:?}"),
    }
}

#[test]
fn refuse_segtab_mismatch() {
    let pristine = fixture();
    let mut map = fixture_map();
    map.segtab.pop();
    match carve(&pristine, &map, DEFAULT_LOAD_SEGMENT) {
        Err(CarveError::SegtabCountMismatch { have, want }) => {
            assert_eq!(have, 1);
            assert_eq!(want, 2);
        }
        other => panic!("expected SegtabCountMismatch, got {other:?}"),
    }
}
