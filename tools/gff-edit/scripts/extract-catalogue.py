#!/usr/bin/env python3
"""Extract the full object/spell/creature catalogues from the game data.

Reads the canonical installs under .games/ and emits machine-generated
markdown catalogues (bestiary, item catalogue, spell catalogue, one of
each per game) with a verification footer. The field layouts are
docs/object-formats.md; this script is their executable form.
Corpus-wide invariants (negated-id anchors, name joins, sprite
references) are counted into the footer, and a fixed anchor list must
pass or the run fails loudly (exit 2), so a data or layout regression
cannot ship as a quietly-wrong catalogue.

Stdlib-only. Regenerate the docs with:

    python3 tools/gff-edit/scripts/extract-catalogue.py

Exit codes: 0 ok, 1 selftest failure, 2 anchor/data failure,
3 missing game data.
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DS1_EXE_POWER_TABLE = 0x41F70  # 196 records x 32 bytes
DS1_EXE_LEVEL_TABLE = 0x4512C  # 138 records x 7 bytes, byte 0 = level
DS2_POWER_TABLE = 0x120E8  # RESOURCE.GFF, 320 records x 73 bytes
DS2_WIZ_LEVELS = 0x4D656  # DSUN.EXE, 11 boundary bytes
DS2_CL_LEVELS = 0x4D661  # DSUN.EXE, 11 boundary bytes

LOAD_END = -1
LA_OBJECT, LA_CONTAINER, LA_DATA, LA_NEXT = 1, 2, 3, 4
TYPE_ITEM, TYPE_COMBAT, TYPE_MINI = 1, 2, 5
NULL16 = 9999


# --------------------------------------------------------------------------
# GFF container parsing (docs/file-formats.md section 1)


@dataclass
class Gff:
    data: bytes
    # type (stripped FOURCC) -> list of (id, location, length)
    indexed: dict[str, list[tuple[int, int, int]]]
    # type -> (seg_loc_id, [(first_id, num_chunks), ...])
    segmented: dict[str, tuple[int, list[tuple[int, int]]]]


def parse_gff(path: Path) -> Gff:
    data = path.read_bytes()
    if data[:4] != b"GFFI" or len(data) < 28:
        raise ValueError(f"not a GFF container: {path}")
    toc_location = struct.unpack_from("<I", data, 12)[0]
    types_offset = struct.unpack_from("<I", data, toc_location)[0]
    pos = toc_location + types_offset
    (num_types,) = struct.unpack_from("<H", data, pos)
    pos += 2
    indexed: dict[str, list[tuple[int, int, int]]] = {}
    segmented: dict[str, tuple[int, list[tuple[int, int]]]] = {}
    for _ in range(num_types):
        raw, count = struct.unpack_from("<Ii", data, pos)
        fourcc = raw.to_bytes(4, "little").decode("ascii").rstrip()
        pos += 8
        if count & 0x80000000:
            n = count & 0x7FFFFFFF
            _seg_count, seg_loc_id, num_runs = struct.unpack_from("<iiI", data, pos)
            pos += 12
            runs = []
            for _ in range(num_runs):
                first_id, num_chunks = struct.unpack_from("<ii", data, pos)
                pos += 8
                runs.append((first_id, num_chunks))
            assert n == sum(r[1] for r in runs), f"run sum mismatch {fourcc}"
            segmented[fourcc] = (seg_loc_id, runs)
        else:
            entries = []
            for _ in range(count):
                cid, location, length = struct.unpack_from("<III", data, pos)
                pos += 12
                entries.append((cid, location, length))
            indexed.setdefault(fourcc, []).extend(entries)
    return Gff(data=data, indexed=indexed, segmented=segmented)


def resolve_type(gff: Gff, fourcc: str) -> list[tuple[int, bytes]]:
    """All chunks of a type as (resource id, payload bytes)."""
    if fourcc in gff.segmented:
        seg_loc_id, runs = gff.segmented[fourcc]
        gffi_chunks = gff.indexed.get("GFFI", [])
        _cid, loc, length = gffi_chunks[seg_loc_id]
        table = gff.data[loc : loc + length]
        (entry_count,) = struct.unpack_from("<I", table, 0)
        chunks: list[tuple[int, bytes]] = []
        entry_index = 0
        for first_id, num_chunks in runs:
            for k in range(num_chunks):
                off, size = struct.unpack_from("<II", table, 4 + (entry_index + k) * 8)
                chunks.append((first_id + k, gff.data[off : off + size]))
            entry_index += num_chunks
        assert entry_index == entry_count, "secondary table size mismatch"
        return chunks
    return [
        (cid, gff.data[loc : loc + length])
        for cid, loc, length in gff.indexed.get(fourcc, [])
    ]


def get_chunk(gff: Gff, fourcc: str, cid: int) -> bytes:
    for cid_, payload in resolve_type(gff, fourcc):
        if cid_ == cid:
            return payload
    raise KeyError(f"chunk {fourcc}:{cid} not found")


# --------------------------------------------------------------------------
# RDFF chain walking and record decoding


@dataclass
class Block:
    load_action: int
    blocknum: int
    type: int
    index: int
    source: int
    payload: bytes


def walk_rdff(payload: bytes, chunk_id: int) -> list[Block]:
    blocks = []
    off = 0
    while True:
        if off + 10 > len(payload):
            raise ValueError(f"RDFF {chunk_id}: truncated header at {off}")
        la, blocknum, btype, index, source, length = struct.unpack_from(
            "<bbhhhh", payload, off
        )
        if la == LOAD_END:
            break
        body = payload[off + 10 : off + 10 + length]
        if len(body) != length:
            raise ValueError(f"RDFF {chunk_id}: truncated payload at {off}")
        blocks.append(Block(la, blocknum, btype, index, source, body))
        off += 10 + length
    return blocks


def cstr(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def i8(data: bytes, off: int) -> int:
    return struct.unpack_from("<b", data, off)[0]


def u8(data: bytes, off: int) -> int:
    return data[off]


def i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0]


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


@dataclass
class Creature:
    game: str
    obj_id: int
    name: str
    hp: int
    psp: int
    ac: int
    move: int
    thac0: int | None
    allegiance: int
    stats: tuple[int, ...]
    level: tuple[int, ...]
    real_class: tuple[int, ...]
    attacks: tuple[int, ...]  # half-rounds
    damage: tuple[tuple[int, int, int], ...]  # (dice, sides, bonus) x3
    saves: tuple[int, ...]
    magic_res: int
    xp: int
    base_ac: int
    base_move: int
    sprite_bmp: int
    special_attack: int
    special_defense: int
    flags: int
    sp_alt: int  # DS2 cb+14 unresolved candidate


def decode_creature(
    game: str, obj_id: int, combat: bytes, charrec: bytes, sprite: int
) -> Creature:
    if game == "ds1":
        name = cstr(combat[40:56])
        thac0: int | None = i8(combat, 31)
        sp_alt = 0
        ac_off, move_off, alleg_off, stats_off = 26, 27, 29, 34
        lvl_off, cls_off, atk_off, dmg_off, save_off = 36, 33, 43, 46, 55
        mr_off, bac_off, bmv_off = 41, 39, 40
    else:
        name = cstr(combat[33:49])
        thac0 = None
        sp_alt = u16(combat, 14)
        ac_off, move_off, alleg_off, stats_off = 18, 19, 21, 25
        lvl_off, cls_off, atk_off, dmg_off, save_off = 30, 27, 37, 40, 49
        mr_off, bac_off, bmv_off = 35, 33, 34
    return Creature(
        game=game,
        obj_id=obj_id,
        name=name,
        hp=i16(combat, 0),
        psp=i16(combat, 2),
        ac=i8(combat, ac_off),
        move=u8(combat, move_off),
        thac0=thac0,
        allegiance=u8(combat, alleg_off),
        stats=tuple(u8(combat, stats_off + k) for k in range(6)),
        level=tuple(u8(charrec, lvl_off + k) for k in range(3)),
        real_class=tuple(u8(charrec, cls_off + k) for k in range(3)),
        attacks=tuple(u8(charrec, atk_off + k) for k in range(3)),
        damage=tuple(
            (
                u8(charrec, dmg_off + k),
                u8(charrec, dmg_off + 3 + k),
                u8(charrec, dmg_off + 6 + k),
            )
            for k in range(3)
        ),
        saves=tuple(u8(charrec, save_off + k) for k in range(5)),
        magic_res=u8(charrec, mr_off),
        xp=u32(charrec, 0),
        base_ac=i8(charrec, bac_off),
        base_move=u8(charrec, bmv_off),
        sprite_bmp=sprite,
        special_attack=u8(combat, 22),
        special_defense=u8(combat, 23),
        flags=u8(combat, 24) if game == "ds2" else u8(combat, 33),
        sp_alt=sp_alt,
    )


@dataclass
class ItemStats:
    wclass: int
    dmg_type: int
    weight: int
    material: int
    slot: int
    attacks: int
    sides: int
    dice: int
    mod: int
    flags: int
    legal_class: int
    base_ac: int


@dataclass
class Item:
    game: str
    obj_id: int
    quantity: int
    value: int
    charges: int
    special: int
    slot: int
    name_idx: int
    stats_index: int
    sprite_bmp: int
    load_action: int
    stats: ItemStats | None = None


def decode_item(
    game: str, obj_id: int, payload: bytes, sprite: int, load_action: int
) -> Item:
    if game == "ds1":
        return Item(
            game=game,
            obj_id=obj_id,
            quantity=u16(payload, 2),
            value=u16(payload, 6),
            charges=u8(payload, 14),
            special=u8(payload, 16),
            slot=u8(payload, 17),
            name_idx=u8(payload, 18),
            stats_index=i16(payload, 10),
            sprite_bmp=sprite,
            load_action=load_action,
        )
    return Item(
        game=game,
        obj_id=obj_id,
        quantity=u16(payload, 2),
        value=u16(payload, 6),
        charges=u16(payload, 14),
        special=u8(payload, 18),
        slot=u8(payload, 19),
        name_idx=u8(payload, 20),
        stats_index=i16(payload, 10),
        sprite_bmp=sprite,
        load_action=load_action,
    )


def decode_ds1_it1r(data: bytes, k: int) -> ItemStats:
    row = data[k * 20 : (k + 1) * 20]
    return ItemStats(
        wclass=u8(row, 0),
        dmg_type=u16(row, 2),
        weight=u8(row, 4),
        material=u8(row, 8),
        slot=u8(row, 9),
        attacks=u8(row, 11),
        sides=u8(row, 12),
        dice=u8(row, 13),
        mod=i8(row, 14),
        flags=u8(row, 15),
        legal_class=u16(row, 16),
        base_ac=i8(row, 18),
    )


def decode_ds2_template(data: bytes) -> ItemStats:
    return ItemStats(
        wclass=u8(data, 0),
        dmg_type=u8(data, 1),
        weight=u8(data, 2),
        material=u8(data, 4),
        slot=u8(data, 5),
        attacks=u8(data, 7),
        sides=u8(data, 8),
        dice=u8(data, 9),
        mod=i8(data, 10),
        flags=u8(data, 11),
        legal_class=u16(data, 12),
        base_ac=i8(data, 14),
    )


@dataclass
class Mini:
    obj_id: int
    name: str
    priority: int
    flags: int


# --------------------------------------------------------------------------
# Corpus extraction


@dataclass
class GameData:
    game: str
    creatures: list[Creature] = field(default_factory=list)
    items: dict[int, Item] = field(default_factory=dict)
    item_names: dict[int, str] = field(default_factory=dict)
    minis: list[Mini] = field(default_factory=list)
    spells: list[dict] = field(default_factory=list)
    monr: list[tuple[int, list[tuple[int, int]]]] = field(default_factory=list)
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)


def extract_objects(
    game: str, objdb: Path
) -> tuple[
    list[Creature],
    dict[int, Item],
    list[Mini],
    dict[int, bytes],
    dict[str, int],
]:
    """Walk the object database. Returns creatures, items, minis, the
    DS2 15-byte template blocks keyed by header index, and invariant
    counts."""
    gff = parse_gff(objdb)
    bmp_ids = {cid for cid, _ in resolve_type(gff, "BMP")}
    stats = {
        "total": 0,
        "combat": 0,
        "combat_total": 0,
        "item_la1": 0,
        "id_ok": 0,
        "sprite_ok": 0,
    }
    creatures: list[Creature] = []
    items: dict[int, Item] = {}
    minis: list[Mini] = []
    templates: dict[int, bytes] = {}
    for cid, payload in resolve_type(gff, "RDFF"):
        stats["total"] += 1
        try:
            blocks = walk_rdff(payload, cid)
        except ValueError as exc:
            print(f"warning: {exc}", file=sys.stderr)
            continue
        for b in blocks:
            if b.load_action == LA_DATA and b.type == 4 and len(b.payload) == 15:
                templates[b.index] = b.payload
        combat = next(
            (b for b in blocks if b.load_action == LA_OBJECT and b.type == TYPE_COMBAT),
            None,
        )
        if combat is not None:
            stats["combat_total"] += 1
            charrec = next(
                (
                    b
                    for b in blocks
                    if b.load_action == LA_DATA
                    and b.type in (3, 4)
                    and len(b.payload) > 40
                ),
                None,
            )
            if charrec is None:
                print(
                    f"warning: RDFF {cid}: combat without charrec",
                    file=sys.stderr,
                )
                continue
            stats["combat"] += 1
            stats["id_ok"] += i16(combat.payload, 6) == -cid
            stats["sprite_ok"] += combat.index in bmp_ids
            creatures.append(
                decode_creature(
                    game, cid, combat.payload, charrec.payload, combat.index
                )
            )
            continue
        item_block = next(
            (b for b in blocks if b.type == TYPE_ITEM and b.load_action in (1, 2, 4)),
            None,
        )
        if item_block is not None:
            iid = -i16(item_block.payload, 0)
            if item_block.load_action == LA_OBJECT:
                stats["id_ok"] += i16(item_block.payload, 0) == -cid
            stats["sprite_ok"] += item_block.index in bmp_ids
            item = decode_item(
                game,
                iid,
                item_block.payload,
                item_block.index,
                item_block.load_action,
            )
            if iid not in items or items[iid].load_action != LA_OBJECT:
                items[iid] = item
            if item_block.load_action == LA_OBJECT:
                stats["item_la1"] += 1
        mini = next(
            (b for b in blocks if b.type == TYPE_MINI and len(b.payload) >= 23),
            None,
        )
        if mini is not None:
            minis.append(
                Mini(
                    obj_id=cid,
                    name=cstr(mini.payload[5:21]),
                    priority=u8(mini.payload, 4),
                    flags=u8(mini.payload, 21),
                )
            )
    return creatures, items, minis, templates, stats


def attach_ds1_item_stats(out: GameData, gpldata: Path) -> None:
    gff = parse_gff(gpldata)
    it1r = get_chunk(gff, "IT1R", 1)
    rows = len(it1r) // 20
    name_raw = get_chunk(gff, "NAME", 1)
    pool = [cstr(name_raw[k * 25 : (k + 1) * 25]) for k in range(len(name_raw) // 25)]
    joined = stats_ok = sentinels = out_of_range = 0
    for iid, item in out.items.items():
        if item.stats_index == NULL16:
            sentinels += 1  # measured: "no base-stats row" marker
        elif 0 <= item.stats_index < rows:
            item.stats = decode_ds1_it1r(it1r, item.stats_index)
            stats_ok += 1
        else:
            out_of_range += 1
        if 0 <= item.name_idx < len(pool):
            out.item_names[iid] = pool[item.name_idx]
            joined += 1
    out.checks.append(
        (
            "DS1 item IT1R joins",
            stats_ok + sentinels == len(out.items) and out_of_range == 0,
            f"{stats_ok} rows + {sentinels} null-sentinels, "
            f"{out_of_range} out of range",
        )
    )
    out.checks.append(
        ("DS1 item name joins", joined == len(out.items), f"{joined}/{len(out.items)}")
    )


def attach_ds2_item_stats(out: GameData, templates: dict[int, bytes]) -> None:
    stats_ok = 0
    for iid, item in out.items.items():
        if item.stats_index in templates:
            item.stats = decode_ds2_template(templates[item.stats_index])
            stats_ok += 1
    out.checks.append(
        (
            "DS2 item template joins",
            stats_ok == len(out.items),
            f"{stats_ok}/{len(out.items)}",
        )
    )
    out.stats["template_rows"] = len(templates)


def attach_ds2_item_names(out: GameData, resource: Path) -> None:
    gff = parse_gff(resource)
    text_raw = get_chunk(gff, "TEXT", 1000)
    pool = text_raw.split(b"\r\n")
    joined = unnamed = 0
    for iid, item in out.items.items():
        if item.name_idx == 0:
            unnamed += 1  # measured: 0 = no name (scenery/containers)
        elif item.name_idx <= len(pool):
            out.item_names[iid] = cstr(pool[item.name_idx - 1])
            joined += 1
    out.checks.append(
        (
            "DS2 item name joins",
            joined + unnamed == len(out.items),
            f"{joined} named + {unnamed} nameless of {len(out.items)}",
        )
    )


def _find_creature(creatures: list[Creature], cid: int, **want: int) -> bool:
    c = next((c for c in creatures if c.obj_id == cid), None)
    if c is None:
        return False
    got = {
        "hp": c.hp,
        "ac": c.ac,
        "thac0": c.thac0,
        "psp": c.psp,
        "hd": c.level[0],
        "mr": c.magic_res,
    }
    return all(got[k] == v for k, v in want.items())


def _name_has(out: GameData, iid: int, needle: str) -> bool:
    return needle in out.item_names.get(iid, "").lower().replace("'", "")


def _name_get(out: GameData, iid: int) -> str:
    return out.item_names.get(iid, "<no name>")


def _spell_name(spells: list[dict], idx: int) -> str:
    return next((s["name"] for s in spells if s["index"] == idx), "<none>")


def extract_ds1(games_dir: Path) -> GameData:
    out = GameData("ds1")
    creatures, items, minis, _templates, stats = extract_objects(
        "ds1", games_dir / "ds1" / "SEGOBJEX.GFF"
    )
    out.creatures, out.items, out.minis = creatures, items, minis
    attach_ds1_item_stats(out, games_dir / "ds1" / "GPLDATA.GFF")

    resource = parse_gff(games_dir / "ds1" / "RESOURCE.GFF")
    spin = dict(resolve_type(resource, "SPIN"))
    exe = (games_dir / "ds1" / "DSUN.EXE").read_bytes()
    out.spells = decode_spells_ds1(spin, exe)
    out.monr = decode_monr(get_chunk(resource, "MONR", 1))

    wyvern = next((c.name for c in creatures if c.obj_id == 5), "")
    out.checks.extend(
        [
            ("DS1 RDFF chunks", stats["total"] == 1046, str(stats["total"])),
            (
                "DS1 creatures == 291 records (290 decoded + 1 stub)",
                stats["combat"] == 290 and stats["combat_total"] == 291,
                f"{stats['combat']} decoded + {stats['combat_total']} total",
            ),
            (
                "DS1 negated-id anchors",
                stats["id_ok"] == stats["combat"] + stats["item_la1"],
                f"{stats['id_ok']}/{stats['combat'] + stats['item_la1']}",
            ),
            (
                "Silt Runner 291 (hp 8, thac0 19)",
                _find_creature(creatures, 291, hp=8, thac0=19),
                "hp/thac0",
            ),
            (
                "obj 1010 ~ Chatkcha",
                _name_has(out, 1010, "chatkcha"),
                _name_get(out, 1010),
            ),
            ("creature 5 ~ Wyvern", "wyvern" in wyvern.lower(), wyvern),
            (
                "spell 35 ~ Monster Summoning I",
                "monster summoning i" in _spell_name(out.spells, 35).lower(),
                _spell_name(out.spells, 35),
            ),
            (
                "spell 69 ~ Bless (level C1)",
                "bless" in _spell_name(out.spells, 69).lower()
                and out.spells[69]["level"] == "1",
                _spell_name(out.spells, 69),
            ),
        ]
    )
    return out


def extract_ds2(games_dir: Path) -> GameData:
    out = GameData("ds2")
    creatures, items, minis, templates, stats = extract_objects(
        "ds2", games_dir / "ds2" / "OBJEX.GFF"
    )
    out.creatures, out.items, out.minis = creatures, items, minis
    attach_ds2_item_stats(out, templates)
    attach_ds2_item_names(out, games_dir / "ds2" / "RESOURCE.GFF")

    resource_path = games_dir / "ds2" / "RESOURCE.GFF"
    resource = parse_gff(resource_path)
    out.spells = decode_spells_ds2(
        resource_path.read_bytes(), games_dir / "ds2" / "DSUN.EXE"
    )
    out.monr = decode_monr(get_chunk(resource, "MONR", 1))

    n = len(creatures)
    item5807 = out.items.get(5807)
    out.checks.extend(
        [
            ("DS2 RDFF chunks", stats["total"] == 1643, str(stats["total"])),
            ("DS2 creatures == 352", n == 352, str(n)),
            (
                "DS2 negated-id anchors",
                stats["id_ok"] == stats["combat"] + stats["item_la1"],
                f"{stats['id_ok']}/{stats['combat'] + stats['item_la1']}",
            ),
            (
                "Umber Hulk 405 (hp 50, ac 2, hd 8)",
                _find_creature(creatures, 405, hp=50, ac=2, hd=8),
                "ok",
            ),
            (
                "Mindflayer 416 (MR 90, psp 300)",
                _find_creature(creatures, 416, mr=90, psp=300),
                "ok",
            ),
            (
                "obj 603 ~ Longsword",
                _name_has(out, 603, "longsword") or _name_has(out, 603, "long sword"),
                _name_get(out, 603),
            ),
            (
                "spell 0 ~ Armor",
                "armor" in _spell_name(out.spells, 0).lower(),
                _spell_name(out.spells, 0),
            ),
            (
                "elevator 5807 sprite == BMP 951",
                item5807 is not None and item5807.sprite_bmp == 951,
                str(item5807.sprite_bmp if item5807 else None),
            ),
        ]
    )
    return out


def decode_monr(data: bytes) -> list[tuple[int, list[tuple[int, int]]]]:
    rows = []
    for k in range(len(data) // 42):
        off = k * 42
        region = i16(data, off)
        entries = [
            (i16(data, off + 2 + j * 4), i16(data, off + 4 + j * 4)) for j in range(10)
        ]
        rows.append((region, entries))
    return rows


# --------------------------------------------------------------------------
# Spells


def spell_level_ds1(exe: bytes, index: int) -> str:
    if index <= 137:
        return str(exe[DS1_EXE_LEVEL_TABLE + index * 7])
    if index <= 171:
        return "P"
    if index <= 178:
        return "S"
    return "I"


def spell_level_ds2(wiz: bytes, cl: bytes, index: int) -> str:
    if index < wiz[-1]:
        for lvl in range(10):
            if wiz[lvl] <= index < wiz[lvl + 1]:
                return str(lvl + 1)
    if index < cl[-1]:
        for lvl in range(10):
            if cl[lvl] <= index < cl[lvl + 1]:
                return str(lvl + 1)
    if index < 269:
        return "P"
    return "I"


def decode_spell_record(
    rec: bytes, index: int, sid: int | None, name: str, level: str
) -> dict:
    return {
        "index": index,
        "id": sid,
        "name": name,
        "level": level,
        "range": i16(rec, 1),
        "dur_n": rec[4] & 0xF,
        "dur_s": rec[4] >> 4,
        "dur_pl": u16(rec, 5),
        "dur_mult": i16(rec, 7),
        "area": u16(rec, 9),
        "area_pl": u8(rec, 11),
        "target": u8(rec, 12),
        "special": u16(rec, 17),
        "effect": i8(rec, 25),
        "effect_type": u16(rec, 26),
        "dmg": u32(rec, 28),
    }


def decode_spells_ds1(spin: dict[int, bytes], exe: bytes) -> list[dict]:
    spells = []
    for index in range(196):
        base = DS1_EXE_POWER_TABLE + index * 32
        rec = exe[base : base + 32]
        if index < 172:
            sid: int | None = index + 1
            name = cstr(spin.get(sid, b"?")).split(":")[0].strip()
        elif index < 179:
            sid = 249 + index - 172
            name = cstr(spin.get(sid, b"?")).split(":")[0].strip()
        else:
            sid = None
            name = f"(innate power {index - 178})"
        spells.append(
            decode_spell_record(rec, index, sid, name, spell_level_ds1(exe, index))
        )
    return spells


def decode_spells_ds2(resource: bytes, exe_path: Path) -> list[dict]:
    exe = exe_path.read_bytes()
    wiz = exe[DS2_WIZ_LEVELS : DS2_WIZ_LEVELS + 11]
    cl = exe[DS2_CL_LEVELS : DS2_CL_LEVELS + 11]
    spells = []
    for index in range(320):
        base = DS2_POWER_TABLE + index * 73
        rec = resource[base : base + 73]
        name = cstr(rec[32:64])
        sid = index + 1 if index < 269 else None
        spells.append(
            decode_spell_record(rec, index, sid, name, spell_level_ds2(wiz, cl, index))
        )
    return spells


# --------------------------------------------------------------------------
# Markdown emission


def fmt_duration(s: dict) -> str:
    mult = s["dur_mult"]
    tag = {0: "instant", -9999: "indefinite"}.get(mult)
    if tag:
        return tag
    base = f"{s['dur_n']}d{s['dur_s']}"
    if s["dur_pl"]:
        base += f"+{s['dur_pl']}/lvl"
    if mult == 60:
        return f"{base} rds/lvl"
    if mult in (600, 3600):
        return f"{base} (x{mult})"
    return f"{base} (m{mult})"


def unpack_damage(d: int) -> tuple[int, int, int, int, int, int, int, int, int]:
    """The packed damage word, byte-wise, low-bits-first per byte
    (docs/object-formats.md section 6). Returns (plus, dice_plus, div,
    dice, sides, scale, savable, save_mod, save_type)."""
    b0 = d & 0xFF
    b1 = (d >> 8) & 0xFF
    b2 = (d >> 16) & 0xFF
    b3 = (d >> 24) & 0xFF
    save_mod = (b3 >> 1) & 0xF
    if save_mod >= 8:
        save_mod -= 16
    return (
        b0 & 0x1F,
        b0 >> 5,
        b1 & 7,
        b1 >> 3,
        b2 & 0xF,
        b2 >> 4,
        b3 & 1,
        save_mod,
        b3 >> 5,
    )


def fmt_damage(s: dict) -> str:
    """Partial derivation of the packed damage word; the raw hex is
    always appended so nothing is lost to a wrong reading
    (docs/object-formats.md section 6)."""
    d = s["dmg"]
    plus, dice_plus, div, dice, sides, scale, savable, _sm, _st = unpack_damage(d)
    if not sides:
        return f"- [0x{d:08x}]"
    notes = []
    if dice_plus and div > 1:
        core = f"((lvl+{dice_plus})/{div})d{sides}"
    elif dice_plus:
        tail = f"+{dice}" if dice else ""
        core = f"({dice_plus}*lvl{tail})d{sides}"
    else:
        core = f"{dice}d{sides}"
        if div > 1:
            notes.append(f"div{div}")
    if plus:
        core += f"+{plus}"
    if scale:
        notes.append(f"sc{scale}")
    if notes:
        core += " (" + ", ".join(notes) + ")"
    return f"{core} [0x{d:08x}]"


def fmt_saves(s: dict) -> str:
    _p, _dp, _dv, _dc, _sd, _sc, savable, save_mod, save_type = unpack_damage(s["dmg"])
    if not savable:
        return "-"
    names = {
        1: "poison",
        2: "wands",
        3: "petr",
        4: "breath",
        5: "spells",
        6: "paral",
        7: "death/magic",
    }
    base = names.get(save_type, str(save_type))
    return f"{base}{save_mod:+d}" if save_mod else base


def emit_spells(out: GameData, lines: list[str]) -> None:
    label = "Shattered Lands" if out.game == "ds1" else "Wake of the Ravager"
    lines.append(f"# Spell catalogue: Dark Sun: {label}")
    lines.append("")
    lines.append(
        "<!-- machine-generated by tools/gff-edit/scripts/"
        "extract-catalogue.py; do not edit -->"
    )
    lines.append("")
    lines.append(
        "Levels: number = spell level; P = psionic; S = stat power;"
        " I = innate monster power. Ids are SPIN ids (record index + 1)"
        " where one exists. The damage column is a partial derivation of"
        " the packed engine word; the raw hex is authoritative"
        " (docs/object-formats.md section 6). DS1 names come from SPIN;"
        " DS2 names from the engine power table."
    )
    lines.append("")
    lines.append(
        "| id | lvl | name | range | duration | area | target"
        " | damage (packed) | save | fx | eff |"
    )
    lines.append("|---:|---|---|---:|---|---:|---:|---|---|---|---:|")
    for s in out.spells:
        sid = s["id"] if s["id"] is not None else "-"
        area = str(s["area"])
        if s["area_pl"]:
            area += f"+{s['area_pl']}/lvl"
        lines.append(
            f"| {sid} | {s['level']} | {s['name']} | {s['range']} "
            f"| {fmt_duration(s)} | {area} | {s['target']} "
            f"| {fmt_damage(s)} | {fmt_saves(s)} "
            f"| 0x{s['effect_type']:04x} | {s['effect']} |"
        )
    lines.append("")


def fmt_attack(c: Creature) -> str:
    slots = []
    for k in range(3):
        halves = c.attacks[k]
        dice, sides, bonus = c.damage[k]
        if not halves or not dice or not sides:
            continue
        text = f"{halves // 2}x{dice}d{sides}"
        if bonus:
            text += f"{bonus:+d}"
        slots.append(text)
    return " + ".join(slots) if slots else "-"


def emit_bestiary(out: GameData, lines: list[str]) -> None:
    label = "Shattered Lands" if out.game == "ds1" else "Wake of the Ravager"
    lines.append(f"# Bestiary: Dark Sun: {label}")
    lines.append("")
    lines.append(
        "<!-- machine-generated by tools/gff-edit/scripts/"
        "extract-catalogue.py; do not edit -->"
    )
    lines.append("")
    lines.append(
        "Every creature record in the game's object database"
        " (combat + character blocks, docs/object-formats.md section 2)."
        " Attacks are the half-round slots (value/2 per round) with"
        " their damage dice. DS2 THAC0 has no stored byte (the engine"
        " derives it from level at runtime). special-attack bytes are"
        " unresolved enums and are not shown; allegiance and alignment"
        " enums are unconfirmed. XP is the charrec value; several DS1"
        " rows carry filler values."
    )
    lines.append("")
    lines.append(
        "| id | name | hp | psp | AC | MV | HD | THAC0 | attacks x damage"
        " | MR% | XP | saves | stats |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|")
    for c in sorted(out.creatures, key=lambda c: c.obj_id):
        thac0 = str(c.thac0) if c.thac0 is not None else "(derived)"
        lines.append(
            f"| {c.obj_id} | {c.name} | {c.hp} | {c.psp} | {c.ac} | {c.move}"
            f" | {c.level[0]} | {thac0} | {fmt_attack(c)} | {c.magic_res}"
            f" | {c.xp} | {'/'.join(str(v) for v in c.saves)}"
            f" | {'/'.join(str(v) for v in c.stats)} |"
        )
    lines.append("")
    if out.minis:
        lines.append("## Named non-combat entities (mini records)")
        lines.append("")
        lines.append("| id | name | priority |")
        lines.append("|---:|---|---:|")
        for m in sorted(out.minis, key=lambda m: m.obj_id):
            lines.append(f"| {m.obj_id} | {m.name} | {m.priority} |")
        lines.append("")
    if out.monr:
        lines.append("## MONR random-encounter table (RESOURCE id 1)")
        lines.append("")
        if out.game == "ds2":
            lines.append(
                "DS2's MONR is stale DS1 carryover"
                " (docs/object-formats.md section 7); rows reference DS1"
                " region and creature ids."
            )
            lines.append("")
        lines.append("| region | creature id (weight) |")
        lines.append("|---:|---|")
        for region, entries in out.monr:
            cells = ", ".join(f"{cid} ({w})" for cid, w in entries if cid)
            lines.append(f"| {region} | {cells} |")
        lines.append("")


def emit_items(out: GameData, lines: list[str]) -> None:
    label = "Shattered Lands" if out.game == "ds1" else "Wake of the Ravager"
    lines.append(f"# Item catalogue: Dark Sun: {label}")
    lines.append("")
    lines.append(
        "<!-- machine-generated by tools/gff-edit/scripts/"
        "extract-catalogue.py; do not edit -->"
    )
    lines.append("")
    lines.append(
        "Every type-1 object in the game's object database. Value is"
        " ceramic (9999/65000 = quest/priceless sentinels). Dice and"
        " to-hit come from the base-stat tables (DS1 IT1R; DS2 15-byte"
        " templates); doors and containers appear alongside gear by"
        " design (they are item records)."
    )
    lines.append("")
    lines.append(
        "| id | name | qty | value | dmg | AC | wgt | mat | slot"
        " | legal | charges | BMP |"
    )
    lines.append("|---:|---|---:|---:|---|---:|---:|---|---|---|---:|---:|")
    for iid in sorted(out.items):
        item = out.items[iid]
        st = item.stats
        if st and st.sides:
            dmg = f"{st.dice}d{st.sides}{st.mod:+d}"
            ac = f"{st.base_ac:+d}" if st.base_ac else "-"
        elif st and st.base_ac:
            dmg = f"AC {st.base_ac:+d}"
            ac = "-"
        else:
            dmg = "-"
            ac = "-"
        weight = str(st.weight) if st else "-"
        material = str(st.material) if st else "-"
        slot = str(st.slot) if st else "-"
        legal = f"0x{st.legal_class:04x}" if st else "-"
        value = (
            f"{item.value} (special)"
            if item.value in (NULL16, 65000)
            else str(item.value)
        )
        charges = str(item.charges) if item.charges else "-"
        lines.append(
            f"| {iid} | {out.item_names.get(iid, '')} | {item.quantity}"
            f" | {value} | {dmg} | {ac} | {weight} | {material} | {slot}"
            f" | {legal} | {charges} | {item.sprite_bmp} |"
        )
    lines.append("")


# --------------------------------------------------------------------------
# Selftest (synthetic fixtures; live anchors run inside the extractors)


def selftest() -> int:
    failures = []

    combat = bytearray(58)
    struct.pack_into("<h", combat, 0, 50)
    struct.pack_into("<h", combat, 4, 95)
    struct.pack_into("<h", combat, 6, -405)
    combat[26] = 2
    combat[31] = 11
    combat[34:40] = bytes([10] * 6)
    combat[40:51] = b"Umber Hulk\x00"
    charrec = bytearray(71)
    struct.pack_into("<I", charrec, 0, 4000)
    struct.pack_into("<H", charrec, 8, 50)
    charrec[36] = 8
    header = struct.pack("<bbhhhh", 1, 0, 2, 325, 71, 58)
    header2 = struct.pack("<bbhhhh", 3, 0, 4, 95, 15, 71)
    end = struct.pack("<bbhhhh", -1, 0, 0, 0, 0, 0)
    chain = header + bytes(combat) + header2 + bytes(charrec) + end
    blocks = walk_rdff(chain, 405)
    failures.append(
        (
            "rdff walk",
            len(blocks) == 2 and blocks[-1].load_action == LA_DATA,
            f"{len(blocks)} blocks (END terminates, not returned)",
        )
    )
    c = decode_creature("ds1", 405, blocks[0].payload, blocks[1].payload, 325)
    failures.append(
        (
            "creature decode",
            c.name == "Umber Hulk"
            and c.hp == 50
            and c.ac == 2
            and c.level[0] == 8
            and c.thac0 == 11,
            f"{c.name} hp={c.hp} ac={c.ac} hd={c.level[0]}",
        )
    )

    s = {"dmg": (3 << 11) | (10 << 16)}
    failures.append(("damage 3d10", "3d10" in fmt_damage(s), fmt_damage(s)))
    s2 = {"dmg": 1 | (8 << 8) | (4 << 16)}
    failures.append(("damage 1d4+1", "1d4+1" in fmt_damage(s2), fmt_damage(s2)))
    s3 = {"dmg": 0x00140221}  # the real Magic Missile word
    failures.append(
        (
            "damage magic missile",
            "((lvl+1)/2)d4+1" in fmt_damage(s3),
            fmt_damage(s3),
        )
    )
    s4 = {"dmg": 0xA1060120}  # the real Fireball word
    failures.append(("damage fireball", "(1*lvl)d6" in fmt_damage(s4), fmt_damage(s4)))

    for label, ok, detail in failures:
        print(f"{'ok' if ok else 'FAIL'}  {label}: {detail}")
    return 0 if all(ok for _l, ok, _d in failures) else 1


# --------------------------------------------------------------------------


def add_footer(lines: list[str], out: GameData) -> None:
    lines.append("## Extraction verification")
    lines.append("")
    for label, ok, detail in out.checks:
        state = "PASS" if ok else "FAIL"
        lines.append(f"- {state}: {label} ({detail})")
    lines.append("")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--games",
        type=Path,
        default=REPO_ROOT / ".games",
        help="games root (default: .games)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "docs",
        help="output directory (default: docs)",
    )
    ap.add_argument("--game", choices=("ds1", "ds2", "both"), default="both")
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="print catalogues instead of writing files",
    )
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if not (args.games / "ds1" / "SEGOBJEX.GFF").is_file():
        print(f"error: game data not found under {args.games}", file=sys.stderr)
        return 3

    games: list[GameData] = []
    docs: dict[str, list[str]] = {}
    for game, extractor in (("ds1", extract_ds1), ("ds2", extract_ds2)):
        if args.game not in (game, "both"):
            continue
        g = extractor(args.games)
        games.append(g)
        for kind, emitter in (
            ("bestiary", emit_bestiary),
            ("item-catalogue", emit_items),
            ("spell-catalogue", emit_spells),
        ):
            lines: list[str] = []
            emitter(g, lines)
            add_footer(lines, g)
            docs[f"{kind}-ds{game[-1]}.md"] = lines

    for name, lines in docs.items():
        text = "\n".join(lines) + "\n"
        if args.stdout:
            print(f"===== {name} =====")
            print(text)
        else:
            (args.out / name).write_text(text)
            print(f"wrote {args.out / name}")

    failed = False
    for g in games:
        for label, ok, detail in g.checks:
            print(f"{'ok' if ok else 'FAIL'}  {g.game} anchor {label}: {detail}")
            failed = failed or not ok
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
