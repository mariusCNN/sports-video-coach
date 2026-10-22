"""Pass 2: on-court filtering, team classification and court-space tracking."""
from __future__ import annotations

import numpy as np
import pandas as pd
import supervision as sv
from trackers import ByteTrackTracker

from .court import LENGTH, WIDTH

COURT_MARGIN = 0.8  # metres outside the lines still counted as on court


def on_court(df: pd.DataFrame, margin=COURT_MARGIN) -> pd.Series:
    return df.cx.between(-margin, LENGTH + margin) & df.cy.between(-margin, WIDTH + margin)


def track_team(df_team: pd.DataFrame, frame_rate: float, scale=20.0, half=0.45) -> np.ndarray:
    """ByteTrack in court space using small pseudo-boxes around each foot point.

    Returns a tracker id per row (-1 when unassigned).
    """
    # trackers scales lost_track_buffer as 30 fps units (max gap = buffer / 30 s), so 60 = 2 s at any frame_rate
    tracker = ByteTrackTracker(lost_track_buffer=60, frame_rate=frame_rate,
                               track_activation_threshold=0.5, minimum_iou_threshold=0.05,
                               high_conf_det_threshold=0.55)
    ids = np.full(len(df_team), -1, int)
    pos = {idx: i for i, idx in enumerate(df_team.index)}
    for _, g in df_team.groupby("frame", sort=True):
        x, y = g.cx.to_numpy() * scale, g.cy.to_numpy() * scale
        h = half * scale
        xyxy = np.stack([x - h, y - h, x + h, y + h], 1)
        d = sv.Detections(xyxy=xyxy.astype(np.float32), confidence=g.conf.to_numpy().astype(np.float32),
                          data={"row": g.index.to_numpy()})
        out = tracker.update(d)
        if len(out):
            for r, tid in zip(out.data["row"], out.tracker_id):
                ids[pos[r]] = int(tid)
    return ids


def smooth_tracks(df: pd.DataFrame, win=5) -> pd.DataFrame:
    df = df.sort_values(["track", "frame"]).copy()
    for c in ("cx", "cy"):
        df[c + "_s"] = df.groupby("track")[c].transform(lambda s: s.rolling(win, center=True, min_periods=1).median())
    return df
