import pytest

from sports_video_coach import cli, guide


def test_guide_lists_prints_and_names_unknown_ones(capsys):
    assert guide.main([]) == 0
    listed = capsys.readouterr().out
    assert all(f"  {n}\n" in listed for n in ("review", "report", "narration", "film"))
    assert cli.main(["guide", "review"]) == 0
    assert "review.json" in capsys.readouterr().out
    assert guide.main(["film.md", "--path"]) == 0
    assert capsys.readouterr().out.strip().endswith("prompts/film.md")
    with pytest.raises(SystemExit) as e:
        guide.main(["nope"])
    assert "its guides: film, narration, report, review" in str(e.value.code)


def test_cli_prints_chinese_through_a_non_utf8_pipe(monkeypatch):
    import io
    import sys
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    cli.utf8_stdio()
    print("网球", end="")
    sys.stdout.flush()
    assert raw.getvalue().decode("utf8") == "网球"
