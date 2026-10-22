"""Write a new plugin folder from the generic plugin: `sports-video-coach new-plugin <name> [--sport tennis]`.

The copy goes to ./plugins/<name>/ (or --dir), where the core finds it without installing anything (also found:
$SVC_PLUGIN_PATH and <workspace>/plugins). It runs as is (frames -> review -> report -> artifacts); then make it
yours: the prompts first (prompts/review.md is what the agent looks for), then stages for your own measurements.
See docs/plugins.md.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

TEMPLATE = Path(__file__).parent / "plugins" / "generic"


def scaffold(name: str, dest: Path, sport: str = "") -> Path:
    """Copy the generic plugin to dest/<name>/ with NAME and SPORT set; refuses to overwrite."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name) or name == "generic":
        raise SystemExit(f"plugin name {name!r}: lowercase letters, digits, - or _, starting with a letter, not 'generic'")
    out = dest / name
    if out.exists():
        raise SystemExit(f"{out} exists; pick another name or delete it first")
    shutil.copytree(TEMPLATE, out, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    init = out / "__init__.py"
    s = init.read_text(encoding="utf8")
    s = s.replace('NAME = "generic"', f'NAME = "{name}"', 1)
    s = re.sub(r'^SPORT = ""', f'SPORT = "{sport}"', s, count=1, flags=re.M)
    s = s.replace('"""The generic plugin: any sport or activity, no computer vision.',
                  f'"""The {name} plugin (from the generic template): {sport or "your sport"}, no computer vision yet.', 1)
    init.write_text(s, encoding="utf8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach new-plugin", description=__doc__.split("\n\n")[0])
    ap.add_argument("name", help="plugin name, e.g. tennis")
    ap.add_argument("--sport", default="", help="the sport it analyses (default: the name)")
    ap.add_argument("--dir", default="plugins", help="parent folder (default ./plugins)")
    a = ap.parse_args(argv)
    out = scaffold(a.name, Path(a.dir), a.sport or a.name)
    print(f"wrote {out}")
    print(f"check:  sports-video-coach plugins      (lists {a.name}; run from this folder or set SVC_PLUGIN_PATH)")
    print(f"use:    sports-video-coach run <video> --plugin {a.name}")
    print(f"next:   edit {out / 'prompts' / 'review.md'} and {out / 'prompts' / 'report.md'} for {a.sport or a.name}")


if __name__ == "__main__":
    main()
