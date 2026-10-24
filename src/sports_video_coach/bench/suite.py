"""The benchmark suite `svc-bench-1`: short drawn videos whose ground truth is exact because we drew it.

Every video is drawn with ffmpeg from lavfi colour sources, drawbox and overlay with time expressions (the style of
`sports_video_coach.demo`): no people, no real footage. 640x360 at 25 fps, each one 20-31 s. The truth of a task is
computed from the same numbers that drive its drawing, so the two cannot drift apart.

Kinds and their answer shapes:
- count: an integer
- rate: a number per minute
- timestamps: a list of seconds from the start of the video
- outcomes: a list of "made" / "missed", in order

The truth lives here, in the package, and is never written into a prepared folder.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import media

SUITE = "svc-bench-1"
FPS = 25
W, H = 640, 360
KINDS = ("count", "rate", "timestamps", "outcomes")


def num(v: float) -> str:
    """A number for an ffmpeg expression (no exponent, no trailing zeros)."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def windows(default: str, parts: list[tuple[float, float, str]]) -> str:
    """An ffmpeg expression in `t`: `default`, except inside each [t0, t1) window where it is that window's
    expression. A flat sum of gated terms (windows must not overlap), so no deep if() nesting."""
    terms = [f"gte(t,{num(a)})*lt(t,{num(b)})*(({e})-({default}))" for a, b, e in parts]
    return "+".join([f"({default})"] + terms)


def ramp(t0: float, t1: float, v0: float, v1: float) -> str:
    """Linear from v0 at t0 to v1 at t1."""
    return f"{num(v0)}+({num(v1 - v0)})*(t-{num(t0)})/{num(t1 - t0)}"


def encode(out: Path, seconds: float, bg: str, boxes: list[str], sprites: list[tuple[str, str, str]]) -> Path:
    """Draw one video: a `bg` colour floor with static `boxes` (drawbox specs), then each sprite
    (`color=...` source spec, x expression, y expression) overlaid in order."""
    args = ["-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:r={FPS}:d={num(seconds)}"]
    for src, _, _ in sprites:
        args += ["-f", "lavfi", "-i", f"{src}:r={FPS}:d={num(seconds)}"]
    chain = f"[0]{','.join(boxes) if boxes else 'null'}[s0]"
    for i, (_, x, y) in enumerate(sprites, 1):
        chain += f";[s{i - 1}][{i}]overlay=x='{x}':y='{y}':eval=frame[s{i}]"
    media.ffmpeg(*args, "-filter_complex", chain, "-map", f"[s{len(sprites)}]", "-r", FPS, "-pix_fmt", "yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", FPS, "-bf", "0", out)
    return out


# --- count: jumps of the red block -----------------------------------------------------------------------------
# (start s, height px). Uneven gaps, back-to-back doubles and two tiny 14 px hops: one tile a second misses some.
JUMPS = [(1.0, 90), (2.2, 90), (3.1, 40), (5.6, 90), (6.3, 14), (9.0, 90), (12.4, 90), (13.2, 40), (16.8, 90),
         (17.5, 14), (21.0, 90), (24.6, 40), (25.3, 90)]
JUMP_S = 0.64  # 16 frames in the air
DECOY_JUMPS = [4.0, 8.0, 11.0, 15.0, 19.5, 23.0]  # the grey block in the back: not counted
JUMP_VIDEO_S = 28.0
FLOOR_Y = 300


def hops(rest_y: int, starts: list[tuple[float, int]]) -> str:
    return windows(str(rest_y), [(a, a + JUMP_S, f"{rest_y}-{h}*4*((t-{num(a)})/{num(JUMP_S)})*"
                                                 f"(1-(t-{num(a)})/{num(JUMP_S)})") for a, h in starts])


def draw_jumps(out: Path) -> Path:
    floor = [f"drawbox=x=0:y={FLOOR_Y}:w={W}:h=4:c=white:t=fill", "drawbox=x=0:y=304:w=640:h=56:c=0x6b4a2f:t=fill"]
    return encode(out, JUMP_VIDEO_S, "0x30476b", floor, [
        ("color=c=0x8a8a8a:s=30x30", "470", hops(FLOOR_Y - 30, [(a, 60) for a in DECOY_JUMPS])),
        ("color=c=0xd0312d:s=40x40", "260", hops(FLOOR_Y - 40, JUMPS)),
    ])


# --- rate: arm strokes of a swimmer --------------------------------------------------------------------------------
STROKES_PER_MIN = 42.0  # the yellow arm block circles the body this many times a minute
KICKS_PER_MIN = 126.0   # the small grey kick block: a decoy at three times the stroke rate
SWIM_VIDEO_S = 30.0


def draw_swim(out: Path) -> Path:
    body_x = "40+15*t"
    lanes = [f"drawbox=x=0:y={y}:w={W}:h=3:c=0xf0f0f0:t=fill" for y in (90, 270)]
    w_arm = f"2*PI*{num(STROKES_PER_MIN / 60)}"
    w_kick = f"2*PI*{num(KICKS_PER_MIN / 60)}"
    return encode(out, SWIM_VIDEO_S, "0x1f6fa8", lanes, [
        ("color=c=0xe6e6e6:s=70x24", body_x, "168"),
        ("color=c=0x9a9a9a:s=14x10", f"{body_x}-16", f"175+7*sin({w_kick}*t)"),
        ("color=c=0xf2c522:s=16x16", f"{body_x}+27+46*cos({w_arm}*t+0.9)", f"172+46*sin({w_arm}*t+0.9)"),
    ])


# --- timestamps: the runner touches cones ------------------------------------------------------------------------
# (time s, block x px) keyframes, linear in between; a touch = the block arrives at a cone (then stops or turns).
CONE_X = {"left": 60, "middle": 305, "right": 540}
RUN = [(0.0, "left"), (1.0, "left"), (3.2, "right"), (3.6, "right"), (5.4, "middle"), (6.8, "right"),
       (7.6, "right"), (10.4, "left"), (11.0, "left"), (12.2, "middle"), (13.6, "middle"), (14.8, "right"),
       (15.2, "right"), (17.4, "left"), (20.0, "left")]
RUN_VIDEO_S = 20.0


def touches() -> list[float]:
    """Arrival times: a keyframe reached by moving (the previous keyframe was elsewhere)."""
    return [t for (_, a), (t, b) in zip(RUN, RUN[1:]) if a != b]


def draw_run(out: Path) -> Path:
    cones = ["drawbox=x=0:y=260:w=640:h=4:c=white:t=fill",
             "drawbox=x=40:y=232:w=20:h=28:c=0xff8c1a:t=fill", "drawbox=x=580:y=232:w=20:h=28:c=0xff8c1a:t=fill",
             "drawbox=x=310:y=246:w=20:h=14:c=0xff8c1a:t=fill"]
    parts = [(t0, t1, ramp(t0, t1, CONE_X[a], CONE_X[b])) for (t0, a), (t1, b) in zip(RUN, RUN[1:])]
    return encode(out, RUN_VIDEO_S, "0x2f6b3a", cones, [("color=c=0xd0312d:s=30x60", windows("60", parts), "200")])


# --- outcomes: shots at a hoop -----------------------------------------------------------------------------------
# Each shot: 1.2 s of flight from the shooter to a point at the rim, then 1.0 s after it. "made" drops through the
# net; "front" hits the front rim and comes back; "over" hits the back rim and bounces back over the rim and out;
# "short" falls in front of the rim.
SHOTS = ["made", "front", "made", "made", "over", "short", "made", "front", "made", "over"]
SHOT_GAP = 3.0
SHOT_FLIGHT, SHOT_AFTER = 1.2, 1.0
SHOOT_FROM = (90, 250)
RIM_Y, RIM_X0, RIM_X1 = 150, 500, 560
BALL = 16
SHOTS_VIDEO_S = 1.0 + SHOT_GAP * len(SHOTS)

# ball centre during the after-phase, v = 0..1: (x(v), y(v)) as expression strings in "v"
AFTER = {
    "made": ("530", f"{RIM_Y}+180*v"),
    "front": ("500-160*v", f"{RIM_Y}-80*v+260*v*v"),
    "over": ("558-200*v", f"{RIM_Y - 2}-200*v+380*v*v"),
    "short": ("472+18*v", "205+125*v"),
}
TARGET = {"made": (530, RIM_Y), "front": (500, RIM_Y), "over": (558, RIM_Y - 2), "short": (472, 205)}


def outcome(kind: str) -> str:
    return "made" if kind == "made" else "missed"


def draw_shots(out: Path) -> Path:
    hoop = [f"drawbox=x=0:y=330:w={W}:h=30:c=0x8b5a2b:t=fill",
            "drawbox=x=566:y=80:w=8:h=100:c=white:t=fill",                         # backboard
            "drawbox=x=574:y=120:w=66:h=6:c=0x777777:t=fill",                      # its pole arm
            f"drawbox=x={RIM_X0 + 4}:y={RIM_Y + 3}:w={RIM_X1 - RIM_X0 - 8}:h=30:c=0xdddddd:t=2",  # net
            f"drawbox=x={RIM_X0}:y={RIM_Y}:w={RIM_X1 - RIM_X0}:h=4:c=0xd02020:t=fill",            # rim
            "drawbox=x=70:y=250:w=30:h=80:c=0x3355cc:t=fill"]                       # shooter
    xs, ys = [], []
    for i, kind in enumerate(SHOTS):
        t0 = 1.0 + SHOT_GAP * i
        t1 = t0 + SHOT_FLIGHT
        (x0, y0), (x1, y1) = SHOOT_FROM, TARGET[kind]
        u = f"((t-{num(t0)})/{num(SHOT_FLIGHT)})"
        xs.append((t0, t1, f"{x0}+{x1 - x0}*{u}-{BALL // 2}"))
        ys.append((t0, t1, f"(1-{u})*{y0}+{u}*{y1}-170*4*{u}*(1-{u})-{BALL // 2}"))
        v = f"((t-{num(t1)})/{num(SHOT_AFTER)})"
        ax, ay = AFTER[kind]
        xs.append((t1, t1 + SHOT_AFTER, f"{ax.replace('v', v)}-{BALL // 2}"))
        ys.append((t1, t1 + SHOT_AFTER, f"{ay.replace('v', v)}-{BALL // 2}"))
    return encode(out, SHOTS_VIDEO_S, "0x23324a", hoop,
                  [(f"color=c=0xf08a24:s={BALL}x{BALL}", windows("-60", xs), windows("-60", ys))])


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    question: str        # what to measure (TASKS.md)
    answer_format: str   # how to write the answer
    seconds: float
    truth: object
    draw: Callable[[Path], Path]

    @property
    def video(self) -> str:
        return f"{self.id}.mp4"


TASKS = [
    Task("jump-count", "count",
         "Count the jumps of the big red block. A jump is any time the red block leaves the floor (the white line), "
         "however low. The grey block in the back is not counted.",
         "an integer, e.g. `5`", JUMP_VIDEO_S, len(JUMPS), draw_jumps),
    Task("stroke-rate", "rate",
         "A swimmer seen from above swims left to right: the white bar is the body, the yellow block is the arm. "
         "Measure the stroke rate: full circles of the yellow arm block per minute. The small grey block at the "
         "back is the kick, not a stroke.",
         "a number of strokes per minute, e.g. `30.5`", SWIM_VIDEO_S, STROKES_PER_MIN, draw_swim),
    Task("cone-touches", "timestamps",
         "A red block runs between three cones (two tall ones at the ends, a low one in the middle). Give the time "
         "of every cone touch: the moment the block arrives at a cone, where it then stops or turns back. Running "
         "past a cone without stopping or turning is not a touch.",
         "a list of seconds from the start of the video, in order, e.g. `[1.5, 4.25]`", RUN_VIDEO_S, touches(),
         draw_run),
    Task("shot-outcomes", "outcomes",
         f"A shooter (blue, left) takes {len(SHOTS)} shots at the hoop (red rim, grey net, white backboard). For "
         "each shot in order, say whether the ball went down through the rim (`made`) or not (`missed`).",
         f'a list of {len(SHOTS)} strings, each "made" or "missed", e.g. `["made", "missed", ...]`',
         SHOTS_VIDEO_S, [outcome(k) for k in SHOTS], draw_shots),
]
BY_ID = {t.id: t for t in TASKS}

assert all(t.kind in KINDS for t in TASKS) and len(BY_ID) == len(TASKS)
assert math.isclose(STROKES_PER_MIN * 3, KICKS_PER_MIN)
# the times a truth depends on fall on whole frames, so a frame-exact reading can match the truth exactly
assert all(abs(t * FPS - round(t * FPS)) < 1e-9 for t, _ in RUN)
