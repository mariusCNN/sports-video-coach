"""The effort chart (`bench.effort`): its data equals the result files, both languages render, the PNGs are written
and the benchmark page shows them in "What effort changed"."""
import json
import shutil
from pathlib import Path

import pytest

from sports_video_coach import page_check
from sports_video_coach.bench import effort, page

RESULTS = Path(__file__).resolve().parents[1] / "benchmark" / "results"


def fresh_frames_files() -> list[Path]:
    out = []
    for f in sorted(RESULTS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf8"))
        if d.get("seed") is not None and d.get("suite") == "svc-bench-3" and d.get("track") == "frames":
            out.append(f)
    return out


def bar(data: dict, model: str, setting: str) -> dict:
    g = next(g for g in data["groups"] if g["model"] == model)
    return next(b for b in g["bars"] if b["effort"] == setting)


def test_effort_of_reads_the_settings():
    assert effort.effort_of("frames track; claude -p --tools Read; default effort") == effort.DEFAULT
    assert effort.effort_of("frames track; claude -p --tools Read; effort high") == "high"
    assert effort.effort_of("Codex: ...; reasoning effort xhigh") == "xhigh"
    assert effort.effort_of("") == effort.DEFAULT
    assert effort.model_label("claude-sonnet-5-5", "Claude Code") == "Sonnet 5.5"
    assert effort.model_label("gpt-6-astra", "Codex") == "gpt-6-astra"


def test_chart_data_equals_the_result_files():
    rows, _ = page.load(RESULTS)
    data = effort.effort_data(rows)
    # every run of a charted contender is in exactly one bar, grouped by its settings' effort
    expect: dict[tuple[str, str], list[str]] = {}
    for f in fresh_frames_files():
        d = json.loads(f.read_text(encoding="utf8"))
        expect.setdefault((d["contender"]["model"], effort.effort_of(d["contender"]["settings"])), []).append(f.name)
    for g in data["groups"]:
        assert len(g["bars"]) >= 2
        for b in g["bars"]:
            assert b["files"] == sorted(expect[(g["model"], b["effort"])])
            assert b["n"] == len(b["files"])
            vals = [page.above_value(next(r for r in rows if r["_file"] == f), None) for f in b["files"]]
            assert (b["lo"], b["hi"]) == (round(min(vals), 3), round(max(vals), 3))
    charted = {g["model"] for g in data["groups"]}
    assert {"claude-sonnet-5-5", "claude-opus-5-5"} <= charted
    assert "claude-haiku-5-5" not in charted          # one effort setting only: nothing to compare
    # the runs the posts quote (a later run adds to a bar, so only bars no new run is expected in are pinned)
    sd = bar(data, "claude-sonnet-5-5", effort.DEFAULT)
    assert (sd["n"], sd["lo"], sd["hi"]) == (2, 0.413, 0.426)
    assert bar(data, "claude-sonnet-5-5", "high")["above"] == 0.994
    assert bar(data, "claude-opus-5-5", "low")["above"] == 0.778
    od = bar(data, "claude-opus-5-5", effort.DEFAULT)
    assert (od["n"], od["lo"], od["hi"]) == (2, 0.994, 1.0)
    mx = bar(data, "claude-sonnet-5-5", "max")
    assert mx["timed_out"] >= 1 and mx["lo"] == 0.0
    assert [b["effort"] for b in data["groups"][1]["bars"]][:2] == [effort.DEFAULT, "high"]   # default first


def runs_of(*specs) -> list[dict]:
    """Synthetic fresh-seed frames rows: (model, settings, above, wall, answered)."""
    rows = []
    for i, (model, settings, above, wall, answered) in enumerate(specs):
        rows.append({"schema": 1, "suite": "svc-bench-3", "track": "frames", "seed": 100 + i, "date": "2026-10-25",
                     "contender": {"agent": "Claude Code", "model": model, "settings": settings},
                     "tasks": [{"id": "x", "answer": 1 if answered else None, "score": above}],
                     "total": above, "wall_seconds": wall, "_file": f"{i:02d}.json", "_above": above})
    return rows


@pytest.fixture
def fake_above(monkeypatch):
    monkeypatch.setattr(page, "above_value", lambda r, floor: r["_above"])


def test_bars_label_n_range_time_and_a_timed_out_run(fake_above):
    rows = runs_of(("claude-m-1-0", "default effort", 0.4, 10, True), ("claude-m-1-0", "default effort", 0.5, 30, True),
                   ("claude-m-1-0", "effort max", 0.0, 1200.5, False), ("claude-m-1-0", "effort low", 0.7, 50, True),
                   ("claude-solo-1-0", "default effort", 0.9, 5, True))
    data = effort.effort_data(rows)
    assert [g["label"] for g in data["groups"]] == ["M 1.0"]
    bars = data["groups"][0]["bars"]
    assert [b["effort"] for b in bars] == ["default", "low", "max"]
    assert (bars[0]["n"], bars[0]["above"], bars[0]["lo"], bars[0]["hi"], bars[0]["secs"]) == (2, 0.45, 0.4, 0.5, 20)
    assert (bars[2]["no_answer"], bars[2]["timed_out"]) == (1, 1)
    assert effort.bar_note(bars[0], "en") == "n=2 · 0.400–0.500 · 20 s/run"
    assert effort.bar_note(bars[2], "en") == "n=1 · no answer, timed out at 1200 s"
    line = effort.lines(data)[0]
    assert line.startswith("M 1.0 · Claude Code: default effort: 0.450 mean, range 0.400–0.500 (2 runs, 20 s")
    assert "effort max: no answer, killed at the 1200 s time limit, scored 0 (1 run)" in line
    zh = effort.lines(data, "zh")[0]
    assert "默认 effort：平均 0.450" in zh and "到 1200 s 时限被终止" in zh


def test_no_answer_runs_inside_a_bar_are_named(fake_above):
    rows = runs_of(("claude-m-1-0", "default effort", 0.4, 10, True), ("claude-m-1-0", "effort max", 0.0, 1200, False),
                   ("claude-m-1-0", "effort max", 0.9, 800, True))
    b = effort.effort_data(rows)["groups"][0]["bars"][1]
    assert effort.bar_note(b, "en") == "n=2 · 0.000–0.900 · 1 no answer · 1000 s/run"
    assert "1 gave no answer" in effort.phrase(b)


def build(tmp_path) -> Path:
    results = tmp_path / "results"
    results.mkdir()
    for f in fresh_frames_files():
        shutil.copy(f, results / f.name)
    out = tmp_path / "site"
    assert page.main([str(results), str(out)]) == 0
    return out


def png_size(path: Path) -> tuple[int, int]:
    b = path.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")


def test_page_shows_the_chart_in_both_languages(tmp_path):
    pytest.importorskip("matplotlib")
    out = build(tmp_path)
    en = (out / "index.html").read_text(encoding="utf8")
    zh = (out / "zh" / "index.html").read_text(encoding="utf8")
    assert png_size(out / effort.NAMES["en"]) == effort.SIZE
    assert '<h4 id="effort">What effort changed</h4>' in en and 'src="effort.png"' in en
    assert '<a href="#effort">What effort changed</a>' in en
    assert "default effort: 0.419 mean, range 0.413–0.426 (2 runs" in en and "not a variance estimate" in en
    assert 'alt="Bar chart of mean score above chance by effort setting. Opus 5.5' in en
    # the section sits on the fresh-seed frames board, under its description
    assert en.index('id="frames-svc-bench-3-fresh"') < en.index('id="effort"')
    assert '<h4 id="effort">effort 改变了什么</h4>' in zh and "不是方差估计" in zh
    if effort.cjk_font():
        assert png_size(out / effort.NAMES["zh"]) == effort.SIZE and 'src="../effort-zh.png"' in zh
    assert page_check.problems(out) == [] and page_check.problems(out / "zh") == []


def test_without_a_cjk_font_the_zh_page_shows_the_english_chart(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    monkeypatch.setattr(effort, "cjk_font", lambda: None)
    out = build(tmp_path)
    assert not (out / effort.NAMES["zh"]).exists()
    assert 'src="../effort.png"' in (out / "zh" / "index.html").read_text(encoding="utf8")


def test_without_matplotlib_the_section_is_text_only(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "matplotlib", None)
    out = build(tmp_path)
    en = (out / "index.html").read_text(encoding="utf8")
    assert not (out / effort.NAMES["en"]).exists()
    assert '<h4 id="effort">' in en and "effort.png" not in en


def test_every_new_text_has_a_translation():
    for en in (effort.TITLE, effort.SUB, effort.FLOOR, effort.LEAD, effort.BOUND, effort.ALT,
               "No contender ran at two effort settings yet."):
        assert page.ZH[en]
