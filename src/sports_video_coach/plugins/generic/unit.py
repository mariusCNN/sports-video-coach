"""The analysis unit: <folder>/analysis.json, video.mp4, run/frames, run/review/review.json, README.md per language.

Steps: frames (cmd) -> review (agent: review.json) -> report (agent: README per language) -> the core artifacts
(clips, narration, html, qa, publish, film; analysis.json `artifacts` picks them).

`python -m <this module> <folder>` (stage `review-check`) prints what review.json still lacks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sports_video_coach import pipeline as P
from sports_video_coach.timefmt import seconds

from . import NAME

PROMPTS = Path(__file__).parent / "prompts"
MIN_MOMENTS = 3


class Analysis(P.Session):
    """One analysis folder (analysis.json), driven by pipeline.drive with STEPS."""
    JSON = "analysis.json"
    PLUGIN = NAME
    LABEL = "analysis"
    PLAN = "next steps"

    def fill_values(self) -> dict:
        sport = self.game.get("sport")
        if isinstance(sport, dict):  # {"zh": .., "en": ..}: names per page language
            sport = sport.get("en") or next(iter(sport.values()), "")
        return dict(super().fill_values(), prompts=PROMPTS, sport=sport or "the sport in the video",
                    focus=self.game.get("focus") or "the main athlete in the video")

    def finished(self):
        print(f"[analysis] done. Page: {self.folder / 'index.html'}")
        films = [self.folder / f"film.{l}.mp4" for l in self.langs if (self.folder / f"film.{l}.mp4").exists()]
        if films:
            print("[analysis] explained video (send it yourself, it is not published): " + ", ".join(map(str, films)))
        mp3s = [self.folder / f"listen.{l}.mp3" for l in self.langs if (self.folder / f"listen.{l}.mp3").exists()]
        if mp3s:
            print("[analysis] narration (also on the page): " + ", ".join(map(str, mp3s)))
        clips = sorted((self.folder / "clips").glob("*.mp4"))
        if clips:
            print(f"[analysis] clips (also on the page): {len(clips)} in {self.folder / 'clips'}")

    @classmethod
    def load(cls, folder: Path) -> "Analysis":
        folder = Path(folder)
        p = folder / cls.JSON
        if not p.exists():
            sys.exit(f"{p} not found: start with `sports-video-coach run <video files>`")
        data = json.loads(p.read_text(encoding="utf8"))
        langs = tuple(data.get("languages") or P.profile_langs())
        return cls(folder, data, langs)


def review_errors(g: Analysis) -> list[str]:
    """What run/review/review.json still lacks (see prompts/review.md)."""
    p = g.review / "review.json"
    if not p.exists():
        return [f"{p} missing"]
    try:
        data = json.loads(p.read_text(encoding="utf8"))
    except json.JSONDecodeError as e:
        return [f"{p}: not valid JSON ({e})"]
    errs = []
    moments = data.get("moments") if isinstance(data, dict) else None
    if not isinstance(moments, list) or len(moments) < MIN_MOMENTS:
        return [f"{p}: needs a `moments` list with at least {MIN_MOMENTS} entries"]
    frames = g.run / "frames" / "frames.json"
    dur = json.loads(frames.read_text(encoding="utf8")).get("duration_s") if frames.exists() else None
    for i, m in enumerate(moments, 1):
        try:
            t0, t1 = seconds(m["start"]), seconds(m["end"])
        except (KeyError, TypeError, ValueError):
            errs.append(f"moment {i}: `start` and `end` must be mm:ss")
            continue
        if t1 <= t0:
            errs.append(f"moment {i}: end {m['end']} is not after start {m['start']}")
        if dur is not None and t1 > dur + 1:
            errs.append(f"moment {i}: end {m['end']} is after the video ends ({dur:.0f} s)")
        for k in ("what", "why"):
            if not str(m.get(k) or "").strip():
                errs.append(f"moment {i}: `{k}` is empty")
    if not str(data.get("summary") or "").strip():
        errs.append("`summary` is empty: one or two sentences on what the video shows overall")
    return errs


def reports_written(g: Analysis) -> bool:
    return all((g.folder / P.readme(l)).exists() for l in g.langs)


STEPS = [
    P.Step("frames", "cmd", lambda g: (g.run / "frames" / "frames.json").exists(),
           lambda g: [["frames", str(g.video), "--out", str(g.run / "frames"),
                       "--every", str(g.game.get("every_s", 2))]],
           inputs=lambda g: [g.video], params=lambda g: {"every_s": g.game.get("every_s", 2)}),
    P.Step("review", "agent", lambda g: not review_errors(g), errors=review_errors,
           how="Film review: open every sheet in {run}/frames (frames.json lists them in time order) and write "
               "{review}/review.json as the review guide says (`sports-video-coach guide review` prints it; sport: "
               "{sport}; focus: {focus}). Delegate the sheets to subagents if you have them, at most 3 at once, one "
               "part each. An "
               "unclear moment: `sports-video-coach frames {video} --out {run}/frames-zoom --start 0:12 --end 0:15 "
               "--every 0.2` cuts a dense sheet of just that."),
    P.Step("report", "agent", reports_written,
           how="Write the coaching report {readmes} in {folder} from {review}/review.json, as `sports-video-coach "
               "guide report` says ({langs}); mark the moments to show with ![caption](clip:mm:ss-mm:ss)."),
    *P.tail_steps(
        lambda g: g.video,
        listen_how="Write the narration scripts listen.<lang>.md for {langs} in {folder} (`sports-video-coach guide narration`).",
        qa_how="QA: serve {folder} over http (a browser-check subagent if you have one) and check the page in every "
               "language, the audio and every clip on a 390 px wide screen. No browser: `sports-video-coach page-check "
               "{folder}` is accepted; say in qa.md that layout and playback were not looked at. Write the result to "
               "{folder}/qa.md, first word PASS when it passes.",
        film_script_how="Write the explained-video scripts {folder}/film.<lang>.md for {langs} from the finished "
                        "report (`sports-video-coach guide film`); check them with `sports-video-coach film {folder} --video "
                        "{video} --dry`."),
]
NAMES = [s.name for s in STEPS]


def main(argv=None):
    """Stage `review-check <folder>`: print what review.json still lacks; exit 1 when anything does."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.exit("usage: review-check <analysis folder>")
    errs = review_errors(Analysis.load(Path(argv[0])))
    for e in errs:
        print(e)
    print("review.json: OK" if not errs else f"{len(errs)} problem(s)")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
