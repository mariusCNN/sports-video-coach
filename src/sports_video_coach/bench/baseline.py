"""The blind baseline: the floor of the benchmark, a guesser that answers every task without seeing any video.

  sports-video-coach bench baseline --suite svc-bench-2 [--track frames] [--seed N] [--date D] [--out FILE]

It reads only the text a contender is given (`TASKS.md` for that suite and track, built by `bench.tasks_md`) and
answers each task from it, with no prior of its own and nothing tuned to the truth:

- count, rate, timestamps: the example answer printed in the task's "Answer:" line (`5`, `30.5`, `[1.5, 4.25]`).
- outcomes: the example's pattern (`"made", "missed"`) repeated to the number of strings the "Answer:" line asks for.

It then scores those answers with the normal scorer and writes a normal schema-1 result file whose agent is
"blind baseline" (`score.BASELINE_AGENT`). The leaderboard reads that file's per-task scores as the floor of the
"above chance" score. The guesser is deterministic: the same suite and track always give the same answers.
A fresh seed (`--seed`) changes the counts the task text states (the number of shots), so a run on a fresh seed
gets its own floor: the leaderboard computes it from the run's seed with `result(..., seed=N)` and never stores it.
A guesser that knows sport (a typical running cadence, say) can score higher, so this floor is a lower bound on
what guessing gets.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from itertools import cycle, islice
from pathlib import Path

from .. import media
from . import frames as F, score as S, tasks_md
from .suite import SUITE

SETTINGS = "answers copied from the TASKS.md examples; no video or still seen"
_HEAD = re.compile(r"^### \d+\. `([^`]+)` \((\w+)\)", re.M)
_EXAMPLE = re.compile(r"e\.g\. `([^`]+)`")
_COUNT = re.compile(r"a list of (\d+) strings")


def sections(md: str) -> dict[str, tuple[str, str]]:
    """{task id: (kind, the task's text)} from a TASKS.md."""
    heads = list(_HEAD.finditer(md))
    out = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        out[h.group(1)] = (h.group(2), md[h.end():nxt.start() if nxt else len(md)])
    return out


def guess(kind: str, text: str):
    """The blind answer to one task, from its text only (None when the text gives no example)."""
    line = next((ln for ln in text.splitlines() if ln.startswith("Answer:")), "")
    ex = _EXAMPLE.search(line)
    if not ex:
        return None
    if kind == "outcomes":
        pattern = re.findall(r'"([^"]+)"', ex.group(1))
        n = _COUNT.search(line)
        if not pattern or not n:
            return None
        return list(islice(cycle(pattern), int(n.group(1))))
    try:
        return json.loads(ex.group(1))
    except ValueError:
        return None


def answers(suite: str = SUITE, track: str = F.TRACK, seed: int | None = None) -> dict:
    """{task id: blind answer} for every task of the suite (drawn from `seed`), from that TASKS.md text."""
    by_id = sections(tasks_md(suite, track, seed=seed))
    return {t.id: guess(*by_id[t.id]) if t.id in by_id else None for t in S.suite_tasks(suite, seed).TASKS}


def result(suite: str = SUITE, track: str = F.TRACK, date: str | None = None, seed: int | None = None) -> dict:
    return S.result(answers(suite, track, seed), S.BASELINE_AGENT, "", settings=SETTINGS, date=date, suite=suite,
                    track=track, seed=seed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench baseline",
                                 description="Score the blind baseline (answers from the task text only) and write "
                                             "a result file.")
    ap.add_argument("--suite", default=SUITE, choices=sorted(S.SUITES))
    ap.add_argument("--track", default=F.TRACK, choices=F.TRACKS)
    ap.add_argument("--seed", type=int, default=None, help="the floor of a fresh seed (svc-bench-3 only)")
    ap.add_argument("--date", default=None, help="date in the result file (default today)")
    ap.add_argument("--out", type=Path, default=None,
                    help="result file (default benchmark/results/<date>-blind-baseline[-<suite>][-frames].json)")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        S.suite_tasks(a.suite, a.seed)
    except ValueError as e:
        ap.error(f"--seed: {e}")
    res = result(a.suite, a.track, a.date, a.seed)
    out = a.out or S.default_path(res)
    out.parent.mkdir(parents=True, exist_ok=True)
    media.write_json_atomic(out, res)
    print(S.table(res))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
