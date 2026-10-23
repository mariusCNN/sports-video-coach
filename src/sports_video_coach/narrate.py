"""Turn a spoken script (plain paragraphs written for the ear) into an MP3, with a pause between paragraphs.

usage:
  sports-video-coach narrate <unit folder> [--lang zh en]
      report narration: listen.zh.md / listen.en.md -> listen.zh.mp3 / listen.en.mp3 in that folder; an mp3
      newer than its script is kept (--force re-renders it), so a rerun after a network error redoes only the rest
  sports-video-coach narrate --script cues.zh.md [--gap 6 --chime --loud --rate -5%]
      any single script -> cues.zh.mp3 next to it (language from the .<lang>.md suffix, else --lang; a
      language with no voice is an error, never another language's voice). --chime plays a short
      two-tone bell before every paragraph and --gap leaves silence after it, which makes a loop you can
      listen to on court; --loud normalises to -14 LUFS so it cuts through gym noise; --tight trims the
      silence the TTS voice leaves around each paragraph, so --gap is the real pause (e.g. --gap 0.4).

Uses edge-tts (Microsoft neural voices, needs internet: the script text is sent to Microsoft's TTS
service) and ffmpeg ($FFMPEG overrides the binary). Lines starting with '#' are notes for the writer and are
not read. Voices: optional `narration.voices` in game.json (folder or its parent), e.g.
  "narration": {"voices": {"en": "en-GB-RyanNeural", "zh": {"voice": "zh-CN-YunxiNeural", "rate": "-5%"}}}
otherwise the defaults in VOICES (one per language in langs.py).
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from . import langs as L
from . import media
from .units import load as load_game
from .media import ffmpeg

VOICES = {c: (l.voice, "+0%") for c, l in L.LANGS.items()}
PAUSE_S = 0.7
MP3 = ["-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "48k"]
TRIES, BACKOFF_S = 3, 2.0  # edge-tts sometimes returns no audio for a moment; a retry usually gets it
# read speed of the default voices (langs.py says how each was found; the narration guide quotes zh and en)
PER_MIN = {c: l.per_min for c, l in L.LANGS.items()}


class TTSFailed(SystemExit):
    """The online voice failed after every retry: exits with one line, not a traceback."""


def paragraphs(text: str) -> list[str]:
    lines = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    return [" ".join(p.split()) for p in "\n".join(lines).split("\n\n") if p.strip()]


def voice_for(lang: str, table: dict | None = None) -> tuple[str, str]:
    """(voice, rate) of a language; a language with no voice stops the run, never reads with another one's voice."""
    table = table or VOICES
    if lang not in table:
        raise L.Unknown(f"no voice for language {lang!r} (known: {', '.join(table)}); add it to langs.py or set "
                        f'"narration": {{"voices": {{"{lang}": "<edge-tts voice>"}}}} in the unit json')
    return table[lang]


def voices(game: dict) -> dict[str, tuple[str, str]]:
    """VOICES overridden by game.json narration.voices ({lang: "voice"} or {lang: {"voice", "rate"}})."""
    out = dict(VOICES)
    for lang, v in ((game.get("narration") or {}).get("voices") or {}).items():
        if lang.startswith("_"):
            continue
        if isinstance(v, str):
            out[lang] = (v, out.get(lang, (v, "+0%"))[1])
        elif isinstance(v, dict) and v.get("voice"):
            out[lang] = (v["voice"], v.get("rate", "+0%"))
    return out


async def speak(paras: list[str], voice: str, rate: str, tmp: Path) -> list[Path]:
    import edge_tts

    parts = []
    for i, p in enumerate(paras):
        out = tmp / f"p{i:03d}.mp3"
        for n in range(1, TRIES + 1):
            try:
                await edge_tts.Communicate(p, voice, rate=rate).save(str(out))
                break
            except (edge_tts.exceptions.EdgeTTSException, OSError, asyncio.TimeoutError) as e:  # aiohttp: OSError
                if n == TRIES:
                    raise TTSFailed(f"text-to-speech (edge-tts, online) failed: {type(e).__name__}: {e}; "
                                    "check the network and run again") from None
                print(f"[narrate] edge-tts {type(e).__name__}, retry {n}/{TRIES - 1}", flush=True)
                await asyncio.sleep(BACKOFF_S * n)
        parts.append(out)
    return parts


_ZH_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _len_match(paras: list[str], lang: str) -> re.Match | None:
    pattern = L.minutes_re(lang if lang in L.LANGS else "en")  # the registry's; an unknown code reads like English
    return pattern.search(" ".join(paras)) if pattern else None


def stated_sentence(paras: list[str], lang: str) -> str:
    """The sentence that states the length ('' when none), as the writer has to find it."""
    m = _len_match(paras, lang)
    if not m:
        return ""
    text = " ".join(paras)
    ends = re.compile(r"[.!?。！？]")
    start = max((e.end() for e in ends.finditer(text, 0, m.start())), default=0)
    end = next((e.end() for e in ends.finditer(text, m.end())), len(text))
    return text[start:end].strip()


def stated(paras: list[str], lang: str) -> tuple[float, bool] | None:
    """The length the script says it runs ("约 2 分钟", "一分半", "約一分", "약 2분", "about three minutes"; the
    pattern is the language's `minutes` in the registry) in seconds, and whether it
    is only an upper bound ("不到一分钟", "under a minute"); None when it names none. The first mention counts:
    the opening "this runs about N minutes"."""
    m = _len_match(paras, lang)
    if not m:
        return None
    w, words = m["n"].lower(), (L.LANGS.get(lang) or L.LANGS["en"]).numbers
    if w[0].isdigit():
        n = float(w.replace(",", "."))  # 1,5 minutos
    elif w in words:
        n = words[w]
    else:  # 三, 十二, 二十, 二十五
        tens, _, ones = w.rpartition("十") if "十" in w else ("", "", w)
        n = (_ZH_NUM.get(tens, 1) * 10 if "十" in w else 0) + _ZH_NUM.get(ones, 0)
    return (n + (0.5 if m["h1"] or m["h2"] else 0)) * 60, bool(m["under"])  # 一分半, two and a half minutes


def count(paras: list[str], lang: str) -> int:
    """What PER_MIN counts: Chinese / Japanese / Korean characters without punctuation, else every character."""
    return sum(L.count(p, lang) for p in paras)


def estimate_s(paras: list[str], lang: str) -> float:
    """Read time at the measured speed (PER_MIN), plus the pauses between paragraphs."""
    return count(paras, lang) / PER_MIN.get(lang, PER_MIN["en"]) * 60 + PAUSE_S * max(0, len(paras) - 1)


def size_text(paras: list[str], lang: str) -> str:
    """One line for the writer: paragraphs, words / characters and the estimated read time."""
    words = "" if L.cjk(lang) else f"{sum(len(p.split()) for p in paras)} words, "
    what = "characters without punctuation" if L.cjk(lang) else "characters"
    return (f"{len(paras)} paragraphs, {words}{count(paras, lang)} {what}, "
            f"reads in about {estimate_s(paras, lang):.0f} s")


def check_length(paras: list[str], lang: str) -> str | None:
    """A warning when the stated length is off the estimated read time by more than 30 s, or a quarter of a short
    length ("一分钟" for 78 s), else None."""
    if not (s := stated(paras, lang)):
        return None
    (said, under), est = s, estimate_s(paras, lang)
    if abs(est - said) <= min(30, said / 4) or under and est <= said:  # "under a minute" fits any shorter length
        return None
    return (f"[narrate] warning: the {lang} script says {'under' if under else 'about'} {said / 60:g} min but reads in about {est:.0f} s; "
            "fix that sentence (the real length prints when the mp3 is written)")


def length_problem(script: Path, lang: str) -> str | None:
    """check_length of a listen.<lang>.md, naming the sentence to fix (the driven run waits on it before rendering)."""
    paras = paragraphs(script.read_text(encoding="utf8"))
    if not check_length(paras, lang):
        return None
    (said, under), est = stated(paras, lang), estimate_s(paras, lang)
    return (f"{script.name} says {'under' if under else 'about'} {said / 60:g} min but reads in about {est:.0f} s: "
            f"fix the sentence \"{stated_sentence(paras, lang)}\"")


def silence(seconds: float, out: Path) -> Path:
    ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(seconds), *MP3, str(out))
    return out


def chime(out: Path) -> Path:
    """Two soft rising tones (A5 -> E6), then a short breath before the voice."""
    ffmpeg("-filter_complex",
           "sine=f=880:d=0.14,afade=t=in:d=0.01,afade=t=out:st=0.09:d=0.05[a];"
           "sine=f=1319:d=0.45,afade=t=in:d=0.01,afade=t=out:st=0.05:d=0.4[b];"
           "[a][b]concat=n=2:v=0:a=1,volume=0.35,apad=pad_dur=0.35",
           *MP3, str(out))
    return out


def trim(part: Path) -> Path:
    """Cut the lead-in and tail silence edge-tts puts around every paragraph (about half a second each)."""
    out = part.with_name(part.stem + ".trim.mp3")
    edge = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05"
    ffmpeg("-i", str(part), "-af", f"{edge},areverse,{edge},areverse", *MP3, str(out))
    return out


def stitch(parts: list[Path], out: Path, tmp: Path, gap: float = PAUSE_S, bell: bool = False, loud: bool = False,
           tight: bool = False):
    if tight:
        parts = [trim(p) for p in parts]
    pause = silence(gap, tmp / "pause.mp3")
    ding = chime(tmp / "chime.mp3") if bell else None
    seq = []
    for p in parts:
        seq += ([ding] if ding else []) + [p, pause]
    if not bell:
        seq = seq[:-1]  # a narration ends on the last word; a cue loop keeps its gap so the repeat breathes
    listing = tmp / "list.txt"
    quote = lambda p: p.as_posix().replace("'", "'\\''")  # ffmpeg concat syntax: ' ends the quote, \' is a quote
    listing.write_text("".join(f"file '{quote(p)}'\n" for p in seq), encoding="utf8")
    norm = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=7"] if loud else []
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), *norm, *MP3, str(out))


def render(src: Path, out: Path, lang: str, gap: float, bell: bool, loud: bool, rate: str | None,
           voice_table: dict | None = None, tight: bool = False):
    paras = paragraphs(src.read_text(encoding="utf8"))
    voice, default_rate = voice_for(lang, voice_table)
    if warn := check_length(paras, lang):
        print(warn, flush=True)
    print(f"[narrate] {lang}: {size_text(paras, lang)}; rendering with {voice} (edge-tts, online)...", flush=True)
    with media.scratch(out) as t:
        tmp = Path(t)
        parts = asyncio.run(speak(paras, voice, rate or default_rate, tmp))
        with media.partial(out) as part:  # a stopped run never leaves a short listen.<lang>.mp3 that counts as done
            stitch(parts, part, tmp, gap, bell, loud, tight)
    # the length, so the script's "about N minutes" can be checked without ffprobe
    print("wrote", out, f"{out.stat().st_size / 1e6:.1f} MB,", len(paras), "paragraphs,",
          f"{media.duration_s(out):.0f} s")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", help="report folder with listen.<lang>.md")
    ap.add_argument("--lang", nargs="+", choices=list(VOICES),
                    help="languages to render (default: every listen.<lang>.md in the folder)")
    ap.add_argument("--script", type=Path, help="a single script file instead of a report folder")
    ap.add_argument("--out", type=Path, help="output mp3 for --script (default: next to it)")
    ap.add_argument("--gap", type=float, default=PAUSE_S, help="seconds of silence after each paragraph")
    ap.add_argument("--chime", action="store_true", help="short bell before each paragraph")
    ap.add_argument("--loud", action="store_true", help="normalise loudness to -14 LUFS")
    ap.add_argument("--rate", help='speaking rate, e.g. "-5%%"')
    ap.add_argument("--tight", action="store_true", help="trim TTS silence around each paragraph so --gap is exact")
    ap.add_argument("--force", action="store_true", help="re-render a language whose mp3 is newer than its script")
    a = ap.parse_args(argv)
    if a.script:
        vt = voices(load_game(a.script.parent))
        lang = next((c for c in vt if a.script.name.endswith(f".{c}.md")), None) or (a.lang or [None])[0]
        if lang is None:  # never read a script with another language's voice
            parts = a.script.name.split(".")
            sys.exit(f"{a.script.name}: " + (f"no voice for language {parts[-2]!r}" if len(parts) > 2 else
                                             "no .<lang>.md suffix") +
                     f" (known: {', '.join(vt)}); name the file <name>.<lang>.md or pass --lang")
        render(a.script, a.out or a.script.with_suffix(".mp3"), lang, a.gap, a.chime, a.loud, a.rate, vt, a.tight)
        return
    if not a.folder:
        ap.error("give a report folder or --script")
    folder = Path(a.folder)
    vt = voices(load_game(folder))
    langs = a.lang or [c for c in VOICES if (folder / f"listen.{c}.md").exists()]
    if not langs:
        sys.exit(f"{folder} has no listen.<lang>.md ({', '.join(VOICES)})")
    for lang in langs:
        src, out = folder / f"listen.{lang}.md", folder / f"listen.{lang}.mp3"
        if not a.force and up_to_date(out, src):  # a rerun after a failure redoes only the stale language
            print(f"[narrate] {lang}: {out.name} is newer than {src.name}, kept (--force re-renders)")
            continue
        render(src, out, lang, a.gap, a.chime, a.loud, a.rate, vt, a.tight)


def up_to_date(out: Path, src: Path, slack: float = 2.0) -> bool:
    """out exists and src did not change after it (the driver's test for the narrate step)."""
    return out.exists() and src.exists() and src.stat().st_mtime <= out.stat().st_mtime + slack


if __name__ == "__main__":
    main()
