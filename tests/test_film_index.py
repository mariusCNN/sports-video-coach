"""Shot chart and playlists from reviewed trips (film_index), their clips and publishing them."""
import json
import shutil
from pathlib import Path

from sports_video_coach import clips

from hoop_tape_miner import film_index
from sports_video_coach import publish, render_html

FIXTURE = Path(__file__).parent / "fixtures" / "report_min"   # periods [[0, 600], [700, 1300]], us 4 / 7, them 11


def trip(pid, offence, result, **kw):
    t = {"schema": 2, "pid": pid, "offence": offence, "result": result, "confidence": "medium", "t0": pid * 20.0,
         "t1": pid * 20.0 + 15, "shot": None, "fts": None, "foul": None, "evidence": {}}
    t.update(kw)
    return t


def shot(t, shooter, made, zone, points=None, **kw):
    return {"t": t, "shooter": shooter, "made": made, "points": points, "zone": zone, "type": kw.get("type", "layup"),
            "contested": kw.get("contested", "open"), **({"xy": kw["xy"]} if "xy" in kw else {})}


TRIPS = [
    trip(1, "us", "made2", shot=shot(30.0, "4", True, "rim", 2), evidence={"result": [30.0], "shot": [30.0]}),
    trip(2, "us", "missed", shot=shot(None, "7", False, "three"), evidence={"result": [62.0], "shot": [61.5, 62.0]}),
    trip(3, "us", "unclear", shot=shot(None, "4", None, "midrange"), key_clip={"t0": 90, "t1": 96}),   # no time
    trip(4, "them", "made3", shot=shot(750.0, "11", True, "three", 3), evidence={"result": [750.0], "shot": [750.0]},
         transition=True),
    trip(5, "us", "turnover", evidence={"result": [800.0]}, turnover_kind="live"),
    trip(6, "us", "turnover", evidence={"result": [900.0]}, turnover_kind="dead"),
    trip(7, "them", "foul_side", foul={"t": 1000.0, "by_team": "us", "by": "7", "on": "11", "type": "reach_in",
                                       "led_to": "side-out"}, evidence={"result": [1000.0], "foul": [1000.0]}),
    trip(8, "us", "missed", shot=shot(1100.0, None, False, None), evidence={"result": [1100.0], "shot": [1100.0]},
         oreb_crash={"n": 2, "got": "us"}),
]


def game_folder(tmp_path, trips=TRIPS, cut=True):
    folder = tmp_path / "game"
    shutil.copytree(FIXTURE, folder)
    review = folder / "run" / "review_v1"
    review.mkdir(parents=True)
    (review / "coach_part1.json").write_text(json.dumps(trips), encoding="utf8")
    (folder / "player-4").mkdir()
    for name in ("README.md", "README.en.md"):
        (folder / "player-4" / name).write_text(f"# #4\n\nText.\n", encoding="utf8")
    if cut:
        for d in (folder, folder / "player-4"):
            for a, b in clips.find_clips(d):
                p = clips.clip_path(d, a, b)
                p.parent.mkdir(exist_ok=True)
                p.write_bytes(b"fake mp4")
                p.with_suffix(".jpg").write_bytes(b"fake jpg")
    return folder


def test_events_take_times_from_the_trip_and_never_guess_outcomes():
    evs = film_index.events(TRIPS, [[0, 600], [700, 1300]])
    shots = [e for e in evs if e.kind == "shot"]
    assert [(e.player, e.t, e.half, e.made) for e in shots] == [
        ("4", 30.0, 1, True), ("7", 61.5, 1, False), ("11", 750.0, 2, True), (None, 1100.0, 2, False), ("4", None, None, None)]
    first = shots[0]
    assert first.window == ("00:24", "00:32") and first.pts == 2
    assert shots[-1].window == ("01:29", "01:37")  # no time: the v1 key_clip window, padded by 1 s
    assert shots[2].tags == {"transition"} and shots[2].pts == 3
    tos = [e for e in evs if e.kind == "turnover"]
    assert [sorted(e.tags) for e in tos] == [["live"], ["dead"]]
    foul = next(e for e in evs if e.kind == "foul")
    assert (foul.team, foul.player, foul.on, foul.window) == ("us", "7", "11", ("16:36", "16:42"))
    assert [e.t for e in evs if e.kind == "oreb"] == [1100.0]


def test_events_tolerate_trips_without_the_optional_fields():
    plain = [trip(1, "us", "turnover"), trip(2, "them", "missed", shot={"made": False}), "junk"]
    evs = film_index.events(plain, None)
    assert [(e.kind, e.window, e.half, e.tags) for e in evs] == [("turnover", None, None, set()), ("shot", None, None, set())]


def test_zone_stats_leave_unclear_outcomes_out_of_points_per_shot():
    evs = [e for e in film_index.events(TRIPS) if e.kind == "shot" and e.team == "us"]
    st = film_index.zone_stats(evs)
    assert st["rim"] == dict(att=1, made=1, missed=0, unknown=0, pts=2, pps=2.0)
    assert st["midrange"] == dict(att=1, made=0, missed=0, unknown=1, pts=0, pps=None)
    assert st[None]["missed"] == 1 and st["three"]["pps"] == 0.0


def test_team_page_playlists_per_player_and_theme(tmp_path):
    ix = film_index.index(game_folder(tmp_path, cut=False))
    keys = {p.key: p for p in ix["playlists"]}
    assert list(keys) == ["p4", "p7", "live", "turnovers", "fouls", "transition", "their-scores", "oreb"]
    assert [e.kind for e in keys["p7"].items] == ["shot", "foul"]
    assert len(keys["live"].items) == 1 and len(keys["turnovers"].items) == 2
    assert keys["transition"].title == {"zh": "转换防守", "en": "Transition defence"}
    assert len(ix["shots"]) == 5  # both teams on the team page


def test_live_ball_playlist_only_when_trips_carry_turnover_kind(tmp_path):
    plain = [{k: v for k, v in t.items() if k not in ("turnover_kind", "transition")} for t in TRIPS]
    keys = [p.key for p in film_index.index(game_folder(tmp_path, plain, cut=False))["playlists"]]
    assert "live" not in keys and "transition" not in keys and "turnovers" in keys


def test_playlists_are_capped(tmp_path):
    many = [trip(i, "us", "missed", shot=shot(10.0 * i, "4", False, "rim"), evidence={"result": [10.0 * i], "shot": [10.0 * i]})
            for i in range(1, film_index.MAX_PLAYLIST + 6)]
    pl = film_index.index(game_folder(tmp_path, many, cut=False))["playlists"][0]
    assert len(pl.items) == film_index.MAX_PLAYLIST and pl.total == film_index.MAX_PLAYLIST + 5


def test_player_page_shows_only_the_focus_player(tmp_path):
    ix = film_index.index(game_folder(tmp_path, cut=False) / "player-4")
    assert ix["focus"] == "4" and {e.player for e in ix["shots"]} == {"4"}
    assert [p.key for p in ix["playlists"]] == ["p-shots"]


def test_no_review_means_no_sections():
    assert film_index.index(FIXTURE) is None and clips.find_clips(FIXTURE) == []
    assert film_index.sections(FIXTURE, "zh", False, 1) == ("", [])


def test_clips_stage_includes_chart_and_playlist_windows(tmp_path):
    folder = game_folder(tmp_path, cut=False)
    (folder / "README.md").write_text("# r\n\n![x](clip:00:24-00:32)\n", encoding="utf8")
    found = clips.find_clips(folder)
    assert found[0] == ("00:24", "00:32") and found.count(("00:24", "00:32")) == 1   # shared with the chart, cut once
    assert ("12:24", "12:32") in found and ("13:15", "13:22") in found               # their three, our live-ball TO
    assert clips.find_clips(folder, film=False) == [("00:24", "00:32")]


def test_page_renders_clickable_chart_and_playlists(tmp_path):
    folder = game_folder(tmp_path)
    page = render_html.page(folder)
    for lang, chart, lists in (("zh", "投篮分布", "片段合集"), ("en", "Shot chart", "Playlists")):
        assert f'>{chart}</h2>' in page and f'>{lists}</h2>' in page
        assert f'href="#{lang}-s3">{chart}</a>' in page   # in the contents
    assert page.count("<svg class=\"fi-court\"") == 2
    assert 'data-src="clips/0024-0032.mp4" data-poster="clips/0024-0032.jpg"' in page
    assert 'data-made="u"' in page and "make/miss unclear" in page and "进没进看不清" in page
    assert '<option value="us:4">#4</option>' in page and '<option value="them:11" hidden>#11</option>' in page
    assert 'id="en-pl-live"' in page and 'class="film-lists"' in page and page.count("data-film-chart data-lang-code") == 2


def test_page_without_cut_clips_has_dots_but_no_links(tmp_path):
    page = render_html.page(game_folder(tmp_path, cut=False))
    assert "fi-court" in page and 'data-src="' not in page and 'class="film-lists"' not in page


def test_share_file_keeps_the_chart_without_clips(tmp_path):
    page = render_html.page(game_folder(tmp_path), share=True)
    assert "fi-court" in page and 'data-src="' not in page and 'class="film-lists"' not in page
    assert "On the published link every shot opens its clip." in page


def test_publish_copies_chart_and_playlist_clips(tmp_path):
    folder = game_folder(tmp_path)
    dest = tmp_path / "site" / "tok"
    assert publish.build_report(folder, dest) == []
    for a, b in clips.find_clips(folder):
        name = clips.clip_name(a, b)
        assert (dest / "clips" / f"{name}.mp4").is_file() and (dest / "clips" / f"{name}.jpg").is_file()
    player = publish.build_report(folder / "player-4", tmp_path / "site" / "p4")
    assert player == [] and (tmp_path / "site" / "p4" / "clips" / "0024-0032.mp4").is_file()


def test_half_written_review_does_not_stop_the_readme_clips(tmp_path, capsys):
    folder = game_folder(tmp_path, cut=False)
    (folder / "run" / "review_v1" / "coach_part2.json").write_text("", encoding="utf8")
    (folder / "README.md").write_text("# r\n\n![x](clip:00:24-00:32)\n", encoding="utf8")
    assert clips.find_clips(folder) == [("00:24", "00:32")]
    assert "warning: no shot chart" in capsys.readouterr().out


def test_zone_heat_and_labels():
    st = film_index.zone_stats([film_index.Event("shot", "us", "4", 1.0, 1, None, zone="rim", made=m)
                                for m in (True, False, False, None)])
    assert film_index.heat(st["rim"]) == "h-1"                  # 2 pts / 3 known shots = 0.67: cold step
    assert film_index.heat(st["three"]) == "hna"                # no shots: grey
    assert film_index.label("rim", st["rim"], "zh") == ("1/3", "33% · 不明 1")
    assert film_index.label("three", st["three"], "en") == ("–", "")
    hot = film_index.zone_stats([film_index.Event("shot", "us", "4", 1.0, 1, None, zone="three", made=True)] * 3)
    assert film_index.heat(hot["three"]) == "h2"


def test_chart_has_zone_labels_and_shot_chips(tmp_path):
    page = render_html.page(game_folder(tmp_path))
    assert page.count("<g class=\"fi-label") - page.count("<g class=\"fi-labels") == 8 and 'class="fi-chips"' in page
    assert "fi-unzoned" not in page and "<circle cx=\"75\" cy=\"15.75\" r=\"2.25\"/>" in page


def test_located_shots_get_a_mark_at_the_nearer_basket(tmp_path):
    assert film_index.spot([26.0, 7.5]) == (75.0, 20.0)          # 2 m in front of the right basket
    assert film_index.spot([2.0, 7.5]) == (75.0, 20.0)           # same spot at the left basket
    assert film_index.spot([27.5, 0.5]) == (145.0, 5.0)          # right corner, near sideline: far side of the chart
    assert film_index.spot(None) is None and film_index.spot(["a", 1]) is None
    page = render_html.page(game_folder(tmp_path / "a"))
    assert "<g class=\"fi-spots" not in page and "class=\"fi-loc\"" not in page   # nothing located: no layer/note
    trips = [dict(t, shot=dict(t["shot"], xy=[26.0, 7.5])) if t["pid"] == 1 else t for t in TRIPS]
    page = render_html.page(game_folder(tmp_path / "b", trips))
    assert page.count('<g class="fi-spot ') == page.count('<g class="fi-spots">') >= 1 and 'class="fi-spot us m1" data-k="0"' in page
    assert 'class="fi-loc"' in page and "1 / 4" in page          # our 4 shots, one located
