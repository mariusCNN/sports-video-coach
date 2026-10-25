"""The jump-rope plugin, a worked example: `new-plugin jump-rope` plus one measuring stage.

Video -> skip (cmd: run/skip/skip.json) -> frame sheets -> agent review -> report -> artifacts, with the
measured skip count on the page. See README.md for which file does what.
"""
from __future__ import annotations

from pathlib import Path

from sports_video_coach.plugin import Kind, Plugin
from sports_video_coach.render_html import PageHooks

from .page import skip_box, skip_file

NAME = "jump-rope"
SPORT = "jump rope"          # e.g. "tennis"; the generic plugin takes the sport from analysis.json

PLUGIN = Plugin(
    name=NAME,
    summary="Jump rope: counts skips from a still side-view video, then coaches rhythm and form",
    use_when="a jump rope / skipping session filmed from a still camera",
    stages={
        "new": (f"{__name__}.new", "start an analysis from one or more videos: analysis.json naming the video where "
                                  "it is (several: joined into the folder's video.mp4)"),
        "skip": (f"{__name__}.skip", "count jump-rope skips from a still side view: run/skip/skip.json"),
        "review-check": (f"{__name__}.unit", "check run/review/review.json against the review brief"),
    },
    kinds=[Kind("analysis", "analysis.json", f"{__name__}.unit:Analysis", f"{__name__}.unit:STEPS",
                match=lambda d: d.get("plugin", NAME) == NAME)],
    prompts=Path(__file__).parent / "prompts",
    page=PageHooks(before=skip_box, inputs=lambda folder: [skip_file(folder)]),
)
