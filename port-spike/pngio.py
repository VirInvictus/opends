#!/usr/bin/env python3
"""pngio — minimal PNG writer for the port spike.

RGBA8, no filter, one IDAT. Stdlib-only; the spike's atlas and sprite
output. (Reading stays unnecessary: export_region.py decodes the game's
own bitmap containers directly and recolors from the raw palette bytes.)
"""

from __future__ import annotations

import struct
import zlib


def write_rgba(path, width: int, height: int, rgba: bytes) -> None:
    def chunk(typ: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + typ
            + payload
            + struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(
        b"\x00" + rgba[y * width * 4 : (y + 1) * width * 4] for y in range(height)
    )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)
