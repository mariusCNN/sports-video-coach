"""Basketball workspace layout (the root, slug and profile come from sports_video_coach.workspace).

Layout: <workspace>/teams/<opponent-slug>/<date>/  game.json, official.json, README*.md, figures, run/
Team profile: <workspace>/team.json (template templates/team.example.json), read by `profile()`.
Heavy files (videos, run/, raw league data) go to `media_dir()`: <media_root>/teams/<slug>/<date> when the profile
sets media_root, else the game folder itself.
"""
from __future__ import annotations

import re
from pathlib import Path

from sports_video_coach.workspace import WINDOWS_RESERVED, profile, root, slug  # noqa: F401


def _legacy_slug(name: str) -> str:
    """The slug older versions used (only whitespace replaced); existing folders keep that name."""
    return re.sub(r"\s+", "-", name.strip().lower())


def _slug_dir(parent: Path, name: str) -> Path:
    """parent/slug(name), or an existing parent/<legacy slug> folder made by an older version."""
    old = parent / _legacy_slug(name)
    return old if old.name != slug(name) and old.is_dir() else parent / slug(name)


def team_dir(opponent: str) -> Path:
    return _slug_dir(root() / "teams", opponent)


def game_dir(opponent: str, date: str) -> Path:
    return team_dir(opponent) / date


def media_dir(opponent: str, date: str, prof: dict | None = None) -> Path:
    media_root = (profile() if prof is None else prof).get("media_root")
    if media_root:
        return _slug_dir(Path(media_root).expanduser() / "teams", opponent) / date
    return game_dir(opponent, date)
