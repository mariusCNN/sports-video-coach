"""The benchmark leaderboard page (`bench page`): empty state, ranking, broken files, no stray external URLs."""
import json
import re

from sports_video_coach import page_check
from sports_video_coach.bench import card, effort, page


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
    frames = html[html.index('<h2 id="frames">'):html.index('<h2 id="method">')]
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
    html = re.sub(r'<script type="application/ld\+json">.*?</script>', "", html, flags=re.S)  # data, not fetched
    urls = set(re.findall(r"""(?:https?:)?//[^\s"'<>)]+""", html))
    allowed = ("https://github.com/mariusDing/sports-video-coach", "https://example.org/ev", page.PAGE_URL, page.DEMO_URL,
               page.CODESPACES_URL)
    assert urls and all(u.startswith(allowed) for u in urls), urls
    assert "<script" not in html                            # self-contained: no stylesheet or script fetched
    assert set(re.findall(r"<link rel=\"([^\"]+)\"", html)) == {"canonical", "alternate"}


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
    assert '<meta property="og:locale" content="en_US">' in html
    assert page_check.problems(out) == []
    # the Chinese page previews the Chinese card (when a CJK font drew it), with Chinese text
    zh = (out / "zh" / "index.html").read_text(encoding="utf8")
    name = card.NAMES["zh"] if effort.cjk_font() else card.NAME
    assert f'<meta property="og:image" content="{page.PAGE_URL}{name}">' in zh
    assert '<meta property="og:locale" content="zh_CN">' in zh and "哪个编程 agent 最会看体育录像？" in zh
    if effort.cjk_font():
        png = (out / card.NAMES["zh"]).read_bytes()
        assert (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) == card.SIZE


def test_without_a_cjk_font_the_zh_page_previews_the_english_card(tmp_path, monkeypatch):
    __import__("pytest").importorskip("matplotlib")
    monkeypatch.setattr(effort, "cjk_font", lambda: None)
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a.json", row("Agent A", "model-a", 1.0, [1.0, 1.0, 1.0]))
    out, _ = render(tmp_path, results)
    assert not (out / card.NAMES["zh"]).exists()
    zh = (out / "zh" / "index.html").read_text(encoding="utf8")
    assert f'<meta property="og:image" content="{page.PAGE_URL}card.png">' in zh


def test_every_card_text_has_a_translation():
    for en in (card.TITLE, card.SUB, card.FLOOR, "frames only (eyes)", "code track", "No runs yet: be the first."):
        assert page.ZH[en]


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
    assert "Before you trust this: 11 things" in facts
    assert "no run used a fresh seed yet" in facts
    assert "2 of 3 runs were submitted by mariusDing" in facts and "1 by others" in facts
    assert "2 of 3 runs say in Settings" in facts
    assert "1 of 2 contenders" in facts and "differed by up to 0.524" in facts   # A: 0.869 vs 0.345 above
    assert "up to 0.30 on one task (cadence)" in facts
    assert "1 of 3 runs link a transcript" in facts
    assert "<li>Latest run 2026-10-24</li>" in html
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


def test_first_screen_links_boards_rerun_repo_and_demo(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "c.json", row("A", "m", 0.5, [0.5, 0.5, 0.5]))
    write(results, "f.json", row("B", "n", 0.6, [0.6, 0.6, 0.6], suite="svc-bench-3", track="frames"))
    out, html = render(tmp_path, results)
    top = html[:html.index('<h2 id="leaderboard">')]
    nav = top[top.index('<nav class="jump"'):top.index("</nav>")]
    assert '"#frames-svc-bench-3"' in nav and "-fresh" not in nav            # no fresh-seed runs, no link
    assert '"#leaderboard"' in nav and '"#rerun"' in nav and f'"{page.REPO_URL}"' in nav
    assert f'href="{page.DEMO_URL}"' in top and "your own sports video" in top
    assert page_check.problems(out) == []                                      # every jump target exists


def test_rerun_section_links_codespaces_in_both_languages(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    out, html = render(tmp_path, results)
    zh = (out / "zh" / "index.html").read_text(encoding="utf8")
    assert page.CODESPACES_URL == "https://codespaces.new/mariusDing/sports-video-coach"
    for doc, label in ((html, "Open in GitHub Codespaces"), (zh, "在 GitHub Codespaces 中打开")):
        para = doc[doc.index('<p id="codespaces">'):]
        para = para[:para.index("</p>")]
        assert doc.index('<pre id="rerun">') < doc.index(para)                 # right under the rerun command
        assert f'<a href="{page.CODESPACES_URL}">{label}</a>' in para and "<code>uv run</code>" in para


def test_first_screen_links_without_runs(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    out, html = render(tmp_path, results)
    nav = html[html.index('<nav class="jump"'):html.index("</nav>")]
    assert "#frames-" not in nav and "#leaderboard" not in nav and '"#rerun"' in nav
    assert page_check.problems(out) == []


NUM_CELL = re.compile(r'<td class="num[^"]*">([^<]*)')
NUMBER = re.compile(r"^(?:\$?\d+(?:\.\d+)?(?: s)?|\d+\.\d+&ndash;\d+\.\d+)$")


def numbers(html: str) -> list[str]:
    """Every number in the page's table cells, in order (ranks, scores, totals, times, costs)."""
    return [c.strip() for c in NUM_CELL.findall(html) if NUMBER.match(c.strip())]


def test_chinese_page_shows_the_same_rows_and_numbers_as_the_english_one():
    from pathlib import Path
    rows, notes = page.load(Path(__file__).resolve().parents[1] / "benchmark" / "results")
    en, zh = (page.render(rows, notes, lang=x) for x in ("en", "zh"))
    assert '<html lang="zh-CN">' in zh and "体育录像复盘基准测试" in zh
    assert zh.count("<tr") == en.count("<tr") and zh.count("<table") == en.count("<table")
    assert numbers(zh) == numbers(en) and len(numbers(en)) > 100
    assert re.findall(r' id="([^"]+)"', zh) == re.findall(r' id="([^"]+)"', en)   # same sections and anchors
    for text in ("Leaderboard", "Before you trust this", "Where each contender fails", "Above chance", "Method"):
        assert text not in zh
    assert "排行榜" in zh and "信之前先看" in zh and "每个参赛者错在哪里" in zh and "超出盲猜" in zh


def test_language_switch_and_hreflang_both_ways(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a.json", row("Agent A", "model-a", 0.75, [1.0, 0.75, 0.5]))
    write(results, "base.json", row("blind baseline", "", 0.5, [0.5, 0.5, 0.5]))
    out, en = render(tmp_path, results)
    zh = (out / "zh" / "index.html").read_text(encoding="utf8")
    assert '<a class="switch" href="zh/" hreflang="zh-CN" lang="zh-CN">中文</a>' in en
    assert '<a class="switch" href="../" hreflang="en" lang="en">English</a>' in zh
    for html in (en, zh):
        assert f'<link rel="alternate" hreflang="en" href="{page.PAGE_URL}">' in html
        assert f'<link rel="alternate" hreflang="zh-CN" href="{page.PAGE_URL}zh/">' in html
        assert f'<link rel="alternate" hreflang="x-default" href="{page.PAGE_URL}">' in html
    assert f'<link rel="canonical" href="{page.PAGE_URL}">' in en
    assert f'<link rel="canonical" href="{page.PAGE_URL}zh/">' in zh
    assert f'<meta property="og:url" content="{page.PAGE_URL}zh/">' in zh
    assert '<a href="../../">sports-video-coach</a>' in zh            # the site's home, one folder further up
    assert '<td class="num total">0.750</td><td class="num above">0.500</td>' in zh
    assert page_check.problems(out) == [] and page_check.problems(out / "zh") == []


def test_chinese_page_empty_state_and_clip_paths(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    out, _ = render(tmp_path, results)
    zh = (out / "zh" / "index.html").read_text(encoding="utf8")
    assert "还没有运行记录，来做第一个。" in zh and "<table" not in zh
    assert page_check.problems(out / "zh") == []
    clip = page.clip_block(True, "zh")
    assert 'src="../clip.mp4"' in clip and 'src="../clip.gif"' in clip and 'href="../clip.gif"' in clip


def test_chinese_diff_lines():
    assert page.diff_answer("count", 10, {"answer": 12}, "zh") == "多了 2"
    assert page.diff_answer("rate", 50, {"answer": 45}, "zh") == "偏低 10.0%"
    assert page.diff_answer("timestamps", [1.0, 2.0], {"answer": [1.0, 5.0]}, "zh") == \
        "2 个中有 1 个不在 0.5 s 内（在 2 s）；1 个对不上（在 5 s）"
    assert page.diff_answer("outcomes", ["made", "missed"], {"answer": ["made"]}, "zh") == "只答了 2 个中的 1 个"
    assert page.diff_answer("outcomes", ["made", "missed"], {"answer": ["missed", "missed"]}, "zh") == \
        "2 个中错 1 个（第 1 个答成 missed）"
    assert page.show_value("outcomes", ["made", "missed", "made"], "zh") == "进 2，不进 1"
    assert page.diff_answer("count", 10, {}, "zh") == "未记录回答"


def dataset_blocks(html: str) -> list[dict]:
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def test_dataset_structured_data_and_sitemap_lastmod(tmp_path):
    import xml.etree.ElementTree as ET
    from sports_video_coach import demo
    from sports_video_coach.bench import export
    results = tmp_path / "results"
    results.mkdir()
    write(results, "a.json", row("A", "m1", 0.9, [0.9, 0.9, 0.9], date="2026-10-22"))
    write(results, "b.json", row("B", "m2", 0.6, [0.6, 0.6, 0.6], date="2026-10-23"))
    write(results, "c.json", row("C", "m3", 0.5, [0.5, 0.5, 0.5], suite="x</script><!--", date="2026-10-21"))
    write(results, "floor.json", row(page.BASELINE_AGENT, "", 0.2, [0.2, 0.2, 0.2], date="2026-10-20"))
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitemap.xml").write_text(demo.sitemap_xml(), encoding="utf8")   # as `demo --site` leaves it
    out = site / "benchmark"
    assert page.main([str(results), str(out)]) == 0
    board = json.loads((out / export.NAME).read_text(encoding="utf8"))
    contenders = sum(len(b["contenders"]) for b in board["boards"])
    assert (board["runs"], contenders, len(board["boards"])) == (3, 3, 2)
    for lang, path in (("en", out / "index.html"), ("zh", out / "zh" / "index.html")):
        html = path.read_text(encoding="utf8")
        assert "x</script><!--" not in html.split("</head>")[0]          # the hostile suite name is escaped
        (ld,) = dataset_blocks(html)                                    # exactly one, and it parses
        assert ld["@context"] == "https://schema.org" and ld["@type"] == "Dataset"
        assert ld["url"] == page.URLS[lang] and ld["inLanguage"] == page.TAGS[lang]
        assert ld["name"] and 50 <= len(ld["description"]) <= 5000
        assert ld["sameAs"] == page.REPO_URL and ld["license"] == page.LICENSE_URL
        assert ld["creator"] == {"@type": "Person", "name": "mariusDing", "url": "https://github.com/mariusDing"}
        assert ld["dateModified"] == "2026-10-23"                       # the newest result file, not the build
        assert ld["keywords"] and ld["measurementTechnique"]
        assert {v["name"] for v in ld["variableMeasured"]} == {k for k, _, _ in page.KINDS} | {"total", "above chance"}
        assert [(d["@type"], d["contentUrl"], d["encodingFormat"]) for d in ld["distribution"]] == [
            ("DataDownload", f"{page.PAGE_URL}leaderboard.json", "application/json"),
            ("DataDownload", page.RESULTS_URL, "application/json")]
        assert "x</script><!--" in ld["description"]                    # escaped in the page, intact once parsed
        numbers = (f"{board['runs']} scored runs", f"{contenders} contenders", f"{len(board['boards'])} boards",
                   "4 result files", "1 blind baselines") if lang == "en" else (
                   f"{board['runs']} 次计分运行", f"{contenders} 个参赛者", f"{len(board['boards'])} 张", "4 个结果文件")
        assert all(n in ld["description"] for n in numbers), ld["description"]
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = ET.fromstring((site / "sitemap.xml").read_bytes()).findall("s:url", ns)
    lastmod = {u.find("s:loc", ns).text: getattr(u.find("s:lastmod", ns), "text", None) for u in urls}
    assert list(lastmod) == list(demo.SITE_PAGES)
    assert {u: d for u, d in lastmod.items() if d} == {u: "2026-10-23" for u in demo.SITE_PAGES
                                                        if u.startswith(page.PAGE_URL)}
    assert page_check.problems(out) == [] and page_check.problems(out / "zh") == []


def test_dataset_date_counts_baselines_and_skips_bad_dates():
    rows = [row("A", "m", 0.5, [0.5] * 3, date="2026-10-22"), row(page.BASELINE_AGENT, "", 0.1, [0.1] * 3,
                                                                    date="2026-10-24"),
            row("B", "m", 0.5, [0.5] * 3, date="someday")]
    assert page.newest_date(rows) == "2026-10-24"
    assert page.newest_date([row("A", "m", 0.5, [0.5] * 3, date="")]) is None


def test_no_runs_no_dataset_and_sitemap_untouched(tmp_path):
    from sports_video_coach import demo
    results = tmp_path / "results"
    results.mkdir()
    write(results, "floor.json", row(page.BASELINE_AGENT, "", 0.2, [0.2, 0.2, 0.2]))
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitemap.xml").write_text(demo.sitemap_xml(), encoding="utf8")
    assert page.main([str(results), str(site / "benchmark")]) == 0
    assert dataset_blocks((site / "benchmark" / "index.html").read_text(encoding="utf8")) == []
    assert page.sitemap([], site / "benchmark") is False
    assert "<lastmod>" in (site / "sitemap.xml").read_text(encoding="utf8")   # the floor file has a date
    other = tmp_path / "elsewhere"                                             # not the demo site: left alone
    other.mkdir()
    (other / "sitemap.xml").write_text("<urlset/>", encoding="utf8")
    assert page.sitemap([row("A", "m", 0.5, [0.5] * 3)], other / "benchmark") is False
    assert (other / "sitemap.xml").read_text(encoding="utf8") == "<urlset/>"


def test_dataset_numbers_on_the_published_results():
    from pathlib import Path
    from sports_video_coach.bench import export
    rows, notes = page.load(Path(__file__).resolve().parent.parent / "benchmark" / "results")
    (ld,) = dataset_blocks(page.dataset_ld(rows))
    board = export.leaderboard(rows, notes)
    assert f"{board['runs']} scored runs" in ld["description"] and board["runs"] > 0
    assert f"{sum(len(b['contenders']) for b in board['boards'])} contenders" in ld["description"]
    assert ld["dateModified"] == page.newest_date(rows) and 50 <= len(ld["description"]) <= 5000


def test_submit_section_says_first_pr_checks_wait_for_approval(tmp_path):
    # GitHub holds a first-time contributor's fork PR runs until a maintainer approves them
    results = tmp_path / "results"
    results.mkdir()
    out, html = render(tmp_path, results)
    zh = (out / "zh" / "index.html").read_text(encoding="utf8")
    en_submit = html[html.index('<h2 id="submit">'):]
    zh_submit = zh[zh.index('<h2 id="submit">'):]
    assert "Your first PR's checks start after a maintainer approves them; we reply within a day." in en_submit
    assert "你的第一个 PR 的检查要等维护者批准后才会运行；我们一天内回复。" in zh_submit
