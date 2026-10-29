"""`sports-video-coach demo`: see every deliverable in about a minute, no agent and no video of your own.

Draws a synthetic video (a red block running a shuttle between two cones, no people), starts a generic analysis
unit from it, copies in a pre-written film review, report, narration and film script (`files/`), and runs the
normal pipeline: frames, clips, narration, page, a scripted QA self-check, explained video. With your own video
the agent writes those files; here they come with the package so the run needs nothing but ffmpeg (and the
network for edge-tts, unless --offline).

usage: sports-video-coach demo [--out <folder>] [--lang en zh] [--no-film] [--offline] [--site <folder>]
       sports-video-coach demo indexnow [--dry-run]   (tell IndexNow search engines the public site changed)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import INSTALL, media, page_check, pipeline as P, workspace
from .. import site_counter
from ..plugins.generic import new, unit as U

FILES = Path(__file__).parent / "files"
SECONDS = 22
# The block's x position (px) over time: four 4 s legs between the cones, turns of 1.5 s, 0.5 s and 1.5 s.
# The pre-written review and report describe exactly this; change both together.
PATH_X = ("if(lt(t,4),60+120*t,if(lt(t,5.5),540,if(lt(t,9.5),540-120*(t-5.5),if(lt(t,10),60,"
          "if(lt(t,14),60+120*(t-10),if(lt(t,15.5),540,if(lt(t,19.5),540-120*(t-15.5),60)))))))")


def draw_video(out: Path) -> Path:
    """Write the synthetic drill video: green floor, a white line, two orange cones, the red block."""
    floor = ("drawbox=x=0:y=260:w=640:h=4:c=white:t=fill,"
             "drawbox=x=40:y=232:w=20:h=28:c=0xff8c1a:t=fill,drawbox=x=580:y=232:w=20:h=28:c=0xff8c1a:t=fill")
    media.ffmpeg("-f", "lavfi", "-i", f"color=c=0x2f6b3a:s=640x360:r=25:d={SECONDS}",
                 "-f", "lavfi", "-i", f"color=c=0xd0312d:s=30x60:r=25:d={SECONDS}",
                 "-filter_complex", f"[0]{floor}[bg];[bg][1]overlay=x='{PATH_X}':y=200[v]",
                 "-map", "[v]", "-pix_fmt", "yuv420p", "-c:v", "libx264", out)
    return out


def copy_files(folder: Path, langs: list[str]) -> None:
    """The pre-written agent outputs, for the chosen languages; files already there are kept."""
    want = {"review.json": folder / "run" / "review" / "review.json"}
    for lang in langs:
        want[P.readme(lang)] = folder / P.readme(lang)
        want[f"listen.{lang}.md"] = folder / f"listen.{lang}.md"
        want[f"film.{lang}.md"] = folder / f"film.{lang}.md"
    for name, dst in want.items():
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FILES / name, dst)


def self_check(g: U.Analysis) -> list[str]:
    """What the page is missing (`page-check`: links, anchors, media), plus at least one cut clip. Not a browser."""
    errs = page_check.problems(g.folder)
    if not list(g.folder.glob("clips/*.mp4")):
        errs.append("no clips were cut")
    return errs


def write_qa(g: U.Analysis) -> None:
    errs = self_check(g)
    if errs:
        sys.exit("[demo] page self-check failed:\n  " + "\n  ".join(errs))
    text = ("PASS\n\nScripted self-check by `sports-video-coach demo` (`page-check`: links, anchors, every clip and "
            "audio file), not a browser check. With your own video the agent checks the page in a browser instead.\n\n"
            f"checked: {P.qa_hash(g)}\n")
    media.write_text_atomic(g.folder / "qa.md", text)


SITE_URL = "https://mariusding.github.io/sports-video-coach/"
REPO_URL = "https://github.com/mariusDing/sports-video-coach"
TRAINING_MEDIA = f"{REPO_URL}/releases/download/showcase-2026-10-29"
TAGLINE = "Your AI agent watches your game film and coaches you."
PITCH = ("Open-source sports video analysis and basketball analytics for athletes, coaches and AI agents. "
         "Turn your game or workout into a coaching page, source clips, narration, drills and an explained video.")
CARDS = (("Athletes", "One session in: what to fix, one drill, a check for next time."),
         ("Coaches", "A team report and focus-player deep dive, with clips, audio and optional unlisted sharing links."),
         ("Developers", "A resumable CLI that pauses (exit 3) whenever it needs the agent's eyes or words, with a "
                        "validator per agent step. A new sport plugin is one command."))
FEATURES = (
    ("Watch, read or listen", "Timestamped reviews, mobile reports, source clips and narrated MP4s. Generic reports support eight languages; basketball supports English and Chinese."),
    ("Basketball game analysis", "Player and ball tracking, shot charts, league statistics, Four Factors, possessions and lineups. Measurements and reviewed evidence support team and player coaching."),
    ("Practice and prepare", "Personal shooting sessions, movement review, training plans, cue audio, opponent scouting, season summaries, tactics replays and phone reels."),
    ("Built for coding agents", "Claude Code, Codex and other agents use JSON artifacts, writing guides and explicit exit codes. Resume completed stages or extend the workflow with a sport plugin."),
    ("OpenHoopVision evidence", "Optional shot, pass, dribble, rebound and possession-change candidates, plus pose and jersey evidence. Review decisions and source clips keep automatic suggestions inspectable."),
    ("Vision experiments you can check", "Compare WASB ball heatmaps, SAHI sliced detection and KaliCalib court proposals against independent labels. Interactive HTML and comparison videos expose misses, false positives and cost."),
)
TRY = (INSTALL, "sports-video-coach doctor", "sports-video-coach demo --offline")
REAL_GIF = "https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/real-session.gif"
CASE_URL = f"{SITE_URL}case-study/"
PLUGINS_URL = f"{REPO_URL}/blob/master/docs/plugins.md"
TITLE = "sports-video-coach - sports video analysis and basketball film review with Claude Code or Codex"
BENCH_URL = f"{SITE_URL}benchmark/"  # written by `bench page` in the demo-site workflow, not by build_site
SITE_PAGES = (SITE_URL, CASE_URL, f"{SITE_URL}demo/", BENCH_URL, f"{BENCH_URL}zh/",   # zh/: the Chinese leaderboard
              f"{BENCH_URL}findings/", f"{BENCH_URL}zh/findings/")       # the findings article, en and zh


def canonical(url: str) -> str:
    return f'<link rel="canonical" href="{url}">'


def json_ld() -> str:
    """The landing page's schema.org SoftwareApplication block: facts from the repo only (pyproject, LICENSE)."""
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "sports-video-coach",
        "description": PITCH,
        "url": SITE_URL,
        "codeRepository": REPO_URL,
        "sameAs": [REPO_URL],
        "license": "https://opensource.org/licenses/MIT",
        "operatingSystem": "Windows, Linux",
        "applicationCategory": "MultimediaApplication",
        "featureList": [title for title, _ in FEATURES],
        "isAccessibleForFree": True,
    }
    # "</" cannot appear in the JSON (only URLs and plain text), so the script element cannot be closed early
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


def robots_txt() -> str:
    # A project Pages site lives under /sports-video-coach/; crawlers read robots.txt only at the domain root
    # (mariusding.github.io/robots.txt), so this file is not read by them. It is kept for completeness; the
    # sitemap (submitted in Search Console or found via links) is what helps discovery.
    return f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n"


def sitemap_xml(lastmod: dict[str, str] | None = None) -> str:
    """The site's sitemap; `lastmod`: {page url: YYYY-MM-DD} for pages whose date is known (`bench page` passes the
    newest result file's date for the benchmark pages, never the build time)."""
    lastmod = lastmod or {}
    urls = "".join(f"  <url><loc>{u}</loc>{f'<lastmod>{lastmod[u]}</lastmod>' if u in lastmod else ''}</url>\n"
                   for u in SITE_PAGES)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')


# IndexNow (https://www.indexnow.org/documentation): a site proves it owns its URLs by hosting <key>.txt holding the
# key, then POSTs changed URLs once; Bing, Yandex, Seznam, Naver and the others share the submission. The key is a
# public ownership proof by design (anyone can read the file on the site), not a secret, so it lives in the code.
# A project Pages site cannot write the domain root (mariusding.github.io/), so the key file sits at SITE_URL and is
# named as keyLocation; a key file there covers only URLs under SITE_URL, which is every page we submit.
INDEXNOW_KEY = "bfa6c325a9ce2c6c52580f1b61b58b23"
INDEXNOW_KEY_FILE = f"{INDEXNOW_KEY}.txt"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
INDEXNOW_STATUS = {
    200: "OK: submitted",
    202: "accepted: received, the key is still being validated (usual on a first submission)",
    400: "bad request: invalid format",
    403: f"forbidden: key not valid (is {SITE_URL}{INDEXNOW_KEY_FILE} live and holding the key?)",
    422: "unprocessable: a URL is not on the host, or the key does not match the protocol",
    429: "too many requests: submitting too often; wait and send only changed URLs",
}


def indexnow_body() -> dict:
    """The IndexNow POST body: every page in the sitemap, the host, the key and where the key file is."""
    return {"host": SITE_URL.split("/")[2], "key": INDEXNOW_KEY, "keyLocation": f"{SITE_URL}{INDEXNOW_KEY_FILE}",
            "urlList": re.findall(r"<loc>([^<]+)</loc>", sitemap_xml())}


def indexnow(argv=None) -> int:
    """`demo indexnow`: notify IndexNow search engines of the public site's pages. Run by hand after a deploy that
    changed them, not on every push: resubmitting unchanged URLs wastes crawl quota and can get a 429."""
    ap = argparse.ArgumentParser(prog="sports-video-coach demo indexnow",
                                 description=f"POST the demo site's pages ({SITE_URL}) to {INDEXNOW_ENDPOINT}.")
    ap.add_argument("--dry-run", action="store_true", help="print the JSON body only, send nothing")
    a = ap.parse_args(argv)
    body = indexnow_body()
    text = json.dumps(body, indent=1)
    if a.dry_run:
        print(text)
        return 0
    req = urllib.request.Request(INDEXNOW_ENDPOINT, data=text.encode("utf8"), method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    except urllib.error.URLError as e:
        print(f"[indexnow] could not reach {INDEXNOW_ENDPOINT}: {e.reason}")
        return 1
    print(f"[indexnow] HTTP {status} {INDEXNOW_STATUS.get(status, 'unexpected status')} ({len(body['urlList'])} URLs)")
    return 0 if status in (200, 202) else 1


def version() -> str:
    """The installed package's version ('' when it runs from a tree that was never installed)."""
    from importlib.metadata import PackageNotFoundError, version as v
    try:
        return v("sports-video-coach")
    except PackageNotFoundError:
        return ""


def version_note(ver: str) -> str:
    """The landing page's version line: a build from master between releases says so, rather than looking like a
    release that is not on the releases page."""
    if not ver:
        return ""
    if ".dev" in ver:
        return f" Built from master ({ver}, not released yet)."
    return f" Version {ver}."


def landing(films: list[str]) -> str:
    """The English landing page of the demo site: tagline, pitch, the explained video, three cards, how to try it,
    links and the version."""
    ver = version()
    try_it = "\n".join(TRY)
    video = ""
    if "film.en.mp4" in films:
        poster = ' poster="film.en.jpg"' if "film.en.jpg" in films else ""
        video = f'<video controls playsinline preload="none"{poster} src="film.en.mp4"></video>'
    other = " ".join(f'<a href="{f}">{f}</a>' for f in films if f.endswith(".mp4") and f != "film.en.mp4")
    cards = "".join(f"<section><h2>{t}</h2><p>{d}</p></section>" for t, d in CARDS)
    features = "".join(f"<section><h3>{t}</h3><p>{d}</p></section>" for t, d in FEATURES)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title>
<meta name="description" content="{PITCH}">
{canonical(SITE_URL)}
{json_ld()}
<meta property="og:title" content="sports-video-coach: {TAGLINE}">
<meta property="og:description" content="{PITCH}">
<meta property="og:image" content="{REAL_GIF}">
<meta property="og:url" content="{SITE_URL}">
<meta name="twitter:card" content="summary_large_image">
<style>
body {{ margin: 0; font: 17px/1.55 system-ui, sans-serif; color: #1d1b38; background: #f6f5fb; }}
main {{ max-width: 46rem; margin: 0 auto; padding: 2rem 1.1rem 3rem; }}
h1 {{ font-size: clamp(1.6rem, 5vw, 2.3rem); line-height: 1.2; margin: .2rem 0 .8rem; }}
.name {{ font-weight: 700; color: #5c5a86; margin: 0; }}
video {{ width: 100%; border-radius: 10px; background: #221f45; margin: 1.2rem 0 .4rem; }}
.walkthrough {{ margin: 1.2rem 0; }}
.walkthrough img {{ display: block; width: 100%; height: auto; border-radius: 10px; }}
figcaption {{ font-size: .9rem; color: #5c5a86; margin-top: .5rem; }}
summary {{ cursor: pointer; font-weight: 600; }}
.cards {{ display: grid; gap: .8rem; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); margin: 1.4rem 0; }}
.cards section {{ background: #fff; border-radius: 10px; padding: .9rem 1rem; box-shadow: 0 1px 3px #0001; }}
.cards h2 {{ font-size: 1.05rem; margin: 0 0 .3rem; }}
.cards h3 {{ font-size: 1.05rem; margin: 0 0 .3rem; }}
.cards p {{ margin: 0; font-size: .95rem; }}
.feature-title {{ margin: 2rem 0 .5rem; font-size: 1.4rem; }}
.note {{ background: #eae7f4; border-radius: 10px; padding: .9rem 1rem; font-size: .95rem; }}
.go {{ display: flex; flex-wrap: wrap; gap: .6rem; }}
.go a {{ padding: .6rem 1rem; border-radius: 999px; background: #221f45; color: #fff; font-weight: 600;
        text-decoration: none; }}
.go a + a {{ background: #fff; color: #221f45; border: 1px solid #221f45; }}
small {{ display: block; margin-top: 1.4rem; color: #5c5a86; }}
h2.try {{ font-size: 1.1rem; margin: 1.6rem 0 .4rem; }}
pre {{ background: #221f45; color: #fff; border-radius: 10px; padding: .8rem 1rem; overflow-x: auto;
      font-size: .9rem; margin: 0 0 .4rem; }}
</style>
</head>
<body>
<main>
<p class="name">sports-video-coach</p>
<h1>{TAGLINE}</h1>
<p>{PITCH}</p>
<section id="training-example">
<h2 class="feature-title">A real training review in 43 seconds</h2>
<video controls playsinline preload="none" poster="{TRAINING_MEDIA}/poster-en-wide.jpg"
 src="{TRAINING_MEDIA}/sports-video-coach-en-wide.mp4" aria-label="English basketball training review showcase"></video>
<p>Original footage, freeze-frame cues, two selected attempts, and a next-practice suggestion.
This agent-reviewed example is edited for length; it does not measure improvement or shooting accuracy.</p>
<p><a href="{TRAINING_MEDIA}/sports-video-coach-en-vertical.mp4">Watch the vertical version</a> ·
<a href="{REPO_URL}/releases/tag/showcase-2026-10-29">Video files and context</a> ·
<a href="case-study/">A shooting-drill walkthrough</a></p>
</section>
<h2 class="feature-title">Explore a complete coaching-page demo</h2>
{video}
<div class="cards">{cards}</div>
<p class="go"><a href="demo/">Open the demo coaching page</a><a href="{REPO_URL}">Get it on GitHub</a></p>
<h2 class="feature-title">From game film to the next practice</h2>
<div class="cards">{features}</div>
<p><a href="{REPO_URL}/blob/master/docs/features.md">Explore every feature and command</a> ·
<a href="{REPO_URL}/blob/master/README.zh.md">中文介绍</a> ·
<a href="{REPO_URL}/blob/master/llms.txt">Agent documentation index</a></p>
<p class="note"><strong>Choose the depth you need.</strong> Generic film review needs no GPU. Basketball vision
needs its tracking dependencies and usable footage. WASB, SAHI and KaliCalib are opt-in experiments, with mixed
results in the first diagnostic; they do not automatically replace official stats or reviewed calibration.
<a href="{REPO_URL}/blob/master/docs/perception-lab.md">Read the measured results and limitations</a>.</p>
<p>Vision runs locally. Frames your agent views go to its model provider; narration uses online text-to-speech.
Publishing is optional. <a href="{REPO_URL}/blob/master/docs/privacy.md">Privacy and sharing</a>.</p>
<h2 class="try">Check your setup, then try a local demo</h2>
<pre><code>{try_it}</code></pre>
<p>Needs ffmpeg and ffprobe. The offline demo uses no agent or online speech service.
For your own video, ask your agent to run <code>sports-video-coach run &lt;video&gt; --quick</code>:
one English page with clips and QA first; use <code>--lang</code> for another language. Your agent plan is used for the review.</p>
<p>Your sport needs more than frames? <a href="{PLUGINS_URL}">Write a plugin for your sport</a>.</p>
<p>Which coding agent reviews sports film best? See the <a href="{BENCH_URL}">benchmark leaderboard</a>.</p>
<small>The coaching-page demo is synthetic: a drawn drill video (a red block between two cones) and a pre-written review, so
no person appears. {("Other languages: " + other) if other else ""}{version_note(ver)}</small>
</main>
{site_counter.tag()}
</body>
</html>
"""


def case_study() -> str:
    """A public walkthrough of the author's already-published GIF, without exposing additional session data."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>A real shooting session — sports-video-coach</title>{canonical(CASE_URL)}
<meta name="description" content="Watch the author's shooting drill become an agent review and a coaching page.">
<meta property="og:title" content="My coding agent reviews my shooting drill">
<meta property="og:image" content="{REAL_GIF}"><meta property="og:url" content="{CASE_URL}">
<meta name="twitter:card" content="summary_large_image">
<style>
body {{ margin:0; font:17px/1.55 system-ui,sans-serif; color:#1d1b38; background:#f6f5fb; }}
main {{ max-width:46rem; margin:auto; padding:1.5rem 1.1rem 3rem; }}
h1 {{ font-size:clamp(1.8rem,5vw,2.5rem); line-height:1.15; }}
h2 {{ font-size:1.2rem; }} img {{ width:100%; height:auto; border-radius:12px; }}
figure {{ margin:1.5rem 0; }} figcaption,small {{ color:#5c5a86; font-size:.9rem; }}
section {{ background:white; border-radius:12px; padding:1rem 1.2rem; margin:1rem 0; }}
a {{ color:#403586; }} .action {{ display:inline-block; padding:.7rem 1rem; background:#221f45;
color:white; border-radius:999px; text-decoration:none; margin:.4rem .4rem .4rem 0; }}
li {{ margin:.4rem 0; }} summary {{ cursor:pointer; font-weight:600; }}
</style></head><body><main>
<a href="../">sports-video-coach</a><h1>My coding agent reviews my shooting drill.</h1>
<p>A real run on the author's own phone video: the drill, a review moment, then the coaching page.</p>
<figure><img src="{REAL_GIF}" width="720" height="480"
alt="The author's shooting drill, the agent's review pausing on the held finish, then the coaching page">
<figcaption>The existing, publicly shared real-session walkthrough from this repository.</figcaption></figure>
<section><h2>Follow the video into the report</h2><ol>
<li><strong>The source:</strong> the author's own shooting practice.</li>
<li><strong>The review:</strong> the agent looks at timestamped frames and identifies moments to revisit.</li>
<li><strong>The result:</strong> a coaching page brings the observations and relevant clips together.</li>
</ol></section>
<section><h2>Try it on a short clip of your own</h2>
<p>Start with one drill, keep the athlete in view, and say who the agent should watch.
The quick workflow builds a page and clips before adding narration or an explained video.</p>
<a class="action" href="{REPO_URL}#try-it">Open the quick-start instructions</a>
<a href="../demo/">Explore the synthetic sample report</a></section>
<details><summary>What this walkthrough establishes</summary>
<p>It shows a real session's workflow and output. It is an edited walkthrough, not a controlled test of coaching
accuracy or improvement. The complete source video, full review and model billing record are not published here.</p>
<p>The interactive sample report uses synthetic footage and a pre-written review; the
<a href="{BENCH_URL}">benchmark</a> separately tests counting and timing on generated drills.</p></details>
<p><a href="{REPO_URL}">View the source on GitHub</a> · MIT · Alpha</p>
</main>{site_counter.tag()}</body></html>"""


def build_site(folder: Path, site: Path) -> list[str]:
    """The public demo site from a finished demo folder: an English landing page at the root, the coaching page
    under demo/, the explained videos and posters at the root. Returns warnings (see publish.build_report)."""
    from .. import publish
    warnings = publish.build_report(folder, site / "demo")
    page = site / "demo" / "index.html"
    # the demo is synthetic and meant to be found and shared; real report pages keep noindex and no preview
    card = "\n".join([
        canonical(f"{SITE_URL}demo/"),
        '<meta property="og:title" content="sports-video-coach demo: a coaching page made from one video">',
        f'<meta property="og:description" content="{PITCH}">',
        f'<meta property="og:image" content="{SITE_URL}film.en.jpg">',
        f'<meta property="og:url" content="{SITE_URL}demo/">',
        '<meta name="twitter:card" content="summary_large_image">'])
    banner = ('<p style="margin:0;padding:.6rem 1rem;background:#221f45;color:#fff;font:15px/1.4 system-ui,sans-serif;'
              'text-align:center">Synthetic demo (a drawn video, a pre-written review). Made by '
              f'<a href="{REPO_URL}" style="color:#fff;font-weight:600">sports-video-coach</a>: '
              'run it on your own video.</p>')
    text = page.read_text(encoding="utf8")
    for old, new in (('<meta name="robots" content="noindex, nofollow">', card), ("<body>", "<body>\n" + banner)):
        if text.count(old) != 1:
            raise SystemExit(f"demo site: page template changed, {old!r} not found once")
        text = text.replace(old, new)
    page.write_text(text, encoding="utf8")
    films = sorted(folder.glob("film.*.mp4")) + sorted(folder.glob("film.*.jpg"))
    for f in films:
        shutil.copy2(f, site / f.name)
    (site / "index.html").write_text(landing([f.name for f in films]), encoding="utf8")
    (site / "case-study").mkdir(exist_ok=True)
    (site / "case-study" / "index.html").write_text(case_study(), encoding="utf8")
    (site / "robots.txt").write_text(robots_txt(), encoding="utf8")
    (site / "sitemap.xml").write_text(sitemap_xml(), encoding="utf8")
    (site / INDEXNOW_KEY_FILE).write_text(INDEXNOW_KEY, encoding="utf8")  # IndexNow ownership proof, public
    return warnings


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "indexnow":
        return indexnow(argv[1:])
    ap = argparse.ArgumentParser(prog="sports-video-coach demo", description=__doc__.split("\n\n")[0],
                                 epilog="sports-video-coach demo indexnow [--dry-run]: tell IndexNow search engines "
                                        "(Bing, Yandex, ...) the public site's pages; run by hand after a deploy")
    ap.add_argument("--out", help="the demo folder (default: <workspace>/analysis/demo/<today>)")
    ap.add_argument("--lang", nargs="+", choices=["en", "zh"], default=["en"], help="languages (default: en)")
    ap.add_argument("--no-film", action="store_true", help="stop after the page (skips the explained video)")
    ap.add_argument("--offline", action="store_true",
                    help="no network: clips and the page only (narration and the film need online text-to-speech)")
    ap.add_argument("--site", help="also write the public demo site here: English landing page, coaching page in demo/")
    a = ap.parse_args(argv)
    if not (shutil.which(media.ffmpeg_exe()) and shutil.which("ffprobe")):
        sys.exit("[demo] needs ffmpeg and ffprobe on PATH (https://ffmpeg.org/download.html)")
    t0 = time.monotonic()
    folder = (Path(a.out) if a.out else workspace.root() / "analysis" / "demo" / time.strftime("%Y-%m-%d")).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / "drill.mp4"
    if not video.exists():
        draw_video(video)
    new.main([str(video), "--sport", "shuttle run (synthetic demo)", "--focus", "the red block",
              "--name", "demo", "--lang", *a.lang, "--every", "2", "--out", str(folder)])
    arts = ["clips", "html"] if a.offline else ["clips", "narration", "html"] + ([] if a.no_film else ["film"])
    gj = folder / "analysis.json"
    data = json.loads(gj.read_text(encoding="utf8"))
    if data.get("artifacts") != arts:
        media.write_text_atomic(gj, json.dumps({**data, "artifacts": arts}, ensure_ascii=False, indent=1) + "\n")
    copy_files(folder, a.lang)
    code = P.drive(U.Analysis.load(folder), U.STEPS, until="html")
    if code == 0:
        print("[demo] the page is built; next the QA stand-in, then the rest (the run goes on, nothing failed)")
        g = U.Analysis.load(folder)
        if not P.qa_done(g):
            write_qa(g)
            print("[demo] qa: wrote qa.md (scripted self-check, stands in for the agent's browser check)")
        code = P.drive(g, U.STEPS)
    if code != 0:
        print(f"[demo] stopped with exit {code}; the lines above say why. Fix that, then run the same command again "
              "to resume. No network for narration? `sports-video-coach demo --offline` makes the clips and the page.")
        return code
    print(f"\n[demo] done in {time.monotonic() - t0:.0f} s. Open {(folder / 'index.html').as_posix()} in a browser.")
    for lang in a.lang:
        if (folder / f"film.{lang}.mp4").exists():
            print(f"[demo] explained video: {(folder / f'film.{lang}.mp4').as_posix()}")
    if a.site:
        warnings = build_site(folder, Path(a.site))
        if warnings:
            sys.exit("[demo] site: " + "; ".join(warnings))
        print(f"[demo] site: {(Path(a.site) / 'index.html').as_posix()} (landing page), "
              f"{(Path(a.site) / 'demo' / 'index.html').as_posix()}")
    print("[demo] The video is drawn and the review is pre-written. With your own video, your agent writes them:\n"
          "       sports-video-coach run my_video.mp4 --sport tennis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
