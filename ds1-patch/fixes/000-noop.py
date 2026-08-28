"""fix.ds1.noop: pipeline-proof no-op fix. Edits zero bytes.

Exists to prove the darkfix package shape end to end (roadmap
Phase 6): hash verification, backup, journal, --verify, and the
--unapply round-trip, before any real fix ships.
"""

from darkfix.patcher import apply_bytes

ID = "fix.ds1.noop"
TARGET = "DSUN.EXE"
SOURCE_SHA256 = "7bbd84f105b1ebe538a4abdfccdb2bacbf5b4fa763b45fa3a84499780f1d8c96"
EDITS = []


def apply(source_path, dest_path):
    apply_bytes(source_path, dest_path, EDITS)
