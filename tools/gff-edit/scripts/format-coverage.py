#!/usr/bin/env python3
"""Format coverage report: which GFF chunk kinds exist, which are documented.

Phase 5.6.0. Walks a dev-side games tree, parses every GFF container's
TOC (28-byte header + type list only; no chunk bodies), and tabulates
chunks per FOURCC: how many files carry it, how many chunks, and
whether the kind is documented. The documented baseline is captured
from `gff-cat kind --list` (gff-edit v0.6.0) and embedded below;
regenerate the baseline with --kinds-file <output-of-kind-list> when
gff-edit grows.

The point is the gap list: chunk kinds the corpus actually contains
but no doc describes (RNME, VECT, PLYL, ALL, DATA, RGTP, PREF, GREQ
at minimum, per the 2026-09-04 deep-dive), and containers no tool has
ever touched. Stdlib-only; the report is regenerated output, safe to
commit as docs.

Exit codes: 0 ok, 2 bad input paths.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

# Captured from `cargo run -p gff-edit -- kind --list` (gff-edit 0.6.0),
# 2026-09-04. Refresh with --kinds-file when gff-edit's catalogue grows.
KNOWN_KINDS = frozenset(
    """GFFI FORM GFRE GTOC PAL BMP BMAP PORT WALL ICON TILE TMAP TXRF OMAP
    CMAP CBMP FONT BMA ACF RMAP GMAP ETAB MONR MSEQ PSEQ FSEQ LSEQ GSEQ
    CSEQ MGTL BVOC FVOC SINF ADV DADV DRV WIND DBOX EBOX BUTN MENU SBAR
    APFM ACCL IT1R OJFF RDFF FNFO RDAT NAME TEXT MERR ETME SPIN SCMD SJMP
    POBJ GPL MAS GPLI GPLX CHAR SPST PSST PSIN CACT STXT SAVE""".split()
)

DEFAULT_ROOTS = (".games", "testing_facility")


def parse_gff_toc(data: bytes) -> dict[str, int] | None:
    """Parse the TOC type list: FOURCC -> chunk count. None if not a GFF.

    Header (28 bytes) + TOC header + type list per docs/file-formats.md
    1. Segmented type lists (0x80000000 count flag) contribute their
    low-31-bits count; per-chunk resolution is not needed for coverage.
    """
    if len(data) < 28 or data[:4] != b"GFFI":
        return None
    toc_location = struct.unpack_from("<I", data, 12)[0]
    toc_length = struct.unpack_from("<I", data, 16)[0]
    if toc_location + 8 > len(data) or toc_length == 0:
        return None
    types_offset, _free_list_offset = struct.unpack_from("<II", data, toc_location)
    pos = toc_location + types_offset
    if pos + 2 > len(data):
        return None
    (num_types,) = struct.unpack_from("<H", data, pos)
    pos += 2
    kinds: dict[str, int] = {}
    for _ in range(num_types):
        if pos + 8 > len(data):
            return None
        fourcc_raw, count = struct.unpack_from("<II", data, pos)
        pos += 8
        # Some catalogued kinds carry a NUL or other non-printable byte
        # in the FOURCC; keep them printable in report output.
        raw = fourcc_raw.to_bytes(4, "little")
        fourcc = "".join(chr(b) if 0x20 <= b < 0x7F else "?" for b in raw)
        # FOURCCs are padded to 4 bytes ("PAL ", "BMP "); the catalogue
        # spells them without padding, so compare (and display) stripped.
        fourcc = fourcc.rstrip() or "?"
        if count & 0x80000000:
            # Segmented list: a 12-byte (seg_count, seg_loc_id,
            # num_entries) trio follows, then num_entries 8-byte
            # (first_id, num_chunks) runs. Layout per gff-edit's
            # parse_toc (src/lib.rs), the in-repo authority.
            if pos + 12 > len(data):
                return None
            _seg_count, _seg_loc_id, num_runs = struct.unpack_from("<iiI", data, pos)
            pos += 12
            if pos + num_runs * 8 > len(data):
                return None
            pos += num_runs * 8
            kinds[fourcc] = kinds.get(fourcc, 0) + (count & 0x7FFFFFFF)
        else:
            pos += count * 12  # (id, location, length) u32 triplets follow
            kinds[fourcc] = kinds.get(fourcc, 0) + count
    return kinds


def game_label(path: Path, roots: list[Path]) -> str:
    try:
        rel = path.relative_to(roots[0].resolve())
    except (ValueError, IndexError):
        return str(path.parent)
    parts = rel.parts
    return "/".join(parts[:2]) if len(parts) > 1 else (parts[0] if parts else ".")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--roots",
        default=",".join(DEFAULT_ROOTS),
        help="comma-separated dirs to walk (default: .games,testing_facility)",
    )
    ap.add_argument(
        "--kinds-file",
        type=Path,
        help="refresh the baseline from `gff-cat kind --list` output",
    )
    ap.add_argument("--json", action="store_true", help="machine JSON")
    args = ap.parse_args(argv)

    roots = [Path(r) for r in args.roots.split(",") if r]
    for r in roots:
        if not r.is_dir():
            print(f"error: root is not a directory: {r}", file=sys.stderr)
            return 2

    known = set(KNOWN_KINDS)
    if args.kinds_file:
        known = {
            line.split()[0]
            for line in args.kinds_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

    stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {"files": 0, "chunks": 0, "games": set()}
    )
    gff_files = 0
    skipped = 0
    unparsed = []
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError:
                skipped += 1
                continue
            if data[:4] != b"GFFI":
                skipped += 1
                continue
            kinds = parse_gff_toc(data)
            if kinds is None:
                unparsed.append(path)
                continue
            gff_files += 1
            label = game_label(path, roots)
            for fourcc, count in kinds.items():
                row = stats[fourcc]
                row["files"] += 1  # type: ignore[operator]
                row["chunks"] += count  # type: ignore[operator]
                row["games"].add(label)  # type: ignore[union-attr]

    undocumented = {k: v for k, v in stats.items() if k not in known}
    never_seen = sorted(known - set(stats))

    if args.json:
        print(
            json.dumps(
                {
                    "gff_files": gff_files,
                    "skipped_files": skipped,
                    "unparsed": [str(p) for p in unparsed],
                    "kinds": {
                        fcc: {
                            "files": v["files"],
                            "chunks": v["chunks"],
                            "games": sorted(v["games"]),
                            "documented": fcc in known,
                        }
                        for fcc, v in sorted(stats.items())
                    },
                    "documented_never_seen_in_corpus": never_seen,
                },
                indent=2,
                default=lambda o: sorted(o) if isinstance(o, set) else str(o),
            )
        )
        return 0

    def sort_key(item):
        fcc, v = item
        return (fcc in known, -v["chunks"], fcc)

    print("# GFF format coverage report (machine-generated, `format-coverage.py`)")
    print("#")
    print(f"# roots: {', '.join(str(r) for r in roots)}")
    print(f"# GFF containers: {gff_files}   non-GFF/skipped files: {skipped}")
    if unparsed:
        print(f"# ⚠ files with GFFI magic but unparsable TOC: {len(unparsed)}")
        for p in unparsed:
            print(f"#   {p}")
    print(
        f"# documented kinds in corpus: {len(stats) - len(undocumented)} / {len(known)}"
    )
    print()
    print("## Undocumented kinds in the corpus (the gap list)")
    print()
    print("| FOURCC | files | chunks | where |")
    print("|---|---|---|---|")
    for fcc, v in sorted(undocumented.items(), key=sort_key):
        where = ", ".join(sorted(v["games"])[:4])
        more = "" if len(v["games"]) <= 4 else f" (+{len(v['games']) - 4} dirs)"
        print(f"| `{fcc}` | {v['files']} | {v['chunks']} | {where}{more} |")
    if not undocumented:
        print("_(none)_")
    print()
    print("## Documented kinds in the corpus")
    print()
    print("| FOURCC | files | chunks |")
    print("|---|---|---|")
    for fcc, v in sorted(
        ((k, v) for k, v in stats.items() if k in known), key=sort_key
    ):
        print(f"| `{fcc}` | {v['files']} | {v['chunks']} |")
    print()
    print("## Documented kinds never seen in this corpus")
    print()
    print(", ".join(f"`{k}`" for k in never_seen) or "_(none)_")
    return 0


if __name__ == "__main__":
    sys.exit(main())
