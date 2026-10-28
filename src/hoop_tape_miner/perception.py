"""Optional OpenHoopVision backend and evidence import. No model imports in the host process.

Completed JSONL stays private in run/perception. Candidates never overwrite official
statistics or reviewed trips. NBA coordinates and fallback points remain untrusted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

from sports_video_coach import media

UPSTREAM = "https://github.com/feifeifei85/OpenHoopVision"
PIN = "ec969037b2c02b983a77b260c50cb9eb36fe9fc1"
SCHEMA = "svc_perception_v1"
IMPORT_VERSION = 2
EVENTS = {"shot", "pass", "dribble", "rebound", "turnover", "steal"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def paths(game_path: Path) -> tuple[dict, Path, Path]:
    game_path = game_path.resolve()
    game = load(game_path)
    run = Path(game.get("run") or "run")
    video = Path(game["video"])
    return game, (run if run.is_absolute() else game_path.parent / run), (
        video if video.is_absolute() else game_path.parent / video)


def evidence_path(folder: Path) -> Path | None:
    from .film_index import run_dir
    run = run_dir(folder)
    return run / "perception" / "evidence.json" if run is not None else None


def finite(value, name: str, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"invalid {name}: {value!r}")
    return float(value)


def frame_time(event: dict, key: str, fps: float, default: float) -> float:
    frame = event.get(key + "_frame")
    by_frame = None
    if frame is not None:
        frame = finite(frame, key + "_frame", 1)
        if frame != int(frame):
            raise ValueError(f"{key}_frame must be an integer")
        by_frame = (frame - 1) / fps
    if event.get(key) is not None:
        value = finite(event[key], key)
        if by_frame is not None and abs(value - by_frame) > 1e-4:
            raise ValueError(f"{key} seconds and frame disagree")
        return value
    return by_frame if by_frame is not None else default


def team_of(value, mapping: dict) -> str | None:
    key = {0: "dark", 1: "light"}.get(value, value)
    return mapping.get(key)


def completed_sources(run: Path) -> list[Path]:
    return [p for p in sorted((run / "perception").glob("*/tracks.jsonl")) if (p.parent / "run.json").is_file()]


def verified_completion(provenance: dict, source: dict, video: Path) -> bool:
    """A command string alone cannot certify that an external stream finished."""
    sig = provenance.get("signature", {})
    start, end = sig.get("start"), sig.get("end")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
               for v in (start, end)) or not 0 <= start < end:
        return False
    stat = video.stat()
    return bool(provenance.get("command") and provenance.get("weights")
                and provenance.get("tracks_sha256") == source["sha256"]
                and sig.get("upstream_commit") == PIN and sig.get("video")
                and Path(sig["video"]).resolve() == video.resolve()
                and sig.get("video_size") == stat.st_size and sig.get("video_mtime") == stat.st_mtime_ns
                and abs(source["start"] - start) < 1e-4
                and abs(source["end"] - end) <= max(.1, 1.5 / source["fps"]))


def import_signature(game: dict, run: Path, video: Path, files: list[Path], mapping: dict) -> dict:
    from sports_video_coach.pipeline import signature
    root = run / "perception"
    inputs = [video, run / "camera.npz", root / "reviews.json", root / "labels.json", *files,
              *(p.parent / "run.json" for p in files),
              *sorted((run / game.get("review_dir", "review_v1")).glob("coach_part*.json"))]
    return dict(version=IMPORT_VERSION, rosters=game.get("rosters"), team_map=mapping,
                sources=[str(p.resolve()) for p in files],
                inputs={str(p.resolve()): signature(p) for p in inputs})


def import_done(game) -> bool:
    if not enabled(game):
        return True
    evidence = game.run / "perception" / "evidence.json"
    files = completed_sources(game.run)
    if not evidence.exists() or not files or not game.video:
        return False
    dark = game.game["perception"].get("dark_team")
    mapping = {"dark": dark, "light": "them" if dark == "us" else "us"} if dark else {}
    return load(evidence).get("import_signature") == import_signature(game.game, game.run, game.video, files, mapping)


def import_jsonl(source: Path, *, offset: float = 0, team_map: dict | None = None,
                 rosters: dict | None = None, source_id: str = "source") -> dict:
    """Normalize a finalized frame stream, keeping categorical evidence and raw event fields."""
    finite(offset, "offset")
    mapping = team_map or {}
    if set(mapping) - {"dark", "light"} or any(v not in {"us", "them"} for v in mapping.values()):
        raise ValueError("team_map must map dark/light to us/them")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("team_map must be one-to-one")
    rosters = {k: {str(n) for n in v} for k, v in (rosters or {}).items()}
    counts, identities, events, seen = Counter(), {}, [], {}
    run_config, first_t, last_t, fps = {}, None, None, None
    previous_frame = 0
    with source.open(encoding="utf8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row.get("schema") != "basketball_frame_v2":
                    raise ValueError("expected basketball_frame_v2 (compact events.json is insufficient)")
                rate = finite(row.get("fps"), "fps", 1e-6)
                frame = finite(row.get("frame"), "frame", 1)
                if frame != int(frame) or frame != previous_frame + 1:
                    raise ValueError("frame numbers must increase consecutively from 1")
                t = finite(row.get("time"), "time")
                if abs(t - (frame - 1) / rate) > max(0.001, 0.1 / rate):
                    raise ValueError("frame and timestamp disagree")
                if fps is not None and abs(rate - fps) > 0.001:
                    raise ValueError("fps changed within a stream")
                fps, previous_frame = rate, frame
                first_t = t if first_t is None else first_t
                last_t = t
                run_config = row.get("run_config", run_config)
                counts["frames"] += 1
                ball = row.get("ball") or {}
                counts["ball_observed_frames"] += int(bool(ball.get("observed")))
                counts["ball_interpolated_frames"] += int(bool(ball.get("interpolated")))
                counts["rim_frames"] += int(bool(row.get("rim")))
                players = row.get("players") or []
                for player in players:
                    counts["player_observations"] += 1
                    counts["pose_observations"] += int(bool(player.get("pose")))
                    counts["court_observations"] += int(player.get("court_xy") is not None)
                    counts["number_observations"] += int(player.get("jersey_number") is not None)
                    pid = player.get("id")
                    if pid is None:
                        continue
                    identity = identities.setdefault(str(pid), dict(
                        id=f"{source_id}:{pid}", upstream_id=pid, first=offset + t, last=offset + t,
                        observations=0, teams=Counter(), numbers=Counter(), local_ids=set()))
                    identity["last"] = offset + t
                    identity["observations"] += 1
                    if player.get("local_track_id") is not None:
                        identity["local_ids"].add(player["local_track_id"])
                    team = team_of(player.get("team_semantic", player.get("team")), mapping)
                    if team:
                        identity["teams"][team] += 1
                    number = player.get("jersey_number")
                    if number is not None:
                        number = str(number)
                        if team and (not rosters.get(team) or number in rosters[team]):
                            identity["numbers"][number] += 1
                for raw in row.get("events") or []:
                    kind = raw.get("event")
                    if kind not in EVENTS:
                        continue
                    start = frame_time(raw, "start", fps, t)
                    end = frame_time(raw, "end", fps, t)
                    if end < start or end > t + 1 / fps:
                        raise ValueError("invalid event interval")
                    key = json.dumps([kind, raw.get("shot_id"), start, end, raw.get("player_id"),
                                      raw.get("receiver_id")], sort_keys=True)
                    if key in seen:
                        if seen[key] != raw:
                            raise ValueError("conflicting copies of a completed event")
                        continue
                    seen[key] = raw
                    result = {"made": "made", "miss": "missed", "missed": "missed"}.get(raw.get("result"))
                    pid = raw.get("player_id")
                    event = dict(id=f"{source_id}-{len(events) + 1:05d}", type=kind,
                                 start=round(start + offset, 6), end=round(end + offset, 6),
                                 team=team_of(raw.get("team"), mapping),
                                 player_id=f"{source_id}:{pid}" if pid is not None else None,
                                 result=result, points=None, court_xy=None,
                                 review_status="pending", source=source_id, line=line_no,
                                 evidence=dict(result_source=raw.get("result_source"),
                                               verdict=raw.get("verdict_confidence"),
                                               points_source=raw.get("points_source")), raw=raw)
                    for field in ("receiver_id", "gained_by"):
                        value = raw.get(field)
                        event[field] = f"{source_id}:{value}" if value is not None else None
                    event["gained_team"] = team_of(raw.get("gained_team"), mapping)
                    event["rebound_type"] = raw.get("rebound_type")
                    event["cause"] = raw.get("cause")
                    if raw.get("points_source") == "two_point_fallback":
                        event["evidence"]["warning"] = "point value unresolved; upstream used two-point fallback"
                    events.append(event)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"{source}:{line_no}: {exc}") from exc
    if not counts["frames"]:
        raise ValueError(f"{source}: empty frame stream")
    result_identities = []
    for identity in identities.values():
        identity["local_ids"] = sorted(identity["local_ids"], key=str)
        identity["teams"] = dict(identity["teams"])
        identity["numbers"] = dict(identity["numbers"])
        result_identities.append(identity)
    return dict(id=source_id, path=str(source.resolve()), sha256=digest(source), offset=offset,
                start=round(offset + first_t, 6), end=round(offset + last_t + 1 / fps, 6), fps=fps,
                team_map=mapping, counts=dict(counts), run_config=run_config,
                events=events, identities=result_identities)


def bundle(sources: list[dict]) -> dict:
    """Combine disjoint windows; each window retains its own identity namespace."""
    ordered = sorted(sources, key=lambda x: x["start"])
    if len({s["id"] for s in sources}) != len(sources):
        raise ValueError("duplicate source IDs or overlapping evidence windows")
    for left, right in zip(ordered, ordered[1:]):
        if left["id"] == right["id"] or left["end"] > right["start"] + 1e-6:
            raise ValueError("overlapping evidence windows would double-count candidates")
    counts = Counter()
    for source in ordered:
        counts.update(source["counts"])
    events = sorted((e for s in ordered for e in s["events"]), key=lambda e: (e["start"], e["id"]))
    commits = {s.get("provenance", {}).get("signature", {}).get("upstream_commit") for s in ordered}
    return dict(schema=SCHEMA, backend="OpenHoopVision", upstream=UPSTREAM,
                upstream_commit=next(iter(commits)) if len(commits) == 1 else None,
                counts=dict(counts), event_counts=dict(Counter(e["type"] for e in events)),
                analyzed_seconds=round(sum(s["end"] - s["start"] for s in ordered), 3),
                sources=[{k: v for k, v in s.items() if k not in {"events", "identities"}} for s in ordered],
                identities=[p for s in ordered for p in s["identities"]], events=events,
                policy="Model candidates only; no official stats, point values or confirmed player identities.")


def apply_reviews(doc: dict, reviews: dict) -> dict:
    """Explicit per-event human/agent review; cannot silently introduce new IDs."""
    known = {e["id"] for e in doc["events"]}
    if set(reviews) - known:
        raise ValueError("review contains unknown event IDs")
    for event in doc["events"]:
        review = reviews.get(event["id"])
        if review is None:
            continue
        if (review.get("status") not in {"confirmed", "rejected", "unclear"}
                or not isinstance(review.get("note"), str) or not review["note"].strip()
                or ("note_zh" in review and not isinstance(review["note_zh"], str))):
            raise ValueError(f"{event['id']}: review needs status and evidence note")
        if any("????" in review.get(k, "") or "\ufffd" in review.get(k, "") for k in ("note", "note_zh")):
            raise ValueError(f"{event['id']}: review text has damaged encoding or placeholder question marks")
        event["review_status"] = review["status"]
        event["review"] = review
    return doc


def analyze(args) -> Path:
    """Run pinned external source in its own process, atomically publish completed records."""
    game, run, video = paths(Path(args.game))
    checkout = Path(args.checkout).resolve()
    sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if sha != PIN:
        raise ValueError(f"expected OpenHoopVision {PIN}; got {sha}")
    changed = subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain",
                                       "--untracked-files=no", "--", ".", ":(exclude)weights/**"], text=True).strip()
    if changed:
        raise ValueError("OpenHoopVision tracked source differs from the pinned revision")
    for name in ("rf-detr-basketball.pth", "rtmpose-s_simcc-aic-coco.pth", "court_mobilenetv4_896x512.pt",
                 "osnet_x1_0_msmt17.pt", "basketball_jersey_number.ckpt"):
        weight = checkout / "weights" / name
        if not weight.is_file() or weight.stat().st_size < 1024:
            raise ValueError(f"missing checkpoint payload: {weight} (Git LFS pointers are not weights)")
    offset = finite(args.start, "start")
    if args.fps is not None:
        finite(args.fps, "fps", 1)
    if args.batch < 1 or args.short_side < 32:
        raise ValueError("batch must be positive and short-side at least 32")
    duration = media.duration_s(video)
    end = args.end if args.end is not None else duration
    if finite(end, "end") <= offset:
        raise ValueError("end must be after start")
    if end > duration + .001:
        raise ValueError("analysis interval extends beyond the source video")
    out = (run / "perception" / f"{offset:.3f}-{end:.3f}").resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "tracks.jsonl"
    weights = {p.name: digest(p) for p in (checkout / "weights").iterdir() if p.is_file()}
    signature = dict(upstream_commit=sha, video=str(video.resolve()), video_size=video.stat().st_size,
                     video_mtime=video.stat().st_mtime_ns, start=offset, end=end, fps=args.fps,
                     short_side=args.short_side, batch=args.batch)
    stamp = out / "run.json"
    if (not args.force and raw.exists() and stamp.exists() and load(stamp).get("signature") == signature
            and load(stamp).get("weights") == weights):
        print(f"kept completed analysis: {raw}")
        return raw
    clip = out / "input.mp4"
    rate = args.fps
    if rate is None:
        stream = next(s for s in media.probe(video)["streams"] if s.get("codec_type") == "video")
        rate = float(Fraction(stream["avg_frame_rate"]))
        finite(rate, "source average fps", 1e-6)
    with media.partial(clip) as target:
        # Upstream uses a frame-index clock. Normalize timestamps even for a VFR source.
        media.ffmpeg("-ss", offset, "-i", video, "-t", end - offset, "-vf", f"fps={rate}",
                     "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-an", target)
    started = time.monotonic()
    with media.partial(raw) as raw_tmp:
        command = [args.python or sys.executable, str(checkout / "main.py"), "--video", str(clip),
                   "--output", "none", "--tracks", str(raw_tmp), "--events", str(out / "upstream-events.json"),
                   "--short-side", str(args.short_side), "--detector-batch-size", str(args.batch),
                   "--pose-batch-size", "16"]
        with (out / "backend.log").open("w", encoding="utf8") as log:
            subprocess.run(command, cwd=checkout, stdout=log, stderr=subprocess.STDOUT, check=True)
    media.write_json_atomic(stamp, dict(signature=signature, seconds=round(time.monotonic() - started, 2),
                                       weights=weights, command=command, tracks_sha256=digest(raw)))
    print(f"completed analysis: {raw}")
    return raw


def import_sources(args) -> Path:
    game, run, video = paths(Path(args.game))
    source_files = [Path(x) for x in args.tracks] if args.tracks else completed_sources(run)
    if not source_files:
        raise ValueError("no completed tracks.jsonl files")
    mapping = {"dark": args.dark_team, "light": "them" if args.dark_team == "us" else "us"} if args.dark_team else {}
    expected = import_signature(game, run, video, source_files, mapping)
    sources = []
    for path in source_files:
        if any(part in {".partial", ".tmp"} or part.endswith((".partial", ".tmp")) for part in path.parts):
            raise ValueError(f"{path}: temporary streams cannot be imported")
        stamp = path.parent / "run.json"
        provenance = load(stamp) if stamp.exists() else {}
        sig = provenance.get("signature", {})
        if sig.get("video") and Path(sig["video"]).resolve() != video.resolve():
            raise ValueError(f"{path}: analysis belongs to a different source video")
        sha = digest(path)
        if provenance.get("tracks_sha256") and provenance["tracks_sha256"] != sha:
            raise ValueError(f"{path}: completed stream changed after analysis")
        offset = sig["start"] if stamp.exists() else args.offset
        # Offsets and team interpretation are part of review identity, not just the raw bytes.
        identity = hashlib.sha256(json.dumps([sha, offset, mapping], sort_keys=True).encode()).hexdigest()[:12]
        source = import_jsonl(path, offset=offset, team_map=mapping, rosters=game.get("rosters"),
                              source_id=f"ohv-{identity}")
        if stamp.exists():
            source["provenance"] = provenance
            if isinstance(sig.get("end"), (int, float)) and abs(source["end"] - sig["end"]) > max(.1, 1.5 / source["fps"]):
                raise ValueError(f"{path}: completed frame coverage differs from the analysis interval")
        verified = verified_completion(provenance, source, video)
        source["finalization"] = "adapter_completed_run" if verified else "external_unverified"
        processed = path.parent / "input.mp4"
        spatial = dict(aligned=False, reason="External JSONL has no verified source-frame transform")
        if verified and processed.is_file():
            if media.video_size(processed) == media.video_size(video):
                spatial = dict(aligned=True, basis="adapter_full_frame_input", transform="identity",
                               source_size=list(media.video_size(video)))
        source["spatial"] = spatial
        sources.append(source)
    doc = bundle(sources)
    doc["import_signature"] = expected
    doc["video_duration"] = media.duration_s(video)
    if any(s["end"] > doc["video_duration"] + 0.1 for s in sources):
        raise ValueError("evidence extends beyond the source video")
    from .perception_review import compare_reviewed, project_candidates
    project_candidates(doc, run / "camera.npz")
    compare_reviewed(doc, run / game.get("review_dir", "review_v1"))
    reviews = run / "perception" / "reviews.json"
    if reviews.exists():
        apply_reviews(doc, load(reviews))
    labels = run / "perception" / "labels.json"
    if labels.exists():
        from .perception_eval import evaluate
        doc["evaluation"] = evaluate(doc, load(labels))
    out = run / "perception" / "evidence.json"
    if expected != import_signature(game, run, video, source_files, mapping):
        raise ValueError("perception inputs changed during import; retry with stable completed sources")
    media.write_json_atomic(out, doc)
    print(json.dumps({"file": str(out), "seconds": doc["analyzed_seconds"], "events": doc["event_counts"]}))
    return out


def enabled(game) -> bool:
    return bool((game.game.get("perception") or {}).get("enabled"))


def analysis_done(game) -> bool:
    if not enabled(game):
        return True
    if not game.video or not game.video.is_file():
        return False
    cfg = game.game["perception"]
    stat = game.video.stat()
    duration = media.duration_s(game.video)
    weights = None
    if cfg.get("checkout"):
        weight_dir = Path(cfg["checkout"]) / "weights"
        if not weight_dir.is_dir():
            return False
        weights = {p.name: digest(p) for p in weight_dir.iterdir() if p.is_file()}
    for path in (game.run / "perception").glob("*/run.json"):
        stamp = load(path)
        sig = stamp.get("signature", {})
        if weights is not None and stamp.get("weights") != weights:
            continue
        if (path.parent / "tracks.jsonl").is_file() and all((
            sig.get("upstream_commit") == PIN, sig.get("start") == 0,
            isinstance(sig.get("end"), (int, float)) and abs(sig["end"] - duration) < .1,
            sig.get("video") == str(game.video.resolve()), sig.get("video_size") == stat.st_size,
            sig.get("video_mtime") == stat.st_mtime_ns, sig.get("fps") == cfg.get("fps"),
            sig.get("short_side") == cfg.get("short_side", 768), sig.get("batch") == cfg.get("batch", 2),
        )):
            return True
    return False


def analysis_commands(game) -> list[list[str]]:
    config = game.game["perception"]
    command = ["perception", "analyze", "--game", str(game.gj), "--checkout", config["checkout"]]
    for key in ("python", "fps", "short_side", "batch"):
        if config.get(key) is not None:
            command.extend(["--" + key.replace("_", "-"), str(config[key])])
    return [command]


def import_commands(game) -> list[list[str]]:
    command = ["perception", "import", "--game", str(game.gj)]
    team = game.game["perception"].get("dark_team")
    if team:
        command.extend(["--dark-team", team])
    return [command]


def source_inputs(game) -> list[Path]:
    root = game.run / "perception"
    return [*sorted(root.glob("*/tracks.jsonl")), *sorted(root.glob("*/run.json")),
            root / "reviews.json", root / "labels.json", game.run / "camera.npz",
            *sorted(game.review.glob("coach_part*.json"))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    run = sub.add_parser("analyze", help="run an existing pinned OpenHoopVision checkout (no installation)")
    run.add_argument("--game", required=True)
    run.add_argument("--checkout", required=True)
    run.add_argument("--python", help="backend Python executable; defaults to the current environment")
    run.add_argument("--start", type=float, default=0)
    run.add_argument("--end", type=float)
    run.add_argument("--fps", type=float, help="optional validated analysis frame rate; default native")
    run.add_argument("--short-side", type=int, default=768)
    run.add_argument("--batch", type=int, default=2)
    run.add_argument("--force", action="store_true")
    imp = sub.add_parser("import", help="import completed adapter output or unverified external frame JSONL")
    imp.add_argument("--game", required=True)
    imp.add_argument("--tracks", nargs="+")
    imp.add_argument("--offset", type=float, default=0, help="original-video offset without a run.json")
    imp.add_argument("--dark-team", choices=["us", "them"], help="explicitly verified jersey-color mapping")
    assets = sub.add_parser("media", help="cut evidence clips and render an overlay validation reel")
    assets.add_argument("--game", required=True)
    assets.add_argument("--limit", type=int, default=12)
    assets.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.action == "analyze":
            analyze(args)
        elif args.action == "import":
            import_sources(args)
        else:
            from .perception_media import build
            build(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as ex:
        raise SystemExit(str(ex)) from ex


if __name__ == "__main__":
    main()
