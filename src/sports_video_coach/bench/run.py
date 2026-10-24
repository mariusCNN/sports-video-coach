"""`sports-video-coach bench run`: prepare a suite, run one agent on it headless, score it, in one command.

The agent runs in a fresh folder with stdin closed and is killed at the timeout. Its transcript stays in the folder.
The wall time is measured here; the cost is read from the agent's own output when it reports one (Claude Code's
`result` event), never estimated.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, quote

from .. import media
from . import score as S
from .suite import SUITE

ISSUE_FORM = "https://github.com/mariusDing/sports-video-coach/issues/new"
MAX_URL = 7500           # GitHub rejects much longer prefilled URLs; past this the result is pasted by hand
AGENTS = {"claude": "Claude Code", "codex": "Codex"}

# One line, no double quotes or percent signs: it is passed as one argument, also through Windows .cmd shims.
PROMPT = (
    "You are a contender in a sports film review benchmark (suite {suite}). "
    "The current folder holds {n} short videos, TASKS.md and answers.json. "
    "Read TASKS.md and follow its rules exactly: watch the videos (frames, ffmpeg, OpenCV or any script you write "
    "on the video files in this folder), then replace each null in answers.json with your answer in the stated "
    "format. "
    "Do not read the sports-video-coach package source, its git history, or any truth or result file anywhere on "
    "this machine. Work only inside this folder (temporary files under this folder are fine). "
    "Work alone, do not ask questions, and finish when answers.json is filled and parses as JSON. "
    "End with one line per task: your answer and how you got it."
)


def prompt(suite: str) -> str:
    return PROMPT.format(suite=suite, n=len(S.SUITES[suite].TASKS))


def split_template(template: str) -> list[str]:
    """Split a --cmd template like a shell would, keeping Windows backslashes in paths."""
    lex = shlex.shlex(template, posix=True)
    lex.whitespace_split = True
    if os.name == "nt":
        lex.escape = ""
    return list(lex)


def command(agent: str, text: str, prompt_file: Path, model: str = "", template: str = "") -> list[str]:
    """The argv that runs `agent` headless on the prompt `text` (also saved in `prompt_file`)."""
    if agent == "claude":
        argv = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"]
        return argv + (["--model", model] if model else []) + [text]
    if agent == "codex":
        argv = ["codex", "exec", "-c", "check_for_update_on_startup=false", "--skip-git-repo-check",
                "-s", "workspace-write"]
        return argv + (["--model", model] if model else []) + [text]
    if not template.strip():
        raise SystemExit("--agent cmd needs --cmd \"<command line with {prompt} or {prompt_file}>\"")
    if "{prompt}" not in template and "{prompt_file}" not in template:
        raise SystemExit("--cmd must contain {prompt} or {prompt_file}")
    subs = {"{prompt}": text, "{prompt_file}": str(prompt_file), "{model}": model}
    out = []
    for tok in split_template(template):
        for k, v in subs.items():
            tok = tok.replace(k, v)
        out.append(tok)
    return out


def resolve(argv: list[str]) -> list[str]:
    """argv with its program found on PATH (on Windows this finds `.cmd` / `.exe` shims)."""
    exe = shutil.which(argv[0])
    if not exe:
        raise SystemExit(f"{argv[0]!r} is not on PATH")
    return [exe] + argv[1:]


def kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def execute(argv: list[str], cwd: Path, transcript: Path, stderr: Path, timeout: float) -> tuple[int | None, float]:
    """Run argv in cwd with stdin closed; (exit code, or None if killed at the timeout; wall seconds)."""
    kw = {"start_new_session": True} if os.name != "nt" else {}
    t0 = time.monotonic()
    with open(transcript, "wb") as out, open(stderr, "wb") as err:
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, **kw)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            code = None
    return code, round(time.monotonic() - t0, 1)


def claude_stats(transcript: Path) -> dict:
    """Model and cost from a Claude Code stream-json transcript (only what the transcript states)."""
    out = {}
    try:
        lines = transcript.read_text(encoding="utf8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init" and isinstance(ev.get("model"), str):
            out.setdefault("model", ev["model"])
        if ev.get("type") == "result" and S.is_num(ev.get("total_cost_usd")):
            out["cost_usd"] = round(float(ev["total_cost_usd"]), 4)
    return out


def agent_version(argv0: str) -> str:
    try:
        p = subprocess.run([argv0, "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"\d+\.\d+(?:\.\d+)?\S*", p.stdout or "")
    return m.group(0) if m else ""


def issue_url(res: dict) -> str:
    """A prefilled benchmark_result issue form URL (the result file is left out if it would make it too long)."""
    c = res["contender"]
    fields = {"template": "benchmark_result.yml",
              "title": f"[Benchmark]: {c['agent']} {c['model']} on {res['suite']} ({res['total']})".replace("  ", " "),
              "agent": c["agent"], "version": c["agent_version"], "model": c["model"],
              "settings": c["settings"] or "none", "evidence": res.get("evidence", "")}
    url = ISSUE_FORM + "?" + urlencode({k: v for k, v in fields.items() if v}, quote_via=quote)
    full = url + "&" + urlencode({"result": json.dumps(res, indent=2)}, quote_via=quote)
    return full if len(full) <= MAX_URL else url


def default_out(agent: str, model: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    name = "-".join(x for x in (S.slug(agent), S.slug(model), stamp) if x)
    return Path.home() / "svc-bench-runs" / name


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="sports-video-coach bench run",
        description="Prepare a suite, run one agent on it headless (stdin closed, killed at the timeout), "
                    "score it and print the result file and a prefilled issue form link.")
    ap.add_argument("--suite", default=SUITE, choices=sorted(S.SUITES), help=f"default {SUITE}")
    ap.add_argument("--agent", required=True, choices=["claude", "codex", "cmd"],
                    help="claude (Claude Code), codex (Codex CLI) or cmd (any other CLI, with --cmd)")
    ap.add_argument("--model", default="", help="passed to the agent CLI as --model (and {model} in --cmd)")
    ap.add_argument("--cmd", default="",
                    help='for --agent cmd: the command line, with {prompt} (the prompt text) or {prompt_file} '
                         '(a file holding it), e.g. "gemini -y -p {prompt}"')
    ap.add_argument("--name", default="", help="agent name for the result (default: Claude Code, Codex, or the "
                                               "program of --cmd)")
    ap.add_argument("--out", type=Path, default=None,
                    help="run folder, must be new or empty (default ~/svc-bench-runs/<agent>-<model>-<time>)")
    ap.add_argument("--timeout", type=float, default=1200, help="kill the agent after this many seconds (1200)")
    ap.add_argument("--settings", default="", help='what you changed from defaults, e.g. "effort high"')
    ap.add_argument("--by", default="", help="your GitHub handle")
    ap.add_argument("--evidence", default="", help="URL of the transcript, if you publish it")
    ap.add_argument("--dry-run", action="store_true", help="print the command it would run; run nothing")
    a = ap.parse_args(argv)
    if a.timeout <= 0:
        ap.error("--timeout must be positive")
    if a.agent != "cmd" and a.cmd:
        ap.error("--cmd is only for --agent cmd")

    out = (a.out or default_out(a.name or a.agent, a.model)).resolve()
    text = prompt(a.suite)
    prompt_file = out / "PROMPT.txt"
    argv_ = command(a.agent, text, prompt_file, a.model, a.cmd)
    transcript = out / ("transcript.jsonl" if a.agent == "claude" else "transcript.txt")
    if a.dry_run:
        print(f"suite {a.suite}, folder {out}, timeout {a.timeout:g} s, stdin closed")
        print(subprocess.list2cmdline(argv_) if os.name == "nt" else shlex.join(argv_))
        return 0
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; pick a new --out")
    exe = resolve(argv_)
    name = a.name or AGENTS.get(a.agent) or Path(argv_[0]).stem

    print(f"{a.suite}: drawing {len(S.SUITES[a.suite].TASKS)} videos into {out}")
    from . import prepare
    prepare(out, suite=a.suite)
    media.write_text_atomic(prompt_file, text + "\n")
    print(f"running {name} (timeout {a.timeout:g} s) ...", flush=True)
    code, wall = execute(exe, out, transcript, out / "stderr.log", a.timeout)
    status = f"killed at the {a.timeout:g} s timeout" if code is None else f"exit code {code}"
    print(f"agent finished in {wall:g} s, {status}; transcript {transcript}")

    stats = claude_stats(transcript) if a.agent == "claude" else {}
    model = a.model or stats.get("model", "")
    version = agent_version(exe[0]) if a.agent != "cmd" else ""
    try:
        answers = S.read_answers(out)
    except (OSError, ValueError, SystemExit) as e:   # a missing or broken answers.json scores 0, like an empty one
        print(f"answers.json could not be read ({e}); every task scores 0")
        answers = {}
    res = S.result(answers, name, model, version, a.settings.strip(), a.by.strip(),
                   int(wall) if wall == int(wall) else wall, a.evidence.strip(), suite=a.suite)
    res["cost_usd"] = stats.get("cost_usd")
    run_info = {"exit_code": code, "timed_out": code is None, "timeout_seconds": a.timeout}
    media.write_json_atomic(out / "run.json", run_info)
    dest = out / S.default_path(res).name
    media.write_json_atomic(dest, res)
    print(S.table(res))
    if res["cost_usd"] is not None:
        print(f"cost: {res['cost_usd']} USD (from the agent's result event)")
    print(f"\nresult file: {dest}")
    print("submit it: copy it to benchmark/results/ in a pull request, or open the prefilled issue form:")
    print(issue_url(res))
    return 0
