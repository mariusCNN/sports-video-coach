"""The language registry: every report language the core knows, in one table (LANGS).

A language is its code (the file suffix: README.ja.md, listen.ja.md, film.ja.md; `--lang ja`), its BCP 47 tag for
the page, the edge-tts voice that reads it, how its text is counted and wrapped (CJK: no spaces between words), its
read speed for length estimates, the subtitle font per platform and the page's labels. README.md is the Chinese
report, README.<code>.md every other language. A language without its own page labels shows the English ones.

Add a language: one `Lang(...)` in LANGS (docs/architecture.md says what each field does).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

# the film's subtitle font since the first release; it covers Latin scripts too
DEFAULT_FONTS = {"win32": "Microsoft YaHei", "darwin": "PingFang SC", "other": "Noto Sans CJK SC"}


@dataclass(frozen=True)
class Lang:
    code: str             # file suffix and --lang value
    tag: str              # BCP 47, the page's lang attribute
    name: str             # in English, for messages ("missing: listen.ja.md (Japanese)")
    button: str           # the page's language switch
    voice: str            # default edge-tts voice
    alt_voice: str        # another voice of the language (the other gender), for narration.voices
    per_min: int          # read speed of `voice`: what count() counts, a minute
    cjk: bool = False     # no spaces between words: count characters without punctuation, wrap anywhere
    sub_chars: int = 84   # one film subtitle at most (about two lines at 720p)
    fonts: dict = field(default_factory=lambda: DEFAULT_FONTS)  # subtitle font per platform
    page_font: str = ""   # CSS font stack for the page body (empty: the default stack)
    ui: dict | None = None  # page labels (None: English)
    film: dict = field(default_factory=dict)  # film tags: slow, freeze (missing: English)


UI_ZH = dict(contents="目录", switch="切换语言", reports="报告",
             listen="听报告", listen_sub="约 {m} 分钟，可以边看边听", listen_sub_s="约 {s} 秒，可以边看边听",
             play="播放 / 暂停", seek="播放进度", speed="播放速度",
             clip="片段", slow="慢放", missing="（片段还没剪：运行 clips）")
UI_EN = dict(contents="Contents", switch="Switch language", reports="Reports",
             listen="Listen to the report", listen_sub="About {m} min. Read along or just listen.",
             listen_sub_s="About {s} seconds. Read along or just listen.", play="Play / pause",
             seek="Playback position", speed="Playback speed",
             clip="Clip", slow="Slow-mo", missing="(clip not cut yet: run the clips stage)")
UI_JA = dict(contents="目次", switch="言語を切り替える", reports="レポート",
             listen="レポートを聞く", listen_sub="約 {m} 分。読みながらでも、聞くだけでも", listen_sub_s="約 {s} 秒。読みながらでも、聞くだけでも",
             play="再生 / 一時停止", seek="再生位置", speed="再生速度",
             clip="クリップ", slow="スロー", missing="（クリップがまだありません：clips を実行してください）")

# per_min: zh and en measured on rendered report scripts (zh: Chinese characters without punctuation, en: characters
# with spaces; English words a minute range 130-190 with word length). The others come from one ~25 s sample
# paragraph per default voice (2026-10-23), not from full scripts: treat them as rough until measured (ja 285: an 84 s report script).
LANGS: dict[str, Lang] = {l.code: l for l in (
    Lang("zh", "zh-CN", "Chinese", "中文", "zh-CN-YunjianNeural", "zh-CN-XiaoxiaoNeural", 235, cjk=True, sub_chars=30,
         ui=UI_ZH, film=dict(slow="慢放", freeze="定格")),
    Lang("en", "en", "English", "EN", "en-US-AndrewNeural", "en-US-AvaNeural", 960,
         ui=UI_EN, film=dict(slow="Slow motion", freeze="Paused")),
    Lang("ja", "ja", "Japanese", "日本語", "ja-JP-KeitaNeural", "ja-JP-NanamiNeural", 285, cjk=True, sub_chars=30,
         fonts={"win32": "Yu Gothic", "darwin": "Hiragino Sans", "other": "Noto Sans CJK JP"},
         page_font='"Noto Sans JP", "Hiragino Sans", "Yu Gothic", Meiryo, system-ui, sans-serif',
         ui=UI_JA, film=dict(slow="スロー", freeze="一時停止")),
    Lang("ko", "ko", "Korean", "한국어", "ko-KR-InJoonNeural", "ko-KR-SunHiNeural", 270, cjk=True, sub_chars=34,
         fonts={"win32": "Malgun Gothic", "darwin": "Apple SD Gothic Neo", "other": "Noto Sans CJK KR"},
         page_font='"Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif',
         film=dict(slow="슬로모션", freeze="일시정지")),
    Lang("es", "es", "Spanish", "ES", "es-ES-AlvaroNeural", "es-ES-ElviraNeural", 850,
         film=dict(slow="Cámara lenta", freeze="Pausa")),
    Lang("fr", "fr", "French", "FR", "fr-FR-HenriNeural", "fr-FR-DeniseNeural", 950,
         film=dict(slow="Ralenti", freeze="Pause")),
    Lang("de", "de", "German", "DE", "de-DE-ConradNeural", "de-DE-KatjaNeural", 950,
         film=dict(slow="Zeitlupe", freeze="Standbild")),
    Lang("pt", "pt-BR", "Portuguese", "PT", "pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", 800,
         film=dict(slow="Câmera lenta", freeze="Pausa")),
)}
CODES = tuple(LANGS)


class Unknown(SystemExit):
    """A language code the registry does not know: exits with one line naming the known ones."""


def get(code: str) -> Lang:
    """The registry entry of `code`; Unknown (exit with the supported codes) for any other."""
    if code not in LANGS:
        raise Unknown(f"unknown language {code!r} (supported: {', '.join(CODES)}; add one in "
                      "sports_video_coach/langs.py)")
    return LANGS[code]


def tag(code: str) -> str:
    """BCP 47 tag for the page ("zh-CN"); an unknown code is used as it is."""
    return LANGS[code].tag if code in LANGS else code


def name(code: str) -> str:
    return LANGS[code].name if code in LANGS else code


def cjk(code: str) -> bool:
    return code in LANGS and LANGS[code].cjk


def readme(code: str) -> str:
    """README.md is the Chinese report, README.<code>.md any other language."""
    return "README.md" if code == "zh" else f"README.{code}.md"


def ui(code: str) -> dict[str, str]:
    """The page labels of a language, English where it has none."""
    return dict((LANGS.get(code) and LANGS[code].ui) or UI_EN)


def film_tag(code: str, key: str) -> str:
    """A film tag ("slow", "freeze") in the language, else in English."""
    own = LANGS[code].film if code in LANGS else {}
    return own.get(key) or LANGS["en"].film[key]


def font(code: str, platform: str = sys.platform) -> str:
    """The subtitle font for the language on this platform (win32, darwin, other)."""
    fonts = LANGS[code].fonts if code in LANGS else DEFAULT_FONTS
    return fonts.get(platform) or fonts["other"]


def count(text: str, code: str) -> int:
    """What per_min counts: in a CJK language the characters without punctuation and spaces, else every character."""
    return len(re.findall(r"\w", text)) if cjk(code) else len(text)


def read_s(text: str, code: str) -> float:
    """Seconds the default voice takes to read `text` (an unknown code reads at the English speed)."""
    return count(text, code) / (LANGS.get(code) or LANGS["en"]).per_min * 60
