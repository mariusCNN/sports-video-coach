"""shot-locate: which shots get a sheet, the court grid, merging agent answers into the trips, the run steps."""
import json

import cv2
import numpy as np

from hoop_tape_miner import court
from hoop_tape_miner import shot_locate as L


def trip(pid, shot, offence="us", **kw):
    t = {"schema": 2, "pid": pid, "trip": 1, "t0": pid * 10.0, "t1": pid * 10.0 + 8, "offence": offence,
         "result": "missed", "shot": shot, "fts": None, "foul": None, "confidence": "medium"}
    t.update(kw)
    return t


def review(tmp_path, trips):
    r = tmp_path / "review_v1"
    r.mkdir()
    (r / "part1.json").write_text(json.dumps([{"pid": p, "start": 0, "end": 1, "side": "right"} for p in (1, 2, 3)]),
                                  encoding="utf8")
    (r / "coach_part1.json").write_text(json.dumps(trips), encoding="utf8")
    return r


SHOTS = [trip(1, {"t": 15.0, "shooter": "7", "made": False, "zone": "three"}),
         trip(2, {"t": None, "shooter": None, "made": None, "zone": "rim"}, evidence={"shot": [24.0, 25.5]}),
         trip(3, None, result="turnover")]


def test_shot_list_takes_release_times_and_the_attacked_half(tmp_path):
    shots = L.shot_list(review(tmp_path, SHOTS))
    assert [(s["n"], s["pid"], s["t"], s["side"], s["zone"]) for s in shots] == [
        (1, 1, 15.0, "right", "three"), (2, 2, 25.5, "right", "rim")]   # no shot.t: the last evidence time


def test_zone_of_a_spot_matches_the_film_review_zones():
    hx, hy = court.hoop_xy("right")
    assert L.zone_of([hx - 1.0, hy], "right") == "rim"
    assert L.zone_of([court.LENGTH - 5.0, 6.0], "right") == "paint_non_rim"
    assert L.zone_of([hx - 5.0, hy], "right") == "midrange"
    assert L.zone_of([hx - 7.5, hy], "right") == "three"
    assert L.zone_of([27.0, 0.5], "right") == "three"                      # corner, outside the straight line
    assert L.zone_of([1.0, 7.0], "left") == "rim"


def test_grid_is_drawn_on_the_attacked_half_only():
    # a top-down camera: 40 px per metre, court x to the right, y down
    H = np.array([[40.0, 0, 20], [0, 40.0, 20], [0, 0, 1]])
    out = L.draw_grid(np.zeros((680, 1180, 3), np.uint8), H, "right")
    assert out[20 + 40 * 7, 20 + 40 * 20].any()                  # x20 / y7 crossing on the right half: drawn
    assert not out[20 + 40 * 7 + 20, 20 + 40 * 5 + 20].any()     # left half, between court lines: untouched
    assert L.half_range("left") == (0.0, 14.0) and L.half_range(None) == (0.0, court.LENGTH)


def test_nearest_camera_skips_far_samples():
    cams = dict(frame=np.array([0, 10]), t=np.array([0.0, 1.0]), H=np.stack([np.eye(3)] * 2),
                quality=np.array([0.9, np.nan]))
    H, t, q = L.nearest_camera(cams, 0.2)
    assert t == 0.0 and q == 0.9
    assert L.nearest_camera(cams, 1.3)[1:] == (1.0, None)
    assert L.nearest_camera(cams, 2.0) == (None, None, None)


def test_build_writes_one_sheet_per_shot_with_a_time(tmp_path):
    video = tmp_path / "v.mp4"
    w = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 180))
    for _ in range(40):
        w.write(np.full((180, 320, 3), 90, np.uint8))
    w.release()
    shots = [dict(n=1, part="coach_part1.json", pid=1, trip=1, t=2.0, shooter="4", offence="us", zone="rim",
                  made=True, side="left"),
             dict(n=2, part="coach_part1.json", pid=2, trip=1, t=None, shooter=None, offence="us", zone=None,
                  made=None, side=None)]
    cams = dict(frame=np.arange(40), t=np.arange(40) / 10, H=np.stack([np.diag([10.0, 10.0, 1.0])] * 40),
                quality=np.full(40, 0.9))
    res = L.build(cv2.VideoCapture(str(video)), shots, tmp_path, cams)
    assert res[0]["sheet"] == "s01.jpg" and (tmp_path / "s01.jpg").is_file() and len(res[0]["tiles"]) == 6
    assert res[0]["tiles"][4] == {"t": 2.0, "cam_t": 2.0, "quality": 0.9} and res[1]["sheet"] is None
    assert [len(b) for b in L.batches([dict(s, sheet="x") for s in shots * 4], 3)] == [3, 3, 2]
    text = L.brief(L.BRIEF.read_text(encoding="utf8"), 1, res[:1], tmp_path)
    assert "S01" in text and "answers_1.json" in text and '"xy": [24.3, 3.1]' in text


def test_merge_takes_confident_spots_and_never_guesses(tmp_path):
    r = review(tmp_path, SHOTS + [trip(4, {"t": 40.0, "shooter": "9", "made": True, "zone": "three"})])
    loc = r / "locate"
    loc.mkdir()
    tiles = [dict(t=14.0 + k * 0.3, cam_t=14.0 + k * 0.3, quality=0.9) for k in range(6)]
    meta = [dict(n=1, part="coach_part1.json", pid=1, trip=1, side="right", zone="three", sheet="s01.jpg", tiles=tiles),
            dict(n=2, part="coach_part1.json", pid=2, trip=1, side="right", zone="rim", sheet="s02.jpg", tiles=tiles),
            dict(n=3, part="coach_part1.json", pid=4, trip=1, side="right", zone="three", sheet=None, tiles=[])]
    (loc / "shots.json").write_text(json.dumps({"shots": meta}), encoding="utf8")
    (loc / "answers_1.json").write_text(json.dumps([
        {"n": 1, "xy": [24.04, 7.5], "tile": 4, "confidence": "high", "note": "feet on x24"},
        {"n": 2, "xy": [26.0, 7.5], "tile": 3, "confidence": "low", "note": "feet hidden"}]), encoding="utf8")
    assert len(L.missing(r)) == 3
    log = L.merge(r)
    trips = json.loads((r / "coach_part1.json").read_text(encoding="utf8"))
    s1, s2, s4 = trips[0]["shot"], trips[1]["shot"], trips[3]["shot"]
    assert s1["xy"] == [24.0, 7.5] and s1["xy_src"]["tile_t"] == tiles[3]["t"] and s1["xy_src"]["confidence"] == "high"
    assert s2["xy"] is None and s2["xy_note"] == "unclear: feet hidden"
    assert s4["xy"] is None and "no release time" in s4["xy_note"]
    assert s1["zone"] == "three" and "near line" in s1["zone_flag"]   # 2.4 m out: within 0.5 m of the rim zone
    assert any("near line: spot reads paint_non_rim" in x for x in log)
    assert L.missing(r) == [] and L.conflicts(r) == []
    assert "reviewed zone" not in text_of_brief(loc)


def text_of_brief(loc):
    meta = json.loads((loc / "shots.json").read_text(encoding="utf8"))["shots"]
    return L.brief(L.BRIEF.read_text(encoding="utf8"), 1, [dict(m, t=1.0, shooter=None, offence="us") for m in meta if m["sheet"]],
                   loc)


def test_spot_decides_the_zone_but_never_a_made_shots_points():
    hx, hy = court.hoop_xy("right")
    miss = {"made": False, "points": 2, "zone": "rim", "xy": [hx - 5.0, hy]}           # 5 m out: clearly midrange
    assert L.settle_zone(miss, "right") == f"zone rim -> midrange (spot {miss['xy']})"
    assert (miss["zone"], miss["zone_review"], miss["points"], miss["points_review"]) == ("midrange", "rim", 2, 2)
    wing = {"made": False, "points": 2, "zone": "midrange", "xy": [hx - 4.0, hy + 6.5]}  # 7.6 m: beyond the arc
    L.settle_zone(wing, "right")
    assert (wing["zone"], wing["points"]) == ("three", 3)
    L.settle_zone(wing, "right")                                                     # re-merge: same result
    assert (wing["zone"], wing["zone_review"], wing["points_review"]) == ("three", "midrange", 2)
    L.settle_zone(wing, None)                                                        # spot gone: review restored
    assert (wing["zone"], wing["points"]) == ("midrange", 2) and "zone_review" not in wing
    made = {"made": True, "points": 2, "zone": "midrange", "xy": [hx - 4.0, hy + 6.5]}
    assert L.settle_zone(made, "right").startswith("confirm: made 2-pointer") and made["zone"] == "midrange"
    on_line = {"made": True, "points": 2, "zone": "midrange", "xy": [hx - 6.8, hy]}   # on the arc, foot on the line
    assert L.settle_zone(on_line, "right", arc="on") is None and "zone_flag" not in on_line


def test_check_lists_made_shots_to_confirm(tmp_path):
    t = trip(1, {"t": 15.0, "shooter": "7", "made": True, "points": 2, "zone": "midrange", "xy": [20.0, 13.0],
                 "zone_flag": "confirm: made 2-pointer but the spot reads three"}, result="made2")
    r = review(tmp_path, [t])
    assert L.missing(r) == [] and len(L.conflicts(r)) == 1


def test_run_waits_for_shot_locate_after_film_review(tmp_path):
    from hoop_tape_miner import run as R
    names = R.NAMES
    assert names.index("film-review") < names.index("locate-sheets") < names.index("shot-locate") < names.index("features")
    folder = tmp_path / "g"
    (folder / "run" / "review_v1").mkdir(parents=True)
    (folder / "game.json").write_text(json.dumps({"video": "v.mp4"}), encoding="utf8")
    (folder / "run" / "review_v1" / "coach_part1.json").write_text(json.dumps(SHOTS), encoding="utf8")
    g = R.Game.load(folder)
    step = next(s for s in R.STEPS if s.name == "shot-locate")
    assert step.done(g)                                    # no camera.npz: no grid to read a spot against
    (folder / "run" / "camera.npz").write_bytes(b"x")
    assert not step.done(g) and len(R.locate_errors(g)) == 2
    sheets = next(s for s in R.STEPS if s.name == "locate-sheets")
    assert sheets.args(g)[0][:2] == ["shot-locate", "sheets"] and not sheets.done(g)
    g.game["shot_locate"] = False
    assert step.done(g) and sheets.done(g)


def test_neighbouring_shots_fix_a_wrong_attacked_half():
    def s(n, t, offence, side):
        return dict(n=n, t=t, offence=offence, side=side)
    shots = [s(1, 10, "us", "right"), s(2, 20, "them", "left"), s(3, 30, "us", "right"),
             s(4, 40, "them", "right"),                                          # the other team, in our possession
             s(5, 50, "us", "left"),                                             # also wrong: one vote off
             s(6, 60, "them", "left"), s(7, 70, "us", "right"), s(8, 80, "us", "right")]
    L.vote_sides(shots)
    assert [x["side"] for x in shots] == ["right", "left", "right", "left", "right", "left", "right", "right"]
    assert "say left" in shots[3]["side_note"] and "side_note" not in shots[0]
    # half-time switch: the neighbours split, nothing changes
    half = [s(1, 10, "us", "right"), s(2, 20, "us", "right"), s(3, 30, "us", "right"),
            s(4, 40, "us", "left"), s(5, 50, "us", "left"), s(6, 60, "us", "left")]
    assert [x["side"] for x in L.vote_sides(half)] == ["right"] * 3 + ["left"] * 3
