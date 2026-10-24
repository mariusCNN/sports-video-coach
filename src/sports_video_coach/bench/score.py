"""Scoring and validation of benchmark result files (schema 1, suite `svc-bench-1`).

Per-task score, 0..1, rounded to 3 decimals:
- count: max(0, 1 - |answer - truth| / truth).
- rate: 1 within 2 % of the truth, falling linearly to 0 at 20 % off.
- timestamps: answers are matched one-to-one to truth events in time order (the order-keeping matching with the
  most credit); a matched event scores 1 when |error| <= 0.5 s, falling linearly to 0 at 2 s; a missed event
  scores 0. The credit sum is divided by max(len(truth), len(answer)), so extra answers cost as much as missed
  events.
- outcomes: the fraction of positions where the answer equals the truth, over max(len(truth), len(answer)).
A missing (null) or malformed answer scores 0. total = mean task score, rounded to 3 decimals.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .suite import BY_ID, KINDS, SUITE, TASKS

SCHEMA = 1
TOL = 0.0005  # validate: a stored score may differ from the re-score by rounding only


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def score_count(truth: int, answer) -> tuple[float, str]:
    if not is_num(answer):
        return 0.0, "not a number"
    err = abs(answer - truth)
    return max(0.0, 1 - err / truth), ("exact" if err == 0 else f"off by {err:g}")


def score_rate(truth: float, answer) -> tuple[float, str]:
    if not is_num(answer):
        return 0.0, "not a number"
    rel = abs(answer - truth) / truth
    s = 1.0 if rel <= 0.02 else 0.0 if rel >= 0.2 else 1 - (rel - 0.02) / 0.18
    return s, f"{rel * 100:.1f}% off"


def event_credit(err: float) -> float:
    return 1.0 if err <= 0.5 else 0.0 if err >= 2.0 else (2.0 - err) / 1.5


def score_timestamps(truth: list[float], answer) -> tuple[float, str]:
    if not isinstance(answer, list) or not all(is_num(a) for a in answer):
        return 0.0, "not a list of seconds"
    a = sorted(float(x) for x in answer)
    n, m = len(truth), len(a)
    # best[i][j]: most credit matching truth[:i] with a[:j], order kept (an LCS-style alignment)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best[i][j] = max(best[i - 1][j], best[i][j - 1],
                             best[i - 1][j - 1] + event_credit(abs(truth[i - 1] - a[j - 1])))
    denom = max(n, m)
    close = sum(1 for t in truth if any(abs(t - x) <= 0.5 for x in a))
    return (best[n][m] / denom if denom else 1.0), f"{close} of {n} within 0.5 s, {m} answered"


def score_outcomes(truth: list[str], answer) -> tuple[float, str]:
    if not isinstance(answer, list):
        return 0.0, "not a list"
    norm = [str(x).strip().lower() if x is not None else None for x in answer]
    right = sum(1 for t, x in zip(truth, norm) if t == x)
    return right / max(len(truth), len(norm)), f"{right} of {len(truth)} right, {len(norm)} answered"


SCORERS = {"count": score_count, "rate": score_rate, "timestamps": score_timestamps, "outcomes": score_outcomes}
assert set(SCORERS) == set(KINDS)


def score_task(task_id: str, answer) -> dict:
    """One task row of a result file."""
    t = BY_ID[task_id]
    if answer is None:
        s, note = 0.0, "missing answer"
    else:
        s, note = SCORERS[t.kind](t.truth, answer)
    return {"id": t.id, "kind": t.kind, "truth": t.truth, "answer": answer, "score": round(s, 3), "note": note}


def total(rows: list[dict]) -> float:
    return round(sum(r["score"] for r in rows) / len(rows), 3) if rows else 0.0


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def tool_version() -> str:
    try:
        from importlib.metadata import version
        return version("sports-video-coach")
    except Exception:  # an uninstalled checkout
        return ""


def read_answers(folder: Path) -> dict:
    """{task id: answer} from <folder>/answers.json (unknown ids are an error, missing ones are null)."""
    p = Path(folder) / "answers.json"
    if not p.exists():
        raise SystemExit(f"{p} not found: run `sports-video-coach bench prepare --out {folder}` first")
    data = json.loads(p.read_text(encoding="utf8"))
    if data.get("suite", SUITE) != SUITE:
        raise SystemExit(f"{p} is for suite {data.get('suite')!r}, this tool scores {SUITE!r}")
    answers = data.get("answers", {})
    if not isinstance(answers, dict):
        raise SystemExit(f"{p}: `answers` must be an object of task id -> answer")
    unknown = sorted(set(answers) - set(BY_ID))
    if unknown:
        raise SystemExit(f"{p}: unknown task ids {unknown}; the suite has {list(BY_ID)}")
    return {t.id: answers.get(t.id) for t in TASKS}


def result(answers: dict, agent: str, model: str, agent_version: str = "", settings: str = "", by: str = "",
           wall_seconds: float | None = None, evidence: str = "", date: str | None = None) -> dict:
    rows = [score_task(t.id, answers.get(t.id)) for t in TASKS]
    return {"schema": SCHEMA, "suite": SUITE, "tool_version": tool_version(),
            "date": date or dt.date.today().isoformat(),
            "contender": {"agent": agent, "agent_version": agent_version, "model": model, "settings": settings},
            "submitted_by": by, "tasks": rows, "total": total(rows),
            "wall_seconds": wall_seconds, "evidence": evidence}


def default_path(res: dict) -> Path:
    c = res["contender"]
    name = "-".join(x for x in (res["date"], slug(c["agent"]), slug(c["model"])) if x)
    return Path("benchmark") / "results" / f"{name}.json"


def table(res: dict) -> str:
    c = res["contender"]
    head = f"{c['agent']}" + (f" {c['agent_version']}" if c["agent_version"] else "") + \
           (f" / {c['model']}" if c["model"] else "") + (f" ({c['settings']})" if c["settings"] else "")
    w = max(len(r["id"]) for r in res["tasks"])
    lines = [f"{SUITE}: {head}", ""]
    lines += [f"  {r['id']:{w}s}  {r['kind']:10s}  {r['score']:.3f}  {r['note']}" for r in res["tasks"]]
    lines += ["", f"  {'total':{w}s}  {'':10s}  {res['total']:.3f}"]
    return "\n".join(lines)


def problems(res) -> list[str]:
    """Why a result file is not a valid, honestly scored schema-1 file ([] when it is)."""
    if not isinstance(res, dict):
        return ["not a JSON object"]
    out = []
    if res.get("schema") != SCHEMA:
        out.append(f"schema is {res.get('schema')!r}, expected {SCHEMA}")
    if res.get("suite") != SUITE:
        out.append(f"suite is {res.get('suite')!r}, expected {SUITE!r}")
    try:
        dt.date.fromisoformat(str(res.get("date")))
    except ValueError:
        out.append(f"date {res.get('date')!r} is not an ISO date")
    c = res.get("contender")
    if not isinstance(c, dict):
        out.append("contender missing")
    else:
        for k in ("agent", "agent_version", "model", "settings"):
            if not isinstance(c.get(k), str):
                out.append(f"contender.{k} must be a string")
        if isinstance(c.get("agent"), str) and not c["agent"].strip():
            out.append("contender.agent is empty")
    for k in ("tool_version", "submitted_by", "evidence"):
        if not isinstance(res.get(k, ""), str):
            out.append(f"{k} must be a string")
    ws = res.get("wall_seconds")
    if ws is not None and (not is_num(ws) or ws < 0):
        out.append("wall_seconds must be a non-negative number or null")
    rows = res.get("tasks")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return out + ["tasks must be a list of objects"]
    ids = [r.get("id") for r in rows]
    if sorted(map(str, ids)) != sorted(BY_ID):
        out.append(f"tasks {ids} do not match the suite's {list(BY_ID)}")
    for r in rows:
        if r.get("id") not in BY_ID:
            continue
        want = score_task(r["id"], r.get("answer"))
        for k in ("kind", "truth"):
            if r.get(k) != want[k]:
                out.append(f"{r['id']}: {k} is {r.get(k)!r}, the suite says {want[k]!r}")
        if not is_num(r.get("score")) or abs(r["score"] - want["score"]) > TOL:
            out.append(f"{r['id']}: score is {r.get('score')!r}, re-scoring the answer gives {want['score']}")
    if len(ids) == len(BY_ID) and not out:
        want_total = total([score_task(r["id"], r.get("answer")) for r in rows])
        if not is_num(res.get("total")) or abs(res["total"] - want_total) > TOL:
            out.append(f"total is {res.get('total')!r}, re-scoring gives {want_total}")
    elif not is_num(res.get("total")):
        out.append("total must be a number")
    return out


def validate_file(p: Path) -> list[str]:
    try:
        res = json.loads(Path(p).read_text(encoding="utf8"))
    except (OSError, ValueError) as e:
        return [f"cannot read: {e}"]
    return problems(res)
