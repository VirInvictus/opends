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
import tomllib
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

# Curated EXE symbol catalogue confidence levels (syms/<game>.toml).
SYMS_CONFIDENCE = ("verified", "probable", "provisional")


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


def load_syms(
    path: Path, report: dict[str, Any] | None = None
) -> dict[tuple[Any, int], dict[str, Any]]:
    """Load a curated EXE symbol catalogue (tools/ovr-map/syms/<game>.toml).

    Returns a lookup keyed by (segment, offset): ("resident", file_offset)
    for resident-image functions, (seg_index, segment-local cs: offset) for
    overlay functions. Schema and curation rule live in the catalogue
    files' header comments; this loader enforces the same rules.

    When `report` is given, overlay rows are bound-checked against the
    parsed map so a typo'd segment index or an offset past the segment end
    fails loudly here instead of silently never matching.
    """
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise OvrError(f"symbol catalogue {path} is not valid TOML: {e}") from e

    lookup: dict[tuple[Any, int], dict[str, Any]] = {}
    for i, row in enumerate(data.get("function", [])):
        where = f"{path}:function[{i}]"
        name = row.get("name")
        if not isinstance(name, str) or not name:
            raise OvrError(f"{where}: name must be a non-empty string")
        seg = row.get("segment")
        off = row.get("offset")
        if seg != "resident" and not isinstance(seg, int):
            raise OvrError(
                f'{where}: segment must be "resident" or an integer overlay index'
            )
        if not isinstance(off, int) or off < 0:
            raise OvrError(f"{where}: offset must be a non-negative integer")
        conf = row.get("confidence", "provisional")
        if conf not in SYMS_CONFIDENCE:
            raise OvrError(f"{where}: confidence {conf!r} not one of {SYMS_CONFIDENCE}")
        if report is not None and isinstance(seg, int):
            segs = [s for s in report["segments"] if s["index"] == seg]
            if not segs:
                raise OvrError(f"{where}: no overlay segment {seg} in this binary")
            if not segs[0]["empty"] and off >= segs[0]["size"]:
                raise OvrError(
                    f"{where}: offset 0x{off:x} is past the end of segment {seg} "
                    f"(size 0x{segs[0]['size']:x})"
                )
        key = (seg, off)
        if key in lookup:
            raise OvrError(f"{where}: duplicate catalogue address {key}")
        lookup[key] = row
    return lookup


def verify(
    report: dict[str, Any],
    offset: int,
    syms: dict[tuple[Any, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Answer 'what is at this file offset'. The query the patch workflow needs."""
    out: dict[str, Any] = {"file_offset": offset}
    if offset < report["mz"]["image_end"]:
        out["region"] = "resident"
        out["note"] = "inside the MZ image; not overlaid code"
        sym = syms.get(("resident", offset)) if syms else None
        if sym:
            out.update(
                {
                    "name": sym["name"],
                    "confidence": sym.get("confidence", "provisional"),
                    "evidence": sym.get("evidence", ""),
                }
            )
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
            sym = syms.get((seg["index"], local)) if syms else None
            if sym:
                out.update(
                    {
                        "name": sym["name"],
                        "confidence": sym.get("confidence", "provisional"),
                        "evidence": sym.get("evidence", ""),
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


def callgraph(
    data: bytes,
    report: dict[str, Any],
    syms: dict[tuple[Any, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
            sym = syms.get((seg_index, entry["entry_offset"])) if syms else None
            edges.append(
                {
                    "call_site": i,
                    "target_stub": entry["stub_offset"],
                    "callee_segment": seg_index,
                    "callee_entry_offset": entry["entry_offset"],
                    "callee_file_offset": entry["file_offset"],
                    "callee_name": sym["name"] if sym else None,
                }
            )
        i += 1

    total_stubs = report["summary"]["entry_points"]
    with_caller = len({e["target_stub"] for e in edges})
    indirect = data.count(b"\xff\x1e", 0, image_end)
    named = len({e["callee_name"] for e in edges if e["callee_name"]})
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
            "named_callees_hit": named,
            "note": (
                "Most stubs are reached indirectly (FF 1E) or by table dispatch. "
                "A stub absent from these edges is NOT evidence it is unreachable; "
                "this graph is deliberately incomplete."
            ),
        },
    }


def disasm(
    data: bytes,
    report: dict[str, Any],
    index: int,
    limit: int | None,
    syms: dict[tuple[Any, int], dict[str, Any]] | None = None,
) -> str:
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
            sym = syms.get((index, local)) if syms else None
            out.append("")
            out.append(
                f"; ---- entry[{labels[local]}]  cs:0x{local:04x}"
                f"  file 0x{seg['file_start'] + local:x}"
                + (f"  <{sym['name']}>" if sym else "")
            )
        out.append(line)
        count += 1
        if limit is not None and count >= limit:
            out.append(f"; ... truncated at {limit} lines (--limit)")
            break
    return "\n".join(out)


GHIDRA_TEMPLATE = """\
// Generated by ovr-map %(version)s. Do not edit by hand; regenerate instead:
//   python3 tools/ovr-map/ovr-map.py <DSUN.EXE> --ghidra -o OvrMap.java
//
// Creates one Ghidra overlay memory block per Borland overlay segment of
// DSUN.EXE, at its correct base, and labels every INT 3Fh entry stub as a
// confirmed function entry.
//
// Why this is needed: Ghidra's MZ loader maps only the resident image (as
// CODE_n blocks). Everything past the FBOV header, which is where the
// overlaid code lives, is not mapped at all. Without this the overlay area
// is simply absent from the program.
//
// Java rather than Python on purpose: Ghidra 12 dropped Jython, and Python
// scripts now require a PyGhidra install (jpype). Java scripts run with no
// extra setup.
//
//@category OpenDS
import java.io.ByteArrayInputStream;
import java.io.File;
import java.nio.file.Files;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.SegmentedAddressSpace;
import ghidra.program.model.mem.MemoryBlock;

public class %(classname)s extends GhidraScript {

    // segIndex:basePara:size:fileStart   (basePara assigned by ovr-map so the
    // whole overlay area fits inside the 16-bit segment range)
    private static final String SEGMENTS = %(segments)s;

    // segIndex:entryOffset:fileOffset:stubOffset
    private static final String ENTRIES = %(entries)s;

    private static final String SOURCE_EXE = "%(source)s";
    private static final int HEADER_SIZE = 0x%(header_size)x;
    // Synthetic base paragraph for the first overlay block. Overlay segments
    // have no fixed load address in the file (the manager pages them in), so
    // any distinct base works as long as segment-local cs: offsets line up,
    // which they do because each block starts at offset 0 of its segment.
    @Override
    public void run() throws Exception {
        // toAddr(String) does not parse seg:off here; go through the segmented
        // space directly, which is what the MZ loader gives us.
        SegmentedAddressSpace space =
            (SegmentedAddressSpace) currentProgram.getAddressFactory().getDefaultAddressSpace();

        byte[] image = loadImage();
        if (image == null) {
            println("ovr-map: no image; aborting");
            return;
        }

        // An overlay block lives in its OWN address space, so addresses inside it
        // must be derived from the block's start, not from the default space.
        // Labelling via space.getAddress(...) silently lands in ram: instead.
        java.util.Map<Integer, Address> startOf = new java.util.HashMap<>();
        int blocks = 0;
        int labels = 0;
        for (String line : SEGMENTS.split(";")) {
            if (line.isEmpty()) {
                continue;
            }
            String[] f = line.split(":");
            int index = Integer.parseInt(f[0]);
            int para = Integer.parseInt(f[1]);
            int size = Integer.parseInt(f[2]);
            int fileStart = Integer.parseInt(f[3]);
            if (size == 0) {
                continue;
            }
            Address at = space.getAddress(para, 0);
            String name = String.format("ovr_%%02d", index);
            byte[] body = new byte[size];
            System.arraycopy(image, fileStart, body, 0, size);
            MemoryBlock blk = currentProgram.getMemory().createInitializedBlock(
                name, at, new ByteArrayInputStream(body), size, monitor, true);
            blk.setComment(String.format(
                "OpenDS overlay segment %%d: file 0x%%x..0x%%x (ovr-map)",
                index, fileStart, fileStart + size));
            startOf.put(index, blk.getStart());
            blocks++;
        }

        for (String line : ENTRIES.split(";")) {
            if (line.isEmpty()) {
                continue;
            }
            String[] f = line.split(":");
            int index = Integer.parseInt(f[0]);
            int entryOffset = Integer.parseInt(f[1]);
            int fileOffset = Integer.parseInt(f[2]);
            int stubOffset = Integer.parseInt(f[3]);

            Address segStart = startOf.get(index);
            if (segStart == null) {
                continue;
            }
            Address entry = segStart.add(entryOffset);
            String label = String.format("ovr%%02d_%%04x", index, entryOffset);
            disassemble(entry);
            createLabel(entry, label, true);
            setEOLComment(entry, String.format(
                "overlay entry: file 0x%%x, stub 0x%%x (ovr-map)", fileOffset, stubOffset));
            labels++;

            // The stub itself lives in the resident image, which the MZ loader
            // did map. Label it too so a caller's far call reads as a name.
            int linear = stubOffset - HEADER_SIZE;
            if (linear > 0) {
                try {
                    Address stub = space.getAddress(linear >> 4, linear & 0xf);
                    createLabel(stub, "stub_" + label, true);
                } catch (Exception e) {
                    // A stub outside any mapped block is not fatal; skip it.
                }
            }
        }

        println(String.format(
            "ovr-map: created %%d overlay blocks, labelled %%d entry points", blocks, labels));
    }

    private byte[] loadImage() throws Exception {
        File f = new File(SOURCE_EXE);
        if (!f.isFile()) {
            f = askFile("Select the DSUN.EXE this map was generated from", "Open");
        }
        if (f == null || !f.isFile()) {
            return null;
        }
        return Files.readAllBytes(f.toPath());
    }
}
"""


def ghidra_script(report: dict[str, Any], classname: str = "OvrMap") -> str:
    """Emit a self-contained Ghidra script that replays the segment map.

    The data is baked in as delimited strings rather than generated statements:
    935 label calls inline would risk Java's 64 KB per-method bytecode limit,
    while a string constant lives in the constant pool.
    """
    # Overlay segments have no fixed load address (the manager pages them in),
    # so assign synthetic bases. They must be consecutive, not a fixed stride:
    # a 0x1000-paragraph stride overflows the 16-bit segment range by segment 57.
    # Start clear of the resident image, then advance by each segment's own size.
    para = _align(report["mz"]["image_end"], 16) // 16 + 0x100
    segs = []
    entries = []
    for seg in report["segments"]:
        base = para
        if not seg["empty"]:
            para += (seg["size"] + 15) // 16
            if para > 0xFFFF:
                raise OvrError(
                    f"overlay layout does not fit the 16-bit segment range "
                    f"(segment {seg['index']} would end at paragraph 0x{para:x})"
                )
        segs.append(f"{seg['index']}:{base}:{seg['size']}:{seg['file_start']}")
        for entry in seg["entries"]:
            entries.append(
                f"{seg['index']}:{entry['entry_offset']}:"
                f"{entry['file_offset']}:{entry['stub_offset']}"
            )

    def java_str(items: list[str]) -> str:
        return '"' + ";".join(items) + '"'

    return GHIDRA_TEMPLATE % {
        "version": report["version"],
        "classname": classname,
        "segments": java_str(segs),
        "entries": java_str(entries),
        # Absolute: Ghidra runs the script from its own working directory, so a
        # relative path here would not resolve. askFile() is the fallback if the
        # binary has since moved.
        "source": str(Path(report["file"]).resolve()),
        "header_size": report["mz"]["header_size"],
    }


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
        syms_path = HERE / "syms" / f"{name}.toml"
        if syms_path.is_file():
            try:
                named = load_syms(syms_path, report=rep)
                check(bool(named), f"{syms_path.name} parsed to zero rows")
            except OvrError as e:
                check(False, str(e))
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
        "--syms",
        metavar="FILE",
        type=Path,
        help="curated symbol catalogue (tools/ovr-map/syms/<game>.toml); "
        "names render in --disasm, --callgraph and --verify",
    )
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="assert structural invariants against .games/ds1 and .games/ds2, skipping if absent",
    )
    ap.add_argument(
        "--ghidra",
        action="store_true",
        help="emit a Ghidra script that recreates the overlay blocks and labels entries",
    )
    ap.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        type=Path,
        help="write --ghidra output to FILE (class name follows the stem)",
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

    syms: dict[tuple[Any, int], dict[str, Any]] | None = None
    if args.syms is not None:
        if not args.syms.is_file():
            print(f"ovr-map: no such symbol catalogue: {args.syms}", file=sys.stderr)
            return 2
        try:
            # Load against the parsed map so catalogue typos fail loudly.
            syms = load_syms(args.syms, report=report)
        except OvrError as e:
            print(f"ovr-map: {e}", file=sys.stderr)
            return 1

    if args.verify is not None:
        try:
            offset = int(args.verify, 0)
        except ValueError:
            print(f"ovr-map: bad offset: {args.verify}", file=sys.stderr)
            return 2
        print(json.dumps(verify(report, offset, syms), indent=2))
        return 0

    if args.disasm is not None:
        try:
            print(disasm(args.exe.read_bytes(), report, args.disasm, args.limit, syms))
        except OvrError as e:
            print(f"ovr-map: {e}", file=sys.stderr)
            return 1
        return 0

    if args.ghidra:
        classname = args.output.stem if args.output else "OvrMap"
        if not classname.isidentifier():
            print(
                f"ovr-map: {classname!r} is not a valid Java class name",
                file=sys.stderr,
            )
            return 2
        script = ghidra_script(report, classname)
        if args.output:
            args.output.write_text(script)
            print(f"wrote {args.output} ({len(script)} bytes, class {classname})")
        else:
            print(script)
        return 0

    if args.callgraph:
        graph = callgraph(args.exe.read_bytes(), report, syms)
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
            if syms:
                print(f"named callees hit: {cov['named_callees_hit']}")
            print(f"\n{cov['note']}")
        return 0

    print(json.dumps(report, indent=2) if args.json else human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
