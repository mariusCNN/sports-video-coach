"""game.json helpers shared by the reporting stages: locate/load it, team display names and colours.

Source of truth for team identity is game.json:
  us.team / them.team      display names ("Us" / "Them" when missing)
  us.colour / them.colour  jersey colour words used for team clustering (build_tracks)
  us.hex / them.hex        optional chart colours (#rrggbb); neutral palette defaults when missing
Keys named `_comment` are documentation (see templates/game.example.json) and are ignored.
"""
from __future__ import annotations

from pathlib import Path

from sports_video_coach import units

SIDES = ("us", "them")
# Neutral default chart pair (validated violet / aqua on a light surface); override with us.hex / them.hex.
DEFAULT_HEX = {"us": "#6250d6", "them": "#1baf7a"}
DEFAULT_NAME = {"us": "Us", "them": "Them"}


def find_up(folder: Path | str, name: str = "game.json", levels: int = 1) -> Path | None:
    """`name` in `folder` or up to `levels` parents (a player sub-report sits one level below the game)."""
    return units.find_up(folder, name, levels)


def load_game(path: Path | str | None) -> dict:
    """Load the unit json (game.json, or a session.json / movement.json / season.json, or any plugin's json) from a
    file path or a folder; {} when not found. See sports_video_coach.units."""
    return units.load(path)


def is_training(game: dict) -> bool:
    return game.get("kind") == "training"


def is_movement(game: dict) -> bool:
    return game.get("kind") == "movement"


def is_season(game: dict) -> bool:
    return game.get("kind") == "season"


def is_personal(game: dict) -> bool:
    """A one-player page (training or movement session), not a game."""
    return is_training(game) or is_movement(game)


def team(game: dict, side: str) -> dict:
    t = game.get(side) or {}
    return t if isinstance(t, dict) else {}


def team_name(game: dict, side: str) -> str:
    return team(game, side).get("team") or DEFAULT_NAME[side]


def team_hex(game: dict, side: str, default: str | None = None) -> str:
    h = team(game, side).get("hex")
    return h if is_hex(h) else (default or DEFAULT_HEX[side])


is_hex, hex_to_rgb, hex_to_bgr, mix = units.is_hex, units.hex_to_rgb, units.hex_to_bgr, units.mix
