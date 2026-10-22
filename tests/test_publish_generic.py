"""Core publish without any sport: a report folder no plugin owns, and reports of several plugins on one hub."""
import json
import sys

import pytest

from sports_video_coach import plugin, publish

TENNIS = '''from pathlib import Path
from sports_video_coach.plugin import Kind, Plugin
from sports_video_coach.publish import SiteHooks
PLUGIN = Plugin(name="tennis", summary="test plugin", kinds=[Kind("match", "match.json")],
                site=SiteHooks(hidden=lambda f: f.name == "private",
                               group=lambda f: "final" if f.name.startswith("final") else None,
                               groups=("final",), ui={"en": {"title": "Tennis", "final": "Final"}}))
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else json.dumps(text), encoding="utf8")


def registry(ws):
    return json.loads((ws / "publish.json").read_text(encoding="utf8"))


def hub_of(ws):
    return (ws / "site" / registry(ws)["hub"] / "index.html").read_text(encoding="utf8")


def test_report_no_plugin_owns_gets_a_stable_link_on_the_hub(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    folder = tmp_path / "notes" / "player-3"       # a basketball-looking name means nothing without the plugin
    write(folder / "README.md", "# Swim drills\n\nKick from the hips.\n")
    assert plugin.owner(folder) is None and publish.hooks_for(folder) is publish.DEFAULT
    publish.main([str(folder)])
    reg = registry(tmp_path)
    tok = reg["reports"]["notes/player-3"]
    assert "Kick from the hips" in (tmp_path / "site" / tok / "index.html").read_text(encoding="utf8")
    hub = hub_of(tmp_path)
    assert f"../{tok}/" in hub and "Swim drills" in hub and "<small>player-3</small>" in hub
    assert "<title>报告</title>" in hub and "赛季" not in hub and "比赛" not in hub
    assert reg["programs"] == {}
    publish.main([str(folder)])                    # re-publishing keeps the link
    assert registry(tmp_path)["reports"]["notes/player-3"] == tok


def test_folder_without_app_hooks_is_not_an_app(tmp_path):
    write(tmp_path / "plan" / "README.md", "# Plan\n")
    assert not publish.is_program(tmp_path / "plan")
    with pytest.raises(SystemExit):
        publish.build_program(tmp_path / "plan", tmp_path / "out")


@pytest.fixture
def tennis(tmp_path, monkeypatch):
    d = tmp_path / "plugins" / "tennis"
    write(d / "__init__.py", TENNIS)
    monkeypatch.setenv("SVC_PLUGIN_PATH", str(d.parent))
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    for m in [m for m in sys.modules if m.startswith("svc_plugin_")]:
        monkeypatch.delitem(sys.modules, m)
    plugin.plugins(refresh=True)
    yield tmp_path / "ws"
    monkeypatch.undo()
    plugin.plugins(refresh=True)


def test_each_report_uses_its_own_plugins_hooks(tennis):
    ws = tennis
    game = ws / "teams" / "owls" / "2026-01-02"
    write(game / "game.json", {"us": "A", "them": "Owls", "date": "2026-01-02"})
    write(game / "README.md", "# Owls\n")
    write(game / "player-4" / "README.md", "# Four\n")
    match, private, final = ws / "tennis" / "2026-01-03", ws / "tennis" / "private", ws / "tennis" / "final-2026"
    for f, title in ((match, "Match"), (private, "Secret"), (final, "Final day")):
        write(f / "match.json", {})
        write(f / "README.md", f"# {title}\n")
    other = ws / "misc" / "player-9"
    write(other / "README.md", "# Misc\n")
    assert publish.hooks_for(match).groups and publish.hooks_for(game).groups != publish.hooks_for(match).groups
    publish.main([str(f) for f in (game, game / "player-4", match, private, final, other)])
    reg, hub = registry(ws), hub_of(ws)
    on = {k: f"../{t}/" in hub for k, t in reg["reports"].items()}
    assert on == {"teams/owls/2026-01-02": True, "teams/owls/2026-01-02/player-4": False,
                  "tennis/2026-01-03": True, "tennis/private": False, "tennis/final-2026": True,
                  "misc/player-9": True}
    assert 'class="final"' in hub and "Final final-2026" in hub
    assert hub.index(reg["reports"]["tennis/final-2026"]) < hub.index(reg["reports"]["tennis/2026-01-03"])
