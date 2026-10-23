"""Render a report folder (README.md = 中文, README.<code>.md = any other language of langs.py, e.g. README.en.md,
README.ja.md; one or several) into one HTML page with a language switch (中文 / EN / 日本語). Images are inlined; if
listen.<code>.mp3 files (listen.zh.mp3, listen.en.mp3) sit next to the READMEs
(the `narrate` stage makes them) the page gets a play button that reads the report aloud. Clip markers
`![caption](clip:03:10-03:19)` become numbered video players (cut them first with the `clips` stage).

The plugin that owns the folder (`plugin.owner`, a sub-report folder resolves to its unit) may add `PageHooks`:
the top band (a game score, a session's numbers), accent colours, labels, panels above the report and sections
after it. A folder no plugin owns, or a plugin without hooks, gets a plain band: title, date and sport.

usage: sports-video-coach html <report folder> [--out index.html]
       sports-video-coach html <report folder> --share --out /somewhere/report.html
--share drops repo links and local paths and embeds the audio, so the single file can be sent to anyone, clips
included. `publish` uses the same clean-up but keeps audio and clips as files (page(..., share=True, embed=False))
for a hosted copy.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from markdown_it import MarkdownIt
from markdown_it.common.utils import isMdAsciiPunct, isPunctChar, isWhiteSpace
from markdown_it.rules_inline import StateInline
from markdown_it.rules_inline.state_inline import Scanned

from sports_video_coach import clips as clipmod
from sports_video_coach import langs as langs_
from sports_video_coach import plugin, units
from sports_video_coach.media import joined, source_at, video_size
from sports_video_coach.timefmt import seconds
from sports_video_coach.media import duration_s  # ffprobe with a timeout: a cloud placeholder file can hang it

# Raw HTML is off: README text is agent-written and quotes league data, so a <script> or <img onerror> in it must
# show as text, never run on the published site. Pages use markdown only (clips and images come from markers).
MD = MarkdownIt("commonmark", {"html": False}).enable("table")


def _cjk(ch: str) -> bool:
    """Han, kana, hangul, CJK punctuation and full-width forms."""
    o = ord(ch)
    return (0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0x9FFF or 0xA960 <= o <= 0xA97F or 0xAC00 <= o <= 0xD7FF
            or 0xF900 <= o <= 0xFAFF or 0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFFEF or 0x20000 <= o <= 0x3FFFF)


class _CJKInline(StateInline):
    """CommonMark leaves the asterisks of `**一句话：**第 4 次` as text: a run between CJK punctuation and a CJK letter
    is not right-flanking. As in markdown-it-cjk-friendly, a CJK character beside the run counts like whitespace or
    punctuation for the punctuation rule, so the run still opens or closes. Latin text renders as before."""

    def scanDelims(self, start: int, canSplitWord: bool) -> Scanned:
        pos, marker = start, self.src[start]
        last = self.src[start - 1] if start > 0 else " "
        while pos < self.posMax and self.src[pos] == marker:
            pos += 1
        nxt = self.src[pos] if pos < self.posMax else " "
        last_p = isMdAsciiPunct(ord(last)) or isPunctChar(last)
        next_p = isMdAsciiPunct(ord(nxt)) or isPunctChar(nxt)
        last_w, next_w = isWhiteSpace(ord(last)), isWhiteSpace(ord(nxt))
        left = not (next_w or (next_p and not (last_w or last_p or _cjk(last))))
        right = not (last_w or (last_p and not (next_w or next_p or _cjk(nxt))))
        return Scanned(left and (canSplitWord or not right or last_p), right and (canSplitWord or not left or next_p),
                       pos - start)


def _parse_inline(src, md, env, tokens):  # ParserInline.parse with the CJK-aware state
    state = _CJKInline(src, md, env, tokens)
    MD.inline.tokenize(state)
    for rule in MD.inline.ruler2.getRules(""):
        rule(state)
    return state.tokens


MD.inline.parse = _parse_inline
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
# (code, html lang, switch label, README) per registry language, zh first (langs.py)
LANGS = [(c, l.tag, l.button, langs_.readme(c)) for c, l in langs_.LANGS.items()]
UI = {c: langs_.ui(c) for c in langs_.CODES}  # labels per language (langs.py)
# CJK headings use the body face; Japanese and Korean text gets its own fonts (not the Chinese glyph forms)
LANG_CSS = "\n".join(
    [", ".join(f'.report[lang="{l.tag}"] h2' for l in langs_.LANGS.values() if l.cjk) +
     " { font-family: var(--body); font-weight: 700; font-size: clamp(1.3rem, 2.8vw, 1.65rem); }"] +
    [f'[lang="{l.tag}"] {{ --body: {l.page_font}; font-family: var(--body); }}'
     for l in langs_.LANGS.values() if l.page_font])
PLAY_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path class="i-play" d="M8 5.5v13l10.5-6.5z"/>'
             '<path class="i-pause" d="M7 5h3.6v14H7zM13.4 5H17v14h-3.6z"/></svg>')


# Accent colours when the plugin sets none: (main, light variant for the dark top band) for the two CSS accents
# `--us` (main accent) and `--them` (second accent).
DEFAULT_COLOURS = {"us": ("#5b4bd1", "#b9b0ff"), "them": ("#11907b", "#6fe0c9")}


@dataclass
class PageHooks:
    """What a plugin adds to a report page; every field is optional (None / empty: the plain default).

    lab(key) in a band is the label `key` in every page language (one span each, the switch shows one)."""
    ui: dict[str, dict[str, str]] = field(default_factory=dict)  # labels per language, merged over UI
    board: Callable[[Path], dict] | None = None   # folder -> band data; its "colours" {"us"|"them": (main, light)}
    band: Callable[[dict, Callable[[str], str]], str] | None = None  # (band data, lab) -> top band HTML
    before: Callable[[Path, dict, list], str] | None = None  # (folder, band data, langs) -> HTML above the report
    # (folder, lang, embed, number of its first h2) -> (HTML, h2 titles, page assets added once) after the report
    sections: Callable[[Path, str, bool, int], tuple[str, list[str], str]] | None = None


DEFAULT = PageHooks()


# Common sport names per language (langs.py `sports`), so a zh or fr page does not show "tennis"; analysis.json
# `"sport": {"zh": .., "en": ..}` (`--sport-name LANG=NAME`) names any other sport per language.
SPORT_ZH, SPORT_JA = langs_.SPORT_ZH, langs_.SPORT_JA
SPORTS = {c: l.sports for c, l in langs_.LANGS.items() if l.sports}  # a language without a table shows English


def sport_names(sport, langs=("en",)) -> dict[str, str]:
    """{lang: sport name} for the page languages: a per-language dict as given, else the SPORTS tables both ways
    (the English name or any language's own name finds the others). An unknown sport shows as given, except that
    with several languages a CJK page leaves out ("") a name not in its script, and the others one in a CJK script."""
    if isinstance(sport, dict):  # names given per language win; the others come from the English one's tables
        fallback = next((str(v) for v in sport.values() if v), "")
        base = sport_names(str(sport["en"]), langs) if sport.get("en") else {}
        return {c: label(str(sport.get(c) or base.get(c) or fallback)) for c in langs}
    raw = str(sport or "").strip()
    low = raw.lower()
    key = low if low in langs_.SPORTS_EN else next(
        (k for t in SPORTS.values() for k, v in t.items() if v.lower() == low), None)
    if key:
        en = raw if low == key else key
        return {c: label(SPORTS.get(c, {}).get(key) or en) for c in langs}
    native = bool(re.search(r"[぀-ヿ㐀-鿿가-힯]", raw))  # Chinese, kana or Hangul
    shown = raw if native or len(langs) == 1 else ""
    en = ("" if len(langs) > 1 else raw) if native else raw
    return {c: label(shown if langs_.cjk(c) else en) for c in langs}


def label(name: str) -> str:
    """A sport name as a header label: "tennis" -> "Tennis"; "3x3", "NBA" and Chinese stay as they are."""
    return name[:1].upper() + name[1:] if name.islower() and name.isascii() else name


def default_board(folder: Path, data: dict, sport: str, heading: str, langs=("en",)) -> dict:
    """Plain band data: the title spans, the unit's date (or a dated folder name) and the sport / plugin name
    ({lang: name}, see sport_names)."""
    date = data.get("date") or (folder.name if re.fullmatch(r"\d{4}-\d{2}-\d{2}", folder.name) else "")
    return dict(heading=heading, date=str(date), sport=sport_names(data.get("sport") or sport, langs),
                colours=DEFAULT_COLOURS)


def default_band(sb: dict, lab) -> str:
    """The plain band: the title over sport · date, both in each page language (the date the reader's way)."""
    names = sb["sport"] if isinstance(sb["sport"], dict) else {"": str(sb["sport"])}
    def line(code, name):
        return " · ".join(html.escape(x) for x in (name, langs_.date(sb["date"], code)) if x)
    lines = {c: line(c, n) for c, n in names.items()}
    if len(set(lines.values())) > 1:  # one span per language, the switch shows one (first language visible)
        meta = "".join(f'<span data-lang="{c}"{" hidden" if i else ""}>{t}</span>'
                       for i, (c, t) in enumerate(lines.items()))
    else:
        meta = next(iter(lines.values()), "")
    return f"""<div class="score" data-result="plain">
      <div class="team us"><span class="name">{sb["heading"]}</span><span class="side">{meta}</span></div>
    </div>"""


def hooks_of(folder: Path) -> tuple[PageHooks, str, dict]:
    """(page hooks, plugin name, unit json) of the plugin owning the folder; DEFAULT, "", {} when none does."""
    own = plugin.owner(folder)
    if own is None:
        return DEFAULT, "", {}
    return own[0].page or DEFAULT, own[0].name, own[2]


def find_up(folder: Path, name: str) -> Path:
    p = units.find_up(folder, name)
    if p is None:
        raise FileNotFoundError(f"{name} not found in {folder} or its parent")
    return p


def data_uri(p: Path) -> str:
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def inside(folder: Path, rel: str) -> Path | None:
    """The file `rel` names, if it resolves inside `folder` (no ../, no absolute or drive paths), else None."""
    if not rel or re.match(r"^[a-zA-Z][\w+.-]*:|^[\\/]", rel):
        return None
    root = folder.resolve()
    p = (root / rel).resolve()
    return p if p.is_relative_to(root) else None


def inline_images(body: str, folder: Path) -> str:
    """Embed images that live in the report folder; anything else (other folders, other file types) is left alone."""
    def sub(m):
        p = inside(folder, m.group(1))
        if p is None or p.suffix.lower() not in IMAGE_EXT or not p.is_file():
            return m.group(0)
        return f'src="{data_uri(p)}"'
    return re.sub(r'src="([^"]+)"', sub, body)


def for_sharing(md_text: str) -> str:
    """Drop top-level list items that point at repo files or local paths (they break once the page is
    sent on); keep everything else, nested items included."""
    out, skipping = [], False
    for line in md_text.splitlines():
        if line.startswith(("- ", "* ")):
            skipping = bool(re.search(r"\]\((?!https?:|#|clip:)[^)]+\)|`[^`]*[\\/][^`]*`", line))
        elif not line.startswith(" "):
            skipping = False
        if not skipping:
            out.append(line)
    text = "\n".join(out) + "\n"
    return re.sub(r"`[^`]*[\\/][^`]*`(?:[，,]\s*)?", "", text)  # inline local paths, e.g. (`<media root>\...`, each trip ...)


CLIP_IMG = re.compile(r'(<p>)?<img src="clips/([0-9_]+-[0-9_]+)\.mp4" alt="([^"]*)"\s*/?>(?(1)</p>)')


def portrait(mp4: Path) -> str:
    """' style="aspect-ratio: 9 / 16"' for an upright phone clip (the player keeps its shape before it loads), else ''."""
    try:
        w, h = video_size(mp4)
    except Exception:  # not a readable video (a test stub): the default 16:9 box
        return ""
    return f' style="aspect-ratio: {w} / {h}"' if h > w else ""


def in_files(sources: list[dict] | None, start: str, end: str) -> str:
    """'' for one video, else ' · side.mp4 00:15–00:20': where a clip of the joined video sits in its own file
    (both ends named when it spans two files)."""
    if not sources or not start:
        return ""
    dec = 1 if "." in start + end or any(not float(s["start"]).is_integer() for s in sources) else 0
    a, b = source_at(sources, seconds(start), dec), source_at(sources, seconds(end), dec)
    if a.rsplit(" ", 1)[0] == b.rsplit(" ", 1)[0]:
        b = b.rsplit(" ", 1)[1]
    return html.escape(f" · {a}–{b}")


def clip_players(body: str, folder: Path | None, lang: str, embed: bool, windows: dict, ui: dict | None = None,
                 sources: list[dict] | None = None) -> str:
    """Clip images (from `clip:` markers) -> numbered <figure> with a video player, poster and slow-mo button.
    Paths stay relative in index.html (clips/ sits next to it); embed (--share) inlines them. ui: labels (UI).
    sources: the joined files of a unit made from several videos (each caption then says where it is in its file)."""
    t = (ui or UI)[lang]
    n = 0

    def sub(m):
        nonlocal n
        n += 1
        name, alt = m.group(2), m.group(3)
        start, end = windows.get(name, ("", ""))
        mp4 = folder / "clips" / f"{name}.mp4" if folder else None
        cap = (f'<figcaption><span class="clip-no">{t["clip"]} {n} · {start}–{end}{in_files(sources, start, end)}'
               f'</span>{alt}</figcaption>')
        if mp4 is None or not mp4.exists():
            print(f"warning: clips/{name}.mp4 missing; run the clips stage on {folder}", file=sys.stderr)
            return f'<figure class="clip missing" id="{lang}-clip-{name}">{cap}<p>{t["missing"]}</p></figure>'
        poster = clipmod.poster_of(mp4)  # the telestrated poster when the posters stage made one
        src = data_uri(mp4) if embed else f"clips/{mp4.name}"
        post = f' poster="{data_uri(poster) if embed else "clips/" + poster.name}"' if poster.exists() else ""
        tall = portrait(mp4)
        return (f'<figure class="clip{" tall" if tall else ""}" id="{lang}-clip-{name}"><video controls playsinline '
                f'preload="none"{post}{tall} src="{src}"></video>'
                f'<div class="clip-bar">{cap}<button type="button" class="slow" data-slow aria-pressed="false">'
                f'{t["slow"]} ½×</button></div></figure>')
    body = CLIP_IMG.sub(sub, body)
    return body.replace('href="#clip-', f'href="#{lang}-clip-')  # [▶ 03:10](#clip-0310-0319) jumps to the player


def render(md_text: str, lang: str, share: bool = False, folder: Path | None = None, embed: bool | None = None,
           ui: dict | None = None, sources: list[dict] | None = None):
    md_text = re.sub(r"^# .*\n", "", md_text, count=1)  # H1 becomes the page header
    if share:
        md_text = for_sharing(md_text)
    windows = {}

    def clip_md(m):  # markdown-it would mangle "clip:03:10-03:19" as a URL, so hand it a plain relative path
        name = clipmod.clip_name(*m.groups())
        windows[name] = m.groups()
        return f"](clips/{name}.mp4)"
    md_text = clipmod.CLIP_RE.sub(clip_md, md_text)
    body = MD.render(md_text)  # CommonMark: lists need no blank line before them, 2-space nesting works
    body = clip_players(body, folder, lang, share if embed is None else embed, windows, ui, sources)
    if share:  # any repo-relative link left would be dead for the recipient
        body = re.sub(r'<a href="(?!https?:|#)[^"]*">(.*?)</a>', r"\1", body)
    heads = []

    def h2(m):
        heads.append(re.sub(r"<[^>]+>", "", m.group(1)))
        return f'<h2 id="{lang}-s{len(heads)}">{m.group(1)}</h2>'
    body = re.sub(r"<h2>(.*?)</h2>", h2, body)
    body = re.sub(r"<table>", '<div class="table-wrap"><table>', body).replace("</table>", "</table></div>")
    body = re.sub(r"<p>(<img [^>]+>)</p>", r'<div class="figure">\1</div>', body)
    return body, heads


def readme_name(code: str) -> str:
    """The report file of a language: README.md is Chinese, README.<code>.md any other language."""
    return next((f for c, _, _, f in LANGS if c == code), f"README.{code}.md")


def report_langs(folder: Path) -> list[tuple]:
    """LANGS entries whose README exists in folder, in the unit's `languages` order, then LANGS order (zh first);
    the first one is the default (the page's lang, the visible text), as in `film`."""
    langs = [l for l in LANGS if (folder / l[3]).exists()]
    if not langs:
        raise SystemExit(f"{folder} has no report README ({' / '.join(l[3] for l in LANGS)})")
    order = [c for c in (units.load(folder).get("languages") or []) if isinstance(c, str)]
    return sorted(langs, key=lambda l: order.index(l[0]) if l[0] in order else len(order))


def first_readme(folder: Path) -> Path:
    return folder / report_langs(folder)[0][3]


def length_label(ui: dict, seconds: float) -> str:
    """'About 1.5 min' for a long recording, to the nearest half minute (84 s never reads as 1 min); under a minute
    in seconds (to 5 s), so 47 s never reads as 1 min either."""
    if seconds < 55 and "listen_sub_s" in ui:
        return ui["listen_sub_s"].format(s=max(5, round(seconds / 5) * 5))
    return ui["listen_sub"].format(m=f"{max(1, int(seconds / 30 + 0.5) / 2):g}")  # 75 s rounds up


def listen_block(folder: Path, embed: bool, langs: list[tuple] | None = None):
    """Big play button + progress for the narration, or empty strings when there is no audio yet."""
    langs = langs or report_langs(folder)
    first = langs[0][0]
    files ={c: folder / f"listen.{c}.mp3" for c, *_ in langs}
    if not all(p.exists() for p in files.values()):
        return "", ""
    audios, labels = [], []

    def hide(c):
        return "" if c == first else " hidden"
    for c, attr, *_ in langs:
        src = data_uri(files[c]) if embed else files[c].name
        # native controls stay visible when scripts are blocked (WeChat / mail file previews); the script hides them
        audios.append(f'<audio id="audio-{c}" class="native" data-lang="{c}"{hide(c)} controls preload="metadata" src="{src}"></audio>')
        labels.append(f'<span data-lang="{c}" lang="{attr}"{hide(c)}><b>{UI[c]["listen"]}</b>'
                      f'<small>{length_label(UI[c], duration_s(files[c]))}</small></span>')
    block = f"""<div class="listen">
      <button type="button" class="play big" data-play aria-label="{UI[first]['play']}">{PLAY_ICON}</button>
      <div class="listen-body">
        <div class="listen-label">{''.join(labels)}</div>
        <div class="listen-track">
          <input type="range" class="seek" min="0" max="100" step="1" value="0" aria-label="{UI[first]['seek']}">
          <span class="clock">0:00</span>
          <button type="button" class="speed" aria-label="{UI[first]['speed']}">1×</button>
        </div>
      </div>
      {''.join(audios)}
    </div>"""
    mini = f'<button type="button" class="play mini" data-play aria-label="{UI[first]["play"]}">{PLAY_ICON}</button>'
    return block, mini


def page(folder: Path, share: bool = False, embed: bool | None = None) -> str:
    """share: drop repo links and local paths; embed (default: same as share): inline audio and clips."""
    embed = share if embed is None else embed
    hooks, sport, data = hooks_of(folder)
    ui = {c: {**t, **hooks.ui.get(c, hooks.ui.get("en", {}))} for c, t in UI.items()}  # plugin labels, else English
    sb = hooks.board(folder) if hooks.board else None
    arts, tocs, titles = [], [], {}
    assets = ""
    langs = report_langs(folder)
    first, first_attr = langs[0][0], langs[0][1]

    def hide(c):
        return "" if c == first else " hidden"
    for code, attr, _, fname in langs:
        text = (folder / fname).read_text(encoding="utf8")
        titles[code] = re.match(r"# (.*)", text).group(1).strip()
        body, heads = render(text, code, share, folder, embed, ui, joined(data.get("sources")))
        if hooks.sections:  # plugin sections after the report (e.g. charts, tables from the plugin's data)
            more, more_heads, more_assets = hooks.sections(folder, code, embed, len(heads) + 1)
            body, heads, assets = body + more, heads + more_heads, assets or more_assets
        arts.append(f'<article class="report" data-lang="{code}" lang="{attr}"{hide(code)}>{inline_images(body, folder)}</article>')
        links = "".join(f'<li><a href="#{code}-s{i}">{html.escape(h)}</a></li>' for i, h in enumerate(heads, 1))
        tocs.append(f'<nav class="toc" data-lang="{code}" lang="{attr}" aria-label="{ui[code]["contents"]}"{hide(code)}>'
                    f'<p class="toc-title">{ui[code]["contents"]}</p><ol>{links}</ol></nav>')

    def lab(key):
        return "".join(f'<span data-lang="{c}"{hide(c)}>{ui[c][key]}</span>' for c, *_ in langs)

    def title_spans():
        return "".join(f'<span data-lang="{c}"{hide(c)}>{html.escape(titles[c])}</span>' for c, *_ in langs)
    if sb is None:
        sb = default_board(folder, data, sport, title_spans(), [c for c, *_ in langs])
    board = (hooks.band or default_band)(sb, lab)
    colours = {**DEFAULT_COLOURS, **(sb.get("colours") or {})}
    (us_hex, us_light), (them_hex, them_light) = colours["us"], colours["them"]
    buttons = "".join(f'<button type="button" data-set-lang="{c}" lang="{a}" aria-pressed="{str(c == first).lower()}">{n}</button>'
                      for c, a, n, _ in langs) if len(langs) > 1 else ""   # one language: no switch
    listen, mini = listen_block(folder, embed, langs)
    ui_js = {c: {k: ui[c][k] for k in ("play", "seek", "speed", "switch")} for c, *_ in langs}
    return TEMPLATE.format(
        html_lang=first_attr,
        page_title=html.escape(titles[first]), titles_js=json.dumps(json.dumps(titles, ensure_ascii=False)).replace("</", "<\\/"),
        ui_js=json.dumps(json.dumps(ui_js, ensure_ascii=False)),
        lang_switch=f'<div class="lang" role="group" aria-label="{ui[first]["switch"]}">{buttons}</div>' if buttons else "", heading=title_spans(), board=board,
        us_hex=us_hex, them_hex=them_hex, us_light=us_light, them_light=them_light,
        us_light_rgb=", ".join(map(str, units.hex_to_rgb(us_light))),
        listen=listen, mini=mini, tocs="".join(tocs), lang_css=LANG_CSS,
        articles=(hooks.before(folder, sb, langs) if hooks.before else "") + "".join(arts) + assets,
    )


TEMPLATE = """<!doctype html>
<html lang="{html_lang}" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<link rel="icon" href="data:,">
<title>{page_title}</title>
<style>
:root {{
  --ink: #221f45;        /* page ink + score band */
  --ink-soft: #4a4868;
  --muted: #6c6b84;
  --paper: #f5f5f8;
  --sheet: #ffffff;
  --rule: #dcdce6;
  --us: {us_hex};         /* game.json us.hex */
  --them: {them_hex};       /* game.json them.hex */
  --us-light: {us_light};   /* lighter twins on the dark score band */
  --them-light: {them_light};
  --us-light-rgb: {us_light_rgb};
  --whistle: #c9343f;    /* points we gave away */
  --display: "Barlow Condensed", "Roboto Condensed", "Arial Narrow", sans-serif-condensed, sans-serif;
  --body: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-padding-top: 4.5rem; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.75 var(--body); }}
[hidden] {{ display: none !important; }}

/* sticky title bar with the language switch, then the scoreboard band */
.topbar {{ position: sticky; top: 0; z-index: 10; background: var(--ink); border-bottom: 1px solid #34315c; }}
.bar {{ max-width: 72rem; margin: 0 auto; padding: .6rem 1.25rem; display: flex; align-items: center; gap: .75rem; }}
.bar h1 {{ margin: 0 auto 0 0; font: 500 .95rem/1.4 var(--body); color: #c9c7e6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }}
.board {{ background: var(--ink); color: #fff; }}
.board-inner {{ max-width: 72rem; margin: 0 auto; padding: .5rem 1.25rem 1.75rem; }}
.lang {{ display: inline-flex; border: 1px solid #5c5a86; border-radius: 999px; padding: 2px; flex: none; }}
.lang button {{ font: 600 0.95rem/1 var(--display); letter-spacing: .02em; color: #c9c7e6; background: none; border: 0;
  border-radius: 999px; padding: .45rem .9rem; cursor: pointer; }}
.lang button[aria-pressed="true"] {{ background: #fff; color: var(--ink); }}
button:focus-visible, a:focus-visible, input:focus-visible {{ outline: 3px solid #f2c94c; outline-offset: 2px; }}
.score {{ display: grid; grid-template-columns: 1fr auto 1fr; align-items: end; gap: 1rem; margin-top: 1.5rem; }}
.team {{ display: flex; flex-direction: column; gap: .15rem; }}
.team.them {{ text-align: right; }}
.team .name {{ font: 600 clamp(1.1rem, 2.6vw, 1.6rem)/1.1 var(--display); }}
.team .side {{ font-size: .8rem; color: #a9a7cc; }}
.team.us .name {{ color: var(--us-light); }}
.team.them .name {{ color: var(--them-light); }}
.pts {{ font: 700 clamp(4rem, 13vw, 8.5rem)/.85 var(--display); font-variant-numeric: tabular-nums; display: flex; gap: .35em; }}
.pts .dash {{ color: #5c5a86; font-weight: 500; }}
.pts .lose {{ color: #8f8db3; }}
.halves {{ display: flex; justify-content: center; gap: 1.75rem; margin-top: .9rem; font-size: .85rem; color: #a9a7cc; }}
.halves b {{ font: 600 1.15rem var(--display); color: #fff; margin-left: .35rem; font-variant-numeric: tabular-nums; }}

/* narration: one big button under the score, a small twin in the sticky bar */
.play {{ flex: none; display: grid; place-items: center; border: 0; border-radius: 50%; cursor: pointer; padding: 0; }}
.play svg {{ fill: currentColor; }}
.play .i-pause, .play.playing .i-play {{ display: none; }}
.play.playing .i-pause {{ display: inline; }}
.play.big {{ width: 5.5rem; height: 5.5rem; background: #fff; color: var(--us); box-shadow: 0 0 0 6px rgba(var(--us-light-rgb), .25); }}
.play.big svg {{ width: 2.6rem; height: 2.6rem; }}
.play.big:hover {{ box-shadow: 0 0 0 9px rgba(var(--us-light-rgb), .35); }}
.play.big.playing {{ background: var(--us-light); color: var(--ink); }}
.play.mini {{ width: 2.1rem; height: 2.1rem; background: #fff; color: var(--us); }}
.play.mini svg {{ width: 1.1rem; height: 1.1rem; }}
.listen {{ display: flex; align-items: center; gap: 1.25rem; max-width: 38rem; margin: 1.75rem auto 0; padding: 1rem 1.25rem;
  border: 1px solid #3d3a6b; border-radius: 1.25rem; background: #2b2856; }}
.listen-body {{ flex: 1; min-width: 0; }}
.listen-label b {{ display: block; font-size: 1.15rem; }}
.listen-label small {{ color: #a9a7cc; font-size: .85rem; }}
.listen-track {{ display: flex; align-items: center; gap: .75rem; margin-top: .5rem; }}
.listen {{ flex-wrap: wrap; }}
.listen audio[controls] {{ flex-basis: 100%; width: 100%; }}
.no-js .play, .no-js .listen-track {{ display: none; }}
.seek {{ flex: 1; min-width: 0; accent-color: var(--us-light); }}
.clock {{ font: 600 1rem var(--display); font-variant-numeric: tabular-nums; color: #c9c7e6; min-width: 3.2rem; text-align: right; }}
.speed {{ font: 600 .95rem/1 var(--display); color: #c9c7e6; background: none; border: 1px solid #5c5a86; border-radius: 999px;
  padding: .35rem .6rem; cursor: pointer; min-width: 3.2rem; }}

/* body */
.layout {{ max-width: 72rem; margin: 0 auto; padding: 0 1.25rem 4rem; display: grid; grid-template-columns: 1fr; gap: 2rem; }}
@media (min-width: 1080px) {{ .layout {{ grid-template-columns: 14rem minmax(0, 46rem); justify-content: center; }} }}
.toc {{ display: none; }}
@media (min-width: 1080px) {{
  .toc {{ display: block; position: sticky; top: 4.5rem; align-self: start; margin-top: 2.5rem; font-size: .88rem; }}
  .toc[hidden] {{ display: none; }}
}}
.toc-title {{ color: var(--muted); margin: 0 0 .5rem; }}
.toc ol {{ list-style: none; margin: 0; padding: 0; border-left: 2px solid var(--rule); }}
.toc a {{ display: block; padding: .3rem 0 .3rem .9rem; color: var(--ink-soft); text-decoration: none; margin-left: -2px; border-left: 2px solid transparent; }}
.toc a:hover {{ color: var(--us); border-left-color: var(--us); }}

.layout > main {{ min-width: 0; }}
.report {{ padding-top: 2rem; min-width: 0; }}
.report > p:first-child {{ color: var(--muted); font-size: .92rem; }}
.report > p:nth-child(2) {{ font-size: 1.12rem; line-height: 1.8; border-left: 4px solid var(--whistle); padding: .2rem 0 .2rem 1.1rem; margin: 1.5rem 0; }}
.report h2 {{ font: 700 clamp(1.5rem, 3.2vw, 2rem)/1.2 var(--display); letter-spacing: .01em; margin: 3.25rem 0 1rem;
  padding-top: 1.25rem; border-top: 3px solid var(--ink); }}
{lang_css}
.report h3 {{ font-size: 1.08rem; margin: 2rem 0 .6rem; color: var(--ink); }}
.report p, .report li {{ max-width: 42rem; }}
.report ul, .report ol {{ padding-left: 1.3rem; }}
.report li {{ margin: .3rem 0; }}
.report li::marker {{ color: var(--us); font-weight: 700; }}
.report strong {{ color: var(--ink); font-weight: 700; }}
.report a {{ color: var(--us); text-underline-offset: 3px; }}
.report code {{ font-size: .85em; background: #ebebf2; padding: .1em .35em; border-radius: 4px; word-break: break-all; }}
.report hr {{ display: none; }}
.figure {{ margin: 1.5rem 0; overflow-x: auto; background: #fff; border: 1px solid var(--rule); border-radius: 6px; }}
.figure img {{ display: block; width: 100%; height: auto; }}

/* film clips next to the analysis */
.clip {{ margin: 1.25rem 0 1.75rem; background: #000; border-radius: 6px; overflow: hidden; max-width: 42rem; }}
.clip video {{ display: block; width: 100%; aspect-ratio: 16 / 9; background: #000; }}
.clip.tall {{ max-width: 24rem; }}
.clip.tall video {{ width: auto; max-width: 100%; height: min(70vh, 40rem); margin: 0 auto; }}
.clip-bar {{ display: flex; align-items: flex-start; gap: .75rem; padding: .6rem .8rem; background: var(--ink); color: #e6e5f5; }}
.clip figcaption {{ flex: 1; min-width: 0; font-size: .9rem; line-height: 1.55; }}
.clip-no {{ display: block; font: 600 .95rem/1.3 var(--display); letter-spacing: .03em; color: var(--us-light); font-variant-numeric: tabular-nums; }}
.slow {{ flex: none; font: 600 .85rem/1 var(--body); color: #c9c7e6; background: none; border: 1px solid #5c5a86; border-radius: 999px;
  padding: .4rem .7rem; cursor: pointer; }}
.slow[aria-pressed="true"] {{ background: var(--us-light); color: var(--ink); border-color: var(--us-light); }}
.no-js .slow {{ display: none; }}
.clip.missing {{ background: #fff4f4; border: 1px dashed var(--whistle); padding: .6rem .8rem; }}
.clip.missing .clip-no {{ color: var(--whistle); }}
.clip.missing p {{ margin: .3rem 0 0; color: var(--whistle); font-size: .85rem; }}
td .clip {{ min-width: 16rem; margin: .25rem 0; }}

.table-wrap {{ overflow-x: auto; margin: 1.25rem 0; background: var(--sheet); border: 1px solid var(--rule); border-radius: 6px; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; line-height: 1.55; }}
th, td {{ text-align: left; vertical-align: top; padding: .55rem .75rem; border-bottom: 1px solid var(--rule); }}
th {{ font-weight: 700; color: var(--ink-soft); background: #f0f0f5; white-space: nowrap; }}
tr:last-child td {{ border-bottom: 0; }}
td:first-child {{ white-space: nowrap; font-variant-numeric: tabular-nums; }}
td strong {{ color: var(--whistle); }}

@media (max-width: 560px) {{
  body {{ font-size: 15px; }}
  .halves {{ gap: 1rem; flex-wrap: wrap; }}
  .figure img {{ width: 760px; max-width: none; }}  /* chart text stays readable; swipe sideways */
  .listen {{ gap: .9rem; padding: .85rem; }}
  .play.big {{ width: 4.5rem; height: 4.5rem; }}
}}
@media (prefers-reduced-motion: no-preference) {{
  .play.big {{ transition: box-shadow .2s, background-color .2s; }}
}}
@media print {{
  .lang, .toc, .listen, .play, .slow {{ display: none !important; }}
  .board {{ background: none; color: var(--ink); }}
  .team.us .name, .team.them .name, .halves b {{ color: var(--ink); }}
}}
</style>
</head>
<body>
<div class="topbar">
  <div class="bar">
    <h1>{heading}</h1>
    {mini}
    {lang_switch}
  </div>
</div>
<header class="board">
  <div class="board-inner">
    {board}
    {listen}
  </div>
</header>
<div class="layout">
  {tocs}
  <main>{articles}</main>
</div>
<script>
(() => {{
  const titles = JSON.parse({titles_js});
  const ui = JSON.parse({ui_js});
  const buttons = document.querySelectorAll("[data-set-lang]");
  const playBtns = document.querySelectorAll("[data-play]");
  const seek = document.querySelector(".seek"), clock = document.querySelector(".clock"), speedBtn = document.querySelector(".speed");
  const audios = Object.fromEntries([...document.querySelectorAll("audio[data-lang]")].map(a => [a.dataset.lang, a]));
  const speeds = [1, 1.25, 1.5];
  let lang = Object.keys(titles)[0], speed = 0;
  const fmt = s => Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");
  document.documentElement.classList.remove("no-js");

  // Embedded audio: a Blob URL seeks and reports duration more reliably than a multi-MB data: URI in in-app webviews.
  function toBlob(a, type) {{
    const s = a.getAttribute("src") || "";
    if (!s.startsWith("data:")) return;
    try {{
      const bin = atob(s.slice(s.indexOf(",") + 1)), buf = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
      a.src = URL.createObjectURL(new Blob([buf], {{ type: type || "audio/mpeg" }}));
    }} catch (e) {{}}
  }}
  function showNative(a) {{ a.controls = true; a.classList.add("fallback"); }}
  Object.values(audios).forEach(a => {{ if (a) {{ a.controls = false; toBlob(a); }} }});

  function syncAudio() {{
    const a = audios[lang];
    if (!a) return;
    playBtns.forEach(b => b.classList.toggle("playing", !a.paused));
    if (isFinite(a.duration)) seek.max = Math.floor(a.duration);
    seek.value = Math.floor(a.currentTime);
    clock.textContent = fmt(a.paused && !a.currentTime && isFinite(a.duration) ? a.duration : a.currentTime);
  }}
  Object.values(audios).forEach(a => a && ["play", "pause", "timeupdate", "loadedmetadata", "ended"].forEach(ev => a.addEventListener(ev, syncAudio)));
  playBtns.forEach(b => b.addEventListener("click", () => {{
    const a = audios[lang];
    if (!a) return;
    if (!a.paused) return a.pause();
    const p = a.play();
    if (p && p.catch) p.catch(() => showNative(a));  // blocked custom player: fall back to the browser's own controls
  }}));
  Object.values(audios).forEach(a => a && a.addEventListener("error", () => showNative(a)));

  // clips: one thing plays at a time (narration or one clip); the slow-mo button halves the speed
  const videos = document.querySelectorAll(".clip video");
  videos.forEach(v => {{
    toBlob(v, "video/mp4");
    v.addEventListener("play", () => {{
      Object.values(audios).forEach(a => a && a.pause());
      videos.forEach(o => {{ if (o !== v) o.pause(); }});
    }});
  }});
  Object.values(audios).forEach(a => a && a.addEventListener("play", () => videos.forEach(v => v.pause())));
  document.querySelectorAll("[data-slow]").forEach(b => b.addEventListener("click", () => {{
    const v = b.closest(".clip").querySelector("video"), on = b.getAttribute("aria-pressed") !== "true";
    v.defaultPlaybackRate = v.playbackRate = on ? 0.5 : 1;  // default survives the first load of a preload="none" video
    b.setAttribute("aria-pressed", String(on));
  }}));
  seek?.addEventListener("input", () => {{ audios[lang].currentTime = Number(seek.value); }});
  speedBtn?.addEventListener("click", () => {{
    speed = (speed + 1) % speeds.length;
    Object.values(audios).forEach(a => {{ if (a) a.playbackRate = speeds[speed]; }});
    speedBtn.textContent = speeds[speed] + "×";
  }});

  function currentSection() {{
    const heads = document.querySelectorAll('.report:not([hidden]) h2');
    let idx = 0;
    heads.forEach((h, i) => {{ if (h.getBoundingClientRect().top < 120) idx = i + 1; }});
    return idx;
  }}
  function setLang(next, keepPlace) {{
    if (!titles[next]) next = Object.keys(titles)[0];  // the report's first language
    const section = keepPlace ? currentSection() : 0;
    if (next !== lang && audios[lang]) audios[lang].pause();  // the two narrations are different scripts
    document.querySelectorAll(".clip video").forEach(v => v.pause());
    lang = next;
    document.querySelectorAll("[data-lang]").forEach(el => {{ el.hidden = el.dataset.lang !== lang; }});
    buttons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.setLang === lang)));
    playBtns.forEach(b => b.setAttribute("aria-label", ui[lang].play));
    seek?.setAttribute("aria-label", ui[lang].seek);
    speedBtn?.setAttribute("aria-label", ui[lang].speed);
    document.querySelector(".lang").setAttribute("aria-label", ui[lang].switch);
    document.documentElement.lang = document.querySelector('.report[data-lang="' + lang + '"]')?.lang || lang;
    document.title = titles[lang];
    try {{ localStorage.setItem("report-lang", lang); }} catch (e) {{}}
    const url = new URL(location.href); url.searchParams.set("lang", lang);
    if (keepPlace && /^#([a-z]{{2,3}})-s\\d+$/.test(url.hash)) url.hash = section ? lang + "-s" + section : "";
    history.replaceState(null, "", url);
    if (section) document.getElementById(lang + "-s" + section)?.scrollIntoView();
    syncAudio();
  }}
  buttons.forEach(b => b.addEventListener("click", () => setLang(b.dataset.setLang, true)));
  const fromHash = location.hash.match(/^#([a-z]{{2,3}})-s\\d+$/);
  let start = fromHash ? fromHash[1] : new URLSearchParams(location.search).get("lang");
  if (!start) {{ try {{ start = localStorage.getItem("report-lang"); }} catch (e) {{}} }}
  const nav = (navigator.language || "").slice(0, 2).toLowerCase();  // the reader's language, else English
  if (!start) start = titles[nav] ? nav : "en";
  setLang(start || Object.keys(titles)[0], false);
  if (fromHash) document.querySelector(location.hash)?.scrollIntoView();  // target was hidden at load
  const clipHash = location.hash.match(/^#clip-([0-9_-]+)$/);  // language-free link to a clip
  if (clipHash) document.getElementById(lang + "-clip-" + clipHash[1])?.scrollIntoView();
}})();
</script>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default="index.html", help="file name in the folder, or an absolute path")
    ap.add_argument("--share", action="store_true", help="copy to send to others: drop repo links and local paths, embed audio and clips")
    a = ap.parse_args(argv)
    folder = Path(a.folder)
    out = folder / a.out
    out.write_text(page(folder, a.share), encoding="utf8")
    print("wrote", out, f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
