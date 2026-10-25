"""Tests for the swim-stroke-rate plugin. In a clone: `uv run pytest <this folder>`; after `uv tool install`:
`uv run --isolated --no-project --with pytest --with sports-video-coach@git+https://github.com/mariusDing/sports-video-coach@ac27030efdd1c7008e3174650ff16f81f7c41187 pytest <this folder>`
(the revision new-plugin was run from, so the tests see the core this plugin was written against)."""
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
    assert "swim-stroke-rate" in found and not plugin.errors()


def test_plugins_lists_it(found, capsys):
    cli.list_plugins(["--json"])
    rows = {p["name"]: p for p in json.loads(capsys.readouterr().out)["plugins"]}
    assert "swim-stroke-rate" in rows and "review-check" in rows["swim-stroke-rate"]["stages"]


def test_its_step_table(found):
    """In order, with room for your own steps (a measurement before the review, say)."""
    names = [s.name for s in found["swim-stroke-rate"].kinds[0].step_table()]
    assert names.index("frames") < names.index("review") < names.index("report") and names[-1] == "film"
    assert names.index("stroke") < names.index("review")  # the measurement is there before the agent reviews


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
