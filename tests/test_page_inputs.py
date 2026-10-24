"""A plugin's page hooks read files of their own (a measured number): `PageHooks.inputs` names them, so a change
to one makes the html step stale instead of leaving an old number on the page with exit 0."""
import json
import os
import sys

import pytest

from sports_video_coach import pipeline as P
from sports_video_coach import plugin

SWIM = '''import json
from pathlib import Path
from sports_video_coach.plugin import Kind, Plugin
from sports_video_coach.render_html import PageHooks

def box(folder, band, langs):
    d = json.loads((folder / "run" / "stroke.json").read_text(encoding="utf8"))
    return f"<p>Stroke rate: {d['spm']}</p>"

PLUGIN = Plugin(name="swimt", summary="test plugin", kinds=[Kind("swim", "swim.json")],
                page=PageHooks(before=box, inputs=lambda folder: [folder / "run" / "stroke.json"]))
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else json.dumps(text), encoding="utf8")


@pytest.fixture
def swim(tmp_path, monkeypatch):
    d = tmp_path / "plugins" / "swimt"
    write(d / "__init__.py", SWIM)
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(d.parent))
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    for m in [m for m in sys.modules if m.startswith("svc_plugin_")]:
        monkeypatch.delitem(sys.modules, m)
    plugin.plugins(refresh=True)
    folder = tmp_path / "ws" / "swim" / "2026-10-24"
    write(folder / "swim.json", {"plugin": "swimt"})
    write(folder / "README.md", "# Swim\n\nLonger glide.\n")
    write(folder / "run" / "stroke.json", {"spm": 45.0})
    yield SwimUnit(folder, {"plugin": "swimt"}, ("en",))
    monkeypatch.undo()
    plugin.plugins(refresh=True)


class SwimUnit(P.Unit):
    JSON = "swim.json"


def html_step():
    return next(s for s in P.tail_steps(lambda g: g.folder / "video.mp4", "", "", "") if s.name == "html")


def test_page_hook_input_is_an_html_input(swim):
    assert swim.folder / "run" / "stroke.json" in P.html_inputs(swim)


def test_changed_page_hook_input_makes_the_page_stale(swim):
    from sports_video_coach import render_html
    step, store = html_step(), P.Store(swim.folder)
    render_html.main([str(swim.folder)])
    assert "Stroke rate: 45.0" in (swim.folder / "index.html").read_text(encoding="utf8")
    P.record(step, swim, store)
    assert P.html_done(swim) and P.changes(step, swim, store) == []
    stroke = swim.folder / "run" / "stroke.json"
    write(stroke, {"spm": 44.0})                     # the author re-measures: one number changes
    later = (swim.folder / "index.html").stat().st_mtime + 10
    os.utime(stroke, (later, later))
    assert P.changes(step, swim, store) == ["run/stroke.json"]
    assert not P.html_done(swim)
    render_html.main([str(swim.folder)])
    assert "Stroke rate: 44.0" in (swim.folder / "index.html").read_text(encoding="utf8")


def test_hooks_without_inputs_add_nothing(tmp_path):
    g = SwimUnit(tmp_path, {}, ("en",))              # no plugin owns the folder: the core inputs only
    write(tmp_path / "README.md", "# x\n")
    assert P.html_inputs(g) == [tmp_path / P.readme("en"), g.gj]
