"""Suite svc-bench-2 ("hard"): truth derived from the drawing parameters, the naive answers it is built to defeat,
scoring and the prepare / score / validate / page round trip with --suite."""
import json
import shutil

import pytest

from sports_video_coach import bench
from sports_video_coach.bench import page, score as S, suite, suite2

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")
TRUTH = {t.id: t.truth for t in suite2.TASKS}


def test_suite2_tasks_and_truth():
    assert suite2.SUITE == "svc-bench-2" and S.SUITES["svc-bench-2"] is suite2
    assert sorted({t.kind for t in suite2.TASKS}) == sorted(suite.KINDS)
    assert len(suite2.TASKS) == 5 and all(t.seconds <= 60 for t in suite2.TASKS)
    assert not set(suite2.BY_ID) & set(suite.BY_ID)          # no id is shared with suite 1
    assert TRUTH == {
        "dribble-count": 56, "squat-reps": 8, "cadence-change": 182.186,
        "cone-touches-pan": [3.6, 7.6, 10.6, 11.0, 11.4, 14.8, 19.6, 22.0, 23.2, 26.6],
        "shot-outcomes-hard": ["made", "missed", "missed", "made", "made", "missed", "made", "missed", "made",
                               "missed", "made", "missed"],
    }
    for t in suite2.TASKS:
        assert "hand-held" in t.question or "camera follows" in t.question


def test_suite2_truth_is_not_what_a_naive_reading_gives():
    # dribbles: both balls bounce, but only the blue player's count; nothing bounces while his ball is carried
    assert TRUTH["dribble-count"] == len(suite2.BLUE_BOUNCES)
    assert len(suite2.BLUE_BOUNCES) + len(suite2.GREEN_BOUNCES) > 100
    lo, hi = suite2.BLUE_HOLD
    assert not [f for f in suite2.BLUE_BOUNCES if lo < f < hi]
    # squats: 13 attempts, 8 good (shallow ones, a double dip and one that never locks out do not count)
    assert len(suite2.SQUATS) == 13 and TRUTH["squat-reps"] == 8
    assert suite2.good_reps([140, 270, 150]) == 0                 # back to the line is not above it
    assert suite2.good_reps([140, 270, 200, 270, 140, 270, 149]) == 2
    # cadence: the whole-video average is more than 2 % off the rate after the change
    whole = 60 * (len(suite2.STRIKES) - 1) * suite2.FPS / (suite2.STRIKES[-1] - suite2.STRIKES[0])
    assert abs(whole - TRUTH["cadence-change"]) / TRUTH["cadence-change"] > 0.05
    assert TRUTH["cadence-change"] == suite2.cadence_after(suite2.CADENCE_SPLIT)
    # cones: every arrival at a cone is not a touch (a pass-by and a pace change at a cone are not)
    at_cone = [t for t, x in suite2.RUN2[1:] if x in suite2.CONES]
    assert len(at_cone) > len(TRUTH["cone-touches-pan"]) and TRUTH["cone-touches-pan"] == suite2.cone_touches()
    # shots: pump fakes are not shots; the tip-in and the dip-in-pop-out are misses
    assert len(TRUTH["shot-outcomes-hard"]) == len(suite2.SHOTS2) == 12
    assert suite2.shot_outcome("airball-tipin") == "missed" and suite2.shot_outcome("in-out") == "missed"
    assert suite2.shot_outcome("fake+bank-in") == "made"



def test_suite2_no_uncounted_event_at_the_video_edges():
    """Nothing the rule counts happens in a video outside the truth: no extra floor touch, foot strike, lockout or
    touch before the first or after the last counted event."""
    fps, n = suite2.FPS, suite2.frames(suite2.DRIBBLE_S)
    for bounces, heights, hold in ((suite2.BLUE_BOUNCES, suite2.BLUE_H, suite2.BLUE_HOLD),
                                   (suite2.GREEN_BOUNCES, suite2.GREEN_H, None)):
        segs = suite2.dribble_segments(bounces, heights, hold)
        touches = [i for i in range(n) if suite2.height_at(segs, i / fps) <= 0.5]
        assert touches == [f for f in bounces if f < n]
    assert suite2.STRIKES[-1] < suite2.frames(suite2.CADENCE_S) <= suite2.STRIKES[-1] + min(suite2.STRIDE_B)
    ys = [suite2.plate_y(i / fps) for i in range(suite2.frames(suite2.SQUAT_S))]
    assert suite2.good_reps(ys) == TRUTH["squat-reps"]
    assert suite2.RUN2[-1][0] == suite2.RUN2_S and suite2.RUN2[-1][1] == suite2.RUN2[-2][1]   # still at the end
    assert suite2.SHOT_PATH.t <= suite2.SHOTS2_S

def test_suite2_scoring():
    assert S.score_task("dribble-count", 56, "svc-bench-2")["score"] == 1.0
    assert S.score_task("dribble-count", 57, "svc-bench-2")["score"] == round(1 - 1 / 56, 3)
    whole = 168.35
    assert S.score_task("cadence-change", whole, "svc-bench-2")["score"] == pytest.approx(1 - (0.0759 - 0.02) / 0.18,
                                                                                         abs=0.002)
    assert S.score_task("shot-outcomes-hard", ["made"] * 12, "svc-bench-2")["score"] == 0.5
    with pytest.raises(KeyError):
        S.score_task("dribble-count", 56)                      # suite 1 by default: not its task


def fake_draw(monkeypatch):
    drawn = []
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: lambda out: drawn.append(out) or out), raising=False)
    return drawn


def test_prepare_suite2_writes_no_truth(tmp_path, monkeypatch):
    drawn = fake_draw(monkeypatch)
    assert bench.main(["prepare", "--out", str(tmp_path), "--suite", "svc-bench-2"]) == 0
    assert [p.name for p in drawn] == [t.video for t in suite2.TASKS]
    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    assert data == {"suite": "svc-bench-2", "answers": {t.id: None for t in suite2.TASKS}}
    md = (tmp_path / "TASKS.md").read_text(encoding="utf8")
    assert md.startswith("# svc-bench-2:")
    for t in suite2.TASKS:
        assert t.id in md and t.video in md
    for v in TRUTH["cone-touches-pan"][1:] + [TRUTH["cadence-change"], 182.2]:
        assert f"{v:g}" not in md
    # answers of one suite are never silently mixed with another suite's tasks
    (tmp_path / "answers.json").write_text(json.dumps({"suite": "svc-bench-2", "answers": {"squat-reps": 8}}),
                                           encoding="utf8")
    with pytest.raises(SystemExit):
        bench.prepare(tmp_path)
    bench.prepare(tmp_path, suite="svc-bench-2")              # same suite: kept
    assert json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))["answers"] == {"squat-reps": 8}


def test_suite1_tasks_md_is_unchanged_by_the_suite_option():
    assert bench.tasks_md() == bench.tasks_md("svc-bench-1")
    assert bench.tasks_md().startswith("# svc-bench-1:")


def test_score_validate_suite2_round_trip(tmp_path, monkeypatch, capsys):
    answers = dict(TRUTH, **{"squat-reps": 13, "cadence-change": None})
    (tmp_path / "answers.json").write_text(json.dumps({"suite": "svc-bench-2", "answers": answers}),
                                           encoding="utf8")
    monkeypatch.chdir(tmp_path)
    assert bench.main(["score", str(tmp_path), "--agent", "Codex", "--model", "gpt-x", "--wall-seconds", "90"]) == 0
    out = list((tmp_path / "benchmark" / "results").glob("*.json"))
    assert len(out) == 1 and out[0].name.endswith("-codex-gpt-x-svc-bench-2.json")
    res = json.loads(out[0].read_text(encoding="utf8"))
    assert res["suite"] == "svc-bench-2" and res["schema"] == 1
    scores = {r["id"]: r["score"] for r in res["tasks"]}
    assert scores == {"dribble-count": 1.0, "squat-reps": 0.375, "cadence-change": 0.0, "cone-touches-pan": 1.0,
                      "shot-outcomes-hard": 1.0}
    assert res["total"] == round(sum(scores.values()) / 5, 3)
    assert "svc-bench-2:" in capsys.readouterr().out
    assert S.problems(res) == []
    for edit in (lambda r: r.update(suite="svc-bench-1"),             # moved to the other suite
                 lambda r: r.update(suite="svc-bench-9"),
                 lambda r: r["tasks"][2].update(score=1.0),
                 lambda r: r["tasks"][0].update(truth=57)):
        bad = json.loads(out[0].read_text(encoding="utf8"))
        edit(bad)
        assert S.problems(bad), edit


def test_page_has_one_table_per_suite_hard_first(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    for name, suite_name, tot in (("one.json", "svc-bench-1", 1.0), ("two.json", "svc-bench-2", 0.6)):
        res = S.result({}, "Agent " + suite_name[-1], "m", suite=suite_name)
        res.update(total=tot)
        (results / name).write_text(json.dumps(res), encoding="utf8")
    out = tmp_path / "site"
    assert page.main([str(results), str(out)]) == 0
    html = (out / "index.html").read_text(encoding="utf8")
    assert html.count("<table>") == 2 and html.count("<table class=\"summary\">") == 2   # runs + summary per suite
    assert html.index('id="svc-bench-2"') < html.index("Agent 2") < html.index('id="svc-bench-1"') \
        < html.index("Agent 1")
    assert ">dribble-count</th>" in html and ">jump-count</th>" in html
    assert "--suite svc-bench-2" in html


@needs_ffmpeg
def test_drawn_squat_video_shows_the_good_reps(tmp_path):
    """A careful pixel reading of the drawn video (plate centre vs the two white lines, both moving with the
    hand-held camera) gives the truth; fixed pixel rows do not."""
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    v = suite2.draw_squat(tmp_path / "squat.mp4")
    cap = cv2.VideoCapture(str(v))
    below, n, frames = False, 0, 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        frames += 1
        b, g, r = (img[:, :, i].astype(int) for i in range(3))
        white = ((b > 210) & (g > 210) & (r > 210))[:, 150:300].sum(1)
        ys = np.nonzero(white > 40)[0]
        groups = [x for x in np.split(ys, np.nonzero(np.diff(ys) > 3)[0] + 1) if len(x)]
        if len(groups) != 2:
            continue
        lock, depth = groups[0].mean(), groups[1].mean()
        plate = np.nonzero((r > 200) & (g > 160) & (b < 100))[0].mean()
        if plate > depth:
            below = True
        elif plate < lock and below:
            n, below = n + 1, False
    assert frames == round(suite2.SQUAT_S * suite2.FPS)
    assert n == TRUTH["squat-reps"]
