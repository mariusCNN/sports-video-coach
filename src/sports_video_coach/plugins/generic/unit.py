"""The analysis unit: <folder>/analysis.json, run/frames, run/review/review.json, README.md per language. The video is
analysis.json `video`: one source video by its absolute path, left where it is (keep it there), or several joined
into <folder>/video.mp4.

Steps: frames (cmd) -> review (agent: review.json) -> report (agent: README per language) -> the core artifacts
(clips, narration, html, qa, publish, film; analysis.json `artifacts` picks them).

`python -m <this module> <folder>` (stage `review-check`) prints what review.json still lacks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sports_video_coach import media, pipeline as P
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
        return dict(super().fill_values(), prompts=PROMPTS, plugin=NAME, sport=sport or "the sport in the video",
                    focus=self.game.get("focus") or "the main athlete in the video")

    def finished(self):
        clips = sorted((self.folder / "clips").glob("*.mp4"))
        got, old = P.kept(self, html=[self.folder / "index.html"],
                          film=[self.folder / f"film.{l}.mp4" for l in self.langs],
                          narration=[self.folder / f"listen.{l}.mp3" for l in self.langs],
                          clips=[self.folder / "clips"] if clips else [])
        page = "html" in got
        print(f"[analysis] done. Page: {P.slash(self.folder / 'index.html')}" if page else "[analysis] done.")
        if got.get("film"):
            print("[analysis] explained video (send it yourself, it is not published): "
                  + ", ".join(map(P.slash, got["film"])))
        if got.get("narration"):
            print("[analysis] narration (also on the page): " + ", ".join(map(P.slash, got["narration"])))
        if got.get("clips"):
            print(f"[analysis] clips{' (also on the page)' if page else ''}: {len(clips)} in "
                  f"{P.slash(self.folder / 'clips')}")
        if old:
            print(f"[analysis] {old}")

    @classmethod
    def load(cls, folder: Path) -> "Analysis":
        folder = Path(folder)
        p = folder / cls.JSON
        if not p.exists():
            sys.exit(f"{p} not found: start with `sports-video-coach run <video files>`")
        data = json.loads(p.read_text(encoding="utf8"))
        return cls(folder, data, P.unit_langs(data, cls.LANG_CHOICES))


def split_hint(g: Analysis) -> str:
    """'' or ' (26 sheets; with helpers: 1-9, 10-18, 19-26)': contiguous sheet ranges, about 10 per helper, at most 3."""
    frames = g.run / "frames" / "frames.json"
    n = len(json.loads(frames.read_text(encoding="utf8"))["sheets"]) if frames.exists() else 0
    k = min(3, -(-n // 10))
    if k < 2:
        return ""
    size = -(-n // k)
    ranges = [f"{a + 1}-{min(n, a + size)}" for a in range(0, n, size)]
    return f" ({n} sheets; with helpers, one range each: {', '.join(ranges)})"


def merge_parts(g: Analysis) -> Path | None:
    """run/review/part*.json (one per helper) joined into review.json, moments in time order; None when there is a
    review.json already or no parts."""
    p = g.review / "review.json"
    parts = sorted(g.review.glob("part*.json")) if g.review.is_dir() else []
    if p.exists() or not parts:
        return None
    moments, summaries = [], []
    for part in parts:
        data = json.loads(part.read_text(encoding="utf8"))
        moments += data.get("moments") or []
        if str(data.get("summary") or "").strip():
            summaries.append(str(data["summary"]).strip())

    def at(m):
        try:
            return seconds(m["start"])
        except (KeyError, TypeError, ValueError):
            return 0.0
    moments.sort(key=at)
    media.write_text_atomic(p, json.dumps({"summary": " ".join(summaries), "moments": moments},
                                          ensure_ascii=False, indent=1) + "\n")
    print(f"merged {len(parts)} part(s) into {P.slash(p)}: {len(moments)} moments. The summary joins the parts' "
          "summaries: rewrite it as one or two sentences for the whole video.")
    return p


def review_errors(g: Analysis) -> list[str]:
    """What run/review/review.json still lacks (see prompts/review.md)."""
    p = g.review / "review.json"
    if not p.exists():
        parts = sorted(g.review.glob("part*.json")) if g.review.is_dir() else []
        if parts:
            return [f"{p} missing; {len(parts)} part file(s) there: `sports-video-coach {NAME}:review-check "
                    f"{P.slash(g.folder)}` merges them into it"]
        return [f"{p} missing" + split_hint(g)]
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


def review_ok(g: Analysis) -> str:
    """The line once review.json passes: 'review-check: OK, 7 moments'."""
    data = json.loads((g.review / "review.json").read_text(encoding="utf8"))
    return f"review-check: OK, {len(data['moments'])} moments"


def reports_written(g: Analysis) -> bool:
    return all((g.folder / P.readme(l)).exists() for l in g.langs)


STEPS = [
    P.Step("frames", "cmd", lambda g: (g.run / "frames" / "frames.json").exists(),
           lambda g: [["frames", str(g.video), "--out", str(g.run / "frames"),
                       "--every", str(g.game.get("every_s", 2))]],
           inputs=lambda g: [g.video], params=lambda g: {"every_s": g.game.get("every_s", 2)}),
    P.Step("review", "agent", lambda g: not review_errors(g), errors=review_errors, passed=review_ok,
           how="Film review: open every sheet in {run}/frames (frames.json lists them in time order) and write "
               "{review}/review.json as the review guide says (`sports-video-coach guide review --unit {folder}` "
               "prints it; sport: {sport}; focus: {focus}). Delegate the sheets to helpers (subagents), if your "
               "tool has them, at "
               "most 3 at once, one contiguous range each, writing {review}/part<N>.json; `sports-video-coach "
               "{plugin}:review-check {folder}` merges them. An unclear moment, or a fast object (shuttle, ball, a "
               "swing) between two tiles: `sports-video-coach frames {video} --out {run}/frames-zoom --start 0:12 "
               "--end 0:15 --every 0.2` cuts a dense sheet of just that."),
    P.Step("report", "agent", reports_written, checks=P.report_checks,
           errors=lambda g: P.missing([g.folder / P.readme(l) for l in g.langs], g),  # a language added: only its file
           derives=lambda g: [(g.folder / P.readme(l), [g.review / "review.json"]) for l in g.langs],
           how="Write the coaching report {readmes} in {folder} from {review}/review.json, as `sports-video-coach "
               "guide report --unit {folder}` says ({langs}); mark the moments to show with "
               "![caption](clip:mm:ss-mm:ss)."),
    *P.tail_steps(
        lambda g: g.video,
        listen_how="Write the narration scripts listen.<lang>.md for {langs} in {folder} (`sports-video-coach guide "
                   "narration --unit {folder}`).",
        qa_how="QA: serve {folder} over http (a browser helper, if your tool has one) and check the page in every "
               "language, the audio and every clip on a 390 px wide screen. Write the result to {folder}/qa.md, "
               "first word PASS when it passes.",
        film_script_how="Write the explained-video scripts {folder}/film.<lang>.md for {langs} from the finished "
                        "report (`sports-video-coach guide film --unit {folder}`); check them with "
                        "`sports-video-coach film {folder} --video {video} --dry`."),
]
NAMES = [s.name for s in STEPS]


def main(argv=None):
    """Stage `review-check <folder>`: merge helpers' run/review/part*.json into review.json when there is none, then
    print what review.json still lacks; exit 1 when anything does."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: review-check <analysis folder>: merge run/review/part*.json, then list what review.json lacks")
        sys.exit(0 if argv else 2)
    g = Analysis.load(Path(argv[0]))
    merge_parts(g)
    errs = review_errors(g)
    for e in errs:
        print(e)
    print(review_ok(g) if not errs else f"{len(errs)} problem(s)")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
