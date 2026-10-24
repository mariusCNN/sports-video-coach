"""The humanize check: stock AI phrasing in reports and scripts, and the run steps that wait on it."""
from pathlib import Path

from sports_video_coach import guide, humanize, plugin


def test_flags_chinese_stock_phrasing_and_keeps_plain_coach_talk():
    found = humanize.findings("问题不在他，在于没人接应。值得注意的是，第三节只回防一人。为什么？因为他在看球。", "zh")
    assert any("不在" in f for f in found)
    assert any("值得注意" in f for f in found)
    assert any("自问自答" in f for f in found)
    assert humanize.findings("他没错，是没人去接他。第三节，只有一个人回防。他在看球，没跑。", "zh") == []


def test_flags_english_stock_phrasing():
    found = humanize.findings("It's not about effort, it's about timing. Moreover, this is crucial. Why? He froze.", "en")
    assert len(found) == 4
    assert humanize.findings("You were working. You were just late. Only one guy got back.", "en") == []


def test_slide_labels_count_only_in_spoken_paragraphs_and_pointing_is_fine():
    text = "## 练习：四打四\n\n练习：四打四转换。看：他停在中线。\n\n![下场目标：至少八次](stat:8)\n"
    found = humanize.findings(text, "zh", spoken=True)
    assert len(found) == 1 and "练习：四打四转换" in found[0]  # the heading and the caption are shown, not spoken
    assert humanize.findings(text, "zh") == []  # a report: labels are headings' business
    assert humanize.findings("Now watch: he stops. 12:05 he goes.", "en", spoken=True) == []


def test_notes_and_targets_are_not_checked():
    text = "# 不是笔记，而是给自己看的\n![看这一球](clip:01:00-01:10)\n> 01:05 0.4,0.6 \"只有一人回防\"\n"
    assert humanize.spoken_text(text) == [("shown", "看这一球"), ("shown", "只有一人回防")]
    assert humanize.findings(text, "zh") == []


def test_dense_dashes_are_flagged():
    assert any("破折号" in f for f in humanize.findings("他跑了——没回防——又丢一球——" * 2, "zh"))
    assert humanize.findings("One dash — fine. " + "A plain sentence. " * 30, "en") == []


def test_checks_name_the_file_and_the_guide(tmp_path: Path):
    (tmp_path / "README.md").write_text("总的来说，回防慢。", encoding="utf8")
    (tmp_path / "listen.en.md").write_text("Let's dive in.", encoding="utf8")
    found = humanize.checks([tmp_path / "README.md", tmp_path / "listen.en.md", tmp_path / "film.zh.md"], ["zh"])
    assert found[0].startswith("README.md: ") and found[1].startswith("listen.en.md: ")
    assert "guide humanize" in found[-1]
    assert humanize.checks([tmp_path / "film.zh.md"]) == []
    assert humanize.main([str(tmp_path)]) == 1


def test_every_plugin_has_the_humanize_guide():
    assert "humanize" in guide.guides(plugin.get("generic"))
    bb = plugin.get("basketball")
    if bb.prompts and Path(bb.prompts).is_dir():
        assert guide.guides(bb)["humanize"].name == "humanize.md"
