"""`sports-video-coach bench report <result.json...> [--results DIR]`: a result file's score as Markdown.

For each file: whether it validates (`bench validate`'s checks), then its suite, track, seed, contender, total,
above chance, time, cost and where it would rank on its table, and per task the answer, the truth (from the
suite, not from the file), the score and what was missed. Every number comes from the same code as the
leaderboard page (`bench.page`), against the floor the page would use (the latest blind baseline of the same
suite and track in `--results`, or the file's own seed's floor), so the report shows what the page will show.
CI appends it to a pull request's checks summary; run it locally first to see the same report. Exit 1 when a file
does not validate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import page as P
from .score import validate_file

RESULTS = Path("benchmark") / "results"


def md(v) -> str:
    """Text safe inside a Markdown table cell: no newlines, pipes, HTML or code spans."""
    s = re.sub(r"\s+", " ", "" if v is None else str(v)).strip()
    return s.replace("\\", "\\\\").replace("|", "\\|").replace("`", "'").replace("<", "&lt;").replace(">", "&gt;")


def contender(r: dict) -> str:
    c = r["contender"]
    head = str(c.get("agent") or "") + (f" {c['agent_version']}" if c.get("agent_version") else "")
    return head + (f" / {c['model']}" if c.get("model") else "") + (f" ({c['settings']})" if c.get("settings") else "")


def board(r: dict, rows: list[dict]) -> tuple[list[dict], dict | None]:
    """(the other runs on `r`'s table, the floor row the page measures it against), from the loaded result files."""
    same = [x for x in rows if P.suite_of(x) == P.suite_of(r) and P.track_of(x) == P.track_of(r)]
    others = [x for x in same if not P.is_baseline(x) and x["_file"] != r["_file"]]
    return others, P.floor_of(same)


def rank(r: dict, others: list[dict]) -> tuple[int, int]:
    """(place, runs) of `r` on its table of every run, ranked as the page ranks it: total, then earlier date."""
    key = lambda x: (-float(x["total"]), str(x.get("date", "")), x["_file"])   # noqa: E731
    shown = sorted(others + [r], key=key)
    return shown.index(r) + 1, len(shown)


def answer_text(kind: str, task: dict) -> str:
    if "answer" not in task:
        return P.NOT_RECORDED
    a = task["answer"]
    if kind == "timestamps" and isinstance(a, list) and all(P.is_num(x) for x in a):
        return f"{P.show_value(kind, a)}: {', '.join(f'{float(x):g}' for x in a)} s"
    if kind == "outcomes" and isinstance(a, list):
        return f"{P.show_value(kind, a)}: {' '.join('M' if str(x).strip().lower() == 'made' else 'x' for x in a)}"
    return P.show_value(kind, a) if P.is_num(a) or a is None else json.dumps(a)


def report_one(path: Path, rows: list[dict]) -> tuple[str, bool]:
    """(the Markdown section of one result file, whether it validates)."""
    name = Path(path).name
    errs = validate_file(path)
    if errs:
        lines = [f"### `{md(name)}`: does not validate", ""] + [f"- {md(e)}" for e in errs]
        lines += ["", "Fix the file (or rerun `sports-video-coach bench score`) and push again; "
                      "`sports-video-coach bench validate <file>` checks it locally."]
        return "\n".join(lines), False
    r = json.loads(Path(path).read_text(encoding="utf8"))
    r["_file"] = name
    others, floor_row = board(r, rows)
    floor = {str(t["id"]): t.get("score") for t in floor_row["tasks"]} if floor_row else None
    above = P.above_value(r, floor)
    if r.get("seed") is not None:
        floor_from = f"the blind baseline on seed {r['seed']}"
    else:
        floor_from = f"`{md(floor_row['_file'])}`" if floor_row else "no blind baseline file for this suite and track"
    place, n = rank(r, others)
    ws, cost = r.get("wall_seconds"), r.get("cost_usd")
    ev = str(r.get("evidence") or "")
    lines = [f"### `{md(name)}`: validates", "",
             "| | |", "|---|---|",
             f"| Suite | {md(r.get('suite') or P.SUITE)} |",
             f"| Track | {md(P.track_of(r))} |"]
    if r.get("seed") is not None:
        lines.append(f"| Seed | {md(r['seed'])} (fresh, listed under {md(P.suite_of(r))}) |")
    lines += [f"| Contender | {md(contender(r))} |",
              f"| Submitted by | {md(r.get('submitted_by') or '-')} |",
              f"| Date | {md(r.get('date'))} |",
              f"| Total | **{float(r['total']):.3f}** |",
              f"| Above chance | {'-' if above is None else f'**{above:.3f}**'} (floor: {floor_from}) |",
              f"| Time | {P.wall(float(ws)) if P.is_num_value(ws) else '-'} |",
              f"| Cost | {P.usd(float(cost)) if P.is_num_value(cost) else '-'} |",
              f"| Evidence | {md(ev) if ev.startswith(('https://', 'http://')) else '-'} |"]
    if not P.is_baseline(r):
        lines.append(f"| Rank by total | {place} of {n} runs on its table |")
    lines += ["", "| Task | Kind | Answer | Truth | Score | What was missed |", "|---|---|---|---|---:|---|"]
    tasks = P.suite_tasks(str(r.get("suite") or P.SUITE), r.get("seed")).BY_ID
    for t in r["tasks"]:
        st = tasks[str(t["id"])]
        miss = P.diff_answer(st.kind, st.truth, t) or "-"
        lines.append(f"| {md(t['id'])} | {st.kind} | {md(answer_text(st.kind, t))} | "
                     f"{md(P.show_truth(st.kind, st.truth))} | {float(t['score']):.3f} | {md(miss)} |")
    return "\n".join(lines), True


def report(paths: list[Path], results: Path = RESULTS) -> tuple[str, bool]:
    """(the Markdown report of every file, whether all of them validate)."""
    rows, _ = P.load(Path(results))
    parts, ok = ["## Benchmark result check", ""], True
    if not paths:
        parts.append("No result file in `benchmark/results/` was added or changed.")
    for p in paths:
        text, good = report_one(Path(p), rows)
        parts += [text, ""]
        ok = ok and good
    parts.append("Scored by `sports-video-coach bench report` with the leaderboard page's code; the page shows the "
                 "same numbers once the file is merged.")
    return "\n".join(parts) + "\n", ok


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench report", description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", type=Path, help="result files (none: a report saying nothing changed)")
    ap.add_argument("--results", type=Path, default=RESULTS,
                    help=f"the folder of result files that holds the floors and the other runs (default {RESULTS})")
    a = ap.parse_args(argv)
    text, ok = report(a.files, a.results)
    sys.stdout.buffer.write(text.encode("utf8"))
    sys.stdout.flush()
    return 0 if ok else 1
