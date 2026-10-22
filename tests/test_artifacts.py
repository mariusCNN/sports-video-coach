import json
from pathlib import Path

import pytest

from sports_video_coach import artifacts, pipeline as P


class U(P.Unit):
    @classmethod
    def load(cls, folder: Path):
        return cls(folder, json.loads((folder / "game.json").read_text(encoding="utf8")))


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("SVC_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    return tmp_path / "ws"


def unit(tmp_path, data: dict) -> U:
    (tmp_path / "game.json").write_text(json.dumps(data), encoding="utf8")
    return U.load(tmp_path)


def tail_names(g) -> list[str]:
    steps = P.tail_steps(lambda g: g.folder / "v.mp4", "listen", "qa", "film")
    return [s.name for s in artifacts.keep(steps, g)]


def test_default_is_every_artifact_in_order(tmp_path, ws):
    assert artifacts.selected(unit(tmp_path, {})) == artifacts.NAMES
    assert tail_names(unit(tmp_path, {})) == ["clips", "listen-script", "narrate", "html", "qa", "publish",
                                              "film-script", "film"]


def test_html_keeps_qa_and_clips_and_drops_the_rest(tmp_path, ws):
    g = unit(tmp_path, {"artifacts": ["publish", "html"]})
    assert artifacts.selected(g) == ("clips", "html", "qa", "publish")
    assert tail_names(g) == ["clips", "html", "qa", "publish"]


def test_film_keeps_clips(tmp_path, ws):
    g = unit(tmp_path, {"artifacts": ["html", "film"]})  # the example the docs give
    assert artifacts.selected(g) == ("clips", "html", "qa", "film")
    assert tail_names(g) == ["clips", "html", "qa", "film-script", "film"]
    assert artifacts.check(["film"]) == ("clips", "film")


def test_profile_choice_applies_when_the_unit_has_none(tmp_path, ws):
    (ws / "profile.json").write_text(json.dumps({"artifacts": ["film"]}), encoding="utf8")
    assert tail_names(unit(tmp_path, {})) == ["clips", "film-script", "film"]
    assert artifacts.selected(unit(tmp_path, {"artifacts": ["clips"]})) == ("clips",)


def test_unknown_artifact_and_publish_without_html_exit(tmp_path, ws):
    with pytest.raises(SystemExit, match="unknown artifact.*'pdf'"):
        artifacts.selected(unit(tmp_path, {"artifacts": ["pdf"]}))
    with pytest.raises(SystemExit, match="needs 'html'"):
        artifacts.selected(unit(tmp_path, {"artifacts": ["publish"]}))


def test_drive_exits_on_a_bad_choice_before_running(tmp_path, ws):
    calls = []
    g = unit(tmp_path, {"artifacts": ["nope"]})
    with pytest.raises(SystemExit):
        P.drive(g, P.tail_steps(lambda g: g.folder / "v.mp4", "l", "q", "f"), runner=lambda *a, **k: calls.append(a))
    assert calls == []
