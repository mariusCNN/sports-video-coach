"""Basketball's film hooks: `court:` scenes (animated court diagrams), 我#7 / 对#11 freeze marks found in the CV
tracks, the '<us> vs <them>' title card and the team colours from game.json. Registered on PLUGIN as scenes / film.

Cheap to import (the plugin listing loads it): matplotlib and pandas load only when a diagram or the tracks are used.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sports_video_coach.film import FilmHooks, SceneKind, title_lines, folder_date

from . import film_court as fc
from . import game_config as gc


def title_text(folder: Path, game: dict, h: int) -> str:
    """'<us> vs <them>' plus date and final score (game.json result only) on a smaller second line.
    Training and movement sessions: `title` (else '<name> · training' / '<name> · movement') plus the date."""
    if gc.is_personal(game):
        kind = "movement" if gc.is_movement(game) else "training"
        head = game.get("title") or f"{game.get('name') or '#' + str(game.get('player', ''))} · {kind}"
        return title_lines(head, str(game.get("date") or folder.name), h)
    head = f"{gc.team_name(game, 'us')} vs {gc.team_name(game, 'them')}"
    pm = re.fullmatch(r"player-(\w+)", folder.name)
    if pm:
        head = f"#{pm[1]} · {head}"
    res = game.get("result") or {}
    score = f"{res['us']}–{res['them']}" if isinstance(res.get("us"), int) and isinstance(res.get("them"), int) else ""
    return title_lines(head, " · ".join(x for x in (folder_date(folder), score) if x), h)


def colours(game: dict) -> tuple[str, str]:
    """Our team colour (accent) and theirs (court diagrams draw their players in it)."""
    return gc.team_hex(game, "us"), gc.team_hex(game, "them", "#e0e0e0")


def find_run(run: Path | None, folder: Path, video: Path | None) -> Path | None:
    """The CV run with tracks.pkl: --run, else run/ next to the report or the video."""
    if run:
        if not (run / "tracks.pkl").is_file():
            sys.exit(f"{run}: no tracks.pkl (the CV run folder)")
        return run
    near = [folder / "run"] + ([video.parent / "run", video.parent.parent / "run"] if video else [])
    return next((d for d in near if (d / "tracks.pkl").is_file()), None)


def tracks(run: Path | None, folder: Path, video: Path | None, src_w: int, src_h: int):
    """The player boxes for 我#7 / 对#11 marks, or None when no CV run is found."""
    d = find_run(run, folder, video)
    return fc.Tracks.load(d, src_w, src_h) if d else None


def render_court(play: dict, ctx, starts: list[float], length: float, out_dir: Path) -> Path:
    return fc.render_court(play, ctx.w, ctx.h, starts, length, out_dir, ctx.accent, ctx.second, ctx.fps)


COURT = SceneKind("court", "court diagram", parse=fc.load_play, render=render_court, problems=fc.play_problems,
                  steps=lambda play: len(play["steps"]), anim=fc.ANIM)
SCENES = {COURT.prefix: COURT}
FILM = FilmHooks(title=title_text, colours=colours, parse_ref=fc.parse_ref, tracks=tracks,
                 mark_help='我#7, 对#11, 0.4,0.6, A->B, "label"')
