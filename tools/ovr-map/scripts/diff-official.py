#!/usr/bin/env python3
"""Cluster-annotated official-patch differ: CD 1.0 vs GOG 1.10 (DS2).

Phase 5.6.0's promotion of the first-measured segment diff (survey 8)
into a real tool. Pairs the two binaries' overlay segments, then for
every changed segment reports the differing bytes as per-cluster file
offsets in BOTH binaries, the nearest overlay entry stub to each
cluster, and a best-effort ndisasm excerpt decoded from the nearest
preceding entry (a valid instruction boundary).

Segment pairing is signature-checked, not blind index pairing: segments
whose descriptor geometry (size + entry-offset sequence) match exactly
are paired and the pairing is trustworthy function-by-function;
leftovers fall through to index pairing flagged UNVERIFIED, so an
insertion in either binary shows up as noise instead of a silent
misalignment.

DS1 is out of scope on purpose: no DS1 1.0 base exists to diff against
(docs/install-variants.md 1), and the floppy line is a different
product build. Defaults target the canonical comparison; both binaries
are overridable. Stdlib-only; needs `ndisasm` (nasm) for excerpts.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent

OLD_DEFAULT = Path(".games/archive-org/cd10-extracted/DSUN.EXE")
NEW_DEFAULT = Path(".games/ds2/DSUN.EXE")

# Differing bytes closer than this are one fix; 16 covers the 14-byte
# runs survey 8 observed in the low-cluster segments.
CLUSTER_GAP = 16


def load_ovr_map():
    """Import the ovr-map tool (hyphenated filename) for its parser."""
    spec = importlib.util.spec_from_file_location("ovr_map", TOOL_DIR / "ovr-map.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {TOOL_DIR / 'ovr-map.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def segment_signature(seg: dict) -> tuple | None:
    """Geometry signature: size + entry-offset sequence.

    Two segments with equal signatures are the same code under any
    rebuild that did not touch them; a rebuilt segment with shifted
    function boundaries will not match, which is the point.
    """
    if seg["empty"]:
        return None
    return (seg["size"], tuple(e["entry_offset"] for e in seg["entries"]))


def pair_segments(
    segs_old: list[dict], segs_new: list[dict]
) -> list[tuple[dict | None, dict | None, str]]:
    """Pair old/new segments, exact-signature matches first.

    Leftover non-empty segments pair by index among candidates the
    signature pass left unpaired, flagged 'unverified'. Returns
    (old, new, status) with status identical-geometry | unverified |
    old-only | new-only.
    """
    pairs: list[tuple[dict | None, dict | None, str]] = []
    used_old: set[int] = set()
    used_new: set[int] = set()

    by_sig_old: dict[tuple, list[int]] = {}
    for i, s in enumerate(segs_old):
        sig = segment_signature(s)
        if sig is not None:
            by_sig_old.setdefault(sig, []).append(i)

    for j, t in enumerate(segs_new):
        sig = segment_signature(t)
        if sig is None:
            continue
        for i in by_sig_old.get(sig, []):
            if i not in used_old and j not in used_new:
                pairs.append((segs_old[i], t, "identical-geometry"))
                used_old.add(i)
                used_new.add(j)
                break

    for i, s in enumerate(segs_old):
        if i in used_old or s["empty"]:
            continue
        if i < len(segs_new) and i not in used_new:
            pairs.append((s, segs_new[i], "unverified"))
            used_old.add(i)
            used_new.add(i)
        else:
            pairs.append((s, None, "old-only"))

    for j, t in enumerate(segs_new):
        if j not in used_new and not t["empty"]:
            pairs.append((None, t, "new-only"))

    return pairs


def diff_clusters(a: bytes, b: bytes) -> list[tuple[int, int]]:
    """Differing-byte clusters as (start, end) ranges over shared length."""
    clusters: list[tuple[int, int]] = []
    start = None
    prev = -CLUSTER_GAP - 1
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            if start is None:
                start = i
            elif i - prev > CLUSTER_GAP:
                clusters.append((start, prev + 1))
                start = i
            prev = i
    if start is not None:
        clusters.append((start, prev + 1))
    return clusters


def nearest_entry(seg: dict, local: int) -> dict | None:
    prior = [e for e in seg["entries"] if e["entry_offset"] <= local]
    return max(prior, key=lambda e: e["entry_offset"]) if prior else None


def ndisasm_excerpt(data: bytes, seg: dict, start: int, end: int) -> str:
    """Disassemble the cluster from the nearest preceding entry stub.

    Falls back to a segment-start decode when no entry precedes the
    cluster; that decode may be desynced and says so. Entries are the
    only instruction boundaries this tool can trust statically.
    """
    entry = nearest_entry(seg, start)
    from_off = entry["entry_offset"] if entry else 0
    length = min(end + 16, seg["size"]) - from_off
    proc = subprocess.run(
        ["ndisasm", "-b", "16", "-o", hex(from_off), "-"],
        input=data[
            seg["file_start"] + from_off : seg["file_start"] + from_off + length
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        return "    (ndisasm failed: %s)" % proc.stderr.decode(errors="replace").strip()
    lines = []
    for line in proc.stdout.decode(errors="replace").splitlines():
        try:
            local = int(line.split(None, 1)[0], 16)
        except (ValueError, IndexError):
            continue
        if start - 8 <= local < end + 8:
            lines.append("    " + line)
    tag = (
        f"decoded from entry cs:0x{entry['entry_offset']:04x}"
        if entry
        else "no preceding entry; decode may be desynced"
    )
    return f"    ({tag})\n" + "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--old", type=Path, default=OLD_DEFAULT, help="base DSUN.EXE (CD 1.0)"
    )
    ap.add_argument(
        "--new", type=Path, default=NEW_DEFAULT, help="patched DSUN.EXE (GOG 1.10)"
    )
    ap.add_argument(
        "--clusters",
        metavar="SEG[,SEG...]",
        help="per-cluster excerpts for these segments only (default: all)",
    )
    ap.add_argument(
        "--summary-only", action="store_true", help="survey-8-style table, no excerpts"
    )
    args = ap.parse_args(argv)

    for p in (args.old, args.new):
        if not p.is_file():
            print(f"error: no such file: {p}", file=sys.stderr)
            return 2

    ovr_map = load_ovr_map()
    try:
        rep_old = ovr_map.build(args.old)
        rep_new = ovr_map.build(args.new)
    except ovr_map.OvrError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    data_old = args.old.read_bytes()
    data_new = args.new.read_bytes()

    pairs = pair_segments(rep_old["segments"], rep_new["segments"])

    identical = changed = unverified = 0
    changed_segments: list[tuple[dict, dict, str]] = []
    for old, new, status in pairs:
        if old is None or new is None:
            continue
        a = data_old[old["file_start"] : old["file_end"]]
        b = data_new[new["file_start"] : new["file_end"]]
        if a == b:
            identical += 1
            continue
        changed += 1
        if status != "identical-geometry":
            unverified += 1
        changed_segments.append((old, new, status))

    print(f"CD 1.0 ({args.old}) vs GOG 1.10 ({args.new})")
    print(
        f"  segments identical: {identical}   changed: {changed} "
        f"(signature-verified pairs: {changed - unverified})"
    )
    print(
        "  pairing is signature-checked (size + entry-offset sequence); "
        "[UNVERIFIED] rows may be misaligned by an insertion."
    )
    print()

    want = None
    if args.clusters:
        want = {int(x) for x in args.clusters.split(",")}

    for old, new, status in sorted(changed_segments, key=lambda p: p[0]["index"]):
        a = data_old[old["file_start"] : old["file_end"]]
        b = data_new[new["file_start"] : new["file_end"]]
        clusters = diff_clusters(a, b)
        diff_bytes = sum(end - start for start, end in clusters)
        flag = "" if status == "identical-geometry" else "  [UNVERIFIED]"
        print(
            f"segment {old['index']:2d}: {len(clusters)} clusters, {diff_bytes} differing "
            f"bytes (old size {old['size']}, new size {new['size']}){flag}"
        )
        if args.summary_only or (want is not None and old["index"] not in want):
            continue
        for start, end in clusters:
            e_old = nearest_entry(old, start)
            anchor = (
                f"after entry cs:0x{e_old['entry_offset']:04x} "
                f"+{start - e_old['entry_offset']}"
                if e_old
                else "no preceding entry"
            )
            print(
                f"  cluster old 0x{old['file_start'] + start:x}..0x{old['file_start'] + end:x} "
                f"(seg-local 0x{start:x}..0x{end:x}, {end - start} B, {anchor})"
            )
            print(
                f"          new 0x{new['file_start'] + start:x}..0x{new['file_start'] + end:x}"
            )
            print("      old:")
            print(ndisasm_excerpt(data_old, old, start, end))
            print("      new:")
            print(ndisasm_excerpt(data_new, new, start, end))
        print()

    if not args.summary_only and not args.clusters:
        print(
            "Re-run with --clusters 0,5,8 for per-cluster excerpts "
            "(each re-decodes from its nearest preceding entry stub)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
