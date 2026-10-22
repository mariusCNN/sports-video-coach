"""Drawing for the film stage: telestration on a frozen frame (ASS vector drawings: the frame dimmed with the
marked spots cut out, a ring at their feet, arrows, a label).

Marks in a freeze line (`> 03:10 0.42,0.61 0.42,0.61->0.7,0.5 "alone"`):
    0.42,0.61          a point on the frame (fractions of width and height): where a player's feet are
    A->B               an arrow from mark A to mark B
    "text"             a label above the first mark
A sport plugin may add marks resolved from its tracking (FilmHooks.parse_ref / tracks, e.g. basketball's 我#7); a
mark of any other kind than "point" is looked up with `tracks.locate(mark, t)`.
"""
from __future__ import annotations

import math
import re
from typing import Callable

MARK_HEX = "#ffd400"  # telestration yellow
SHORT_ARROW = 0.12   # arrow ends closer than this (frame fractions) get one ring, at the start
POINT_RE = re.compile(r"^(\d*\.?\d+),(\d*\.?\d+)$")
ARROW_RE = re.compile(r"^(.+?)(?:->|→)(.+)$")
LABEL_RE = re.compile(r'"([^"]*)"|“([^”]*)”')


def parse_mark(tok: str, ref: Callable[[str], tuple | None] | None = None):
    """'0.4,0.6' -> ('point', 0.4, 0.6); 'A->B' -> ('arrow', a, b); a plugin mark via ref(tok) (basketball:
    '我#7' -> ('player', 'us', '7')); else None."""
    m = ARROW_RE.match(tok)
    if m and not POINT_RE.match(tok):
        a, b = parse_mark(m[1], ref), parse_mark(m[2], ref)
        return ("arrow", a, b) if a and b and a[0] != "arrow" and b[0] != "arrow" else None
    m = POINT_RE.match(tok)
    if m and 0 <= float(m[1]) <= 1 and 0 <= float(m[2]) <= 1:
        return ("point", float(m[1]), float(m[2]))
    return ref(tok) if ref else None


def parse_freeze_line(line: str, ref: Callable[[str], tuple | None] | None = None):
    """'> 03:10 0.4,0.6 "alone"' -> (time text, [marks], label, [bad tokens]); ref reads plugin marks."""
    body = line[1:].strip()
    label = ""
    m = LABEL_RE.search(body)
    if m:
        label = (m[1] if m[1] is not None else m[2]).strip()
        body = (body[:m.start()] + body[m.end():]).strip()
    toks = body.split()
    t = toks[0] if toks else ""
    marks, bad = [], []
    for tok in toks[1:]:
        mk = parse_mark(tok, ref)
        (marks if mk else bad).append(mk or tok)
    return t, marks, label, bad


def mark_text(mark) -> str:
    """A parsed mark back as script text: ('point', 0.4, 0.6) -> '0.4,0.6'; an arrow 'A->B'; a plugin mark 'us#7'."""
    if mark[0] == "point":
        return f"{mark[1]:g},{mark[2]:g}"
    if mark[0] == "arrow":
        return f"{mark_text(mark[1])}->{mark_text(mark[2])}"
    return "#".join(map(str, mark[1:]))


def mark_box(mark, t: float, tracks=None):
    """A point mark, or a plugin mark found by `tracks.locate(mark, t)` -> its box (x1, y1, x2, y2) as frame
    fractions, or None if it cannot be found."""
    if mark[0] == "point":
        x, y = mark[1], mark[2]
        return x - 0.02, y - 0.16, x + 0.02, y  # a point is where the feet are
    if tracks is not None:
        return tracks.locate(mark, t)
    return None


def _n(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def ellipse(cx: float, cy: float, rx: float, ry: float, reverse: bool = False) -> str:
    """ASS drawing of an ellipse (four bezier arcs); reverse=True winds the other way, to cut a hole."""
    k = 0.5523
    pts = [(cx + rx, cy), (cx, cy + ry), (cx - rx, cy), (cx, cy - ry)]
    ctrl = [((cx + rx, cy + k * ry), (cx + k * rx, cy + ry)), ((cx - k * rx, cy + ry), (cx - rx, cy + k * ry)),
            ((cx - rx, cy - k * ry), (cx - k * rx, cy - ry)), ((cx + k * rx, cy - ry), (cx + rx, cy - k * ry))]
    if reverse:
        pts = [pts[0], pts[3], pts[2], pts[1]]
        ctrl = [(c2, c1) for c1, c2 in reversed(ctrl)]
    out = f"m {_n(pts[0][0])} {_n(pts[0][1])}"
    for i in range(4):
        (a, b), (c, d) = ctrl[i]
        ex, ey = pts[(i + 1) % 4]
        out += f" b {_n(a)} {_n(b)} {_n(c)} {_n(d)} {_n(ex)} {_n(ey)}"
    return out


def arrow(p, q, shaft: float, head_l: float, head_w: float) -> str:
    """ASS drawing of a filled arrow from p to q."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    head_l = min(head_l, L * 0.6)
    ex, ey = q[0] - ux * head_l, q[1] - uy * head_l
    pts = [(p[0] + nx * shaft / 2, p[1] + ny * shaft / 2), (ex + nx * shaft / 2, ey + ny * shaft / 2),
           (ex + nx * head_w / 2, ey + ny * head_w / 2), q, (ex - nx * head_w / 2, ey - ny * head_w / 2),
           (ex - nx * shaft / 2, ey - ny * shaft / 2), (p[0] - nx * shaft / 2, p[1] - ny * shaft / 2)]
    return f"m {_n(pts[0][0])} {_n(pts[0][1])} l " + " ".join(f"{_n(x)} {_n(y)}" for x, y in pts[1:])


def bgr(hex_: str) -> str:
    """'#ffd400' -> '&H00D4FF&' (ASS override colour)."""
    h = hex_.lstrip("#").upper()
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&"


def freeze_events(marks, label: str, t: float, tracks, w: int, h: int, fit, start: float,
                  end: float) -> list[tuple]:
    """ASS events over a frame frozen at video time t: the frame dimmed except the marked players, a ring at their
    feet, arrows, the label. fit = (ox, oy, vw, vh): where the source frame sits in the output frame; tracks
    resolves plugin marks (see mark_box). Returns (start, end, style, text) tuples."""
    ox, oy, vw, vh = fit

    def px(fx, fy):
        return ox + fx * vw, oy + fy * vh

    boxes = {}
    for mk in marks:
        for m in (mk[1:] if mk[0] == "arrow" else (mk,)):
            if m not in boxes:
                boxes[m] = mark_box(m, t, tracks)
    found = [(m, b) for m, b in boxes.items() if b]
    ev = []
    head = "{\\an7\\pos(0,0)\\fad(200,0)\\p1\\bord0\\shad0"
    explicit = [m for m in marks if m[0] != "arrow"]
    ring_marks = explicit or [m for m, _ in found]
    for mk in [] if explicit else marks:  # arrows only: a short one ("stopped short of the cone") rings its start
        if mk[0] == "arrow" and boxes.get(mk[1]) and boxes.get(mk[2]) and mk[2] in ring_marks and mk[1] != mk[2]:
            (a1, b1, a2, b2), (c1, d1, c2, d2) = boxes[mk[1]], boxes[mk[2]]
            if math.hypot((a1 + a2 - c1 - c2) / 2, (b1 + b2 - d1 - d2) / 2) < SHORT_ARROW:
                ring_marks = [m for m in ring_marks if m != mk[2]]
    holes = []
    for m, (x1, y1, x2, y2) in found:
        if m in ring_marks:
            (a, b), (c, d) = px(x1, y1), px(x2, y2)
            bw, bh = c - a, d - b
            holes.append(ellipse((a + c) / 2, (b + d) / 2, bw * 0.85 + w * 0.012, bh * 0.62 + h * 0.012, reverse=True))
    if holes:  # dim everything but the marked players
        ev.append((start, end, "Draw", head + f"\\1c&H000000&\\1a&H78&}}m 0 0 l {w} 0 l {w} {h} l 0 {h} " + " ".join(holes)))
    feet = {}
    for m, (x1, y1, x2, y2) in found:
        (a, b), (c, d) = px(x1, y1), px(x2, y2)
        rx = max((c - a) * 0.8, w * 0.018)
        feet[m] = ((a + c) / 2, d, rx, b)
        if m in ring_marks:
            ring = ellipse((a + c) / 2, d, rx, rx * 0.32)
            ev.append((start, end, "Draw", head + f"\\1a&HFF&\\bord{max(2, round(h * 0.006))}\\3c{bgr(MARK_HEX)}}}" + ring))
    for mk in marks:
        if mk[0] != "arrow" or mk[1] not in feet or mk[2] not in feet:
            continue
        (x0, y0, r0, _), (x1, y1, r1, _) = feet[mk[1]], feet[mk[2]]
        L = math.hypot(x1 - x0, y1 - y0) or 1.0
        p = (x0 + (x1 - x0) * min(0.45, r0 * 0.7 / L), y0 + (y1 - y0) * min(0.45, r0 * 0.7 / L))
        q = (x1 - (x1 - x0) * min(0.45, r1 * 0.7 / L), y1 - (y1 - y0) * min(0.45, r1 * 0.7 / L))
        ev.append((start, end, "Draw", head + f"\\1c{bgr(MARK_HEX)}\\bord{max(1, round(h * 0.003))}\\3c&H000000&}}"
                   + arrow(p, q, h * 0.012, h * 0.04, h * 0.035)))
    if label:
        first = next((feet[m] for m in ring_marks if m in feet), None)
        tops = [feet[m][3] for m in ring_marks if m in feet]
        # over the first ring, above every ringed player's head so the box never covers one
        x, top = (first[0], min(tops)) if first else (w / 2, h * 0.3)
        y = max(top - h * 0.04, h * 0.16)
        ev.append((start, end, "Mark", f"{{\\an2\\pos({_n(x)},{_n(y)})\\fad(200,0)}}" + label))
    return ev
