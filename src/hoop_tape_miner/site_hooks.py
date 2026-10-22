"""Basketball's published site (sports_video_coach.publish.SiteHooks): the team hub of game reports.

Player pages (player-<N>) and personal training / movement sessions get their own link but are never on the team
hub; season pages (`hoop-tape-miner season`, a folder with season.json) are pinned above the games; a training
program (`hoop-tape-miner program`, a folder with program.json) is the app page at /p/<token>/.
Imported by the plugin at listing time, so it stays cheap: `program` is imported only to build a page.
"""
from __future__ import annotations

import re
from pathlib import Path

from sports_video_coach.publish import SiteHooks


def hidden(folder: Path) -> bool:
    return bool(re.fullmatch(r"player-\w+", folder.name)
                or (folder / "session.json").exists() or (folder / "movement.json").exists())


def group(folder: Path) -> str | None:
    return "season" if (folder / "season.json").exists() else None


def is_app(folder: Path) -> bool:
    return (folder / "program.json").exists()


def app_page(folder: Path) -> str:
    from . import program
    return program.page(folder)


SITE = SiteHooks(
    hidden=hidden,
    group=group,
    groups=("season",),
    ui={"zh": {"title": "比赛复盘", "season": "赛季"}, "en": {"title": "Game reports", "season": "Season"}},
    is_app=is_app,
    app_page=app_page,
)
