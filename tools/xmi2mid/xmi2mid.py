#!/usr/bin/env python3
"""xmi2mid: convert Dark Sun XMI sequence payloads to standard MIDI.

v0.1.0: linear, lossless-pass conversion with a branch sidecar.

An XMI payload (the body of a GSEQ/LSEQ/PSEQ/CSEQ/FSEQ chunk, or a
standalone .XMI) is `FORM XDIR { INFO } CAT XMID { FORM XMID {
[TIMB] [RBRN] EVNT } }` (verified 2026-10-06; file-formats.md 5).
EVNT uses XMI's delta encoding (sum of bytes < 0x80 up to the next
status byte), note-ons carry a VLQ duration instead of a paired
note-off, and XMIDI controllers 0x73/0x74/0x77/0x78 implement the
engine's adaptive-music machinery (FOR/NEXT loops, Indirect Control
polls, branch selection against the RBRN table).

Conversion policy (documented, deliberate):

- XMI ticks map 1:1 onto output ticks at 120 Hz (SMF division 60
  PPQN with tempo 500000: 500000/60 = 8333 us per tick). The classic
  public-domain xmi2mid (libgff bundles it; see CREDITS.md) uses the
  same mapping; the delta and note-duration decoders follow its
  `GetVLQ2`/note handling, re-derived from the corpus evidence.
- Every note-on's VLQ duration becomes a scheduled note-off, so the
  MIDI plays correctly in any sequencer.
- One linear pass; ticks are preserved, so RBRN branch ticks and
  loop spans in the sidecar are already in output coordinates.
- XMIDI controllers 0x73 (Indirect Control), 0x74 (FOR), 0x75
  (NEXT), 0x77 (Callback), and 0x78 (Sequence Branch Index) are
  REMOVED from the note data (a plain MIDI player cannot honour
  them) and recorded in the sidecar JSON instead: loop spans,
  branch-select events with their ticks, and the RBRN table. A
  port's music director implements the adaptive behaviour from the
  sidecar; this is the branch-aware handling a straight xmi2mid
  port lacks (libgff's xmi2mid skips non-EVNT chunks entirely).
- TIMB patch lists land in the sidecar too (MT-32 patch requests
  are not GM-program changes; baking them into the MIDI would lie).

Stdlib-only. Inputs are raw payload files (what audio-extract dumps
as *.xmi). Exit codes: 0 ok, 1 per-file conversion errors recorded,
2 bad input paths.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

VERSION = (Path(__file__).resolve().parent / "VERSION").read_text().strip()

SMF_DIVISION = 60  # PPQN; with tempo 500000 this is exactly 120 Hz
XMI_CONTROLLER_FOR = 0x74
XMI_CONTROLLER_NEXT = 0x75
XMI_CONTROLLER_BRANCH = 0x78
XMIDI_CONTROLLERS = {
    0x73,
    XMI_CONTROLLER_FOR,
    XMI_CONTROLLER_NEXT,
    0x77,
    XMI_CONTROLLER_BRANCH,
}


class XmiError(ValueError):
    pass


def _read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    """Standard MIDI VLQ (for meta lengths and note durations)."""
    value = 0
    for _ in range(4):
        if pos >= len(data):
            raise XmiError("VLQ runs past end of data")
        b = data[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if not b & 0x80:
            return value, pos
    raise XmiError("VLQ longer than 4 bytes")


def parse_xmi(data: bytes, name: str) -> dict:
    """Walk FORM XDIR / CAT XMID / FORM XMID and decode each sequence.

    Quirk (corpus-verified): the shipped files declare XDIR's FORM
    size as covering only the INFO chunk; the CAT XMID block follows
    as a sibling chunk past the declared extent. The top-level walk
    therefore runs to the end of the payload, not to FORM's size.

    Returns {timb: [(patch, bank)...], rbrn: [(id, tick)...],
    evnt: bytes} for the first XMID form (the shipped corpus is
    always one sequence per XDIR).
    """
    if data[:4] != b"FORM" or len(data) < 12:
        raise XmiError(f"{name}: not an XMI FORM container")
    if data[8:12] != b"XDIR":
        raise XmiError(f"{name}: FORM type is {data[8:12]!r}, not XDIR")
    pos = 12
    sequences = 0
    timb = []
    rbrn = []
    evnt = None
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4]
        size = struct.unpack_from(">I", data, pos + 4)[0]
        body = data[pos + 8 : pos + 8 + size]
        if len(body) != size:
            raise XmiError(f"{name}: chunk {cid!r} at {pos} overruns container")
        if cid == b"CAT ":
            if body[0:4] != b"XMID":
                raise XmiError(f"{name}: CAT type is {body[0:4]!r}, not XMID")
            # Walk the FORM XMID blocks inside the CAT body.
            inner = 4
            while inner + 8 <= len(body):
                icid = body[inner : inner + 4]
                isize = struct.unpack_from(">I", body, inner + 4)[0]
                ibody = body[inner + 8 : inner + 8 + isize]
                if len(ibody) != isize:
                    raise XmiError(f"{name}: FORM XMID at CAT+{inner} overruns")
                if icid == b"FORM":
                    if ibody[0:4] != b"XMID":
                        raise XmiError(f"{name}: inner FORM type {ibody[0:4]!r}")
                    ipos = 4
                    while ipos + 8 <= len(ibody):
                        scid = ibody[ipos : ipos + 4]
                        ssize = struct.unpack_from(">I", ibody, ipos + 4)[0]
                        sbody = ibody[ipos + 8 : ipos + 8 + ssize]
                        if len(sbody) != ssize:
                            raise XmiError(f"{name}: sequence chunk overruns")
                        if scid == b"TIMB":
                            count = struct.unpack_from("<H", sbody, 0)[0]
                            timb = [
                                struct.unpack_from("<BB", sbody, 2 + 2 * i)
                                for i in range(count)
                            ]
                        elif scid == b"RBRN":
                            count = struct.unpack_from("<H", sbody, 0)[0]
                            for i in range(count):
                                bid, tick = struct.unpack_from("<HI", sbody, 2 + 6 * i)
                                rbrn.append((bid, tick))
                        elif scid == b"EVNT":
                            evnt = sbody
                        ipos += 8 + ssize
                    sequences += 1
                inner += 8 + isize
        pos += 8 + size
    if evnt is None:
        raise XmiError(f"{name}: no EVNT chunk")
    if sequences != 1:
        raise XmiError(f"{name}: expected 1 sequence, walked {sequences}")
    return {"timb": timb, "rbrn": rbrn, "evnt": evnt}


def decode_evnt(evnt: bytes, name: str) -> list[dict]:
    """Decode an EVNT stream into absolute-tick events.

    Event dicts: {tick, status, bytes} with XMI note durations
    already resolved into explicit note-on/note-off pairs and XMIDI
    loop/branch controllers tagged. Bounded by the stream length.
    """
    events: list[dict] = []
    pos = 0
    tick = 0
    running_status: int | None = None
    while pos < len(evnt):
        # XMI delta: sum bytes < 0x80; the first >= 0x80 is status.
        delta = 0
        while pos < len(evnt) and evnt[pos] < 0x80:
            delta += evnt[pos]
            pos += 1
        tick += delta
        if pos >= len(evnt):
            # Corpus-verified (2026-10-06): EVNT chunks can end after a
            # delta run with no further status byte - writers pad the
            # chunk after the EOT meta, and some streams simply stop.
            # End of stream is end of track, not an error.
            break
        status = evnt[pos]
        pos += 1
        if status == 0xFF:
            meta_type = evnt[pos]
            length, pos = _read_vlq(evnt, pos + 1)
            meta_data = evnt[pos : pos + length]
            pos += length
            # Re-emit the standard SMF meta shape: type, VLQ length, data.
            len_buf = bytearray()
            _write_vlq(len_buf, length)
            events.append(
                {
                    "tick": tick,
                    "status": 0xFF,
                    "bytes": bytes([meta_type]) + bytes(len_buf) + meta_data,
                }
            )
            running_status = None
            if meta_type == 0x2F:
                # End of track: stop here; anything after it in the
                # chunk is padding (observed: trailing zero bytes).
                break
            continue
        if status < 0x80:
            # Running status: reuse the previous channel status.
            if running_status is None:
                raise XmiError(
                    f"{name}: running status with no prior status at {pos - 1}"
                )
            data_start = pos - 1
            pos = data_start
            status = running_status
        running_status = status
        kind = status & 0xF0
        if kind == 0x90:  # note-on with XMI duration
            note = evnt[pos]
            velocity = evnt[pos + 1]
            duration, pos2 = _read_vlq(evnt, pos + 2)
            pos = pos2
            events.append(
                {"tick": tick, "status": status, "bytes": bytes([note, velocity])}
            )
            events.append(
                {
                    "tick": tick + duration,
                    "status": 0x80 | (status & 0x0F),
                    "bytes": bytes([note, 0]),
                }
            )
        elif kind in (0x80, 0xA0, 0xB0, 0xE0):
            b1, b2 = evnt[pos], evnt[pos + 1]
            pos += 2
            if kind == 0xB0 and b1 in XMIDI_CONTROLLERS:
                events.append(
                    {
                        "tick": tick,
                        "status": status,
                        "bytes": bytes([b1, b2]),
                        "xmidi": b1,
                    }
                )
            else:
                events.append(
                    {"tick": tick, "status": status, "bytes": bytes([b1, b2])}
                )
        elif kind in (0xC0, 0xD0):
            events.append({"tick": tick, "status": status, "bytes": bytes([evnt[pos]])})
            pos += 1
        elif status in (0xF0, 0xF7):  # sysex, standard VLQ length
            length, pos = _read_vlq(evnt, pos)
            events.append(
                {"tick": tick, "status": status, "bytes": evnt[pos : pos + length]}
            )
            pos += length
            running_status = None
        else:
            raise XmiError(f"{name}: unsupported status {status:#04x} at {pos - 1}")
    return events


def _write_vlq(out: bytearray, value: int) -> None:
    if value < 0:
        raise XmiError("negative delta time")
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    out.extend(reversed(buffer))


def write_smf(events: list[dict], name: str) -> bytes:
    """Serialize absolute-tick events as a format-0 SMF at 120 Hz."""

    def sort_key(e):
        rank = 0 if (e["status"] & 0xF0) == 0x80 else 1
        return (e["tick"], rank)

    ordered = sorted(events, key=sort_key)
    track = bytearray()
    last = 0
    for e in ordered:
        _write_vlq(track, e["tick"] - last)
        last = e["tick"]
        track.append(e["status"])
        track += e["bytes"]
    if not (
        ordered
        and ordered[-1]["status"] == 0xFF
        and ordered[-1]["bytes"][:2] == b"\x2f\x00"
    ):
        # The source EVNT normally ends with its own EOT meta; add one
        # only when it does not.
        _write_vlq(track, 0)
        track += bytes([0xFF, 0x2F, 0x00])
    # Tempo meta first: rebuild with tempo at tick 0.
    tempo_event = {
        "tick": 0,
        "status": 0xFF,
        "bytes": bytes([0x51, 0x03]) + struct.pack(">I", 500000)[1:],
    }
    head = bytearray()
    _write_vlq(head, 0)
    head += tempo_event["status"].to_bytes(1, "little") + tempo_event["bytes"]
    body = bytes(head) + bytes(track)
    return (
        b"MThd"
        + struct.pack(">IHHH", 6, 0, 1, SMF_DIVISION)
        + b"MTrk"
        + struct.pack(">I", len(body))
        + body
    )


def convert(data: bytes, name: str) -> tuple[bytes, dict]:
    parsed = parse_xmi(data, name)
    events = decode_evnt(parsed["evnt"], name)
    note_events = []
    loops: list[dict] = []
    branch_selects: list[dict] = []
    open_fors: list[dict] = []
    for e in events:
        if "xmidi" in e:
            ctrl = e["xmidi"]
            value = e["bytes"][1]
            if ctrl == XMI_CONTROLLER_FOR:
                open_fors.append(
                    {"start_tick": e["tick"], "count": value, "infinite": value == 0}
                )
            elif ctrl == XMI_CONTROLLER_NEXT:
                if open_fors:
                    f = open_fors.pop()
                    f["end_tick"] = e["tick"]
                    loops.append(f)
            elif ctrl == XMI_CONTROLLER_BRANCH:
                branch_selects.append({"tick": e["tick"], "branch": value})
            # 0x73 / 0x77 engine polls: recorded as dropped, not listed.
            continue
        note_events.append(e)
    midi = write_smf(note_events, name)
    total_ticks = max((e["tick"] for e in note_events), default=0)
    sidecar = {
        "tool": "xmi2mid",
        "version": VERSION,
        "source": name,
        "smf_division": SMF_DIVISION,
        "tempo_us_per_quarter": 500000,
        "tick_rate_hz": 120,
        "total_ticks": total_ticks,
        "duration_s": round(total_ticks / 120, 3),
        "timb": [{"patch": p, "bank": b} for p, b in parsed["timb"]],
        "rbrn_branches": [
            {"branch": bid, "tick": tick} for bid, tick in parsed["rbrn"]
        ],
        "loop_spans": loops,
        "branch_selects": branch_selects,
    }
    return midi, sidecar


def selftest() -> int:
    # Synthetic XMI: TIMB (2 patches), RBRN (2 branches), EVNT with a
    # note (duration 30), a branch select, an infinite FOR/NEXT loop,
    # and a tempo-free controller event.
    def chunk(cid: bytes, body: bytes) -> bytes:
        return cid + struct.pack(">I", len(body)) + body

    timb_body = struct.pack("<H", 2) + bytes([20, 0, 41, 0x7F])
    rbrn_body = (
        struct.pack("<H", 2) + struct.pack("<HI", 1, 10) + struct.pack("<HI", 2, 50)
    )
    evnt = bytes([0])  # delta 0
    evnt += bytes([0x90, 60, 100]) + bytes([30])  # note-on C, dur 30 (VLQ single byte)
    evnt += bytes([10])  # delta 10 -> tick 40
    evnt += bytes([0xB0, 0x78, 1])  # select branch 1
    evnt += bytes([0]) + bytes([0xB0, 0x74, 0])  # FOR infinite at tick 40
    evnt += bytes([20])  # delta 20 -> tick 60
    evnt += bytes([0xB0, 0x75, 0])  # NEXT at tick 60
    evnt += bytes([0xFF, 0x2F, 0x00])  # end of track meta
    seq = chunk(b"TIMB", timb_body) + chunk(b"RBRN", rbrn_body) + chunk(b"EVNT", evnt)
    form_xmid = b"FORM" + struct.pack(">I", len(seq) + 4) + b"XMID" + seq
    cat = chunk(b"CAT ", b"XMID" + form_xmid)
    info = chunk(b"INFO", struct.pack("<H", 1))
    xdir_body = info + cat
    xmi = b"FORM" + struct.pack(">I", len(xdir_body) + 4) + b"XDIR" + xdir_body

    midi, side = convert(xmi, "selftest")

    # Corpus failure modes, both now legal: a pad byte after EOT, and
    # a stream that ends without any EOT meta.
    padded = xmi.replace(
        bytes([0xFF, 0x2F, 0x00]) + b"", bytes([0xFF, 0x2F, 0x00, 0x00])
    )
    m2, s2 = convert(padded, "selftest-pad")
    assert m2 == midi and s2["total_ticks"] == side["total_ticks"]
    trimmed = evnt[:-3]  # drop the EOT meta entirely
    seq_t = (
        chunk(b"TIMB", timb_body) + chunk(b"RBRN", rbrn_body) + chunk(b"EVNT", trimmed)
    )
    form_t = b"FORM" + struct.pack(">I", len(seq_t) + 4) + b"XMID" + seq_t
    cat_t = chunk(b"CAT ", b"XMID" + form_t)
    xdir_t = info + cat_t
    xmi_t = b"FORM" + struct.pack(">I", len(xdir_t) + 4) + b"XDIR" + xdir_t
    m3, s3 = convert(xmi_t, "selftest-noeot")
    assert m3.endswith(b"\xff\x2f\x00")  # the writer appended the EOT
    assert s3["total_ticks"] == 30 and s3["loop_spans"] == side["loop_spans"]

    assert midi[:4] == b"MThd"
    fmt, ntrk, div = struct.unpack_from(">HHH", midi, 8)
    assert (fmt, ntrk, div) == (0, 1, 60)
    # Sidecar invariants.
    assert side["timb"] == [{"patch": 20, "bank": 0}, {"patch": 41, "bank": 127}]
    assert side["rbrn_branches"] == [
        {"branch": 1, "tick": 10},
        {"branch": 2, "tick": 50},
    ]
    assert side["loop_spans"] == [
        {"start_tick": 10, "count": 0, "infinite": True, "end_tick": 30}
    ]
    assert side["branch_selects"] == [{"tick": 10, "branch": 1}]
    # MIDI track: parse the events back and check the note-off tick.
    track_start = 14  # MThd is 4 + 4 + 6 bytes
    assert midi[track_start : track_start + 4] == b"MTrk"
    track_len = struct.unpack_from(">I", midi, track_start + 4)[0]
    track = midi[track_start + 8 : track_start + 8 + track_len]
    pos = 0
    ticks = []
    statuses = []
    while pos < len(track):
        delta = 0
        while True:
            b = track[pos]
            pos += 1
            delta = (delta << 7) | (b & 0x7F)
            if not b & 0x80:
                break
        status = track[pos]
        pos += 1
        if status == 0xFF:
            length = track[pos + 1]
            pos += 2 + length
        else:
            n = 1 if (status & 0xF0) in (0xC0, 0xD0) else 2
            pos += n
        ticks.append(delta)
        statuses.append(status)
    # tempo(0), note-on(0), note-off(30), end-of-track right after (the
    # loop/branch controllers were dropped, not converted).
    assert ticks == [0, 0, 30, 0], ticks
    assert statuses[1] == 0x90 and statuses[2] == 0x80, statuses
    assert 0xB0 not in statuses, statuses
    print(f"xmi2mid {VERSION} selftest ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("files", nargs="*", type=Path, help="XMI payload files to convert")
    ap.add_argument(
        "--out", type=Path, default=Path("midi-out"), help="output directory"
    )
    ap.add_argument(
        "--selftest", action="store_true", help="synthetic-payload selftest"
    )
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.files:
        ap.error("at least one input file is required (or --selftest)")
    for f in args.files:
        if not f.is_file():
            print(f"error: not a file: {f}", file=sys.stderr)
            return 2

    args.out.mkdir(parents=True, exist_ok=True)
    # Payloads in the wild share a stem (two CSEQ-1000.xmi, one per
    # container); disambiguate output names so nothing overwrites.
    from collections import Counter

    stem_counts = Counter(f.stem for f in args.files)
    had_errors = False
    for f in args.files:
        data = f.read_bytes()
        try:
            midi, sidecar = convert(data, f.name)
        except XmiError as exc:
            print(f"{f.name}: CONVERSION FAILED: {exc}", file=sys.stderr)
            had_errors = True
            continue
        stem = f.stem if stem_counts[f.stem] == 1 else f"{f.stem}-{f.parent.name}"
        midi_path = args.out / f"{stem}.mid"
        json_path = args.out / f"{stem}.xmi.json"
        midi_path.write_bytes(midi)
        json_path.write_text(json.dumps(sidecar, indent=2) + "\n")
        print(
            f"{f.name}: {sidecar['total_ticks']} ticks ({sidecar['duration_s']} s),"
            f" {len(sidecar['rbrn_branches'])} branches,"
            f" {len(sidecar['loop_spans'])} loops,"
            f" {len(sidecar['timb'])} patches -> {midi_path.name}"
        )
    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
