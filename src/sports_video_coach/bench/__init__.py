"""`sports-video-coach bench`: a reproducible benchmark of agents and models as sports film reviewers.

Suites: `svc-bench-1` (four short drawn videos), `svc-bench-2` ("hard": five drawn videos with a hand-held
camera, look-alike decoys and rule-defined events) and `svc-bench-3` ("eyes": small, short and hidden events, for
the frames track). The truth is exact (we drew them). Run one with any agent:

  sports-video-coach bench prepare --out <dir> [--suite svc-bench-2]   videos, TASKS.md and an answers.json to fill
                                [--track frames]       still images instead of videos, for an agent that runs no code
  (your agent watches the videos and fills <dir>/answers.json; it must not read the package source or any truth)
  sports-video-coach bench score <dir> --agent A --model M [--agent-version V] [--settings S] [--by HANDLE]
                                [--wall-seconds N] [--evidence URL] [--out FILE]
  sports-video-coach bench validate <result.json...>   re-score a result file; exit 1 if it was edited or broken
  sports-video-coach bench page ...                     the leaderboard page from benchmark/results/
  sports-video-coach bench run --agent claude|codex|cmd [--model M] [--suite S] [--track frames] [--cmd "..."]
                                [--dry-run]
                                all of it in one command: prepare, run the agent headless, score, issue link
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from .. import media
from . import frames as F, score as S
from .suite import SUITE

TASKS_MD = """# {suite}: sports film review benchmark

Watch each video and answer what it asks. Every video was drawn by `sports-video-coach bench prepare`, so the
right answer is known exactly; your answers are scored against it.

## Rules

- Watch the videos: look at frames, use ffmpeg, OpenCV or any script on the video files in this folder.
- Do not read the sports-video-coach package source, its git history or any truth or result file. The truth is
  in the package; reading it is cheating and makes the result worthless.
- Write only `answers.json` in this folder: replace each `null` with your answer, in the format below. Leave
  `null` for a task you skip (it scores 0).
- Times are seconds from the start of the video (the first frame is 0.0). Every video is 640x360 at 25 fps.

## Tasks

{tasks}

## Scoring (each task 0..1; total = mean, 3 decimals)

- count: max(0, 1 - |answer - truth| / truth).
- rate: 1 within 2 % of the truth, falling linearly to 0 at 20 % off.
- timestamps: answers are matched one-to-one to the true events in time order; a matched event scores 1 within
  0.5 s, falling linearly to 0 at 2 s off; a missed event scores 0. The sum is divided by the larger of the
  number of true events and the number of answers, so extra answers cost as much as missed ones.
- outcomes: the fraction of positions where your answer is right, over the larger of the two list lengths.

When done, the person running the benchmark scores it:

    sports-video-coach bench score <this folder> --agent "<agent>" --model "<model>"
"""

TASKS_MD_FRAMES = """# {suite}: sports film review benchmark, frames track

Look at the still images of each video and answer what it asks. Every video was drawn by `sports-video-coach bench
prepare`, so the right answer is known exactly; your answers are scored against it. The videos themselves are not
in this folder: this track measures how well you review film by eye.

## Rules

- Look only at the images in this folder. Each task lists its contact sheets: `sheets/<task>/`, 25 stills to a
  sheet in time order (read left to right, top to bottom), each with its time under it. `frames/<task>/` holds
  the same stills at full size (640x360), named by their time (`t012.48.jpg` is t = 12.48 s), for a closer look.
- Do not run code, scripts or commands, and do not measure pixels with a program: judge by eye. Read the images,
  then write your answers.
- Do not read the sports-video-coach package source, its git history or any truth or result file. The truth is
  in the package; reading it is cheating and makes the result worthless.
- Answer in `answers.json` in this folder: replace each `null` with your answer, in the format below. Leave
  `null` for a task you skip (it scores 0). With no tool that writes files, end your reply with the whole
  answers.json in one ```json block; the person running the benchmark saves it as answers.json.
- Times are seconds from the start of the video (the first still is t = 0.00). The videos ran at 25 fps; each task
  says how far apart its stills are, so a moment between two stills is between their times.

## Tasks

{tasks}

## Scoring (each task 0..1; total = mean, 3 decimals)

- count: max(0, 1 - |answer - truth| / truth).
- rate: 1 within 2 % of the truth, falling linearly to 0 at 20 % off.
- timestamps: answers are matched one-to-one to the true events in time order; a matched event scores 1 within
  0.5 s, falling linearly to 0 at 2 s off; a missed event scores 0. The sum is divided by the larger of the
  number of true events and the number of answers, so extra answers cost as much as missed ones.
- outcomes: the fraction of positions where your answer is right, over the larger of the two list lengths.

When done, the person running the benchmark scores it:

    sports-video-coach bench score <this folder> --agent "<agent>" --model "<model>"
"""


def tasks_md(suite: str = SUITE, track: str = F.TRACK, out: Path | None = None) -> str:
    """TASKS.md for a suite and track; on the frames track with `out`, each task lists its contact sheets."""
    parts = []
    for i, t in enumerate(S.SUITES[suite].TASKS, 1):
        if track == "frames":
            where = (f"stills in `frames/{t.id}/` and `sheets/{t.id}/`, one every {F.step(t.id) / F.FPS:g} s "
                     f"of a {t.seconds:g} s video")
        else:
            where = f"video `{t.video}`, {t.seconds:g} s"
        part = f"### {i}. `{t.id}` ({t.kind}) - {where}\n\n{t.question}\n\nAnswer: {t.answer_format}."
        if track == "frames" and out is not None:
            part += "\n\nContact sheets:\n\n" + "\n".join(f"- `{p}`" for p in F.sheets(out, t.id))
        parts.append(part)
    md = TASKS_MD_FRAMES if track == "frames" else TASKS_MD
    return md.format(suite=suite, tasks="\n\n".join(parts))


def prepare(out: Path, ids: list[str] | None = None, force: bool = False, suite: str = SUITE,
            track: str = F.TRACK) -> list[Path]:
    """Draw the suite's videos and write TASKS.md and an answers.json template into `out`. No truth is written.
    An answers.json that already holds an answer is kept unless `force` (one of another suite or track is an error).
    On the frames track each video becomes stills and contact sheets (see `frames`), no video stays in `out`, and
    the return value is the list of sheet folders."""
    if track not in F.TRACKS:
        raise SystemExit(f"unknown track {track!r}; one of {list(F.TRACKS)}")
    out = Path(out)
    tasks = S.SUITES[suite].TASKS
    ans = out / "answers.json"
    old, old_suite, old_track = {}, suite, track
    if ans.exists() and not force:
        try:
            data = json.loads(ans.read_text(encoding="utf8"))
            old, old_suite = data.get("answers", {}) or {}, data.get("suite", SUITE)
            old_track = data.get("track", F.TRACK)
        except (ValueError, AttributeError):
            old = {}
    answered = any(v is not None for v in old.values())
    if answered and (old_suite, old_track) != (suite, track):
        raise SystemExit(f"{ans} already has answers for suite {old_suite!r}, track {old_track!r}; use another "
                         f"folder or --force")
    out.mkdir(parents=True, exist_ok=True)
    todo = [t for t in tasks if ids is None or t.id in ids]
    made = []
    for t in todo:
        t0 = time.monotonic()
        if track == "frames":
            n = F.draw_stills([t], out)[0]
            made.append(out / "sheets" / t.id)
            print(f"  drew {t.video} ({t.seconds:g} s) as {n} stills in {time.monotonic() - t0:.1f} s")
        else:
            made.append(t.draw(out / t.video))
            print(f"  drew {t.video} ({t.seconds:g} s) in {time.monotonic() - t0:.1f} s")
    if track == "frames":
        shutil.rmtree(out / ".partial", ignore_errors=True)
    media.write_text_atomic(out / "TASKS.md", tasks_md(suite, track, out))
    if answered:
        print(f"  kept {ans} (it already has answers; --force writes a blank one)")
    else:
        blank = {"suite": suite, "track": track, "answers": {t.id: None for t in tasks}}
        if track == F.TRACK:
            del blank["track"]          # a code-track answers.json stays as it always was
        media.write_json_atomic(ans, blank)
    return made


def cmd_prepare(argv) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench prepare",
                                 description="Draw the suite's videos and write TASKS.md and answers.json.")
    ap.add_argument("--out", required=True, type=Path, help="folder to write (created if missing)")
    ap.add_argument("--suite", default=SUITE, choices=sorted(S.SUITES),
                    help=f"which suite to draw (default {SUITE}; svc-bench-2 is the hard one)")
    ap.add_argument("--track", default=F.TRACK, choices=F.TRACKS,
                    help="code (default): videos, any tool; frames: still images only, for review by eye")
    ap.add_argument("--force", action="store_true", help="overwrite an answers.json that already has answers")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    what = "videos" if a.track == F.TRACK else "videos as stills"
    print(f"{a.suite}: drawing {len(S.SUITES[a.suite].TASKS)} {what} into {a.out.resolve()}")
    prepare(a.out, force=a.force, suite=a.suite, track=a.track)
    print(f"done in {time.monotonic() - t0:.1f} s. Next: let the agent read {a.out / 'TASKS.md'} and fill "
          f"{a.out / 'answers.json'}, then `sports-video-coach bench score {a.out} --agent ... --model ...`")
    return 0


def cmd_score(argv) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench score",
                                 description="Score <dir>/answers.json and write a schema-1 result file.")
    ap.add_argument("dir", type=Path, help="the folder `bench prepare` wrote and the agent answered in")
    ap.add_argument("--agent", required=True, help='the coding agent, e.g. "Claude Code" (or "script")')
    ap.add_argument("--agent-version", default="", help="its version, if known")
    ap.add_argument("--model", required=True, help='the model behind it, e.g. "claude-opus-5-5" ("" if none)')
    ap.add_argument("--settings", default="", help='free text, e.g. "effort medium"')
    ap.add_argument("--by", default="", help="GitHub handle of who ran it")
    ap.add_argument("--wall-seconds", type=float, default=None, help="how long the agent took")
    ap.add_argument("--evidence", default="", help="URL of a transcript, gist or PR")
    ap.add_argument("--out", type=Path, default=None,
                    help="result file (default benchmark/results/<date>-<agent>-<model>[-<suite>][-frames].json; "
                         "svc-bench-1 files have no suite suffix)")
    a = ap.parse_args(argv)
    if not a.agent.strip():
        ap.error("--agent must not be empty")
    ws = a.wall_seconds
    res = S.result(S.read_answers(a.dir), a.agent.strip(), a.model.strip(), a.agent_version.strip(),
                   a.settings.strip(), a.by.strip(), int(ws) if ws is not None and ws == int(ws) else ws,
                   a.evidence.strip(), suite=S.answers_suite(a.dir), track=S.answers_track(a.dir))
    out = a.out or S.default_path(res)
    out.parent.mkdir(parents=True, exist_ok=True)
    media.write_json_atomic(out, res)
    print(S.table(res))
    print(f"\nwrote {out}")
    from .run import issue_url
    print("submit it: add it to benchmark/results/ in a pull request, or open the prefilled issue form:")
    print(issue_url(res))
    return 0


def cmd_validate(argv) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench validate",
                                 description="Re-score result files; exit 1 if any is broken or was edited.")
    ap.add_argument("files", nargs="+", type=Path)
    a = ap.parse_args(argv)
    bad = 0
    for f in a.files:
        errs = S.validate_file(f)
        if errs:
            bad += 1
            print(f"{f}: INVALID")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"{f}: ok")
    return 1 if bad else 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    cmds = {"prepare": cmd_prepare, "score": cmd_score, "validate": cmd_validate}
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    if argv[0] == "page":
        from .page import main as page_main
        return page_main(argv[1:])
    if argv[0] == "run":
        from .run import main as run_main
        return run_main(argv[1:])
    if argv[0] == "baseline":
        from .baseline import main as baseline_main
        return baseline_main(argv[1:])
    if argv[0] not in cmds:
        print(f"unknown bench command {argv[0]!r}; one of: prepare, score, validate, page, run", file=sys.stderr)
        return 2
    return cmds[argv[0]](argv[1:])
