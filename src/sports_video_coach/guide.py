"""`sports-video-coach guide [<name>] [--plugin NAME]`: print a plugin's writing guide, or list its guides.

The agent steps name their guide by path, and after `uv tool install` that path is deep in the tool's folder
(an agent sandboxed to the project may not read it). This prints the same file, so `guide review` is enough.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import plugin


def guides(p: plugin.Plugin) -> dict[str, Path]:
    """{name: path} of the plugin's guides (prompts/*.md), by file name without `.md`."""
    return {f.stem: f for f in sorted(p.prompts.glob("*.md"))} if p.prompts and p.prompts.is_dir() else {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach guide", description=__doc__.split("\n\n")[0])
    ap.add_argument("name", nargs="?", help="the guide, e.g. review, report, narration, film (default: list them)")
    ap.add_argument("--plugin", default="generic", help="whose guides (default generic)")
    ap.add_argument("--path", action="store_true", help="print the file's path instead of its text")
    a = ap.parse_args(argv)
    p = plugin.get(a.plugin)
    found = guides(p)
    if not a.name:
        if not found:
            sys.exit(f"plugin {p.name!r} has no guides")
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
