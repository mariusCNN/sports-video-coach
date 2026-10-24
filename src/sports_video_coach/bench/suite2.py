"""The benchmark suite `svc-bench-2` ("hard"): drawn videos with exact truth that a naive colour-blob tracker gets
wrong.

Suite 1 was saturated: every agent tried wrote a small pixel tracker and scored 1.0. The same answer kinds come back
here, drawn the hard way:
- a hand-held camera (shake, a slow tilt, a camera that follows the runner), so fixed pixel positions mean nothing
  and every rule is relative to something in the scene;
- look-alike decoys of the same colour (a second dribbler with an identical ball, two identical feet, a rebounder
  who puts a missed shot back in);
- rule-defined events (partial reps, a rep that never locks out, a pump fake, a ball that dips in and pops out);
- an occluding pillar, events 0.4 s apart and a pace that changes halfway;
- sensor noise, a brightness flicker, a short motion blur and stronger compression.

Frames are drawn with numpy / OpenCV (both core dependencies) and piped to ffmpeg; 640x360 at 25 fps like suite 1.
Every truth is computed from the same numbers that drive the drawing, so the two cannot drift apart, and the noise
uses a fixed seed. The truth lives here and is never written into a prepared folder.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np

from .. import media
from .suite import FPS, H, W, Task

SUITE = "svc-bench-2"
NOISE = 12                    # +- uniform sensor noise per channel
CRF = 30                      # stronger compression than suite 1 (20)
SHUTTER = (-1 / 75, 0.0, 1 / 75)  # each frame is the mean of three instants: a short motion blur


def bgr(rgb: str) -> tuple[int, int, int]:
    v = int(rgb, 16)
    return v & 255, (v >> 8) & 255, v >> 16


def frames(seconds: float) -> int:
    return round(seconds * FPS)


def shake(t: float, ax: float, ay: float, seed: float) -> tuple[float, float]:
    """A hand-held camera: a few incommensurate sines, at most `ax` / `ay` pixels."""
    x = ax * (0.55 * math.sin(2 * math.pi * 1.7 * t + seed) + 0.3 * math.sin(2 * math.pi * 3.1 * t + 2 * seed + 1)
              + 0.15 * math.sin(2 * math.pi * 0.43 * t + 0.5))
    y = ay * (0.5 * math.sin(2 * math.pi * 2.3 * t + seed + 2) + 0.3 * math.sin(2 * math.pi * 1.1 * t + 0.7)
              + 0.2 * math.sin(2 * math.pi * 4.3 * t + seed))
    return x, y


def clamp(v: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(v))))


def lerp_keys(keys: list[tuple[float, float]], t: float) -> float:
    """Piecewise linear through (time, value) keyframes, flat outside them."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0) if t1 > t0 else v1
    return keys[-1][1]


# --- drawing helpers (frame coordinates = world minus the camera offset) ---------------------------------------------

def circle(img, x: float, y: float, r: float, color) -> None:
    import cv2
    cv2.circle(img, (int(round(x * 16)), int(round(y * 16))), int(round(r * 16)), color, -1, cv2.LINE_AA, 4)


def rect(img, x0: float, y0: float, x1: float, y1: float, color) -> None:
    import cv2
    cv2.rectangle(img, (int(round(x0)), int(round(y0))), (int(round(x1)) - 1, int(round(y1)) - 1), color, -1)


def line(img, p0, p1, color, thick: int) -> None:
    import cv2
    cv2.line(img, (int(round(p0[0] * 16)), int(round(p0[1] * 16))), (int(round(p1[0] * 16)), int(round(p1[1] * 16))),
             color, thick, cv2.LINE_AA, 4)


def render(out: Path, seconds: float, world: np.ndarray, cam: Callable[[int], tuple[int, int]],
           draw: Callable[[np.ndarray, float, int, int], None], seed: int) -> Path:
    """Draw every frame (a crop of `world` at the camera offset, then the moving things) and encode it with ffmpeg.
    `cam(i)` gives the integer world offset of frame i; `draw(frame, t, ox, oy)` paints the scene at time t."""
    n = frames(seconds)
    cmd = [media.ffmpeg_exe(), "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(CRF),
           "-g", str(FPS), "-bf", "0", "-pix_fmt", "yuv420p", str(out)]
    rng = np.random.default_rng(seed)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n):
            t = i / FPS
            ox, oy = cam(i)
            acc = np.zeros((H, W, 3), np.float32)
            for dt in SHUTTER:
                f = world[oy:oy + H, ox:ox + W].copy()
                draw(f, t + dt, ox, oy)
                acc += f
            acc *= (1 + 0.06 * math.sin(2 * math.pi * 0.7 * t + seed)) / len(SHUTTER)   # brightness flicker
            acc += rng.integers(-NOISE, NOISE + 1, size=acc.shape, dtype=np.int16)
            proc.stdin.write(np.clip(acc, 0, 255).astype(np.uint8).tobytes())
        proc.stdin.close()
        rc = proc.wait()
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    if rc:
        raise subprocess.CalledProcessError(rc, cmd)
    return out


def canvas(w: int, h: int, color: str) -> np.ndarray:
    img = np.empty((h, w, 3), np.uint8)
    img[:] = bgr(color)
    return img


def shaky(world_w: int, world_h: int, base: tuple[float, float], ax: float, ay: float, seed: float,
          drift: Callable[[float], tuple[float, float]] = lambda t: (0.0, 0.0)) -> Callable[[int], tuple[int, int]]:
    def cam(i: int) -> tuple[int, int]:
        t = i / FPS
        sx, sy = shake(t, ax, ay, seed)
        dx, dy = drift(t)
        return clamp(base[0] + sx + dx, 0, world_w - W), clamp(base[1] + sy + dy, 0, world_h - H)
    return cam


# --- count: the blue player's dribbles ------------------------------------------------------------------------------
# Two players dribble identical orange balls and swap sides once (the balls pass each other). The blue player then
# carries his ball (no dribble) behind a pillar and back. Bounce intervals are whole frames; a few dribbles are low.
DRIBBLE_S = 38.0
DRIB_FLOOR = 330
BALL_R = 10
PILLAR = (520, 575)
BLUE_X = [(0, 130), (9, 130), (13, 390), (19, 390), (22, 640), (23.5, 640), (26.5, 390), (DRIBBLE_S, 390)]
GREEN_X = [(0, 410), (9, 410), (13, 150), (DRIBBLE_S, 150)]
BLUE_IV = [13, 12, 15, 11, 14, 12, 16, 13, 11, 14]               # frames between bounces
BLUE_H = [70, 74, 66, 18, 72, 70, 22, 68, 75, 64, 16, 72]        # arc heights (px above the floor)
GREEN_IV = [14, 12, 13, 15, 12]
GREEN_H = [66, 72, 60, 70, 64]
BLUE_HOLD = (465, 672)   # frames: last bounce before the carry is at or before 465, the next bounce is at 672
HOLD_H = 52              # the carried ball's height above the floor


def bounce_frames(start: int, last: int, iv: list[int]) -> list[int]:
    out, f, k = [], start, 0
    while f <= last:
        out.append(f)
        f += iv[k % len(iv)]
        k += 1
    return out


BLUE_BOUNCES = bounce_frames(8, BLUE_HOLD[0], BLUE_IV) + bounce_frames(BLUE_HOLD[1], frames(DRIBBLE_S) - 10,
                                                                         BLUE_IV[3:] + BLUE_IV[:3])
GREEN_BOUNCES = bounce_frames(10, frames(DRIBBLE_S) + 20, GREEN_IV)


def dribble_segments(bounces: list[int], heights: list[int], hold: tuple[int, int] | None) -> list[tuple]:
    """(t0, t1, kind, height): 'arc' between two bounces, 'hold' for the carry (rise, hold, fall). The last arc lands
    after the video ends, so the ball is in the air in the last frame and every floor touch in the video is a
    counted bounce."""
    fs = [bounces[0] - 13] + bounces + [max(bounces[-1], frames(DRIBBLE_S)) + 13]
    segs = []
    for k, (a, b) in enumerate(zip(fs, fs[1:])):
        kind = "hold" if hold and a <= hold[0] < b and b == hold[1] else "arc"
        segs.append((a / FPS, b / FPS, kind, HOLD_H if kind == "hold" else heights[k % len(heights)]))
    return segs


def height_at(segs: list[tuple], t: float) -> float:
    for t0, t1, kind, h in segs:
        if t0 <= t <= t1:
            if kind == "arc":
                u = (t - t0) / (t1 - t0)
                return h * 4 * u * (1 - u)
            r = 0.28
            if t < t0 + r:
                return h * (1 - ((t - t0 - r) / r) ** 2)
            if t > t1 - r:
                return h * (1 - ((t - t1 + r) / r) ** 2)
            return float(h)
    return 0.0


def draw_dribble(out: Path) -> Path:
    import cv2
    ww, wh = 700, 420
    world = canvas(ww, wh, "2a3550")
    for x in range(20, ww, 90):
        cv2.rectangle(world, (x, 40), (x + 5, DRIB_FLOOR - 1), bgr("56637f"), -1)       # wall panels
    world[DRIB_FLOOR:DRIB_FLOOR + 3] = bgr("f0f0f0")
    world[DRIB_FLOOR + 3:] = bgr("8b5a2b")
    blue_segs = dribble_segments(BLUE_BOUNCES, BLUE_H, BLUE_HOLD)
    green_segs = dribble_segments(GREEN_BOUNCES, GREEN_H, None)
    ball = bgr("f08a24")

    def player(img, x, color, ox, oy):
        rect(img, x - 18 - ox, DRIB_FLOOR - 92 - oy, x + 18 - ox, DRIB_FLOOR - oy, color)
        circle(img, x - ox, DRIB_FLOOR - 106 - oy, 12, color)

    def draw(img, t, ox, oy):
        gx, bx = lerp_keys(GREEN_X, t), lerp_keys(BLUE_X, t)
        player(img, gx, bgr("2e9e4f"), ox, oy)
        circle(img, gx - 30 - ox, DRIB_FLOOR - BALL_R - height_at(green_segs, t) - oy, BALL_R, ball)
        player(img, bx, bgr("3355cc"), ox, oy)
        circle(img, bx + 30 - ox, DRIB_FLOOR - BALL_R - height_at(blue_segs, t) - oy, BALL_R, ball)
        rect(img, PILLAR[0] - ox, 0, PILLAR[1] - ox, H, bgr("6e6e6e"))
        rect(img, PILLAR[0] - ox, 0, PILLAR[0] + 4 - ox, H, bgr("4a4a4a"))

    return render(out, DRIBBLE_S, world, shaky(ww, wh, (30, 30), 14, 10, 0.3), draw, seed=21)


# --- count: good squat reps -----------------------------------------------------------------------------------------
# The centre of the yellow plate must go below the lower (depth) line and then back above the upper (lockout) line.
SQUAT_TOP, LOCK_Y, DEPTH_Y = 140, 150, 260       # world y: standing plate centre, upper line, lower line
SQUAT_FLOOR = 380
SQUATS = [[272], [268], [248], [274], [270, 196, 272], [250], [246], [270], [270, 160, 268], [276], [252], [268],
          [272, 196]]                            # turning points of each attempt; the last never locks out
SQUAT_RESTS = [0.8, 0.7, 1.1, 0.6, 0.9, 1.3, 0.7, 0.8, 1.0, 0.6, 0.9, 1.2]


def squat_keys() -> list[tuple[float, float]]:
    """(time, plate y) waypoints; cosine easing between them, so the turning points are the extremes."""
    keys, t = [(0.0, SQUAT_TOP), (1.0, SQUAT_TOP)], 1.0
    for k, turns in enumerate(SQUATS):
        last = k == len(SQUATS) - 1
        path = turns + ([] if last else [SQUAT_TOP])
        prev = SQUAT_TOP
        for y in path:
            t += 0.84 if abs(y - prev) > 90 else 0.52
            keys.append((round(t, 2), y))
            if y > DEPTH_Y - 20:                  # a short pause at the bottom
                t += 0.12
                keys.append((round(t, 2), y))
            prev = y
        if not last:
            t += SQUAT_RESTS[k]
            keys.append((round(t, 2), SQUAT_TOP))
    keys.append((round(t + 1.2, 2), keys[-1][1]))
    return keys


SQUAT_KEYS = squat_keys()
SQUAT_S = math.ceil(SQUAT_KEYS[-1][0]) + 1.0


def good_reps(ys: list[float]) -> int:
    below, n = False, 0
    for y in ys:
        if y > DEPTH_Y:
            below = True
        elif y < LOCK_Y and below:
            n, below = n + 1, False
    return n


def plate_y(t: float) -> float:
    keys = SQUAT_KEYS
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, y0), (t1, y1) in zip(keys, keys[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return y0 + (y1 - y0) * (1 - math.cos(math.pi * u)) / 2
    return keys[-1][1]


def draw_squat(out: Path) -> Path:
    import cv2
    ww, wh = 700, 420
    world = canvas(ww, wh, "26303f")
    world[SQUAT_FLOOR:] = bgr("5a4a3a")
    for x0 in (250, 438):
        cv2.rectangle(world, (x0, 60), (x0 + 11, SQUAT_FLOOR - 1), bgr("8a8f99"), -1)   # rack uprights
    for y in (LOCK_Y, DEPTH_Y):
        world[y - 1:y + 2, 230:470] = bgr("f4f4f4")                                       # the two white lines
    plate, body = bgr("f2c522"), bgr("a33a2a")

    def draw(img, t, ox, oy):
        y = plate_y(t) + 2.5 * math.sin(2 * math.pi * 0.35 * t)
        rect(img, 338 - ox, y + 70 - oy, 362 - ox, SQUAT_FLOOR - oy, body)          # legs
        rect(img, 336 - ox, y - 6 - oy, 364 - ox, y + 72 - oy, body)                # torso
        circle(img, 330 - ox, y - 26 - oy, 12, body)                                # head
        circle(img, 350 - ox, y - oy, 16, plate)

    def tilt(t):
        return 0.0, -40 * t / SQUAT_S

    return render(out, SQUAT_S, world, shaky(ww, wh, (30, 50), 8, 8, 1.1, tilt), draw, seed=22)


# --- rate: running cadence that changes halfway -------------------------------------------------------------------
CADENCE_S = 40.0
CADENCE_SPLIT = 20.0
STRIDE_A = [10, 9, 10, 10, 9, 11, 10, 9]   # frames between foot strikes before the split (about 154 a minute)
STRIDE_B = [8, 9, 8, 8, 9, 8, 7, 9]        # after it (about 182 a minute)
BELT_Y = 300
FOOT_FRONT, FOOT_BACK = 392, 312


def strike_frames() -> list[int]:
    out, f, k = [], 6, 0
    split = frames(CADENCE_SPLIT)
    while f < frames(CADENCE_S):
        out.append(f)
        nxt = f + STRIDE_A[k % len(STRIDE_A)]
        if nxt >= split:
            nxt = f + STRIDE_B[k % len(STRIDE_B)]
        f, k = nxt, k + 1
    return out


STRIKES = strike_frames()


def cadence_after(split: float) -> float:
    fs = [f for f in STRIKES if f >= frames(split)]
    return round(60 * (len(fs) - 1) * FPS / (fs[-1] - fs[0]), 3)


def foot_pos(strikes: list[float], other: list[float], t: float) -> tuple[float, float]:
    """One foot: on the belt from its strike for 80 % of the step, moving back with the belt; then a swing forward
    and up until its next strike."""
    stride = strikes[1] - strikes[0]
    s = [strikes[0] - stride] + strikes + [strikes[-1] + stride]
    for a, b in zip(s, s[1:]):
        if a <= t < b:
            nxt_other = min([o for o in other if o > a] or [a + (b - a) / 2])
            contact = 0.8 * (nxt_other - a)
            if t < a + contact:
                return FOOT_BACK + (FOOT_FRONT - FOOT_BACK) * (1 - (t - a) / contact), 0.0
            u = (t - a - contact) / (b - a - contact)
            return FOOT_BACK + (FOOT_FRONT - FOOT_BACK) * (3 * u * u - 2 * u ** 3), 44 * math.sin(math.pi * u)
    return FOOT_FRONT, 0.0


def draw_cadence(out: Path) -> Path:
    import cv2
    ww, wh = 700, 420
    world = canvas(ww, wh, "33415a")
    cv2.rectangle(world, (140, BELT_Y + 16), (570, BELT_Y + 60), bgr("70757d"), -1)       # treadmill deck
    cv2.rectangle(world, (560, 150), (575, BELT_Y + 60), bgr("70757d"), -1)               # its console post
    world[BELT_Y + 60:] = bgr("4a3a2c")
    ts = [f / FPS for f in STRIKES]
    left, right = ts[0::2], ts[1::2]
    belt, stripe = bgr("3c3c3c"), bgr("6a6a6a")
    foot, limb, body = bgr("161616"), bgr("a33a2a"), bgr("2f6fbf")

    def draw(img, t, ox, oy):
        rect(img, 150 - ox, BELT_Y - oy, 560 - ox, BELT_Y + 16 - oy, belt)
        shift = (t * 200) % 40
        for x in range(150, 600, 40):
            sx = x - shift
            if 150 <= sx <= 554:
                rect(img, sx - ox, BELT_Y + 2 - oy, sx + 6 - ox, BELT_Y + 14 - oy, stripe)
        hip = (352 - ox, 228 - oy)
        rect(img, 335 - ox, 148 - oy, 369 - ox, 230 - oy, body)
        circle(img, 356 - ox, 132 - oy, 13, body)
        for mine, other in ((left, right), (right, left)):
            fx, lift = foot_pos(mine, other, t)
            fy = BELT_Y - 6 - lift
            line(img, hip, (fx - ox, fy - oy), limb, 7)
            rect(img, fx - 15 - ox, fy - 6 - oy, fx + 15 - ox, fy + 6 - oy, foot)
            swing = (fx - (FOOT_FRONT + FOOT_BACK) / 2) / 40                    # arm opposite to its leg
            line(img, (352 - ox, 160 - oy), (352 - 48 * swing - ox, 215 - oy), limb, 6)

    return render(out, CADENCE_S, world, shaky(ww, wh, (30, 30), 10, 8, 2.2), draw, seed=23)


# --- timestamps: cone touches with a camera that follows the runner --------------------------------------------------
# A long field (1700 px); the camera follows the runner with a lag, so in the picture the runner seems to turn when
# the camera catches up. A touch = a keyframe at a cone, reached by moving, after which the runner stops or turns.
FIELD_W = 1700
CONES = [140, 560, 860, 940, 1280, 1560]
RUN2 = [(0.0, 140), (0.8, 140), (3.6, 560), (4.4, 560), (7.6, 1280), (9.0, 1060), (9.8, 1060), (10.6, 860),
        (11.0, 940), (11.4, 860), (13.0, 1280), (14.8, 1560), (15.6, 1560), (19.6, 560), (20.8, 760), (21.6, 760),
        (22.0, 860), (22.6, 860), (23.2, 940), (26.6, 140), (28.0, 140)]
RUN2_S = 28.0
RUN_GROUND = 330
CAM_LAG = 0.07   # per frame: the camera centre moves this share of the way to the runner


def cone_touches() -> list[float]:
    out = []
    for (_, xa), (t, xb), (_, xc) in zip(RUN2, RUN2[1:], RUN2[2:]):
        if xb in CONES and xa != xb and (xc == xb or (xc - xb > 0) != (xb - xa > 0)):
            out.append(t)
    return out


def follow_cam() -> Callable[[int], tuple[int, int]]:
    xs, c = [], float(RUN2[0][1])
    for i in range(frames(RUN2_S)):
        c += CAM_LAG * (lerp_keys(RUN2, i / FPS) - c)
        xs.append(c)

    def cam(i: int) -> tuple[int, int]:
        sx, sy = shake(i / FPS, 6, 8, 0.7)
        return clamp(xs[min(i, len(xs) - 1)] - W / 2 + sx, 0, FIELD_W - W), clamp(30 + sy, 0, 60)
    return cam


def draw_cones(out: Path) -> Path:
    import cv2
    wh = 420
    world = canvas(FIELD_W, wh, "3b4a3f")
    world[200:] = bgr("2f6b3a")
    posts = [37, 151, 233, 380, 455, 612, 690, 843, 917, 1068, 1179, 1250, 1405, 1471, 1622]
    for x in posts:
        cv2.rectangle(world, (x, 110), (x + 7, 199), bgr("9aa38f"), -1)                   # fence posts
    world[150:153] = bgr("9aa38f")
    for x in range(100, FIELD_W, 100):
        world[200:, x - 1:x + 2] = bgr("e8e8e8")                                         # field lines
    world[362:365] = bgr("e8e8e8")
    for x in CONES:
        pts = np.array([[x - 12, RUN_GROUND], [x + 12, RUN_GROUND], [x, RUN_GROUND - 30]], np.int32)
        cv2.fillPoly(world, [pts], bgr("ff8c1a"), cv2.LINE_AA)
    red = bgr("d0312d")

    def draw(img, t, ox, oy):
        x = lerp_keys(RUN2, t)
        rect(img, x - 15 - ox, RUN_GROUND - 62 - oy, x + 15 - ox, RUN_GROUND - 2 - oy, red)

    return render(out, RUN2_S, world, follow_cam(), draw, seed=24)


# --- outcomes: hard shots -----------------------------------------------------------------------------------------
# Side view. Ball centre paths are built from segments; a shot is made when the ball goes down through the ring and
# out of the bottom of the net before anyone else touches it.
RIM_Y, RIM_X0, RIM_X1 = 160, 500, 560
NET_BOTTOM = 200
COURT_FLOOR = 350
SHOT_R = 8
HANDS = (106, 250)
FLOOR_BALL = COURT_FLOOR - SHOT_R
SHOTS2 = ["swish", "front-out", "in-out", "back-high-in", "fake+bank-in", "airball-tipin", "roll-in", "roll-out",
          "front-up-in", "fake+back-front-out", "swish", "in-out"]
MADE2 = {"swish", "back-high-in", "bank-in", "roll-in", "front-up-in"}


def shot_outcome(kind: str) -> str:
    return "made" if kind.split("+")[-1] in MADE2 else "missed"


class Path2:
    """A ball path: segments (t0, t1, f(u) -> (x, y), in_hands, holder)."""

    def __init__(self, start):
        self.t, self.p, self.segs = 0.0, start, []

    def seg(self, dur, f, hands=False, holder=""):
        self.segs.append((self.t, self.t + dur, f, hands, holder))
        self.t += dur
        self.p = f(1.0)

    def hold(self, dur, hands=True, holder="shooter"):
        p = self.p
        self.seg(dur, lambda u: p, hands, holder)

    def line(self, dur, p1, hands=False):
        p0 = self.p
        self.seg(dur, lambda u: (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u), hands)

    def arc(self, dur, p1, h):
        p0 = self.p
        self.seg(dur, lambda u: (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u - 4 * h * u * (1 - u)))

    def drop(self, dur, p1):
        p0 = self.p
        self.seg(dur, lambda u: (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u * u))

    def orbit(self, dur, phi1):
        c = (RIM_X0 + RIM_X1) / 2

        def f(u):
            phi = phi1 * u
            return c + 18 * math.cos(phi), RIM_Y - 10 - 3 * abs(math.sin(phi))
        self.seg(dur, f)

    def through(self):
        self.drop(0.35, (530, NET_BOTTOM + 15))
        self.drop(0.3, (530, FLOOR_BALL))

    def at(self, t):
        for t0, t1, f, hands, holder in self.segs:
            if t0 <= t <= t1:
                return f((t - t0) / (t1 - t0) if t1 > t0 else 1.0), hands, holder
        t0, t1, f, hands, holder = self.segs[0] if t < self.segs[0][0] else self.segs[-1]
        return f(0.0 if t < t0 else 1.0), hands, holder


def shots_path() -> Path2:
    p = Path2(HANDS)
    for kind in SHOTS2:
        p.hold(0.5)
        if kind.startswith("fake+"):
            p.line(0.3, (HANDS[0], HANDS[1] - 28), hands=True)
            p.line(0.3, HANDS, hands=True)
            p.hold(0.4)
        p.line(0.25, (110, 228), hands=True)
        what = kind.split("+")[-1]
        target = {"swish": (530, 150), "front-out": (501, 151), "in-out": (536, 150), "back-high-in": (553, 151),
                  "bank-in": (558, 112), "airball-tipin": (470, 215), "roll-in": (548, 150),
                  "roll-out": (548, 150), "front-up-in": (501, 151), "back-front-out": (553, 151)}[what]
        p.arc(1.1, target, 120)
        if what == "swish":
            p.through()
        elif what == "front-out":
            p.arc(0.7, (440, FLOOR_BALL), 50)
        elif what == "in-out":
            p.line(0.12, (534, 166))
            p.arc(0.9, (440, FLOOR_BALL), 100)
        elif what == "back-high-in":
            p.arc(0.9, (530, 150), 70)
            p.through()
        elif what == "bank-in":
            p.line(0.25, (530, 150))
            p.through()
        elif what == "airball-tipin":
            p.drop(0.25, (468, 252))
            p.hold(0.25, hands=False, holder="rebounder")
            p.arc(0.8, (530, 150), 60)
            p.through()
        elif what == "roll-in":
            p.orbit(1.1, 2.5 * math.pi)
            p.through()
        elif what == "roll-out":
            p.orbit(1.2, 3 * math.pi)
            p.arc(0.3, (486, RIM_Y), 6)          # rolls off over the front of the rim, outside the ring
            p.drop(0.45, (455, FLOOR_BALL))
        elif what == "front-up-in":
            p.arc(0.7, (530, 150), 45)
            p.through()
        elif what == "back-front-out":
            p.arc(0.7, (496, 151), 50)
            p.arc(0.6, (445, FLOOR_BALL), 30)
        x = p.p[0]
        p.arc(0.5, (x - 40, FLOOR_BALL), 40)
        p.arc(0.9, HANDS, 50)
    p.hold(0.6)
    return p


SHOT_PATH = shots_path()
SHOTS2_S = math.ceil(SHOT_PATH.t * FPS) / FPS


def draw_shots2(out: Path) -> Path:
    import cv2
    ww, wh = 700, 420
    world = canvas(ww, wh, "23324a")
    world[COURT_FLOOR:] = bgr("8b5a2b")
    cv2.rectangle(world, (566, 80), (573, 179), bgr("f0f0f0"), -1)                      # backboard
    cv2.rectangle(world, (574, 120), (699, 125), bgr("777777"), -1)                     # its arm
    cv2.rectangle(world, (640, 120), (651, COURT_FLOOR - 1), bgr("777777"), -1)         # pole
    ball, net, rim = bgr("f08a24"), bgr("dddddd"), bgr("d02020")
    path = SHOT_PATH
    tip = [(s[0], s[1]) for s in path.segs if s[4] == "rebounder"]

    def draw(img, t, ox, oy):
        (bx, by), hands, _ = path.at(t)
        jump = 22 if any(a - 0.2 <= t <= b + 0.15 for a, b in tip) else 0
        rect(img, 430 - ox, 262 - jump - oy, 460 - ox, COURT_FLOOR - jump - oy, bgr("2e9e4f"))   # rebounder
        rise = (HANDS[1] - by) * 0.6 if hands else 0.0
        rect(img, 70 - ox, 258 - rise - oy, 102 - ox, COURT_FLOOR - rise - oy, bgr("3355cc"))    # shooter
        circle(img, bx - ox, by - oy, SHOT_R, ball)
        for a, b in (((504, 164), (512, NET_BOTTOM)), ((556, 164), (548, NET_BOTTOM)), ((504, 164), (530, NET_BOTTOM)),
                     ((530, 164), (548, NET_BOTTOM)), ((530, 164), (512, NET_BOTTOM)),
                     ((556, 164), (530, NET_BOTTOM))):
            line(img, (a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy), net, 1)
        rect(img, RIM_X0 - ox, RIM_Y - oy, RIM_X1 - ox, RIM_Y + 4 - oy, rim)

    return render(out, SHOTS2_S, world, shaky(ww, wh, (30, 30), 12, 9, 1.7), draw, seed=25)


TASKS = [
    Task("dribble-count", "count",
         "Two players dribble identical orange balls: the blue player and the green player. Count the bounces of "
         "the blue player's ball: each time it touches the floor (the white line), however low the dribble. The "
         "green player's bounces do not count. The camera is hand-held. When the blue player walks behind the grey "
         "pillar he carries his ball in his hand: no bounce of his happens while his ball is hidden.",
         "an integer, e.g. `5`", DRIBBLE_S, len(BLUE_BOUNCES), draw_dribble),
    Task("squat-reps", "count",
         "A lifter (side view) squats with a yellow plate on his shoulders in front of a rack with two white "
         "lines. Count the good reps. A rep is good when the centre of the yellow plate goes below the lower white "
         "line and after that comes back above the upper white line. Going below the lower line again before "
         "getting back above the upper line does not start a new rep, and a squat that has not come back above the "
         "upper line when the video ends does not count. The camera is hand-held.",
         "an integer, e.g. `5`", SQUAT_S, good_reps([y for _, y in SQUAT_KEYS]), draw_squat),
    Task("cadence-change", "rate",
         "A runner on a treadmill, side view; both feet look the same. A foot strike is the moment either foot "
         "lands on the belt. The runner changes pace during the video. Report the cadence from 20.0 s to the end: "
         "60 x (the number of foot strikes at or after 20.0 s, minus 1) / (the time of the last of those strikes "
         "minus the time of the first), in strikes per minute. Arm swings are not strikes. The camera is "
         "hand-held.",
         "a number of strikes per minute, e.g. `150.5`", CADENCE_S, cadence_after(CADENCE_SPLIT), draw_cadence),
    Task("cone-touches-pan", "timestamps",
         "A red runner moves along a long field with six orange cones; the camera follows the runner, so the cones "
         "move across the picture. Give the time of every cone touch: the moment the runner's centre arrives at a "
         "cone where the runner then stops or turns back. Starting at a cone is not a touch. Running past a cone "
         "without stopping (also when the runner slows down or speeds up there) is not a touch, and stopping "
         "between cones is not a touch.",
         "a list of seconds from the start of the video, in order, e.g. `[1.5, 4.25]`", RUN2_S, cone_touches(),
         draw_cones),
    Task("shot-outcomes-hard", "outcomes",
         f"A shooter (blue, left) takes {len(SHOTS2)} shots at the hoop (red rim, grey net, white backboard); a "
         "green player stands under the hoop. A shot starts when the ball leaves the shooter's hands; a pump fake "
         "(the ball goes up and comes back down without leaving his hands) is not a shot. For each shot in order: "
         "`made` if the ball goes down through the ring and out of the bottom of the net before anyone else touches "
         "it, else `missed`. Bouncing or rolling on the rim or off the backboard and then going down through counts "
         "as made. A ball that dips into the ring and pops back out is missed. If the green player touches the ball "
         "before it goes in, the shot is missed, even if he then puts it in. The camera is hand-held.",
         f'a list of {len(SHOTS2)} strings, each "made" or "missed", e.g. `["made", "missed", ...]`', SHOTS2_S,
         [shot_outcome(k) for k in SHOTS2], draw_shots2),
]
BY_ID = {t.id: t for t in TASKS}

assert len(BY_ID) == len(TASKS)
# every rule has a margin: no turning point of the plate sits within 8 px of a line
assert all(abs(y - line_y) >= 8 for turns in SQUATS for y in turns + [SQUAT_TOP] for line_y in (LOCK_Y, DEPTH_Y))
assert all(abs(t * FPS - round(t * FPS)) < 1e-9 for t, _ in RUN2)
assert all(x in CONES for x in (140, 560, 860, 940, 1280, 1560))
# the carried ball is hidden behind the pillar only inside the carry
assert BLUE_BOUNCES[BLUE_BOUNCES.index(BLUE_HOLD[1]) - 1] <= BLUE_HOLD[0] < BLUE_HOLD[1]
