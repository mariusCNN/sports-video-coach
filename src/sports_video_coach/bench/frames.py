"""The `frames` track of the benchmark: the agent gets still images instead of videos and may not run code.

On the default `code` track an agent may write a pixel tracker, and on both suites every agent that did scored about
1.0. The `frames` track asks the other question: how well does a model review film by eye? `bench prepare --track
frames` draws each video in a scratch folder, keeps every STEP-th frame as a JPG with its time burned in under the
picture, lays the same stills out on numbered contact sheets, and deletes the video. The truth is the same as on the
code track: a still's time is its exact frame time (frame index / 25), so the timestamps tasks are answerable.

Frame rate: every task keeps every 2nd frame (12.5 stills per second, one every 0.08 s). The shortest thing a task
needs seen is the treadmill's 0.28 s between foot strikes (cadence-change); the others are the 0.4 s between two cone
touches, the 0.44 s between two blue bounces, the about 0.3 s a squat plate stays below the lower line and a short jump
of the red block. 12.5 per second puts at least 3 stills into each of them. STEP is per task so a later suite can
choose differently.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .. import media
from .suite import FPS

TRACKS = ("code", "frames")
TRACK = "code"                      # the default track; a result or answers file without a track is on it
STEP = {}                           # task id -> keep every n-th video frame (default DEFAULT_STEP)
DEFAULT_STEP = 2
COLS, ROWS = 5, 5                   # stills per contact sheet: 25 (a sheet is 1280 x 820)
THUMB = (256, 144)                  # a still on a sheet
BAR = 24                            # the label bar under a full still
SHEET_BAR = 20                      # the label bar under a still on a sheet
QUALITY = 88


def step(task_id: str) -> int:
    return STEP.get(task_id, DEFAULT_STEP)


def stamp(t: float) -> str:
    return f"{t:06.2f}"


def label(img, text: str, bar: int, scale: float):
    """`img` with a black bar of height `bar` under it holding `text` in white (nothing of the picture covered)."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    out = np.zeros((h + bar, w, 3), dtype=np.uint8)
    out[:h] = img
    cv2.putText(out, text, (6, h + bar - 6), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def write_jpg(path: Path, img) -> None:
    import cv2
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, QUALITY])
    if not ok:
        raise RuntimeError(f"could not encode {path}")
    path.write_bytes(buf.tobytes())


def stills(video: Path, task_id: str, out: Path) -> int:
    """Write every step(task_id)-th frame of `video` as `<out>/frames/<task_id>/t<time>.jpg` and the same stills as
    contact sheets of 25 `<out>/sheets/<task_id>/sheet-<n>_t<first>-<last>.jpg`. Returns the number of stills."""
    import cv2
    import numpy as np
    fdir, sdir = out / "frames" / task_id, out / "sheets" / task_id
    for d in (fdir, sdir):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"could not open {video}")
    k, i, kept, page = step(task_id), 0, 0, []

    def flush():
        if not page:
            return
        tw, th = THUMB
        sheet = np.zeros((ROWS * (th + SHEET_BAR), COLS * tw, 3), dtype=np.uint8)
        for n, (t, img) in enumerate(page):
            cell = label(cv2.resize(img, THUMB, interpolation=cv2.INTER_AREA), f"t = {t:.2f} s", SHEET_BAR, 0.5)
            r, c = divmod(n, COLS)
            sheet[r * (th + SHEET_BAR):(r + 1) * (th + SHEET_BAR), c * tw:(c + 1) * tw] = cell
        num = len(list(sdir.glob("*.jpg"))) + 1
        write_jpg(sdir / f"sheet-{num:03d}_t{stamp(page[0][0])}-{stamp(page[-1][0])}.jpg", sheet)
        page.clear()

    try:
        while True:
            ok, img = cap.read()
            if not ok:
                break
            if i % k == 0:
                t = i / FPS
                write_jpg(fdir / f"t{stamp(t)}.jpg", label(img, f"{task_id}   t = {t:.2f} s", BAR, 0.6))
                page.append((t, img))
                kept += 1
                if len(page) == COLS * ROWS:
                    flush()
            i += 1
        flush()
    finally:
        cap.release()
    if not kept:
        raise RuntimeError(f"no frames read from {video}")
    return kept


def sheets(out: Path, task_id: str) -> list[str]:
    """The contact sheets of a task, as paths relative to `out` in time order."""
    return [f"sheets/{task_id}/{p.name}" for p in sorted((Path(out) / "sheets" / task_id).glob("sheet-*.jpg"))]


def draw_stills(tasks, out: Path) -> list[int]:
    """Draw each task's video in a scratch folder next to `out`, write its stills into `out` and delete the video:
    the run folder never holds a video."""
    counts = []
    with media.scratch(out / "x") as tmp:
        for t in tasks:
            video = t.draw(tmp / t.video)
            counts.append(stills(Path(video), t.id, out))
            Path(video).unlink(missing_ok=True)
    return counts
