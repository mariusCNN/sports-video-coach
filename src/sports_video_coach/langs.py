"""The language registry: every report language the core knows, in one table (LANGS).

A language is its code (the file suffix: README.ja.md, listen.ja.md, film.ja.md; `--lang ja`), its BCP 47 tag for
the page, the edge-tts voice that reads it, how its text is counted and wrapped (CJK: no spaces between words), its
read speed for length estimates, the subtitle font per platform, the page's labels, how it writes a date and the
names of common sports.
README.md is the Chinese report, README.<code>.md every other language. Every language has its own page labels; a
code outside the table shows the English ones.

Add a language: one `Lang(...)` in LANGS (docs/architecture.md says what each field does).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from functools import cache

# subtitle fonts: a Latin-script face per platform for en, es, fr, de, pt (and unknown codes); Chinese keeps the
# CJK face it had since the first release; ja / ko set their own
DEFAULT_FONTS = {"win32": "Segoe UI", "darwin": "Helvetica Neue", "other": "DejaVu Sans"}
CJK_SC_FONTS = {"win32": "Microsoft YaHei", "darwin": "PingFang SC", "other": "Noto Sans CJK SC"}


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
    date: str = "{y}-{mm}-{dd}"  # a date as the reader writes it: {d} {m} day / month, {dd} {mm} zero-padded, {mon}
    months: tuple = ()     # {mon}: the short month names, January first
    sports: dict = field(default_factory=dict)  # common sport names {English name: own name} (missing: English)


# stated lengths: the number (digits, a number word, kanji), the minute word, a half before or after it, and an
# upper bound ("under a minute"). Every pattern has the groups n, h1, h2 and under.
_KANJI = "[一两二三四五六七八九十]{1,3}"
MIN_ZH = rf"(?P<under>不到|少于)?\s*(?P<n>\d+(?:\.\d+)?|{_KANJI})\s*分(?:(?P<h1>半)钟?|钟(?P<h2>半)?)"  # not 三分球
MIN_JA = (rf"(?P<n>\d+(?:\.\d+)?|{_KANJI})\s*分(?!の[\d一二三四五六七八九十])間?(?P<h1>半)?(?P<h2>)"
          r"(?P<under>以内|未満|弱)?")  # 約2分, 約一分, 1分半, 1分以内 (not 3分の1)
# Korean: digits; Sino-Korean words (이 분, 십오 분) after 약 or before 정도 / 쯤 / 반; native words (두 분, 열 분)
# only before those: 한 분 / 세 분 alone are people, 이 분 alone is "this person"
_KO_SINO = "[이삼사오육칠팔구]?십[일이삼사오육칠팔구]?|[일이삼사오육칠팔구]"
_KO_NATIVE = "열(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉)?|한|두|세|네|다섯|여섯|일곱|여덟|아홉"
_KO_TAIL = r"(?=\s*(?:정도|쯤|가량|남짓|이내|미만|이하|동안))"
MIN_KO = (rf"(?P<pre>(?<![가-힣])약\s*)?(?P<n>\d+(?:\.\d+)?|(?:(?<![가-힣])|(?<=약))(?:(?P<sino>{_KO_SINO})|"
          rf"(?P<native>{_KO_NATIVE})))\s*분(?!의\s*\d)(?![석야류리배해할명위])(?P<h1>\s*반)?(?P<h2>)"
          rf"(?(native)(?(h1)|{_KO_TAIL})|(?(sino)(?(pre)|(?(h1)|{_KO_TAIL}))))"
          r"(?P<under>\s*(?:이내|미만|이하|도 안|이 안))?")  # 약 2분, 1분 반, 약 이 분, 일 분 반, 오 분 정도
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
_KO_ONES = "일이삼사오육칠팔구"
_KO_NATIVE_ONES = ("한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉")
NUM_KO = {**{w: i for i, w in enumerate(_KO_ONES, 1)},  # 일 .. 구, 십 .. 구십구
          **{(_KO_ONES[t - 1] if t > 1 else "") + "십" + (_KO_ONES[o - 1] if o else ""): t * 10 + o
             for t in range(1, 10) for o in range(10)},
          **{w: i for i, w in enumerate(_KO_NATIVE_ONES, 1)}, "열": 10,  # 한 .. 아홉, 열, 열한 .. 열아홉
          **{"열" + w: 10 + i for i, w in enumerate(_KO_NATIVE_ONES, 1)}}


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
UI_KO = dict(contents="목차", switch="언어 바꾸기", reports="리포트",
             listen="리포트 듣기", listen_sub="약 {m}분. 읽으면서 들어도, 듣기만 해도 됩니다",
             listen_sub_s="약 {s}초. 읽으면서 들어도, 듣기만 해도 됩니다", play="재생 / 일시정지", seek="재생 위치",
             speed="재생 속도", clip="클립", slow="슬로", missing="(클립이 아직 없습니다: clips 단계를 실행하세요)")
UI_ES = dict(contents="Índice", switch="Cambiar idioma", reports="Informes",
             listen="Escucha el informe", listen_sub="Unos {m} min. Léelo mientras escuchas o solo escucha.",
             listen_sub_s="Unos {s} segundos. Léelo mientras escuchas o solo escucha.", play="Reproducir / pausa",
             seek="Posición de reproducción", speed="Velocidad de reproducción",
             clip="Clip", slow="Cámara lenta", missing="(clip aún sin cortar: ejecuta la etapa clips)")
UI_FR = dict(contents="Sommaire", switch="Changer de langue", reports="Rapports",
             listen="Écouter le rapport", listen_sub="Environ {m} min. Lisez en écoutant, ou écoutez simplement.",
             listen_sub_s="Environ {s} secondes. Lisez en écoutant, ou écoutez simplement.", play="Lecture / pause",
             seek="Position de lecture", speed="Vitesse de lecture",
             clip="Extrait", slow="Ralenti", missing="(extrait pas encore découpé : lancez l’étape clips)")
UI_DE = dict(contents="Inhalt", switch="Sprache wechseln", reports="Berichte",
             listen="Bericht anhören", listen_sub="Etwa {m} Min. Mitlesen oder einfach zuhören.",
             listen_sub_s="Etwa {s} Sekunden. Mitlesen oder einfach zuhören.", play="Abspielen / Pause",
             seek="Wiedergabeposition", speed="Wiedergabetempo",
             clip="Clip", slow="Zeitlupe", missing="(Clip noch nicht geschnitten: Schritt clips ausführen)")
UI_PT = dict(contents="Sumário", switch="Mudar idioma", reports="Relatórios",
             listen="Ouça o relatório", listen_sub="Cerca de {m} min. Leia junto ou só ouça.",
             listen_sub_s="Cerca de {s} segundos. Leia junto ou só ouça.", play="Reproduzir / pausar",
             seek="Posição da reprodução", speed="Velocidade de reprodução",
             clip="Clipe", slow="Câmera lenta", missing="(clipe ainda não cortado: rode a etapa clips)")

# Common sport names per language, keyed by the English name (SPORTS_EN), so a page header in that language does
# not show "volleyball"; `--sport-name LANG=NAME` (analysis.json `"sport": {lang: name}`) names any other sport.
SPORTS_EN = ("tennis", "basketball", "football", "soccer", "badminton", "table tennis", "volleyball", "swimming",
             "running", "golf", "baseball", "boxing", "climbing", "cycling", "skiing", "skateboarding",
             "martial arts", "gymnastics", "yoga", "weightlifting", "fitness", "dance", "pickleball", "squash",
             "rugby", "hockey", "ice hockey", "cricket", "athletics")


def _sports(*names: str) -> dict:
    """{English name: own name}, the names in SPORTS_EN order."""
    assert len(names) == len(SPORTS_EN), len(names)
    return dict(zip(SPORTS_EN, names))


SPORT_ZH = _sports("网球", "篮球", "足球", "足球", "羽毛球", "乒乓球", "排球", "游泳", "跑步", "高尔夫", "棒球", "拳击", "攀岩",
                   "骑行", "滑雪", "滑板", "武术", "体操", "瑜伽", "举重", "健身", "舞蹈", "匹克球", "壁球", "橄榄球", "曲棍球",
                   "冰球", "板球", "田径")
SPORT_JA = _sports("テニス", "バスケットボール", "サッカー", "サッカー", "バドミントン", "卓球", "バレーボール", "水泳", "ランニング",
                   "ゴルフ", "野球", "ボクシング", "クライミング", "自転車", "スキー", "スケートボード", "武道", "体操", "ヨガ",
                   "ウエイトリフティング", "フィットネス", "ダンス", "ピックルボール", "スカッシュ", "ラグビー", "ホッケー",
                   "アイスホッケー", "クリケット", "陸上競技")
SPORT_KO = _sports("테니스", "농구", "축구", "축구", "배드민턴", "탁구", "배구", "수영", "달리기", "골프", "야구", "복싱", "클라이밍",
                   "사이클", "스키", "스케이트보드", "무술", "체조", "요가", "역도", "피트니스", "댄스", "피클볼", "스쿼시", "럭비",
                   "하키", "아이스하키", "크리켓", "육상")
SPORT_ES = _sports("Tenis", "Baloncesto", "Fútbol", "Fútbol", "Bádminton", "Tenis de mesa", "Voleibol", "Natación",
                   "Carrera a pie", "Golf", "Béisbol", "Boxeo", "Escalada", "Ciclismo", "Esquí", "Skateboarding",
                   "Artes marciales", "Gimnasia", "Yoga", "Halterofilia", "Fitness", "Baile", "Pickleball", "Squash",
                   "Rugby", "Hockey", "Hockey sobre hielo", "Críquet", "Atletismo")
SPORT_FR = _sports("Tennis", "Basket-ball", "Football", "Football", "Badminton", "Tennis de table", "Volley-ball",
                   "Natation", "Course à pied", "Golf", "Baseball", "Boxe", "Escalade", "Cyclisme", "Ski", "Skateboard",
                   "Arts martiaux", "Gymnastique", "Yoga", "Haltérophilie", "Fitness", "Danse", "Pickleball", "Squash",
                   "Rugby", "Hockey", "Hockey sur glace", "Cricket", "Athlétisme")
SPORT_DE = _sports("Tennis", "Basketball", "Fußball", "Fußball", "Badminton", "Tischtennis", "Volleyball", "Schwimmen",
                   "Laufen", "Golf", "Baseball", "Boxen", "Klettern", "Radfahren", "Skifahren", "Skateboarden",
                   "Kampfkunst", "Turnen", "Yoga", "Gewichtheben", "Fitness", "Tanz", "Pickleball", "Squash", "Rugby",
                   "Hockey", "Eishockey", "Cricket", "Leichtathletik")
SPORT_PT = _sports("Tênis", "Basquete", "Futebol", "Futebol", "Badminton", "Tênis de mesa", "Vôlei", "Natação",
                   "Corrida", "Golfe", "Beisebol", "Boxe", "Escalada", "Ciclismo", "Esqui", "Skate", "Artes marciais",
                   "Ginástica", "Ioga", "Levantamento de peso", "Fitness", "Dança", "Pickleball", "Squash", "Rúgbi",
                   "Hóquei", "Hóquei no gelo", "Críquete", "Atletismo")

# per_min: zh and en measured on rendered report scripts (zh: Chinese characters without punctuation, en: characters
# with spaces; English words a minute range 130-190 with word length). The others come from one ~25 s sample
# paragraph per default voice (2026-10-23), not from full scripts: treat them as rough until measured (ja 285: an 84 s
# report script; ko 245: a 442-character report script that read in 112 s).
LANGS: dict[str, Lang] = {l.code: l for l in (
    Lang("zh", "zh-CN", "Chinese", "中文", "zh-CN-YunjianNeural", "zh-CN-XiaoxiaoNeural", 235, cjk=True, sub_chars=30,
         fonts=CJK_SC_FONTS, ui=UI_ZH, film=dict(slow="慢放", freeze="定格"), date="{y}年{m}月{d}日",
         minutes=MIN_ZH, sports=SPORT_ZH),
    Lang("en", "en", "English", "EN", "en-US-AndrewNeural", "en-US-AvaNeural", 960,
         ui=UI_EN, film=dict(slow="Slow motion", freeze="Paused"), date="{d} {mon} {y}",
         months=("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
         minutes=MIN_EN, numbers=NUM_EN),
    Lang("ja", "ja", "Japanese", "日本語", "ja-JP-KeitaNeural", "ja-JP-NanamiNeural", 285, cjk=True, sub_chars=30,
         fonts={"win32": "Yu Gothic", "darwin": "Hiragino Sans", "other": "Noto Sans CJK JP"},
         page_font='"Noto Sans JP", "Hiragino Sans", "Yu Gothic", Meiryo, system-ui, sans-serif',
         ui=UI_JA, film=dict(slow="スロー", freeze="一時停止"), date="{y}年{m}月{d}日",
         minutes=MIN_JA, sports=SPORT_JA),
    Lang("ko", "ko", "Korean", "한국어", "ko-KR-InJoonNeural", "ko-KR-SunHiNeural", 245, cjk=True, sub_chars=34,
         fonts={"win32": "Malgun Gothic", "darwin": "Apple SD Gothic Neo", "other": "Noto Sans CJK KR"},
         page_font='"Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif',
         ui=UI_KO, film=dict(slow="슬로모션", freeze="일시정지"), date="{y}년 {m}월 {d}일",
         minutes=MIN_KO, numbers=NUM_KO, sports=SPORT_KO),
    Lang("es", "es", "Spanish", "ES", "es-ES-AlvaroNeural", "es-ES-ElviraNeural", 850,
         ui=UI_ES, film=dict(slow="Cámara lenta", freeze="Pausa"), date="{d} {mon} {y}",
         months=("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"),
         minutes=MIN_ES, numbers=NUM_ES, sports=SPORT_ES),
    Lang("fr", "fr", "French", "FR", "fr-FR-HenriNeural", "fr-FR-DeniseNeural", 950,
         ui=UI_FR, film=dict(slow="Ralenti", freeze="Pause"), date="{d} {mon} {y}",
         months=("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."),
         minutes=MIN_FR, numbers=NUM_FR, sports=SPORT_FR),
    Lang("de", "de", "German", "DE", "de-DE-ConradNeural", "de-DE-KatjaNeural", 950,
         ui=UI_DE, film=dict(slow="Zeitlupe", freeze="Standbild"), date="{dd}.{mm}.{y}",
         minutes=MIN_DE, numbers=NUM_DE, sports=SPORT_DE),
    Lang("pt", "pt-BR", "Portuguese", "PT", "pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", 800,
         ui=UI_PT, film=dict(slow="Câmera lenta", freeze="Pausa"), date="{dd}/{mm}/{y}",
         minutes=MIN_PT, numbers=NUM_PT, sports=SPORT_PT),
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


def date(iso: str, code: str) -> str:
    """An ISO date ("2026-10-23") as the language writes it ("23 oct 2026", "2026年10月23日"); anything else (a
    folder name, an unknown code) as it is. For display only: file names and json keep ISO dates."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso).strip())
    if not m or code not in LANGS or not 1 <= int(m[2]) <= 12:
        return str(iso)
    y, mm, dd = m.groups()
    months = LANGS[code].months or LANGS["en"].months
    return LANGS[code].date.format(y=y, mm=mm, dd=dd, m=int(mm), d=int(dd), mon=months[int(mm) - 1])


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
