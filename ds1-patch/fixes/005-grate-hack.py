"""fix.ds1.grate-hack: the slave pens' sewer grate (GPL 137) hack
path is dead. Three faults, per Calvin Rodo's analysis
(gate-verified): the weapon-in-hand test reads lflag[3] == 1 where
the code just set it to 0, so "hack the lock off" is never
offered; a successful hack never opens the grate (the pick path's
tail - print "The grate opens." via lstring[0], set gflag[505] -
never runs); and attacking the grate tests field 43 (most hit
points, which an item record does not carry and reads as 0) under
220, so the lock always breaks. The attack fix uses the rip-open
path's own roll form (RAND(30) < Str). Beta: UNTESTED at runtime;
disabled by default. Source: CalvinRodo/yuan-ti GplRepairs.cs
(MIT); docs/gate-review-yuan-ti-2026-11-13.md; field meanings per
docs/gplx-field-map.md.
"""

from darkfix.patcher import apply_gpl_repairs

ID = "fix.ds1.grate-hack"
TARGET = "GPLDATA.GFF"
SOURCE_SHA256 = "405fdadcf703b9ac15d05735e0a74cb41419e9178c6aced9f02538314dd6eb04"

# Chunk-relative repairs (GPL 137): one same-length guard flip and
# three detours (the his/her pronoun line with relocated labels,
# the pick-path tail appended after the sentence's period, and the
# Strength roll).
REPAIRS = [
    {
        "kind": "GPL",
        "chunk_id": 137,
        "offset": 0xA65,
        "expect": "18e28c4989258200e1d5e28e03d78f01e1",
        "replace": "18e28c4989258200e1d5e28e03d78f00e1",
    },
    {
        "kind": "GPL",
        "chunk_id": 137,
        "offset": 0x9E0,
        "expect": "4f0062920541cfae3c7979f3cdd766cf283461c7af9a0e9a32a0d9bf1eb41bf36641df4f4d083469e68018",
        "replace": "4f0062920541cfae3c7979f3cdd766cf283461c7af9a0e9a32a0d9bf1eb41bf36641df4f4d080180"
        + "18b18025024715d78f013e003f4f00629205d1a79a00603f004c4f00629205d19792006067",
        "relocate": [51, 64],
    },
    {
        "kind": "GPL",
        "chunk_id": 137,
        "offset": 0xA14,
        "expect": "4f006292055c8018",
        "replace": "4f006292055c80184f00628100168f01cd01f9",
    },
    {
        "kind": "GPL",
        "chunk_id": 137,
        "offset": 0xB5C,
        "expect": "18b18027012bda00dc",
        "replace": "18e28c528f1ee1dab180250117",
    },
]


def apply(source_path, dest_path):
    apply_gpl_repairs(source_path, dest_path, REPAIRS)
