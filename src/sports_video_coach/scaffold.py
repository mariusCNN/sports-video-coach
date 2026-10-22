"""Write a new plugin folder from the generic plugin: `sports-video-coach new-plugin <name> [--sport tennis]`.

The copy goes to ./plugins/<name>/ (or --dir), where the core finds it without installing anything (also found:
$SVC_PLUGIN_PATH and <workspace>/plugins). It runs as is (frames -> review -> report -> artifacts); then make it
yours: the prompts first (prompts/review.md is what the agent looks for), then stages for your own measurements.
It also writes tests/test_<name>.py (`uv run pytest plugins/<name>`). See docs/plugins.md.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

TEMPLATE = Path(__file__).parent / "plugins" / "generic"


TEST = '''"""Tests for the {name} plugin; from the folder that holds plugins/: `uv run pytest plugins/{name}`."""
import json
import sys
from pathlib import Path

import pytest

from sports_video_coach import cli, plugin

HERE = Path(__file__).resolve().parents[1]           # this plugin's folder
MODULE = "svc_plugin_" + HERE.name.replace("-", "_")  # folder plugins import under this name


@pytest.fixture
def found(monkeypatch):
    """The plugins with this one's parent folder on SVC_PLUGIN_PATH, loaded afresh."""
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(HERE.parent))
    monkeypatch.delitem(sys.modules, MODULE, raising=False)
    yield plugin.plugins(refresh=True)
    monkeypatch.undo()
    plugin.plugins(refresh=True)


def test_it_loads_with_no_error(found):
    assert "{name}" in found and not plugin.errors()


def test_plugins_lists_it(found, capsys):
    cli.list_plugins(["--json"])
    rows = {{p["name"]: p for p in json.loads(capsys.readouterr().out)["plugins"]}}
    assert "{name}" in rows and "review-check" in rows["{name}"]["stages"]


def test_its_step_table(found):
    names = [s.name for s in found["{name}"].kinds[0].step_table()]
    assert names[:3] == ["frames", "review", "report"] and names[-1] == "film"
'''


def scaffold(name: str, dest: Path, sport: str = "") -> Path:
    """Copy the generic plugin to dest/<name>/ with NAME, SPORT and its texts set, plus tests/test_<name>.py;
    refuses to overwrite."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name) or name == "generic":
        raise SystemExit(f"plugin name {name!r}: lowercase letters, digits, - or _, starting with a letter, not 'generic'")
    out = dest / name
    if out.exists():
        raise SystemExit(f"{out} exists; pick another name or delete it first")
    shutil.copytree(TEMPLATE, out, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    what = sport or name
    init = out / "__init__.py"
    s = init.read_text(encoding="utf8")
    s = s.replace('NAME = "generic"', f'NAME = "{name}"', 1)
    s = re.sub(r'^SPORT = ""', f'SPORT = "{sport}"', s, count=1, flags=re.M)
    s = s.replace('"""The generic plugin: any sport or activity, no computer vision.',
                  f'"""The {name} plugin (from the generic template): {sport or "your sport"}, no computer vision yet.', 1)
    # `plugins` shows these to agents choosing a plugin: never two identical rows
    s = re.sub(r'^    summary=".*",$', f'    summary="{what} video: contact sheets -> agent film review -> coaching '
               'report (scaffolded from generic; describe what it adds)",', s, count=1, flags=re.M)
    s = re.sub(r'^    use_when=".*",$', f'    use_when="a {what} video: a game, a race or a training session",', s, count=1, flags=re.M)
    init.write_text(s, encoding="utf8")
    for f in [out / "new.py", *sorted((out / "prompts").glob("*.md"))]:  # stage names and guide titles
        t = f.read_text(encoding="utf8")
        f.write_text(t.replace("sports-video-coach generic:", f"sports-video-coach {name}:")
                     .replace("(generic plugin)", f"({name} plugin)"), encoding="utf8")
    (out / "tests").mkdir()
    (out / "tests" / f"test_{name.replace('-', '_')}.py").write_text(TEST.format(name=name), encoding="utf8")
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
    print(f"test:   uv run pytest {out}")
    print(f"next:   edit {out / 'prompts' / 'review.md'} and {out / 'prompts' / 'report.md'} for {a.sport or a.name}, "
          f"and summary / use_when in {out / '__init__.py'}")


if __name__ == "__main__":
    main()
