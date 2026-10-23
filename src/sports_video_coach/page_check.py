"""`sports-video-coach page-check <folder...>`: a static check of each report page, for agents with no browser.

Reads `<folder>/index.html` and checks: every local src / href / poster exists, every `#anchor` has its id, every
clip and listen.<lang>.mp3 in the folder is linked and readable (ffprobe duration > 0), no local disk path leaked
into the page, and a mobile viewport is declared. Prints the problems and exits 1, else prints OK and exits 0.
It also warns (without failing) about English phrases left inside a report in another language (Chinese, Japanese,
Korean: any English phrase; Spanish, French ...: the guides' hedge words).

It does not see layout, playback or the 390 px phone view: a browser check still covers those. Say in qa.md which
checks you ran.
"""
from __future__ import annotations

import argparse
import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import langs as L
from . import media

REF = re.compile(r"""\b(?:src|href|poster)\s*=\s*["']([^"']+)["']""", re.I)
ID = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""", re.I)
LOCAL_PATH = re.compile(r"""(?:file:///|\b[A-Za-z]:[\\/](?:Users|home)\b|/home/\w|/Users/\w)""")
REPORT = re.compile(r"""<article\b[^>]*\blang=["']([^"']+)["'][^>]*>(.*?)</article>""", re.I | re.S)
TAG = re.compile(r"<[^>]+>")
HEDGE = re.compile(r"(?<![A-Za-z])(?:unclear|likely|unknown|maybe)(?![A-Za-z])", re.I)  # guide words left untranslated
# three or more Latin words in a row: a sentence or phrase, not a name, unit or acronym (ACL, mp4, Brunson)
LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*(?:[ ,]+[A-Za-z][A-Za-z'\u2019-]*){2,}")


def playable_s(p: Path) -> float:
    try:
        return media.duration_s(p)
    except Exception:  # ffprobe failed, or printed no duration: a truncated or empty file
        return 0.0


def problems(folder: Path) -> list[str]:
    """What is wrong with folder/index.html and the media next to it (empty list: it passes)."""
    page = folder / "index.html"
    if not page.exists():
        return [f"{page} missing: run `sports-video-coach html {folder.as_posix()}`"]
    html = page.read_text(encoding="utf8")
    ids = set(ID.findall(html))
    errs, linked = [], set()
    for ref in sorted(set(REF.findall(html))):
        u = urlsplit(ref)
        if u.scheme in ("http", "https", "data", "mailto", "javascript") or ref.startswith("//"):
            continue
        if not u.path:
            if u.fragment and u.fragment not in ids:
                errs.append(f"link #{u.fragment} has no element with that id")
            continue
        path = unquote(u.path)
        linked.add(path)
        if not (folder / path).exists():
            errs.append(f"{ref} is linked but {path} does not exist")
    for p in [*sorted(folder.glob("clips/*.mp4")), *sorted(folder.glob("listen.*.mp3"))]:
        rel = p.relative_to(folder).as_posix()
        if rel not in linked:
            errs.append(f"{rel} is not linked from index.html")
        elif playable_s(p) <= 0:
            errs.append(f"{rel} has no playable length (ffprobe cannot read it)")
    leak = LOCAL_PATH.search(html)
    if leak:
        errs.append(f"a local disk path is in the page ({html[leak.start():leak.start() + 40]!r}...)")
    if 'name="viewport"' not in html:
        errs.append("no <meta name=\"viewport\">: phones will show a zoomed-out desktop page")
    return errs


def warnings(folder: Path) -> list[str]:
    """Things a reader may trip on that are not broken: English phrases inside a report that is not English (up to
    5 shown per language). A Latin-script language (es, fr ...) is checked for the hedge words only."""
    page = folder / "index.html"
    if not page.exists():
        return []
    codes = {l.tag.lower(): c for c, l in L.LANGS.items()}
    found: dict[str, list[str]] = {}
    for tag, body in REPORT.findall(page.read_text(encoding="utf8")):
        code = codes.get(tag.lower(), tag.split("-")[0].lower())
        if code != "en":
            found.setdefault(code, []).extend(english(html_lib.unescape(TAG.sub("\n", body)), L.cjk(code)))
    return [f"{len(runs)} English phrase(s) in the {L.name(code)} report, e.g. "
            + "; ".join(repr(r[:60]) for r in list(dict.fromkeys(runs))[:5])
            + ": translate them unless they are names or terms the reader knows"
            for code, runs in found.items() if runs]


def english(text: str, cjk: bool) -> list[str]:
    """English phrases (CJK text only) and hedge words in a report's text (a phrase never runs across tags)."""
    runs = []
    if cjk:
        for m in LATIN_RUN.finditer(text):
            run = m.group(0).strip(" ,")
            gloss = text[:m.start()].rstrip(" \"'“").endswith(("(", "（"))  # 协防轮转（help the helper）
            name = all(w[0].isupper() for w in re.findall(r"[A-Za-z]+", run))  # Riverside Owls
            if not (gloss or name):
                runs.append(run)
    inside = [m.span() for m in LATIN_RUN.finditer(text)] if cjk else []  # counted with its phrase already
    return runs + [w.group(0) for w in HEDGE.finditer(text) if not any(a <= w.start() and w.end() <= b for a, b in inside)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach page-check", description=__doc__.split("\n\n")[0])
    ap.add_argument("folders", nargs="+", type=Path, help="report folders (each with an index.html)")
    a = ap.parse_args(argv)
    bad = 0
    for folder in a.folders:
        errs = problems(folder)
        for e in errs:
            print(f"[page-check] {folder.as_posix()}: {e}")
        for w in warnings(folder):
            print(f"[page-check] {folder.as_posix()}: warning: {w}")
        if not errs:
            print(f"[page-check] {folder.as_posix()}: OK (links, anchors, media; layout and playback not checked)")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
