"""fix.ds1.slave-follow: the battlefield slave stops following the
party after a zone transition. The follow order
(`follow GNAME[37], NAME(-198)`) is issued exactly once
(GPL-132@0x38b) and nothing re-issues it when region 9 reloads.
The fix appends the follow to MAS-9's post-raid ordering block
(@0x9e-0xbe), which runs at region load once the raid flag
(GF[5]) is set -- the same window that already orders the two
departed elves. Beta: UNTESTED at runtime; disabled by default
per the beta QA gate (issue #18). Finding: docs/ds1-sweep-triage
row 1b; authoring: gpl-asm 0.10.x movable pipeline, no
relocations (straight-line body).
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.slave-follow"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

REPAIRS = [
    {
        "kind": "MAS",
        "chunk_id": 9,
        "offset": 0x9E,
        "expect": "3c8f448f029100c73c8f448f029100c86f0c0900879100c76f0c0900879100c8",
        "replace": "3c8f448f029100c73c8f448f029100c86f0c0900879100c76f0c0900879100c83789259100c6",
        "relocate": [],
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
