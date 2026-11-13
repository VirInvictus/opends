"""fix.ds1.tracking: the ranger tracking roll (GPL 210) over the
region 8 bodies can never succeed. Three stacked faults, per
Calvin Rodo's analysis (gate-verified): the ranger test reads the
class-bits word off the combat record instead of the sheet
(field 17's sheet target, 0x200 = the ranger bit); the three
class-slot bonus tests bit-test class CODES (13-16) against the
same 0x200, which is always false because a code is not a bitmask;
and the roll is inverted (success required the score under the
roll). Beta: UNTESTED at runtime; disabled by default. Source:
CalvinRodo/yuan-ti GplRepairs.cs (MIT);
docs/gate-review-yuan-ti-2026-11-13.md; field meanings per
docs/gplx-field-map.md.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.tracking"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repairs (GPL 210): four detours (the class reads and
# the range tests) plus one same-length swap (the roll direction).
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 210,
        "offset": 0x5FD,
        "expect": "18e28c20b1802601110200e1",
        "replace": "18e28c20b180260247110200e1",
    },
    {
        "kind": "GPL",
        "chunk_id": 210,
        "offset": 0x60C,
        "expect": "18e28c20b180260247230200e1",
        "replace": "18e28c20b18026024723d98f0ce1d5e2b18026024723da8f11e1",
    },
    {
        "kind": "GPL",
        "chunk_id": 210,
        "offset": 0x622,
        "expect": "18e28c20b180260247240200e1",
        "replace": "18e28c20b18026024724d98f0ce1d5e2b18026024724da8f11e1",
    },
    {
        "kind": "GPL",
        "chunk_id": 210,
        "offset": 0x638,
        "expect": "18e28c20b180260247250200e1",
        "replace": "18e28c20b18026024725d98f0ce1d5e2b18026024725da8f11e1",
    },
    {
        "kind": "GPL",
        "chunk_id": 210,
        "offset": 0x6CC,
        "expect": "188204dae28c528f14e1",
        "replace": "18e28c528f14e1da8204",
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
