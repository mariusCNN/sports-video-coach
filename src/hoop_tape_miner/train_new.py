"""Start a personal training session: session folder, session.json and one joined session video.

usage: hoop-tape-miner train-new <phone video> [<phone video> ...] [--player 7] [--date 2025-03-12]
           [--name "Alex"] [--plan "free throws, left-hand layups"] [--height 1080]

The phone files are joined in the given order into `session.mp4` (rotation applied, 30 fps, H.264, long side
--height px) in the media folder; their start offsets in the joined video are kept in session.json `sources`, so
every time in the report can be traced back to a phone file. Targets from the previous session's plan.json are
copied into `targets`, and the next train-summary checks them. The latest game before the session (the player's
jersey on our box score) seeds `game_focus`: that game's insights for the jersey, then the team's, with drill and
next-game target (game_link.focus). Prints the session folder.
--player defaults to team.json focus_player; --date to the first file's recording date (else its file date).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from sports_video_coach import media

from . import game_link
from . import training as T
from . import workspace

LONG_SIDE = 1080


probe, target_size = media.video_info, media.target_size


def join(videos: list[Path], out: Path, long_side: int = LONG_SIDE) -> list[dict]:
    """Normalise every file to the first file's orientation and size, then concatenate; returns sources."""
    return media.join(videos, out, long_side, label="train-new")


def previous_targets(folder: Path) -> tuple[list[dict], str | None]:
    """Targets of the latest earlier session's plan.json (drills[].target), and that session's name."""
    for prev in reversed(T.earlier_sessions(folder)):
        p = prev / "plan.json"
        if p.exists():
            plan = json.loads(p.read_text(encoding="utf8"))
            return [d["target"] for d in plan.get("drills", []) if d.get("target")], prev.name
    return [], None


def create(videos: list[Path], player: str, date: str | None = None, name: str | None = None, plan: str = "",
           long_side: int = LONG_SIDE, joiner=join) -> Path:
    for v in videos:
        if not v.is_file():
            sys.exit(f"video not found: {v}")
    date = date or probe(videos[0])["date"] or dt.date.fromtimestamp(videos[0].stat().st_mtime).isoformat()
    sname = T.session_name(player, date)
    folder = T.sessions_root(player) / sname
    media = T.media_root_for(player) / sname
    folder.mkdir(parents=True, exist_ok=True)
    video = media / "session.mp4"
    sources = joiner(videos, video, long_side)
    targets, from_session = previous_targets(folder)
    prof = workspace.profile()
    jersey = game_link.jersey_for({"player": player}, prof)
    root = game_link.workspace_of(folder)
    focus = game_link.focus(root, jersey, date) if jersey and root else None
    s = dict(kind="training", player=str(player), name=name or "", date=date, title="",
             sources=sources, video=str(video.resolve()), run=str((media / "run").resolve()),
             hex=prof.get("hex") or "", plan=plan, targets=targets, targets_from=from_session,
             rim=[], rim_checked=False, jersey=jersey, game_focus=focus)
    (folder / "session.json").write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(f"[train-new] session {folder}")
    print(f"[train-new] video {video} ({sum(x['duration'] for x in sources) / 60:.1f} min)")
    if targets:
        print(f"[train-new] {len(targets)} targets from {from_session}")
    if focus:
        print(f"[train-new] game focus: {len(focus['insights'])} insights from {focus['game']}")
    return folder


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hoop-tape-miner train-new", description=__doc__.split("\n\n")[0])
    ap.add_argument("videos", nargs="+", help="phone video files of one workout, in recording order")
    ap.add_argument("--player", help="player number or slug (default: team.json focus_player)")
    ap.add_argument("--date", help="session date YYYY-MM-DD (default: recording date of the first file)")
    ap.add_argument("--name", help="player display name for the pages")
    ap.add_argument("--plan", default="", help="what you meant to train, in your own words")
    ap.add_argument("--height", type=int, default=LONG_SIDE, help=f"long side of session.mp4 in px (default {LONG_SIDE})")
    a = ap.parse_args(argv)
    player = a.player or workspace.profile().get("focus_player")
    if not player:
        ap.error("--player is required when team.json has no focus_player")
    return create([Path(v) for v in a.videos], str(player), a.date, a.name, a.plan, a.height)


if __name__ == "__main__":
    main()
