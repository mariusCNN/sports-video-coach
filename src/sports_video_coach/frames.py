"""Contact sheets of a video for an agent to review: one tile every N seconds, each labelled with its video time.

usage: sports-video-coach frames <video> --out <folder>/run/frames [--every 2] [--cols 4] [--rows 3] [--width 480]
           [--start mm:ss.s --end mm:ss.s]

Writes `sheet_NNN.jpg` (cols x rows tiles, in time order) and `frames.json`:
  {"video", "duration_s", "every_s", "sheets": [{"file", "start", "end", "tiles": ["mm:ss", ...]}]}
Labels are mm:ss, or mm:ss.s when tiles are under a second apart (then they fall on whole tenths).
An agent opens the sheets in order, notes what happens and when, then cuts closer looks with `clips`. Sheets that
already exist for the same settings are kept (frames.json `every_s`, `cols`, `rows`, `width` and the video size).
A close look at one moment: `--start 0:12 --end 0:14 --every 0.1 --out run/frames-zoom` (tenths in the labels).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from . import media
from .timefmt import mmss, seconds


def times(duration: float, every: float, start: float = 0.0) -> list[float]:
    """Tile times every `every` seconds before `duration`: from `start` (a window), else from every/2 (skips the
    black first frame). Under a second apart they fall on whole tenths, so the labels are exact."""
    t0 = start if start > 0 else every / 2
    if every < 1:
        t0 = math.ceil(round(t0 * 10, 6)) / 10
    out, k = [], 0
    while (t := round(t0 + k * every, 2)) < duration:
        out.append(t)
        k += 1
    return out


def sheets(ts: list[float], per: int) -> list[list[float]]:
    return [ts[i:i + per] for i in range(0, len(ts), per)]


def tile(frame, label: str, width: int):
    import cv2
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (width, max(2, round(h * width / w))))
    cv2.rectangle(frame, (0, 0), (92, 30), (0, 0, 0), -1)
    cv2.putText(frame, label, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    return frame


def build(video: Path, out: Path, every: float = 2.0, cols: int = 4, rows: int = 3, width: int = 480,
          start: float | None = None, end: float | None = None) -> dict:
    """Write the sheets and frames.json into `out` (only `start`-`end` seconds when given); returns its data."""
    import cv2
    import numpy as np
    duration = media.duration_s(video)
    settings = dict(every_s=every, cols=cols, rows=rows, width=width, size=list(media.video_size(video)))
    if start is not None or end is not None:  # a window; whole-video sheets keep their old settings keys
        settings.update(start_s=start or 0.0, end_s=end)
    index = out / "frames.json"
    if index.exists():
        old = json.loads(index.read_text(encoding="utf8"))
        if {k: old.get(k) for k in settings} == settings and all((out / s["file"]).exists() for s in old["sheets"]):
            print(f"frames: up to date ({len(old['sheets'])} sheets in {out})")
            return old
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    data = dict(video=str(video), duration_s=round(duration, 2), **settings, sheets=[])
    dec = 1 if every < 1 else 0  # label 0:12.5 when tiles are under a second apart
    stop = min(duration, end) if end is not None else duration
    for i, group in enumerate(sheets(times(stop, every, start or 0.0), cols * rows), 1):
        tiles = []
        for t in group:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            tiles.append((t, tile(frame, mmss(t, dec), width)))
        if not tiles:
            continue
        th = max(f.shape[0] for _, f in tiles)
        blank = np.zeros((th, width, 3), np.uint8)
        cells = [cv2.copyMakeBorder(f, 0, th - f.shape[0], 0, 0, cv2.BORDER_CONSTANT) for _, f in tiles]
        cells += [blank] * (cols * rows - len(cells))
        grid = np.vstack([np.hstack(cells[r * cols:(r + 1) * cols]) for r in range(rows)])
        name = f"sheet_{i:03d}.jpg"
        cv2.imwrite(str(out / name), grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
        data["sheets"].append(dict(file=name, start=mmss(tiles[0][0], dec), end=mmss(tiles[-1][0], dec),
                                   tiles=[mmss(t, dec) for t, _ in tiles]))
    cap.release()
    media.write_json_atomic(index, data, indent=1)
    print(f"frames: {len(data['sheets'])} sheets ({every:g} s per tile) in {out}")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach frames", description=__doc__.split("\n\n")[0])
    ap.add_argument("video")
    ap.add_argument("--out", required=True, help="folder for the sheets and frames.json")
    ap.add_argument("--every", type=float, default=2.0, help="seconds between tiles (default 2)")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--width", type=int, default=480, help="tile width in pixels (default 480)")
    ap.add_argument("--start", type=seconds, help="only from this video time (mm:ss.s or seconds)")
    ap.add_argument("--end", type=seconds, help="only up to this video time")
    a = ap.parse_args(argv)
    video = Path(a.video)
    if not video.is_file():
        raise SystemExit(f"video not found: {video}")
    if a.start is not None and a.end is not None and a.end <= a.start:
        raise SystemExit("--end must be after --start")
    if a.every <= 0:
        raise SystemExit("--every must be above 0")
    if a.every < 1 and abs(a.every * 10 - round(a.every * 10)) > 1e-6:  # labels and clip times are in tenths
        snapped = max(0.1, round(a.every, 1))
        print(f"frames: --every {a.every:g} -> {snapped:g} (tiles are labelled in tenths of a second, as clip times are)")
        a.every = snapped
    build(video, Path(a.out), a.every, a.cols, a.rows, a.width, a.start, a.end)


if __name__ == "__main__":
    main()
