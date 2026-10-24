"""Turn a report into one explained video: the narration plays over the clips, charts and chapter cards it talks
about, with burned-in subtitles, so the team can just watch.

Script: film.<lang>.md in the report folder (writing guide: the plugin's prompts/film.md). Every visual line starts a
scene:

    # note for the writer                                  not read, not shown
    ## Why the 22-4 run happened                           chapter card (over blurred footage of the next clip)
    ![#7 drives into #11's press](clip:03:08-03:20)       footage (video time); caption = banner at the top
    > 03:10 0.42,0.61 0.42,0.61->0.6,0.55 "nobody comes"  freeze the clip there and draw on it (see film_draw)
    >                                                      (alone) the clip plays on; what follows is read over it
    ![Score margin](momentum.png)                          a picture from the folder, fitted to the frame
    ![fouls in the 4th quarter](stat:9)                    a big number with its caption
    ![Get back on defence](court:plays/safety.json)        a plugin scene kind (`<prefix>:`, Plugin.scenes;
                                                           basketball: an animated court diagram)

Paragraphs after a visual line are narrated over it (blank line = paragraph, as in listen.<lang>.md); paragraphs
before the first visual go over a title card (FilmHooks.title, else the unit json title / folder name and date). A
clip shorter than its narration plays once, then replays at half speed, then holds its last frame; game sound is
turned down under the voice. A scene without narration lasts CARD_S / IMAGE_S, or the clip's own length.

Freeze lines: the clip plays up to that moment, stops, and the paragraphs after the `>` line are narrated over the
frozen frame (a punch-in zoom on a long hold, the rest dimmed around the marked spots: a floor ring in the team colour,
arrows that draw on, a label pill, one beat at a time); then the clip
plays on. A `>` line on its own resumes the clip at once: the paragraphs after it are read over the running play.
x,y fractions of the frame always work; a plugin may add marks found in its tracking (FilmHooks.parse_ref / tracks;
basketball: 我#7 / 对#11 from run/tracks.pkl, --run). In a plugin scene with steps (a court diagram) the first
paragraph goes over the set-up and each further paragraph starts the next step.

The folder's owning plugin (plugin.owner) gives the hooks; a folder no plugin owns, or a plugin without hooks, gets
the generic scenes only (clips, pictures, stats, cards) and a generic title card. A scene prefix nobody knows stops
the run with the list of known prefixes.

Each paragraph is spoken by edge-tts (needs internet: the text is sent to Microsoft's TTS service) and cached in
<folder>/.film-cache/, so editing one scene only re-speaks that scene. Needs ffmpeg with libass ($FFMPEG and
$FFPROBE override the binaries).

usage: sports-video-coach film <report folder> [--lang zh en] [--video game.mp4] [--run run/]
       [--height 720] [--crf 23] [--font "Microsoft YaHei"] [--scenes 3-6] [--dry] [--force]
--crf trades size for quality (x264: +6 is about half the size; 23 makes ~75 MB for 10 min at 720p).
A full render also writes film.<lang>.jpg, a poster frame from the title card (~1 s).
--dry checks the script and prints the scene list with estimated lengths (no TTS, no rendering).
--scenes renders only those scenes (1-based) into film.<lang>.preview.mp4, for a quick look.
A film.<lang>.mp4 newer than its script and the files it shows (the video, pictures, plugin scene files) is kept,
so adding a language renders only that one; --force renders it again.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import film_draw as fd
from . import langs as L
from . import media, units
from .clips import seconds
from .media import duration_s, ffmpeg, has_audio, video_size
from .narrate import voice_for, voices

FPS = 30
CRF = 23                         # x264 quality (--crf): higher = smaller file
POSTER_S = 1.0                   # poster frame time (the title card)
LEAD, TAIL, GAP = 0.3, 0.5, 0.4  # silence before the voice, after it, and between paragraphs (s)
CARD_S, IMAGE_S = 3.0, 4.0       # scene length without narration
SLOW = 0.5                       # replay speed when the narration outlasts a clip
DUCK = 0.2                       # game sound volume under the voice
MAX_CHARS = {c: l.sub_chars for c, l in L.LANGS.items()}  # one subtitle at most (about two lines at 720p)
FREEZE_S = 2.0                   # a freeze without narration
MIN_ZOOM_HOLD = 1.5              # a shorter freeze is not zoomed (in and out would be all it does)
BANNER_S = 6.0                  # a clip's caption shows this long, at its start
COUNT_S, COUNT_STEPS = 0.6, 12   # a stat card's number counts up in this long, in so many steps
KICKER_RE = re.compile(r"^([^：:]{1,12})[：:]\s*(.+)$")  # "第一件事：有压力" -> kicker "第一件事", title "有压力"
SLOW_TAG = {c: L.film_tag(c, "slow") for c in L.CODES}
FREEZE_TAG = {c: L.film_tag(c, "freeze") for c in L.CODES}
TARGET_S = (120, 240)  # film length the guides ask for (2-4 min)


def target_s(video_s: float | None) -> tuple[int, int]:
    """The film length (seconds) the guide asks for: 2-4 min; for a source under a minute two to four times its
    length to the nearest 5 s, as the guide states it (a 22 s drill: 45-90 s), at least 30-60 s."""
    if video_s is None or video_s >= 60:
        return TARGET_S
    lo = max(30, 5 * round(2 * video_s / 5))
    return lo, max(60, 5 * round(4 * video_s / 5))


def length_text(s: float) -> str:
    """A film length as --dry prints it: seconds under 2 min (58 s never reads as 1.0 min), else minutes."""
    return f"{s:.0f} s" if s < 120 else f"{s / 60:.1f} min"
WORD_RE = re.compile(r"[^\W_]")  # a letter, digit or CJK character: something to speak
STILL_MAX_S = 12.0  # --dry notes a still scene (title, stat, picture) that talks longer than this
FONT = L.font("zh")  # the Chinese subtitle font (plugin title cards); every language has its own (langs.font)
BG = "#14161f"

TIME = r"\d{1,2}:\d{2}(?:\.\d)?"
CLIP_RE = re.compile(rf"^({TIME})-({TIME})$")
TIME_RE = re.compile(rf"^{TIME}$")
VISUAL_RE = re.compile(r"^!\[(.*)\]\((.+)\)$")
PREFIX_RE = re.compile(r"^([a-z][a-z0-9_-]+):(?!//)")  # `clip:`, `stat:`, a plugin's `court:` (not C:/ or http://)
BUILTIN = ("clip", "stat")  # the scene prefixes every folder has; a picture has none
MARK_HELP = '0.4,0.6, A->B, "label"'
DEFAULT_ACCENT, DEFAULT_SECOND = "#6250d6", "#e0e0e0"


@dataclass
class FilmCtx:
    """What a plugin scene renders with."""
    folder: Path
    data: dict      # the unit json
    lang: str
    w: int
    h: int
    fps: int
    accent: str     # FilmHooks.colours: our colour
    second: str     # the other side's colour


@dataclass
class SceneKind:
    """One film-script scene kind a plugin adds: `![caption](<prefix>:<file>)`, the file relative to the folder.
    Rendered as still frames + an ffconcat list over IMAGE_S or its narration; each paragraph after the first starts
    the next step (steps(obj) of them), each step animates in `anim` seconds."""
    prefix: str                                          # "court"
    noun: str                                            # "court diagram", for messages
    parse: Callable[[Path], Any]                         # the scene file -> object (ValueError / TypeError if bad)
    render: Callable[[Any, FilmCtx, list[float], float, Path], Path]  # (obj, ctx, step starts, length, dir) -> ffconcat
    problems: Callable[[Any], list[str]] = lambda obj: []
    steps: Callable[[Any], int] = lambda obj: 0
    anim: float = 1.0


@dataclass
class FilmHooks:
    """What a plugin adds to the film; every field optional (None = the generic behaviour)."""
    title: Callable[[Path, dict, int], str] | None = None       # (folder, unit json, height) -> ASS title card text
    colours: Callable[[dict], tuple[str, str]] | None = None    # unit json -> (accent, second colour)
    parse_ref: Callable[[str], tuple | None] | None = None      # freeze token -> a tracked mark ('player', ...) / None
    tracks: Callable[[Path | None, Path, Path | None, int, int], Any] | None = None  # (--run, folder, video, src w,
    #                                                  src h) -> object with locate(mark, t) -> box, or None
    mark_help: str = MARK_HELP                                  # the readable marks, in the "cannot read" message


GENERIC = FilmHooks()


def hooks_for(folder: Path) -> tuple[FilmHooks, dict[str, SceneKind]]:
    """The film hooks and scene kinds of the plugin owning `folder`; generic ones when none (or it has none)."""
    from . import plugin
    own = plugin.owner(folder)
    p = own[0] if own else None
    return (p.film if p and p.film else GENERIC), dict(p.scenes if p and p.scenes else {})


@dataclass
class Freeze:
    line: str  # the `> mm:ss marks "label"` line
    paras: list[str] = field(default_factory=list)
    ref: Callable[[str], tuple | None] | None = field(default=None, repr=False, compare=False)  # plugin marks

    def parts(self):
        return fd.parse_freeze_line(self.line, self.ref)  # (time text, marks, label, unreadable tokens)

    @property
    def resume(self) -> bool:
        """A bare `>`: the clip plays on, and the paragraphs after it are read over the running play."""
        return self.line.strip() == ">"

    def at(self) -> float | None:
        return None if self.resume else seconds(self.parts()[0])


@dataclass
class Scene:
    kind: str  # title | card | image | clip | stat | a plugin scene prefix (court)
    text: str  # card title or banner caption
    src: str = ""  # image path, "mm:ss-mm:ss" for a clip, the number for a stat, the file of a plugin scene
    paras: list[str] = field(default_factory=list)
    freezes: list[Freeze] = field(default_factory=list)

    def window(self) -> tuple[float, float]:
        m = CLIP_RE.match(self.src)
        return seconds(m[1]), seconds(m[2])

    def clip_s(self) -> float:
        if self.kind != "clip":
            return 0.0
        t0, t1 = self.window()
        return t1 - t0


def parse_script(text: str, hooks: FilmHooks | None = None) -> list[Scene]:
    """Scenes of a film script; `<prefix>:` targets become scenes of kind <prefix> (check() rejects unknown ones),
    hooks.parse_ref reads the plugin's freeze marks."""
    ref = hooks.parse_ref if hooks else None
    scenes: list[Scene] = []
    para: list[str] = []

    def end_para():
        if para:
            if not scenes:
                scenes.append(Scene("title", ""))
            sc = scenes[-1]
            (sc.freezes[-1].paras if sc.freezes else sc.paras).append(" ".join(" ".join(para).split()))
            para.clear()

    for raw in text.splitlines():
        line = raw.strip()
        m = VISUAL_RE.match(line)
        if line.startswith("## ") or m:
            end_para()
            if m:
                cap, target = m[1].strip(), m[2].strip()
                pm = PREFIX_RE.match(target)
                kind = pm[1] if pm else "image"
                scenes.append(Scene(kind, cap, target[len(kind) + 1:].strip() if kind != "image" else target))
            else:
                scenes.append(Scene("card", line[3:].strip()))
        elif line.startswith(">"):
            end_para()
            if not scenes:
                scenes.append(Scene("title", ""))
            scenes[-1].freezes.append(Freeze(line, ref=ref))
        elif line.startswith("#"):
            continue
        elif not line:
            end_para()
        else:
            para.append(line)
    end_para()
    return scenes


def check(scenes: list[Scene], folder: Path, video: Path | None, video_s: float | None, tracks=None,
          kinds: dict[str, SceneKind] | None = None, hooks: FilmHooks = GENERIC) -> list[str]:
    """Problems that would stop the render (missing pictures, bad clip windows, no video, unreadable freezes,
    scene prefixes no plugin knows). kinds: the plugin's scene kinds by prefix."""
    kinds = kinds or {}
    out = []
    for i, sc in enumerate(scenes, 1):
        for p in [*sc.paras, *(p for fz in sc.freezes for p in fz.paras)]:
            if not WORD_RE.search(html.unescape(p)):  # `&gt;` alone is a symbol too
                out.append(f"scene {i}: {p!r} has nothing to say (TTS gets no speech from it); write words or drop it")
        if sc.kind == "image" and not (folder / sc.src).is_file():
            out.append(f"scene {i}: picture not found: {folder / sc.src}")
        if sc.kind not in ("title", "card", "image", *BUILTIN, *kinds):
            known = ", ".join(f"{k}:" for k in (*BUILTIN, *kinds))
            out.append(f"scene {i}: unknown scene prefix {sc.kind + ':'!r} (known here: {known}; a plugin adds more)")
        if sc.kind in kinds:
            sk, f = kinds[sc.kind], folder / sc.src
            if not f.is_file():
                out.append(f"scene {i}: {sk.noun} not found: {f}")
            else:
                try:
                    out += [f"scene {i} ({sc.src}): {p}" for p in sk.problems(sk.parse(f))]
                except (ValueError, TypeError, AttributeError) as e:
                    out.append(f"scene {i}: cannot read {f}: {e}")
        if sc.freezes and sc.kind != "clip":
            out.append(f"scene {i}: freeze lines (>) only work after a clip line")
        if sc.kind == "clip" and CLIP_RE.match(sc.src):
            t0, t1 = sc.window()
            times = []
            for k, fz in enumerate(sc.freezes):
                if fz.resume:
                    if not k or sc.freezes[k - 1].resume:
                        out.append(f"scene {i}: a `>` line on its own resumes the clip; it only works after a freeze")
                    continue
                t, marks, _, bad = fz.parts()
                if not TIME_RE.match(t):
                    out.append(f"scene {i}: freeze needs a time first (> mm:ss ...), got {fz.line!r}")
                    continue
                times.append(seconds(t))
                if not t0 <= seconds(t) <= t1:
                    out.append(f"scene {i}: freeze {t} is outside the clip {sc.src}")
                out += [f"scene {i}: freeze {t}: only one \"label\" per freeze line; split it into two lines or drop "
                        f"{b!r}" if b[:1] in "\"“" else f"scene {i}: freeze {t}: cannot read {b!r} ({hooks.mark_help})"
                        for b in bad]
                if tracks is None and any(m[0] != "point" for mk in marks for m in points(mk)):
                    out.append(f"scene {i}: freeze {t} marks players but no CV tracks were found; pass --run")
            if times != sorted(times):
                out.append(f"scene {i}: freeze lines must be in time order")
        if sc.kind == "clip":
            if not CLIP_RE.match(sc.src):
                out.append(f"scene {i}: clip window must be mm:ss-mm:ss, got {sc.src!r}")
                continue
            t0, t1 = sc.window()
            if t1 <= t0:
                out.append(f"scene {i}: clip {sc.src} ends before it starts")
            if video is None or not video.is_file():
                out.append(f"scene {i}: clip needs the game video; pass --video or set video in the unit json")
            elif video_s is not None and t1 > video_s + 0.5:
                out.append(f"scene {i}: clip {sc.src} runs past the end of the video ({video_s:.0f} s)")
    return out


def points(mark) -> tuple:
    """The player / point marks inside a mark (an arrow has two)."""
    return mark[1:] if mark[0] == "arrow" else (mark,)


def freeze_warnings(scenes: list[Scene], tracks) -> list[str]:
    """Marks after the label (the label belongs at the end of the line), and marked players the tracks do not
    have at that moment (their ring is left out)."""
    out = []
    for i, sc in enumerate(scenes, 1):
        for fz in sc.freezes:
            t, marks, _, _ = fz.parts()
            m = fd.LABEL_RE.search(fz.line)
            if m and fz.line[m.end():].strip():
                out.append(f"scene {i}: freeze {t}: `{fz.line[m.end():].strip()}` comes after the label; put the "
                           "label last: > mm:ss.s x,y x,y \"label\"")
            if tracks is None or not TIME_RE.match(t):
                continue
            for m in dict.fromkeys(m for mk in marks for m in points(mk)):
                if m[0] != "point" and fd.mark_box(m, seconds(t), tracks) is None:
                    name = "#".join(map(str, m[1:]))  # ('player', 'us', '9') -> us#9
                    out.append(f"scene {i}: freeze {t}: {name} is not in the tracks near that moment; "
                               f"mark them with x,y instead")
    return out


def clip_plan(t0: float, t1: float, freeze_at: list[float | None], voice: list[float]):
    """A clip with freezes. voice[0] = narration before the first freeze, voice[k] = narration on freeze k
    (freeze_at None: a resume, read over the play that follows). Returns (length, segments, narration starts,
    freeze spans): segments are ("play", from, to) in video time or ("hold", at, seconds); starts are scene times
    (None for a group without narration); spans are None for a resume."""
    segs, starts, spans = [], [LEAD if voice[0] else None], []
    s, v, end = 0.0, t0, (LEAD + voice[0]) if voice[0] else 0.0
    for tk, vk in zip(freeze_at, voice[1:]):
        if tk is None:  # the play goes on at once; the voice follows the freeze narration
            ns = max(s + 0.3, end + GAP if end else 0.0) if vk else None
            if vk:
                end = ns + vk
            starts.append(ns)
            spans.append(None)
            continue
        if tk > v:
            segs.append(("play", v, tk))
            s, v = s + tk - v, tk
        if vk:
            ns = max(s + LEAD, end + GAP if end else 0.0)  # the narration before it may still be running
            fe, end = ns + vk + TAIL, ns + vk
        else:
            ns, fe = None, s + FREEZE_S
        starts.append(ns)
        spans.append((s, fe))
        segs.append(("hold", tk, fe - s))
        s = fe
    if t1 > v:
        segs.append(("play", v, t1))
        s += t1 - v
    return max(s, end + TAIL if end else 0.0), segs, starts, spans


def timing(kind: str, voice_s: float, clip_s: float = 0.0) -> tuple[float, float]:
    """(scene length, slow-motion replay length) for a scene with `voice_s` seconds of narration."""
    if kind == "clip":
        if not voice_s:
            return clip_s, 0.0
        need = LEAD + voice_s + TAIL
        if need <= clip_s + 1.0:  # a short overrun just holds the last frame
            return max(clip_s, need), 0.0
        return need, min(clip_s / SLOW, need - clip_s)
    base = CARD_S if kind in ("title", "card", "stat") else IMAGE_S
    return (max(base, LEAD + voice_s + TAIL) if voice_s else base), 0.0


# ---- subtitles ---------------------------------------------------------------------------------------------

def chunks(text: str, max_chars: int) -> list[str]:
    """Split a sentence into subtitle-sized pieces, at commas first, then at spaces or anywhere."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    packed, cur = [], ""
    for piece in re.findall(r"[^，、；：,;:]+[，、；：,;:]?\s*|[，、；：,;:]\s*", text):
        if cur.strip() and len(cur) + len(piece) > max_chars:
            packed.append(cur.strip())
            cur = ""
        cur += piece
    if cur.strip():
        packed.append(cur.strip())
    out = []
    for c in packed:
        while len(c) > max_chars:
            cut = c.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            out.append(c[:cut].strip())
            c = c[cut:].strip()
        if c:
            out.append(c)
    return out


def em_width(text: str) -> float:
    """Rough width of `text` in ems: a CJK (wide) character is 1, anything else about 0.55."""
    return sum(1.0 if unicodedata.east_asian_width(c) in "WF" else 0.55 for c in text)


def _kind(c: str) -> str:
    """h (hiragana), k (katakana and ー), c (kanji), p (punctuation), else o."""
    return ("h" if "぀" <= c <= "ゟ" else "k" if "゠" <= c <= "ヿ" else "c" if "一" <= c <= "鿿" or c == "々"
            else "p" if c in "，、；：。！？,;:" else "o")


def ja_score(a: str, b: str) -> int:
    """How good a Japanese line break between `a` and `b` is: 3 after punctuation or a particle before a new word,
    2 at another kana-to-kanji / katakana step, 1 between hiragana or kanji and katakana, 0 inside a kanji run, a
    katakana word, before okurigana, punctuation or a small kana."""
    ka, kb = _kind(a), _kind(b)
    if kb == "p" or b in "ゃゅょっぁぃぅぇぉャュョッァィゥェォー":
        return 0
    if ka == "p" or ka == "h" and kb in "ck":
        return 3 if ka == "p" or a in "はがをにへでとのも" else 2
    return 1 if (ka, kb) in (("h", "h"), ("k", "c"), ("c", "k")) else 0


def ja_break(text: str, at: int, lo: int, near: int = 3) -> int:
    """The best break in `text` within `near` characters of `at` (not before `lo`): `at` when none is better."""
    ks = range(max(lo, at - near), min(len(text) - 1, at + near) + 1)
    best = max(ks, key=lambda k: (ja_score(text[k - 1], text[k]), -abs(k - at)), default=at)
    return best if ja_score(text[best - 1], text[best]) > ja_score(text[at - 1], text[at]) else at


def fit(text: str, cap: float, lang: str = "") -> list[str]:
    """`text` as balanced lines of at most `cap` ems. libass wraps at spaces only, so CJK text with no spaces runs
    off a narrow frame; this breaks it, after punctuation when one is close, never inside a Latin word or number.
    Japanese also breaks after a particle or at a kana-kanji step close by, not inside a word (ja_break).
    Text with no wide characters is left to libass (one line)."""
    width = em_width(text)
    if width <= cap or not any(unicodedata.east_asian_width(c) in "WF" for c in text):
        return [text]
    for n in range(math.ceil(width / cap), math.ceil(width / cap) + 3):
        target, lines, cur, hold = width / n, [], "", 0
        for i, c in enumerate(text):
            cur += c
            nxt = text[i + 1:i + 2]
            if hold:  # a better Japanese break a few characters on
                if i + 1 < hold:
                    continue
                cut, hold = len(cur), 0
            else:
                if len(lines) == n - 1 or em_width(cur) < target or (c.isascii() and c.isalnum() and nxt.isascii()
                                                                     and nxt.isalnum()):
                    continue
                back = max(cur.rfind(p) for p in "，、；：。,;:")
                cut = back + 1 if 0 <= back < len(cur) - 1 and em_width(cur[:back + 1]) >= target * 0.7 else len(cur)
                if lang == "ja" and cut == len(cur) and nxt:
                    k = ja_break(text, i + 1, i + 2 - len(cur))
                    if k > i + 1:
                        hold = k
                        continue
                    cut -= i + 1 - k
            lines.append(cur[:cut])
            cur = cur[cut:]
        lines = [x.strip() for x in [*lines, cur] if x.strip()]
        if all(em_width(x) <= cap for x in lines):
            return lines
    return lines


def tidy(t: str) -> str:
    """Subtitles drop trailing commas and full stops (but keep ? and !)."""
    return t.strip().rstrip("，。、；：,;:.").strip()


def cue_split(start: float, end: float, text: str, max_chars: int) -> list[tuple[float, float, str]]:
    parts = chunks(text, max_chars)
    total = sum(len(p) for p in parts) or 1
    out, t = [], start
    for p in parts:
        d = (end - start) * len(p) / total
        out.append((t, t + d, tidy(p)))
        t += d
    return [c for c in out if c[2]]


def ass_time(s: float) -> str:
    cs = int(round(max(s, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def ass_colour(hex_: str, alpha: int = 0) -> str:
    r, g, b = units.hex_to_rgb(hex_)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def ass_escape(t: str) -> str:
    return t.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def ass_doc(w: int, h: int, font: str, accent: str, events: list[tuple[float, float, str, str]]) -> str:
    """events: (start, end, style, text); text is already escaped and may carry ASS override tags. Sizes follow the
    short side, so a portrait film has the same text size as a landscape one."""
    u = min(w, h)
    m = round(u * 0.04)
    side = round(w * 0.08)  # banner keeps clear of broadcast logos in the top corners
    white, ink, shade = "&H00FFFFFF", "&H00000000", "&H80000000"
    styles = {  # size, primary, outline/box, back (shadow), border style, outline, shadow, alignment, margin l/r,
        # margin v, bold. One system: white type, a thin dark outline and a soft shadow instead of boxes
        "Sub": (round(u * 0.055), white, ink, shade, 1, max(2, round(u * 0.004)), max(1, round(u * 0.003)), 2, m,
                round(u * 0.045), 1),
        "Banner": (round(u * 0.034), white, ass_colour(fd.INK_HEX, 0x40), ass_colour(fd.INK_HEX, 0x40), 3,
                   round(u * 0.014), 0, 8, side, m, 1),
        "Title": (round(u * 0.075), white, ink, shade, 1, 0, max(1, round(u * 0.004)), 5, m, 0, 1),
        "Kicker": (round(u * 0.036), ass_colour(accent), ink, shade, 1, 0, max(1, round(u * 0.003)), 1, m, 0, 1),
        "Tag": (round(u * 0.032), white, ink, ink, 1, 0, 0, 4, m, m, 1),  # the badge text (film_draw.badge)
        "Draw": (20, white, ink, ink, 1, 0, 0, 7, 0, 0, 0),  # telestration shapes (ASS drawings)
        "Mark": (round(u * 0.04), white, ink, ink, 1, 0, 0, 5, m, 0, 1),  # a freeze label, in its pill
        "Big": (round(u * 0.2), white, ink, shade, 1, 0, max(2, round(u * 0.006)), 2, m, 0, 1),
        "Caption": (round(u * 0.045), "&H00C8BCB8", ink, shade, 1, 0, max(1, round(u * 0.003)), 8, m, 0, 0),
    }
    layer = {"Draw": 0, "Mark": 1}
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
             "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
             "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
             "MarginL, MarginR, MarginV, Encoding"]
    for name, (size, prim, outl, back, bs, ol, sh, al, ml, mv, bold) in styles.items():
        lines.append(f"Style: {name},{font},{size},{prim},{prim},{outl},{back},{-bold},0,0,0,100,100,0,0,"
                     f"{bs},{ol},{sh},{al},{ml},{ml},{mv},1")
    lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    lines += [f"Dialogue: {layer.get(st, 2)},{ass_time(s)},{ass_time(e)},{st},,0,0,0,,{t}"
              for s, e, st, t in events if e > s]
    return "\n".join(lines) + "\n"


def scene_events(sc: Scene, length: float, slow: float, clip_s: float, cues, lang: str, title: str, h: int,
                 extra=(), frame: tuple[int, int] | None = None):
    """Subtitle events for one scene; cue times count from the start of the voice (LEAD). extra: more events.
    h: the short side (text sizes); frame: (width, height) of the film, default 16:9 at h."""
    fw, fh = frame or (round(h * 16 / 9), h)
    m, side = round(h * 0.04), round(fw * 0.08)  # the margins and font sizes ass_doc gives Sub, Banner, Title
    sub_fs, small, big = round(h * 0.057), round(h * 0.036), round(h * 0.075)
    ev = []

    def wrap(text: str, cap: float) -> str:
        return "\\N".join(ass_escape(y) for y in fit(text, cap, lang))
    if sc.kind == "title":
        ev.append((0, length, "Title", "{\\fad(400,300)}" + title))
    elif sc.kind == "card":
        ev += card_events(sc.text, length, lang, h, fw, fh)
    elif sc.kind == "stat":
        ev += stat_events(sc.src, sc.text, length, lang, h, fw, fh)
    elif sc.text:  # what the clip is about, while it starts; then the picture is the players'
        ev.append((0, min(length, BANNER_S), "Banner", "{\\fad(250,300)}" + wrap(sc.text, (fw - 2.5 * side) / small)))
    if slow:
        ev += fd.badge(SLOW_TAG.get(lang, SLOW_TAG["en"]), clip_s, clip_s + slow, fw, fh, icon="play")
    subs = sorted((LEAD + s, LEAD + e, t) for s, e, t in cues)
    for i, (s, e, t) in enumerate(subs):
        if i + 1 < len(subs) and subs[i + 1][0] - e < 0.6:  # no flicker between close subtitles
            e = subs[i + 1][0]
        ev.append((s, min(e, length), "Sub", wrap(t, (fw - 3 * m) / sub_fs)))
    return ev + list(extra)


def card_events(text: str, length: float, lang: str, h: int, fw: int, fh: int) -> list[tuple]:
    """A chapter card, left-aligned as in a broadcast: an accent bar, the kicker (what comes before the first "："
    / ":", e.g. "第一件事") in the accent colour, then the title; " · " splits it into lines that come in one after
    another (a sign-off). Each slides in a little and fades."""
    big, x0 = round(h * 0.075), round(fw * 0.1)
    parts = [x.strip() for x in text.split(" · ") if x.strip()]
    kicker = ""
    km = KICKER_RE.match(parts[0]) if len(parts) == 1 else None
    if km:
        kicker, parts = km[1].strip(), [km[2].strip()]
    rows = [fit(p, (fw - 2 * x0) / big, lang) for p in parts]
    lh = big * 1.3
    top = fh / 2 - sum(len(r) for r in rows) * lh / 2 + (h * 0.03 if kicker else 0)
    slide = round(h * 0.03)

    def move(y: float) -> str:
        return f"{{\\an7\\move({x0 - slide},{round(y)},{x0},{round(y)},0,350)\\fad(300,250)}}"

    bar_y = top - h * (0.105 if kicker else 0.045)
    ev = [(0.0, length, "Kicker", f"{{\\an7\\pos({x0},{round(bar_y)})\\p1\\fad(250,250)\\shad0}}"
           f"m 0 0 l {round(h * 0.07)} 0 l {round(h * 0.07)} {max(3, round(h * 0.007))} l 0 {max(3, round(h * 0.007))}")]
    if kicker:
        ev.append((0.1, length, "Kicker", move(top - h * 0.075) + ass_escape(kicker)))
    y = top
    for i, r in enumerate(rows):
        ev.append((0.25 + i * 0.5, length, "Title", move(y) + "\\N".join(ass_escape(x) for x in r)))
        y += len(r) * lh
    return ev


def stat_events(src: str, text: str, length: float, lang: str, h: int, fw: int, fh: int) -> list[tuple]:
    """A number card: the number in white counting up from zero, its caption muted under it. A target ("≤4",
    "≥8": what to aim for next game, not what happened) says it in words ("最多" / "at most") over the number,
    both in the accent colour, so a goal never looks like a stat."""
    src = src.strip()
    goal = next((k for k, sym in (("at_most", ("≤", "<=")), ("at_least", ("≥", ">="))) if src.startswith(sym)), None)
    if goal:
        src = src.lstrip("≤≥<>=").strip()
    cx, cy = round(fw / 2), round(fh / 2 + h * 0.06)
    style, extra = ("Kicker", f"\\fs{round(h * 0.2)}\\shad{max(2, round(h * 0.006))}") if goal else ("Big", "")
    ev = []
    if goal:
        ev.append((0.0, length, "Kicker", f"{{\\an2\\pos({cx},{round(cy - h * 0.2)})\\fs{round(h * 0.05)}"
                   f"\\fad(250,250)}}" + L.film_tag(lang, goal)))
    head = f"{{\\an2\\pos({cx},{cy}){extra}"
    nums = [int(x) for x in re.findall(r"\d+", src)]
    if nums and max(nums) <= 999:  # counts up over COUNT_S in steps, then holds
        n, t0 = COUNT_STEPS, 0.15
        for k in range(n + 1):
            p = 1 - (1 - k / n) ** 3  # ease out: fast, then settles
            shown = re.sub(r"\d+", lambda mm: str(round(int(mm[0]) * p)), src)
            s = 0.0 if k == 0 else t0 + (k - 1) * COUNT_S / n
            e = length if k == n else t0 + k * COUNT_S / n
            ev.append((s, e, style, head + ("\\fad(150,0)}" if k == 0 else "\\fad(0,250)}" if k == n else "}")
                       + ass_escape(shown)))
    else:
        ev.append((0.0, length, style, head + "\\fad(250,250)}" + ass_escape(src)))
    if text:
        cap = "\\N".join(ass_escape(y) for y in fit(text, (fw - 2 * round(h * 0.08)) / round(h * 0.045), lang))
        ev.append((0.3, length, "Caption", f"{{\\an8\\pos({cx},{round(cy + h * 0.035)})\\fad(300,250)}}" + cap))
    return ev


def title_lines(head: str, sub: str, h: int) -> str:
    """ASS title card text: the head, then `sub` (date, score) on a second line after a thin gap."""
    gap = f"\\N{{\\fs{round(h * 0.02)}}} "  # a thin blank line between the title and the date
    return ass_escape(head) + (f"{gap}\\N{{\\fs{round(h * 0.05)}\\b0\\c&HE0E0E0&}}{ass_escape(sub)}" if sub else "")


def folder_date(folder: Path) -> str:
    """The nearest yyyy-mm-dd folder name at or above `folder`, else ''."""
    return next((p for p in reversed(folder.resolve().parts) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)), "")


def report_title(folder: Path, lang: str | None) -> str:
    """The `# ` heading of the report in that language (README.md is Chinese, README.<lang>.md the others), or ""."""
    if not lang:
        return ""
    p = folder / L.readme(lang)
    m = re.match(r"#\s+(.+)", p.read_text(encoding="utf8")) if p.exists() else None
    return m.group(1).strip() if m else ""


def title_text(folder: Path, data: dict, h: int, hooks: FilmHooks = GENERIC, lang: str | None = None) -> str:
    """The title card: hooks.title, else the unit json `title`, the report's heading or the folder name, over its date
    (written the language's way, langs.date)."""
    if hooks.title:
        return hooks.title(folder, data, h)
    def shown(d):
        return L.date(d, lang) if lang else d
    head = str(data.get("title") or report_title(folder, lang) or shown(folder.resolve().name))
    sub = str(data.get("date") or folder_date(folder))
    # a heading "<sport>: <who>, <date>" has it already
    return title_lines(head, "" if sub in head or shown(sub) in head else shown(sub), h)


# ---- speech ------------------------------------------------------------------------------------------------

async def _tts(text: str, voice: str, rate: str, out: Path) -> list[tuple[float, float, str]]:
    import edge_tts

    cues = []
    with open(out, "wb") as f:
        async for ch in edge_tts.Communicate(text, voice, rate=rate).stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "SentenceBoundary":
                cues.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    return cues


def spoken(text: str, voice: str, rate: str, cache: Path) -> tuple[Path, float, list]:
    """One paragraph as speech: (wav, seconds, sentence cues), cached by voice + rate + text."""
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode("utf8")).hexdigest()[:16]
    mp3, meta, wav = cache / f"{key}.mp3", cache / f"{key}.json", cache / f"{key}.wav"
    if mp3.exists() and meta.exists():
        m = json.loads(meta.read_text(encoding="utf8"))
        cues = [tuple(c) for c in m["cues"]]
    else:
        cache.mkdir(parents=True, exist_ok=True)
        try:
            cues = asyncio.run(_tts(text, voice, rate, mp3))
        except Exception as e:  # edge_tts.NoAudioReceived, a network error: name the paragraph, not a traceback
            mp3.unlink(missing_ok=True)
            raise SystemExit(f"edge-tts gave no speech for {text[:80]!r} ({type(e).__name__}: {e}). A paragraph "
                             "with nothing to say (only symbols) gets none: fix it in the script. Otherwise check "
                             "the internet connection and run again (spoken paragraphs are cached).") from e
        cues = cues or [(0.0, duration_s(mp3), text)]  # no sentence timing from the service: one cue, split later
        meta.write_text(json.dumps({"duration": duration_s(mp3), "cues": cues, "text": text}, ensure_ascii=False),
                        encoding="utf8")
    if not wav.exists():
        # edge-tts ends every clip with ~0.9 s of silence; cut it so scene changes and paragraph gaps stay tight
        with media.partial(wav) as part:  # a stopped run must not leave a cut-short voice in the cache
            ffmpeg("-i", str(mp3), "-af", "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                   "-c:a", "pcm_s16le", str(part))
    dur = duration_s(wav)
    return wav, dur, [(s, min(e, dur), t) for s, e, t in cues if s < dur]


def voice_track(paras: list[str], voice: str, rate: str, cache: Path, out: Path, max_chars: int):
    """Paragraphs -> one wav with GAP between them: (wav or None, seconds, subtitle cues, paragraph starts)."""
    if not paras:
        return None, 0.0, [], []
    parts, cues, starts, t = [], [], [], 0.0
    for p in paras:
        mp3, dur, pc = spoken(p, voice, rate, cache)
        starts.append(t)
        for s, e, txt in pc:
            cues += cue_split(t + s, t + e, txt, max_chars)
        parts.append(mp3)
        t += dur + GAP
    ins = [x for p in parts for x in ("-i", str(p))]
    pads = "".join(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=mono"
                   f"{f',apad=pad_dur={GAP}' if i < len(parts) - 1 else ''}[p{i}];" for i in range(len(parts)))
    ffmpeg(*ins, "-filter_complex", pads + "".join(f"[p{i}]" for i in range(len(parts))) +
           f"concat=n={len(parts)}:v=0:a=1[a]", "-map", "[a]", "-c:a", "pcm_s16le", str(out))
    return out, duration_s(out), cues, starts


# ---- rendering ---------------------------------------------------------------------------------------------

def scene_cmd(sc: Scene, length: float, slow: float, w: int, h: int, folder: Path, video: Path | None,
              game_audio: bool, voices: list[tuple[Path, float]], ass_name: str, accent: str, out: str, *,
              segs=None, bg: float | None = None, frames: str | None = None, crf: int = CRF,
              zooms=None) -> list[str]:
    """ffmpeg arguments for one scene. voices: (wav, start s) per narration group; segs: a clip's play / hold
    segments (clip_plan); bg: video time of the blurred footage behind a card; frames: a plugin scene's ffconcat
    list (a court diagram); zooms: the punch-in of each hold, in order (film_draw.freeze_zoom, None for none)."""
    zooms = list(zooms or [])
    fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    hold = f"tpad=stop_mode=clone:stop_duration={length:.3f},trim=duration={length:.3f}"
    args, graph, game = [], [], []
    duck = DUCK if voices else 1.0
    if sc.kind == "clip":
        t0, t1 = sc.window()
        segs = segs or [("play", t0, t1)]
        for i, (kind, a, b) in enumerate(segs):  # one input per segment: no frames buffered between them
            if kind == "play":
                args += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(video)]
                v = f"[{i}:v]{fit},setsar=1,fps={FPS},setpts=PTS-STARTPTS"
                if slow and len(segs) == 1:
                    v += (f",split[n][r];[r]setpts=PTS/{SLOW},fps={FPS},trim=duration={slow:.3f}[s];"
                          f"[n][s]concat=n=2:v=1:a=0")
                if game_audio:
                    graph.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=mono,asetpts=PTS-STARTPTS,"
                                 f"apad=whole_dur={b - a:.3f},atrim=duration={b - a:.3f}[g{i}]")
            else:  # a frozen frame: the first frame at that moment, cloned for b seconds, in silence
                args += ["-ss", f"{max(t0, min(a, t1 - 0.2)):.3f}", "-t", "0.2", "-i", str(video)]
                v = (f"[{i}:v]{fit},setsar=1,fps={FPS},setpts=PTS-STARTPTS,trim=end_frame=1,"
                     f"tpad=stop_mode=clone:stop_duration={b:.3f},trim=duration={b:.3f}")
                z = zooms.pop(0) if zooms else None
                if z:
                    v += "," + zoom_filter(z, b, w, h)
                if game_audio:
                    graph.append(f"aevalsrc=0:c=mono:s=48000:d={b:.3f}[g{i}]")
            graph.append(v + f"[y{i}]")
        graph.append("".join(f"[y{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0,{hold}[c]")
        if game_audio:
            graph.append("".join(f"[g{i}]" for i in range(len(segs))) +
                         f"concat=n={len(segs)}:v=0:a=1,volume={duck}[ga]")
            game = ["[ga]"]
    elif sc.kind == "image":
        args = ["-loop", "1", "-framerate", str(FPS), "-t", f"{length:.3f}", "-i", str((folder / sc.src).resolve())]
        # fitted between the banner and the subtitles, so neither covers a chart's title or axis labels
        top, bottom = round(h * 0.11), round(h * 0.15)
        graph.append(f"[0:v]scale={w}:{h - top - bottom}:force_original_aspect_ratio=decrease,"
                     f"pad={w}:{h}:(ow-iw)/2:{top}+({h - top - bottom}-ih)/2:color=white,setsar=1[c]")
    elif frames:
        args = ["-f", "concat", "-safe", "0", "-i", frames]
        graph.append(f"[0:v]scale={w}:{h},setsar=1,fps={FPS},{hold}[c]")
    else:  # title, card, stat: over the game itself, blurred and darkened, when there is footage to use
        if bg is not None and video:
            args = ["-ss", f"{bg:.3f}", "-t", f"{length:.3f}", "-i", str(video)]
            # heavily blurred and dark, so the card reads calm (no blobs of the venue's logos showing through)
            v = (f"[0:v]{fit},setsar=1,fps={FPS},setpts=PTS-STARTPTS,boxblur=30:3,eq=saturation=0.6,"
                 f"colorlevels=romax=0.28:gomax=0.28:bomax=0.3,{hold}")
        else:
            args = ["-f", "lavfi", "-i", f"color=c=0x{BG[1:]}:s={w}x{h}:r={FPS}:d={length:.3f}"]
            v = "[0:v]null"
        if sc.kind == "title":  # a chapter card draws its own accent bar (card_events)
            u = min(w, h)  # under the text, which sits mid-frame at the short side's size
            v += (f",drawbox=x={w // 2 - w // 16}:y={int(h / 2 + u * (0.14 if sc.kind == 'title' else 0.08))}:"
                  f"w={w // 8}:h={max(4, u // 120)}:color=0x{accent[1:]}:t=fill")
        graph.append(v + "[c]")
    graph.append(f"[c]format=yuv420p,ass={ass_name}[v]")

    n, labels = args.count("-i"), list(game)
    for j, (wav, start) in enumerate(voices):
        args += ["-i", str(wav)]
        graph.append(f"[{n + j}:a]aformat=sample_rates=48000:channel_layouts=mono,"
                     f"adelay={int(round(start * 1000))}:all=1[vo{j}]")
        labels.append(f"[vo{j}]")
    if not labels:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"]
        labels.append(f"[{n}:a]")
    mix = labels[0] if len(labels) == 1 else "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
    # Timestamps rebuilt from the sample count and a finite apad: some game clips came out of amix with broken
    # timestamps, and an open-ended apad then never let atrim / -t stop (ffmpeg ticket #3015 pattern).
    graph.append(f"{mix}asetpts=N/SR/TB,apad=whole_dur={length:.3f},atrim=duration={length:.3f}[a]")
    return [*args, "-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]", "-t", f"{length:.3f}",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-ac", "1", out]


def zoom_filter(zoom: tuple[float, float, float], length: float, w: int, h: int) -> str:
    """ffmpeg filter for the punch-in on a frozen frame: eases into the (zoom, x, y) window of film_draw.freeze_zoom
    over ZOOM_S and back out over the last OUT_S, so the play runs on from the full frame. The frame is doubled
    first so zoompan's whole-pixel steps do not shake."""
    z, x, y = zoom
    t = f"(in/{FPS})"
    # e: 0 -> 1 -> 0 with smoothstep ease; the window's size is linear in e (zoom = 1 / (1 - e (1 - 1/z)))
    a = f"clip({t}/{fd.ZOOM_S},0,1)"
    b = f"clip(({length:.3f}-{t})/{fd.OUT_S},0,1)"
    e = f"min({a}*{a}*(3-2*{a}),{b}*{b}*(3-2*{b}))"
    return (f"scale={2 * w}:{2 * h},zoompan=z='1/(1-{e}*{1 - 1 / z:.4f})':x='{2 * x:.1f}*{e}':y='{2 * y:.1f}*{e}'"
            f":d=1:s={w}x{h}:fps={FPS},setsar=1")


def backdrop(scenes: list[Scene], i: int) -> float | None:
    """Footage behind a card (scene index i, 0-based): the start of the next clip, else of the one before."""
    clips = [sc for sc in scenes[i + 1:] + scenes[:i][::-1] if sc.kind == "clip" and CLIP_RE.match(sc.src)]
    return clips[0].window()[0] if clips else None


def film_size(height: int, src: tuple[int, int]) -> tuple[int, int]:
    """(width, height) of the film: 16:9 with `height` as the short side, upright when the video is (a phone held
    upright), so the athlete fills the frame on the phone it is watched on."""
    long = int(round(height * 16 / 9 / 2)) * 2
    return (height, long) if src[1] > src[0] else (long, height)


def fit_box(src: tuple[int, int], w: int, h: int) -> tuple[float, float, float, float]:
    """Where a src-sized frame sits once fitted into w x h: (x, y, width, height)."""
    k = min(w / src[0], h / src[1])
    return (w - src[0] * k) / 2, (h - src[1] * k) / 2, src[0] * k, src[1] * k


def court_steps(starts: list[float], n: int) -> list[float]:
    """Step start times of a plugin scene with steps (a court diagram): paragraph 2, 3, ... start steps 1, 2, ...;
    extra steps every 2.5 s."""
    st = [LEAD + t for t in starts[1:]][:n]
    while len(st) < n:
        st.append((st[-1] if st else LEAD + 0.5) + 2.5)
    return st


def plan(sc: Scene, voice_s: list[float], para_starts: list[float], n_steps: int = 0, anim: float = 1.0):
    """(length, slow, segments, narration starts, freeze spans, step starts) for one scene; n_steps / anim: a
    plugin scene's steps and the seconds each takes to animate."""
    if sc.kind == "clip" and sc.freezes:
        t0, t1 = sc.window()
        length, segs, starts, spans = clip_plan(t0, t1, [fz.at() for fz in sc.freezes], voice_s)
        return length, 0.0, segs, starts, spans, []
    length, slow = timing(sc.kind, voice_s[0], sc.clip_s())
    steps = court_steps(para_starts, n_steps) if n_steps else []
    if steps:
        length = max(length, steps[-1] + anim + 1.0)
    return length, slow, None, [LEAD], [], steps


def build(folder: Path, lang: str, video: Path | None, height: int, font: str | None,
          pick: tuple[int, int] | None = None, dry: bool = False, run: Path | None = None,
          crf: int = CRF) -> Path | None:
    """Render film.<lang>.mp4 (font None: the language's subtitle font, langs.font)."""
    script = folder / f"film.{lang}.md"
    hooks, kinds = hooks_for(folder)
    scenes = parse_script(script.read_text(encoding="utf8"), hooks)
    if not scenes:
        sys.exit(f"{script}: no scenes")
    game = units.load(folder)
    needs_video = any(sc.kind == "clip" for sc in scenes)
    has_video = bool(video and video.is_file())
    video_s = duration_s(video) if needs_video and has_video else None
    src = video_size(video) if needs_video and has_video else (16, 9)
    tracks = None
    if hooks.tracks and any(m[0] != "point" for sc in scenes for fz in sc.freezes for mk in fz.parts()[1]
                            for m in points(mk)):
        tracks = hooks.tracks(run, folder, video, *src)
    problems = check(scenes, folder, video if needs_video else None, video_s, tracks, kinds, hooks)
    if problems:
        sys.exit(f"{script}:\n  " + "\n  ".join(problems))
    for warn in freeze_warnings(scenes, tracks):
        print(f"warning: {warn}")
    objs = {i: kinds[sc.kind].parse(folder / sc.src) for i, sc in enumerate(scenes, 1) if sc.kind in kinds}
    steps = {i: kinds[scenes[i - 1].kind].steps(o) for i, o in objs.items()}
    anim = {i: kinds[scenes[i - 1].kind].anim for i in objs}
    w, h = film_size(height, src)
    if dry:
        if h > w:
            print(f"film {w}x{h}: upright, like the video")
        total = 0.0
        for i, sc in enumerate(scenes, 1):
            groups = [sc.paras] + [fz.paras for fz in sc.freezes]
            voice_s = [sum(L.read_s(p, lang) for p in g) + GAP * max(0, len(g) - 1) for g in groups]
            starts = [sum(L.read_s(p, lang) + GAP for p in sc.paras[:k]) for k in range(len(sc.paras))]
            length, slow, *_ = plan(sc, voice_s, starts, steps.get(i, 0), anim.get(i, 1.0))
            total += length
            n_resume = sum(fz.resume for fz in sc.freezes)  # a bare > resumes the play: not a freeze
            extra = (f"  {len(sc.freezes) - n_resume} freeze(s)" + (f", {n_resume} resume(s)" if n_resume else "")
                     if sc.freezes else "  slow replay" if slow else "")
            print(f"{i:3d} {sc.kind:5s} {sc.src or sc.text[:30]:<30s} {sum(len(p) for g in groups for p in g):5d} chars"
                  f" ~{length:5.1f} s{extra}")
            for fz in sc.freezes:
                if fz.resume:
                    print("      resume: the play runs on under the next paragraphs")
                    continue
                t, marks, label, _ = fz.parts()
                print(f"      freeze {t}: {len(marks)} mark(s) {' '.join(map(fd.mark_text, marks)) or '-'}"
                      f"  label {label!r}")
            if sc.kind != "clip" and length > STILL_MAX_S:
                print(f"      note: {script.name} scene {i}: {length:.0f} s on a still picture; split the text or move "
                      f"part of it to a clip")
        print(f"{script.name}: {len(scenes)} scenes, about {length_text(total)}")
        lo, hi = target_s(video_s)
        if not lo <= round(total) <= hi:  # a warning, not an error; compared as printed
            span = f"{lo // 60}-{hi // 60} min" if lo >= 120 else f"{lo}-{hi} s"
            source = f" with a {video_s:.0f} s video" if video_s is not None and video_s < 60 else ""
            print(f"note: {script.name}: about {length_text(total)}, {'under' if total < lo else 'over'} the {span} the film "
                  f"guide aims for{source}; " + (
                      "add a moment the report covers or a slow replay of one; fine for a short report, never pad"
                      if total < lo else "cut scenes unless that is on purpose"))
        return None

    accent, second = hooks.colours(game) if hooks.colours else (DEFAULT_ACCENT, DEFAULT_SECOND)
    ctx = FilmCtx(folder, game, lang, w, h, FPS, accent, second)
    voice, rate = voice_for(lang, voices(game))
    font = font or L.font(lang)
    print(f"[film] {lang}: voice {voice} (edge-tts, online, rate {rate}), subtitle font {font}", flush=True)
    title = title_text(folder, game, height, hooks, lang)
    cache = folder / ".film-cache"
    game_audio = has_audio(video) if needs_video else False
    fit = fit_box(src, w, h)
    chosen = list(enumerate(scenes, 1))
    if pick:
        chosen = [(i, sc) for i, sc in chosen if pick[0] <= i <= pick[1]]
    out = folder / (f"film.{lang}.preview.mp4" if pick else f"film.{lang}.mp4")
    max_chars = MAX_CHARS.get(lang, 84)
    if h > w:  # a narrow frame: shorter lines, up to three of them
        max_chars = round(max_chars * w / h * 1.5)
    with media.scratch(out) as t:
        tmp = Path(t)
        rendered = []
        for i, sc in chosen:
            groups = [sc.paras] + [fz.paras for fz in sc.freezes]
            tracks_ = [voice_track(g, voice, rate, cache, tmp / f"v{i:03d}_{k}.wav", max_chars)
                       for k, g in enumerate(groups)]
            length, slow, segs, starts, spans, step_at = plan(sc, [v[1] for v in tracks_], tracks_[0][3],
                                                              steps.get(i, 0), anim.get(i, 1.0))
            voiced = [(v, st) for v, st in zip(tracks_, starts) if v[0] and st is not None]
            cues = [(a + st - LEAD, b + st - LEAD, txt) for v, st in voiced for a, b, txt in v[2]]
            extra, zooms = [], []
            for fz, span in zip(sc.freezes, spans):
                if span is None:
                    continue
                fs, fe = span
                tt, marks, label, _ = fz.parts()
                zoom = fd.freeze_zoom(marks, seconds(tt), tracks, w, h, fit) if fe - fs >= MIN_ZOOM_HOLD else None
                zooms.append(zoom)
                extra += fd.freeze_events(marks, ass_escape(label), seconds(tt), tracks, w, h, fit, fs, fe,
                                          zoom=zoom, animate=True)
                extra += fd.badge(FREEZE_TAG.get(lang, FREEZE_TAG["en"]), fs, fe, w, h, icon="pause")
            ass_name = f"s{i:03d}.ass"
            (tmp / ass_name).write_text(ass_doc(w, h, font, accent, scene_events(sc, length, slow, sc.clip_s(), cues,
                                                                                 lang, title, height, extra, (w, h))),
                                        encoding="utf8")
            frames = None
            if i in objs:
                frames = kinds[sc.kind].render(objs[i], ctx, step_at, length, tmp / f"c{i:03d}") \
                    .relative_to(tmp).as_posix()
            bg = backdrop(scenes, i - 1) if sc.kind in ("title", "card", "stat") and has_video else None
            seg = f"s{i:03d}.mp4"
            ffmpeg(*scene_cmd(sc, length, slow, w, h, folder, video, game_audio, [(v[0], st) for v, st in voiced],
                              ass_name, accent, seg, segs=segs, bg=bg, frames=frames, crf=crf, zooms=zooms),
                   cwd=tmp)
            rendered.append(seg)
            print(f"scene {i}/{len(scenes)} {sc.kind} {length:.1f} s", flush=True)
        with media.partial(out) as part:  # a stopped render never leaves a short film.<lang>.mp4 that counts as done
            media.concat([tmp / x for x in rendered], part.resolve(), tmp)
    if not pick:
        poster(out, out.with_suffix(".jpg"))
    print(f"wrote {out} {out.stat().st_size / 1e6:.1f} MB, {duration_s(out) / 60:.1f} min")
    return out


def inputs(folder: Path, lang: str, video: Path | None) -> list[Path]:
    """What film.<lang>.mp4 is made from: its script, the video (when a clip scene cuts from it), the pictures and
    plugin scene files it shows."""
    script = folder / f"film.{lang}.md"
    scenes = parse_script(script.read_text(encoding="utf8"), hooks_for(folder)[0]) if script.exists() else []
    out = [script, *([video] if video and any(sc.kind == "clip" for sc in scenes) else [])]
    return out + [folder / sc.src for sc in scenes if sc.kind not in ("title", "card", "clip", "stat") and sc.src]


def up_to_date(out: Path, ins: list[Path], slack: float = 2.0) -> bool:
    """out exists and no input changed after it (as narrate.up_to_date, over every input)."""
    return out.exists() and all(not p.exists() or p.stat().st_mtime <= out.stat().st_mtime + slack for p in ins)


def poster(mp4: Path, jpg: Path, at: float = POSTER_S) -> Path:
    """One frame (the title card at ~1 s) as the page player's poster."""
    t = min(at, duration_s(mp4) / 2)
    ffmpeg("-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", "-q:v", "3", str(jpg))
    return jpg


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # scene titles are often Chinese; a cp1252 console must not crash
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="sports-video-coach film", description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", help="report folder with film.<lang>.md")
    ap.add_argument("--lang", nargs="+", help="languages to render (default: every film.<lang>.md in the folder)")
    ap.add_argument("--video", help="the video the clips cut from (default: the unit json video)")
    ap.add_argument("--run", help="the plugin's tracking run, for tracked freeze marks (basketball: the CV run folder "
                                  "with tracks.pkl for 我#7 / 对#11; default: run/ next to the report or the video)")
    ap.add_argument("--height", type=int, default=720, help="video height in pixels (default 720)")
    ap.add_argument("--crf", type=int, default=CRF, help=f"x264 quality, higher = smaller file (default {CRF}; "
                                                          "28 is about half the size)")
    ap.add_argument("--font", help=f"subtitle font, must cover the script's language (default per language: {FONT} "
                                   f"for zh, {L.font('en')} for en and other Latin scripts, {L.font('ja')} for ja, "
                                   f"{L.font('ko')} for ko)")
    ap.add_argument("--scenes", help="render only scenes A-B (1-based) into film.<lang>.preview.mp4")
    ap.add_argument("--dry", action="store_true", help="check the script and print scenes with estimated lengths")
    ap.add_argument("--force", action="store_true", help="re-render a language whose film is newer than its script "
                                                         "and the files it shows")
    a = ap.parse_args(argv)
    folder = Path(a.folder)
    have = sorted(p.name.split(".")[1] for p in folder.glob("film.*.md"))
    order = [l for l in (units.load(folder).get("languages") or []) if l in have]
    langs = a.lang or order + [l for l in have if l not in order]  # the unit's language order (zh first if asked)
    if not langs:
        sys.exit(f"no film.<lang>.md in {folder}; see prompts/film.md")
    pick = None
    if a.scenes:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", a.scenes)
        if not m:
            ap.error("--scenes takes A or A-B, e.g. 3-6")
        pick = (int(m[1]), int(m[2] or m[1]))
    # ffmpeg runs in a temp dir: --video is relative to the shell, a unit json path to the folder
    video = Path(a.video).resolve() if a.video else units.load(folder).get("video")
    if video and not Path(video).is_absolute():
        video = (folder / video).resolve()
    for lang in langs:
        out = folder / f"film.{lang}.mp4"
        if not (a.force or a.dry or pick) and up_to_date(out, inputs(folder, lang, Path(video) if video else None)):
            print(f"[film] {lang}: {out.name} is newer than film.{lang}.md, kept (--force re-renders)")
            continue
        build(folder, lang, Path(video) if video else None, a.height, a.font, pick, a.dry,
              Path(a.run) if a.run else None, a.crf)


if __name__ == "__main__":
    main()
