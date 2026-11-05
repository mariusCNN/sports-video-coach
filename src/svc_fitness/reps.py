"""Per-rep measurements from one lifter's 2D pose track (pure functions), and the stage that writes run/reps/reps.json.

Input: t (N,) seconds, kp (N,17,2) COCO keypoints in px, conf (N,17); image y grows downward. Lengths are in leg
lengths (hip to ankle), so they do not depend on the camera distance. 2D angles are only valid when the camera looks
at the plane of motion: the stage measures angles only for sets filmed from the side (or oblique, flagged), and only
the metrics the library says that view supports. Missing = None, never 0.

Stage `reps <folder> [--set S01]`: reads run/review/sets.json and run/pose/<id>.npz, writes run/reps/reps.json.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

KP_MIN = 0.3                 # keypoint confidence below this counts as missing
NOSE, L_SH, R_SH, L_WR, R_WR, L_HIP, R_HIP, L_KN, R_KN, L_AN, R_AN = 0, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16
PROMINENCE = {"squat": 0.15, "lunge": 0.12, "single_leg": 0.12, "hinge": 0.18, "olympic_pull": 0.18,
              "plyo": 0.15, "push": 0.08, "pull": 0.08}  # a rep moves the tracked point at least this many leg lengths (our rule)
START_ZONE = 0.05            # within this share of a rep's range of its start level counts as "at the start" (our rule)
TURN_ZONE = 0.25             # a pause can only happen this close to the turn, as a share of the range (our rule)
SETTLED = 0.3               # still and within this share of the range of the start level = the rep starts (our rule)
PAUSE_SPEED = 0.15           # leg lengths per second: slower than this at the turn counts as a pause (our rule)
MIN_REP_S = 0.5              # two turns at least this far apart (our rule)
TEMPO_FPS_MIN = 24.0         # below this the phase times are too coarse to report
# which signal moves and where the rep turns: squat-like patterns go down and come back (turn = lowest hip), hinges
# from standing lean over and come back (turn = most trunk lean, in units of 90°), pulls start low and go up
# (turn = highest wrist)
SIGNAL = {"squat": ("hip", 1), "lunge": ("hip", 1), "single_leg": ("hip", 1), "isometric": ("hip", 1),
          "plyo": ("hip", 1), "calf": ("hip", -1), "hinge": ("lean", 1), "olympic_pull": ("wrist", -1),
          "push": ("wrist", 1), "pull": ("wrist", -1), "carry": ("hip", 1), "core": ("hip", 1)}
# in these patterns the way to the turn lowers the load (eccentric); in the others it lifts it (concentric)
SPLIT = {"lunge", "single_leg"}  # one leg in front: depth and knee travel are measured on the front leg
ECC_FIRST = {"squat", "lunge", "single_leg", "hinge", "plyo", "push", "isometric", "carry", "core"}


def clean(kp: np.ndarray, conf: np.ndarray) -> np.ndarray:
    """Keypoints with low-confidence points set to nan."""
    kp = np.array(kp, float)
    kp[np.asarray(conf) < KP_MIN] = np.nan
    return kp


def smooth(x: np.ndarray, fps: float, window_s: float = 0.1) -> np.ndarray:
    """Gaps filled by linear interpolation, then a centred moving average of about window_s seconds."""
    x = np.array(x, float)
    ok = np.isfinite(x)
    if ok.sum() < 2:
        return x
    idx = np.arange(len(x))
    x = np.interp(idx, idx[ok], x[ok])
    k = max(1, int(round(window_s * fps)) | 1)
    if k > 1 and len(x) > k:
        pad = k // 2
        x = np.convolve(np.pad(x, pad, mode="edge"), np.ones(k) / k, mode="valid")
    return x


def fps_of(t: np.ndarray) -> float:
    dt = np.diff(np.asarray(t, float))
    dt = dt[np.isfinite(dt) & (dt > 0)]
    return float(1 / np.median(dt)) if len(dt) else 0.0


def near_side(conf: np.ndarray) -> str:
    """'L' or 'R': the body side facing the camera (its hip, knee and ankle are seen with more confidence)."""
    c = np.asarray(conf, float)
    left = np.nanmean(c[:, [L_HIP, L_KN, L_AN]])
    right = np.nanmean(c[:, [R_HIP, R_KN, R_AN]])
    return "L" if left >= right else "R"


def angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Angle at b (degrees) between b->a and b->c, per frame."""
    u, v = a - b, c - b
    with np.errstate(all="ignore"):
        cos = (u * v).sum(-1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(v, axis=-1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def leg_length(kp: np.ndarray, side: str) -> float:
    """Thigh + shin in px (90th percentile of each, so a bent knee does not shorten it). Ankle hidden in most
    frames: twice the thigh (shin and thigh are about the same length)."""
    hip, kn, ank = (kp[:, L_HIP], kp[:, L_KN], kp[:, L_AN]) if side == "L" else (kp[:, R_HIP], kp[:, R_KN], kp[:, R_AN])
    thigh = np.linalg.norm(hip - kn, axis=-1)
    shin = np.linalg.norm(kn - ank, axis=-1)
    thigh, shin = thigh[np.isfinite(thigh)], shin[np.isfinite(shin)]
    if not len(thigh):
        return float("nan")
    th = float(np.percentile(thigh, 90))
    return th + (float(np.percentile(shin, 90)) if len(shin) >= 0.3 * len(thigh) else th)


def series(kp: np.ndarray, side: str, fps: float) -> dict[str, np.ndarray]:
    """Smoothed per-frame series for the near side: hip/knee/ankle/shoulder/wrist points, knee and hip angles, trunk
    lean from vertical (degrees), all in px except angles."""
    s = {"L": (L_SH, L_WR, L_HIP, L_KN, L_AN), "R": (R_SH, R_WR, R_HIP, R_KN, R_AN)}[side]
    pts = {}
    for name, i in zip(("sh", "wr", "hip", "kn", "an"), s):
        pts[name] = np.stack([smooth(kp[:, i, 0], fps), smooth(kp[:, i, 1], fps)], -1)
    pts["nose"] = np.stack([smooth(kp[:, NOSE, 0], fps), smooth(kp[:, NOSE, 1], fps)], -1)
    knee = angle(pts["hip"], pts["kn"], pts["an"])
    hip = angle(pts["sh"], pts["hip"], pts["kn"])
    d = pts["sh"] - pts["hip"]
    with np.errstate(all="ignore"):
        lean = np.degrees(np.arctan2(np.abs(d[:, 0]), -d[:, 1]))
    return dict(pts, knee=knee, hip_angle=hip, lean=lean)


def turns(z: np.ndarray, fps: float, prominence: float, expect: int | None = None) -> list[int]:
    """Indices of the rep turns: local maxima of z that rise at least `prominence` above the lowest point on each
    side before a higher turn, at least MIN_REP_S apart. `expect` (reps counted by eye): keep only that many, the
    most prominent ones, so wobbles and knee drives between reps do not count."""
    scored = _turns(np.asarray(z, float), fps, prominence)
    if expect and len(scored) > expect:
        scored = sorted(sorted(scored, key=lambda ip: -ip[1])[:expect])
    return [i for i, _ in scored]


def _turns(z: np.ndarray, fps: float, prominence: float) -> list[tuple[int, float]]:
    n, out = len(z), []
    if n < 3 or not np.isfinite(z).any():
        return out
    gap = max(1, int(MIN_REP_S * fps))
    cand = [i for i in range(1, n - 1) if z[i] >= z[i - 1] and z[i] > z[i + 1]]
    for i in cand:
        left = z[max(0, i - 10 * gap):i + 1]
        right = z[i:min(n, i + 10 * gap)]
        # lowest point between i and the nearest higher point on each side (topographic prominence, bounded)
        def side_min(seg, rev):
            seg = seg[::-1] if rev else seg
            higher = np.nonzero(seg > z[i])[0]
            seg = seg[:higher[0]] if len(higher) else seg
            return np.nanmin(seg)
        prom = z[i] - max(side_min(left, True), side_min(right, False))
        if prom >= prominence:
            if out and i - out[-1][0] < gap:
                if z[i] > z[out[-1][0]]:
                    out[-1] = (i, prom)
                continue
            out.append((i, prom))
    return out


def _phase(z: np.ndarray, t: np.ndarray, a: int, c: int, b: int) -> dict:
    """Times for one rep with start-level window [a..c..b] around turn c: to-turn, at-turn (pause), back. The pause
    is the stretch around the turn where the point is near the turn and slower than PAUSE_SPEED."""
    lo = min(np.nanmin(z[a:c + 1]), np.nanmin(z[c:b + 1]))
    rng = z[c] - lo
    if not np.isfinite(rng) or rng <= 0:
        return {}
    with np.errstate(all="ignore"):
        v = np.abs(np.gradient(z, t))
    still = (z >= z[c] - TURN_ZONE * rng) & (v < PAUSE_SPEED)
    near_start = (z <= lo + START_ZONE * rng) | ((z <= lo + SETTLED * rng) & (v < PAUSE_SPEED))
    i = c
    while i > a and still[i - 1]:
        i -= 1
    j = c
    while j < b and still[j + 1]:
        j += 1
    s = i
    while s > a and not near_start[s]:
        s -= 1
    e = j
    while e < b and not near_start[e]:
        e += 1
    return dict(to_turn_s=float(t[i] - t[s]), pause_s=float(t[j] - t[i]), back_s=float(t[e] - t[j]),
                start=float(t[s]), end=float(t[e]))


def measure(t: np.ndarray, kp: np.ndarray, conf: np.ndarray, pattern: str, metrics: list[str],
            expect: int | None = None) -> dict:
    """Reps and their metrics for one set. `metrics`: the library keys valid for this exercise and camera view;
    `expect`: the reps counted on the zoomed sheets, when known (the pose then keeps at most that many turns)."""
    t = np.asarray(t, float)
    fps = fps_of(t)
    kp = clean(kp, conf)
    side = near_side(conf)
    leg = leg_length(kp, side)
    if not np.isfinite(leg) or leg <= 0 or len(t) < 5:
        return {"reps": [], "n": 0, "note": "lifter not seen well enough to measure"}
    s = series(kp, side, fps)
    point, sign = SIGNAL.get(pattern, ("hip", 1))
    z = sign * {"wrist": s["wr"][:, 1] / leg, "hip": s["hip"][:, 1] / leg, "lean": s["lean"] / 90}[point]
    idx = turns(z, fps, PROMINENCE.get(pattern, 0.15), expect)
    ecc_first = pattern in ECC_FIRST
    facing = np.sign(np.nanmedian(s["nose"][:, 0] - s["hip"][:, 0])) or 1.0
    both = {k: series(kp, k, fps) for k in "LR"} if pattern in SPLIT else None
    reps = []
    bounds = [0] + [int((idx[k] + idx[k + 1]) // 2) for k in range(len(idx) - 1)] + [len(t) - 1]
    for k, c in enumerate(idx):
        a, b = bounds[k], bounds[k + 1]
        ph = _phase(z, t, a, c, b)
        r = {"n": k + 1, "t": round(float(t[c]), 2)}
        if ph and fps >= TEMPO_FPS_MIN and "tempo" in metrics:
            ecc, con = (ph["to_turn_s"], ph["back_s"]) if ecc_first else (ph["back_s"], ph["to_turn_s"])
            r.update(ecc_s=round(ecc, 2), con_s=round(con, 2), pause_s=round(ph["pause_s"], 2))
        win = slice(a, b + 1)
        leg_s = s
        if both:  # the front leg: its ankle is further ahead in the facing direction at the turn
            ahead = {k: facing * v["an"][c, 0] for k, v in both.items()}
            if all(np.isfinite(x) for x in ahead.values()):
                leg_s = both[max(ahead, key=ahead.get)]  # by position only: pose models swap L and R labels
        if "depth" in metrics:
            kn = leg_s["knee"][win]
            r["knee_min_deg"] = _r(np.nanmin(kn)) if np.isfinite(kn).any() else None
            r["hip_below_knee"] = _r((leg_s["hip"][c, 1] - leg_s["kn"][c, 1]) / leg, 2)  # > 0: hip crease below the knee
        if "trunk_lean" in metrics:
            r["trunk_lean_deg"] = _r(s["lean"][c])
        if "knee_travel" in metrics:
            r["knee_ahead"] = _r(facing * (leg_s["kn"][c, 0] - leg_s["an"][c, 0]) / leg, 2)  # > 0: knee in front of the ankle
        if "hip_extension" in metrics:
            r["hip_max_deg"] = _r(np.nanmax(s["hip_angle"][win]))
        if "bar_path" in metrics:
            wx = s["wr"][win, 0]
            r["bar_drift"] = _r((np.nanmax(wx) - np.nanmin(wx)) / leg, 2) if np.isfinite(wx).any() else None
        reps.append(r)
    out = {"n": len(reps), "reps": reps, "side": side, "fps": round(fps, 1), "leg_px": round(leg, 1)}
    con = [r["con_s"] for r in reps if r.get("con_s")]
    if "velocity_loss" in metrics and len(con) >= 3:
        best, last = min(con[:2]), float(np.mean(con[-2:]))
        out["slowing_pct"] = round(100 * (last / best - 1), 0)  # concentric time: last two reps vs the faster first two
    for key in ("knee_min_deg", "trunk_lean_deg", "ecc_s", "con_s", "bar_drift", "hip_below_knee", "knee_ahead"):
        vals = [r[key] for r in reps if isinstance(r.get(key), (int, float))]
        if vals:
            out[f"{key}_mean"] = round(float(np.mean(vals)), 2)
            out[f"{key}_range"] = [round(min(vals), 2), round(max(vals), 2)]
    return out


def _r(x, d: int = 0):
    x = float(x)
    return None if not math.isfinite(x) else (round(x) if d == 0 else round(x, d))


def main(argv=None):
    from sports_video_coach.timefmt import mmss, seconds

    from . import library
    from .pose import source_window
    from .unit import Session, load_sets
    ap = argparse.ArgumentParser(prog="sports-video-coach fitness:reps", description=__doc__.split("\n\n")[0])
    ap.add_argument("folder")
    ap.add_argument("--set", action="append", help="only this set id (repeatable)")
    a = ap.parse_args(argv)
    g = Session.load(Path(a.folder))
    sets = load_sets(g)
    ex = library.exercises()
    out_p = g.run / "reps" / "reps.json"
    old = json.loads(out_p.read_text(encoding="utf8")) if out_p.exists() and a.set else {"sets": {}}
    res = old.get("sets", {})
    for s in sets:
        if a.set and s["id"] not in a.set:
            continue
        e = ex.get(s.get("exercise"))
        pose = g.run / "pose" / f"{s['id']}.npz"
        view = s.get("view", "")
        base = dict(exercise=s.get("exercise"), view=view, reps_seen=s.get("reps"))
        if not e:
            res[s["id"]] = dict(base, measured=False, note="exercise not in the library")
            continue
        metrics = library.valid_metrics(e, "side" if view in ("side", "oblique") else view)
        if not pose.exists():
            res[s["id"]] = dict(base, measured=False, note="no pose track (view or pose pass skipped)")
            continue
        d = np.load(pose)
        seen = s.get("reps") if isinstance(s.get("reps"), int) and s.get("reps") > 0 else None
        m = measure(d["t"], d["kp"], d["conf"], e["pattern"], metrics, seen)
        m.update(base, measured=bool(m["reps"]), metrics=metrics)
        offset = seconds(s["start"]) - source_window(g, seconds(s["start"]), seconds(s["end"]))[1]
        for r in m["reps"]:
            r["at"] = mmss(r["t"] + offset, 1)
        if view == "oblique":
            m["note"] = "oblique view: angles are approximate"
        if isinstance(s.get("reps"), int) and m["n"] != s["reps"]:
            m["count_note"] = (f"pose found only {m['n']} of the {s['reps']} reps counted on the zoomed sheets: "
                               "trust that count; the per-rep numbers cover the reps found")
        res[s["id"]] = m
        print(f"[reps] {s['id']} {e['id']}: {m['n']} reps" + (f", slowing {m['slowing_pct']:.0f}%"
                                                             if m.get("slowing_pct") is not None else ""))
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps({"version": 1, "sets": res}, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"[reps] wrote {out_p.as_posix()}")


if __name__ == "__main__":
    main()
