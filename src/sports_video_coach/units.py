"""Find and load a unit's json (game.json, session.json, analysis.json, ...), plus small colour helpers.

Which json names exist comes from the plugins' kinds (`plugin.json_names()`); a sub-report folder (a player page
below a game) finds the json of its unit up to `Kind.levels` folders up. Keys named `_comment` are documentation.
"""
from __future__ import annotations

import json
from pathlib import Path


def find_up(folder: Path | str, name: str, levels: int = 1) -> Path | None:
    """`name` in `folder` or up to `levels` parents."""
    d = Path(folder)
    for _ in range(levels + 1):
        if (d / name).exists():
            return d / name
        d = d.parent
    return None


def unit_json(folder: Path | str) -> Path | None:
    """The unit json for a folder: a json file path as is, else the first plugin json name found."""
    from . import plugin
    p = Path(folder)
    if p.is_file():
        return p
    if not p.is_dir():
        return None
    for name, levels in plugin.json_names():
        found = find_up(p, name, levels)
        if found:
            return found
    return None


def load(path: Path | str | None) -> dict:
    """The unit json from a file path or a folder (see unit_json); {} when not found."""
    if path is None:
        return {}
    p = unit_json(path)
    return json.loads(p.read_text(encoding="utf8")) if p else {}


def is_hex(h) -> bool:
    return isinstance(h, str) and len(h) == 7 and h.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in h[1:])


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def hex_to_bgr(h: str) -> tuple[int, int, int]:
    r, g, b = hex_to_rgb(h)
    return b, g, r


def mix(h: str, other: str = "#ffffff", t: float = 0.5) -> str:
    """Blend colour `h` towards `other` by fraction t (0 = h, 1 = other)."""
    a, b = hex_to_rgb(h), hex_to_rgb(other)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))
