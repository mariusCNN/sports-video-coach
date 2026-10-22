"""Validate reviewed events and retain uncertainty in derived statistics."""
from __future__ import annotations

import math

import pandas as pd


FIELDS = ("pid", "t", "offence", "event", "result", "points", "shot_type", "shooter",
          "zone", "side", "play_type", "rebound", "defence_seen", "confidence", "notes")


def reviewed_events(rows: list[dict]) -> pd.DataFrame:
    """Reject malformed labels; unknown outcomes/points remain null."""
    for i, e in enumerate(rows):
        missing = set(FIELDS) - e.keys()
        if missing:
            raise ValueError(f"Event {i}: missing {sorted(missing)}")
        if e["offence"] not in ("us", "them") or e["confidence"] not in ("low", "medium", "high"):
            raise ValueError(f"Event {i}: invalid team or confidence")
        if not isinstance(e["pid"], int) or e["pid"] < 0:
            raise ValueError(f"Event {i}: invalid possession id")
        if not isinstance(e["t"], (int, float)) or not math.isfinite(e["t"]) or e["t"] < 0:
            raise ValueError(f"Event {i}: invalid timestamp")
        if e["event"] not in ("shot", "free_throws", "turnover", "foul", "end_of_period", "other"):
            raise ValueError(f"Event {i}: invalid event type")
        if e["result"] not in (None, "made", "missed") or e["points"] not in (None, 0, 1, 2, 3):
            raise ValueError(f"Event {i}: invalid result or points")
        if e["event"] == "shot":
            allowed = {None: (None,), "missed": (0,), "made": (2, 3)}[e["result"]]
            if e["points"] not in allowed:
                raise ValueError(f"Event {i}: shot result and points disagree")
    return pd.DataFrame(rows, columns=FIELDS).sort_values("t", kind="stable").reset_index(drop=True)


def resolved_events(events: pd.DataFrame) -> pd.DataFrame:
    """Low-confidence outcomes never contribute to makes or observed points."""
    out = events.copy()
    out.loc[out.confidence == "low", ["result", "points"]] = [None, float("nan")]
    return out


def event_summary(events: pd.DataFrame) -> dict:
    accepted = resolved_events(events)
    teams = {}
    for team in ("us", "them"):
        e = accepted[accepted.offence == team]
        s = e[e.event == "shot"]
        known = s.result.isin(["made", "missed"])
        teams[team] = dict(
            reviewed_shot_attempts=int(len(s)), resolved_shot_attempts=int(known.sum()),
            made_field_goals=int((s.result == "made").sum()),
            unknown_shot_outcomes=int((~known).sum()),
            observed_points=int(e.loc[e.event.isin(["shot", "free_throws"]), "points"].sum()),
            reviewed_turnovers=int(((e.event == "turnover") & e.confidence.ne("low")).sum()),
        )
    return dict(event_count=len(events), labelled_segments=int(events.pid.nunique()),
                confidence_counts=events.confidence.value_counts().to_dict(), teams=teams,
                score_is_complete=False,
                note="Video-reviewed sample only; unknown and low-confidence outcomes excluded from points and makes.")
