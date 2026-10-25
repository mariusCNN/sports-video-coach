import pytest

from sports_video_coach import demo, site_counter
from sports_video_coach.bench import findings, page

PAGES = {
    "landing": lambda: demo.landing([]),
    "bench en": lambda: page.render([], [], lang="en"),
    "bench zh": lambda: page.render_zh([], []),
    "findings en": lambda: findings.render([], "en"),
    "findings zh": lambda: findings.render([], "zh"),
}


def test_no_counter_by_default(monkeypatch):
    monkeypatch.delenv(site_counter.ENV, raising=False)
    assert site_counter.tag() == ""
    for name, render in PAGES.items():
        assert "goatcounter" not in render(), name


@pytest.mark.parametrize("name", PAGES)
def test_counter_on_each_site_page(monkeypatch, name):
    monkeypatch.setenv(site_counter.ENV, "svc-demo")
    html = PAGES[name]()
    tag = ('<script data-goatcounter="https://svc-demo.goatcounter.com/count" async '
           'src="https://gc.zgo.at/count.js"></script>')
    assert html.count(tag) == 1 and html.index(tag) < html.index("</body>")


@pytest.mark.parametrize("code", ["", "  ", "-x", "a", "x.evil.com/count?", 'x"><script>', "a" * 51])
def test_invalid_code_gives_no_tag(monkeypatch, code):
    monkeypatch.setenv(site_counter.ENV, code)
    assert site_counter.tag() == ""


def test_report_pages_never_count(monkeypatch):
    monkeypatch.setenv(site_counter.ENV, "svc-demo")
    from pathlib import Path
    src = Path(site_counter.__file__).parent
    for name in ("render_html.py", "publish.py", "publish_worker.js"):
        assert "site_counter" not in (src / name).read_text(encoding="utf8"), name
