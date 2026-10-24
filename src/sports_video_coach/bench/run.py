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
from . import frames as F, score as S
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

FENCE = "`" * 3
# The frames track: no code, so the agent may have no tool that writes files and ends its reply with answers.json.
# Same one-line rules as PROMPT; with Claude Code it is the prompt the leaderboard's frames rows were run with.
FRAMES_PROMPT = (
    "You are a contender in a sports film review benchmark (suite {suite}, frames track). "
    "This track measures how well you review film by eye: you get still images of {n} short videos and no way to "
    "run code. Judge by looking only. Do not try to read anything outside the given images and task text, and do "
    "not start helpers or sub-agents. Work alone, do not ask questions. "
    "End your reply with the whole answers.json (keys suite, track, answers; replace each null with your answer "
    "in the stated format) in one " + FENCE + "json block, after one line per task: your answer and how you got it. "
    "The current folder holds TASKS.md, answers.json and the images (contact sheets in sheets/, full-size stills in "
    "frames/). {read} TASKS.md first, then the images it lists."
)
CLAUDE_FRAMES = ["claude", "-p", "--restricted", "--safe-mode", "--strict-mcp-config", "--tools", "Read",
                 "--permission-prompts", "none", "--output-format", "stream-json", "--verbose"]
CLAUDE_FRAMES_SETTINGS = "frames track; claude -p --restricted --safe-mode --tools Read; default effort"

# Clean room (the default): the contender runs without the runner's own agent config, so rows from different
# machines compare like for like. Claude Code: --safe-mode drops CLAUDE.md, skills, plugins, hooks, MCP servers,
# custom agents and commands; --setting-sources project skips the user settings file (its model, effort, language,
# env); --strict-mcp-config skips every MCP config not given on the command line. The login still works.
# Codex: CODEX_HOME is a temporary folder holding only a copy of auth.json, so ~/.codex AGENTS.md, config.toml,
# skills, hooks, rules and memories are not read; the copy is deleted after the run.
CLAUDE_CLEAN = ["--safe-mode", "--setting-sources", "project", "--strict-mcp-config"]
CLEAN_ROOM = "clean-room: no user config"
MY_CONFIG = "runner's own agent config (--use-my-config)"
# The calling session's identity, never passed to the contender: an outsider's shell has none of it, and a nested
# Claude Code that inherits ORCA_* / CLAUDE_CODE_SESSION_ID reports the *caller's* session as ended when it exits.
SESSION_ENV = re.compile(r"^(ORCA_.*|CLAUDECODE|CLAUDE_PID|CLAUDE_CODE_(SESSION_ID|ENTRYPOINT|EXECPATH|CHILD_SESSION|"
                         r"SESSION_ATTENDED|MESSAGING_SOCKET|MESSAGING_TOKEN|SSE_PORT))$", re.I)


def prompt(suite: str, track: str = F.TRACK, agent: str = "") -> str:
    n = len(S.SUITES[suite].TASKS)
    if track == F.TRACK:
        return PROMPT.format(suite=suite, n=n)
    read = "Your only tool is Read: read" if agent == "claude" else "Read"
    return FRAMES_PROMPT.format(suite=suite, n=n, read=read)


def split_template(template: str) -> list[str]:
    """Split a --cmd template like a shell would, keeping Windows backslashes in paths."""
    lex = shlex.shlex(template, posix=True)
    lex.whitespace_split = True
    if os.name == "nt":
        lex.escape = ""
    return list(lex)


def command(agent: str, text: str, prompt_file: Path, model: str = "", template: str = "",
            track: str = F.TRACK, my_config: bool = False) -> list[str]:
    """The argv that runs `agent` headless on the prompt `text` (also saved in `prompt_file`). Claude Code runs
    clean-room unless `my_config` (Codex's clean room is its environment, see `agent_env`)."""
    if agent == "claude":
        if track != F.TRACK:   # --restricted already ignores every settings file; --safe-mode drops the rest
            argv = [a for a in CLAUDE_FRAMES if not (my_config and a == "--safe-mode")]
        else:
            argv = (["claude", "-p"] + ([] if my_config else CLAUDE_CLEAN) +
                    ["--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"])
        return argv + (["--model", model] if model else []) + [text]
    if agent == "codex" and track != F.TRACK:
        raise SystemExit("bench run --track frames runs Claude Code or --agent cmd; for Codex see the frames track "
                         "in docs/benchmark.md")
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


def agent_env(base: dict | None = None, codex_home: Path | None = None) -> dict:
    """The contender's environment: `base` (default os.environ) without the calling session's identity
    (SESSION_ENV), with CODEX_HOME set when a clean-room Codex home is given."""
    env = {k: v for k, v in (os.environ if base is None else base).items() if not SESSION_ENV.match(k)}
    if env.get("TERM_PROGRAM") == "Orca":
        del env["TERM_PROGRAM"]
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return env


def user_codex_home(env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else Path.home() / ".codex"


def clean_codex_home(user_home: Path) -> Path:
    """A new temporary CODEX_HOME (outside the run folder) holding only a copy of the login, auth.json."""
    import tempfile
    home = Path(tempfile.mkdtemp(prefix="svc-bench-codex-home-"))
    auth = user_home / "auth.json"
    if auth.is_file():
        shutil.copy2(auth, home / "auth.json")
    return home


def drop_codex_home(home: Path, user_home: Path) -> None:
    """Delete the temporary CODEX_HOME. If Codex refreshed the login during the run, keep the new tokens first:
    a refresh can retire the old refresh token, which would log the runner out."""
    tmp, auth = home / "auth.json", user_home / "auth.json"
    try:
        if tmp.is_file() and auth.is_file() and tmp.read_bytes() != auth.read_bytes() \
                and tmp.stat().st_mtime > auth.stat().st_mtime:
            shutil.copy2(tmp, auth)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def execute(argv: list[str], cwd: Path, transcript: Path, stderr: Path, timeout: float,
            env: dict | None = None) -> tuple[int | None, float]:
    """Run argv in cwd with stdin closed; (exit code, or None if killed at the timeout; wall seconds)."""
    kw = {"start_new_session": True} if os.name != "nt" else {}
    t0 = time.monotonic()
    with open(transcript, "wb") as out, open(stderr, "wb") as err:
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                env=agent_env() if env is None else env, **kw)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            code = None
    return code, round(time.monotonic() - t0, 1)


def claude_stats(transcript: Path) -> dict:
    """Model, version and cost from a Claude Code stream-json transcript (only what the transcript states)."""
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
            if isinstance(ev.get("claude_code_version"), str):
                out.setdefault("version", ev["claude_code_version"])
        if ev.get("type") == "result" and S.is_num(ev.get("total_cost_usd")):
            out["cost_usd"] = round(float(ev["total_cost_usd"]), 4)
    return out


def final_text(transcript: Path, agent: str) -> str:
    """The agent's last reply: Claude Code's `result` event, else the whole transcript of another CLI."""
    try:
        text = transcript.read_text(encoding="utf8", errors="replace")
    except OSError:
        return ""
    if agent != "claude":
        return text
    final = ""
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result" and isinstance(ev.get("result"), str):
            final = ev["result"]
    return final


def answers_from_reply(out: Path, text: str, suite: str, track: str) -> bool:
    """Save the last json block of the agent's reply as <out>/answers.json when the agent left that file empty
    (an agent with no file-writing tool ends with it, as TASKS.md asks). True if it was saved."""
    try:
        if any(v is not None for v in S.read_answers(out).values()):
            return False
    except (OSError, ValueError, SystemExit):
        pass
    blocks = re.findall(FENCE + r"json[ \t]*\r?\n(.*?)" + FENCE, text, re.S)
    try:
        data = json.loads(blocks[-1]) if blocks else None
    except ValueError:
        return False
    answers = data.get("answers", data) if isinstance(data, dict) else None
    if not isinstance(answers, dict):
        return False
    ids = [t.id for t in S.SUITES[suite].TASKS]
    media.write_json_atomic(out / "answers.json",
                            {"suite": suite, "track": track, "answers": {i: answers.get(i) for i in ids}})
    return True


def codex_stats(log: Path) -> dict:
    """Model and reasoning effort from the header `codex exec` prints to stderr (only what the header states)."""
    out = {}
    try:
        lines = log.read_text(encoding="utf8", errors="replace").splitlines()
    except OSError:
        return out
    seps = [i for i, line in enumerate(lines[:40]) if line.strip() == "--------"]
    for line in lines[seps[0] + 1:seps[1]] if len(seps) >= 2 else []:
        key, _, value = line.partition(":")
        if key.strip() == "model" and value.strip():
            out["model"] = value.strip()
        if key.strip() == "reasoning effort" and value.strip():
            out["effort"] = value.strip()
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
    on_track = f" {res['track']} track" if res.get("track", F.TRACK) != F.TRACK else ""
    fields = {"template": "benchmark_result.yml",
              "title": f"[Benchmark]: {c['agent']} {c['model']} on {res['suite']}{on_track} ({res['total']})"
                       .replace("  ", " "),
              "agent": c["agent"], "version": c["agent_version"], "model": c["model"],
              "settings": c["settings"] or "none", "evidence": res.get("evidence", "")}
    url = ISSUE_FORM + "?" + urlencode({k: v for k, v in fields.items() if v}, quote_via=quote)
    full = url + "&" + urlencode({"result": json.dumps(res, indent=2)}, quote_via=quote)
    return full if len(full) <= MAX_URL else url


def settings_text(agent: str, track: str, my_config: bool, given: str = "", stats: dict | None = None) -> str:
    """The result's `settings`: how the runner's own config was handled, then what was changed from defaults
    (`given`, else what the run itself states: the Codex reasoning effort, the frames track command)."""
    stats = stats or {}
    frames = agent == "claude" and track != F.TRACK
    if agent == "cmd":
        iso = ""            # a custom command runs as given: isolating it from the runner's config is the runner's job
    elif my_config:
        iso = MY_CONFIG
    else:
        iso = "" if frames else CLEAN_ROOM   # the frames command line already says --restricted --safe-mode
    auto = (f"reasoning effort {stats['effort']}" if "effort" in stats else
            CLAUDE_FRAMES_SETTINGS.replace(" --safe-mode", "" if my_config else " --safe-mode") if frames else "")
    return "; ".join(x for x in (iso, given.strip() or auto) if x)


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
    ap.add_argument("--track", default=F.TRACK, choices=F.TRACKS,
                    help="code (default): videos, any tool; frames: still images only, no code (Claude Code runs "
                         "with Read as its only tool)")
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
    ap.add_argument("--use-my-config", action="store_true",
                    help="run the agent with your own agent config (CLAUDE.md, skills, plugins, hooks, MCP servers, "
                         "user settings; ~/.codex AGENTS.md and config). Default: clean room, none of it; the result's "
                         "settings say which")
    ap.add_argument("--dry-run", action="store_true", help="print the command it would run; run nothing")
    a = ap.parse_args(argv)
    if a.timeout <= 0:
        ap.error("--timeout must be positive")
    if a.agent != "cmd" and a.cmd:
        ap.error("--cmd is only for --agent cmd")

    out = (a.out or default_out(a.name or a.agent, a.model)).resolve()
    text = prompt(a.suite, a.track, a.agent)
    prompt_file = out / "PROMPT.txt"
    argv_ = command(a.agent, text, prompt_file, a.model, a.cmd, a.track, a.use_my_config)
    codex_clean = a.agent == "codex" and not a.use_my_config
    if a.agent == "cmd":
        room = "custom command: it runs as given, so keeping your own agent config out is up to you"
    elif a.use_my_config:
        room = "your own agent config is loaded (--use-my-config)"
    else:
        room = "clean room: no user agent config" + (" (CODEX_HOME = a temporary copy of your login only)"
                                                     if codex_clean else "")
    transcript = out / ("transcript.jsonl" if a.agent == "claude" else "transcript.txt")
    if a.dry_run:
        print(f"suite {a.suite}, track {a.track}, folder {out}, timeout {a.timeout:g} s, stdin closed; {room}")
        print(subprocess.list2cmdline(argv_) if os.name == "nt" else shlex.join(argv_))
        return 0
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; pick a new --out")
    exe = resolve(argv_)
    name = a.name or AGENTS.get(a.agent) or Path(argv_[0]).stem

    what = "videos" if a.track == F.TRACK else "videos as stills"
    print(f"{a.suite}: drawing {len(S.SUITES[a.suite].TASKS)} {what} into {out}")
    from . import prepare
    prepare(out, suite=a.suite, track=a.track)
    media.write_text_atomic(prompt_file, text + "\n")
    print(f"running {name} (timeout {a.timeout:g} s; {room}) ...", flush=True)
    home = clean_codex_home(user_codex_home()) if codex_clean else None
    try:
        code, wall = execute(exe, out, transcript, out / "stderr.log", a.timeout, agent_env(codex_home=home))
    finally:
        if home is not None:
            drop_codex_home(home, user_codex_home())
    status = f"killed at the {a.timeout:g} s timeout" if code is None else f"exit code {code}"
    print(f"agent finished in {wall:g} s, {status}; transcript {transcript}")

    stats = (claude_stats(transcript) if a.agent == "claude"
             else codex_stats(out / "stderr.log") if a.agent == "codex" else {})
    model = a.model or stats.get("model", "")
    settings = settings_text(a.agent, a.track, a.use_my_config, a.settings, stats)
    if a.track != F.TRACK and answers_from_reply(out, final_text(transcript, a.agent), a.suite, a.track):
        print("answers.json: saved from the json block at the end of the agent's reply")
    version = stats.get("version") or (agent_version(exe[0]) if a.agent != "cmd" else "")
    try:
        answers = S.read_answers(out)
    except (OSError, ValueError, SystemExit) as e:   # a missing or broken answers.json scores 0, like an empty one
        print(f"answers.json could not be read ({e}); every task scores 0")
        answers = {}
    res = S.result(answers, name, model, version, settings, a.by.strip(),
                   int(wall) if wall == int(wall) else wall, a.evidence.strip(), suite=a.suite, track=a.track)
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
