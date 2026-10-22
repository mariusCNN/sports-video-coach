"""Regression checks for evidence and tracking calculations used by the report."""
import unittest

import pandas as pd

from hoop_tape_miner.events import event_summary, reviewed_events
from hoop_tape_miner.metrics import player_summary


def shot(**changes):
    row = dict(pid=0, t=1.0, offence="us", event="shot", result="made", points=2,
               shot_type="layup", shooter=None, zone="paint", side="center",
               play_type="drive", rebound=None, defence_seen="unclear",
               confidence="high", notes="visible shot")
    return row | changes


class ReportingTests(unittest.TestCase):
    def test_unknown_and_low_confidence_results_do_not_become_misses_or_points(self):
        events = reviewed_events([shot(), shot(t=2, result=None, points=None),
                                  shot(t=3, result="missed", points=0),
                                  shot(t=4, confidence="low", points=3, zone="three")])
        s = event_summary(events)["teams"]["us"]
        self.assertEqual(s["reviewed_shot_attempts"], 4)
        self.assertEqual(s["resolved_shot_attempts"], 2)
        self.assertEqual(s["unknown_shot_outcomes"], 2)
        self.assertEqual(s["observed_points"], 2)

    def test_invalid_shot_outcome_is_rejected(self):
        for changes in ({"result": None}, {"result": "missed"}, {"points": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                reviewed_events([shot(**changes)])

    def test_empty_review_is_valid(self):
        s = event_summary(reviewed_events([]))
        self.assertEqual(s["event_count"], 0)
        self.assertEqual(s["teams"]["us"]["observed_points"], 0)

    def test_coverage_counts_frame_union_and_omits_ambiguous_motion(self):
        tracks = pd.DataFrame(dict(track=[1, 1, 1, 2], frame=[0, 1, 2, 1],
                                   t=[0, .1, .2, .1], cx_s=[0, .1, .2, 8], cy_s=[0]*4))
        s = player_summary(tracks, [1, 2])
        self.assertAlmostEqual(s["tracked_minutes"], 3 / 10 / 60)
        self.assertEqual(s["ambiguous_frames"], 1)
        self.assertAlmostEqual(s["distance_m"], .2)

    def test_distance_uses_actual_elapsed_time(self):
        tracks = pd.DataFrame(dict(track=[1, 1], frame=[0, 2], t=[0, .2],
                                   cx_s=[0, .4], cy_s=[0, 0]))
        self.assertAlmostEqual(player_summary(tracks, [1])["distance_m"], .4)


if __name__ == "__main__":
    unittest.main()
