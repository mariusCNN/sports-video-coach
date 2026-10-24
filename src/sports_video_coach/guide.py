"""`sports-video-coach guide [<name>] [--plugin NAME | --unit FOLDER]`: print a plugin's writing guide, or list them.

The agent steps name their guide by path, and after `uv tool install` that path is deep in the tool's folder
(an agent sandboxed to the project may not read it). This prints the same file. The agent steps print
`guide review --unit <folder>`: the unit's own plugin, found as `run <folder>` finds it (also a plugin in a
`plugins/` folder above the unit), so the command works from any folder.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import plugin


SHARED = ("humanize",)  # core guides every plugin has: the generic one unless the plugin writes its own


def guides(p: plugin.Plugin) -> dict[str, Path]:
    """{name: path} of the plugin's guides (prompts/*.md), by file name without `.md`, plus the shared guides
    (SHARED) from the generic plugin when the plugin has none of that name."""
    own = {f.stem: f for f in sorted(p.prompts.glob("*.md"))} if p.prompts and p.prompts.is_dir() else {}
    if p.name == "generic":
        return own
    base = guides(plugin.get("generic"))
    return own | {n: base[n] for n in SHARED if n in base and n not in own} if own else own


def unit_plugin(folder: str) -> plugin.Plugin:
    """The plugin that owns the unit at `folder`; exits when it is no unit folder."""
    found = plugin.owner(folder)
    if found is None:
        sys.exit(f"{folder}: no unit json here (or above a sub-report); give a folder `sports-video-coach run` made")
    return found[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach guide", description=__doc__.split("\n\n")[0])
    ap.add_argument("name", nargs="?", help="the guide, e.g. review, report, narration, film (default: list them)")
    who = ap.add_mutually_exclusive_group()
    who.add_argument("--plugin", default="generic", help="whose guides (default generic)")
    who.add_argument("--unit", metavar="FOLDER", help="the guides of this unit folder's plugin (the form the agent "
                     "steps print)")
    ap.add_argument("--path", action="store_true", help="print the file's path instead of its text")
    a = ap.parse_args(argv)
    p = unit_plugin(a.unit) if a.unit else plugin.get(a.plugin)
    found = guides(p)
    if not a.name:
        if not found:
            where = (f": they are in {p.prompts}, which this install does not have (a plugin that runs from a clone "
                     "keeps its guides there; see `sports-video-coach plugins`)") if p.prompts and not Path(
                p.prompts).is_dir() else ""
            sys.exit(f"plugin {p.name!r} has no guides{where}")
        print(f"{p.name} guides ({p.prompts}):")
        for name in found:
            print(f"  {name}")
        return 0
    f = found.get(Path(a.name).stem)
    if f is None:
        sys.exit(f"plugin {p.name!r} has no guide {a.name!r}; its guides: {', '.join(found) or '-'}")
    if a.path:
        print(f.as_posix())
        return 0
    if hasattr(sys.stdout, "reconfigure"):  # a Chinese guide on a Windows console
        sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(f.read_text(encoding="utf8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
