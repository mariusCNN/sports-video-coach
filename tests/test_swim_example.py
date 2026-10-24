"""The worked example plugin in examples/plugins/swim-stroke-rate: it loads the documented way (its parent folder on
SVC_PLUGIN_PATH), `plugins --json` lists it, and its stroke stage measures a synthetic swimmer's known rate."""
import json
import sys
from pathlib import Path

import pytest

from sports_video_coach import cli, plugin

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "plugins"
NAME, MODULE = "swim-stroke-rate", "svc_plugin_swim_stroke_rate"
TRUTH_SPM, TOLERANCE_SPM = 45.0, 1.0   # measured 45.0 on the 8 s, 30 fps clip


@pytest.fixture
def found(monkeypatch):
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(EXAMPLES))
    for m in [m for m in sys.modules if m == MODULE or m.startswith(MODULE + ".")]:
        monkeypatch.delitem(sys.modules, m)
    yield plugin.plugins(refresh=True)
    monkeypatch.undo()
    plugin.plugins(refresh=True)


def test_the_example_registers_and_plugins_json_lists_it(found, capsys):
    assert NAME in found and not plugin.errors()
    cli.main(["plugins", "--json"])
    rows = {p["name"]: p for p in json.loads(capsys.readouterr().out)["plugins"]}
    assert {"stroke", "synth"} <= set(rows[NAME]["stages"])
    names = [s.name for s in found[NAME].kinds[0].step_table()]
    assert names.index("stroke") < names.index("review")


def test_the_stroke_stage_measures_the_known_rate(found, tmp_path, capsys):
    video = tmp_path / "swim.mp4"
    cli.main([f"{NAME}:synth", str(video), "--spm", str(TRUTH_SPM)])
    cli.main([f"{NAME}:stroke", str(video), "--out", str(tmp_path / "stroke")])
    got = json.loads((tmp_path / "stroke" / "stroke.json").read_text(encoding="utf8"))
    print(f"measured {got['stroke_rate_spm']} cycles/min, truth {TRUTH_SPM}")
    assert abs(got["stroke_rate_spm"] - TRUTH_SPM) <= TOLERANCE_SPM, got
    assert got["frames"] == 240 and got["windows"]
