"""Evidence clips and a labelled overlay reel, rendered from completed perception JSONL."""
from __future__ import annotations

import bisect
import json
from pathlib import Path

from sports_video_coach import media
from .perception import digest, load, paths

RENDER_VERSION = 3


def signature(evidence: Path, video: Path, limit: int) -> dict:
    stat = video.stat()
    return dict(evidence_sha256=digest(evidence), limit=limit, renderer=RENDER_VERSION,
                video=str(video.resolve()), video_size=stat.st_size, video_mtime=stat.st_mtime_ns)


def complete(out: Path, expected: dict) -> bool:
    stamp = out / "media.json"
    if not stamp.exists():
        return False
    manifest = load(stamp)
    if manifest.get("signature") != expected:
        return False
    required = [out / f'{eid}{suffix}.mp4' for eid in manifest["event_ids"] for suffix in ("", "-overlay")]
    if required:
        required.append(out / "validation.mp4")
    return all(p.is_file() and p.stat().st_size > 0 for p in required)


def done(game) -> bool:
    from .perception import enabled
    if not enabled(game):
        return True
    evidence = game.run / "perception" / "evidence.json"
    if not evidence.exists() or not game.video or not game.video.exists():
        return False
    return complete(game.folder / "perception", signature(evidence, game.video,
                    game.game["perception"].get("media_limit", 12)))


def commands(game) -> list[list[str]]:
    return [["perception", "media", "--game", str(game.gj), "--limit",
             str(game.game["perception"].get("media_limit", 12))]]


def select_events(events: list[dict], limit: int) -> list[dict]:
    """Reviewed examples first, then spread across event kinds and the game timeline."""
    if limit < 1:
        raise ValueError("limit must be positive")
    selected = [e for e in events if e["review_status"] != "pending"][:limit]
    used = {e["id"] for e in selected}
    for kind in ("shot", "rebound", "pass", "turnover", "steal", "dribble"):
        if any(e["type"] == kind for e in selected):
            continue
        candidates = [e for e in events if e["type"] == kind and e["id"] not in used]
        if candidates and len(selected) < limit:
            event = candidates[len(candidates) // 2]
            selected.append(event)
            used.add(event["id"])
    candidates = [e for e in events if e["id"] not in used]
    left = limit - len(selected)
    for i in range(min(left, len(candidates))):
        selected.append(candidates[min(len(candidates) - 1, int(i * len(candidates) / left))])
    return sorted(selected, key=lambda e: e["start"])


def frame_rows(doc: dict, selected: list[dict]) -> dict:
    windows = [(e["start"] - 3, e["end"] + 3) for e in selected]
    result = {}
    for source in doc["sources"]:
        if not source.get("spatial", {}).get("aligned"):
            continue
        if not any(a <= source["end"] and b >= source["start"] for a, b in windows):
            continue
        if digest(Path(source["path"])) != source["sha256"]:
            raise ValueError("perception stream changed after import; re-import before rendering")
        rows = []
        with Path(source["path"]).open(encoding="utf8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                t = row["time"] + source["offset"]
                if any(a <= t <= b for a, b in windows):
                    rows.append((t, row))
        result[source["id"]] = rows
    return result


def annotate(frame, row, event, t):
    import cv2
    w = frame.shape[1]
    for player in (row or {}).get("players", []):
        box = player.get("box")
        if not box:
            continue
        x1, y1, x2, y2 = map(int, box)
        team = player.get("team_semantic")
        color = {"light": (235, 175, 70), "dark": (120, 180, 250)}.get(team, (170, 170, 170))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
        label = f'ID {player.get("id", "?")}'
        if player.get("jersey_number") is not None:
            label += f' ~#{player["jersey_number"]}'
        cv2.putText(frame, label, (max(0, x1), max(78, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1, cv2.LINE_AA)
        pose = player.get("pose") or []
        for a, b in ((5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
                     (11, 13), (13, 15), (12, 14), (14, 16)):
            if len(pose) > b and min(pose[a][2], pose[b][2]) >= .25:
                cv2.line(frame, tuple(map(int, pose[a][:2])), tuple(map(int, pose[b][:2])), color, 1, cv2.LINE_AA)
    ball = (row or {}).get("ball") or {}
    if ball.get("center"):
        center = tuple(map(int, ball["center"]))
        cv2.circle(frame, center, 9, (30, 240, 100) if ball.get("observed") else (160, 160, 160), 2)
    cv2.rectangle(frame, (0, 0), (w, 73), (20, 30, 40), -1)
    headline = f'{int(t)//60:02d}:{t%60:04.1f}  {event["type"].upper()}  |  {event["review_status"].upper()}'
    cv2.putText(frame, headline, (14, 22), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 1, cv2.LINE_AA)
    legend = ('Player / pose: orange = dark kit, blue = light kit, grey = unknown; IDs / numbers unconfirmed'
              if event.get("spatial_aligned", True) else 'Source footage only: external coordinates are not verified')
    cv2.putText(frame, legend,
                (14, 43), cv2.FONT_HERSHEY_SIMPLEX, .42, (200, 215, 225), 1, cv2.LINE_AA)
    cv2.putText(frame, 'Ball: green = detected (may be wrong), grey = predicted | Original-video clock',
                (14, 64), cv2.FONT_HERSHEY_SIMPLEX, .42, (200, 215, 225), 1, cv2.LINE_AA)
    return frame


def render_overlay(video: Path, out: Path, event: dict, rows: list, start: float, end: float):
    import cv2
    fps = 24
    times = [r[0] for r in rows]
    with media.scratch(out) as tmp:
        # ffmpeg uses presentation timestamps, including low-rate/VFR recordings.
        # Seeking source frames with round(time * average_fps) would drift or skip them.
        normalized = tmp / "source.mp4"
        media.ffmpeg("-ss", start, "-i", video, "-t", end - start, "-vf", f"fps={fps}",
                     "-c:v", "libx264", "-crf", "18", "-preset", "ultrafast", "-an", normalized)
        cap = cv2.VideoCapture(str(normalized))
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not cap.isOpened():
            raise ValueError(f"cannot read normalized clip from {video}")
        intermediate = tmp / "overlay.mp4"
        writer = cv2.VideoWriter(str(intermediate), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if not writer.isOpened():
            cap.release()
            raise ValueError("overlay video writer unavailable")
        try:
            written = 0
            for i in range(int(cap.get(cv2.CAP_PROP_FRAME_COUNT))):
                t = start + i / fps
                ok, frame = cap.read()
                if not ok:
                    raise ValueError(f"video ended during evidence clip at {t:.2f}")
                k = bisect.bisect_left(times, t)
                near = min((j for j in (k - 1, k) if 0 <= j < len(times)),
                           key=lambda j: abs(times[j] - t), default=None)
                candidate = rows[near][1] if near is not None else None
                max_delta = min(.05, .5 / candidate["fps"] + 1e-4) if candidate else 0
                row = candidate if near is not None and abs(times[near] - t) <= max_delta else None
                writer.write(annotate(frame, row, event, t))
                written += 1
            if not written:
                raise ValueError("empty evidence clip")
        finally:
            cap.release()
            writer.release()
        with media.partial(out) as target:
            media.ffmpeg("-i", intermediate, "-c:v", "libx264", "-crf", "20", "-preset", "fast",
                         "-pix_fmt", "yuv420p", "-movflags", "+faststart", target)


def build(args):
    game_path = Path(args.game).resolve()
    _, run, video = paths(game_path)
    evidence = run / "perception" / "evidence.json"
    doc = load(evidence)
    selected = select_events(doc["events"], args.limit)
    out = game_path.parent / "perception"
    out.mkdir(parents=True, exist_ok=True)
    stamp = out / "media.json"
    expected = signature(evidence, video, args.limit)
    if not args.force and complete(out, expected):
        print(f"kept evidence media: {out}")
        return
    rows = frame_rows(doc, selected)
    duration = media.duration_s(video)
    rendered, windows = [], []
    for event in selected:
        source = next(s for s in doc["sources"] if s["id"] == event["source"])
        start = max(0, source["start"], event["start"] - 3)
        end = min(duration, source["end"], event["end"] + 3, event["start"] + 24)
        if end <= start:
            raise ValueError(f"{event['id']}: no source footage in event window")
        clip = out / f'{event["id"]}.mp4'
        with media.partial(clip) as target:
            media.ffmpeg("-ss", start, "-i", video, "-t", end - start, "-c:v", "libx264", "-crf", "20",
                         "-preset", "fast", "-c:a", "aac", "-movflags", "+faststart", target)
        overlay = out / f'{event["id"]}-overlay.mp4'
        render_overlay(video, overlay, {**event, "spatial_aligned": source.get("spatial", {}).get("aligned", False)},
                       rows.get(event["source"], []), start, end)
        rendered.append(overlay)
        windows.append(dict(id=event["id"], start=start, end=end, truncated=end < event["end"]))
        print(f"rendered evidence {event['id']}", flush=True)
    if rendered:
        with media.partial(out / "validation.mp4") as target:
            media.concat(rendered, target, out)
    media.write_json_atomic(stamp, dict(signature=expected, event_ids=[e["id"] for e in selected],
                                       windows=windows, overlay_fps=24,
                                       duration_seconds=media.duration_s(out / "validation.mp4") if rendered else 0))
    print(out / "validation.mp4" if rendered else "No event candidates; empty media manifest written.")
