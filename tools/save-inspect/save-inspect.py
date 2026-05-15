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
    """Decode the 10-byte gff_rdff_header_t at the start of a record.

    Layout from dsoageofheroes/libgff include/gff/rdff.h
    `gff_rdff_header_t` (MIT). See CREDITS.md.
    """
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


# Enum lookups for ds_character_t fields.
# From dsoageofheroes/libgff include/gff/object.h enum gff_race_e (MIT).
RACE_NAMES = {
    0: "MONSTER",
    1: "HUMAN",
    2: "DWARF",
    3: "ELF",
    4: "HALFELF",
    5: "HALFGIANT",
    6: "HALFLING",
    7: "MUL",
    8: "THRIKREEN",
}

GENDER_NAMES = {0: "MALE", 1: "FEMALE"}

ALIGNMENT_NAMES = {
    0: "LAWFUL_GOOD",
    1: "NEUTRAL_GOOD",
    2: "CHAOTIC_GOOD",
    3: "LAWFUL_NEUTRAL",
    4: "TRUE_NEUTRAL",
    5: "CHAOTIC_NEUTRAL",
    6: "LAWFUL_EVIL",
    7: "NEUTRAL_EVIL",
    8: "CHAOTIC_EVIL",
}


def _name_enum(value: int, names: dict[int, str]) -> dict[str, Any]:
    """Wrap an enum integer with its name lookup."""
    out: dict[str, Any] = {"value": value}
    if value in names:
        out["name"] = names[value]
    return out


def _longest_ascii_run(body: bytes, min_len: int = 4) -> tuple[str | None, int]:
    """Find the longest printable-ASCII run of length >= `min_len`.
    Used as a fallback heuristic for spotting a character name
    inside a sub-block whose layout we haven't fully decoded.
    """
    best: tuple[int, int] | None = None
    start: int | None = None
    for i, b in enumerate(body):
        if 0x20 <= b <= 0x7E:
            if start is None:
                start = i
        else:
            if start is not None:
                length = i - start
                if length >= min_len and (best is None or length > best[1] - best[0]):
                    best = (start, i)
                start = None
    if start is not None:
        length = len(body) - start
        if length >= min_len and (best is None or length > best[1] - best[0]):
            best = (start, len(body))
    if best is None:
        return None, -1
    s = body[best[0] : best[1]].decode("latin-1", errors="replace")
    return s, best[0]


def _decode_combat(body: bytes) -> dict[str, Any]:
    """Decode a combat sub-block per `ds1_combat_t` (libgff
    `include/gff/object.h`, MIT).

    The libgff struct is DS1-flavored at 58 bytes. DS2 combat
    sub-blocks are 49 bytes with a different internal layout
    (the name field appears earlier; field offsets don't match).
    For DS2 we emit the body as opaque hex with a `_format` tag
    rather than producing wrong-looking stat values.
    """
    out: dict[str, Any] = {}
    n = len(body)
    if n < 56:
        # Heuristic: DS1 combat is 58 bytes; DS2 is 49. Anything
        # below ~56 is almost certainly the DS2 (or smaller)
        # variant whose layout we haven't fully RE'd.
        out["_format"] = "ds2_or_unknown_combat_layout"
        out["_note"] = (
            "combat sub-block is smaller than the DS1 ds1_combat_t "
            "(58 bytes); field decoding deferred. See "
            "docs/file-formats.md §2."
        )
        out["_raw_hex"] = body.hex()
        # Best-effort name extraction: scan for a printable ASCII
        # run, since the name field is somewhere in here.
        run, run_offset = _longest_ascii_run(body)
        if run:
            out["_likely_name"] = run
            out["_likely_name_offset"] = run_offset
        return out
    # The struct's layout via library headers (lengths in bytes):
    # i16 hp, psp, char_index, id, ready_item_index, weapon_index,
    # pack_index; u8[8] data_block; u8 special_attack,
    # special_defense; i16 icon; i8 ac; u8 move, status, allegiance,
    # data; i8 thac0; u8 priority, flags; ds_stats_t stats (6 bytes);
    # char name[18].
    fmt = "<7h8B2BhB5BB1B1B6BHHB"
    # That's hard to read; do it field by field for honesty.
    pos = 0

    def take(t: str, size: int) -> Any | None:
        nonlocal pos
        if pos + size > n:
            return None
        v = struct.unpack_from(t, body, pos)[0]
        pos += size
        return v

    def take_bytes(size: int) -> bytes | None:
        nonlocal pos
        if pos + size > n:
            return None
        v = body[pos : pos + size]
        pos += size
        return v

    for fname in ("hp", "psp", "char_index", "id", "ready_item_index",
                  "weapon_index", "pack_index"):
        v = take("<h", 2)
        if v is None:
            out["_truncated_at"] = fname
            return out
        out[fname] = v
    blk = take_bytes(8)
    if blk is None:
        out["_truncated_at"] = "data_block"
        return out
    out["data_block_hex"] = blk.hex()
    for fname in ("special_attack", "special_defense"):
        v = take("<B", 1)
        if v is None:
            out["_truncated_at"] = fname
            return out
        out[fname] = v
    v = take("<h", 2)
    if v is None:
        out["_truncated_at"] = "icon"
        return out
    out["icon"] = v
    v = take("<b", 1)
    if v is None:
        out["_truncated_at"] = "ac"
        return out
    out["ac"] = v
    for fname in ("move", "status", "allegiance", "data"):
        v = take("<B", 1)
        if v is None:
            out["_truncated_at"] = fname
            return out
        out[fname] = v
    v = take("<b", 1)
    if v is None:
        out["_truncated_at"] = "thac0"
        return out
    out["thac0"] = v
    for fname in ("priority", "flags"):
        v = take("<B", 1)
        if v is None:
            out["_truncated_at"] = fname
            return out
        out[fname] = v
    stats_bytes = take_bytes(6)
    if stats_bytes is None:
        out["_truncated_at"] = "stats"
        return out
    out["stats"] = {
        "str": stats_bytes[0],
        "dex": stats_bytes[1],
        "con": stats_bytes[2],
        "intel": stats_bytes[3],
        "wis": stats_bytes[4],
        "cha": stats_bytes[5],
    }
    name_bytes = take_bytes(18)
    if name_bytes is None:
        # No name field in this variant (DS2 49-byte combat ends here).
        # Leave name unset; trailing_hex captures any leftover.
        pass
    else:
        out["name"] = name_bytes.split(b"\x00", 1)[0].decode("latin-1", errors="replace")
    if pos < n:
        out["_trailing_hex"] = body[pos:].hex()
    return out


def _decode_character(body: bytes) -> dict[str, Any]:
    """Decode a character sub-block per `ds_character_t` (libgff
    `include/gff/object.h`, MIT). Best-effort.

    DS1 character = 71 bytes; the libgff struct computes to 72,
    so the trailing `palette` byte may not be present and we mark
    it absent on truncation. DS2 character = 66 bytes (stripped
    variant; field decoding may produce off-by-N values past the
    early fields).
    """
    out: dict[str, Any] = {}
    n = len(body)
    if n < 70:
        out["_format"] = "ds2_or_unknown_character_layout"
        out["_note"] = (
            "character sub-block is smaller than DS1's 71 bytes; "
            "DS2 (66 bytes) and other variants haven't been fully "
            "RE'd. See docs/file-formats.md §2."
        )
        out["_raw_hex"] = body.hex()
        return out
    pos = 0

    def take(t: str, size: int, key: str) -> bool:
        nonlocal pos
        if pos + size > n:
            out["_truncated_at"] = key
            return False
        v = struct.unpack_from(t, body, pos)[0]
        pos += size
        out[key] = v
        return True

    def take_bytes(size: int, key: str) -> bool:
        nonlocal pos
        if pos + size > n:
            out["_truncated_at"] = key
            return False
        out[key] = body[pos : pos + size].hex()
        pos += size
        return True

    if not take("<I", 4, "current_xp"):
        return out
    if not take("<I", 4, "high_xp"):
        return out
    if not take("<H", 2, "base_hp"):
        return out
    if not take("<H", 2, "high_hp"):
        return out
    if not take("<H", 2, "base_psp"):
        return out
    if not take("<H", 2, "id"):
        return out
    if not take_bytes(2, "_data1"):
        return out
    if not take("<H", 2, "legal_class"):
        return out
    if not take_bytes(4, "_data2"):
        return out
    # race
    if pos + 1 > n:
        out["_truncated_at"] = "race"
        return out
    out["race"] = _name_enum(body[pos], RACE_NAMES)
    pos += 1
    if pos + 1 > n:
        out["_truncated_at"] = "gender"
        return out
    out["gender"] = _name_enum(body[pos], GENDER_NAMES)
    pos += 1
    if pos + 1 > n:
        out["_truncated_at"] = "alignment"
        return out
    out["alignment"] = _name_enum(body[pos], ALIGNMENT_NAMES)
    pos += 1
    # stats (6 bytes)
    if pos + 6 > n:
        out["_truncated_at"] = "stats"
        return out
    out["stats"] = {
        "str": body[pos],
        "dex": body[pos + 1],
        "con": body[pos + 2],
        "intel": body[pos + 3],
        "wis": body[pos + 4],
        "cha": body[pos + 5],
    }
    pos += 6
    if pos + 3 > n:
        out["_truncated_at"] = "real_class"
        return out
    out["real_class"] = [
        struct.unpack_from("<b", body, pos + i)[0] for i in range(3)
    ]
    pos += 3
    if pos + 3 > n:
        out["_truncated_at"] = "level"
        return out
    out["level"] = list(body[pos : pos + 3])
    pos += 3
    if not take("<b", 1, "base_ac"):
        return out
    if not take("<B", 1, "base_move"):
        return out
    if not take("<B", 1, "magic_resistance"):
        return out
    if not take("<B", 1, "num_blows"):
        return out
    if pos + 3 > n:
        out["_truncated_at"] = "num_attacks"
        return out
    out["num_attacks"] = list(body[pos : pos + 3])
    pos += 3
    if pos + 3 > n:
        out["_truncated_at"] = "num_dice"
        return out
    out["num_dice"] = list(body[pos : pos + 3])
    pos += 3
    if pos + 3 > n:
        out["_truncated_at"] = "num_sides"
        return out
    out["num_sides"] = list(body[pos : pos + 3])
    pos += 3
    if pos + 3 > n:
        out["_truncated_at"] = "num_bonuses"
        return out
    out["num_bonuses"] = list(body[pos : pos + 3])
    pos += 3
    if pos + 5 > n:
        out["_truncated_at"] = "saving_throw"
        return out
    st = body[pos : pos + 5]
    out["saving_throw"] = {
        "paralysis": st[0],
        "wand": st[1],
        "petrify": st[2],
        "breath": st[3],
        "spell": st[4],
    }
    pos += 5
    for key in ("allegiance", "size", "spell_group"):
        if not take("<B", 1, key):
            return out
    if pos + 3 > n:
        out["_truncated_at"] = "high_level"
        return out
    out["high_level"] = list(body[pos : pos + 3])
    pos += 3
    if not take("<H", 2, "sound_fx"):
        return out
    if not take("<H", 2, "attack_sound"):
        return out
    if not take("<B", 1, "psi_group"):
        return out
    if not take("<B", 1, "palette"):
        return out
    if pos < n:
        out["_trailing_hex"] = body[pos:].hex()
    return out


# Slot enum from libgff include/gff/item.h.
ITEM_SLOT_NAMES = {
    0: "ARM",
    1: "AMMO",
    2: "MISSILE",
    3: "HAND0",
    4: "FINGER0",
    5: "WAIST",
    6: "LEGS",
    7: "HEAD",
    8: "NECK",
    9: "CHEST",
    10: "HAND1",
    11: "FINGER1",
    12: "CLOAK",
    13: "FOOT",
}


def _decode_item(body: bytes) -> dict[str, Any]:
    """Decode an item sub-block per `ds1_item_t` (libgff
    `include/gff/item.h`, MIT; "Not confirmed at all" per the
    upstream comment). Best-effort with libgff annotations.

    DS1 item sub-blocks are 21 bytes; DS2 item sub-blocks are 23.
    The libgff struct computes to 23 (DS2 fit). For DS1, the
    trailing 2 bytes (`priority` + `data0`) will be `_truncated_at`.
    """
    out: dict[str, Any] = {}
    n = len(body)
    pos = 0

    def take(t: str, size: int, key: str) -> bool:
        nonlocal pos
        if pos + size > n:
            out["_truncated_at"] = key
            return False
        v = struct.unpack_from(t, body, pos)[0]
        pos += size
        out[key] = v
        return True

    if not take("<h", 2, "id"):
        return out
    if not take("<H", 2, "quantity"):
        return out
    if not take("<h", 2, "next"):
        return out
    if not take("<H", 2, "value"):
        return out
    if not take("<h", 2, "pack_index"):
        return out
    if not take("<h", 2, "item_index"):
        return out
    if not take("<h", 2, "icon"):
        return out
    if not take("<H", 2, "charges"):
        return out
    if not take("<B", 1, "special"):
        return out
    # slot
    if pos + 1 > n:
        out["_truncated_at"] = "slot"
        return out
    out["slot"] = _name_enum(body[pos], ITEM_SLOT_NAMES)
    pos += 1
    if not take("<B", 1, "name_idx"):
        return out
    if not take("<b", 1, "bonus"):
        return out
    if not take("<H", 2, "priority"):
        return out
    if not take("<b", 1, "data0"):
        return out
    if pos < n:
        out["_trailing_hex"] = body[pos:].hex()
    return out


def decode_char_body(payload: bytes) -> dict[str, Any]:
    """Walk the RDFF sub-blocks of a CHAR chunk and dispatch each
    to its decoder (combat / character / item).

    Layout per libsoloscuro `src/entity.c` `sol_entity_load_from_gff`
    (MIT): the chunk is `[RDFF + combat] [RDFF + char]
    [RDFF + item] * (blocknum - 2)`, optionally followed by an
    `RDFF_END` terminator (`load_action == -1`, `len == 0`). The
    first sub-block's `blocknum` gives the total count (excluding
    the terminator).
    """
    result: dict[str, Any] = {"sub_blocks": []}
    pos = 0
    sub_idx = 0
    total_expected: int | None = None

    while pos + 10 <= len(payload):
        header_bytes = payload[pos : pos + 10]
        header = decode_rdff_header(header_bytes)
        body_offset = pos + 10
        body_len = header.get("len", 0)
        body_end = body_offset + body_len

        if header.get("load_action") == -1:
            # RDFF_END terminator.
            result["sub_blocks"].append(
                {"index": sub_idx, "offset": pos, "rdff_header": header, "terminator": True}
            )
            pos = body_end
            sub_idx += 1
            break

        if total_expected is None:
            total_expected = header.get("blocknum")
            result["expected_sub_block_count"] = total_expected

        if body_end > len(payload):
            result["sub_blocks"].append(
                {
                    "index": sub_idx,
                    "offset": pos,
                    "rdff_header": header,
                    "_truncated": True,
                }
            )
            break

        body = payload[body_offset:body_end]
        # Positional dispatch matches libsoloscuro's reader:
        #   sub[0] = combat, sub[1] = character, sub[2..] = items.
        role: str
        decoded: dict[str, Any]
        if sub_idx == 0:
            role = "combat"
            decoded = _decode_combat(body)
        elif sub_idx == 1:
            role = "character"
            decoded = _decode_character(body)
        else:
            role = "item"
            decoded = _decode_item(body)

        result["sub_blocks"].append(
            {
                "index": sub_idx,
                "offset": pos,
                "role": role,
                "rdff_header": header,
                "decoded": decoded,
            }
        )
        pos = body_end
        sub_idx += 1
        if total_expected is not None and sub_idx >= total_expected:
            # Stop here; there may still be a terminator sub-block
            # but we won't require it.
            if pos + 10 <= len(payload):
                term = decode_rdff_header(payload[pos : pos + 10])
                if term.get("load_action") == -1:
                    result["sub_blocks"].append(
                        {
                            "index": sub_idx,
                            "offset": pos,
                            "rdff_header": term,
                            "terminator": True,
                        }
                    )
                    pos += 10 + term.get("len", 0)
                    sub_idx += 1
            break

    result["bytes_consumed"] = pos
    result["bytes_total"] = len(payload)
    if pos < len(payload):
        result["_trailing_hex"] = payload[pos:].hex()
    return result


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
        # The leading 10 bytes are the same RDFF header v0.1.0
        # surfaced; keep it so existing consumers don't break.
        header = decode_rdff_header(payload)
        base["rdff_header"] = header
        base["body_length"] = len(payload) - 10
        base["body_hex_preview"] = hex_preview(payload[10:])
        # New in v0.2.0: walk the sub-blocks (combat / character /
        # items) per libsoloscuro's reader. Best-effort: each
        # decoder is bounded by its sub-block's rdff.len.
        base["body"] = decode_char_body(payload)
    elif kind == "PSIN":
        # gff_psin_t = uint8_t types[7] — dsoageofheroes/libgff
        # include/gff/psionic.h (MIT). See CREDITS.md.
        if len(payload) >= 7:
            base["types"] = list(payload[:7])
            if len(payload) > 7:
                base["trailing_hex"] = hex_preview(payload[7:])
        else:
            base["truncated"] = True
            base["raw_hex"] = hex_preview(payload)
    elif kind == "PSST":
        # gff_psionic_list_t = uint8_t psionics[34] —
        # dsoageofheroes/libgff include/gff/psionic.h (MIT).
        # See CREDITS.md.
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
