"""The fitness session unit: analysis.json ("plugin": "fitness"), run/frames, run/review/sets.json, run/pose,
run/reps/reps.json, run/review/review.json, README per language.

Steps: frames (cmd) -> sets (agent: split the session into sets, name each exercise from the library) -> pose (cmd)
-> reps (cmd) -> review (agent: review.json) -> report (agent) -> the core artifacts.

`python -m svc_fitness.unit <folder>` (stage `sets-check`) prints what sets.json still lacks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sports_video_coach import pipeline as P
from sports_video_coach.plugins.generic import unit as G
from sports_video_coach.timefmt import seconds

from . import NAME, library, page

PROMPTS = Path(__file__).parent / "prompts"
VIEWS = ("side", "front", "back", "oblique", "unclear")


class Session(G.Analysis):
    """One training session folder (analysis.json with "plugin": "fitness")."""
    PLUGIN = NAME
    LABEL = "session"
    PLAN = "next sessions"

    def fill_values(self) -> dict:
        return dict(super().fill_values(), prompts=PROMPTS, plugin=NAME, sets=self.review / "sets.json",
                    reps=self.run / "reps" / "reps.json", library=library.FILE)


def load_sets(g: Session) -> list[dict]:
    """run/review/sets.json `sets` ([] when missing)."""
    p = g.review / "sets.json"
    return json.loads(p.read_text(encoding="utf8")).get("sets", []) if p.exists() else []


def sets_errors(g: Session) -> list[str]:
    """What run/review/sets.json still lacks (prompts/sets.md)."""
    p = g.review / "sets.json"
    if not p.exists():
        return [f"{p} missing" + G.split_hint(g)]
    try:
        data = json.loads(p.read_text(encoding="utf8"))
    except json.JSONDecodeError as e:
        return [f"{p}: not valid JSON ({e})"]
    sets = data.get("sets") if isinstance(data, dict) else None
    if not isinstance(sets, list) or not sets:
        return [f"{p}: needs a non-empty `sets` list"]
    errs, ids, ex = [], set(), library.exercises()
    frames = g.run / "frames" / "frames.json"
    dur = json.loads(frames.read_text(encoding="utf8")).get("duration_s") if frames.exists() else None
    for i, s in enumerate(sets, 1):
        sid = s.get("id") or f"#{i}"
        if not s.get("id"):
            errs.append(f"set {i}: `id` is empty (S01, S02, ...)")
        elif s["id"] in ids:
            errs.append(f"set {sid}: duplicate id")
        ids.add(s.get("id"))
        try:
            t0, t1 = seconds(s["start"]), seconds(s["end"])
            if t1 <= t0:
                errs.append(f"set {sid}: end is not after start")
            if dur is not None and t1 > dur + 1:
                errs.append(f"set {sid}: end {s['end']} is after the video ends ({dur:.0f} s)")
        except (KeyError, TypeError, ValueError):
            errs.append(f"set {sid}: `start` and `end` must be mm:ss")
        if s.get("exercise") not in ex:
            hit = library.find(str(s.get("exercise") or ""))
            errs.append(f"set {sid}: exercise {s.get('exercise')!r} is not a library id"
                        + (f" (did you mean {hit['id']!r}?)" if hit else
                           "; pick the closest id from `sports-video-coach fitness:library`, or 'other' with `name`"
                           if s.get("exercise") != "other" else ""))
            if s.get("exercise") == "other" and page.set_name(s, "en").strip():
                errs.pop()
        if s.get("view") not in VIEWS:
            errs.append(f"set {sid}: `view` must be one of {', '.join(VIEWS)}")
        if s.get("reps") is not None and not (isinstance(s["reps"], int) and s["reps"] >= 0):
            errs.append(f"set {sid}: `reps` must be a whole number or null (unclear)")
    return errs


def pose_done(g: Session) -> bool:
    out = g.run / "pose"
    st = out / "status.json"
    status = json.loads(st.read_text(encoding="utf8")) if st.exists() else {}
    if "pose" in status and status["pose"] is None:
        return True  # ultralytics missing: nothing to measure
    want = [s["id"] for s in load_sets(g) if s.get("view") in ("side", "oblique", "front")]
    return st.exists() and all((out / f"{i}.npz").exists() for i in want)


STEPS = [
    G.STEPS[0],  # frames
    P.Step("sets", "agent", lambda g: not sets_errors(g), errors=sets_errors,
           passed=lambda g: f"sets-check: OK, {len(load_sets(g))} sets",
           how="Split the session into sets: open every sheet in {run}/frames and write {sets} as `sports-video-coach "
               "guide sets --unit {folder}` says (exercise ids: `sports-video-coach fitness:library`; one card: "
               "`sports-video-coach fitness:library <id>`). More than 10 sheets: delegate contiguous ranges to helpers, "
               "at most 3 at once, each writing {review}/sets-part<N>.json, then join them into {sets}. Check with "
               "`sports-video-coach fitness:sets-check {folder}`."),
    P.Step("pose", "cmd", pose_done, lambda g: [["pose", str(g.folder)]],
           inputs=lambda g: [g.review / "sets.json"], long=True),
    P.Step("reps", "cmd", lambda g: (g.run / "reps" / "reps.json").exists(), lambda g: [["reps", str(g.folder)]],
           inputs=lambda g: [g.review / "sets.json", *sorted((g.run / "pose").glob("*.npz"))], after=("pose",)),
    P.Step("review", "agent", lambda g: not G.review_errors(g), errors=G.review_errors, passed=G.review_ok,
           how="Film review of the lifts: write {review}/review.json as `sports-video-coach guide review --unit "
               "{folder}` says, from the sets in {sets}, the measured reps in {reps} (one entry per set) and the sheets "
               "in {run}/frames; zoom a rep with `sports-video-coach frames {video} --out {run}/frames-zoom-<set> "
               "--start 0:12 --end 0:14.4 --every 0.2`. Delegate sets to helpers (at most 3 at once) writing "
               "{review}/part<N>.json; `sports-video-coach {plugin}:review-check {folder}` merges them."),
    *G.STEPS[2:],  # report, then the core artifacts
]
NAMES = [s.name for s in STEPS]


def main(argv=None):
    """Stage `sets-check <folder>`: print what run/review/sets.json still lacks; exit 1 when anything does."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: sets-check <session folder>: list what run/review/sets.json lacks")
        sys.exit(0 if argv else 2)
    g = Session.load(Path(argv[0]))
    errs = sets_errors(g)
    for e in errs:
        print(e)
    print(f"sets-check: OK, {len(load_sets(g))} sets" if not errs else f"{len(errs)} problem(s)")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
