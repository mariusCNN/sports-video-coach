"""Regression checks for jersey identity and crop selection."""
import unittest

import numpy as np
import pandas as pd

from hoop_tape_miner.analyze import identities
from hoop_tape_miner.jersey import pick_crops


def pick_crops_reference(tr, all_df, k=4):
    """The original per-row filtering implementation, kept to prove the grouped version is equivalent."""
    tr = tr.assign(h=tr.y2 - tr.y1).query("h > 60")
    if tr.empty:
        return tr
    clean = []
    for idx, r in tr.iterrows():
        o = all_df[(all_df.frame == r.frame) & (all_df.index != idx)]
        ix = np.clip(np.minimum(o.x2, r.x2) - np.maximum(o.x1, r.x1), 0, None)
        iy = np.clip(np.minimum(o.y2, r.y2) - np.maximum(o.y1, r.y1), 0, None)
        frac = (ix * iy).max() / ((r.x2 - r.x1) * (r.y2 - r.y1)) if len(o) else 0
        clean.append(frac < 0.15)
    tr = tr[np.array(clean)]
    if tr.empty:
        return tr
    tr = tr.sort_values("frame")
    parts = np.array_split(np.arange(len(tr)), min(k, len(tr)))
    return pd.DataFrame([tr.iloc[ix].sort_values("h").iloc[-1] for ix in parts if len(ix)])


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tr = pd.DataFrame(dict(track=[1, 2, 3, 4], team=["us", "us", "us", "them"]))
        self.rosters = {"us": ["7", "5"], "them": ["9"]}

    def test_single_roster_read_is_accepted_when_vote_is_none(self):
        jersey = {"1": dict(number="none", reads=["7", "none"])}
        self.assertEqual(identities(self.tr, jersey, self.rosters), {1: "7"})

    def test_conflicting_reads_stay_unassigned(self):
        jersey = {"1": dict(number="none", reads=["7", "5"])}
        self.assertEqual(identities(self.tr, jersey, self.rosters), {})

    def test_single_read_off_roster_or_without_roster_is_rejected(self):
        jersey = {"1": dict(number="none", reads=["44"]), "4": dict(number="none", reads=["9"])}
        self.assertEqual(identities(self.tr, jersey, self.rosters), {4: "9"})
        self.assertEqual(identities(self.tr, jersey, {}), {})

    def test_voted_number_still_requires_roster(self):
        jersey = {"1": dict(number="7", reads=["7", "7"]), "2": dict(number="44", reads=["44", "44"])}
        self.assertEqual(identities(self.tr, jersey, self.rosters), {1: "7"})


class PickCropsTests(unittest.TestCase):
    def test_grouped_occlusion_check_matches_original(self):
        rng = np.random.default_rng(0)
        rows = []
        for f in range(40):
            for _ in range(rng.integers(1, 5)):
                x, y = rng.uniform(0, 400, 2)
                w, h = rng.uniform(30, 90), rng.uniform(40, 160)
                rows.append(dict(frame=f, x1=x, y1=y, x2=x + w, y2=y + h))
        all_df = pd.DataFrame(rows)
        tr = all_df.groupby("frame").head(1)
        got = pick_crops(tr, all_df, k=6)
        want = pick_crops_reference(tr, all_df, k=6)
        pd.testing.assert_frame_equal(got.reset_index(drop=True), want.reset_index(drop=True))

    def test_frame_missing_from_detections_is_treated_as_unoccluded(self):
        tr = pd.DataFrame(dict(frame=[1], x1=[0.0], y1=[0.0], x2=[50.0], y2=[100.0]))
        empty = tr.iloc[:0]
        self.assertEqual(len(pick_crops(tr, empty, k=4)), 1)


if __name__ == "__main__":
    unittest.main()
