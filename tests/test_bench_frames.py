"""The frames-only track of the benchmark: stills and contact sheets instead of videos, scored the same way."""
import json

import cv2
import numpy as np
import pytest

from sports_video_coach import bench, page_check
from sports_video_coach.bench import frames as F, page, score as S, suite, suite2


def tiny_video(path, n=60, size=(160, 90)):
    """A 25 fps video whose frame i is filled with grey level i (so a still shows which frame it is)."""
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), suite.FPS, size)
    for i in range(n):
        w.write(np.full((size[1], size[0], 3), i * 4, dtype=np.uint8))
    w.release()
    return path


@pytest.fixture
def fake_draw(monkeypatch):
    """Every task draws a 60-frame video instead of its real one."""
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: lambda out: tiny_video(out)), raising=False)


def test_stills_keep_every_step_th_frame_and_fill_sheets(tmp_path):
    video = tiny_video(tmp_path / "v.mp4", n=60)
    n = F.stills(video, "jump-count", tmp_path / "out")
    assert n == 30                                           # every 2nd of 60 frames
    names = sorted(p.name for p in (tmp_path / "out" / "frames" / "jump-count").glob("*.jpg"))
    assert names[0] == "t000.00.jpg" and names[1] == "t000.08.jpg" and names[-1] == "t002.32.jpg"
    sheets = F.sheets(tmp_path / "out", "jump-count")
    assert sheets == ["sheets/jump-count/sheet-001_t000.00-001.92.jpg",
                      "sheets/jump-count/sheet-002_t002.00-002.32.jpg"]   # 25 + 5 stills
    img = cv2.imread(str(tmp_path / "out" / sheets[0]))
    assert img.shape[:2] == (F.ROWS * (F.THUMB[1] + F.SHEET_BAR), F.COLS * F.THUMB[0])
    full = cv2.imread(str(tmp_path / "out" / "frames" / "jump-count" / "t000.00.jpg"))
    assert full.shape[:2] == (90 + F.BAR, 160)               # the label bar is added under the picture


def test_prepare_frames_writes_stills_and_no_video_or_truth(tmp_path, fake_draw):
    made = bench.prepare(tmp_path, suite=suite2.SUITE, track="frames")
    assert made == [tmp_path / "sheets" / t.id for t in suite2.TASKS]
    assert not list(tmp_path.rglob("*.mp4")) and not (tmp_path / ".partial").exists()
    for t in suite2.TASKS:
        assert F.sheets(tmp_path, t.id) and list((tmp_path / "frames" / t.id).glob("t*.jpg"))
    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    assert data == {"suite": suite2.SUITE, "track": "frames", "answers": {t.id: None for t in suite2.TASKS}}
    md = (tmp_path / "TASKS.md").read_text(encoding="utf8")
    assert "frames track" in md and "Do not run code" in md and "do not read" in md.lower()
    for t in suite2.TASKS:
        assert t.id in md and f"`{F.sheets(tmp_path, t.id)[0]}`" in md and t.video not in md
    for v in suite2.BY_ID["cone-touches-pan"].truth + [suite2.BY_ID["cadence-change"].truth]:
        assert f"{v:g}" not in md
    # answers of the frames track are not overwritten by a code-track prepare
    data["answers"]["squat-reps"] = 8
    (tmp_path / "answers.json").write_text(json.dumps(data), encoding="utf8")
    with pytest.raises(SystemExit, match="track 'frames'"):
        bench.prepare(tmp_path, suite=suite2.SUITE)
    with pytest.raises(SystemExit, match="unknown track"):
        bench.prepare(tmp_path, suite=suite2.SUITE, track="ears")


def test_code_track_prepare_is_unchanged(tmp_path, fake_draw):
    bench.prepare(tmp_path)
    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    assert "track" not in data
    md = (tmp_path / "TASKS.md").read_text(encoding="utf8")
    assert "frames track" not in md and all(t.video in md for t in suite.TASKS)


def frames_result(tmp_path, monkeypatch, answers):
    (tmp_path / "answers.json").write_text(json.dumps({"suite": suite2.SUITE, "track": "frames",
                                                       "answers": answers}), encoding="utf8")
    monkeypatch.chdir(tmp_path)
    assert bench.main(["score", str(tmp_path), "--agent", "Claude Code", "--model", "m"]) == 0
    out = list((tmp_path / "benchmark" / "results").glob("*.json"))
    assert len(out) == 1
    return out[0]


def test_score_and_validate_a_frames_result(tmp_path, monkeypatch, capsys):
    f = frames_result(tmp_path, monkeypatch, {"squat-reps": 8, "dribble-count": 50})
    assert f.name.endswith("-claude-code-m-svc-bench-2-frames.json")
    res = json.loads(f.read_text(encoding="utf8"))
    assert res["track"] == "frames" and res["suite"] == suite2.SUITE
    scores = {r["id"]: r["score"] for r in res["tasks"]}
    assert scores["squat-reps"] == 1.0 and scores["dribble-count"] == round(1 - 6 / 56, 3)
    assert "frames track" in capsys.readouterr().out
    assert S.validate_file(f) == []
    res["track"] = "ears"
    assert any("track" in e for e in S.problems(res))
    # a code-track result never gets a track field
    code = S.result({}, "A", "m", suite=suite2.SUITE)
    assert "track" not in code and S.default_path(code).name.endswith("-a-m-svc-bench-2.json")


def test_unknown_track_in_answers_is_refused(tmp_path):
    (tmp_path / "answers.json").write_text(json.dumps({"suite": suite.SUITE, "track": "ears", "answers": {}}),
                                           encoding="utf8")
    with pytest.raises(SystemExit):
        S.answers_track(tmp_path)


def test_page_shows_tracks_apart_and_code_rows_as_before(tmp_path):
    code = S.result({"jump-count": 13}, "Code Agent", "model-c")
    frames = S.result({"squat-reps": 8}, "Eyes Agent", "model-e", suite=suite2.SUITE, track="frames")
    results = tmp_path / "results"
    results.mkdir()
    (results / "code.json").write_text(json.dumps(code), encoding="utf8")
    out = tmp_path / "site"
    assert page.main([str(results), str(out)]) == 0
    only_code = (out / "index.html").read_text(encoding="utf8")
    (results / "frames.json").write_text(json.dumps(frames), encoding="utf8")
    assert page.main([str(results), str(out)]) == 0
    html = (out / "index.html").read_text(encoding="utf8")
    lb, fr = html.index('id="leaderboard"'), html.index('id="frames"')
    assert lb < html.index("Code Agent") < fr < html.index("Eyes Agent")
    # the code track's tables are the same with or without frames rows
    cut = lambda h: h[h.index('id="leaderboard"'):h.index('id="frames"')]  # noqa: E731
    assert cut(html) == cut(only_code)
    assert 'id="frames-svc-bench-2"' in html and "No frames-only runs yet." in only_code
    assert page_check.problems(out) == []
