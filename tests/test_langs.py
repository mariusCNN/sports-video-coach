"""The language registry (langs.py) and the stages that read it: Japanese end to end, unknown codes refused."""
import json
import shutil

import pytest

from sports_video_coach import film, langs as L, media, narrate as N, page_check, pipeline as P, render_html, run
from sports_video_coach.plugins.generic import new


def test_registry_lookups():
    assert L.CODES[:2] == ("zh", "en") and {"ja", "ko", "es", "fr", "de", "pt"} <= set(L.CODES)
    assert L.tag("zh") == "zh-CN" and L.tag("ja") == "ja" and L.tag("pt") == "pt-BR"
    assert L.readme("zh") == "README.md" and L.readme("ja") == "README.ja.md"
    assert L.cjk("ja") and L.cjk("ko") and not L.cjk("fr")
    assert L.ui("ja")["contents"] == "目次" and L.ui("ko") == L.UI_KO and L.ui("xx") == L.UI_EN  # unknown: English
    assert L.font("ja", "win32") == "Yu Gothic" and L.font("ja", "linux") == "Noto Sans CJK JP"
    assert L.font("zh") == film.FONT and L.font("es", "darwin") == "Helvetica Neue"
    assert L.film_tag("ja", "slow") == "スロー" and L.film_tag("xx", "freeze") == "Paused"
    assert L.count("こんにちは、世界。", "ja") == 7 and abs(L.read_s("あ" * 285, "ja") - 60) < 0.1
    with pytest.raises(L.Unknown, match="unknown language 'xx'.*ja"):
        L.get("xx")


def test_every_voice_speaks_its_own_language():
    for code, lang in L.LANGS.items():
        for voice in (lang.voice, lang.alt_voice):
            assert voice.split("-")[0] == code and voice.endswith("Neural"), voice
        assert N.voice_for(code) == (lang.voice, "+0%")
    with pytest.raises(L.Unknown, match="no voice for language 'xx'"):
        N.voice_for("xx")


def fake_speech(monkeypatch) -> list[str]:
    used = []

    async def speak(paras, voice, rate, tmp):
        used.append(voice)
        return []
    monkeypatch.setattr(N, "speak", speak)
    monkeypatch.setattr(N, "stitch", lambda parts, out, *a: out.write_bytes(b"mp3"))
    monkeypatch.setattr(N.media, "duration_s", lambda p: 1.0)
    return used


def test_narrate_script_reads_japanese_with_a_japanese_voice(tmp_path, monkeypatch, capsys):
    used = fake_speech(monkeypatch)
    (tmp_path / "listen.ja.md").write_text("約三分のレポートです。\n\n右肩が早く開いています。\n", encoding="utf8")
    N.main(["--script", str(tmp_path / "listen.ja.md")])
    assert used == ["ja-JP-KeitaNeural"] and (tmp_path / "listen.ja.mp3").exists()
    assert "rendering with ja-JP-KeitaNeural" in capsys.readouterr().out
    assert N.stated(["約三分のレポートです。"], "ja") == (180, False)
    assert N.stated(["1分半ほどです。"], "ja") == (90, False) and N.stated(["3分の1"], "ja") is None


def test_narrate_never_falls_back_to_another_languages_voice(tmp_path, monkeypatch):
    used = fake_speech(monkeypatch)
    (tmp_path / "listen.xx.md").write_text("Bonjour.\n", encoding="utf8")
    with pytest.raises(SystemExit, match="no voice for language 'xx'"):
        N.main(["--script", str(tmp_path / "listen.xx.md")])
    with pytest.raises(SystemExit):  # argparse: xx is not a choice
        N.main([str(tmp_path), "--lang", "xx"])
    assert used == []


def test_generic_new_and_run_accept_japanese():
    assert new.parser().parse_args(["v.mp4", "--lang", "ja", "en"]).lang == ["ja", "en"]
    with pytest.raises(SystemExit):
        new.parser().parse_args(["v.mp4", "--lang", "xx"])
    assert "--lang" in run.help_text("generic")


def test_run_with_lang_ja_asks_for_the_japanese_files(tmp_path, monkeypatch):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("needs ffmpeg")
    video = tmp_path / "swing.mp4"
    media.ffmpeg("-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10", "-pix_fmt", "yuv420p", video)
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    with pytest.raises(SystemExit) as e:
        run.main([str(video), "--plugin", "generic", "--lang", "ja"])
    assert e.value.code == P.WAITING
    [folder] = list((tmp_path / "ws" / "analysis").glob("*/*"))
    assert json.loads((folder / "analysis.json").read_text(encoding="utf8"))["languages"] == ["ja"]
    assert P.missing([folder / "listen.ja.md"], None) == [f"missing: {P.slash((folder / 'listen.ja.md').as_posix())} "
                                                          "(Japanese)"]


def test_profile_languages_take_every_registry_code_unless_a_plugin_limits_them(monkeypatch):
    monkeypatch.setattr(P.workspace, "profile", lambda: {"languages": ["ja", "en"]})
    assert P.profile_langs() == ("ja", "en")
    with pytest.raises(SystemExit, match="not supported"):
        P.profile_langs(P.LANGS)   # basketball: zh and en only


def test_lang_on_a_later_run_replaces_the_unit_languages(tmp_path, monkeypatch, capsys):
    """An existing unit adds a language with `run <folder> --lang`, as with --artifacts; a wrong code is a usage
    error and writes nothing."""
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    folder = tmp_path / "a"
    folder.mkdir()
    aj = folder / "analysis.json"
    aj.write_text(json.dumps({"plugin": "generic", "sport": "tennis", "languages": ["en"]}), encoding="utf8")
    assert run.drive_unit(folder, ["--lang", "en", "zh", "--status"]) == 0
    assert json.loads(aj.read_text(encoding="utf8"))["languages"] == ["en", "zh"]
    assert "[run] languages in analysis.json: en, zh" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        run.drive_unit(folder, ["--lang", "xx"])
    assert e.value.code == 2 and json.loads(aj.read_text(encoding="utf8"))["languages"] == ["en", "zh"]
    assert "--lang LANG" in run.help_text() and "[--lang LANG ...]" in run.HELP


def test_lang_on_a_basketball_game_keeps_its_zh_en_limit(tmp_path, monkeypatch, capsys):
    from hoop_tape_miner import run as R
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    game = tmp_path / "teams" / "red-foxes" / "2025-03-08"
    (game / "run").mkdir(parents=True)
    gj = game / "game.json"
    gj.write_text(json.dumps({"video": "v.mp4", "periods": [[0, 60]], "us": {"team": "A"}, "them": {"team": "B"}}),
                  encoding="utf8")
    with pytest.raises(SystemExit) as e:
        run.drive_unit(game, ["--lang", "en", "ja"])
    assert e.value.code == 2 and "languages" not in json.loads(gj.read_text(encoding="utf8"))
    run.drive_unit(game, ["--lang", "en", "--status"])
    assert R.Game.load(game).langs == ("en",)    # the game json wins over the profile's zh + en


def test_language_switch_names_every_language_in_its_own_words(tmp_path):
    assert {c: l.button for c, l in L.LANGS.items()} == {
        "zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어", "es": "Español", "fr": "Français",
        "de": "Deutsch", "pt": "Português"}   # no mix of names and codes (한국어 beside EN)
    assert L.ui("ko")["slow"] == "느리게"
    (tmp_path / "README.ko.md").write_text("# 스윙\n\n![클립](clip:00:01-00:05)\n", encoding="utf8")
    (tmp_path / "README.en.md").write_text("# Swing\n", encoding="utf8")
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "0001-0005.mp4").write_bytes(b"")
    page = render_html.page(tmp_path)
    assert ">한국어</button>" in page and ">English</button>" in page and "느리게 ½×" in page


def test_page_in_japanese(tmp_path):
    (tmp_path / "README.ja.md").write_text("# スイングの見直し\n\n## 続けること\n\n構えは安定しています。\n", encoding="utf8")
    page = render_html.page(tmp_path)
    assert page.startswith('<!doctype html>\n<html lang="ja"') and 'lang="ja"' in page
    assert "目次" in page and '<button type="button" data-set-lang' not in page   # one language: no switch
    assert '.report[lang="ja"] h2' in page and '"Noto Sans JP"' in page
    (tmp_path / "README.md").write_text("# 挥杆复盘\n\n## 继续保持\n\n站姿很稳。\n", encoding="utf8")
    page = render_html.page(tmp_path)
    assert '<html lang="zh-CN"' in page and 'data-set-lang="ja" lang="ja"' in page and ">日本語</button>" in page
    assert render_html.sport_names("tennis", ("zh", "ja", "en")) == {"zh": "网球", "ja": "テニス", "en": "Tennis"}
    assert render_html.sport_names("テニス", ("ja", "en")) == {"ja": "テニス", "en": "Tennis"}


def test_common_sports_have_names_in_every_language_with_a_table():
    both = ("fr", "es", "de", "pt", "ko", "en")
    assert render_html.sport_names("volleyball", both) == {"fr": "Volley-ball", "es": "Voleibol", "de": "Volleyball",
                                                           "pt": "Vôlei", "ko": "배구", "en": "Volleyball"}
    assert render_html.sport_names("Natation", ("fr", "en")) == {"fr": "Natation", "en": "Swimming"}  # own name in
    for code in ("zh", "ja", "ko", "es", "fr", "de", "pt"):
        assert set(L.LANGS[code].sports) == set(L.SPORTS_EN) and all(L.LANGS[code].sports.values())
    assert render_html.sport_names("shuttle run", ("fr", "en")) == {"fr": "Shuttle run", "en": "Shuttle run"}
    assert render_html.sport_names({"fr": "Navette", "en": "shuttle run"}, ("fr", "en"))["fr"] == "Navette"
    given = render_html.sport_names({"fr": "Volley", "en": "volleyball"}, ("fr", "de", "en"))  # --sport-name wins
    assert given == {"fr": "Volley", "de": "Volleyball", "en": "Volleyball"}


def test_report_guide_writes_dates_as_the_page_header_does():
    from sports_video_coach.plugins.generic.unit import PROMPTS
    guide = (PROMPTS / "report.md").read_text(encoding="utf8")
    assert "<date>" not in guide.split("## Rules")[0]                     # the header shows it: no date in the title
    for code in L.CODES:
        assert f"`{L.date('2026-10-23', code)}`" in guide, code


def test_every_language_has_its_own_page_labels_and_date():
    for code in L.CODES:
        assert set(L.ui(code)) == set(L.UI_EN), code
        assert code == "en" or L.ui(code)["listen"] != L.UI_EN["listen"], code
        assert "clips" in L.ui(code)["missing"]  # the stage name stays a command
    dates = {c: L.date("2026-10-23", c) for c in L.CODES}
    assert dates == {"zh": "2026年10月23日", "en": "23 Oct 2026", "ja": "2026年10月23日", "ko": "2026년 10월 23일",
                     "es": "23 oct 2026", "fr": "23 oct. 2026", "de": "23.10.2026", "pt": "23/10/2026"}
    assert L.date("2026-03-05", "de") == "05.03.2026" and L.date("2026-03-05", "es") == "5 mar 2026"
    assert L.date("session-a", "es") == "session-a" and L.date("2026-10-23", "xx") == "2026-10-23"


def test_latin_languages_get_a_latin_subtitle_font():
    for code in ("en", "es", "fr", "de", "pt"):
        assert L.font(code, "win32") == "Segoe UI" and L.font(code, "darwin") == "Helvetica Neue"
        assert L.font(code, "linux") == "DejaVu Sans"
    assert L.font("zh", "win32") == "Microsoft YaHei" and L.font("zh") == film.FONT  # Chinese keeps its CJK face
    assert L.font("zh", "linux") == "Noto Sans CJK SC" and L.font("ko", "win32") == "Malgun Gothic"


def test_spanish_page_has_spanish_labels_and_follows_the_unit_order(tmp_path, monkeypatch):
    monkeypatch.setattr(render_html, "duration_s", lambda p: 70.0)
    (tmp_path / "analysis.json").write_text(json.dumps({"languages": ["es", "en"], "date": "2026-10-23",
                                                        "sport": "tennis"}), encoding="utf8")
    (tmp_path / "README.es.md").write_text("# Dobles: la red\n\n## Qué mantener\n\n![El saque](clip:00:02-00:06)\n",
                                           encoding="utf8")
    (tmp_path / "README.en.md").write_text("# Doubles: the net\n\n## Keep\n\n![The serve](clip:00:02-00:06)\n",
                                           encoding="utf8")
    for c in ("es", "en"):
        (tmp_path / f"listen.{c}.mp3").write_bytes(b"x")
    page = render_html.page(tmp_path)
    assert page.startswith('<!doctype html>\n<html lang="es"')  # the unit's first language, as in film
    assert "Escucha el informe" in page and "Unos 1 min. Léelo" in page and "Índice" in page
    assert 'aria-label="Reproducir / pausa"' in page and 'aria-label="Cambiar idioma"' in page
    assert "23 oct 2026" in page and "23 Oct 2026" in page
    assert page.index('data-lang="es"') < page.index('data-lang="en"')
    assert page_check.foreign_labels(page) == []
    stale = page.replace("Escucha el informe", "Listen to the report").replace(
        'aria-label="Reproducir / pausa"', 'aria-label="Play / pause"')
    errs = page_check.foreign_labels(stale)
    assert len(errs) == 2 and all("English page label inside the Spanish part" in e for e in errs)
    assert "'Listen to the report'" in errs[0] or "'Listen to the report'" in errs[1]
    (tmp_path / "index.html").write_text(stale, encoding="utf8")
    assert any("Listen to the report" in e for e in page_check.problems(tmp_path))


def test_page_check_leaves_a_label_shared_by_both_languages():
    page = ('<html lang="de"><body><div data-lang="de"><span class="clip-no">Clip 1 · 00:02–00:06</span></div>'
            '<div data-lang="en" hidden><span>Clip 1 · 00:02–00:06</span><p>Clip 3 shows the serve.</p></div>'
            '<div data-lang="fr" hidden><span>Clip 2 · 00:04–00:08</span><p>Inhalt</p></div></body></html>')
    errs = page_check.foreign_labels(page)
    assert len(errs) == 2 and all("inside the French part" in e for e in errs)  # "Clip" is English and German


def test_film_wraps_japanese_subtitles():
    text = "インパクトの直前に右肩が早く開いてしまい、ボールが右に出やすくなっています。次の練習では、トップで一度止まりましょう。"
    pieces = film.chunks(text, film.MAX_CHARS["ja"])
    assert len(pieces) > 1 and all(len(p) <= film.MAX_CHARS["ja"] for p in pieces)
    lines = film.fit(pieces[0], 12)
    assert len(lines) > 1 and all(film.em_width(x) <= 12 for x in lines)
    assert film.SLOW_TAG["ja"] == "スロー" and film.FREEZE_TAG["ja"] == "一時停止"


def test_japanese_subtitles_break_after_a_particle_not_inside_a_word():
    text = "四球中四球、同じ方向へ飛び出しました"
    assert film.fit(text, 12) == ["四球中四球、同じ方", "向へ飛び出しました"]   # zh rules: cut where the width is
    assert film.fit(text, 12, "ja") == ["四球中四球、同じ方向へ", "飛び出しました"]
    lines = film.fit("インパクトの直前に右肩が早く開いてしまい、ボールが右に出やすくなっています。", 14, "ja")
    assert lines[:2] == ["インパクトの直前に", "右肩が早く開いてしまい、"] and all(film.em_width(x) <= 14 for x in lines)
    assert film.ja_score("へ", "飛") == 3 and film.ja_score("方", "向") == 0 and film.ja_score("ボ", "ー") == 0


def test_page_check_flags_english_left_in_a_japanese_or_french_report(tmp_path):
    (tmp_path / "index.html").write_text(
        '<article class="report" data-lang="ja" lang="ja"><p>右肩が開くのは likely です。</p>'
        '<p>次は keep your head still を意識。</p></article>'
        '<article class="report" data-lang="fr" lang="fr"><p>La balle part à droite, unclear.</p></article>'
        '<article class="report" data-lang="en" lang="en"><p>The shoulder likely opens early.</p></article>',
        encoding="utf8")
    warns = page_check.warnings(tmp_path)
    assert len(warns) == 2
    assert warns[0].startswith("2 English phrase(s) in the Japanese report") and "keep your head still" in warns[0]
    assert warns[1].startswith("1 English phrase(s) in the French report, e.g. 'unclear'")
