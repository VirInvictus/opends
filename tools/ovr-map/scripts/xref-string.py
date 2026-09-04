#!/usr/bin/env python3
"""String cross-references for DSUN.EXE: the naming campaign's anchor tool.

Given a resident-image string (or any data offset), find the code that
references it. The reference mechanism on these Borland/Watcom binaries
is NOT the naive adjacent (off, seg) pair: strings live in DGROUP, DS
holds DGROUP's paragraph at runtime, and code references a string with
a bare 16-bit immediate (usually `push imm16`, sometimes a mov) of the
offset relative to DGROUP.

DGROUP is discovered the honest way: the MZ entry point's first
instruction is `mov dx, <DGROUP>` followed by `mov ds, dx` (verified
on both games: DS1 0x4356, DS2 0x47e0). A reference must also survive
the reachability test: 0 <= off < 0x10000 against this DGROUP.

Each hit is reported with its containing region (resident / overlay
segment), the nearest Watcom prologue (`55 8B EC`) scanning back, and,
for overlay hits, the nearest confirmed entry stub. That evidence pair
(string semantics + containing confirmed function) is what a curated
`syms/<game>.toml` row needs; nothing is written automatically.

Stdlib-only; needs ndisasm for the excerpt.
"""

from __future__ import annotations

import argparse
import importlib.util
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent

# opcodes whose immediate operand can carry a DS-relative offset
REF_OPCODES = (0x68, 0xB8, 0xB9, 0xBA, 0xBB, 0xBE, 0xBF)


def load_ovr_map():
    spec = importlib.util.spec_from_file_location("ovr_map", TOOL_DIR / "ovr-map.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {TOOL_DIR / 'ovr-map.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_dgroup(data: bytes, mz: dict) -> int:
    """Read DGROUP from the entry point: `mov dx, imm16` first instruction."""
    e_ip, e_cs = struct.unpack_from("<HH", data, 0x14)
    entry = mz["header_size"] + e_cs * 16 + e_ip
    if data[entry] != 0xBA:  # mov dx, imm16
        raise SystemExit(
            f"entry point at 0x{entry:x} does not start with `mov dx, imm` "
            "(expected the Watcom startup prologue); pass --dgroup explicitly"
        )
    return struct.unpack_from("<H", data, entry + 1)[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("strings", nargs="+", help="string literal (searched) or 0x offset")
    ap.add_argument("--exe", type=Path, default=Path(".games/ds1/DSUN.EXE"))
    ap.add_argument(
        "--dgroup", type=lambda x: int(x, 0), help="override the discovered DGROUP"
    )
    args = ap.parse_args(argv)

    if not args.exe.is_file():
        print(f"error: no EXE at {args.exe}", file=sys.stderr)
        return 2

    ovr_map = load_ovr_map()
    report = ovr_map.build(args.exe)
    data = args.exe.read_bytes()
    mz = report["mz"]
    dgroup = args.dgroup if args.dgroup is not None else discover_dgroup(data, mz)
    print(f"# {args.exe}  DGROUP=0x{dgroup:x}  header=0x{mz['header_size']:x}")

    for needle in args.strings:
        if needle.startswith("0x"):
            foff = int(needle, 0)
            text = data[foff : foff + 40]
            text = text[: text.index(b"\x00")] if b"\x00" in text else text
        else:
            foff = data.find(needle.encode())
            if foff < 0:
                print(f"\n== {needle!r}: string not found in binary")
                continue
            text = needle.encode()
        off = foff - mz["header_size"] - dgroup * 16
        print(f"\n== {text!r} at file 0x{foff:x} (DGROUP offset 0x{off:x})")
        if not (0 <= off < 0x10000):
            print("   offset out of 16-bit reach of this DGROUP; wrong segment class?")
            continue
        pat = struct.pack("<H", off)
        hits = []
        start = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            start = i + 1
            if i >= 1 and data[i - 1] in REF_OPCODES:
                hits.append(i - 1)
        if not hits:
            print("   no push/mov-immediate references found")
            continue
        for r in hits:
            seg = next(
                (
                    s
                    for s in report["segments"]
                    if not s["empty"] and s["file_start"] <= r < s["file_end"]
                ),
                None,
            )
            region = f"ovr{seg['index']:02d}" if seg else "resident"
            prologue = data.rfind(b"\x55\x8b\xec", max(0, r - 0x600), r)
            line = f"   ref at 0x{r:x} in {region}"
            if prologue >= 0:
                line += f", containing function prologue at 0x{prologue:x}"
                if seg is not None and seg["file_start"] <= prologue < seg["file_end"]:
                    local = prologue - seg["file_start"]
                    entry = next(
                        (e for e in seg["entries"] if e["file_offset"] == prologue),
                        None,
                    )
                    line += (
                        " (= confirmed entry stub cs:0x" + f"{local:04x})"
                        if entry
                        else f" (seg-local 0x{local:x})"
                    )
            print(line)
            dis_start = r - 10
            proc = subprocess.run(
                ["ndisasm", "-b", "16", "-o", hex(dis_start), "-"],
                input=data[dis_start : r + 12],
                capture_output=True,
            )
            for out_line in proc.stdout.decode(errors="replace").splitlines()[:6]:
                print("     " + out_line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
