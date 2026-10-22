"""The generic plugin: any sport or activity, no computer vision. Frame sheets -> agent review -> report -> artifacts.

It is also the template `sports-video-coach new-plugin <name>` copies: module references are built from `__name__`,
so a copy works under its own package name. Change NAME, SPORT and the prompts first, then add stages.
"""
from __future__ import annotations

from pathlib import Path

from sports_video_coach.plugin import Kind, Plugin

NAME = "generic"
SPORT = ""          # e.g. "tennis"; the generic plugin takes the sport from analysis.json

PLUGIN = Plugin(
    name=NAME,
    summary="any sport or activity video, no tracking: contact sheets -> agent film review -> coaching report",
    use_when="no plugin for this sport is installed, or a quick first look at any game or training video",
    stages={
        "new": (f"{__name__}.new", "start an analysis from one or more videos: analysis.json + joined video.mp4"),
        "review-check": (f"{__name__}.unit", "check run/review/review.json against the review brief"),
    },
    kinds=[Kind("analysis", "analysis.json", f"{__name__}.unit:Analysis", f"{__name__}.unit:STEPS",
                match=lambda d: d.get("plugin", NAME) == NAME)],
    prompts=Path(__file__).parent / "prompts",
)
