"""The effort chart: what changing only the reasoning effort did, as a 1200x675 PNG for posts (X, dev.to) and the
benchmark page's "What effort changed" section. It reads the fresh-seed frames runs of svc-bench-3 from the result
files (nothing typed by hand), groups them by contender (agent + model) and effort setting (the `effort LEVEL` its
settings name, else the CLI's default), and keeps the contenders run at two or more settings. Each bar is the mean
above-chance score of that setting's runs, each run against the blind guess on its own seed (`page.above_value`),
labelled with n, the range when n > 1 and the mean time per run; a run that gave no answer at all is shown as
such (and as timed out when it ran to the default time limit). `effort_data` is the data step (tested); `draw`
needs matplotlib, like the share card: without it `bench page` writes no image and the section is text only.
`effort.png` is English, `effort-zh.png` Chinese (only when a CJK font is installed; else the Chinese page shows
the English image).
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

NAMES = {"en": "effort.png", "zh": "effort-zh.png"}
SIZE = (1200, 675)
SUITE = "svc-bench-3"
TRACK = "frames"
DEFAULT = "default"
ORDER = (DEFAULT, "minimal", "low", "medium", "high", "xhigh", "max")   # bar order within a contender
TIMEOUT = 1200      # `bench run --timeout` default (s): a run with no answer that ran this long was killed by it
CJK_FONTS = ("Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", "Source Han Sans SC", "SimHei")
ANCHOR = "effort"
NOTE_WIDTH = 36  # characters per note line at fontsize 15

TITLE = "Same model, different effort: score on unseen seeds"
SUB = "{} fresh seeds · frames track (stills only, no code) · {}"
FLOOR = "Mean above chance: 0 = the blind guess on the same seed (no video), 1 = perfect. n = runs per bar."
LEAD = ("Same model, same kind of task (svc-bench-3 drawn from a new seed for every run, reviewed by eye from "
        "stills); only the effort setting changed. Mean score above chance:")
BOUND = ("One run per setting unless n says otherwise, each on its own seed: a measured difference, not a variance "
         "estimate. Default = no effort flag (the CLI's own default). Every run is a row in the board below.")
ALT = "Bar chart of mean score above chance by effort setting. {}"


def effort_of(settings: str) -> str:
    """The effort a run's settings name (`effort high`, `reasoning effort xhigh`), else DEFAULT."""
    found = re.findall(r"\beffort ([a-z]+)\b", settings or "")
    return found[-1] if found else DEFAULT


def model_label(model: str, agent: str) -> str:
    """`claude-sonnet-5-5` -> `Sonnet 5.5`; any other model as it is; no model -> the agent."""
    m = re.fullmatch(r"claude-([a-z]+)-(\d+)-(\d+)", model or "")
    return f"{m[1].capitalize()} {m[2]}.{m[3]}" if m else (model or agent)


def no_answer(r: dict) -> bool:
    return all(t.get("answer") is None for t in r["tasks"])


def effort_data(rows: list[dict]) -> dict:
    """What the chart and the page section show: {"suite", "date", "groups": [{"agent", "model", "label", "bars":
    [{"effort", "n", "above", "lo", "hi", "secs", "files", "no_answer", "timed_out", "limits"}]}]}; "limits": the
    time limits the timed-out runs hit, each its wall time rounded down to whole 100 s, sorted, no repeats. Groups (contenders with
    two or more effort settings) ordered by agent and model; bars in ORDER."""
    from . import page as P
    runs = [r for r in rows if not P.is_baseline(r) and r.get("seed") is not None
            and str(r.get("suite") or P.SUITE) == SUITE and P.track_of(r) == TRACK]
    by: dict[tuple[str, str], dict[str, list[dict]]] = {}
    for r in runs:
        c = r["contender"]
        key = (str(c.get("agent") or ""), str(c.get("model") or ""))
        by.setdefault(key, {}).setdefault(effort_of(str(c.get("settings") or "")), []).append(r)
    rank = {e: i for i, e in enumerate(ORDER)}
    groups, used = [], []
    for (agent, model), efforts in sorted(by.items()):
        if len(efforts) < 2:
            continue
        bars = []
        for e in sorted(efforts, key=lambda e: (rank.get(e, len(ORDER)), e)):
            mine = sorted(efforts[e], key=lambda r: r["_file"])
            vals = [v for v in (P.above_value(r, None) for r in mine) if v is not None]
            secs, _ = P.mean_of(mine, "wall_seconds")
            silent = [r for r in mine if no_answer(r)]
            killed = [float(r["wall_seconds"]) for r in silent if P.is_num_value(r.get("wall_seconds"))
                      and float(r["wall_seconds"]) >= TIMEOUT]
            bars.append({"effort": e, "n": len(mine), "files": [r["_file"] for r in mine],
                         "above": round(sum(vals) / len(vals), 3) if vals else None,
                         "lo": round(min(vals), 3) if vals else None, "hi": round(max(vals), 3) if vals else None,
                         "secs": secs, "no_answer": len(silent),
                         "timed_out": len(killed), "limits": sorted({int(w // 100 * 100) for w in killed})})
            used += mine
        groups.append({"agent": agent, "model": model, "label": model_label(model, agent), "bars": bars})
    dates = [str(r.get("date")) for r in used if r.get("date")]
    return {"suite": SUITE, "date": max(dates) if dates else "", "groups": groups}


def setting(e: str, lang: str = "en") -> str:
    from .page import t
    return t("default effort", lang) if e == DEFAULT else t("effort {}", lang).format(e)


def limits_word(b: dict, lang: str = "en") -> str:
    """The time limits a bar's timed-out runs hit, e.g. "1200 s and 2400 s"."""
    from .page import t
    each = [f"{x} s" for x in b["limits"]]
    return each[0] if len(each) == 1 else t(", ", lang).join(each[:-1]) + t(" and ", lang) + each[-1]


def runs_word(n: int, lang: str = "en") -> str:
    from .page import t
    return t("1 run", lang) if n == 1 else t("{} runs", lang).format(n)


def phrase(b: dict, lang: str = "en") -> str:
    """One bar as words, e.g. "effort high: 0.994 (1 run, 256 s)"."""
    from .page import t
    s, runs = setting(b["effort"], lang), runs_word(b["n"], lang)
    if b["n"] == b["no_answer"]:
        if b["timed_out"] == b["n"]:
            return t("{}: no answer, killed at the time limit ({}), scored 0 ({})", lang).format(
                s, limits_word(b, lang), runs)
        return t("{}: no answer, scored 0 ({})", lang).format(s, runs)
    secs = f"{b['secs']:.0f}" if b["secs"] is not None else "-"
    silent = t("; {} gave no answer", lang).format(b["no_answer"]) if b["no_answer"] else ""
    if b["n"] == 1:
        return t("{}: {} ({}, {} s)", lang).format(s, f"{b['above']:.3f}", runs, secs)
    return t("{}: {} mean, range {}–{} ({}, {} s per run{})", lang).format(
        s, f"{b['above']:.3f}", f"{b['lo']:.3f}", f"{b['hi']:.3f}", runs, secs, silent)


def lines(data: dict, lang: str = "en") -> list[str]:
    """One line per contender: its label, then every setting's phrase."""
    from .page import t
    return [f"{g['label']} · {g['agent']}{t(': ', lang)}" + t("; ", lang).join(phrase(b, lang) for b in g["bars"])
            for g in data["groups"]]


def bar_note(b: dict, lang: str) -> str:
    """The small text right of a bar: n, the range when n > 1, runs with no answer, the time per run, or why it
    scored 0."""
    from .page import t
    if b["n"] == b["no_answer"]:
        why = (t("no answer, timed out at {}", lang).format(limits_word(b, lang)) if b["timed_out"] == b["n"]
               else t("no answer", lang))
        return f"n={b['n']} · {why}"
    parts = [f"n={b['n']}"]
    if b["n"] > 1:
        parts.append(f"{b['lo']:.3f}–{b['hi']:.3f}")
    if b["no_answer"]:
        parts.append(t("{} no answer", lang).format(b["no_answer"]))
    if b["secs"] is not None:
        parts.append(t("{} s/run", lang).format(f"{b['secs']:.0f}"))
    return " · ".join(parts)


def cjk_font() -> str | None:
    """The first installed CJK font matplotlib can use, or None."""
    from matplotlib import font_manager
    for name in CJK_FONTS:
        try:
            font_manager.findfont(name, fallback_to_default=False)
            return name
        except ValueError:
            continue
    return None


def draw(data: dict, path: Path, lang: str = "en", font: str | None = None) -> Path:
    """Write the chart for `effort_data` output to `path` (PNG, SIZE pixels); `font` for the Chinese text."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .page import URLS, t

    ink, muted, bg, bar, track, warn = "#1d1b38", "#5c5a86", "#f6f5fb", "#3b36a8", "#e2e0ef", "#a3332b"
    w, h = SIZE
    rc = {"font.family": "sans-serif", "font.sans-serif": ([font] if font else []) + ["DejaVu Sans"]}
    with plt.rc_context(rc):
        fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=bg)
        fig.text(0.04, 0.925, t(TITLE, lang), fontsize=26, fontweight="bold", color=ink, va="center")
        fig.text(0.04, 0.855, t(SUB, lang).format(data["suite"], data["date"]), fontsize=17, color=muted,
                 va="center")
        groups = data["groups"]
        if not groups:
            fig.text(0.04, 0.5, t("No contender ran at two effort settings yet.", lang), fontsize=26, color=ink)
        rows = sum(1 + len(g["bars"]) for g in groups)
        top, bottom = 0.77, 0.14
        step = min(0.085, (top - bottom) / max(rows, 1))
        y = top
        x_bar, w_bar = 0.22, 0.3
        for g in groups:
            fig.text(0.04, y, f"{g['label']} · {g['agent']}", fontsize=21, fontweight="bold", color=ink,
                     va="center")
            y -= step
            for b in g["bars"]:
                fig.text(0.06, y, setting(b["effort"], lang), fontsize=19, color=ink, va="center")
                ax = fig.add_axes((x_bar, y - step * 0.28, w_bar, step * 0.56))
                ax.set_xlim(0, 1)
                ax.barh([0], [1], color=track, height=1)
                ax.barh([0], [b["above"] or 0], color=bar, height=1)
                ax.axis("off")
                failed = b["n"] == b["no_answer"]
                value = "0" if failed else f"{b['above']:.3f}" if b["above"] is not None else "-"
                fig.text(x_bar + w_bar + 0.015, y, value, fontsize=21, fontweight="bold",
                         color=warn if failed else ink, va="center")
                # A long note (two time limits) wraps rather than running off the right edge.
                note = "\n".join(textwrap.wrap(bar_note(b, lang), NOTE_WIDTH))
                fig.text(x_bar + w_bar + 0.105, y, note, fontsize=15, color=warn if failed else muted,
                         va="center")
                y -= step
        fig.text(0.04, 0.075, t(FLOOR, lang), fontsize=14, color=muted, va="center")
        fig.text(0.04, 0.03, URLS[lang] + "#" + ANCHOR, fontsize=13, color=muted, va="center")
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=100, facecolor=bg)
        plt.close(fig)
    return path


def write(rows: list[dict], out_dir: Path) -> dict[str, Path]:
    """Draw the chart per language into out_dir: {lang: path}, empty when matplotlib is not installed or no
    contender ran at two effort settings; no "zh" entry when no CJK font is installed."""
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return {}
    data = effort_data(rows)
    if not data["groups"]:
        return {}
    out = {"en": draw(data, out_dir / NAMES["en"])}
    font = cjk_font()
    if font:
        out["zh"] = draw(data, out_dir / NAMES["zh"], "zh", font)
    return out
