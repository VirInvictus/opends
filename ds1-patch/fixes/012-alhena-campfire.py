"""fix.ds1.alhena-campfire: Alhena never materializes at the endgame
campfire. The caravan-arrival script (GPL-28@0x298) exits when
GF[123] == 1 (the caravan-raid flag, set at GPL-21@0x28a and never
cleared) BEFORE the post-war GF[138] branch that registers Alhena's
LOS trigger and spawns her (-212, the corpus's only spawn site at
GPL-28@0x51c). After the war every normal endgame has GF[123] set,
so the spawn is unreachable: the report ("has never materialized")
is exactly this. The fix guards the exit: it fires only when
GF[123] == 1 AND GF[138] == 0 (war not won), so a post-war arrival
falls through to the registration/spawn path. Beta: UNTESTED at
runtime; disabled by default per the beta QA gate (issue #18).
Finding: docs/ds1-sweep-triage row 2; authoring: gpl-asm movable
pipeline with both branch words relocated by the applier.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.alhena-campfire"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 28,
        "offset": 0x298,
        "expect": "188d7bd78f013e02a231",
        "replace": "188d7bd78f013e0013188d8ad88f013e00133167",
        "relocate": [7, 16],
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
