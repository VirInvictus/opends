"""fix.ds1.trustee-rounds: the slave pens' Trustee (-89) stops for
good. His rounds state counter GNUM[20] is picked apart by other pen
scripts: GPL 147 sets it to 8 for the gate scene, GPL 137 resets it
to 0 -- and GPL 137's knock-fight path (GPL 137 @0x1740) subtracts
2 unguarded, driving it negative from states 0 or 1. A negative
state matches no corner case in GPL 8's rounds switch, so on a
fresh load (locals zeroed) the Trustee walks toward tile (0,0) --
a spot that does not exist -- never arrives, never advances the
state, and the busy flag (cleared only by GPL 8's state-0 arm,
@0xedc) never lifts: his dialog sticks at "I'd love to talk more,
but I have to get back to work". The fix guards the writer: below
2, the knock clamps the state to 0 (the same reset GPL 137's own
door path uses at @0x1520) instead of going negative. Beta: UNTESTED
at runtime; disabled by default per the beta QA gate (issue #18).
Relayed claim verified and fixed by our own trace (issue #23;
trace record in fixes/010-trustee-rounds.md).
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.trustee-rounds"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# One chunk-relative detour repair: the knock-fight path's unguarded
# `word minus equal GNUM[20], 2` becomes a guarded subtract.
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 137,
        "offset": 0x1740,
        "expect": "7b87148f02",
        "replace": "188714da8f023e000e168f0087143f00167b87148f0267",
        "relocate": [7, 15],
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
