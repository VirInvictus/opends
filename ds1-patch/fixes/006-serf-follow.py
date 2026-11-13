"""fix.ds1.serf-follow: the Fields of Draj serf escort (GPL 60)
only follows the party across the region-10 exit when within 14
cells; one further behind stays behind without his orders and can
re-run the whole deal for a second obelisk gem (-1352). Calvin's
design: widen the follow-distance guard (14 -> 127) instead of our
triage's persistent-flag candidate, which needed chunk growth.
BALANCE-CLASS (item-duplication guard): off by default per spec 5
policy, and it stays off in this beta like every fix in it. Beta:
UNTESTED at runtime. Source: CalvinRodo/yuan-ti GplRepairs.cs
(MIT); docs/gate-review-yuan-ti-2026-11-13.md.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.serf-follow"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repair (GPL 60): one immediate in the
# RANGE(gname[37], -259) < 14 guard, same-length.
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 60,
        "offset": 0xCD8,
        "expect": "18e28c808925910103e1da8f0e",
        "replace": "18e28c808925910103e1da8f7f",
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
