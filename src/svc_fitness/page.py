"""Page hooks: the session's muscle map (bars, share of the training emphasis) and the measured reps per set, in one
closed fold above the report, so the phone's first screen shows the report's advice."""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import library

UI = {"zh": dict(fold="肌肉分布和每组数据", muscles="这次练到的肌肉（按动作和次数估算）", sets="每组测到的数据", set="组", ex="动作",
                 reps="次数", depth="最低膝角", lean="躯干前倾", tempo="下 / 起（秒）", slow="后几次变慢",
                 note="只有侧面拍的组才测角度；估算，不是肌电。", none="—"),
      "en": dict(fold="Muscle map and per-set numbers", muscles="Muscles this session trained (estimated from exercises and reps)", sets="Measured per set",
                 set="Set", ex="Exercise", reps="Reps", depth="Lowest knee angle", lean="Trunk lean",
                 tempo="Down / up (s)", slow="Slowing", note="Angles only from side-view sets; estimates, not EMG.",
                 none="—")}


def files(folder: Path) -> tuple[Path, Path]:
    run = Path(folder) / "run"
    return run / "review" / "sets.json", run / "reps" / "reps.json"


def inputs(folder: Path) -> list[Path]:
    return list(files(folder))


def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf8")) if p.exists() else {}


def muscle_bars(share: dict[str, float], lang: str, top: int = 10) -> str:
    """Horizontal bars, largest first, as plain HTML/CSS (no script)."""
    lib = library.load()
    rows = []
    hi = max(share.values()) if share else 1
    for m, v in list(share.items())[:top]:
        name = lib["muscles"].get(m, {}).get(lang) or lib["muscles"].get(m, {}).get("en") or m
        rows.append(f'<div class="fx-row"><span class="fx-name">{html.escape(name)}</span>'
                    f'<span class="fx-bar"><i style="width:{100 * v / hi:.0f}%"></i></span>'
                    f'<span class="fx-val">{v:.0f}%</span></div>')
    return "".join(rows)


def set_name(s: dict, lang: str) -> str:
    """The name the review gave a set ("other" exercises): one string, or one per language."""
    n = s.get("name")
    if isinstance(n, dict):
        return str(n.get(lang) or n.get("en") or next(iter(n.values()), "") or "")
    return str(n or "")


def _fmt(v, unit: str = "", nd: int = 0) -> str:
    """A table number: whole degrees and percent, seconds to `nd` decimals; "—" when not measured."""
    return f"{round(v, nd):g}{unit}" if isinstance(v, (int, float)) else "—"


def box(folder: Path, band: dict, langs: list) -> str:
    """HTML above the report: muscle map + per-set table, one block per page language. `langs`: the page's
    (code, html lang, switch label, README) tuples, first shown; plain codes work too."""
    sets_p, reps_p = files(folder)
    sets = _read(sets_p).get("sets", [])
    if not sets:
        return ""
    reps = _read(reps_p).get("sets", {})
    ex = library.exercises()
    out = ['<style>.fx{margin:1rem 0}.fx-row{display:flex;align-items:center;gap:.5rem;margin:.2rem 0}'
           '.fx-name{flex:0 0 7.5rem;font-size:.9rem}.fx-bar{flex:1;background:#eee;border-radius:4px;height:.8rem}'
           '.fx-bar i{display:block;height:100%;background:#d9480f;border-radius:4px}.fx-val{flex:0 0 3rem;'
           'text-align:right;font-variant-numeric:tabular-nums}.fx table{border-collapse:collapse;min-width:100%;'
           'font-size:.85rem}.fx td,.fx th{padding:.3rem .4rem;border-bottom:1px solid #eee;text-align:left;'
           'white-space:nowrap}.fx summary{cursor:pointer;font-weight:600;padding:.4rem 0}'
           '.fx-scroll{overflow-x:auto}.fx small{color:#666}</style>']
    for i, entry in enumerate(langs):
        lang, tag = (entry[0], entry[1]) if isinstance(entry, (tuple, list)) else (entry, entry)
        t = UI.get(lang, UI["en"])
        rows = []
        for s in sets:
            e = ex.get(s.get("exercise"))
            name = (e or {}).get(lang) or (e or {}).get("zh" if lang == "zh" else "en") or set_name(s, lang) or "?"
            r = reps.get(s.get("id"), {})
            n = s.get("reps") if s.get("reps") is not None else r.get("n")
            tempo = (f"{_fmt(r.get('ecc_s_mean'), nd=1)} / {_fmt(r.get('con_s_mean'), nd=1)}"
                     if r.get("ecc_s_mean") is not None else "—")
            rows.append(f"<tr><td>{html.escape(str(s.get('id')))}</td><td>{html.escape(name)}</td><td>{_fmt(n)}</td>"
                        f"<td>{_fmt(r.get('knee_min_deg_mean'), '°')}</td><td>{_fmt(r.get('trunk_lean_deg_mean'), '°')}"
                        f"</td><td>{tempo}</td><td>{_fmt(r.get('slowing_pct'), '%')}</td></tr>")
        out.append(f'<section class="fx" lang="{tag}" data-lang="{lang}"{" hidden" if i else ""}><details>'
                   f'<summary>{t["fold"]}</summary><h3>{t["muscles"]}</h3>'
                   f"{muscle_bars(library.muscle_load(sets), lang)}<h3>{t['sets']}</h3><div class=\"fx-scroll\"><table>"
                   f"<tr><th>{t['set']}</th><th>{t['ex']}</th><th>{t['reps']}</th><th>{t['depth']}</th>"
                   f"<th>{t['lean']}</th><th>{t['tempo']}</th><th>{t['slow']}</th></tr>{''.join(rows)}</table></div>"
                   f"<small>{t['note']}</small></details></section>")
    return "".join(out)
