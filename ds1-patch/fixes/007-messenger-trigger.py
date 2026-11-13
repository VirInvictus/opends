"""fix.ds1.messenger-trigger: region 9's messenger never arrives
for players who stay in the region through the elves' departure.
MAS 9 registers his sight trigger (GPL 133 entry 1 on object
-1297) only when gflag[245] is already set at region load, but
gflag[245] flips mid-stay at GPL 58; without a re-entry the
registration never happens. Our triage named the three GPL-58
sites; Calvin Rodo implemented the register-on-flip fix as three
identical detours that re-arm MAS 9's own registration, behind
MAS 9's own gflag[339] == 0 guard (set by GPL 133/132 once the
messenger fires). Site ours, implementation his; gate-verified
2026-11-13. Beta: UNTESTED at runtime; disabled by default.
Source: CalvinRodo/yuan-ti GplRepairs.cs (MIT);
docs/gate-review-yuan-ti-2026-11-13.md.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.messenger-trigger"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repairs (GPL 58): three detours with identical
# structure, one per gflag[245] = 1 site. Each preserves the
# original store, then registers the trigger while gflag[339] == 0.
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 58,
        "offset": 0x1A,
        "expect": "168f018df5",
        "replace": "168f018df5"
        + "18cd0153d78f00"
        + "3e0019"
        + "1b000100859105118f0f"
        + "67",
        "relocate": [13],
    },
    {
        "kind": "GPL",
        "chunk_id": 58,
        "offset": 0x99,
        "expect": "168f018df5",
        "replace": "168f018df5"
        + "18cd0153d78f00"
        + "3e0019"
        + "1b000100859105118f0f"
        + "67",
        "relocate": [13],
    },
    {
        "kind": "GPL",
        "chunk_id": 58,
        "offset": 0xCC,
        "expect": "168f018df5",
        "replace": "168f018df5"
        + "18cd0153d78f00"
        + "3e0019"
        + "1b000100859105118f0f"
        + "67",
        "relocate": [13],
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
