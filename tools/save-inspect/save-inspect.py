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
