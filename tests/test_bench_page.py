"""The benchmark leaderboard page (`bench page`): empty state, ranking, broken files, no stray external URLs."""
import json
import re

from sports_video_coach import page_check
from sports_video_coach.bench import card, page


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
    frames = html[html.index('<h2 id="frames">'):]
    one = frames.index("bench run --agent claude --model &lt;model&gt; --suite svc-bench-3 --track frames")
    assert one < frames.index("bench prepare --out bench-frames --suite svc-bench-3 --track frames")  # one command first
    assert "bench score bench-frames" in frames
    assert "--agent cmd --cmd" in frames and "--agent codex" not in frames   # frames runs Claude Code or a cmd
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
    allowed = ("https://github.com/mariusDing/sports-video-coach", "https://example.org/ev", page.PAGE_URL)
    assert urls and all(u.startswith(allowed) for u in urls), urls
    assert "<link" not in html and "<script" not in html   # self-contained: no stylesheet or script fetched


def summary_of(html: str) -> str:
    return html[html.index('<table class="summary">'):html.index("<h4>Every run</h4>")]


def test_summary_groups_runs_per_contender_and_ranks_by_mean_above_chance(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "base.json", row("blind baseline", "", 0.5, [0.5, 0.5, 0.5]))
    write(results, "a1.json", row("Agent A", "model-a", 1.0, [1.0, 1.0, 1.0]))            # above 1.0
    write(results, "a2.json", row("Agent A", "model-a", 0.5, [0.5, 0.5, 0.5]))            # above 0.0
    write(results, "b.json", row("Agent B", "model-b", 0.8, [0.8, 0.8, 0.8]))               # above 0.6
    write(results, "a-hi.json", row("Agent A", "model-a", 0.9, [0.9, 0.9, 0.9], contender={
        "agent": "Agent A", "model": "model-a", "settings": "effort high"}))             # another contender
    out, html = render(tmp_path, results)
    s = summary_of(html)
    assert html.index("<h4>Summary</h4>") < html.index("<h4>Every run</h4>") < html.index("<strong>Floor:</strong>")
    # effort high (0.8) > Agent B (0.6) > Agent A at effort medium (mean of 1.0 and 0.0 = 0.5)
    assert s.index("effort high") < s.index("Agent B") < s.index("effort medium")
    assert ('<td class="num">2</td><td class="num total">0.750</td><td class="num above">0.500</td>'
            '<td class="num">0.000&ndash;1.000</td>') in s
    assert "blind baseline" not in s and "Floor" not in s
    assert s.count("<tr>") == 4                                         # header + three contenders
    assert "a dash for a single run" in html
    assert page_check.problems(out) == []


def test_summary_single_run_shows_a_dash_not_a_range(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "base.json", row("blind baseline", "", 0.5, [0.5, 0.5, 0.5]))
    write(results, "a.json", row("Agent A", "model-a", 0.75, [1.0, 0.75, 0.5]))
    _, html = render(tmp_path, results)
    s = summary_of(html)
    assert ('<td class="num">1</td><td class="num total">0.750</td><td class="num above">0.500</td>'
            '<td class="num sub">-</td>') in s
    assert "&ndash;" not in s


def test_summary_without_a_floor_ranks_by_mean_total(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "lo.json", row("Agent Low", "m", 0.4, [0.4, 0.4, 0.4]))
    write(results, "hi.json", row("Agent High", "m", 0.8, [0.8, 0.8, 0.8]))
    _, html = render(tmp_path, results)
    s = summary_of(html)
    assert s.index("Agent High") < s.index("Agent Low")
    assert "&ndash;" not in s and '<td class="num above">' not in s


def test_share_card_is_written_and_the_preview_tags_point_at_it(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "base.json", row("blind baseline", "", 0.5, [0.5, 0.5, 0.5]))
    write(results, "a.json", row("Agent A", "model-a", 1.0, [1.0, 1.0, 1.0]))
    out, html = render(tmp_path, results)
    png = (out / card.NAME).read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) == card.SIZE
    assert f'<meta property="og:image" content="{page.PAGE_URL}card.png">' in html
    assert f'<meta property="og:url" content="{page.PAGE_URL}">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html and 'property="og:title"' in html
    assert page_check.problems(out) == []


def test_without_matplotlib_there_is_no_card_and_no_og_image(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "matplotlib", None)   # import matplotlib raises ImportError
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a.json", row("Agent A", "model-a", 1.0, [1.0, 1.0, 1.0]))
    out, html = render(tmp_path, results)
    assert not (out / card.NAME).exists()
    assert "og:image" not in html and 'property="og:title"' in html


def test_card_numbers_are_the_summary_numbers(tmp_path):
    rows = []
    for suite, track, name, scores in (
            ("svc-bench-2", "frames", "base", [0.5, 0.5, 0.5]), ("svc-bench-2", "frames", "a1", [1.0, 1.0, 1.0]),
            ("svc-bench-2", "frames", "a2", [0.5, 0.5, 0.5]), ("svc-bench-2", "frames", "b", [0.8, 0.8, 0.8]),
            ("svc-bench-2", "code", "base", [0.5, 0.5, 0.5]), ("svc-bench-2", "code", "c", [0.9, 0.9, 0.9]),
            ("svc-bench-3", "frames", "nofloor", [0.9, 0.9, 0.9]),          # no blind baseline: not on the card
            ("svc-bench-1", "code", "base", [0.5, 0.5, 0.5]),
            *[("svc-bench-1", "code", f"x{i}", [1.0 - i / 10] * 3) for i in range(6)]):
        agent = {"base": "blind baseline", "a1": "Agent A", "a2": "Agent A"}.get(name, f"Agent {name}")
        r = row(agent, "" if name == "base" else "claude-model", sum(scores) / 3, scores, suite=suite, track=track)
        r["_file"] = f"{suite}-{track}-{name}.json"
        rows.append(r)
    data = card.card_data(rows)
    assert data["date"] == "2026-10-24"
    assert [(p["suite"], p["track"]) for p in data["panels"]] == [
        ("svc-bench-2", "frames"), ("svc-bench-2", "code"), ("svc-bench-1", "code")]   # suite order, frames first
    frames = data["panels"][0]["bars"]
    # Agent B 0.6 above chance; Agent A the mean of 1.0 and 0.0 over two runs, as in the page's Summary
    assert [(b["agent"], b["n"], b["above"]) for b in frames] == [("Agent b", 1, 0.6), ("Agent A", 2, 0.5)]
    assert frames[0]["label"] == "model · Agent b"
    assert len(data["panels"][2]["bars"]) == card.BARS
    summary = page.summarize([r for r in rows if r["suite"] == "svc-bench-2" and r["track"] == "frames"],
                             page.floor_of([r for r in rows if r["suite"] == "svc-bench-2" and r["track"] == "frames"]))
    assert [round(s["above"], 3) for s in summary] == [b["above"] for b in frames]


# "Where each contender fails": answers vs truth, derived at build time


def test_fails_diff_count_and_rate():
    assert page.diff_answer("count", 47, {"answer": 49}) == "2 too many"
    assert page.diff_answer("count", 47, {"answer": 40}) == "7 too few"
    assert page.diff_answer("count", 47, {"answer": 47}) == ""
    assert page.diff_answer("rate", 40.0, {"answer": 44.0}) == "10.0% high"
    assert page.diff_answer("rate", 40.0, {"answer": "fast"}) == "not a number"


def test_fails_diff_timestamps_names_missed_and_extra_events():
    truth = [1.0, 3.0, 5.0, 7.0]
    assert page.diff_answer("timestamps", truth, {"answer": [1.1, 2.9, 5.2, 7.4]}) == "all within 0.5 s"
    why = page.diff_answer("timestamps", truth, {"answer": [1.0, 5.1, 12.4]})
    assert why == "2 of 4 not within 0.5 s (at 3 s, 7 s); 1 unmatched (at 12.4 s)"
    many = page.diff_answer("timestamps", [float(i) for i in range(10)], {"answer": []})
    assert many == "10 of 10 not within 0.5 s (at 0 s, 1 s, 2 s, 3 s +6 more)"


def test_fails_diff_outcome_sequence():
    truth = ["made", "missed", "made", "missed"]
    assert page.diff_answer("outcomes", truth, {"answer": ["made", "made", "made", "missed"]}) == \
        "1 of 4 wrong (#2 said made)"
    assert page.diff_answer("outcomes", truth, {"answer": ["Made", "missed"]}) == \
        "answered 2 of 4"
    assert page.diff_answer("outcomes", truth, {"answer": truth + ["made"]}) == "1 extra"


def test_fails_not_recorded_and_no_answer():
    assert page.diff_answer("count", 13, {"id": "jump-count", "score": 0.5}) == page.NOT_RECORDED
    assert page.diff_answer("count", 13, {"answer": None}) == "no answer given"
    r = row("Agent A", "model-a", 0.5, [0.5, 0.5, 0.5])
    r["tasks"] = [{"id": "jump-count", "kind": "count", "score": 0.4},             # answer key absent
                  {"id": "stroke-rate", "kind": "rate", "answer": 42.0, "score": 0.0}]  # stored score is ignored
    r["_file"] = "a.json"
    tasks = {t["id"]: t for t in page.fails([r], "svc-bench-1")}
    jump = tasks["jump-count"]["runs"][0]
    assert jump["why"] == page.NOT_RECORDED and jump["score"] == 0.4 and jump["miss"]
    rate = tasks["stroke-rate"]["runs"][0]
    assert rate["score"] == 1.0 and not rate["miss"]            # recomputed from answer + suite truth
    assert page.fails([r], "no-such-suite") == []


def test_fails_section_on_the_page_is_folded_and_skips_the_baseline(tmp_path):
    from sports_video_coach.bench.score import BASELINE_AGENT
    results = tmp_path / "results"
    results.mkdir()
    a = row("Agent A", "model-a", 0.5, [1, 1, 1])
    a["tasks"] = [{"id": "jump-count", "kind": "count", "answer": 11, "score": 0.846}]
    base = row(BASELINE_AGENT, "", 0.1, [0.1, 0.1, 0.1])
    base["tasks"] = [{"id": "jump-count", "kind": "count", "answer": 5, "score": 0.385}]
    write(results, "a.json", a)
    write(results, "base.json", base)
    _, html = render(tmp_path, results)
    sec = html[html.index('<details class="fails">'):]
    sec = sec[:sec.index("</details>")]
    assert "<details open" not in html
    assert html.index("<h4>Summary</h4>") < html.index('<details class="fails">')
    assert "Where each contender fails" in sec and "2 too few" in sec and "<strong>Truth:</strong> 13" in sec
    assert "model-a" in sec and "base.json" not in sec


def test_summary_counts_a_killed_run_with_its_contender_and_marks_ties():
    ok = row("A", "m", 1.0, [1.0, 1.0, 1.0])
    killed = row("A", "m", 0.0, [0.0, 0.0, 0.0])
    killed["contender"]["settings"] = "effort medium; killed at the 1700 s time limit"
    tied = row("B", "n", 1.0, [1.0, 1.0, 1.0])
    for i, r in enumerate((ok, killed, tied)):
        r["_file"] = f"{i}.json"
    summary = page.summarize([ok, killed, tied])
    by = {s["key"][:2]: s for s in summary}
    assert by[("A", "m")]["n"] == 2 and by[("A", "m")]["total"] == 0.5    # the failure counts in the mean
    assert by[("A", "m")]["key"][2] == "effort medium"
    assert page.ranks(summary) == ["1", "2"]
    assert page.ranks(page.summarize([ok, tied])) == ["1=", "1="]


def test_time_and_cost_columns_show_what_was_recorded(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a.json", row("Agent A", "m", 0.9, [0.9, 0.9, 0.9], wall_seconds=489.3, cost_usd=3.9145))
    write(results, "b.json", row("Agent A", "m", 0.7, [0.7, 0.7, 0.7], wall_seconds=100))
    out, html = render(tmp_path, results)
    assert ">Time</th>" in html and ">Cost</th>" in html and ">Mean time</th>" in html
    assert "489 s" in html and "$3.91" in html and "295 s" in html     # the mean of 489.3 and 100
    assert "(1 of 2)" in html                                            # only one run reported its cost
    assert page_check.problems(out) == []


def test_skeptic_facts_are_counted_from_the_files(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    a = row("Agent A", "m", 0.9, [0.9, 0.9, 0.9], submitted_by="mariusDing", wall_seconds=10)
    a["contender"]["settings"] = "user CLAUDE.md loaded"
    write(results, "a.json", a)
    write(results, "a2.json", {**a, "total": 0.5, "tasks": [dict(t, score=0.5) for t in a["tasks"]]})
    write(results, "b.json", row("Agent B", "n", 0.8, [0.8, 0.8, 0.8], evidence="https://example.org/t"))
    base = row(page.BASELINE_AGENT, "", 0.2, [0.2, 0.3, 0.2])
    write(results, "base.json", base)
    out, html = render(tmp_path, results)
    facts = html[html.index('id="facts"'):html.index('id="leaderboard"')]
    assert "Before you trust this: 10 things" in facts
    assert "2 of 3 runs were submitted by mariusDing" in facts and "1 by others" in facts
    assert "2 of 3 runs say in Settings" in facts
    assert "1 of 2 contenders" in facts and "differed by up to 0.524" in facts   # A: 0.869 vs 0.345 above
    assert "up to 0.30 on one task (cadence)" in facts
    assert "1 of 3 runs link a transcript" in facts
    assert "time recorded for 2 of 3 runs, cost for 0 of 3" in facts
    assert 'href="#prompt"' in facts and 'id="prompt"' in html
    assert "Do not read the sports-video-coach package source" in html      # the code-track prompt, verbatim
    assert page_check.problems(out) == []


def test_saturated_only_when_every_run_scored_one(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a.json", row("Agent A", "m", 1.0, [1.0, 1.0, 1.0]))
    write(results, "b.json", row("Agent B", "n", 1.0, [1.0, 1.0, 1.0]))
    _, html = render(tmp_path, results)
    assert "Saturated on this track: all 2 runs scored 1.0" in html
    write(results, "c.json", row("Agent C", "o", 0.9, [0.9, 0.9, 0.9]))
    _, html = render(tmp_path, results)
    assert "Saturated" not in html
    code = html[html.index('id="leaderboard"'):html.index('id="frames"')]
    assert code.index('id="svc-bench-1"') < code.index('id="svc-bench-3"')    # suites with no runs go last
