"""`sports-video-coach page-check <folder...> [--strict] [--write-qa]`: a static check of each report page, for
agents with no browser.

Reads `<folder>/index.html` and checks: every local src / href / poster exists, every `#anchor` has its id, every
clip and listen.<lang>.mp3 in the folder is linked and readable (ffprobe duration > 0), no local disk path leaked
into the page, a mobile viewport is declared, and no page label of another language (langs.py `ui`: "Listen to
the report" in the Spanish part) sits in a language's part. Prints the problems and exits 1, else prints OK and
exits 0.
It also warns about the report parts of the page and the scripts next to it (listen.<lang>.md, the narration;
film.<lang>.md, the explained video's voice and subtitles): English left inside another language (Chinese,
Japanese, Korean: any English phrase; Spanish, French ...: the guides' hedge words and section labels), mojibake
("Ã©", "â€™": UTF-8 read in the wrong encoding), and French straight double quotes used as quotation marks (« … »).
Warnings do not fail the check unless `--strict` is given (the run's qa step waits on them too).

It does not see layout, playback or the 390 px phone view: a browser check still covers those. `--write-qa`
writes a qa.md draft in the unit folder that lists what was checked and says layout, audio and clip playback were
NOT checked (PASS only when nothing was found, with the unit's `checked:` stamp); it never replaces a qa.md
written by hand, and a rewrite keeps the agent's own notes (a `## Agent notes` heading and everything below it).
"""
from __future__ import annotations

import argparse
import html as html_lib
import re
import sys
from html.parser import HTMLParser
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
# the report guides' English section labels, left in a Latin-script report (CJK text: LATIN_RUN finds them)
GUIDE_LABELS = re.compile(r"(?<![A-Za-z])(?:What the video shows|Why it happens|The correct model|"
                          r"How to check next time|Keep doing|Bottom line)(?![A-Za-z])", re.I)
GARBLED = re.compile("\u00c3[\u0080-\u00bf]|\u00e2\u20ac|\u00c2[\u00a0-\u00bf]")  # UTF-8 read as Latin-1 / cp1252
QUOTED = re.compile(r'"[^"\n]{2,}"')
# in a script, syntax around the words shown: freeze marks (> 00:04 0.44,0.21 "label") and markers ![caption](clip:..)
MARK = re.compile(r"^[ \t]*>(.*)$", re.M)
MARKER = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")


def script_text(text: str) -> str:
    """A script's words as heard or shown: marker captions and freeze-mark labels kept, their syntax dropped."""
    text = MARK.sub(lambda m: " ".join(re.findall(r'"([^"\n]*)"', m.group(1))), text)
    return MARKER.sub(r"\1", text)


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
    return errs + foreign_labels(html)


class _Texts(HTMLParser):
    """(language code, text) of every text node and aria-label: the language of the nearest data-lang (else lang)
    around it, the page's <html lang> outside any; scripts and styles skipped."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str | None]] = []  # (tag, code)
        self.out: list[tuple[str, str]] = []
        self.skip = 0

    def code(self, attrs: dict) -> str | None:
        if attrs.get("data-lang"):
            return attrs["data-lang"]
        if attrs.get("lang"):
            tag = attrs["lang"].lower()
            return next((c for c, l in L.LANGS.items() if l.tag.lower() == tag), tag.split("-")[0])
        return next((c for _, c in reversed(self.stack) if c), None)

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        code = self.code(a)
        if a.get("aria-label") and code:
            self.out.append((code, a["aria-label"]))
        if tag in self.VOID:
            return
        self.stack.append((tag, code))
        self.skip += tag in ("script", "style")

    def handle_endtag(self, tag):
        while self.stack:  # close up to the matching tag (a missing end tag never shifts the languages)
            t, _ = self.stack.pop()
            if t == tag:
                self.skip -= tag in ("script", "style")
                break

    def handle_data(self, data):
        code = next((c for _, c in reversed(self.stack) if c), None)
        if data.strip() and code and not self.skip:
            self.out.append((code, data.strip()))


def label_patterns() -> dict[str, list[tuple[str, re.Pattern]]]:
    """{language: [(label, pattern)]}: each page label (langs.py `ui`) as a whole text, placeholders ({m}, {s})
    matching a number; a label may be followed by numbers and punctuation only ("Clip 1 · 00:02–00:06", "Slow-mo ½×")."""
    out = {}
    for code in L.CODES:
        pats = []
        for label in dict.fromkeys(L.ui(code).values()):
            body = "".join(r"[\d.,]+" if part.startswith("{") else re.escape(part)
                           for part in re.split(r"(\{\w+\})", label) if part)
            pats.append((label, re.compile(body + r"[\s\d.,:·–\-½×()]*")))
        out[code] = pats
    return out


def foreign_labels(page: str) -> list[str]:
    """Page labels of another language inside a language's part of the page ("Listen to the report" in the Spanish
    part), unless the label is also that language's own ("Clip" is English, Spanish and German)."""
    parser = _Texts()
    parser.feed(page)
    pats = label_patterns()
    found: dict[tuple[str, str], str] = {}  # (part's language, text) -> the language whose label it is
    for code, text in parser.out:
        if code not in L.LANGS or (code, text) in found:
            continue
        own = set(L.ui(code).values())
        other = next((o for o, labels in pats.items() if o != code
                      for label, pat in labels if label not in own and pat.fullmatch(text)), None)
        if other:
            found[(code, text)] = other
    return [f"{text!r}: {L.name(other)} page label inside the {L.name(code)} part of the page; the page labels "
            f"come from langs.py `ui` (re-run `sports-video-coach html`)" for (code, text), other in found.items()]


def texts(folder: Path) -> list[tuple[str, str, str]]:
    """(where, language code, plain text) of each report part of folder/index.html and of each narration and
    explained-video script next to it (listen.<lang>.md, film.<lang>.md: the voice and the subtitles come from
    them), with the scripts' clip and freeze-mark syntax taken out."""
    out = []
    page = folder / "index.html"
    if page.exists():
        codes = {l.tag.lower(): c for c, l in L.LANGS.items()}
        for tag, body in REPORT.findall(page.read_text(encoding="utf8")):
            code = codes.get(tag.lower(), tag.split("-")[0].lower())
            out.append((f"the {L.name(code)} report", code, html_lib.unescape(TAG.sub("\n", body))))
    for p in [*sorted(folder.glob("listen.*.md")), *sorted(folder.glob("film.*.md"))]:
        code = p.name.split(".")[1]
        if code in L.LANGS:
            out.append((f"{p.name} ({L.name(code)})", code, script_text(p.read_text(encoding="utf8"))))
    return out


def warnings(folder: Path) -> list[str]:
    """Things a reader or listener may trip on that are not broken, in the page's report parts and the scripts
    (texts()): leftover ** in a report part (bold that did not render), English phrases inside a text that is not
    English (up to 5 shown each; a Latin-script language such as es or fr is checked for the guides' hedge words and
    section labels only), mojibake (UTF-8 read as Latin-1: "Ã©", "â€™"), and in French straight double quotes used
    as quotation marks (« … » instead)."""
    out = []
    for where, code, text in texts(folder):
        runs = english(text, L.cjk(code)) if code != "en" else []
        if runs:
            out.append(f"{len(runs)} English phrase(s) in {where}, e.g. "
                       + "; ".join(repr(r[:60]) for r in list(dict.fromkeys(runs))[:5])
                       + ": translate them unless they are names or terms the reader knows")
        bad = [m.group(0) for m in GARBLED.finditer(text)]
        if bad:
            out.append(f"mojibake in {where} ({len(bad)}x, e.g. {bad[0]!r}): the text was saved or read in the "
                       f"wrong encoding; rewrite it as UTF-8")
        marks = re.findall(r".{0,12}\*\*.{0,12}", text) if where.endswith(" report") else []
        if marks:
            out.append(f"{len(marks)} literal ** in {where}, e.g. {marks[0].strip()!r}: the bold did not render; "
                       f"put a space or line break around it in the README and re-run `sports-video-coach html`")
        quoted = QUOTED.findall(text) if code == "fr" else []
        if quoted:
            out.append(f"{len(quoted)} straight-quoted phrase(s) in {where}, e.g. {quoted[0][:40]!r}: French "
                       f"quotation marks are « … »")
    return out


def english(text: str, cjk: bool) -> list[str]:
    """English phrases (CJK text only), hedge words and guide section labels in a text (a phrase never runs across
    tags)."""
    runs = []
    if cjk:
        for m in LATIN_RUN.finditer(text):
            run = m.group(0).strip(" ,")
            gloss = text[:m.start()].rstrip(" \"'“").endswith(("(", "（"))  # 协防轮转（help the helper）
            name = all(w[0].isupper() for w in re.findall(r"[A-Za-z]+", run))  # Riverside Owls
            if not (gloss or name):
                runs.append(run)
    inside = [m.span() for m in LATIN_RUN.finditer(text)] if cjk else []  # counted with its phrase already
    words = [*HEDGE.finditer(text), *([] if cjk else GUIDE_LABELS.finditer(text))]
    return runs + [w.group(0) for w in words if not any(a <= w.start() and w.end() <= b for a, b in inside)]


CHECKED = ("every local link, image, clip and audio file exists; every #anchor has its id; every clip and "
           "listen.<lang>.mp3 is linked and has a playable length (ffprobe); no local disk path in the page; a "
           "mobile viewport is declared; no other language's page labels in a language's part; the report parts "
           "and the listen / film scripts for leftover English, mojibake and (French) straight quotes")
NOT_CHECKED = ("the layout and the 390 px phone view, audio playback, clip playback, the language switch "
               "(no browser was used)")
QA_MARK = "Written by `sports-video-coach page-check --write-qa`"
NOTES = "## Agent notes"  # the agent's own part of a draft: kept when the draft is written again


def agent_notes(text: str) -> str:
    """The `## Agent notes` heading of a qa.md and everything below it ('' when it has none)."""
    m = re.search(rf"^{re.escape(NOTES)}\b.*", text, re.M | re.S)
    return m.group(0).rstrip() + "\n" if m else ""


def qa_text(results: list[tuple[Path, list[str], list[str]]], stamp: str | None, notes: str = "") -> str:
    """qa.md from (folder, problems, warnings) per report folder: PASS only when nothing was found; `notes` (the
    agent's section of the last draft) goes at the end."""
    ok = not any(errs or warns for _, errs, warns in results)
    lines = ["PASS" if ok else "FAIL", "", f"{QA_MARK} (a static check, not a browser check). Add your own notes "
             f"under a `{NOTES}` heading at the end: writing the draft again keeps them.", "",
             f"Checked: {CHECKED}.", "", f"NOT checked: {NOT_CHECKED}.", ""]
    for folder, errs, warns in results:
        lines.append(f"- {folder.as_posix()}: " + ("OK" if not (errs or warns) else f"{len(errs)} problem(s), "
                                                    f"{len(warns)} warning(s)"))
        lines += [f"  - {e}" for e in errs] + [f"  - warning: {w}" for w in warns]
    if stamp:
        lines += ["", f"checked: {stamp}"]
    return "\n".join(lines) + "\n" + (f"\n{notes}" if notes else "")


def write_qa(folders: list[Path], results) -> Path | None:
    """Write qa.md in the unit folder of the first report folder (else that folder), with the unit's QA stamp
    when the folder is a unit the run drives; None (and a message) when a qa.md written by hand is there."""
    from . import plugin, units
    path = units.unit_json(folders[0])
    where = path.parent if path else folders[0]
    qa = where / "qa.md"
    old = qa.read_text(encoding="utf8") if qa.exists() else ""
    if qa.exists() and QA_MARK not in old:
        print(f"[page-check] {qa.as_posix()} was not written by page-check: left as it is (delete it to write a "
              f"draft)")
        return None
    stamp = None
    found = plugin.owner(where) if path else None
    if found and found[1].unit:
        from . import pipeline
        stamp = pipeline.qa_hash(found[1].unit_class().load(where))
    media.write_text_atomic(qa, qa_text(results, stamp, agent_notes(old)))
    print(f"[page-check] wrote {qa.as_posix()} ({qa.read_text(encoding='utf8').split()[0]}; layout and playback "
          f"marked as not checked)")
    return qa


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach page-check", description=__doc__.split("\n\n")[0],
                                 epilog="Exit codes: 0 no problems (warnings allowed unless --strict), 1 a problem "
                                        "(or a warning with --strict).")
    ap.add_argument("folders", nargs="+", type=Path, help="report folders (each with an index.html)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too (leftover English, mojibake, "
                                                          "French straight quotes)")
    ap.add_argument("--write-qa", action="store_true",
                    help="write a qa.md draft in the unit folder (PASS only when nothing was found, with what was "
                         "checked and what was not: layout, audio and clip playback); an agent with no browser")
    a = ap.parse_args(argv)
    bad, results = 0, []
    for folder in a.folders:
        errs = problems(folder)
        warns = warnings(folder)
        for e in errs:
            print(f"[page-check] {folder.as_posix()}: {e}")
        for w in warns:
            print(f"[page-check] {folder.as_posix()}: warning: {w}")
        if not errs and a.strict and warns:  # exits 1: never print OK over it
            print(f"[page-check] {folder.as_posix()}: FAIL ({len(warns)} warning{'s' * (len(warns) > 1)}, --strict)")
        elif not errs:
            print(f"[page-check] {folder.as_posix()}: OK (links, anchors, media; layout and playback not checked)")
        bad += bool(errs) or (a.strict and bool(warns))
        results.append((folder, errs, warns))
    if a.write_qa:
        write_qa(a.folders, results)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
