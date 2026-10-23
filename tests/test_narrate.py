"""narrate: paragraph split, the --tight silence trim (ffmpeg calls recorded, not run), TTS retries (mocked),
the stale-only rerun and the stated-length warning."""
from sports_video_coach import narrate as N


def test_paragraphs_drop_writer_notes():
    assert N.paragraphs("# note\nfirst  line\nsame para\n\nsecond") == ["first line same para", "second"]


def record_ffmpeg(monkeypatch):
    calls = []
    monkeypatch.setattr(N, "ffmpeg", lambda *a: calls.append(a))
    return calls


def concat_list(tmp_path):
    return (tmp_path / "list.txt").read_text(encoding="utf8")


def test_stitch_tight_trims_every_part(tmp_path, monkeypatch):
    calls = record_ffmpeg(monkeypatch)
    parts = [tmp_path / "p000.mp3", tmp_path / "p001.mp3"]
    N.stitch(parts, tmp_path / "out.mp3", tmp_path, gap=0.4, tight=True)
    trims = [c for c in calls if "-af" in c and "silenceremove" in c[c.index("-af") + 1]]
    assert len(trims) == 2
    listing = concat_list(tmp_path)
    assert "p000.trim.mp3" in listing and "p001.trim.mp3" in listing
    assert "p000.mp3'" not in listing


def test_stitch_without_tight_keeps_parts(tmp_path, monkeypatch):
    calls = record_ffmpeg(monkeypatch)
    N.stitch([tmp_path / "p000.mp3"], tmp_path / "out.mp3", tmp_path)
    assert not any("silenceremove" in " ".join(c) for c in calls)
    assert ".trim." not in concat_list(tmp_path)


def test_concat_list_quotes_paths_with_an_apostrophe(tmp_path, monkeypatch):
    record_ffmpeg(monkeypatch)
    part = tmp_path / "it's" / "p000.mp3"
    N.stitch([part], tmp_path / "out.mp3", tmp_path)
    assert "file '" + (tmp_path / "it").as_posix() + r"'\''s/p000.mp3'" in concat_list(tmp_path)


def test_ffprobe_has_a_timeout(tmp_path, monkeypatch):
    import subprocess
    from sports_video_coach import media
    from sports_video_coach import render_html
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n")
    monkeypatch.setattr(media.subprocess, "run", fake_run)  # render_html probes through media
    assert render_html.duration_s(tmp_path / "a.mp3") == 12.5
    assert seen.get("timeout") and seen.get("encoding") == "utf8"


def test_render_with_a_relative_unit_folder_runs_ffmpeg(tmp_path, monkeypatch):
    """README-style `run ws/analysis/x/<date>`: the concat list must still resolve (real ffmpeg, no TTS)."""
    import shutil
    from pathlib import Path

    import pytest
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")

    async def speak(paras, voice, rate, tmp):
        return [N.silence(0.2, tmp / f"p{i:03d}.mp3") for i in range(len(paras))]
    monkeypatch.setattr(N, "speak", speak)
    monkeypatch.chdir(tmp_path)
    unit = Path("ws") / "unit"
    unit.mkdir(parents=True)
    (unit / "listen.en.md").write_text("one\n\ntwo\n", encoding="utf8")
    N.render(unit / "listen.en.md", unit / "listen.en.mp3", "en", 0.1, False, False, None)
    assert (tmp_path / "ws" / "unit" / "listen.en.mp3").stat().st_size > 0
    assert not (tmp_path / "ws" / "unit" / ".partial").exists()


def fake_tts(monkeypatch, fails: int):
    """edge_tts.Communicate that returns no audio `fails` times, then writes a file; no network."""
    import edge_tts
    calls = []

    class Communicate:
        def __init__(self, text, voice, rate):
            calls.append(text)

        async def save(self, path):
            if len(calls) <= fails:
                raise edge_tts.exceptions.NoAudioReceived("No audio was received.")
            open(path, "wb").write(b"mp3")
    monkeypatch.setattr(edge_tts, "Communicate", Communicate)
    monkeypatch.setattr(N, "BACKOFF_S", 0)
    return calls


def test_speak_retries_when_no_audio_comes_back(tmp_path, monkeypatch, capsys):
    import asyncio
    calls = fake_tts(monkeypatch, fails=2)
    parts = asyncio.run(N.speak(["Hello."], "v", "+0%", tmp_path))
    assert len(calls) == 3 and parts[0].read_bytes() == b"mp3"
    assert "retry 2/2" in capsys.readouterr().out


def test_speak_gives_up_with_one_clear_line(tmp_path, monkeypatch):
    import asyncio

    import pytest
    fake_tts(monkeypatch, fails=9)
    with pytest.raises(SystemExit) as e:
        asyncio.run(N.speak(["Hello."], "v", "+0%", tmp_path))
    msg = str(e.value.code)
    assert msg.startswith("text-to-speech (edge-tts, online) failed: NoAudioReceived")
    assert msg.endswith("check the network and run again") and "\n" not in msg


def test_narrate_rerun_renders_only_the_stale_language(tmp_path, monkeypatch):
    import os
    for lang in ("zh", "en"):
        (tmp_path / f"listen.{lang}.md").write_text("Hello.\n", encoding="utf8")
    (tmp_path / "listen.zh.mp3").write_bytes(b"done")          # zh rendered before the failure, en not
    old = (tmp_path / "listen.zh.md").stat().st_mtime - 60
    os.utime(tmp_path / "listen.zh.md", (old, old))
    done = []
    monkeypatch.setattr(N, "render", lambda src, out, lang, *a, **k: done.append(lang))
    N.main([str(tmp_path), "--lang", "zh", "en"])
    assert done == ["en"]
    N.main([str(tmp_path), "--lang", "zh", "--force"])
    assert done == ["en", "zh"]


def test_stated_length_is_read_in_both_languages():
    assert N.stated(["这是报告，约 2 分钟。"], "zh") == (120, False)
    assert N.stated(["大概一分半钟。"], "zh") == (90, False)
    assert N.stated(["约十二分钟"], "zh") == (720, False)
    assert N.stated(["演示，不到一分钟。"], "zh") == (60, True)
    assert N.stated(["他投了三分球。"], "zh") is None             # 三分 is a shot, not a length
    assert N.stated(["This runs about three minutes."], "en") == (180, False)
    assert N.stated(["About a minute and a half."], "en") == (90, False)
    assert N.stated(["About 1.5 min."], "en") == (90, False)
    assert N.stated(["The demo, under a minute."], "en") == (60, True)
    assert N.stated(["No length here."], "en") is None


def test_stated_length_is_read_in_every_registry_language():
    cases = {"ja": [("約一分です。", 60), ("約2分です。", 120), ("一分半ほど。", 90), ("約十二分間。", 720),
                    ("1分以内です。", (60, True)), ("3分の1", None)],
             "ko": [("약 2분입니다.", 120), ("약2분.", 120), ("1분 반 정도.", 90), ("약 한 분이 나옵니다.", None), ("약 세 분이 왔다.", None),
                    ("1분 미만입니다.", (60, True)), ("3분의 1", None), ("부분 분석", None)],
             "es": [("Dura unos 2 minutos.", 120), ("Un minuto y medio.", 90), ("Menos de un minuto.", (60, True)),
                    ("Unos 1,5 minutos.", 90)],
             "fr": [("Environ deux minutes.", 120), ("Une minute et demie.", 90), ("Moins d'une minute.", (60, True))],
             "de": [("Etwa 2 Minuten.", 120), ("Eineinhalb Minuten.", 90), ("Anderthalb Minuten.", 90),
                    ("Unter einer Minute.", (60, True)), ("Zweieinhalb Minuten.", 150)],
             "pt": [("Cerca de 2 minutos.", 120), ("Um minuto e meio.", 90), ("Menos de um minuto.", (60, True))]}
    for lang, said in cases.items():
        for text, want in said:
            want = want if want is None or isinstance(want, tuple) else (want, False)
            assert N.stated([text], lang) == want, (lang, text)


def test_japanese_length_warning_for_the_cold_test_script():
    """「約一分です。」 over an 84 s script (the cold test said a minute, the page showed 約 1.5 分)."""
    warn = N.check_length(["約一分です。" + "あ" * 395], "ja")
    assert warn and "about 1 min" in warn
    assert N.check_length(["約一分です。" + "あ" * 280], "ja") is None


def test_length_warning_when_the_script_is_off_by_more_than_30_s():
    long_zh = ["这是报告，一分钟。" + "练" * 345]                    # 352 characters, about 90 s
    warn = N.check_length(long_zh, "zh")
    assert "about 1 min" in warn and "90 s" in warn
    assert N.check_length(["这是报告，约一分半。" + "练" * 340], "zh") is None
    assert N.check_length(["About two minutes. " + "word " * 380], "en") is None    # 1919 characters, 120 s
    assert N.check_length(["About two minutes. " + "word " * 100], "en").startswith("[narrate] warning: the en")
    assert N.check_length(["练" * 900], "zh") is None                # no stated length, nothing to check
    assert N.check_length(["Under a minute. " + "word " * 50], "en") is None   # 17 s is under a minute
    assert N.check_length(["Under a minute. " + "word " * 300], "en").startswith("[narrate] warning")


def test_read_time_uses_the_measured_rates():
    """Measured with the default voices: 887 characters / 6 paragraphs read in 58 s, 201 Chinese characters in 55 s;
    English words a minute vary with word length, characters do not."""
    en = ["x" * 147] * 6
    assert abs(N.estimate_s(en, "en") - 58) < 2
    assert abs(N.estimate_s(["练习，" * 17] * 6, "zh") - 55.6) < 2   # punctuation is not read as characters
    assert N.size_text(["One two three.", "Four."], "en") == "2 paragraphs, 4 words, 19 characters, reads in about 2 s"
    assert N.size_text(["一二三。"], "zh") == "1 paragraphs, 3 characters without punctuation, reads in about 1 s"


def test_render_prints_the_length_warning_and_goes_on(tmp_path, monkeypatch, capsys):
    import pytest
    (tmp_path / "listen.zh.md").write_text("这是报告，一分钟。" + "练" * 345 + "\n", encoding="utf8")

    async def speak(paras, voice, rate, tmp):
        raise RuntimeError("stop after the check")
    monkeypatch.setattr(N, "speak", speak)
    with pytest.raises(RuntimeError):
        N.render(tmp_path / "listen.zh.md", tmp_path / "listen.zh.mp3", "zh", 0.7, False, False, None)
    out = capsys.readouterr().out
    assert "[narrate] warning: the zh script says about 1 min" in out
    assert "[narrate] zh: 1 paragraphs, 352 characters without punctuation, reads in about 90 s; rendering" in out
