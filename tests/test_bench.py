import json
import shutil

import pytest

from sports_video_coach import bench, cli
from sports_video_coach.bench import score as S, suite

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")
TRUTH = {t.id: t.truth for t in suite.TASKS}


def test_suite_covers_every_kind_with_drawn_truth():
    assert suite.SUITE == "svc-bench-1"
    assert sorted({t.kind for t in suite.TASKS}) == sorted(suite.KINDS)
    assert TRUTH["jump-count"] == len(suite.JUMPS)
    assert TRUTH["cone-touches"] == [3.2, 5.4, 6.8, 10.4, 12.2, 14.8, 17.4]
    assert TRUTH["shot-outcomes"].count("made") == suite.SHOTS.count("made")
    assert all(t.seconds <= 40 for t in suite.TASKS)


@pytest.mark.parametrize("answer,want", [(13, 1.0), (12, 1 - 1 / 13), (26, 0.0), (40, 0.0), ("13", 0.0),
                                         (True, 0.0)])
def test_count(answer, want):
    assert S.score_count(13, answer)[0] == pytest.approx(want)


@pytest.mark.parametrize("answer,want", [(42, 1.0), (42.8, 1.0), (46.2, 1 - (0.1 - 0.02) / 0.18), (50.4, 0.0),
                                         (30, 0.0), (None, 0.0)])
def test_rate(answer, want):
    assert S.score_rate(42.0, answer)[0] == pytest.approx(want)


def test_timestamps_perfect_partial_missing_and_extra():
    truth = [3.2, 5.4, 6.8, 10.4]
    assert S.score_timestamps(truth, truth)[0] == 1.0
    assert S.score_timestamps(truth, [10.4, 3.2, 6.8, 5.4])[0] == 1.0          # order of the answer list is free
    assert S.score_timestamps(truth, [3.6, 5.4, 6.8, 10.4])[0] == 1.0          # 0.4 s off still full credit
    assert S.score_timestamps(truth, [4.45, 5.4, 6.8, 10.4])[0] == pytest.approx((3 + 0.5) / 4)  # 1.25 s off
    assert S.score_timestamps(truth, [3.2, 6.8, 10.4])[0] == pytest.approx(3 / 4)   # one missed, not shifted
    assert S.score_timestamps(truth, truth + [12.0, 15.0])[0] == pytest.approx(4 / 6)  # extras penalised
    assert S.score_timestamps(truth, [])[0] == 0.0
    assert S.score_timestamps(truth, "3.2")[0] == 0.0
    note = S.score_timestamps(truth, [3.2, 6.8, 10.4])[1]
    assert note == "3 of 4 within 0.5 s, 3 answered"


def test_outcomes():
    truth = ["made", "missed", "made", "missed"]
    assert S.score_outcomes(truth, truth)[0] == 1.0
    assert S.score_outcomes(truth, [" Made", "MISSED", "missed", "missed"])[0] == 0.75
    assert S.score_outcomes(truth, ["made", "missed"])[0] == 0.5               # short list: the rest are wrong
    assert S.score_outcomes(truth, truth + ["made", "made", "made", "made"])[0] == 0.5
    assert S.score_outcomes(truth, "made")[0] == 0.0


def test_missing_answer_scores_zero():
    row = S.score_task("jump-count", None)
    assert row["score"] == 0.0 and row["note"] == "missing answer" and row["answer"] is None


def fill(folder, answers):
    (folder / "answers.json").write_text(json.dumps({"suite": suite.SUITE, "answers": answers}), encoding="utf8")


def test_prepare_writes_no_truth(tmp_path, monkeypatch):
    drawn = []
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: lambda out: drawn.append(out) or out), raising=False)
    bench.prepare(tmp_path)
    assert [p.name for p in drawn] == [t.video for t in suite.TASKS]
    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    assert data == {"suite": suite.SUITE, "answers": {t.id: None for t in suite.TASKS}}
    md = (tmp_path / "TASKS.md").read_text(encoding="utf8")
    for t in suite.TASKS:
        assert t.id in md and t.video in md
    for v in TRUTH["cone-touches"] + [suite.STROKES_PER_MIN]:
        assert f"{v:g}" not in md
    assert "do not read" in md.lower()
    # answers already written are kept on a second prepare
    fill(tmp_path, {"jump-count": 3})
    bench.prepare(tmp_path)
    assert json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))["answers"]["jump-count"] == 3


def test_score_validate_round_trip_and_tampering(tmp_path, monkeypatch, capsys):
    fill(tmp_path, dict(TRUTH, **{"jump-count": 12, "stroke-rate": None}))
    monkeypatch.chdir(tmp_path)
    assert bench.main(["score", str(tmp_path), "--agent", "Claude Code", "--model", "Opus 5.5",
                       "--settings", "effort medium", "--by", "someone", "--wall-seconds", "412"]) == 0
    out = list((tmp_path / "benchmark" / "results").glob("*.json"))
    assert len(out) == 1 and out[0].name.endswith("-claude-code-opus-5-5.json")
    res = json.loads(out[0].read_text(encoding="utf8"))
    assert res["schema"] == 1 and res["suite"] == "svc-bench-1" and res["wall_seconds"] == 412
    assert res["contender"] == {"agent": "Claude Code", "agent_version": "", "model": "Opus 5.5",
                                "settings": "effort medium"}
    scores = {r["id"]: r["score"] for r in res["tasks"]}
    assert scores == {"jump-count": round(1 - 1 / 13, 3), "stroke-rate": 0.0, "cone-touches": 1.0,
                      "shot-outcomes": 1.0}
    assert res["total"] == round(sum(scores.values()) / 4, 3)
    assert "total" in capsys.readouterr().out

    assert bench.main(["validate", str(out[0])]) == 0
    for edit in (lambda r: r["tasks"][1].update(score=1.0),                       # a hand-raised score
                 lambda r: r.update(total=0.99),
                 lambda r: r["tasks"][0].update(truth=12),                         # truth moved to the answer
                 lambda r: r.update(schema=2),
                 lambda r: r["tasks"].pop()):
        bad = json.loads(out[0].read_text(encoding="utf8"))
        edit(bad)
        p = tmp_path / "bad.json"
        p.write_text(json.dumps(bad), encoding="utf8")
        assert bench.main(["validate", str(p)]) == 1
    keep = json.loads(out[0].read_text(encoding="utf8"))
    keep["extra_field"] = "kept"                                                   # unknown fields are fine
    p.write_text(json.dumps(keep), encoding="utf8")
    assert bench.main(["validate", str(p)]) == 0


def test_score_rejects_unknown_task_ids(tmp_path):
    fill(tmp_path, {"no-such-task": 1})
    with pytest.raises(SystemExit):
        S.read_answers(tmp_path)


def test_cli_registers_bench_and_page_delegates(monkeypatch):
    assert cli.resolve("bench")[0] == "sports_video_coach.bench"
    import sys
    import types
    fake = types.ModuleType("sports_video_coach.bench.page")
    fake.main = lambda argv: 7 if argv == ["--x"] else 0
    monkeypatch.setitem(sys.modules, "sports_video_coach.bench.page", fake)
    assert bench.main(["page", "--x"]) == 7


@needs_ffmpeg
def test_drawn_runner_touches_cones_at_the_truth(tmp_path):
    cv2 = pytest.importorskip("cv2")
    v = suite.draw_run(tmp_path / "run.mp4")
    cap = cv2.VideoCapture(str(v))
    xs = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        red = (img[:, :, 2] > 160) & (img[:, :, 1] < 90)
        xs.append(int(red.any(axis=0).argmax()))
    assert len(xs) == suite.RUN_VIDEO_S * suite.FPS
    moves = [b - a for a, b in zip(xs, xs[1:])]
    arrivals = [round(i / suite.FPS, 2) for i in range(1, len(moves))
                if moves[i - 1] and (moves[i] == 0 or (moves[i] > 0) != (moves[i - 1] > 0))]
    assert arrivals == TRUTH["cone-touches"]


@pytest.mark.parametrize("raw,floor,want", [(1.0, 0.5, 1.0), (0.75, 0.5, 0.5), (0.5, 0.5, 0.0), (0.2, 0.5, 0.0),
                                            (0.6, 0.0, 0.6), (0.9, 1.0, None), (None, 0.5, None), (0.5, None, None)])
def test_above_chance_task(raw, floor, want):
    got = S.above_chance_task(raw, floor)
    assert got == (None if want is None else pytest.approx(want))


def test_above_chance_total_is_mean_over_tasks_with_a_floor():
    rows = [{"id": "a", "score": 1.0}, {"id": "b", "score": 0.75}, {"id": "c", "score": 0.1}, {"id": "d", "score": 1}]
    floors = {"a": 0.5, "b": 0.5, "c": 0.3, "d": 1.0}          # d's floor is 1: it tells nothing, left out
    assert S.above_chance(rows, floors) == round((1.0 + 0.5 + 0.0) / 3, 3)
    assert S.above_chance(rows, {}) is None


def test_blind_baseline_is_deterministic_and_never_reads_the_truth(monkeypatch):
    import dataclasses

    from sports_video_coach.bench import baseline as B, suite2
    for name in ("svc-bench-1", "svc-bench-2"):
        first = B.answers(name)
        assert first == B.answers(name) == B.answers(name, "frames")      # same task text on both tracks
        assert all(v is not None for v in first.values())
    before = B.answers("svc-bench-2")
    assert before == {"dribble-count": 5, "squat-reps": 5, "cadence-change": 150.5,
                      "cone-touches-pan": [1.5, 4.25], "shot-outcomes-hard": ["made", "missed"] * 6}
    moved = [dataclasses.replace(t, truth=[99.0] if isinstance(t.truth, list) else 999) for t in suite2.TASKS]
    monkeypatch.setattr(suite2, "TASKS", moved)                            # every truth changed: answers stay
    assert B.answers("svc-bench-2") == before


def test_blind_baseline_result_file_validates(tmp_path):
    from sports_video_coach.bench import baseline as B
    out = tmp_path / "b.json"
    assert B.main(["--suite", "svc-bench-2", "--track", "frames", "--date", "2026-10-24", "--out", str(out)]) == 0
    res = json.loads(out.read_text(encoding="utf8"))
    assert res["contender"]["agent"] == S.BASELINE_AGENT and res["track"] == "frames"
    assert S.validate_file(out) == []
    assert S.default_path(res).name == "2026-10-24-blind-baseline-svc-bench-2-frames.json"
