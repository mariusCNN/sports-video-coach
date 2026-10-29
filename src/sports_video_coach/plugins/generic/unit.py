"""The analysis unit: <folder>/analysis.json, run/frames, run/review/review.json, README.md per language. The video is
analysis.json `video`: one source video by its absolute path, left where it is (keep it there), or several joined
into <folder>/video.mp4.

Steps: frames (cmd) -> review (agent: review.json) -> report (agent: README per language) -> the core artifacts
(clips, narration, html, qa, publish, film; analysis.json `artifacts` picks them).

`python -m <this module> <folder>` (stage `review-check`) prints what review.json still lacks.
"""
from __future__ import annotations

import json
import math
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
        return dict(super().fill_values(), prompts=PROMPTS, plugin=NAME,
                    sport=P.quoted(sport) if sport else "the sport in the video",
                    focus=P.quoted(self.game["focus"]) if self.game.get("focus") else "the main athlete in the video")

    def finished(self):
        if insufficient(self):
            review = json.loads((self.review / "review.json").read_text(encoding="utf8"))
            print("[analysis] completed: insufficient evidence; no new coaching artifacts generated.")
            print(f"[analysis] reason: {P.line(review['summary'])}")
            print(f"[analysis] next: {P.line(review['next_steps'])}")
            print(f"[analysis] result: {P.slash(self.review / 'review.json')}")
            print("[analysis] any older artifacts in this folder are retained; they do not describe this result.")
            return
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
    moments, summaries, schemas = [], [], []
    for part in parts:
        data = json.loads(part.read_text(encoding="utf8"))
        schemas.append(data.get("schema", 1))
        moments += data.get("moments") or []
        if str(data.get("summary") or "").strip():
            summaries.append(str(data["summary"]).strip())

    def at(m):
        try:
            return seconds(m["start"])
        except (KeyError, TypeError, ValueError):
            return 0.0
    moments.sort(key=at)
    merged = {"summary": " ".join(summaries), "moments": moments}
    if schemas and all(schema == 2 for schema in schemas):
        merged.update(schema=2, status="reviewed")
    media.write_text_atomic(p, json.dumps(merged,
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
    if not isinstance(data, dict):
        return [f"{p}: review must be a JSON object"]
    errs = []
    schema = data.get("schema", 1)
    if type(schema) is not int or schema not in (1, 2):
        return [f"{p}: schema must be 1 or 2"]
    status = data.get("status", "reviewed")
    if status not in ("reviewed", "insufficient_evidence"):
        return [f"{p}: status must be reviewed or insufficient_evidence"]
    if not isinstance(data.get("summary"), str) or not data["summary"].strip():
        errs.append("`summary` is empty: one or two sentences on what the video shows overall")
    moments = data.get("moments")
    if status == "insufficient_evidence":
        if moments != []:
            errs.append("insufficient_evidence needs an empty `moments` list")
        if not isinstance(data.get("next_steps"), str) or not data["next_steps"].strip():
            errs.append("insufficient_evidence needs `next_steps`: what footage would make a review possible")
        return errs
    minimum = 1 if schema == 2 else MIN_MOMENTS
    if not isinstance(moments, list) or len(moments) < minimum:
        return [f"{p}: needs a `moments` list with at least {minimum} entries"]
    frames = g.run / "frames" / "frames.json"
    dur = json.loads(frames.read_text(encoding="utf8")).get("duration_s") if frames.exists() else None
    for i, m in enumerate(moments, 1):
        if not isinstance(m, dict):
            errs.append(f"moment {i}: must be an object")
            continue
        try:
            t0, t1 = seconds(m["start"]), seconds(m["end"])
        except (KeyError, TypeError, ValueError):
            errs.append(f"moment {i}: `start` and `end` must be mm:ss")
            continue
        if not (math.isfinite(t0) and math.isfinite(t1)) or t0 < 0:
            errs.append(f"moment {i}: times must be finite and non-negative")
        elif t1 <= t0:
            errs.append(f"moment {i}: end {P.quoted(m['end'])} is not after start {P.quoted(m['start'])}")
        if dur is not None and t1 > dur + 1:
            errs.append(f"moment {i}: end {P.quoted(m['end'])} is after the video ends ({dur:.0f} s)")
        for k in ("what", "why"):
            if not isinstance(m.get(k), str) or not m[k].strip():
                errs.append(f"moment {i}: `{k}` is empty")
        for key, choices in (("confidence", ("seen", "likely", "unclear")), ("tag", ("fix", "good", "context"))):
            if (schema == 2 or key in m) and m.get(key) not in choices:
                errs.append(f"moment {i}: `{key}` must be one of {', '.join(choices)}")
    return errs


def insufficient(g: Analysis) -> bool:
    """Only a validated refusal can finish the run without artifacts."""
    p = g.review / "review.json"
    return (p.exists() and not review_errors(g) and
            json.loads(p.read_text(encoding="utf8")).get("status") == "insufficient_evidence")


def review_ok(g: Analysis) -> str:
    """The line once review.json passes: 'review-check: OK, 7 moments'."""
    data = json.loads((g.review / "review.json").read_text(encoding="utf8"))
    if data.get("status") == "insufficient_evidence":
        return "review-check: OK, insufficient evidence (no coaching claim)"
    return f"review-check: OK, {len(data['moments'])} moments"


def reports_written(g: Analysis) -> bool:
    return all((g.folder / P.readme(l)).exists() for l in g.langs)


STEPS = [
    P.Step("frames", "cmd", lambda g: (g.run / "frames" / "frames.json").exists(),
           lambda g: [["frames", str(g.video), "--out", str(g.run / "frames"),
                       "--every", str(g.game.get("every_s", 2))]],
           inputs=lambda g: [g.video], params=lambda g: {"every_s": g.game.get("every_s", 2)}),
    P.Step("review", "agent", lambda g: not review_errors(g), errors=review_errors, passed=review_ok, terminal=insufficient,
           how="Film review: open every sheet in {run}/frames (frames.json lists them in time order) and write "
               "{review}/review.json as the review guide says (`sports-video-coach guide review --unit {folder}` "
               "prints it; sport: {sport}; focus: {focus}). More than 10 sheets: delegate them to helpers "
               "(subagents), if your tool has them, at "
               "most 3 at once, one contiguous range each, writing {review}/part<N>.json; `sports-video-coach "
               "{plugin}:review-check {folder}` merges them. An unclear moment, or a fast object (shuttle, ball, a "
               "swing) between two tiles: `sports-video-coach frames {video} --out {run}/frames-zoom-0m12s --start "
               "0:12 --end 0:14.4 --every 0.2` cuts one full sheet of just that (12 tiles; --end is exclusive, so "
               "end = start + 12 x every). Give each zoom its own --out folder: a second zoom into one folder "
               "replaces the first."),
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
