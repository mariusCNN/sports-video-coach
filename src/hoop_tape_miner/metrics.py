"""Tactical metrics computed from court-space tracks and possession segments."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull

from .court import FT_LINE, LANE_WIDTH, LENGTH, THREE_PT_RADIUS, THREE_PT_SIDE, WIDTH, hoop_xy


def zone_of(x, y, side):
    """Court zone relative to the attacked basket: paint / midrange / three / backcourt."""
    hx, hy = hoop_xy(side)
    attack_x = x if side == "right" else LENGTH - x  # distance from midcourt toward basket
    if attack_x < LENGTH / 2:
        return "backcourt"
    bx = LENGTH if side == "right" else 0.0
    in_paint = abs(x - bx) <= FT_LINE and abs(y - WIDTH / 2) <= LANE_WIDTH / 2
    if in_paint:
        return "paint"
    d = np.hypot(x - hx, y - hy)
    corner = y < THREE_PT_SIDE or y > WIDTH - THREE_PT_SIDE
    return "three" if (d > THREE_PT_RADIUS or corner) else "midrange"


def hull_area(pts: np.ndarray) -> float:
    if len(pts) < 3:
        return np.nan
    try:
        return float(ConvexHull(pts).volume)
    except Exception:
        return np.nan


def mean_nn(pts: np.ndarray) -> float:
    if len(pts) < 2:
        return np.nan
    d = np.linalg.norm(pts[:, None] - pts[None], axis=2)
    np.fill_diagonal(d, np.inf)
    return float(d.min(1).mean())


def possession_metrics(tracks: pd.DataFrame, poss: pd.DataFrame) -> pd.DataFrame:
    """Per-possession spatial metrics for the offence and the defence."""
    rows = []
    by_frame = {f: g for f, g in tracks[tracks.team.isin(["us", "them"])].groupby("frame")}
    for pid, p in poss.iterrows():
        off, deff = p.offence, ("them" if p.offence == "us" else "us")
        side = p.side
        hx, hy = hoop_xy(side)
        spac, hull_o, hull_d, gap, zones, crossed_t = [], [], [], [], [], None
        for f in p.frames:
            g = by_frame.get(f)
            if g is None:
                continue
            o = g[g.team == off][["cx_s", "cy_s"]].to_numpy()
            d = g[g.team == deff][["cx_s", "cy_s"]].to_numpy()
            if len(o) >= 3:
                spac.append(mean_nn(o))
                hull_o.append(hull_area(o))
            if len(d) >= 3:
                hull_d.append(hull_area(d))
            if len(o) and len(d):
                dist = np.linalg.norm(o[:, None] - d[None], axis=2)
                gap.append(float(dist.min(1).mean()))  # how tightly attackers are guarded
            zones += [zone_of(x, y, side) for x, y in o]
            if crossed_t is None and len(o) >= 4:
                ax = o[:, 0] if side == "right" else LENGTH - o[:, 0]
                if (ax > LENGTH / 2).sum() >= 4:
                    crossed_t = g.t.iloc[0] - p.start
        zc = pd.Series(zones, dtype=object).value_counts(normalize=True)
        rows.append(dict(pid=pid, offence=off, side=side, period=p.period, start=p.start, dur=p.dur,
                         spacing=np.nanmean(spac) if spac else np.nan,
                         off_hull=np.nanmean(hull_o) if hull_o else np.nan,
                         def_hull=np.nanmean(hull_d) if hull_d else np.nan,
                         guard_gap=np.nanmean(gap) if gap else np.nan,
                         paint_share=zc.get("paint", 0.0), mid_share=zc.get("midrange", 0.0),
                         three_share=zc.get("three", 0.0), cross_time=crossed_t))
    return pd.DataFrame(rows).set_index("pid")


def player_summary(tracks: pd.DataFrame, track_ids, fps=10.0) -> dict:
    """Minutes, distance, speed and zone profile for one player (union of tracklets)."""
    t = tracks[tracks.track.isin(track_ids)].sort_values(["track", "frame"])
    if t.empty:
        return {}
    # OCR may assign the same jersey to two simultaneous tracklets. Count the
    # union for coverage, and omit ambiguous positions from movement estimates.
    tracked_s = t.frame.nunique() / fps
    ambiguous = t.duplicated("frame", keep=False)
    ambiguous_frames = t.loc[ambiguous, "frame"].nunique()
    t = t.loc[~ambiguous]
    step = t.groupby("track")[["cx_s", "cy_s"]].diff()
    dt = t.groupby("track").t.diff()
    v = np.hypot(step.cx_s, step.cy_s) / dt
    valid = (dt > 0) & (dt < 0.25) & (v < 9.5)
    v = v[valid]  # drop jumps / identity switches
    dist = float((v * dt[valid]).sum())
    return dict(tracked_minutes=tracked_s / 60, distance_m=dist,
                ambiguous_frames=int(ambiguous_frames), motion_samples=int(valid.sum()),
                distance_per_min=dist / max(tracked_s / 60, 1e-6),
                avg_speed=float(v.mean()), top_speed_p95=float(v.quantile(0.95)),
                sprint_share=float((v > 4.0).mean()))
