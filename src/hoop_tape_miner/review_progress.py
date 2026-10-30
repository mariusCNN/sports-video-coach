"""Persistent, self-reported sheet coverage; not proof that a reviewer understood the film."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sports_video_coach.media import write_json_atomic

POLICY = "review_policy.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def progress(review: Path, part: int, read: list[str] = ()) -> dict:
    """Save only sheets whose possession has a valid checkpoint; invalidate changed inputs."""
    review = Path(review).resolve()
    source = review / f"part{part}.json"
    possessions = json.loads(source.read_text(encoding="utf8"))
    assigned = {name: p["pid"] for p in possessions for name in p["sheets"]}
    for name in assigned:
        path = (review / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(review):
            raise ValueError(f"unsafe sheet path: {name}")
    unknown = set(read) - assigned.keys()
    if unknown:
        raise ValueError(f"sheets not assigned to part {part}: {sorted(unknown)}")
    stamp = digest(source)
    ledger = review / f"read_part{part}.json"
    old = json.loads(ledger.read_text(encoding="utf8")) if ledger.exists() else {}
    if not isinstance(old, dict) or (old and old.get("version") != 1):
        raise ValueError(f"invalid progress file: {ledger.name}")
    saved = old.get("read", {}) if old.get("part_sha256") == stamp else {}
    if not isinstance(saved, dict):
        raise ValueError(f"invalid read map: {ledger.name}")
    hashes = {name: digest(review / name) for name in set(saved) | set(read)
              if name in assigned and (review / name).is_file()}
    valid = {name: sha for name, sha in saved.items() if name in hashes and hashes[name] == sha}
    if read:
        from .coach_schema import validate_part
        checkpoint = review / f"coach_part{part}.json"
        if not checkpoint.is_file():
            raise ValueError(f"save {checkpoint.name} before recording sheets")
        errors = validate_part(checkpoint)
        if errors:
            raise ValueError(f"invalid checkpoint {checkpoint.name}: {'; '.join(errors)}")
        trips = json.loads(checkpoint.read_text(encoding="utf8"))
        have = {p["pid"] for p in trips}
        for name in read:
            if name not in hashes:
                raise ValueError(f"sheet not found: {name}")
            if assigned[name] not in have:
                raise ValueError(f"save pid {assigned[name]} in {checkpoint.name} before recording {name}")
            valid[name] = hashes[name]
        write_json_atomic(ledger, {"version": 1, "part_sha256": stamp, "read": valid})
    pending = [name for name in assigned if name not in valid]
    return {"part": part, "read": len(valid), "total": len(assigned), "pending": pending,
            "checkpoint": str(review / f"coach_part{part}.json"),
            "note": "Self-reported coverage; retain notes and independently verify uncertain plays."}


def errors(review: Path) -> list[str]:
    """Legacy reviews stay compatible; newly generated reviews require coverage ledgers."""
    if (review / ".sheets-incomplete").exists():
        return ["coach-sheets generation incomplete; rerun coach-sheets before reviewing"]
    policy = review / POLICY
    if not policy.exists():
        return []
    try:
        if json.loads(policy.read_text(encoding="utf8")) != {"sheet_coverage": 1}:
            return [f"{POLICY}: unsupported coverage policy"]
        out = []
        for path in sorted(review.glob("part*.json")):
            part = int(path.stem.removeprefix("part"))
            status = progress(review, part)
            if status["pending"]:
                out.append(f"part{part}: {len(status['pending'])} unread or changed sheets; "
                           f"run coach-sheets progress --review {review} --part {part}")
        return out
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"sheet coverage: {exc}"]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hoop-tape-miner coach-sheets progress")
    ap.add_argument("--review", required=True)
    ap.add_argument("--part", required=True, type=int)
    ap.add_argument("--read", nargs="+", default=[], help="exact assigned paths, only after viewing and saving JSON")
    args = ap.parse_args(argv)
    try:
        if args.part < 1:
            raise ValueError("--part must be positive")
        result = progress(Path(args.review), args.part, args.read)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ap.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=1))
