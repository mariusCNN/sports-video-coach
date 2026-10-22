"""Plus-minus from synthetic lineup intervals and an official score flow (no GPU, no video)."""
import json
import tempfile
import unittest
from pathlib import Path

from hoop_tape_miner.plusminus import compute, main, merge, score_events


def ev(t, team, pts, play_t=None):
    e = {"our_video_t": t, "team": team, "points": pts}
    if play_t is not None:
        e["play_t"] = play_t
    return e


OFFICIAL = {"score_flow": [ev(10, "us", 2), ev(30, "them", 2), ev(55, "them", 3), ev(70, "us", 1),
                           ev(90, "us", 2, play_t=79), ev(None, "them", 2)]}
LINEUP = {"us#7": [[0, 40], [60, 80]], "them#5": [[20, 100]]}


class PlusMinusTests(unittest.TestCase):
    def test_stints_on_off(self):
        r = compute(LINEUP, score_events(OFFICIAL))["us#7"]
        s1, s2 = r["stints"]
        self.assertEqual((s1["for"], s1["against"], s1["net"]), (2, 2, 0))
        self.assertEqual((s1["entry_score"], s1["exit_score"]), ([0, 0], [2, 2]))
        # 70 us+1, 79 us+2 (play_t beats our_video_t=90), stint end is exclusive
        self.assertEqual((s2["for"], s2["against"], s2["net"]), (3, 0, 3))
        self.assertEqual(r["on"], {"seconds": 60, "for": 5, "against": 2, "net": 3})
        self.assertEqual(r["off"], {"for": 0, "against": 3, "net": -3})  # off-video event ignored

    def test_opponent_perspective(self):
        r = compute(LINEUP, score_events(OFFICIAL))["them#5"]
        self.assertEqual((r["on"]["for"], r["on"]["against"], r["on"]["net"]), (5, 3, 2))

    def test_event_times_and_merge(self):
        evs = score_events(OFFICIAL, {"10": 41})
        self.assertEqual(evs[0][0], 30)  # them at 30, us moved to 41
        r = compute(LINEUP, evs, ["us#7"], merge_gap=20)["us#7"]
        self.assertEqual(len(r["stints"]), 1)
        self.assertEqual(merge([[50, 60], [0, 10], [12, 20]], 2), [[0, 20], [50, 60]])

    def test_windows_and_cli(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "lineup.json").write_text(json.dumps(LINEUP))
            (d / "fix.json").write_text(json.dumps({"us#7": [[0, 100]]}))
            (d / "off.json").write_text(json.dumps(OFFICIAL))
            main(["--lineup", str(d / "lineup.json"), "--lineup", str(d / "fix.json"), "--official",
                  str(d / "off.json"), "--player", "7", "--windows", "0-50,50-100", "--out", str(d / "pm.json")])
            r = json.loads((d / "pm.json").read_text())
            self.assertEqual(list(r), ["us#7"])
            self.assertEqual(r["us#7"]["on"]["net"], 0)  # 5-5 with the override covering everything
            self.assertEqual([w["on"] for w in r["us#7"]["windows"]], [[2, 2], [3, 3]])


if __name__ == "__main__":
    unittest.main()
