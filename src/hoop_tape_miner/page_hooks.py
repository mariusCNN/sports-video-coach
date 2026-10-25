"""Basketball page hooks for the core page renderer (sports_video_coach.render_html.PageHooks).

The top band by kind (game score with halves, season record, training session, movement session), team colours and
names from game.json (us.hex / them.hex, us.team / them.team), the Four Factors panel above a game report, and after
the report the film_index sections (shot chart, playlists) and the tracking sections (load per stint, matchups).
Cheap to import (the plugin registers PAGE at import time); film_index, load and matchups load when a page renders.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from sports_video_coach import render_html
from sports_video_coach.render_html import DEFAULT_COLOURS, LANGS
from . import game_config as gc

UI = {  # labels on basketball pages, merged over render_html.UI
    "zh": dict(us="我们", them="对手", half1="上半场", half2="下半场", final="终场",
               missing="（片段还没剪：运行 hoop-tape-miner clips）",
               training="个人训练", made="命中 / 出手", shots="投篮", finishes="终结", dribble="运球",
               targets="目标达成", vs_last="对比上次", minutes="分钟", unclear="无法判断",
               movement="运动模式", segments="片段", seen="看到的问题", hypotheses="待侧拍验证", good="保持的优点",
               measured="测量值", season="赛季", points="得分–失分", games="场次"),
    "en": dict(us="Us", them="Them", half1="1st half", half2="2nd half", final="Final",
               missing="(clip not cut yet: run hoop-tape-miner clips)",
               training="Training", made="Made / attempts", shots="Shots", finishes="Finishes", dribble="Dribbling",
               targets="Targets met", vs_last="vs last session", minutes="min", unclear="unclear",
               movement="Movement", segments="Segments", seen="Findings seen", hypotheses="To test (side re-shoot)",
               good="Good habits", measured="Measured", season="Season", points="Points for–against",
               games="Games"),
}


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def scoreboard(folder: Path):
    """Team names, colours and score from game.json; scores are None while the result is not filled in."""
    game = gc.load_game(folder)
    if not game:
        raise FileNotFoundError(f"game.json / session.json not found in {folder} or its parent")
    if gc.is_personal(game):
        return training_scoreboard(folder, game)
    if gc.is_season(game):
        return season_scoreboard(game)
    res = game.get("result") or {}
    fin = (_num(res.get("us")), _num(res.get("them")))
    ht = res.get("halftime") or {}
    h1 = (_num(ht.get("us")), _num(ht.get("them")))
    h2 = (fin[0] - h1[0], fin[1] - h1[1]) if None not in fin + h1 else (None, None)
    colours = {}
    for side in gc.SIDES:
        h = gc.team(game, side).get("hex")
        colours[side] = (h, gc.mix(h, "#ffffff", 0.55)) if gc.is_hex(h) else DEFAULT_COLOURS[side]
    return dict(us=gc.team_name(game, "us"), them=gc.team_name(game, "them"), final=fin, h1=h1, h2=h2, colours=colours)


BOARD = """<div class="score" data-result="{result}">
      <div class="team us"><span class="name">{us_name}</span><span class="side">{us_label}</span></div>
      <div class="pts" aria-label="{us_pts}–{them_pts}"><span class="{us_cls}">{us_pts}</span><span class="dash">–</span><span class="{them_cls}">{them_pts}</span></div>
      <div class="team them"><span class="name">{them_name}</span><span class="side">{them_label}</span></div>
    </div>
    <div class="halves">{halves}</div>"""


def training_scoreboard(folder: Path, s: dict) -> dict:
    """Session band: the player, made / attempts and % over all reviewed reps (summary.json `headline`)."""
    p = folder / "summary.json"
    summ = json.loads(p.read_text(encoding="utf8")) if p.exists() else {}
    h = s.get("hex")
    colours = dict(DEFAULT_COLOURS)
    if gc.is_hex(h):
        colours["us"] = (h, gc.mix(h, "#ffffff", 0.55))
    name = s.get("name") or f"#{s.get('player', '')}"
    return dict(training=True, movement=gc.is_movement(s), us=name, them="", date=s.get("date") or folder.name,
                summary=summ, colours=colours)


def season_scoreboard(s: dict) -> dict:
    """Season band (season.json from `hoop-tape-miner season`): our team, won-lost, points for-against."""
    colours = dict(DEFAULT_COLOURS)
    for side in gc.SIDES:
        h = gc.team(s, side).get("hex")
        if gc.is_hex(h):
            colours[side] = (h, gc.mix(h, "#ffffff", 0.55))
    return dict(season=True, us=gc.team_name(s, "us"), them="", record=s.get("record") or {},
                games=s.get("games"), sid=s.get("season", ""), colours=colours)


def season_board(sb: dict, lab) -> str:
    r = sb["record"]
    wl = f'{r.get("W", 0)}–{r.get("L", 0)}' + (f'–{r["T"]}' if r.get("T") else "")
    return f"""<div class="score" data-result="season">
      <div class="team us"><span class="name">{html.escape(sb["us"])}</span><span class="side">{lab("season")} · {html.escape(str(sb["sid"]))}</span></div>
      <div class="pts" aria-label="{wl}"><span>{wl}</span></div>
      <div class="team them"><span class="name">{r.get("for", 0)}–{r.get("against", 0)}</span><span class="side">{lab("points")}</span></div>
    </div>
    <div class="halves"><span>{lab("games")}<b>{sb["games"]}</b></span></div>"""


def _pct(t: dict | None) -> str:
    return f"{round(100 * t['pct'])}%" if t and t.get("pct") is not None else "–"


def training_board(sb: dict, lab) -> str:
    summ = sb["summary"]
    tot = (summ.get("totals") or {})
    allr = tot.get("all") or {}
    stats = []
    for key, t in (("shots", tot.get("shot")), ("finishes", tot.get("finish"))):
        if t and (t.get("att") or t.get("unclear")):
            got = f'{t["made"]}/{t["att"]} · {_pct(t)}' if t.get("att") else "–"
            more = f' +{t["unclear"]} {lab("unclear")}' if t.get("unclear") else ""
            stats.append(f'<span>{lab(key)}<b>{got}</b>{more}</span>')
    drib = summ.get("dribble") or {}
    if drib.get("seconds"):
        stats.append(f'<span>{lab("dribble")}<b>{drib["seconds"] / 60:.1f}</b> {lab("minutes")}</span>')
    tg = summ.get("targets") or []
    if tg:
        stats.append(f'<span>{lab("targets")}<b>{sum(t["status"] == "met" for t in tg)}/{len(tg)}</b></span>')
    d = (summ.get("previous") or {}).get("delta_pct")
    if d is not None:
        stats.append(f'<span>{lab("vs_last")}<b>{"+" if d >= 0 else "−"}{abs(round(100 * d))}</b> pp</span>')
    made = f'{allr["made"]}/{allr["att"]}' if allr.get("att") else "–"
    return f"""<div class="score" data-result="training">
      <div class="team us"><span class="name">{html.escape(sb["us"])}</span><span class="side">{lab("training")} · {html.escape(str(sb["date"]))}</span></div>
      <div class="pts" aria-label="{_pct(allr)}"><span>{_pct(allr)}</span></div>
      <div class="team them"><span class="name">{made}</span><span class="side">{lab("made")}</span></div>
    </div>
    <div class="halves">{"".join(stats)}</div>"""


def movement_board(sb: dict, lab) -> str:
    """Movement band: the player, film findings seen / to test / good habits and measured metrics (headline)."""
    h = sb["summary"].get("headline") or {}
    stats = [f'<span>{lab(k)}<b>{h[k]}</b></span>' for k in ("segments", "hypotheses", "good") if h.get(k) is not None]
    if h.get("shown_metrics"):
        stats.append(f'<span>{lab("measured")}<b>{h["shown_metrics"]}</b></span>')
    seen = h.get("seen")
    return f"""<div class="score" data-result="training">
      <div class="team us"><span class="name">{html.escape(sb["us"])}</span><span class="side">{lab("movement")} · {html.escape(str(sb["date"]))}</span></div>
      <div class="pts" aria-label="{seen if seen is not None else '–'}"><span>{seen if seen is not None else '–'}</span></div>
      <div class="team them"><span class="name"></span><span class="side">{lab("seen")}</span></div>
    </div>
    <div class="halves">{"".join(stats)}</div>"""


# ---- Four Factors panel (team page) ----------------------------------------------------------------------------
FF_UI = {
    "zh": dict(title="四要素 Four Factors", side="", efg="有效命中率 eFG%", tov="失误率 TOV%", live="活球", dead="死球",
               orb="进攻篮板率 ORB%", ft="罚球率（罚中/出手）", poss="回合数", ppp="每回合得分",
               transition="转换进攻 每次得分", half_court="阵地进攻 每次得分", second_chance="二次进攻 每次得分",
               after_live_turnover="对方活球失误后 每次得分", trips="次", trip="次",
               note="来源：联赛数据（命中）+ 录像复盘（出手、失误、篮板、回合）。百分比 = 每 100 次。"
                    "回合数 = 复盘的进攻次数减去抢到前场篮板后的二次进攻；每回合得分用录像里的得分。",
               factors=dict(efg="投篮（eFG%）", tov="失误（TOV%）", orb="进攻篮板（ORB%）", ft="罚球（罚球率）"),
               decided="决定比赛的因素：{f}，我们 {a} 对 对手 {b}，{who}领先 {gap} 个百分点（加权 {w}）。",
               us_word="我们", them_word="对手", lower="越低越好", more="回合数、每回合得分与数据来源",
               unclear="决定比赛的因素：无法判断（样本太小或差距太小）。"),
    "en": dict(title="Four Factors", side="", efg="Effective FG% (eFG%)", tov="Turnover rate (TOV%)", live="live",
               dead="dead", orb="Offensive rebounding (ORB%)", ft="Free-throw rate (FTM/FGA)", poss="Possessions",
               ppp="Points per possession", transition="Transition, points per trip",
               half_court="Half-court, points per trip", second_chance="Second chance, points per trip",
               after_live_turnover="After their live-ball turnover, points per trip", trips="trips", trip="trip",
               note="Sources: league sheet (makes) + film review (attempts, turnovers, rebounds, possessions). "
                    "Percentages are per 100. Possessions = reviewed trips minus second-chance trips (after an "
                    "offensive rebound); points per possession uses the points seen on film.",
               factors=dict(efg="shooting (eFG%)", tov="turnovers (TOV%)", orb="offensive rebounding (ORB%)",
                            ft="free throws (FT rate)"),
               decided="The factor that decided the game: {f}, us {a} vs them {b}, {gap} percentage points in favour of {who} "
                       "(weighted {w}).",
               us_word="us", them_word="them", lower="lower is better",
               more="Possessions, points per trip and sources",
               unclear="The factor that decided the game: unclear (sample or gap too small)."),
}
_FF_KEYS = {"efg": "efg_pct", "tov": "tov_pct", "orb": "orb_pct", "ft": "ft_rate_pct"}


def _ff_pct(v) -> str:
    return "–" if v is None else f"{v:.1f}%"


def summary_paths(folder: Path) -> list[Path]:
    """Where a team report folder's summary.json may be (game.json in the folder itself): the folder's own, then
    <run>/<review_dir or review_v1>/summary.json; [] without game.json. Also the page's html inputs."""
    gj = folder / "game.json"
    if not gj.exists():
        return []
    game = json.loads(gj.read_text(encoding="utf8"))
    run = Path(game["run"]) if game.get("run") else folder / "run"
    return [folder / "summary.json", run / (game.get("review_dir") or "review_v1") / "summary.json"]


def four_factors_summary(folder: Path) -> dict | None:
    """summary.json `all` block with `four_factors` for a team report folder (`summary_paths`, first one that has
    it); None when there is none."""
    for p in summary_paths(folder):
        if p.exists():
            try:
                allv = json.loads(p.read_text(encoding="utf8")).get("all") or {}
            except (ValueError, AttributeError):
                continue
            if isinstance(allv, dict) and isinstance(allv.get("four_factors"), dict):
                return allv
    return None


def four_factors_panel(folder: Path, names: dict | None = None, langs: list[tuple] | None = None) -> str:
    """Small two-team table (zh + en blocks, one shown at a time) with the Four Factors, PPP by trip type and the
    deciding-factor line; empty string when the review has no four_factors yet."""
    allv = four_factors_summary(folder)
    if not allv:
        return ""
    ff, pp = allv["four_factors"], allv.get("ppp") or {}
    us, them = ff.get("us") or {}, ff.get("them") or {}
    names = names or {}
    langs = langs or LANGS[:2]  # basketball pages are zh + en
    first = langs[0][0]

    def hide(c):
        return "" if c == first else " hidden"
    blocks = []
    for c, attr, *_ in langs:
        t = FF_UI[c]

        def tov(s):
            if s.get("tov_pct") is None:
                return "–"
            extra = (f' <small>({t["live"]} {s["tov_live_pct"]:.1f} · {t["dead"]} {s["tov_dead_pct"]:.1f})</small>'
                     if s.get("tov_live_pct") is not None and s.get("tov_dead_pct") is not None else "")
            return _ff_pct(s["tov_pct"]) + extra

        def orb(s):
            v = _ff_pct(s.get("orb_pct"))
            return v + (f' <small>({s["orb"]}/{s["orb_chances"]})</small>' if s.get("orb_chances") else "")

        def poss(s):
            return "–" if s.get("possessions") is None else f'{s["possessions"]:g}'

        def num(v):
            return "–" if v is None else f"{v:.2f}"

        def ppp_cell(side, k):
            g = (pp.get(side) or {}).get(k) or {}
            n = g.get("trips", 0)
            return f'{num(g.get("ppp"))} <small>({n} {t["trip"] if n == 1 else t["trips"]})</small>' if n else "–"
        def bar(k, cell, side):
            a, b = us.get(k), them.get(k)
            top = max(a or 0, b or 0) or 1
            v = us.get(k) if side == "us" else them.get(k)
            w = 0 if v is None else round(100 * v / top)
            return (f'<span class="ff-val {side}"><span class="ff-bar" style="width:{w}%"></span>'
                    f'<span class="ff-num">{cell}</span></span>')
        bars = [(t["efg"], "efg_pct", _ff_pct(us.get("efg_pct")), _ff_pct(them.get("efg_pct")), ""),
                (t["tov"], "tov_pct", tov(us), tov(them), t["lower"]),
                (t["orb"], "orb_pct", orb(us), orb(them), ""),
                (t["ft"], "ft_rate_pct", _ff_pct(us.get("ft_rate_pct")), _ff_pct(them.get("ft_rate_pct")), "")]
        rows = [(t["poss"], poss(us), poss(them)), (t["ppp"], num(us.get("ppp")), num(them.get("ppp")))]
        rows += [(t[k], ppp_cell("us", k), ppp_cell("them", k))
                 for k in ("transition", "half_court", "second_chance", "after_live_turnover") if pp]
        d = ff.get("decided") or {}
        if d.get("status") == "ok" and d.get("factor") in _FF_KEYS:
            key = _FF_KEYS[d["factor"]]
            line = t["decided"].format(f=t["factors"][d["factor"]], a=_ff_pct(us.get(key)),
                                       b=_ff_pct(them.get(key)), gap=f'{abs(d["gap"]):.1f}',
                                       w=f'{abs(d["weighted"][d["factor"]]):.1f}',
                                       who=t["us_word"] if d["favours"] == "us" else t["them_word"])
        else:
            line = t["unclear"]
        us_name, them_name = (html.escape(names.get(k) or UI[c][k]) for k in ("us", "them"))
        legend = (f'<p class="ff-legend"><span class="ff-key us">{us_name}</span>'
                  f'<span class="ff-key them">{them_name}</span></p>')
        grid = "".join(f'<div class="ff-row"><span class="ff-label">{lab}'
                       + (f' <small>{hint}</small>' if hint else "") + '</span>'
                       + bar(k, a, "us") + bar(k, b, "them") + '</div>'
                       for lab, k, a, b, hint in bars)
        head = f'<tr><th></th><th>{us_name}</th><th>{them_name}</th></tr>'
        body = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{e}</td></tr>" for a, b, e in rows)
        blocks.append(f'<section class="factors" data-lang="{c}" lang="{attr}"{hide(c)}>'
                      f'<h3 class="factors-title">{t["title"]}</h3><p class="decided">{html.escape(line)}</p>'
                      f'{legend}<div class="ff-bars">{grid}</div>'
                      f'<details class="more"><summary>{t["more"]}</summary>'
                      f'<div class="table-wrap"><table>{head}{body}</table></div>'
                      f'<p class="factors-note">{t["note"]}</p></details></section>')
    style = ("<style>.factors{margin:2rem 0 2.5rem}.factors .decided{font-weight:700;max-width:var(--measure)}"
             ".ff-legend{display:flex;gap:1.25rem;margin:.75rem 0 .5rem;font-size:.85rem;color:var(--ink-soft)}"
             ".ff-key::before{content:'';display:inline-block;width:.8rem;height:.8rem;margin-right:.4rem;"
             "vertical-align:-.05rem;border-radius:2px;background:var(--us)}.ff-key.them::before{background:var(--them)}"
             ".ff-bars{border-top:2px solid var(--ink);background:var(--sheet)}"
             ".ff-row{display:grid;grid-template-columns:minmax(8rem,1.1fr) 1fr 1fr;gap:.25rem .75rem;align-items:center;"
             "padding:.6rem .7rem;border-bottom:1px solid var(--rule)}"
             ".ff-label{font-size:.88rem;line-height:1.35}.ff-label small{display:block;color:var(--muted);font-size:.78rem}"
             ".ff-val{position:relative;display:block;min-height:1.9rem;background:var(--paper);border-radius:2px;overflow:hidden}"
             ".ff-bar{position:absolute;inset:0 auto 0 0;background:var(--us);opacity:.3}.ff-val.them .ff-bar{background:var(--them)}"
             ".ff-num{position:relative;display:block;padding:0 .5rem;font:700 1.05rem/1.9rem var(--display);"
             "font-variant-numeric:tabular-nums;color:var(--ink)}"
             ".ff-num small{font:500 .78rem var(--display);color:var(--ink-soft)}"
             ".factors td,.factors th{white-space:nowrap;font-variant-numeric:tabular-nums}"
             ".factors td:first-child{white-space:normal}.factors small{color:inherit}"
             ".factors-note{color:var(--muted);font-size:.8rem}"
             "@media (max-width:560px){.ff-row{grid-template-columns:1fr 1fr}.ff-label{grid-column:1/-1}"
             ".factors table{font-size:.8rem}.factors td,.factors th{padding:.4rem .45rem}}"
             "</style>")
    return style + "".join(blocks)


def tracking_sections(folder: Path, lang: str, first: int) -> tuple[str, list[str]]:
    """(HTML, h2 titles) from the run's load.json (player page: stint table) and matchups.json (team page: shot
    defence + matchups; player page: that player's rows); empty when the files are missing."""
    from . import film_index
    from . import load as loadmod  # numpy / pandas: imported only when a page is rendered
    from . import matchups as mumod

    run = film_index.run_dir(folder) if Path(folder).is_dir() else None
    if run is None:
        return "", []
    focus = film_index.focus_of(folder)
    out, heads = [], []
    for name, mod, render in (("load.json", loadmod, lambda d: loadmod.table_html(d, focus, lang) if focus else ""),
                              ("matchups.json", mumod, lambda d: mumod.tables_html(d, focus, lang))):
        p = run / name
        if not p.exists():
            continue
        try:
            body = render(json.loads(p.read_text(encoding="utf8")))
        except (ValueError, KeyError, TypeError) as ex:
            print(f"warning: {p} not shown ({ex})", file=sys.stderr)
            continue
        if body:
            title = mod.UI[lang]["title"]
            out.append(f'<h2 id="{lang}-s{first + len(heads)}">{title}</h2>{body}')
            heads.append(title)
    return "".join(out), heads


def sections(folder: Path, lang: str, embed: bool, first: int) -> tuple[str, list[str], str]:
    """After the report: shot chart + playlists (film_index), then load per stint and matchups; the film assets
    (its script and styles) go once at the end of the page when there is a film section."""
    from . import film_index
    film, film_heads = film_index.sections(folder, lang, embed, first)
    track, track_heads = tracking_sections(folder, lang, first + len(film_heads))
    return film + track, film_heads + track_heads, film_index.ASSETS if film else ""


def band(sb: dict, lab) -> str:
    """The top band by kind: season record, movement session, training session, else the game score."""
    if sb.get("season"):
        return season_board(sb, lab)
    if sb.get("movement"):
        return movement_board(sb, lab)
    if sb.get("training"):
        return training_board(sb, lab)
    us, them = sb["final"]
    known = None not in (us, them)
    result = ("win" if us > them else "loss" if us < them else "tie") if known else "unknown"
    halves = [f'<span>{lab(key)}<b>{a}–{b}</b></span>'
              for key, (a, b) in (("half1", sb["h1"]), ("half2", sb["h2"])) if None not in (a, b)]
    if known:
        halves.append(f'<span>{lab("final")}<b>{us}–{them}</b></span>')
    return BOARD.format(
        result=result, us_cls="" if not known or us >= them else "lose", them_cls="" if not known or them >= us else "lose",
        us_name=html.escape(sb["us"]), them_name=html.escape(sb["them"]), us_label=lab("us"), them_label=lab("them"),
        us_pts=us if known else "", them_pts=them if known else "", halves="".join(halves))


def intro(folder: Path, sb: dict, langs: list[tuple]) -> str:
    """Four Factors panel inside a game report, before section 1 (not on training, movement or season pages)."""
    return "" if sb.get("training") or sb.get("season") else four_factors_panel(folder, sb, langs)


PAGE = render_html.PageHooks(ui=UI, board=scoreboard, band=band, intro=intro, sections=sections,
                             inputs=summary_paths)

