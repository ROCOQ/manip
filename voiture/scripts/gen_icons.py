#!/usr/bin/env python3
"""Génère les icônes PNG de l'app (sans dépendance) : une voiture blanche sur fond vert."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
BG = (15, 118, 110)
FG = (255, 255, 255)
GLASS = (153, 222, 214)


def inside_rounded_rect(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def color_at(x: float, y: float):
    """Coordonnées normalisées 0..1. Renvoie la couleur du pixel."""
    # roues
    for wx in (0.31, 0.69):
        d2 = (x - wx) ** 2 + (y - 0.66) ** 2
        if d2 <= 0.085 ** 2:
            return BG if d2 <= 0.035 ** 2 else FG
    # vitres
    if inside_rounded_rect(x, y, 0.33, 0.37, 0.49, 0.48, 0.02) or inside_rounded_rect(x, y, 0.52, 0.37, 0.67, 0.48, 0.02):
        return GLASS
    # habitacle et caisse
    if inside_rounded_rect(x, y, 0.28, 0.31, 0.72, 0.56, 0.07):
        return FG
    if inside_rounded_rect(x, y, 0.14, 0.47, 0.86, 0.67, 0.06):
        return FG
    return BG


def render(size: int, ss: int = 3) -> bytes:
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            acc = [0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    c = color_at((px + (sx + 0.5) / ss) / size, (py + (sy + 0.5) / ss) / size)
                    acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]
            n = ss * ss
            row += bytes((acc[0] // n, acc[1] // n, acc[2] // n))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
        (OUT / name).write_bytes(render(size))
        print("écrit", OUT / name)


if __name__ == "__main__":
    main()
