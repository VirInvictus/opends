"""fix.ds1.deadtriggers: repoint the four static dead-trigger
registrations from the emptied GPL-200@0x909 stub to each object's
own working handler. See 001-deadtriggers.md for the full analysis
and the authoring pipeline that produced these bytes.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.deadtriggers"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repairs: each site covers opcode + handler entry
# immediate (+ chunk immediate where the handler changes chunk), at
# its offset inside the named GPL chunk. Same bytes as the original
# absolute-offset form (migrated 2026-11-17, issue #22); the
# selftest's real-install cycle pins the merged patched hash, which
# this migration must not change.
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 41,
        "offset": 0x1D,
        "expect": "66090900c8",
        "replace": "6600010029",
    },  # GPL-41@0x1d looktrigger -2248 -> GPL-41 entry 1
    {
        "kind": "GPL",
        "chunk_id": 195,
        "offset": 0x2B,
        "expect": "650909",
        "replace": "65033b",
    },  # GPL-195@0x2b attacktrigger -255 -> GPL-200 entry 0x33b
    {
        "kind": "GPL",
        "chunk_id": 203,
        "offset": 0x3FE,
        "expect": "66090900c8",
        "replace": "66038900cb",
    },  # GPL-203@0x3fe looktrigger -2263 -> GPL-203 entry 0x389
    {
        "kind": "GPL",
        "chunk_id": 203,
        "offset": 0x406,
        "expect": "66090900c8",
        "replace": "66038900cb",
    },  # GPL-203@0x406 looktrigger -1209 -> GPL-203 entry 0x389
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
