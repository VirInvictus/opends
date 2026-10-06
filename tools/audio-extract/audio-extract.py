#!/usr/bin/env python3
"""audio-extract: dump the audio chunks of a Dark Sun GFF container.

v0.1.0: initial cut. Parses a GFF container's TOC (indexed and
segmented chunk lists), slices out the audio chunk kinds, and writes:

- BVOC/FVOC payloads decoded to WAV (Creative Voice block decode),
- GSEQ/LSEQ/PSEQ/CSEQ/MSEQ payloads dumped verbatim (XMI-family
  sequence data; conversion to standard MIDI is a future tool),
- an inventory JSON (ids, sizes, VOC block structure, sample rates,
  durations for PCM, magic sniff for sequences).

Chunk ids and the fourcc set follow docs/file-formats.md; the TOC
walker follows the in-repo authority (tools/gff-edit/src/lib.rs
`parse_toc` / `resolve_segmented_type`, itself cross-checked against
libgff and dsun_music). Routing context (which ids the engine plays
when) lives in docs/audio-routing.md; this tool only opens the boxes.

Stdlib-only. Exit codes: 0 ok, 1 decode errors recorded (output still
written), 2 bad input paths.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import wave
from pathlib import Path

VERSION = (Path(__file__).resolve().parent / "VERSION").read_text().strip()

SEGMENTED_FLAG = 0x80000000
CHUNK_COUNT_MASK = 0x7FFFFFFF

# The audio chunk kinds this tool opens. BVOC/FVOC are Creative Voice
# payloads (background/foreground digital samples); the *SEQ family is
# XMI sequence data rendered per sound driver at content-build time,
# every observed payload a FORM/XDIR directory (docs/file-formats.md
# section 5). MSEQ (master XMI) is accepted for completeness; the
# shipped corpus carries none.
KINDS = ("BVOC", "FVOC", "GSEQ", "LSEQ", "PSEQ", "CSEQ", "MSEQ", "FSEQ")
VOC_KINDS = ("BVOC", "FVOC")
SEQ_KINDS = ("GSEQ", "LSEQ", "PSEQ", "CSEQ", "MSEQ", "FSEQ")

# VOC block types (Creative Voice File, the standard layout).
VOC_TERMINATOR = 0x00
VOC_SOUND_DATA = 0x01
VOC_SOUND_CONTINUE = 0x02
VOC_SILENCE = 0x03
VOC_MARKER = 0x04
VOC_ASCII_TEXT = 0x05
VOC_REPEAT_START = 0x06
VOC_REPEAT_END = 0x07
VOC_EXTENDED = 0x08
VOC_NEW_FORMAT_DATA = 0x09

# Repeat expansion cap: a corrupted repeat count must not explode the
# output. Shipped-game VOCs observed so far do not use repeats at all.
MAX_REPEAT_COUNT = 16


class VocError(ValueError):
    pass


# --- GFF container -----------------------------------------------------


class GffError(ValueError):
    pass


def _u16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def _u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def _i32(b: bytes, off: int) -> int:
    return struct.unpack_from("<i", b, off)[0]


class Chunk:
    __slots__ = ("kind", "id", "location", "length")

    def __init__(self, kind: str, id: int, location: int, length: int) -> None:
        self.kind = kind
        self.id = id
        self.location = location
        self.length = length


def parse_gff(data: bytes) -> dict[str, list[Chunk]]:
    """Parse a GFF container's TOC into kind -> chunks, ids resolved.

    Follows tools/gff-edit/src/lib.rs parse_toc /
    resolve_segmented_type: header toc_location/toc_length at 12/16,
    TOC header (types_offset, free_list_offset), type list of
    {fourcc, count} entries where the count's high bit marks a
    segmented list (secondary table inside a GFFI-type chunk, ids
    reconstructed from segment runs).
    """
    if len(data) < 28 or data[:4] != b"GFFI":
        raise GffError("not a GFF container (no GFFI magic)")
    toc_location = _u32(data, 12)
    toc_length = _u32(data, 16)
    if toc_location + toc_length > len(data) or toc_length < 8:
        raise GffError(f"TOC out of bounds (at {toc_location}, len {toc_length})")
    toc = data[toc_location : toc_location + toc_length]

    types_offset = _u32(toc, 0)
    if types_offset + 2 > len(toc):
        raise GffError("TOC types list out of bounds")
    num_types = _u16(toc, types_offset)
    cursor = types_offset + 2

    indexed: dict[str, list[Chunk]] = {}
    segmented: dict[str, tuple[int, list[tuple[int, int]]]] = {}

    for _ in range(num_types):
        if cursor + 8 > len(toc):
            raise GffError("type entry out of bounds")
        kind = toc[cursor : cursor + 4].decode("latin-1").rstrip()
        raw_count = _u32(toc, cursor + 4)
        cursor += 8
        if raw_count & SEGMENTED_FLAG:
            if cursor + 12 > len(toc):
                raise GffError("segmented header out of bounds")
            _seg_count = _i32(toc, cursor)
            seg_loc_id = _i32(toc, cursor + 4)
            num_runs = _u32(toc, cursor + 8)
            cursor += 12
            runs = []
            for _ in range(num_runs):
                if cursor + 8 > len(toc):
                    raise GffError("segment run out of bounds")
                first_id = _i32(toc, cursor)
                num_chunks = _i32(toc, cursor + 4)
                cursor += 8
                runs.append((first_id, num_chunks))
            segmented[kind] = (seg_loc_id, runs)
        else:
            count = raw_count & CHUNK_COUNT_MASK
            if cursor + count * 12 > len(toc):
                raise GffError("indexed chunk entries out of bounds")
            chunks = []
            for i in range(count):
                base = cursor + i * 12
                id = _i32(toc, base)
                location = _u32(toc, base + 4)
                length = _u32(toc, base + 8)
                if location + length > len(data):
                    raise GffError(
                        f"chunk {kind.rstrip() or '?'} id {id} out of bounds "
                        f"(at {location}+{length}, file {len(data)})"
                    )
                chunks.append(Chunk(kind, id, location, length))
            # A kind may appear more than once in the type list
            # (indexed and segmented entries coexist in shipped files).
            indexed.setdefault(kind, []).extend(chunks)
            cursor += count * 12

    for kind, (seg_loc_id, runs) in segmented.items():
        gffi = indexed.get("GFFI")
        if not gffi:
            raise GffError(f"segmented type {kind} but no GFFI type")
        if not 0 <= seg_loc_id < len(gffi):
            raise GffError(
                f"segmented type {kind}: seg_loc_id {seg_loc_id} "
                f"out of range (GFFI has {len(gffi)})"
            )
        table_start = gffi[seg_loc_id].location
        if table_start + 4 > len(data):
            raise GffError(f"secondary table out of bounds at {table_start}")
        entry_count = _u32(data, table_start)
        runs_total = sum(max(n, 0) for _, n in runs)
        if runs_total != entry_count:
            raise GffError(
                f"segmented type {kind}: runs total {runs_total} "
                f"!= secondary table entries {entry_count}"
            )
        chunks = []
        entry_index = 0
        for first_id, num_chunks in runs:
            if num_chunks <= 0:
                continue
            for k in range(num_chunks):
                pos = table_start + 4 + (entry_index + k) * 8
                if pos + 8 > len(data):
                    raise GffError("secondary table entry out of bounds")
                location = _u32(data, pos)
                length = _u32(data, pos + 4)
                if location + length > len(data):
                    raise GffError(
                        f"segmented chunk {kind} id {first_id + k} out of bounds"
                    )
                chunks.append(Chunk(kind, first_id + k, location, length))
            entry_index += num_chunks
        indexed.setdefault(kind, []).extend(chunks)

    return indexed


# --- Creative Voice decode ---------------------------------------------


def _voc_sr_to_rate(sr: int) -> int:
    # Type-1 sound data: SR byte, rate = 1000000 / (256 - SR) Hz.
    return 1000000 // (256 - sr)


class VocDecode:
    """Result of a VOC decode: one or more contiguous PCM parts.

    A part is a run of same-format audio; a mid-file rate/width change
    starts a new part (a WAV can only carry one rate).
    """

    def __init__(self) -> None:
        self.parts: list[dict] = []
        self.notes: list[str] = []

    def total_seconds(self) -> float | None:
        if not self.parts:
            return None
        return round(sum(p["duration_s"] for p in self.parts), 3)


def decode_voc(data: bytes, name: str) -> VocDecode:
    """Decode a Creative Voice File (full header or bare block stream).

    Block types per the standard; types 6/7 (repeat) expand bounded.
    8-bit unsigned PCM and 16-bit little-endian PCM are the codecs
    seen in SSI-era VOCs; anything else raises VocError.
    """
    out = VocDecode()
    pos = 0
    if data[:19] == b"Creative Voice File":
        if len(data) < 26:
            raise VocError(f"{name}: truncated VOC file header")
        pos = _u16(data, 20)
        if not 19 < pos <= len(data):
            raise VocError(f"{name}: bad VOC data_offset {pos}")

    # cur carries the part being accumulated: rate/width/channels/bytes.
    cur: dict | None = None

    def flush() -> None:
        nonlocal cur
        if cur and cur["data"]:
            out.parts.append(
                {
                    "rate": cur["rate"],
                    "channels": cur["channels"],
                    "width": cur["width"],
                    "samples": len(cur["data"]) // cur["width"] // cur["channels"],
                    "duration_s": round(
                        len(cur["data"]) / cur["width"] / cur["channels"] / cur["rate"],
                        3,
                    ),
                }
            )
            out.parts[-1]["_data"] = cur["data"]
        cur = None

    repeat_stack: list[tuple[int, int]] = []  # (pos, remaining count)

    def process_stream(start: int, end: int) -> None:
        nonlocal cur
        pos = start
        while pos < end:
            btype = data[pos]
            pos += 1
            if btype == VOC_TERMINATOR:
                break
            if pos + 3 > end:
                raise VocError(f"{name}: truncated block header at {pos - 1}")
            blen = data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16)
            pos += 3
            if pos + blen > end:
                raise VocError(f"{name}: block type {btype} overruns data")
            body = data[pos : pos + blen]
            pos += blen

            if btype == VOC_SOUND_DATA:
                if len(body) < 2:
                    raise VocError(f"{name}: short sound-data block")
                rate = _voc_sr_to_rate(body[0])
                width = 1
                channels = 1
                pcm = body[2:]
                if cur and (cur["rate"], cur["width"], cur["channels"]) != (
                    rate,
                    width,
                    channels,
                ):
                    flush()
                if cur is None:
                    cur = {
                        "rate": rate,
                        "width": width,
                        "channels": channels,
                        "data": bytearray(),
                    }
                cur["data"] += pcm
            elif btype == VOC_SOUND_CONTINUE:
                if cur is None:
                    raise VocError(f"{name}: continuation with no open part")
                cur["data"] += body
            elif btype == VOC_SILENCE:
                if len(body) < 3:
                    raise VocError(f"{name}: short silence block")
                count = _u16(body, 0) + 1
                rate = _voc_sr_to_rate(body[2])
                if cur and (cur["rate"], cur["width"], cur["channels"]) != (
                    rate,
                    1,
                    1,
                ):
                    flush()
                if cur is None:
                    cur = {"rate": rate, "width": 1, "channels": 1, "data": bytearray()}
                cur["data"] += b"\x80" * count
            elif btype == VOC_MARKER:
                if len(body) >= 2:
                    out.notes.append(f"marker {struct.unpack_from('<H', body)[0]}")
            elif btype == VOC_ASCII_TEXT:
                text = body.split(b"\x1a")[0].decode("latin-1", "replace").strip()
                if text:
                    out.notes.append(f"text: {text}")
            elif btype == VOC_REPEAT_START:
                if len(body) < 2:
                    raise VocError(f"{name}: short repeat-start block")
                count = _u16(body, 0)
                if count == 0xFFFF:
                    count = MAX_REPEAT_COUNT
                repeat_stack.append((pos, min(count, MAX_REPEAT_COUNT)))
            elif btype == VOC_REPEAT_END:
                if repeat_stack:
                    start, count = repeat_stack.pop()
                    if count > 1 and len(out.parts) < 64:
                        # Bounded expansion: replay the loop body.
                        for _ in range(count - 1):
                            process_stream(start, pos)
            elif btype == VOC_EXTENDED:
                if len(body) < 4:
                    raise VocError(f"{name}: short extended block")
                tc = _u16(body, 0)
                channels = body[3] + 1
                rate = 256000000 // (65536 - tc)
                if cur and (cur["rate"], cur["channels"]) != (rate, channels):
                    flush()
                # Width is decided by the following type-1 block.
                if cur is None:
                    cur = {
                        "rate": rate,
                        "width": 1,
                        "channels": channels,
                        "data": bytearray(),
                    }
                else:
                    cur["rate"] = rate
                    cur["channels"] = channels
            elif btype == VOC_NEW_FORMAT_DATA:
                if len(body) < 8:
                    raise VocError(f"{name}: short new-format block")
                rate, bits, channels, codec = struct.unpack_from("<IBBH", body, 0)
                if codec not in (0, 4) or bits not in (8, 16):
                    raise VocError(
                        f"{name}: unsupported new-format codec {codec} / {bits} bit"
                    )
                width = bits // 8
                pcm = body[8:]
                if cur and (cur["rate"], cur["width"], cur["channels"]) != (
                    rate,
                    width,
                    channels,
                ):
                    flush()
                if cur is None:
                    cur = {
                        "rate": rate,
                        "width": width,
                        "channels": channels,
                        "data": bytearray(),
                    }
                cur["data"] += pcm
            else:
                raise VocError(f"{name}: unsupported VOC block type {btype}")

    process_stream(pos, len(data))
    flush()
    return out


def write_wav(path: Path, part: dict) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(part["channels"])
        w.setsampwidth(part["width"])
        w.setframerate(part["rate"])
        w.writeframes(bytes(part.pop("_data")))


# --- extraction driver --------------------------------------------------


def magic_sniff(payload: bytes) -> dict:
    """Identify a sequence payload coarsely (deep XMI decode is the
    future xmi2mid converter's job, not this tool's)."""
    if payload[:4] == b"FORM":
        return {
            "magic": "FORM",
            "form_type": payload[8:12].decode("latin-1", "replace"),
        }
    if payload[:4] == b"CAT ":
        return {"magic": "CAT", "form_type": payload[8:12].decode("latin-1", "replace")}
    if payload[:19] == b"Creative Voice File":
        return {"magic": "voc-file"}
    return {"magic": payload[:4].decode("latin-1", "replace").rstrip() or "none"}


def extract_file(
    path: Path,
    out_dir: Path,
    dir_name: str,
    kinds: tuple[str, ...],
    want_wav: bool,
    want_payload: bool,
) -> dict:
    data = path.read_bytes()
    by_kind = parse_gff(data)
    stem = dir_name
    file_dir = out_dir / stem
    file_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "file": str(path),
        "size": len(data),
        "kinds_present": {k: len(v) for k, v in sorted(by_kind.items()) if k in KINDS},
        "chunks": [],
        "errors": [],
    }

    for kind in kinds:
        for chunk in sorted(by_kind.get(kind, []), key=lambda c: c.id):
            payload = data[chunk.location : chunk.location + chunk.length]
            entry: dict = {
                "kind": kind,
                "id": chunk.id,
                "offset": chunk.location,
                "length": chunk.length,
            }
            try:
                if kind in VOC_KINDS:
                    dec = decode_voc(payload, f"{stem}/{kind}-{chunk.id}")
                    entry["magic"] = "voc"
                    entry["notes"] = dec.notes
                    if dec.parts:
                        entry["rate"] = dec.parts[0]["rate"]
                        entry["width"] = dec.parts[0]["width"]
                        entry["channels"] = dec.parts[0]["channels"]
                        entry["duration_s"] = dec.total_seconds()
                        entry["parts"] = len(dec.parts)
                        if want_wav:
                            base = f"{kind}-{chunk.id}"
                            written = []
                            for i, part in enumerate(dec.parts):
                                suffix = "" if len(dec.parts) == 1 else f"-part{i + 1}"
                                wav_path = file_dir / f"{base}{suffix}.wav"
                                write_wav(wav_path, part)
                                written.append(wav_path.name)
                            entry["wav"] = written
                    else:
                        entry["error"] = "no audio blocks decoded"
                else:
                    entry.update(magic_sniff(payload))
                    if want_payload:
                        ext = "xmi" if entry.get("magic") in ("FORM", "CAT") else "bin"
                        (file_dir / f"{kind}-{chunk.id}.{ext}").write_bytes(payload)
            except (VocError, GffError, ValueError) as exc:
                entry["error"] = str(exc)
                report["errors"].append(f"{kind}-{chunk.id}: {exc}")
            report["chunks"].append(entry)

    return report


def summarize(report: dict) -> str:
    lines = [
        f"{report['file']}: {report['size']} bytes",
    ]
    for kind, count in report["kinds_present"].items():
        chunks = [c for c in report["chunks"] if c["kind"] == kind]
        total = sum(c["length"] for c in chunks)
        ids = f"ids {min(c['id'] for c in chunks)}..{max(c['id'] for c in chunks)}"
        dur = sum(c.get("duration_s") or 0 for c in chunks)
        dur_txt = f", {dur:.1f}s audio" if dur else ""
        errs = sum(1 for c in chunks if "error" in c)
        err_txt = f", {errs} decode errors" if errs else ""
        lines.append(
            f"  {kind:5s} {count:4d} chunks, {total:8d} bytes, {ids}{dur_txt}{err_txt}"
        )
    return "\n".join(lines)


def build_selftest_gff() -> tuple[bytes, dict]:
    """Synthesize a minimal GFF: one indexed BVOC (full VOC file) and
    one segmented BVOC list (two runs, ids 1 and 5, secondary table in
    the first GFFI chunk) plus one indexed GSEQ carrying a FORM/XRFF
    payload. Returns (bytes, expected)."""

    def block(btype: int, body: bytes) -> bytes:
        return (
            bytes([btype])
            + bytes(
                [len(body) & 0xFF, (len(body) >> 8) & 0xFF, (len(body) >> 16) & 0xFF]
            )
            + body
        )

    # Full VOC file: 26-byte header, one type-1 block (SR byte 131 ->
    # 8000 Hz, pack byte 0, 8-bit unsigned), terminator.
    voc_payload = b"Creative Voice File\x1a"
    voc_payload += struct.pack("<HHH", 26, 0x0114, (~0x0114 + 0x1234) & 0xFFFF)
    voc_payload += block(VOC_SOUND_DATA, bytes([131, 0]) + b"\x40\x41\x42\x43")
    voc_payload += bytes([VOC_TERMINATOR])

    # Bare block stream: type-9 block, 16-bit, 4000 Hz, mono.
    body9 = struct.pack("<IBBH", 4000, 16, 1, 4) + b"\x01\x02\x03\x04\x05\x06"
    new_format = block(VOC_NEW_FORMAT_DATA, body9) + bytes([VOC_TERMINATOR])

    seq_payload = (
        b"FORM"
        + struct.pack("<I", 4)
        + b"XDIR"
        + b"CAT "
        + struct.pack("<I", 4)
        + b"XMID"
    )

    # Segmented BVOC payloads: id 1 is a placeholder byte, id 5 empty.
    # The GFFI chunk is the secondary table (2 entries), 20 bytes.
    table_size = 4 + 2 * 8

    order: list[tuple[str, int, int]] = [
        ("BVOC", 7, len(voc_payload)),
        ("SEG0", 0, 1),
        ("SEG1", 0, 0),
        ("GFFI", 1, table_size),
        ("GSEQ", 1, len(seq_payload)),
    ]
    header_len = 28
    num_types = 4  # GFFI, BVOC (indexed), BVOC (segmented), GSEQ
    toc_size = 8 + 2 + num_types * 8 + 12 * 3 + (12 + 2 * 8)
    data_start = header_len + toc_size

    offs: dict[tuple[str, int], tuple[int, int]] = {}
    off = data_start
    for kind, id, size in order:
        offs[(kind, id)] = (off, size)
        off += size

    seg0_loc, seg0_len = offs[("SEG0", 0)]
    seg1_loc, seg1_len = offs[("SEG1", 0)]
    table = struct.pack("<I", 2)
    table += struct.pack("<II", seg0_loc, seg0_len)
    table += struct.pack("<II", seg1_loc, seg1_len)
    assert len(table) == table_size

    def fourcc(s: str) -> bytes:
        return s.encode("latin-1").ljust(4, b" ")[:4]

    gffi_loc, gffi_len = offs[("GFFI", 1)]
    voc_loc, voc_len = offs[("BVOC", 7)]
    seq_loc, seq_len = offs[("GSEQ", 1)]

    toc = bytearray()
    toc += struct.pack("<II", 8, toc_size)  # types_offset=8, free at end
    toc += struct.pack("<H", num_types)
    toc += fourcc("GFFI") + struct.pack("<I", 1)
    toc += struct.pack("<iII", 1, gffi_loc, gffi_len)
    toc += fourcc("BVOC") + struct.pack("<I", 1)
    toc += struct.pack("<iII", 7, voc_loc, voc_len)
    toc += fourcc("BVOC") + struct.pack("<I", SEGMENTED_FLAG | 2)
    toc += struct.pack("<iiI", 2, 0, 2)  # seg_count, seg_loc_id, num_runs
    toc += struct.pack("<ii", 1, 1)  # run: id 1, one chunk
    toc += struct.pack("<ii", 5, 1)  # run: id 5, one chunk
    toc += fourcc("GSEQ") + struct.pack("<I", 1)
    toc += struct.pack("<iII", 1, seq_loc, seq_len)
    assert len(toc) == toc_size

    # Payload order must match the layout pass above.
    seg0_data = b"\x00"
    out = bytearray()
    out += b"GFFI" + struct.pack("<III", 0x00030000, 28, header_len)
    out += struct.pack("<II", toc_size, 0)  # toc_length, file_flags
    out += struct.pack("<I", 1)  # data0
    assert len(out) == header_len
    out += toc
    assert len(out) == data_start
    for blob in (voc_payload, seg0_data, b"", table, seq_payload):
        out += blob
    assert len(out) == off

    expected = {
        "bvoc_7": (8000, 1, 1),
        "segmented_ids": [1, 5],
    }
    return bytes(out), expected, new_format


def selftest() -> int:
    gff, expected, new_format = build_selftest_gff()
    by_kind = parse_gff(gff)

    assert set(by_kind) == {"GFFI", "BVOC", "GSEQ"}, sorted(by_kind)
    seg_ids = [c.id for c in by_kind["BVOC"] if c.id in (1, 5)]
    assert seg_ids == expected["segmented_ids"], seg_ids
    assert [c.id for c in by_kind["GSEQ"]] == [1]
    assert by_kind["GSEQ"][0].length == 24  # FORM hdr + XDIR + CAT XMID

    voc_chunk = next(c for c in by_kind["BVOC"] if c.id == 7)
    data = gff[voc_chunk.location : voc_chunk.location + voc_chunk.length]
    dec = decode_voc(data, "selftest")
    assert len(dec.parts) == 1
    part = dec.parts[0]
    assert (part["rate"], part["width"], part["channels"]) == expected["bvoc_7"], part
    assert part["_data"] == b"\x40\x41\x42\x43"
    # durations are stored rounded to 3 decimals (real chunks are
    # seconds long; the 4-sample selftest clip just proves the math)
    assert part["duration_s"] == round(4 / 8000, 3)

    seg5 = next(c for c in by_kind["BVOC"] if c.id == 5)
    assert gff[seg5.location : seg5.location + seg5.length] == b""

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "t.wav"
        write_wav(wav_path, part)
        with wave.open(str(wav_path), "rb") as w:
            assert w.getframerate() == 8000 and w.getsampwidth() == 1

    dec2 = decode_voc(new_format, "selftest-nf")
    assert len(dec2.parts) == 1
    assert dec2.parts[0]["rate"] == 4000 and dec2.parts[0]["width"] == 2
    assert dec2.parts[0]["_data"] == b"\x01\x02\x03\x04\x05\x06"

    print(f"audio-extract {VERSION} selftest ok")
    return 0


def selftest_corpus() -> int:
    """Corpus invariants measured 2026-09-21 (mineout prompt); skipped
    when the games are not extracted."""
    ds1 = Path(".games/ds1")
    if not ds1.is_dir():
        print("corpus selftest skipped (.games/ds1 absent)")
        return 0
    failures = []

    def check(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    res = parse_gff((ds1 / "RESOURCE.GFF").read_bytes())
    gseq_ids = sorted(c.id for c in res.get("GSEQ", []))
    check(gseq_ids == list(range(1, 24)), f"DS1 RESOURCE GSEQ ids: {gseq_ids}")
    lseq_ids = sorted(c.id for c in res.get("LSEQ", []))
    check(lseq_ids == list(range(1, 24)), f"DS1 RESOURCE LSEQ ids: {lseq_ids}")
    bvoc = res.get("BVOC", [])
    bvoc_ids = sorted(c.id for c in bvoc)
    check(len(bvoc) == 111, f"DS1 BVOC count {len(bvoc)}")
    check(
        all(1 <= i <= 130 for i in bvoc_ids) and len(bvoc_ids) == len(set(bvoc_ids)),
        "DS1 BVOC ids within 1..130, unique",
    )
    cseq_ids = sorted(c.id for c in res.get("CSEQ", []))
    check(cseq_ids == [1000], f"DS1 CSEQ ids: {cseq_ids}")
    check(
        "MSEQ" not in res and "FSEQ" not in res,
        "DS1 ships no MSEQ/FSEQ in RESOURCE.GFF",
    )

    cine = parse_gff((ds1 / "CINE.GFF").read_bytes())
    for kind in ("GSEQ", "LSEQ", "PSEQ"):
        ids = sorted(c.id for c in cine.get(kind, []))
        check(ids == [26, 27, 28, 29], f"DS1 CINE {kind} ids: {ids}")
    cseq_ids = sorted(c.id for c in cine.get("CSEQ", []))
    check(cseq_ids == [1000], f"DS1 CINE CSEQ ids: {cseq_ids}")
    check("MSEQ" not in cine and "FSEQ" not in cine, "DS1 CINE ships no MSEQ/FSEQ")

    if failures:
        for f in failures:
            print(f"corpus selftest FAILURE: {f}")
        return 1
    print("corpus selftest ok (DS1 RESOURCE.GFF + CINE.GFF invariants)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("files", nargs="*", type=Path, help="GFF containers to mine")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("audio-out"),
        help="output directory for WAVs, payloads and inventory (default ./audio-out)",
    )
    ap.add_argument(
        "--kinds",
        default=",".join(KINDS),
        help="comma-separated kinds to extract (default: all audio kinds)",
    )
    ap.add_argument(
        "--json", action="store_true", help="print the inventory JSON to stdout too"
    )
    ap.add_argument(
        "--no-wav", action="store_true", help="skip WAV writing (inventory only)"
    )
    ap.add_argument(
        "--no-payloads",
        action="store_true",
        help="skip sequence payload dumps (inventory only)",
    )
    ap.add_argument(
        "--selftest", action="store_true", help="synthetic-container selftest"
    )
    ap.add_argument(
        "--selftest-corpus",
        action="store_true",
        help="assert measured DS1 corpus invariants (skips without .games)",
    )
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.selftest_corpus:
        return selftest_corpus()
    if not args.files:
        ap.error("at least one GFF file is required (or --selftest)")

    kinds = tuple(k.strip().upper() for k in args.kinds.split(",") if k.strip())
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        print(f"error: unknown kinds {bad}; known: {KINDS}", file=sys.stderr)
        return 2
    for f in args.files:
        if not f.is_file():
            print(f"error: not a file: {f}", file=sys.stderr)
            return 2

    args.out.mkdir(parents=True, exist_ok=True)
    # Containers in the wild share a stem (three RESOURCE.GFF, two
    # RESFLOP.GFF); disambiguate output dirs so nothing overwrites.
    from collections import Counter

    stem_counts = Counter(f.stem for f in args.files)
    reports = []
    had_errors = False
    for f in args.files:
        dir_name = f.stem if stem_counts[f.stem] == 1 else f"{f.stem}-{f.parent.name}"
        report = extract_file(
            f,
            args.out,
            dir_name,
            kinds,
            want_wav=not args.no_wav,
            want_payload=not args.no_payloads,
        )
        reports.append(report)
        print(summarize(report))
        if report["errors"]:
            had_errors = True

    inventory = {"tool": "audio-extract", "version": VERSION, "files": reports}
    inv_path = args.out / "audio-inventory.json"
    inv_path.write_text(json.dumps(inventory, indent=2) + "\n")
    print(f"\ninventory: {inv_path}")
    if args.json:
        print(json.dumps(inventory, indent=2))
    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
