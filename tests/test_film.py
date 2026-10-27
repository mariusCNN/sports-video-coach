"""No-network tests for the explained-video stage (`hoop-tape-miner film`); the render test fakes the TTS."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from sports_video_coach import film
from sports_video_coach import film_draw as fd
from hoop_tape_miner import film_court as fc
from hoop_tape_miner.film_hooks import FILM, SCENES, title_text

SCRIPT = """# writer's note, never read
Hello team, this is the review.

## Why we lost the run
Two things.
Both fixable.

![#7 loses it to the press](clip:0:02-0:04)
Watch number seventeen.

Again, alone.
### also a note
![Score margin](momentum.png)
"""


def test_parse_script_scenes_and_paragraphs():
    s = film.parse_script(SCRIPT)
    assert [(x.kind, x.text, x.src) for x in s] == [
        ("title", "", ""), ("card", "Why we lost the run", ""), ("clip", "#7 loses it to the press", "0:02-0:04"),
        ("image", "Score margin", "momentum.png")]
    assert s[0].paras == ["Hello team, this is the review."]
    assert s[1].paras == ["Two things. Both fixable."]
    assert s[2].paras == ["Watch number seventeen.", "Again, alone."]
    assert s[3].paras == [] and s[2].window() == (2.0, 4.0) and s[2].clip_s() == 2.0


def test_target_length_scales_down_for_a_short_source():
    assert film.target_s(None) == film.target_s(600) == film.TARGET_S == (120, 240)
    assert film.target_s(22) == (45, 90) and film.target_s(30) == (60, 120)  # the guide: 2-4x, to 5 s
    assert film.target_s(5) == (30, 60)
    assert film.length_text(58.4) == "58 s" and film.length_text(119) == "119 s" and film.length_text(150) == "2.5 min"


def test_parse_script_starting_with_a_visual_has_no_title_card():
    assert [x.kind for x in film.parse_script("## Start\nText.\n")] == ["card"]


def test_check_flags_missing_picture_bad_window_and_missing_video(tmp_path):
    scenes = film.parse_script("![a](nope.png)\n![b](clip:0:09-0:05)\n![c](clip:7)\n")
    probs = film.check(scenes, tmp_path, None, None)
    assert any("picture not found" in p for p in probs)
    assert any("ends before it starts" in p for p in probs)
    assert any("mm:ss-mm:ss" in p for p in probs)
    assert any("needs the game video" in p for p in probs)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    assert any("past the end" in p for p in film.check(film.parse_script("![x](clip:0:01-0:30)"), tmp_path, video, 20))


def test_timing_holds_replays_slow_or_plays_clip_through():
    assert film.timing("clip", 0, 10) == (10, 0)                       # no voice: the clip as it is
    assert film.timing("clip", 5, 10) == (10, 0)                       # voice fits: play to the end
    length, slow = film.timing("clip", 9.5, 10)                        # small overrun: hold the last frame
    assert slow == 0 and length == pytest.approx(film.LEAD + 9.5 + film.TAIL)
    length, slow = film.timing("clip", 20, 10)                         # long talk: half-speed replay
    assert length == pytest.approx(film.LEAD + 20 + film.TAIL) and slow == pytest.approx(length - 10)
    assert film.timing("clip", 60, 10)[1] == pytest.approx(10 / film.SLOW)  # replay at most once, then hold
    assert film.timing("card", 0) == (film.CARD_S, 0) and film.timing("image", 0) == (film.IMAGE_S, 0)
    assert film.timing("card", 10)[0] == pytest.approx(film.LEAD + 10 + film.TAIL)


def test_subtitle_chunks_split_at_commas_and_tidy_ends():
    zh = "同一段时间，我们自己的进攻一次挡拆都没有，球一停就一个人往人堆里冲。"
    parts = film.chunks(zh, 20)
    assert all(len(p) <= 20 for p in parts) and "".join(parts) == zh
    cues = film.cue_split(1.0, 4.0, zh, 20)
    assert cues[0][0] == 1.0 and cues[-1][1] == pytest.approx(4.0)
    assert not any(c[2].endswith(("，", "。")) for c in cues)
    assert film.tidy("Really?") == "Really?" and film.tidy("Done.") == "Done"
    long_en = "word " * 40
    assert all(len(p) <= 30 for p in film.chunks(long_en, 30))


def test_ass_doc_and_scene_events():
    sc = film.parse_script("![cap {x}](clip:0:01-0:03)\nA.")[0]
    ev = film.scene_events(sc, 8.0, 3.0, 2.0, [(0.0, 1.0, "A"), (1.2, 2.0, "B")], "zh", "T", 720)
    styles = [e[2] for e in ev]
    assert styles == ["Banner", "Draw", "Draw", "Tag", "Sub", "Sub"]  # the caption, the slow-motion badge, subtitles
    assert ev[0][3].endswith("cap (x)") and ev[0][1] == film.BANNER_S and ev[3][3].endswith("慢放")
    assert ev[3][:2] == (2.0, 5.0)  # the badge shows while the replay is slowed
    assert ev[4][1] == pytest.approx(film.LEAD + 1.2)  # short gap closed: no flicker
    doc = film.ass_doc(1280, 720, "Font X", "#6250d6", ev)
    assert "PlayResY: 720" in doc and "Style: Sub,Font X," in doc
    assert "Dialogue: 2,0:00:00.00,0:00:06.00,Banner,,0,0,0,,{\\fad(250,300)}cap (x)" in doc  # above drawings
    assert film.ass_time(3725.456) == "1:02:05.46" and film.ass_colour("#6250d6", 0x30) == "&H30D65062"


FREEZE_SCRIPT = """![alone vs the press](clip:03:08-03:20)
Watch the ball.

> 03:10 我#7 对#11 我#7->0.6,0.5 "nobody comes"
Stop here. Nobody comes.

> 03:13.5 0.3,0.6
Now he is trapped.
![fouls](stat:9)
![get back](court:plays/back.json)
Set-up.

Step one.
"""


def test_parse_freeze_lines_stats_and_courts():
    s = film.parse_script(FREEZE_SCRIPT, FILM)
    assert [(x.kind, x.src) for x in s] == [("clip", "03:08-03:20"), ("stat", "9"), ("court", "plays/back.json")]
    clip = s[0]
    assert clip.paras == ["Watch the ball."] and [f.paras for f in clip.freezes] == [["Stop here. Nobody comes."],
                                                                                     ["Now he is trapped."]]
    t, marks, label, bad = clip.freezes[0].parts()
    assert t == "03:10" and label == "nobody comes" and not bad
    assert marks == [("player", "us", "7"), ("player", "them", "11"),
                     ("arrow", ("player", "us", "7"), ("point", 0.6, 0.5))]
    assert clip.freezes[1].at() == pytest.approx(193.5) and clip.freezes[1].parts()[1] == [("point", 0.3, 0.6)]
    assert fd.parse_freeze_line('> 1:00 them#3 junk “标签”', fc.parse_ref)[1:] == (
        [("player", "them", "3")], "标签", ["junk"])
    assert fd.parse_freeze_line("> 1:00 them#3 0.5,0.5")[1:] == ([("point", 0.5, 0.5)], "", ["them#3"])  # no plugin


def test_check_flags_bad_freezes_and_court_files(tmp_path):
    (tmp_path / "plays").mkdir()
    (tmp_path / "plays" / "back.json").write_text(json.dumps({"us": {"1": [20, 7]}, "steps": [{"move": {"us:2": [1, 1]}}]}),
                                                  encoding="utf8")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    bad = FREEZE_SCRIPT.replace("03:13.5 0.3,0.6", "03:30 wat") + "## card\n> 0:01 0.1,0.1\n"
    probs = film.check(film.parse_script(bad, FILM), tmp_path, video, 2000, kinds=SCENES, hooks=FILM)
    assert any("outside the clip" in p for p in probs) and any("cannot read 'wat'" in p for p in probs)
    assert any("no CV tracks" in p for p in probs) and any("only work after a clip" in p for p in probs)
    assert any("unknown player us:2" in p for p in probs)
    two = FREEZE_SCRIPT.replace("03:13.5 0.3,0.6", '03:13.5 0.3,0.6 "you" 0.5,0.6 "cone"')
    probs = film.check(film.parse_script(two, FILM), tmp_path, video, 2000, kinds=SCENES, hooks=FILM)
    assert any("only one \"label\" per freeze line" in p and "'\"cone\"'" in p for p in probs)


def test_clip_plan_plays_freezes_and_resumes():
    # 12 s clip, freezes at +2 s and +5.5 s; 3 s of talk before the first freeze, 4 s on it, none on the second
    length, segs, starts, spans = film.clip_plan(188, 200, [190, 193.5], [3.0, 4.0, 0.0])
    assert [x[0] for x in segs] == ["play", "hold", "play", "hold", "play"]
    assert segs[0] == ("play", 188, 190) and segs[2] == ("play", 190, 193.5) and segs[4] == ("play", 193.5, 200)
    first = film.LEAD + 3.0 + film.GAP  # the talk before the freeze is still running when the clip reaches it
    assert starts == [film.LEAD, pytest.approx(first), None]
    assert spans[0] == (2.0, pytest.approx(first + 4.0 + film.TAIL))
    assert spans[1][1] - spans[1][0] == pytest.approx(film.FREEZE_S)
    assert length == pytest.approx(12 + segs[1][2] + film.FREEZE_S)


def test_bare_freeze_line_reads_over_the_play_that_follows():
    scenes = film.parse_script("![x](clip:03:08-03:20)\n> 03:10 我#7 \"alone\"\nStop here.\n\n>\nWatch on.\n", FILM)
    fz = scenes[0].freezes
    assert [f.resume for f in fz] == [False, True] and fz[1].paras == ["Watch on."] and fz[1].at() is None
    assert not any("only works after" in p for p in film.check(scenes, Path("."), Path("v.mp4"), 3000.0))
    bad = film.parse_script("![x](clip:03:08-03:20)\n>\nToo early.\n")
    assert any("only works after a freeze" in p for p in film.check(bad, Path("."), Path("v.mp4"), 3000.0))
    # 3 s on the freeze at +2 s, then 4 s over the play: the clip runs on right away, the voice after the freeze talk
    length, segs, starts, spans = film.clip_plan(188, 200, [190, None], [0.0, 3.0, 4.0])
    assert segs == [("play", 188, 190), ("hold", 190, pytest.approx(film.LEAD + 3.0 + film.TAIL)), ("play", 190, 200)]
    hold_end = 2.0 + segs[1][2]
    assert spans[1] is None and starts[2] == pytest.approx(max(hold_end + 0.3, 2.0 + film.LEAD + 3.0 + film.GAP))
    assert length == pytest.approx(hold_end + 10)


def test_freeze_events_circle_tracked_players_and_dim_the_rest():
    import pandas as pd

    df = pd.DataFrame([{"t": 190.0, "team": "us", "number": "7", "x1": 370, "y1": 268, "x2": 456, "y2": 412},
                       {"t": 190.1, "team": "them", "number": "11", "x1": 475, "y1": 293, "x2": 529, "y2": 414}])
    tracks = fc.Tracks(df, 1280, 720)
    assert tracks.box("us", "7", 190.05) == pytest.approx((370 / 1280, 268 / 720, 456 / 1280, 412 / 720))
    assert tracks.box("us", "7", 191) is None and tracks.box("them", "7", 190) is None
    marks = fd.parse_freeze_line('> 03:10 我#7 对#11 我#7->对#11 "alone"', fc.parse_ref)[1]
    ev = fd.freeze_events(marks, "alone", 190.0, tracks, 1280, 720, (0, 0, 1280, 720), 2.0, 6.0)
    styles = [e[2] for e in ev]
    # the dim layer, two rings (dark disc + coloured rim each), one arrow, the label (leader, pill, strip, text)
    assert styles == ["Draw"] * 6 + ["Draw"] * 3 + ["Mark"]
    assert ev[0][3].count(" m ") == 1 and "\\blur" in ev[0][3]  # the two players overlap: one soft hole, merged
    assert fd.bgr(fd.US_HEX) in ev[2][3] and fd.bgr(fd.THEM_HEX) in ev[4][3]  # ours blue, theirs red
    assert all(e[:2] == (2.0, 6.0) for e in ev) and not any("\\fad" in e[3] for e in ev)  # a still: all at once
    short = fd.parse_freeze_line('> 00:04.5 0.87,0.72->0.92,0.72 "short"', fc.parse_ref)[1]
    ev = fd.freeze_events(short, "short", 4.5, None, 1280, 720, (0, 0, 1280, 720), 2.0, 6.0)
    assert ev[0][3].count(" m ") == 1 and [e[2] for e in ev].count("Draw") == 7  # one hole, one ring, the arrow
    far = fd.parse_freeze_line('> 00:04.5 0.2,0.72->0.8,0.72', fc.parse_ref)[1]
    assert fd.freeze_events(far, "", 4.5, None, 1280, 720, (0, 0, 1280, 720), 2.0, 6.0)[0][3].count(" m ") == 2
    assert film.freeze_warnings(film.parse_script("![x](clip:03:08-03:20)\n> 03:10 我#9\n", FILM), tracks) == [
        "scene 1: freeze 03:10: us#9 is not in the tracks near that moment; mark them with x,y instead"]
    stub = film.parse_script("![x](clip:03:08-03:20)\n> 03:10 我0.66,0.6->0.71,0.55 0.2,0.5->0.4,0.5\n", FILM)
    assert film.freeze_warnings(stub, None) == [
        "scene 1: freeze 03:10: the arrow us:0.66,0.6->0.71,0.55 is too short to read; aim it further "
        "(at least 0.1 of the frame) or ring the players instead"]
    pass_ = film.parse_script("![x](clip:03:08-03:20)\n> 03:10 我#7 对#11 我#7->对#11 我#7->0.9,0.5\n", FILM)
    assert film.freeze_warnings(pass_, tracks) == [  # two tracked players about 0.07 apart, centre to centre
        "scene 1: freeze 03:10: the arrow us#7->them#11 is too short to read; aim it further "
        "(at least 0.1 of the frame) or ring the players instead"]
    assert film.freeze_warnings(pass_, None) == []  # no tracks: a player arrow cannot be measured


def test_court_diagram_states_and_frames(tmp_path):
    play = {"us": {"1": [20, 7.5], "2": [25, 2]}, "them": {"19": [22, 6]}, "ball": "us:1",
            "steps": [{"dribble": {"us:1": [23, 7]}}, {"pass": ["us:1", "us:2"], "ring": ["them:19"]},
                      {"shot": "us:2"}]}
    f = tmp_path / "p.json"
    f.write_text(json.dumps(play), encoding="utf8")
    play = fc.load_play(f)
    assert fc.play_problems(play) == []
    st = fc.play_states(play)
    assert st[1]["pos"]["us:1"] == (23, 7) and st[2]["ball"] == "us:2" and st[3]["ball"] == "basket:us:2"
    assert film.court_steps([0.0, 3.0], 3) == [film.LEAD + 3.0, film.LEAD + 5.5, film.LEAD + 8.0]
    lst = fc.render_court(play, 320, 180, [1.0, 3.0, 5.0], 7.0, tmp_path / "c", "#6250d6", "#e04040", fps=10)
    lines = lst.read_text(encoding="utf8").splitlines()
    durs = [float(x.split()[1]) for x in lines if x.startswith("duration")]
    assert sum(durs) == pytest.approx(7.0, abs=0.01) and (tmp_path / "c" / "c00000.png").is_file()


def test_title_text_uses_game_json_names_date_and_score(tmp_path):
    folder = tmp_path / "teams" / "x" / "2025-03-08"
    folder.mkdir(parents=True)
    game = {"us": {"team": "A"}, "them": {"team": "B"}, "result": {"us": 44, "them": 39}}
    t = title_text(folder, game, 720)
    assert t.startswith("A vs B\\N") and t.endswith("2025-03-08 · 44–39")
    assert title_text(folder / "player-7", {}, 720).startswith("#7 · Us vs Them")


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")
def test_film_renders_scenes_with_fake_voice(tmp_path, monkeypatch, capsys):
    def ff(*a):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)

    video = tmp_path / "game.mp4"
    ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=6", "-f", "lavfi", "-i",
       "sine=f=300:d=6", "-pix_fmt", "yuv420p", "-shortest", str(video))
    folder = tmp_path / "2025-03-08"
    folder.mkdir()
    ff("-f", "lavfi", "-i", "color=c=white:s=200x100:d=1", "-frames:v", "1", str(folder / "momentum.png"))
    (folder / "game.json").write_text(json.dumps({"us": {"team": "A"}, "them": {"team": "B"}}), encoding="utf8")
    (folder / "film.en.md").write_text(SCRIPT, encoding="utf8")

    def fake_spoken(text, voice, rate, cache):  # 0.1 s of tone per character stands in for edge-tts
        cache.mkdir(parents=True, exist_ok=True)
        out = cache / f"{abs(hash(text))}.wav"
        ff("-f", "lavfi", "-i", f"sine=f=600:d={len(text) / 10}", str(out))
        return out, len(text) / 10, [(0.0, len(text) / 10, text)]

    monkeypatch.setattr(film, "spoken", fake_spoken)
    film.main([str(folder), "--video", str(video), "--height", "180", "--dry"])
    assert "4 scenes" in capsys.readouterr().out and not (folder / "film.en.mp4").exists()

    out = film.build(folder, "en", video, 180, film.FONT)
    voice = {i: film.LEAD + (sum(len(p) for p in ps) / 10 + film.GAP * (len(ps) - 1)) + film.TAIL
             for i, ps in enumerate(sc.paras for sc in film.parse_script(SCRIPT)) if ps}
    expected = voice[0] + voice[1] + voice[2] + film.IMAGE_S  # clip (2 s) is outlasted by its narration
    assert out == folder / "film.en.mp4"
    assert film.duration_s(out) == pytest.approx(expected, abs=0.5)
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,height", "-of", "csv=p=0",
                              str(out)], capture_output=True, text=True, check=True).stdout
    assert "video,180" in streams and "audio" in streams

    preview = film.build(folder, "en", video, 180, film.FONT, pick=(3, 3))
    assert preview.name == "film.en.preview.mp4" and film.duration_s(preview) == pytest.approx(voice[2], abs=0.3)

    # narration a little longer than the clip: no slow replay, the last frame holds
    (folder / "film.en.md").write_text("![x](clip:0:01-0:03)\nWatch the pass.\n", encoding="utf8")
    assert film.timing("clip", 1.5, 2.0)[1] == 0
    hold = film.build(folder, "en", video, 180, film.FONT)
    assert film.duration_s(hold) == pytest.approx(film.LEAD + 1.5 + film.TAIL, abs=0.2)

    # a card and a stat over blurred footage, a clip that freezes once, an animated court diagram
    (folder / "plays").mkdir()
    (folder / "plays" / "p.json").write_text(json.dumps({"us": {"1": [20, 7.5]}, "steps": [{"move": {"us:1": [24, 4]}}]}),
                                             encoding="utf8")
    (folder / "film.en.md").write_text('## Card\n![x](clip:0:01-0:04)\nGo.\n> 0:02 0.5,0.8 "here"\nLook.\n'
                                       '![n](stat:3)\n![p](court:plays/p.json)\nSet.\n\nMove.\n', encoding="utf8")
    rich = film.build(folder, "en", video, 180, film.FONT)
    clip = film.clip_plan(1, 4, [2], [0.3, 0.5])[0]
    assert clip == pytest.approx(3 + 1.3)  # the 3 s clip plus a 1.3 s freeze
    assert film.duration_s(rich) == pytest.approx(film.CARD_S + clip + film.CARD_S + film.IMAGE_S, abs=0.5)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")
def test_spoken_cuts_trailing_silence_from_cached_speech(tmp_path):
    import hashlib

    key = hashlib.sha1("v|+0%|Hi.".encode("utf8")).hexdigest()[:16]
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=500:d=1", "-af", "apad=pad_dur=1",
                    str(tmp_path / f"{key}.mp3")], check=True)
    (tmp_path / f"{key}.json").write_text(json.dumps({"duration": 2.0, "cues": [[0.0, 2.0, "Hi."]]}), encoding="utf8")
    wav, dur, cues = film.spoken("Hi.", "v", "+0%", tmp_path)
    assert wav.suffix == ".wav" and dur == pytest.approx(1.0, abs=0.15) and cues == [(0.0, dur, "Hi.")]


def test_card_lines_come_in_one_after_another_left_aligned_under_the_accent_bar():
    sc = film.Scene("card", "Pressure comes, find a teammate · Two come, pass")
    bar, one, two = film.scene_events(sc, 5, 0, 0, [], "en", "", 720)
    assert bar[2] == "Kicker" and "\\p1" in bar[3]  # the accent bar, drawn in the accent colour
    assert one[2] == two[2] == "Title" and one[0] < two[0]  # a sign-off: line by line
    assert one[3] == r"{\an7\move(106,278,128,278,0,350)\fad(300,250)\fs63}Pressure comes, find a teammate"
    assert two[3].endswith("}Two come, pass") and "\\move(106,360,128,360" in two[3]


def test_a_chapter_card_shows_its_kicker_apart_from_the_title():
    sc = film.parse_script("## 第一件事：有压力，第二个人来接\n")[0]
    ev = film.scene_events(sc, 5, 0, 0, [], "zh", "", 720)
    assert [e[2] for e in ev] == ["Kicker", "Kicker", "Title"]
    assert ev[1][3].endswith("}第一件事") and ev[2][3].endswith("}有压力，第二个人来接")


def test_a_stat_counts_up_and_a_goal_says_at_most_in_words():
    sc = film.parse_script("![fast breaks](stat:22–4)\n")[0]
    ev = film.scene_events(sc, 5, 0, 0, [], "en", "", 720)
    nums = [e for e in ev if e[2] == "Big"]
    assert len(nums) == film.COUNT_STEPS + 1 and nums[0][3].endswith("}0–0") and nums[-1][3].endswith("}22–4")
    assert nums[-1][1] == 5 and all(x[1] == pytest.approx(y[0]) for x, y in zip(nums[1:], nums[2:]))  # no gap
    assert ev[-1][2] == "Caption" and ev[-1][3].endswith("fast breaks")
    goal = film.scene_events(film.parse_script("![下场目标](stat:≤4)\n")[0], 5, 0, 0, [], "zh", "", 720)
    assert goal[0][2] == "Kicker" and goal[0][3].endswith("最多")
    assert not any("≤" in e[3] for e in goal) and goal[-2][3].endswith("}4") and goal[-2][2] == "Kicker"
    at_least = film.scene_events(film.parse_script("![x](stat:≥8)\n")[0], 5, 0, 0, [], "en", "", 720)
    assert at_least[0][3].endswith("At least")


def test_a_stats_board_puts_six_numbers_in_two_rows_of_three():
    sc = film.parse_script("![本场关键数字](stats:9–21 上半场 | 22–4 被打的一波 | 17 快攻 | 10–2 罚球 | 16–11 犯规 | 14–7 回追)\n")[0]
    assert sc.kind == "stats" and film.check([sc], Path("."), None, None) == []
    ev = film.scene_events(sc, 6, 0, 0, [], "zh", "", 720)
    nums = [e for e in ev if e[2] == "Big"]
    assert [n[3].rsplit("}", 1)[1] for n in nums] == ["9–21", "22–4", "17", "10–2", "16–11", "14–7"]
    pos = [tuple(map(int, re.search(r"\\pos\((\d+),(\d+)\)", n[3]).groups())) for n in nums]
    assert len({y for _, y in pos}) == 2 and [x for x, _ in pos[:3]] == [x for x, _ in pos[3:]]  # 3 + 3, aligned
    assert ev[0][2] == "Kicker" and ev[0][3].endswith("本场关键数字")
    assert sum(e[2] == "Caption" for e in ev) == 6
    assert [film.stats_cols(n) for n in (1, 2, 3, 4, 5, 6)] == [1, 2, 3, 2, 3, 3]
    five = [e for e in film.stats_events("1 a | 2 b | 3 c | 4 d | 5 e", "", 5, "en", 720, 1280, 720) if e[2] == "Big"]
    xs = [int(re.search(r"\\pos\((\d+),", e[3])[1]) for e in five]
    assert (xs[3] + xs[4]) / 2 == pytest.approx(640, abs=2)  # a short last row is centred


def test_an_animated_freeze_zooms_in_builds_the_marks_and_clears_before_the_play():
    marks = fd.parse_freeze_line('> 00:04 0.4,0.6 0.5,0.62 0.4,0.6->0.5,0.62 "two"')[1]
    zoom = fd.freeze_zoom(marks, 4.0, None, 1280, 720, (0, 0, 1280, 720))
    z, x, y = zoom
    assert 1.1 <= z <= fd.ZOOM_MAX and 0 <= x <= 1280 - 1280 / z and 0 <= y <= 720 - 720 / z
    ev = fd.freeze_events(marks, "two", 4.0, None, 1280, 720, (0, 0, 1280, 720), 2.0, 10.0, zoom=zoom, animate=True)
    starts = sorted({e[0] for e in ev})
    assert starts[0] >= 2.0 + fd.ZOOM_S and len(starts) >= 4  # after the zoom settles, one beat at a time
    assert all(e[1] == pytest.approx(10.0 - fd.OUT_S - 0.1) for e in ev)  # gone before the zoom goes back
    assert all("\\fad(" in e[3] for e in ev) and any("\\t(0,350,\\clip(" in e[3] for e in ev)  # the arrow draws on
    still = fd.freeze_events(marks, "two", 4.0, None, 1280, 720, (0, 0, 1280, 720), 2.0, 10.0)
    ring = lambda evs: next(e[3] for e in evs if "\\an5\\pos(" in e[3] and "\\3c" in e[3])
    rx = lambda t: float(re.search(r"\\pos\(([\d.]+),", t)[1])
    assert rx(ring(ev)) == pytest.approx((0.4 * 1280 - x) * z, abs=1)  # the marks follow the zoomed frame
    assert rx(ring(still)) == pytest.approx(0.4 * 1280, abs=1)
    far = fd.parse_freeze_line("> 00:04 0.05,0.9 0.95,0.3")[1]
    assert fd.freeze_zoom(far, 4.0, None, 1280, 720, (0, 0, 1280, 720)) is None  # too far apart to zoom


def test_a_zoomed_hold_eases_in_and_out_in_the_scene_command(tmp_path):
    sc = film.parse_script("![x](clip:0:01-0:05)\n> 0:02 0.4,0.6\nA.\n")[0]
    segs = [("play", 1.0, 2.0), ("hold", 2.0, 4.0), ("play", 2.0, 5.0)]
    cmd = lambda zooms: film.scene_cmd(sc, 9.0, 0, 1280, 720, tmp_path, tmp_path / "v.mp4", False, [], "s.ass",
                                       "#5b4bd1", "o.mp4", segs=segs, zooms=zooms)
    args = cmd([(1.3, 100.0, 50.0)])
    graph = args[args.index("-filter_complex") + 1]
    assert graph.count("zoompan=") == 1 and "scale=2560:1440,zoompan=" in graph and ":s=1280x720:" in graph
    assert f"/{fd.ZOOM_S}" in graph and f"(4.000-(in/{film.FPS}))/{fd.OUT_S}" in graph
    plain = cmd([None])
    assert "zoompan" not in plain[plain.index("-filter_complex") + 1]


def test_badge_says_paused_with_an_icon():
    ev = fd.badge("定格", 1.0, 3.0, 1280, 720)
    assert [e[2] for e in ev] == ["Draw", "Draw", "Tag"] and ev[2][3].endswith("定格")
    assert ev[1][3].count(" m ") == 1  # two bars
    assert all(e[:2] == (1.0, 3.0) for e in ev)


def test_a_spot_can_say_its_team_so_its_ring_and_label_take_the_team_colour():
    assert fd.parse_mark("对0.77,0.53") == ("point", 0.77, 0.53, "them")
    assert fd.parse_mark("us:0.4,0.6") == ("point", 0.4, 0.6, "us") and fd.parse_mark("0.4,0.6") == ("point", 0.4, 0.6)
    assert fd.mark_text(fd.parse_mark("对0.77,0.53")) == "them:0.77,0.53"
    assert fd.parse_mark("我0.6,0.5->对0.7,0.5")[2] == ("point", 0.7, 0.5, "them")
    assert fd.mark_hex(("point", 0.7, 0.5, "them")) == fd.THEM_HEX and fd.mark_hex(("point", 0.7, 0.5)) == fd.POINT_HEX
    assert fd.mark_hex(("player", "us", "7")) == fd.US_HEX and fd.mark_hex(None) == fd.POINT_HEX
    marks = fd.parse_freeze_line('> 00:04 对0.4,0.6 "two"')[1]
    ev = fd.freeze_events(marks, "two", 4.0, None, 1280, 720, (0, 0, 1280, 720), 2.0, 10.0, animate=True)
    red = fd.bgr(fd.THEM_HEX)
    assert sum(red in e[3] for e in ev) == 2  # the rim and the label's strip
    pill, text = next(e for e in ev if "\\p1" in e[3] and "\\1a&H22&" in e[3]), ev[-1]
    assert text[2] == "Mark" and text[0] > pill[0]  # the label's text comes in after its pill


def test_a_clip_banner_goes_at_the_first_freeze():
    sc = film.parse_script("![cap](clip:0:01-0:09)\nA.\n")[0]
    banner = lambda **kw: next(e for e in film.scene_events(sc, 20, 0, 0, [], "en", "", 720, **kw) if e[2] == "Banner")
    assert banner()[1] == film.BANNER_S and banner(banner_to=3.2)[1] == 3.2
    assert banner(banner_to=0.0)[1] == 0.0  # a freeze on the clip's first frame: no banner over it


def test_a_short_hold_still_shows_every_mark_and_the_label():
    marks = fd.parse_freeze_line('> 00:04 我0.4,0.6 我0.6,0.62 我0.4,0.6->我0.6,0.62 "open"')[1]
    zoom = fd.freeze_zoom(marks, 4.0, None, 1280, 720, (0, 0, 1280, 720))
    ev = fd.freeze_events(marks, "open", 4.0, None, 1280, 720, (0, 0, 1280, 720), 2.0, 2.0 + film.FREEZE_S,
                          zoom=zoom, animate=True)
    assert all(e[1] > e[0] for e in ev) and ev[-1][2] == "Mark"  # the arrow and the label start before stop
    assert any("\\clip(" in e[3] for e in ev)


def test_a_clock_time_in_a_title_is_not_a_kicker_and_a_stat_keeps_its_zeros():
    sc = film.parse_script("## At 03:10 the press broke\n")[0]
    assert [e[2] for e in film.scene_events(sc, 5, 0, 0, [], "en", "", 720)] == ["Kicker", "Title"]
    for src in ("0.05", "4:05"):
        ev = film.scene_events(film.parse_script(f"![x](stat:{src})\n")[0], 5, 0, 0, [], "en", "", 720)
        assert [e for e in ev if e[2] == "Big"][-1][3].endswith("}" + src)


def test_a_dark_team_colour_is_lightened_for_card_text():
    assert film.lighten("#5b4bd1") == "#a59ce6" and film.lighten("#ffffff") == "#ffffff"
    assert "&H00E69CA5" in film.ass_doc(1280, 720, "Arial", "#5b4bd1", [])  # the Kicker style


def test_generic_folder_film_plan_without_a_plugin(tmp_path, monkeypatch, capsys):
    """A folder no plugin owns: clips, cards and point freezes plan with the generic hooks and title card."""
    folder = tmp_path / "2025-03-12"
    folder.mkdir()
    (folder / "film.en.md").write_text("Hello.\n\n## Footwork\nTwo things.\n![the cut](clip:0:02-0:06)\nWatch.\n"
                                       '> 0:03 0.5,0.8 "here"\nStop.\n', encoding="utf8")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(film, "duration_s", lambda p: 20.0)
    monkeypatch.setattr(film, "video_size", lambda p: (1280, 720))
    assert film.hooks_for(folder) == (film.GENERIC, {})
    film.main([str(folder), "--video", str(video), "--dry"])
    out = capsys.readouterr().out
    assert [ln.split()[1] for ln in out.splitlines()[:3]] == ["title", "card", "clip"]
    assert "1 freeze(s)" in out and "3 scenes" in out
    assert "freeze 0:03: 1 mark(s) 0.5,0.8  label 'here'" in out  # what --dry read from the freeze line
    assert "note: film.en.md: about" in out  # names the script: several languages print one after another
    assert "under the 40-80 s the film guide aims for with a 20 s video; add a moment" in out  # a short plan
    assert " min" not in out  # a film under 2 min is told in seconds
    (folder / "film.en.md").write_text("Hello.\n\n![the cut](clip:0:02-0:06)\nWatch.\n"
                                       '> 0:03 0.5,0.8 "here"\nStop.\n>\nOn it goes.\n', encoding="utf8")
    film.main([str(folder), "--video", str(video), "--dry"])
    out = capsys.readouterr().out
    assert "      resume: the play runs on" in out and "1 freeze(s), 1 resume(s)" in out
    (folder / "film.en.md").write_text("Hello.\n\n![the cut](clip:0:02-0:06)\nWatch.\n> 0:03\nStop.\n"
                                       "> 0:04\nAgain.\n>\nOn it goes.\n", encoding="utf8")
    film.main([str(folder), "--video", str(video), "--dry"])
    assert "2 freeze(s), 1 resume(s)" in capsys.readouterr().out  # two freezes and a bare `>`, not 3 freezes
    (folder / "film.en.md").write_text("Hello.\n\n![the cut](clip:0:02-0:06)\n"
                                       '> 0:03 0.88,0.72 "stop here" 0.92,0.72\nStop.\n\n## Numbers\n'
                                       + "A long still talk. " * 14 + "\n", encoding="utf8")
    film.main([str(folder), "--video", str(video), "--dry"])
    out = capsys.readouterr().out
    assert "warning: scene 2: freeze 0:03: `0.92,0.72` comes after the label; put the label last" in out
    assert "note: film.en.md scene 3: " in out and "on a still picture; split the text" in out  # ~18 s, one picture
    assert film.title_text(folder, {}, 720) == "2025-03-12"  # the folder name; no date line repeating it
    assert film.title_text(folder, {"title": "Sprint"}, 720).endswith("2025-03-12")
    assert film.title_text(folder, {"title": "Sprint, 2025-03-12"}, 720).count("2025-03-12") == 1
    (folder / "README.en.md").write_text("# Hill sprints: the turn\n\nbody\n", encoding="utf8")
    assert film.title_text(folder, {}, 720, lang="en").startswith("Hill sprints: the turn")  # the report's heading
    assert film.title_text(folder, {}, 720, lang="zh") == "2025年3月12日"                  # no README.md: folder name
    (folder / "README.es.md").write_text("# Dobles: la red\n\nbody\n", encoding="utf8")
    assert film.title_text(folder, {}, 720, lang="es").endswith("12 mar 2025")  # the date the reader's way
    assert film.title_text(folder, {"title": "Dobles, 12 mar 2025"}, 720, lang="es").count("2025") == 1


def test_unknown_scene_prefix_names_the_known_ones(tmp_path):
    (tmp_path / "plays").mkdir()
    (tmp_path / "plays" / "p.json").write_text("{}", encoding="utf8")
    (tmp_path / "film.en.md").write_text("![p](court:plays/p.json)\nSet.\n", encoding="utf8")
    with pytest.raises(SystemExit) as e:  # no plugin owns the folder: court: is unknown here
        film.build(tmp_path, "en", None, 180, film.FONT, dry=True)
    assert "unknown scene prefix 'court:'" in str(e.value) and "clip:, stat:" in str(e.value)
    probs = film.check(film.parse_script("![p](court:plays/p.json)\n![x](reel:a.mp4)\n"), tmp_path, None, None,
                       kinds=SCENES)
    assert probs == ["scene 2: unknown scene prefix 'reel:' (known here: clip:, stat:, stats:, court:; a plugin adds more)"]
    sc = film.parse_script("Intro.\n\n![x](reel:a.mp4)\n")[1]
    assert sc.line == 3 and film.prefix_problem(sc, SCENES) == probs[0].removeprefix("scene 2: ")


def test_film_keeps_a_language_newer_than_its_script_and_what_it_shows(tmp_path, monkeypatch, capsys):
    """Adding zh renders only zh: film.en.mp4 newer than film.en.md, the video and its pictures is kept."""
    import os
    import time
    video, pic = tmp_path / "v.mp4", tmp_path / "chart.png"
    for p in (video, pic):
        p.write_bytes(b"x")
    for lang in ("en", "zh"):
        (tmp_path / f"film.{lang}.md").write_text("Hi.\n\n![c](clip:0:01-0:03)\nGo.\n![m](chart.png)\nSee.\n",
                                                  encoding="utf8")
    (tmp_path / "film.en.mp4").write_bytes(b"old")
    later = time.time() + 30
    os.utime(tmp_path / "film.en.mp4", (later, later))
    built = []
    monkeypatch.setattr(film, "build", lambda folder, lang, *a, **k: built.append(lang))
    film.main([str(tmp_path), "--video", str(video)])
    assert built == ["zh"] and "[film] en: film.en.mp4 is newer than film.en.md, kept" in capsys.readouterr().out
    assert film.inputs(tmp_path, "en", video) == [tmp_path / "film.en.md", video, pic]
    film.main([str(tmp_path), "--video", str(video), "--lang", "en", "--force"])
    assert built == ["zh", "en"]
    os.utime(pic, (later + 30, later + 30))                    # a picture it shows changed: render again
    film.main([str(tmp_path), "--video", str(video), "--lang", "en"])
    assert built == ["zh", "en", "en"]


def test_basketball_folder_gets_court_scenes_and_player_marks(tmp_path):
    (tmp_path / "game.json").write_text("{}", encoding="utf8")
    hooks, kinds = film.hooks_for(tmp_path)
    assert hooks is FILM and set(kinds) == {"court"}


def test_a_paragraph_with_nothing_to_say_stops_before_tts(tmp_path):
    scenes = film.parse_script("Hello.\n\n## Card\n&gt;\n\n——\n")
    probs = film.check(scenes, tmp_path, None, None)
    assert probs == ["scene 2: '&gt;' has nothing to say (TTS gets no speech from it); write words or drop it",
                     "scene 2: '——' has nothing to say (TTS gets no speech from it); write words or drop it"]
    assert film.check(film.parse_script("你好。\n\n## 数字\n第2段 00:08。\n"), tmp_path, None, None) == []


def test_a_tts_failure_names_the_paragraph(tmp_path, monkeypatch):
    async def no_audio(text, voice, rate, out):
        out.write_bytes(b"")
        raise RuntimeError("No audio was received")
    monkeypatch.setattr(film, "_tts", no_audio)
    with pytest.raises(SystemExit, match="edge-tts gave no speech for 'Toss higher.'"):
        film.spoken("Toss higher.", "en-US-AriaNeural", "+0%", tmp_path / "tts")
    assert not list((tmp_path / "tts").glob("*.mp3"))  # nothing half-written is cached


def test_an_upright_video_makes_an_upright_film_with_the_same_text_size():
    assert film.film_size(720, (1280, 720)) == (1280, 720) and film.film_size(720, (720, 1280)) == (720, 1280)
    sc = film.parse_script("## Card\nOne line.\n")[0]
    tall = film.scene_events(sc, 5, 0, 0, [], "en", "", 720, frame=(720, 1280))[-1][3]
    wide = film.scene_events(sc, 5, 0, 0, [], "en", "", 720)[-1][3]
    ty, wy = (int(re.search(r"\\move\(\d+,(\d+),", t)[1]) for t in (tall, wide))
    assert ty - 640 == wy - 360  # mid-frame, as in a landscape film
    styles = lambda doc: [ln for ln in doc.splitlines() if ln.startswith("Style:")]
    tall, land = styles(film.ass_doc(720, 1280, "F", "#6250d6", [])), styles(film.ass_doc(1280, 720, "F", "#6250d6", []))
    assert [s for s in tall if s.startswith("Style: Sub")] == [s for s in land if s.startswith("Style: Sub")]


def test_chinese_subtitles_break_into_lines_that_fit_an_upright_film():
    line = "录像里只看得到一个红色方块在两个橙色标志之间来回"  # 24 wide characters, no spaces: libass cannot wrap it
    sc = film.parse_script("![clip](clip:0:01-0:05)\n")[0]
    cues = [(0.0, 3.0, line)]
    tall = film.scene_events(sc, 5, 0, 4, cues, "zh", "", 720, frame=(720, 1280))[-1][3]
    assert tall.split(r"\N") == ["录像里只看得到一个红色方", "块在两个橙色标志之间来回"]
    assert r"\N" not in film.scene_events(sc, 5, 0, 4, cues, "zh", "", 720)[-1][3]  # fits a landscape line
    assert film.fit("练习：节拍折返，四组，每组六个来回，每到一端数一", 15) == ["练习：节拍折返，四组，", "每组六个来回，每到一端数一"]
    assert film.fit("用 ACL 和 shuttle run 练三组，每组六个来回", 15)[0] == "用 ACL 和 shuttle run"  # no word cut
    assert film.fit("Keep your hips low and push off the line", 15) == ["Keep your hips low and push off the line"]
