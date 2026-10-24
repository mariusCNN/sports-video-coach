"""The findings article next to the leaderboard: its numbers come from the page's functions, its links resolve."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from sports_video_coach import demo, page_check
from sports_video_coach.bench import effort as effort_chart
from sports_video_coach.bench import findings as F
from sports_video_coach.bench import page

RESULTS = Path(__file__).resolve().parent.parent / "benchmark" / "results"


@pytest.fixture(scope="module")
def rows():
    rows, _ = page.load(RESULTS)
    assert rows, "the repo's benchmark/results is the data this article is about"
    return rows


@pytest.fixture(scope="module")
def site(tmp_path_factory, rows):
    """The leaderboard and the article written the way `bench page` writes them."""
    out = tmp_path_factory.mktemp("site") / "benchmark"
    assert page.main([str(RESULTS), str(out)]) == 0
    return out


def n3(v):
    return f"{v:.3f}"


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_numbers_equal_the_page_functions(rows):
    d = F.findings_data(rows)
    fresh = [r for r in rows if page.suite_of(r) == F.BOARD and page.track_of(r) == F.TRACK]
    summary = {x["key"]: x for x in page.summarize(fresh)}
    html = text(F.render(rows, "en", None, d))

    # effort: the bars are effort_data's, and the answer quotes the widest pair
    assert d["effort"]["data"] == effort_chart.effort_data(rows)
    b = d["effort"]["best"]
    assert f'from {n3(b["lo"]["above"])}' in html and f'to {n3(b["hi"]["above"])}' in html

    # floor: each suite's blind guess is the board's floor row; fresh floors are seed_floor's mean
    for s in d["floor"]["suites"]:
        assert s["total"] == float(page.floor_of(F.board_rows(rows, s["suite"], F.TRACK))["total"])
        assert f'{s["suite"]}: {n3(s["total"])}' in html
    seeds = []
    for r in fresh:
        if not page.is_baseline(r):
            f = page.seed_floor(str(r.get("suite") or page.SUITE), page.track_of(r), r["seed"])
            seeds.append(sum(f.values()) / len(f))
    assert sorted(d["floor"]["seeds"]) == sorted(seeds)
    assert f'{n3(d["floor"]["lo"])}–{n3(d["floor"]["hi"])}' in html

    # every contender row on the fresh board is summarize's
    for x in d["cost"]["summary"]:
        assert x == summary[x["key"]]
        assert f'{n3(x["above"])}' in html
    w = d["floor"]["worst"]
    assert f'totals {n3(w["total"])} but is only {n3(w["above"])}' in html

    # code track: counts straight from the result files
    code = [r for r in rows if page.track_of(r) == page.TRACK and not page.is_baseline(r)]
    assert d["code"]["n"] == len(code)
    assert d["code"]["ones"] == sum(1 for r in code if float(r["total"]) == 1)
    assert d["code"]["lo"] == min(float(r["total"]) for r in code)
    assert f'{d["code"]["ones"]} of {d["code"]["n"]} code-track runs' in html

    # local model: above_value against its board's floor
    for x in d["local"]["runs"]:
        r = next(r for r in rows if r["_file"] == x["file"])
        floor_row = page.floor_of(F.board_rows(rows, page.suite_of(r), F.TRACK))
        assert x["above"] == page.above_value(r, F.floor_scores(floor_row))
        assert x["total"] == float(r["total"])

    # cost: cheapest at TOP or more, with summarize's cost and time
    c = d["cost"]["cheap"]
    assert c["above"] >= F.TOP and page.usd(c["cost"]) in html and page.wall(c["secs"]) in html

    # fails: page.fails' scores, the hardest task over runs that answered
    mine = [r for r in fresh if not page.is_baseline(r)]
    silent = {r["_file"] for r in mine if effort_chart.no_answer(r)}
    task = next(t for t in page.fails(mine, F.BOARD) if t["id"] == d["fails"]["hard"])
    scores = [x["score"] for x in task["runs"] if x["score"] is not None and x["file"] not in silent]
    assert d["fails"]["hard_mean"] == round(sum(scores) / len(scores), 3) and d["fails"]["hard_n"] == len(scores)
    assert f'mean score of {n3(d["fails"]["hard_mean"])} over the {len(scores)} runs' in html

    assert d["runs"] == sum(1 for r in rows if not page.is_baseline(r))
    assert d["date"] == max(str(r["date"]) for r in rows if r.get("date"))


def test_written_by_bench_page_with_head_tags(site, rows):
    for lang, path in (("en", site / "findings" / "index.html"), ("zh", site / "zh" / "findings" / "index.html")):
        html = path.read_text(encoding="utf8")
        assert f'<link rel="canonical" href="{F.URLS[lang]}">' in html
        assert all(f'href="{u}"' in html for u in F.URLS.values())   # hreflang both ways
        assert '<meta property="og:type" content="article">' in html and 'name="twitter:card"' in html
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        assert ld["@type"] == "Article" and ld["url"] == F.URLS[lang]
        assert ld["datePublished"] == F.findings_data(rows)["date"]
        assert '<a href="../#rerun">' in html and page.WANTED_URL in html and "coding agent" in html.replace(
            "编程 agent", "coding agent")
    assert '<a href="findings/">' in (site / "index.html").read_text(encoding="utf8")
    assert '<a href="findings/">' in (site / "zh" / "index.html").read_text(encoding="utf8")


def test_links_and_anchors_resolve_in_the_built_site(site):
    for path in (site / "findings" / "index.html", site / "zh" / "findings" / "index.html"):
        html = path.read_text(encoding="utf8")
        for href in re.findall(r'href="([^"]+)"', html):
            if urlsplit(href).scheme:
                continue
            target, _, anchor = href.partition("#")
            dest = (path.parent / target).resolve()
            if dest.is_dir():
                dest = dest / "index.html"
            if dest.parent == site.parent.resolve() and not dest.exists():
                continue   # the site home is written by build_site, not by `bench page`
            assert dest.exists(), (path, href)
            if anchor:
                assert f'id="{anchor}"' in dest.read_text(encoding="utf8"), (path, href)
        assert page_check.problems(path.parent) == []


def test_sitemap_lists_both_pages():
    xml = demo.sitemap_xml()
    assert f"<loc>{F.URLS['en']}</loc>" in xml and f"<loc>{F.URLS['zh']}</loc>" in xml


def test_zh_has_every_string(rows):
    F.render(rows, "zh")   # t() raises KeyError on a missing entry
    with pytest.raises(KeyError):
        F.t("not a translated string", "zh")


def test_no_results_say_no_findings_yet(tmp_path):
    html = F.render([], "en")
    assert "No runs yet, so no findings yet." in html and 'class="finding"' not in html
    assert "还没有运行记录" in F.render([], "zh")
    assert '"datePublished"' not in html
