"""2D tactics-board replay of a possession from CV tracks (NBA-Player-Movements style).

Renders player dots (team colour, jersey number when known) with short trails on a
top-down FIBA court, plus the ball when the detector saw it, to an MP4/GIF.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .court import LENGTH, WIDTH, court_polylines, hoop_xy, project
from .game_config import hex_to_bgr, load_game, team_hex

PX_PER_M = 36
PAD = 1.0
BGR = {"us": hex_to_bgr(team_hex({}, "us")), "them": hex_to_bgr(team_hex({}, "them")), "ref": (140, 140, 140)}


def use_game(game: dict):
    """Dot colours from game.json us.hex / them.hex (neutral defaults when missing)."""
    for side in ("us", "them"):
        BGR[side] = hex_to_bgr(team_hex(game, side))
SURFACE = (251, 252, 252)


def to_px(x, y):
    return int((x + PAD) * PX_PER_M), int((y + PAD) * PX_PER_M)


def court_image():
    w, h = int((LENGTH + 2 * PAD) * PX_PER_M), int((WIDTH + 2 * PAD) * PX_PER_M)
    img = np.full((h, w, 3), SURFACE, np.uint8)
    for pl in court_polylines():
        pts = np.array([to_px(x, y) for x, y in pl], np.int32)
        cv2.polylines(img, [pts], False, (150, 150, 150), 2, cv2.LINE_AA)
    for side in ("left", "right"):
        cv2.circle(img, to_px(*hoop_xy(side)), 8, (60, 60, 60), 2, cv2.LINE_AA)
    return img


def ball_positions(det: pd.DataFrame, cam) -> pd.DataFrame:
    """Project ball detections to the floor (approximate: ball in the air lands long)."""
    H = {int(f): h for f, h in zip(cam["frame"], cam["H"]) if np.isfinite(h).all()}
    rows = []
    for _, r in det[det.kind == "ball"].iterrows():
        if int(r.frame) in H:
            c = project(np.linalg.inv(H[int(r.frame)]), np.array([[(r.x1 + r.x2) / 2, r.y2]]))[0]
            rows.append((int(r.frame), r.t, c[0], c[1], r.conf))
    return pd.DataFrame(rows, columns=["frame", "t", "bx", "by", "conf"])


def render(tracks: pd.DataFrame, ball: pd.DataFrame, t0: float, t1: float, out: Path, fps=10, trail=8,
           title="", events=()):
    base = court_image()
    h, w = base.shape[:2]
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h + 40))
    seg = tracks[(tracks.t >= t0) & (tracks.t <= t1)]
    frames = sorted(seg.frame.unique())
    hist: dict[int, list] = {}
    for fi in frames:
        g = seg[seg.frame == fi]
        img = base.copy()
        for _, r in g.iterrows():
            if r.team not in BGR or not np.isfinite(r.cx_s):
                continue
            p = to_px(r.cx_s, r.cy_s)
            hist.setdefault(int(r.track), []).append(p)
            hist[int(r.track)] = hist[int(r.track)][-trail:]
            pts = hist[int(r.track)]
            for i in range(1, len(pts)):
                cv2.line(img, pts[i - 1], pts[i], BGR[r.team], 2, cv2.LINE_AA)
            cv2.circle(img, p, 11, BGR[r.team], -1, cv2.LINE_AA)
            cv2.circle(img, p, 11, (255, 255, 255), 1, cv2.LINE_AA)
            n = r.number if isinstance(r.number, str) else ""
            if n:
                cv2.putText(img, n, (p[0] - 8 * len(n), p[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        b = ball[(ball.frame - fi).abs() <= 3]
        if len(b):
            r = b.iloc[(b.frame - fi).abs().argmin()]
            if -PAD < r.bx < LENGTH + PAD and -PAD < r.by < WIDTH + PAD:
                cv2.circle(img, to_px(r.bx, r.by), 6, (0, 120, 255), -1, cv2.LINE_AA)
        bar = np.full((40, w, 3), (30, 30, 30), np.uint8)
        t = float(g.t.iloc[0])
        txt = f"{title}  {int(t // 60):02d}:{t % 60:04.1f}"
        for et, etxt in events:
            if abs(et - t) < 2.5:
                txt += f"   << {etxt}"
        cv2.putText(bar, txt, (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        writer.write(np.vstack([img, bar]))
    writer.release()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pid", type=int, action="append", help="possession id(s) to render")
    ap.add_argument("--t0", type=float)
    ap.add_argument("--t1", type=float)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--game", help="game.json (team colours); default: neutral colours")
    args = ap.parse_args(argv)
    use_game(load_game(args.game))
    run, out = Path(args.run), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tracks = pd.read_pickle(run / "tracks.pkl")
    det = pd.read_pickle(run / "detections.pkl")
    cam = np.load(run / "camera.npz")
    ball = ball_positions(det, cam)
    jobs = []
    if args.pid:
        poss = pd.read_pickle(run / "possessions.pkl")
        for pid in args.pid:
            p = poss.loc[pid]
            jobs.append((p.start - 1, p.end + 2, out / f"p{pid:03d}.mp4", f"P{pid:03d} {p.offence} offence"))
    if args.t0 is not None:
        jobs.append((args.t0, args.t1, out / f"t{int(args.t0)}_{int(args.t1)}.mp4", "replay"))
    for t0, t1, path, title in jobs:
        render(tracks, ball, t0, t1, path, fps=args.fps, title=title)
        print("wrote", path)


if __name__ == "__main__":
    main()
