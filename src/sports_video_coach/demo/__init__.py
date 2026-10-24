"""`sports-video-coach demo`: see every deliverable in about a minute, no agent and no video of your own.

Draws a synthetic video (a red block running a shuttle between two cones, no people), starts a generic analysis
unit from it, copies in a pre-written film review, report, narration and film script (`files/`), and runs the
normal pipeline: frames, clips, narration, page, a scripted QA self-check, explained video. With your own video
the agent writes those files; here they come with the package so the run needs nothing but ffmpeg (and the
network for edge-tts, unless --offline).

usage: sports-video-coach demo [--out <folder>] [--lang en zh] [--no-film] [--offline] [--site <folder>]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

from .. import media, page_check, pipeline as P, workspace
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
TAGLINE = "Your AI agent watches your game film and coaches you."
PITCH = ("Drop in a phone video of a game or workout. Claude Code or Codex reviews it like a coach and gives back a "
         "phone page with clips, audio narration, drills and a target for next time. Runs on your machine.")
CARDS = (("Athletes", "One session in: what to fix, one drill, a check for next time."),
         ("Coaches", "One game in: a team page and a page per player, with clips and audio, shared as private links."),
         ("Developers", "A resumable CLI that pauses (exit 3) whenever it needs the agent's eyes or words, with a "
                        "validator per agent step. A new sport plugin is one command."))
TRY = (f"uv tool install git+{REPO_URL}", "sports-video-coach demo")   # needs ffmpeg on PATH
PLUGINS_URL = f"{REPO_URL}/blob/master/docs/plugins.md"
TITLE = "sports-video-coach - sports video analysis and basketball film review with Claude Code or Codex"
SITE_PAGES = (SITE_URL, f"{SITE_URL}demo/")


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
        "isAccessibleForFree": True,
    }
    # "</" cannot appear in the JSON (only URLs and plain text), so the script element cannot be closed early
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


def robots_txt() -> str:
    # A project Pages site lives under /sports-video-coach/; crawlers read robots.txt only at the domain root
    # (mariusding.github.io/robots.txt), so this file is not read by them. It is kept for completeness; the
    # sitemap (submitted in Search Console or found via links) is what helps discovery.
    return f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n"


def sitemap_xml() -> str:
    urls = "".join(f"  <url><loc>{u}</loc></url>\n" for u in SITE_PAGES)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')


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
{f'<meta property="og:image" content="{SITE_URL}film.en.jpg">' if "film.en.jpg" in films else ""}
<meta property="og:url" content="{SITE_URL}">
<meta name="twitter:card" content="summary_large_image">
<style>
body {{ margin: 0; font: 17px/1.55 system-ui, sans-serif; color: #1d1b38; background: #f6f5fb; }}
main {{ max-width: 46rem; margin: 0 auto; padding: 2rem 1.1rem 3rem; }}
h1 {{ font-size: clamp(1.6rem, 5vw, 2.3rem); line-height: 1.2; margin: .2rem 0 .8rem; }}
.name {{ font-weight: 700; color: #5c5a86; margin: 0; }}
video {{ width: 100%; border-radius: 10px; background: #221f45; margin: 1.2rem 0 .4rem; }}
.cards {{ display: grid; gap: .8rem; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); margin: 1.4rem 0; }}
.cards section {{ background: #fff; border-radius: 10px; padding: .9rem 1rem; box-shadow: 0 1px 3px #0001; }}
.cards h2 {{ font-size: 1.05rem; margin: 0 0 .3rem; }}
.cards p {{ margin: 0; font-size: .95rem; }}
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
{video}
<div class="cards">{cards}</div>
<p class="go"><a href="demo/">Open the demo coaching page</a><a href="{REPO_URL}">Get it on GitHub</a></p>
<h2 class="try">Try it (needs ffmpeg)</h2>
<pre><code>{try_it}</code></pre>
<p>Your sport needs more than frames? <a href="{PLUGINS_URL}">Write a plugin for your sport</a>.</p>
<small>The demo is synthetic: a drawn drill video (a red block between two cones) and a pre-written review, so
no person appears. {("Other languages: " + other) if other else ""}{version_note(ver)}</small>
</main>
</body>
</html>
"""


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
    (site / "robots.txt").write_text(robots_txt(), encoding="utf8")
    (site / "sitemap.xml").write_text(sitemap_xml(), encoding="utf8")
    return warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach demo", description=__doc__.split("\n\n")[0])
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
