#!/usr/bin/env python3
"""Export the DS1 bestiary rows the interact INFO path shows.

Walks SEGOBJEX.GFF with extract-catalogue.py's decoder (the same
source docs/bestiary-ds1.md was generated from) and writes
generated/ui/bestiary.json: object id -> {name, hp, ac, thac0, move,
xp, align, dmg}. The interact strip's INFO button shows the row for
the clicked entity's ETAB creature id. Stdlib-only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "generated" / "ui"
DS1 = REPO / ".games" / "ds1"

_spec = importlib.util.spec_from_file_location(
    "opds_extract", REPO / "tools/gff-edit/scripts/extract-catalogue.py"
)
ec = importlib.util.module_from_spec(_spec)
sys.modules["opds_extract"] = ec
_spec.loader.exec_module(ec)


def fmt_damage(c) -> str:
    # docs/bestiary-ds1.md style: "2x1d8+8 + 1x1d4+2"; attacks are
    # half-round slots, so per-round count = value / 2
    slots = []
    for k in range(3):
        dice, sides, bonus = c.damage[k]
        atk = c.attacks[k]
        if atk == 0 or dice == 0:
            break
        mod = f"{bonus:+d}" if bonus else ""
        slots.append(f"{atk // 2}x{dice}d{sides}{mod}")
    return " + ".join(slots)


def main() -> None:
    creatures, _items, _minis, _templates, _stats, _inventories = ec.extract_objects(
        "ds1", DS1 / "SEGOBJEX.GFF"
    )
    out = {}
    for c in creatures:
        out[str(c.obj_id)] = {
            "name": c.name,
            "hp": c.hp,
            "ac": c.ac,
            "thac0": c.thac0,
            "move": c.move,
            "xp": c.xp,
            "align": ec.ALIGNMENT_NAMES[c.alignment]
            if 0 <= c.alignment < len(ec.ALIGNMENT_NAMES)
            else "-",
            "dmg": fmt_damage(c),
        }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bestiary.json").write_text(json.dumps(out, indent=1))
    print(f"bestiary rows: {len(out)}")


if __name__ == "__main__":
    main()
