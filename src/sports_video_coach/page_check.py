"""`sports-video-coach page-check <folder...>`: a static check of each report page, for agents with no browser.

Reads `<folder>/index.html` and checks: every local src / href / poster exists, every `#anchor` has its id, every
clip and listen.<lang>.mp3 in the folder is linked and readable (ffprobe duration > 0), no local disk path leaked
into the page, and a mobile viewport is declared. Prints the problems and exits 1, else prints OK and exits 0.

It does not see layout, playback or the 390 px phone view: a browser check still covers those. Say in qa.md which
checks you ran.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import media

REF = re.compile(r"""\b(?:src|href|poster)\s*=\s*["']([^"']+)["']""", re.I)
ID = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""", re.I)
LOCAL_PATH = re.compile(r"""(?:file:///|\b[A-Za-z]:[\\/](?:Users|home)\b|/home/\w|/Users/\w)""")


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach page-check", description=__doc__.split("\n\n")[0])
    ap.add_argument("folders", nargs="+", type=Path, help="report folders (each with an index.html)")
    a = ap.parse_args(argv)
    bad = 0
    for folder in a.folders:
        errs = problems(folder)
        for e in errs:
            print(f"[page-check] {folder.as_posix()}: {e}")
        if not errs:
            print(f"[page-check] {folder.as_posix()}: OK (links, anchors, media; layout and playback not checked)")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
