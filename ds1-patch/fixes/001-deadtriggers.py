"""fix.ds1.deadtriggers: repoint the four static dead-trigger
registrations from the emptied GPL-200@0x909 stub to each object's
own working handler. See 001-deadtriggers.md for the full analysis
and the authoring pipeline that produced these bytes.
"""

from darkfix.patcher import apply_bytes

ID = "fix.ds1.deadtriggers"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Absolute GPLDATA.GFF offsets; each edit covers opcode + handler
# entry immediate (+ chunk immediate where the handler changes
# chunk). Fingerprints verified against the canonical GOG 1.10
# install; chunk lengths are untouched.
EDITS = [
    {
        "offset": 0x029D1E,
        "expect": "66090900c8",
        "replace": "6600010029",
    },  # GPL-41@0x1d looktrigger -2248 -> GPL-41 entry 1
    {
        "offset": 0x0BE7FD,
        "expect": "650909",
        "replace": "65033b",
    },  # GPL-195@0x2b attacktrigger -255 -> GPL-200 entry 0x33b
    {
        "offset": 0x0C666C,
        "expect": "66090900c8",
        "replace": "66038900cb",
    },  # GPL-203@0x3fe looktrigger -2263 -> GPL-203 entry 0x389
    {
        "offset": 0x0C6674,
        "expect": "66090900c8",
        "replace": "66038900cb",
    },  # GPL-203@0x406 looktrigger -1209 -> GPL-203 entry 0x389
]


def apply(source_path, dest_path):
    apply_bytes(source_path, dest_path, EDITS)
