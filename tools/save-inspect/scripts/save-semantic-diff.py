#!/usr/bin/env python3
"""Semantic SAVE diff: play-session byte diffs annotated with field meaning.

Phase 5.6.0's DARKRUN SAVE semantic differ. `save-inspect save-diff`
answers "which SAVE chunks changed"; this tool answers "what does the
change mean" as far as the repo's accumulated knowledge goes. Each
differing byte cluster inside a chunk is matched against the field
hypotheses in `syms/save-fields.toml` (kind + id + byte range, with a
record-array interpretation where the chunk is one), and labelled with
the row's meaning, confidence and evidence. Clusters no row covers are
grouped as unknown: that list is the next session's RE target, and a
confirmed discovery becomes a new TOML row, so understanding
accumulates in the catalogue instead of scrollback.

Stdlib-only. Reuses save-inspect's parser for the GFF plumbing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent

CLUSTER_GAP = 16  # differing bytes closer than this are one change

CONFIDENCE_RANK = {"verified": 0, "probable": 1, "speculative": 2}


def load_save_inspect():
    spec = importlib.util.spec_from_file_location(
        "save_inspect", TOOL_DIR / "save-inspect.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {TOOL_DIR / 'save-inspect.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def chunk_map(parsed: dict) -> dict[tuple[str, int], dict]:
    """(kind, id) -> chunk record with absolute file placement."""
    out: dict[tuple[str, int], dict] = {}
    for c in parsed.get("chunks", []):
        out[(c["kind"], int(c["id"]))] = c
    return out


def diff_clusters(a: bytes, b: bytes) -> list[tuple[int, int]]:
    """Differing-byte clusters as [start, end) over the shared length."""
    clusters: list[tuple[int, int]] = []
    start = None
    prev = -(CLUSTER_GAP + 1)
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


def load_hypotheses(path: Path) -> list[dict]:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    rows = []
    for i, row in enumerate(data.get("field", [])):
        where = f"{path}:field[{i}]"
        kind = row.get("kind")
        cid = row.get("id")
        rng = row.get("range")
        if not kind or cid is None or not rng or len(rng) != 2:
            raise ValueError(f"{where}: kind, id and range [start, end) are required")
        if row.get("confidence", "speculative") not in CONFIDENCE_RANK:
            raise ValueError(
                f"{where}: confidence must be verified|probable|speculative"
            )
        rows.append(row)
    return rows


def covering_rows(
    rows: list[dict], kind: str, cid: int, start: int, end: int
) -> list[dict]:
    """Hypothesis rows whose (record, range) covers a cluster."""
    hits = []
    for row in rows:
        if row["kind"] != kind or int(row["id"]) != cid:
            continue
        lo, hi = row["range"]
        record_size = row.get("record_size")
        if record_size:
            first_record = start // record_size
            last_record = max(first_record, (end - 1) // record_size)
            if last_record != first_record:
                # Spans records; report the range, not a single index.
                hits.append((row, first_record, last_record))
                continue
            lo_abs, hi_abs = (
                first_record * record_size + lo,
                first_record * record_size + hi,
            )
        else:
            lo_abs, hi_abs = lo, hi
        if lo_abs <= start and end <= hi_abs:
            hits.append((row, None, None))
    return hits


def annotate(rows: list[dict], kind: str, cid: int, start: int, end: int) -> list[dict]:
    """Annotations for one cluster, most-verified first."""
    out = []
    for row, first_rec, last_rec in covering_rows(rows, kind, cid, start, end):
        entry = {
            "meaning": row["meaning"],
            "confidence": row.get("confidence", "speculative"),
            "evidence": row.get("evidence", ""),
        }
        if first_rec is not None:
            entry["records"] = [first_rec, last_rec]
        elif row.get("record_size"):
            entry["record"] = start // row["record_size"]
            entry["field_offset_in_record"] = start % row["record_size"]
        out.append(entry)
    out.sort(key=lambda e: CONFIDENCE_RANK.get(e["confidence"], 9))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("a", type=Path, help="earlier DARKRUN-shape GFF")
    ap.add_argument("b", type=Path, help="later DARKRUN-shape GFF")
    ap.add_argument(
        "--fields",
        type=Path,
        default=TOOL_DIR / "syms" / "save-fields.toml",
        help="field hypotheses TOML (default: syms/save-fields.toml)",
    )
    ap.add_argument(
        "--all-chunks",
        action="store_true",
        help="include non-SAVE chunks too (default: SAVE only)",
    )
    ap.add_argument("--json", action="store_true", help="machine JSON")
    args = ap.parse_args(argv)

    for p in (args.a, args.b):
        if not p.is_file():
            print(f"error: no such file: {p}", file=sys.stderr)
            return 2

    si = load_save_inspect()
    a_map = chunk_map(si.parse_gff(args.a))
    b_map = chunk_map(si.parse_gff(args.b))
    rows = load_hypotheses(args.fields)

    report: list[dict] = []
    for key in sorted(set(a_map) | set(b_map)):
        kind, cid = key
        if not args.all_chunks and kind != "SAVE":
            continue
        in_a, in_b = a_map.get(key), b_map.get(key)
        if in_a is None or in_b is None:
            report.append(
                {
                    "chunk": f"{kind}-{cid}",
                    "change": "added" if in_b else "removed",
                    "byte_length": (in_b or in_a)["length"],
                }
            )
            continue
        a_body, b_body = in_a["bytes"], in_b["bytes"]
        if a_body == b_body:
            continue
        clusters = diff_clusters(a_body, b_body)
        entry: dict = {
            "chunk": f"{kind}-{cid}",
            "change": "modified",
            "clusters": [],
        }
        for start, end in clusters:
            cluster = {
                "offset": start,
                "end": end,
                "bytes": end - start,
                "before": a_body[start:end].hex(" "),
                "after": b_body[start:end].hex(" "),
                "annotations": annotate(rows, kind, cid, start, end),
            }
            entry["clusters"].append(cluster)
        report.append(entry)

    if args.json:
        print(
            json.dumps({"a": str(args.a), "b": str(args.b), "chunks": report}, indent=2)
        )
        return 0

    print(f"# Semantic SAVE diff: {args.a} vs {args.b}")
    print(f"# field hypotheses: {args.fields}")
    changed = [r for r in report if r["change"] == "modified"]
    print(
        f"# {len(changed)} chunks changed, "
        f"{sum(r['change'] != 'modified' for r in report)} added/removed"
    )
    print()
    for entry in report:
        if entry["change"] != "modified":
            print(f"{entry['chunk']}: {entry['change']} ({entry['byte_length']} bytes)")
            continue
        print(f"{entry['chunk']}: {len(entry['clusters'])} cluster(s)")
        for c in entry["clusters"]:
            loc = f"offset 0x{c['offset']:x}..0x{c['end']:x} ({c['bytes']} B)"
            if c["annotations"]:
                for ann in c["annotations"]:
                    loc_extra = ""
                    if "record" in ann:
                        loc_extra = (
                            f", record {ann['record']}"
                            f" field+0x{ann['field_offset_in_record']:x}"
                        )
                    elif "records" in ann:
                        loc_extra = (
                            f", records {ann['records'][0]}..{ann['records'][1]}"
                        )
                    print(f"  {loc}{loc_extra}: {ann['meaning']} [{ann['confidence']}]")
                    break  # strongest annotation is the headline
                others = len(c["annotations"]) - 1
                if others:
                    print(f"    (+{others} more hypothesis row(s) cover this range)")
            else:
                print(f"  {loc}: UNKNOWN; no hypothesis row covers this yet")
            print(f"    before: {c['before']}")
            print(f"    after:  {c['after']}")
        print()
    unknown = [
        (e["chunk"], c) for e in changed for c in e["clusters"] if not c["annotations"]
    ]
    if unknown:
        print(
            f"{len(unknown)} unknown cluster(s): the next RE target. "
            "Confirmed findings become new rows in "
            f"{args.fields}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
