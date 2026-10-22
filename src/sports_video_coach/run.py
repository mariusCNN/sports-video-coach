"""`sports-video-coach run <target>`: drive one unit end to end, whatever plugin owns it.

The target is one of:
  - a unit folder (or its json): the owning plugin's driver stage runs it (`Kind.driver`), else the core walks the
    kind's step table with pipeline.drive;
  - a target a plugin claims (e.g. a league game url): that plugin's `run` stage takes it;
  - one or more video files: the plugin's `new` stage (default: the generic plugin) starts a unit from them and the
    driver goes on with the folder it made.
Exit codes as every driver: 0 done, 3 an agent step is waiting (do it, run again), 1 a command failed.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from . import pipeline, plugin

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}


def stage_main(p: plugin.Plugin, stage: str):
    if stage not in p.stages:
        sys.exit(f"plugin {p.name!r} has no stage {stage!r}; its stages: {', '.join(p.stages) or '-'}")
    return importlib.import_module(p.stages[stage][0]).main


def drive_unit(folder: Path, rest: list[str]) -> int:
    """Run the unit at `folder` with its plugin's driver, or the core step walker."""
    own = plugin.owner(folder)
    if own is None:
        sys.exit(f"{folder}: no unit json a plugin knows (installed: {', '.join(plugin.plugins())}); "
                 "start one with `sports-video-coach run <video files>`")
    p, kind, _ = own
    if kind.driver:
        return stage_main(p, kind.driver)([str(folder), *rest]) or 0
    if not kind.steps:
        sys.exit(f"{folder}: {p.name} {kind.name} units are not driven step by step")
    steps = kind.step_table()
    ap = argparse.ArgumentParser(prog=f"sports-video-coach run ({p.name} {kind.name})")
    pipeline.add_drive_args(ap, [s.name for s in steps])
    a = ap.parse_args(rest)
    unit = kind.unit_class().load(folder if folder.is_dir() else folder.parent)
    if a.status:
        pipeline.print_status(unit, steps)
        return 0
    return pipeline.drive(unit, steps, a.until, a.redo, a.publish, a.dry)


HELP = """usage: sports-video-coach run <videos...> [--plugin NAME] [start options]
       sports-video-coach run <folder> [driver options]
       sports-video-coach run <url> [--plugin NAME]

Turns your sports video into a film review, a coaching page with narration and clips, and an explained video.
The first run starts a folder from the videos; later runs take that folder and go on where it stopped.

Exit codes: 0 done (the deliverables are listed), 3 an agent step is waiting (the output says what to write and
with which guide; do it, run again), 1 a command failed (read the log it names, fix, run again).
"""


def help_text(name: str | None = None) -> str:
    """The user-facing help: the forms, then the start options of the plugin's `new` stage and the driver options."""
    def options(ap: argparse.ArgumentParser) -> str:
        fmt = ap._get_formatter()
        fmt.add_arguments([a for a in ap._actions if a.option_strings and a.dest != "help"])
        return fmt.format_help()

    parts = [HELP]
    try:
        p = plugin.get(name or "generic")
        mod = importlib.import_module(p.stages["new"][0]) if "new" in p.stages else None
    except (SystemExit, ImportError):
        mod = None
    if mod is not None and hasattr(mod, "parser"):
        parts.append(f"start options ({p.name} plugin, first run with videos):\n" + options(mod.parser()))
    ap = argparse.ArgumentParser(add_help=False)
    pipeline.add_drive_args(ap, ["STEP"])
    for a in ap._actions:
        if a.dest in ("until", "redo"):
            a.choices, a.metavar = None, "STEP"
    parts.append("driver options (later runs with the folder; `--status` lists the steps):\n" + options(ap))
    return "\n".join(parts)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ("-h", "--help"):
        name = argv[argv.index("--plugin") + 1] if "--plugin" in argv[:-1] else None
        print(help_text(name))
        sys.exit(0 if argv else 1)
    name = None
    if "--plugin" in argv:
        i = argv.index("--plugin")
        name = argv[i + 1] if i + 1 < len(argv) else sys.exit("--plugin needs a name")
        argv = argv[:i] + argv[i + 2:]
    target = argv[0]
    path = Path(target)
    videos = [a for a in argv if Path(a).suffix.lower() in VIDEO_EXT and Path(a).is_file()]
    if videos:
        p = plugin.get(name or "generic")
        folder = stage_main(p, "new")(argv)
        if folder is None:
            return
        sys.exit(drive_unit(Path(folder), []))
    if path.exists():
        sys.exit(drive_unit(path, argv[1:]))
    p = plugin.get(name) if name else plugin.claimant(target)
    if p is None:
        sys.exit(f"not a folder, a video file or a target any plugin claims: {target!r}")
    sys.exit(stage_main(p, "run")(argv) or 0)


if __name__ == "__main__":
    main()
