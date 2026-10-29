import json
import os
import sys

import pytest

from sports_video_coach import cli, pipeline, plugin, units

LOCAL = '''from sports_video_coach.plugin import Kind, Plugin
PLUGIN = Plugin(name="{name}", summary="test plugin", stages={{"fetch": ("json", "same name as basketball"),
                                                              "rally": ("json", "only here")}},
                kinds=[Kind("drill", "drill.json", "x:Y", "x:Z")])
'''


@pytest.fixture
def local(tmp_path, monkeypatch):
    """A clean registry with one local folder plugin `tennis` and one broken folder plugin."""
    d = tmp_path / "plugins"
    (d / "tennis").mkdir(parents=True)
    (d / "tennis" / "__init__.py").write_text(LOCAL.format(name="tennis"), encoding="utf8")
    (d / "broken").mkdir()
    (d / "broken" / "__init__.py").write_text("raise RuntimeError('boom')\n", encoding="utf8")
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(d))
    monkeypatch.setenv("SVC_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.chdir(tmp_path)
    for m in [m for m in sys.modules if m.startswith("svc_plugin_")]:
        monkeypatch.delitem(sys.modules, m)
    plugin.plugins(refresh=True)
    yield d
    monkeypatch.undo()
    plugin.plugins(refresh=True)


def test_builtin_and_entry_point_plugins_load():
    found = plugin.plugins(refresh=True)
    assert list(found)[0] == "generic" and "basketball" in found
    assert {k.json for k in found["basketball"].kinds} >= {"game.json", "session.json", "movement.json"}


def test_local_folder_plugin_loads_and_a_broken_one_is_reported(local):
    assert "tennis" in plugin.plugins()
    errs = plugin.errors()
    assert any("broken" in where and "boom" in e for where, e in errs.items())


def test_resolve_order(local):
    assert cli.resolve("tennis:fetch") == ("json", "tennis:fetch")
    assert cli.resolve("fetch", default="basketball")[0] == "hoop_tape_miner.fetch"
    assert cli.resolve("rally") == ("json", "rally")      # unique across plugins
    assert cli.resolve("clips")[0] == "sports_video_coach.clips"   # core
    with pytest.raises(SystemExit, match="several plugins"):
        cli.resolve("fetch")
    assert cli.resolve("no-such") == ("", "")
    with pytest.raises(SystemExit, match="has no stage"):
        cli.resolve("tennis:nope")


def test_stage_cmd_qualifies_plugin_stages():
    assert pipeline.stage_cmd(["extract", "x"], "basketball")[-3:] == ["sports_video_coach.cli", "basketball:extract", "x"]
    assert pipeline.stage_cmd(["clips", "x"], "basketball")[-2:] == ["clips", "x"]
    assert pipeline.stage_cmd(["a"], None)[-1] == "a"


def test_owner_by_json_name_kind_and_level(tmp_path):
    g = tmp_path / "game"
    (g / "player-7").mkdir(parents=True)
    (g / "game.json").write_text("{}", encoding="utf8")
    p, k, _ = plugin.owner(g / "player-7")
    assert (p.name, k.name) == ("basketball", "game")
    s = tmp_path / "s"
    s.mkdir()
    (s / "session.json").write_text(json.dumps({"kind": "training"}), encoding="utf8")
    assert plugin.owner(s)[1].name == "training"
    assert units.load(s) == {"kind": "training"}
    assert plugin.owner(tmp_path / "nothing") is None


def test_owner_named_plugin_wins_and_unknown_kind_fails(tmp_path):
    (tmp_path / "game.json").write_text(json.dumps({"plugin": "generic"}), encoding="utf8")
    with pytest.raises(SystemExit, match="no kind for game.json"):
        plugin.owner(tmp_path)


def test_claims_league_urls_only():
    assert plugin.claimant("https://my.gloryleague.basketball/game/abc/overview").name == "basketball"
    assert plugin.claimant("https://example.com/video.mp4") is None


def test_old_cli_keeps_every_stage_and_lists_plugins(capsys):
    from hoop_tape_miner import cli as old
    assert {"run", "fetch", "train", "move", "html", "clips", "narrate", "film", "publish"} <= set(old.STAGES)
    cli.main(["plugins", "--json"])
    names = [p["name"] for p in json.loads(capsys.readouterr().out)["plugins"]]
    assert names[:1] == ["generic"] and "basketball" in names


def test_units_say_which_plugin_runs_their_stages(tmp_path):
    from hoop_tape_miner import run, train_run
    assert run.Game(tmp_path, {}).PLUGIN == "basketball" and train_run.Session(tmp_path, {}).PLUGIN == "basketball"


def test_missing_packages_are_listed_with_the_install_hint(monkeypatch, capsys):
    p = plugin.Plugin(name="heavy", summary="s", requires=("json", "no_such_pkg_xyz"), install="clone and uv sync")
    assert plugin.missing(p) == ["no_such_pkg_xyz"] and plugin.missing(plugin.get("generic")) == []
    monkeypatch.setattr(plugin, "plugins", lambda refresh=False: {"heavy": p})
    cli.list_plugins([])
    out = capsys.readouterr().out
    assert out == "heavy: not usable in this install (1 package missing, `plugins --json` lists them); needs clone " \
                  "and uv sync\n"                                     # one line, not the summary, units and stages
    cli.list_plugins(["--json"])
    row = json.loads(capsys.readouterr().out)["plugins"][0]
    assert row["missing"] == ["no_such_pkg_xyz"] and row["install"] == "clone and uv sync" and row["summary"] == "s"


def test_plugins_marks_a_summary_new_plugin_left_as_it_was(tmp_path, monkeypatch, capsys):
    from sports_video_coach import scaffold
    scaffold.scaffold("rowing", tmp_path / "plugins")
    scaffold.scaffold("kayak", tmp_path / "plugins", summary='kayak "sprint" video: stroke rate -> report',
                      use_when="a kayak race")
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(tmp_path / "plugins"))
    for m in ("svc_plugin_rowing", "svc_plugin_kayak"):
        monkeypatch.delitem(sys.modules, m, raising=False)
    try:
        found = plugin.plugins(refresh=True)
        assert not plugin.summary_written(found["rowing"]) and plugin.summary_written(found["kayak"])
        assert found["kayak"].summary == 'kayak "sprint" video: stroke rate -> report'
        assert found["kayak"].use_when == "a kayak race"
        cli.list_plugins([])
        out = capsys.readouterr().out
        assert "rowing: rowing video:" in out and out.count("[summary not written yet]") == 1
        cli.list_plugins(["--json"])
        rows = {r["name"]: r for r in json.loads(capsys.readouterr().out)["plugins"]}
        assert rows["rowing"]["summary_written"] is False and rows["kayak"]["summary_written"] is True
    finally:
        monkeypatch.undo()
        plugin.plugins(refresh=True)


def test_a_stage_that_needs_a_missing_package_exits_with_a_hint(monkeypatch):
    def stage(argv):
        raise ModuleNotFoundError("No module named 'pandas'", name="pandas")
    monkeypatch.setattr(cli, "resolve", lambda stage, default, args=(): ("fake_stage_mod", "html"))
    monkeypatch.setitem(sys.modules, "fake_stage_mod", type(sys)("fake_stage_mod"))
    sys.modules["fake_stage_mod"].main = stage
    with pytest.raises(SystemExit) as e:
        cli.main(["html", "x"])
    assert "'pandas' is not installed" in str(e.value) and "sports-video-coach plugins" in str(e.value)


def test_basketball_declares_its_heavy_packages():
    p = plugin.get("basketball")
    assert {"pandas", "torch"} <= set(p.requires) and "uv sync" in p.install


SWIM = '''from sports_video_coach.plugin import Plugin
PLUGIN = Plugin(name="swimming", summary="test plugin", stages={"new": (__name__ + ".new", "start")})
'''


@pytest.fixture
def swimming(tmp_path, monkeypatch):
    """A clean registry with one local plugin `swimming` whose `new` stage records its argv."""
    d = tmp_path / "plugins" / "swimming"
    d.mkdir(parents=True)
    (d / "__init__.py").write_text(SWIM, encoding="utf8")
    (d / "new.py").write_text("SEEN = []\ndef main(argv):\n    SEEN.append(argv)\n", encoding="utf8")
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(d.parent))
    for m in [m for m in sys.modules if m.startswith("svc_plugin_")]:
        monkeypatch.delitem(sys.modules, m)
    plugin.plugins(refresh=True)
    yield tmp_path
    monkeypatch.undo()
    plugin.plugins(refresh=True)


def test_videos_go_to_the_plugin_named_for_the_sport(swimming, capsys):
    from sports_video_coach import run
    video = swimming / "lap.mp4"
    video.write_bytes(b"x")
    run.main([str(video), "--sport", "Swimming"])
    assert sys.modules["svc_plugin_swimming.new"].SEEN == [[str(video), "--sport", "Swimming"]]
    assert "[run] plugin: swimming (named for --sport Swimming; `--plugin generic`" in capsys.readouterr().out
    assert run.for_sport(["v.mp4", "--sport=swimming"])[0].name == "swimming"
    p, why = run.for_sport(["v.mp4", "--sport", "tennis"])
    assert p.name == "generic" and "no plugin named for --sport tennis" in why
    p, why = run.for_sport(["v.mp4"])
    assert p.name == "generic" and "no --sport" in why


def test_run_says_which_plugin_starts_the_unit_and_why(swimming, capsys, monkeypatch):
    from sports_video_coach import run
    video = swimming / "lap.mp4"
    video.write_bytes(b"x")
    run.main([str(video), "--plugin", "swimming"])
    assert "[run] plugin: swimming (--plugin)" in capsys.readouterr().out
    if "basketball" in plugin.plugins():    # a plugin with no `new` stage: videos go to generic, and it says why
        p, why = run.for_sport(["v.mp4", "--sport", "Basketball"])
        assert p.name == "generic" and "basketball plugin does not start from videos" in why
    monkeypatch.setattr(run, "stage_main", lambda p, stage: lambda argv: None)
    run.main([str(video), "--sport", "tennis"])
    assert "[run] plugin: generic (no plugin named for --sport tennis" in capsys.readouterr().out


def test_an_unknown_plugin_lists_the_folders_searched_and_how_to_add_one(tmp_path, monkeypatch):
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(tmp_path / "mine"))
    monkeypatch.chdir(tmp_path)
    plugin.plugins(refresh=True)
    try:
        with pytest.raises(SystemExit) as e:
            plugin.get("rowing")
    finally:
        monkeypatch.undo()
        plugin.plugins(refresh=True)
    msg = str(e.value.code)
    assert msg.startswith("unknown plugin 'rowing'; installed: generic")
    assert f"{(tmp_path / 'mine').resolve().as_posix()}  (missing)" in msg       # $SVC_PLUGIN_PATH
    assert (tmp_path / "plugins").resolve().as_posix() in msg                    # ./plugins
    assert "SVC_PLUGIN_PATH" in msg and "SVC_WORKSPACE" in msg and "cd to" in msg


def test_a_unit_finds_its_plugin_in_a_plugins_folder_above_it_from_any_folder(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "plugins" / "rowing").mkdir(parents=True)
    (ws / "plugins" / "rowing" / "__init__.py").write_text(
        LOCAL.format(name="rowing").replace('"drill", "drill.json"', '"analysis", "analysis.json"'), encoding="utf8")
    unit = ws / "analysis" / "rowing" / "2026-01-01"
    unit.mkdir(parents=True)
    (unit / "analysis.json").write_text(json.dumps({"plugin": "rowing"}), encoding="utf8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)               # not where plugins/ is; the workspace (HOOP_WORKSPACE) is another one
    monkeypatch.delitem(sys.modules, "svc_plugin_rowing", raising=False)
    try:
        assert "rowing" not in plugin.plugins(refresh=True)
        p, k, _ = plugin.owner(unit)
        assert p.name == "rowing" and k.json == "analysis.json"
        assert str((ws / "plugins").resolve()) in pipeline.child_env()["SVC_PLUGIN_PATH"].split(os.pathsep)
    finally:
        monkeypatch.undo()
        plugin.plugins(refresh=True)


def test_the_commands_the_agent_steps_print_work_from_any_folder(tmp_path, monkeypatch, capsys):
    from sports_video_coach import guide, scaffold
    ws = tmp_path / "ws"
    scaffold.scaffold("rowing", ws / "plugins")         # new-plugin's default place; the run's workspace is another
    unit = ws / "analysis" / "rowing" / "2026-01-01"
    (unit / "run" / "review").mkdir(parents=True)
    (unit / "analysis.json").write_text(json.dumps({"plugin": "rowing", "video": "v.mp4"}), encoding="utf8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delitem(sys.modules, "svc_plugin_rowing", raising=False)
    try:
        assert "rowing" not in plugin.plugins(refresh=True)
        assert guide.main(["review", "--unit", str(unit), "--path"]) == 0
        assert capsys.readouterr().out.strip() == (ws / "plugins" / "rowing" / "prompts" / "review.md").resolve().as_posix()
        plugin._EXTRA.clear()
        plugin.plugins(refresh=True)
        assert cli.resolve("rowing:review-check", None, [str(unit)])[1] == "rowing:review-check"
        with pytest.raises(SystemExit):
            guide.main(["review", "--unit", str(elsewhere)])     # no unit there
    finally:
        monkeypatch.undo()
        plugin.plugins(refresh=True)


def test_the_run_echo_is_the_command_that_runs(capsys):
    class G:
        PLUGIN = "rowing"
    step = pipeline.Step("strokes", "cmd", lambda g: False, lambda g: [["strokes", "v.mp4", "--out", "o"]])
    seen = []
    assert pipeline.run_cmd(step, G(), runner=lambda cmd, **kw: seen.append(cmd) or type("R", (), {"returncode": 0}))
    assert "[run] strokes: sports-video-coach rowing:strokes v.mp4 --out o" in capsys.readouterr().out
    assert seen[0][3:] == ["rowing:strokes", "v.mp4", "--out", "o"]
    assert pipeline.shown(["frames", "v.mp4"], "rowing") == "sports-video-coach frames v.mp4"   # a core stage: bare
