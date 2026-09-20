#!/usr/bin/env python3
"""Build the Wave 4 parity audit sheets: oracle (DOSBox) vs port.

Renders each port screen through Godot Movie Maker (--write-movie PNG
output, no interaction needed), crops the 320x200 board out of the
1280x960 frame (4x integer scale, centred), and stacks it against the
committed oracle capture with labels. Sheets land in port-spike/audit/.

Stdlib + Pillow (already sanctioned for exporters).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
RAW = Path("/tmp/audit-320")
FRAMES = 12  # 0.4 s at 30 fps; last frame is the settled one

# name -> (scene, env, oracle file)
SCREENS = {
    "menu": ("res://menu.tscn", {}, "menu_3000.png"),
    "creation": ("res://wind_test.tscn", {"SPIKE_SCREEN": "creation"}, "creation_3011.png"),
    "inventory": ("res://wind_test.tscn", {"SPIKE_SCREEN": "inventory"}, "inventory_13500_ktarchek.png"),
    "sheet": ("res://wind_test.tscn", {"SPIKE_SCREEN": "sheet"}, "sheet_11500_ktarchek.png"),
    "use": ("res://wind_test.tscn", {"SPIKE_SCREEN": "use"}, "use_spells_ktarchek.png"),
    "effects": ("res://wind_test.tscn", {"SPIKE_SCREEN": "effects"}, "effects_empty_ktarchek.png"),
    "gamemenu": ("res://wind_test.tscn", {"SPIKE_SCREEN": "gamemenu"}, "gamemenu_10500.png"),
    "load": ("res://wind_test.tscn", {"SPIKE_SCREEN": "load"}, "load_3009.png"),
    "map": ("res://wind_test.tscn", {"SPIKE_SCREEN": "map"}, "map_arena.png"),
    "popup": ("res://wind_test.tscn", {"SPIKE_SCREEN": "popup"}, "popup_14000_exitgame.png"),
    "combathud": ("res://wind_test.tscn", {"SPIKE_SCREEN": "combathud"}, "combat_hud_ktarchek.png"),
}


def render(name: str, scene: str, env: dict[str, str]) -> Image.Image:
    out_dir = RAW / name
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.png"):
        stale.unlink()
    if name == "combathud":
        # the movie writer captures black for this bare-Node2D harness;
        # use the plain SPIKE snap and crop the integer-scaled board
        out = out_dir / "snap.png"
        full_env = {**dict(__import__("os").environ), **env, "SPIKE_OUT": str(out)}
        subprocess.run(
            ["godot", "--path", ".", scene],
            env=full_env,
            check=True,
            timeout=180,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        im = Image.open(out).convert("RGBA")
        w, h = im.size
        k = min(w // 320, h // 200)
        bw, bh = 320 * k, 200 * k
        board = im.crop(
            ((w - bw) // 2, (h - bh) // 2, (w - bw) // 2 + bw, (h - bh) // 2 + bh)
        )
        return board.resize((320, 200), Image.NEAREST)
    cmd = [
        "godot",
        "--path",
        ".",
        scene,
        "--write-movie",
        str(out_dir / name) + ".png",
        "--quit-after",
        str(FRAMES),
        "--fixed-fps",
        "30",
    ]
    subprocess.run(
        cmd,
        env={**dict(__import__("os").environ), **env},
        check=True,
        timeout=180,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    frame = sorted(out_dir.glob("*.png"))[-1]
    im = Image.open(frame).convert("RGBA")
    # board: 320x200 at 4x, centred in the 1280x960 movie frame
    w, h = im.size
    k = min(w // 320, h // 200)
    bw, bh = 320 * k, 200 * k
    board = im.crop(
        ((w - bw) // 2, (h - bh) // 2, (w - bw) // 2 + bw, (h - bh) // 2 + bh)
    )
    return board.resize((320, 200), Image.NEAREST)


def sheet(name: str, oracle: Image.Image, port: Image.Image, out: Path) -> None:
    gap, label_h = 12, 18
    W = 320 * 2 + gap * 3
    H = 200 + label_h + gap * 2
    im = Image.new("RGBA", (W, H), (24, 24, 24, 255))
    d = ImageDraw.Draw(im)
    im.paste(oracle, (gap, label_h + gap))
    im.paste(port, (gap * 2 + 320, label_h + gap))
    d.text(
        (gap, 4),
        f"{name}  |  oracle (left)  vs  port (right)",
        fill=(230, 230, 200, 255),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    im.resize((W * 3, H * 3), Image.NEAREST).save(out)


def main() -> None:
    only = sys.argv[1:] or list(SCREENS)
    for name in only:
        scene, env, oracle_png = SCREENS[name]
        oracle = Image.open(HERE / "oracle" / oracle_png).convert("RGBA")
        port = render(name, scene, env)
        sheet(name, oracle, port, HERE / "audit" / f"{name}.png")
        print(f"{name}: audit/{name}.png")


if __name__ == "__main__":
    main()
