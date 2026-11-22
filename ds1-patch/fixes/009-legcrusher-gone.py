"""fix.ds1.legcrusher-gone: the slave pens stop speaking of
Legcrusher as if he were about once he is dead or gone. The party
can kill Legcrusher (-326), after which Kurzak keeps calling for
him (GPL 136 @0x130), greets the party about him three ways (GPL
141 @0x6B4/0x70B/0x766), answers the half-giant question about him
(GPL 141 @0xF29), and Dinos still warns of him (GPL 139 @0x218).
Each site gains a detour guard: RANGE(GNAME[37], NAME(-326)) < 999
(Legcrusher still on the map) plays the shipped line; anything else
plays a replacement line. Beta: UNTESTED at runtime; disabled by
default, per the beta QA gate (issue #18). Discovery: CalvinRodo /
yuan-ti (MIT); the detour sources are OUR assembly of the recorded
design (issue #20, gpl-asm 0.10.0 movable mode), with one
notation note: Calvin's gname[5] and our GNAME[37] are the same
register (raw gname index 0x25, POV -- yuan-ti displays gname
indices minus 0x20, we keep the raw byte); the identity table is
docs/reference/gff-data-reference.md. The replacement lines are Calvin's, invented dialog by
recorded decision (known-bugs.md 3.6 row 4).
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.legcrusher-gone"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative detour repairs; each `replace` is the assembled
# detour body (guard, IF/ELSE around shipped vs replacement lines,
# ENDIF) with its two label words in detour-relative form; the
# applier appends [EXIT_GPL][body][JUMP back] past the chunk end and
# rebases the words listed in `relocate` (indices of the label
# words' first bytes inside `replace`).
REPAIRS = [
    {
        # Kurzak's call to the arena (GPL 136 @ 0x130)
        "kind": "GPL",
        "chunk_id": 136,
        "offset": 0x130,
        "expect": "4f0073920599973e3e5d79e8cbc90a08f97a20cfb30e4d387a6fe5cd0830",
        "replace": "18e28c808925910146e1da03e73e002e4f0073920599973e3e5d79e8cbc90a08f97a20cfb30e4d387a6fe5cd08303f00884f0073920599973e3e5d79e8cbc90a05cb972099973e3e5d79e8cbc9fa08587421411f661c9a70f4dfcb9ac419f2f441d7820d197965418b2e6dfcb2a092831efdb95064dfdf720c3bb220c9cb0e741e77f541d782106067",
        "relocate": [14, 47],
    },
    {
        # Kurzak's greeting (GPL 141 @ 0x6b4)
        "kind": "GPL",
        "chunk_id": 141,
        "offset": 0x6B4,
        "expect": "4f007392058fbf7e441d3469dd9d079dfd5067dfd1068cbcb2ae4125074d1bfae7d1d104941df0f3419f7e9dd9d074de83461ed95074de839e5dd9106febd100304f0073920599973e3e5d79e8cbc9720060",
        "replace": "18e28c808925910146e1da03e73e00624f007392058fbf7e441d3469dd9d079dfd5067dfd1068cbcb2ae4125074d1bfae7d1d104941df0f3419f7e9dd9d074de83461ed95074de839e5dd9106febd100304f0073920599973e3e5d79e8cbc97200603f00be4f007392058fbf7e441d3469dd9d079dfd5067dfd1068cbcb2ae415f4f4d082665cf8f975e7a32f2419f7eecab10494f91068c3db2a0d187220e9bd063dfb72a0c9bfbee4187764419b2f4c7a1079dfd506df3cf2ecccb900367",
        "relocate": [14, 99],
    },
    {
        # Kurzak's greeting once he sent Legcrusher (GPL 141 @ 0x70b)
        "kind": "GPL",
        "chunk_id": 141,
        "offset": 0x70B,
        "expect": "4f007392059283461c883a6f41cf2eec882665cf8f975e7a32f24187374cbc9079dfd572093d13f3419f7efc883a68c3d1079dfd5066dfd776441b72a0c59736fe5950034f00739205928336febbb220f3bfaae400c0",
        "replace": "18e28c808925910146e1da03e73e00664f007392059283461c883a6f41cf2eec882665cf8f975e7a32f24187374cbc9079dfd572093d13f3419f7efc883a68c3d1079dfd5066dfd776441b72a0c59736fe5950034f00739205928336febbb220f3bfaae400c03f00ba4f0073920592839e5ddd104ccb9f1f2ebcf465e4830e6e997920f3bfaac418776441a32a0dd97b65e4831e1db95062c38f5ae4125064dfb93f441cfaf0e1bf9e541e77f54f9106bddbfba0efa3cae400c067",
        "relocate": [14, 103],
    },
    {
        # Kurzak's greeting once Legcrusher found them (GPL 141 @ 0x766)
        "kind": "GPL",
        "chunk_id": 141,
        "offset": 0x766,
        "expect": "4f00739205929f6a0cfb30e441e77f541b34f3e997765c883a6f41332e7c7cbaf3d19792e4125068c3d32a0d3d1077d197720ef9506cdfcf2a0cfb30e4d387a6fe5cd0034f00739205e9a30f441df0f95c8018",
        "replace": "18e28c808925910146e1da03e73e00634f00739205929f6a0cfb30e441e77f541b34f3e997765c883a6f41332e7c7cbaf3d19792e4125068c3d32a0d3d1077d197720ef9506cdfcf2a0cfb30e4d387a6fe5cd0034f00739205e9a30f441df0f95c80183f00a44f00739205a7bd04ccb9f1f2ebcf465e48336febbb220f3bfaae4153465dc83be8f283269c9b93f441a32a0c7bf6e5418b0e3d683be9e9a1079dfd5fa00667",
        "relocate": [14, 100],
    },
    {
        # Kurzak's answer to the half-giant question (GPL 141 @ 0xf29)
        "kind": "GPL",
        "chunk_id": 141,
        "offset": 0xF29,
        "expect": "4f007392059fa1620e9a30f44fcd074d19506ddfbb9f4cbc9074e5874eecbc972091a79a0dd876e541a79a099973e3e5d79e8cbc9720064f0073920591953f341bb7f441d37ef418b969cfa3a2c418baf441a32a7e6833efdf91077d3d3420dbbf773e9979735c8018",
        "replace": "18e28c808925910146e1da03e73e00794f007392059fa1620e9a30f44fcd074d19506ddfbb9f4cbc9074e5874eecbc972091a79a0dd876e541a79a099973e3e5d79e8cbc9720064f0073920591953f341bb7f441d37ef418b969cfa3a2c418baf441a32a7e6833efdf91077d3d3420dbbf773e9979735c80183f00f24f00739205a9a30f441df0f341332e7c7cbaf3d19792c41d346541b77eee7d32f241d3961d3bb2f25c8276fc5bf27941a30f341cf2e5dc83469da83661e9976795c801804f0073920591953f341bb7f441d37ef418b969cfa3a2c418baf441a32a7e6833efdf91077d3d3420dbbf773e9979735c801867",
        "relocate": [14, 122],
    },
    {
        # Dinos's warning (GPL 139 @ 0x218)
        "kind": "GPL",
        "chunk_id": 139,
        "offset": 0x218,
        "expect": "4f0073920597d797ac3ad3f341b37efd7a7767419b7f241e77f55c82cefea83165e9d32f2419f7a0cda73e8e883165cdbf96541a32a0e797764e6801804f00739205dfd7a2099973e3e5d79e8cbc972006",
        "replace": "18e28c808925910146e1da03e73e00614f0073920597d797ac3ad3f341b37efd7a7767419b7f241e77f55c82cefea83165e9d32f2419f7a0cda73e8e883165cdbf96541a32a0e797764e6801804f00739205dfd7a2099973e3e5d79e8cbc9720063f00b14f0073920597d797ac3ad3f341b37efd7a7767419b7f241e77f55c82cefea83165e9d32f2419f7a0cda73e8e883165cdbf96541a32a0c7bf6e5e68326fefb9068cbcb2a0d1a76f3cbb332e400c67",
        "relocate": [14, 98],
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
