"""Contact sheets of a video for an agent to review: one tile every N seconds, each labelled with its video time.

usage: sports-video-coach frames <video> --out <folder>/run/frames [--every 2] [--cols 4] [--rows 3] [--width 480]
           [--start mm:ss.s --end mm:ss.s]

Writes `sheet_NNN.jpg` (cols x rows tiles from 0:00, in time order, split by a thin dark gap; each tile is one
whole frame, so x,y fractions read off a tile are fractions of the frame, as `film` freeze marks take them) and
`frames.json`:
  {"video", "duration_s", "every_s", "sheets": [{"file", "start", "end", "tiles": ["mm:ss", ...]}]}
When the video joins several files (the unit json's `sources`), frames.json lists them as `parts` (file, start,
end on the joined timeline), the first tile of each later file is labelled "part N/M" and every label also names
the file and the time in it ("00:42.5  side.mp4 00:17.5").
Each label sits bottom left (clear of a clock or score burned in top left) and is the video time of the frame
shown: mm:ss when every tile falls on a whole second, else mm:ss.s (tiles under a second apart fall on whole
tenths).
An agent opens the sheets in order, notes what happens and when, then cuts closer looks with `clips`. Sheets that
already exist for the same settings are kept (frames.json `every_s`, `cols`, `rows`, `width`, `labels`, `gap_px`,
`label_at` and the video size).
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
    """Tile times every `every` seconds before `duration`: from `start` (a window), else from 0:00 (the first frame
    is a tile too: a serve or a start can happen there). A window off the second with a gap under a whole second
    starts on the next whole tenth, so the labels are exact."""
    t0 = start
    if not float(every).is_integer():
        t0 = math.ceil(round(t0 * 10, 6)) / 10
    out, k = [], 0
    while (t := round(t0 + k * every, 2)) < duration:
        out.append(t)
        k += 1
    return out


def shown_at(cap, t: float) -> float:
    """Video time of the frame just read (a seek lands on the first frame at or after `t`); `t` if the reader's
    position is missing or far off."""
    import cv2
    got = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
    return round(got, 3) if abs(got - t) < 1 else t  # 0.99999 would read 00:00


def labels(ts: list[float]) -> int:
    """Decimals of the tile labels: 0 when every tile time is a whole second, else 1 (mm:ss.s)."""
    return 0 if all(float(t).is_integer() for t in ts) else 1


GAP, GAP_BGR = 3, (40, 40, 40)  # a thin dark line between tiles, so tile edges show on a uniform court
LABEL_H = 30                     # the time label: a black strip this high at a tile's bottom left


def tile_origin(n: int, cols: int, width: int, th: int) -> tuple[int, int]:
    """Top left pixel (x, y) of tile `n` (0-based, row by row) on a sheet of `width` x `th` tiles split by GAP."""
    r, c = divmod(n, cols)
    return c * (width + GAP), r * (th + GAP)


def sheets(ts: list[float], per: int) -> list[list[float]]:
    return [ts[i:i + per] for i in range(0, len(ts), per)]


def tile(frame, label: str, width: int, part: str = ""):
    """The frame scaled to `width`, its time label bottom left (the top left often holds a clock or score burned
    into the video); `part` ("part 2/2") marks where a new file starts."""
    import cv2
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (width, max(2, round(h * width / w))))
    y = frame.shape[0] - LABEL_H
    w_label = 12 + cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0][0]
    cv2.rectangle(frame, (0, y), (w_label, y + LABEL_H), (0, 0, 0), -1)
    cv2.putText(frame, label, (6, y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    if part:
        x = w_label + 4
        cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), (0, 212, 255), 4)
        cv2.rectangle(frame, (x, y), (x + 14 * len(part), y + LABEL_H), (0, 212, 255), -1)
        cv2.putText(frame, part, (x + 6, y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2, cv2.LINE_AA)
    return frame


def part_starts(ts: list[float], sources: list[dict] | None) -> dict[float, str]:
    """{tile time: "part N/M"} for the first tile of each joined file after the first."""
    out = {}
    for n, s in enumerate(sources or [], 1):
        if n > 1:
            t = next((t for t in ts if t >= s["start"]), None)
            if t is not None and t not in out:
                out[t] = f"part {n}/{len(sources)}"
    return out


def unit_sources(video: Path) -> list[dict] | None:
    """The `sources` of the unit whose joined video this is (its json in the video's folder), else None."""
    from . import units
    u = units.load(video.parent) if video.parent.is_dir() else {}
    v = u.get("video")
    if len(u.get("sources") or []) > 1 and v and Path(v).name == video.name:
        return u["sources"]
    return None


def build(video: Path, out: Path, every: float = 2.0, cols: int = 4, rows: int = 3, width: int = 480,
          start: float | None = None, end: float | None = None, sources: list[dict] | None = None) -> dict:
    """Write the sheets and frames.json into `out` (only `start`-`end` seconds when given); `sources` (the joined
    files, from media.join) marks where each starts. Returns the frames.json data."""
    import cv2
    import numpy as np
    duration = media.duration_s(video)
    settings = dict(every_s=every, cols=cols, rows=rows, width=width, labels="frame",  # labels: shown frame's time
                    gap_px=GAP, label_at="bottom-left", size=list(media.video_size(video)))
    if start is not None or end is not None:  # a window; whole-video sheets keep their old settings keys
        settings.update(start_s=start or 0.0, end_s=end)
    if sources:
        settings["labels"] = "frame+file"  # the joined time, then the file and the time in that file
        settings["parts"] = [dict(file=Path(s["file"]).name, start=mmss(s["start"], 1),
                                  end=mmss(s["start"] + s["duration"], 1)) for s in sources]
    index = out / "frames.json"
    if index.exists():
        old = json.loads(index.read_text(encoding="utf8"))
        if {k: old.get(k) for k in settings} == settings and all((out / s["file"]).exists() for s in old["sheets"]):
            print(f"frames: up to date ({len(old['sheets'])} sheets in {out.as_posix()})")
            return old
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    data = dict(video=str(video), duration_s=round(duration, 2), **settings, sheets=[])
    stop = min(duration, end) if end is not None else duration
    ts = times(stop, every, start or 0.0)
    dec = labels(ts)  # 0:12.5 unless every tile is on a whole second
    marks = part_starts(ts, sources)
    local = dec if all(float(x["start"]).is_integer() for x in sources or []) else 1  # a file starting off the second

    def label(t: float) -> str:
        return mmss(t, dec) + (f"  {media.source_at(sources, t, local, 14)}" if sources else "")
    for i, group in enumerate(sheets(ts, cols * rows), 1):
        tiles = []
        for t in group:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            s = shown_at(cap, t)
            tiles.append((s, tile(frame, label(s), width, marks.get(t, ""))))
        if not tiles:
            continue
        th = max(f.shape[0] for _, f in tiles)
        grid = np.full((rows * th + (rows - 1) * GAP, cols * width + (cols - 1) * GAP, 3), GAP_BGR, np.uint8)
        for n in range(cols * rows):  # each frame whole at its tile's top left (black below a shorter one, and in
            x, y = tile_origin(n, cols, width, th)  # the empty tiles after the last); the gap lies outside it
            grid[y:y + th, x:x + width] = 0
            if n < len(tiles):
                f = tiles[n][1]
                grid[y:y + f.shape[0], x:x + width] = f
        name = f"sheet_{i:03d}.jpg"
        cv2.imwrite(str(out / name), grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
        data["sheets"].append(dict(file=name, start=mmss(tiles[0][0], dec), end=mmss(tiles[-1][0], dec),
                                   tiles=[mmss(t, dec) for t, _ in tiles]))
    cap.release()
    media.write_json_atomic(index, data, indent=1)
    print(f"frames: {len(data['sheets'])} sheets ({every:g} s per tile) in {out.as_posix()}")
    if sources:
        print(f"frames: {len(sources)} joined files, times are on the joined timeline: {media.parts_line(sources)}; "
              'each label also names the file and the time in it; the first tile of each later file is marked '
              '"part N/M"')
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
    build(video, Path(a.out), a.every, a.cols, a.rows, a.width, a.start, a.end, unit_sources(video))


if __name__ == "__main__":
    main()
