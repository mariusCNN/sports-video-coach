"""`leaderboard.json` (`bench.export`), written by `bench page`: the same ranks and numbers as the page, from the
result files only."""
import json
from pathlib import Path

from sports_video_coach.bench import export, page
from sports_video_coach.bench.score import BASELINE_AGENT

RESULTS = Path(__file__).resolve().parent.parent / "benchmark" / "results"


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


def build(tmp_path, files: dict) -> dict:
    results = tmp_path / "results"
    results.mkdir()
    for name, data in files.items():
        (results / name).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf8")
    out = tmp_path / "site"
    assert page.main([str(results), str(out)]) == 0
    return json.loads((out / export.NAME).read_text(encoding="utf8"))


def test_empty_results_give_an_empty_board_list(tmp_path):
    data = build(tmp_path, {})
    assert data["schema"] == 1 and data["runs"] == 0 and data["boards"] == [] and data["latest_run"] is None
    assert data["page"] == page.PAGE_URL and data["results"] == page.RESULTS_URL


def test_ranks_floor_and_skipped_files(tmp_path):
    floor = row(BASELINE_AGENT, "", 0.5, [0.5, 0.5, 0.5])
    data = build(tmp_path, {
        "a.json": row("Agent A", "m1", 0.75, [1.0, 0.5, 0.75], wall_seconds=12.34, date="2026-10-25"),
        "b.json": row("Agent B", "m2", 1.0, [1.0, 1.0, 1.0], cost_usd=0.123456),
        "floor.json": floor,
        "broken.json": "{not json",
    })
    assert data["runs"] == 2 and data["latest_run"] == "2026-10-25"
    assert data["skipped"] == ["broken.json: not valid JSON (JSONDecodeError)"]
    (b,) = data["boards"]
    assert (b["track"], b["suite"], b["floor_file"]) == ("code", "svc-bench-1", "floor.json")
    assert [(c["rank"], c["agent"]) for c in b["contenders"]] == [("1", "Agent B"), ("2", "Agent A")]
    assert b["contenders"][0]["mean_above_chance"] == 1.0 and b["contenders"][0]["mean_cost_usd"] == 0.1235
    assert b["contenders"][1]["mean_wall_seconds"] == 12.3 and b["contenders"][1]["mean_cost_usd"] is None
    assert [r["file"] for r in b["runs"]] == ["b.json", "a.json"]    # best total first, the floor is not a run
    assert b["runs"][1]["above_chance"] == 0.5    # (1-.5)/.5=1, 0, (.75-.5)/.5=.5 -> mean .5


def test_tracks_and_suites_in_page_order(tmp_path):
    data = build(tmp_path, {
        "f.json": row("A", "m", 0.5, [0.5, 0.5, 0.5], track="frames", suite="svc-bench-3"),
        "c1.json": row("A", "m", 0.5, [0.5, 0.5, 0.5]),
        "c3.json": row("A", "m", 0.5, [0.5, 0.5, 0.5], suite="svc-bench-3"),
    })
    assert [(b["track"], b["suite"]) for b in data["boards"]] == [
        ("code", "svc-bench-3"), ("code", "svc-bench-1"), ("frames", "svc-bench-3")]


def test_published_results_match_the_page_summary():
    """On the real results folder, every board's contenders are the page's Summary, rank for rank."""
    rows, notes = page.load(RESULTS)
    data = export.leaderboard(rows, notes)
    assert data["runs"] == sum(1 for r in rows if not page.is_baseline(r)) > 0
    assert sum(len(b["runs"]) for b in data["boards"]) == data["runs"]
    for b in data["boards"]:
        mine = [r for r in rows if page.track_of(r) == b["track"] and page.suite_of(r) == b["suite"]]
        summary = page.summarize([r for r in mine if not page.is_baseline(r)], page.floor_of(mine))
        assert [c["rank"] for c in b["contenders"]] == page.ranks(summary)
        assert [(c["agent"], c["model"], c["settings"]) for c in b["contenders"]] == [s["key"] for s in summary]
    json.dumps(data)    # serialisable as is
