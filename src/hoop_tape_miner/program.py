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
copies the mp3 next to the page.

The page is the engine program_app.html with that data inlined. Ticks, finished workouts and the game log are
saved in the browser (localStorage). `hoop-tape-miner publish <program folder> --deploy` gives it a random
/p/<token>/ link; opened from that link the page also syncs the whole log to the site's /api/sync/<token>
(Workers KV, newest copy wins), so another device, or `program pull`, sees the same progress.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import time
import urllib.request
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
    if not plan["phases"]:
        errors.append("phases is empty")
    return errors


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
    # data last, so text inside the fragments can never be taken for a placeholder
    for marker, data in (("/*PLAN*/", plan), ("/*VIDEOS*/", videos), ("/*REFS*/", refs)):
        out = out.replace(marker, script_json(data), 1)
    return out


def build(folder: Path) -> Path:
    out = folder / "index.html"
    media.write_text_atomic(out, page(folder))
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
