"""Coach review helpers: lineup intervals, on-court sets, part split, brief filling, sheet layout."""
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hoop_tape_miner import coach_review

from hoop_tape_miner.coach_review import (brief_values, compose, events_text, fill_brief, intervals, lineup_intervals,
                                      on_court, split_parts, window_events)


class CoachReviewTests(unittest.TestCase):
    def test_intervals_gap_fill_and_min_length(self):
        ts = list(np.arange(0, 20, 1.0)) + [60, 61] + list(np.arange(100, 130, 2.0))
        self.assertEqual(intervals(ts, gap=25, min_len=8), [(0.0, 19.0), (100.0, 128.0)])

    def test_lineup_split_by_period_and_roster(self):
        t = np.arange(0, 60, 1.0)
        tr = pd.DataFrame({"t": np.r_[t, t, t], "team": ["us"] * 60 + ["us"] * 60 + ["them"] * 60,
                           "number": ["7"] * 60 + ["99"] * 60 + [None] * 60})
        lu = lineup_intervals(tr, periods=[(0, 29), (31, 60)], rosters={"us": ["7", 9]})
        self.assertEqual(lu, {"us#7": [(0.0, 29.0), (31.0, 59.0)]})
        self.assertEqual(on_court(lu, 10, 20), {"us": ["7"], "them": []})
        self.assertEqual(on_court(lu, 28, 40)["us"], ["7"])  # overlap 9 of 12 s

    def test_events_window_and_text(self):
        flow = [{"our_video_t": 61.5, "team": "us", "points": 2, "score_us": 2, "score_them": 0},
                {"our_video_t": None, "team": "them", "points": 2, "score_us": 2, "score_them": 2}]
        ev = window_events(flow, 50, 70)
        self.assertEqual(events_text(ev), "us +2 @~01:01 (2-0)")
        self.assertEqual(events_text([]), "no official scoring in window")

    def test_split_parts_balanced_by_sheets(self):
        man = [{"pid": i, "sheets": ["x"] * n} for i, n in enumerate([4, 4, 1, 1, 1, 1])]
        parts = split_parts(man, 2)
        self.assertEqual([[m["pid"] for m in p] for p in parts], [[0, 1], [2, 3, 4, 5]])
        self.assertEqual(len(split_parts(man[:1], 6)), 1)  # empty parts dropped

    def test_fill_brief_leaves_unknown_braces(self):
        s = fill_brief("Us {us_team} vs {them_team}, part {part}/{n_parts}; json {\"a\": 1} {other}",
                       {"us_team": "A", "them_team": "B", "part": 2, "n_parts": 6})
        self.assertEqual(s, "Us A vs B, part 2/6; json {\"a\": 1} {other}")

    def test_sheet_budget_preserves_all_possessions_in_order(self):
        man = [{"pid": i, "sheets": ["x"] * n} for i, n in enumerate([4, 4, 1, 1, 7, 0, 2])]
        parts = split_parts(man, 6, max_sheets=5)
        self.assertEqual([[m["pid"] for m in p] for p in parts], [[0], [1, 2], [3], [4], [5, 6]])
        self.assertEqual([m for p in parts for m in p], man)
        for part in parts:
            self.assertTrue(sum(len(m["sheets"]) for m in part) <= 5 or len(part) == 1)
        self.assertEqual(split_parts([], 6, max_sheets=5), [])

    def test_invalid_partition_budget(self):
        for n, cap in [(0, None), (-1, None), (6, 0), (6, -1)]:
            with self.assertRaises(ValueError):
                split_parts([], n, max_sheets=cap)

    def test_brief_values_and_part_names(self):
        game = {"name": "2025-03-08 league game", "us": {"team": "A", "colour": "red", "focus_player": "7"},
                "them": {"team": "B", "colour": "white"}, "result": {"halftime": {"us": 20, "them": 23}},
                "brief": {"watch_notes": "their #18 is misread"}}
        official = {"final": {"us": {"pts": 5}, "them": {"pts": 2}},
                    "totals": {"us": {"FGM-A": {"made": 2}, "2PM-A": {"made": 1}, "3PM-A": {"made": 1},
                                      "FTM-A": {"made": 0}, "PF": 3}},
                    "players": {"us": {"7": {"PTS": 3}, "15": {"PTS": 2}, "4": {"PTS": 0}}}}
        v = brief_values(game, official, Path("rev"))
        self.assertEqual((v["game_date"], v["focus_players"], v["watch_notes"]), ("2025-03-08", "#7", "their #18 is misread"))
        self.assertEqual(v["official_totals"], "Final 5-2 (us-them), halftime 20-23. us: made FG 2 (1 twos, 1 threes), "
                                               "FT 0, fouls 3; scorers #7 3, #15 2")
        s = fill_brief("# T\n\n<!--\nnote {us_team}\n-->\n\nRead {review_dir}/partN.json", v, part=3)
        self.assertEqual(s, f"# T\n\nRead {Path('rev').resolve().as_posix()}/part3.json")

    def test_compose_layout(self):
        lay = {"grid": [2, 2], "header": 28}
        sheet = compose([np.full((45, 80, 3), 255, np.uint8)] * 3, "hdr", lay)
        self.assertEqual(sheet.shape, (28 + 90, 160, 3))
        self.assertEqual(int(sheet[-1, -1].sum()), 0)  # padding tile is black


if __name__ == "__main__":
    unittest.main()


def test_official_is_optional(tmp_path, capsys):
    game = tmp_path / "game.json"
    game.write_text("{}")
    assert coach_review.load_official(None, game) == {"score_flow": []}
    assert "no official stats" in capsys.readouterr().out
    (tmp_path / "official.json").write_text('{"score_flow": [1]}')
    assert coach_review.load_official(None, game) == {"score_flow": [1]}
    with pytest.raises(SystemExit):
        coach_review.load_official(str(tmp_path / "missing.json"), game)


@pytest.mark.parametrize("options", [["--parts", "0"], ["--max-sheets", "-1"],
                                    ["--parts", "2", "--max-sheets", "5"]])
def test_partition_cli_rejects_invalid_options_before_io(options, tmp_path):
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exc:
        coach_review.main(["--run", str(tmp_path), "--game", "missing.json", "--out", str(out), *options])
    assert exc.value.code == 2
    assert not out.exists()


def test_sheet_budget_cli_reuses_existing_sheets(tmp_path, capsys):
    import json
    out = tmp_path / "review"
    out.mkdir()
    game = tmp_path / "game.json"
    game.write_text("{}", encoding="utf-8")
    manifest = [{"pid": i, "start": i * 20, "end": i * 20 + 19,
                 "sheets": [f"p{i}_{n}.jpg" for n in range(size)]}
                for i, size in enumerate([2, 3, 6, 2])]
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    coach_review.main(["--run", str(tmp_path), "--game", str(game), "--out", str(out),
                       "--max-sheets", "5", "--skip-sheets", "--brief", str(tmp_path / "missing.md")])
    parts = [json.loads(p.read_text()) for p in sorted(out.glob("part*.json"))]
    assert [[m["pid"] for m in p] for p in parts] == [[0, 1], [2], [3]]
    assert "possession 2 exceeds --max-sheets; kept intact" in capsys.readouterr().out
    assert not (out / ".sheets-incomplete").exists()
    assert (out / "review_policy.json").is_file()
    assert not list(out.glob("*.jpg"))  # No video or sheet regeneration needed.


def _flow(*ts, team="us"):
    return {"score_flow": [{"official_t": 100 + i, "our_video_t": t, "team": team, "points": 2,
                            "score_us": 2 * (i + 1), "score_them": 0} for i, t in enumerate(ts)]}


def test_event_windows_cover_lag():
    off = _flow(100.0)
    off["score_flow"].append({"official_t": 9, "our_video_t": None, "team": "them", "points": 1,
                              "score_us": 2, "score_them": 1})
    w = coach_review.event_windows(off, [])
    assert len(w) == 1
    # the scorer logs 10-30 s after the play: the window must reach back past that lag and a bit after
    assert w[0]["t0"] <= 100 - 30 and w[0]["t1"] >= 100 + 5
    assert w[0]["events"][0] == {"kind": "score", "t": 100.0, "team": "us", "points": 2, "official_t": 100,
                                      "score": "2-0"}
    assert coach_review.event_windows(_flow(10.0), [])[0]["t0"] == 0.0  # clipped at video start


def test_event_windows_merge_overlaps():
    w = coach_review.event_windows(_flow(300.0, 100.0, 120.0, 200.0), [], pre=35, post=6)
    assert [(x["t0"], x["t1"]) for x in w] == [(65.0, 126.0), (165.0, 206.0), (265.0, 306.0)]
    assert [len(x["events"]) for x in w] == [2, 1, 1]
    assert [e["t"] for e in w[0]["events"]] == [100.0, 120.0]
    assert w == coach_review.event_windows(_flow(300.0, 100.0, 120.0, 200.0), [])  # deterministic


def test_event_windows_fouls_and_teams():
    trips = [{"pid": 3, "trip": 1, "t0": 500.0, "t1": 520.0, "foul": {"t": 510.0, "by_team": "them", "by": "2",
                                                                       "on": "7", "type": "shooting"}},
             {"pid": 9, "trip": 1, "t0": 900.0, "t1": 915.0, "foul": {"t": None, "by_team": None, "type": "unclear"}},
             {"pid": 10, "trip": 1, "t0": 950.0, "t1": 960.0, "foul": None}]
    w = coach_review.event_windows({"score_flow": []}, trips)
    assert [(x["t0"], x["t1"]) for x in w] == [(475.0, 516.0), (880.0, 921.0)]
    assert w[0]["events"][0]["by"] == "2" and w[0]["events"][0]["t_known"]
    assert not w[1]["events"][0]["t_known"]  # fell back to the trip end
    assert coach_review.window_teams(w[0]) == ["them"] and coach_review.window_teams(w[1]) == ["them", "us"]
    md = coach_review.event_questions(1, w[0], ["ev01_00.jpg"], 4)
    assert "F1" in md and "ev01_00.jpg" in md and "who shot" in md


def test_candidate_tracks_nearest_rim():
    dets = pd.DataFrame({"team": ["us", "us", "them"], "track": [1, 2, 3], "cx_s": [3.0, 14.0, 26.0],
                         "cy_s": [7.5, 7.5, 9.0]})
    assert coach_review.candidate_tracks(dets, ["us", "them"]) == {1, 3}
    assert coach_review.candidate_tracks(dets, ["us"], max_dist=1.0) == set()


def _trip(pid, t0, t1, offence="us", **kw):
    x = {"schema": 2, "pid": pid, "trip": 1, "t0": t0, "t1": t1, "offence": offence, "result": "unclear",
         "shot": None, "fts": None, "foul": None, "evidence": {}, "confidence": "low"}
    x.update(kw)
    return x


def test_merge_event_answers_shots_fts_and_fouls():
    from hoop_tape_miner.coach_review import merge_event_answers
    trips = [_trip(1, 50, 62), _trip(2, 62, 80, "them", foul={"t": 70, "by_team": "us", "by": None, "on": None,
                                                                 "type": "unclear", "cause": None, "led_to": None},
                                     result="foul_ft", fts={"shooter": None, "made": 0, "att": 2})]
    wins = [{"window": 1, "t0": 30, "t1": 110,
             "events": [{"kind": "score", "t": 75}, {"kind": "foul", "t": 70, "pid": 2, "trip": 1}]}]
    ans = {1: {"events": [
        {"id": "S1", "team": "us", "kind": "shot", "shot_t": 58, "shooter": "7", "made": True, "points": 3,
         "evidence_t": [58], "confidence": "high"},
        {"id": "S2", "team": "them", "kind": "ft", "shot_t": 74, "shooter": "9", "made": True, "points": 1,
         "evidence_t": [74], "confidence": "medium"},
        {"id": "S3", "team": "us", "kind": "shot", "shot_t": 59, "shooter": "4", "made": True, "points": 2,
         "evidence_t": [], "confidence": "high"},           # no frame cited: ignored
        {"id": "S4", "team": "us", "kind": "shot", "shot_t": 300, "shooter": "4", "made": True, "points": 2,
         "evidence_t": [300], "confidence": "high"}],       # no trip there: unmatched, nothing created
        "fouls": [{"id": "F1", "t": 71, "by_team": "us", "by": "22", "on": "9", "type": "shooting_on_drive",
                   "real": True, "evidence_t": [71], "confidence": "medium"}]}}
    log = merge_event_answers(trips, wins, ans)
    a, b = trips
    assert a["result"] == "made3" and a["shot"]["shooter"] == "7" and a["result_v2m"] == "unclear"
    assert a["evidence"]["shot"] == [58]
    assert b["fts"] == {"shooter": "9", "made": 1, "att": 2}
    assert b["foul"]["by"] == "22" and b["foul"]["type"] == "shooting_on_drive" and b["foul_v2m"]["by"] is None
    assert len(trips) == 2 and any("unmatched" in line for line in log)


def test_merge_event_answers_removes_foul_not_on_film():
    from hoop_tape_miner.coach_review import merge_event_answers
    f = {"t": 70, "by_team": "us", "by": "5", "on": None, "type": "reach_in", "cause": None, "led_to": None}
    trips = [_trip(2, 62, 80, "them", foul=f)]
    wins = [{"window": 3, "t0": 35, "t1": 76, "events": [{"kind": "foul", "t": 70, "pid": 2, "trip": 1}]}]
    merge_event_answers(trips, wins, {3: {"fouls": [{"id": "F1", "real": False, "evidence_t": [69, 71],
                                                      "confidence": "high"}]}})
    assert trips[0]["foul"] is None and trips[0]["foul_v2m"] == f


def test_merge_event_answers_rule_out_jerseys():
    from hoop_tape_miner.coach_review import merge_event_answers
    trips = [_trip(1, 50, 62, result="made2", shot={"t": 58, "shooter": "14", "made": True, "points": 2}),
             _trip(2, 62, 80, "them", foul={"t": 70, "by_team": "us", "by": "44", "on": None, "type": "unclear",
                                            "cause": None, "led_to": None})]
    wins = [{"window": 1, "t0": 30, "t1": 110, "events": [{"kind": "foul", "t": 70, "pid": 2, "trip": 1}]}]
    ans = {1: {"events": [{"id": "S1", "team": "us", "kind": "shot", "shot_t": 58.5, "shooter": None, "made": True,
                           "points": 2, "evidence_t": [58.5], "confidence": "medium", "not_shooter": ["14"]}],
               "fouls": [{"id": "F1", "t": 70.5, "by_team": "us", "by": None, "evidence_t": [70.5],
                          "confidence": "medium", "real": True, "not_by": ["44"]}]}}
    merge_event_answers(trips, wins, ans)
    assert trips[0]["shot"]["shooter"] is None and trips[0]["shot_v2m"]["shooter"] == "14"
    assert trips[1]["foul"]["by"] is None and trips[1]["foul_v2m"]["by"] == "44"


def test_merge_event_answers_ignores_unknown_foul_type():
    from hoop_tape_miner.coach_review import merge_event_answers
    trips = [_trip(2, 62, 80, "them", foul={"t": 70, "by_team": "us", "by": None, "on": None, "type": "reach_in",
                                            "cause": None, "led_to": None})]
    wins = [{"window": 1, "t0": 30, "t1": 110, "events": [{"kind": "foul", "t": 70, "pid": 2, "trip": 1}]}]
    merge_event_answers(trips, wins, {1: {"fouls": [{"id": "F1", "t": 70, "by": "22", "type": "shooting",
                                                      "evidence_t": [70], "confidence": "high", "real": True}]}})
    assert trips[0]["foul"]["type"] == "reach_in" and trips[0]["foul"]["by"] == "22"


def test_merge_event_answers_respects_box_score():
    from hoop_tape_miner.coach_review import merge_event_answers
    trips = [_trip(1, 50, 62, result="made3", shot={"t": 58, "shooter": "7", "made": True, "points": 3}),
             _trip(2, 90, 99, result="made2", shot={"t": 95, "shooter": "9", "made": True, "points": 2})]
    wins = [{"window": 1, "t0": 30, "t1": 110, "events": []}]
    ans = {1: {"events": [{"id": "S1", "team": "us", "kind": "shot", "shot_t": 58, "shooter": "9", "made": True,
                           "points": 3, "evidence_t": [58], "confidence": "medium"}]}}
    log = merge_event_answers(trips, wins, ans, box={"us": {"9": 4, "7": 3}})
    assert trips[0]["shot"]["shooter"] == "7" and any("exceeds box score" in line for line in log)
    merge_event_answers(trips, wins, ans, box={"us": {"9": 5, "7": 3}})
    assert trips[0]["shot"]["shooter"] == "9"
