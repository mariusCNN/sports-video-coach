"""Start an analysis: <workspace>/analysis/<name>/<date>/ with analysis.json, from one or more videos.

usage: sports-video-coach generic:new <video> [<video> ...] [--sport tennis] [--focus "player in red"]
           [--name my-serve] [--date 2025-03-16] [--lang en zh] [--every 2] [--out <folder>]

One video is used where it is (analysis.json `video` points to it); several are joined in order into the
folder's video.mp4 (their offsets kept in `sources`). Prints the folder; `sports-video-coach run <folder>` goes on.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from sports_video_coach import media, pipeline, workspace

from . import NAME, SPORT


def langs_default() -> list[str]:
    return list(workspace.profile().get("languages") or ["en"])


def main(argv=None) -> Path:
    ap = argparse.ArgumentParser(prog=f"sports-video-coach {NAME}:new", description=__doc__.split("\n\n")[0])
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--sport", default=SPORT, help="what the video shows (tennis, swimming, ...)")
    ap.add_argument("--focus", default="", help="who to coach, e.g. 'the player in red' or a jersey number")
    ap.add_argument("--name", help="folder name (default: sport or the first video's name)")
    ap.add_argument("--date", help="YYYY-MM-DD (default: the first video's recording date, else today)")
    ap.add_argument("--lang", nargs="+", choices=pipeline.LANGS, help="report languages (default: profile, else en)")
    ap.add_argument("--every", type=float, default=2.0, help="seconds between contact-sheet tiles (default 2)")
    ap.add_argument("--out", help="the analysis folder (default: <workspace>/analysis/<name>/<date>)")
    a = ap.parse_args(argv)
    videos = [Path(v).resolve() for v in a.videos]
    missing = [str(v) for v in videos if not v.is_file()]
    if missing:
        raise SystemExit(f"video not found: {', '.join(missing)}")
    info = media.video_info(videos[0])
    date = a.date or info.get("date") or dt.date.today().isoformat()
    name = workspace.slug(a.name or a.sport or videos[0].stem)
    folder = Path(a.out) if a.out else workspace.root() / "analysis" / name / date
    folder.mkdir(parents=True, exist_ok=True)
    data = dict(plugin=NAME, kind="analysis", sport=a.sport, focus=a.focus, date=date,
                languages=a.lang or langs_default(), every_s=a.every)
    if len(videos) == 1:
        data["video"] = str(videos[0])
    else:
        out = folder / "video.mp4"
        data["sources"] = media.join(videos, out, label="new")
        data["video"] = "video.mp4"
    p = folder / "analysis.json"
    if p.exists():
        old = json.loads(p.read_text(encoding="utf8"))
        data = {**old, **{k: v for k, v in data.items() if v not in ("", None)}}
    media.write_text_atomic(p, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(folder)
    return folder


if __name__ == "__main__":
    main()
