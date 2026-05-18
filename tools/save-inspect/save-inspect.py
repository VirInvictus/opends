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


def _decode_combat_ds2(body: bytes) -> dict[str, Any]:
    """Decode the DS2 49-byte combat sub-block.

    Layout (empirically locked across all 19 CHAR records in
    `.games/ds2/__support/save/CHARSAVE.GFF`; field semantics
    for the prefix come from libgff's `ds1_combat_t`, the rest
    from inspection):

    | Offset | Size | Field |
    |--------|------|-------|
    | 0..1   | i16  | hp |
    | 2..3   | i16  | psp |
    | 4..5   | i16  | char_index |
    | 6..7   | i16  | id |
    | 8..9   | i16  | ready_item_index |
    | 10..11 | i16  | weapon_index |
    | 12..13 | i16  | pack_index |
    | 14..21 | u8[8]| data_block (opaque combat-state bytes) |
    | 22     | u8   | special_attack |
    | 23     | u8   | special_defense |
    | 24     | u8   | _reserved_0 (always 0x00 observed) |
    | 25..30 | u8[6]| stats (str, dex, con, int, wis, cha) |
    | 31     | u8   | _slot_31 (varies, low values; semantics open) |
    | 32     | u8   | _reserved_1 (always 0x00 observed) |
    | 33..48 | char[16] | name (NUL-padded) |

    Bytes 24, 31, and 32 are the three positions whose semantics
    haven't been pinned down. 24 and 32 are uniformly 0x00 across
    the corpus (likely padding / reserved). Byte 31 takes a small
    range (0..6 observed) and is probably an alignment / class /
    flags byte. Documented as `_slot_31` until DSUN.EXE RE
    confirms the meaning.
    """
    out: dict[str, Any] = {"_format": "ds2_combat"}
    (
        out["hp"],
        out["psp"],
        out["char_index"],
        out["id"],
        out["ready_item_index"],
        out["weapon_index"],
        out["pack_index"],
    ) = struct.unpack_from("<7h", body, 0)
    out["data_block_hex"] = body[14:22].hex()
    out["special_attack"] = body[22]
    out["special_defense"] = body[23]
    out["_reserved_0"] = body[24]
    out["stats"] = {
        "str": body[25],
        "dex": body[26],
        "con": body[27],
        "intel": body[28],
        "wis": body[29],
        "cha": body[30],
    }
    out["_slot_31"] = body[31]
    out["_reserved_1"] = body[32]
    out["name"] = body[33:49].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    # Real saves leave non-zero garbage in the name field's trailing
    # bytes (the engine doesn't always zero the buffer between writes).
    # Preserve those bytes verbatim so encode→decode round-trips
    # byte-identically when the user hasn't edited `name`.
    out["_name_raw_hex"] = body[33:49].hex()
    return out


def _decode_combat(body: bytes) -> dict[str, Any]:
    """Decode a combat sub-block.

    DS1's `ds1_combat_t` (libgff `include/gff/object.h`, MIT) is
    58 bytes. DS2 ships a 49-byte variant that drops 9 bytes
    compared to DS1: shorter name (16 vs 18), no `icon` /
    `ac` / 3-of-4 of move/status/allegiance/data. Stats land
    earlier in the record (offset 25 vs offset 34 in DS1).

    The DS1-shared 24-byte prefix matches byte-for-byte between
    DS1 and DS2 (hp, psp, char_index, id, ready_item_index,
    weapon_index, pack_index, data_block[8], special_attack,
    special_defense). v0.4.0 extends the DS2 decode beyond the
    prefix with a structured field map derived from inspecting
    every CHAR sub-block in DS1 and DS2 GOG 1.10. See
    `docs/file-formats.md` §2 for the full layout.
    """
    out: dict[str, Any] = {}
    n = len(body)
    if n == 49:
        return _decode_combat_ds2(body)
    if n < 56:
        # Smaller than DS1's 58 and not the known DS2 49: unknown
        # variant. Emit opaque + the shared 24-byte prefix.
        out["_format"] = "ds2_or_unknown_combat_layout"
        out["_note"] = (
            f"combat sub-block size {n} doesn't match DS1's 58 or "
            "DS2's 49; emitting the DS1-shared 24-byte prefix and "
            "the body as opaque hex."
        )
        out["_raw_hex"] = body.hex()
        if n >= 24:
            (
                out["hp"],
                out["psp"],
                out["char_index"],
                out["id"],
                out["ready_item_index"],
                out["weapon_index"],
                out["pack_index"],
            ) = struct.unpack_from("<7h", body, 0)
            out["data_block_hex"] = body[14:22].hex()
            out["special_attack"] = body[22]
            out["special_defense"] = body[23]
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
        # Preserve trailing-garbage bytes for round-trip fidelity
        # (the engine doesn't always zero the name buffer).
        out["_name_raw_hex"] = name_bytes.hex()
    if pos < n:
        out["_trailing_hex"] = body[pos:].hex()
    return out


def _decode_character_ds2(body: bytes) -> dict[str, Any]:
    """Decode the DS2 66-byte character sub-block.

    DS2 ships a stripped variant of DS1's `ds_character_t`. The
    layout was recovered empirically by comparing every CHAR
    record in DS1 and DS2 `CHARSAVE.GFF` side-by-side. DS2 saves
    6 bytes vs DS1's 72-byte (with-palette) layout by dropping
    `_data2` (4 bytes) and two of `(race, gender, alignment)`
    (2 bytes), keeping a single pre-stats byte that pattern-
    matches DS1's `alignment` field.

    | Offset | Size | Field | Notes |
    |--------|------|-------|-------|
    | 0..3   | u32  | current_xp | Matches DS1. |
    | 4..7   | u32  | high_xp | Matches DS1. |
    | 8..9   | u16  | base_hp | Matches combat's `hp`. |
    | 10..11 | u16  | high_hp | |
    | 12..13 | u16  | base_psp | Matches combat's `psp`. |
    | 14..15 | u16  | id | Matches combat's `id`. |
    | 16..17 | 2 B  | _data1 | Opaque, matches DS1's `_data1`. |
    | 18..19 | u16  | legal_class | |
    | 20     | u8   | alignment | DS2-shape match against DS1[26]. |
    | 21..26 | u8[6]| stats | str/dex/con/intel/wis/cha. |
    | 27..29 | i8[3]| real_class | -1 = empty slot. |
    | 30..32 | u8[3]| level | |
    | 33     | i8   | base_ac | |
    | 34     | u8   | base_move | |
    | 35     | u8   | magic_resistance | |
    | 36     | u8   | num_blows | |
    | 37..39 | u8[3]| num_attacks | |
    | 40..42 | u8[3]| num_dice | |
    | 43..45 | u8[3]| num_sides | |
    | 46..48 | u8[3]| num_bonuses | |
    | 49..53 | u8[5]| saving_throw | paralysis/wand/petrify/breath/spell. |
    | 54     | u8   | allegiance | |
    | 55     | u8   | size | |
    | 56     | u8   | spell_group | |
    | 57..59 | u8[3]| high_level | |
    | 60..61 | u16  | sound_fx | |
    | 62..63 | u16  | attack_sound | |
    | 64     | u8   | psi_group | |
    | 65     | u8   | palette | Always present (DS1's optional 72nd byte). |
    """
    out: dict[str, Any] = {"_format": "ds2_character"}
    (
        out["current_xp"],
        out["high_xp"],
    ) = struct.unpack_from("<II", body, 0)
    (
        out["base_hp"],
        out["high_hp"],
        out["base_psp"],
        out["id"],
    ) = struct.unpack_from("<HHHH", body, 8)
    out["_data1"] = body[16:18].hex()
    out["legal_class"] = struct.unpack_from("<H", body, 18)[0]
    out["alignment"] = _name_enum(body[20], ALIGNMENT_NAMES)
    out["stats"] = {
        "str": body[21],
        "dex": body[22],
        "con": body[23],
        "intel": body[24],
        "wis": body[25],
        "cha": body[26],
    }
    out["real_class"] = [
        struct.unpack_from("<b", body, 27 + i)[0] for i in range(3)
    ]
    out["level"] = list(body[30:33])
    out["base_ac"] = struct.unpack_from("<b", body, 33)[0]
    out["base_move"] = body[34]
    out["magic_resistance"] = body[35]
    out["num_blows"] = body[36]
    out["num_attacks"] = list(body[37:40])
    out["num_dice"] = list(body[40:43])
    out["num_sides"] = list(body[43:46])
    out["num_bonuses"] = list(body[46:49])
    out["saving_throw"] = {
        "paralysis": body[49],
        "wand": body[50],
        "petrify": body[51],
        "breath": body[52],
        "spell": body[53],
    }
    out["allegiance"] = body[54]
    out["size"] = body[55]
    out["spell_group"] = body[56]
    out["high_level"] = list(body[57:60])
    out["sound_fx"] = struct.unpack_from("<H", body, 60)[0]
    out["attack_sound"] = struct.unpack_from("<H", body, 62)[0]
    out["psi_group"] = body[64]
    out["palette"] = body[65]
    return out


def _decode_character(body: bytes) -> dict[str, Any]:
    """Decode a character sub-block per `ds_character_t` (libgff
    `include/gff/object.h`, MIT). Best-effort.

    DS1 character = 71 bytes; the libgff struct computes to 72,
    so the trailing `palette` byte may not be present and we mark
    it absent on truncation. DS2 character = 66 bytes (stripped
    variant of DS1; see `_decode_character_ds2`).
    """
    out: dict[str, Any] = {}
    n = len(body)
    if n == 66:
        return _decode_character_ds2(body)
    if n < 70:
        out["_format"] = "ds2_or_unknown_character_layout"
        out["_note"] = (
            f"character sub-block size {n} doesn't match DS1's 71 / 72 "
            "or DS2's 66; emitting as opaque hex."
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
    `include/gff/item.h`, MIT).

    DS1 item sub-blocks are 21 bytes; DS2 item sub-blocks are 23.
    libgff's struct computes to 23 and the field layout matches
    DS2's wire format byte-for-byte (confirmed v0.6.0 against
    every item in a played `CHARSAVE.GFF` from the `ds2-smoke`
    `--play` session: 27 items on the heaviest-inventory NPC,
    all 23-byte aligned, every field through `data0` reads
    cleanly). DS1 truncates at the trailing `priority` +
    `data0` pair (which the upstream comment flags as "Not
    confirmed at all"; for DS1 they aren't there).
    """
    out: dict[str, Any] = {}
    n = len(body)
    if n == 23:
        out["_format"] = "ds2_item"
    elif n == 21:
        out["_format"] = "ds1_item"
    pos = 0

    def take(t: str, size: int, key: str) -> bool:
        nonlocal pos
        if pos + size > n:
            out["_truncated_at"] = key
            # Capture remaining bytes so encoders can re-emit them.
            # Without this, DS1 21-byte items (which truncate at the
            # 2-byte `priority` field at pos=20 with 1 byte left)
            # lose that byte on round-trip.
            if pos < n:
                out["_trailing_hex"] = body[pos:].hex()
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


def decode_stxt(payload: bytes) -> dict[str, Any]:
    """Decode a STXT chunk: in DARKRUN.GFF this is the save name
    (the user's "FUCK" / "Brundle" / etc.). Stored as a null-
    terminated ASCII string padded with zero bytes to a fixed
    chunk length. Pull the leading text up to the first null;
    everything after is padding.
    """
    end = payload.find(b"\x00")
    name = payload[:end] if end >= 0 else payload
    out: dict[str, Any] = {
        "_format": "stxt_save_name",
        "name": name.decode("ascii", errors="replace"),
        "length_used": len(name),
        "length_total": len(payload),
    }
    return out


def decode_save_chunk(chunk_id: int, payload: bytes) -> dict[str, Any]:
    """Decode a SAVE chunk inside DARKRUN.GFF.

    SAVE chunks are per-region world state: entity positions, NPC
    activity, trigger flags, quest progression. The engine writes
    ~60 of them per saved game. No public schema; v0.7.0 surfaces
    the structural shape we know (chunk-id-keyed; small ids carry
    fixed-size scalars; large ids carry per-region or per-party
    blobs) and leaves the body as opaque hex pending empirical RE.

    What we do know after one DS1 played save vs the factory:
      - Chunk id 1 (largest, ~10 KB) carries the party / PC data.
      - Chunk ids 10-17 are exactly 2 bytes (u16 LE) each. They
        store small counters or coordinates; values vary per save.
      - Chunk id 18 is a 51-byte boolean array (all 0x01 in the
        sample save: 51 region-visited flags?).
      - The remaining ids span 100 bytes to a few KB and almost
        certainly hold per-region world state. Field semantics
        TBD; ship as opaque hex so downstream consumers see the
        bytes without making up structure.

    Per-game tag: v0.7.0 ships only `_format: ds1_save_chunk`.
    DS2 likely shares the wire format (the engine code is the
    same shape per `docs/dso-symbols.md`) but we have no played
    DS2 sample to verify. The tag is updated to `ds2_save_chunk`
    or split into two variants once that data exists.
    """
    out: dict[str, Any] = {
        "_format": "ds1_save_chunk",
        "chunk_id": chunk_id,
        "byte_length": len(payload),
    }
    if len(payload) == 2:
        # The id 10-17 family: each is a single u16 LE scalar.
        out["u16_value"] = int.from_bytes(payload, "little")
    out["raw_hex"] = hex_preview(payload, limit=128)
    # Full bytes for round-trip; the truncated raw_hex above stays
    # for human inspection. Necessary because SAVE chunks can be
    # 10 KB and the truncation would lose the tail on re-encode.
    out["_raw_bytes_hex"] = payload.hex()
    return out


def decode_etme(payload: bytes) -> dict[str, Any]:
    """Decode an ETME chunk: the engine-template-metadata block
    that DARKRUN / DARKSAVE both ship. ASCII text with comments
    (`;` lines) describing the file's expected GFS layout. Not
    semantically meaningful for modders; surfaced as text so the
    JSON output is readable.
    """
    return {
        "_format": "etme_template_text",
        "text": decode_text(payload),
        "byte_length": len(payload),
    }


def decode_etab(payload: bytes) -> dict[str, Any]:
    """Decode an ETAB chunk: the engine's entity table. In
    DARKRUN.GFF the ETAB chunk is consistently 10000 bytes wide
    and mostly zero in newly-played saves; the cells fill in
    as entities spawn into the active region. Schema is part of
    the DARKRUN-side RE thread that v0.7.0 doesn't crack; surface
    as opaque hex with a tag.
    """
    out: dict[str, Any] = {
        "_format": "etab_entity_table",
        "byte_length": len(payload),
        "raw_hex": hex_preview(payload, limit=128),
        "_raw_bytes_hex": payload.hex(),
    }
    # Cheap fingerprint: how many leading zero bytes? Newly-started
    # games have huge zero runs; deep into a playthrough this
    # drops. Surface as a one-number anomaly check.
    leading_zeros = 0
    for b in payload:
        if b == 0:
            leading_zeros += 1
        else:
            break
    out["leading_zero_bytes"] = leading_zeros
    return out


# ---------- encoders (v0.8.0) ----------
#
# Each `_encode_X` is the inverse of `_decode_X`. The invariant
# every encoder upholds: bytes produced have length equal to the
# original sub-block's wire length, so the rdff_header `len` field
# stays unchanged on re-encode. Decoded fields with a known type
# (i16, u8, char[N]) flow back through the inverse `struct.pack`;
# `_raw_hex` and `*_hex` keys flow back through `bytes.fromhex`;
# enum dicts (`{"value": N, "name": "X"}`) extract `value`.
#
# Each encoder raises `EncodeError` on a missing required field or
# a value out of range. The errors surface to the user as part of
# the schema-validation pass before any write touches disk.


class EncodeError(ValueError):
    """Raised when a decoded JSON record can't be re-encoded.

    The message names the path that failed (e.g.
    `chunk CHAR/29 / character / stats.str: expected u8, got 999`)
    so a hand-edited JSON's typos surface with line-of-sight to
    the offending key.
    """


def _enum_value(v: Any) -> int:
    """Extract the integer from a `_name_enum` dict, or pass an int
    through. Used by encoders for fields like `alignment` / `slot`
    that the decoder wraps as `{"value": N, "name": "X"}`."""
    if isinstance(v, dict):
        return int(v["value"])
    return int(v)


def _pack_u8(v: int, ctx: str) -> bytes:
    if not (0 <= v <= 255):
        raise EncodeError(f"{ctx}: expected u8 in 0..255, got {v}")
    return bytes([v])


def _pack_i8(v: int, ctx: str) -> bytes:
    if not (-128 <= v <= 127):
        raise EncodeError(f"{ctx}: expected i8 in -128..127, got {v}")
    return struct.pack("<b", v)


def _pack_u16(v: int, ctx: str) -> bytes:
    if not (0 <= v <= 0xFFFF):
        raise EncodeError(f"{ctx}: expected u16 in 0..65535, got {v}")
    return struct.pack("<H", v)


def _pack_i16(v: int, ctx: str) -> bytes:
    if not (-32768 <= v <= 32767):
        raise EncodeError(f"{ctx}: expected i16, got {v}")
    return struct.pack("<h", v)


def _pack_u32(v: int, ctx: str) -> bytes:
    if not (0 <= v <= 0xFFFFFFFF):
        raise EncodeError(f"{ctx}: expected u32, got {v}")
    return struct.pack("<I", v)


def _pack_name(name: str, length: int, ctx: str) -> bytes:
    """Pack a name string into a fixed-length NUL-padded buffer."""
    raw = name.encode("latin-1", errors="replace")
    if len(raw) > length:
        raise EncodeError(
            f"{ctx}: name {name!r} is {len(raw)} bytes, max {length}"
        )
    return raw.ljust(length, b"\x00")


def _pack_hex(hex_str: str, expected_len: int | None, ctx: str) -> bytes:
    try:
        out = bytes.fromhex(hex_str)
    except ValueError as e:
        raise EncodeError(f"{ctx}: bad hex string: {e}")
    if expected_len is not None and len(out) != expected_len:
        raise EncodeError(
            f"{ctx}: expected {expected_len} bytes from hex, got {len(out)}"
        )
    return out


def _encode_stats(stats: dict[str, Any], ctx: str) -> bytes:
    """Pack the 6-byte stats array in canonical str/dex/con/int/wis/cha order."""
    out = bytearray(6)
    for i, key in enumerate(("str", "dex", "con", "intel", "wis", "cha")):
        if key not in stats:
            raise EncodeError(f"{ctx}: stats.{key} missing")
        out[i:i+1] = _pack_u8(int(stats[key]), f"{ctx}/stats.{key}")
    return bytes(out)


def _encode_saving_throw(st: dict[str, Any], ctx: str) -> bytes:
    out = bytearray(5)
    for i, key in enumerate(("paralysis", "wand", "petrify", "breath", "spell")):
        if key not in st:
            raise EncodeError(f"{ctx}: saving_throw.{key} missing")
        out[i:i+1] = _pack_u8(int(st[key]), f"{ctx}/saving_throw.{key}")
    return bytes(out)


def _encode_combat_ds2(d: dict[str, Any], ctx: str) -> bytes:
    out = bytearray(49)
    out[0:14] = struct.pack(
        "<7h",
        int(d["hp"]), int(d["psp"]), int(d["char_index"]),
        int(d["id"]), int(d["ready_item_index"]),
        int(d["weapon_index"]), int(d["pack_index"]),
    )
    out[14:22] = _pack_hex(d["data_block_hex"], 8, f"{ctx}/data_block_hex")
    out[22:23] = _pack_u8(int(d["special_attack"]), f"{ctx}/special_attack")
    out[23:24] = _pack_u8(int(d["special_defense"]), f"{ctx}/special_defense")
    out[24:25] = _pack_u8(int(d.get("_reserved_0", 0)), f"{ctx}/_reserved_0")
    out[25:31] = _encode_stats(d["stats"], ctx)
    out[31:32] = _pack_u8(int(d.get("_slot_31", 0)), f"{ctx}/_slot_31")
    out[32:33] = _pack_u8(int(d.get("_reserved_1", 0)), f"{ctx}/_reserved_1")
    # Prefer `_name_raw_hex` when present (preserves engine
    # garbage in the trailing padding bytes for byte-identical
    # round-trip). Falls back to null-padded `name` when the
    # user has edited the field and removed the raw-hex tag.
    if "_name_raw_hex" in d:
        out[33:49] = _pack_hex(d["_name_raw_hex"], 16, f"{ctx}/_name_raw_hex")
    else:
        out[33:49] = _pack_name(d.get("name", ""), 16, f"{ctx}/name")
    return bytes(out)


def _encode_combat(d: dict[str, Any], ctx: str) -> bytes:
    """Encode a combat sub-block. Dispatches by `_format` tag (or
    by `_raw_hex` fallback for unknown variants).
    """
    fmt = d.get("_format")
    if fmt == "ds2_combat":
        return _encode_combat_ds2(d, ctx)
    if "_raw_hex" in d:
        return _pack_hex(d["_raw_hex"], None, f"{ctx}/_raw_hex")
    # DS1: 58 bytes.
    out = bytearray()
    out.extend(struct.pack(
        "<7h",
        int(d["hp"]), int(d["psp"]), int(d["char_index"]),
        int(d["id"]), int(d["ready_item_index"]),
        int(d["weapon_index"]), int(d["pack_index"]),
    ))
    out.extend(_pack_hex(d["data_block_hex"], 8, f"{ctx}/data_block_hex"))
    out.extend(_pack_u8(int(d["special_attack"]), f"{ctx}/special_attack"))
    out.extend(_pack_u8(int(d["special_defense"]), f"{ctx}/special_defense"))
    out.extend(_pack_i16(int(d["icon"]), f"{ctx}/icon"))
    out.extend(_pack_i8(int(d["ac"]), f"{ctx}/ac"))
    for key in ("move", "status", "allegiance", "data"):
        out.extend(_pack_u8(int(d[key]), f"{ctx}/{key}"))
    out.extend(_pack_i8(int(d["thac0"]), f"{ctx}/thac0"))
    for key in ("priority", "flags"):
        out.extend(_pack_u8(int(d[key]), f"{ctx}/{key}"))
    out.extend(_encode_stats(d["stats"], ctx))
    # Same name-padding preservation as the DS2 path.
    if "_name_raw_hex" in d:
        out.extend(_pack_hex(d["_name_raw_hex"], 18, f"{ctx}/_name_raw_hex"))
    elif "name" in d:
        out.extend(_pack_name(d["name"], 18, f"{ctx}/name"))
    if "_trailing_hex" in d:
        out.extend(_pack_hex(d["_trailing_hex"], None, f"{ctx}/_trailing_hex"))
    return bytes(out)


def _encode_character_ds2(d: dict[str, Any], ctx: str) -> bytes:
    out = bytearray(66)
    struct.pack_into("<II", out, 0, int(d["current_xp"]), int(d["high_xp"]))
    struct.pack_into(
        "<HHHH", out, 8,
        int(d["base_hp"]), int(d["high_hp"]),
        int(d["base_psp"]), int(d["id"]),
    )
    out[16:18] = _pack_hex(d["_data1"], 2, f"{ctx}/_data1")
    out[18:20] = _pack_u16(int(d["legal_class"]), f"{ctx}/legal_class")
    out[20:21] = _pack_u8(_enum_value(d["alignment"]), f"{ctx}/alignment")
    out[21:27] = _encode_stats(d["stats"], ctx)
    for i in range(3):
        out[27 + i : 28 + i] = _pack_i8(int(d["real_class"][i]), f"{ctx}/real_class[{i}]")
    for i in range(3):
        out[30 + i : 31 + i] = _pack_u8(int(d["level"][i]), f"{ctx}/level[{i}]")
    out[33:34] = _pack_i8(int(d["base_ac"]), f"{ctx}/base_ac")
    out[34:35] = _pack_u8(int(d["base_move"]), f"{ctx}/base_move")
    out[35:36] = _pack_u8(int(d["magic_resistance"]), f"{ctx}/magic_resistance")
    out[36:37] = _pack_u8(int(d["num_blows"]), f"{ctx}/num_blows")
    for i in range(3):
        out[37 + i : 38 + i] = _pack_u8(int(d["num_attacks"][i]), f"{ctx}/num_attacks[{i}]")
    for i in range(3):
        out[40 + i : 41 + i] = _pack_u8(int(d["num_dice"][i]), f"{ctx}/num_dice[{i}]")
    for i in range(3):
        out[43 + i : 44 + i] = _pack_u8(int(d["num_sides"][i]), f"{ctx}/num_sides[{i}]")
    for i in range(3):
        out[46 + i : 47 + i] = _pack_u8(int(d["num_bonuses"][i]), f"{ctx}/num_bonuses[{i}]")
    out[49:54] = _encode_saving_throw(d["saving_throw"], ctx)
    out[54:55] = _pack_u8(int(d["allegiance"]), f"{ctx}/allegiance")
    out[55:56] = _pack_u8(int(d["size"]), f"{ctx}/size")
    out[56:57] = _pack_u8(int(d["spell_group"]), f"{ctx}/spell_group")
    for i in range(3):
        out[57 + i : 58 + i] = _pack_u8(int(d["high_level"][i]), f"{ctx}/high_level[{i}]")
    out[60:62] = _pack_u16(int(d["sound_fx"]), f"{ctx}/sound_fx")
    out[62:64] = _pack_u16(int(d["attack_sound"]), f"{ctx}/attack_sound")
    out[64:65] = _pack_u8(int(d["psi_group"]), f"{ctx}/psi_group")
    out[65:66] = _pack_u8(int(d["palette"]), f"{ctx}/palette")
    return bytes(out)


def _encode_character(d: dict[str, Any], ctx: str) -> bytes:
    fmt = d.get("_format")
    if fmt == "ds2_character":
        return _encode_character_ds2(d, ctx)
    if "_raw_hex" in d:
        return _pack_hex(d["_raw_hex"], None, f"{ctx}/_raw_hex")
    # DS1: 71 or 72 bytes (palette optional).
    out = bytearray()
    out.extend(_pack_u32(int(d["current_xp"]), f"{ctx}/current_xp"))
    out.extend(_pack_u32(int(d["high_xp"]), f"{ctx}/high_xp"))
    out.extend(_pack_u16(int(d["base_hp"]), f"{ctx}/base_hp"))
    out.extend(_pack_u16(int(d["high_hp"]), f"{ctx}/high_hp"))
    out.extend(_pack_u16(int(d["base_psp"]), f"{ctx}/base_psp"))
    out.extend(_pack_u16(int(d["id"]), f"{ctx}/id"))
    out.extend(_pack_hex(d["_data1"], 2, f"{ctx}/_data1"))
    out.extend(_pack_u16(int(d["legal_class"]), f"{ctx}/legal_class"))
    out.extend(_pack_hex(d["_data2"], 4, f"{ctx}/_data2"))
    out.extend(_pack_u8(_enum_value(d["race"]), f"{ctx}/race"))
    out.extend(_pack_u8(_enum_value(d["gender"]), f"{ctx}/gender"))
    out.extend(_pack_u8(_enum_value(d["alignment"]), f"{ctx}/alignment"))
    out.extend(_encode_stats(d["stats"], ctx))
    for i in range(3):
        out.extend(_pack_i8(int(d["real_class"][i]), f"{ctx}/real_class[{i}]"))
    for i in range(3):
        out.extend(_pack_u8(int(d["level"][i]), f"{ctx}/level[{i}]"))
    out.extend(_pack_i8(int(d["base_ac"]), f"{ctx}/base_ac"))
    out.extend(_pack_u8(int(d["base_move"]), f"{ctx}/base_move"))
    out.extend(_pack_u8(int(d["magic_resistance"]), f"{ctx}/magic_resistance"))
    out.extend(_pack_u8(int(d["num_blows"]), f"{ctx}/num_blows"))
    for i in range(3):
        out.extend(_pack_u8(int(d["num_attacks"][i]), f"{ctx}/num_attacks[{i}]"))
    for i in range(3):
        out.extend(_pack_u8(int(d["num_dice"][i]), f"{ctx}/num_dice[{i}]"))
    for i in range(3):
        out.extend(_pack_u8(int(d["num_sides"][i]), f"{ctx}/num_sides[{i}]"))
    for i in range(3):
        out.extend(_pack_u8(int(d["num_bonuses"][i]), f"{ctx}/num_bonuses[{i}]"))
    out.extend(_encode_saving_throw(d["saving_throw"], ctx))
    for key in ("allegiance", "size", "spell_group"):
        out.extend(_pack_u8(int(d[key]), f"{ctx}/{key}"))
    for i in range(3):
        out.extend(_pack_u8(int(d["high_level"][i]), f"{ctx}/high_level[{i}]"))
    out.extend(_pack_u16(int(d["sound_fx"]), f"{ctx}/sound_fx"))
    out.extend(_pack_u16(int(d["attack_sound"]), f"{ctx}/attack_sound"))
    out.extend(_pack_u8(int(d["psi_group"]), f"{ctx}/psi_group"))
    if "palette" in d:
        out.extend(_pack_u8(int(d["palette"]), f"{ctx}/palette"))
    if "_trailing_hex" in d:
        out.extend(_pack_hex(d["_trailing_hex"], None, f"{ctx}/_trailing_hex"))
    return bytes(out)


def _encode_item(d: dict[str, Any], ctx: str) -> bytes:
    """Encode an item sub-block. DS1 = 21 bytes (truncates at
    `bonus`); DS2 = 23 bytes (includes `priority` + `data0`).
    Format dispatch follows the `_format` tag the decoder set.
    """
    fmt = d.get("_format")
    out = bytearray()
    out.extend(_pack_i16(int(d["id"]), f"{ctx}/id"))
    out.extend(_pack_u16(int(d["quantity"]), f"{ctx}/quantity"))
    out.extend(_pack_i16(int(d["next"]), f"{ctx}/next"))
    out.extend(_pack_u16(int(d["value"]), f"{ctx}/value"))
    out.extend(_pack_i16(int(d["pack_index"]), f"{ctx}/pack_index"))
    out.extend(_pack_i16(int(d["item_index"]), f"{ctx}/item_index"))
    out.extend(_pack_i16(int(d["icon"]), f"{ctx}/icon"))
    out.extend(_pack_u16(int(d["charges"]), f"{ctx}/charges"))
    out.extend(_pack_u8(int(d["special"]), f"{ctx}/special"))
    out.extend(_pack_u8(_enum_value(d["slot"]), f"{ctx}/slot"))
    out.extend(_pack_u8(int(d["name_idx"]), f"{ctx}/name_idx"))
    out.extend(_pack_i8(int(d["bonus"]), f"{ctx}/bonus"))
    if fmt == "ds2_item":
        out.extend(_pack_u16(int(d["priority"]), f"{ctx}/priority"))
        out.extend(_pack_i8(int(d["data0"]), f"{ctx}/data0"))
    if "_trailing_hex" in d:
        out.extend(_pack_hex(d["_trailing_hex"], None, f"{ctx}/_trailing_hex"))
    return bytes(out)


def encode_rdff_header(h: dict[str, Any], ctx: str) -> bytes:
    """Inverse of `decode_rdff_header`: pack the 10-byte
    `gff_rdff_header_t`.
    """
    return struct.pack(
        "<bbhhhh",
        int(h["load_action"]),
        int(h["blocknum"]),
        int(h["type"]),
        int(h["index"]),
        int(h["from"]),
        int(h["len"]),
    )


def encode_char_body(body: dict[str, Any], ctx: str) -> bytes:
    """Inverse of `decode_char_body`: walk every sub-block, encode
    via the role-specific encoder, prepend the rdff header. The
    `len` field in each rdff_header stays canonical (the encoder
    asserts byte-length equivalence so the header doesn't need to
    be recomputed).
    """
    out = bytearray()
    for sb in body.get("sub_blocks", []):
        header = sb.get("rdff_header")
        if header is None:
            raise EncodeError(f"{ctx}/sub_blocks[{sb.get('index','?')}]: missing rdff_header")
        out.extend(encode_rdff_header(header, ctx))
        if sb.get("terminator"):
            # RDFF_END: 10-byte header, no body.
            continue
        role = sb.get("role")
        decoded = sb.get("decoded", {})
        sub_ctx = f"{ctx}/sub_blocks[{sb['index']}]({role})"
        if role == "combat":
            body_bytes = _encode_combat(decoded, sub_ctx)
        elif role == "character":
            body_bytes = _encode_character(decoded, sub_ctx)
        elif role == "item":
            body_bytes = _encode_item(decoded, sub_ctx)
        else:
            raise EncodeError(f"{sub_ctx}: unknown sub-block role {role!r}")
        expected = int(header["len"])
        if len(body_bytes) != expected:
            raise EncodeError(
                f"{sub_ctx}: encoder produced {len(body_bytes)} bytes, "
                f"rdff_header.len says {expected}"
            )
        out.extend(body_bytes)
    if "_trailing_hex" in body:
        out.extend(_pack_hex(body["_trailing_hex"], None, f"{ctx}/_trailing_hex"))
    return bytes(out)


def encode_chunk(chunk: dict[str, Any]) -> bytes:
    """Inverse of `decode_chunk`: produce the bytes for a single
    chunk's payload. Handles every kind that has a structured
    decoder; falls back to `raw_hex` for everything else.

    Required input shape: the chunk dict that `decode_chunk`
    produces. The encoder ignores `kind` / `id` / `offset` /
    `length` (those are GFF-container metadata, not payload).
    """
    kind = chunk["kind"]
    ctx = f"chunk {kind}/{chunk['id']}"

    if kind == "CHAR":
        # CHAR is a sequence of `rdff_header + sub_block_body`
        # records. The decoder surfaces the leading rdff_header
        # twice (once as `rdff_header` for convenience, once
        # inside `body.sub_blocks[0].rdff_header`); we only encode
        # the latter so the leading header doesn't double-emit.
        if "body" in chunk:
            return encode_char_body(chunk["body"], ctx)
        if "body_hex_preview" in chunk:
            raise EncodeError(
                f"{ctx}: CHAR chunk has body_hex_preview but no structured body; "
                "re-emit through `save-inspect` and edit the JSON tree"
            )
        raise EncodeError(f"{ctx}: CHAR chunk missing `body`")
    if kind == "PSIN":
        if "types" in chunk:
            if len(chunk["types"]) != 7:
                raise EncodeError(f"{ctx}/types: expected 7 entries")
            out = bytearray()
            for i, v in enumerate(chunk["types"]):
                out.append(int(v) & 0xFF)
            if "trailing_hex" in chunk:
                out.extend(_pack_hex(chunk["trailing_hex"], None, f"{ctx}/trailing_hex"))
            return bytes(out)
        return _pack_hex(chunk.get("raw_hex", ""), None, f"{ctx}/raw_hex")
    if kind == "PSST":
        if "psionics" in chunk:
            if len(chunk["psionics"]) != 34:
                raise EncodeError(f"{ctx}/psionics: expected 34 entries")
            out = bytearray(int(v) & 0xFF for v in chunk["psionics"])
            if "trailing_hex" in chunk:
                out.extend(_pack_hex(chunk["trailing_hex"], None, f"{ctx}/trailing_hex"))
            return bytes(out)
        return _pack_hex(chunk.get("raw_hex", ""), None, f"{ctx}/raw_hex")
    if kind == "TEXT":
        # decode_text normalises CRLF to LF; reverse that on encode.
        text = chunk.get("text", "")
        return text.replace("\n", "\r\n").encode("latin-1", errors="replace")
    if kind == "STXT":
        if "name" not in chunk or "length_total" not in chunk:
            raise EncodeError(f"{ctx}: STXT missing name / length_total")
        total = int(chunk["length_total"])
        name = chunk["name"].encode("ascii", errors="replace")
        if len(name) + 1 > total:
            raise EncodeError(
                f"{ctx}: STXT name + null exceeds length_total ({len(name)+1} > {total})"
            )
        return name + b"\x00" * (total - len(name))
    if kind == "SAVE":
        # v0.7.0 surface is opaque hex. The encoder uses the full
        # bytes (`_raw_bytes_hex`) so SAVE chunks larger than the
        # 128-byte preview cap round-trip correctly.
        if "_raw_bytes_hex" in chunk:
            return _pack_hex(chunk["_raw_bytes_hex"], None, f"{ctx}/_raw_bytes_hex")
        return _pack_hex(chunk.get("raw_hex", ""), None, f"{ctx}/raw_hex")
    if kind == "ETME":
        # ETME is plain text; reverse the LF-normalisation.
        text = chunk.get("text", "")
        return text.replace("\n", "\r\n").encode("latin-1", errors="replace")
    if kind == "ETAB":
        if "_raw_bytes_hex" in chunk:
            return _pack_hex(chunk["_raw_bytes_hex"], None, f"{ctx}/_raw_bytes_hex")
        return _pack_hex(chunk.get("raw_hex", ""), None, f"{ctx}/raw_hex")
    if kind in ("SPST", "CACT", "PREF", "GREQ"):
        # Prefer the full _raw_bytes_hex; fall back to the truncated
        # raw_hex (which may fail with `bad hex string` if the chunk
        # was over 128 bytes and got the "...(N more bytes)" suffix).
        if "_raw_bytes_hex" in chunk:
            return _pack_hex(chunk["_raw_bytes_hex"], None, f"{ctx}/_raw_bytes_hex")
        return _pack_hex(chunk.get("raw_hex", ""), None, f"{ctx}/raw_hex")
    # Unknown kind: rely on raw_hex.
    if "_raw_bytes_hex" in chunk:
        return _pack_hex(chunk["_raw_bytes_hex"], None, f"{ctx}/_raw_bytes_hex")
    if "raw_hex" not in chunk:
        raise EncodeError(f"{ctx}: no raw_hex; cannot encode unknown kind")
    return _pack_hex(chunk["raw_hex"], None, f"{ctx}/raw_hex")


def write_gff(parsed: dict[str, Any], chunk_bytes: list[tuple[str, int, bytes]]) -> bytes:
    """Re-pack a GFF file from a header + per-chunk (kind, id, body)
    list. Inverse of `parse_gff` for indexed-only files.

    Layout: 28-byte header (already in `parsed["header"]`),
    contiguous chunk data area, TOC at the end. The TOC has a
    4-byte free-list offset, then types section: u16 num_types,
    per-type 4-byte FOURCC + u32 chunk_count, per-chunk
    `(i32 id, u32 offset, u32 length)`.

    We use the original `data_location` (always 28) and rebuild
    the TOC; the free-list is emitted as zero entries (matches what
    most GFFs ship with).
    """
    header = parsed["header"]
    data_location = 28  # canonical; matches every GFF we read

    # Group chunks by kind, preserving original (kind, id) order
    # for stability. Same id within different kinds is permitted.
    by_kind: dict[str, list[tuple[int, bytes]]] = {}
    kind_order: list[str] = []
    for kind, cid, body in chunk_bytes:
        if kind not in by_kind:
            by_kind[kind] = []
            kind_order.append(kind)
        by_kind[kind].append((cid, body))

    # Lay out chunk bodies contiguously starting at data_location.
    cursor = data_location
    placements: dict[tuple[str, int], tuple[int, int, bytes]] = {}
    for kind in kind_order:
        for cid, body in by_kind[kind]:
            placements[(kind, cid)] = (cursor, len(body), body)
            cursor += len(body)
    data_end = cursor

    # TOC starts at data_end. The TOC begins with two u32 offsets
    # (types-list, free-list); the types-list comes first (offset
    # 8 = right after these two u32s) and the free-list is empty.
    toc_buf = bytearray()
    types_offset = 8  # relative to TOC start
    free_list_offset = 0  # 0 sentinel = empty free list
    toc_buf.extend(struct.pack("<II", types_offset, free_list_offset))
    toc_buf.extend(struct.pack("<H", len(kind_order)))
    for kind in kind_order:
        kind_bytes = kind.encode("latin-1")
        if len(kind_bytes) != 4:
            raise EncodeError(f"chunk kind {kind!r} is not 4 bytes")
        toc_buf.extend(kind_bytes)
        toc_buf.extend(struct.pack("<I", len(by_kind[kind])))  # no segmented flag
        for cid, body in by_kind[kind]:
            offset, length, _ = placements[(kind, cid)]
            toc_buf.extend(struct.pack("<iII", cid, offset, length))

    toc_location = data_end
    toc_length = len(toc_buf)

    # Build the 28-byte header.
    out = bytearray()
    out.extend(b"GFFI")
    out.extend(struct.pack(
        "<IIIIII",
        int(header["version"]),
        data_location,
        toc_location,
        toc_length,
        int(header["file_flags"]),
        int(header["data0"]),
    ))
    # Pad to data_location (it's always 28 = HEADER_SIZE, no pad
    # needed, but be defensive).
    while len(out) < data_location:
        out.append(0)
    # Append every chunk body in placement order.
    for kind in kind_order:
        for cid, body in by_kind[kind]:
            out.extend(body)
    # Append the TOC.
    out.extend(toc_buf)
    return bytes(out)


# ---------- end encoders ----------


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
        # Full bytes for round-trip; the truncated `raw_hex` above
        # stays for human-readable inspection.
        base["_raw_bytes_hex"] = payload.hex()
    elif kind == "TEXT":
        base["text"] = decode_text(payload)
    elif kind == "SAVE":
        # v0.7.0: per-region world state (DARKRUN.GFF). Schema is
        # empirically incomplete; the decoder surfaces structural
        # shape (length, optional u16 for 2-byte chunks) plus an
        # opaque hex preview. See `decode_save_chunk` for details.
        base.update(decode_save_chunk(chunk["id"], payload))
    elif kind == "STXT":
        # v0.7.0: in DARKRUN.GFF this is the save name (e.g. the
        # "FUCK" save). Null-terminated ASCII padded to chunk
        # length.
        base.update(decode_stxt(payload))
    elif kind == "ETAB":
        # v0.7.0: engine entity table (10 KB allocation, mostly
        # zero in fresh saves). Opaque-hex surface for now.
        base.update(decode_etab(payload))
    elif kind == "ETME":
        # v0.7.0: engine-template-metadata text block, present in
        # both DARKSAVE.GFF (factory) and DARKRUN.GFF (played).
        base.update(decode_etme(payload))
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


def _diff_dict(a: Any, b: Any, path: list[Any]) -> list[dict[str, Any]]:
    """Recursively compare two values; return a list of change
    records describing where they differ. Each record carries the
    `path` (a list of keys / indices) plus the two values."""
    changes: list[dict[str, Any]] = []
    if type(a) is not type(b):
        changes.append({"path": list(path), "kind": "type_changed", "from": _short(a), "to": _short(b)})
        return changes
    if isinstance(a, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            if k not in a:
                changes.append({"path": list(path) + [k], "kind": "added", "to": _short(b[k])})
            elif k not in b:
                changes.append({"path": list(path) + [k], "kind": "removed", "from": _short(a[k])})
            else:
                changes.extend(_diff_dict(a[k], b[k], path + [k]))
        return changes
    if isinstance(a, list):
        # Align by index. Length-mismatch surfaces explicitly.
        if len(a) != len(b):
            changes.append({
                "path": list(path),
                "kind": "list_length_changed",
                "from": len(a),
                "to": len(b),
            })
        for i in range(min(len(a), len(b))):
            changes.extend(_diff_dict(a[i], b[i], path + [i]))
        return changes
    if a != b:
        changes.append({"path": list(path), "kind": "value_changed", "from": a, "to": b})
    return changes


def _short(v: Any) -> Any:
    """Trim long values for diff-record display."""
    if isinstance(v, str) and len(v) > 80:
        return v[:77] + "..."
    if isinstance(v, list) and len(v) > 8:
        return v[:8] + ["..."]
    if isinstance(v, dict):
        return {k: _short(vv) for k, vv in list(v.items())[:12]}
    return v


def diff_summaries(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Produce a structured diff between two `summarise` outputs.
    `chunks_by_kind` and `chunks` are compared by content; the
    `source` / `tool_version` keys are skipped (they always
    differ between separate runs).

    Output shape:
    ```
    {
        "tool": "save-inspect",
        "version": <VERSION>,
        "a": "<path>",
        "b": "<path>",
        "summary": {
            "changed_chunk_count": N,
            "added_chunk_count": N,
            "removed_chunk_count": N,
        },
        "changes": [ { "path": [...], "kind": "...", ... }, ... ],
    }
    ```
    """
    # Compare chunks by (kind, id). Map each side into a keyed dict.
    def keyed(s: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
        out: dict[tuple[str, int], dict[str, Any]] = {}
        for c in s.get("chunks", []):
            kind = c.get("kind", "?")
            cid = int(c.get("id", -1))
            out[(kind, cid)] = c
        return out

    a_keyed = keyed(a)
    b_keyed = keyed(b)
    keys = sorted(set(a_keyed.keys()) | set(b_keyed.keys()))
    changes: list[dict[str, Any]] = []
    changed = added = removed = 0
    for k in keys:
        if k not in a_keyed:
            added += 1
            changes.append({
                "path": [f"chunks[{k[0]}-{k[1]}]"],
                "kind": "chunk_added",
                "to": _short(b_keyed[k]),
            })
            continue
        if k not in b_keyed:
            removed += 1
            changes.append({
                "path": [f"chunks[{k[0]}-{k[1]}]"],
                "kind": "chunk_removed",
                "from": _short(a_keyed[k]),
            })
            continue
        sub = _diff_dict(a_keyed[k], b_keyed[k], [f"chunks[{k[0]}-{k[1]}]"])
        if sub:
            changed += 1
            changes.extend(sub)
    return {
        "tool": "save-inspect",
        "version": VERSION,
        "summary": {
            "changed_chunk_count": changed,
            "added_chunk_count": added,
            "removed_chunk_count": removed,
            "change_count": len(changes),
        },
        "changes": changes,
    }


def _build_inspect_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect", description=__doc__.strip().splitlines()[0]
    )
    p.add_argument("--version", action="version", version=f"save-inspect {VERSION}")
    p.add_argument("file", type=Path, help="path to CHARSAVE.GFF")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="write JSON to file (default stdout)",
    )
    p.add_argument(
        "--pretty", action="store_true",
        help="pretty-print JSON with 2-space indent",
    )
    return p


def _build_diff_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect diff",
        description="Compare two CHARSAVE.GFFs and report what changed.",
    )
    p.add_argument("a", type=Path, help="first CHARSAVE.GFF")
    p.add_argument("b", type=Path, help="second CHARSAVE.GFF")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="write diff JSON to file (default stdout)",
    )
    p.add_argument(
        "--pretty", action="store_true",
        help="pretty-print JSON with 2-space indent",
    )
    return p


def _build_roundtrip_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect roundtrip",
        description=(
            "Round-trip a GFF through decode_chunk -> encode_chunk -> "
            "write_gff and report whether the bytes match the original. "
            "Per-chunk diagnostics surface where the encoders are missing "
            "fields or wrong layouts."
        ),
    )
    p.add_argument("file", type=Path, help="path to the GFF to round-trip")
    p.add_argument(
        "--pretty", action="store_true",
        help="pretty-print JSON report",
    )
    return p


def roundtrip_gff(path: Path) -> dict[str, Any]:
    """Decode every chunk, re-encode, compare to original bytes.

    Returns a JSON-friendly report: per-chunk byte-length and a
    `bytes_equal` flag plus the file-level outcome. Used both as
    a standalone subcommand (`save-inspect roundtrip foo.gff`)
    and as the corpus-test surface for v0.8.0.
    """
    parsed = parse_gff(path)
    original_bytes = path.read_bytes()
    per_chunk: list[dict[str, Any]] = []
    chunk_rebuilds: list[tuple[str, int, bytes]] = []
    ok = True
    encode_errors: list[str] = []
    for c in parsed["chunks"]:
        decoded = decode_chunk(c)
        try:
            re_body = encode_chunk(decoded)
            err: str | None = None
        except EncodeError as e:
            re_body = None
            err = str(e)
            encode_errors.append(err)
            ok = False
        if re_body is None:
            per_chunk.append({
                "chunk": f"{c['kind']}-{c['id']}",
                "original_len": len(c["bytes"]),
                "encoded_ok": False,
                "encode_error": err,
            })
            chunk_rebuilds.append((c["kind"], c["id"], c["bytes"]))
            continue
        match = re_body == c["bytes"]
        per_chunk.append({
            "chunk": f"{c['kind']}-{c['id']}",
            "original_len": len(c["bytes"]),
            "encoded_len": len(re_body),
            "bytes_equal": match,
        })
        if not match:
            ok = False
        chunk_rebuilds.append((c["kind"], c["id"], re_body))

    # File-level round-trip: rebuild the GFF and compare.
    try:
        rebuilt = write_gff(parsed, chunk_rebuilds)
        file_equal = rebuilt == original_bytes
    except EncodeError as e:
        rebuilt = b""
        file_equal = False
        encode_errors.append(f"write_gff: {e}")

    return {
        "tool": "save-inspect",
        "version": VERSION,
        "mode": "roundtrip",
        "file": str(path),
        "summary": {
            "all_chunks_ok": ok,
            "file_bytes_equal": file_equal,
            "original_file_size": len(original_bytes),
            "rebuilt_file_size": len(rebuilt),
            "encode_errors": encode_errors,
        },
        "chunks": per_chunk,
    }


def _build_save_edit_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect save-edit",
        description=(
            "Apply a JSON edit to a GFF save and write the result. "
            "Input JSON must match the `save-inspect <file> --pretty` "
            "output schema. The encoder re-packs every chunk; the GFF "
            "writer rebuilds the TOC."
        ),
    )
    p.add_argument("json_path", type=Path, help="edited JSON input")
    p.add_argument("original", type=Path, help="original GFF (used for header sanity-check)")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="output GFF path. Default: write back to `original` after backup.",
    )
    p.add_argument(
        "--no-backup", action="store_true",
        help="skip the .bak.<timestamp> snapshot (default: take one)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="print what would be written; don't touch disk",
    )
    return p


def save_edit(
    json_path: Path,
    original: Path,
    output: Path | None,
    take_backup: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """Re-encode `json_path` against `original`, write the result.

    Returns a JSON-friendly report. Validation errors raise
    `EncodeError` (caught by the caller and surfaced as exit-2).
    """
    summary = summarise(parse_gff(original))
    incoming = json.loads(json_path.read_text(encoding="utf-8"))
    if "chunks" not in incoming:
        raise EncodeError("input JSON has no top-level `chunks` array")
    if len(incoming["chunks"]) != len(summary["chunks"]):
        raise EncodeError(
            f"input JSON has {len(incoming['chunks'])} chunks; "
            f"original has {len(summary['chunks'])}. "
            f"save-edit doesn't add or remove chunks in v0.8.0."
        )

    # Re-encode every chunk; collect (kind, id, body) tuples that
    # write_gff packs.
    rebuilds: list[tuple[str, int, bytes]] = []
    per_chunk: list[dict[str, Any]] = []
    for orig, edited in zip(summary["chunks"], incoming["chunks"]):
        if orig["kind"] != edited.get("kind") or orig["id"] != edited.get("id"):
            raise EncodeError(
                f"chunk mismatch: original {orig['kind']}/{orig['id']} "
                f"vs input {edited.get('kind')}/{edited.get('id')}"
            )
        body = encode_chunk(edited)
        rebuilds.append((orig["kind"], orig["id"], body))
        per_chunk.append({
            "chunk": f"{orig['kind']}-{orig['id']}",
            "original_len": orig["length"],
            "encoded_len": len(body),
            "changed": body != parse_gff(original)["chunks"][len(per_chunk)]["bytes"]
                       if not dry_run else None,
        })

    parsed_for_header = parse_gff(original)
    new_bytes = write_gff(parsed_for_header, rebuilds)

    out_path = output if output is not None else original
    backup_path: Path | None = None
    if not dry_run:
        if take_backup and out_path.exists():
            ts = str(int(out_path.stat().st_mtime))
            backup_path = out_path.with_name(out_path.name + f".bak.{ts}")
            backup_path.write_bytes(out_path.read_bytes())
        out_path.write_bytes(new_bytes)

    return {
        "tool": "save-inspect",
        "version": VERSION,
        "mode": "save-edit",
        "input_json": str(json_path),
        "original": str(original),
        "output": str(out_path),
        "backup": str(backup_path) if backup_path is not None else None,
        "dry_run": dry_run,
        "summary": {
            "chunks_processed": len(rebuilds),
            "original_size": parsed_for_header["file_size"],
            "new_size": len(new_bytes),
        },
        "chunks": per_chunk,
    }


# ---------- v0.9.0 modder-friendly PC discovery / edit surface ----------


def _enumerate_pcs(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the CHAR chunks in record order, with --pc index
    attached as `pc_index`. The PCs are the playable characters
    inside the CHARSAVE.GFF; we ignore non-CHAR chunks (PSIN,
    PSST, CACT, etc.).
    """
    out: list[dict[str, Any]] = []
    for c in summary.get("chunks", []):
        if c.get("kind") != "CHAR":
            continue
        rec = dict(c)
        rec["pc_index"] = len(out)
        out.append(rec)
    return out


def _pc_overview(pc: dict[str, Any]) -> dict[str, Any]:
    """Pull the high-leverage fields from a CHAR record's
    structured sub-blocks. Defensive: returns Nones for fields the
    decoder couldn't pin (DS1 saves don't carry the `_format` tag
    but the field names are the same).
    """
    blocks = pc.get("body", {}).get("sub_blocks", [])
    combat = next((b.get("decoded", {}) for b in blocks if b.get("role") == "combat"), {})
    character = next((b.get("decoded", {}) for b in blocks if b.get("role") == "character"), {})
    items = [b for b in blocks if b.get("role") == "item"]
    return {
        "pc_index": pc.get("pc_index"),
        "chunk_id": pc.get("id"),
        "name": combat.get("name", "?").strip(),
        "hp": combat.get("hp"),
        "psp": combat.get("psp"),
        "char_id": combat.get("id"),
        "max_hp": character.get("base_hp"),
        "max_psp": character.get("base_psp"),
        "current_xp": character.get("current_xp"),
        "stats": combat.get("stats") or character.get("stats") or {},
        "alignment": character.get("alignment"),
        "level": character.get("level"),
        "item_count": len(items),
    }


def _build_list_pcs_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect list-pcs",
        description=(
            "List every PC in a CHARSAVE.GFF with name, HP, PSP, "
            "XP, and inventory count. Use the PC column as the "
            "--pc index for edit-pc / list-items / give-item."
        ),
    )
    p.add_argument("file", type=Path, help="path to CHARSAVE.GFF")
    p.add_argument("--json", action="store_true",
                   help="emit a JSON array instead of the human table")
    return p


def cmd_list_pcs(args: argparse.Namespace) -> int:
    try:
        parsed = parse_gff(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    summary = summarise(parsed)
    pcs = _enumerate_pcs(summary)
    overviews = [_pc_overview(p) for p in pcs]
    if args.json:
        sys.stdout.write(json.dumps(overviews, indent=2) + "\n")
        return 0
    if not overviews:
        print(f"no CHAR records in {args.file}", file=sys.stderr)
        return 1
    print(f"{len(overviews)} PC(s) in {args.file}:\n")
    print(f"  {'PC':3} {'CHAR':5} {'Name':16} {'HP':>4}/{'Max':>4}  "
          f"{'PSP':>4}/{'Max':>4}  {'XP':>8}  Items")
    print("  " + "-" * 70)
    for o in overviews:
        name = (o["name"] or "?")[:16]
        hp = o["hp"] if o["hp"] is not None else "?"
        mhp = o["max_hp"] if o["max_hp"] is not None else "?"
        psp = o["psp"] if o["psp"] is not None else "?"
        mpsp = o["max_psp"] if o["max_psp"] is not None else "?"
        xp = o["current_xp"] if o["current_xp"] is not None else "?"
        print(f"  {o['pc_index']:3} {o['chunk_id']:5} {name:16} "
              f"{hp:>4}/{mhp:>4}  {psp:>4}/{mpsp:>4}  {xp:>8}  "
              f"{o['item_count']}")
    return 0


# Item-name catalogue. Loaded from tools/save-inspect/syms/items.toml
# at command time. The bootstrap workflow: list-items shows raw
# ids; the modder identifies each in the game; rows get added
# here; subsequent list-items show names.

HERE_DIR = Path(__file__).resolve().parent
ITEMS_CATALOGUE_PATH = HERE_DIR / "syms" / "items.toml"


def _load_items_catalogue() -> dict[int, dict[str, Any]]:
    if not ITEMS_CATALOGUE_PATH.is_file():
        return {}
    import tomllib
    data = tomllib.loads(ITEMS_CATALOGUE_PATH.read_text(encoding="utf-8"))
    out: dict[int, dict[str, Any]] = {}
    for row in data.get("item", []):
        if "id" in row and "name" in row:
            out[int(row["id"])] = row
    return out


def _build_list_items_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect list-items",
        description=(
            "List one PC's inventory. Each row shows the item id, "
            "quantity, slot, charges, and a name lookup from "
            "syms/items.toml (empty by default; grows as you tag "
            "items in-game)."
        ),
    )
    p.add_argument("file", type=Path, help="path to CHARSAVE.GFF")
    p.add_argument("--pc", type=int, required=True,
                   help="PC index (0-based; see `list-pcs`)")
    p.add_argument("--json", action="store_true",
                   help="emit a JSON array instead of the human table")
    return p


def cmd_list_items(args: argparse.Namespace) -> int:
    try:
        parsed = parse_gff(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    summary = summarise(parsed)
    pcs = _enumerate_pcs(summary)
    if args.pc < 0 or args.pc >= len(pcs):
        print(f"error: --pc {args.pc} out of range (have {len(pcs)} PC(s)). "
              f"Run `list-pcs` to see indices.", file=sys.stderr)
        return 2
    pc = pcs[args.pc]
    overview = _pc_overview(pc)
    blocks = pc.get("body", {}).get("sub_blocks", [])
    items = [b for b in blocks if b.get("role") == "item"]
    catalogue = _load_items_catalogue()

    if args.json:
        rows = []
        for slot_idx, b in enumerate(items):
            d = b.get("decoded", {})
            iid = d.get("id")
            cat = catalogue.get(iid, {})
            rows.append({
                "slot_index": slot_idx,
                "item_id": iid,
                "name": cat.get("name"),
                "notes": cat.get("notes"),
                "quantity": d.get("quantity"),
                "charges": d.get("charges"),
                "value": d.get("value"),
                "slot": d.get("slot"),
                "icon": d.get("icon"),
            })
        sys.stdout.write(json.dumps(rows, indent=2) + "\n")
        return 0

    name = (overview["name"] or "?")[:24]
    print(f"PC {args.pc} '{name}' (CHAR {pc['id']}) inventory ({len(items)} item(s)):\n")
    if not items:
        print("  (no items)")
        return 0
    print(f"  {'Slot':4} {'ID':>6} {'Qty':>4} {'Chg':>4} {'SlotKind':10} "
          f"Name (from syms/items.toml)")
    print("  " + "-" * 70)
    unknown_ids: set[int] = set()
    for slot_idx, b in enumerate(items):
        d = b.get("decoded", {})
        iid = d.get("id")
        cat = catalogue.get(iid, {})
        slot_kind = (d.get("slot") or {}).get("name", "?")
        name = cat.get("name", "?")
        if iid is not None and iid not in catalogue:
            unknown_ids.add(iid)
        print(f"  {slot_idx:>4} {iid:>6} {d.get('quantity', 0):>4} "
              f"{d.get('charges', 0):>4} {slot_kind:10} {name}")
    if unknown_ids:
        print()
        print(f"  {len(unknown_ids)} unknown item id(s). Add rows to")
        print(f"  {ITEMS_CATALOGUE_PATH.relative_to(HERE_DIR.parent.parent)} as you identify them in-game.")
    return 0


def _apply_pc_edits(
    pc: dict[str, Any],
    edits: dict[str, Any],
) -> list[str]:
    """Mutate `pc` in place: write each edit into the right
    sub-block. Returns a list of human-readable "applied N -> M"
    lines for the dry-run report.

    Field routing:
      - combat sub-block: hp, psp, stats.{str,dex,con,intel,wis,cha}
      - character sub-block: base_hp ("max_hp"), base_psp
        ("max_psp"), current_xp, stats.* (kept in sync with combat)
      - both combat AND character carry stats; we write to both so
        the values stay consistent.
    """
    blocks = pc.get("body", {}).get("sub_blocks", [])
    combat = next((b.get("decoded") for b in blocks if b.get("role") == "combat"), None)
    character = next((b.get("decoded") for b in blocks if b.get("role") == "character"), None)
    if combat is None or character is None:
        raise EncodeError(
            f"PC {pc.get('pc_index')} (CHAR {pc.get('id')}): missing combat "
            "or character sub-block; can't edit"
        )
    log: list[str] = []
    if "hp" in edits:
        log.append(f"hp: {combat.get('hp')} -> {edits['hp']}")
        combat["hp"] = int(edits["hp"])
    if "psp" in edits:
        log.append(f"psp: {combat.get('psp')} -> {edits['psp']}")
        combat["psp"] = int(edits["psp"])
    if "max_hp" in edits:
        log.append(f"max_hp (character.base_hp): {character.get('base_hp')} -> {edits['max_hp']}")
        character["base_hp"] = int(edits["max_hp"])
    if "max_psp" in edits:
        log.append(f"max_psp (character.base_psp): {character.get('base_psp')} -> {edits['max_psp']}")
        character["base_psp"] = int(edits["max_psp"])
    if "current_xp" in edits:
        log.append(f"current_xp: {character.get('current_xp')} -> {edits['current_xp']}")
        character["current_xp"] = int(edits["current_xp"])
    for stat_key, edit_key in (
        ("str", "str"), ("dex", "dex"), ("con", "con"),
        ("intel", "int"), ("wis", "wis"), ("cha", "cha"),
    ):
        if edit_key in edits:
            new = int(edits[edit_key])
            for owner_name, owner in (("combat.stats", combat.get("stats")),
                                       ("character.stats", character.get("stats"))):
                if owner is not None:
                    log.append(f"{owner_name}.{stat_key}: {owner.get(stat_key)} -> {new}")
                    owner[stat_key] = new
    return log


def _rewrite_save_with_edits(
    parsed: dict[str, Any],
    summary: dict[str, Any],
    edited_chunks_by_key: dict[tuple[str, int], dict[str, Any]],
) -> bytes:
    """Encode every chunk (modified or not) and run write_gff.

    `edited_chunks_by_key`: keyed `(kind, id)` -> the chunk dict
    (from summary.chunks) AS MUTATED by the editor. Chunks not
    in the dict use their original summary entry (which encodes
    back byte-identically per the v0.8.0 round-trip property).
    """
    rebuilds: list[tuple[str, int, bytes]] = []
    for c in summary["chunks"]:
        key = (c["kind"], int(c["id"]))
        source = edited_chunks_by_key.get(key, c)
        body = encode_chunk(source)
        rebuilds.append((c["kind"], int(c["id"]), body))
    return write_gff(parsed, rebuilds)


def _build_edit_pc_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect edit-pc",
        description=(
            "Edit one PC's high-leverage fields and write the "
            "patched save. Backups land at <save>.bak.<timestamp> "
            "by default. Pass --dry-run to preview the changes "
            "without writing."
        ),
    )
    p.add_argument("file", type=Path, help="path to CHARSAVE.GFF")
    p.add_argument("--pc", type=int, required=True,
                   help="PC index (0-based; see `list-pcs`)")
    p.add_argument("--hp", type=int, default=None, help="set current HP")
    p.add_argument("--psp", type=int, default=None, help="set current PSP")
    p.add_argument("--max-hp", type=int, default=None,
                   help="set max HP (character.base_hp)")
    p.add_argument("--max-psp", type=int, default=None,
                   help="set max PSP (character.base_psp)")
    p.add_argument("--xp", dest="current_xp", type=int, default=None,
                   help="set current XP (character.current_xp)")
    for stat in ("str", "dex", "con", "int", "wis", "cha"):
        p.add_argument(f"--{stat}", type=int, default=None,
                       help=f"set {stat} (1..25 D&D 2e range)")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="output GFF path (default: rewrite the input in place after backup)",
    )
    p.add_argument(
        "--no-backup", action="store_true",
        help="skip the .bak.<mtime> snapshot (default: take one)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="report what would change; don't touch disk",
    )
    return p


def cmd_edit_pc(args: argparse.Namespace) -> int:
    edits: dict[str, Any] = {}
    for k in ("hp", "psp", "max_hp", "max_psp", "current_xp",
              "str", "dex", "con", "int", "wis", "cha"):
        val = getattr(args, k, None)
        if val is not None:
            edits[k] = val
    if not edits:
        print("error: pass at least one field flag (--hp, --psp, --str, etc.)",
              file=sys.stderr)
        return 2

    try:
        parsed = parse_gff(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    summary = summarise(parsed)
    pcs = _enumerate_pcs(summary)
    if args.pc < 0 or args.pc >= len(pcs):
        print(f"error: --pc {args.pc} out of range (have {len(pcs)} PC(s)). "
              f"Run `list-pcs` to see indices.", file=sys.stderr)
        return 2
    pc = pcs[args.pc]
    name = (pc.get("body", {}).get("sub_blocks", [{}])[0]
             .get("decoded", {}).get("name", "?") or "?").strip()
    try:
        log = _apply_pc_edits(pc, edits)
    except EncodeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"PC {args.pc} '{name}' (CHAR {pc['id']}):")
    for line in log:
        print(f"  {line}")

    if args.dry_run:
        print("\ndry-run: no file written.")
        return 0

    # Re-encode + write. The pc dict (mutated) is one of the
    # summary['chunks'] entries; build the rewrite via summary
    # so other chunks pass through.
    try:
        new_bytes = _rewrite_save_with_edits(
            parsed, summary, {(pc["kind"], int(pc["id"])): pc}
        )
    except EncodeError as e:
        print(f"error: encode failed: {e}", file=sys.stderr)
        return 2

    out_path = args.output if args.output is not None else args.file
    backup_path: Path | None = None
    if not args.no_backup and out_path.exists():
        ts = str(int(out_path.stat().st_mtime))
        backup_path = out_path.with_name(out_path.name + f".bak.{ts}")
        backup_path.write_bytes(out_path.read_bytes())
    out_path.write_bytes(new_bytes)
    print(f"\nwrote {len(new_bytes)} bytes to {out_path}")
    if backup_path is not None:
        print(f"backup at {backup_path}")
    return 0


def _build_edit_item_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect edit-item",
        description=(
            "Edit one item-slot's fields in place (no chunk "
            "growth; the existing slot stays at its size). The "
            "bootstrap loop for `syms/items.toml`: pick an empty "
            "or unwanted slot, set --item-id to a candidate, "
            "load the save in DOSBox, see what shows up, tag it."
        ),
    )
    p.add_argument("file", type=Path, help="path to CHARSAVE.GFF")
    p.add_argument("--pc", type=int, required=True,
                   help="PC index (0-based; see `list-pcs`)")
    p.add_argument("--slot", type=int, required=True,
                   help="item-slot index within the PC (0-based; see `list-items`)")
    p.add_argument("--item-id", type=int, default=None,
                   help="set the item id (i16; the value `list-items` shows in the ID column)")
    p.add_argument("--quantity", type=int, default=None,
                   help="set quantity (u16)")
    p.add_argument("--charges", type=int, default=None,
                   help="set charges (u16)")
    p.add_argument("--value", type=int, default=None,
                   help="set sale value (u16)")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="output GFF path (default: rewrite the input in place after backup)",
    )
    p.add_argument(
        "--no-backup", action="store_true",
        help="skip the .bak.<mtime> snapshot (default: take one)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="report what would change; don't touch disk",
    )
    return p


def cmd_edit_item(args: argparse.Namespace) -> int:
    edits: dict[str, Any] = {}
    for k in ("item_id", "quantity", "charges", "value"):
        val = getattr(args, k, None)
        if val is not None:
            edits[k] = val
    if not edits:
        print("error: pass at least one field (--item-id, --quantity, --charges, --value)",
              file=sys.stderr)
        return 2

    try:
        parsed = parse_gff(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    summary = summarise(parsed)
    pcs = _enumerate_pcs(summary)
    if args.pc < 0 or args.pc >= len(pcs):
        print(f"error: --pc {args.pc} out of range (have {len(pcs)} PC(s))",
              file=sys.stderr)
        return 2
    pc = pcs[args.pc]
    blocks = pc.get("body", {}).get("sub_blocks", [])
    items = [b for b in blocks if b.get("role") == "item"]
    if args.slot < 0 or args.slot >= len(items):
        print(f"error: --slot {args.slot} out of range "
              f"(PC {args.pc} has {len(items)} item slot(s))", file=sys.stderr)
        return 2
    item = items[args.slot]
    decoded = item.setdefault("decoded", {})
    name = (blocks[0].get("decoded", {}).get("name", "?") or "?").strip()

    log: list[str] = []
    if "item_id" in edits:
        log.append(f"id: {decoded.get('id')} -> {edits['item_id']}")
        decoded["id"] = int(edits["item_id"])
    if "quantity" in edits:
        log.append(f"quantity: {decoded.get('quantity')} -> {edits['quantity']}")
        decoded["quantity"] = int(edits["quantity"])
    if "charges" in edits:
        log.append(f"charges: {decoded.get('charges')} -> {edits['charges']}")
        decoded["charges"] = int(edits["charges"])
    if "value" in edits:
        log.append(f"value: {decoded.get('value')} -> {edits['value']}")
        decoded["value"] = int(edits["value"])

    print(f"PC {args.pc} '{name}' slot {args.slot}:")
    for line in log:
        print(f"  {line}")

    if args.dry_run:
        print("\ndry-run: no file written.")
        return 0

    try:
        new_bytes = _rewrite_save_with_edits(
            parsed, summary, {(pc["kind"], int(pc["id"])): pc}
        )
    except EncodeError as e:
        print(f"error: encode failed: {e}", file=sys.stderr)
        return 2

    out_path = args.output if args.output is not None else args.file
    backup_path: Path | None = None
    if not args.no_backup and out_path.exists():
        ts = str(int(out_path.stat().st_mtime))
        backup_path = out_path.with_name(out_path.name + f".bak.{ts}")
        backup_path.write_bytes(out_path.read_bytes())
    out_path.write_bytes(new_bytes)
    print(f"\nwrote {len(new_bytes)} bytes to {out_path}")
    if backup_path is not None:
        print(f"backup at {backup_path}")
    return 0


def _build_find_empty_slots_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect find-empty-slots",
        description=(
            "Scan every PC's inventory and report empty / unwanted "
            "slots. Slots with `quantity = 0` are the safest swap "
            "targets for the `edit-item` bootstrap loop -- changing "
            "their item id doesn't displace anything the player is "
            "carrying. Pair with `edit-item --pc N --slot K "
            "--item-id X` to fill the loop."
        ),
    )
    p.add_argument("file", type=Path, help="path to CHARSAVE.GFF")
    p.add_argument("--json", action="store_true",
                   help="emit a JSON array instead of the human table")
    return p


def cmd_find_empty_slots(args: argparse.Namespace) -> int:
    try:
        parsed = parse_gff(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    summary = summarise(parsed)
    pcs = _enumerate_pcs(summary)
    empties: list[dict[str, Any]] = []
    for pc in pcs:
        name = (pc.get("body", {}).get("sub_blocks", [{}])[0]
                 .get("decoded", {}).get("name", "?") or "?").strip()
        blocks = pc.get("body", {}).get("sub_blocks", [])
        items = [b for b in blocks if b.get("role") == "item"]
        for slot_idx, b in enumerate(items):
            d = b.get("decoded", {})
            if int(d.get("quantity", 0)) == 0:
                empties.append({
                    "pc_index": pc["pc_index"],
                    "pc_name": name,
                    "slot": slot_idx,
                    "current_id": d.get("id"),
                    "slot_kind": (d.get("slot") or {}).get("name", "?"),
                })
    if args.json:
        sys.stdout.write(json.dumps(empties, indent=2) + "\n")
        return 0
    if not empties:
        print(f"no quantity-0 slots in {args.file}", file=sys.stderr)
        return 1
    print(f"{len(empties)} empty slot(s) in {args.file} "
          f"(quantity = 0; safe `edit-item` swap targets):\n")
    print(f"  {'PC':3} {'Slot':>4} {'Current-ID':>10} {'SlotKind':10} PC name")
    print("  " + "-" * 60)
    for e in empties:
        print(f"  {e['pc_index']:3} {e['slot']:>4} {e['current_id']:>10} "
              f"{e['slot_kind']:10} {e['pc_name']}")
    print()
    print("Use `edit-item --pc N --slot K --item-id X --quantity 1` to")
    print("repurpose any of these for the items.toml bootstrap loop.")
    return 0


# ---------- end v0.9.0 ----------


def _build_save_diff_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="save-inspect save-diff",
        description=(
            "Compare two DARKRUN-shape GFFs (DARKRUN.GFF / SAVE0N.SAV) "
            "and report SAVE-chunk differences: per-chunk byte-diff "
            "counts plus full structural surface."
        ),
    )
    p.add_argument("a", type=Path, help="first DARKRUN.GFF (factory or earlier)")
    p.add_argument("b", type=Path, help="second DARKRUN.GFF (played or later)")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="write diff JSON to file (default stdout)",
    )
    p.add_argument(
        "--pretty", action="store_true",
        help="pretty-print JSON with 2-space indent",
    )
    p.add_argument(
        "--all-chunks", action="store_true",
        help="include non-SAVE chunk differences too (default: SAVE only)",
    )
    return p


def save_chunk_diff(
    a_parsed: dict[str, Any],
    b_parsed: dict[str, Any],
    only_save: bool = True,
) -> dict[str, Any]:
    """SAVE-chunk-focused diff between two parsed DARKRUN-shape GFFs.

    Unlike `diff_summaries` (which walks the decoded summary trees
    field-by-field), this one operates at the chunk-byte level: for
    each chunk that exists in both files, it reports the byte-diff
    count and the first 64 bytes of the differing region. The
    intent is to make empirical SAVE-chunk RE easy: do an action
    in-game, save, compare against the pre-action save, see exactly
    which bytes changed where.

    By default the report only covers SAVE chunks; `only_save=False`
    includes ETAB / STXT / ETME / etc. as well.
    """
    def keyed_bytes(parsed: dict[str, Any]) -> dict[tuple[str, int], bytes]:
        out: dict[tuple[str, int], bytes] = {}
        for c in parsed.get("chunks", []):
            out[(c["kind"], int(c["id"]))] = c["bytes"]
        return out

    a_chunks = keyed_bytes(a_parsed)
    b_chunks = keyed_bytes(b_parsed)
    keys = sorted(set(a_chunks.keys()) | set(b_chunks.keys()))
    if only_save:
        keys = [k for k in keys if k[0] == "SAVE"]

    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged_count = 0
    for k in keys:
        if k not in a_chunks:
            added.append({
                "chunk": f"{k[0]}-{k[1]}",
                "kind": k[0],
                "id": k[1],
                "byte_length": len(b_chunks[k]),
                "raw_hex_preview": hex_preview(b_chunks[k], limit=64),
            })
            continue
        if k not in b_chunks:
            removed.append({
                "chunk": f"{k[0]}-{k[1]}",
                "kind": k[0],
                "id": k[1],
                "byte_length": len(a_chunks[k]),
                "raw_hex_preview": hex_preview(a_chunks[k], limit=64),
            })
            continue
        ab = a_chunks[k]
        bb = b_chunks[k]
        if ab == bb:
            unchanged_count += 1
            continue
        # Same chunk, different bytes. Compute the byte-diff count
        # and the first differing-byte offset.
        diff_bytes = 0
        first_diff = None
        for i in range(max(len(ab), len(bb))):
            av = ab[i] if i < len(ab) else None
            bv = bb[i] if i < len(bb) else None
            if av != bv:
                diff_bytes += 1
                if first_diff is None:
                    first_diff = i
        changed.append({
            "chunk": f"{k[0]}-{k[1]}",
            "kind": k[0],
            "id": k[1],
            "a_byte_length": len(ab),
            "b_byte_length": len(bb),
            "byte_diff_count": diff_bytes,
            "first_diff_offset": first_diff,
            "a_hex_preview": hex_preview(ab, limit=64),
            "b_hex_preview": hex_preview(bb, limit=64),
        })

    return {
        "tool": "save-inspect",
        "version": VERSION,
        "mode": "save-diff",
        "filter": "save-only" if only_save else "all-chunks",
        "summary": {
            "added_chunk_count": len(added),
            "removed_chunk_count": len(removed),
            "changed_chunk_count": len(changed),
            "unchanged_chunk_count": unchanged_count,
            "total_byte_diff": sum(c["byte_diff_count"] for c in changed),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Manual dispatch: if the first arg is a known subcommand,
    # route there. Otherwise default to the v0.1.x inspect path
    # (the bare-file form `save-inspect <file>`).
    if argv and argv[0] == "diff":
        diff_args = _build_diff_parser().parse_args(argv[1:])
        try:
            sa = summarise(parse_gff(diff_args.a))
            sb = summarise(parse_gff(diff_args.b))
        except (FileNotFoundError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        out = diff_summaries(sa, sb)
        out["a"] = str(diff_args.a)
        out["b"] = str(diff_args.b)
        indent = 2 if diff_args.pretty else None
        text = json.dumps(out, indent=indent, ensure_ascii=False)
        if diff_args.output is None or str(diff_args.output) == "-":
            sys.stdout.write(text + "\n")
        else:
            diff_args.output.write_text(text + "\n", encoding="utf-8")
        return 0
    if argv and argv[0] == "roundtrip":
        rt_args = _build_roundtrip_parser().parse_args(argv[1:])
        try:
            report = roundtrip_gff(rt_args.file)
        except (FileNotFoundError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        indent = 2 if rt_args.pretty else None
        sys.stdout.write(json.dumps(report, indent=indent, ensure_ascii=False) + "\n")
        return 0 if report["summary"]["all_chunks_ok"] and report["summary"]["file_bytes_equal"] else 1
    if argv and argv[0] == "save-edit":
        se_args = _build_save_edit_parser().parse_args(argv[1:])
        try:
            report = save_edit(
                se_args.json_path,
                se_args.original,
                se_args.output,
                take_backup=not se_args.no_backup,
                dry_run=se_args.dry_run,
            )
        except (FileNotFoundError, ValueError, EncodeError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return 0
    if argv and argv[0] == "list-pcs":
        return cmd_list_pcs(_build_list_pcs_parser().parse_args(argv[1:]))
    if argv and argv[0] == "list-items":
        return cmd_list_items(_build_list_items_parser().parse_args(argv[1:]))
    if argv and argv[0] == "edit-pc":
        return cmd_edit_pc(_build_edit_pc_parser().parse_args(argv[1:]))
    if argv and argv[0] == "edit-item":
        return cmd_edit_item(_build_edit_item_parser().parse_args(argv[1:]))
    if argv and argv[0] == "find-empty-slots":
        return cmd_find_empty_slots(_build_find_empty_slots_parser().parse_args(argv[1:]))
    if argv and argv[0] == "save-diff":
        sd_args = _build_save_diff_parser().parse_args(argv[1:])
        try:
            pa = parse_gff(sd_args.a)
            pb = parse_gff(sd_args.b)
        except (FileNotFoundError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        out = save_chunk_diff(pa, pb, only_save=not sd_args.all_chunks)
        out["a"] = str(sd_args.a)
        out["b"] = str(sd_args.b)
        indent = 2 if sd_args.pretty else None
        text = json.dumps(out, indent=indent, ensure_ascii=False)
        if sd_args.output is None or str(sd_args.output) == "-":
            sys.stdout.write(text + "\n")
        else:
            sd_args.output.write_text(text + "\n", encoding="utf-8")
        return 0

    args = _build_inspect_parser().parse_args(argv)

    try:
        parsed = parse_gff(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    summary = summarise(parsed)
    indent = 2 if args.pretty else None
    text = json.dumps(summary, indent=indent, ensure_ascii=False)

    if args.output is None or str(args.output) == "-":
        sys.stdout.write(text + "\n")
    else:
        args.output.write_text(text + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
