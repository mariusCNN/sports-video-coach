"""The per-player table: league points and fouls, plus-minus from the lineups, film-counted rebounds / assists / steals."""
import json
import os
import shutil
from pathlib import Path

import pytest

from hoop_tape_miner import box
from sports_video_coach import render_html

FIXTURE = Path(__file__).parent / "fixtures" / "report_min"

OFFICIAL = {"players": {"us": {"17": {"PTS": 3, "PF": 2}, "10": {"PTS": 9, "PF": 4}, "3": {"PTS": 0, "PF": 0}}}}
PM = {"us#17": {"on": {"seconds": 905, "for": 13, "against": 20, "net": -7}},
      "us#10": {"on": {"seconds": 330, "for": 9, "against": 7, "net": 2}}}
BOX = {"events": [{"t": 50, "kind": "reb", "team": "us", "who": "17"},
                  {"t": 60, "kind": "reb", "team": "us", "who": None},
                  {"t": 70, "kind": "reb", "team": "them", "who": None},
                  {"t": 80, "kind": "ast", "team": "us", "who": "17"},
                  {"t": 90, "kind": "stl", "team": "us", "who": "10"}]}


def _team_folder(tmp_path, with_box=True):
    folder = tmp_path / "game"
    shutil.copytree(FIXTURE, folder)
    run = tmp_path / "run"
    (run / "review_v1").mkdir(parents=True)
    (run / "review_v1" / "plusminus.json").write_text(json.dumps(PM), encoding="utf8")
    game = json.loads((folder / "game.json").read_text(encoding="utf8"))
    game["run"] = str(run)
    (folder / "game.json").write_text(json.dumps(game), encoding="utf8")
    (run / "official.json").write_text(json.dumps(OFFICIAL), encoding="utf8")
    if with_box:
        (folder / "box.json").write_text(json.dumps(BOX), encoding="utf8")
    return folder


def test_rows_join_league_lineups_and_film_and_skip_players_never_seen(tmp_path):
    data, unclear = box.rows(_team_folder(tmp_path))
    assert [r["num"] for r in data] == ["10", "17"]  # by points; #3 has nothing recorded and was never seen
    r17 = data[1]
    assert (r17["pts"], r17["pf"], r17["reb"], r17["ast"], r17["stl"], r17["pm"], r17["seen_s"]) == (3, 2, 1, 1, 0, -7, 905)
    assert unclear == {"reb": 1, "ast": 0, "stl": 0}  # their rebound is not ours to count


def test_without_box_json_the_film_columns_are_unknown_not_zero(tmp_path):
    data, unclear = box.rows(_team_folder(tmp_path, with_box=False))
    assert all(r["reb"] is None and r["ast"] is None for r in data) and unclear == {}
    page = box.table_html(_team_folder(tmp_path / "b", with_box=False))
    assert "<td>–</td>" in page


def test_team_page_shows_the_table_with_its_legend_in_both_languages(tmp_path):
    page = render_html.page(_team_folder(tmp_path))
    assert page.count('class="box"') == 2 and "每人数据" in page and "Player numbers" in page
    assert "看不清是谁" in page and "联赛官方记录" in page and "正负值" in page
    assert '<td class="neg">-7<small>15:05</small></td>' in page
    zh = page[page.index('<article class="report" data-lang="zh"'):]
    assert zh.index('class="box"') < zh.index('id="zh-s1"')


@pytest.mark.parametrize("source", ["box.json", "official.json", "run/official.json", "run/review_v1/plusminus.json"])
def test_player_numbers_follow_changed_and_new_sources(tmp_path, source):
    from sports_video_coach import pipeline as P
    folder = _team_folder(tmp_path)
    unit = P.Unit(folder, json.loads((folder / "game.json").read_text(encoding="utf8")))
    step = next(s for s in P.tail_steps(lambda g: None, "", "", "") if s.name == "html")
    store = P.Store(folder)
    render_html.main([str(folder)])
    P.record(step, unit, store)
    assert P.html_done(unit) and not P.changes(step, unit, store)
    path = (tmp_path if source.startswith("run/") else folder) / source
    content = BOX if source == "box.json" else PM if source.endswith("plusminus.json") else OFFICIAL
    path.write_text(json.dumps(content, indent=2), encoding="utf8")
    later = (folder / "index.html").stat().st_mtime + 10
    os.utime(path, (later, later))
    assert path in P.html_inputs(unit)
    assert P.changes(step, unit, store) and not P.html_done(unit)


def test_relative_run_is_resolved_from_the_game_folder(tmp_path, monkeypatch):
    from hoop_tape_miner import page_hooks
    folder = _team_folder(tmp_path)
    game = json.loads((folder / "game.json").read_text(encoding="utf8"))
    game["run"] = "../run"
    (folder / "game.json").write_text(json.dumps(game), encoding="utf8")
    monkeypatch.chdir(tmp_path)
    assert box.rows(Path("game"))[0][1]["pm"] == -7
    assert tmp_path / "run" / "review_v1" / "summary.json" in page_hooks.PAGE.inputs(folder)


@pytest.mark.parametrize("bad", ['{', '[]', '{"events": {}}', '{"events": [null]}'])
def test_invalid_film_counts_fail_instead_of_showing_missing_or_zero(tmp_path, bad, capsys):
    folder = _team_folder(tmp_path)
    (folder / "box.json").write_text(bad, encoding="utf8")
    with pytest.raises(SystemExit, match="box.json"):
        box.rows(folder)
    try:
        code = box.main([str(folder)])
    except SystemExit as e:
        assert "box.json" in str(e)
    else:
        assert code == 1
    assert "# 17 pts" not in capsys.readouterr().out


def test_candidate_preserves_a_shot_at_video_start():
    trip = {"t0": 0, "t1": 10, "offence": "us", "result": "missed", "shot": {"t": 0, "made": False}}
    assert box.candidates([trip])[0]["t"] == 0


def test_check_flags_bad_entries_and_candidates_come_from_the_trips():
    assert box.check({"events": [{"kind": "blk", "team": "us", "who": "7"},
                                 {"kind": "reb", "team": "x", "who": 7}]}) == [
        "events[0]: kind must be one of reb, ast, stl", "events[1]: team must be us or them",
        "events[1]: who must be a jersey string like \"13\" or null"]
    trips = [{"t0": 0, "t1": 10, "offence": "us", "result": "missed", "shot": {"t": 8, "made": False},
              "oreb_crash": {"got": "us"}},
             {"t0": 10, "t1": 20, "offence": "us", "result": "made2", "shot": {"t": 18, "made": True, "shooter": "9"}},
             {"t0": 20, "t1": 30, "offence": "them", "result": "turnover", "turnover_kind": "live"},
             {"t0": 30, "t1": 40, "offence": "us", "result": "missed", "shot": {"t": None}},
             {"t0": 40, "t1": 50, "offence": "them", "result": "turnover", "turnover_kind": "dead"},
             {"t0": 50, "t1": 60, "offence": "them", "result": "made2"}]
    c = box.candidates(trips)
    assert [(e["kind"], e["team"], e["t"]) for e in c] == [("reb", "us", 8), ("ast", "us", 18), ("stl", "us", 20 + 10),
                                                           ("reb", "them", 40)]
    assert "scorer 9" in c[1]["note"]
