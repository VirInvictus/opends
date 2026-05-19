#!/usr/bin/env python3
"""ds1-party-edit: experiment with editing DS1 party members in DARKRUN.GFF.

Operates on BOTH DARKRUN.GFF and SAVE01.SAV (they're byte-identical
at save time per save-inspect v0.6.0; the engine reads SAVE01 on
load and writes DARKRUN during play). Edits go to both so changes
survive a reload.

Layout (RE'd 2026-05-18 by editing Brandon's actual played save):

  SAVE-5 chunk = array of DS1 combat sub-blocks (58 bytes each),
                 one per party PC, in display order. The name is
                 at offset 40..57 of each record (NULL-terminated,
                 padded). Stats[6] at offset 34..39 (STR DEX CON
                 INT WIS CHR), but the engine reads these for HP
                 / display only; combat damage is computed from
                 the SAVE-6 character sub-block.

  SAVE-6 chunk = array of DS1 character sub-blocks (71-72 bytes
                 each), same order as SAVE-5. THIS is where the
                 engine reads damage dice / damage bonus / level
                 / etc. Editing stats here AND in SAVE-5 keeps
                 the display consistent.

Editing notes:

  Stats above 25 break the engine's 2e bonus tables and produce
  +0 damage bonus. Setting STR 99 with a 1d1 cached weapon =
  1 damage per hit. For godmode try setting num_dice/num_sides/
  num_bonuses to large values instead (e.g. 5d20+50).

Usage examples:

  # List PCs in this save
  ds1-party-edit.py list

  # See one PC's full combat + character record
  ds1-party-edit.py show Gerakis

  # Edit stats (combat AND character, kept in sync)
  ds1-party-edit.py edit Gerakis --str 24 --dex 18 --con 22

  # Edit weapon damage (5d20+50 makes him hit like a truck)
  ds1-party-edit.py edit Gerakis --weapon-dice 5 --weapon-sides 20 --weapon-bonus 50

  # Edit current/max HP and PSP
  ds1-party-edit.py edit Gerakis --hp 999 --max-hp 999 --psp 200 --max-psp 200

  # Edit XP (instant level-up effect on next reload)
  ds1-party-edit.py edit Gerakis --xp 50000

  # Restore from backup
  ds1-party-edit.py restore

Default paths target Brandon's Wine install; --darkrun / --save01
override.

The script auto-backs up to <file>.bak.ds1-party-edit.<timestamp>
on every edit. `restore` flag rolls back to the most recent backup
pair.
"""

from __future__ import annotations

import argparse
import shutil
import struct
import sys
from pathlib import Path

DEFAULT_DARKRUN = Path.home() / ".wine/drive_c/GOG Games/Dark Sun/DARKRUN.GFF"
DEFAULT_SAVE01 = Path.home() / ".wine/drive_c/GOG Games/Dark Sun/SAVE01.SAV"

# Offsets within the relevant SAVE chunks (relative to chunk start).
# SAVE-5 (combat sub-blocks; 58 bytes per record):
COMBAT_RECORD_SIZE = 58
COMBAT_HP_OFF = 0          # i16
COMBAT_PSP_OFF = 2         # i16
COMBAT_STATS_OFF = 34      # u8[6]
COMBAT_NAME_OFF = 40       # char[18]

# SAVE-6 (character sub-blocks; 71-72 bytes per record):
CHAR_RECORD_SIZE = 72      # ds1_character_t with palette byte
CHAR_CURRENT_XP_OFF = 0    # u32
CHAR_HIGH_XP_OFF = 4       # u32
CHAR_BASE_HP_OFF = 8       # u16
CHAR_HIGH_HP_OFF = 10      # u16
CHAR_BASE_PSP_OFF = 12     # u16
CHAR_STATS_OFF = 27        # u8[6] (after the 21-byte preamble)
CHAR_NUM_DICE_OFF = 46     # u8[3]
CHAR_NUM_SIDES_OFF = 49    # u8[3]
CHAR_NUM_BONUSES_OFF = 52  # u8[3]


def parse_gff_chunk(data: bytes, kind: bytes, chunk_id: int) -> tuple[int, int]:
    """Return (chunk_offset, chunk_length) inside a GFF file for a
    given (kind, id). Light parser; just walks the TOC. Returns
    (-1, 0) if not found.
    """
    # GFF header: bytes 0..3 = "GFFI"; bytes 4..7 version; 8..11
    # data_location; 12..15 toc_location; 16..19 toc_length;
    # 20..23 file_flags; 24..27 data0.
    if data[:4] != b"GFFI":
        raise SystemExit("not a GFF file (bad magic)")
    toc_loc = struct.unpack_from("<I", data, 12)[0]
    types_off = struct.unpack_from("<I", data, toc_loc)[0]
    cursor = toc_loc + types_off
    num_types = struct.unpack_from("<H", data, cursor)[0]
    cursor += 2
    for _ in range(num_types):
        type_kind = data[cursor:cursor + 4]
        raw_count = struct.unpack_from("<I", data, cursor + 4)[0]
        cursor += 8
        if raw_count & 0x80000000:
            raise SystemExit(f"segmented chunk type {type_kind!r}; not handled")
        for _ in range(raw_count):
            res_id, location, length = struct.unpack_from("<iII", data, cursor)
            cursor += 12
            if type_kind == kind and res_id == chunk_id:
                return location, length
    return -1, 0


def find_party_records(darkrun: bytes) -> list[dict]:
    """Walk SAVE-5 and return per-PC records: name, combat-abs-offset,
    char-abs-offset. Pairs combat (SAVE-5 record N) with character
    (SAVE-6 record N).
    """
    s5_off, s5_len = parse_gff_chunk(darkrun, b"SAVE", 5)
    s6_off, s6_len = parse_gff_chunk(darkrun, b"SAVE", 6)
    if s5_off < 0:
        raise SystemExit("SAVE/5 chunk not in DARKRUN; not a played DS1 save")
    # Walk combat records (58 bytes each); stop at first record
    # whose name is empty (= unused slot).
    pcs: list[dict] = []
    for i in range(8):  # DS1 supports up to 4-8 party
        record_off = s5_off + i * COMBAT_RECORD_SIZE
        if record_off + COMBAT_RECORD_SIZE > s5_off + s5_len:
            break
        name_field = darkrun[record_off + COMBAT_NAME_OFF:
                             record_off + COMBAT_NAME_OFF + 18]
        # Strip at first null. Empty -> end of party.
        name = name_field.split(b"\x00", 1)[0].decode("latin-1", errors="replace")
        if not name:
            break
        char_record_off = s6_off + i * CHAR_RECORD_SIZE if s6_off >= 0 else -1
        pcs.append({
            "index": i,
            "name": name,
            "combat_abs": record_off,
            "char_abs": char_record_off,
        })
    return pcs


def find_pc(pcs: list[dict], who: str) -> dict:
    """Resolve --pc by index (numeric) or by name (case-insensitive
    substring match)."""
    if who.isdigit():
        idx = int(who)
        if 0 <= idx < len(pcs):
            return pcs[idx]
        raise SystemExit(f"PC index {idx} out of range (0..{len(pcs)-1})")
    matches = [p for p in pcs if who.lower() in p["name"].lower()]
    if not matches:
        raise SystemExit(f"no PC name matching {who!r}; available: "
                         + ", ".join(p["name"] for p in pcs))
    if len(matches) > 1:
        raise SystemExit(f"multiple PCs matching {who!r}: "
                         + ", ".join(p["name"] for p in matches))
    return matches[0]


def show(args: argparse.Namespace) -> int:
    data = args.darkrun.read_bytes()
    pcs = find_party_records(data)
    pc = find_pc(pcs, args.pc)
    print(f"PC {pc['index']}: {pc['name']}")
    print(f"  combat record at abs offset {pc['combat_abs']}")
    print(f"  char record   at abs offset {pc['char_abs']}")
    co = pc["combat_abs"]
    hp = struct.unpack_from("<h", data, co + COMBAT_HP_OFF)[0]
    psp = struct.unpack_from("<h", data, co + COMBAT_PSP_OFF)[0]
    stats = list(data[co + COMBAT_STATS_OFF:co + COMBAT_STATS_OFF + 6])
    print(f"  combat HP={hp} PSP={psp} stats={stats} (STR DEX CON INT WIS CHR)")
    if pc["char_abs"] >= 0:
        ho = pc["char_abs"]
        xp = struct.unpack_from("<I", data, ho + CHAR_CURRENT_XP_OFF)[0]
        max_hp = struct.unpack_from("<H", data, ho + CHAR_BASE_HP_OFF)[0]
        max_psp = struct.unpack_from("<H", data, ho + CHAR_BASE_PSP_OFF)[0]
        cstats = list(data[ho + CHAR_STATS_OFF:ho + CHAR_STATS_OFF + 6])
        nd = list(data[ho + CHAR_NUM_DICE_OFF:ho + CHAR_NUM_DICE_OFF + 3])
        ns = list(data[ho + CHAR_NUM_SIDES_OFF:ho + CHAR_NUM_SIDES_OFF + 3])
        nb = list(data[ho + CHAR_NUM_BONUSES_OFF:ho + CHAR_NUM_BONUSES_OFF + 3])
        print(f"  char   XP={xp} max_hp={max_hp} max_psp={max_psp}")
        print(f"  char   stats={cstats}")
        print(f"  char   weapon: {nd[0]}d{ns[0]}+{nb[0]} (num_dice/sides/bonuses [0..2] = {nd} / {ns} / {nb})")
    return 0


def list_pcs(args: argparse.Namespace) -> int:
    data = args.darkrun.read_bytes()
    pcs = find_party_records(data)
    print(f"{len(pcs)} party PC(s) in {args.darkrun}:")
    for p in pcs:
        co = p["combat_abs"]
        hp = struct.unpack_from("<h", data, co + COMBAT_HP_OFF)[0]
        stats = list(data[co + COMBAT_STATS_OFF:co + COMBAT_STATS_OFF + 6])
        print(f"  {p['index']}  {p['name']:14}  HP={hp:>4}  stats={stats}")
    return 0


def edit(args: argparse.Namespace) -> int:
    # Read DARKRUN to find offsets; apply same edits to both files.
    darkrun_bytes = args.darkrun.read_bytes()
    save01_bytes = args.save01.read_bytes()
    if len(darkrun_bytes) != len(save01_bytes):
        print(
            f"warning: DARKRUN ({len(darkrun_bytes)}B) and SAVE01 "
            f"({len(save01_bytes)}B) differ in size; they should be "
            "byte-identical at save time. Proceeding anyway.",
            file=sys.stderr,
        )
    pcs = find_party_records(darkrun_bytes)
    pc = find_pc(pcs, args.pc)
    co = pc["combat_abs"]
    ho = pc["char_abs"]
    log: list[str] = []

    # Mutable buffers; the `both` closure swaps the bytes in place.
    darkrun_buf = bytearray(darkrun_bytes)
    save01_buf = bytearray(save01_bytes)

    def both(off: int, new_bytes: bytes, label: str) -> None:
        before_d = bytes(darkrun_buf[off:off + len(new_bytes)])
        darkrun_buf[off:off + len(new_bytes)] = new_bytes
        save01_buf[off:off + len(new_bytes)] = new_bytes
        log.append(f"  {label}: {before_d.hex(' ')} -> {new_bytes.hex(' ')}")

    # Combat record edits
    if args.hp is not None:
        both(co + COMBAT_HP_OFF, struct.pack("<h", args.hp), f"combat.hp -> {args.hp}")
    if args.psp is not None:
        both(co + COMBAT_PSP_OFF, struct.pack("<h", args.psp), f"combat.psp -> {args.psp}")
    stat_edits = [
        ("str", 0), ("dex", 1), ("con", 2),
        ("int", 3), ("wis", 4), ("cha", 5),
    ]
    for stat_key, stat_idx in stat_edits:
        v = getattr(args, stat_key, None)
        if v is not None:
            # Combat stats
            both(co + COMBAT_STATS_OFF + stat_idx, bytes([v]),
                 f"combat.stats.{stat_key} -> {v}")
            # Char stats
            if ho >= 0:
                both(ho + CHAR_STATS_OFF + stat_idx, bytes([v]),
                     f"char.stats.{stat_key} -> {v}")
    # Character record edits
    if ho >= 0:
        if args.max_hp is not None:
            both(ho + CHAR_BASE_HP_OFF, struct.pack("<H", args.max_hp),
                 f"char.base_hp -> {args.max_hp}")
        if args.max_psp is not None:
            both(ho + CHAR_BASE_PSP_OFF, struct.pack("<H", args.max_psp),
                 f"char.base_psp -> {args.max_psp}")
        if args.xp is not None:
            both(ho + CHAR_CURRENT_XP_OFF, struct.pack("<I", args.xp),
                 f"char.current_xp -> {args.xp}")
        if args.weapon_dice is not None:
            both(ho + CHAR_NUM_DICE_OFF, bytes([args.weapon_dice]),
                 f"char.num_dice[0] -> {args.weapon_dice}")
        if args.weapon_sides is not None:
            both(ho + CHAR_NUM_SIDES_OFF, bytes([args.weapon_sides]),
                 f"char.num_sides[0] -> {args.weapon_sides}")
        if args.weapon_bonus is not None:
            both(ho + CHAR_NUM_BONUSES_OFF, bytes([args.weapon_bonus]),
                 f"char.num_bonuses[0] -> {args.weapon_bonus}")

    if not log:
        print("error: no edit flags given. See --help for available fields.",
              file=sys.stderr)
        return 2

    print(f"PC {pc['index']}: {pc['name']}")
    for line in log:
        print(line)

    if args.dry_run:
        print("\ndry-run: no file written.")
        return 0

    # Backup both files (latest mtime in the filename for collision-free)
    import time
    ts = int(time.time())
    dr_bak = args.darkrun.with_name(args.darkrun.name + f".bak.ds1-party-edit.{ts}")
    sv_bak = args.save01.with_name(args.save01.name + f".bak.ds1-party-edit.{ts}")
    if not args.no_backup:
        shutil.copy(args.darkrun, dr_bak)
        shutil.copy(args.save01, sv_bak)
    args.darkrun.write_bytes(bytes(darkrun_buf))
    args.save01.write_bytes(bytes(save01_buf))
    print(f"\nwrote {args.darkrun}")
    print(f"wrote {args.save01}")
    if not args.no_backup:
        print(f"backups: {dr_bak}\n         {sv_bak}")
    return 0


def restore(args: argparse.Namespace) -> int:
    # Find the most recent ds1-party-edit backup pair.
    dr_baks = sorted(args.darkrun.parent.glob(args.darkrun.name + ".bak.ds1-party-edit.*"))
    sv_baks = sorted(args.save01.parent.glob(args.save01.name + ".bak.ds1-party-edit.*"))
    if not dr_baks or not sv_baks:
        print(f"no ds1-party-edit backups found alongside {args.darkrun}",
              file=sys.stderr)
        return 1
    dr = dr_baks[-1]
    sv = sv_baks[-1]
    shutil.copy(dr, args.darkrun)
    shutil.copy(sv, args.save01)
    print(f"restored from:\n  {dr}\n  {sv}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ds1-party-edit", description=__doc__.splitlines()[0])
    p.add_argument("--darkrun", type=Path, default=DEFAULT_DARKRUN,
                   help="path to DARKRUN.GFF")
    p.add_argument("--save01", type=Path, default=DEFAULT_SAVE01,
                   help="path to SAVE01.SAV (engine reads this on load)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list party PCs")
    p_list.set_defaults(handler=list_pcs)

    p_show = sub.add_parser("show", help="show one PC's full record")
    p_show.add_argument("pc", help="PC index (0-based) or name substring")
    p_show.set_defaults(handler=show)

    p_edit = sub.add_parser("edit", help="edit one PC's fields")
    p_edit.add_argument("pc", help="PC index or name substring")
    p_edit.add_argument("--hp", type=int)
    p_edit.add_argument("--psp", type=int)
    p_edit.add_argument("--max-hp", type=int)
    p_edit.add_argument("--max-psp", type=int)
    p_edit.add_argument("--xp", type=int)
    for stat in ("str", "dex", "con", "int", "wis", "cha"):
        p_edit.add_argument(f"--{stat}", type=int)
    p_edit.add_argument("--weapon-dice", type=int,
                        help="num_dice[0] (number of damage dice)")
    p_edit.add_argument("--weapon-sides", type=int,
                        help="num_sides[0] (die size, e.g. 6 = 1d6)")
    p_edit.add_argument("--weapon-bonus", type=int,
                        help="num_bonuses[0] (flat damage bonus)")
    p_edit.add_argument("--dry-run", action="store_true")
    p_edit.add_argument("--no-backup", action="store_true")
    p_edit.set_defaults(handler=edit)

    p_restore = sub.add_parser("restore",
                               help="restore from the most recent .bak.ds1-party-edit.* pair")
    p_restore.set_defaults(handler=restore)

    args = p.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
