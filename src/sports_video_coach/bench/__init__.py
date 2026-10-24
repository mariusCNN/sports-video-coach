"""`sports-video-coach bench`: a reproducible benchmark of agents and models as sports film reviewers.

Suite `svc-bench-1`: short drawn videos whose truth is exact (we drew them). Run it with any agent:

  sports-video-coach bench prepare --out <dir>     videos, TASKS.md and an answers.json to fill
  (your agent watches the videos and fills <dir>/answers.json; it must not read the package source or any truth)
  sports-video-coach bench score <dir> --agent A --model M [--agent-version V] [--settings S] [--by HANDLE]
                                [--wall-seconds N] [--evidence URL] [--out FILE]
  sports-video-coach bench validate <result.json...>   re-score a result file; exit 1 if it was edited or broken
  sports-video-coach bench page ...                     the leaderboard page from benchmark/results/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .. import media
from . import score as S
from .suite import SUITE, TASKS

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


def tasks_md() -> str:
    parts = []
    for i, t in enumerate(TASKS, 1):
        parts.append(f"### {i}. `{t.id}` ({t.kind}) - video `{t.video}`, {t.seconds:g} s\n\n{t.question}\n\n"
                     f"Answer: {t.answer_format}.")
    return TASKS_MD.format(suite=SUITE, tasks="\n\n".join(parts))


def prepare(out: Path, ids: list[str] | None = None, force: bool = False) -> list[Path]:
    """Draw the videos and write TASKS.md and an answers.json template into `out`. No truth is written.
    An answers.json that already holds an answer is kept unless `force`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    todo = [t for t in TASKS if ids is None or t.id in ids]
    videos = []
    for t in todo:
        t0 = time.monotonic()
        videos.append(t.draw(out / t.video))
        print(f"  drew {t.video} ({t.seconds:g} s) in {time.monotonic() - t0:.1f} s")
    media.write_text_atomic(out / "TASKS.md", tasks_md())
    ans = out / "answers.json"
    old = {}
    if ans.exists() and not force:
        try:
            old = json.loads(ans.read_text(encoding="utf8")).get("answers", {}) or {}
        except (ValueError, AttributeError):
            old = {}
    if any(v is not None for v in old.values()):
        print(f"  kept {ans} (it already has answers; --force writes a blank one)")
    else:
        media.write_json_atomic(ans, {"suite": SUITE, "answers": {t.id: None for t in TASKS}})
    return videos


def cmd_prepare(argv) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench prepare",
                                 description="Draw the suite's videos and write TASKS.md and answers.json.")
    ap.add_argument("--out", required=True, type=Path, help="folder to write (created if missing)")
    ap.add_argument("--force", action="store_true", help="overwrite an answers.json that already has answers")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    print(f"{SUITE}: drawing {len(TASKS)} videos into {a.out.resolve()}")
    prepare(a.out, force=a.force)
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
                    help="result file (default benchmark/results/<date>-<agent>-<model>.json)")
    a = ap.parse_args(argv)
    if not a.agent.strip():
        ap.error("--agent must not be empty")
    ws = a.wall_seconds
    res = S.result(S.read_answers(a.dir), a.agent.strip(), a.model.strip(), a.agent_version.strip(),
                   a.settings.strip(), a.by.strip(), int(ws) if ws is not None and ws == int(ws) else ws,
                   a.evidence.strip())
    out = a.out or S.default_path(res)
    out.parent.mkdir(parents=True, exist_ok=True)
    media.write_json_atomic(out, res)
    print(S.table(res))
    print(f"\nwrote {out}")
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
    if argv[0] not in cmds:
        print(f"unknown bench command {argv[0]!r}; one of: prepare, score, validate, page", file=sys.stderr)
        return 2
    return cmds[argv[0]](argv[1:])
