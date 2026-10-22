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
