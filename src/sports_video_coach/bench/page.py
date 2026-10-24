"""`sports-video-coach bench page <results_dir> <out_dir>`: the public benchmark leaderboard.

Reads every `*.json` result file in `<results_dir>` (schema 1, written by `bench score`) and writes
`<out_dir>/index.html`: a self-contained static page (inline CSS, light and dark, readable at 390 px) with the
leaderboard ranked by total (above it, a summary per contender: runs, mean total, mean and range of above
chance), with an "above chance" score next to it (the floor is the blind baseline's result
file of that suite and track, `bench.baseline`, shown as a marked row under the ranked ones; under it a folded
"Where each contender fails" block: per task the suite's truth, each run's stored answer, the recomputed score and
what was missed) (one table per suite, the hard suite first; runs on the frames-only track, which
see still images and run no code, in their own tables below), the method, how to run it yourself, how to submit a
run and honesty notes, and `card.png`, the share card link previews show (`bench.card`, needs matplotlib; the
page's `og:image` points at it). With no
results it shows a "no runs yet" state; a file that does not parse is skipped and named in a visible note. The page
never invents a row: every number on it comes from a result file.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from . import card as share_card
from . import clip as share_clip
from . import run as bench_run
from .score import BASELINE_AGENT, SUITES as TRUTH_SUITES, above_chance, is_num, score_task

OWNER = "mariusDing"           # the repo owner, who also wrote the tool and submitted its first runs
REPO_URL = f"https://github.com/{OWNER}/sports-video-coach"
DOC_URL = f"{REPO_URL}/blob/master/docs/benchmark.md"
RESULTS_URL = f"{REPO_URL}/tree/master/benchmark/results"
ISSUE_URL = f"{REPO_URL}/issues/new?template=benchmark_result.yml"
PAGE_URL = "https://mariusding.github.io/sports-video-coach/benchmark/"   # where the demo-site CI publishes it
SUITE = "svc-bench-1"          # a result file without a suite field is from suite 1
SUITES = (                     # (name, what it is), shown in this order; unknown suites follow by name
    ("svc-bench-3", "Eyes: four drawn videos whose events are small, short or hidden: a ball 5 px in radius on a "
                    "640x360 frame, a ball 3 px in radius at a 16 px wide far rim, double touches 0.24 s apart, a "
                    "banner and a defender in front of the moment, pass fakes, and decoys with nearly the same answer (a second juggler, a second pair passing, a far boat "
                    "at a close rate)."),
    ("svc-bench-2", "Hard: five drawn videos with a hand-held camera, look-alike decoys (a second ball, two "
                    "identical feet, a rebounder), rule-defined events and noise."),
    ("svc-bench-1", "Four short drawn videos on a still camera."),
)
TRACK = "code"                 # a result file without a track field is on the code track
FRAMES = ("Frames-only track: the agent sees still images of each video (contact sheets with the time under every "
          "still) and has no tool that runs code, so it must review by eye. Same videos, same truth, same scoring "
          "as the code track. The scores measure what the model saw and how much it looked: a model that opens few "
          "stills guesses, and a guess can score well.")
ABOVE = ("Above chance: per task, (score - floor) / (1 - floor), clipped to 0..1, where the floor is the score of "
         "the blind baseline (it copies the example answers from the task text and sees no video); 0 = no better "
         "than that guess, 1 = perfect.")
COSTS = ("Time = wall seconds the run took; cost = USD the agent itself reported (Claude Code does, Codex does "
         "not); '-' = not recorded.")
SUMMARY = ("n = runs of that agent, model and settings; range = lowest to highest above-chance total over them "
           "(a dash for a single run). A run whose settings only add a note (such as being killed at the time "
           "limit) counts with its contender.")
TITLE = "Sports film review benchmark"
WHAT = ("Which coding agent and vision model reviews sports film best, on synthetic drills? Each run is scored "
        "against ground truth the tool drew into the videos, so every number is measured, not judged.")

KINDS = (
    ("count", "How many reps, bounces or shots.", "1 - |error| / truth, never below 0."),
    ("rate", "A cadence or a percentage.", "1 within 2 % of the truth, falling linearly to 0 at 20 %."),
    ("timestamps", "When each event happens.",
     "Per event: 1 within 0.5 s, linear to 0 at 2 s, 0 if missing; summed and divided by the longer of the truth "
     "and answer lists, so extra events cost too."),
    ("outcomes", "Made or missed, in order.", "Fraction of positions answered correctly."),
)
COMMANDS = (
    ("Install (needs ffmpeg on PATH)", f"uv tool install git+{REPO_URL}"),
    ("Make the tasks: videos and an empty answers.json (the newest suite; leave out --suite for svc-bench-1)",
     "sports-video-coach bench prepare --out bench-run --suite svc-bench-3"),
    ("Let your agent watch the videos and fill bench-run/answers.json, then score it",
     'sports-video-coach bench score bench-run --agent "Your agent" --model "your-model"'),
)

CSS = """
:root { --bg: #f6f5fb; --card: #fff; --ink: #1d1b38; --muted: #5c5a86; --line: #e2e0ef; --accent: #3b36a8;
        --code-bg: #221f45; --code-ink: #fff; --good: #1d7a46; --warn-bg: #fff4d6; --warn-ink: #6b4d00;
        color-scheme: light; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg: #14132a; --card: #1e1c3b; --ink: #ecebf7; --muted: #a9a7cc;
    --line: #34315c; --accent: #a9a4ff; --code-bg: #0c0b1c; --code-ink: #ecebf7; --good: #6ad79b;
    --warn-bg: #3b3115; --warn-ink: #f3d98b; color-scheme: dark; }
}
:root[data-theme="dark"] { --bg: #14132a; --card: #1e1c3b; --ink: #ecebf7; --muted: #a9a7cc; --line: #34315c;
  --accent: #a9a4ff; --code-bg: #0c0b1c; --code-ink: #ecebf7; --good: #6ad79b; --warn-bg: #3b3115;
  --warn-ink: #f3d98b; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font: 17px/1.55 system-ui, sans-serif; color: var(--ink); background: var(--bg); }
main { max-width: 52rem; margin: 0 auto; padding: 1.6rem 16px 3rem; }
a { color: var(--accent); }
.name { font-weight: 700; color: var(--muted); margin: 0; }
.name a { color: inherit; text-decoration: none; }
h1 { font-size: clamp(1.5rem, 5vw, 2.2rem); line-height: 1.2; margin: .2rem 0 .6rem; }
h2 { font-size: 1.2rem; margin: 2.2rem 0 .6rem; }
h3 { font-size: 1rem; margin: 0 0 .2rem; }
h4 { font-size: .9rem; margin: .9rem 0 .3rem; }
.lead { margin: 0 0 1rem; max-width: 40rem; }
.chips { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0; padding: 0; list-style: none; }
.chips li { font-size: .85rem; padding: .15rem .6rem; border-radius: 999px; background: var(--card);
            border: 1px solid var(--line); }
.scroll { overflow-x: auto; background: var(--card); border-radius: 10px; border: 1px solid var(--line); }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { padding: .5rem .6rem; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: .8rem; color: var(--muted); font-weight: 600; }
tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.total { font-weight: 700; color: var(--good); }
td.above { font-weight: 700; }
tr.floor td { background: var(--warn-bg); color: var(--warn-ink); }
td.sub { color: var(--muted); font-size: .85rem; }
.empty { background: var(--card); border: 1px dashed var(--line); border-radius: 10px; padding: 1.2rem 1rem; }
.empty p { margin: .2rem 0; }
.note { background: var(--warn-bg); color: var(--warn-ink); border-radius: 10px; padding: .7rem 1rem;
        margin: .8rem 0; font-size: .9rem; }
.note ul { margin: .3rem 0 0; padding-left: 1.2rem; }
.cards { display: grid; gap: .7rem; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); }
.cards section { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: .8rem 1rem; }
.cards p { margin: .2rem 0; font-size: .92rem; }
.cards .rule { color: var(--muted); }
ol.steps { padding-left: 1.3rem; }
ol.steps li { margin-bottom: .8rem; }
pre { background: var(--code-bg); color: var(--code-ink); border-radius: 10px; padding: .7rem 1rem;
      overflow-x: auto; font-size: .85rem; margin: .3rem 0 0; }
ul.plain { padding-left: 1.2rem; }
ul.plain li { margin-bottom: .3rem; }
footer { margin-top: 2.4rem; color: var(--muted); font-size: .85rem; }
details.fails { margin: 1rem 0 0; background: var(--card); border: 1px solid var(--line); border-radius: 10px;
                padding: .5rem .8rem; }
details.fails summary { cursor: pointer; font-weight: 600; }
details.fails h5 { font-size: .9rem; margin: 1rem 0 .2rem; }
details.fails p.truth { margin: 0 0 .4rem; font-size: .88rem; overflow-wrap: anywhere; }
td.why { white-space: normal; min-width: 11rem; overflow-wrap: anywhere; }
tr.miss td.why { color: var(--warn-ink); background: var(--warn-bg); }
details.facts { margin: 1rem 0 0; background: var(--warn-bg); color: var(--warn-ink); border-radius: 10px;
                padding: .5rem .9rem; font-size: .92rem; }
details.facts summary { cursor: pointer; font-weight: 600; }
details.facts ul { margin: .4rem 0 .2rem; padding-left: 1.1rem; }
details.facts li { margin-bottom: .35rem; }
details.prompt { margin: .8rem 0; }
details.prompt summary { cursor: pointer; font-weight: 600; }
pre.wrap { white-space: pre-wrap; overflow-wrap: anywhere; }
.kind { font-size: .75rem; font-weight: 400; color: var(--muted); border: 1px solid var(--line);
        border-radius: 999px; padding: 0 .45rem; margin-left: .3rem; }
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def load(results_dir: Path) -> tuple[list[dict], list[str]]:
    """(rows, notes): the result files that parse as schema 1, and one note per file skipped and why."""
    rows, notes = [], []
    files = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            notes.append(f"{f.name}: not valid JSON ({type(e).__name__})")
            continue
        why = problem(data)
        if why:
            notes.append(f"{f.name}: {why}")
            continue
        data["_file"] = f.name
        rows.append(data)
    rows.sort(key=lambda r: (-float(r["total"]), str(r.get("date", "")), r["_file"]))
    return rows, notes


def problem(data) -> str:
    """Why a parsed file cannot be shown ('' when it can)."""
    if not isinstance(data, dict):
        return "not a JSON object"
    if data.get("schema") != 1:
        return f"schema {data.get('schema')!r}, this page reads schema 1"
    if not isinstance(data.get("contender"), dict):
        return "no contender block"
    total = data.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not 0 <= total <= 1:
        return "total is not a number from 0 to 1"
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(t, dict) and "id" in t for t in tasks):
        return "tasks is not a list of tasks with ids"
    return ""


def task_ids(rows: list[dict]) -> list[str]:
    """Every task id, in the order the rows first list them."""
    ids: list[str] = []
    for r in rows:
        for t in r["tasks"]:
            if str(t["id"]) not in ids:
                ids.append(str(t["id"]))
    return ids


def score_cell(v) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return '<td class="num sub">-</td>'
    return f'<td class="num">{v:.2f}</td>'


def evidence(url) -> str:
    url = str(url or "")
    if not url.startswith(("https://", "http://")):
        return '<td class="sub">-</td>'
    label = "transcript" if "/benchmark/transcripts/" in url else "link"
    return f'<td><a href="{esc(url)}" rel="nofollow noopener">{label}</a></td>'


def is_baseline(r: dict) -> bool:
    """A blind-baseline result file: the floor, not a contender."""
    return r["contender"].get("agent") == BASELINE_AGENT


def above_value(r: dict, floor: dict | None) -> float | None:
    return above_chance([{"id": str(t["id"]), "score": t.get("score")} for t in r["tasks"]], floor) if floor else None


def above_cell(r: dict, floor: dict | None) -> str:
    v = above_value(r, floor)
    if v is None:
        return '<td class="num sub">-</td>'
    return f'<td class="num above">{v:.3f}</td>'


def table(rows: list[dict], floor_row: dict | None = None) -> str:
    """The ranked rows of one suite and track, then the blind baseline's row (`floor_row`) marked as the floor.
    Without a floor row the above-chance column shows '-'."""
    shown = rows + ([floor_row] if floor_row else [])
    ids = task_ids(shown)
    floor = {str(t["id"]): t.get("score") for t in floor_row["tasks"]} if floor_row else None
    head = "".join(f'<th class="num" scope="col">{esc(i)}</th>' for i in ids)
    body = []
    for rank, r in enumerate(shown, 1):
        c = r["contender"]
        base = r is floor_row
        agent = esc(c.get("agent", "")) + (f' <span class="sub">{esc(c["agent_version"])}</span>'
                                           if c.get("agent_version") else "")
        if base:
            agent = f"<strong>Floor:</strong> {agent} (no video seen)"
        scores = {str(t["id"]): t.get("score") for t in r["tasks"]}
        who = esc(r.get("submitted_by") or "-")
        tr = '<tr class="floor">' if base else "<tr>"
        body.append(
            f'{tr}<td class="num">{"floor" if base else rank}</td><td>{agent}</td>'
            f'<td>{esc(c.get("model") or "-")}</td><td class="sub">{esc(c.get("settings") or "-")}</td>'
            + "".join(score_cell(scores.get(i)) for i in ids)
            + f'<td class="num total">{float(r["total"]):.3f}</td>{above_cell(r, floor)}'
            f'{num_cell(r.get("wall_seconds"), wall)}{num_cell(r.get("cost_usd"), usd)}'
            f'<td>{esc(r.get("date", ""))}</td><td>{who}</td>{evidence(r.get("evidence"))}</tr>')
    return (f'<div class="scroll"><table><thead><tr><th class="num" scope="col">#</th><th scope="col">Agent</th>'
            f'<th scope="col">Model</th><th scope="col">Settings</th>{head}<th class="num" scope="col">Total</th>'
            f'<th class="num" scope="col">Above chance</th>'
            f'<th class="num" scope="col">Time</th><th class="num" scope="col">Cost</th>'
            f'<th scope="col">Date</th><th scope="col">Submitter</th><th scope="col">Evidence</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">Scores 0 to 1 per task; total = mean. '
            f'Ranked by total, then earlier date. {esc(ABOVE)} {esc(COSTS)} '
            f'Raw files: <a href="{RESULTS_URL}">benchmark/results</a>.</p>')


def is_num_value(v) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float))


def wall(v: float) -> str:
    return f"{v:.0f} s"


def usd(v: float) -> str:
    return f"${v:.2f}"


def num_cell(v, fmt) -> str:
    """A time or cost cell: '-' when the run did not record it."""
    return f'<td class="num">{fmt(float(v))}</td>' if is_num_value(v) else '<td class="num sub">-</td>'


def mean_of(runs: list[dict], field: str) -> tuple[float | None, int]:
    """(mean of `field` over the runs that recorded it, how many did)."""
    vals = [float(r[field]) for r in runs if is_num_value(r.get(field))]
    return (sum(vals) / len(vals) if vals else None), len(vals)


def contender_key(r: dict) -> tuple[str, str, str]:
    c = r["contender"]
    return str(c.get("agent") or ""), str(c.get("model") or ""), str(c.get("settings") or "")


def merge_notes(keys: list[tuple[str, str, str]]) -> dict[tuple[str, str, str], tuple[str, str, str]]:
    """Each key mapped to the contender it belongs to: a run whose settings are another run's settings of the same
    agent and model plus a note ("...; killed at the time limit") is the same contender, so its failure counts in
    that contender's mean instead of standing apart."""
    out = {}
    for k in keys:
        bases = [b for b in keys if b[:2] == k[:2] and b[2] and k[2].startswith(b[2] + "; ")]
        out[k] = min(bases, key=lambda b: len(b[2])) if bases else k
    return out


def summarize(rows: list[dict], floor_row: dict | None = None) -> list[dict]:
    """One entry per contender (agent + model + settings) of the given runs: n, mean total, and the mean, min and
    max above chance (None without a floor). Ranked by mean above chance, then mean total, then name. The blind
    baseline is never a contender."""
    floor = {str(t["id"]): t.get("score") for t in floor_row["tasks"]} if floor_row else None
    runs_ = [r for r in rows if not is_baseline(r)]
    to = merge_notes(sorted({contender_key(r) for r in runs_}))
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in runs_:
        groups.setdefault(to[contender_key(r)], []).append(r)
    out = []
    for key, runs in groups.items():
        above = [v for v in (above_value(r, floor) for r in runs) if v is not None]
        secs_, n_secs = mean_of(runs, "wall_seconds")
        cost, n_cost = mean_of(runs, "cost_usd")
        out.append({"key": key, "n": len(runs), "total": sum(float(r["total"]) for r in runs) / len(runs),
                    "above": sum(above) / len(above) if above else None,
                    "lo": min(above) if above else None, "hi": max(above) if above else None,
                    "secs": secs_, "n_secs": n_secs, "cost": cost, "n_cost": n_cost})
    out.sort(key=lambda s: (s["above"] is None, -(s["above"] or 0), -s["total"], s["key"]))
    return out


def ranks(summary: list[dict]) -> list[str]:
    """Shown ranks: entries with the same mean above chance and mean total (to 3 decimals) share a rank, marked '='."""
    keys = [(None if s["above"] is None else round(s["above"], 3), round(s["total"], 3)) for s in summary]
    return [f"{keys.index(k) + 1}{'=' if keys.count(k) > 1 else ''}" for k in keys]


def summary_table(rows: list[dict], floor_row: dict | None = None) -> str:
    """The per-contender summary of one suite and track, shown above its table of every run."""
    body = []
    summary = summarize(rows, floor_row)
    for rank, s in zip(ranks(summary), summary):
        agent, model, settings = s["key"]
        above = (f'<td class="num above">{s["above"]:.3f}</td>' if s["above"] is not None
                 else '<td class="num sub">-</td>')
        spread = (f'<td class="num">{s["lo"]:.3f}&ndash;{s["hi"]:.3f}</td>' if s["n"] > 1 and s["lo"] is not None
                  else '<td class="num sub">-</td>')
        body.append(f'<tr><td class="num">{rank}</td><td>{esc(agent)}</td><td>{esc(model or "-")}</td>'
                    f'<td class="sub">{esc(settings or "-")}</td><td class="num">{s["n"]}</td>'
                    f'<td class="num total">{s["total"]:.3f}</td>{above}{spread}'
                    f'{part_mean(s["secs"], s["n_secs"], s["n"], wall)}'
                    f'{part_mean(s["cost"], s["n_cost"], s["n"], usd)}</tr>')
    return ('<h4>Summary</h4><div class="scroll"><table class="summary"><thead><tr>'
            '<th class="num" scope="col">#</th><th scope="col">Agent</th><th scope="col">Model</th>'
            '<th scope="col">Settings</th><th class="num" scope="col">Runs (n)</th>'
            '<th class="num" scope="col">Mean total</th><th class="num" scope="col">Mean above chance</th>'
            '<th class="num" scope="col">Range</th><th class="num" scope="col">Mean time</th>'
            '<th class="num" scope="col">Mean cost</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">Ranked by mean above chance; '
            f'&ldquo;=&rdquo; marks a tie. {esc(SUMMARY)} {esc(COSTS)}</p><h4>Every run</h4>')


def part_mean(v, n_with: int, n: int, fmt) -> str:
    """A mean time or cost cell, with '(k of n)' when only some runs recorded it."""
    if v is None:
        return '<td class="num sub">-</td>'
    part = f' <span class="sub">({n_with} of {n})</span>' if n_with < n else ""
    return f'<td class="num">{fmt(v)}{part}</td>'


def suite_of(r: dict) -> str:
    return str(r.get("suite") or SUITE)


def track_of(r: dict) -> str:
    return str(r.get("track") or TRACK)


def floor_of(rows: list[dict]) -> dict | None:
    """The floor of one suite and track's rows: its latest blind-baseline result file, or None."""
    base = [r for r in rows if is_baseline(r)]
    return max(base, key=lambda r: (str(r.get("date", "")), r["_file"])) if base else None


NOT_RECORDED = "answer not recorded"
FAILS = ("Every contender run, task by task: the truth (from the suite), each run's answer as its result file stores "
         "it, the score recomputed from the two, and what was missed. The blind baseline is left out. Timestamps: an "
         "event not answered within 0.5 s still earns part of its point up to 2 s off; an unmatched answer is one "
         "with no event within 0.5 s.")
SHOW = 4                       # list diffs name at most this many times or positions, then "+N more"


def secs(v: float) -> str:
    return f"{float(v):g} s"


def some(items: list[str]) -> str:
    """At most SHOW items, then '+N more'."""
    head = ", ".join(items[:SHOW])
    return head + (f" +{len(items) - SHOW} more" if len(items) > SHOW else "")


def match_events(truth: list[float], answer: list[float], tol: float = 0.5) -> tuple[list[float], list[float]]:
    """(missed truth times, extra answer times): one-to-one pairs within `tol` seconds, closest pairs first."""
    pairs = sorted((abs(t - a), i, j) for i, t in enumerate(truth) for j, a in enumerate(answer) if abs(t - a) <= tol)
    ti, aj = set(), set()
    for _, i, j in pairs:
        if i not in ti and j not in aj:
            ti.add(i)
            aj.add(j)
    return ([t for i, t in enumerate(truth) if i not in ti],
            sorted(a for j, a in enumerate(answer) if j not in aj))


def diff_answer(kind: str, truth, task: dict) -> str:
    """What a run got wrong on one task, in a short line ('' when the answer equals the truth). `task` is the result
    file's task row; its `answer` is compared with `truth` (from the suite)."""
    if "answer" not in task:
        return NOT_RECORDED
    ans = task["answer"]
    if ans is None:
        return "no answer given"
    if kind in ("count", "rate"):
        if not is_num(ans):
            return "not a number"
        err = ans - truth
        if err == 0:
            return ""
        if kind == "count":
            return f"{abs(err):g} {'too many' if err > 0 else 'too few'}"
        return f"{abs(err) / truth * 100:.1f}% {'high' if err > 0 else 'low'}"
    if kind == "timestamps":
        if not isinstance(ans, list) or not all(is_num(a) for a in ans):
            return "not a list of seconds"
        missed, extra = match_events([float(t) for t in truth], sorted(float(a) for a in ans))
        bits = []
        if missed:
            bits.append(f"{len(missed)} of {len(truth)} not within 0.5 s (at {some([secs(t) for t in missed])})")
        if extra:
            bits.append(f"{len(extra)} unmatched (at {some([secs(a) for a in extra])})")
        return "; ".join(bits) or "all within 0.5 s"
    if kind == "outcomes":
        if not isinstance(ans, list):
            return "not a list"
        norm = [str(x).strip().lower() if x is not None else None for x in ans]
        wrong = [f"#{i + 1} said {x}" for i, (t, x) in enumerate(zip(truth, norm)) if t != x]
        bits = [f"{len(wrong)} of {len(truth)} wrong ({some(wrong)})"] if wrong else []
        if len(norm) < len(truth):
            bits.append(f"answered {len(norm)} of {len(truth)}")
        elif len(norm) > len(truth):
            bits.append(f"{len(norm) - len(truth)} extra")
        return "; ".join(bits)
    return ""


def show_value(kind: str, v) -> str:
    """A truth or answer in a few characters: a number, 'N times', or 'N made, M missed'."""
    if v is None:
        return "-"
    if kind == "timestamps" and isinstance(v, list):
        return f"{len(v)} time{'s' * (len(v) != 1)}"
    if kind == "outcomes" and isinstance(v, list):
        made = sum(1 for x in v if str(x).strip().lower() == "made")
        return f"{made} made, {len(v) - made} missed"
    return f"{v:g}" if is_num(v) else str(v)


def show_truth(kind: str, truth) -> str:
    """The truth line of a task: the value, plus the list itself for timestamps and outcomes."""
    if kind == "timestamps":
        return f"{show_value(kind, truth)}: {', '.join(f'{t:g}' for t in truth)} s"
    if kind == "outcomes":
        return f"{show_value(kind, truth)}: {' '.join('M' if x == 'made' else 'x' for x in truth)} (M = made)"
    return show_value(kind, truth)


def run_labels(rows: list[dict]) -> list[str]:
    """A short name per run: the model (or agent), with 'run k' when several runs share that name."""
    names = [str(r["contender"].get("model") or r["contender"].get("agent") or "?") for r in rows]
    seen: dict[str, int] = {}
    out = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(f"{name} run {seen[name]}" if names.count(name) > 1 else name)
    return out


def fails(rows: list[dict], suite: str) -> list[dict]:
    """Per task of `suite`: {id, kind, truth, runs: [{label, file, answer, score, why, miss}]}, derived from the
    runs' stored answers and the suite's truth (never the truth copied into a result file). The score is recomputed
    (`score_task`); a row without a stored answer keeps its stored score and says the answer was not recorded.
    Empty for a suite this tool does not know."""
    mod = TRUTH_SUITES.get(suite)
    runs = sorted((r for r in rows if not is_baseline(r)), key=lambda r: r["_file"])
    if mod is None or not runs:
        return []
    labels = run_labels(runs)
    out = []
    for t in mod.TASKS:
        lines = []
        for r, label in zip(runs, labels):
            row = next((x for x in r["tasks"] if str(x["id"]) == t.id), None)
            if row is None:
                continue
            if "answer" in row:
                score = score_task(t.id, row["answer"], suite)["score"]
            else:
                score = row.get("score") if is_num(row.get("score")) else None
            why = diff_answer(t.kind, t.truth, row)
            lines.append({"label": label, "file": r["_file"], "answer": row.get("answer"), "score": score,
                          "why": why, "miss": score is None or score < 1,
                          "recorded": "answer" in row})
        if lines:
            out.append({"id": t.id, "kind": t.kind, "truth": t.truth, "runs": lines})
    return out


def fails_section(rows: list[dict], suite: str) -> str:
    """The folded 'Where each contender fails' block of one suite and track ('' when nothing to show)."""
    tasks = fails(rows, suite)
    if not tasks:
        return ""
    parts = []
    for t in tasks:
        body = []
        for x in t["runs"]:
            ans = show_value(t["kind"], x["answer"]) if x["recorded"] else "-"
            score = f'{x["score"]:.2f}' if x["score"] is not None else "-"
            why = x["why"] or ("score below 1" if x["miss"] else "exact")
            tr = '<tr class="miss">' if x["miss"] else "<tr>"
            body.append(f'{tr}<td title="{esc(x["file"])}">'
                        f'{esc(x["label"])}</td><td class="num">{esc(ans)}</td><td class="num">{score}</td>'
                        f'<td class="why">{esc(why)}</td></tr>')
        parts.append(f'<h5>{esc(t["id"])}<span class="kind">{esc(t["kind"])}</span></h5>'
                     f'<p class="truth"><strong>Truth:</strong> {esc(show_truth(t["kind"], t["truth"]))}</p>'
                     '<div class="scroll"><table class="fails"><thead><tr><th scope="col">Run</th>'
                     '<th class="num" scope="col">Answer</th><th class="num" scope="col">Score</th>'
                     '<th scope="col">What was missed</th></tr></thead>'
                     f'<tbody>{"".join(body)}</tbody></table></div>')
    return (f'<details class="fails"><summary>Where each contender fails</summary>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">{esc(FAILS)}</p>{"".join(parts)}</details>')


def boards(rows: list[dict], prefix: str = "") -> str:
    """One leaderboard table per suite, in SUITES order (a suite with no runs says so); `prefix` keeps the anchors
    of a second track's tables apart."""
    known = [n for n, _ in SUITES]
    names = known + sorted({suite_of(r) for r in rows if not is_baseline(r)} - set(known))
    ran = {suite_of(r) for r in rows if not is_baseline(r)}
    names = [n for n in names if n in ran] + [n for n in names if n not in ran]   # empty suites last
    what = dict(SUITES)
    out = []
    for n in names:
        mine = [r for r in rows if suite_of(r) == n and not is_baseline(r)]
        floor = floor_of([r for r in rows if suite_of(r) == n])
        body = summary_table(mine, floor) + table(mine, floor) + fails_section(mine, n) if mine else '<p class="sub" style="color:var(--muted)">No runs on this suite yet.</p>'
        sat = (f" Saturated on this track: all {len(mine)} runs scored 1.0, so it ranks nobody."
               if len(mine) > 1 and all(float(r["total"]) == 1 for r in mine) else "")
        desc = f"<p>{esc(what.get(n, '') + sat)}</p>" if n in what or sat else ""
        out.append(f'<h3 id="{esc(prefix + n)}" style="margin-top:1.4rem">{esc(n)}</h3>{desc}{body}')
    return "\n".join(out)


def empty() -> str:
    return ('<div class="empty"><p><strong>No runs yet — be the first.</strong></p>'
            "<p>Run the suite with your agent (below), then open a pull request with your result file.</p></div>")


def frames_board(rows: list[dict]) -> str:
    """The frames-only track's section: its own tables, or a line saying it has no runs yet."""
    mine = [r for r in rows if track_of(r) == "frames"]
    body = boards(mine, "frames-") if any(not is_baseline(r) for r in mine) else \
        '<p class="sub" style="color:var(--muted)">No frames-only runs yet.</p>'
    run = "sports-video-coach bench run --agent claude --model <model> --suite svc-bench-3 --track frames"
    prep = "sports-video-coach bench prepare --out bench-frames --suite svc-bench-3 --track frames"
    return (f'<h2 id="frames">Frames-only track (eyes)</h2><p>{esc(FRAMES)}</p>'
            "<p>Rerun it in one command: it prepares the suite, runs Claude Code headless with no code tools (or "
            "any CLI with <code>--agent cmd --cmd \"... {prompt}\"</code>), and scores the answers.</p>"
            f"<pre><code>{esc(run)}</code></pre>"
            "<p>Another agent: prepare the stills, let it fill <code>bench-frames/answers.json</code> by eye, then "
            "score it with <code>bench score bench-frames</code>.</p>"
            f"<pre><code>{esc(prep)}</code></pre>{body}")


OWN_CONFIG = ("CLAUDE.md loaded", "user config loaded", "AGENTS.md was loaded", "(user config)")


def facts(rows: list[dict]) -> list[str]:
    """What a skeptic asks first, one short line each, counted from the result files (HTML, already escaped)."""
    runs = [r for r in rows if not is_baseline(r)]
    if not runs:
        return []
    n = len(runs)
    by_owner = sum(1 for r in runs if str(r.get("submitted_by") or "").lower() == OWNER.lower())
    others = n - by_owner
    who = (f"all {n} runs were submitted by {esc(OWNER)}, who also wrote this tool; no outside runs yet."
           if not others else f"{by_owner} of {n} runs were submitted by {esc(OWNER)}, who wrote this tool; "
                              f"{others} by others.")
    own = sum(1 for r in runs if any(m in str(r["contender"].get("settings") or "") for m in OWN_CONFIG))
    singles = contenders = 0
    spread = None                                   # (hi - lo, model, suite, track)
    for (suite, track) in sorted({(suite_of(r), track_of(r)) for r in runs}):
        mine = [r for r in rows if suite_of(r) == suite and track_of(r) == track]
        floor = floor_of(mine)
        for x in summarize(mine, floor):
            contenders += 1
            singles += x["n"] == 1
        scores = {str(t["id"]): t.get("score") for t in floor["tasks"]} if floor else None
        same: dict[tuple[str, str, str], list[float]] = {}   # repeats with identical settings: run-to-run noise
        for r in mine:
            v = above_value(r, scores)
            if not is_baseline(r) and v is not None:
                same.setdefault(contender_key(r), []).append(v)
        for key, vals in same.items():
            if len(vals) > 1 and (spread is None or max(vals) - min(vals) > spread[0]):
                spread = (max(vals) - min(vals), key[1] or key[0], suite, track)
    noise = (f" Two runs with identical settings differed by up to {spread[0]:.3f} above chance "
             f"({esc(spread[1])}, {esc(spread[2])} {esc(spread[3])} track): read smaller gaps as noise. A run "
             "killed at its time limit scores 0 and widens its contender's range further."
             if spread else "")
    floors = [(t.get("score"), str(t["id"])) for r in rows if is_baseline(r) for t in r["tasks"]
              if is_num(t.get("score"))]
    top = max(floors) if floors else None
    guess = (f" That guess alone scores up to {top[0]:.2f} on one task ({esc(top[1])})." if top else "")
    ev = sum(1 for r in runs if str(r.get("evidence") or "").startswith(("https://", "http://")))
    timed = sum(1 for r in runs if is_num_value(r.get("wall_seconds")))
    costed = sum(1 for r in runs if is_num_value(r.get("cost_usd")))
    return [
        f"<strong>Who ran it:</strong> {who}",
        f"<strong>Own config:</strong> {own} of {n} runs say in Settings that the submitter's own agent config "
        "(CLAUDE.md, AGENTS.md or Codex config) was loaded.",
        f"<strong>Sample size:</strong> {singles} of {contenders} contenders (per suite and track) ran once.{noise}",
        "<strong>Settings:</strong> not equalized. Each row ran at the effort and flags its Settings column names.",
        "<strong>Truth:</strong> the tool draws the videos from numbers, so the truth is exact. No human labels, no "
        "judge model.",
        "<strong>Suite design:</strong> svc-bench-2 and svc-bench-3 were each built after models scored 1.0 on the "
        "suite before, so the author knew which models already saturated it.",
        '<strong>Prompt:</strong> <code>bench run</code> sends one fixed text per track, the same for every '
        'model; only the Claude Code frames rows are known to have run with it. See '
        '<a href="#prompt">the exact prompt</a>.',
        "<strong>Above chance:</strong> measured from a blind guess that copies the example answers in the task "
        f"text, not from random.{guess}",
        f"<strong>Evidence:</strong> {ev} of {n} runs link a transcript"
        + (" (in its Evidence column): every file the agent opened, every command it ran and its final reply, with "
           "images, home folders and key-like strings taken out. Anyone can read them; CI re-scores the answers but "
           "does not read the transcripts." if ev else
           ". The no-peeking rule is honour-based: CI re-scores the answers but cannot see what the agent read."),
        f"<strong>Time and cost:</strong> in every table; time recorded for {timed} of {n} runs, cost for "
        f"{costed} of {n}.",
    ]


def latest(rows: list[dict]) -> str:
    """A chip with the newest run's date ('' without runs)."""
    dates = [str(r.get("date") or "") for r in rows if not is_baseline(r) and r.get("date")]
    return f"<li>Latest run {esc(max(dates))}</li>" if dates else ""


def facts_block(rows: list[dict]) -> str:
    items = facts(rows)
    if not items:
        return ""
    return (f'<details class="facts" id="facts"><summary>Before you trust this: {len(items)} things a skeptic '
            f'asks first</summary><ul>{"".join(f"<li>{x}</li>" for x in items)}</ul></details>')


def presets_step() -> str:
    """The one-command step of "Run it yourself": Claude Code, Codex and one line per preset in bench_run.PRESETS."""
    one = "sports-video-coach bench run --agent {} --suite svc-bench-3"
    lines = "".join(f"<li><code>--agent {esc(k)}</code> {esc(p.name)}: <code>{esc(bench_run.shown(k))}</code>"
                    "</li>" for k, p in bench_run.PRESETS.items())
    return ("<li>Or do it all in one command (prepare, run headless, score): Claude Code or Codex"
            f"<pre><code>{esc(one.format('claude'))}\n{esc(one.format('codex'))}</code></pre>"
            "or a preset for another agent CLI. The presets are built from each CLI's docs (read "
            f"{esc(bench_run.DOCS_READ)}) but not run by the maintainer, so untested against the real CLIs; code "
            f'track only (<a href="{DOC_URL}#add-your-agent-in-one-command">doc links per flag</a>). Any other '
            f'CLI: <code>--agent cmd --cmd "... {{prompt}}"</code>.<ul class="plain">{lines}</ul></li>')


def prompt_block() -> str:
    """The exact prompts `bench run` sends (shown for svc-bench-3; other suites change only the name and count)."""
    code = bench_run.prompt("svc-bench-3", "code")
    frames = bench_run.prompt("svc-bench-3", "frames", "claude")
    return ('<details class="prompt" id="prompt"><summary>The exact prompt</summary>'
            "<p>What <code>bench run</code> sends, word for word (for svc-bench-3; other suites change only the "
            "suite name and video count). One text per track, the same for every model.</p>"
            f"<h4>Code track</h4><pre class=\"wrap\"><code>{esc(code)}</code></pre>"
            f"<h4>Frames track (Claude Code)</h4><pre class=\"wrap\"><code>{esc(frames)}</code></pre>"
            "<p>The Claude Code frames rows were run with this frames prompt. The other rows do not store their "
            "prompt in the result file, so for them it is unclear.</p></details>")


def social(card: bool) -> str:
    """The link preview tags (Open Graph, X), as the landing page has them; og:image only when the card exists."""
    tags = [f'<meta property="og:title" content="{esc(share_card.TITLE)}">',
            f'<meta property="og:description" content="{esc(WHAT)}">']
    if card:
        tags += [f'<meta property="og:image" content="{PAGE_URL}{share_card.NAME}">',
                 f'<meta property="og:image:width" content="{share_card.SIZE[0]}">',
                 f'<meta property="og:image:height" content="{share_card.SIZE[1]}">']
    tags += [f'<meta property="og:url" content="{PAGE_URL}">',
             '<meta name="twitter:card" content="summary_large_image">']
    return "\n".join(tags)


def clip_block(clip: bool) -> str:
    """The short clip at the top (`bench.clip`: one hard moment, then truth vs answers), when it was drawn."""
    if not clip:
        return ""
    return (f'<figure style="margin:1rem 0"><video src="{share_clip.MP4}" autoplay muted loop playsinline '
            f'preload="metadata" aria-label="{esc(share_clip.ALT)}" style="display:block;width:100%;max-width:'
            f'{share_clip.SIZE}px;height:auto;border-radius:10px"><img src="{share_clip.GIF}" '
            f'alt="{esc(share_clip.ALT)}" style="width:100%;height:auto"></video>'
            f'<figcaption style="color:var(--muted);font-size:.9rem;margin-top:.3rem">One hard moment of '
            f'{share_clip.SUITE} ({share_clip.TASK}, {share_clip.TRACK} track), then what each model answered, '
            f'from the result files. <a href="{share_clip.GIF}">GIF</a> · <a href="{share_clip.MP4}">MP4</a>'
            f'</figcaption></figure>')


def render(rows: list[dict], notes: list[str], card: bool = False, clip: bool = False) -> str:
    code = [r for r in rows if track_of(r) == TRACK]
    board = boards(code) if any(not is_baseline(r) for r in code) else empty()
    runs = sum(1 for r in rows if not is_baseline(r))
    skipped = ""
    if notes:
        items = "".join(f"<li>{esc(n)}</li>" for n in notes)
        skipped = (f'<div class="note" role="note"><strong>{len(notes)} result file{"s" * (len(notes) > 1)} '
                   f"skipped</strong> (not shown in the table):<ul>{items}</ul></div>")
    kinds = "".join(f'<section><h3>{k}</h3><p>{esc(what)}</p><p class="rule">{esc(rule)}</p></section>'
                    for k, what, rule in KINDS)
    steps = "".join(f"<li>{esc(label)}<pre><code>{esc(cmd)}</code></pre></li>"
                    for label, cmd in COMMANDS) + presets_step()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title>
<meta name="description" content="{esc(WHAT)}">
{social(card)}
<style>{CSS}</style>
</head>
<body>
<main>
<p class="name"><a href="../">sports-video-coach</a></p>
<h1>{TITLE}</h1>
<p class="lead">{esc(WHAT)}</p>
<ul class="chips"><li>Suites {", ".join(n for n, _ in SUITES)}</li><li>{runs} run{"s" * (runs != 1)}</li>
<li>Measured truth only</li>{latest(rows)}</ul>
{clip_block(clip)}
{facts_block(rows)}

<h2 id="leaderboard">Leaderboard</h2>
{skipped}{board}

{frames_board(rows)}

<h2 id="method">Method</h2>
<p>The tasks are synthetic videos drawn by the tool, so the truth is exact: no human labels, no judge model.
The agent sees only the videos and writes its answers; <code>bench score</code> compares them with the truth.</p>
{prompt_block()}
<div class="cards">{kinds}</div>
<p>Total = the mean of the task scores. {esc(ABOVE)} Full rules: <a href="{DOC_URL}">docs/benchmark.md</a>.</p>

<h2 id="run">Run it yourself</h2>
<ol class="steps">{steps}</ol>

<h2 id="submit">Submit your run</h2>
<ul class="plain">
<li>Open a pull request that adds your result file to <code>benchmark/results/</code>.
CI re-scores it with <code>bench validate</code>.</li>
<li>No pull request? Paste the file into the <a href="{ISSUE_URL}">benchmark result issue form</a>.</li>
<li>Rules: do not read the truth files or the package source; one run = one file; report wall time honestly.</li>
</ul>

<h2 id="honesty">Honesty notes</h2>
<ul class="plain">
<li>The benchmark and this page were built with a coding agent (Claude Code).</li>
<li>Every row can be rerun: same suite, same command, scores recomputed from the stored answers. A rerun's answers
can differ (see the sample size note at the top).</li>
<li>The author wrote the tool, drew the suites and submitted the first runs; outside runs are welcome (above).</li>
<li>Failed and killed runs stay on the board and count in their contender's mean.</li>
<li>Synthetic drills test counting and timing, not every part of a coach's review.</li>
</ul>

<footer>Made by <a href="{REPO_URL}">sports-video-coach</a> (MIT).</footer>
</main>
</body>
</html>
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach bench page", description=__doc__.split("\n\n")[0])
    ap.add_argument("results_dir", help="folder of result files (benchmark/results)")
    ap.add_argument("out_dir", help="where to write index.html")
    a = ap.parse_args(argv)
    rows, notes = load(Path(a.results_dir))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    card = share_card.write(rows, out)
    if card is None:
        print("[bench page] no share card: matplotlib is not installed (the page has no og:image)")
    clip = share_clip.write(rows, out)
    (out / "index.html").write_text(render(rows, notes, card is not None, clip is not None), encoding="utf8")
    for n in notes:
        print(f"[bench page] skipped {n}")
    runs = sum(1 for r in rows if not is_baseline(r))
    print(f"[bench page] {(out / 'index.html').as_posix()}: {runs} run{'s' * (runs != 1)}, "
          f"{len(notes)} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
