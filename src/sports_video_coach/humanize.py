"""Stock AI phrasing in the scripts and reports a coach is supposed to have written (the humanize check).

A report, a narration script or a film script that reads like a chatbot loses the team in the first minute. The
writing guides end with a humanize pass (`sports-video-coach guide humanize`); this check flags what that pass
must catch: the not-X-but-Y contrast, written-register connectives ("此外", "moreover"), hype and buzzwords
("至关重要", "game-changer"), summary openers ("总的来说", "in conclusion"), and dashes used as pauses. The driven
run keeps the listen-script and film-script steps (and the report step of a plugin that asks) waiting until the
findings are fixed or kept with `--accept`.

Only what is read or shown is checked: lines starting with `#` are writer's notes; a film script's captions,
freeze labels and paragraphs are checked, its targets (`clip:...`, file names, marks) are not. Languages without a
list here get the dash check only.

usage: sports-video-coach humanize <file or folder ...> [--lang zh]
       A folder checks its README*.md, listen.*.md and film.*.md; the language comes from the file name
       (README.md: zh unless --lang says otherwise). Exit 1 when something is found.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (pattern, what to do instead); patterns are searched per paragraph, so a contrast split over two lines counts
ZH = [
    (r"不是[^。！？\n]{1,24}?[，,]\s*(?:而)?是", "“不是…而是…”的对比句：直接说是什么"),
    (r"不在于?[^。！？\n]{1,16}?[，,]\s*(?:而)?在于?", "“不在…在于…”的对比句：直接说问题在哪"),
    (r"不仅(?:仅)?[^。！？\n]{1,24}?(?:更|而且|还)", "“不仅…更…”：拆成两句，或只留重要的那半"),
    (r"这不(?:仅仅|只)是", "“这不仅仅是…”：直接说是什么"),
    (r"值得(?:注意|一提|关注)的是|需要(?:注意|指出)的是", "铺垫句：删掉，直接说事"),
    (r"总的来说|总而言之|综上所述|简而言之|换句话说|一句话总结|归根结底", "总结套话：教练不这么说，删掉"),
    (r"首先[^。！？]{0,60}其次", "“首先…其次…”：口头上直接说“第一”或者分开讲"),
    (r"至关重要|举足轻重|不可或缺|重中之重|不言而喻|毫无疑问|显而易见", "夸大的书面词：换成具体的事实或数字"),
    (r"让我们|我们一起来|一起来看看", "主持腔：说“看这一球”“停一下”"),
    (r"赋能|助力|彰显|打造|抓手|闭环|底层逻辑|全方位|多维度|深度解析|深入剖析|完美诠释|教科书级", "空话、流行词：换成场上的具体动作"),
    (r"旨在|从而|进而|此外|与此同时|然而|因此[，,]", "书面连接词：口语里说“所以”“还有”“但是”，或者干脆断句"),
    (r"关键在于|核心在于|本质上|真正的(?:问题|关键)", "“关键在于”式拔高：直接说该做的动作"),
    (r"这就是为什么", "“这就是为什么…”的收尾句：删掉，事实已经说清楚了"),
    (r"(?:为什么(?:会这样)?|怎么办|原因呢|结果呢|问题在哪|差别在哪)[？?]", "自问自答：直接说原因"),
]
EN = [
    (r"\bnot (?:just|only|merely) [^.!?\n]{1,40}?,? but\b", "not-just-X-but-Y: say the one thing"),
    (r"\b(?:it|this|that)(?:'s not| is not| isn'?t| was not| wasn'?t) (?:just |only )?(?:about )?[^.!?\n]{1,40}?[,;:—-]+\s*(?:it|this|that)(?:'s| is| was)\b",
     "it's-not-X-it's-Y contrast: say what it is"),
    (r"\b(?:delve|delves|delving|crucial|pivotal|paramount|testament|game-?changer|unlock|elevate|seamless(?:ly)?|"
     r"robust|leverage|showcase|underscore[sd]?|tapestry|landscape|realm|holistic|synergy)\b",
     "buzzword: name the concrete action on the floor"),
    (r"\b(?:moreover|furthermore|additionally|notably|importantly|consequently|thus|hence)\b",
     "written connective: say 'and', 'so', 'but', or start a new sentence"),
    (r"\b(?:in conclusion|in summary|overall,|to sum up|all in all|at the end of the day|the bottom line is)\b",
     "summary opener: cut it"),
    (r"\b(?:it'?s worth noting|it is worth noting|it'?s important to note|make no mistake|here'?s the thing)\b",
     "throat-clearing: cut it, say the fact"),
    (r"\blet'?s (?:dive|delve|break (?:it|this) down|take a (?:closer|deeper) look|unpack)\b",
     "host talk: say 'watch this one' or 'stop here'"),
    (r"\b(?:masterclass|world-class|truly|incredibly|absolutely)\b", "hype: let the clip show it"),
    (r"(?:^|(?<=[.!?] ))(?:why|the result|the answer|the fix|the problem|the difference|what happened)\?",
     "asking yourself and answering: just give the reason"),
]
# spoken paragraphs only (narration, film): a sentence opening with a slide-style label ("练习：", "Goal:")
LABEL_OPEN = re.compile(r"(?:^|(?<=[。！？])|(?<=[.!?] ))([^\s，。！？,.!?：:]{1,8}|[A-Za-z]+(?: [A-Za-z]+)?)[：:]")
LABEL_HINT = {"zh": "开头像幻灯片标签：说成一句话（“练的是…”“下场我们要…”）",
              "en": "a slide label opening a spoken sentence: say it as a sentence"}
LABEL_OK = {"看", "注意", "听", "watch", "now watch", "look", "listen"}  # how a coach really points at the screen
PATTERNS = {"zh": ZH, "en": EN}
DASH_RE = re.compile(r"——|—|\s–\s|\s--\s")
DASH_PER = 400   # more than one dash per this many characters reads as a chatbot's pause
VISUAL_RE = re.compile(r"^!\[(.*)\]\((.+)\)$")
LABEL_RE = re.compile(r'"([^"]*)"|“([^”]*)”')


def spoken_text(text: str) -> list[tuple[str, str]]:
    """What a reader hears or sees, as (kind, text): "para" for a paragraph, "shown" for a caption, a freeze label
    or a `## ` heading. `#` notes are dropped; blank lines split paragraphs."""
    out, para = [], []
    for raw in text.splitlines():
        line = raw.strip()
        m = VISUAL_RE.match(line)
        if not line or line.startswith("#") or m or line.startswith(">"):
            if para:
                out.append(("para", " ".join(para)))
                para = []
            if m and m[1].strip():
                out.append(("shown", m[1].strip()))
            elif line.startswith(">"):
                lm = LABEL_RE.search(line)
                if lm:
                    out.append(("shown", (lm[1] if lm[1] is not None else lm[2]).strip()))
            elif line.startswith("## "):
                out.append(("shown", line[3:].strip()))  # a heading is shown (film chapter card, report section)
            continue
        para.append(line)
    if para:
        out.append(("para", " ".join(para)))
    return [(k, p) for k, p in out if p]


def snippet(text: str, a: int, b: int, pad: int = 8) -> str:
    """The match with a little context, on one line."""
    s = text[max(0, a - pad):min(len(text), b + pad)].replace("\n", " ")
    return ("…" if a > pad else "") + s + ("…" if b + pad < len(text) else "")


def findings(text: str, lang: str, spoken: bool = False) -> list[str]:
    """`"…snippet…": what to do` per stock phrase in the text (a script or report in `lang`), in order; a dash
    count note when dashes are dense. spoken: a script read aloud (narration, film), where a paragraph sentence
    opening with a label ("练习：") is flagged too."""
    out = []
    parts = spoken_text(text)
    for kind, p in parts:
        for pat, hint in PATTERNS.get(lang, []):
            for m in re.finditer(pat, p, flags=re.I):
                out.append(f"\"{snippet(p, m.start(), m.end())}\": {hint}")
        if spoken and kind == "para" and lang in LABEL_HINT:
            for m in LABEL_OPEN.finditer(p):
                if not re.fullmatch(r"[\d\s]+", m[1]) and m[1].lower() not in LABEL_OK:  # 12:05 is no label
                    out.append(f"\"{snippet(p, m.start(1), m.end())}\": {LABEL_HINT[lang]}")
    body = "\n".join(p for _, p in parts)
    dashes = len(DASH_RE.findall(body))
    if dashes and dashes > max(1, len(body) // DASH_PER):
        out.append(f"{dashes} dashes in {len(body)} characters: use a full stop or a comma instead"
                   if lang != "zh" else f"{dashes} 个破折号（{len(body)} 字）：换成句号或逗号")
    return list(dict.fromkeys(out))


def lang_of(path: Path, default: str = "zh") -> str:
    """listen.en.md -> en; README.md -> `default` (the report's first language)."""
    parts = path.name.split(".")
    return parts[-2] if len(parts) >= 3 else default


def file_findings(path: Path, lang: str | None = None) -> list[str]:
    """findings() of one file, each prefixed with the file name (what the run prints and `--accept` records)."""
    if not path.exists():
        return []
    spoken = path.name.startswith(("listen.", "film."))
    return [f"{path.name}: {f}" for f in findings(path.read_text(encoding="utf8"), lang or lang_of(path), spoken)]


def checks(paths: list[Path], langs: list[str] | None = None) -> list[str]:
    """file_findings over several files (a README.md takes the first of `langs`), with a closing hint naming the
    guide; empty when nothing is found."""
    first = (langs or ["zh"])[0]
    found = [f for p in paths for f in file_findings(p, lang_of(p, first))]
    if found:
        found.append("these read as AI-written: do the humanize pass (`sports-video-coach guide humanize`), "
                     "keeping every fact; `--accept` keeps a phrase you mean")
    return found


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="sports-video-coach humanize", description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", help="scripts or reports, or folders (their README*, listen.*, film.*)")
    ap.add_argument("--lang", help="the language of a README.md (default zh; README.<lang>.md says its own)")
    a = ap.parse_args(argv)
    files = []
    for p in map(Path, a.paths):
        files += sorted(f for g in ("README*.md", "listen.*.md", "film.*.md") for f in p.glob(g)) if p.is_dir() else [p]
    total = 0
    for f in files:
        found = file_findings(f, a.lang if a.lang and len(f.name.split(".")) < 3 else None)
        total += len(found)
        for line in found:
            print(line)
    print(f"humanize: {total} finding(s) in {len(files)} file(s)" + ("; see `sports-video-coach guide humanize`"
                                                                     if total else ""))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
