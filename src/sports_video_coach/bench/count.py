"""The benchmark page's "Count it yourself" block: the visitor watches one task video of `svc-bench-3`, types a
count, and only then sees the truth, every contender's stored answer for that task and the blind guess.

The task is `juggle-touches` (the only count in the suite, the same one `bench.clip` shows): count the red player's
foot touches, double touches count twice, floor bounces and the other juggler do not. The question video is the
task video exactly as contenders got it (`suite3.draw_juggle`, 640x360, 29.76 s, H.264, no audio), remuxed with the
index at the front so a browser can start it before the whole file arrives; no answer is drawn on it (unlike
`clip.mp4`). `count.jpg` is its first frame, the poster. Both need ffmpeg only (no Pillow, no matplotlib).

`count_data` reads every answer from the result files (the published suite only: a fresh-seed run counted another
video); the truth comes from the suite, and a result file whose stored truth differs is refused.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .. import media
from . import suite3
from .clip import STEP, SUITE, TASK, model_label
from .suite import FPS

MP4, POSTER = "count.mp4", "count.jpg"
QUESTION = suite3.BY_ID[TASK].question   # the task text every contender got (the Chinese page translates it)
STILL_S = STEP / FPS                     # a frames-track contender gets one still every STILL_S seconds
TRACKS = ("frames", "code")     # shown in this order: the frames track reviews by eye, as the visitor does


def count_data(rows: list[dict]) -> dict | None:
    """What the block shows, or None when no contender ran the task on the published suite: {"suite", "task",
    "question", "seconds", "truth", "floor": {"answer", "score"} or None, "contenders": [{"track", "label",
    "runs": [{"file", "answer", "score"}]}]}. Contenders are grouped by track (frames first), agent and model,
    best mean score first (then more runs); a contender's runs by file name."""
    from . import page as P
    task = suite3.BY_ID[TASK]
    groups: dict[tuple[str, str, str], list[dict]] = {}
    floor = None
    for r in sorted(rows, key=lambda r: r["_file"]):
        if P.suite_of(r) != SUITE:
            continue
        row = next((t for t in r["tasks"] if t.get("id") == TASK), None)
        if row is None:
            continue
        if row.get("truth") != task.truth:
            raise ValueError(f"{r['_file']}: {TASK} truth {row.get('truth')!r} is not the suite's {task.truth!r}")
        run = {"file": r["_file"], "answer": row.get("answer"), "score": row.get("score") or 0.0}
        if P.is_baseline(r):
            floor = floor or {"answer": run["answer"], "score": run["score"]}
            continue
        c = r["contender"]
        groups.setdefault((P.track_of(r), str(c.get("agent") or ""), str(c.get("model") or "")), []).append(run)
    if not groups:
        return None
    contenders = [{"track": track, "label": model_label(agent, model), "runs": runs,
                   "mean": sum(x["score"] for x in runs) / len(runs)} for (track, agent, model), runs in groups.items()]
    order = {t: i for i, t in enumerate(TRACKS)}
    contenders.sort(key=lambda c: (order.get(c["track"], len(order)), c["track"], -c["mean"], -len(c["runs"]),
                                   c["label"]))
    return {"suite": SUITE, "task": TASK, "question": task.question, "seconds": task.seconds, "truth": task.truth,
            "floor": floor, "contenders": contenders}


def draw(out_dir: Path) -> tuple[Path, Path]:
    """Write count.mp4 (the task video, index first) and count.jpg (its first frame) into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4, jpg = out_dir / MP4, out_dir / POSTER
    with tempfile.TemporaryDirectory(prefix="svc-count-") as tmp:
        video = suite3.draw_juggle(Path(tmp) / "juggle.mp4")
        media.ffmpeg("-i", video, "-map", "0:v", "-c", "copy", "-an", "-movflags", "+faststart", mp4)
    media.ffmpeg("-i", mp4, "-frames:v", "1", "-q:v", "3", jpg)
    return mp4, jpg


def write(rows: list[dict], out_dir: Path) -> tuple[Path, Path] | None:
    """Draw the question video into out_dir; None (nothing written) without ffmpeg or a contender run of the task."""
    if not shutil.which(media.ffmpeg_exe()) or count_data(rows) is None:
        return None
    return draw(out_dir)
