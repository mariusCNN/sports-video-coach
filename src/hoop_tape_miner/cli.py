"""`hoop-tape-miner <stage> ...`: `sports-video-coach` with the basketball plugin as the default.

Every stage name that worked before still works; core stages (clips, narrate, html, film, publish, ...) and other
plugins' stages are reachable too. See sports_video_coach.cli.
"""
from __future__ import annotations

from sports_video_coach import cli as core

from .plugin import STAGES as _OWN

STAGES = {**_OWN, **{k: v for k, v in core.CORE.items() if k not in _OWN}}  # every stage this script knows


def main(argv=None):
    return core.main(argv, prog="hoop-tape-miner", default="basketball")


if __name__ == "__main__":
    main()
