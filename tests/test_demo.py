import json
import shutil

import cv2
import pytest

from sports_video_coach import cli, demo, film, pipeline as P
from sports_video_coach.plugins.generic import unit as U

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")


def block_x(video, t: float) -> int:
    """Left edge (px) of the red block at time t."""
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, img = cap.read()
    cap.release()
    assert ok
    red = (img[:, :, 2] > 160) & (img[:, :, 1] < 90)
    return int(red.any(axis=0).argmax())


@needs_ffmpeg
def test_drawn_video_matches_the_prewritten_review(tmp_path):
    # the report claims turns of 1.5 s, 0.5 s and 1.5 s; the drawing must show exactly that
    v = demo.draw_video(tmp_path / "d.mp4")
    assert abs(block_x(v, 4.6) - 540) <= 4 and abs(block_x(v, 5.4) - 540) <= 4      # stalled at the right cone
    assert abs(block_x(v, 9.7) - 60) <= 4 and block_x(v, 10.6) > 100                # quick turn, already gone
    assert abs(block_x(v, 15.0) - 540) <= 4
    moments = json.loads((demo.FILES / "review.json").read_text(encoding="utf8"))["moments"]
    assert [m["what"][:4] for m in moments][:3] == ["04.0", "09.5", "14.0"]


def test_cli_lists_demo():
    assert cli.resolve("demo")[0] == "sports_video_coach.demo"


@needs_ffmpeg
def test_offline_demo_runs_to_done_without_an_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    out = tmp_path / "demo"
    assert demo.main(["--out", str(out), "--offline", "--lang", "en", "zh"]) == 0
    g = U.Analysis.load(out)
    assert not U.review_errors(g) and P.qa_done(g)
    assert sorted(p.name for p in (out / "clips").glob("*.mp4")) == ["0002-0008.mp4", "0008-0012.mp4", "0013-0018.mp4"]
    assert (out / "index.html").exists() and not (out / "listen.en.mp3").exists()
    assert demo.main(["--out", str(out), "--offline"]) == 0       # a second run resumes: nothing left to do


@needs_ffmpeg
def test_film_scripts_check_clean(tmp_path):
    v = demo.draw_video(tmp_path / "d.mp4")
    for lang in ("en", "zh"):
        scenes = film.parse_script((demo.FILES / f"film.{lang}.md").read_text(encoding="utf8"))
        assert len(scenes) >= 4 and film.check(scenes, tmp_path, v, demo.SECONDS) == []


@needs_ffmpeg
def test_version_note_marks_a_build_from_master():
    assert demo.version_note("0.3.0") == " Version 0.3.0."
    assert "not released yet" in demo.version_note("0.3.1.dev0") and "Version" not in demo.version_note("0.3.1.dev0")
    assert demo.version_note("") == ""


def test_site_opens_on_an_english_landing_page(tmp_path, monkeypatch):
    from sports_video_coach import page_check
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path / "ws"))
    out, site = tmp_path / "demo", tmp_path / "site"
    assert demo.main(["--out", str(out), "--offline", "--lang", "en", "zh", "--site", str(site)]) == 0
    home = (site / "index.html").read_text(encoding="utf8")
    assert '<html lang="en">' in home and demo.TAGLINE in home and 'href="demo/"' in home
    assert all(f"<h2>{t}</h2>" in home for t, _ in demo.CARDS)
    assert all(cmd in home for cmd in demo.TRY) and f'href="{demo.PLUGINS_URL}"' in home
    assert demo.version() and demo.version_note(demo.version()) in home
    assert "noindex" not in (site / "demo" / "index.html").read_text(encoding="utf8")   # meant to be found
    assert page_check.problems(site) == [] and page_check.problems(site / "demo") == []
