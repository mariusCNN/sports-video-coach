"""Where personal data lives: a gitignored workspace, never the repo's tracked files.

The workspace root is $SVC_WORKSPACE (or $HOOP_WORKSPACE, its older name) when set, else ./workspace. The profile
(languages, media_root, publish settings, a plugin's own keys) is <workspace>/profile.json, or team.json when there
is no profile.json (template: templates/team.example.json). Plugins decide the layout below the root (basketball:
teams/<opponent>/<date>/ and players/<player>/...; the generic plugin: analyses/<sport>/<date>/).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

PROFILES = ("profile.json", "team.json")


def root() -> Path:
    env = os.environ.get("SVC_WORKSPACE") or os.environ.get("HOOP_WORKSPACE")
    return Path(env).expanduser() if env else Path.cwd() / "workspace"


WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def slug(name: str) -> str:
    """Folder name safe on Windows: lowercase, every run of characters other than letters and digits -> '-'
    ("Red Foxes" -> "red-foxes", "Bulls/Bears" -> "bulls-bears"); "team" when nothing is left."""
    s = re.sub(r"[\W_]+", "-", name.lower()).strip("-") or "team"
    return f"{s}-team" if s in WINDOWS_RESERVED else s


def profile_path() -> Path | None:
    for name in PROFILES:
        p = root() / name
        if p.exists():
            return p
    return None


def profile() -> dict:
    """The workspace profile without its _comment keys; {} when missing."""
    p = profile_path()
    if p is None:
        return {}
    data = json.loads(p.read_text(encoding="utf8"))
    return {k: v for k, v in data.items() if k != "_comment"} if isinstance(data, dict) else {}
