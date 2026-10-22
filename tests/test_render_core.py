"""The page renderer lives in the core; basketball adds its bands and sections through PageHooks."""
import json
import shutil
from pathlib import Path

from hoop_tape_miner import page_hooks
from sports_video_coach import plugin, render_html

FIXTURE = Path(__file__).parent / "fixtures" / "report_min"
# page(FIXTURE) rendered by hoop_tape_miner.render_html before it moved into the core (commit 65734f0).
GOLDEN = Path(__file__).parent / "fixtures" / "report_min.page.html"


def test_basketball_page_is_byte_identical_to_the_pre_move_renderer():
    assert render_html.page(FIXTURE) == GOLDEN.read_text(encoding="utf8").replace("\r\n", "\n")


def test_basketball_plugin_registers_its_page_hooks():
    own = plugin.owner(FIXTURE)
    assert own[0].name == "basketball" and own[0].page is page_hooks.PAGE
    assert render_html.hooks_of(FIXTURE)[0] is page_hooks.PAGE


def test_player_sub_report_uses_the_game_hooks(tmp_path):  # player-<N> resolves to its game (Kind.levels)
    game = tmp_path / "game"
    shutil.copytree(FIXTURE, game)
    me = game / "player-4"
    me.mkdir()
    (me / "README.en.md").write_text("# Player 4\n\n## Shots\n\nok\n", encoding="utf8")
    assert render_html.hooks_of(me)[0] is page_hooks.PAGE
    page = render_html.page(me)
    assert "Example Owls" in page and 'data-result="win"' in page


def _generic(folder: Path, json_data: dict | None) -> Path:
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("# 发球练习\n\n## 要点\n\n- 抛球稳定\n", encoding="utf8")
    (folder / "README.en.md").write_text("# Serve practice\n\n## Key points\n\n- Steady toss\n", encoding="utf8")
    if json_data is not None:
        (folder / "analysis.json").write_text(json.dumps(json_data), encoding="utf8")
    return folder


def test_folder_no_plugin_owns_gets_the_plain_band(tmp_path):
    for i, data in enumerate((None, {"plugin": "generic", "date": "2025-03-16", "sport": "tennis"})):
        folder = _generic(tmp_path / f"u{i}" / "2025-03-15", data)
        assert render_html.hooks_of(folder)[0] is render_html.DEFAULT
        page = render_html.page(folder)
        assert 'data-result="plain"' in page and "Serve practice" in page and "发球练习" in page
        # no json: the dated folder name; an analysis.json the generic plugin owns: its own date and sport
        assert ("2025-03-15" if data is None else "tennis · 2025-03-16") in page
        for basketball in ("factors", "fi-", "data-result=\"win\"", "Four Factors", "我们", "1st half"):
            assert basketball not in page
        assert f"--us: {render_html.DEFAULT_COLOURS['us'][0]};" in page
        assert 'id="en-s1">Key points</h2>' in page


def test_default_board_shows_date_and_sport():
    sb = render_html.default_board(Path("x"), {"date": "2025-03-16", "sport": "tennis"}, "generic", "<span>T</span>")
    band = render_html.default_band(sb, lambda k: k)
    assert "<span>T</span>" in band and "tennis · 2025-03-16" in band


def test_plugin_hooks_fall_back_per_field(tmp_path, monkeypatch):
    folder = _generic(tmp_path / "f", None)
    hooks = render_html.PageHooks(sections=lambda f, lang, embed, first: (
        f'<h2 id="{lang}-s{first}">Extra</h2>', ["Extra"], "<!--assets-->"))
    monkeypatch.setattr(render_html, "hooks_of", lambda f: (hooks, "demo", {}))
    page = render_html.page(folder)
    assert 'data-result="plain"' in page and 'id="en-s2">Extra</h2>' in page
    assert page.count("<!--assets-->") == 1 and 'href="#en-s2">Extra</a>' in page
