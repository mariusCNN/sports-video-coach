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


def test_new_picks_the_tile_interval_from_the_length_and_keeps_an_old_one(analysis, video):
    assert [new.auto_every(s) for s in (6, 30, 31, 120, 121, 3600)] == [0.5, 0.5, 1.0, 1.0, 2.0, 2.0]
    p = analysis.folder / "analysis.json"
    assert json.loads(p.read_text(encoding="utf8"))["every_s"] == 0.5  # the 6 s test video
    new.main([str(video), "--out", str(analysis.folder), "--every", "2"])
    new.main([str(video), "--out", str(analysis.folder)])  # a second start keeps the sheets already cut
    assert json.loads(p.read_text(encoding="utf8"))["every_s"] == 2


def test_run_help_lists_the_start_and_driver_options(capsys):
    with pytest.raises(SystemExit) as e:
        run.main(["--help"])
    out = capsys.readouterr().out
    assert e.value.code == 0
    assert all(f in out for f in ("--lang", "--every", "--focus", "--status", "--redo STEP", "Exit codes"))


def test_frames_label_tenths_under_a_second(tmp_path, video):
    data = frames.build(video, tmp_path / "f", every=0.5, cols=2, rows=2)
    assert data["sheets"][0]["tiles"] == ["00:00.3", "00:00.8", "00:01.3", "00:01.8"]  # whole tenths, even gaps


def test_frames_window_for_a_close_look(tmp_path, video, capsys):
    frames.main([str(video), "--out", str(tmp_path / "z"), "--start", "0:02", "--end", "3", "--every", "0.2"])
    data = json.loads((tmp_path / "z" / "frames.json").read_text(encoding="utf8"))
    assert data["sheets"][0]["tiles"] == ["00:02.0", "00:02.2", "00:02.4", "00:02.6", "00:02.8"]  # from --start
    assert (data["start_s"], data["end_s"]) == (2.0, 3.0)
    whole = frames.build(video, tmp_path / "f", every=2)
    assert "start_s" not in whole  # whole-video sheets keep the settings keys they always had
    with pytest.raises(SystemExit):
        frames.main([str(video), "--out", str(tmp_path / "z"), "--start", "3", "--end", "2"])


def test_a_second_video_of_the_same_day_gets_its_own_folder(video, tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    other = tmp_path / "other.mp4"
    shutil.copy(video, other)
    first = new.main([str(video), "--sport", "tennis", "--date", "2026-01-02"])
    assert new.main([str(video), "--sport", "tennis", "--date", "2026-01-02"]) == first  # the same video goes on
    second = new.main([str(other), "--sport", "tennis", "--date", "2026-01-02"])
    assert second.name == "2026-01-02-2" and new.folder_inputs(second) == [str(other.resolve())]
    assert new.folder_inputs(first) == [str(video.resolve())]


def test_frames_sheets_and_index(tmp_path, video, capsys):
    data = frames.build(video, tmp_path / "f", every=1, cols=3, rows=2)
    assert [s["file"] for s in data["sheets"]] == ["sheet_001.jpg"]
    assert data["sheets"][0]["tiles"] == ["00:00", "00:01", "00:02", "00:03", "00:04", "00:05"]
    assert (tmp_path / "f" / "sheet_001.jpg").stat().st_size > 1000
    frames.build(video, tmp_path / "f", every=1, cols=3, rows=2)
    assert "up to date" in capsys.readouterr().out
    assert frames.times(5, 2) == [1.0, 3.0] and frames.times(1, 0.1)[-1] == 0.9


def test_status_and_waiting_on_review(analysis, video):
    names = [n for n, *_ in P.rows(analysis, U.STEPS)]
    assert names[:3] == ["frames", "review", "report"] and names[-1] == "film"
    frames.build(video, analysis.run / "frames", every=2)
    calls = []
    assert P.drive(analysis, U.STEPS, runner=lambda *a, **k: calls.append(a)) == P.WAITING
    assert calls == []


def test_clips_not_done_before_a_report_exists(analysis):
    # nothing to cut yet must not read as "done" in --status: a fresh session would trust it
    assert not P.clips_done(analysis)
    (analysis.folder / "README.en.md").write_text("# r\n\nno clips marked\n", encoding="utf8")
    assert P.clips_done(analysis)
    ok = {n: ok for n, _, ok, _ in P.rows(analysis, U.STEPS)}
    assert ok["clips"] is True


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


def test_logs_stay_with_a_unit_outside_the_workspace(analysis, tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    assert P.logs_dir(analysis) == analysis.run / "logs"              # made with --out elsewhere
    inside = U.Analysis(tmp_path / "ws" / "analysis" / "x" / "d", analysis.game, analysis.langs)
    assert P.logs_dir(inside) == tmp_path / "ws" / "logs"


def test_status_marks_publish_optional(analysis, capsys):
    P.print_status(analysis, U.STEPS)
    assert "skip  publish" in capsys.readouterr().out


def test_built_line_names_what_was_built_and_what_was_left_out(tmp_path):
    g = U.Analysis(tmp_path, {"plugin": "generic"}, ("en",))
    assert P.built_line(g, publish=False) == ("[run] built: clips, narration, html, qa, film; "
                                              "publish: only with --publish")
    g.game["artifacts"] = ["clips", "html"]
    assert P.built_line(g, publish=False) == ("[run] built: clips, html, qa; left out by \"artifacts\" in "
                                              "analysis.json: narration, publish, film")
