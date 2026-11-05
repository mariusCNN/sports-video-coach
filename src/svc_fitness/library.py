"""The exercise library (library/exercises.json): exercises, muscles, patterns, cues, faults, doses, sport transfer.

Stage `library [ID|ALIAS ...] [--check] [--json]`: no argument lists every exercise; ids or aliases print their cards;
--check validates the file (exit 1 on a problem).
"""
from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

FILE = Path(__file__).parent / "library" / "exercises.json"
METRICS = ("depth", "trunk_lean", "tempo", "bar_path", "knee_travel", "hip_extension", "knee_valgus", "symmetry",
           "rep_count", "pause", "velocity_loss", "ground_contact", "pelvis_drop")
VIEWS = ("side", "front", "back", "oblique")


@lru_cache(maxsize=4)
def load(path: Path = FILE) -> dict:
    """The library json, read once."""
    return json.loads(Path(path).read_text(encoding="utf8"))


def exercises(lib: dict | None = None) -> dict[str, dict]:
    """id -> exercise."""
    return {e["id"]: e for e in (lib or load())["exercises"]}


def find(name: str, lib: dict | None = None) -> dict | None:
    """The exercise whose id, zh, en or alias is `name` (case and spacing ignored), else None."""
    key = _norm(name)
    for e in (lib or load())["exercises"]:
        if key in {_norm(x) for x in [e["id"], e.get("zh", ""), e.get("en", ""), *e.get("aliases", [])] if x}:
            return e
    return None


def _norm(s: str) -> str:
    return "".join(str(s).lower().replace("_", " ").replace("-", " ").split())


def muscle_load(sets: list[dict], lib: dict | None = None) -> dict[str, float]:
    """Muscle -> share (sums to 100) of the session's training emphasis: each set's exercise muscle shares weighted
    by its reps (unknown reps count 1 set = 5 reps). Sets without a library exercise are left out."""
    ex, total = exercises(lib), {}
    for s in sets:
        e = ex.get(s.get("exercise"))
        if not e:
            continue
        reps = s.get("reps") if isinstance(s.get("reps"), (int, float)) and s.get("reps") > 0 else 5
        for m in e.get("muscles", []):
            total[m["m"]] = total.get(m["m"], 0.0) + m["share"] * reps
    s = sum(total.values())
    return {k: round(100 * v / s, 1) for k, v in sorted(total.items(), key=lambda kv: -kv[1])} if s else {}


def valid_metrics(exercise: dict, view: str) -> list[str]:
    """The metric keys a 2D video from `view` can measure for this exercise (exercises.json `views`)."""
    return list((exercise.get("views") or {}).get(view, []))


def check(lib: dict) -> list[str]:
    """Problems in the library: duplicate ids, unknown muscles / patterns / metrics / refs, shares not summing to 100."""
    errs, ids = [], [e.get("id") for e in lib.get("exercises", [])]
    muscles, patterns = lib.get("muscles", {}), lib.get("patterns", {})
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errs.append(f"duplicate ids: {', '.join(map(str, dup))}")
    for e in lib.get("exercises", []):
        i = e.get("id")
        for k in ("zh", "en", "pattern", "muscles", "cues"):
            if not e.get(k):
                errs.append(f"{i}: `{k}` is empty")
        if e.get("pattern") and e["pattern"] not in patterns:
            errs.append(f"{i}: unknown pattern {e['pattern']!r}")
        shares = [m.get("share", 0) for m in e.get("muscles", [])]
        if shares and abs(sum(shares) - 100) > 0.5:
            errs.append(f"{i}: muscle shares sum to {sum(shares)}, not 100")
        errs += [f"{i}: unknown muscle {m.get('m')!r}" for m in e.get("muscles", []) if m.get("m") not in muscles]
        for view, keys in (e.get("views") or {}).items():
            if view not in VIEWS:
                errs.append(f"{i}: unknown view {view!r}")
            errs += [f"{i}: unknown metric {k!r} ({view})" for k in keys if k not in METRICS]
        errs += [f"{i}: fault metric {f.get('metric')!r} unknown" for f in e.get("faults", [])
                 if f.get("metric") and f["metric"] not in METRICS]
        errs += [f"{i}: {k} {x!r} is not an exercise id" for k in ("regress", "progress") for x in e.get(k, [])
                 if x not in ids]
    return errs


def card(e: dict, lib: dict | None = None) -> str:
    """One exercise as short markdown (what the agent reads when writing about it)."""
    lib = lib or load()
    mus = lib["muscles"]
    lines = [f"## {e['zh']} ({e['en']}) `{e['id']}`", f"- pattern: {lib['patterns'][e['pattern']]['zh']}",
             "- muscles: " + ", ".join(f"{mus[m['m']]['zh']} {m['share']}%" for m in e["muscles"])
             + (f" ({e['muscles_basis']})" if e.get("muscles_basis") else ""),
             "- cues: " + " / ".join(e.get("cues", []))]
    for f in e.get("faults", []):
        lines.append(f"- fault {f['zh']}: {f.get('see', '')} -> {f.get('fix', '')}"
                     + (f" [metric {f['metric']}]" if f.get("metric") else ""))
    for k in ("knee", "back"):
        if e.get(k):
            lines.append(f"- {k}: {e[k]}")
    if e.get("basketball"):
        lines.append(f"- basketball: {e['basketball'].get('why', '')} ({e['basketball'].get('when', '')})")
    if e.get("dose"):
        lines.append("- dose: " + "; ".join(f"{k} {v}" for k, v in e["dose"].items()))
    if e.get("refs"):
        lines.append("- refs: " + ", ".join(e["refs"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach fitness:library", description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="*", help="exercise ids or aliases (none: list them all)")
    ap.add_argument("--check", action="store_true", help="validate library/exercises.json")
    ap.add_argument("--json", action="store_true", help="print the exercises as json")
    a = ap.parse_args(argv)
    lib = load()
    if a.check:
        errs = check(lib)
        print("\n".join(errs) if errs else f"library OK: {len(lib['exercises'])} exercises, "
              f"{len(lib['muscles'])} muscles")
        sys.exit(1 if errs else 0)
    if not a.names:
        for e in lib["exercises"]:
            print(f"{e['id']:24} {e['zh']} / {e['en']} ({e['pattern']})")
        return
    found = [(n, find(n, lib)) for n in a.names]
    missing = [n for n, e in found if not e]
    if a.json:
        print(json.dumps([e for _, e in found if e], ensure_ascii=False, indent=1))
    else:
        print("\n\n".join(card(e, lib) for _, e in found if e))
    if missing:
        sys.exit(f"not in the library: {', '.join(missing)} (`sports-video-coach fitness:library` lists them)")


if __name__ == "__main__":
    main()
