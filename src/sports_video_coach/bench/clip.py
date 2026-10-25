"""The benchmark page's short clip (`clip.mp4` and `clip.gif` next to `index.html`, about 18 s, 720x720): one hard
moment of `svc-bench-3`, then the truth against what each contender answered on that task.

1. The juggling video (`juggle-touches`), drawn by the suite exactly as contenders got it, at real speed with a
   running touch count.
2. The stills a frames-track contender gets (one every 0.08 s) around the first quick double touch, zoomed and
   slowed down: two touches 0.24 s apart, the ball hopping about 10 px.
3. The truth and each contender's answer per run, from the result files.
4. Where the full leaderboard is.

Every number on screen comes from the suite (`suite3`: touch frames, the hop, the truth) or the result files, never
typed in: `clip_data` is the data step (tested against the files); `scenes` turns it into the text drawn; `draw`
renders it and needs Pillow (comes with matplotlib, which the light install does not have) and ffmpeg. Without
them `bench page` skips the clip and the page shows none.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import media
from .suite import FPS

MP4, GIF = "clip.mp4", "clip.gif"
SIZE = 720                  # the MP4 is SIZE x SIZE; legible on a 390 px wide phone screen
GIF_SIZE, GIF_FPS = 600, 10  # the GIF (README, X) is smaller to stay under 4 MB
SUITE, TRACK, TASK = "svc-bench-3", "frames", "juggle-touches"
STEP = 2                    # a frames-track still every STEP video frames (bench.frames.DEFAULT_STEP)
SLOW_HOLD = 6               # output frames per still in the slowed part (one still per 0.08 s -> 3x slower)
ALT = ("Clip: a drawn video of a player juggling a small ball, then the stills an agent sees around a quick double "
       "touch, zoomed in, then the true touch count against what each model answered.")


def model_label(agent: str, model: str) -> str:
    """'claude-opus-5-5' -> 'Opus 5.5'; another model keeps its agent: 'Codex · gpt-6-astra'."""
    if model.startswith("claude-"):
        name, *ver = model.removeprefix("claude-").split("-")
        return f"{name.title()} {'.'.join(ver)}".strip()
    return f"{agent} · {model}" if model else agent


def double_touch() -> dict:
    """The first quick double touch of the juggling video: the two touch frames, their numbers in the count, the
    gap and the hop height (from the numbers that drive the drawing)."""
    from . import suite3 as S3
    touches = S3.JUG_TOUCHES
    i = next(i for i in range(len(touches) - 1) if touches[i + 1] - touches[i] <= 6)
    hop = next(h for f, k, h in S3.JUG_CONTACTS if f == touches[i])
    return {"frames": [touches[i], touches[i + 1]], "numbers": [i + 1, i + 2],
            "gap_s": round((touches[i + 1] - touches[i]) / FPS, 2), "hop_px": hop, "ball_r": S3.JUG_R,
            "touches": list(touches)}


def clip_data(rows: list[dict]) -> dict | None:
    """What the clip shows, or None when no contender ran the task: {"suite", "track", "task", "truth", "moment",
    "contenders": [{"label", "baseline", "runs": [{"file", "answer", "score", "killed"}]}], "owner_runs", "runs"}.
    Contenders are ordered by their mean score on the task (best first), the blind guess last; a contender's runs by
    file name."""
    from . import page as P, suite3 as S3
    truth = S3.BY_ID[TASK].truth
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in sorted(rows, key=lambda r: r["_file"]):
        if P.suite_of(r) != SUITE or P.track_of(r) != TRACK:
            continue
        task = next((t for t in r["tasks"] if t.get("id") == TASK), None)
        if task is None:
            continue
        if task.get("truth") != truth:
            raise ValueError(f"{r['_file']}: {TASK} truth {task.get('truth')!r} is not the suite's {truth!r}")
        c = r["contender"]
        groups.setdefault((str(c.get("agent") or ""), str(c.get("model") or "")), []).append(
            {"file": r["_file"], "answer": task.get("answer"), "score": task.get("score") or 0.0,
             "killed": "killed at" in str(c.get("settings") or ""), "baseline": P.is_baseline(r),
             "by": str(r.get("submitted_by") or "")})
    if not any(not run["baseline"] for runs in groups.values() for run in runs):
        return None
    contenders = []
    for (agent, model), runs in groups.items():
        base = runs[0]["baseline"]
        contenders.append({"label": "Blind guess" if base else model_label(agent, model), "baseline": base,
                           "mean": sum(x["score"] for x in runs) / len(runs),
                           "runs": [{k: x[k] for k in ("file", "answer", "score", "killed")} for x in runs]})
    contenders.sort(key=lambda c: (c["baseline"], -c["mean"], -len(c["runs"]), c["label"]))
    real = [run for runs in groups.values() for run in runs if not run["baseline"]]
    return {"suite": SUITE, "track": TRACK, "task": TASK, "truth": truth, "moment": double_touch(),
            "contenders": contenders, "runs": len(real),
            "owner_runs": sum(1 for x in real if x["by"].lower() == P.OWNER.lower())}


def answer_text(run: dict) -> str:
    if run["answer"] is None:
        return "–"
    return str(run["answer"])


def row_note(c: dict, truth) -> str:
    """The small line under a contender's name: no video for the blind guess, else how many runs and how far off."""
    if c["baseline"]:
        return "copies the task's example, sees no video"
    runs = c["runs"]
    parts = [f"{len(runs)} runs" if len(runs) > 1 else "1 run"]
    for k, r in enumerate(runs, 1):
        if r["answer"] is None:
            parts.append(f"run {k} killed, no answer" if r["killed"] else f"run {k} no answer")
    offs = sorted({abs(r["answer"] - truth) for r in runs if isinstance(r["answer"], int)})
    if offs == [0]:
        parts.append("exact")
    elif offs:
        parts.append("off by " + " / ".join(str(o) for o in offs if o) + ("" if 0 not in offs else " / exact"))
    return " · ".join(parts)


def scenes(data: dict) -> dict:
    """Every text the clip draws, by scene (tests compare its numbers with the result files)."""
    m, truth = data["moment"], data["truth"]
    a, b = m["numbers"]
    return {
        "intro": {"kicker": f"{data['suite']} · {data['track']} track (stills only)",
                  "title": "Count the red player's touches",
                  "caption": [f"Hand-held camera, a ball {m['ball_r']} px in radius,", "an identical ball juggled next to him."]},
        "slow": {"kicker": "The stills the agent gets, one every 0.08 s",
                 "title": "A double touch, slowed 3x",
                 "caption": [f"Touches {a} and {b}: {m['gap_s']:.2f} s apart,",
                             f"the ball hops {m['hop_px']} px. Both count."]},
        "answers": {"kicker": f"{data['task']} · answers from benchmark/results",
                    "title": f"Truth: {truth} touches",
                    "rows": [{"label": c["label"], "answers": [answer_text(r) for r in c["runs"]],
                              "exact": [r["answer"] == truth for r in c["runs"]],
                              "note": row_note(c, truth)} for c in data["contenders"]]},
        "end": {"title": "Full leaderboard, every answer, method:",
                "url": "mariusding.github.io/sports-video-coach/benchmark",
                "caption": [(f"All {data['runs']} runs above were submitted by" if data["owner_runs"] == data["runs"]
                             else f"{data['owner_runs']} of these {data['runs']} runs were submitted by"),
                            "the tool's author. Drawn videos, exact truth."]},
    }


# --- drawing -------------------------------------------------------------------------------------------------------
BG, CARD, INK, MUTED, ACCENT = "#14132a", "#1e1c3b", "#ecebf7", "#a9a7cc", "#8f8af0"
GOOD, OFF = "#4cc38a", "#f08a6b"
INTRO_S, END_S, ROW_GAP_S, ANSWERS_HOLD_S = 3.0, 3.0, 0.5, 4.0
VIDEO_Y = 190
CROP = (100, 184, 316, 319)   # x0, y0, x1, y1 of the 640x360 frame around the red player's foot (4:3)


def fonts():
    """(regular, bold) font file paths: DejaVu Sans from matplotlib, the same on every machine; None for Pillow's."""
    try:
        import matplotlib
        d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        if (d / "DejaVuSans.ttf").is_file():
            return d / "DejaVuSans.ttf", d / "DejaVuSans-Bold.ttf"
    except ImportError:
        pass
    return None, None


class Painter:
    def __init__(self):
        from PIL import ImageFont
        self.regular, self.bold = fonts()
        self.cache = {}
        self.ImageFont = ImageFont

    def font(self, size: int, bold: bool = False):
        key = (size, bold)
        if key not in self.cache:
            path = self.bold if bold else self.regular
            self.cache[key] = (self.ImageFont.truetype(str(path), size) if path
                               else self.ImageFont.load_default(size))
        return self.cache[key]

    def blank(self):
        from PIL import Image
        return Image.new("RGB", (SIZE, SIZE), BG)

    def header(self, img, kicker: str, title: str):
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        d.text((36, 36), kicker, fill=MUTED, font=self.font(26))
        d.text((36, 76), title, fill=INK, font=self.font(38, True))

    def caption(self, img, lines: list[str], y: int):
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        for i, s in enumerate(lines):
            d.text((36, y + i * 40), s, fill=INK, font=self.font(30))

    def chip(self, img, xy, text: str, color: str, size: int = 28):
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        f = self.font(size, True)
        x0, y0, x1, y1 = d.textbbox(xy, text, font=f)
        d.rounded_rectangle((x0 - 12, y0 - 8, x1 + 12, y1 + 8), radius=10, fill=color)
        d.text(xy, text, fill=BG, font=f)


ROWS_TOP, ROWS_BOTTOM, ROW_STEP = 150, SIZE - 16, 88   # the answers list: first card's top, last card's bottom limit


def answer_layout(p: Painter, rows: list[dict]) -> list[dict]:
    """Where each answers-scene row goes: {"card" box, "label" (cut with '…' to end before the answers),
    "label_xy", "note_xy", "answer_xy" (one per run), and the fonts}. Rows shrink together so the last card ends
    above ROWS_BOTTOM however many contenders there are."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    s = min(1.0, (ROWS_BOTTOM - ROWS_TOP) / (len(rows) * ROW_STEP)) if rows else 1.0
    step = int(ROW_STEP * s)
    label_f, note_f, answer_f = p.font(round(30 * s), True), p.font(round(23 * s)), p.font(round(34 * s), True)
    out = []
    for j, r in enumerate(rows):
        y = ROWS_TOP + j * step
        x, xy = SIZE - 44, []
        for ans in reversed(r["answers"]):
            x -= d.textlength(ans, font=answer_f)
            xy.insert(0, (x, y + round(12 * s)))
            x -= round(26 * s)
        label, room = r["label"], x - 44 - round(16 * s)
        while d.textlength(label, font=label_f) > room and len(label) > 1:
            label = label[:-2].rstrip() + "…"
        out.append({"card": (24, y, SIZE - 24, y + step - round(12 * s)), "label": label,
                    "label_xy": (44, y + round(10 * s)), "note_xy": (44, y + round(47 * s)), "answer_xy": xy,
                    "label_font": label_f, "note_font": note_f, "answer_font": answer_f})
    return out


def video_frames(video: Path, upto: int) -> list:
    """The first `upto` frames of the drawn video as RGB arrays."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    out = []
    try:
        while len(out) < upto:
            ok, f = cap.read()
            if not ok:
                break
            out.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    finally:
        cap.release()
    return out


def frames_of(data: dict, video: list):
    """Yield the clip's frames (PIL images, FPS a second)."""
    from PIL import Image, ImageDraw
    p, text = Painter(), scenes(data)
    m = data["moment"]
    touches = m["touches"]
    w = SIZE
    vh = round(w * 360 / 640)
    for i in range(round(INTRO_S * FPS)):                                 # 1. real speed, running count
        img = p.blank()
        p.header(img, text["intro"]["kicker"], text["intro"]["title"])
        img.paste(Image.fromarray(video[i]).resize((w, vh), Image.BILINEAR), (0, VIDEO_Y))
        p.chip(img, (SIZE - 250, VIDEO_Y + 16), f"touches: {sum(1 for f in touches if f <= i)}", INK)
        p.caption(img, text["intro"]["caption"], VIDEO_Y + vh + 40)
        yield img
    f0, f1 = m["frames"]
    x0, y0, x1, y1 = CROP
    cw = SIZE
    ch = round(cw * (y1 - y0) / (x1 - x0))
    first = (f0 - 6) // STEP * STEP
    for still in range(first, f1 + 8, STEP):                              # 2. the stills, zoomed, slowed
        img = p.blank()
        p.header(img, text["slow"]["kicker"], text["slow"]["title"])
        crop = Image.fromarray(video[still]).crop(CROP).resize((cw, ch), Image.NEAREST)
        img.paste(crop, (0, VIDEO_Y - 40))
        d = ImageDraw.Draw(img)
        d.text((24, VIDEO_Y - 28), f"t = {still / FPS:.2f} s", fill=INK, font=p.font(28, True),
               stroke_width=3, stroke_fill=BG)
        for n, f in zip(m["numbers"], m["frames"]):
            if abs(still - f) <= 1:
                p.chip(img, (SIZE - 200, VIDEO_Y - 24), f"touch {n}", GOOD)
        p.caption(img, text["slow"]["caption"], VIDEO_Y - 40 + ch + 24)
        hold = SLOW_HOLD * (3 if any(abs(still - f) <= 1 for f in m["frames"]) else 1)
        for _ in range(hold):
            yield img
    rows = text["answers"]["rows"]                                        # 3. truth vs answers
    layout = answer_layout(p, rows)
    for k in range(round((ROW_GAP_S * len(rows) + ANSWERS_HOLD_S) * FPS)):
        shown = min(len(rows), int(k / (ROW_GAP_S * FPS)) + 1)
        img = p.blank()
        p.header(img, text["answers"]["kicker"], text["answers"]["title"])
        d = ImageDraw.Draw(img)
        for r, box in zip(rows[:shown], layout[:shown]):
            d.rounded_rectangle(box["card"], radius=12, fill=CARD)
            d.text(box["label_xy"], box["label"], fill=MUTED if r["label"] == "Blind guess" else INK, font=box["label_font"])
            d.text(box["note_xy"], r["note"], fill=MUTED, font=box["note_font"])
            for (ans, ok), xy in zip(zip(r["answers"], r["exact"]), box["answer_xy"]):
                d.text(xy, ans, fill=GOOD if ok else OFF, font=box["answer_font"])
        yield img
    end = text["end"]                                                     # 4. where to look
    for _ in range(round(END_S * FPS)):
        img = p.blank()
        d = ImageDraw.Draw(img)
        d.text((36, 230), end["title"], fill=MUTED, font=p.font(30))
        d.text((36, 290), end["url"].split("/", 1)[0] + "/", fill=ACCENT, font=p.font(36, True))
        d.text((36, 340), end["url"].split("/", 1)[1], fill=ACCENT, font=p.font(36, True))
        p.caption(img, end["caption"], 450)
        yield img


def draw(data: dict, out_dir: Path) -> tuple[Path, Path]:
    """Render the clip for `clip_data` output into out_dir: clip.mp4 (H.264, SIZE px) and clip.gif (GIF_SIZE px)."""
    from . import suite3 as S3
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4, gif = out_dir / MP4, out_dir / GIF
    ff = media.ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="svc-clip-") as tmp:
        video = S3.draw_juggle(Path(tmp) / "juggle.mp4")
        need = max(round(INTRO_S * FPS), data["moment"]["frames"][1] + 8 + STEP)
        frames = video_frames(video, need)
        cmd = [ff, "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{SIZE}x{SIZE}",
               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", str(mp4)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for img in frames_of(data, frames):
                proc.stdin.write(img.tobytes())
            proc.stdin.close()
            rc = proc.wait()
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if rc:
            raise subprocess.CalledProcessError(rc, cmd)
    vf = (f"fps={GIF_FPS},scale={GIF_SIZE}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff"
          "[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run([ff, "-nostdin", "-v", "error", "-y", "-i", str(mp4), "-vf", vf, "-loop", "0", str(gif)],
                   check=True)
    return mp4, gif


def write(rows: list[dict], out_dir: Path) -> tuple[Path, Path] | None:
    """Draw the clip into out_dir; None (nothing written) without Pillow or ffmpeg, or when no run has the task."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        return None
    if not shutil.which(media.ffmpeg_exe()):
        return None
    data = clip_data(rows)
    return draw(data, out_dir) if data else None


def main(argv: list[str]) -> int:
    """`python -m sports_video_coach.bench.clip <results_dir> <out_dir>`: the clip alone (for a post)."""
    from . import page as P
    if len(argv) != 2:
        print("usage: python -m sports_video_coach.bench.clip <results_dir> <out_dir>")
        return 2
    rows, _ = P.load(Path(argv[0]))
    made = write(rows, Path(argv[1]))
    if made is None:
        print("[bench clip] nothing drawn: needs Pillow, ffmpeg and a run of the task")
        return 1
    for f in made:
        print(f"[bench clip] {f.as_posix()}: {f.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
