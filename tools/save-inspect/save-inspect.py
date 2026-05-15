#!/usr/bin/env python3
"""save-inspect: dump a Dark Sun CHARSAVE.GFF as JSON.

Stdlib-only. Decodes the well-understood save chunks (CHAR
header, PSIN/PSST psionics, TEXT) and emits opaque hex previews
for chunks whose internal layout isn't yet documented per game
(CHAR record data, SPST, CACT, PREF, GREQ). v0.2.0 will fill in
the RDFF schemas for CHAR records (per-game; see
docs/file-formats.md §2).

The embedded GFF parser only handles indexed chunks. CHARSAVE.GFF
never uses segmented chunks; if that changes we'd shell out to
gff-cat or bind to the gff-edit Rust crate.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text().strip()

HEADER_SIZE = 28
SEGMENTED_FLAG = 0x8000_0000
CHUNK_COUNT_MASK = 0x7FFF_FFFF


def parse_gff(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < HEADER_SIZE:
        raise ValueError(f"file too short: {len(data)} bytes")
    if data[:4] != b"GFFI":
        raise ValueError(f"bad GFF magic: {data[:4]!r}")
    (
        identity,
        version,
        data_location,
        toc_location,
        toc_length,
        file_flags,
        data0,
    ) = struct.unpack_from("<4sIIIIII", data, 0)
    if (version >> 16) != 3:
        raise ValueError(f"unsupported version: 0x{version:08x}")

    toc = data[toc_location : toc_location + toc_length]
    types_offset = struct.unpack_from("<I", toc, 0)[0]
    # free_list_offset at toc[4..8] — unused here.
    num_types = struct.unpack_from("<H", toc, types_offset)[0]
    cursor = types_offset + 2

    chunks: list[dict[str, Any]] = []
    for _ in range(num_types):
        if cursor + 8 > len(toc):
            raise ValueError(f"TOC truncated at offset {cursor}")
        kind = toc[cursor : cursor + 4].decode("latin-1")
        raw_count = struct.unpack_from("<I", toc, cursor + 4)[0]
        cursor += 8
        if raw_count & SEGMENTED_FLAG:
            raise ValueError(
                f"segmented chunk type '{kind}' not supported by save-inspect v0.1.0; "
                "use gff-cat for inspection"
            )
        chunk_count = raw_count & CHUNK_COUNT_MASK
        for _ in range(chunk_count):
            res_id, location, length = struct.unpack_from("<iII", toc, cursor)
            cursor += 12
            payload = data[location : location + length]
            chunks.append(
                {
                    "kind": kind,
                    "id": res_id,
                    "offset": location,
                    "length": length,
                    "bytes": payload,
                }
            )

    return {
        "file_size": len(data),
        "header": {
            "identity": identity.decode("ascii", errors="replace"),
            "version": version,
            "major_version": (version >> 16) & 0xFFFF,
            "data_location": data_location,
            "toc_location": toc_location,
            "toc_length": toc_length,
            "file_flags": file_flags,
            "data0": data0,
        },
        "chunks": chunks,
    }


def decode_rdff_header(payload: bytes) -> dict[str, Any]:
    """Decode the 10-byte gff_rdff_header_t at the start of a record."""
    if len(payload) < 10:
        return {"_truncated": True, "raw_bytes": len(payload)}
    (load_action, blocknum, rdff_type, index, from_, length) = struct.unpack_from(
        "<bbhhhh", payload, 0
    )
    return {
        "load_action": load_action,
        "blocknum": blocknum,
        "type": rdff_type,
        "index": index,
        "from": from_,
        "len": length,
    }


def hex_preview(payload: bytes, limit: int = 64) -> str:
    """Hex preview of the first `limit` bytes, space-separated."""
    head = payload[:limit]
    out = " ".join(f"{b:02x}" for b in head)
    if len(payload) > limit:
        out += f" ... ({len(payload) - limit} more bytes)"
    return out


def decode_text(payload: bytes) -> str:
    """Decode a TEXT/STXT chunk's plain bytes, CRLF normalised to LF."""
    return payload.decode("latin-1", errors="replace").replace("\r\n", "\n")


def decode_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Decode a single chunk's payload into a JSON-friendly dict."""
    kind = chunk["kind"]
    payload: bytes = chunk["bytes"]
    base: dict[str, Any] = {
        "kind": kind,
        "id": chunk["id"],
        "offset": chunk["offset"],
        "length": chunk["length"],
    }

    if kind == "CHAR":
        header = decode_rdff_header(payload)
        body = payload[10:]
        base["rdff_header"] = header
        base["body_length"] = len(body)
        base["body_hex_preview"] = hex_preview(body)
    elif kind == "PSIN":
        # gff_psin_t = uint8_t types[7].
        if len(payload) >= 7:
            base["types"] = list(payload[:7])
            if len(payload) > 7:
                base["trailing_hex"] = hex_preview(payload[7:])
        else:
            base["truncated"] = True
            base["raw_hex"] = hex_preview(payload)
    elif kind == "PSST":
        # gff_psionic_list_t = uint8_t psionics[34].
        if len(payload) >= 34:
            base["psionics"] = list(payload[:34])
            if len(payload) > 34:
                base["trailing_hex"] = hex_preview(payload[34:])
        else:
            base["truncated"] = True
            base["raw_hex"] = hex_preview(payload)
    elif kind in ("SPST", "CACT", "PREF", "GREQ"):
        base["raw_hex"] = hex_preview(payload, limit=128)
    elif kind == "TEXT":
        base["text"] = decode_text(payload)
    else:
        # Unknown chunk type: bytes only.
        base["raw_hex"] = hex_preview(payload, limit=128)

    return base


def summarise(parsed: dict[str, Any]) -> dict[str, Any]:
    """Build the final JSON-friendly summary."""
    chunks = [decode_chunk(c) for c in parsed["chunks"]]
    by_kind: dict[str, int] = {}
    for c in parsed["chunks"]:
        by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1
    return {
        "tool": "save-inspect",
        "version": VERSION,
        "file_size": parsed["file_size"],
        "header": parsed["header"],
        "chunks_by_kind": dict(sorted(by_kind.items())),
        "chunks": chunks,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="save-inspect", description=__doc__.strip().splitlines()[0]
    )
    p.add_argument("--version", action="version", version=f"save-inspect {VERSION}")
    p.add_argument("file", type=Path, help="path to CHARSAVE.GFF")
    p.add_argument(
        "-o", "--output", type=Path, default=None, help="write JSON to file (default stdout)"
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print JSON with 2-space indent",
    )
    args = p.parse_args(argv)

    try:
        parsed = parse_gff(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    summary = summarise(parsed)
    indent = 2 if args.pretty else None
    text = json.dumps(summary, indent=indent, ensure_ascii=False)

    if args.output is None or str(args.output) == "-":
        sys.stdout.write(text)
        sys.stdout.write("\n")
    else:
        args.output.write_text(text + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
