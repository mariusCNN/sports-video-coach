"""Write a new plugin folder from the generic plugin: `sports-video-coach new-plugin <name> [--sport tennis]`.

The copy goes to <workspace>/plugins/<name>/ (or --dir), where the core finds it without installing anything (also
found: ./plugins, $SVC_PLUGIN_PATH, and a plugins/ folder above a unit that names it). It runs as is (frames -> review
-> report -> artifacts); then make it yours: the prompts first (prompts/review.md is what the agent looks for), then
stages for your own measurements. It also writes tests/test_<name>.py (`test_command` says how to run them). See
docs/plugins.md.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from . import plugin, workspace

TEMPLATE = Path(__file__).parent / "plugins" / "generic"
REPO = "git+https://github.com/mariusDing/sports-video-coach"


TEST = '''"""Tests for the {name} plugin. In a clone: `uv run pytest <this folder>`; after `uv tool install`:
`uv run --isolated --no-project --with pytest --with sports-video-coach@{repo} pytest <this folder>`."""
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
    """In order, with room for your own steps (a measurement before the review, say)."""
    names = [s.name for s in found["{name}"].kinds[0].step_table()]
    assert names.index("frames") < names.index("review") < names.index("report") and names[-1] == "film"


# A stage on a synthetic video (ffmpeg on PATH): uncomment, and name your stage and its arguments.
#
# import importlib
# import shutil
# import subprocess
#
# @pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
# def test_my_stage_on_a_test_video(found, tmp_path):
#     video = tmp_path / "v.mp4"
#     subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
#                     "-pix_fmt", "yuv420p", str(video)], check=True)
#     importlib.import_module(MODULE + ".pose").main([str(video), "--out", str(tmp_path / "pose")])
#     assert (tmp_path / "pose" / "pose.json").exists()
'''


def scaffold(name: str, dest: Path, sport: str = "", summary: str = "", use_when: str = "") -> Path:
    """Copy the generic plugin to dest/<name>/ with NAME, SPORT, summary, use_when and its texts set, plus
    tests/test_<name>.py; refuses to overwrite. No summary: a placeholder that `plugins` marks as not written."""
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
    summary = summary or f"{what} video: contact sheets -> agent film review -> coaching report {plugin.UNWRITTEN}"
    use_when = use_when or f"a {what} video: a game, a race or a training session"
    for key, text in (("summary", summary), ("use_when", use_when)):  # a Python string literal, quotes escaped
        s = re.sub(rf'^    {key}=".*",$', lambda m: f"    {key}={json.dumps(text, ensure_ascii=False)},", s,
                   count=1, flags=re.M)
    init.write_text(s, encoding="utf8")
    for f in [out / "new.py", *sorted((out / "prompts").glob("*.md"))]:  # stage names and guide titles
        t = f.read_text(encoding="utf8")
        f.write_text(t.replace("sports-video-coach generic:", f"sports-video-coach {name}:")
                     .replace("(generic plugin)", f"({name} plugin)"), encoding="utf8")
    (out / "tests").mkdir()
    (out / "tests" / f"test_{name.replace('-', '_')}.py").write_text(TEST.format(name=name, repo=REPO), encoding="utf8")
    return out


def in_clone() -> bool:
    """True when this package runs from a source checkout (src/sports_video_coach next to pyproject.toml)."""
    root = Path(__file__).resolve().parents[2]
    return (root / "pyproject.toml").is_file() and (root / "src" / "sports_video_coach").is_dir()


def test_command(out: Path) -> str:
    """How to run a scaffolded plugin's tests: `uv run pytest` in a clone; a tool install has no pytest and no
    project, so a throwaway env with both."""
    if in_clone():
        return f"uv run pytest {out.as_posix()}"
    return f"uv run --isolated --no-project --with pytest --with sports-video-coach@{REPO} pytest {out.as_posix()}"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach new-plugin", description=__doc__.split("\n\n")[0])
    ap.add_argument("name", help="plugin name, e.g. tennis")
    ap.add_argument("--sport", default="", help="the sport it analyses (default: the name)")
    ap.add_argument("--summary", default="", help="one line: what it analyses and delivers (agents choose a plugin "
                    "by it; default: a placeholder that `plugins` marks as not written yet)")
    ap.add_argument("--use-when", default="", help="one line: when an agent should pick it")
    ap.add_argument("--dir", help="parent folder (default <workspace>/plugins: $SVC_WORKSPACE/plugins, else "
                                   "./workspace/plugins)")
    a = ap.parse_args(argv)
    out = scaffold(a.name, Path(a.dir) if a.dir else workspace.root() / "plugins", a.sport or a.name,
                   a.summary, a.use_when)
    print(f"wrote {out.as_posix()}")
    print(f"sport:  {a.sport or a.name}" + ("" if a.sport else f"  (the plugin name; for another: --sport <sport>, or "
          f"change SPORT in {(out / '__init__.py').as_posix()})"))
    print(f"check:  sports-video-coach plugins      (lists {a.name}; from another folder: set SVC_WORKSPACE, or "
          f"SVC_PLUGIN_PATH={out.parent.as_posix()})")
    print(f"use:    sports-video-coach run <video> --plugin {a.name}")
    print(f"test:   {test_command(out)}")
    print(f"next:   edit {(out / 'prompts').as_posix()}/review.md and report.md for {a.sport or a.name}"
          + ("" if a.summary and a.use_when else f", and summary / use_when in {(out / '__init__.py').as_posix()}"))


if __name__ == "__main__":
    main()
