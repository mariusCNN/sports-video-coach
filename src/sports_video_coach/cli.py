"""`sports-video-coach <stage> ...`: thin dispatcher over the core stages and every plugin's stages.

A stage name resolves in this order: `<plugin>:<stage>`; the default plugin's stage (the `hoop-tape-miner` script
defaults to basketball); a core stage; a stage name that exactly one plugin has. Two plugins with the same stage
name need the qualified form. Stage modules are imported lazily, so listing stages never loads torch.
"""
from __future__ import annotations

import importlib
import json
import sys

from . import plugin

CORE = {
    "plugins": ("sports_video_coach.cli", "list the installed plugins (what each analyses, when to use it, its stages)"),
    "run": ("sports_video_coach.run", "drive one unit end to end: a unit folder, a target a plugin claims, or new videos"),
    "demo": ("sports_video_coach.demo", "every deliverable in about a minute: a drawn video, a pre-written review, no agent"),
    "guide": ("sports_video_coach.guide", "print a plugin's writing guide (review, report, narration, film) or list them"),
    "frames": ("sports_video_coach.frames", "contact sheets of a video (one tile every N seconds) for an agent to review"),
    "new-plugin": ("sports_video_coach.scaffold", "write a new plugin folder from the generic template"),
    "clips": ("sports_video_coach.clips", "cut the video clips a report marks with ![caption](clip:mm:ss-mm:ss)"),
    "narrate": ("sports_video_coach.narrate", "listen.<lang>.md -> listen.<lang>.mp3 (edge-tts + ffmpeg)"),
    "html": ("sports_video_coach.render_html", "report folder (README.md + README.en.md) -> one bilingual index.html"),
    "page-check": ("sports_video_coach.page_check", "static check of a report page: links, anchors, media, no local paths"),
    "film": ("sports_video_coach.film", "film.<lang>.md -> explained video: narration over clips and charts, subtitled"),
    "publish": ("sports_video_coach.publish", "reports -> private-link website (Cloudflare Workers), one stable link per report"),
}


def resolve(stage: str, default: str | None = None) -> tuple[str, str]:
    """(module, label) for a stage name; exits with a message when it is unknown or ambiguous."""
    if ":" in stage:
        name, _, st = stage.partition(":")
        p = plugin.get(name)
        if st not in p.stages:
            sys.exit(f"plugin {name!r} has no stage {st!r}; its stages: {', '.join(p.stages)}")
        return p.stages[st][0], f"{name}:{st}"
    found = plugin.plugins()
    if default and default in found and stage in found[default].stages:
        return found[default].stages[stage][0], stage
    if stage in CORE:
        return CORE[stage][0], stage
    hits = [p for p in found.values() if stage in p.stages]
    if len(hits) == 1:
        return hits[0].stages[stage][0], stage
    if hits:
        sys.exit(f"stage {stage!r} is in several plugins; use one of: {', '.join(f'{p.name}:{stage}' for p in hits)}")
    return "", ""


def usage(prog: str = "sports-video-coach", default: str | None = None) -> str:
    rows = list(CORE.items())
    found = plugin.plugins()
    if default and default in found:
        rows = list(found[default].stages.items()) + [r for r in rows if r[0] not in found[default].stages]
    w = max(len(k) for k, _ in rows)
    lines = [f"usage: {prog} <stage> [args]   ({prog} <stage> -h for a stage's options)", ""]
    lines += [f"  {k:{w}s}  {d}" for k, (_, d) in rows]
    if not default:
        lines += ["", "plugin stages (`<plugin>:<stage>`; unique names also work bare):"]
        for p in found.values():
            lines.append(f"  {p.name}: {', '.join(p.stages) or '-'}")
    return "\n".join(lines)


def list_plugins(argv=None) -> None:
    """The `plugins` stage: what each plugin analyses and when to use it (--json for agents)."""
    as_json = "--json" in (argv or [])
    found, errs = plugin.plugins(), plugin.errors()
    if as_json:
        print(json.dumps({"plugins": [dict(name=p.name, summary=p.summary, use_when=p.use_when,
                                           kinds=[dict(name=k.name, json=k.json) for k in p.kinds],
                                           stages=list(p.stages), prompts=str(p.prompts) if p.prompts else None,
                                           missing=plugin.missing(p), install=p.install)
                                      for p in found.values()], "errors": errs}, indent=1))
        return
    for p in found.values():
        print(f"{p.name}: {p.summary}")
        if p.use_when:
            print(f"  use when: {p.use_when}")
        if gone := plugin.missing(p):
            print(f"  not usable in this install: needs {', '.join(gone)}" + (f" ({p.install})" if p.install else ""))
        print(f"  units: {', '.join(f'{k.name} ({k.json})' for k in p.kinds) or '-'}")
        print(f"  stages: {', '.join(p.stages) or '-'}")
    for where, e in errs.items():
        print(f"broken plugin ({where}): {e}")


def main(argv=None, prog: str = "sports-video-coach", default: str | None = None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(usage(prog, default))
        sys.exit(0 if argv else 1)
    if argv[0] == "plugins":
        return list_plugins(argv[1:])
    name, label = resolve(argv[0], default)
    if not name:
        print(f"unknown stage {argv[0]!r}\n\n{usage(prog, default)}")
        sys.exit(1)
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name != name:
            raise
        sys.exit(f"stage {argv[0]!r} is not available in this checkout ({name} is missing)")
    sys.argv[0] = f"{prog} {label}"  # argparse prog for stages that do not set one
    try:
        return mod.main(argv[1:])
    except ModuleNotFoundError as e:  # a plugin's heavy dependency in a light install: say what to do, no traceback
        if not e.name or e.name.split(".")[0] == __package__:
            raise
        sys.exit(f"{prog} {label}: the Python package {e.name!r} is not installed. `sports-video-coach plugins` "
                 f"shows which plugins this install can run and how to add the rest.")


if __name__ == "__main__":
    main()
