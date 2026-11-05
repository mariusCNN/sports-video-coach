"""Stage `pose <folder> [--set S01] [--force] [--fps 60]`: the lifter's 2D pose in every set's window.

Reads run/review/sets.json; for each set filmed from the side, oblique or front, runs YOLO pose (ultralytics,
yolo11s-pose; weights cached under ~/.cache/sports-video-coach) on the set's window of its *source* video (a joined
unit maps its timeline back through analysis.json `sources`, so the native frame rate is kept, capped at --fps),
follows one person (the agent's `who` box at the set start if given, else the largest person, then the box that
overlaps the last one most) and writes run/pose/<id>.npz: t (source s), kp (N,17,2), conf (N,17), box (N,4).
Without ultralytics it says so and writes nothing; the review then covers those sets from the frames alone.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

WEIGHTS = Path.home() / ".cache" / "sports-video-coach"
POSE_MODEL = "yolo11s-pose.pt"
MEASURED_VIEWS = ("side", "oblique", "front")
BATCH = 16


def source_window(g, start: float, end: float) -> tuple[Path, float, float]:
    """(file, t0, t1) in the source video for a window on the unit's timeline."""
    from sports_video_coach import media
    srcs = media.joined(g.game.get("sources"))
    if not srcs:
        return g.video, start, end
    s = next((s for s in reversed(srcs) if s["start"] <= start + 1e-6), srcs[0])
    return Path(s["file"]), start - s["start"], min(end, s["start"] + s["duration"]) - s["start"]


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return float(inter / area) if area > 0 else 0.0


def pick(boxes: list[np.ndarray], last: np.ndarray | None, who: np.ndarray | None) -> int | None:
    """Index of the lifter among this frame's boxes: most overlap with the last pick (or the `who` box), else the
    largest box."""
    if not boxes:
        return None
    ref = last if last is not None else who
    if ref is not None:
        ov = [iou(b, ref) for b in boxes]
        if max(ov) > 0.2:
            return int(np.argmax(ov))
    return int(np.argmax([(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]))


def scan(video: Path, t0: float, t1: float, fps_cap: float, who: list | None = None) -> dict:
    import cv2
    from ultralytics import YOLO
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(WEIGHTS / POSE_MODEL))
    cap = cv2.VideoCapture(str(video))
    native = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(native / fps_cap)))
    cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000)
    ts, frames, out = [], [], dict(t=[], kp=[], conf=[], box=[])
    last, whob = None, (np.array(who, float) if who else None)

    def flush():
        nonlocal last
        if not frames:
            return
        for t, r in zip(ts, model(frames, verbose=False)):
            boxes = [b for b in r.boxes.xyxy.cpu().numpy()] if r.boxes is not None else []
            i = pick(boxes, last, whob)
            if i is None:
                out["t"].append(t); out["kp"].append(np.full((17, 2), np.nan)); out["conf"].append(np.zeros(17))
                out["box"].append(np.full(4, np.nan))
                continue
            last = boxes[i]
            out["t"].append(t); out["kp"].append(r.keypoints.xy.cpu().numpy()[i])
            out["conf"].append(r.keypoints.conf.cpu().numpy()[i]); out["box"].append(boxes[i])
        ts.clear(); frames.clear()

    k = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if t > t1:
            break
        if k % step == 0 and t >= t0 - 1e-3:
            ts.append(round(t, 4)); frames.append(img)
            if len(frames) >= BATCH:
                flush()
        k += 1
    flush()
    cap.release()
    return {k: np.array(v, float) for k, v in out.items()}


def main(argv=None):
    from sports_video_coach.timefmt import seconds
    from .unit import Session, load_sets
    ap = argparse.ArgumentParser(prog="sports-video-coach fitness:pose", description=__doc__.split("\n\n")[0])
    ap.add_argument("folder")
    ap.add_argument("--set", action="append", help="only this set id (repeatable)")
    ap.add_argument("--force", action="store_true", help="scan again even when run/pose/<id>.npz exists")
    ap.add_argument("--fps", type=float, default=60.0, help="frames per second to scan at most (default 60)")
    a = ap.parse_args(argv)
    g = Session.load(Path(a.folder))
    out = g.run / "pose"
    out.mkdir(parents=True, exist_ok=True)
    todo = [s for s in load_sets(g) if s.get("view") in MEASURED_VIEWS and (not a.set or s["id"] in a.set)]
    if importlib.util.find_spec("ultralytics") is None:
        print("[pose] ultralytics is not installed: no pose measurements (install the basketball extra, "
              "`uv sync` in a clone); the review covers the sets from the frames")
        (out / "status.json").write_text(json.dumps({"pose": None, "reason": "ultralytics missing"}) + "\n",
                                         encoding="utf8")
        return
    for s in todo:
        p = out / f"{s['id']}.npz"
        if p.exists() and not a.force:
            continue
        video, t0, t1 = source_window(g, seconds(s["start"]), seconds(s["end"]))
        d = scan(video, t0, t1, a.fps, s.get("who"))
        np.savez_compressed(p, **d, source=str(video))
        seen = int(np.isfinite(d["kp"][:, 11, 0]).sum()) if len(d["t"]) else 0
        print(f"[pose] {s['id']}: {len(d['t'])} frames from {video.name} {t0:.1f}-{t1:.1f} s, lifter seen in {seen}")
    (out / "status.json").write_text(json.dumps({"pose": "yolo11s-pose", "sets": [s["id"] for s in todo]}) + "\n",
                                     encoding="utf8")


if __name__ == "__main__":
    main()
