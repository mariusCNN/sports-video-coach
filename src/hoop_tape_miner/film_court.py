"""Basketball drawing for the film stage: track-resolved player marks on frozen frames and animated court diagrams
(matplotlib frames + an ffconcat list). The generic telestration (points, arrows, rings, labels) is in
sports_video_coach.film_draw; film_hooks plugs this module into the core film.

Player marks in a freeze line (`> 03:10 我#7 对#11 我#7->0.5,0.4 "alone"`):
    我#7 / us#7      our player 7, found in the CV tracks (run/tracks.pkl) at that moment
    对#11 / them#11    their player 11

Court diagrams (`![caption](court:plays/x.json)`): full-court metres, x 0-28 from the left baseline (we attack the
right basket, they attack the left one), y 0-15 from the top sideline on screen.
    {"view": "half" (the right half: our offence) | "left" (their offence, our defence) | "full",
     "us": {"1": [20, 7.5], ...}, "them": {"19": [22, 6], ...}, "ball": "us:1",
     "steps": [{"note": "...", "move": {"us:2": [25, 2]}, "dribble": {"us:1": [24, 7]},
                "pass": ["us:1", "us:2"], "shot": "us:2", "ring": ["them:19"], "ball": "them:25"}, ...]}
    (move: run without the ball; dribble: with it; ball: who has it now, e.g. a rebound)
Each narration paragraph starts the next step.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from sports_video_coach.film_draw import MARK_HEX

BALL_HEX = "#f08a24"
REF_RE = re.compile(r"^(我|us|对|them)#(\w+)$")
ANIM = 1.0  # seconds a court step takes to animate
BASKET = (26.425, 7.5)  # the basket we attack


def basket(key: str) -> tuple[float, float]:
    """The basket a player shoots at: ours on the right for us:N, theirs on the left for them:N."""
    return BASKET if key.startswith("us:") else (28 - BASKET[0], BASKET[1])


# ---- player marks ------------------------------------------------------------------------------------------------

def parse_ref(tok: str):
    """'我#7' / 'us#7' -> ('player', 'us', '7'); '对#11' / 'them#11' -> ('player', 'them', '11'); else None."""
    m = REF_RE.match(tok)
    return ("player", "us" if m[1] in ("我", "us") else "them", m[2]) if m else None


class Tracks:
    """Player boxes from the CV pass (run/tracks.pkl), as fractions of the source frame."""

    def __init__(self, df, src_w: int, src_h: int):
        self.df, self.w, self.h = df, src_w, src_h

    @classmethod
    def load(cls, run: Path, src_w: int, src_h: int) -> "Tracks":
        import pandas as pd

        df = pd.read_pickle(run / "tracks.pkl")
        return cls(df[df["number"].notna()][["t", "team", "number", "x1", "y1", "x2", "y2"]], src_w, src_h)

    def box(self, side: str, number: str, t: float, tol: float = 0.25):
        d = self.df
        s = d[(d["team"] == side) & (d["number"].astype(str) == str(number)) & ((d["t"] - t).abs() <= tol)]
        if s.empty:
            return None
        r = s.iloc[(s["t"] - t).abs().argmin()]
        return r.x1 / self.w, r.y1 / self.h, r.x2 / self.w, r.y2 / self.h

    def locate(self, mark, t: float):
        """A ('player', side, number) mark -> its box at t (film_draw.mark_box asks this), or None."""
        return self.box(mark[1], mark[2], t) if mark[0] == "player" else None


# ---- court diagrams ----------------------------------------------------------------------------------------------

def load_play(path: Path) -> dict:
    play = json.loads(path.read_text(encoding="utf8"))
    for side in ("us", "them"):
        play[side] = {str(k): tuple(v) for k, v in (play.get(side) or {}).items()}
    play.setdefault("steps", [])
    return play


def play_problems(play: dict) -> list[str]:
    known = {f"us:{k}" for k in play["us"]} | {f"them:{k}" for k in play["them"]}
    out = []
    if play.get("ball") and play["ball"] not in known:
        out.append(f"ball holder {play['ball']} is not a player")
    for i, st in enumerate(play["steps"], 1):
        refs = [*(st.get("move") or {}), *(st.get("dribble") or {}), *(st.get("pass") or []), *(st.get("ring") or [])]
        refs += [st[k] for k in ("shot", "ball") if st.get(k)]
        out += [f"step {i}: unknown player {r} (use us:N or them:N)" for r in refs if r not in known]
    return out


def play_states(play: dict) -> list[dict]:
    """Positions and ball holder before step 1 and after each step."""
    pos = {f"us:{k}": v for k, v in play["us"].items()} | {f"them:{k}": v for k, v in play["them"].items()}
    ball = play.get("ball")
    states = [{"pos": dict(pos), "ball": ball}]
    for st in play["steps"]:
        pos = dict(pos)
        for k, v in {**(st.get("move") or {}), **(st.get("dribble") or {})}.items():
            pos[k] = tuple(v)
        if st.get("pass"):
            ball = st["pass"][-1]
        if st.get("shot"):
            ball = "basket:" + st["shot"]
        if st.get("ball"):
            ball = st["ball"]
        states.append({"pos": pos, "ball": ball})
    return states


def _court_lines(ax, view: str):
    from matplotlib.patches import Arc, Circle, Rectangle

    kw = dict(color="white", lw=2, alpha=0.85, fill=False)
    ax.add_patch(Rectangle((14 if view == "half" else 0, 0), 28 if view == "full" else 14, 15, **kw))
    ax.plot([14, 14], [0, 15], color="white", lw=2, alpha=0.85)
    if view == "full":
        ax.add_patch(Circle((14, 7.5), 1.8, **kw))
    else:  # only the half that is on this side of the half-court line
        th = (-90, 90) if view == "half" else (90, 270)
        ax.add_patch(Arc((14, 7.5), 3.6, 3.6, theta1=th[0], theta2=th[1], color="white", lw=2, alpha=0.85))
    a = math.degrees(math.asin(6.6 / 6.75))
    for mirror in {"full": (False, True), "left": (True,)}.get(view, (False,)):
        def X(x):
            return 28 - x if mirror else x
        bx = X(BASKET[0])
        ax.add_patch(Rectangle((min(X(22.2), X(28)), 7.5 - 2.45), 5.8, 4.9, **kw))
        ax.add_patch(Circle((X(22.2), 7.5), 1.8, **kw))
        th1, th2 = (180 - a, 180 + a) if not mirror else (-a, a)
        ax.add_patch(Arc((bx, 7.5), 13.5, 13.5, theta1=th1, theta2=th2, color="white", lw=2, alpha=0.85))
        ax.add_patch(Arc((bx, 7.5), 2.5, 2.5, theta1=90 if not mirror else -90, theta2=270 if not mirror else 90,
                         color="white", lw=1.5, alpha=0.6))
        for y in (0.9, 14.1):
            ax.plot([X(28), X(25.01)], [y, y], color="white", lw=2, alpha=0.85)
        ax.plot([X(26.8), X(26.8)], [6.6, 8.4], color="white", lw=3)
        ax.add_patch(Circle((bx, 7.5), 0.3, color=BALL_HEX, lw=2, fill=False))


def _ease(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def render_court(play: dict, w: int, h: int, starts: list[float], length: float, out_dir: Path, us_hex: str,
                 them_hex: str, fps: int = 30) -> Path:
    """Animated diagram frames + an ffconcat list (returned). Step k starts at starts[k] (scene seconds)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch

    states = play_states(play)
    n = len(play["steps"])
    starts = list(starts[:n])
    while len(starts) < n:  # more steps than paragraphs: the rest follow every few seconds
        starts.append((starts[-1] if starts else 0.5) + 2.5)
    view = play.get("view", "half")
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor="#14161f")
    top, bottom = 0.11, 0.15  # same area as charts: clear of the banner and the subtitles
    xr = {"full": (0, 28), "left": (0, 14)}.get(view, (14, 28))
    ax = fig.add_axes((0.02, bottom, 0.96, 1 - top - bottom))
    ax.set_xlim(xr[0] - 0.6, xr[1] + 0.6)
    ax.set_ylim(15.6, -0.6)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.add_patch(matplotlib.patches.Rectangle((xr[0], 0), xr[1] - xr[0], 15, color="#22283a", zorder=0))
    _court_lines(ax, view)
    r = 0.55
    tokens, labels = {}, {}
    for key in states[0]["pos"]:
        side, num = key.split(":", 1)
        c = Circle((0, 0), r, facecolor=us_hex if side == "us" else "#14161f", edgecolor="white" if side == "us"
                   else them_hex, lw=2.5, zorder=5)
        ax.add_patch(c)
        tokens[key] = c
        labels[key] = ax.text(0, 0, num, color="white" if side == "us" else them_hex, ha="center", va="center",
                              fontsize=h / 720 * 13, fontweight="bold", zorder=6)
    ball = Circle((0, 0), 0.28, color=BALL_HEX, zorder=7)
    ax.add_patch(ball)
    rings = []
    arrows: list = []

    def place(pos, holder, ball_xy=None):
        for k, (x, y) in pos.items():
            tokens[k].center = (x, y)
            labels[k].set_position((x, y))
        if ball_xy is None and holder in pos:
            hx, hy = pos[holder]
            ball_xy = (hx + 0.45, hy + 0.45)
        if ball_xy is None and holder and holder.startswith("basket:"):
            ball_xy = basket(holder[7:])
        ball.set_visible(ball_xy is not None)
        if ball_xy is not None:
            ball.center = ball_xy

    def draw_arrows(st, a, b, u):
        for art in arrows:
            art.remove()
        arrows.clear()
        segs = [(k, "move") for k in (st.get("move") or {})] + [(k, "dribble") for k in (st.get("dribble") or {})]
        for k, kind in segs:
            p, q = a["pos"][k], b["pos"][k]
            cur = (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
            if math.hypot(q[0] - p[0], q[1] - p[1]) < 0.8 or math.hypot(cur[0] - p[0], cur[1] - p[1]) < 0.3:
                continue  # a short shuffle: an arrow would hide behind the dot
            ours = k.startswith("us:")
            col = us_hex if ours else them_hex
            # our runs white, theirs in their colour and thinner; dribbles curve
            style = dict(arrowstyle="-|>,head_length=0.6,head_width=0.35", lw=3 if ours or kind == "dribble" else 2,
                         color="white" if kind == "move" and ours else col, alpha=1 if ours else 0.8,
                         mutation_scale=20, zorder=3, shrinkA=0, shrinkB=r * 20)
            if kind == "dribble":
                style["connectionstyle"] = "arc3,rad=0.15"
            arrows.append(ax.add_patch(FancyArrowPatch(p, cur, **style)))
        if st.get("pass"):
            p = b["pos"][st["pass"][0]] if st["pass"][0] in b["pos"] else a["pos"][st["pass"][0]]
            q = b["pos"][st["pass"][-1]]
            cur = (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
            arrows.append(ax.add_patch(FancyArrowPatch(p, cur, arrowstyle="-|>,head_length=0.6,head_width=0.35",
                                                       lw=2.5, ls=(0, (4, 3)), color=BALL_HEX, mutation_scale=20,
                                                       zorder=3, shrinkB=r * 20)))
        if st.get("shot"):
            p = b["pos"][st["shot"]]
            b0 = basket(st["shot"])
            cur = (p[0] + (b0[0] - p[0]) * u, p[1] + (b0[1] - p[1]) * u)
            arrows.append(ax.add_patch(FancyArrowPatch(p, cur, arrowstyle="-|>,head_length=0.6,head_width=0.35",
                                                       lw=2.5, ls=(0, (2, 3)), color=BALL_HEX, mutation_scale=20,
                                                       zorder=3, shrinkB=14, connectionstyle="arc3,rad=-0.2")))

    def set_rings(st, positions):
        for art in rings:
            art.remove()
        rings.clear()
        for k in st.get("ring") or []:
            rings.append(ax.add_patch(Circle(positions[k], r * 1.9, fill=False, edgecolor=MARK_HEX, lw=3, zorder=4)))

    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, float]] = []
    idx = 0

    def snap(dur: float):
        nonlocal idx
        name = f"c{idx:05d}.png"
        fig.savefig(out_dir / name, dpi=100, facecolor=fig.get_facecolor())
        entries.append((name, max(dur, 1 / fps)))
        idx += 1

    place(states[0]["pos"], states[0]["ball"])
    snap(starts[0] if n else length)
    frames = max(1, round(ANIM * fps))
    for k, st in enumerate(play["steps"]):
        a, b = states[k], states[k + 1]
        nxt = starts[k + 1] if k + 1 < n else length
        span = max(1 / fps, min(ANIM, nxt - starts[k]))
        m = max(1, min(frames, round(span * fps)))
        set_rings(st, b["pos"])
        for f in range(1, m + 1):
            u = _ease(f / m)
            pos = {key: (pa[0] + (b["pos"][key][0] - pa[0]) * u, pa[1] + (b["pos"][key][1] - pa[1]) * u)
                   for key, pa in a["pos"].items()}
            ball_xy = None
            if st.get("pass"):
                p0 = pos[st["pass"][0]]
                q0 = pos[st["pass"][-1]]
                ball_xy = (p0[0] + (q0[0] - p0[0]) * u + 0.45, p0[1] + (q0[1] - p0[1]) * u + 0.45)
            elif st.get("shot"):
                p0 = pos[st["shot"]]
                b0 = basket(st["shot"])
                ball_xy = (p0[0] + (b0[0] - p0[0]) * u, p0[1] + (b0[1] - p0[1]) * u)
            holder = (st.get("ball") or a["ball"]) if ball_xy is None else None
            place(pos, holder, ball_xy)
            for art, key in zip(rings, st.get("ring") or []):
                art.center = pos[key]
            draw_arrows(st, a, b, u)
            last = f == m
            snap(max(nxt - starts[k] - (m - 1) / fps, 1 / fps) if last else 1 / fps)
    plt.close(fig)
    lst = out_dir / "court.ffconcat"
    body = "ffconcat version 1.0\n" + "".join(f"file '{nm}'\nduration {d:.4f}\n" for nm, d in entries)
    lst.write_text(body + f"file '{entries[-1][0]}'\n", encoding="utf8")
    return lst
