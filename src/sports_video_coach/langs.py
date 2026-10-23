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
from functools import cache

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
    minutes: str = ""     # regex of a stated length ("about 2 minutes"): groups n, h1 / h2 (half), under; "": no check
    numbers: dict = field(default_factory=dict)  # number words of `minutes` (kanji numbers are read without them)


# stated lengths: the number (digits, a number word, kanji), the minute word, a half before or after it, and an
# upper bound ("under a minute"). Every pattern has the groups n, h1, h2 and under.
_KANJI = "[一两二三四五六七八九十]{1,3}"
MIN_ZH = rf"(?P<under>不到|少于)?\s*(?P<n>\d+(?:\.\d+)?|{_KANJI})\s*分(?:(?P<h1>半)钟?|钟(?P<h2>半)?)"  # not 三分球
MIN_JA = (rf"(?P<n>\d+(?:\.\d+)?|{_KANJI})\s*分(?!の[\d一二三四五六七八九十])間?(?P<h1>半)?(?P<h2>)"
          r"(?P<under>以内|未満|弱)?")  # 約2分, 約一分, 1分半, 1分以内 (not 3分の1)
MIN_KO = (r"(?P<n>\d+(?:\.\d+)?)\s*분(?!의\s*\d)"
          r"(?P<h1>\s*반)?(?P<h2>)(?P<under>\s*(?:이내|미만|이하|도 안|이 안))?")  # 약 2분, 1분 반 (digits: 한 분 is a person)
MIN_EN = (r"\b(?P<under>under\s+|less\s+than\s+)?(?P<n>\d+(?:\.\d+)?|a|one|two|three|four|five|six|seven|eight|"
          r"nine|ten)(?P<h1>\s+and\s+a\s+half)?\s+min(?:ute)?s?\b(?P<h2>\s+and\s+a\s+half)?")
MIN_ES = (r"\b(?P<under>menos\s+de\s+)?(?P<n>\d+(?:[.,]\d+)?|una?|uno|dos|tres|cuatro|cinco|seis|siete|ocho|"
          r"nueve|diez)\s+minutos?\b(?P<h1>\s+y\s+medio)?(?P<h2>)")  # unos 2 minutos, un minuto y medio
MIN_FR = (r"(?P<under>\bmoins\s+d['\u2019]\s*)?\b(?P<n>\d+(?:[.,]\d+)?|une?|deux|trois|quatre|cinq|six|sept|"
          r"huit|neuf|dix)\s+minutes?\b(?P<h1>\s+et\s+demie?)?(?P<h2>)")  # environ 2 minutes, moins d'une minute
MIN_DE = (r"\b(?P<under>unter\s+|weniger\s+als\s+)?(?P<n>\d+(?:[.,]\d+)?|anderthalb|einer|eine|ein|zwei|drei|"
          r"vier|fünf|sechs|sieben|acht|neun|zehn)(?P<h1>einhalb)?\s+Minuten?\b(?P<h2>)")  # etwa 2 Minuten, zweieinhalb
MIN_PT = (r"\b(?P<under>menos\s+de\s+)?(?P<n>\d+(?:[.,]\d+)?|uma?|dois|duas|três|quatro|cinco|seis|sete|oito|"
          r"nove|dez)\s+minutos?\b(?P<h1>\s+e\s+meio)?(?P<h2>)")  # cerca de 2 minutos, um minuto e meio


def _words(first: dict, *rest: str) -> dict:
    """Number words: `first` as given, then `rest` from two up."""
    return {**first, **{w: i for i, w in enumerate(rest, 2)}}


NUM_EN = _words({"a": 1, "one": 1}, "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
NUM_ES = _words({"un": 1, "una": 1, "uno": 1}, "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
                "diez")
NUM_FR = _words({"un": 1, "une": 1}, "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix")
NUM_DE = _words({"anderthalb": 1.5, "ein": 1, "eine": 1, "einer": 1}, "zwei", "drei", "vier", "fünf", "sechs",
                "sieben", "acht", "neun", "zehn")
NUM_PT = _words({"um": 1, "uma": 1, "duas": 2}, "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
                "dez")


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
         ui=UI_ZH, film=dict(slow="慢放", freeze="定格"),
         minutes=MIN_ZH),
    Lang("en", "en", "English", "EN", "en-US-AndrewNeural", "en-US-AvaNeural", 960,
         ui=UI_EN, film=dict(slow="Slow motion", freeze="Paused"),
         minutes=MIN_EN, numbers=NUM_EN),
    Lang("ja", "ja", "Japanese", "日本語", "ja-JP-KeitaNeural", "ja-JP-NanamiNeural", 285, cjk=True, sub_chars=30,
         fonts={"win32": "Yu Gothic", "darwin": "Hiragino Sans", "other": "Noto Sans CJK JP"},
         page_font='"Noto Sans JP", "Hiragino Sans", "Yu Gothic", Meiryo, system-ui, sans-serif',
         ui=UI_JA, film=dict(slow="スロー", freeze="一時停止"),
         minutes=MIN_JA),
    Lang("ko", "ko", "Korean", "한국어", "ko-KR-InJoonNeural", "ko-KR-SunHiNeural", 270, cjk=True, sub_chars=34,
         fonts={"win32": "Malgun Gothic", "darwin": "Apple SD Gothic Neo", "other": "Noto Sans CJK KR"},
         page_font='"Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif',
         film=dict(slow="슬로모션", freeze="일시정지"),
         minutes=MIN_KO),
    Lang("es", "es", "Spanish", "ES", "es-ES-AlvaroNeural", "es-ES-ElviraNeural", 850,
         film=dict(slow="Cámara lenta", freeze="Pausa"),
         minutes=MIN_ES, numbers=NUM_ES),
    Lang("fr", "fr", "French", "FR", "fr-FR-HenriNeural", "fr-FR-DeniseNeural", 950,
         film=dict(slow="Ralenti", freeze="Pause"),
         minutes=MIN_FR, numbers=NUM_FR),
    Lang("de", "de", "German", "DE", "de-DE-ConradNeural", "de-DE-KatjaNeural", 950,
         film=dict(slow="Zeitlupe", freeze="Standbild"),
         minutes=MIN_DE, numbers=NUM_DE),
    Lang("pt", "pt-BR", "Portuguese", "PT", "pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", 800,
         film=dict(slow="Câmera lenta", freeze="Pausa"),
         minutes=MIN_PT, numbers=NUM_PT),
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


@cache
def minutes_re(code: str) -> re.Pattern | None:
    """The compiled stated-length pattern of a language (None: it has none, so its length is not checked)."""
    return re.compile(LANGS[code].minutes, re.I) if code in LANGS and LANGS[code].minutes else None


def count(text: str, code: str) -> int:
    """What per_min counts: in a CJK language the characters without punctuation and spaces, else every character."""
    return len(re.findall(r"\w", text)) if cjk(code) else len(text)


def read_s(text: str, code: str) -> float:
    """Seconds the default voice takes to read `text` (an unknown code reads at the English speed)."""
    return count(text, code) / (LANGS.get(code) or LANGS["en"]).per_min * 60
