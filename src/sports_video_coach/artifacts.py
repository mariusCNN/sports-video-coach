"""Which deliverables a unit builds: clips, narration, html (the page), qa, publish (links), film (explained video).

The choice comes from the unit json `"artifacts": [...]`, else the profile's `"artifacts"`, else every one. A step
belongs to an artifact through `Step.artifact`; the driver skips steps of artifacts not chosen. A plugin may add its
own artifact names (`Plugin.artifacts`: name -> help) and tag its steps with them.

Rules: `qa` is kept whenever `html` is (a page is never shipped unchecked), `clips` whenever `html` or `film` is
(both show the clips) and `publish` needs `html`.
"""
from __future__ import annotations

import sys

NAMES = ("clips", "narration", "html", "qa", "publish", "film")
HELP = {
    "clips": "short video clips cut at the moments the report marks",
    "narration": "listen.<lang>.mp3: the report read aloud",
    "html": "index.html: the bilingual coaching page with clips and audio",
    "qa": "a checked page (qa.md PASS) before anything is shared",
    "publish": "private links to the pages (Cloudflare Workers)",
    "film": "film.<lang>.mp4: an explained video, narration over the clips",
}
IMPLIED = {"html": ("qa", "clips"), "film": ("clips",)}  # chosen -> also built: the page is checked, both show clips


def known(unit=None) -> tuple[str, ...]:
    """Core artifact names plus the extra ones of the unit's plugin."""
    extra = ()
    name = getattr(unit, "PLUGIN", None)
    if name:
        from . import plugin
        found = plugin.plugins().get(name)
        extra = tuple(k for k in (found.artifacts if found else {}) if k not in NAMES)
    return NAMES + extra


def check(names, allowed=NAMES) -> tuple[str, ...]:
    """The chosen names in canonical order, plus the ones they imply (IMPLIED); exits on unknown names or publish
    without html."""
    names = list(names)
    bad = [n for n in names if n not in allowed]
    if bad:
        sys.exit(f"unknown artifact(s) {', '.join(map(repr, bad))}; choose from: {', '.join(allowed)}")
    if "publish" in names and "html" not in names:
        sys.exit("artifact 'publish' needs 'html' (publish deploys the page)")
    names += [m for n in list(names) for m in IMPLIED.get(n, ()) if m not in names]
    return tuple(n for n in allowed if n in names)


def selected(unit) -> tuple[str, ...]:
    """The artifacts this unit builds (unit json, else profile, else all)."""
    allowed = known(unit)
    names = (getattr(unit, "game", None) or {}).get("artifacts")
    if names is None:
        from . import workspace
        names = workspace.profile().get("artifacts")
    return allowed if names is None else check(names, allowed)


def keep(steps: list, unit) -> list:
    """The steps the unit runs: untagged ones always, tagged ones when their artifact is chosen."""
    chosen = set(selected(unit))
    return [s for s in steps if s.artifact is None or s.artifact in chosen]
