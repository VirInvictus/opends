"""fix.ds1.script-repairs: three same-length script repairs from the
2026-10-07 DS1 sweep triage (docs/ds1-sweep-triage-2026-10-07.md):
the Lava Rifts hermit/ranger occlusion, the Linara conversation
dead-end, and the final-battle stage-gate strand. See
002-script-repairs.md for the full analysis and the safety
arguments. Disabled by default: this fix targets GPLDATA.GFF, and
spec 5 allows only one enabled fix per target file (001-deadtriggers
ships enabled); enable this one and toggle 001 off to take it.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.script-repairs"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repairs: each site changes only the 2-byte
# entry/operand immediate, with the opcode and chunk bytes carried
# in the fingerprint (the localsub carries its 3-byte form). Same
# bytes as the original absolute-offset form (migrated 2026-11-17,
# issue #22); the selftest's real-install cycle pins the merged
# patched hash, which this migration must not change.
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 100,
        "offset": 0x684,
        "expect": "1b00560064",
        "replace": "1b01bd0064",
    },  # GPL-100@0x684 inlostrigger -21 (the ranger) entry 86 -> 445:
    # 86 is the HERMIT's handler; the re-arm occludes the ranger's
    # own MAS-27 registration and replays the hermit scene (the
    # endless-dialog-loop and duplicate-Iron-Necklace bug).
    {
        "kind": "GPL",
        "chunk_id": 68,
        "offset": 0xAA,
        "expect": "13134e",
        "replace": "1300d1",
    },  # GPL-68@0xaa local sub 4942 -> 209: GNUM55==2 routed to a
    # one-line dead end with no menu; 209 is the general menu every
    # other branch of the conversation uses (the Jasmine spellbook
    # topic becomes discussable again).
    {
        "kind": "GPL",
        "chunk_id": 62,
        "offset": 0x10F1,
        "expect": "10f9",
        "replace": "00ef",
    },  # GPL-62@0x10f1 noorderstrigger entry 4345 -> 239: the
    # inter-stage time gate 4345 exits without re-arming when a
    # stage is cleared inside its window, stranding the final
    # battle permanently; arming the driver 239 directly removes
    # the strand (and the intended inter-stage pause).
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
