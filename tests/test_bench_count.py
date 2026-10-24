"""The benchmark page's "Count it yourself" block (`bench.count`): answers from the result files, truth from the
suite, the reveal hidden until a count is entered, the Chinese twin, and the question video."""
import json
import re
import shutil
from pathlib import Path

import pytest

from sports_video_coach import media, page_check
from sports_video_coach.bench import count, page, suite3

RESULTS = Path(__file__).resolve().parents[1] / "benchmark" / "results"
TRUTH = suite3.BY_ID[count.TASK].truth
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")


def result(agent: str, model: str, answer, track: str = "frames", **extra) -> dict:
    score = max(0.0, 1 - abs(answer - TRUTH) / TRUTH) if isinstance(answer, int) else 0.0
    return {"schema": 1, "suite": count.SUITE, "track": track, "tool_version": "0.0.0", "date": "2026-10-24",
            "contender": {"agent": agent, "model": model, "settings": ""}, "submitted_by": "someone",
            "tasks": [{"id": count.TASK, "kind": "count", "truth": TRUTH, "answer": answer, "score": score}],
            "total": score, **extra}


def fake_results(tmp_path: Path) -> Path:
    d = tmp_path / "results"
    d.mkdir()
    files = {"a.json": result("Claude Code", "claude-opus-5-5", 31),
             "b.json": result("Claude Code", "claude-opus-5-5", TRUTH),
             "c.json": result("Codex", "gpt-6-astra", None),
             "d.json": result("Claude Code", "claude-sonnet-5-5", 52, track="code"),
             "e.json": result("Claude Code", "claude-haiku-5-5", 12, seed=7),   # a fresh seed: another video
             "f.json": result("blind baseline", "", 5)}
    for name, data in files.items():
        (d / name).write_text(json.dumps(data), encoding="utf8")
    return d


def block(html: str) -> str:
    return html[html.index('<section class="count"'):html.index("</section>", html.index('<section class="count"'))]


def test_answers_come_from_the_result_files(tmp_path):
    rows, _ = page.load(fake_results(tmp_path))
    data = count.count_data(rows)
    assert data["truth"] == TRUTH and data["question"] == count.QUESTION and data["seconds"] == suite3.JUG_S
    shown = [(c["track"], c["label"], [r["answer"] for r in c["runs"]]) for c in data["contenders"]]
    assert shown == [("frames", "Opus 5.5", [31, TRUTH]), ("frames", "Codex · gpt-6-astra", [None]),
                     ("code", "Sonnet 5.5", [52])]                     # frames first, best mean first; no seed run
    assert data["floor"]["answer"] == 5
    html = page.count_block(rows)
    assert '<span class="exact">47</span>' in html and ">31, <" in html and ">52<" in html and "&ndash;" in html
    assert ">12<" not in html
    assert f'data-truth="{TRUTH}"' in html and f"Truth: {TRUTH} touches" in html
    line = page.share_line(data)
    assert line == (f"I counted {{n}} touches. Truth: {TRUTH}. Models by eye (stills): Opus 5.5 31, {TRUTH}. "
                    f"Count it yourself: {page.PAGE_URL}#count")


def test_every_repo_result_of_the_task_is_shown(tmp_path):
    rows, _ = page.load(RESULTS)
    data = count.count_data(rows)
    want = sorted(r["_file"] for r in rows if page.suite_of(r) == count.SUITE and not page.is_baseline(r))
    assert sorted(run["file"] for c in data["contenders"] for run in c["runs"]) == want and len(want) >= 5


def test_no_block_without_a_contender_run(tmp_path):
    rows, _ = page.load(fake_results(tmp_path))
    assert count.count_data([r for r in rows if page.is_baseline(r) or r.get("seed")]) is None
    assert page.count_block([r for r in rows if page.is_baseline(r)]) == ""
    assert page.render(rows, [], count=False).count('id="count"') == 0


def test_a_file_whose_truth_differs_from_the_suite_is_refused(tmp_path):
    rows, _ = page.load(fake_results(tmp_path))
    rows[0]["tasks"][0]["truth"] = 3
    with pytest.raises(ValueError, match="truth"):
        count.count_data(rows)


def test_reveal_is_hidden_until_a_count_is_entered(tmp_path):
    rows, _ = page.load(fake_results(tmp_path))
    html = page.render(rows, [], clip=True, count=True)
    b = block(html)
    assert '<form id="count-form" hidden>' in b                       # no JS: no box, a closed reveal
    assert '<details id="count-reveal">' in b and "<details id=\"count-reveal\" open" not in b
    assert b.index('id="count-reveal"') < b.index('<p class="truth">')    # the truth only inside the reveal
    assert b.index("<video") < b.index("<form")
    assert f'<video src="{count.MP4}" poster="{count.POSTER}"' in b and "autoplay" not in b.split("<details")[0]
    assert 'src="clip.mp4"' in b.split('<details id="count-reveal">')[1]   # the clip shows the answer: inside
    assert html.index('id="count"') < html.index('id="leaderboard"')
    assert html.index('class="jump"') < html.index('id="count"')         # after the first-screen links
    assert '<label for="count-n">' in b and 'aria-live="polite"' in b
    assert "reveal.hidden = true" in b and "fetch(" not in b and "http" not in page.COUNT_JS
    assert ".count [hidden] { display: none; }" in html                 # the flex form still hides


def test_chinese_block(tmp_path):
    rows, _ = page.load(fake_results(tmp_path))
    en, zh = (page.render(rows, [], clip=True, count=True, lang=x) for x in ("en", "zh"))
    b = block(zh)
    assert "自己数一数" in b and f"真实值：{TRUTH} 次" in b and "静帧赛道" in b and "盲猜（没看视频）" in b
    assert page.ZH[count.QUESTION] in b and count.QUESTION not in b
    assert f'<video src="../{count.MP4}" poster="../{count.POSTER}"' in b
    assert f"你也来数：{page.PAGE_URL}zh/#count" in b
    assert re.findall(r' id="([^"]+)"', block(en)) == re.findall(r' id="([^"]+)"', b)
    for text in ("Count it yourself", "Show the answers", "Your count", "Blind guess"):
        assert text not in b


def test_a_missing_translation_raises(monkeypatch, tmp_path):
    rows, _ = page.load(fake_results(tmp_path))
    monkeypatch.delitem(page.ZH, "Count it yourself")
    with pytest.raises(KeyError):
        page.count_block(rows, "zh")


@needs_ffmpeg
def test_page_builds_the_question_video(tmp_path):
    out = tmp_path / "site"
    assert page.main([str(fake_results(tmp_path)), str(out)]) == 0
    mp4, jpg = out / count.MP4, out / count.POSTER
    assert 100_000 < mp4.stat().st_size < 1_000_000 and 1_000 < jpg.stat().st_size < 200_000
    streams = media.ffprobe("-show_entries", "stream=codec_name,codec_type,width,height", "-of", "csv=p=0", mp4)
    assert streams.split() == ["h264,video,640,360"]                    # no audio stream
    assert abs(media.duration_s(mp4) - suite3.JUG_S) < 0.05
    head = mp4.read_bytes()[:64 * 1024]
    assert head.find(b"moov") != -1 and head.find(b"moov") < max(head.find(b"mdat"), 1 << 30)   # index first
    for d in (out, out / "zh"):
        assert 'id="count"' in (d / "index.html").read_text(encoding="utf8")
        assert page_check.problems(d) == []
