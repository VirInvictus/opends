"""fix.ds1.halfling-race: the slave pens' halfling (GPL 31) reads the
speaker's race from the combat record's field path, which carries
none (byte 0), so a halfling in the party is never greeted as one
and the insult names no race. The fix reads the character sheet's
race field (the 71-byte record, +0x18) instead. Beta: UNTESTED at
runtime; disabled by default. Source: CalvinRodo/yuan-ti
GplRepairs.cs (MIT), byte-encodings gate-verified 2026-11-13
(docs/gate-review-yuan-ti-2026-11-13.md); field meanings per
docs/gplx-field-map.md.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.halfling-race"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repairs (GPL 31): each site is a detour (+1 byte)
# swapping the depth-1 combat-record race read for the depth-2
# character-sheet path; the == 6 halfling-race test is unchanged.
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 31,
        "offset": 0x3B,
        "expect": "18b180250114d78f06",
        "replace": "18b18025024714d78f06",
    },
    {
        "kind": "GPL",
        "chunk_id": 31,
        "offset": 0x254,
        "expect": "17b180250114",
        "replace": "17b18025024714",
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
