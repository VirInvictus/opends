"""fix.ds1.script-repairs: three same-length script repairs from the
2026-10-07 DS1 sweep triage (docs/ds1-sweep-triage-2026-10-07.md):
the Lava Rifts hermit/ranger occlusion, the Linara conversation
dead-end, and the final-battle stage-gate strand. See
002-script-repairs.md for the full analysis and the safety
arguments. Disabled by default: this fix targets GPLDATA.GFF, and
spec 5 allows only one enabled fix per target file (001-deadtriggers
ships enabled); enable this one and toggle 001 off to take it.
"""

from darkfix.patcher import apply_bytes

ID = "fix.ds1.script-repairs"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Absolute GPLDATA.GFF offsets; each edit changes only the 2-byte
# entry/operand immediate, with the opcode and chunk bytes carried
# in the fingerprint (the localsub carries its 3-byte form).
# Fingerprints verified against the canonical GOG 1.10 install;
# chunk lengths are untouched.
EDITS = [
    {
        "offset": 0x0663D0,
        "expect": "1b00560064",
        "replace": "1b01bd0064",
    },  # GPL-100@0x684 inlostrigger -21 (the ranger) entry 86 -> 445:
    # 86 is the HERMIT's handler; the re-arm occludes the ranger's
    # own MAS-27 registration and replays the hermit scene (the
    # endless-dialog-loop and duplicate-Iron-Necklace bug).
    {
        "offset": 0x046522,
        "expect": "13134e",
        "replace": "1300d1",
    },  # GPL-68@0xaa local sub 4942 -> 209: GNUM55==2 routed to a
    # one-line dead end with no menu; 209 is the general menu every
    # other branch of the conversation uses (the Jasmine spellbook
    # topic becomes discussable again).
    {
        "offset": 0x03FB1C,
        "expect": "10f9",
        "replace": "00ef",
    },  # GPL-62@0x10f1 noorderstrigger entry 4345 -> 239: the
    # inter-stage time gate 4345 exits without re-arming when a
    # stage is cleared inside its window, stranding the final
    # battle permanently; arming the driver 239 directly removes
    # the strand (and the intended inter-stage pause).
]


def apply(source_path, dest_path):
    apply_bytes(source_path, dest_path, EDITS)
