#!/usr/bin/env python3
"""Export the DS1 UI from the game's own data.

- WIND/3000's items: the four BUTN placements (init positions in the
  320x200 menu space) and the ACCL/8100 accelerator.
- The button faces are ICON/2048..2051 (the flaming menu text), decoded
  to PNG with the game palette via tools/image-extract.
- ACCL/8100 keys: S/C/L/E upper+lower -> userids 8100..8107.
- EVERY WIND (27 of them) dumps to winds.json: window rect, border
  plate, and per-item type/id/pos plus the resolved BUTN/EBOX/APFM
  geometry, icon ids and shipped text. Referenced ICON faces (every
  frame, unflattened) and border BMP plates export as PNGs.

Writes generated/ui/ui.json + winds.json + the art PNGs. Stdlib-only;
shells out to image-extract, post-fixes PNGs with Pillow.
"""

from __future__ import annotations

import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "generated" / "ui"
RESOURCE = REPO / ".games" / "ds1" / "RESOURCE.GFF"
IMAGE_EXTRACT = REPO / "target" / "debug" / "image-extract"

_spec = importlib.util.spec_from_file_location(
    "opds_extract", REPO / "tools/gff-edit/scripts/extract-catalogue.py"
)
ec = importlib.util.module_from_spec(_spec)
sys.modules["opds_extract"] = ec
_spec.loader.exec_module(ec)

MENU_WIND = 3000
BUTTON_IDS = [2048, 2049, 2050, 2051]
NAMES = ["start", "create", "load", "exit"]
ACCL_ID = 8100
# The menu screen furniture: BMP 20028 is the burning arc with the green
# orb, BMP 20029 the ornate stone panel (both 2026-09-19, matched against
# a DOSBox capture of the real boot menu).
ARC_BMP = 20028
PANEL_BMP = 20029
# Measured off the real menu: the arc sits above the panel, both centred.
ARC_POS = [49, 38]
PANEL_POS = [3, 55]


def _postfix_png(path: Path) -> None:
    """image-extract emits top-down RGB with palette index 0 opaque; the
    menu art is stored top-down (so the tool's bottom-up flip shows it
    inverted) and index 0 is the transparent background. Flip back and
    punch index 0 out."""
    from PIL import Image

    pal_chunk = ec.get_chunk(ec.parse_gff(RESOURCE), "PAL", 1000)
    bg = (pal_chunk[0] * 255 // 63, pal_chunk[1] * 255 // 63, pal_chunk[2] * 255 // 63)
    im = Image.open(path).convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, _ = px[x, y]
            # image-extract rounds palette scaling slightly differently
            # (84 vs 85), so match the background index with tolerance
            if abs(r - bg[0]) <= 2 and abs(g - bg[1]) <= 2 and abs(b - bg[2]) <= 2:
                px[x, y] = (r, g, b, 0)
    im.save(path)


def _export_bitmap(kind: str, bid: int, name: str) -> dict:
    out_png = OUT / f"{name}.png"
    rr = subprocess.run(
        [
            str(IMAGE_EXTRACT),
            str(RESOURCE),
            "--kind",
            kind,
            "--id",
            str(bid),
            "--frame",
            "0",
            "-o",
            str(out_png),
            "--palette",
            "1000",
        ],
        capture_output=True,
        text=True,
    )
    if rr.returncode != 0:
        print(f"{kind} {bid} failed:", rr.stderr[-160:])
        return {}
    d = out_png.read_bytes()
    w, h = struct.unpack_from(">II", d, 16)
    _postfix_png(out_png)
    return {"png": f"{name}.png", "w": w, "h": h}


def _resolve_item(res, kind: str, iid: int) -> dict:
    """Pull the geometry/icon/text payload out of a BUTN/EBOX/APFM item
    chunk. BUTN and APFM keep their hot-zone frame at +40/+42; the EBOX
    frame sits at +34/+36 instead."""
    try:
        c = ec.get_chunk(res, kind, iid)
    except Exception:
        return {}
    out: dict = {"chunk_len": len(c)}
    if kind == "EBOX":
        out["w"], out["h"] = ec.i16(c, 34), ec.i16(c, 36)
        return out
    out["w"] = ec.i16(c, 40)
    out["h"] = ec.i16(c, 42)
    if kind == "BUTN":
        # field-by-field gates: shipped BUTN chunks run 110..114+ bytes
        if len(c) >= 90:
            out["flags"] = ec.u16(c, 88)
        if len(c) >= 92:
            out["userid"] = ec.u16(c, 90)
        if len(c) >= 104:
            out["iconx"] = ec.i16(c, 92)
            out["icony"] = ec.i16(c, 94)
            out["textx"] = ec.i16(c, 96)
            out["texty"] = ec.i16(c, 98)
            out["icon_id"] = ec.u32(c, 100)
        if len(c) >= 110:
            out["hotkey"] = ec.u8(c, 108)
            tlen = ec.u8(c, 109)
            out["text"] = c[110 : 110 + tlen].decode("ascii", "replace").rstrip("\x00")
    return out


def _export_icon_frames(res, icon_id: int) -> list[dict]:
    """Every frame of an ICON, named icon<id>_f<n>.png (state frames
    stay unflattened: the state model, not animation, decides which
    frame a button shows)."""
    pngs = []
    try:
        icon = ec.get_chunk(res, "ICON", icon_id)
    except Exception:
        return pngs
    count = ec.u16(icon, 4)
    for fi in range(count):
        name = f"icon{icon_id}_f{fi}"
        out_png = OUT / f"{name}.png"
        if not out_png.exists():
            rr = subprocess.run(
                [
                    str(IMAGE_EXTRACT),
                    str(RESOURCE),
                    "--kind",
                    "ICON",
                    "--id",
                    str(icon_id),
                    "--frame",
                    str(fi),
                    "-o",
                    str(out_png),
                    "--palette",
                    "1000",
                ],
                capture_output=True,
                text=True,
            )
            if rr.returncode != 0:
                print(f"ICON {icon_id} f{fi} failed:", rr.stderr[-120:])
                continue
            _postfix_png(out_png)
        d = out_png.read_bytes()
        w, h = struct.unpack_from(">II", d, 16)
        pngs.append({"png": f"{name}.png", "w": w, "h": h})
    return pngs


def _export_bmp_plate(bmp_id: int) -> dict | None:
    name = f"bmp{bmp_id}"
    out_png = OUT / f"{name}.png"
    if not out_png.exists():
        rr = subprocess.run(
            [
                str(IMAGE_EXTRACT),
                str(RESOURCE),
                "--kind",
                "BMP",
                "--id",
                str(bmp_id),
                "--frame",
                "0",
                "-o",
                str(out_png),
                "--palette",
                "1000",
            ],
            capture_output=True,
            text=True,
        )
        if rr.returncode != 0:
            print(f"BMP {bmp_id} failed:", rr.stderr[-120:])
            return None
        _postfix_png(out_png)
    d = out_png.read_bytes()
    w, h = struct.unpack_from(">II", d, 16)
    return {"png": f"{name}.png", "w": w, "h": h}


def _make_creation_bg() -> str:
    """The creation backdrop regenerates from the committed oracle
    capture with every dynamic text region patched over using clean
    texture strips of the same capture (leather and parchment), so the
    port's live TextBlitter rows do not ghost against baked pixels."""
    import numpy as np
    from PIL import Image

    src = HERE / "oracle" / "creation_3011.png"
    im = Image.open(src).convert("RGBA")

    arr = np.asarray(im).copy()

    def inpaint_text(x0: int, y0: int, x1: int, y1: int) -> None:
        """Blank the engine-printed text inside a panel: pixels that are
        neither parchment nor burned border get replaced by the local
        parchment median, dilated until no holes remain."""
        reg = arr[y0:y1, x0:x1, :3].astype(float)
        r, g, b = reg[:,:,0], reg[:,:,1], reg[:,:,2]
        # parchment is warm and bright; text is steel-blue or dark brown
        text = ((b >= r) & (r > 90)) | ((r < 110) & (g < 75) & (b < 60))
        known = ~text
        for _ in range(12):
            if known.all():
                break
            H, W = reg.shape[:2]
            padr = np.pad(reg, ((1, 1), (1, 1), (0, 0)), mode="edge")
            padk = np.pad(known, 1, mode="edge")
            sums = np.zeros((H, W, 3))
            cnt = np.zeros((H, W))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    nk = padk[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                    nv = padr[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                    sums += nv * nk[:, :, None]
                    cnt += nk
            fill = cnt > 0
            todo = (~known) & fill
            reg[todo] = (sums[todo] / cnt[todo][:, None]).astype(arr.dtype)
            known |= todo
        arr[y0:y1, x0:x1, :3] = np.clip(reg, 0, 255).astype(arr.dtype)

    # stat block + name row sit on leather; tile clean leather over them
    def patch(band: tuple[int, int, int, int], tile: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = band
        tx, ty, tw, th = tile
        strip = arr[ty:ty + th, tx:tx + tw].copy()
        y = y0
        while y < y1:
            h = min(th, y1 - y)
            x = x0
            while x < x1:
                w = min(tw, x1 - x)
                arr[y:y + h, x:x + w] = strip[:h, :w]
                x += tw
            y += th

    # class list and discipline rows: engine-printed text on parchment
    inpaint_text(216, 4, 314, 73)
    inpaint_text(212, 102, 316, 128)

    dst = OUT / "bg_3011.png"
    Image.fromarray(arr).save(dst)
    return "bg_3011.png"


def _export_title_plates() -> None:
    """Per-screen flame title plates (EFFECTS / VIEW CHARACTER / MAP)."""
    for bid in (20075, 20079, 20080, 20087):
        _export_bmp_plate(bid)


def _make_inventory_bg() -> str:
    """Inventory backdrop from the committed oracle capture with the
    dynamic text (party HP/status, stat values, money, name) in-painted
    away; those rows draw live. Static furniture stays baked."""
    import numpy as np
    from PIL import Image

    src = HERE / "oracle" / "inventory_13500_ktarchek.png"
    im = Image.open(src).convert("RGBA")
    arr = np.asarray(im).copy()

    def inpaint_light(x0: int, y0: int, x1: int, y1: int) -> None:
        reg = arr[y0:y1, x0:x1, :3].astype(float)
        r, g, b = reg[:,:,0], reg[:,:,1], reg[:,:,2]
        text = (r > 140) & (g > 140) & (b > 140)
        known = ~text
        for _ in range(12):
            if known.all():
                break
            H, W = reg.shape[:2]
            padr = np.pad(reg, ((1, 1), (1, 1), (0, 0)), mode="edge")
            padk = np.pad(known, 1, mode="edge")
            sums = np.zeros((H, W, 3))
            cnt = np.zeros((H, W))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    nk = padk[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                    nv = padr[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                    sums += nv * nk[:, :, None]
                    cnt += nk
            fill = cnt > 0
            todo = (~known) & fill
            reg[todo] = (sums[todo] / cnt[todo][:, None]).astype(arr.dtype)
            known |= todo
        arr[y0:y1, x0:x1, :3] = np.clip(reg, 0, 255).astype(arr.dtype)

    # party strip HP/status under each of the four slots
    for i in range(4):
        inpaint_light(2, 39 + 48 * i, 46, 55 + 48 * i)
    # right stat panel: yellow engine-printed values, labels, PSI and
    # the weapon readout lines - mask catches yellow, bright and dark
    # relief pixels, stone grey survives
    stat = (225, 48, 318, 152)
    reg = arr[stat[1]:stat[3], stat[0]:stat[2], :3].astype(float)
    r, g, b = reg[:,:,0], reg[:,:,1], reg[:,:,2]
    text = ((r > 165) & (g > 140) & (b < 135)) | ((r > 170) & (g > 170) & (b > 170)) \
        | ((r < 85) & (g < 85) & (b < 85))
    known = ~text
    for _ in range(12):
        if known.all():
            break
        H, W = reg.shape[:2]
        padr = np.pad(reg, ((1, 1), (1, 1), (0, 0)), mode="edge")
        padk = np.pad(known, 1, mode="edge")
        sums = np.zeros((H, W, 3))
        cnt = np.zeros((H, W))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                nk = padk[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                nv = padr[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                sums += nv * nk[:, :, None]
                cnt += nk
        fill = cnt > 0
        todo = (~known) & fill
        reg[todo] = (sums[todo] / cnt[todo][:, None]).astype(arr.dtype)
        known |= todo
    arr[stat[1]:stat[3], stat[0]:stat[2], :3] = np.clip(reg, 0, 255).astype(arr.dtype)
    # money readout and name plate text
    inpaint_light(50, 178, 130, 198)
    inpaint_light(56, 0, 160, 16)
    dst = OUT / "bg_13500.png"
    Image.fromarray(arr).save(dst)
    return "bg_13500.png"


def export_winds(res) -> dict:
    """Dump all WIND windows: rect, border plate, and each item with its
    referenced chunk resolved (size, icon, shipped text)."""
    winds = {}
    icon_cache: dict[int, list[dict]] = {}
    plates: dict[int, dict | None] = {}
    # Full-screen backdrop plates: BMP ids chosen to mirror their window
    # ids where the engine ships one. 3011's leather-and-parchment
    # backdrop has no pinned BMP, so it regenerates from the committed
    # oracle capture (static furniture; dynamic layers draw over it).
    bg_bmps = {
        11500: 11000,
        13500: 13001,
        10500: 10000,
        10501: 10001,
        3009: 3009,
        15500: 15000,
        15502: 15001,
        14000: 14000,
    }
    for wid, raw in ec.resolve_type(res, "WIND"):
        items = []
        count = ec.u16(raw, 243)
        for k in range(count):
            o = 261 + 30 * k
            fourcc = raw[o + 4 : o + 8].decode("ascii", "replace").rstrip("\x00 ")
            iid = ec.u32(raw, o + 8)
            ix, iy = ec.i16(raw, o + 12), ec.i16(raw, o + 14)
            item: dict = {"type": fourcc, "id": iid, "x": ix, "y": iy}
            if fourcc in ("BUTN", "EBOX", "APFM"):
                item.update(_resolve_item(res, fourcc, iid))
                icon_id = item.get("icon_id") or 0
                if fourcc == "BUTN" and icon_id:
                    if icon_id not in icon_cache:
                        icon_cache[icon_id] = _export_icon_frames(res, icon_id)
                    item["icon_frames"] = icon_cache[icon_id]
            items.append(item)
        wind = {
            "id": wid,
            "x": ec.i16(raw, 150),
            "y": ec.i16(raw, 152),
            "w": ec.i16(raw, 190),
            "h": ec.i16(raw, 192),
            "border_bmp": ec.u32(raw, 194),
            "items": items,
        }
        bb = wind["border_bmp"]
        if bb:
            if bb not in plates:
                plates[bb] = _export_bmp_plate(bb)
            wind["border_png"] = (plates[bb] or {}).get("png")
        if wid in bg_bmps:
            art = _export_bmp_plate(bg_bmps[wid])
            wind["bg_png"] = art["png"] if art else None
        elif wid == 13500:
            wind["bg_png"] = _make_inventory_bg()
        elif wid == 3011:
            wind["bg_png"] = _make_creation_bg()
        winds[str(wid)] = wind
        print(
            f"WIND {wid}: {wind['w']}x{wind['h']} at ({wind['x']},{wind['y']})"
            f" border={bb} items={count}"
        )
    _export_title_plates()
    (OUT / "winds.json").write_text(json.dumps(winds, indent=1))
    print(
        f"wrote winds.json ({len(winds)} windows), "
        f"{len(icon_cache)} icon faces, {len(plates)} plates"
    )
    return winds


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = ec.parse_gff(RESOURCE)

    wind = ec.get_chunk(res, "WIND", MENU_WIND)
    items = []
    for k in range(5):  # WIND/3000: ACCL + 4 BUTN
        o = 261 + 30 * k
        fourcc = wind[o + 4 : o + 8].decode("ascii", "replace").rstrip("\x00 ")
        iid = struct.unpack_from("<I", wind, o + 8)[0]
        init = struct.unpack_from("<2h", wind, o + 12)
        items.append({"type": fourcc, "id": iid, "init": list(init)})
    print("WIND/3000 items:", items)

    ui: dict = {"menu_space": [320, 200], "buttons": [], "keys": []}
    ui["arc"] = dict(_export_bitmap("BMP", ARC_BMP, "menu_arc"), pos=ARC_POS)
    ui["panel"] = dict(_export_bitmap("BMP", PANEL_BMP, "menu_panel"), pos=PANEL_POS)
    sys.path.insert(0, str(HERE))
    import export_cine

    for i, bid in enumerate(BUTTON_IDS):
        icon = ec.get_chunk(res, "ICON", bid)
        count = struct.unpack_from("<H", icon, 4)[0]
        pngs = []
        wh = None
        for fi in range(count):
            out_png = OUT / f"menu_{NAMES[i]}_{fi}.png"
            rr = subprocess.run(
                [
                    str(IMAGE_EXTRACT),
                    str(RESOURCE),
                    "--kind",
                    "ICON",
                    "--id",
                    str(bid),
                    "--frame",
                    str(fi),
                    "-o",
                    str(out_png),
                    "--palette",
                    "1000",
                ],
                capture_output=True,
                text=True,
            )
            if rr.returncode != 0:
                print(f"icon {bid} frame {fi} failed:", rr.stderr[-160:])
                continue
            # dims from the PNG header (IHDR)
            d = out_png.read_bytes()
            w, h = struct.unpack_from(">II", d, 16)
            _postfix_png(out_png)
            pngs.append({"png": f"menu_{NAMES[i]}_{fi}.png", "w": w, "h": h})
            wh = (w, h)
        pos = next(
            (it["init"] for it in items if it["type"] == "BUTN" and it["id"] == bid),
            [0, 0],
        )
        ui["buttons"].append(
            {
                "name": NAMES[i],
                "id": bid,
                "x": pos[0],
                "y": pos[1],
                "w": wh[0] if wh else 0,
                "h": wh[1] if wh else 0,
                "frames": pngs,
                "frame_count": len(pngs),
            }
        )
        print(
            f"button {NAMES[i]}: ICON {bid} {count} frames, "
            f"{len(pngs)} exported at {pos}"
        )

    pal_chunk = ec.get_chunk(res, "PAL", 1000)
    pal = [
        (
            pal_chunk[j] * 255 // 63,
            pal_chunk[j + 1] * 255 // 63,
            pal_chunk[j + 2] * 255 // 63,
        )
        for j in range(0, 768, 3)
    ]
    accl = ec.get_chunk(res, "ACCL", ACCL_ID)
    count = struct.unpack_from("<H", accl, 12)[0]
    for k in range(count):
        o = 14 + 5 * k
        ui["keys"].append(
            {
                "event": struct.unpack_from("<H", accl, o + 1)[0],
                "userid": struct.unpack_from("<H", accl, o + 3)[0],
            }
        )

    json.dump(ui, open(HERE / "generated" / "ui.json", "w"), indent=1)
    print(f"wrote {OUT}/ + ui.json")

    export_winds(res)


if __name__ == "__main__":
    main()
