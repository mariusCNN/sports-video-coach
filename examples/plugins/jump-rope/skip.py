"""Stage `skip <video> --out <folder>`: jump-rope skips counted from a still side view -> <folder>/skip.json.

How: each frame shrunk to grey 160 px wide; the moving pixels (far from the median frame) give the jumper's height
per frame; a skip is one rise and fall of that height, counted with hysteresis so noise is not a skip.
Plain OpenCV and NumPy: no GPU, no model download.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from sports_video_coach import media

WIDTH = 160


def heights(video: str) -> tuple[np.ndarray, float]:
    """(height of the moving mass per frame, higher = up; fps)."""
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    ok, img = cap.read()
    while ok:
        h = round(img.shape[0] * WIDTH / img.shape[1])
        frames.append(cv2.cvtColor(cv2.resize(img, (WIDTH, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY))
        ok, img = cap.read()
    cap.release()
    if not frames:
        raise SystemExit(f"{video}: no frames read")
    stack = np.stack(frames).astype(np.float32)
    background = np.median(stack, axis=0)
    rows = np.arange(stack.shape[1], dtype=np.float32)[:, None]
    ys = []
    for f in stack:
        moving = np.abs(f - background) > 25
        ys.append(-(rows * moving).sum() / moving.sum() if moving.any() else np.nan)
    y = np.array(ys)
    if np.isnan(y).all():
        return np.zeros(len(y)), fps
    y = np.where(np.isnan(y), np.nanmean(y), y)
    return y, fps


def count_skips(y: np.ndarray, fps: float) -> dict:
    """Skips = rises above the upper band after a fall below the lower band (bands at 30 % / 70 % of the range)."""
    lo, hi = np.percentile(y, 5), np.percentile(y, 95)
    if hi - lo < 1:
        return {"skips": 0, "skips_per_min": 0.0, "at_s": []}
    low, high = lo + 0.3 * (hi - lo), lo + 0.7 * (hi - lo)
    at, armed = [], y[0] < high
    for i, v in enumerate(y):
        if armed and v > high:
            at.append(round(i / fps, 2))
            armed = False
        elif not armed and v < low:
            armed = True
    dur = len(y) / fps
    return {"skips": len(at), "skips_per_min": round(len(at) * 60 / dur, 1), "at_s": at}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach jump-rope:skip")
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    y, fps = heights(a.video)
    result = {"video": Path(a.video).name, "duration_s": round(len(y) / fps, 2), **count_skips(y, fps)}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    media.write_text_atomic(out / "skip.json", json.dumps(result, indent=1) + "\n")
    print(f"{result['skips']} skips ({result['skips_per_min']}/min) -> {(out / 'skip.json').as_posix()}")


if __name__ == "__main__":
    main()
