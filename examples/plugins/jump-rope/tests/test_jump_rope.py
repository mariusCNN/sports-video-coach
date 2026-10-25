"""Tests for the jump-rope plugin. In a clone: `uv run pytest <this folder>`; after `uv tool install`:
`uv run --isolated --no-project --with pytest --with sports-video-coach@git+https://github.com/mariusDing/sports-video-coach@ac27030efdd1c7008e3174650ff16f81f7c41187 pytest <this folder>`
(the revision new-plugin was run from, so the tests see the core this plugin was written against)."""
import importlib
import json
import shutil
import subprocess
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
    assert "jump-rope" in found and not plugin.errors()


def test_plugins_lists_it(found, capsys):
    cli.list_plugins(["--json"])
    rows = {p["name"]: p for p in json.loads(capsys.readouterr().out)["plugins"]}
    assert "jump-rope" in rows and "review-check" in rows["jump-rope"]["stages"]


def test_its_step_table(found):
    """In order, with room for your own steps (a measurement before the review, say)."""
    names = [s.name for s in found["jump-rope"].kinds[0].step_table()]
    assert names.index("frames") < names.index("review") < names.index("report") and names[-1] == "film"
    assert names.index("skip") < names.index("review")  # the count is there before the agent reviews


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("rate_hz,seconds,truth", [(2.3, 20, 46), (1.5, 10, 15), (3.0, 10, 30)])
def test_skip_counts_a_drawn_jumper(found, tmp_path, rate_hz, seconds, truth):
    """A box that rises and falls rate_hz times a second (one hump = one skip), with grain: the exact count."""
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x202830:s=320x240:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"color=c=white:s=40x80:r=30:d={seconds}", "-filter_complex",
                    f"[0][1]overlay=x=140:y='140-50*abs(sin(PI*{rate_hz}*t))':shortest=1,noise=alls=20:allf=t,"
                    "format=yuv420p", str(video)], check=True)
    importlib.import_module(MODULE + ".skip").main([str(video), "--out", str(tmp_path / "skip")])
    got = json.loads((tmp_path / "skip" / "skip.json").read_text(encoding="utf8"))
    assert got["skips"] == truth and len(got["at_s"]) == truth
