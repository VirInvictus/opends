"""fix.ds2.deadtriggers: repoint the 27 static dead-trigger
registrations from the shared no-op GPL-24@0x1 entry to each
object's own working handler. See 001-deadtriggers.md for the full
analysis and the authoring pipeline that produced these bytes.
"""

from darkfix.patcher import apply_bytes

ID = "fix.ds2.deadtriggers"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "be5efb2b76a5f77b9858b9583bd34c452ea86869f0c866436cf8e298ad96fbb8"

# Absolute GPLDATA.GFF offsets; each edit covers opcode + handler
# entry immediate + chunk immediate (the handler changes chunk in
# every row: from the shared no-op GPL-24 to a region chunk).
# Fingerprints verified against the canonical GOG 1.10 install;
# chunk lengths are untouched.
EDITS = [
    {
        "offset": 0x0979E6,
        "expect": "6600010018",
        "replace": "66070800a3",
    },  # GPL-163@0x428 looktrigger -1923 -> GPL-163@1800
    {
        "offset": 0x0B4353,
        "expect": "6d00010018",
        "replace": "6d18cd00bb",
    },  # GPL-187@0x18cd usetrigger -2975 -> GPL-187@6349
    {
        "offset": 0x0B504D,
        "expect": "6d00010018",
        "replace": "6d081f00bc",
    },  # GPL-188@0x81f usetrigger -2975 -> GPL-188@2079
    {
        "offset": 0x0B5747,
        "expect": "6d00010018",
        "replace": "6d0f1900bc",
    },  # GPL-188@0xf19 usetrigger -2975 -> GPL-188@3865
    {
        "offset": 0x0F7AFA,
        "expect": "6d00010018",
        "replace": "6d0c0e00e8",
    },  # GPL-232@0xc76 usetrigger -2975 -> GPL-232@3086
    {
        "offset": 0x0FA309,
        "expect": "6d00010018",
        "replace": "6d074200ea",
    },  # GPL-234@0x742 usetrigger -2975 -> GPL-234@1858
    {
        "offset": 0x106C30,
        "expect": "6d00010018",
        "replace": "6d09fe00f6",
    },  # GPL-246@0xa4b usetrigger -2975 -> GPL-246@2558
    {
        "offset": 0x11D1F3,
        "expect": "6d00010018",
        "replace": "6d00c30110",
    },  # GPL-272@0xca usetrigger -2975 -> GPL-272@195
    {
        "offset": 0x11D265,
        "expect": "6d00010018",
        "replace": "6d00c30110",
    },  # GPL-272@0x13c usetrigger -2975 -> GPL-272@195
    {
        "offset": 0x211DA7,
        "expect": "6d00010018",
        "replace": "6d08d50144",
    },  # GPL-324@0x8d5 usetrigger -2975 -> GPL-324@2261
    {
        "offset": 0x016C48,
        "expect": "6d00010018",
        "replace": "6d1b550023",
    },  # GPL-35@0x1b5e usetrigger -2975 -> GPL-35@6997
    {
        "offset": 0x020086,
        "expect": "6d00010018",
        "replace": "6d0d460031",
    },  # GPL-49@0xd46 usetrigger -2975 -> GPL-49@3398
    {
        "offset": 0x0292E9,
        "expect": "6d00010018",
        "replace": "6d06d5003a",
    },  # GPL-58@0x3a6 usetrigger -2975 -> GPL-58@1749
    {
        "offset": 0x02960F,
        "expect": "6d00010018",
        "replace": "6d06c7003a",
    },  # GPL-58@0x6cc usetrigger -2975 -> GPL-58@1735
    {
        "offset": 0x029618,
        "expect": "6d00010018",
        "replace": "6d06c7003a",
    },  # GPL-58@0x6d5 usetrigger -2975 -> GPL-58@1735
    {
        "offset": 0x0537FA,
        "expect": "6d00010018",
        "replace": "6d1429005b",
    },  # GPL-91@0x1418 usetrigger -2975 -> GPL-91@5161
    {
        "offset": 0x05380B,
        "expect": "6d00010018",
        "replace": "6d1429005b",
    },  # GPL-91@0x1429 usetrigger -2975 -> GPL-91@5161
    {
        "offset": 0x20937D,
        "expect": "6d00010018",
        "replace": "6d1219004a",
    },  # GPL-74@0x1219 usetrigger -2975 -> GPL-74@4633
    {
        "offset": 0x01C6DE,
        "expect": "6d00010018",
        "replace": "6d0614002d",
    },  # GPL-45@0x636 usetrigger -2975 -> GPL-45@1556 (attested by GPL-40)
    {
        "offset": 0x0046F3,
        "expect": "6500010018",
        "replace": "65035d0008",
    },  # GPL-8@0x473 attacktrigger -209 -> GPL-8@861
    {
        "offset": 0x0046FB,
        "expect": "6500010018",
        "replace": "65035d0008",
    },  # GPL-8@0x47b attacktrigger -406 -> GPL-8@861
    {
        "offset": 0x0046EB,
        "expect": "6500010018",
        "replace": "65035d0008",
    },  # GPL-8@0x46b attacktrigger -418 -> GPL-8@861 (sibling rows)
    {
        "offset": 0x00A53C,
        "expect": "6600010018",
        "replace": "6604ee000f",
    },  # GPL-15@0x528 looktrigger -2994 -> GPL-15@1262 (attested by MAS-67)
    {
        "offset": 0x01F0F4,
        "expect": "6600010018",
        "replace": "660359002f",
    },  # GPL-47@0x285 looktrigger -445 -> GPL-47@857 (attested by GPL-30)
    {
        "offset": 0x029061,
        "expect": "6e00010018",
        "replace": "6e00010045",
    },  # GPL-58@0x11e talktotrigger -106 -> GPL-69@1 (attested by MAS-59)
    {
        "offset": 0x209177,
        "expect": "6e00010018",
        "replace": "6e00010045",
    },  # GPL-74@0x1013 talktotrigger -106 -> GPL-69@1 (attested by MAS-59)
    {
        "offset": 0x20024D,
        "expect": "6500010018",
        "replace": "6504cd001d",
    },  # GPL-30@0x1146 attacktrigger -146 -> GPL-29@1229 (attested by MAS-1)
]


def apply(source_path, dest_path):
    apply_bytes(source_path, dest_path, EDITS)
