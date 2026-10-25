from sports_video_coach import page_check as PC

HEAD = '<html><head><meta name="viewport" content="width=device-width"></head><body>'


def page(folder, body, head=HEAD):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(head + body + "</body></html>", encoding="utf8")
    return folder


def test_a_clean_page_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "playable_s", lambda p: 4.0)
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "0001-0005.mp4").write_bytes(b"x")
    (tmp_path / "listen.en.mp3").write_bytes(b"x")
    page(tmp_path, '<a href="#en-s1">1</a><h2 id="en-s1">x</h2><video src="clips/0001-0005.mp4"></video>'
                   '<audio src="listen.en.mp3"></audio><a href="https://example.com">x</a><link href="data:,">')
    assert PC.problems(tmp_path) == []
    assert PC.main([str(tmp_path)]) == 0


def test_each_problem_is_named(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "playable_s", lambda p: 0.0 if p.name == "0009-0012.mp4" else 4.0)
    (tmp_path / "clips").mkdir()
    for n in ("0001-0005.mp4", "0005-0009.mp4", "0009-0012.mp4"):
        (tmp_path / "clips" / n).write_bytes(b"x")
    page(tmp_path, '<a href="#zh-s9">x</a><video src="clips/0001-0005.mp4"></video>'
                   '<video src="clips/0009-0012.mp4"></video><img src="charts/missing.png">'
                   '<p>C:\\Users\\someone\\video.mp4</p>', head="<html><body>")
    errs = "\n".join(PC.problems(tmp_path))
    assert "#zh-s9 has no element" in errs
    assert "charts/missing.png does not exist" in errs
    assert "clips/0005-0009.mp4 is not linked" in errs
    assert "clips/0009-0012.mp4 has no playable length" in errs
    assert "local disk path" in errs and "viewport" in errs
    assert PC.main([str(tmp_path)]) == 1


def test_no_page_says_how_to_make_one(tmp_path):
    assert "sports-video-coach html" in PC.problems(tmp_path)[0]


def test_english_left_in_the_chinese_report_is_a_warning_not_a_failure(tmp_path, capsys):
    page(tmp_path, '<article class="report" data-lang="en" lang="en"><p>keep your hips low</p></article>'
                   '<article class="report" data-lang="zh" lang="zh-CN"><p>落地后 keep your hips low，再起跳。</p>'
                   '<p>协防轮转（help the helper）。对手 <b>Riverside Owls</b> 用 ACL 和 mp4。</p></article>')
    warns = PC.warnings(tmp_path)
    assert len(warns) == 1 and "1 English phrase" in warns[0] and "'keep your hips low'" in warns[0]
    assert PC.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "warning: 1 English phrase" in out and ": OK (" in out
    assert PC.main([str(tmp_path), "--strict"]) == 1
    out = capsys.readouterr().out
    assert ": FAIL (1 warning, --strict)" in out and ": OK (" not in out   # never OK over an exit 1
    page(tmp_path, '<article class="report" lang="zh"><p>重心偏后（unclear），可能是likely站位。</p></article>')
    assert "2 English phrase" in PC.warnings(tmp_path)[0]                 # the guides' hedges, even in a gloss


def test_style_and_script_inside_a_report_are_not_report_text(tmp_path):
    # a plugin panel may carry its own <style> inside the report part; its CSS is not English left in the text
    page(tmp_path, '<article class="report" lang="zh-CN"><style>.bars{border-top:2px solid var(--ink)}</style>'
                   '<script>const shown = "keep your hips low";</script><p>第 4 次挥拍击球点偏低。</p></article>')
    assert PC.warnings(tmp_path) == []


def test_bold_that_did_not_render_is_a_warning(tmp_path):
    page(tmp_path, '<article class="report" lang="zh-CN"><p>**一句话：**第 4 次挥拍击球点偏低。</p></article>')
    warns = PC.warnings(tmp_path)
    assert len(warns) == 1 and "1 literal ** in the Chinese report" in warns[0]
    page(tmp_path, '<article class="report" lang="zh-CN"><p><strong>一句话：</strong>第 4 次挥拍击球点偏低。</p></article>')
    assert PC.warnings(tmp_path) == []


def test_scripts_are_checked_for_leftover_english_mojibake_and_french_quotes(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "playable_s", lambda p: 4.0)
    page(tmp_path, '<article class="report" lang="fr-FR"><p>Le service tombe court.</p></article>')
    (tmp_path / "listen.fr.md").write_text("# Narration\n\nBottom line : servez plus long, likely.\n"
                                           'Dites "fond" à chaque frappe. Ã©tÃ© trop court.\n', encoding="utf8")
    (tmp_path / "film.fr.md").write_text('# Vidéo\n\n![Service 1 : point haut](clip:00:01-00:08)\nRegardez.\n\n'
                                         '> 00:04 0.44,0.21 0.50,0.42 "point haut"\nIci, « fond ».\n', encoding="utf8")
    (tmp_path / "listen.en.md").write_text("# Narration\n\nServe longer, likely.\n", encoding="utf8")
    warns = PC.warnings(tmp_path)
    assert len(warns) == 3 and all("listen.fr.md (French)" in w for w in warns), warns
    assert "2 English phrase" in warns[0] and "'Bottom line'" in warns[0] and "mojibake" in warns[1]
    assert "« … »" in warns[2] and "1 straight-quoted" in warns[2]  # the mark line's "label" is syntax, not prose
    assert PC.main([str(tmp_path)]) == 0 and PC.main([str(tmp_path), "--strict"]) == 1
    assert PC.script_text('> 00:04 0.1,0.2 "haut"\n![cap](clip:00:01-00:02)') == "haut\ncap"


def test_write_qa_drafts_qa_md_that_says_what_was_not_checked(tmp_path, monkeypatch, capsys):
    from sports_video_coach import pipeline as P
    from sports_video_coach.plugins.generic import unit as U
    monkeypatch.setattr(PC, "playable_s", lambda p: 4.0)
    folder = tmp_path / "a"
    page(folder, '<article class="report" lang="en"><p>Serve longer.</p></article>')
    (folder / "analysis.json").write_text('{"plugin": "generic", "sport": "volleyball", "languages": ["en"]}',
                                          encoding="utf8")
    assert PC.main([str(folder), "--write-qa"]) == 0
    text = (folder / "qa.md").read_text(encoding="utf8")
    assert text.startswith("PASS") and "NOT checked: the layout and the 390 px phone view, audio playback" in text
    g = U.Analysis.load(folder)
    assert f"checked: {P.qa_hash(g)}" in text and P.qa_errors(g) == [] and P.qa_checks(g) == []
    (folder / "listen.en.md").write_text("Ã© broken\n", encoding="utf8")
    assert P.qa_checks(g) and "mojibake" in P.qa_checks(g)[0]        # the run's qa step waits on it
    assert next(s for s in U.STEPS if s.name == "qa").checks is P.qa_checks
    with (folder / "qa.md").open("a", encoding="utf8") as f:
        f.write("\n## Agent notes\n\n- language switch checked by hand\n")
    PC.main([str(folder), "--write-qa"])                              # its own draft is rewritten
    text = (folder / "qa.md").read_text(encoding="utf8")
    assert text.startswith("FAIL") and text.endswith("## Agent notes\n\n- language switch checked by hand\n")
    assert text.count("\n## Agent notes") == 1 and "mojibake" not in text.split("\n## Agent notes")[1]
    PC.main([str(folder), "--write-qa"])
    assert (folder / "qa.md").read_text(encoding="utf8") == text      # the notes kept once, not stacked
    (folder / "qa.md").write_text("PASS\n\nchecked by hand in a browser\n", encoding="utf8")
    PC.main([str(folder), "--write-qa"])
    assert "by hand" in (folder / "qa.md").read_text(encoding="utf8")  # a qa.md written by hand is kept
    assert "was not written by page-check" in capsys.readouterr().out
