"""Suite svc-bench-3 ("eyes"): truth derived from the drawing parameters, the naive readings it is built to defeat,
deterministic drawing, no truth in a prepared folder, and scoring."""
import json

import numpy as np
import pytest

from sports_video_coach import bench
from sports_video_coach.bench import score as S, suite, suite3

TRUTH = {t.id: t.truth for t in suite3.TASKS}
SUITE = "svc-bench-3"


def test_suite3_tasks_and_truth():
    assert suite3.SUITE == SUITE and S.SUITES[SUITE] is suite3
    assert {t.kind for t in suite3.TASKS} == {"count", "outcomes", "timestamps", "rate"}
    assert len(suite3.TASKS) == 4 and all(t.seconds <= 60 for t in suite3.TASKS)
    assert TRUTH == {
        "juggle-touches": 47,
        "far-hoop-shots": ["made", "missed", "made", "missed", "missed", "made", "made", "missed", "missed",
                           "made", "missed", "made"],
        "pass-releases": [1.0, 3.0, 4.48, 5.28, 7.16, 9.48, 11.48, 12.16, 14.56, 15.84, 17.76, 19.32],
        "stroke-rate": 33.92,
    }
    for t in suite3.TASKS:
        assert "hand-held" in t.question


def test_suite3_truth_is_not_what_a_naive_reading_gives():
    n = suite3.JUG_N
    # juggling: double touches count twice, floor bounces not at all, the right player's touches not at all
    gaps = [b - a for a in suite3.JUG_TOUCHES for b in suite3.JUG_TOUCHES if 0 < b - a <= 6]
    assert len(gaps) >= 8
    bounces = [f for f, k, _ in suite3.JUG_CONTACTS if k == "N" and f < n]
    assert len(bounces) >= 5
    decoy = [f for f, k, _ in suite3.DECOY_CONTACTS if k == "F" and f < n]
    assert len(decoy) != TRUTH["juggle-touches"]
    # shots: three arrive at the rim behind the banner; fakes, rim-outs and a short one are misses
    assert len(suite3.FAR_COVERED) == 3 and TRUTH["far-hoop-shots"].count("made") == 6
    assert suite3.far_outcome("fake+in-out") == "missed" and suite3.far_outcome("front-up-in*") == "made"
    assert suite3.far_outcome("short") == "missed" and suite3.far_outcome("roll-out") == "missed"
    for ta in suite3.FAR_COVERED:                           # the banner is over the rim when the ball gets there
        assert abs(suite3.banner_x(ta) - suite3.RX) < suite3.BANNER_W / 2
    # passes: four fakes (no release), two one-touch passes, four releases behind the defender, a decoy pair
    assert sum(p[4] for p in suite3.PASSES) == 4 and sum(p[2] == "touch" for p in suite3.PASSES) == 2
    assert len(suite3.PASS_HIDDEN) == 4
    # rowing: the whole-video rate and the far boat's rate are both more than 2 % off the truth
    whole = 60 * (len(suite3.IN_VIDEO) - 1) * suite3.FPS / (suite3.IN_VIDEO[-1] - suite3.IN_VIDEO[0])
    far = [f for f in suite3.DECOY_CATCHES if suite3.frames(15.0) <= f < suite3.frames(suite3.ROW_S)]
    far_rate = 60 * (len(far) - 1) * suite3.FPS / (far[-1] - far[0])
    for wrong in (whole, far_rate):
        assert abs(wrong - TRUTH["stroke-rate"]) / TRUTH["stroke-rate"] > 0.05


def test_suite3_paths_match_the_truth():
    """The drawn ball paths touch where the truth says: the left ball meets the lifted foot at every counted touch
    and the floor at every bounce; every release starts a flight from a blue player's chest."""
    for f, kind, _ in suite3.JUG_CONTACTS:
        if f >= suite3.JUG_N:
            break
        (x, y), _, _ = suite3.juggle_path(suite3.JUG_CONTACTS, suite3.JUG_X).at(f / suite3.FPS)
        assert y == pytest.approx(suite3.TOUCH_DY if kind == "F" else suite3.FLOOR_DY)
        if kind == "F":
            assert suite3.foot_lift(suite3.JUG_CONTACTS, f / suite3.FPS) == pytest.approx(1.0)
    for r in TRUTH["pass-releases"]:
        (x, y), _, _ = suite3.PASS_PATH.at(r)
        assert y == pytest.approx(suite3.PASS_CHEST) and min(abs(x - s) for s in suite3.SPOTS.values()) < 1e-6
        (x2, _), _, _ = suite3.PASS_PATH.at(r + 0.2)
        assert abs(x2 - x) > 40                              # gone toward a teammate (a fake moves 16 px at most)


def raw_frames(draw, monkeypatch, picks=(0, 101, 333)):
    """The un-encoded frames a draw function paints (no ffmpeg): `render` is swapped for one that keeps a few."""
    got = []

    def render(out, seconds, world, cam, paint, seed):
        for i in picks:
            ox, oy = cam(i)
            f = world[oy:oy + 360, ox:ox + 640].copy()
            paint(f, i / suite3.FPS, ox, oy)
            got.append(f)
        return out
    monkeypatch.setattr(suite3, "render", render)
    draw("unused.mp4")
    return got


@pytest.mark.parametrize("task", [t.id for t in suite3.TASKS])
def test_suite3_drawing_is_deterministic(task, monkeypatch):
    draw = suite3.BY_ID[task].draw
    a, b = raw_frames(draw, monkeypatch), raw_frames(draw, monkeypatch)
    assert all(x.shape == (360, 640, 3) and np.array_equal(x, y) for x, y in zip(a, b))
    assert len({x.tobytes() for x in a}) == len(a)            # the scene moves


def fake_draw(monkeypatch):
    drawn = []
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: lambda out: drawn.append(out) or out), raising=False)
    return drawn


def test_prepare_suite3_writes_no_truth(tmp_path, monkeypatch):
    drawn = fake_draw(monkeypatch)
    assert bench.main(["prepare", "--out", str(tmp_path), "--suite", SUITE]) == 0
    assert [p.name for p in drawn] == [t.video for t in suite3.TASKS]
    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    assert data == {"suite": SUITE, "answers": {t.id: None for t in suite3.TASKS}}
    text = "\n".join(p.read_text(encoding="utf8") for p in tmp_path.rglob("*") if p.suffix in (".md", ".json"))
    assert text.startswith("# svc-bench-3:") or "# svc-bench-3:" in text
    for v in ["4.48", "5.28", "9.48", "15.84", "19.32", "33.92", "33.9"]:
        assert v not in text, v
    assert json.dumps(TRUTH["far-hoop-shots"]) not in text and json.dumps(TRUTH["far-hoop-shots"], indent=2) not in text


def test_suite3_scoring():
    for t in suite3.TASKS:                                    # a perfect answer
        assert S.score_task(t.id, t.truth, SUITE)["score"] == 1.0
    assert S.score_task("juggle-touches", 38, SUITE)["score"] == round(1 - 9 / 47, 3)
    assert S.score_task("far-hoop-shots", ["missed"] * 12, SUITE)["score"] == 0.5
    late = [r + 1.0 for r in TRUTH["pass-releases"]]
    assert 0 < S.score_task("pass-releases", late, SUITE)["score"] < 1
    assert S.score_task("pass-releases", TRUTH["pass-releases"][:6], SUITE)["score"] == 0.5
    assert S.score_task("stroke-rate", 31.9, SUITE)["score"] < 0.8     # the far boat's rate
    assert S.score_task("stroke-rate", None, SUITE)["score"] == 0.0


def test_score_validate_suite3_round_trip(tmp_path, monkeypatch):
    answers = dict(TRUTH, **{"juggle-touches": 40})
    (tmp_path / "answers.json").write_text(json.dumps({"suite": SUITE, "answers": answers}), encoding="utf8")
    monkeypatch.chdir(tmp_path)
    assert bench.main(["score", str(tmp_path), "--agent", "Codex", "--model", "gpt-x"]) == 0
    out = list((tmp_path / "benchmark" / "results").glob("*.json"))
    assert len(out) == 1 and out[0].name.endswith("-codex-gpt-x-svc-bench-3.json")
    res = json.loads(out[0].read_text(encoding="utf8"))
    assert res["suite"] == SUITE and S.problems(res) == []
    assert res["total"] == round((round(1 - 7 / 47, 3) + 3) / 4, 3)
