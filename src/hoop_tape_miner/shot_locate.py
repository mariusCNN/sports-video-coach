"""Shot locate: where on the court each reviewed shot was taken, read by an agent off a projected court grid.

    hoop-tape-miner shot-locate sheets --run RUN --review R --video V [--game game.json] [--per-batch 8] [--limit N] [--only 32,34]
    hoop-tape-miner shot-locate merge --review R            # answers -> shot.xy / shot.xy_note in coach_part*.json
    hoop-tape-miner shot-locate check --review R            # shots still without a location, open zone conflicts

`sheets` reads the reviewed trips (R/coach_part*.json, R/part*.json for the attacked half), RUN/camera.npz (court
-> image homography per sampled frame), RUN/tracks.pkl + player_numbers.json and RUN/ball_track.pkl when present.
Per shot it writes R/locate/s<NN>.jpg: six frames around the release (TILE_OFFSETS) with the court lines (magenta,
to check the calibration) and a 1 m grid on the attacked half (yellow x lines along the length, cyan y lines across,
every 2 m labelled in court metres, see court.py), the reviewed shooter boxed. Also R/locate/shots.json (what each
sheet shows) and brief_locate_<b>.md per batch from prompts/shot_locate.md. Reviewers write
R/locate/answers_<b>.json; `merge` copies a located spot into the shot as "xy": [x, y] (court metres, 0.1 m) with
"xy_src" (method, frame time, camera time and quality, confidence), and writes "xy": null plus "xy_note" when the
spot is unclear. A spot is never guessed: low confidence or no answer stays null.

Zones: a located spot decides the shot's zone (zone_of; points 2/3 follow it for missed shots) and the reviewed values
stay in "zone_review" / "points_review", except when the spot is within NEAR_LINE m of a zone line (kept, "zone_flag"
"near line: ...") or when a made shot's spot disagrees on 2 vs 3 points (kept, "zone_flag" "confirm: ..."; `check`
lists these until someone fixes the trip from the sheet and removes the flag). Reviewers do not see the reviewed zone.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from . import court
from .coach_review import compose
from .review import annotate, draw_ball_trail, use_game
from sports_video_coach.timefmt import mmss

TILE_OFFSETS = (-1.8, -1.2, -0.8, -0.4, 0.0, 0.3)   # s from the reviewed release time (often ~1 s late)
LAY = dict(grid=[2, 3], header=34, quality=80)
CAM_SLACK = 0.5     # s: no grid on a frame whose nearest camera sample is further away
ACCEPT = ("high", "medium")
NEAR_LINE = 0.5     # m: typical spread between two readers; a spot this close to a zone line keeps the reviewed zone
PER_BATCH = 8       # shots per reviewer: about 5 minutes each
BRIEF = Path(__file__).resolve().parents[2] / "prompts" / "shot_locate.md"
X_BGR, Y_BGR, LINE_BGR, SHOOTER_BGR = (0, 230, 255), (255, 220, 0), (255, 0, 255), (0, 255, 255)


# ---- which shots ---------------------------------------------------------------------------------------------

def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def release_t(x: dict) -> float | None:
    """The shot's release time: shot.t, else the last evidence.shot time, else None."""
    s = x.get("shot") if isinstance(x.get("shot"), dict) else {}
    if _num(s.get("t")):
        return float(s["t"])
    ev = [t for t in ((x.get("evidence") or {}).get("shot") or []) if _num(t)]
    return float(max(ev)) if ev else None


def shot_list(review: Path) -> list[dict]:
    """Every trip with a shot in R/coach_part*.json, in part order: part file, pid, trip, release t, shooter,
    offence, zone, made and the attacked half (part*.json possession `side`, None when unknown)."""
    sides = {}
    for p in sorted(review.glob("part*.json")):
        d = json.loads(p.read_text(encoding="utf8"))
        for x in d if isinstance(d, list) else d.get("possessions", []):
            sides[x.get("pid")] = x.get("side")
    out = []
    for p in sorted(review.glob("coach_part*.json")):
        for x in json.loads(p.read_text(encoding="utf8")):
            s = x.get("shot") if isinstance(x, dict) else None
            if not isinstance(s, dict):
                continue
            out.append(dict(n=len(out) + 1, part=p.name, pid=x.get("pid"), trip=x.get("trip", 1), t=release_t(x),
                            shooter=s.get("shooter"), offence=x.get("offence"), zone=s.get("zone"),
                            made=s.get("made"), side=sides.get(x.get("pid"))))
    return vote_sides(out)


def vote_sides(shots: list[dict], k: int = 3) -> list[dict]:
    """Teams keep one basket for a half, so a shot when at least 2k - 1 of its k shots before and k shots after (in
    time) point the other way (same offence: their side, other offence: the opposite side) takes that side, with a
    "side_note". A possession's side can be wrong for a shot in it by the other team, or one past its end; at the
    half-time switch the neighbours split and nothing changes. Changes the list in place."""
    flip = {"left": "right", "right": "left"}
    known = sorted((s for s in shots if _num(s["t"]) and s["offence"] in ("us", "them") and s["side"] in flip),
                   key=lambda s: s["t"])
    for s in shots:
        if not _num(s["t"]) or s["offence"] not in ("us", "them"):
            continue
        before = [o for o in known if o["t"] < s["t"] and o is not s][-k:]
        after = [o for o in known if o["t"] > s["t"] and o is not s][:k]
        votes = Counter(o["side"] if o["offence"] == s["offence"] else flip[o["side"]] for o in before + after)
        v, c = votes.most_common(1)[0] if votes else (None, 0)
        if len(before) == len(after) == k and c >= 2 * k - 1 and s["side"] != v:
            s["side_note"] = f"possession side {s['side'] or 'unknown'}, the {2 * k} shots around it say {v}"
            s["side"] = v
    return shots


# ---- the sheet -----------------------------------------------------------------------------------------------

def load_cameras(run: Path) -> dict | None:
    """camera.npz rows with a finite homography: {"frame", "t", "H", "quality"} arrays, or None without the file."""
    p = run / "camera.npz"
    if not p.is_file():
        return None
    c = np.load(p)
    ok = np.isfinite(c["H"]).all(axis=(1, 2))
    q = c["quality"][ok] if "quality" in c.files else np.full(ok.sum(), np.nan)
    return dict(frame=c["frame"][ok].astype(int), t=c["t"][ok].astype(float), H=c["H"][ok], quality=q)


def nearest_camera(cams: dict | None, t: float) -> tuple[np.ndarray | None, float | None, float | None]:
    """(H, camera t, quality) of the sample nearest t, or Nones when none is within CAM_SLACK s."""
    if not cams or not len(cams["t"]):
        return None, None, None
    i = int(np.abs(cams["t"] - t).argmin())
    if abs(cams["t"][i] - t) > CAM_SLACK:
        return None, None, None
    q = cams["quality"][i]
    return cams["H"][i], float(cams["t"][i]), (float(q) if np.isfinite(q) else None)


def half_range(side: str | None) -> tuple[float, float]:
    """x range (court metres) of the attacked half; the whole court when the side is unknown."""
    return {"left": (0.0, court.LENGTH / 2), "right": (court.LENGTH / 2, court.LENGTH)}.get(side, (0.0, court.LENGTH))


def _visible(px: np.ndarray, w: int, h: int, pad: int = 2) -> np.ndarray:
    return np.isfinite(px).all(1) & (px[:, 0] >= pad) & (px[:, 0] < w - pad) & (px[:, 1] >= pad) & (px[:, 1] < h - pad)


def _label(img, text: str, at, color) -> None:
    x, y = int(at[0]), int(at[1])
    cv2.putText(img, text, (x, y), 0, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), 0, 0.55, color, 2, cv2.LINE_AA)


def grid_lines(side: str | None) -> list[tuple[str, float, np.ndarray]]:
    """("x" | "y", value, dense court polyline) for the 1 m grid on the attacked half."""
    x0, x1 = half_range(side)
    lines = [("x", float(x), court._seg((x, 0), (x, court.WIDTH))) for x in range(int(x0), int(x1) + 1)]
    lines += [("y", float(y), court._seg((x0, y), (x1, y))) for y in range(0, int(court.WIDTH) + 1)]
    return lines


def draw_grid(img: np.ndarray, H: np.ndarray, side: str | None) -> np.ndarray:
    """Court lines and the labelled 1 m grid projected with H (court -> image), blended so feet stay visible."""
    h, w = img.shape[:2]
    over = img.copy()
    for kind, v, pl in grid_lines(side):
        px = court.project(H, pl)
        ok = _visible(px, w, h)
        if ok.sum() < 2:
            continue
        major = int(v) % 2 == 0
        cv2.polylines(over, [np.round(px[ok]).astype(np.int32)], False, X_BGR if kind == "x" else Y_BGR,
                      2 if major else 1, cv2.LINE_AA)
    out = cv2.addWeighted(over, 0.55, img, 0.45, 0)
    for pl in court.court_polylines():
        px = court.project(H, pl)
        ok = _visible(px, w, h)
        if ok.sum() >= 2:
            cv2.polylines(out, [np.round(px[ok]).astype(np.int32)], False, LINE_BGR, 1, cv2.LINE_AA)
    for kind, v, pl in grid_lines(side):
        if int(v) % 2:
            continue
        px = court.project(H, pl)
        idx = np.flatnonzero(_visible(px, w, h, pad=24))
        if len(idx):
            for i in {idx[0], idx[-1]}:
                _label(out, f"{kind}{int(v)}", px[i] + (3, -3), X_BGR if kind == "x" else Y_BGR)
    return out


def _shooter_box(img, dets: pd.DataFrame, numbers: dict, shot: dict) -> None:
    if not shot.get("shooter") or "number" not in dets and not numbers:
        return
    for _, r in dets.iterrows():
        n = r.get("number") if "number" in dets else None
        n = n if isinstance(n, str) and n else numbers.get(int(r.track))
        if str(n) == str(shot["shooter"]) and r.team == shot.get("offence"):
            cv2.rectangle(img, (int(r.x1), int(r.y1)), (int(r.x2), int(r.y2)), SHOOTER_BGR, 4)


def build(cap, shots: list[dict], out: Path, cams: dict | None, tracks: pd.DataFrame | None = None,
          numbers: dict | None = None, ball: pd.DataFrame | None = None) -> list[dict]:
    """s<NN>.jpg per located-able shot (see module doc); returns the shots with "sheet" and "tiles"
    ([{"t", "cam_t", "quality"}] per tile, cam_t None = no grid on that frame)."""
    vfps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    by_frame = {f: g for f, g in tracks.groupby("frame")} if tracks is not None and len(tracks) else {}
    analysed = np.array(sorted(by_frame))
    res = []
    for s in shots:
        if s["t"] is None:
            res.append({**s, "sheet": None, "tiles": []})
            continue
        targets = [max(0, int(round((s["t"] + o) * vfps))) for o in TILE_OFFSETS]
        cap.set(cv2.CAP_PROP_POS_FRAMES, targets[0])
        fi, tiles, meta = targets[0], [], []
        for k, tgt in enumerate(targets, 1):
            ok, f = True, None
            while fi <= tgt:
                ok, f = cap.read()
                fi += 1
                if not ok:
                    break
            if not ok or f is None:
                break
            t = tgt / vfps
            img = f
            if len(analysed):
                near = analysed[np.abs(analysed - tgt).argmin()]
                if abs(near - tgt) <= 6:
                    dets = by_frame[near]
                    img = annotate(f, dets, numbers or {})
                    _shooter_box(img, dets, numbers or {}, s)
            if ball is not None and len(ball):
                tr = ball[(ball.t > t - 0.6) & (ball.t <= t + 0.05)]
                if len(tr) and t - tr.t.max() <= 0.3:
                    draw_ball_trail(img, tr[["sx", "sy"]].to_numpy(float))
            H, cam_t, q = nearest_camera(cams, t)
            if H is not None:
                img = draw_grid(img, H, s["side"])
            cv2.rectangle(img, (0, 0), (250, 30), (0, 0, 0), -1)
            cv2.putText(img, f"T{k} {mmss(t, 1)}" + ("" if H is not None else " no grid"), (6, 22), 0, 0.7,
                        (0, 255, 255), 2)
            tiles.append(img)
            meta.append(dict(t=round(t, 2), cam_t=None if cam_t is None else round(cam_t, 2),
                             quality=None if q is None else round(q, 3)))
        if not tiles:
            res.append({**s, "sheet": None, "tiles": []})
            continue
        who = f"#{s['shooter']}" if s["shooter"] else "shooter ?"
        made = {True: "made", False: "missed"}.get(s["made"], "make/miss unclear")
        head = (f"S{s['n']:02d} P{s['pid']} {s['offence']} {who} {made} @{mmss(s['t'], 1)} | "
                f"{s['side'] or 'unknown'} half | yellow x lines, cyan y lines (court m), magenta = court lines")
        name = f"s{s['n']:02d}.jpg"
        cv2.imwrite(str(out / name), compose(tiles, head, LAY), [cv2.IMWRITE_JPEG_QUALITY, LAY["quality"]])
        res.append({**s, "sheet": name, "tiles": meta})
    return res


def batches(shots: list[dict], k: int | None = None, per: int = PER_BATCH) -> list[list[dict]]:
    """Shots with a sheet split into contiguous batches of near-equal size (one reviewer each): k batches, or as
    many as needed for at most `per` shots each."""
    have = [s for s in shots if s.get("sheet")]
    k = max(1, min(k or -(-len(have) // per), len(have)))
    return [b for b in np.array_split(np.array(have, dtype=object), k) if len(b)] if have else []


def brief(template: str, b: int, items: list[dict], out: Path) -> str:
    rows = "\n".join(f"- S{s['n']:02d} `{(out / s['sheet']).as_posix()}`: {s['offence']} "
                     f"{'#' + s['shooter'] if s['shooter'] else 'shooter unknown'}, "
                     f"release ~{mmss(s['t'], 1)}, attacking the {s['side'] or 'unknown'} basket" for s in items)
    return template.format(batch=b, locate_dir=out.as_posix(), shots=rows, n=len(items),
                           answers=(out / f"answers_{b}.json").as_posix(),
                           lay_grid=f"{LAY['grid'][0]} {LAY['grid'][1]}", header=LAY["header"])


# ---- merge and check -----------------------------------------------------------------------------------------

def xy_ok(xy) -> bool:
    return (isinstance(xy, (list, tuple)) and len(xy) == 2 and all(_num(v) for v in xy)
            and 0 <= xy[0] <= court.LENGTH and 0 <= xy[1] <= court.WIDTH)


def zone_of(xy, side: str) -> str:
    """The film-review zone of a court spot attacking `side`: rim (within 2 m of the basket centre, our rim
    zone), paint_non_rim, three (outside the arc, or in a corner beyond the straight line) or midrange."""
    hx, hy = court.hoop_xy(side)
    x, y = xy
    d = float(np.hypot(x - hx, y - hy))
    depth = x if side == "left" else court.LENGTH - x
    if d <= 2.0:
        return "rim"
    if depth <= court.FT_LINE and abs(y - court.WIDTH / 2) <= court.LANE_WIDTH / 2:
        return "paint_non_rim"
    corner = y < court.THREE_PT_SIDE or y > court.WIDTH - court.THREE_PT_SIDE
    return "three" if d > court.THREE_PT_RADIUS or corner else "midrange"


def _two_or_three(zone: str, arc) -> str:
    """zone_of corrected by the reader's foot on the 3-point line: on or inside the line is two points."""
    if arc in ("on", "inside") and zone == "three":
        return "midrange"
    return "three" if arc == "outside" else zone


def settle_zone(shot: dict, side: str | None, arc=None) -> str | None:
    """Zone of the shot from its located spot (see module doc); returns a log line when it differs from the
    reviewed zone. The reviewed zone/points are restored first, so a re-merge starts from the review."""
    if "zone_review" in shot:
        shot["zone"] = shot.pop("zone_review")
    if "points_review" in shot:
        shot["points"] = shot.pop("points_review")
    shot.pop("zone_flag", None)
    rz, xy = shot.get("zone"), shot.get("xy")
    if side not in ("left", "right") or not xy_ok(xy) or rz is None:
        return None
    z = _two_or_three(zone_of(xy, side), arc)
    if z == rz:
        return None
    ring = [(xy[0] + NEAR_LINE * np.cos(a), xy[1] + NEAR_LINE * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 16, False)]
    cls = lambda zz: 3 if zz == "three" else 2
    if any(_two_or_three(zone_of(p, side), arc) != z for p in ring):
        shot["zone_flag"] = f"near line: spot reads {z}, kept the reviewed {rz}"
    elif shot.get("made") is True and cls(z) != (shot.get("points") or cls(rz)):
        shot["zone_flag"] = f"confirm: made {shot.get('points') or cls(rz)}-pointer but the spot reads {z}"
    else:
        shot["zone_review"], shot["zone"] = rz, z
        if shot.get("made") is not True and shot.get("points") in (2, 3):
            shot["points_review"], shot["points"] = shot["points"], cls(z)
        return f"zone {rz} -> {z} (spot {xy})"
    return shot["zone_flag"]


def merge(review: Path, locate: Path | None = None) -> list[str]:
    """Write the answers in R/locate/answers_*.json into the coach_part*.json shots (see module doc); returns a log
    with every change, every zone the spot changed and every zone flag."""
    locate = locate or review / "locate"
    meta = {s["n"]: s for s in json.loads((locate / "shots.json").read_text(encoding="utf8"))["shots"]}
    answers = {}
    for p in sorted(locate.glob("answers_*.json"), key=lambda p: (len(p.stem), p.stem)):   # answers_10 after _9
        for a in json.loads(p.read_text(encoding="utf8")):
            if isinstance(a, dict) and isinstance(a.get("n"), int):
                answers[a["n"]] = a
    parts = {p.name: json.loads(p.read_text(encoding="utf8")) for p in sorted(review.glob("coach_part*.json"))}
    log = []
    for n, s in sorted(meta.items()):
        x = next((x for x in parts.get(s["part"], []) if isinstance(x, dict) and x.get("pid") == s["pid"]
                  and x.get("trip", 1) == s["trip"] and isinstance(x.get("shot"), dict)), None)
        if x is None:
            log.append(f"S{n:02d}: trip pid {s['pid']} trip {s['trip']} no longer in {s['part']}, skipped")
            continue
        shot, a = x["shot"], answers.get(n)
        if s.get("sheet") is None:
            shot.update(xy=None, xy_note="unclear: no release time or no video frame")
            settle_zone(shot, None)
        elif a is None:
            continue                                   # not answered yet: check lists it
        elif a.get("confidence") in ACCEPT and xy_ok(a.get("xy")):
            tile = a.get("tile") if isinstance(a.get("tile"), int) and 1 <= a.get("tile") <= len(s["tiles"]) else None
            tm = s["tiles"][tile - 1] if tile else {}
            shot["xy"] = [round(float(v), 1) for v in a["xy"]]
            shot["xy_src"] = dict(method="grid", tile_t=tm.get("t"), cam_t=tm.get("cam_t"),
                                  cam_quality=tm.get("quality"), confidence=a["confidence"])
            shot.pop("xy_note", None)
            if a.get("note"):
                shot["xy_src"]["note"] = str(a["note"])[:200]
            arc = a.get("arc") if a.get("arc") in ("inside", "on", "outside") else None
            if arc:
                shot["xy_src"]["arc"] = arc
            z = settle_zone(shot, s.get("side"), arc)
            if z:
                log.append(f"S{n:02d}: {z}")
        else:
            why = a.get("note") or ("low confidence" if a.get("confidence") == "low" else "no spot")
            shot.update(xy=None, xy_note=f"unclear: {why}"[:200])
            shot.pop("xy_src", None)
            settle_zone(shot, None)
        log.append(f"S{n:02d}: {s['part']} pid {s['pid']} -> {shot.get('xy') or shot.get('xy_note')}")
    for name, v in parts.items():
        (review / name).write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf8")
    return log


def missing(review: Path) -> list[str]:
    """Shots in R/coach_part*.json with neither "xy" (a spot or null) nor, for null, an "xy_note"."""
    out = []
    for p in sorted(review.glob("coach_part*.json")):
        for x in json.loads(p.read_text(encoding="utf8")):
            s = x.get("shot") if isinstance(x, dict) else None
            if isinstance(s, dict) and ("xy" not in s or (s["xy"] is None and not s.get("xy_note"))):
                out.append(f"{p.name}: pid {x.get('pid')} trip {x.get('trip', 1)} shot has no xy / xy_note")
    return out


def conflicts(review: Path) -> list[str]:
    """Shots whose "zone_flag" asks for a decision ("confirm: ..."): fix the trip from the sheet, drop the flag."""
    out = []
    for p in sorted(review.glob("coach_part*.json")):
        for x in json.loads(p.read_text(encoding="utf8")):
            s = x.get("shot") if isinstance(x, dict) else None
            if isinstance(s, dict) and str(s.get("zone_flag") or "").startswith("confirm"):
                out.append(f"{p.name}: pid {x.get('pid')} trip {x.get('trip', 1)} {s['zone_flag']}")
    return out


# ---- CLI -----------------------------------------------------------------------------------------------------

def sheets_main(argv):
    """shot-locate sheets: grid sheets, shots.json and one brief per batch (see module doc)."""
    ap = argparse.ArgumentParser(prog="hoop-tape-miner shot-locate sheets", description=sheets_main.__doc__)
    ap.add_argument("--run", required=True)
    ap.add_argument("--review", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--game", help="game.json for the team box colours")
    ap.add_argument("--out", help="default: REVIEW/locate")
    ap.add_argument("--batches", type=int, help=f"number of batches (default: {PER_BATCH} shots each)")
    ap.add_argument("--per-batch", type=int, default=PER_BATCH)
    ap.add_argument("--limit", type=int, help="only the first N shots (pilot)")
    ap.add_argument("--only", help="shot numbers, e.g. 32,34: rebuild just these sheets in the existing shots.json "
                                   "and write one more brief for them (answers in a later answers_<b>.json win)")
    ap.add_argument("--brief", default=str(BRIEF))
    a = ap.parse_args(argv)
    run, review = Path(a.run), Path(a.review)
    out = Path(a.out) if a.out else review / "locate"
    if not Path(a.video).is_file():
        raise SystemExit(f"video not found: {a.video}")
    if a.game and Path(a.game).is_file():
        use_game(json.loads(Path(a.game).read_text(encoding="utf8")))
    out.mkdir(parents=True, exist_ok=True)
    shots = shot_list(review)
    shots = shots[:a.limit] if a.limit else shots
    old = None
    if a.only:
        old = json.loads((out / "shots.json").read_text(encoding="utf8"))
        want = {int(v) for v in a.only.split(",")}
        prev = {m["n"]: m for m in old["shots"]}
        shots = [s for s in shots if s["n"] in want]
        for s in shots:
            m = prev.get(s["n"], {})
            if (m.get("part"), m.get("pid"), m.get("trip")) != (s["part"], s["pid"], s["trip"]):
                raise SystemExit(f"S{s['n']:02d} is not the same trip as in shots.json: rebuild every sheet")
    tracks = pd.read_pickle(run / "tracks.pkl") if (run / "tracks.pkl").is_file() else None
    nums = run / "player_numbers.json"
    numbers = {int(k): v for k, v in json.loads(nums.read_text()).items()} if nums.is_file() else {}
    ball = pd.read_pickle(run / "ball_track.pkl") if (run / "ball_track.pkl").is_file() else None
    res = build(cv2.VideoCapture(a.video), shots, out, load_cameras(run), tracks, numbers, ball)
    if old is not None:
        new = {s["n"]: s for s in res}
        res, bs = [new.get(m["n"], m) for m in old["shots"]], [[s for s in new.values() if s.get("sheet")]]
        start = old.get("batches", 0) + 1
    else:
        bs, start = batches(res, a.batches, a.per_batch), 1
    (out / "shots.json").write_text(json.dumps(dict(offsets=TILE_OFFSETS, batches=start - 1 + len(bs), shots=res),
                                               indent=1), encoding="utf8")
    template = Path(a.brief).read_text(encoding="utf8") if Path(a.brief).is_file() else None
    for b, items in enumerate(bs, start):
        if template:
            (out / f"brief_locate_{b}.md").write_text(brief(template, b, list(items), out), encoding="utf8")
    print(f"{sum(bool(s['sheet']) for s in res)}/{len(res)} shots with a sheet, {len(bs)} batches -> {out}")


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "sheets":
        return sheets_main(rest)
    if cmd in ("merge", "check"):
        ap = argparse.ArgumentParser(prog=f"hoop-tape-miner shot-locate {cmd}")
        ap.add_argument("--review", required=True)
        ap.add_argument("--locate", help="default: REVIEW/locate")
        a = ap.parse_args(rest)
        review = Path(a.review)
        if cmd == "merge":
            locate = Path(a.locate) if a.locate else review / "locate"
            log = merge(review, locate)
            (locate / "merge.md").write_text("# Shot locate merge\n\n" + "".join(f"- {x}\n" for x in log),
                                             encoding="utf8")
            print(f"{len(log)} lines -> {locate / 'merge.md'}")
            return
        miss = missing(review) + conflicts(review)
        print("\n".join(miss) or "every shot has a location or an xy_note, no zone to confirm")
        raise SystemExit(1 if miss else 0)
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
