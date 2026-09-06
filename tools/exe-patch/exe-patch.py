#!/usr/bin/env python3
"""exe-patch: author, verify, and apply in-place byte patches to DSUN.EXE.

The Phase 5.7 authoring surface. It addresses patches the way the RE docs
write them (`ovr:seg+off`, a symbol-catalogue name, or a raw file offset),
enforces the mandatory `bytes_old` fingerprint, and refuses anything the
Borland overlay format cannot survive: a length change, a segment-boundary
straddle, or a site in the inter-segment padding.

In-place only: every overlay descriptor stores its payload offset as an
absolute file position, so one inserted byte anywhere before the last
segment shifts every following payload and the game loads garbage as code
(spec.md 3.2). Every edit is a same-length byte replacement or the script
is rejected before anything is written.

Address resolution reads the segment map from `ovr-map --json` (the
documented inter-tool contract), so the FBOV descriptor walk keeps exactly
one implementation. Byte assembly (`--asm`) shells out to nasm in 16-bit
mode, the same toolchain as ovr-map's ndisasm disassembly; pwntools 4.15
cannot assemble this target (it rejects the i386/16 combination), see
docs/re-tooling.md.

Stdlib-only. Python 3.11+.
Format reference: docs/dsun-exe-re.md 1 and 3.5; docs/binary-patching.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text().strip()
OVR_MAP = HERE.parent / "ovr-map" / "ovr-map.py"
REPO = HERE.parents[1]
SYMS_DIR = OVR_MAP.parent / "syms"
HASH_MANIFESTS = REPO / "docs" / "source-hashes"

NUM = r"(?:0x[0-9A-Fa-f]+|\d+)"
AT_OVR = re.compile(rf"ovr:(\d+)\+({NUM})(?:\s*\+\s*({NUM}))?\s*$", re.IGNORECASE)
AT_ABS = re.compile(rf"({NUM})(?:\s*\+\s*({NUM}))?\s*$")
AT_NAME = re.compile(rf"([A-Za-z_]\w*)(?:\s*\+\s*({NUM}))?\s*$")


class PatchError(Exception):
    """Raised for script, address, or validation failures."""


def parse_hex(field: str, where: str) -> bytes:
    cleaned = re.sub(r"\s+", "", field)
    if not cleaned or len(cleaned) % 2 or not re.fullmatch(r"[0-9A-Fa-f]+", cleaned):
        raise PatchError(f"{where}: {field!r} is not a hex byte string")
    return bytes.fromhex(cleaned)


def parse_num(text: str, where: str) -> int:
    try:
        return int(text, 0)
    except ValueError as exc:
        raise PatchError(f"{where}: bad number {text!r}") from exc


def load_map(exe: Path) -> dict[str, Any]:
    """The segment map, via the documented ovr-map --json contract."""
    if not OVR_MAP.is_file():
        raise PatchError(f"sibling tool not found: {OVR_MAP}")
    proc = subprocess.run(
        [sys.executable, str(OVR_MAP), str(exe), "--json"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise PatchError(
            f"ovr-map failed on {exe}: {proc.stderr.decode(errors='replace').strip()}"
        )
    return json.loads(proc.stdout)


def load_syms(path: Path) -> dict[str, list[dict[str, Any]]]:
    """A syms catalogue keyed by name; duplicates kept for the ambiguity check."""
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise PatchError(f"symbol catalogue {path} is not valid TOML: {e}") from e
    by_name: dict[str, list[dict[str, Any]]] = {}
    for i, row in enumerate(data.get("function", [])):
        name = row.get("name")
        seg = row.get("segment")
        off = row.get("offset")
        where = f"{path}:function[{i}]"
        if not isinstance(name, str) or not name:
            raise PatchError(f"{where}: name must be a non-empty string")
        if seg != "resident" and not isinstance(seg, int):
            raise PatchError(
                f'{where}: segment must be "resident" or an integer overlay index'
            )
        if not isinstance(off, int) or off < 0:
            raise PatchError(f"{where}: offset must be a non-negative integer")
        by_name.setdefault(name, []).append(row)
    return by_name


def resolve_at(
    at: str, report: dict[str, Any], syms: dict[str, list[dict[str, Any]]] | None
) -> tuple[int, str]:
    """Resolve an `at` expression to a file offset.

    Three base forms: `ovr:SEG+OFF` (overlay segment index + segment-local
    offset, the docs' own notation), a bare file offset, or a catalogue name
    (an ovr-map syms row: the one address class guaranteed to be a confirmed
    function entry). Every form takes an optional trailing ` + N`.
    """
    val = at.strip()

    m = AT_OVR.match(val)
    if m:
        seg_index = int(m.group(1))
        off = parse_num(m.group(2), f"at {at!r}")
        add = parse_num(m.group(3), f"at {at!r}") if m.group(3) else 0
        segs = [s for s in report["segments"] if s["index"] == seg_index]
        if not segs:
            raise PatchError(
                f"at {at!r}: no overlay segment {seg_index} in this binary"
            )
        seg = segs[0]
        if seg["empty"]:
            raise PatchError(f"at {at!r}: segment {seg_index} is an empty slot")
        if off + add > seg["size"]:
            raise PatchError(
                f"at {at!r}: offset 0x{off + add:x} is past the end of segment "
                f"{seg_index} (size 0x{seg['size']:x})"
            )
        return seg["file_start"] + off + add, (f"segment {seg_index} + 0x{off + add:x}")

    m = AT_NAME.match(val)
    if m and not re.fullmatch(NUM, m.group(1)):
        name = m.group(1)
        add = parse_num(m.group(2), f"at {at!r}") if m.group(2) else 0
        if syms is None:
            raise PatchError(
                f"at {at!r}: symbolic address needs --syms (or a `game` field "
                f"in the script to auto-select the catalogue)"
            )
        rows = syms.get(name)
        if not rows:
            raise PatchError(f"at {at!r}: no catalogue row named {name!r}")
        if len(rows) > 1:
            spots = ", ".join(
                f"segment {r['segment']} offset 0x{r['offset']:x}"
                if r["segment"] != "resident"
                else f"resident 0x{r['offset']:x}"
                for r in rows
            )
            raise PatchError(f"at {at!r}: ambiguous catalogue name {name!r}: {spots}")
        row = rows[0]
        if row["segment"] == "resident":
            return row["offset"] + add, f"{name} (resident) + 0x{add:x}"
        segs = [s for s in report["segments"] if s["index"] == row["segment"]]
        if not segs:
            raise PatchError(
                f"at {at!r}: catalogue row {name!r} names overlay segment "
                f"{row['segment']}, which this binary does not have"
            )
        seg = segs[0]
        if not seg["empty"] and row["offset"] + add > seg["size"]:
            raise PatchError(
                f"at {at!r}: {name} + 0x{add:x} is past the end of segment "
                f"{row['segment']} (size 0x{seg['size']:x})"
            )
        return seg["file_start"] + row["offset"] + add, (
            f"{name} (segment {row['segment']} + 0x{row['offset']:x}) + 0x{add:x}"
        )

    m = AT_ABS.match(val)
    if m:
        off = parse_num(m.group(1), f"at {at!r}")
        add = parse_num(m.group(2), f"at {at!r}") if m.group(2) else 0
        return off + add, f"file offset 0x{off + add:x}"

    raise PatchError(f"at {at!r}: not ovr:SEG+OFF, a number, or a catalogue name")


def classify(report: dict[str, Any], off: int, n: int) -> dict[str, Any]:
    """Region classification plus the structural failures --verify exists for."""
    info: dict[str, Any] = {"file_offset": off, "length": n}
    image_end = report["mz"]["image_end"]
    base = report["fbov"]["overlay_base"]

    if off + n > report["file_size"]:
        info["region"] = "past_eof"
        info["error"] = (
            f"edit runs past end of file (0x{off + n:x} > 0x{report['file_size']:x})"
        )
        return info
    if off < image_end:
        info["region"] = "resident"
        return info
    if off < base:
        info["region"] = "fbov_header"
        info["error"] = (
            f"site 0x{off:x} is inside the FBOV overlay header "
            f"(0x{image_end:x}..0x{base:x}); not patchable payload"
        )
        return info
    for seg in report["segments"]:
        if seg["empty"]:
            continue
        if seg["file_start"] <= off < seg["file_end"]:
            local = off - seg["file_start"]
            info["region"] = "overlay_segment"
            info["segment"] = seg["index"]
            info["segment_offset"] = local
            if off + n > seg["file_end"]:
                info["error"] = (
                    f"edit straddles the end of segment {seg['index']} "
                    f"(payload ends at 0x{seg['file_end']:x})"
                )
            prior = [e for e in seg["entries"] if e["entry_offset"] <= local]
            if prior:
                nearest = max(prior, key=lambda e: e["entry_offset"])
                info["nearest_entry"] = {
                    "entry_offset": nearest["entry_offset"],
                    "file_offset": nearest["file_offset"],
                }
            return info
    info["region"] = "overlay_padding"
    info["error"] = (
        f"site 0x{off:x} is in the inter-segment padding (outside every "
        f"segment payload); a byte written here is never executed and may "
        f"be descriptor or relocation structure"
    )
    return info


def check_game_hash(game: str, data: bytes) -> None:
    """Refuse a script that names a game the target is not."""
    manifest = HASH_MANIFESTS / f"{game}-gog-1.10.toml"
    if not manifest.is_file():
        raise PatchError(
            f"game = {game!r}: canonical hash manifest {manifest} is missing; "
            f"the target cannot be confirmed"
        )
    with manifest.open("rb") as fh:
        hashes = tomllib.load(fh)
    want = hashes.get("files", {}).get("DSUN.EXE")
    if not want:
        raise PatchError(f"game = {game!r}: manifest lists no DSUN.EXE hash")
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise PatchError(
            f"game = {game!r}: target DSUN.EXE hash {got[:12]}... does not match "
            f"the canonical GOG 1.10 manifest {want[:12]}...; refusing a wrong install"
        )


def validate(
    script: Path,
    data: bytes,
    report: dict[str, Any],
    syms: dict[str, list[dict[str, Any]]] | None,
) -> dict[str, Any]:
    """Every gate, before anything is written: schema, game hash, resolution,
    region, fingerprint, overlap. All-or-nothing by construction."""
    try:
        with script.open("rb") as fh:
            top = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise PatchError(f"{script} is not valid TOML: {e}") from e

    game = top.get("game")
    if game is not None:
        if game not in ("ds1", "ds2"):
            raise PatchError(f'game = {game!r}: expected "ds1" or "ds2"')
        check_game_hash(game, data)

    edits = top.get("edit")
    if not edits or not isinstance(edits, list):
        raise PatchError(f"{script}: no [[edit]] entries")

    out: dict[str, Any] = {
        "script": str(script),
        "ok": True,
        "edits": [],
        "errors": [],
    }
    ranges: list[tuple[int, int, int]] = []
    for i, raw in enumerate(edits):
        where = f"edit {i + 1}"
        item: dict[str, Any] = {"index": i + 1, "at": raw.get("at")}
        # Schema violations are hard errors; site conditions (drift, straddle,
        # padding) are per-edit findings so one bad site does not hide others.
        if not isinstance(raw.get("at"), str):
            raise PatchError(f"{where}: `at` must be a string address")
        if "bytes_old" not in raw:
            raise PatchError(
                f"{where}: bytes_old is mandatory (the fingerprint that proves "
                f"the site is what the fix was authored against)"
            )
        if "bytes_new" not in raw:
            raise PatchError(f"{where}: bytes_new is mandatory")
        errors: list[str] = []

        try:
            old = parse_hex(raw["bytes_old"], f"{where} bytes_old")
            new = parse_hex(raw["bytes_new"], f"{where} bytes_new")
        except PatchError as e:
            errors.append(str(e))
            item["errors"] = errors
            out["edits"].append(item)
            out["errors"].extend(errors)
            out["ok"] = False
            continue

        if len(new) != len(old):
            errors.append(
                f"{where}: bytes_old is {len(old)} byte(s) but bytes_new is "
                f"{len(new)}; patches are in-place only and may not change the "
                f"file length (one inserted byte shifts every later overlay "
                f"payload and the game loads garbage as code)"
            )
        else:
            item["old"] = old.hex()
            item["new"] = new.hex()

        try:
            file_off, described = resolve_at(raw["at"], report, syms)
            item["resolved"] = described
            cls = classify(report, file_off, len(old))
            item.update(cls)
            if "error" in cls:
                errors.append(f"{where}: {cls['error']}")
            elif data[file_off : file_off + len(old)] != old:
                actual = data[file_off : file_off + len(old)]
                errors.append(
                    f"{where}: fingerprint drift at 0x{file_off:x}: expected "
                    f"{old.hex(' ')} but found {actual.hex(' ')}"
                )
            else:
                ranges.append((file_off, file_off + len(old), i))
        except PatchError as e:
            errors.append(str(e))

        item["errors"] = errors
        out["edits"].append(item)
        out["errors"].extend(errors)

    ranges.sort()
    for (a0, a1, i), (b0, _b1, j) in zip(ranges, ranges[1:]):
        if b0 < a1:
            msg = (
                f"edit {i + 1} and edit {j + 1} overlap "
                f"(0x{a0:x}..0x{a1:x} vs 0x{b0:x}..)"
            )
            out["errors"].append(msg)
            out["edits"][i].setdefault("errors", []).append(msg)
            out["edits"][j].setdefault("errors", []).append(msg)

    if out["errors"]:
        out["ok"] = False
    return out


def apply_edits(data: bytes, validated: dict[str, Any]) -> bytes:
    """Same-length replacements onto a copy; length is re-asserted."""
    buf = bytearray(data)
    for item in validated["edits"]:
        if item.get("errors"):
            continue
        off = item["file_offset"]
        new = bytes.fromhex(item["new"])
        buf[off : off + len(new)] = new
    if len(buf) != len(data):
        raise PatchError("internal: output length changed; refusing to write")
    return bytes(buf)


def assemble(insn: str) -> bytes:
    """16-bit x86 assembly via nasm, the toolchain ndisasm already anchors.

    The previously documented fallback (`pwn asm` at arch='i386', bits=16)
    does not work on pwntools 4.15: pwnlib rejects the i386/16 combination.
    Confirmed 2026-09-06; docs/re-tooling.md carries the correction.
    """
    nasm = shutil.which("nasm")
    if nasm is None:
        raise PatchError("nasm not found; install nasm for --asm")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "insn.asm"
        obj = Path(td) / "insn.bin"
        src.write_text(f"bits 16\n{insn}\n")
        proc = subprocess.run(
            [nasm, "-f", "bin", "-o", str(obj), str(src)],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise PatchError(
                f"nasm failed: {proc.stderr.decode(errors='replace').strip()}"
            )
        return obj.read_bytes()


def build_fixture() -> bytes:
    """A minimal Borland-overlaid MZ image ovr-map parses: resident image with
    a descriptor table and stubs, FBOV header, two payloads, one real gap."""
    buf = bytearray(0x3B0)
    buf[0:2] = b"MZ"
    struct.pack_into("<HHH", buf, 2, 0x200, 1, 0)  # image_end = 0x200
    struct.pack_into("<H", buf, 8, 2)  # header_size = 0x20
    struct.pack_into("<H", buf, 0x18, 0x1C)  # e_lfarlc
    buf[0x20:0x40] = b"\x90" * 0x20

    def desc(payload: int, size: int, entries: list[int]) -> bytes:
        # 32-byte descriptor: sig + (payload, size, nrelocs, nstubs) + 16
        # reserved bytes the manager uses at runtime, then the 5-byte stubs.
        b = b"\xcd\x3f\x00\x00" + struct.pack("<IHHI", payload, size, 0, len(entries))
        b += b"\x00" * 16
        for eo in entries:
            b += b"\xcd\x3f" + struct.pack("<HB", eo, 0)
        return b

    d0 = desc(0x0000, 0x0100, [0, 0x10])  # 42 bytes at 0x48
    buf[0x48 : 0x48 + len(d0)] = d0
    d1 = desc(0x0120, 0x0080, [0])  # 37 bytes at 0x80
    buf[0x80 : 0x80 + len(d1)] = d1

    buf[0x200:0x204] = b"FBOV"
    struct.pack_into("<III", buf, 0x204, 0x1A0, 0x40, 0)
    buf[0x210:0x310] = b"\x90" * 0x100  # segment 0 payload
    # 0x310..0x330 stays zero: the inter-segment gap the padding test aims at
    buf[0x330:0x3B0] = b"\xc3" * 0x80  # segment 1 payload
    return bytes(buf)


FIXTURE_SYMS = """\
[[function]]
name = "fixture_resident_fn"
segment = "resident"
offset = 0x30
confidence = "verified"
evidence = "exe-patch selftest fixture"

[[function]]
name = "fixture_overlay_fn"
segment = 0
offset = 0x40
confidence = "verified"
evidence = "exe-patch selftest fixture"
"""


def selftest() -> int:
    """Round-trip proof plus every refusal, on a synthetic fixture first
    (so the invariants hold with no .games/ present), then on the real
    binaries when they exist."""
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as td:
        dirp = Path(td)
        exe = dirp / "FIXTURE.EXE"
        data = build_fixture()
        exe.write_bytes(data)
        syms = load_syms(_write_script(dirp / "syms.toml", FIXTURE_SYMS))
        report = load_map(exe)
        check(report["summary"]["segments"] == 2, "fixture: ovr-map parsed 2 segments")
        check(
            report["summary"]["entry_points"] == 3, "fixture: ovr-map parsed 3 entries"
        )
        check(
            report["segments"][0]["file_start"] == 0x210
            and report["segments"][1]["file_end"] == 0x3B0,
            "fixture: segment payload bounds as designed",
        )

        def run(text: str) -> dict[str, Any]:
            return validate(_write_script(dirp / "s.toml", text), data, report, syms)

        # The round-trip proof: a no-op validates and applies byte-identically.
        noop = run('[[edit]]\nat = "ovr:0+0x40"\nbytes_old = "90"\nbytes_new = "90"\n')
        check(noop["ok"], f"fixture: no-op should validate: {noop['errors']}")
        check(
            apply_edits(data, noop) == data, "fixture: no-op applies byte-identically"
        )

        # A real edit and its inverse restore the original bytes exactly.
        edit = run('[[edit]]\nat = "ovr:0+0x40"\nbytes_old = "90"\nbytes_new = "c3"\n')
        check(edit["ok"], f"fixture: edit should validate: {edit['errors']}")
        patched = apply_edits(data, edit)
        check(patched != data and patched[0x250] == 0xC3, "fixture: edit lands")
        inverse = validate(
            _write_script(
                dirp / "inv.toml",
                '[[edit]]\nat = "ovr:0+0x40"\nbytes_old = "c3"\nbytes_new = "90"\n',
            ),
            patched,
            report,
            syms,
        )
        check(
            inverse["ok"] and apply_edits(patched, inverse) == data,
            f"fixture: inverse applies byte-identically: {inverse['errors']}",
        )

        # Bare resident offset and symbolic addressing resolve as documented.
        res = run('[[edit]]\nat = "0x30"\nbytes_old = "90"\nbytes_new = "c3"\n')
        check(
            res["ok"] and res["edits"][0]["region"] == "resident",
            "fixture: bare resident offset should resolve",
        )
        sym = validate(
            _write_script(
                dirp / "sym.toml",
                '[[edit]]\nat = "fixture_overlay_fn"\n'
                'bytes_old = "90"\nbytes_new = "c3"\n',
            ),
            data,
            report,
            syms,
        )
        check(
            sym["ok"] and sym["edits"][0]["file_offset"] == 0x250,
            f"fixture: overlay symbol should resolve to 0x250: {sym['errors']}",
        )
        sym2 = validate(
            _write_script(
                dirp / "sym2.toml",
                '[[edit]]\nat = "fixture_resident_fn + 4"\n'
                'bytes_old = "90"\nbytes_new = "c3"\n',
            ),
            data,
            report,
            syms,
        )
        check(
            sym2["ok"] and sym2["edits"][0]["file_offset"] == 0x34,
            f"fixture: resident symbol + N should resolve to 0x34: {sym2['errors']}",
        )

        # The refusals: padding, straddle, FBOV header, drift, length change,
        # missing fingerprint, overlap, wrong install.
        pad = run('[[edit]]\nat = "ovr:0+0x100"\nbytes_old = "00"\nbytes_new = "90"\n')
        check(
            not pad["ok"] and "padding" in pad["errors"][0],
            f"fixture: padding site must be rejected: {pad['errors']}",
        )
        straddle = run(
            '[[edit]]\nat = "ovr:0+0xff"\nbytes_old = "90 90"\nbytes_new = "c3 c3"\n'
        )
        check(
            not straddle["ok"] and any("straddle" in e for e in straddle["errors"]),
            f"fixture: straddle must be rejected: {straddle['errors']}",
        )
        hdr = run('[[edit]]\nat = "0x201"\nbytes_old = "46"\nbytes_new = "90"\n')
        check(
            not hdr["ok"] and "FBOV" in hdr["errors"][0],
            f"fixture: FBOV header site must be rejected: {hdr['errors']}",
        )
        drift = run('[[edit]]\nat = "ovr:0+0x40"\nbytes_old = "00"\nbytes_new = "c3"\n')
        check(
            not drift["ok"] and any("drift" in e for e in drift["errors"]),
            f"fixture: fingerprint drift must be rejected: {drift['errors']}",
        )
        short = run(
            '[[edit]]\nat = "ovr:0+0x40"\nbytes_old = "90 90"\nbytes_new = "c3"\n'
        )
        check(
            not short["ok"] and any("in-place only" in e for e in short["errors"]),
            f"fixture: length change must be rejected: {short['errors']}",
        )
        try:
            validate(
                _write_script(
                    dirp / "nofp.toml",
                    '[[edit]]\nat = "ovr:0+0x40"\nbytes_new = "c3"\n',
                ),
                data,
                report,
                syms,
            )
            check(False, "fixture: missing bytes_old must raise")
        except PatchError as e:
            check(
                "bytes_old is mandatory" in str(e),
                f"fixture: missing bytes_old message: {e}",
            )
        overlap = run(
            '[[edit]]\nat = "ovr:0+0x40"\nbytes_old = "90"\nbytes_new = "c3"\n\n'
            '[[edit]]\nat = "ovr:0+0x40 + 0"\nbytes_old = "90"\nbytes_new = "c3"\n'
        )
        check(
            not overlap["ok"] and any("overlap" in e for e in overlap["errors"]),
            f"fixture: overlapping edits must be rejected: {overlap['errors']}",
        )
        try:
            validate(
                _write_script(
                    dirp / "wrong.toml",
                    'game = "ds2"\n\n[[edit]]\nat = "ovr:0+0x40"\n'
                    'bytes_old = "90"\nbytes_new = "c3"\n',
                ),
                data,
                report,
                syms,
            )
            check(False, "fixture: wrong-install hash must raise")
        except PatchError as e:
            check("does not match" in str(e), f"fixture: wrong install: {e}")

        # The assembler, when nasm exists: a one-instruction round-trip.
        if shutil.which("nasm") and shutil.which("ndisasm"):
            out = assemble("mov ax, 0x4b75")
            check(out == b"\xb8\x75\x4b", f"asm: unexpected bytes {out.hex()}")
            proc = subprocess.run(
                ["ndisasm", "-b", "16", "-"],
                input=out,
                capture_output=True,
                check=False,
            )
            check(
                b"mov ax,0x4b75" in proc.stdout,
                f"asm: ndisasm round-trip failed: {proc.stdout!r}",
            )
        else:
            print("SKIP assembler round-trip (nasm/ndisasm not present)")

    # The same no-op and padding proofs against the real binaries.
    with tempfile.TemporaryDirectory() as td:
        dirp = Path(td)
        for exe in [REPO / ".games" / g / "DSUN.EXE" for g in ("ds1", "ds2")]:
            if not exe.is_file():
                print(f"SKIP {exe} (not present)")
                continue
            report = load_map(exe)
            data = exe.read_bytes()
            seg0 = next(s for s in report["segments"] if not s["empty"])
            first = data[seg0["file_start"] : seg0["file_start"] + 1].hex()
            noop = validate(
                _write_script(
                    dirp / "noop.toml",
                    f'[[edit]]\nat = "ovr:{seg0["index"]}+0"\n'
                    f'bytes_old = "{first}"\nbytes_new = "{first}"\n',
                ),
                data,
                report,
                None,
            )
            check(noop["ok"], f"{exe.parent.name}: real no-op should validate")

            gap = None
            live = sorted(
                (s for s in report["segments"] if not s["empty"]),
                key=lambda s: s["file_start"],
            )
            for a, b in zip(live, live[1:]):
                if b["file_start"] - a["file_end"] >= 1:
                    gap = a["file_end"]
                    break
            proofs = "noop"
            if gap is not None:
                pad = validate(
                    _write_script(
                        dirp / "pad.toml",
                        "[[edit]]\n"
                        f'at = "0x{gap:x}"\n'
                        f'bytes_old = "{data[gap : gap + 1].hex()}"\n'
                        'bytes_new = "90"\n',
                    ),
                    data,
                    report,
                    None,
                )
                check(
                    not pad["ok"] and "padding" in pad["errors"][0],
                    f"{exe.parent.name}: real gap 0x{gap:x} should be padding",
                )
                proofs += "+padding"
            print(
                f"OK   {exe}  segments={report['summary']['segments']} proofs={proofs}"
            )

    if failures:
        for f in failures:
            print(f"FAIL {f}", file=sys.stderr)
        return 1
    print("exe-patch selftest: all invariants hold")
    return 0


def _write_script(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="exe-patch",
        description=(
            "Author, verify, and apply in-place byte patches to DSUN.EXE "
            "(Phase 5.7 authoring surface)."
        ),
    )
    ap.add_argument("exe", type=Path, nargs="?", help="path to the target DSUN.EXE")
    ap.add_argument(
        "--patch",
        metavar="SCRIPT",
        type=Path,
        help="apply a patch script (writes -o; never modifies the input)",
    )
    ap.add_argument(
        "--verify",
        metavar="SCRIPT",
        type=Path,
        help="run every check against SCRIPT and report; writes nothing",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="with --patch: validate without writing"
    )
    ap.add_argument(
        "--syms",
        metavar="FILE",
        type=Path,
        help="symbol catalogue for name addressing (default: "
        "tools/ovr-map/syms/<game>.toml when the script declares game =)",
    )
    ap.add_argument(
        "--asm",
        metavar="INSN",
        help="assemble INSN in 16-bit mode via nasm and print hex bytes",
    )
    ap.add_argument(
        "-o", "--output", metavar="FILE", type=Path, help="output path for --patch"
    )
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="round-trip proof and refusal checks (synthetic fixture + real "
        "binaries when .games/ is present)",
    )
    ap.add_argument("--version", action="version", version=f"exe-patch {VERSION}")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.asm is not None:
        try:
            print(assemble(args.asm).hex(" "))
            return 0
        except PatchError as e:
            print(f"exe-patch: {e}", file=sys.stderr)
            return 1

    if args.patch is None and args.verify is None:
        ap.error("one of --patch SCRIPT / --verify SCRIPT / --selftest is required")
    if args.exe is None:
        ap.error("exe (the target DSUN.EXE) is required")
    if not args.exe.is_file():
        print(f"exe-patch: no such file: {args.exe}", file=sys.stderr)
        return 2
    if args.patch is not None and args.output is None and not args.dry_run:
        ap.error("--patch needs -o OUTPUT (the tool never modifies its input)")

    try:
        data = args.exe.read_bytes()
        report = load_map(args.exe)

        syms: dict[str, list[dict[str, Any]]] | None = None
        script_path = args.patch if args.patch is not None else args.verify
        assert script_path is not None
        if args.syms is not None:
            syms = load_syms(args.syms)
        else:
            try:
                with script_path.open("rb") as fh:
                    declared = tomllib.load(fh).get("game")
                if declared in ("ds1", "ds2"):
                    default = SYMS_DIR / f"{declared}.toml"
                    if default.is_file():
                        syms = load_syms(default)
            except tomllib.TOMLDecodeError:
                pass  # let validate() report the bad TOML

        validated = validate(script_path, data, report, syms)
    except PatchError as e:
        print(f"exe-patch: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(validated, indent=2))
    else:
        for item in validated["edits"]:
            loc = item.get("resolved", "?")
            region = item.get("region", "?")
            segnote = (
                f" seg {item['segment']} +0x{item['segment_offset']:x}"
                if region == "overlay_segment"
                else ""
            )
            status = "OK" if not item.get("errors") else "FAIL"
            print(
                f"edit {item['index']}: {status}  at {item['at']} -> {loc} "
                f"[{region}{segnote}]"
            )
            for err in item.get("errors", []):
                print(f"        {err}")
        if validated["ok"]:
            print(f"{len(validated['edits'])} edit(s) OK")
        else:
            print(
                f"{len(validated['errors'])} error(s) across "
                f"{len(validated['edits'])} edit(s)"
            )

    if not validated["ok"]:
        return 1
    if args.verify is not None:
        return 0
    if args.dry_run:
        print(f"dry-run: {len(validated['edits'])} edit(s) would apply cleanly")
        return 0

    assert args.output is not None
    if args.output.resolve() == args.exe.resolve():
        print(
            "exe-patch: refusing to overwrite the input; choose another -o",
            file=sys.stderr,
        )
        return 2
    patched = apply_edits(data, validated)
    args.output.write_bytes(patched)
    print(
        f"applied {len(validated['edits'])} edit(s) to {args.output} "
        f"({len(patched)} bytes, length unchanged)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
