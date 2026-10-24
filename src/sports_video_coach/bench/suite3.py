"""The benchmark suite `svc-bench-3` ("eyes"): drawn videos whose events are small, short or hidden, built for the
frames-only track after strong models scored 1.0 on `svc-bench-2` by eye.

Every task stays answerable from the stills a frames-track contender gets (one every 0.08 s), but only by looking
closely, often at the full-size stills rather than the contact sheets:
- small, distant things: a ball 5 px in radius on a 640x360 frame, a ball 3 px in radius at a 16 px wide far rim,
  an oar blade a few pixels tall;
- short events: a double touch whose hop lasts 0.24 s and rises about 10 px, a one-touch pass with no hold;
- occlusion at the moment of the event: a banner passes in front of the rim, a defender stands in front of the
  passer, so the event must be inferred from where the ball goes next;
- near-identical distractors: a second juggler, a second pair passing an identical ball, a second boat rowing at a
  close rate; and look-alike non-events (a floor bounce is not a touch, a pass fake is not a pass, a ball that falls
  just in front of the rim is not a make).

Drawn like suite 2 (numpy / OpenCV frames piped to ffmpeg, 640x360 at 25 fps, hand-held camera shake, noise, flicker,
a short motion blur, CRF 30). Every truth is computed from the same numbers that drive the drawing, so the two cannot
drift apart, and the noise uses a fixed seed. The truth lives here and is never written into a prepared folder.

Fresh seeds: the numbers that make the events (the juggling sequence, the shots, the passes and the defender's walk,
the stroke lengths) form a `Spec`. `DEFAULT` is the published suite (the module-level names below are its values);
`seeded(n)` draws a new `Spec` from the integer seed n, with the same scenes, rules and kinds of traps but different
counts, outcomes, times and rates, and builds its tasks and truth from it. A seeded truth is never written to the
prepared folder: `bench score` and `bench validate` rebuild it from the seed a result file records (the scored file
shows it). The generators keep each seed as readable as the published suite (checked by a pixel read-back of the
stills, see docs/benchmark.md): high juggling arcs take longer, a pass across the middle player is a lob, the defender
hides only held balls and stays clear of every other release, catch and flight.
"""
from __future__ import annotations

import functools
import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .suite import FPS, Task
from .suite2 import Path2, bgr, canvas, circle, frames, lerp_keys, line, rect, render, shaky

SUITE = "svc-bench-3"
WW, WH = 700, 420          # world size; the camera shows x 30..670, y 30..390 give or take the shake
MAX_SEED = 2 ** 63 - 1


def fsec(f: int) -> float:
    return round(f / FPS, 2)


# --- count: juggling touches, with double touches and floor bounces -------------------------------------------------
# Side view. The red player (left) juggles a small yellow ball with one foot; the orange-red player (right) juggles an
# identical ball. A touch is a contact of the left player's foot with his ball: quick double touches (a 0.24 s hop of
# about 10 px) count twice; a bounce on the floor is not a touch.
JUG_S = 29.76
JUG_FLOOR = 350
JUG_R = 5
JUG_X, DECOY_X = 230, 500        # the two players' body centres (world x)
LIFT = 28                        # px the foot rises to meet the ball
FOOT_TOP = JUG_FLOOR - 8         # the top of a foot at rest
TOUCH_DY = FOOT_TOP - LIFT - JUG_R   # ball centre y at a foot touch
FLOOR_DY = JUG_FLOOR - JUG_R         # ball centre y at a floor bounce
# (contact, frames to the next contact, arc height in px above the higher end); F = foot touch, N = floor bounce
JUGGLE = [("F", 16, 80), ("F", 15, 72), ("F", 6, 10), ("F", 17, 88), ("F", 14, 64), ("F", 18, 70), ("N", 13, 36),
          ("F", 16, 80), ("F", 6, 9), ("F", 15, 76), ("F", 16, 82), ("F", 13, 60), ("F", 6, 11), ("F", 18, 90),
          ("F", 15, 70), ("F", 17, 72), ("N", 14, 40), ("F", 15, 78), ("F", 16, 84), ("F", 6, 10), ("F", 6, 10),
          ("F", 17, 86), ("F", 14, 66), ("F", 19, 74), ("N", 12, 30), ("N", 11, 20), ("F", 16, 82), ("F", 15, 70),
          ("F", 6, 9), ("F", 16, 80), ("F", 14, 68), ("F", 17, 76), ("F", 6, 10), ("F", 15, 72), ("F", 18, 88),
          ("N", 13, 34), ("F", 16, 80), ("F", 15, 74), ("F", 14, 66), ("F", 6, 10), ("F", 17, 84), ("F", 16, 78),
          ("F", 15, 70), ("F", 16, 80), ("F", 15, 76)]
DECOY_JUGGLE = [("F", 15, 70), ("F", 17, 78), ("F", 16, 74), ("F", 6, 10), ("F", 15, 70), ("F", 18, 84),
                ("N", 13, 34), ("F", 16, 76)]
JUG_FIRST, DECOY_FIRST = 20, 27  # frame of the first contact (the ball is dropped from the hand before it)


def contacts(seq: list[tuple], first: int, n_frames: int) -> list[tuple[int, str, int]]:
    """(frame, kind, arc height to the next contact) for every contact up to one after the video ends; `seq` is
    repeated if it is too short."""
    out, f, k = [], first, 0
    while True:
        kind, gap, h = seq[k % len(seq)]
        out.append((f, kind, h))
        if f > n_frames:
            return out
        f, k = f + gap, k + 1


def juggle_path(cs: list[tuple[int, str, int]], x0: float) -> Path2:
    touch_x, bounce_x = x0 + 26, x0 + 58

    def at(kind):
        return (touch_x, TOUCH_DY) if kind == "F" else (bounce_x, FLOOR_DY)
    p = Path2((touch_x, 280))
    p.hold(0.4)
    p.drop(cs[0][0] / FPS - 0.4, at(cs[0][1]))
    for (f0, _, h), (f1, k1, _) in zip(cs, cs[1:]):
        p.arc((f1 - f0) / FPS, at(k1), h)
    return p


JUG_N = frames(JUG_S)


def foot_lift(cs: list[tuple[int, str, int]], t: float) -> float:
    """0 (at rest) .. 1 (at a touch): the foot rises over 0.16 s before a touch and drops over 0.16 s after it."""
    return max([max(0.0, 1 - abs(t - f / FPS) / 0.16) for f, k, _ in cs if k == "F"] + [0.0])


def draw_juggle(out: Path, v: Instance | None = None) -> Path:
    v = v or DEFAULT_INSTANCE
    world = canvas(WW, WH, "2a3550")
    for x in range(40, WW, 110):
        world[60:JUG_FLOOR, x:x + 4] = bgr("4a5775")                                  # wall panels
    world[JUG_FLOOR:JUG_FLOOR + 3] = bgr("e0e0e0")
    world[JUG_FLOOR + 3:] = bgr("6b4a2f")
    ball = bgr("f2c522")
    players = [(JUG_X, bgr("d0312d"), juggle_path(v.jug_contacts, JUG_X), v.jug_contacts),
               (DECOY_X, bgr("e0603a"), juggle_path(v.decoy_contacts, DECOY_X), v.decoy_contacts)]

    def draw(img, t, ox, oy):
        for x0, shirt, path, cs in players:
            lift = foot_lift(cs, t)
            fx, fy = x0 + 16 + 10 * lift, FOOT_TOP - LIFT * lift
            rect(img, x0 - 12 - ox, 250 - oy, x0 + 12 - ox, 302 - oy, shirt)                  # torso
            circle(img, x0 - ox, 236 - oy, 11, bgr("c89a74"))                                  # head
            rect(img, x0 - 10 - ox, 300 - oy, x0 - ox, JUG_FLOOR - oy, bgr("23233a"))         # standing leg
            line(img, (x0 + 4 - ox, 300 - oy), (fx - ox, fy + 4 - oy), bgr("23233a"), 7)       # kicking leg
            rect(img, fx - 11 - ox, fy - oy, fx + 11 - ox, fy + 8 - oy, bgr("111111"))         # foot
            (bx, by), _, _ = path.at(t)
            circle(img, bx - ox, by - oy, JUG_R, ball)

    return render(out, JUG_S, world, shaky(WW, WH, (30, 30), 10, 8, 0.9), draw, seed=31)


# --- outcomes: shots at a far hoop, with a banner passing in front of the rim ----------------------------------------
# A wide shot: the rim is 16 px wide and the ball 3 px in radius. Made = the ball goes down through the ring and out
# of the net.
# On three shots a fan's banner covers the rim when the ball gets there; the ball is seen again below or beside it.
FAR_FLOOR = 330
RX, RY, RHALF = 490, 256, 8          # rim centre and half width
FAR_R = 3
NET_Y = RY + 14
FAR_HANDS = (178, 270)
FAR_BALL_FLOOR = FAR_FLOOR - FAR_R
SHOTS3 = ["swish", "front-out", "back-in", "fake+in-out", "short", "roll-in", "swish*", "roll-out", "back-out*",
          "front-up-in*", "in-out", "swish"]            # * = the banner covers the rim when the ball arrives
MADE3 = {"swish", "back-in", "roll-in", "front-up-in"}
BANNER_W, BANNER_V = 90, 150      # banner width and speed (px/s); it covers y RY-44 .. RY+10


def far_outcome(kind: str) -> str:
    return "made" if kind.split("+")[-1].rstrip("*") in MADE3 else "missed"


def far_shots(shots: list[str] = SHOTS3) -> tuple[Path2, list[float]]:
    """The ball path, and the times the ball reaches the rim on the shots the banner covers."""
    p, covered = Path2(FAR_HANDS), []
    hx, hy = FAR_HANDS

    def through():
        p.drop(0.24, (RX, NET_Y + 6))
        p.drop(0.28, (RX, FAR_BALL_FLOOR))

    def orbit(dur, phi1):
        p.seg(dur, lambda u: (RX + 6 * math.cos(phi1 * u), RY - 4 - 1.5 * abs(math.sin(phi1 * u))))

    for kind in shots:
        p.hold(0.6)
        what = kind.split("+")[-1]
        if kind.startswith("fake+"):
            p.line(0.28, (hx, hy - 12), hands=True)
            p.line(0.28, (hx, hy), hands=True)
            p.hold(0.4)
        p.line(0.24, (hx + 2, hy - 14), hands=True)
        hidden = what.endswith("*")
        what = what.rstrip("*")
        target = {"swish": (RX, RY - 4), "front-out": (RX - 9, RY - 3), "in-out": (RX + 2, RY - 3),
                  "back-in": (RX + 8, RY - 3), "back-out": (RX + 8, RY - 3), "short": (RX - 15, RY + 5),
                  "roll-in": (RX + 6, RY - 4), "roll-out": (RX + 6, RY - 4), "front-up-in": (RX - 9, RY - 3)}[what]
        p.arc(1.12, target, 110)
        if hidden:
            covered.append(round(p.t, 2))
        if what == "swish":
            through()
        elif what == "front-out":
            p.arc(0.6, (RX - 52, FAR_BALL_FLOOR), 18)
        elif what == "in-out":
            p.line(0.08, (RX + 1, RY + 3))
            p.arc(0.8, (RX - 46, FAR_BALL_FLOOR), 26)
        elif what == "back-in":
            p.arc(0.6, (RX, RY - 4), 14)
            through()
        elif what == "back-out":
            p.arc(0.6, (RX - 9, RY - 3), 14)
            p.arc(0.6, (RX - 54, FAR_BALL_FLOOR), 16)
        elif what == "short":
            p.line(0.24, (RX - 19, FAR_BALL_FLOOR))
        elif what == "roll-in":
            orbit(1.0, 2.5 * math.pi)
            through()
        elif what == "roll-out":
            orbit(1.12, 3 * math.pi)
            p.arc(0.28, (RX - 12, RY - 1), 3)
            p.drop(0.4, (RX - 22, FAR_BALL_FLOOR))
        elif what == "front-up-in":
            p.arc(0.6, (RX, RY - 4), 16)
            through()
        x = p.p[0]
        p.arc(0.48, (x - 16, FAR_BALL_FLOOR), 12)
        p.arc(0.92, FAR_HANDS, 44)
    p.hold(0.6)
    return p, covered


def banner_x(t: float, covered: list[float] | None = None) -> float | None:
    """Centre x of the banner at t (it passes the rim centre 0.16 s after the ball arrives), or None when off.
    `covered`: the arrival times of the covered shots (default: the published suite's)."""
    for ta in DEFAULT_INSTANCE.far_covered if covered is None else covered:
        x = RX + BANNER_V * (t - ta - 0.16)
        if abs(x - RX) < 400:
            return x
    return None


def draw_far(out: Path, v: Instance | None = None) -> Path:
    v = v or DEFAULT_INSTANCE
    world = canvas(WW, WH, "26324a")
    world[FAR_FLOOR:] = bgr("8b5a2b")
    world[FAR_FLOOR:FAR_FLOOR + 2] = bgr("d8d8d8")
    for x in range(60, WW, 140):
        world[120:FAR_FLOOR, x:x + 3] = bgr("33415c")                                  # far wall seams
    world[RY - 34:RY + 6, RX + 11:RX + 13] = bgr("f0f0f0")                             # backboard
    world[RY - 18:RY - 15, RX + 13:RX + 30] = bgr("777777")                            # its arm
    world[RY - 18:FAR_FLOOR, RX + 28:RX + 32] = bgr("777777")                          # pole
    ball, net, rim = bgr("f08a24"), bgr("dddddd"), bgr("d02020")
    shooter, banner = bgr("3355cc"), bgr("d9d2c0")

    def draw(img, t, ox, oy):
        (bx, by), hands, _ = v.far_path.at(t)
        rise = (FAR_HANDS[1] - by) * 0.6 if hands else 0.0
        rect(img, 166 - ox, 276 - rise - oy, 178 - ox, FAR_FLOOR - rise - oy, shooter)      # shooter
        circle(img, 172 - ox, 270 - rise - oy, 5, bgr("c89a74"))
        circle(img, bx - ox, by - oy, FAR_R, ball)
        for a, b in (((RX - 7, RY + 2), (RX - 4, NET_Y)), ((RX + 7, RY + 2), (RX + 4, NET_Y)),
                     ((RX - 7, RY + 2), (RX + 4, NET_Y)), ((RX + 7, RY + 2), (RX - 4, NET_Y))):
            line(img, (a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy), net, 1)
        rect(img, RX - RHALF - ox, RY - oy, RX + RHALF - ox, RY + 2 - oy, rim)
        x = banner_x(t, v.far_covered)
        if x is not None:
            rect(img, x - BANNER_W / 2 - ox, RY - 44 - oy, x + BANNER_W / 2 - ox, RY + 10 - oy, banner)
            rect(img, x - BANNER_W / 2 - ox, RY - 30 - oy, x + BANNER_W / 2 - ox, RY - 24 - oy, bgr("2f6b3a"))
            rect(img, x - 2 - ox, RY + 10 - oy, x + 2 - ox, WH - oy, bgr("5a4a3a"))            # its pole

    return render(out, v.far_s, world, shaky(WW, WH, (30, 30), 9, 7, 1.3), draw, seed=32)


# --- timestamps: pass releases, with fakes, one-touch passes, a defender in front and a decoy pair ----------------
# Three blue players pass an orange ball; a red defender moves in front of them. A second, grey pair further back
# passes an identical ball. A release = the moment the ball leaves a blue player on a pass to another blue player.
PASS_FLOOR, PASS_CHEST = 350, 290
SPOTS = {"A": 130, "B": 350, "C": 570}
PASS_R = 6
# (passer, receiver, style, hold before the release in s, fake first); style: arc, lob, bounce, touch (one-touch:
# the passer redirects the ball the moment it arrives, no hold)
PASSES = [("A", "B", "arc", 1.0, False), ("B", "C", "arc", 0.6, True), ("C", "B", "bounce", 0.8, False),
          ("B", "A", "touch", 0.0, False), ("A", "C", "lob", 1.2, False), ("C", "A", "lob", 0.4, True),
          ("A", "B", "arc", 0.8, False), ("B", "C", "touch", 0.0, False), ("C", "B", "arc", 1.0, True),
          ("B", "A", "bounce", 0.6, False), ("A", "B", "arc", 0.4, True), ("B", "C", "arc", 0.88, False)]
PASS_S = 21.0
FLIGHT = {"arc": 0.68, "touch": 0.68, "lob": 1.2, "bounce": 0.8}     # s from the release to the catch
FAKE_S = 0.72                                                       # a pass fake and the hold after it


def chest(who: str) -> tuple[float, float]:
    return SPOTS[who], PASS_CHEST


def pass_path(passes: list[tuple] = PASSES) -> tuple[Path2, list[float]]:
    p, releases = Path2(chest("A")), []
    for passer, receiver, style, hold, fake in passes:
        if style != "touch":
            p.hold(hold, holder=passer)
        if fake:
            x, y = chest(passer)
            d = 1 if SPOTS[receiver] > x else -1
            p.line(0.2, (x + 16 * d, y - 6), hands=True)
            p.line(0.2, (x, y), hands=True)
            p.hold(0.32, holder=passer)
        releases.append(round(p.t, 2))
        to = chest(receiver)
        if style == "arc":
            p.arc(0.68, to, 46)
        elif style == "touch":
            p.arc(0.68, to, 40)
        elif style == "lob":
            p.arc(1.2, to, 66)
        elif style == "bounce":
            mid = ((p.p[0] + to[0]) / 2, PASS_FLOOR - PASS_R)
            p.line(0.4, mid)
            p.line(0.4, to)
    p.hold(PASS_S - p.t, holder=passes[-1][1])
    return p, releases


DECOY_SPOTS = (250, 480)
DECOY_CHEST = 196


def decoy_pass_path() -> Path2:
    """The grey pair at the back: holds of 0.6 to 1.4 s and 0.68 s arcs, back and forth."""
    holds = [0.92, 1.2, 0.6, 1.4, 0.8, 1.08, 0.72, 1.32]
    p, k = Path2((DECOY_SPOTS[0], DECOY_CHEST)), 0
    while p.t < PASS_S:
        p.hold(holds[k % len(holds)])
        p.arc(0.68, (DECOY_SPOTS[(k + 1) % 2], DECOY_CHEST), 30)
        k += 1
    return p


DECOY_PASS = decoy_pass_path()
# the defender stands in front of the passer at four releases: 3.0 s (B, after a fake), 9.48 s (C, after a fake),
# 15.84 s (B, bounce pass) and 17.76 s (A, after a fake)
DEFENDER_X = [(0.0, 240), (1.6, 345), (2.0, 350), (3.3, 350), (4.4, 240), (6.6, 240), (8.6, 570), (10.0, 570),
              (11.0, 470), (12.4, 430), (15.3, 350), (16.2, 350), (17.0, 130), (18.2, 130), (19.0, 240), (PASS_S, 240)]
PASS_HIDDEN = [3.0, 9.48, 15.84, 17.76]


def draw_passes(out: Path, v: Instance | None = None) -> Path:
    v = v or DEFAULT_INSTANCE
    world = canvas(WW, WH, "2b3346")
    world[220:] = bgr("9a6a3a")
    world[220:222] = bgr("cfcfcf")
    world[PASS_FLOOR:PASS_FLOOR + 2] = bgr("e6e6e6")
    for x in range(70, WW, 120):
        world[90:220, x:x + 3] = bgr("3b4560")
    ball, blue, grey, red, skin = bgr("f08a24"), bgr("3355cc"), bgr("8a8a8a"), bgr("c42b2b"), bgr("c89a74")
    defender = list(v.spec.defender_x)

    def draw(img, t, ox, oy):
        for x in DECOY_SPOTS:                                                               # the pair at the back
            rect(img, x - 9 - ox, 172 - oy, x + 9 - ox, 222 - oy, grey)
            circle(img, x - ox, 164 - oy, 7, skin)
        (dx, dy), _, _ = DECOY_PASS.at(t)
        circle(img, dx - ox, dy - oy, 4, ball)
        for x in SPOTS.values():
            rect(img, x - 13 - ox, 268 - oy, x + 13 - ox, PASS_FLOOR - oy, blue)
            circle(img, x - ox, 256 - oy, 11, skin)
        (bx, by), _, _ = v.pass_path.at(t)
        circle(img, bx - ox, by - oy, PASS_R, ball)
        x = lerp_keys(defender, t)                                                         # in front of everyone
        rect(img, x - 17 - ox, 262 - oy, x + 17 - ox, PASS_FLOOR - oy, red)
        circle(img, x - ox, 249 - oy, 12, skin)

    return render(out, PASS_S, world, shaky(WW, WH, (30, 30), 10, 8, 2.6), draw, seed=33)


# --- rate: stroke rate of a far sculler after a pace change, with a second boat at a close rate ---------------------
# Two identical boats far away, the camera following them. The near (lower) boat's rower raises the rate at 15 s;
# the far boat rows steadily at a rate between his two. A catch = the yellow oar blade dropping into the water at
# its forward end.
ROW_S = 32.0
ROW_SPLIT = 15.0
NEAR_Y, FAR_Y = 300, 228             # hull top (water line) of the near and the far boat
ROW_A = [54, 53, 55, 54, 52, 55]     # frames per stroke before the split (about 27.8 a minute)
ROW_B = [44, 45, 43, 44, 46, 44]     # after it (about 34 a minute)
ROW_DECOY = [47, 48, 47, 46, 48]     # the far boat (about 31.9 a minute)
ROW_FIRST, ROW_DECOY_FIRST = 9, 31   # frame of each boat's first catch


def catch_frames(first: int, before: list[int], after: list[int] | None, split: float) -> list[int]:
    out, f, k = [], first, 0
    while f < frames(ROW_S) + 60:
        out.append(f)
        nxt = f + before[k % len(before)]
        if after is not None and nxt >= frames(split):
            nxt = f + after[k % len(after)]
        f, k = nxt, k + 1
    return out


def rate_after(in_video: list[int], split: float) -> float:
    fs = [f for f in in_video if f >= frames(split)]
    return round(60 * (len(fs) - 1) * FPS / (fs[-1] - fs[0]), 3)


def stroke(catches: list[int], t: float) -> float:
    """The stroke phase at t, 0 at a catch, rising to 1 at the next."""
    f = t * FPS
    for a, b in zip(catches, catches[1:]):
        if a <= f < b:
            return (f - a) / (b - a)
    return 0.0


def blade(u: float, catch_s: float) -> tuple[float, float]:
    """(x offset from the rowlock, y offset from the water line) of the blade at stroke phase u. Drive: the first
    0.8 s in the water, forward to back; then out, back to forward, and down into the water just before the catch."""
    drive = min(0.45, 0.8 / catch_s)
    ease = lambda v: (1 - math.cos(math.pi * max(0.0, min(1.0, v)))) / 2     # noqa: E731
    if u < drive:
        return 34 - 64 * ease(u / drive), 4.0
    v = (u - drive) / (1 - drive)
    x = -30 + 64 * ease((v - 0.08) / 0.84)
    if v < 0.08:
        y = 4 - 12 * v / 0.08
    elif v > 0.94:
        y = -8 + 12 * (v - 0.94) / 0.06
    else:
        y = -8.0
    return x, y


def draw_rowing(out: Path, v: Instance | None = None) -> Path:
    v = v or DEFAULT_INSTANCE
    world = canvas(WW, WH, "41603f")
    world[:110] = bgr("9cb7c9")
    world[160:] = bgr("1f5f8a")
    hull, body, oar, yellow = bgr("efefef"), bgr("b03030"), bgr("cfcfcf"), bgr("f2c522")
    boats = [(FAR_Y, v.decoy_catches), (NEAR_Y, v.catches)]

    def draw(img, t, ox, oy):
        for k, x0 in enumerate(range(0, 900, 60)):                                 # lane-rope floats, scrolling
            x = (x0 - 70 * t) % 900 - 100
            for y in (190, 264, 338):
                circle(img, x + (y // 2 % 30) - ox, y - oy, 2.5, bgr("e04a3a") if k % 4 else bgr("f0f0f0"))
        for y, cs in boats:
            u = stroke(cs, t)
            i = max(0, min(len(cs) - 2, next((j for j in range(len(cs) - 1) if cs[j + 1] > t * FPS), len(cs) - 2)))
            span = (cs[i + 1] - cs[i]) / FPS
            bx = 350 + 5 * math.sin(2 * math.pi * u)
            rect(img, bx - 46 - ox, y - oy, bx + 46 - ox, y + 5 - oy, hull)
            seat = bx - 8 + 12 * (1 - abs(1 - 2 * u))
            rect(img, seat - 3 - ox, y - 16 - oy, seat + 3 - ox, y - oy, body)
            circle(img, seat + 1 - ox, y - 20 - oy, 3, bgr("c89a74"))
            dx, dy = blade(u, span)
            lock = (bx + 4, y - 3)
            line(img, (lock[0] - ox, lock[1] - oy), (lock[0] + dx - ox, y + dy - oy), oar, 1)
            rect(img, lock[0] + dx - 5 - ox, y + dy - 2 - oy, lock[0] + dx + 5 - ox, y + dy + 2 - oy, yellow)

    return render(out, ROW_S, world, shaky(WW, WH, (30, 30), 8, 6, 3.3), draw, seed=34)


# --- one instance of the suite: the published one, or a fresh seed's -------------------------------------------------
@dataclass(frozen=True)
class Spec:
    """The numbers that make the events of one instance of the suite (`seed` None: the published suite)."""
    juggle: tuple
    decoy_juggle: tuple
    jug_first: int
    decoy_first: int
    shots: tuple
    passes: tuple
    defender_x: tuple
    pass_hidden: tuple
    row_a: tuple
    row_b: tuple
    row_decoy: tuple
    row_first: int
    row_decoy_first: int
    seed: int | None = None


class Instance:
    """The tasks and truth of one `Spec`, with everything its drawing needs. Raises ValueError when an event would
    sit too close to a video's edge (a fresh seed then draws again)."""

    def __init__(self, spec: Spec):
        self.spec, self.seed, self.SUITE = spec, spec.seed, SUITE
        self.jug_contacts = contacts(list(spec.juggle), spec.jug_first, JUG_N)
        self.decoy_contacts = contacts(list(spec.decoy_juggle), spec.decoy_first, JUG_N)
        self.jug_touches = [f for f, k, _ in self.jug_contacts if k == "F" and f < JUG_N]
        self.far_path, self.far_covered = far_shots(list(spec.shots))
        self.far_s = math.ceil(self.far_path.t * FPS) / FPS
        self.pass_path, self.releases = pass_path(list(spec.passes))
        self.catches = catch_frames(spec.row_first, list(spec.row_a), list(spec.row_b), ROW_SPLIT)
        self.decoy_catches = catch_frames(spec.row_decoy_first, list(spec.row_decoy), None, ROW_SPLIT)
        self.in_video = [f for f in self.catches if f < frames(ROW_S)]
        self.check()
        self.TASKS = self.tasks()
        self.BY_ID = {t.id: t for t in self.TASKS}

    def check(self) -> None:
        """Every in-video event is clear of the video's edges: the first and last counted events are well inside."""
        s = self.spec
        after = [f for f, _, _ in self.jug_contacts if f >= JUG_N]
        ok = [self.jug_touches[0] >= 10 and self.jug_touches[-1] <= JUG_N - 8, after[0] >= JUG_N + 4,
              all(abs(r * FPS - round(r * FPS)) < 1e-6 for r in self.releases), self.releases[-1] < PASS_S - 1,
              all(r in self.releases and min(abs(lerp_keys(list(s.defender_x), r) - x) for x in SPOTS.values()) < 4
                  for r in s.pass_hidden),
              self.far_path.t <= self.far_s, len(self.far_covered) == 3,
              self.in_video[-1] <= frames(ROW_S) - 8, self.catches[len(self.in_video)] >= frames(ROW_S) + 4]
        if not all(ok):
            raise ValueError(f"svc-bench-3 spec (seed {s.seed}) fails check {ok.index(False)}")

    def tasks(self) -> list[Task]:
        shots = self.spec.shots
        return [
            Task("juggle-touches", "count",
                 "Two players juggle identical small yellow balls with one foot, side view: the red player on the "
                 "left and the orange-red player on the right. Count the touches of the left (red) player: every "
                 "time his foot touches his ball. A quick double touch (the ball hops a little off the foot and is "
                 "touched again at once) is two touches. A bounce of the ball on the floor is not a touch. The right "
                 "player's touches do not count. The camera is hand-held.",
                 "an integer, e.g. `5`", JUG_S, len(self.jug_touches), functools.partial(draw_juggle, v=self)),
            Task("far-hoop-shots", "outcomes",
                 f"A wide shot of a far hoop (small red rim, grey net, white backboard): the blue shooter on the left "
                 f"takes {len(shots)} shots with a small orange ball. A shot starts when the ball leaves his hands; a "
                 "pump fake (the ball goes up and comes back down without leaving his hands) is not a shot. For each "
                 "shot in order: `made` if the ball goes down through the ring and out of the bottom of the net, else "
                 "`missed`. Bouncing or rolling on the rim and then going down through counts as made; a ball that "
                 "dips into the ring and pops back out, or falls just in front of the rim, is missed. A fan's banner "
                 "sometimes passes in front of the rim: judge those shots by where the ball comes out. The camera is "
                 "hand-held.",
                 f'a list of {len(shots)} strings, each "made" or "missed", e.g. `["made", "missed", ...]`',
                 self.far_s, [far_outcome(k) for k in shots], functools.partial(draw_far, v=self)),
            Task("pass-releases", "timestamps",
                 "Three blue players pass an orange ball; a red defender moves around in front of them, and a grey "
                 "pair further back passes an identical ball (not counted). Give the time of every release: the "
                 "moment the ball leaves a blue player on a pass to another blue player. A pass fake (the ball moves "
                 "toward a teammate and comes back without leaving the hands) is not a pass. A one-touch pass (the "
                 "ball is redirected the moment it arrives, without being held) is a pass, released when it arrives. "
                 "A bounce pass is one pass. When the defender hides the ball, judge the release from where the ball "
                 "goes. The camera is hand-held.",
                 "a list of seconds from the start of the video, in order, e.g. `[1.5, 4.25]`", PASS_S,
                 self.releases, functools.partial(draw_passes, v=self)),
            Task("stroke-rate", "rate",
                 "Two identical single sculls row side by side far from the camera, which follows them; each rower "
                 "has one oar with a small yellow blade. Look at the near boat (the lower one in the picture); its "
                 "rower changes the rate during the video. A catch is the moment its blade drops into the water at "
                 "the forward end of the stroke. Report the stroke rate from 15.0 s to the end: 60 x (the number of "
                 "catches at or after 15.0 s, minus 1) / (the time of the last of those catches minus the time of "
                 "the first), in strokes per minute. The far boat does not count. The camera is hand-held.",
                 "a number of strokes per minute, e.g. `30.5`", ROW_S, rate_after(self.in_video, ROW_SPLIT),
                 functools.partial(draw_rowing, v=self)),
        ]


DEFAULT = Spec(tuple(JUGGLE), tuple(DECOY_JUGGLE), JUG_FIRST, DECOY_FIRST, tuple(SHOTS3), tuple(PASSES),
               tuple(DEFENDER_X), tuple(PASS_HIDDEN), tuple(ROW_A), tuple(ROW_B), tuple(ROW_DECOY), ROW_FIRST,
               ROW_DECOY_FIRST)
DEFAULT_INSTANCE = Instance(DEFAULT)

# the published suite's values, by their old names
JUG_CONTACTS, DECOY_CONTACTS = DEFAULT_INSTANCE.jug_contacts, DEFAULT_INSTANCE.decoy_contacts
JUG_TOUCHES = DEFAULT_INSTANCE.jug_touches
FAR_PATH, FAR_COVERED, FAR_S = DEFAULT_INSTANCE.far_path, DEFAULT_INSTANCE.far_covered, DEFAULT_INSTANCE.far_s
PASS_PATH, RELEASES = DEFAULT_INSTANCE.pass_path, DEFAULT_INSTANCE.releases
CATCHES, DECOY_CATCHES, IN_VIDEO = DEFAULT_INSTANCE.catches, DEFAULT_INSTANCE.decoy_catches, DEFAULT_INSTANCE.in_video
TASKS = DEFAULT_INSTANCE.TASKS
BY_ID = DEFAULT_INSTANCE.BY_ID

assert len(BY_ID) == len(TASKS)


# --- fresh seeds -----------------------------------------------------------------------------------------------------
# Each generator keeps the published suite's kinds of traps and their sizes (a double touch is a 6-frame hop of about
# 10 px, a covered shot's ball reaches the rim behind the banner, a fake is 0.72 s, the far boat rows at least 6 %
# slower than the near boat after the change) and draws new counts, orders, holds and stroke lengths. Only Python's
# own `random.Random(seed)` with integer calls is used, so a seed gives the same suite on every machine.
COVERABLE = ("swish", "back-in", "front-up-in", "front-out", "back-out", "in-out")   # the ball comes out clearly
SHOT_KINDS = ("swish", "front-out", "back-in", "in-out", "short", "roll-in", "roll-out", "back-out", "front-up-in")


def fresh_juggle(rng: random.Random) -> tuple[tuple, int]:
    """A juggling sequence long enough for the whole video, and the frame of its first contact."""
    first = rng.randint(16, 26)
    seq, f = [], first
    while f <= JUG_N + 30:
        roll = rng.randrange(100)
        quick = bool(seq) and seq[-1][1] == 6
        if roll < 18 and seq and seq[-1][0] == "F" and not (len(seq) >= 2 and seq[-1][1] == seq[-2][1] == 6):
            entry = ("F", 6, rng.randint(9, 11))                   # a double touch: the next contact is the foot
        elif roll < 30 and not quick and seq:
            entry = ("N", rng.randint(11, 14), rng.randint(20, 40))
        else:
            gap = rng.randint(13, 19)                               # a higher arc takes longer, as published
            entry = ("F", gap, rng.randint(max(58, 5 * gap - 14), min(90, 5 * gap + 2)))
        if quick and entry[0] == "N":
            entry = ("F",) + entry[1:]
        seq.append(entry)
        f += entry[1]
    return tuple(seq), first


def fresh_shots(rng: random.Random) -> tuple:
    while True:
        n = rng.randint(10, 13)
        kinds = [SHOT_KINDS[rng.randrange(len(SHOT_KINDS))] for _ in range(n)]
        made = sum(far_outcome(k) == "made" for k in kinds)
        if not 3 <= made <= n - 3:
            continue
        can = [i for i, k in enumerate(kinds) if k in COVERABLE]
        if len(can) < 3:
            continue
        hidden: list[int] = []
        for _ in range(40):
            i = can[rng.randrange(len(can))]
            if all(abs(i - j) > 1 for j in hidden):
                hidden.append(i)
            if len(hidden) == 3:
                break
        if len(hidden) < 3:
            continue
        fakes = {rng.randrange(n) for _ in range(rng.randint(1, 2))}
        return tuple(("fake+" if i in fakes else "") + k + ("*" if i in hidden else "") for i, k in enumerate(kinds))


def fresh_passes(rng: random.Random) -> tuple[tuple, tuple, tuple]:
    """(passes, defender keyframes, the releases the defender hides)."""
    while True:
        n, who, t, passes = rng.randint(11, 13), "A", 0.0, []
        for k in range(n):
            to = rng.choice([x for x in "ABC" if x != who])
            roll = rng.randrange(100)
            again = bool(passes) and passes[-1][2] == "touch"
            style = ("touch" if k and roll < 18 and not again else "arc" if roll < 60 else "lob" if roll < 78
                     else "bounce")
            if {who, to} == {"A", "C"}:            # across the middle player: only a lob, as in the published suite
                style = "lob"
            hold = 0.0 if style == "touch" else rng.randint(10, 30) * 0.04
            fake = style != "touch" and rng.randrange(100) < 33
            passes.append((who, to, style, round(hold, 2), fake))
            t += hold + FAKE_S * fake + FLIGHT[style]
            who = to
        touches, fakes = sum(p[2] == "touch" for p in passes), sum(p[4] for p in passes)
        if not (1 <= touches <= 3 and 2 <= fakes <= 5 and 15.0 <= t <= PASS_S - 0.6):
            continue
        path, releases = pass_path(passes)
        if releases[-1] >= PASS_S - 1:
            continue
        hidden: list[float] = []
        caught = {r: r - p[3] - FAKE_S * p[4] for r, p in zip(releases, passes)}   # the ball reached the passer
        for _ in range(60):
            i = rng.randrange(1, n)
            r = releases[i]
            if (r >= 1.6 and passes[i][2] != "touch" and r - caught[r] >= 0.64
                    and all(abs(r - h) >= 2.4 for h in hidden)):            # a held ball, seen arriving first
                hidden.append(r)
            if len(hidden) == 4:
                break
        if len(hidden) < 4:
            continue
        hidden.sort()
        at = {r: SPOTS[passes[releases.index(r)][0]] for r in hidden}
        keys = [(0.0, rng.choice((240, 300, 430, 470)))]
        for k, r in enumerate(hidden):
            arrive = round(max(r - rng.randint(10, 20) * 0.04, caught[r] + 0.24), 2)
            leave = round(r + rng.randint(8, 14) * 0.04, 2)
            if k:
                mid = round((keys[-1][0] + arrive) / 2, 2)
                keys.append((mid, rng.choice((240, 300, 430, 470))))
            keys += [(arrive, at[r]), (leave, at[r])]
        keys.append((PASS_S, rng.choice((240, 300, 430, 470))))
        shown = True                                    # the ball is in plain sight except while the defender
        for k in range(int(PASS_S / 0.04)):              # walks up to a hidden release and away again
            t = k * 0.04
            (bx, by), _, _ = path.at(t)
            if by > 228 and abs(bx - lerp_keys(keys, t)) < 34 and not any(
                    caught[r] - 0.4 <= t <= r + 0.72 for r in hidden):
                shown = False
                break
        if shown and all(b[0] - a[0] >= 0.4 for a, b in zip(keys, keys[1:])):
            return tuple(passes), tuple(keys), tuple(hidden)


def fresh_rowing(rng: random.Random) -> tuple[tuple, tuple, tuple, int, int]:
    """(frames per stroke before the change, after it, the far boat's, first catch of the near and far boat)."""
    while True:
        a, b = rng.randint(50, 58), rng.randint(40, 46)
        lo, hi = math.ceil(b * 1.07), a - 3                    # the far boat: >= 6 % slower than the near after
        if lo > hi:
            continue
        d = rng.randint(lo, hi)
        row_a = tuple(a + rng.randint(-2, 2) for _ in range(6))
        row_b = tuple(b + rng.randint(-2, 2) for _ in range(6))
        row_d = tuple(d + rng.randint(-1, 1) for _ in range(5))
        return row_a, row_b, row_d, rng.randint(5, 16), rng.randint(20, 40)


def fresh(seed: int) -> Spec:
    """A new Spec drawn from `seed` (an integer from 0 to 2**63 - 1); the same seed always gives the same Spec."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be an integer from 0 to {MAX_SEED}, not {seed!r}")
    rng = random.Random(seed)
    for _ in range(200):
        juggle, first = fresh_juggle(rng)
        decoy_k = rng.randrange(len(DECOY_JUGGLE))
        shots = fresh_shots(rng)
        passes, defender, hidden = fresh_passes(rng)
        row_a, row_b, row_d, row_first, decoy_first = fresh_rowing(rng)
        spec = Spec(juggle, tuple(DECOY_JUGGLE[decoy_k:] + DECOY_JUGGLE[:decoy_k]), first, rng.randint(22, 32),
                    shots, passes, defender, hidden, row_a, row_b, row_d, row_first, decoy_first, seed)
        try:
            Instance(spec)
        except ValueError:
            continue
        return spec
    raise RuntimeError(f"no svc-bench-3 spec found for seed {seed}")


@functools.lru_cache(maxsize=64)
def seeded(seed: int) -> Instance:
    """The suite drawn from a fresh seed: an object with SUITE, TASKS and BY_ID like this module, and `seed`."""
    return Instance(fresh(seed))


def new_seed() -> int:
    """A random seed for a fresh run (from the OS, not the clock)."""
    import secrets
    return secrets.randbelow(10 ** 9)
