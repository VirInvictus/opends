#!/usr/bin/env python3
"""Propose EXE symbol names for the ovr-map catalogue: review input, never commits.

The EXE-side counterpart of `tools/gpl-disasm/scripts/import-dso-symbols.py`.
Where that script matches GPL opcode handlers by name equivalence, this one
works the resident-image surface of `DSUN.EXE`: the mechanical passes that
exist today, each with an explicit evidence basis, feeding the naming
campaign in roadmap 5.6.1. It never writes to `tools/ovr-map/syms/`;
everything it emits is a proposal for hand review (the curation rule in
the catalogue headers).

What it can and cannot do:

  CAN (mechanical, honest):
    --census   The resident-target census (docs/dsun-exe-survey.md 3.3,
               regenerated per game): every far-call decoded in every live
               overlay segment, targets resolved to resident file offsets,
               counted. This is the naming campaign's worklist: ~340
               distinct targets, hottest first. Targets that are overlay
               entry stubs are broken out separately: those edges are
               overlay-to-overlay calls routed through the resident stubs,
               which `ovr-map --callgraph` (resident-scan only) cannot see.
    --strings  Source-file string anchors: printable resident-image strings
               ending in `.c` (the `gpldisk.c` class of breadcrumbs,
               survey 3.4), listed beside the DSO table's name-prefix
               families so a human can join subsystem to source module.
    --anchors  Render a hand-curated anchors TOML ([[anchor]] rows: name,
               segment, offset, evidence, confidence) into syms-catalogue
               format, skipping rows already catalogued. The formatter
               half of the pipeline: the campaign produces the evidence,
               this produces the review-ready rows.

  CANNOT (and must not pretend to):
    Match a DSO name to an EXE function automatically. The DSO offsets are
    v1.0-client-relative and do not transfer (docs/dso-symbols.md); the
    transfer method is shape-matching verified by a second observable,
    which is hand work. Any name this script attached to an address would
    be fabrication.

Inputs default to the canonical dev-side paths (.games/<game>/DSUN.EXE,
.dso-online/tools/symbols.txt, tools/ovr-map/syms/<game>.toml) and every
one is overridable. Stdlib-only; needs `ndisasm` (nasm) for --census,
matching ovr-map --disasm's requirement.

Exit codes: 0 ok, 2 bad input paths, 1 tool error.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
REPO = TOOL_DIR.parent.parent

# ndisasm renders a far call as `call word 0xSEG:word 0xOFF` (some builds
# without the `word ` prefixes); both forms parse. The bytes column for
# the 5-byte instruction is 9A + offset:2 + seg:2 = 10 hex digits.
FAR_CALL = re.compile(
    r"^\s*[0-9A-Fa-f]+\s+9[Aa][0-9A-Fa-f]{8}\s+"
    r"call (?:word )?0x([0-9A-Fa-f]+):(?:word )?0x([0-9A-Fa-f]+)"
)

CONFIDENCE = ("verified", "probable", "provisional")


def load_ovr_map():
    """Import the ovr-map tool (hyphenated filename) for its parser/loader."""
    spec = importlib.util.spec_from_file_location("ovr_map", TOOL_DIR / "ovr-map.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {TOOL_DIR / 'ovr-map.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_symbols(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Parse .dso-online/tools/symbols.txt: (functions, globals), name -> offset.

    Same format as the gpl-disasm importer's parser: lines of
    `NAME HEX KIND` with KIND in {f, l}. Offsets are DSO-v1.0-client
    relative and do NOT transfer; only the names cross.
    """
    funcs: dict[str, int] = {}
    globs: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        name, addr_hex, kind = parts
        try:
            addr = int(addr_hex, 16)
        except ValueError:
            continue
        if kind == "f":
            funcs[name] = addr
        elif kind == "l":
            globs[name] = addr
    return funcs, globs


def disasm_segment(data: bytes, seg: dict, ndisasm: str = "ndisasm") -> str:
    """Decode one overlay segment the way ovr-map --disasm does."""
    body = data[seg["file_start"] : seg["file_end"]]
    proc = subprocess.run(
        [ndisasm, "-b", "16", "-o", "0", "-"], input=body, capture_output=True
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ndisasm failed on segment {seg['index']}: "
            f"{proc.stderr.decode(errors='replace').strip()}"
        )
    return proc.stdout.decode(errors="replace")


def resident_census(
    data: bytes, report: dict, stub_offsets: set[int]
) -> dict[str, dict[int, int]]:
    """Count far-call targets of every live overlay segment.

    Returns {"resident": {file_offset: count}, "overlay_target": count,
    "segment_values": {seg: count}, "loose_sites": count}. A decoded
    `call seg:off` resolves to the file offset `header_size + seg*16 + off`
    (the same arithmetic as ovr-map's relocation parser and resident
    callgraph, image-relative paragraphs). Two target filters are kept
    apart on purpose:

      exact  the resolved file offset lands inside the resident image
             (primary; this is the naming worklist)
      loose  only the segment base is required in range (survey 3.3's
             filter, kept for count continuity)

    Caveat carried in the output: overlay payload far-call segment words
    predate the overlay manager's relocation pass (per-descriptor
    relocation tables, location still open, survey 4/10), so a target is
    a candidate until corroborated (prologue bytes, a catalogue name, or
    a second observable).
    """
    mz = report["mz"]
    header = mz["header_size"]
    image_end = mz["image_end"]
    resident: collections.Counter[int] = collections.Counter()
    seg_values: collections.Counter[int] = collections.Counter()
    overlay_target = 0
    stub_hits: collections.Counter[int] = collections.Counter()
    loose_sites = 0
    for seg in report["segments"]:
        if seg["empty"]:
            continue
        for line in disasm_segment(data, seg).splitlines():
            m = FAR_CALL.match(line)
            if not m:
                continue
            call_seg, call_off = int(m.group(1), 16), int(m.group(2), 16)
            target = header + call_seg * 16 + call_off
            if call_seg * 16 + header < image_end:
                loose_sites += 1
                seg_values[call_seg] += 1
            if not (header <= target < image_end):
                continue
            resident[target] += 1
            if target in stub_offsets:
                stub_hits[target] += 1
            for other in report["segments"]:
                if not other["empty"] and (
                    other["file_start"] <= target < other["file_end"]
                ):
                    overlay_target += 1
                    break
    return {
        "resident": dict(resident),
        "overlay_target_count": overlay_target,
        "stub_hits": dict(stub_hits),
        "segment_values": dict(seg_values),
        "loose_sites": loose_sites,
    }


def source_file_strings(
    data: bytes, image_end: int, min_len: int = 5
) -> list[tuple[int, str]]:
    """Printable resident-image strings ending in `.c` (the survey 3.4 class).

    Borland keeps C source names in assertion/error strings ("Bad iCtrl
    in gpldisk.c"); each is a module-level anchor joining the binary to a
    source file the DSO symbol prefixes also name.
    """
    out: list[tuple[int, str]] = []
    run: list[bytes] = []
    start = 0
    for i, b in enumerate(data[:image_end]):
        if 0x20 <= b < 0x7F:
            if not run:
                start = i
            run.append(bytes([b]))
            continue
        if len(run) >= min_len and b"".join(run).endswith(b".c"):
            out.append((start, b"".join(run).decode("ascii")))
        run = []
    if len(run) >= min_len and b"".join(run).endswith(b".c"):
        out.append((start, b"".join(run).decode("ascii")))
    return out


def load_catalogued(syms_path: Path) -> dict[tuple, str]:
    """Already-catalogued (segment, offset) -> name, via ovr-map's loader."""
    if not syms_path.is_file():
        return {}
    ovr_map = load_ovr_map()
    lookup = ovr_map.load_syms(syms_path)
    return {key: row["name"] for key, row in lookup.items()}


def render_census(
    census: dict,
    named: dict[tuple, str],
    data: bytes,
    header: int,
    top: int,
    as_json: bool = False,
) -> str:
    rows = sorted(census["resident"].items(), key=lambda kv: -kv[1])
    prologue = b"\x55\x8b\xec"
    confirmed = sum(1 for off in census["resident"] if data[off : off + 3] == prologue)
    if as_json:
        return json.dumps(
            {
                "header_size": f"0x{header:x}",
                "sites_exact": sum(census["resident"].values()),
                "targets_exact": len(rows),
                "prologue_confirmed": confirmed,
                "distinct_segment_values": len(census["segment_values"]),
                "sites_loose": census["loose_sites"],
                "targets": [
                    {
                        "file_offset": f"0x{off:x}",
                        "calls": n,
                        "name": named.get(("resident", off)),
                        "prologue": data[off : off + 3] == prologue,
                    }
                    for off, n in rows
                ],
                "overlay_to_overlay_stub_hits": {
                    f"0x{off:x}": n for off, n in sorted(census["stub_hits"].items())
                },
            },
            indent=2,
        )
    lines = [
        "# Resident-target census (naming worklist, machine-generated)",
        "#",
        f"# exact sites {sum(census['resident'].values())}, exact targets {len(rows)} "
        f"(55 8B EC prologue at target: {confirmed})",
        f"# distinct called segment values {len(census['segment_values'])} "
        f"(loose filter, {census['loose_sites']} sites: survey 3.3's keying)",
        "#",
        "# Caveat: overlay far-call segment words predate the overlay manager's",
        "# relocation pass (survey 4/10); a target is a candidate until",
        "# corroborated. * marks the 55 8B EC entry prologue; @ marks a",
        "# catalogue name. Sorted by calls.",
        "#",
        "| file offset | calls | evidence |",
        "|---|---|---|",
    ]
    for off, n in rows[:top]:
        name = named.get(("resident", off))
        marks = ("*" if data[off : off + 3] == prologue else "") + (
            f"@{name}" if name else ""
        )
        lines.append(f"| `0x{off:x}` | {n} | {marks} |")
    if len(rows) > top:
        lines.append(f"| ... | | {len(rows) - top} more targets |")
    stubs = census["stub_hits"]
    lines += [
        "",
        f"Overlay-to-overlay calls (resident-side stub hits): "
        f"{len(stubs)} stubs, {sum(stubs.values())} edges "
        "(`ovr-map --callgraph` scans the resident image only and cannot "
        "see these; resolve a stub hit through the map's entries to get "
        "the callee segment:offset).",
    ]
    return "\n".join(lines)


def render_anchors(path: Path, named: dict[tuple, str]) -> str:
    """Render curated [[anchor]] rows into syms-catalogue TOML proposals."""
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    anchors = data.get("anchor", [])
    if not anchors:
        raise ValueError(f"{path}: no [[anchor]] rows found")
    out = [
        f"# Symbol-catalogue proposals rendered from {path}.",
        "# Generated by tools/ovr-map/scripts/propose-exe-symbols.py --anchors.",
        "# Review against the curation rule in syms/<game>.toml; do NOT",
        "# paste blindly. Rows already in the catalogue are skipped.",
        "",
    ]
    kept = skipped = 0
    for i, row in enumerate(anchors):
        where = f"{path}:anchor[{i}]"
        name = row.get("name")
        seg = row.get("segment")
        off = row.get("offset")
        conf = row.get("confidence", "provisional")
        evidence = row.get("evidence", "")
        if not name or seg is None or off is None:
            raise ValueError(f"{where}: name, segment and offset are required")
        if conf not in CONFIDENCE:
            raise ValueError(f"{where}: confidence {conf!r} not one of {CONFIDENCE}")
        key = (seg, off)
        if key in named:
            skipped += 1
            continue
        kept += 1
        out.append("[[function]]")
        out.append(f'name = "{name}"')
        out.append(f'segment = "{seg}"' if isinstance(seg, str) else f"segment = {seg}")
        out.append(f"offset = 0x{off:x}")
        out.append(f'confidence = "{conf}"')
        out.append(f'evidence = "{evidence}"')
        if row.get("dso_source"):
            out.append(f'dso_source = "DSO::{row["dso_source"]}"')
        if row.get("notes"):
            out.append('notes = """')
            out.append(row["notes"])
            out.append('"""')
        out.append("")
    out.insert(
        4,
        f"# {kept} new row{'s' if kept != 1 else ''}, "
        f"{skipped} already catalogued and skipped.",
    )
    return "\n".join(out)


def default_symbols_path() -> Path:
    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        candidate = ancestor / ".dso-online" / "tools" / "symbols.txt"
        if candidate.is_file():
            return candidate
    return Path(".dso-online/tools/symbols.txt")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--game", choices=("ds1", "ds2"), default="ds2")
    ap.add_argument("--exe", type=Path, help="override .games/<game>/DSUN.EXE")
    ap.add_argument("--source", type=Path, default=default_symbols_path())
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--census", action="store_true", help="resident-target census")
    mode.add_argument(
        "--strings", action="store_true", help="source-file string anchors"
    )
    mode.add_argument(
        "--anchors", metavar="FILE", type=Path, help="render curated anchors TOML"
    )
    ap.add_argument("--top", type=int, default=40, help="census rows to show")
    ap.add_argument("--json", action="store_true", help="machine JSON (--census)")
    args = ap.parse_args(argv)

    exe = args.exe or REPO / ".games" / args.game / "DSUN.EXE"
    if not exe.is_file():
        print(f"error: no EXE at {exe}", file=sys.stderr)
        return 2

    ovr_map = load_ovr_map()
    report = ovr_map.build(exe)
    data = exe.read_bytes()
    named = load_catalogued(TOOL_DIR / "syms" / f"{args.game}.toml")
    # A stub's resident-image position is its descriptor-table offset;
    # entry["file_offset"] is the code address inside the overlay segment
    # and can never be a far-call target.
    stub_offsets = {e["stub_offset"] for s in report["segments"] for e in s["entries"]}

    if args.census:
        try:
            census = resident_census(data, report, stub_offsets)
        except FileNotFoundError:
            print(
                "error: ndisasm not found; install nasm for --census", file=sys.stderr
            )
            return 1
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(
            render_census(
                census, named, data, report["mz"]["header_size"], args.top, args.json
            )
        )
        return 0

    if args.strings:
        funcs, _globs = (
            parse_symbols(args.source) if args.source.is_file() else ({}, {})
        )
        # Subsystem prefixes from survey 7 / dso-symbols.md, counted exactly
        # (case-sensitive leading match), rather than an open-ended leading
        # run which fragments on Watcom's runtime prefixes.
        subsystem = (
            "Save",
            "Load",
            "Gpl",
            "Gff",
            "VGA",
            "GUI",
            "Gui",
            "Combat",
            "Region",
            "Map",
            "Dialog",
            "Mouse",
            "Sound",
            "Resource",
            "Decode",
        )
        prefixes = collections.Counter(
            p for n in funcs for p in subsystem if n.startswith(p)
        )
        print("# Source-file string anchors (survey 3.4 class), with the")
        print("# DSO table's dominant name prefixes beside them for the")
        print("# human subsystem-to-module join. Neither side alone is a match.")
        print()
        print("## Resident `.c` strings")
        for off, s in source_file_strings(data, report["mz"]["image_end"]):
            print(f"- `0x{off:x}`  {s!r}")
        print()
        print("## DSO function-name prefixes (subsystem list)")
        for prefix, n in prefixes.most_common():
            print(f"- {prefix}: {n}")
        if not funcs:
            print(f"\n(DSO table not found at {args.source}; prefix column is empty.)")
        return 0

    if args.anchors is not None:
        if not args.anchors.is_file():
            print(f"error: no anchors file at {args.anchors}", file=sys.stderr)
            return 2
        try:
            print(render_anchors(args.anchors, named))
        except (ValueError, tomllib.TOMLDecodeError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        return 0

    # Default: summary of everything the modes would produce.
    print(f"ovr-map symbol proposal summary ({args.game}: {exe.name})")
    print(f"  catalogued names:        {len(named)}")
    print(f"  overlay entry stubs:     {len(stub_offsets)}")
    if args.source.is_file():
        funcs, globs = parse_symbols(args.source)
        print(f"  DSO functions/globals:   {len(funcs)} / {len(globs)}")
    else:
        print(f"  DSO table:               NOT FOUND at {args.source}")
    print()
    print("Modes: --census (naming worklist), --strings (module anchors),")
    print("       --anchors FILE (render curated rows into catalogue format).")
    print("This script proposes; it never writes tools/ovr-map/syms/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
