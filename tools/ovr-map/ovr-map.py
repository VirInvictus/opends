#!/usr/bin/env python3
"""ovr-map: map the Borland overlay structure of a Dark Sun DSUN.EXE.

Turns the engine binary from a blob you hex-search into a segmented,
addressable artifact: which overlay segment covers a file offset, where each
segment really starts, and which addresses are confirmed function entries.

Stdlib-only. Python 3.11+.

Format reference: docs/dsun-exe-re.md 1 and 3.5. Both games are Borland/TLINK
(VROOM) overlaid 16-bit real-mode MZ programs, NOT DOS/4GW.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text().strip()

FBOV_SIG = b"FBOV"
DESC_SIG = b"\xcd\x3f\x00\x00"
DESC_SIZE = 32
STUB_SIZE = 5
# Records are padded out to a 16-byte boundary; verified against DS1 desc[0]
# (32 + 5*5 = 57 -> 0x40) and desc[4] (32 + 5*3 = 47 -> 0x30).
DESC_ALIGN = 16
# Bounds a runaway parse without rejecting any real record (max seen: 47).
MAX_STUBS = 4096


class OvrError(Exception):
    """Raised when the binary does not look like an overlaid MZ image."""


def _align(n: int, to: int = DESC_ALIGN) -> int:
    return (n + to - 1) & ~(to - 1)


def parse_mz(data: bytes) -> dict[str, int]:
    """MZ header fields we need. The image is the program, not a stub."""
    if data[:2] != b"MZ":
        raise OvrError("not an MZ executable")
    e_cblp, e_cp, e_crlc = struct.unpack_from("<HHH", data, 2)
    e_cparhdr = struct.unpack_from("<H", data, 8)[0]
    e_lfarlc = struct.unpack_from("<H", data, 0x18)[0]
    # e_cblp is bytes used on the last page; 0 means the last page is full.
    image_end = (e_cp - 1) * 512 + e_cblp if e_cblp else e_cp * 512
    return {
        "header_size": e_cparhdr * 16,
        "image_end": image_end,
        "relocation_count": e_crlc,
        "relocation_table": e_lfarlc,
    }


def parse_fbov(data: bytes, image_end: int) -> dict[str, int]:
    """The FBOV header sits immediately after the MZ image."""
    if data[image_end : image_end + 4] != FBOV_SIG:
        raise OvrError(
            f"no FBOV signature at 0x{image_end:x} "
            f"(found {data[image_end : image_end + 4]!r}); not a Borland-overlaid image"
        )
    ovrsize, exeinfo, segnum = struct.unpack_from("<III", data, image_end + 4)
    return {
        "ovrsize": ovrsize,
        "exeinfo": exeinfo,
        "segnum": segnum,
        "overlay_base": image_end + 16,
    }


def find_table(data: bytes, exeinfo: int, image_end: int) -> int:
    """Locate the descriptor table.

    `exeinfo` does NOT point at the table. It points at a block of 8-byte
    records followed by the overlay's own filename ("darkcd.exe" in DS1); the
    descriptor table begins after that. Rather than parse a block whose record
    count is not stated anywhere, anchor on exeinfo and take the first position
    that carries the descriptor signature. This is safe because parse_table
    validates the whole chain afterwards: a wrong start derails immediately.
    """
    i = data.find(DESC_SIG, exeinfo, image_end)
    if i < 0:
        raise OvrError(f"no descriptor signature found after exeinfo 0x{exeinfo:x}")
    return i


def parse_table(
    data: bytes, start: int, image_end: int, overlay_base: int
) -> list[dict[str, Any]]:
    """Walk the descriptor chain.

    Each record is 32 bytes:
        +0x00  CD 3F 00 00      INT 3Fh signature
        +0x04  dword            payload offset, relative to the overlay area
        +0x08  word             segment size
        +0x0a  word             relocation count
        +0x0c  dword            entry-stub count

    followed by exactly `nstubs` 5-byte stubs (CD 3F <entry_offset:2> <ovr:1>),
    then padding to a 16-byte boundary.

    The explicit stub count is what makes this deterministic. A stub whose
    entry_offset is 0 is byte-identical to a descriptor prefix (DS1 has one at
    0x46fd5), so any heuristic that sniffs for the next descriptor miscounts.
    """
    segments: list[dict[str, Any]] = []
    pos = start
    while pos + DESC_SIZE <= image_end and data[pos : pos + 4] == DESC_SIG:
        payload, size, nrelocs, nstubs = struct.unpack_from("<IHHI", data, pos + 4)
        if nstubs > MAX_STUBS:
            break
        if overlay_base + payload + size > len(data):
            break

        entries = []
        for k in range(nstubs):
            s = pos + DESC_SIZE + STUB_SIZE * k
            if s + STUB_SIZE > image_end or data[s : s + 2] != b"\xcd\x3f":
                raise OvrError(
                    f"malformed stub {k} for descriptor at 0x{pos:x}: "
                    f"expected INT 3Fh at 0x{s:x}"
                )
            entry_offset, ovr = struct.unpack_from("<HB", data, s + 2)
            entries.append(
                {
                    "stub_offset": s,
                    "entry_offset": entry_offset,
                    "file_offset": overlay_base + payload + entry_offset,
                    "overlay": ovr,
                }
            )

        segments.append(
            {
                "index": len(segments),
                "descriptor_offset": pos,
                "payload_offset": payload,
                "size": size,
                "relocation_count": nrelocs,
                "file_start": overlay_base + payload,
                "file_end": overlay_base + payload + size,
                "empty": size == 0,
                "entries": entries,
            }
        )
        pos = _align(pos + DESC_SIZE + STUB_SIZE * nstubs)

    if not segments:
        raise OvrError(f"no descriptors parsed at 0x{start:x}")
    return segments


def build(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    mz = parse_mz(data)
    fbov = parse_fbov(data, mz["image_end"])
    table_start = find_table(data, fbov["exeinfo"], mz["image_end"])
    segments = parse_table(data, table_start, mz["image_end"], fbov["overlay_base"])

    live = [s for s in segments if not s["empty"]]
    covered = sum(s["size"] for s in segments)
    return {
        "tool": "ovr-map",
        "version": VERSION,
        "file": str(path),
        "file_size": len(data),
        "mz": mz,
        "fbov": fbov,
        "table_start": table_start,
        "summary": {
            "records": len(segments),
            "segments": len(live),
            "empty_records": len(segments) - len(live),
            "entry_points": sum(len(s["entries"]) for s in segments),
            "overlaid_bytes": covered,
            "overlay_area_bytes": fbov["ovrsize"],
            "coverage_pct": round(100.0 * covered / fbov["ovrsize"], 2)
            if fbov["ovrsize"]
            else 0.0,
        },
        "segments": segments,
    }


def verify(report: dict[str, Any], offset: int) -> dict[str, Any]:
    """Answer 'what is at this file offset'. The query the patch workflow needs."""
    out: dict[str, Any] = {"file_offset": offset}
    if offset < report["mz"]["image_end"]:
        out["region"] = "resident"
        out["note"] = "inside the MZ image; not overlaid code"
        return out
    if offset < report["fbov"]["overlay_base"]:
        out["region"] = "fbov_header"
        return out

    for seg in report["segments"]:
        if seg["empty"]:
            continue
        if seg["file_start"] <= offset < seg["file_end"]:
            local = offset - seg["file_start"]
            prior = [e for e in seg["entries"] if e["entry_offset"] <= local]
            nearest = max(prior, key=lambda e: e["entry_offset"]) if prior else None
            out.update(
                {
                    "region": "overlay_segment",
                    "segment": seg["index"],
                    "segment_offset": local,
                    "segment_file_range": [seg["file_start"], seg["file_end"]],
                    "nearest_entry": nearest,
                    "distance_from_entry": (local - nearest["entry_offset"])
                    if nearest
                    else None,
                    "is_entry_point": bool(
                        nearest and nearest["entry_offset"] == local
                    ),
                }
            )
            return out

    out["region"] = "overlay_padding"
    out["note"] = (
        "inside the overlay area but outside every segment (inter-segment padding)"
    )
    return out


def parse_relocations(data: bytes, mz: dict[str, int]) -> set[int]:
    """File offsets that the loader fixes up.

    Used to filter far-call candidates: a real `9A off:2 seg:2` has its segment
    word relocated at load time, so that word's location appears here. Without
    this filter a raw 0x9A scan is mostly false positives.
    """
    out: set[int] = set()
    pos = mz["relocation_table"]
    for _ in range(mz["relocation_count"]):
        if pos + 4 > len(data):
            break
        off, seg = struct.unpack_from("<HH", data, pos)
        out.add(mz["header_size"] + seg * 16 + off)
        pos += 4
    return out


def callgraph(data: bytes, report: dict[str, Any]) -> dict[str, Any]:
    """Far-call edges whose target is an overlay entry stub.

    An overlaid routine is never called at its own address (docs/dsun-exe-re.md
    §3.5). The caller far-calls the 5-byte INT 3Fh stub in the resident image,
    and the overlay manager pages the segment in. So the edge points at the
    stub, and that is what this resolves.

    Coverage is reported, not implied: most stubs are reached indirectly (via
    `FF 1E` indirect far calls or table dispatch) and will show no direct
    caller. A stub with no edge here is not evidence that it is unreachable.
    """
    mz = report["mz"]
    header_size = mz["header_size"]
    image_end = mz["image_end"]
    relocated = parse_relocations(data, mz)

    stub_by_linear: dict[int, tuple[int, dict[str, Any]]] = {}
    for seg in report["segments"]:
        for entry in seg["entries"]:
            stub_by_linear[entry["stub_offset"] - header_size] = (seg["index"], entry)

    edges = []
    i = 0
    while i < image_end - 5:
        if data[i] != 0x9A:
            i += 1
            continue
        # The relocated word is the segment part, at +3.
        if (i + 3) not in relocated:
            i += 1
            continue
        off, seg_word = struct.unpack_from("<HH", data, i + 1)
        hit = stub_by_linear.get(seg_word * 16 + off)
        if hit is not None:
            seg_index, entry = hit
            edges.append(
                {
                    "call_site": i,
                    "target_stub": entry["stub_offset"],
                    "callee_segment": seg_index,
                    "callee_entry_offset": entry["entry_offset"],
                    "callee_file_offset": entry["file_offset"],
                }
            )
        i += 1

    total_stubs = report["summary"]["entry_points"]
    with_caller = len({e["target_stub"] for e in edges})
    indirect = data.count(b"\xff\x1e", 0, image_end)
    return {
        "edges": edges,
        "coverage": {
            "edges_found": len(edges),
            "stubs_total": total_stubs,
            "stubs_with_direct_caller": with_caller,
            "stubs_with_direct_caller_pct": (
                round(100.0 * with_caller / total_stubs, 1) if total_stubs else 0.0
            ),
            "indirect_far_call_sites": indirect,
            "note": (
                "Most stubs are reached indirectly (FF 1E) or by table dispatch. "
                "A stub absent from these edges is NOT evidence it is unreachable; "
                "this graph is deliberately incomplete."
            ),
        },
    }


def disasm(data: bytes, report: dict[str, Any], index: int, limit: int | None) -> str:
    """Disassemble one segment at its correct base, in 16-bit mode.

    Shells out to ndisasm (nasm), matching docs/dsun-exe-re.md's own
    recommendation and the shell-out precedent in verify-install and repro.
    ⚠ 16-bit is not optional: decoding this binary as 32-bit does not error,
    it produces convincing garbage.
    """
    segs = [s for s in report["segments"] if s["index"] == index]
    if not segs:
        raise OvrError(f"no segment with index {index}")
    seg = segs[0]
    if seg["empty"]:
        raise OvrError(f"segment {index} is an empty overlay slot (size 0)")

    body = data[seg["file_start"] : seg["file_end"]]
    try:
        proc = subprocess.run(
            ["ndisasm", "-b", "16", "-o", "0", "-"],
            input=body,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OvrError("ndisasm not found; install nasm for --disasm") from exc
    if proc.returncode != 0:
        raise OvrError(
            f"ndisasm failed: {proc.stderr.decode(errors='replace').strip()}"
        )

    labels = {e["entry_offset"]: n for n, e in enumerate(seg["entries"])}
    header = [
        f"; segment {index}  file 0x{seg['file_start']:x}..0x{seg['file_end']:x}"
        f"  size 0x{seg['size']:x}  entries {len(seg['entries'])}",
        "; offsets below are segment-local (cs:), matching the entry stubs",
        "",
    ]
    out = list(header)
    count = 0
    for line in proc.stdout.decode(errors="replace").splitlines():
        local = None
        head = line.split(None, 1)[0] if line.strip() else ""
        try:
            local = int(head, 16)
        except ValueError:
            local = None
        if local is not None and local in labels:
            out.append("")
            out.append(
                f"; ---- entry[{labels[local]}]  cs:0x{local:04x}"
                f"  file 0x{seg['file_start'] + local:x}"
            )
        out.append(line)
        count += 1
        if limit is not None and count >= limit:
            out.append(f"; ... truncated at {limit} lines (--limit)")
            break
    return "\n".join(out)


def selftest(paths: list[Path]) -> int:
    """Assert the structural invariants against the shipped binaries.

    Corpus-style: skips cleanly when .games/ is absent, matching the Rust
    corpus tests. Lives in the tool rather than a separate suite because the
    Python tools here are single-file and the repo has no Python test harness.
    """
    checked = 0
    failures: list[str] = []
    for path in paths:
        if not path.is_file():
            print(f"SKIP {path} (not present)")
            continue
        checked += 1
        data = path.read_bytes()
        rep = build(path)
        segs = rep["segments"]
        live = [s for s in segs if not s["empty"]]
        name = path.parent.name

        def check(cond: bool, msg: str) -> None:
            if not cond:
                failures.append(f"{name}: {msg}")

        check(
            data[rep["mz"]["image_end"] : rep["mz"]["image_end"] + 4] == FBOV_SIG,
            "FBOV signature not at the MZ image end",
        )
        check(bool(live), "no non-empty segments parsed")
        check(
            all(s["file_end"] <= len(data) for s in segs),
            "a descriptor's range runs past EOF",
        )
        check(
            all(s["file_start"] >= rep["fbov"]["overlay_base"] for s in segs),
            "a segment starts before the overlay area",
        )
        check(
            all(e["entry_offset"] < s["size"] for s in live for e in s["entries"]),
            "an entry stub points outside its own segment",
        )
        check(
            all(rep["mz"]["image_end"] <= s["file_start"] for s in live),
            "a segment overlaps the resident image",
        )
        ranges = sorted((s["file_start"], s["file_end"]) for s in live)
        check(
            all(a[1] <= b[0] for a, b in zip(ranges, ranges[1:])),
            "two segments overlap",
        )
        cov = rep["summary"]["coverage_pct"]
        check(cov > 92.0, f"overlay coverage {cov}% is below the 92% floor")
        print(
            f"OK   {path}  segments={len(live)} entries={rep['summary']['entry_points']} "
            f"coverage={cov}%"
        )

    if not checked:
        print("no binaries present; nothing verified")
        return 0
    for f in failures:
        print(f"FAIL {f}", file=sys.stderr)
    return 1 if failures else 0


def human(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"{report['file']}  ({report['file_size']} bytes)",
        (
            f"  MZ image ends   0x{report['mz']['image_end']:x}"
            f"   header 0x{report['mz']['header_size']:x}"
            f"   relocations {report['mz']['relocation_count']}"
        ),
        f"  overlay base    0x{report['fbov']['overlay_base']:x}   ovrsize {report['fbov']['ovrsize']}",
        f"  descriptor tbl  0x{report['table_start']:x}",
        "",
        f"  segments        {s['segments']}  ({s['empty_records']} empty records skipped)",
        f"  entry points    {s['entry_points']}",
        f"  overlaid        {s['overlaid_bytes']} bytes ({s['overlaid_bytes'] / 1024:.0f} KB)",
        f"  area covered    {s['coverage_pct']}%",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ovr-map",
        description="Map the Borland overlay structure of a Dark Sun DSUN.EXE.",
    )
    ap.add_argument("exe", type=Path, nargs="?", help="path to DSUN.EXE")
    ap.add_argument("--json", action="store_true", help="emit the full map as JSON")
    ap.add_argument(
        "--verify",
        metavar="OFFSET",
        help="report what lives at a file offset (accepts 0x hex)",
    )
    ap.add_argument(
        "--disasm",
        metavar="SEG",
        type=int,
        help="disassemble segment SEG at its correct base, 16-bit, entries labelled",
    )
    ap.add_argument(
        "--limit", metavar="N", type=int, help="cap --disasm output at N lines"
    )
    ap.add_argument(
        "--callgraph",
        action="store_true",
        help="far-call edges targeting entry stubs (deliberately incomplete; reports coverage)",
    )
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="assert structural invariants against .games/ds1 and .games/ds2, skipping if absent",
    )
    ap.add_argument("--version", action="version", version=f"ovr-map {VERSION}")
    args = ap.parse_args(argv)

    if args.selftest:
        repo = HERE.parents[1]
        return selftest([repo / ".games" / g / "DSUN.EXE" for g in ("ds1", "ds2")])

    if args.exe is None:
        ap.error("exe is required unless --selftest is given")

    if not args.exe.is_file():
        print(f"ovr-map: no such file: {args.exe}", file=sys.stderr)
        return 2

    try:
        report = build(args.exe)
    except OvrError as e:
        print(f"ovr-map: {e}", file=sys.stderr)
        return 1

    if args.verify is not None:
        try:
            offset = int(args.verify, 0)
        except ValueError:
            print(f"ovr-map: bad offset: {args.verify}", file=sys.stderr)
            return 2
        print(json.dumps(verify(report, offset), indent=2))
        return 0

    if args.disasm is not None:
        try:
            print(disasm(args.exe.read_bytes(), report, args.disasm, args.limit))
        except OvrError as e:
            print(f"ovr-map: {e}", file=sys.stderr)
            return 1
        return 0

    if args.callgraph:
        graph = callgraph(args.exe.read_bytes(), report)
        if args.json:
            print(json.dumps(graph, indent=2))
        else:
            cov = graph["coverage"]
            print(f"far-call edges targeting entry stubs: {cov['edges_found']}")
            print(
                f"stubs with a direct caller: {cov['stubs_with_direct_caller']}"
                f" / {cov['stubs_total']} ({cov['stubs_with_direct_caller_pct']}%)"
            )
            print(f"indirect far-call sites (FF 1E): {cov['indirect_far_call_sites']}")
            print(f"\n{cov['note']}")
        return 0

    print(json.dumps(report, indent=2) if args.json else human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
