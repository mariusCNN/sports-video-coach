import json
import shutil
import subprocess
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
    assert [new.auto_every(s) for s in (6, 30, 31, 180, 181, 3600)] == [0.5, 0.5, 1.0, 1.0, 2.0, 2.0]
    p = analysis.folder / "analysis.json"
    assert json.loads(p.read_text(encoding="utf8"))["every_s"] == 0.5  # the 6 s test video
    new.main([str(video), "--out", str(analysis.folder), "--every", "2"])
    new.main([str(video), "--out", str(analysis.folder)])  # a second start keeps the sheets already cut
    assert json.loads(p.read_text(encoding="utf8"))["every_s"] == 2


def test_new_stores_the_artifacts_choice(tmp_path, video):
    folder = new.main([str(video), "--out", str(tmp_path / "a"), "--artifacts", "html", "film"])
    assert json.loads((folder / "analysis.json").read_text(encoding="utf8"))["artifacts"] == ["html", "film"]
    with pytest.raises(SystemExit, match="needs 'html'"):
        new.main([str(video), "--out", str(tmp_path / "b"), "--artifacts", "publish"])
    assert not (tmp_path / "b").exists()


def test_run_help_lists_the_start_and_driver_options(capsys):
    with pytest.raises(SystemExit) as e:
        run.main(["--help"])
    out = capsys.readouterr().out
    assert e.value.code == 0
    assert all(f in out for f in ("--lang", "--every", "--focus", "--artifacts", "--status", "--redo STEP", "Exit codes"))


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
    frames.main([str(video), "--out", str(tmp_path / "q"), "--start", "2", "--end", "3", "--every", "0.25"])
    assert "--every 0.25 -> 0.2" in capsys.readouterr().out  # tenths labels: no ambiguous 00:02.2 for 2.25
    assert json.loads((tmp_path / "q" / "frames.json").read_text(encoding="utf8"))["every_s"] == 0.2


def test_a_second_video_of_the_same_day_gets_its_own_folder(video, tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    other = tmp_path / "other.mp4"
    shutil.copy(video, other)
    first = new.main([str(video), "--sport", "tennis", "--date", "2026-01-02"])
    assert new.main([str(video), "--sport", "tennis", "--date", "2026-01-02"]) == first  # the same video goes on
    second = new.main([str(other), "--sport", "tennis", "--date", "2026-01-02"])
    assert second.name == "2026-01-02-2" and new.folder_inputs(second) == [str(other.resolve())]
    assert new.folder_inputs(first) == [str(video.resolve())]


def test_joined_videos_print_their_parts_and_the_sheets_mark_them(tmp_path, video, capsys):
    other = tmp_path / "part2.mp4"
    shutil.copy(video, other)
    folder = new.main([str(video), str(other), "--sport", "shuttle-run", "--lang", "zh", "--out", str(tmp_path / "a")])
    out = capsys.readouterr().out
    assert "[new] joined 2 videos into video.mp4: clip.mp4 = 00:00-00:06, part2.mp4 = 00:06-00:12" in out
    assert "sport 'shuttle-run' has no Chinese name" in out
    a = U.Analysis.load(folder)
    assert frames.unit_sources(a.video) == a.game["sources"] and frames.unit_sources(video) is None
    frames.main([str(a.video), "--out", str(a.run / "frames"), "--every", "1"])
    data = json.loads((a.run / "frames" / "frames.json").read_text(encoding="utf8"))
    assert [p["file"] for p in data["parts"]] == ["clip.mp4", "part2.mp4"] and data["parts"][1]["start"] == "00:06.0"
    assert "the first tile of each later file is marked" in capsys.readouterr().out
    assert frames.part_starts([0.5, 1.5, 6.5, 7.5], a.game["sources"]) == {6.5: "part 2/2"}
    if sys.platform == "win32":  # one path style in run output: it pastes into Git Bash as printed
        assert P.slash(r"C:\ws\a\run") == "C:/ws/a/run"


def test_frames_sheets_and_index(tmp_path, video, capsys):
    data = frames.build(video, tmp_path / "f", every=1, cols=3, rows=2)
    assert [s["file"] for s in data["sheets"]] == ["sheet_001.jpg"]
    assert data["sheets"][0]["tiles"] == ["00:01", "00:02", "00:03", "00:04", "00:05"]  # whole seconds from 1 s
    assert (tmp_path / "f" / "sheet_001.jpg").stat().st_size > 1000
    frames.build(video, tmp_path / "f", every=1, cols=3, rows=2)
    out = capsys.readouterr().out
    assert "up to date" in out and f"in {(tmp_path / 'f').as_posix()}" in out and "\\" not in out  # Git Bash paths
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


def test_scaffolded_plugin_names_itself_and_its_own_guides(tmp_path, monkeypatch):
    out = scaffold.scaffold("swimming", tmp_path / "plugins", "swimming")
    for f in [out / "new.py", *(out / "prompts").glob("*.md")]:
        assert "generic:" not in f.read_text(encoding="utf8") and "(generic plugin)" not in f.read_text(encoding="utf8")
    assert "sports-video-coach swimming:new" in (out / "new.py").read_text(encoding="utf8")
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(tmp_path / "plugins"))
    monkeypatch.delitem(sys.modules, "svc_plugin_swimming", raising=False)
    try:
        found = plugin.plugins(refresh=True)
        p, g = found["swimming"], found["generic"]
        assert p.summary.startswith("swimming video:") and "scaffolded from generic" in p.summary
        assert p.summary != g.summary and p.use_when != g.use_when and "no plugin" not in p.use_when
        steps = p.kinds[0].step_table()
        unit = p.kinds[0].unit_class()(tmp_path / "a", {"plugin": "swimming"}, ("en",))
        hows = {s.name: unit.fill(s.how) for s in steps if s.kind == "agent" and s.how}
        assert "guide review --plugin swimming" in hows["review"] and "swimming:review-check" in hows["review"]
        assert "guide report --plugin swimming" in hows["report"]
        assert "guide film --plugin swimming" in hows["film-script"]
        assert "generic" not in " ".join(hows.values())
    finally:
        monkeypatch.undo()
        plugin.plugins(refresh=True)


def test_new_plugin_writes_to_the_workspace_and_prints_a_test_command_that_fits_the_install(tmp_path, monkeypatch,
                                                                                             capsys):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    scaffold.main(["rowing"])
    out = capsys.readouterr().out
    assert (tmp_path / "ws" / "plugins" / "rowing" / "__init__.py").exists()
    assert f"test:   uv run pytest {(tmp_path / 'ws' / 'plugins' / 'rowing').as_posix()}" in out   # this clone
    monkeypatch.setattr(scaffold, "in_clone", lambda: False)                                     # a tool install
    cmd = scaffold.test_command(tmp_path / "p" / "rowing")
    assert cmd.startswith("uv run --isolated --no-project --with pytest --with sports-video-coach@git+https://")
    assert cmd.endswith(f"pytest {(tmp_path / 'p' / 'rowing').as_posix()}")
    scaffold.main(["kayak", "--dir", str(tmp_path / "mine")])                                    # --dir still wins
    assert (tmp_path / "mine" / "kayak" / "__init__.py").exists()


def test_scaffolded_plugin_tests_pass(tmp_path):
    out = scaffold.scaffold("swimming", tmp_path / "plugins")
    assert (out / "tests" / "test_swimming.py").exists()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(out / "tests")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "3 passed" in r.stdout


def test_a_command_stage_added_as_docs_plugins_md_says_runs_qualified(tmp_path):
    out = scaffold.scaffold("swimming", tmp_path / "plugins")
    (out / "pose.py").write_text("from pathlib import Path\n\n\ndef main(argv=None):\n"
                                 "    Path(argv[-1]).write_text('ok')\n", encoding="utf8")
    init = out / "__init__.py"
    init.write_text(init.read_text(encoding="utf8").replace(
        "    stages={\n", '    stages={\n        "pose": (f"{__name__}.pose", "measure"),\n', 1), encoding="utf8")
    cmd = P.stage_cmd(["pose", str(tmp_path / "pose.json")], "swimming")
    assert cmd[3:] == ["swimming:pose", str(tmp_path / "pose.json")]
    r = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, env=P.child_env())  # finds ./plugins
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "pose.json").read_text() == "ok"


def test_generic_steps_point_at_the_generic_guides(analysis):
    review = next(s for s in U.STEPS if s.name == "review")
    assert "guide review --plugin generic" in analysis.fill(review.how)


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
                                              "analysis.json: narration, publish, film\n[run] to build them too: "
                                              f"sports-video-coach run {P.slash(tmp_path)} --artifacts clips "
                                              "narration html qa film")  # publish is never suggested
    g.game["artifacts"] = ["clips", "narration", "html", "film"]
    assert "to build them too" not in P.built_line(g, publish=False)  # only publish is left out


def test_artifacts_on_a_later_run_replace_the_choice(analysis, capsys):
    gj = analysis.folder / "analysis.json"
    data = json.loads(gj.read_text(encoding="utf8"))
    gj.write_text(json.dumps({**data, "artifacts": ["html"]}), encoding="utf8")
    assert run.drive_unit(analysis.folder, ["--artifacts", "html", "narration", "film", "--status"]) == 0
    assert json.loads(gj.read_text(encoding="utf8"))["artifacts"] == ["clips", "narration", "html", "qa", "film"]
    out = capsys.readouterr().out
    assert "artifacts in analysis.json: clips, narration, html, qa, film" in out and "film-script" in out
    with pytest.raises(SystemExit) as e:  # a wrong name is argparse's usage error
        run.drive_unit(analysis.folder, ["--artifacts", "pdf"])
    assert e.value.code == 2
    with pytest.raises(SystemExit, match="needs 'html'"):
        run.drive_unit(analysis.folder, ["--artifacts", "publish"])
    assert json.loads(gj.read_text(encoding="utf8"))["artifacts"][-1] == "film"  # a refused choice writes nothing


def test_step_texts_are_tool_neutral(analysis):
    texts = " ".join(analysis.fill(s.how) for s in U.STEPS if s.how)
    assert "browser-check" not in texts and "if your tool has" in texts
    assert "subagents if you have" not in texts


def test_finished_lists_every_deliverable_it_finds(analysis, capsys):
    f = analysis.folder
    (f / "clips").mkdir()
    for p in (f / "film.en.mp4", f / "listen.en.mp3", f / "clips" / "0001-0005.mp4"):
        p.write_bytes(b"x")
    analysis.finished()
    out = capsys.readouterr().out
    assert "index.html" in out and "film.en.mp4" in out and "listen.en.mp3" in out and "clips (also on the page): 1" in out


def test_review_parts_from_helpers_merge_into_review_json(analysis, video, capsys):
    frames.build(video, analysis.run / "frames", every=0.5, cols=1, rows=1)  # 12 sheets
    assert U.review_errors(analysis)[0].endswith("(12 sheets; with helpers, one range each: 1-6, 7-12)")
    analysis.review.mkdir(parents=True)
    m = {"start": "00:01", "end": "00:03", "what": "toss behind the head", "why": "late contact"}
    (analysis.review / "part1.json").write_text(json.dumps({"summary": "A.", "moments": [{**m, "start": "00:02"}, m]}),
                                                encoding="utf8")
    (analysis.review / "part2.json").write_text(json.dumps({"summary": "B.", "moments": [{**m, "start": "00:00"}]}),
                                                encoding="utf8")
    assert "merges them into it" in U.review_errors(analysis)[0]
    with pytest.raises(SystemExit) as e:
        U.main([str(analysis.folder)])
    assert e.value.code == 0 and "merged 2 part(s)" in capsys.readouterr().out
    data = json.loads((analysis.review / "review.json").read_text(encoding="utf8"))
    assert data["summary"] == "A. B." and [x["start"] for x in data["moments"]] == ["00:00", "00:01", "00:02"]
    assert U.merge_parts(analysis) is None  # an existing review.json is never overwritten


def test_sport_zh_names_the_sport_on_the_zh_page(tmp_path, video, capsys):
    folder = new.main([str(video), "--sport", "shuttle-run", "--sport-zh", "折返跑", "--lang", "zh", "en",
                       "--out", str(tmp_path / "a")])
    data = json.loads((folder / "analysis.json").read_text(encoding="utf8"))
    assert data["sport"] == {"zh": "折返跑", "en": "shuttle-run"}
    assert "no Chinese name" not in capsys.readouterr().out
    new.main([str(video), "--sport", "shuttle-run", "--lang", "zh", "--out", str(tmp_path / "b")])
    assert '--sport "shuttle run" --sport-name zh=折返跑' in capsys.readouterr().out


def test_sport_name_names_the_sport_per_language(tmp_path, video, capsys):
    folder = new.main([str(video), "--sport", "shuttle-run", "--sport-name", "ja=シャトルラン", "--sport-name",
                       "zh=折返跑", "--lang", "ja", "zh", "--out", str(tmp_path / "a")])
    data = json.loads((folder / "analysis.json").read_text(encoding="utf8"))
    assert data["sport"] == {"ja": "シャトルラン", "zh": "折返跑", "en": "shuttle-run"}
    assert "no Japanese name" not in capsys.readouterr().out
    new.main([str(video), "--sport", "shuttle-run", "--lang", "ja", "--out", str(tmp_path / "b")])
    assert "--sport-name ja=" in capsys.readouterr().out
    for bad in ("xx=Name", "ja", "ja="):
        with pytest.raises(SystemExit) as e:
            new.parser().parse_args(["v.mp4", "--sport-name", bad])
        assert e.value.code == 2
    assert "--sport-name LANG=NAME" in run.help_text("generic") and "--sport-zh" in run.help_text("generic")
