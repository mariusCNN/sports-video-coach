"""The fitness plugin object (entry point `fitness = "svc_fitness.plugin:PLUGIN"`)."""
from __future__ import annotations

from pathlib import Path

from sports_video_coach.plugin import Kind, Plugin
from sports_video_coach.render_html import PageHooks

from . import NAME, page

PKG = __name__.rsplit(".", 1)[0]

PLUGIN = Plugin(
    name=NAME,
    summary="strength & conditioning / gym sessions: sets and exercises named from a 50-exercise library, per-rep "
            "depth, trunk lean, tempo, bar path and slowing from pose (side view), muscle map, coaching for a sport",
    use_when="gym or S&C training videos (squats, pulls, single-leg, plyometrics, microdosing), a phone on a tripod; "
             "basketball game film goes to `basketball`, technique drills on court to `basketball` train / move",
    stages={
        "new": (f"{PKG}.new", "start a session from one or more videos: analysis.json with plugin fitness"),
        "library": (f"{PKG}.library", "list the exercise library, print exercise cards, --check it"),
        "sets-check": (f"{PKG}.unit", "check run/review/sets.json (the sets and their exercises)"),
        "pose": (f"{PKG}.pose", "YOLO pose of the lifter in each side/front-view set: run/pose/<id>.npz"),
        "reps": (f"{PKG}.reps", "per-rep metrics from the pose: run/reps/reps.json"),
        "review-check": ("sports_video_coach.plugins.generic.unit", "check run/review/review.json (merges part*.json)"),
    },
    kinds=[Kind("analysis", "analysis.json", f"{PKG}.unit:Session", f"{PKG}.unit:STEPS",
                match=lambda d: d.get("plugin") == NAME)],
    prompts=Path(__file__).parent / "prompts",
    page=PageHooks(before=page.box, inputs=page.inputs),
)
