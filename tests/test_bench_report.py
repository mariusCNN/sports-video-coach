"""`bench report`: a result file's score as Markdown, with the leaderboard page's numbers (CI's PR summary)."""
import json

from sports_video_coach import bench
from sports_video_coach.bench import baseline, page, report, score as S


def run_file(results, name="2026-10-25-agent-x-model-y-svc-bench-2.json", **extra):
    answers = {"dribble-count": 50, "squat-reps": 8, "cadence-change": 190.0,
               "cone-touches-pan": [3.6, 7.0, 11.0, 30.0], "shot-outcomes-hard": ["made"] * 12}
    res = S.result(answers, "Agent X", "model-y", "1.2", "effort high", by="someone", wall_seconds=321,
                   suite="svc-bench-2", date="2026-10-25") | {"cost_usd": 0.42} | extra
    p = results / name
    p.write_text(json.dumps(res), encoding="utf8")
    return p, res


def setup(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "base.json").write_text(json.dumps(baseline.result("svc-bench-2", date="2026-10-24")),
                                       encoding="utf8")
    return results


def test_report_numbers_equal_the_page(tmp_path):
    results = setup(tmp_path)
    p, res = run_file(results)
    text, ok = report.report([p], results)
    assert ok and "validates" in text
    assert page.main([str(results), str(tmp_path / "site")]) == 0
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf8")
    rows, _ = page.load(results)
    floor = page.floor_of([r for r in rows if page.suite_of(r) == "svc-bench-2"])
    above = page.above_value(res, {str(t["id"]): t["score"] for t in floor["tasks"]})
    assert above is not None and 0 < above < 1
    for shown in (f"{res['total']:.3f}", f"{above:.3f}", "321 s", "$0.42"):
        assert shown in html and shown in text, shown
    assert "| Contender | Agent X 1.2 / model-y (effort high) |" in text
    assert "floor: `base.json`" in text
    assert "| Rank by total | 1 of 1 runs on its table |" in text
    # per task: answer, the suite's truth, the score and what was missed, as the page's fails block says it
    assert "| dribble-count | count | 50 | 56 | 0.893 | 6 too few |" in text
    assert "| squat-reps | count | 8 | 8 | 1.000 | - |" in text
    assert "4 times: 3.6, 7, 11, 30 s" in text and "10 times: 3.6, 7.6" in text
    assert "12 made, 0 missed" in text


def test_invalid_file_fails_and_says_why(tmp_path, capsys):
    results = setup(tmp_path)
    p, res = run_file(results)
    res["tasks"][0]["score"] = 1.0                       # an edited score
    p.write_text(json.dumps(res), encoding="utf8")
    good, _ = run_file(results, name="good.json")
    assert bench.main(["report", "--results", str(results), str(good), str(p)]) == 1
    out = capsys.readouterr().out
    assert "### `good.json`: validates" in out
    assert f"### `{p.name}`: does not validate" in out and "re-scoring the answer gives 0.893" in out
    broken = results / "broken.json"
    broken.write_text("{not json", encoding="utf8")
    text, ok = report.report([broken], results)
    assert not ok and "cannot read" in text


def test_no_changed_files_says_so(tmp_path):
    text, ok = report.report([], setup(tmp_path))
    assert ok and "No result file" in text


def test_outsider_text_cannot_break_the_markdown(tmp_path):
    results = setup(tmp_path)
    p, _ = run_file(results)
    res = json.loads(p.read_text(encoding="utf8"))
    res["contender"]["settings"] = "a | b <img src=x>\n`code`"
    p.write_text(json.dumps(res), encoding="utf8")
    text, ok = report.report([p], results)
    assert ok
    line = next(x for x in text.splitlines() if x.startswith("| Contender |"))
    assert "a \\| b &lt;img src=x&gt; 'code'" in line and "<img" not in text


def test_fresh_seed_run_is_measured_against_its_own_seed_floor(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    seed = 12345
    tasks = S.suite_tasks("svc-bench-3", seed).TASKS
    res = S.result({t.id: t.truth for t in tasks}, "Agent X", "model-y", suite="svc-bench-3", track="frames",
                   seed=seed, date="2026-10-25")
    p = results / "seeded.json"
    p.write_text(json.dumps(res), encoding="utf8")
    text, ok = report.report([p], results)
    assert ok and "| Total | **1.000** |" in text and "| Above chance | **1.000** (floor: the blind baseline on " \
        f"seed {seed}) |" in text
    assert f"| Seed | {seed} (fresh, listed under svc-bench-3-fresh) |" in text
