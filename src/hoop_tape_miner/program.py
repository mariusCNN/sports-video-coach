"""Personal training-plan app: one phone page per training program (a month of sessions), progress synced to the site.

usage: hoop-tape-miner program build <program folder>     -> <folder>/index.html (open it locally, or publish it)
       hoop-tape-miner program check <program folder>     validate program.json only
       hoop-tape-miner program pull  <program folder>     published progress -> <folder>/progress.json

A program folder (e.g. workspace/players/<player>/program/<date>/) holds program.json (sessions, exercises,
calendar, game-day targets; schema in templates/program.example.json), optional videos.json ({video key:
[{url, title, verified}]}, keys listed in an exercise's "v") and refs.json ({key: {s, lab, t, src: [[label,
url]]}}, keys listed in an exercise's "r"), and optional HTML fragments cal.html / game.html / tests.html /
decide.html / lib.html placed into the matching tab as they are (static text, no scripts; the 决策 and 资料 tabs
show only when their fragment exists). An `<audio class="loop" src="x.mp3" title="...">` in a fragment becomes a
big looping play button (e.g. a cue track from `sports-video-coach narrate --script x.zh.md --chime`); publish
copies the mp3 next to the page. A session's "car" (an mp3 file name in the folder, or {"src", "title"}) is the
talk for the drive to the court: the today tab shows it as a play-once button on every day of that session.
An optional "fixture" ({"team", "source", "games": [{"date", "time", "vs", "court", "score": [ours, theirs]} or
{"date", "bye": true}]}) is the league draw: the today and game tabs show that day's game or bye, the calendar
marks the dates and lists the whole season with results, also past the plan's last day.

The page is the engine program_app.html with that data inlined. Ticks, finished workouts and the game log are
saved in the browser (localStorage). `hoop-tape-miner publish <program folder> --deploy` gives it a random
/p/<token>/ link; opened from that link the page also syncs the whole log to the site's /api/sync/<token>
(Workers KV, newest copy wins), so another device, or `program pull`, sees the same progress. Add `?preview` to
the link for a look that writes nothing (checks, demos).

Feedback loop, all optional in program.json: every training day opens with a pre-session check (legs, pain score,
where and red flags, sleep; "readiness": false turns it off) that gives advice and never changes the session; an
exercise with kind "rep" records successes per set and says what counts as one in its "ok" text; game.counters
([key, label, hint]) replaces the log's counters (empty until counted, so a missing count is not a zero) and
game.trees lists the decision trees the log asks "which went worst" about; a session with "review" (true or a hint
text) opens with the last game's log. `program pull` prints all of it.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from sports_video_coach import media
from . import workspace as ws

ENGINE = Path(__file__).with_name("program_app.html")
FRAGMENTS = ("cal", "game", "tests", "decide", "lib")
REQUIRED = ("title", "storageKey", "start", "days", "week1", "phases", "weekdays", "sessions", "exercises")


def load(folder: Path, name: str, default=None):
    p = folder / name
    if not p.exists():
        if default is None:
            sys.exit(f"{p} is missing")
        return default
    try:
        return json.loads(p.read_text(encoding="utf8"))
    except ValueError as e:
        sys.exit(f"{p} is not valid JSON: {e}")


def validate(plan: dict) -> list[str]:
    """Problems that would break the page: missing keys, sessions or exercises referenced but not defined."""
    errors = [f"missing key {k!r}" for k in REQUIRED if k not in plan]
    if errors:
        return errors
    sess, ex = plan["sessions"], plan["exercises"]
    used = {**{f"weekdays[{k}]": v for k, v in plan["weekdays"].items()},
            **{f"special[{k}]": v for k, v in (plan.get("special") or {}).items()},
            **{f"week[{i}]": w.get("code") for i, w in enumerate(plan.get("week") or [])}}
    errors += [f"{where}: unknown session {code!r}" for where, code in used.items() if code not in sess]
    for code, s in sess.items():
        for i, it in enumerate(s.get("items") or []):
            if it.get("ex") not in ex:
                errors.append(f"sessions[{code}].items[{i}]: unknown exercise {it.get('ex')!r}")
    for code, s in sess.items():
        if "car" in s and car_src(s["car"]) is None:
            errors.append(f"sessions[{code}].car: give an mp3 file name in the program folder")
    fixture = plan.get("fixture")
    if fixture is not None and not isinstance(fixture, dict):
        errors.append("fixture: must be an object")
        fixture = {}
    games = (fixture or {}).get("games", [])
    if not isinstance(games, list):
        errors.append("fixture.games: must be a list")
        games = []
    dates = set()
    for i, g in enumerate(games):
        if not isinstance(g, dict):
            errors.append(f"fixture.games[{i}]: must be an object")
            continue
        day = g.get("date")
        try:
            if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                raise ValueError
            date.fromisoformat(day)
        except ValueError:
            errors.append(f"fixture.games[{i}]: date must be a valid YYYY-MM-DD")
        else:
            if day in dates:
                errors.append(f"fixture.games[{i}]: duplicate date {day}")
            dates.add(day)
        if "bye" in g and not isinstance(g["bye"], bool):
            errors.append(f"fixture.games[{i}].bye: must be true or false")
        if not g.get("bye") and not g.get("vs"):
            errors.append(f"fixture.games[{i}]: give the opponent (vs) or bye: true")
        score = g.get("score")
        if score is not None and not (isinstance(score, list) and len(score) == 2
                                      and all(type(x) is int and x >= 0 for x in score)):
            errors.append(f"fixture.games[{i}].score: give [ours, theirs] as non-negative integers")
    if not plan["phases"]:
        errors.append("phases is empty")
    return errors


def car_src(car) -> str | None:
    """The mp3 file name of a session's "car" (a name or {"src", "title"}); None when it is not a plain file name."""
    src = car.get("src") if isinstance(car, dict) else car
    if (not isinstance(src, str) or not src.endswith(".mp3") or Path(src).name != src
            or src.startswith(".") or any(c in src for c in "/\\:")):
        return None
    return src


def car_players(plan: dict, folder: Path) -> str:
    """One hidden <div class="carp" data-codes> with a play-once <audio> per car mp3 (sessions sharing a file share
    the player); the page shows the one of the selected day. Static src= attributes, so publish copies the files."""
    files: dict[str, dict] = {}
    for code, s in plan["sessions"].items():
        if "car" in s:
            car = s["car"] if isinstance(s["car"], dict) else {}
            f = files.setdefault(car_src(s["car"]), {"codes": [], "title": None})
            f["codes"].append(code)
            f["title"] = f["title"] or car.get("title")  # the first title given names the shared player
    for src in files:
        if not (folder / src).exists():
            print(f"[program] warning: {src} is missing in {folder}, its car player will not play", file=sys.stderr)
    return "".join(f'<div class="carp" data-codes="{html.escape(" ".join(f["codes"]))}" hidden><audio class="loop car" '
                   f'src="{html.escape(src)}" title="{html.escape(f["title"] or "车上听 · 去球场的路上")}" preload="metadata"></audio></div>'
                   for src, f in files.items())


def script_json(data) -> str:
    """JSON for an inline <script>: '<' escaped so no text in the data can close the script tag."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def page(folder: Path) -> str:
    """The app page for one program folder (exits on an invalid program.json)."""
    plan = load(folder, "program.json")
    errors = validate(plan)
    if errors:
        sys.exit(f"{folder / 'program.json'}:\n  " + "\n  ".join(errors))
    raw = load(folder, "videos.json", {})
    raw = raw.get("videos", raw)
    videos = {k: [{"url": v["url"], "title": v.get("title", "")} for v in vs
                  if isinstance(v, dict) and v.get("url") and v.get("verified") is not False]
              for k, vs in raw.items() if isinstance(vs, list)}
    refs = load(folder, "refs.json", {})
    out = ENGINE.read_text(encoding="utf8").replace("<!--TITLE-->", html.escape(plan["title"]), 1)
    for name in FRAGMENTS:
        frag = folder / f"{name}.html"
        out = out.replace(f"<!--{name.upper()}-->", frag.read_text(encoding="utf8") if frag.exists() else "", 1)
    out = out.replace("<!--CAR-->", car_players(plan, folder), 1)
    # data last, so text inside the fragments can never be taken for a placeholder
    for marker, data in (("/*PLAN*/", plan), ("/*VIDEOS*/", videos), ("/*REFS*/", refs)):
        out = out.replace(marker, script_json(data), 1)
    return out


def build(folder: Path) -> Path:
    out = folder / "index.html"
    media.write_text_atomic(out, page(folder))
    return out


def session_of(plan: dict, day: str) -> str | None:
    """Session code of an ISO date: a special date first, else the weekday (0 = Sunday, as in the page)."""
    if day in (plan.get("special") or {}):
        return plan["special"][day]
    try:
        wd = (date.fromisoformat(day).weekday() + 1) % 7
    except ValueError:
        return None
    return plan["weekdays"].get(str(wd))


def summary(plan: dict, data: dict) -> list[str]:
    """Lines on what the synced log says about the plan's feedback loop: pre-session checks, success counts of
    "rep" exercises (sum of successes / sets entered), and the last games' counters and worst decision tree."""
    out = []
    for day, r in sorted((data.get("rd") or {}).items())[-5:]:
        where = "、".join(r.get("where") or [])
        out.append(f"  ready {day} legs {r.get('legs', '–')}/4 pain {r.get('pain', '–')}/10"
                   f"{' (' + where + ')' if where else ''}{' RED FLAG' if r.get('flag') else ''}"
                   f"{' sleep ' + str(r['sleep']) + ' h' if r.get('sleep') else ''}")
    kind, reps = plan.get("kind") or {}, {}
    for key, row in (data.get("s") or {}).items():
        day, k, _ = (key.split(":") + ["", ""])[:3]
        items = (plan["sessions"].get(session_of(plan, day) or "") or {}).get("items") or []
        ex = items[int(k)]["ex"] if k.isdigit() and int(k) < len(items) else None
        if ex and kind.get(ex) == "rep" and str(row.get("v", "")).strip():
            try:
                got = float(row["v"])
            except ValueError:
                continue
            tot = reps.setdefault(ex, [0.0, 0])
            tot[0] += got
            tot[1] += 1
    for ex, (got, n) in sorted(reps.items()):
        out.append(f"  reps {ex}: {got:g} successes over {n} sets")
    labels = ({c[0]: c[1] for c in ((plan.get("game") or {}).get("counters") or [])}
              or {k: k for k in ("ast", "to", "miss", "drive2")})
    for g in [x for x in (data.get("log") or []) if x.get("type") != "shoot"][-3:]:
        cts = " ".join(f"{labels.get(k, k)} {g[k]}" for k in labels if g.get(k) is not None)
        out.append(f"  game {g.get('date')} {g.get('type')} worst {g.get('worst') or '–'}{' · ' + cts if cts else ''}")
    return out


def pull(folder: Path) -> Path:
    """Fetch the synced progress of a published program into <folder>/progress.json and print a summary."""
    root = ws.root()
    reg = json.loads((root / "publish.json").read_text(encoding="utf8")) if (root / "publish.json").exists() else {}
    try:
        key = folder.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        sys.exit(f"{folder} is not inside the workspace {root} (set HOOP_WORKSPACE)")
    tok, base = (reg.get("programs") or {}).get(key), reg.get("base_url")
    if not tok or not base:
        sys.exit(f"{key} is not published yet: run `hoop-tape-miner publish {folder} --deploy` first")
    req = urllib.request.Request(f"{base}/api/sync/{tok}", headers={"User-Agent": "hoop-tape-miner"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf8"))
    out = folder / "progress.json"
    media.write_json_atomic(out, data)
    fin, log, sets = data.get("fin") or {}, data.get("log") or [], data.get("s") or {}
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(data["updated"] / 1000)) if data.get("updated") else "never"
    print(f"{out}\n  last update {when}\n  workouts finished {len(fin)}"
          f"{' (' + ', '.join(sorted(fin)[-5:]) + ')' if fin else ''}\n  games logged {len(log)}\n  set rows {len(sets)}")
    for line in summary(load(folder, "program.json"), data):
        print(line)
    for e in (data.get("au") or [])[-8:]:  # loop-audio events, to see where playback stopped on a locked phone
        # events from before the page tagged its device cannot be told apart from a check run: say so
        print(f"  audio {time.strftime('%m-%d %H:%M:%S', time.localtime(e.get('t', 0) / 1000))} {e.get('ev')} "
              f"{e.get('src')} at {e.get('at')} s ({e.get('vis')}, {e.get('dev') or 'device unknown'})")
    if data.get("au") and data.get("ua"):
        print(f"  last browser {data['ua']}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hoop-tape-miner program", description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=("build", "check", "pull"))
    ap.add_argument("folder", type=Path, help="program folder with program.json")
    a = ap.parse_args(argv)
    if a.action == "check":
        errors = validate(load(a.folder, "program.json"))
        print("\n".join(errors) or "ok")
        sys.exit(1 if errors else 0)
    if a.action == "build":
        print(build(a.folder))
    else:
        pull(a.folder)


if __name__ == "__main__":
    main()
