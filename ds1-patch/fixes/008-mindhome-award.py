"""fix.ds1.mindhome-award: the Rebel Mindhome's 5000 XP for the
spiders re-awards on every re-talk once the spiders are dead
(our triage 3.2(4) bonus finding); nothing reads gflag[695],
which the first award sets. Calvin Rodo's fix gates the award
(and its GPL 74 call) on gflag[695] == 0. The re-ask half of the
bug (the GPL-204 router never consulting GF695) is NOT fixed
here and remains queued. Beta: UNTESTED at runtime; disabled by
default. Source: CalvinRodo/yuan-ti GplRepairs.cs (MIT);
docs/gate-review-yuan-ti-2026-11-13.md.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.mindhome-award"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repair (GPL 204): the gnum[16] = 5000 award and its
# global sub move behind an IF gflag[695] == 0 (a detour whose
# label word at replace offset 8 is the IF's ENDIF target).
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 204,
        "offset": 0x5C9,
        "expect": "1613888710140087004a",
        "replace": "18cd02b7d78f003e0014" + "1613888710140087004a" + "67",
        "relocate": [8],
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
