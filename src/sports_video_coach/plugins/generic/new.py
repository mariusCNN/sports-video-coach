"""Start an analysis: <workspace>/analysis/<name>/<date>/ with analysis.json, from one or more videos.

usage: sports-video-coach generic:new <video> [<video> ...] [--sport tennis] [--focus "player in red"]
           [--name my-serve] [--date 2025-03-16] [--lang en ja] [--sport-name ja=サーブ] [--every 1] [--out <folder>]
           [--artifacts html film]

One video is used where it is (analysis.json `video` points to it); several are joined in order into the
folder's video.mp4 (their offsets kept in `sources`). Prints the folder; `sports-video-coach run <folder>` goes on.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from sports_video_coach import artifacts, langs, media, pipeline, workspace
from sports_video_coach.render_html import sport_names

from . import NAME, SPORT


def langs_default() -> list[str]:
    return list(workspace.profile().get("languages") or ["en"])


def auto_every(duration_s: float) -> float:
    """Seconds between contact-sheet tiles for a video this long: denser for short clips, so a 1-2 s moment in a
    drill gets several tiles, while a long game stays at a few dozen sheets."""
    return 0.5 if duration_s <= 30 else 1.0 if duration_s <= 180 else 2.0


def unit_date(given: str | None, tagged: str | None) -> tuple[str, str]:
    """(date, the rest of the line naming where it came from): --date, else the video's creation_time tag, else
    today. An unset tag (before 1990, or after tomorrow: the tag is UTC) does not count."""
    today = dt.date.today()
    if given:
        return given, " from --date"
    if tagged and "1990-01-01" <= tagged <= (today + dt.timedelta(days=1)).isoformat():
        return tagged, (" from the video's creation_time tag (a downloaded or re-encoded copy carries the date it was "
                        "encoded; --date YYYY-MM-DD sets it)")
    if tagged:
        return today.isoformat(), (f": today, the video's creation_time tag {tagged} looks unset (--date YYYY-MM-DD "
                                   "sets it)")
    return today.isoformat(), ": today, the video has no recording date (--date YYYY-MM-DD sets it)"


def folder_inputs(folder: Path) -> list[str] | None:
    """The video paths the analysis in `folder` was started from; None when there is none yet."""
    p = folder / "analysis.json"
    if not p.exists():
        return None
    old = json.loads(p.read_text(encoding="utf8"))
    return [s["file"] for s in old["sources"]] if old.get("sources") else [old.get("video")]


def sport_name(value: str) -> tuple[str, str]:
    """One --sport-name LANG=NAME: (lang, name), the language checked against the registry."""
    code, eq, text = value.partition("=")
    if not eq or not text.strip() or code.strip() not in langs.LANGS:
        raise argparse.ArgumentTypeError(f"{value!r}: give LANG=NAME with LANG one of {', '.join(langs.CODES)}")
    return code.strip(), text.strip()


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=f"sports-video-coach {NAME}:new", description=__doc__.split("\n\n")[0])
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--sport", default=SPORT, help="what the video shows (tennis, swimming, ...)")
    ap.add_argument("--sport-name", action="append", type=sport_name, metavar="LANG=NAME",
                    help="the sport's name on that language's page, e.g. ja=シャトルラン or zh=折返跑; repeat it per "
                    "language (most sports have zh and ja names built in: tennis shows as 网球 / テニス)")
    ap.add_argument("--sport-zh", metavar="NAME", help="the same as --sport-name zh=NAME")
    ap.add_argument("--focus", default="", help="who to coach, e.g. 'the player in red' or a jersey number; "
                    "several players in one report: --focus 'A in red, B in yellow' (one section each, in this order)")
    ap.add_argument("--name", help="folder name (default: sport or the first video's name)")
    ap.add_argument("--date", help="YYYY-MM-DD (default: the first video's recording date, else today)")
    ap.add_argument("--lang", nargs="+", choices=langs.CODES, help="report languages (default: profile, else en)")
    ap.add_argument("--artifacts", nargs="+", choices=artifacts.NAMES, help="deliverables to build (default: "
                    "profile, else all); " + artifacts.IMPLIED_HELP)
    ap.add_argument("--every", type=float, help="seconds between contact-sheet tiles (default: 0.5 up to 30 s "
                    "of video, 1 up to 3 min, else 2)")
    ap.add_argument("--out", help="the analysis folder (default: <workspace>/analysis/<name>/<date>)")
    return ap


def main(argv=None) -> Path:
    a = parser().parse_args(argv)
    if a.artifacts:
        artifacts.check(a.artifacts)  # publish without html: stop before any video work
    videos = [Path(v).resolve() for v in a.videos]
    missing = [str(v) for v in videos if not v.is_file()]
    if missing:
        raise SystemExit(f"video not found: {', '.join(missing)}")
    info = media.video_info(videos[0])
    date, came = unit_date(a.date, info.get("date"))
    name = workspace.slug(a.name or a.sport or videos[0].stem)
    folder = Path(a.out) if a.out else workspace.root() / "analysis" / name / date
    base, n = folder, 1
    while not a.out and folder_inputs(folder) not in (None, [str(v) for v in videos]):
        n += 1  # another video of the same sport on the same day: its own folder, not the first one's
        folder = base.with_name(f"{base.name}-{n}")
    folder.mkdir(parents=True, exist_ok=True)
    names = dict(([("zh", a.sport_zh)] if a.sport_zh else []) + (a.sport_name or []))
    sport = {**names, "en": names.get("en") or a.sport} if names else a.sport
    data = dict(plugin=NAME, kind="analysis", sport=sport, focus=a.focus, date=date,
                languages=a.lang or langs_default(), every_s=a.every or auto_every(info["duration"]))
    if a.artifacts:
        data["artifacts"] = list(a.artifacts)
    if len(videos) == 1:
        data["video"] = str(videos[0])
    else:
        out = folder / "video.mp4"
        data["sources"] = media.join(videos, out, label="new")
        print(f"[new] joined {len(videos)} videos into {out.name}: {media.parts_line(data['sources'])} (every time "
              "from here on, in the sheets, the review and the report, is on this joined timeline)")
        data["video"] = "video.mp4"
    p = folder / "analysis.json"
    if p.exists():
        old = json.loads(p.read_text(encoding="utf8"))
        if a.every is None and "every_s" in old:  # keep the sheets already cut
            del data["every_s"]
        data = {**old, **{k: v for k, v in data.items() if v not in ("", None)}}
    media.write_text_atomic(p, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    sport = data.get("sport")
    if "zh" in data["languages"] and isinstance(sport, str) and not sport_names(sport, ("zh", "en")).get("zh"):
        print(f"[new] sport {sport!r} has no Chinese name for the zh page: start again with --sport-name, e.g. "
              f'`--sport "{sport.replace("-", " ")}" --sport-name zh=折返跑`, or set "sport": {{"zh": "折返跑", "en": '
              f'"{sport.replace("-", " ")}"}} in analysis.json')
    if "ja" in data["languages"] and isinstance(sport, str) and not sport_names(sport, ("ja", "en")).get("ja"):
        print(f"[new] sport {sport!r} has no Japanese name for the ja page: start again with --sport-name, e.g. "
              f'`--sport "{sport.replace("-", " ")}" --sport-name ja=シャトルラン`, or set "sport": {{"ja": '
              f'"<name>", "en": "{sport.replace("-", " ")}"}} in analysis.json')
    print(f"[new] date {date}{came}")
    print(pipeline.slash(folder))
    return folder


if __name__ == "__main__":
    main()
