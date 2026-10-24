"""Drawing for the film stage: telestration on a frozen frame (ASS vector drawings: the frame dimmed around a
soft spotlight on the marked players, a floor ring at their feet, arrows drawn on, a label in a dark pill), plus the
"paused" / "slow motion" badge.

The look follows broadcast film rooms: the freeze first punches in on the marked players (freeze_zoom; the film
stage zooms the frame), then the marks build one beat at a time (spotlight, rings, arrows, label), and all of it
fades out before the play runs on. Our players are ringed in blue, theirs in red, a plain spot in white; the
telestration never uses the venue's yellow.

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

MARK_HEX = "#ffd400"  # highlight yellow of court diagrams and posters
US_HEX, THEM_HEX, POINT_HEX = "#3d8bff", "#ff4d4f", "#ffffff"  # ring colours: our player, theirs, a plain spot
INK_HEX = "#111111"  # label pills and badges
ZOOM_MAX = 1.4       # punch-in on a freeze: at most this (720p source footage goes soft beyond it)
ZOOM_S = 0.5         # the zoom in (and out, OUT_S) takes this long; the marks start after it
OUT_S = 0.35
STEP_S = 0.45        # one mark after another
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
    """ASS drawing of a filled arrow from p to q; the shaft tapers from a point at p to `shaft` wide at the head."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    head_l = min(head_l, L * 0.6)
    ex, ey = q[0] - ux * head_l, q[1] - uy * head_l
    tail = shaft * 0.35
    pts = [(p[0] + nx * tail / 2, p[1] + ny * tail / 2), (ex + nx * shaft / 2, ey + ny * shaft / 2),
           (ex + nx * head_w / 2, ey + ny * head_w / 2), q, (ex - nx * head_w / 2, ey - ny * head_w / 2),
           (ex - nx * shaft / 2, ey - ny * shaft / 2), (p[0] - nx * tail / 2, p[1] - ny * tail / 2)]
    return f"m {_n(pts[0][0])} {_n(pts[0][1])} l " + " ".join(f"{_n(x)} {_n(y)}" for x, y in pts[1:])


def rounded(x: float, y: float, w: float, h: float, r: float) -> str:
    """ASS drawing of a rounded rectangle with its top-left corner at (x, y)."""
    r = min(r, w / 2, h / 2)
    k = r * 0.4477  # 1 - 0.5523: the bezier corner
    return (f"m {_n(x + r)} {_n(y)} l {_n(x + w - r)} {_n(y)} b {_n(x + w - k)} {_n(y)} {_n(x + w)} {_n(y + k)} "
            f"{_n(x + w)} {_n(y + r)} l {_n(x + w)} {_n(y + h - r)} b {_n(x + w)} {_n(y + h - k)} {_n(x + w - k)} "
            f"{_n(y + h)} {_n(x + w - r)} {_n(y + h)} l {_n(x + r)} {_n(y + h)} b {_n(x + k)} {_n(y + h)} {_n(x)} "
            f"{_n(y + h - k)} {_n(x)} {_n(y + h - r)} l {_n(x)} {_n(y + r)} b {_n(x)} {_n(y + k)} {_n(x + k)} {_n(y)} "
            f"{_n(x + r)} {_n(y)}")


def bgr(hex_: str) -> str:
    """'#ffd400' -> '&H00D4FF&' (ASS override colour)."""
    h = hex_.lstrip("#").upper()
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&"


def mark_hex(mark) -> str:
    """Ring colour of a mark: a plugin's player on our side blue, on the other side red, anything else white."""
    if mark and len(mark) > 1 and mark[0] not in ("point", "arrow") and mark[1] in ("us", "them"):
        return US_HEX if mark[1] == "us" else THEM_HEX
    return POINT_HEX


def text_w(text: str, fs: float) -> float:
    """Rough width of one line of text at font size fs (CJK and other wide glyphs one em, Latin about half)."""
    return sum(fs * (1.0 if ord(c) > 0x2E7F else 0.3 if c == " " else 0.56) for c in text)


def _found(marks, t: float, tracks) -> dict:
    """{mark: box or None} of every mark and arrow end."""
    boxes = {}
    for mk in marks:
        for m in (mk[1:] if mk[0] == "arrow" else (mk,)):
            if m not in boxes:
                boxes[m] = mark_box(m, t, tracks)
    return boxes


def freeze_zoom(marks, t: float, tracks, w: int, h: int, fit) -> tuple[float, float, float] | None:
    """The punch-in for a freeze: (zoom, x, y) with (x, y) the top-left corner (output pixels) of the
    w/zoom x h/zoom window that keeps every marked player in frame with room for the label above; None when the
    players are too far apart for at least 1.1x."""
    boxes = [b for b in _found(marks, t, tracks).values() if b]
    if not boxes:
        return None
    ox, oy, vw, vh = fit
    x1, x2 = ox + min(b[0] for b in boxes) * vw, ox + max(b[2] for b in boxes) * vw
    y1, y2 = oy + min(b[1] for b in boxes) * vh, oy + max(b[3] for b in boxes) * vh
    z = min(ZOOM_MAX, w / (x2 - x1 + w * 0.3), h / (y2 - y1 + h * 0.42))
    if z < 1.1:
        return None
    cw, ch = w / z, h / z
    x = min(max((x1 + x2) / 2 - cw / 2, 0.0), w - cw)
    y = min(max((y1 + y2) / 2 - h * 0.05 - ch / 2, 0.0), h - ch)
    return round(z, 3), round(x, 1), round(y, 1)


def _merge(rects: list[list[float]]) -> list[list[float]]:
    """Spotlight ellipses (as bounding rects) merged while they overlap: two players side by side get one soft
    spot, not two overlapping ones (whose overlap would stay dimmed)."""
    rects = [r[:] for r in rects]
    i = 0
    while i < len(rects):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                rects[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                del rects[j]
                i = -1  # the grown rect may now overlap an earlier one
                break
        i += 1
    return rects


def freeze_events(marks, label: str, t: float, tracks, w: int, h: int, fit, start: float,
                  end: float, *, zoom: tuple[float, float, float] | None = None,
                  animate: bool = False) -> list[tuple]:
    """ASS events over a frame frozen at video time t: the frame dimmed around a soft spotlight on the marked
    players, a floor ring at their feet, arrows, the label in a dark pill. fit = (ox, oy, vw, vh): where the
    source frame sits in the output frame; tracks resolves plugin marks (see mark_box); zoom: the punch-in the
    frame got (freeze_zoom), so the marks follow it. animate: build the marks one by one after the zoom settles
    and fade them out before the zoom goes back (a film); else all of it shows from start to end (a still).
    Returns (start, end, style, text) tuples."""
    ox, oy, vw, vh = fit
    z, zx, zy = zoom or (1.0, 0.0, 0.0)
    u = min(w, h)  # sizes follow the short side (uw: the width a landscape frame of it has): same in a portrait film
    uw = u * 16 / 9

    def px(fx, fy):
        return (ox + fx * vw - zx) * z, (oy + fy * vh - zy) * z

    boxes = _found(marks, t, tracks)
    found = [(m, b) for m, b in boxes.items() if b]
    explicit = [m for m in marks if m[0] != "arrow"]
    ring_marks = explicit or [m for m, _ in found]
    for mk in [] if explicit else marks:  # arrows only: a short one ("stopped short of the cone") rings its start
        if mk[0] == "arrow" and boxes.get(mk[1]) and boxes.get(mk[2]) and mk[2] in ring_marks and mk[1] != mk[2]:
            (a1, b1, a2, b2), (c1, d1, c2, d2) = boxes[mk[1]], boxes[mk[2]]
            if math.hypot((a1 + a2 - c1 - c2) / 2, (b1 + b2 - d1 - d2) / 2) < SHORT_ARROW:
                ring_marks = [m for m in ring_marks if m != mk[2]]
    if animate:
        t0 = start + (ZOOM_S if zoom else 0.15) + 0.1  # the first mark, once the zoom settles
        stop = max(t0 + 0.6, end - (OUT_S + 0.1 if zoom else 0.0))
    else:
        t0, stop = start, end
    beat = [t0]  # when the next mark appears

    def at(step: float = STEP_S) -> float:
        s = beat[0]
        beat[0] += step if animate else 0.0
        return s

    def fad(fade_in: int = 180) -> str:
        return f"\\fad({fade_in},150)" if animate else ""

    ev = []
    feet, spots = {}, []
    for m, (x1, y1, x2, y2) in found:
        (a, b), (c, d) = px(x1, y1), px(x2, y2)
        feet[m] = ((a + c) / 2, d, max((c - a) * 0.75, uw * 0.02 * z), b)
        if m in ring_marks:
            ex, ey = (c - a) * 0.9 + uw * 0.02 * z, (d - b) * 0.7 + u * 0.03 * z
            spots.append([(a + c) / 2 - ex, (b + d) / 2 - ey, (a + c) / 2 + ex, (b + d) / 2 + ey])
    if spots:  # dim the rest with a soft edge: the marked players are lifted, not washed out by a pale shape
        holes = " ".join(ellipse((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, (r[2] - r[0]) / 2, (r[3] - r[1]) / 2,
                                 reverse=True) for r in _merge(spots))
        ev.append((at(0.15), stop, "Draw", f"{{\\an7\\pos(0,0)\\p1{fad(250)}\\bord0\\shad0"
                   f"\\blur{max(4, round(u * 0.03))}\\1c&H000000&\\1a&H7A&}}"
                   f"m {-w} {-h} l {2 * w} {-h} l {2 * w} {2 * h} l {-w} {2 * h} " + holes))
    line = max(2.0, u * 0.0055 * min(z, 1.25))
    pop = "\\fscx70\\fscy70\\t(0,220,0.6,\\fscx100\\fscy100)" if animate else ""
    for m in ring_marks:
        if m not in feet:
            continue
        cx, cy, rx, _ = feet[m]
        ry = rx * 0.33
        s = at()
        pos = f"\\an5\\pos({_n(cx)},{_n(cy)})"
        # a floor ring: a dark disc under the player, then the coloured rim (outer ellipse minus inner) with a thin
        # dark edge, so it reads on a light floor and on the venue's logo alike
        ev.append((s, stop, "Draw", f"{{{pos}\\p1{fad()}{pop}\\bord0\\shad0\\blur1\\1c&H000000&\\1a&HB0&}}"
                   + ellipse(rx, ry, rx, ry)))
        ev.append((s, stop, "Draw", f"{{{pos}\\p1{fad()}{pop}\\shad0\\blur0.6\\bord{max(1, round(u * 0.0016))}"
                   f"\\3c&H000000&\\3a&H70&\\1c{bgr(mark_hex(m))}}}"
                   + ellipse(rx, ry, rx, ry) + " " + ellipse(rx, ry, rx - line, ry - line * 0.55, reverse=True)))
    for mk in marks:
        if mk[0] != "arrow" or mk[1] not in feet or mk[2] not in feet:
            continue
        (x0, y0, r0, _), (x1, y1, r1, _) = feet[mk[1]], feet[mk[2]]
        L = math.hypot(x1 - x0, y1 - y0) or 1.0
        p = (x0 + (x1 - x0) * min(0.45, r0 * 0.8 / L), y0 + (y1 - y0) * min(0.45, r0 * 0.8 / L))
        q = (x1 - (x1 - x0) * min(0.45, r1 * 0.8 / L), y1 - (y1 - y0) * min(0.45, r1 * 0.8 / L))
        s = at()
        draw_on = ""
        if animate:  # drawn on from tail to head: a clip box growing from the tail's corner
            pad = u * 0.04
            bx1, by1 = min(p[0], q[0]) - pad, min(p[1], q[1]) - pad
            bx2, by2 = max(p[0], q[0]) + pad, max(p[1], q[1]) + pad
            sx1, sx2 = (bx1, bx1 + pad * 2) if q[0] >= p[0] else (bx2 - pad * 2, bx2)
            sy1, sy2 = (by1, by1 + pad * 2) if q[1] >= p[1] else (by2 - pad * 2, by2)
            draw_on = (f"\\clip({round(sx1)},{round(sy1)},{round(sx2)},{round(sy2)})"
                       f"\\t(0,350,\\clip({round(bx1)},{round(by1)},{round(bx2)},{round(by2)}))")
        ev.append((s, stop, "Draw", f"{{\\an7\\pos(0,0)\\p1{fad(80)}{draw_on}\\1c&HFFFFFF&"
                   f"\\bord{max(1, round(u * 0.0018))}\\3c&H000000&\\3a&H60&\\shad{max(1, round(u * 0.002))}"
                   f"\\4c&H000000&\\4a&H90&\\blur0.6}}" + arrow(p, q, max(3.0, u * 0.008), u * 0.036, u * 0.032)))
    if label:
        first = next((m for m in ring_marks if m in feet), None)
        tops = [feet[m][3] for m in ring_marks if m in feet]
        # over the first ring, above every ringed player's head so the pill never covers one
        x, top = (feet[first][0], min(tops)) if first else (w / 2, h * 0.3)
        fs = u * 0.04
        pw, ph = text_w(label, fs) + fs * 1.4, fs * 1.6
        x = min(max(x, pw / 2 + u * 0.03), w - pw / 2 - u * 0.03)
        y = max(top - u * 0.05 - ph / 2, h * 0.1 + ph / 2)  # the pill's centre
        s = at()

        def place(x_, y_):
            if animate:  # rises a little as it fades in
                return f"\\move({_n(x_)},{_n(y_ + u * 0.012)},{_n(x_)},{_n(y_)},0,200)"
            return f"\\pos({_n(x_)},{_n(y_)})"

        if first and top - (y + ph / 2) > u * 0.025:  # a thin leader from the pill down to the player
            y1, y2 = y + ph / 2, top - u * 0.008
            ev.append((s, stop, "Draw", f"{{\\an7\\pos(0,0)\\p1{fad()}\\bord0\\shad0\\blur0.5\\1c&HFFFFFF&\\1a&H40&}}"
                       f"m {_n(x - 1)} {_n(y1)} l {_n(x + 1)} {_n(y1)} l {_n(x + 1)} {_n(y2)} l {_n(x - 1)} {_n(y2)}"))
        colour = bgr(mark_hex(first))
        ev.append((s, stop, "Draw", f"{{\\an5{place(x, y)}\\p1{fad()}\\bord0\\shad0\\blur0.6\\1c{bgr(INK_HEX)}"
                   f"\\1a&H22&}}" + rounded(0, 0, pw, ph, ph * 0.28)))
        ev.append((s, stop, "Draw", f"{{\\an5{place(x - pw / 2 + fs * 0.35, y)}\\p1{fad()}\\bord0\\shad0\\1c{colour}}}"
                   + rounded(0, 0, fs * 0.16, ph * 0.56, fs * 0.08)))  # a small strip in the ring's colour
        ev.append((s, stop, "Mark", f"{{\\an5{place(x + fs * 0.1, y)}{fad()}}}" + label))
    return ev


def badge(text: str, start: float, end: float, w: int, h: int, icon: str = "pause") -> list[tuple]:
    """The playback state in the top-right corner: a dark pill with a pause (two bars) or play (triangle) icon and
    `text` ("定格", "慢放"), so a viewer always knows the picture is frozen or slowed."""
    u = min(w, h)
    fs, m = u * 0.032, u * 0.04
    ih = fs * 0.72
    pw, ph = text_w(text, fs) + fs * 2.4, fs * 1.6
    x, y = w - m - pw, m
    ix, iy = x + fs * 0.7, y + (ph - ih) / 2
    if icon == "pause":
        bw = ih * 0.3
        shape = " ".join(f"m {_n(a)} {_n(iy)} l {_n(a + bw)} {_n(iy)} l {_n(a + bw)} {_n(iy + ih)} l {_n(a)} {_n(iy + ih)}"
                         for a in (ix, ix + bw * 2.1))
    else:
        shape = f"m {_n(ix)} {_n(iy)} l {_n(ix + ih * 0.85)} {_n(iy + ih / 2)} l {_n(ix)} {_n(iy + ih)}"
    fade = "\\fad(200,200)"
    return [(start, end, "Draw", f"{{\\an7\\pos(0,0)\\p1{fade}\\bord0\\shad0\\blur0.6\\1c{bgr(INK_HEX)}\\1a&H40&}}"
             + rounded(x, y, pw, ph, ph / 2)),
            (start, end, "Draw", f"{{\\an7\\pos(0,0)\\p1{fade}\\bord0\\shad0\\1c&HFFFFFF&}}" + shape),
            (start, end, "Tag", f"{{\\an4\\pos({_n(ix + fs * 1.1)},{_n(y + ph / 2)}){fade}}}" + text)]
