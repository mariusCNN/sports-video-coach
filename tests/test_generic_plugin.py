import json
import shutil
import sys

import pytest

from sports_video_coach import frames, media, pipeline as P, plugin, run, scaffold
from sports_video_coach.plugins.generic import new, unit as U


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("needs ffmpeg")
    out = tmp_path_factory.mktemp("v") / "clip.mp4"
    media.ffmpeg("-f", "lavfi", "-i", "testsrc=duration=6:size=320x240:rate=10", "-pix_fmt", "yuv420p", out)
    return out


@pytest.fixture
def analysis(tmp_path, video):
    folder = new.main([str(video), "--sport", "tennis", "--out", str(tmp_path / "a")])
    return U.Analysis.load(folder)


def test_new_writes_analysis_json_owned_by_generic(analysis, video):
    data = json.loads((analysis.folder / "analysis.json").read_text(encoding="utf8"))
    assert data["plugin"] == "generic" and data["sport"] == "tennis" and data["video"] == str(video.resolve())
    assert data["languages"] == ["en"] and analysis.langs == ("en",)
    p, k, _ = plugin.owner(analysis.folder)
    assert (p.name, k.name) == ("generic", "analysis")


def test_frames_sheets_and_index(tmp_path, video, capsys):
    data = frames.build(video, tmp_path / "f", every=1, cols=3, rows=2)
    assert [s["file"] for s in data["sheets"]] == ["sheet_001.jpg"]
    assert data["sheets"][0]["tiles"] == ["00:00", "00:01", "00:02", "00:03", "00:04", "00:05"]
    assert (tmp_path / "f" / "sheet_001.jpg").stat().st_size > 1000
    frames.build(video, tmp_path / "f", every=1, cols=3, rows=2)
    assert "up to date" in capsys.readouterr().out
    assert frames.times(5, 2) == [1.0, 3.0]


def test_status_and_waiting_on_review(analysis, video):
    names = [n for n, *_ in P.rows(analysis, U.STEPS)]
    assert names[:3] == ["frames", "review", "report"] and names[-1] == "film"
    frames.build(video, analysis.run / "frames", every=2)
    calls = []
    assert P.drive(analysis, U.STEPS, runner=lambda *a, **k: calls.append(a)) == P.WAITING
    assert calls == []


def test_review_validator(analysis, video):
    assert U.review_errors(analysis) == [f"{analysis.review / 'review.json'} missing"]
    analysis.review.mkdir(parents=True)
    rj = analysis.review / "review.json"
    rj.write_text(json.dumps({"moments": [{"start": "00:01"}]}), encoding="utf8")
    assert "at least 3" in U.review_errors(analysis)[0]
    m = {"start": "00:01", "end": "00:03", "what": "toss behind the head", "why": "late contact"}
    rj.write_text(json.dumps({"summary": "s", "moments": [m, m, {**m, "end": "00:00", "why": ""}]}), encoding="utf8")
    errs = U.review_errors(analysis)
    assert any("not after start" in e for e in errs) and any("`why` is empty" in e for e in errs)
    rj.write_text(json.dumps({"summary": "s", "moments": [m, m, m]}), encoding="utf8")
    assert U.review_errors(analysis) == []


def test_core_run_from_a_video_starts_and_stops_at_review(video, tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    with pytest.raises(SystemExit) as e:
        run.main([str(video), "--plugin", "generic"])
    assert e.value.code == P.WAITING
    [folder] = list((tmp_path / "ws" / "analysis").glob("*/*"))
    assert (folder / "run" / "frames" / "frames.json").exists()


def test_scaffolded_plugin_loads_and_owns_its_units(tmp_path, video, monkeypatch):
    out = scaffold.scaffold("tennis", tmp_path / "plugins", "tennis")
    assert 'NAME = "tennis"' in (out / "__init__.py").read_text(encoding="utf8")
    with pytest.raises(SystemExit, match="exists"):
        scaffold.scaffold("tennis", tmp_path / "plugins")
    with pytest.raises(SystemExit, match="plugin name"):
        scaffold.scaffold("Bad Name", tmp_path / "plugins")
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(tmp_path / "plugins"))
    monkeypatch.delitem(sys.modules, "svc_plugin_tennis", raising=False)
    try:
        found = plugin.plugins(refresh=True)
        assert "tennis" in found and not plugin.errors()
        folder = run.stage_main(found["tennis"], "new")([str(video), "--out", str(tmp_path / "t")])
        assert json.loads((folder / "analysis.json").read_text(encoding="utf8"))["sport"] == "tennis"
        p, k, _ = plugin.owner(folder)
        assert p.name == "tennis" and k.unit_class().load(folder).PLUGIN == "tennis"
    finally:
        monkeypatch.undo()
        plugin.plugins(refresh=True)
