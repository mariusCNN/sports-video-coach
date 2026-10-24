"""`sports-video-coach bench page <results_dir> <out_dir>`: the public benchmark leaderboard.

Reads every `*.json` result file in `<results_dir>` (schema 1, written by `bench score`) and writes
`<out_dir>/index.html`: a self-contained static page (inline CSS, light and dark, readable at 390 px) with the
leaderboard ranked by total (one table per suite, the hard suite first; runs on the frames-only track, which
see still images and run no code, in their own tables below), the method, how to run it yourself, how to submit a
run and honesty notes. With no
results it shows a "no runs yet" state; a file that does not parse is skipped and named in a visible note. The page
never invents a row: every number on it comes from a result file.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

REPO_URL = "https://github.com/mariusDing/sports-video-coach"
DOC_URL = f"{REPO_URL}/blob/master/docs/benchmark.md"
RESULTS_URL = f"{REPO_URL}/tree/master/benchmark/results"
ISSUE_URL = f"{REPO_URL}/issues/new?template=benchmark_result.yml"
SUITE = "svc-bench-1"          # a result file without a suite field is from suite 1
SUITES = (                     # (name, what it is), shown in this order; unknown suites follow by name
    ("svc-bench-2", "Hard: five drawn videos with a hand-held camera, look-alike decoys (a second ball, two "
                    "identical feet, a rebounder), rule-defined events and noise."),
    ("svc-bench-1", "Four short drawn videos on a still camera. Saturated: every agent tried scored 1.0."),
)
TRACK = "code"                 # a result file without a track field is on the code track
FRAMES = ("Frames-only track: the agent sees still images of each video (contact sheets with the time under every "
          "still) and has no tool that runs code, so it must review by eye. Same videos, same truth, same scoring "
          "as the code track; the scores measure the model's eyes, not its tracker.")
TITLE = "Sports film review benchmark"
WHAT = ("Which coding agent and vision model reviews sports film best? Each run is scored against ground truth "
        "drawn into synthetic videos, so every number is measured, not judged.")

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
    ("Make the tasks: videos and an empty answers.json (the hard suite; leave out --suite for svc-bench-1)",
     "sports-video-coach bench prepare --out bench-run --suite svc-bench-2"),
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
    return f'<td><a href="{esc(url)}" rel="nofollow noopener">link</a></td>'


def table(rows: list[dict]) -> str:
    ids = task_ids(rows)
    head = "".join(f'<th class="num" scope="col">{esc(i)}</th>' for i in ids)
    body = []
    for rank, r in enumerate(rows, 1):
        c = r["contender"]
        agent = esc(c.get("agent", "")) + (f' <span class="sub">{esc(c["agent_version"])}</span>'
                                           if c.get("agent_version") else "")
        scores = {str(t["id"]): t.get("score") for t in r["tasks"]}
        who = esc(r.get("submitted_by") or "-")
        body.append(
            f'<tr><td class="num">{rank}</td><td>{agent}</td><td>{esc(c.get("model") or "-")}</td>'
            f'<td class="sub">{esc(c.get("settings") or "-")}</td>'
            + "".join(score_cell(scores.get(i)) for i in ids)
            + f'<td class="num total">{float(r["total"]):.3f}</td><td>{esc(r.get("date", ""))}</td>'
            f"<td>{who}</td>{evidence(r.get('evidence'))}</tr>")
    return (f'<div class="scroll"><table><thead><tr><th class="num" scope="col">#</th><th scope="col">Agent</th>'
            f'<th scope="col">Model</th><th scope="col">Settings</th>{head}<th class="num" scope="col">Total</th>'
            f'<th scope="col">Date</th><th scope="col">Submitter</th><th scope="col">Evidence</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">Scores 0 to 1 per task; total = mean. '
            f'Ranked by total, then earlier date. Raw files: <a href="{RESULTS_URL}">benchmark/results</a>.</p>')


def suite_of(r: dict) -> str:
    return str(r.get("suite") or SUITE)


def track_of(r: dict) -> str:
    return str(r.get("track") or TRACK)


def boards(rows: list[dict], prefix: str = "") -> str:
    """One leaderboard table per suite, in SUITES order (a suite with no runs says so); `prefix` keeps the anchors
    of a second track's tables apart."""
    known = [n for n, _ in SUITES]
    names = known + sorted({suite_of(r) for r in rows} - set(known))
    what = dict(SUITES)
    out = []
    for n in names:
        mine = [r for r in rows if suite_of(r) == n]
        body = table(mine) if mine else '<p class="sub" style="color:var(--muted)">No runs on this suite yet.</p>'
        desc = f"<p>{esc(what[n])}</p>" if n in what else ""
        out.append(f'<h3 id="{esc(prefix + n)}" style="margin-top:1.4rem">{esc(n)}</h3>{desc}{body}')
    return "\n".join(out)


def empty() -> str:
    return ('<div class="empty"><p><strong>No runs yet — be the first.</strong></p>'
            "<p>Run the suite with your agent (below), then open a pull request with your result file.</p></div>")


def frames_board(rows: list[dict]) -> str:
    """The frames-only track's section: its own tables, or a line saying it has no runs yet."""
    mine = [r for r in rows if track_of(r) == "frames"]
    body = boards(mine, "frames-") if mine else \
        '<p class="sub" style="color:var(--muted)">No frames-only runs yet.</p>'
    cmd = "sports-video-coach bench prepare --out bench-frames --suite svc-bench-2 --track frames"
    return (f'<h2 id="frames">Frames-only track (eyes)</h2><p>{esc(FRAMES)}</p>'
            f"<pre><code>{esc(cmd)}</code></pre>{body}")


def render(rows: list[dict], notes: list[str]) -> str:
    code = [r for r in rows if track_of(r) == TRACK]
    board = boards(code) if code else empty()
    skipped = ""
    if notes:
        items = "".join(f"<li>{esc(n)}</li>" for n in notes)
        skipped = (f'<div class="note" role="note"><strong>{len(notes)} result file{"s" * (len(notes) > 1)} '
                   f"skipped</strong> (not shown in the table):<ul>{items}</ul></div>")
    kinds = "".join(f'<section><h3>{k}</h3><p>{esc(what)}</p><p class="rule">{esc(rule)}</p></section>'
                    for k, what, rule in KINDS)
    steps = "".join(f"<li>{esc(label)}<pre><code>{esc(cmd)}</code></pre></li>" for label, cmd in COMMANDS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title>
<meta name="description" content="{esc(WHAT)}">
<style>{CSS}</style>
</head>
<body>
<main>
<p class="name"><a href="../">sports-video-coach</a></p>
<h1>{TITLE}</h1>
<p class="lead">{esc(WHAT)}</p>
<ul class="chips"><li>Suites {", ".join(n for n, _ in SUITES)}</li><li>{len(rows)} run{"s" * (len(rows) != 1)}</li>
<li>Measured truth only</li></ul>

<h2 id="leaderboard">Leaderboard</h2>
{skipped}{board}

{frames_board(rows)}

<h2 id="method">Method</h2>
<p>The tasks are synthetic videos drawn by the tool, so the truth is exact: no human labels, no judge model.
The agent sees only the videos and writes its answers; <code>bench score</code> compares them with the truth.</p>
<div class="cards">{kinds}</div>
<p>Total = the mean of the task scores. Full rules: <a href="{DOC_URL}">docs/benchmark.md</a>.</p>

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
<li>The benchmark and this page were built with a coding agent.</li>
<li>Every row is reproducible: same suite, same commands, scores recomputed from the answers.</li>
<li>The author's own tool and agent get no special treatment: their errors are shown like anyone else's.</li>
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
    (out / "index.html").write_text(render(rows, notes), encoding="utf8")
    for n in notes:
        print(f"[bench page] skipped {n}")
    print(f"[bench page] {(out / 'index.html').as_posix()}: {len(rows)} run{'s' * (len(rows) != 1)}, "
          f"{len(notes)} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
