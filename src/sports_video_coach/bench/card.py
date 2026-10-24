"""The benchmark page's share card: a 1200x630 PNG (`card.png` next to `index.html`) that link previews on X,
dev.to and chat apps show. It is drawn from the same per-contender summary as the page's Summary tables
(`page.summarize`, same floor), so it never drifts from them: per suite and track, the top contenders' mean
"above chance" score as bars. `card_data` is the data step (tested); `draw` needs matplotlib, which the light
install does not have: without it `bench page` skips the card and the page has no `og:image`. `card-zh.png` is the
Chinese card for the Chinese pages (only when a CJK font is installed, as for `effort-zh.png`; else they show
`card.png`).
"""
from __future__ import annotations

from pathlib import Path

NAMES = {"en": "card.png", "zh": "card-zh.png"}
NAME = NAMES["en"]
SIZE = (1200, 630)
TITLE = "Which coding agent is the best sports film reviewer?"
SUB = "sports-video-coach benchmark  ·  {}  ·  scored against drawn ground truth"
PANELS = 3       # suite + track panels on the card, hardest first
BARS = 4         # top contenders per panel
TRACKS = ("frames", "code")   # within a suite, the frames-only track (eyes) first
FLOOR = "Mean score above chance per contender: 0 = the blind baseline's guess (no video seen), 1 = perfect."


def label(key: tuple[str, str, str]) -> str:
    """A contender's short name on the card: its model (without a `claude-` prefix) and agent, else its agent."""
    agent, model, _ = key
    return f"{model.removeprefix('claude-')} · {agent}" if model else agent


def card_data(rows: list[dict]) -> dict:
    """What the card shows: {"date", "panels": [{"suite", "track", "bars": [{"label", "agent", "model", "n",
    "above"}]}]}. Panels follow the page's suite order (`page.SUITES`), frames track first, only those with a
    contender above a floor; bars are the first BARS entries of that panel's summary (`page.summarize`)."""
    from . import page as P
    known = [n for n, _ in P.SUITES]
    suites = known + sorted({P.suite_of(r) for r in rows} - set(known))
    panels = []
    for s in suites:
        for t in TRACKS:
            mine = [r for r in rows if P.suite_of(r) == s and P.track_of(r) == t]
            summary = P.summarize(mine, P.floor_of(mine))
            bars = [{"label": label(x["key"]), "agent": x["key"][0], "model": x["key"][1], "n": x["n"],
                     "above": round(x["above"], 3)} for x in summary if x["above"] is not None][:BARS]
            if bars:
                panels.append({"suite": s, "track": t, "bars": bars})
    dates = [str(r.get("date")) for r in rows if r.get("date")]
    return {"date": max(dates) if dates else "", "panels": panels[:PANELS]}


def draw(data: dict, path: Path, lang: str = "en", font: str | None = None) -> Path:
    """Write the card for `card_data` output to `path` (PNG, SIZE pixels); `font` for the Chinese text."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .page import t

    ink, muted, bg, bar, track = "#1d1b38", "#5c5a86", "#f6f5fb", "#3b36a8", "#e2e0ef"
    w, h = SIZE
    rc = {"font.family": "sans-serif", "font.sans-serif": ([font] if font else []) + ["DejaVu Sans"]}
    with plt.rc_context(rc):
        fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=bg)
        fig.text(0.04, 0.9, t(TITLE, lang), fontsize=26, fontweight="bold", color=ink, va="center")
        fig.text(0.04, 0.81, t(SUB, lang).format(data["date"]), fontsize=17, color=muted, va="center")
        panels = data["panels"]
        if not panels:
            fig.text(0.04, 0.5, t("No runs yet: be the first.", lang), fontsize=30, color=ink)
        gap, left, right = 0.03, 0.04, 0.96
        pw = (right - left - gap * (len(panels) - 1)) / max(len(panels), 1)
        for i, p in enumerate(panels):
            x0 = left + i * (pw + gap)
            fig.text(x0, 0.72, p["suite"], fontsize=22, fontweight="bold", color=ink, va="center")
            fig.text(x0, 0.665, t("frames only (eyes)" if p["track"] == "frames" else "code track", lang), fontsize=16,
                     color=muted, va="center")
            for j, b in enumerate(p["bars"]):
                y = 0.585 - j * 0.115
                fig.text(x0, y, b["label"], fontsize=19, color=ink, va="center")
                ax = fig.add_axes((x0, y - 0.07, pw * 0.78, 0.04))
                ax.set_xlim(0, 1)
                ax.barh([0], [1], color=track, height=1)
                ax.barh([0], [b["above"]], color=bar, height=1)
                ax.axis("off")
                fig.text(x0 + pw * 0.8, y - 0.05, f"{b['above']:.2f}", fontsize=20, fontweight="bold", color=ink,
                         va="center")
        fig.text(0.04, 0.045, t(FLOOR, lang), fontsize=15, color=muted, va="center")
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=100, facecolor=bg)
        plt.close(fig)
    return path


def write(rows: list[dict], out_dir: Path) -> dict[str, Path]:
    """Draw the card per language into out_dir: {lang: path}, empty when matplotlib is not installed; no "zh"
    entry when no CJK font is installed."""
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return {}
    from .effort import cjk_font
    data = card_data(rows)
    out = {"en": draw(data, out_dir / NAMES["en"])}
    font = cjk_font()
    if font:
        out["zh"] = draw(data, out_dir / NAMES["zh"], "zh", font)
    return out
