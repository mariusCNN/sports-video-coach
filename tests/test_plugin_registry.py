import json
import sys

import pytest

from sports_video_coach import cli, pipeline, plugin, units

LOCAL = '''from sports_video_coach.plugin import Kind, Plugin
PLUGIN = Plugin(name="{name}", summary="test plugin", stages={{"fetch": ("json", "same name as basketball"),
                                                              "serve": ("json", "only here")}},
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
    assert cli.resolve("serve") == ("json", "serve")      # unique across plugins
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
    assert "not usable in this install: needs no_such_pkg_xyz (clone and uv sync)" in capsys.readouterr().out
    cli.list_plugins(["--json"])
    row = json.loads(capsys.readouterr().out)["plugins"][0]
    assert row["missing"] == ["no_such_pkg_xyz"] and row["install"] == "clone and uv sync"


def test_a_stage_that_needs_a_missing_package_exits_with_a_hint(monkeypatch):
    def stage(argv):
        raise ModuleNotFoundError("No module named 'pandas'", name="pandas")
    monkeypatch.setattr(cli, "resolve", lambda stage, default: ("fake_stage_mod", "html"))
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
    assert "[run] plugin swimming matches --sport Swimming; --plugin generic" in capsys.readouterr().out
    assert run.for_sport(["v.mp4", "--sport=swimming"]).name == "swimming"
    assert run.for_sport(["v.mp4", "--sport", "tennis"]).name == "generic"
    assert run.for_sport(["v.mp4"]).name == "generic"
