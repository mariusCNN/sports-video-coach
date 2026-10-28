"""Small, explicit local shot validation; no official timestamps used as ground truth."""
from __future__ import annotations

import math


def match_times(predicted: list[float], observed: list[tuple[float, float]], tolerance: float) -> list[tuple[int, int]]:
    """Maximum one-to-one matches, then minimum time error, preserving time order.

    Intervals express uncertainty in a reviewed release frame. The dynamic program
    avoids greedy nearest-neighbour matches stealing another shot's only match.
    """
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    p = sorted(enumerate(predicted), key=lambda item: item[1])
    o = sorted(enumerate(observed), key=lambda item: item[1])
    scores = [[(0, 0.0) for _ in range(len(o) + 1)] for _ in range(len(p) + 1)]
    actions = {}
    for i, (_, t) in enumerate(p, 1):
        for j, (_, (lo, hi)) in enumerate(o, 1):
            options = [(scores[i - 1][j], "p"), (scores[i][j - 1], "o")]
            distance = max(lo - t, t - hi, 0)
            if distance <= tolerance:
                count, cost = scores[i - 1][j - 1]
                options.append(((count + 1, cost - distance), "match"))
            scores[i][j], actions[i, j] = max(options, key=lambda x: x[0])
    matches, i, j = [], len(p), len(o)
    while i and j:
        action = actions[i, j]
        if action == "match":
            matches.append((p[i - 1][0], o[j - 1][0]))
            i, j = i - 1, j - 1
        elif action == "p":
            i -= 1
        else:
            j -= 1
    return list(reversed(matches))


def evaluate(doc: dict, labels: dict, tolerance: float = 1.0) -> dict:
    """Evaluate attempts, outcomes and team attribution separately in fully reviewed windows.

    The labels describe every visible shot in each window. Unreviewed/ambiguous
    periods must be excluded before providing windows; missing labels are not misses.
    """
    if labels.get("schema") != "svc_perception_labels_v1":
        raise ValueError("expected svc_perception_labels_v1")
    windows = sorted(labels["windows"], key=lambda w: w["start"])
    if not windows:
        raise ValueError("evaluation needs at least one fully reviewed window")
    previous_end = -1
    output = []
    for window in windows:
        start, end = window["start"], window["end"]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                   for v in (start, end)) or not 0 <= start < end or start < previous_end:
            raise ValueError("invalid or overlapping labelled windows")
        previous_end = end
        if not any(s.get("finalization") == "adapter_completed_run"
                   and s["start"] <= start + 1e-6 and s["end"] >= end - 1e-6 for s in doc["sources"]):
            raise ValueError("labelled window is not fully covered by completed analysis")
        observed = window["shots"]
        for shot in observed:
            lo, hi = shot["release"]
            if not (start <= lo <= hi < end) or shot.get("result") not in {"made", "missed", None}:
                raise ValueError("invalid labelled shot")
            if shot.get("team") not in {"us", "them", None}:
                raise ValueError("invalid labelled team")
        predicted = [e for e in doc["events"] if e["type"] == "shot" and start <= e["start"] < end]
        pairs = match_times([e["start"] for e in predicted], [s["release"] for s in observed], tolerance)
        checked = []
        for i, j in pairs:
            event, shot = predicted[i], observed[j]
            checked.append(dict(event_id=event["id"], label_index=j,
                                time_error=round(max(shot["release"][0] - event["start"],
                                                     event["start"] - shot["release"][1], 0), 4),
                                result_expected=shot.get("result"), result_predicted=event.get("result"),
                                team_expected=shot.get("team"), team_predicted=event.get("team")))
        outcome_known = [m for m in checked if m["result_expected"] is not None]
        team_known = [m for m in checked if m["team_expected"] is not None]
        output.append(dict(start=start, end=end, split=window.get("split", "diagnostic"),
                           labelled_shots=len(observed), candidate_shots=len(predicted), matched=len(pairs),
                           unmatched_candidates=len(predicted) - len(pairs), missed_labels=len(observed) - len(pairs),
                           outcome_labels=len(outcome_known),
                           outcome_correct=sum(m["result_expected"] == m["result_predicted"] for m in outcome_known),
                           outcome_unresolved=sum(m["result_predicted"] is None for m in outcome_known),
                           false_makes=sum(m["result_expected"] == "missed" and m["result_predicted"] == "made"
                                           for m in outcome_known),
                           team_labels=len(team_known),
                           team_correct=sum(m["team_expected"] == m["team_predicted"] for m in team_known),
                           team_unresolved=sum(m["team_predicted"] is None for m in team_known), matches=checked))
    keys = ("labelled_shots", "candidate_shots", "matched", "unmatched_candidates", "missed_labels",
            "outcome_labels", "outcome_correct", "outcome_unresolved", "false_makes",
            "team_labels", "team_correct", "team_unresolved")
    return dict(tolerance_seconds=tolerance, windows=output,
                totals={k: sum(w[k] for w in output) for k in keys},
                label_source=labels.get("source"),
                note="Small local diagnostic. Development and validation windows stay separate; this is not full-game accuracy.")
