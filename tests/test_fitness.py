"""The fitness plugin: the exercise library, per-rep metrics from a pose track, sets.json checks, the page box."""
import json
import math

import numpy as np
import pytest

from sports_video_coach import plugin as registry
from svc_fitness import library, page, reps, unit

LIB = {
    "version": 1,
    "muscles": {"quads": {"zh": "股四头肌", "en": "quads", "region": "thigh"},
                "glutes": {"zh": "臀大肌", "en": "glutes", "region": "hip"},
                "hams": {"zh": "腘绳肌", "en": "hamstrings", "region": "thigh"}},
    "patterns": {"squat": {"zh": "蹲", "en": "squat"}, "hinge": {"zh": "髋铰链", "en": "hinge"}},
    "exercises": [
        {"id": "back_squat", "zh": "后蹲", "en": "Back squat", "aliases": ["high bar squat"], "pattern": "squat",
         "muscles": [{"m": "quads", "share": 60}, {"m": "glutes", "share": 40}], "cues": ["brace"],
         "views": {"side": ["depth", "trunk_lean", "tempo", "velocity_loss", "rep_count"]},
         "regress": ["rdl"], "progress": []},
        {"id": "rdl", "zh": "罗马尼亚硬拉", "en": "Romanian deadlift", "pattern": "hinge",
         "muscles": [{"m": "hams", "share": 50}, {"m": "glutes", "share": 50}], "cues": ["hips back"],
         "views": {"side": ["hip_extension", "bar_path"]}},
    ],
}


def test_the_plugin_is_registered():
    p = registry.get("fitness")
    assert p.name == "fitness"
    assert {"new", "library", "sets-check", "pose", "reps", "review-check"} <= set(p.stages)


def test_library_find_and_check():
    assert library.find("High-Bar Squat", LIB)["id"] == "back_squat"
    assert library.find("后蹲", LIB)["id"] == "back_squat"
    assert library.find("bench press", LIB) is None
    assert library.check(LIB) == []
    bad = json.loads(json.dumps(LIB))
    bad["exercises"][0]["muscles"][0]["share"] = 50
    bad["exercises"][1]["views"]["side"].append("speed")
    errs = library.check(bad)
    assert any("sum to 90" in e for e in errs) and any("'speed'" in e for e in errs)


def test_the_shipped_library_is_consistent():
    lib = library.load()
    assert library.check(lib) == []
    assert len(lib["exercises"]) >= 30
    for e in lib["exercises"]:
        assert e.get("refs") or "estimate" in e.get("muscles_basis", "").lower(), e["id"]  # sourced, or says it is a guess


def test_muscle_load_weights_by_reps_and_sums_to_100():
    share = library.muscle_load([{"exercise": "back_squat", "reps": 10}, {"exercise": "rdl", "reps": 10},
                                 {"exercise": "other", "reps": 5}], LIB)
    assert share == {"glutes": 45.0, "quads": 30.0, "hams": 25.0}
    assert library.muscle_load([], LIB) == {}


def squat_track(n_reps=5, fps=30.0, rep_s=2.0, depth=1.0, slow_last=1.0):
    """A side-view lifter facing +x squatting n_reps times: thigh and shin 50 px each (leg 100 px)."""
    ts, ds = [], []
    t = 0.0
    for _ in range(int(fps)):  # 1 s standing
        ts.append(t), ds.append(0.0)
        t += 1 / fps
    for k in range(n_reps):
        down, up = rep_s / 2, rep_s / 2 * (slow_last if k >= n_reps - 2 else 1.0)
        for i in range(int(down * fps)):
            ts.append(t), ds.append(depth * math.sin(math.pi / 2 * i / (down * fps)))
            t += 1 / fps
        for i in range(int(up * fps)):
            ts.append(t), ds.append(depth * math.cos(math.pi / 2 * i / (up * fps)))
            t += 1 / fps
    for _ in range(int(fps)):
        ts.append(t), ds.append(0.0)
        t += 1 / fps
    d = np.array(ds)
    kp = np.zeros((len(d), 17, 2))
    an = np.stack([np.zeros_like(d), np.full_like(d, 400.0)], -1)
    shin, thigh, lean = np.radians(30 * d), np.radians(80 * d), np.radians(35 * d)
    kn = an + 50 * np.stack([np.sin(shin), -np.cos(shin)], -1)
    hip = kn + 50 * np.stack([-np.sin(thigh), -np.cos(thigh)], -1)
    sh = hip + 50 * np.stack([np.sin(lean), -np.cos(lean)], -1)
    for i, pt in ((reps.L_AN, an), (reps.L_KN, kn), (reps.L_HIP, hip), (reps.L_SH, sh), (reps.L_WR, sh)):
        kp[:, i] = pt
        kp[:, i + 1] = pt + [3, 0]  # the far side, barely offset
    kp[:, reps.NOSE] = sh + [15, -20]
    conf = np.full((len(d), 17), 0.9)
    conf[:, [reps.R_HIP, reps.R_KN, reps.R_AN]] = 0.5
    return np.array(ts), kp, conf


def test_measure_counts_squat_reps_depth_lean_and_slowing():
    t, kp, conf = squat_track(slow_last=1.5)
    m = reps.measure(t, kp, conf, "squat", ["depth", "trunk_lean", "tempo", "velocity_loss"])
    assert m["n"] == 5 and m["side"] == "L"
    assert m["leg_px"] == pytest.approx(100, abs=1)
    r = m["reps"][0]
    assert 60 <= r["knee_min_deg"] <= 80  # shin 30°, thigh 80° from vertical -> about 70° at the knee
    assert r["hip_below_knee"] == pytest.approx(-0.09, abs=0.02)  # the hip stops just above the knee
    assert 30 <= r["trunk_lean_deg"] <= 40
    assert r["ecc_s"] == pytest.approx(0.85, abs=0.15) and r["con_s"] == pytest.approx(0.85, abs=0.15)
    assert r["pause_s"] < 0.4  # a smooth turn, no real pause
    assert 30 <= m["slowing_pct"] <= 70  # the last two up-phases take 1.5x


def test_a_held_bottom_counts_as_a_pause():
    t, kp, conf = squat_track(n_reps=3)
    hold = 30  # hold the bottom of every rep for 1 s
    d = kp[:, reps.L_HIP, 1]
    bottoms = reps.turns(d / 100, 30.0, 0.15)
    for c in reversed(bottoms):
        kp = np.concatenate([kp[:c], np.repeat(kp[c:c + 1], hold, 0), kp[c:]])
        conf = np.concatenate([conf[:c], np.repeat(conf[c:c + 1], hold, 0), conf[c:]])
    t = np.arange(len(kp)) / 30.0
    m = reps.measure(t, kp, conf, "squat", ["tempo"])
    assert m["n"] == 3 and all(1.0 <= r["pause_s"] <= 1.4 for r in m["reps"])


def test_measure_reports_only_the_metrics_the_view_supports():
    t, kp, conf = squat_track(n_reps=3)
    m = reps.measure(t, kp, conf, "squat", ["rep_count"])
    assert m["n"] == 3
    assert all(set(r) == {"n", "t"} for r in m["reps"]) and "slowing_pct" not in m


def test_a_hinge_turns_on_the_trunk_angle():
    t, kp, conf = squat_track(n_reps=4, depth=0.0)  # standing still: legs straight
    lean = np.radians(70 * np.abs(np.sin(np.pi * (t - 1) / 2.0)) * ((t > 1) & (t < 9)))  # 4 reps of 2 s
    hip = kp[:, reps.L_HIP]
    kp[:, reps.L_SH] = kp[:, reps.R_SH] = hip + 50 * np.stack([np.sin(lean), -np.cos(lean)], -1)
    kp[:, reps.L_WR] = kp[:, reps.R_WR] = kp[:, reps.L_SH] + [0, 40]
    m = reps.measure(t, kp, conf, "hinge", ["trunk_lean", "tempo"])
    assert m["n"] == 4
    assert all(65 <= r["trunk_lean_deg"] <= 72 for r in m["reps"])


def test_split_stance_depth_is_measured_on_the_front_leg():
    t, kp, conf = squat_track(n_reps=3)
    # the far leg (R) stands behind with a straight knee: its ankle is 60 px behind the hip
    kp[:, reps.R_AN] = kp[:, reps.L_HIP] + [-60, 80]
    kp[:, reps.R_KN] = kp[:, reps.L_HIP] + [-30, 40]
    kp[:, reps.R_HIP] = kp[:, reps.L_HIP]
    conf[:, [reps.R_HIP, reps.R_KN, reps.R_AN]] = 0.95  # the rear leg seen better: near_side would pick it
    m = reps.measure(t, kp, conf, "lunge", ["depth"])
    assert m["n"] == 3 and all(60 <= r["knee_min_deg"] <= 80 for r in m["reps"])


def test_a_known_count_drops_the_smaller_wobbles():
    t, kp, conf = squat_track(n_reps=4)
    wobble = (t > 2.95) & (t < 3.05)  # a 0.2 leg-length dip at the top between reps 1 and 2
    for i in (reps.L_HIP, reps.R_HIP):
        kp[wobble, i, 1] += 20
    assert reps.measure(t, kp, conf, "squat", [])["n"] == 5
    assert reps.measure(t, kp, conf, "squat", [], expect=4)["n"] == 4
    assert reps.measure(t, kp, conf, "squat", [], expect=6)["n"] == 5  # never invents a rep


def test_measure_ignores_shallow_bobbing_and_low_fps_tempo():
    t, kp, conf = squat_track(n_reps=4, depth=0.1)
    assert reps.measure(t, kp, conf, "squat", ["depth"])["n"] == 0  # hip moves ~0.05 leg lengths: not a rep
    t, kp, conf = squat_track(n_reps=4, fps=15)
    m = reps.measure(t, kp, conf, "squat", ["tempo", "depth"])
    assert m["n"] == 4 and "ecc_s" not in m["reps"][0]


def test_measure_without_a_lifter():
    t = np.arange(20) / 30
    m = reps.measure(t, np.zeros((20, 17, 2)), np.zeros((20, 17)), "squat", ["depth"])
    assert m["n"] == 0 and m["note"]


@pytest.fixture
def session(tmp_path):
    folder = tmp_path / "s"
    (folder / "run" / "frames").mkdir(parents=True)
    (folder / "analysis.json").write_text(json.dumps(
        {"plugin": "fitness", "kind": "analysis", "languages": ["zh"], "video": "video.mp4"}), encoding="utf8")
    (folder / "run" / "frames" / "frames.json").write_text(json.dumps({"duration_s": 120, "sheets": []}),
                                                           encoding="utf8")
    return unit.Session.load(folder)


def write_sets(g, sets):
    g.review.mkdir(parents=True, exist_ok=True)
    (g.review / "sets.json").write_text(json.dumps({"summary": "x", "sets": sets}), encoding="utf8")


def test_sets_check_names_each_problem(session):
    assert "missing" in unit.sets_errors(session)[0]
    ex = next(iter(library.exercises()))
    write_sets(session, [
        {"id": "S01", "start": "0:10", "end": "0:40", "exercise": ex, "view": "side", "reps": 5},
        {"id": "S01", "start": "0:50", "end": "0:45", "exercise": "front squat", "view": "top", "reps": 2.5},
        {"id": "S03", "start": "1:00", "end": "2:30", "exercise": "other", "name": "", "view": "front", "reps": None},
        {"id": "S04", "start": "1:00", "end": "1:20", "exercise": "other", "name": "长凳跳", "view": "unclear",
         "reps": None},
    ])
    errs = unit.sets_errors(session)
    assert not [e for e in errs if e.startswith("set S01:") and "duplicate" not in e and "after start" not in e
                and "view" not in e and "reps" not in e and "library id" not in e]
    assert any("duplicate" in e for e in errs)
    assert any("end is not after start" in e for e in errs)
    assert any("did you mean 'front_squat'" in e for e in errs)
    assert any("`view`" in e for e in errs) and any("`reps`" in e for e in errs)
    assert any(e.startswith("set S03:") and "after the video ends" in e for e in errs)
    assert any(e.startswith("set S03:") and "library id" in e for e in errs)
    assert not any(e.startswith("set S04") for e in errs)


def test_pose_is_done_when_every_measured_set_has_a_track(session):
    ex = next(iter(library.exercises()))
    write_sets(session, [{"id": "S01", "start": "0:10", "end": "0:40", "exercise": ex, "view": "side"},
                         {"id": "S02", "start": "0:50", "end": "1:10", "exercise": ex, "view": "back"}])
    pose = session.run / "pose"
    pose.mkdir(parents=True)
    (pose / "status.json").write_text('{"pose": "yolo11s-pose"}', encoding="utf8")
    assert not unit.pose_done(session)
    (pose / "S01.npz").write_bytes(b"")
    assert unit.pose_done(session)  # a back-view set is not measured
    (pose / "status.json").write_text('{"pose": null}', encoding="utf8")
    (pose / "S01.npz").unlink()
    assert unit.pose_done(session)  # no pose model: nothing to wait for


def test_page_box_shows_the_muscle_map_and_the_set_table(session):
    write_sets(session, [{"id": "S01", "start": "0:10", "end": "0:40", "exercise": "front_squat", "view": "side",
                          "reps": 5}])
    (session.run / "reps").mkdir(parents=True)
    (session.run / "reps" / "reps.json").write_text(json.dumps(
        {"sets": {"S01": {"n": 5, "knee_min_deg_mean": 71.75, "slowing_pct": 20, "ecc_s_mean": 2.27,
                         "con_s_mean": 1.0}}}), encoding="utf8")
    html = page.box(session.folder, {}, ["zh"])
    assert "前蹲" in html and "72°" in html and "20%" in html and "2.3 / 1" in html


def test_page_box_names_other_exercises_per_language(session):
    write_sets(session, [{"id": "S01", "start": "0:10", "end": "0:40", "exercise": "other", "view": "side",
                          "name": {"zh": "摆臂", "en": "arm swings"}},
                         {"id": "S02", "start": "0:50", "end": "1:10", "exercise": "other", "view": "side",
                          "name": "box jump"}])
    html = page.box(session.folder, {}, [("zh", "zh-CN", "中文", "README.md"), ("en", "en", "English", "README.en.md")])
    assert "摆臂" in html and "arm swings" in html and "box jump" in html
    assert '<section class="fx" lang="zh-CN" data-lang="zh"><details>' in html  # first language shown, folded
    assert 'data-lang="en" hidden' in html
    assert unit.sets_errors(session) == []
