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
    page = (site / "demo" / "index.html").read_text(encoding="utf8")
    assert "noindex" not in page   # meant to be found
    assert f'<link rel="canonical" href="{demo.SITE_URL}demo/">' in page and '<link rel="canonical"' in home
    assert (site / "robots.txt").read_text(encoding="utf8") == demo.robots_txt()
    assert (site / "sitemap.xml").read_text(encoding="utf8") == demo.sitemap_xml()
    assert (site / demo.INDEXNOW_KEY_FILE).read_text(encoding="utf8") == demo.INDEXNOW_KEY
    assert page_check.problems(site) == [] and page_check.problems(site / "demo") == []


def test_search_engine_files_and_structured_data():
    import re
    import xml.etree.ElementTree as ET
    robots = demo.robots_txt()
    assert "User-agent: *" in robots and "Allow: /" in robots
    assert f"Sitemap: {demo.SITE_URL}sitemap.xml" in robots
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.fromstring(demo.sitemap_xml().encode()).findall("s:url/s:loc", ns)]
    assert locs == [demo.SITE_URL, demo.SITE_URL + "demo/", demo.SITE_URL + "benchmark/",
                    demo.SITE_URL + "benchmark/zh/", demo.SITE_URL + "benchmark/findings/",
                    demo.SITE_URL + "benchmark/zh/findings/"]
    assert all(u.startswith("https://") for u in locs)
    home = demo.landing(["film.en.mp4", "film.en.jpg"])
    assert f'href="{demo.SITE_URL}benchmark/"' in home   # the leaderboard, written by `bench page` in CI
    assert f'<link rel="canonical" href="{demo.SITE_URL}">' in home
    blob = re.search(r'<script type="application/ld\+json">(.*?)</script>', home, re.S).group(1)
    data = json.loads(blob)
    assert data["@type"] == "SoftwareApplication" and data["description"] == demo.PITCH
    assert data["codeRepository"] == demo.REPO_URL and "MIT" in data["license"]
    assert not {"aggregateRating", "review", "offers", "interactionStatistic"} & data.keys()   # no invented numbers
    title = re.search(r"<title>(.*?)</title>", home).group(1)
    assert all(p in title for p in ("sports video analysis", "basketball film review", "Claude Code", "Codex"))


def test_indexnow_key_and_body():
    import re
    assert re.fullmatch(r"[A-Za-z0-9-]{8,128}", demo.INDEXNOW_KEY)   # the protocol's key format
    body = demo.indexnow_body()
    assert body["host"] == "mariusding.github.io" and body["key"] == demo.INDEXNOW_KEY
    # the key file sits under the project path, which scopes it to URLs under SITE_URL: every URL must be there
    assert body["keyLocation"] == f"{demo.SITE_URL}{demo.INDEXNOW_KEY}.txt"
    assert body["urlList"] == list(demo.SITE_PAGES) and all(u.startswith(demo.SITE_URL) for u in body["urlList"])


def test_indexnow_dry_run_sends_nothing(capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used on --dry-run")
    monkeypatch.setattr(demo.urllib.request, "urlopen", boom)
    assert demo.main(["indexnow", "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out) == demo.indexnow_body()


@pytest.mark.parametrize("status,code", [(200, 0), (202, 0), (403, 1), (422, 1), (429, 1)])
def test_indexnow_posts_the_sitemap_and_reports_the_status(capsys, monkeypatch, status, code):
    import io
    import urllib.error
    sent = {}

    class Resp:
        def __init__(self, s):
            self.status = s

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        sent.update(url=req.full_url, method=req.get_method(), body=json.loads(req.data),
                    ctype=req.get_header("Content-type"))
        if status >= 400:
            raise urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(b""))
        return Resp(status)
    monkeypatch.setattr(demo.urllib.request, "urlopen", fake)
    assert demo.main(["indexnow"]) == code
    assert sent["url"] == "https://api.indexnow.org/indexnow" and sent["method"] == "POST"
    assert sent["ctype"] == "application/json; charset=utf-8" and sent["body"] == demo.indexnow_body()
    out = capsys.readouterr().out
    assert f"HTTP {status} " in out and demo.INDEXNOW_STATUS[status] in out


def test_indexnow_unreachable(capsys, monkeypatch):
    import urllib.error

    def fake(req, timeout=None):
        raise urllib.error.URLError("no network")
    monkeypatch.setattr(demo.urllib.request, "urlopen", fake)
    assert demo.main(["indexnow"]) == 1 and "could not reach" in capsys.readouterr().out
