"""`sports-video-coach bench run`: prepare a suite, run one agent on it headless, score it, in one command.

The agent runs in a fresh folder with stdin closed and is killed at the timeout. Its transcript stays in the folder,
next to a redacted copy that is safe to publish (`bench transcript`).
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
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, quote

from .. import media
from . import frames as F, score as S
from .suite import SUITE

ISSUE_FORM = "https://github.com/mariusDing/sports-video-coach/issues/new"
MAX_URL = 7500           # GitHub rejects much longer prefilled URLs; past this the result is pasted by hand
AGENTS = {"claude": "Claude Code", "codex": "Codex"}


@dataclass(frozen=True)
class Preset:
    """A headless command line for one more agent CLI, built only from its own docs. In `argv`, PROMPT_ARG and
    PROMPT_FILE_ARG become the prompt text / the file holding it, MODEL_ARG becomes `model_flag <model>` or nothing."""
    name: str
    argv: tuple[str, ...]
    model_flag: str
    version: tuple[str, ...]      # prints the CLI's version
    docs: str                     # where the flags are documented (read on DOCS_READ)
    config: str = "runner's own config"   # how much of the runner's own agent config it loads
    note: str = ""


PROMPT_ARG, PROMPT_FILE_ARG, MODEL_ARG = "{prompt}", "{prompt_file}", "{model}"
DOCS_READ = "2026-10-25"
UNTESTED = "preset, not run by the maintainer"
# Every flag below is from the linked docs, read on DOCS_READ. None of these CLIs was installed or run here (the
# tests use fake binaries), so the presets are untested against the real CLIs. None of them documents a way to be
# limited to reading files the way Claude Code's --tools Read is, so no preset runs the frames track.
PRESETS = {
    # https://geminicli.com/docs/cli/cli-reference/ : -p/--prompt forces non-interactive mode, --approval-mode yolo
    # auto-approves every action (-y/--yolo is deprecated for it), -m/--model, -v/--version. Plan mode
    # (https://geminicli.com/docs/cli/plan-mode) is not file-read only: it searches the web, and in a headless run
    # it switches to YOLO once the plan is approved.
    "gemini": Preset("Gemini CLI", ("gemini", "--approval-mode", "yolo", MODEL_ARG, "-p", PROMPT_ARG), "--model",
                     ("gemini", "--version"), "https://geminicli.com/docs/cli/cli-reference/",
                     note="Google moved individual users to Antigravity CLI on 2026-06-18; API-key and Code Assist "
                          "users keep Gemini CLI"),
    # https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/ : -p headless, --approval-mode yolo,
    # -m/--model, --safe-mode drops context files, hooks, extensions, skills, MCP servers and custom subagents
    # (the approval mode still applies).
    "qwen": Preset("Qwen Code", ("qwen", "--safe-mode", "--approval-mode", "yolo", MODEL_ARG, "-p", PROMPT_ARG),
                   "--model", ("qwen", "--version"),
                   "https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/",
                   config="--safe-mode: no context files, hooks, extensions, skills, MCP servers or subagents"),
    # https://aider.chat/docs/config/options.html : --message-file sends one message and exits, --yes-always says
    # yes to every confirmation, --no-git (the run folder is no repo), --no-check-update, --no-pretty,
    # --no-stream, --read adds a read-only file, file arguments are the files it may edit, --model, --version.
    # Scripting: https://aider.chat/docs/scripting.html
    "aider": Preset("Aider", ("aider", "--yes-always", "--no-git", "--no-check-update", "--no-pretty", "--no-stream",
                              MODEL_ARG, "--read", "TASKS.md", "--message-file", PROMPT_FILE_ARG, "answers.json"),
                    "--model", ("aider", "--version"), "https://aider.chat/docs/config/options.html",
                    note="it edits answers.json; whether --yes-always also runs the shell commands it suggests is "
                         "not stated in the docs"),
    # https://opencode.ai/docs/cli/ : `opencode run [message]` is the non-interactive mode, --auto auto-approves
    # permissions that are not explicitly denied, -m/--model provider/model, -v/--version.
    "opencode": Preset("OpenCode", ("opencode", "run", "--auto", MODEL_ARG, PROMPT_ARG), "--model",
                       ("opencode", "--version"), "https://opencode.ai/docs/cli/",
                       note="--model takes provider/model"),
    # https://cursor.com/docs/cli/reference/parameters : the CLI is `agent`; -p/--print for scripts, --force (alias
    # --yolo) applies changes and allows commands not explicitly denied, --trust trusts the folder (headless only),
    # --output-format text, --model, -v/--version. Headless use: https://cursor.com/docs/cli/headless
    "cursor": Preset("Cursor CLI", ("agent", "-p", "--force", "--trust", "--output-format", "text", MODEL_ARG,
                                    PROMPT_ARG), "--model", ("agent", "--version"),
                     "https://cursor.com/docs/cli/reference/parameters"),
    # https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically :
    # -p/--prompt, --allow-all-tools (in its examples), --no-ask-user (no clarifying questions), -s (silent: no
    # session metadata), --model. `copilot version` is in the command reference
    # (https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).
    "copilot": Preset("GitHub Copilot CLI", ("copilot", "-p", PROMPT_ARG, "--allow-all-tools", "--no-ask-user",
                                             "-s", MODEL_ARG), "--model", ("copilot", "version"),
                      "https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/"
                      "run-cli-programmatically"),
    # https://goose-docs.ai/docs/guides/goose-cli-commands : `goose run -t TEXT` runs one prompt and exits,
    # --no-session stores no session file, --model, --version. Tool approval: Autonomous mode is the default
    # (https://goose-docs.ai/docs/guides/goose-permissions); the preset sets nothing, so your own GOOSE_MODE applies.
    "goose": Preset("Goose", ("goose", "run", "--no-session", MODEL_ARG, "-t", PROMPT_ARG), "--model",
                    ("goose", "--version"), "https://goose-docs.ai/docs/guides/goose-cli-commands",
                    note="tool approval follows your GOOSE_MODE (Autonomous by default)"),
}

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

# Clean room (the default for Claude Code): the contender runs without the runner's own agent config, so rows from
# different machines compare like for like. --safe-mode drops CLAUDE.md, skills, plugins, hooks, MCP servers,
# custom agents and commands; --setting-sources project skips the user settings file (its model, effort, language,
# env); --strict-mcp-config skips every MCP config not given on the command line. The login still works, and no
# file is copied or written. Codex is not isolated: it runs with the runner's own CODEX_HOME (~/.codex), because
# isolating it would mean copying its login (auth.json) somewhere else; bench run never touches credential files.
CLAUDE_CLEAN = ["--safe-mode", "--setting-sources", "project", "--strict-mcp-config"]
CLEAN_ROOM = "clean-room: no user config"
MY_CONFIG = "runner's own agent config (--use-my-config)"
CODEX_OWN = "Codex: runner's own config; not isolated, so credentials stay where they are"
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
    clean-room unless `my_config`. Codex always runs with the runner's own config, so `my_config` changes nothing."""
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
    if agent in PRESETS:
        p = PRESETS[agent]
        if track != F.TRACK:
            raise SystemExit(f"--agent {agent}: {p.name} documents no way to be limited to reading files, so its "
                             "preset does not run the frames track. Use --agent cmd --cmd \"...\" with a read-only "
                             "command line you trust, or bench prepare and bench score by hand")
        out = []
        for tok in p.argv:
            if tok == MODEL_ARG:
                out += [p.model_flag, model] if model else []
            else:
                out.append(text if tok == PROMPT_ARG else str(prompt_file) if tok == PROMPT_FILE_ARG else tok)
        return out
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


def agent_env(base: dict | None = None) -> dict:
    """The contender's environment: `base` (default os.environ) without the calling session's identity
    (SESSION_ENV). Everything else, CODEX_HOME and logins included, is passed on unchanged."""
    env = {k: v for k, v in (os.environ if base is None else base).items() if not SESSION_ENV.match(k)}
    if env.get("TERM_PROGRAM") == "Orca":
        del env["TERM_PROGRAM"]
    return env


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


def shown(agent: str) -> str:
    """A preset's command line for people: the prompt as <prompt>, the model flag in brackets."""
    p = PRESETS[agent]
    return " ".join(f"[{p.model_flag} M]" if t == MODEL_ARG else "<prompt>" if t == PROMPT_ARG else
                    "<prompt file>" if t == PROMPT_FILE_ARG else t for t in p.argv)


def agent_version(argv0: str, args: tuple[str, ...] = ("--version",)) -> str:
    try:
        p = subprocess.run([argv0, *args], stdin=subprocess.DEVNULL, capture_output=True, text=True,
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
    elif agent in PRESETS:
        iso = f"{UNTESTED} (--agent {agent}); {PRESETS[agent].config}"
    elif agent == "codex":
        iso = CODEX_OWN     # never isolated: that would mean copying its login
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
    ap.add_argument("--agent", required=True, choices=["claude", "codex", *PRESETS, "cmd"],
                    help="claude (Claude Code), codex (Codex CLI), a preset for another CLI (" +
                         ", ".join(f"{k}: {p.name}" for k, p in PRESETS.items()) + "; built from each CLI's docs "
                         "and NOT run by the maintainer, so untested against the real CLI; code track only), or "
                         "cmd (any other CLI, with --cmd)")
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
    ap.add_argument("--evidence", default="", help="URL of the transcript, if you publish it (publish the redacted "
                                                   "copy, transcript.redacted.*)")
    ap.add_argument("--use-my-config", action="store_true",
                    help="run Claude Code with your own agent config (CLAUDE.md, skills, plugins, hooks, MCP "
                         "servers, user settings). Default: clean room, none of it; the result's settings say which. "
                         "Codex always runs with your own config (~/.codex), so this changes nothing for it")
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
    if a.agent == "cmd":
        room = "custom command: it runs as given, so keeping your own agent config out is up to you"
    elif a.agent in PRESETS:
        p = PRESETS[a.agent]
        room = (f"{p.name} {UNTESTED}, untested against the real CLI (flags from {p.docs}); {p.config}"
                + (f"; {p.note}" if p.note else ""))
    elif a.agent == "codex":
        room = "Codex runs with your own config (~/.codex): not isolated, so credentials stay where they are"
    elif a.use_my_config:
        room = "your own agent config is loaded (--use-my-config)"
    else:
        room = "clean room: no user agent config"
    transcript = out / ("transcript.jsonl" if a.agent == "claude" else "transcript.txt")
    if a.dry_run:
        print(f"suite {a.suite}, track {a.track}, folder {out}, timeout {a.timeout:g} s, stdin closed; {room}")
        print(subprocess.list2cmdline(argv_) if os.name == "nt" else shlex.join(argv_))
        return 0
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; pick a new --out")
    exe = resolve(argv_)
    name = a.name or AGENTS.get(a.agent) or (PRESETS[a.agent].name if a.agent in PRESETS else
                                             Path(argv_[0]).stem)

    what = "videos" if a.track == F.TRACK else "videos as stills"
    print(f"{a.suite}: drawing {len(S.SUITES[a.suite].TASKS)} {what} into {out}")
    from . import prepare
    prepare(out, suite=a.suite, track=a.track)
    media.write_text_atomic(prompt_file, text + "\n")
    print(f"running {name} (timeout {a.timeout:g} s; {room}) ...", flush=True)
    code, wall = execute(exe, out, transcript, out / "stderr.log", a.timeout, agent_env())
    status = f"killed at the {a.timeout:g} s timeout" if code is None else f"exit code {code}"
    print(f"agent finished in {wall:g} s, {status}; transcript {transcript}")
    if transcript.exists():
        from .transcript import default_dst, redact
        try:
            print(f"redacted copy to publish (read it first): {redact(transcript, default_dst(transcript))}")
        except OSError as e:     # the run and its score matter more than the copy
            print(f"could not write the redacted copy ({e}); `sports-video-coach bench transcript` makes one")

    stats = (claude_stats(transcript) if a.agent == "claude"
             else codex_stats(out / "stderr.log") if a.agent == "codex" else {})
    model = a.model or stats.get("model", "")
    settings = settings_text(a.agent, a.track, a.use_my_config, a.settings, stats)
    if a.track != F.TRACK and answers_from_reply(out, final_text(transcript, a.agent), a.suite, a.track):
        print("answers.json: saved from the json block at the end of the agent's reply")
    version = stats.get("version") or ("" if a.agent == "cmd" else
                                       agent_version(exe[0], PRESETS[a.agent].version[1:]) if a.agent in PRESETS
                                       else agent_version(exe[0]))
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
