"""`leaderboard.json`, the machine-readable copy of the leaderboard, written by `bench page` next to index.html.

For anyone who reads the board from a script (a list of leaderboards, a tracker, a citation pinned to a date): one
board per track and suite with runs, in the page's order (code track first, then frames; per track the suites in
`page.SUITES` order, then any other suite by name). Each board has its contenders ranked as the page's Summary ranks
them (same `summarize` and `ranks`) and every run, best total first. Every number comes from a result file in
`benchmark/results` through the page's own functions; nothing is stored that the folder does not hold. No build
time is written, so the file only changes when the results do; `latest_run` is the newest run's date.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import page

NAME = "leaderboard.json"
SCHEMA = 1
TRACKS = ("code", "frames")    # the page shows the code track's tables first, then the frames track's


def num(v, digits: int = 4):
    """A number rounded for the file, or None when the run did not record it."""
    return round(float(v), digits) if page.is_num_value(v) else None


def suite_order(names: set[str]) -> list[str]:
    known = [n for n, _ in page.SUITES]
    fresh = [n + page.FRESH for n in known]
    return [n for n in known + fresh if n in names] + sorted(names - set(known) - set(fresh))


def board(rows: list[dict], track: str, suite: str) -> dict:
    """One track and suite: its floor file, its ranked contenders and every run."""
    mine = [r for r in rows if page.track_of(r) == track and page.suite_of(r) == suite]
    floor_row = page.floor_of(mine)
    floor = {str(t["id"]): t.get("score") for t in floor_row["tasks"]} if floor_row else None
    runs = [r for r in mine if not page.is_baseline(r)]
    summary = page.summarize(runs, floor_row)
    contenders = [{"rank": rank, "agent": s["key"][0], "model": s["key"][1], "settings": s["key"][2],
                   "runs": s["n"], "mean_total": num(s["total"]), "mean_above_chance": num(s["above"]),
                   "above_chance_min": num(s["lo"]), "above_chance_max": num(s["hi"]),
                   "mean_wall_seconds": num(s["secs"], 1), "mean_cost_usd": num(s["cost"])}
                  for rank, s in zip(page.ranks(summary), summary)]
    every = [{"file": r["_file"], "date": str(r.get("date", "")),
              "agent": str(r["contender"].get("agent") or ""),
              "agent_version": str(r["contender"].get("agent_version") or ""),
              "model": str(r["contender"].get("model") or ""),
              "settings": str(r["contender"].get("settings") or ""),
              "submitted_by": str(r.get("submitted_by") or ""), "seed": r.get("seed"),
              "total": num(r["total"]), "above_chance": num(page.above_value(r, floor)),
              "wall_seconds": num(r.get("wall_seconds"), 1), "cost_usd": num(r.get("cost_usd")),
              "evidence": str(r.get("evidence") or "")}
             for r in runs]
    return {"track": track, "suite": suite, "floor_file": floor_row["_file"] if floor_row else None,
            "contenders": contenders, "runs": every}


def leaderboard(rows: list[dict], notes: list[str] = ()) -> dict:
    """The whole file as a dict: rows as `page.load` returns them, notes = the files it skipped and why."""
    runs = [r for r in rows if not page.is_baseline(r)]
    tracks = [t for t in TRACKS if any(page.track_of(r) == t for r in runs)]
    tracks += sorted({page.track_of(r) for r in runs} - set(tracks))
    boards = [board(rows, t, s) for t in tracks
              for s in suite_order({page.suite_of(r) for r in runs if page.track_of(r) == t})]
    return {"schema": SCHEMA, "name": page.TITLE, "page": page.PAGE_URL, "results": page.RESULTS_URL,
            "method": page.DOC_URL,
            "ranking": "per board, contenders by mean above chance, then mean total; '=' marks a tie",
            "latest_run": max((str(r.get("date", "")) for r in runs), default=None), "runs": len(runs),
            "skipped": list(notes), "boards": boards}


def write(rows: list[dict], out_dir: Path, notes: list[str] = ()) -> Path:
    path = out_dir / NAME
    path.write_text(json.dumps(leaderboard(rows, notes), ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    return path
