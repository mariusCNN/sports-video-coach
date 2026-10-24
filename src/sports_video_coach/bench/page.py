"""`sports-video-coach bench page <results_dir> <out_dir>`: the public benchmark leaderboard.

Reads every `*.json` result file in `<results_dir>` (schema 1, written by `bench score`) and writes
`<out_dir>/index.html`: a self-contained static page (inline CSS, light and dark, readable at 390 px) with the
leaderboard ranked by total (above it, a summary per contender: runs, mean total, mean and range of above
chance), with an "above chance" score next to it (the floor is the blind baseline's result
file of that suite and track, `bench.baseline`, shown as a marked row under the ranked ones) (one table per suite, the hard suite first; runs on the frames-only track, which
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
from .score import BASELINE_AGENT, above_chance

REPO_URL = "https://github.com/mariusDing/sports-video-coach"
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
                    "identical feet, a rebounder), rule-defined events and noise. On the frames track the top "
                    "models (Opus 5.5, Codex) scored 1.0 by eye."),
    ("svc-bench-1", "Four short drawn videos on a still camera. Saturated: every agent tried scored 1.0."),
)
TRACK = "code"                 # a result file without a track field is on the code track
FRAMES = ("Frames-only track: the agent sees still images of each video (contact sheets with the time under every "
          "still) and has no tool that runs code, so it must review by eye. Same videos, same truth, same scoring "
          "as the code track; the scores measure the model's eyes, not its tracker.")
ABOVE = ("Above chance: per task, (score - floor) / (1 - floor), clipped to 0..1, where the floor is the score of "
         "the blind baseline (it copies the example answers from the task text and sees no video); 0 = no better "
         "than that guess, 1 = perfect.")
SUMMARY = ("n = runs of that agent, model and settings; range = lowest to highest above-chance total over them "
           "(a dash for a single run).")
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
    ("Or in one command: prepare, run Claude Code or Codex headless on the frames-only track, score",
     "sports-video-coach bench run --agent claude --model <model> --suite svc-bench-3 --track frames"),
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
            f'<td>{esc(r.get("date", ""))}</td><td>{who}</td>{evidence(r.get("evidence"))}</tr>')
    return (f'<div class="scroll"><table><thead><tr><th class="num" scope="col">#</th><th scope="col">Agent</th>'
            f'<th scope="col">Model</th><th scope="col">Settings</th>{head}<th class="num" scope="col">Total</th>'
            f'<th class="num" scope="col">Above chance</th>'
            f'<th scope="col">Date</th><th scope="col">Submitter</th><th scope="col">Evidence</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">Scores 0 to 1 per task; total = mean. '
            f'Ranked by total, then earlier date. {esc(ABOVE)} '
            f'Raw files: <a href="{RESULTS_URL}">benchmark/results</a>.</p>')


def contender_key(r: dict) -> tuple[str, str, str]:
    c = r["contender"]
    return str(c.get("agent") or ""), str(c.get("model") or ""), str(c.get("settings") or "")


def summarize(rows: list[dict], floor_row: dict | None = None) -> list[dict]:
    """One entry per contender (agent + model + settings) of the given runs: n, mean total, and the mean, min and
    max above chance (None without a floor). Ranked by mean above chance, then mean total, then name. The blind
    baseline is never a contender."""
    floor = {str(t["id"]): t.get("score") for t in floor_row["tasks"]} if floor_row else None
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        if not is_baseline(r):
            groups.setdefault(contender_key(r), []).append(r)
    out = []
    for key, runs in groups.items():
        above = [v for v in (above_value(r, floor) for r in runs) if v is not None]
        out.append({"key": key, "n": len(runs), "total": sum(float(r["total"]) for r in runs) / len(runs),
                    "above": sum(above) / len(above) if above else None,
                    "lo": min(above) if above else None, "hi": max(above) if above else None})
    out.sort(key=lambda s: (s["above"] is None, -(s["above"] or 0), -s["total"], s["key"]))
    return out


def summary_table(rows: list[dict], floor_row: dict | None = None) -> str:
    """The per-contender summary of one suite and track, shown above its table of every run."""
    body = []
    for rank, s in enumerate(summarize(rows, floor_row), 1):
        agent, model, settings = s["key"]
        above = (f'<td class="num above">{s["above"]:.3f}</td>' if s["above"] is not None
                 else '<td class="num sub">-</td>')
        spread = (f'<td class="num">{s["lo"]:.3f}&ndash;{s["hi"]:.3f}</td>' if s["n"] > 1 and s["lo"] is not None
                  else '<td class="num sub">-</td>')
        body.append(f'<tr><td class="num">{rank}</td><td>{esc(agent)}</td><td>{esc(model or "-")}</td>'
                    f'<td class="sub">{esc(settings or "-")}</td><td class="num">{s["n"]}</td>'
                    f'<td class="num total">{s["total"]:.3f}</td>{above}{spread}</tr>')
    return ('<h4>Summary</h4><div class="scroll"><table class="summary"><thead><tr>'
            '<th class="num" scope="col">#</th><th scope="col">Agent</th><th scope="col">Model</th>'
            '<th scope="col">Settings</th><th class="num" scope="col">Runs (n)</th>'
            '<th class="num" scope="col">Mean total</th><th class="num" scope="col">Mean above chance</th>'
            '<th class="num" scope="col">Range</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="sub" style="font-size:.85rem;color:var(--muted)">Ranked by mean above chance. '
            f'{esc(SUMMARY)}</p><h4>Every run</h4>')


def suite_of(r: dict) -> str:
    return str(r.get("suite") or SUITE)


def track_of(r: dict) -> str:
    return str(r.get("track") or TRACK)


def floor_of(rows: list[dict]) -> dict | None:
    """The floor of one suite and track's rows: its latest blind-baseline result file, or None."""
    base = [r for r in rows if is_baseline(r)]
    return max(base, key=lambda r: (str(r.get("date", "")), r["_file"])) if base else None


def boards(rows: list[dict], prefix: str = "") -> str:
    """One leaderboard table per suite, in SUITES order (a suite with no runs says so); `prefix` keeps the anchors
    of a second track's tables apart."""
    known = [n for n, _ in SUITES]
    names = known + sorted({suite_of(r) for r in rows if not is_baseline(r)} - set(known))
    what = dict(SUITES)
    out = []
    for n in names:
        mine = [r for r in rows if suite_of(r) == n and not is_baseline(r)]
        floor = floor_of([r for r in rows if suite_of(r) == n])
        body = summary_table(mine, floor) + table(mine, floor) if mine else '<p class="sub" style="color:var(--muted)">No runs on this suite yet.</p>'
        desc = f"<p>{esc(what[n])}</p>" if n in what else ""
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
    cmd = "sports-video-coach bench prepare --out bench-frames --suite svc-bench-3 --track frames"
    return (f'<h2 id="frames">Frames-only track (eyes)</h2><p>{esc(FRAMES)}</p>'
            f"<pre><code>{esc(cmd)}</code></pre>{body}")


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


def render(rows: list[dict], notes: list[str], card: bool = False) -> str:
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
    steps = "".join(f"<li>{esc(label)}<pre><code>{esc(cmd)}</code></pre></li>" for label, cmd in COMMANDS)
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
<li>Measured truth only</li></ul>

<h2 id="leaderboard">Leaderboard</h2>
{skipped}{board}

{frames_board(rows)}

<h2 id="method">Method</h2>
<p>The tasks are synthetic videos drawn by the tool, so the truth is exact: no human labels, no judge model.
The agent sees only the videos and writes its answers; <code>bench score</code> compares them with the truth.</p>
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
    card = share_card.write(rows, out)
    if card is None:
        print("[bench page] no share card: matplotlib is not installed (the page has no og:image)")
    (out / "index.html").write_text(render(rows, notes, card is not None), encoding="utf8")
    for n in notes:
        print(f"[bench page] skipped {n}")
    runs = sum(1 for r in rows if not is_baseline(r))
    print(f"[bench page] {(out / 'index.html').as_posix()}: {runs} run{'s' * (runs != 1)}, "
          f"{len(notes)} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
