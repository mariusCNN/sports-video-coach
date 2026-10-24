"""The swim-stroke-rate plugin, a worked example: `new-plugin swim-stroke-rate` plus one measuring stage.

Video -> stroke (cmd: run/stroke/stroke.json) -> frame sheets -> agent review -> report -> artifacts, with the
measured rate on the page. See README.md for which file does what.
"""
from __future__ import annotations

from pathlib import Path

from sports_video_coach.plugin import Kind, Plugin
from sports_video_coach.render_html import PageHooks

from .page import stroke_box, stroke_file

NAME = "swim-stroke-rate"
SPORT = "swimming"          # e.g. "tennis"; the generic plugin takes the sport from analysis.json

PLUGIN = Plugin(
    name=NAME,
    summary="Swimming stroke rate (cycles per minute) measured from a side-view video, plus the generic film review, report, page and film",
    use_when="a swimming video filmed from the side with a still camera, when the stroke rate matters; worked example for plugin authors",
    stages={
        "new": (f"{__name__}.new", "start an analysis from one or more videos: analysis.json naming the video where "
                                  "it is (several: joined into the folder's video.mp4)"),
        "stroke": (f"{__name__}.stroke", "measure stroke rate (cycles/min): run/stroke/stroke.json"),
        "synth": (f"{__name__}.synth", "draw a test video of a swimmer at a known stroke rate (--spm)"),
        "review-check": (f"{__name__}.unit", "check run/review/review.json against the review brief"),
    },
    kinds=[Kind("analysis", "analysis.json", f"{__name__}.unit:Analysis", f"{__name__}.unit:STEPS",
                match=lambda d: d.get("plugin", NAME) == NAME)],
    prompts=Path(__file__).parent / "prompts",
    page=PageHooks(before=stroke_box, inputs=lambda folder: [stroke_file(folder)]),  # re-render when it changes
)
