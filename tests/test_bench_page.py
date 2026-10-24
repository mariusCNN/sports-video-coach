"""The benchmark leaderboard page (`bench page`): empty state, ranking, broken files, no stray external URLs."""
import json
import re

from sports_video_coach import page_check
from sports_video_coach.bench import page


def row(agent: str, model: str, total: float, scores: list[float], **extra) -> dict:
    ids = ["reps-bounce", "cadence", "contacts"]
    return {
        "schema": 1, "suite": "svc-bench-1", "tool_version": "0.0.0", "date": "2026-10-24",
        "contender": {"agent": agent, "agent_version": "1.0", "model": model, "settings": "effort medium"},
        "submitted_by": "someone",
        "tasks": [{"id": i, "kind": "count", "truth": 7, "answer": 7, "score": s, "note": ""}
                  for i, s in zip(ids, scores)],
        "total": total, "wall_seconds": None, "evidence": "", **extra,
    }


def write(d, name, data):
    (d / name).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf8")


def render(tmp_path, results):
    out = tmp_path / "site"
    assert page.main([str(results), str(out)]) == 0
    return out, (out / "index.html").read_text(encoding="utf8")


def test_empty_results_show_be_the_first(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    out, html = render(tmp_path, results)
    assert "No runs yet" in html and "be the first" in html
    assert "<table" not in html
    assert "bench prepare --out bench-run" in html and "bench score bench-run" in html
    assert page_check.problems(out) == []


def test_missing_results_folder_is_empty_not_a_crash(tmp_path):
    _, html = render(tmp_path, tmp_path / "nope")
    assert "No runs yet" in html


def test_rows_ranked_by_total(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a-low.json", row("Agent Low", "model-a", 0.412, [0.5, 0.236, 0.5]))
    write(results, "b-high.json", row("Agent High", "model-b", 0.9, [1.0, 0.7, 1.0],
                                      evidence="https://example.org/run"))
    out, html = render(tmp_path, results)
    assert "No runs yet" not in html
    assert html.index("Agent High") < html.index("Agent Low")
    assert "0.900" in html and "0.412" in html and "0.24" in html
    for task in ("reps-bounce", "cadence", "contacts"):
        assert f">{task}</th>" in html
    assert '<a href="https://example.org/run"' in html
    assert page_check.problems(out) == []


def test_above_chance_next_to_raw_and_floor_row_marked(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a.json", row("Agent A", "model-a", 0.75, [1.0, 0.75, 0.5]))
    write(results, "base.json", row("blind baseline", "", 0.5, [0.5, 0.5, 0.5]))
    out, html = render(tmp_path, results)
    assert '<th class="num" scope="col">Total</th><th class="num" scope="col">Above chance</th>' in html
    # raw 0.750 stays; above chance = mean of (1-.5)/.5, (.75-.5)/.5, 0 = 0.5
    assert '<td class="num total">0.750</td><td class="num above">0.500</td>' in html
    assert '<tr class="floor"><td class="num">floor</td><td><strong>Floor:</strong> blind baseline' in html
    assert html.index("Agent A") < html.index("<strong>Floor:</strong>")
    assert "(score - floor) / (1 - floor)" in html
    assert "<li>1 run</li>" in html                                     # the floor is not a run
    assert page_check.problems(out) == []


def test_floor_alone_is_not_a_leaderboard_and_no_floor_shows_dash(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "base.json", row("blind baseline", "", 0.5, [0.5, 0.5, 0.5]))
    _, html = render(tmp_path, results)
    assert "No runs yet" in html and "<table" not in html
    (results / "base.json").unlink()
    write(results, "a.json", row("Agent A", "m", 0.75, [1.0, 0.75, 0.5]))
    _, html = render(tmp_path, results)
    assert '<td class="num total">0.750</td><td class="num sub">-</td>' in html


def test_broken_file_is_a_visible_note(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "ok.json", row("Good Agent", "m", 0.5, [0.5, 0.5, 0.5]))
    write(results, "broken.json", "{not json")
    write(results, "old.json", {"schema": 0})
    write(results, "bad-total.json", row("Bad Total", "m", 3, [1, 1, 1]))
    _, html = render(tmp_path, results)
    assert "Good Agent" in html and "Bad Total" not in html
    assert "3 result files" in html
    assert "broken.json: not valid JSON" in html and "old.json" in html and "bad-total.json" in html


def test_text_is_escaped_and_unsafe_evidence_dropped(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "x.json", row("<script>alert(1)</script>", "m", 0.5, [0.5, 0.5, 0.5],
                                 evidence="javascript:alert(1)"))
    _, html = render(tmp_path, results)
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert "javascript:" not in html


def test_no_external_urls_but_repo_and_evidence(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "r.json", row("A", "m", 0.5, [0.5, 0.5, 0.5], evidence="https://example.org/ev"))
    _, html = render(tmp_path, results)
    urls = set(re.findall(r"""(?:https?:)?//[^\s"'<>)]+""", html))
    allowed = ("https://github.com/mariusDing/sports-video-coach", "https://example.org/ev")
    assert urls and all(u.startswith(allowed) for u in urls), urls
    assert "<link" not in html and "<script" not in html   # self-contained: no stylesheet or script fetched
