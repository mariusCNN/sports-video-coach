"""Cross-check candidates against existing calibration and reviewed shots, without changing either."""
from __future__ import annotations

import bisect
import json
from pathlib import Path

from .perception_eval import match_times


def compare_reviewed(doc: dict, review: Path, tolerance: float = 2.0):
    shots = []
    for path in sorted(review.glob("coach_part*.json")):
        for trip in json.loads(path.read_text(encoding="utf8")):
            shot = trip.get("shot") or {}
            t = shot.get("t")
            if isinstance(t, (int, float)) and not isinstance(t, bool):
                shots.append(dict(t=t, team=trip.get("offence"), made=shot.get("made"),
                                  pid=trip.get("pid"), trip=trip.get("trip"), confidence=trip.get("confidence")))
    candidates = [e for e in doc["events"] if e["type"] == "shot"]
    covered = [s for s in shots if any(a["start"] <= s["t"] < a["end"] for a in doc["sources"])]
    pairs = match_times([e["start"] for e in candidates], [(s["t"], s["t"]) for s in covered], tolerance)
    for i, j in pairs:
        event, shot = candidates[i], covered[j]
        distance = abs(event["start"] - shot["t"])
        conflicts = []
        if event.get("team") and shot.get("team") and event["team"] != shot["team"]:
            conflicts.append("team")
        if event.get("result") and isinstance(shot.get("made"), bool) and (event["result"] == "made") != shot["made"]:
            conflicts.append("outcome")
        event["existing_review"] = dict(**shot, time_difference=round(distance, 3), conflicts=conflicts)
    doc["comparison"] = dict(reviewed_shots_in_windows=len(covered), candidate_shots=len(candidates),
                             matched=len(pairs), tolerance_seconds=tolerance,
                             conflicts=sum(bool(e.get("existing_review", {}).get("conflicts")) for e in candidates),
                             note="Timing cross-check against earlier film review, not an independently labelled accuracy benchmark.")


def project_candidates(doc: dict, camera: Path):
    """FIBA coordinates from existing court->image calibration, not the upstream NBA model.

    Coordinates remain candidates: an inferred shooter ID and a box foot point do
    not establish the actual release location. No points are inferred here.
    """
    if not camera.exists():
        return
    import numpy as np
    with np.load(camera) as data:
        times, matrices = data["t"].copy(), data["H"].copy()
        quality = data["quality"].copy()
    if not len(times):
        return
    for source in doc["sources"]:
        if not source.get("spatial", {}).get("aligned"):
            continue
        pending = {}
        for event in doc["events"]:
            if event["source"] == source["id"] and event.get("player_id"):
                frame = round((event["start"] - source["offset"]) * source["fps"]) + 1
                pending.setdefault(frame, []).append(event)
        if not pending:
            continue
        with Path(source["path"]).open(encoding="utf8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                for event in pending.get(row["frame"], []):
                    pid = event["raw"].get("player_id")
                    player = next((p for p in row.get("players", []) if p.get("id") == pid), None)
                    if player is None or not player.get("box"):
                        continue
                    k = bisect.bisect_left(times, event["start"])
                    k = min((j for j in (k - 1, k) if 0 <= j < len(times)), key=lambda j: abs(times[j] - event["start"]))
                    if abs(times[k] - event["start"]) > .15 or not np.isfinite(matrices[k]).all():
                        continue
                    x1, y1, x2, y2 = player["box"]
                    try:
                        point = np.linalg.solve(matrices[k], [(x1 + x2) / 2, y2, 1])
                    except np.linalg.LinAlgError:
                        continue
                    if abs(point[2]) < 1e-8:
                        continue
                    xy = point[:2] / point[2]
                    if np.isfinite(xy).all() and 0 <= xy[0] <= 28 and 0 <= xy[1] <= 15:
                        event["court_xy"] = [round(float(x), 3) for x in xy]
                        event["court_evidence"] = dict(source="existing_fiba_calibration", camera_time=float(times[k]),
                                                        camera_quality=float(quality[k]), method="candidate_player_box_foot",
                                                        trusted=False)


def attach_manifest(manifest: list[dict], evidence: Path):
    if not evidence.exists():
        return
    events = json.loads(evidence.read_text(encoding="utf8"))["events"]
    for item in manifest:
        item["perception_candidates"] = [
            {k: e.get(k) for k in ("id", "type", "start", "end", "team", "result", "review_status", "evidence")}
            for e in events if e["end"] >= item["start"] and e["start"] <= item["end"]]
