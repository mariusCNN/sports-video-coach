"""A basic box score per player of ours: points and fouls from the league, plus-minus from the lineups, rebounds,
assists and steals counted on the film.

usage: hoop-tape-miner box <game folder> [--draft]

The league sheet (official.json in the folder, else in the run) records only made shots and fouls, so the rest is counted on the film:
<game folder>/box.json holds one entry per moment that can give a rebound, an assist or a steal,
    {"events": [{"t": 52.0, "kind": "reb" | "ast" | "stl", "team": "us" | "them", "who": "13" | null, "note": ""}]}
with `who` the jersey that got it, read on the film, or null when it could not be read (counted as unclear, never
given to anyone). --draft writes box.draft.json: the candidates from the review trips (every missed shot -> a
rebound, every made basket of ours -> a possible assist, every live turnover of theirs -> a steal of ours) with
their windows and `who` null, for the reviewer to fill and save as box.json (drop an assist entry when the scorer
made it alone). Without --draft it checks box.json and prints the table.

Plus-minus: <review>/plusminus.json (`hoop-tape-miner plusminus`), the score while the player was seen on court;
the seconds seen are shown with it, since the lineups do not cover every minute.
The team page shows the table above section 1, under the Four Factors (page_hooks.intro).
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

KINDS = ("reb", "ast", "stl")

UI = {
    "zh": dict(title="每人数据", num="号码", pts="得分", reb="篮板", ast="助攻", stl="抢断", pm="正负值", pf="犯规",
               unclear="看不清是谁", team="全队",
               help=[("得分 · 犯规", "联赛官方记录"),
                     ("篮板 · 助攻 · 抢断", "看录像一个个数的；号码看不清的放在“看不清是谁”，不算给任何人"),
                     ("正负值", "他在场时，我们得分减对手得分。小字是录像里认出他在场的时间，不是全部上场时间")]),
    "en": dict(title="Player numbers", num="#", pts="PTS", reb="REB", ast="AST", stl="STL", pm="+/-", pf="PF",
               unclear="Unclear who", team="Team",
               help=[("PTS · PF", "the league's record"),
                     ("REB · AST · STL", "counted on the film; when the jersey could not be read it goes to "
                                         "\"Unclear who\", never to a player"),
                     ("+/-", "our points minus theirs while the player was on court. The small figure is the time "
                             "seen on court in the film, not all the minutes played")]),
}


# ---- data ---------------------------------------------------------------------------------------------------------

def check(box: dict) -> list[str]:
    """Problems in a box.json: unknown kinds or teams, a jersey that is not a string of digits."""
    if not isinstance(box, dict):
        return ["must be an object"]
    events = box.get("events")
    if not isinstance(events, list):
        return ["events must be a list"]
    out = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            out.append(f"events[{i}]: must be an object")
            continue
        if e.get("kind") not in KINDS:
            out.append(f"events[{i}]: kind must be one of {', '.join(KINDS)}")
        if e.get("team") not in ("us", "them"):
            out.append(f"events[{i}]: team must be us or them")
        who = e.get("who")
        if who is not None and not (isinstance(who, str) and who.isascii() and who.isdigit()):
            out.append(f"events[{i}]: who must be a jersey string like \"13\" or null")
    return out


def counts(box: dict, team: str = "us") -> tuple[dict, dict]:
    """({jersey: {kind: n}}, {kind: unclear n}) for one team's events."""
    per, unclear = {}, dict.fromkeys(KINDS, 0)
    for e in box.get("events") or []:
        if e.get("team") != team or e.get("kind") not in KINDS:
            continue
        if e.get("who"):
            per.setdefault(e["who"], dict.fromkeys(KINDS, 0))[e["kind"]] += 1
        else:
            unclear[e["kind"]] += 1
    return per, unclear


def candidates(trips: list[dict]) -> list[dict]:
    """Moments of the review trips that can give a rebound (every missed shot), an assist (every made basket of
    ours) or a steal (every live turnover of theirs), in time order, `who` null. A rebound's team is the review's
    oreb_crash.got when it says, else the team on offence next."""
    from .coach_eval import trip_times
    trips = sorted(trips, key=lambda x: trip_times(x)[0] or 0)
    out = []
    for i, x in enumerate(trips):
        t0, t1 = trip_times(x)
        side, res, shot = x.get("offence"), x.get("result"), x.get("shot") or {}
        t = shot["t"] if shot.get("t") is not None else t1
        if side not in ("us", "them") or t0 is None:
            continue
        win = [round(t0, 1), round(t1, 1)]
        if res == "missed" or shot.get("made") is False:
            got = (x.get("oreb_crash") or {}).get("got")
            if got not in ("us", "them"):
                nxt = next((y.get("offence") for y in trips[i + 1:] if y.get("offence") in ("us", "them")), None)
                got = nxt if nxt in ("us", "them") else None
            out.append({"t": t, "window": win, "kind": "reb", "team": got, "who": None, "note": ""})
        if side == "us" and (res in ("made2", "made3") or shot.get("made") is True):
            out.append({"t": t, "window": win, "kind": "ast", "team": "us", "who": None,
                        "note": f"scorer {shot.get('shooter') or '?'}; drop this entry when the scorer made it alone"})
        if side == "them" and res == "turnover" and x.get("turnover_kind") != "dead":
            out.append({"t": t, "window": win, "kind": "stl", "team": "us", "who": None,
                        "note": "drop this entry when nobody of ours took the ball (a pass out of bounds)"})
    return out


def _load(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf8"))
    except ValueError as e:
        sys.exit(f"{p}: not valid JSON: {e}")
    if not isinstance(data, dict):
        sys.exit(f"{p}: must be an object")
    return data


def inputs(folder: Path) -> list[Path]:
    """Every source of the team table, including a missing file that could later add or override numbers."""
    from . import film_index
    if not (folder / "game.json").is_file():
        return []
    run = film_index.run_dir(folder.resolve())
    if run is None:
        return []
    run = run.resolve()
    game = json.loads((folder / "game.json").read_text(encoding="utf8"))
    return [folder / "box.json", folder / "official.json", run / "official.json",
            run / (game.get("review_dir") or "review_v1") / "plusminus.json"]


def rows(folder: Path) -> tuple[list[dict], dict] | None:
    """(rows per player of ours, unclear counts) for a team report folder, or None when there is neither a box.json
    nor an official.json. A row: num, pts, pf (official), reb/ast/stl (film; None without box.json), pm, seen_s."""
    from . import film_index
    folder = Path(folder).resolve()
    run = film_index.run_dir(folder)
    official = _load(folder / "official.json") or (_load(run / "official.json") if run else None)
    box = _load(folder / "box.json")
    errors = check(box) if box is not None else []
    if errors:
        sys.exit(f"{folder / 'box.json'}:\n  " + "\n  ".join(errors))
    if official is None and box is None:
        return None
    review = film_index.review_dir(folder)
    pm = (_load(review / "plusminus.json") if review else None) or {}
    per, unclear = counts(box or {})
    league = ((official or {}).get("players") or {}).get("us") or {}
    nums = set(league) | set(per) | {k.split("#", 1)[1] for k in pm if k.startswith("us#")}
    out = []
    for n in nums:
        o, f, p = league.get(n) or {}, per.get(n), (pm.get(f"us#{n}") or {}).get("on") or {}
        if not o.get("PTS") and not o.get("PF") and not f and not p.get("seconds"):
            continue  # on the roster, never seen and nothing recorded
        film = f or dict.fromkeys(KINDS, 0)
        out.append({"num": n, "pts": o.get("PTS"), "pf": o.get("PF"),
                    **{k: (film[k] if box is not None else None) for k in KINDS},
                    "pm": p.get("net") if p.get("seconds") else None, "seen_s": p.get("seconds")})
    out.sort(key=lambda r: (-(r["pts"] or 0), int(r["num"]) if r["num"].isdigit() else 999))
    return out, (unclear if box is not None else {})


# ---- page -----------------------------------------------------------------------------------------------------------

STYLE = ("<style>.box{margin:2rem 0 2.5rem}.box table{font-variant-numeric:tabular-nums}"
         ".box th,.box td{text-align:center;white-space:nowrap}.box th:first-child,.box td:first-child{text-align:left}"
         ".box td.pos{color:#1f7a4a}.box td.neg{color:var(--whistle)}.box td small{display:block;color:var(--muted);"
         "font-size:.72rem;font-weight:400}.box tr.sum td{color:var(--muted);border-top:2px solid var(--rule)}"
         ".box tr.focus td{font-weight:700;background:var(--marker-wash)}"
         ".box-help{margin:.6rem 0 0;padding:0;list-style:none;font-size:.82rem;line-height:1.5;color:var(--muted)}"
         ".box-help b{color:var(--ink-soft)}"
         "@media (max-width:560px){.box table{font-size:.82rem}.box td,.box th{padding:.4rem .35rem}}</style>")


def _mmss(s) -> str:
    return f"{int(s) // 60}:{int(s) % 60:02d}"


def table_html(folder: Path, langs: list[tuple] | None = None, focus: str | None = None) -> str:
    """The table, one block per language (the first shown), with a short legend of where each number comes from;
    empty when rows() has nothing."""
    from sports_video_coach.render_html import LANGS
    got = rows(folder)
    if not got or not got[0]:
        return ""
    data, unclear = got
    langs = langs or LANGS[:2]
    first = langs[0][0]

    def cell(v):
        return "–" if v is None else str(v)

    def pm(r):
        if r["pm"] is None:
            return "<td>–</td>"
        cls = "pos" if r["pm"] > 0 else "neg" if r["pm"] < 0 else ""
        return (f'<td class="{cls}">{r["pm"]:+d}' if r["pm"] else "<td>0") + f'<small>{_mmss(r["seen_s"])}</small></td>'
    blocks = []
    for c, attr, *_ in langs:
        t = UI.get(c, UI["en"])
        head = "".join(f"<th>{t[k]}</th>" for k in ("num", "pts", "reb", "ast", "stl", "pm", "pf"))
        body = "".join(f'<tr{" class=focus" if r["num"] == focus else ""}><td>#{html.escape(r["num"])}</td>'
                       + "".join(f"<td>{cell(r[k])}</td>" for k in ("pts", "reb", "ast", "stl"))
                       + pm(r) + f'<td>{cell(r["pf"])}</td></tr>' for r in data)
        if any(unclear.values()):
            body += (f'<tr class="sum"><td>{t["unclear"]}</td><td></td>'
                     + "".join(f"<td>{unclear[k]}</td>" for k in KINDS) + "<td></td><td></td></tr>")
        help_ = "".join(f"<li><b>{a}</b>：{b}</li>" if c.startswith(("zh", "ja")) else f"<li><b>{a}</b>: {b}</li>"
                        for a, b in t["help"])
        blocks.append(f'<section class="box" data-lang="{c}" lang="{attr}"{"" if c == first else " hidden"}>'
                      f'<h3 class="factors-title">{t["title"]}</h3><div class="table-wrap"><table>'
                      f'<tr>{head}</tr>{body}</table></div><ul class="box-help">{help_}</ul></section>')
    return STYLE + "".join(blocks)


# ---- cli ------------------------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="hoop-tape-miner box", description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", type=Path, help="team report folder (game.json, official.json)")
    ap.add_argument("--draft", action="store_true", help="write box.draft.json: the candidates from the review trips")
    a = ap.parse_args(argv)
    from . import film_index
    from .coach_eval import load_trips
    if a.draft:
        review = film_index.review_dir(a.folder)
        if review is None:
            print(f"no review folder for {a.folder} (game.json review_dir)", file=sys.stderr)
            return 1
        ev = candidates(load_trips(review))
        out = a.folder / "box.draft.json"
        out.write_text(json.dumps({"_note": "fill `who` from the film (null = could not read), drop entries that "
                                            "did not happen, save as box.json", "events": ev},
                                  ensure_ascii=False, indent=1), encoding="utf8")
        n = {k: sum(e["kind"] == k for e in ev) for k in KINDS}
        print(f"[box] {out}: {n['reb']} rebounds, {n['ast']} possible assists, {n['stl']} steals to check")
        return 0
    box = _load(a.folder / "box.json")
    errs = check(box) if box is not None else []
    for e in errs:
        print(f"box.json: {e}", file=sys.stderr)
    if errs:
        return 1
    got = rows(a.folder)
    if got:
        for r in got[0]:
            print(f"#{r['num']:>3} pts {r['pts']} reb {r['reb']} ast {r['ast']} stl {r['stl']} pm {r['pm']} pf {r['pf']}")
        print(f"unclear: {got[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
