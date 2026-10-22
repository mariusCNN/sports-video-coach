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
