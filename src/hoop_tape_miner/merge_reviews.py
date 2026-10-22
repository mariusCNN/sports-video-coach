"""Merge independently reviewed parts only after their sheet coverage is complete.

usage: hoop-tape-miner merge-reviews --run <run dir> [--review review]
Reads <run>/<review>/manifest.json, events_part*.json and coverage_part*.json; writes <run>/events.json
and <run>/review_coverage.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .events import event_summary, reviewed_events


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hoop-tape-miner merge-reviews")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--review", default="review")
    args = ap.parse_args(argv)
    source = args.run / args.review
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf8"))
    expected = {p["pid"]: p for p in manifest}
    rows, coverage = [], []
    for events_file in sorted(source.glob("events_part*.json")):
        suffix = events_file.stem.removeprefix("events_")
        rows.extend(json.loads(events_file.read_text(encoding="utf8")))
        coverage.extend(json.loads((source / f"coverage_{suffix}.json").read_text(encoding="utf8")))
    ids = [c["pid"] for c in coverage]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError(f"Incomplete or duplicate segment coverage: expected {len(expected)}, got {len(ids)}")
    for c in coverage:
        actual = [Path(s).name for s in c["reviewed_sheets"]]
        required = [Path(s).name for s in expected[c["pid"]]["sheets"]]
        if len(actual) != len(set(actual)) or set(actual) != set(required):
            raise ValueError(f"Incomplete or duplicate sheet coverage for segment {c['pid']}")
    events = reviewed_events(rows)
    for e in events.to_dict("records"):
        if e["pid"] not in expected:
            raise ValueError(f"Unknown event segment {e['pid']}")
        p = expected[e["pid"]]
        if not p["start"] - 0.5 <= e["t"] <= p["end"] + 2.5:
            raise ValueError(f"Event at {e['t']} is outside segment {e['pid']} and its padding")
    # Keep the review's nulls intact rather than serialising pandas NaN values.
    rows.sort(key=lambda e: (e["t"], e["pid"]))
    coverage.sort(key=lambda c: c["pid"])
    (args.run / "events.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")
    (args.run / "review_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(event_summary(events), indent=2))
    print(f"Complete coverage: {len(coverage)} segments, {sum(len(c['reviewed_sheets']) for c in coverage)} sheets")


if __name__ == "__main__":
    main()
