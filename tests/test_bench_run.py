import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from sports_video_coach import bench
from sports_video_coach.bench import run as R, score as S, suite, suite2

TRUTH = {t.id: t.truth for t in suite.TASKS}

FAKE = """
import json, pathlib, sys, time
mode = sys.argv[1]
prompt = pathlib.Path(sys.argv[2]).read_text(encoding="utf8")
print("prompt:", prompt[:40])
print("stdin:", repr(sys.stdin.read()))
if mode == "sleep":
    time.sleep(60)
elif mode == "delete":
    pathlib.Path("answers.json").unlink()
else:
    answers = json.loads(pathlib.Path(mode).read_text(encoding="utf8"))
    json.dump({"suite": "svc-bench-1", "answers": answers}, open("answers.json", "w"))
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """A fake agent CLI (a python script) and no real drawing of videos."""
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: lambda out: out), raising=False)
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE, encoding="utf8")

    def cmd(mode) -> str:
        if isinstance(mode, dict):
            (tmp_path / "fill.json").write_text(json.dumps(mode), encoding="utf8")
            mode = f'"{tmp_path / "fill.json"}"'
        return f'"{sys.executable}" "{script}" {mode} {{prompt_file}}'
    return cmd


def run(tmp_path, cmd, *extra):
    out = tmp_path / "run"
    code = bench.main(["run", "--agent", "cmd", "--cmd", cmd, "--out", str(out), "--name", "fake", *extra])
    return code, out


def result_of(out):
    files = [p for p in out.glob("*.json") if p.name not in ("answers.json", "run.json")]
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf8"))


def test_run_scores_a_fake_agent_end_to_end(tmp_path, fake, capsys):
    code, out = run(tmp_path, fake(TRUTH), "--model", "m-1", "--by", "someone")
    assert code == 0
    res = result_of(out)
    assert res["total"] == 1.0 and res["suite"] == "svc-bench-1"
    assert res["contender"] == {"agent": "fake", "agent_version": "", "model": "m-1", "settings": ""}
    assert res["submitted_by"] == "someone" and res["cost_usd"] is None
    assert isinstance(res["wall_seconds"], (int, float)) and res["wall_seconds"] >= 0
    assert not S.problems(res)
    log = (out / "transcript.txt").read_text(encoding="utf8")
    assert "stdin: ''" in log                                   # stdin is closed, the agent cannot wait on it
    assert "prompt: You are a contender" in log and (out / "PROMPT.txt").exists()
    assert json.loads((out / "run.json").read_text(encoding="utf8"))["timed_out"] is False
    printed = capsys.readouterr().out
    url = [line for line in printed.splitlines() if line.startswith(R.ISSUE_FORM)][0]
    q = parse_qs(urlparse(url).query)
    assert q["template"] == ["benchmark_result.yml"] and q["agent"] == ["fake"] and q["model"] == ["m-1"]
    assert json.loads(q["result"][0]) == res


def test_run_kills_the_agent_at_the_timeout(tmp_path, fake):
    t0 = time.monotonic()
    code, out = run(tmp_path, fake("sleep"), "--timeout", "2")
    assert code == 0 and time.monotonic() - t0 < 30
    info = json.loads((out / "run.json").read_text(encoding="utf8"))
    assert info["timed_out"] is True and info["exit_code"] is None
    res = result_of(out)
    assert res["total"] == 0.0 and 1.5 <= res["wall_seconds"] < 30


def test_run_with_missing_answers_scores_zero(tmp_path, fake, capsys):
    code, out = run(tmp_path, fake("delete"))
    assert code == 0 and result_of(out)["total"] == 0.0
    assert "could not be read" in capsys.readouterr().out


def test_run_refuses_a_used_folder_and_dry_run_runs_nothing(tmp_path, fake, capsys):
    out = tmp_path / "run"
    out.mkdir()
    (out / "x").write_text("x")
    with pytest.raises(SystemExit, match="not empty"):
        bench.main(["run", "--agent", "cmd", "--cmd", fake(TRUTH), "--out", str(out)])
    dry = tmp_path / "dry"
    assert bench.main(["run", "--agent", "claude", "--model", "claude-haiku-5-5", "--out", str(dry),
                       "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert ("claude -p --safe-mode --setting-sources project --strict-mcp-config --output-format stream-json "
            "--verbose --dangerously-skip-permissions") in printed
    assert "--model claude-haiku-5-5" in printed and "clean room" in printed and not dry.exists()


def test_commands_for_each_agent(tmp_path):
    pf = tmp_path / "PROMPT.txt"
    c = R.command("claude", "P", pf, "claude-haiku-5-5")
    assert c[:2] == ["claude", "-p"] and c[-3:] == ["--model", "claude-haiku-5-5", "P"]
    x = R.command("codex", "P", pf)
    assert x[:2] == ["codex", "exec"] and "workspace-write" in x and "--model" not in x and x[-1] == "P"
    g = R.command("cmd", "the prompt", pf, "gm", "gemini -m {model} -p {prompt}")
    assert g == ["gemini", "-m", "gm", "-p", "the prompt"]
    assert R.command("cmd", "P", pf, template="aider --message-file {prompt_file}")[-1] == str(pf)
    with pytest.raises(SystemExit):
        R.command("cmd", "P", pf, template="gemini -y")
    with pytest.raises(SystemExit):
        R.command("cmd", "P", pf)


def test_claude_runs_clean_room_by_default_and_with_my_config_on_request(tmp_path):
    pf = tmp_path / "PROMPT.txt"
    clean = R.command("claude", "P", pf, "claude-sonnet-5-5")
    assert clean[2:6] == ["--safe-mode", "--setting-sources", "project", "--strict-mcp-config"]
    mine = R.command("claude", "P", pf, "claude-sonnet-5-5", my_config=True)
    assert not set(R.CLAUDE_CLEAN) & set(mine) and "--dangerously-skip-permissions" in mine
    frames_mine = R.command("claude", "P", pf, track="frames", my_config=True)
    assert "--safe-mode" not in frames_mine and "--restricted" in frames_mine      # still no code on frames
    assert "--safe-mode" in R.command("claude", "P", pf, track="frames")
    # Codex's clean room is its environment (a temporary CODEX_HOME), not its command line
    assert R.command("codex", "P", pf, my_config=True) == R.command("codex", "P", pf)


def test_settings_say_how_the_runner_config_was_handled():
    assert R.settings_text("claude", "code", False) == "clean-room: no user config"
    assert R.settings_text("claude", "code", False, "effort high") == "clean-room: no user config; effort high"
    assert R.settings_text("claude", "code", True) == "runner's own agent config (--use-my-config)"
    assert R.settings_text("codex", "code", False, stats={"effort": "high"}) == \
        "clean-room: no user config; reasoning effort high"
    assert R.settings_text("claude", "frames", False) == R.CLAUDE_FRAMES_SETTINGS     # leaderboard rows unchanged
    assert "--safe-mode" not in R.settings_text("claude", "frames", True)
    assert R.settings_text("cmd", "code", False) == "" and R.settings_text("cmd", "code", False, "x") == "x"


def test_agent_env_drops_the_calling_session_identity(tmp_path):
    base = {"PATH": "p", "HOME": "h", "ANTHROPIC_API_KEY": "k", "CLAUDE_CONFIG_DIR": "c", "ORCA_AGENT_PANE": "1",
            "orca_pane_key": "2", "CLAUDECODE": "1", "CLAUDE_PID": "9", "CLAUDE_CODE_SESSION_ID": "s",
            "CLAUDE_CODE_ENTRYPOINT": "cli", "CLAUDE_CODE_EXECPATH": "x", "CLAUDE_CODE_MESSAGING_SOCKET": "m",
            "CLAUDE_CODE_USE_BEDROCK": "1", "TERM_PROGRAM": "Orca"}
    env = R.agent_env(base)
    assert env == {"PATH": "p", "HOME": "h", "ANTHROPIC_API_KEY": "k", "CLAUDE_CONFIG_DIR": "c",
                   "CLAUDE_CODE_USE_BEDROCK": "1"}                   # login and provider settings stay
    assert R.agent_env(base, tmp_path)["CODEX_HOME"] == str(tmp_path)
    assert R.agent_env({"TERM_PROGRAM": "vscode"}) == {"TERM_PROGRAM": "vscode"}


def test_run_does_not_pass_the_session_identity_to_the_agent(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("ORCA_AGENT_PANE", "pane-1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-1")
    monkeypatch.setenv("SVC_KEEP_ME", "kept")
    dump = tmp_path / "env.py"
    dump.write_text("import json, os, sys\njson.dump(dict(os.environ), open('env.json', 'w'))\n", encoding="utf8")
    code, out = run(tmp_path, f'"{sys.executable}" "{dump}" {{prompt_file}}')
    seen = json.loads((out / "env.json").read_text(encoding="utf8"))
    assert code == 0 and seen["SVC_KEEP_ME"] == "kept"
    assert "ORCA_AGENT_PANE" not in seen and "CLAUDE_CODE_SESSION_ID" not in seen


def test_clean_codex_home_holds_only_the_login_and_keeps_a_refreshed_one(tmp_path):
    user = tmp_path / "codex"
    user.mkdir()
    for name, body in (("auth.json", "old"), ("AGENTS.md", "mine"), ("config.toml", "model='x'")):
        (user / name).write_text(body, encoding="utf8")
    home = R.clean_codex_home(user)
    assert sorted(p.name for p in home.iterdir()) == ["auth.json"] and not home.is_relative_to(user)
    (home / "auth.json").write_text("refreshed", encoding="utf8")
    t = (user / "auth.json").stat().st_mtime
    import os
    os.utime(home / "auth.json", (t + 10, t + 10))
    R.drop_codex_home(home, user)
    assert not home.exists() and (user / "auth.json").read_text(encoding="utf8") == "refreshed"
    home = R.clean_codex_home(user)            # unchanged login: nothing is written back, the copy is deleted
    R.drop_codex_home(home, user)
    assert not home.exists() and (user / "auth.json").read_text(encoding="utf8") == "refreshed"
    assert R.user_codex_home({"CODEX_HOME": str(user)}) == user


def test_codex_run_uses_a_temporary_codex_home_unless_my_config(tmp_path, monkeypatch):
    user = tmp_path / "codex"
    user.mkdir()
    (user / "auth.json").write_text("{}", encoding="utf8")
    monkeypatch.setenv("CODEX_HOME", str(user))
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: lambda out: out), raising=False)
    monkeypatch.setattr(R, "resolve", lambda argv: argv)
    monkeypatch.setattr(R, "agent_version", lambda exe: "")
    seen = []
    monkeypatch.setattr(R, "execute", lambda argv, cwd, tr, err, timeout, env: (
        seen.append((env.get("CODEX_HOME"), sorted(p.name for p in Path(env["CODEX_HOME"]).iterdir()))), (0, 1.0))[1])
    assert bench.main(["run", "--agent", "codex", "--out", str(tmp_path / "a")]) == 0
    home, files = seen[0]
    assert home != str(user) and files == ["auth.json"] and not Path(home).exists()
    assert json.loads(next((tmp_path / "a").glob("*codex*.json")).read_text())["contender"]["settings"] == \
        "clean-room: no user config"
    assert bench.main(["run", "--agent", "codex", "--use-my-config", "--out", str(tmp_path / "b")]) == 0
    assert seen[1][0] == str(user)


@pytest.mark.parametrize("name", ["svc-bench-1", "svc-bench-2"])
def test_prompt_is_one_safe_line(name):
    p = R.prompt(name)
    n = len((suite if name == "svc-bench-1" else suite2).TASKS)
    assert name in p and f"holds {n} short videos" in p
    assert "\n" not in p and not set(p) & set('"%^!&|<>')       # survives Windows .cmd shims unchanged


def test_claude_stats_reads_model_version_and_cost_only_when_stated(tmp_path):
    t = tmp_path / "transcript.jsonl"
    init = {"type": "system", "subtype": "init", "model": "claude-haiku-5-5", "claude_code_version": "2.1.9"}
    t.write_text("\n".join([json.dumps(init), "not json", json.dumps({"type": "result", "total_cost_usd": 0.123456})]),
                 encoding="utf8")
    assert R.claude_stats(t) == {"model": "claude-haiku-5-5", "version": "2.1.9", "cost_usd": 0.1235}
    t.write_text(json.dumps({"type": "result"}), encoding="utf8")
    assert R.claude_stats(t) == {}


def test_codex_stats_reads_only_the_header(tmp_path):
    log = tmp_path / "stderr.log"
    log.write_text("Reading additional input from stdin...\nOpenAI Codex v0.1\n--------\nworkdir: C:\\x\n"
                   "model: gpt-x\nreasoning effort: high\n--------\nuser\nmodel: not-this\n", encoding="utf8")
    assert R.codex_stats(log) == {"model": "gpt-x", "effort": "high"}
    log.write_text("no header\nmodel: gpt-x\n", encoding="utf8")
    assert R.codex_stats(log) == {}
    assert R.codex_stats(tmp_path / "missing.log") == {}


def test_issue_url_drops_a_result_too_long_for_a_url():
    res = {"suite": "svc-bench-2", "total": 0.5, "evidence": "",
           "contender": {"agent": "Codex", "agent_version": "1.0", "model": "", "settings": ""}}
    q = parse_qs(urlparse(R.issue_url(res)).query)
    assert q["title"] == ["[Benchmark]: Codex on svc-bench-2 (0.5)"] and q["settings"] == ["none"]
    assert "model" not in q and json.loads(q["result"][0]) == res
    res["padding"] = "x" * 10000
    long = R.issue_url(res)
    assert len(long) <= R.MAX_URL and "result" not in parse_qs(urlparse(long).query)


REPLY = """
import pathlib, sys
answers = pathlib.Path(sys.argv[1]).read_text(encoding="utf8")
print("I read " + pathlib.Path(sys.argv[2]).read_text(encoding="utf8")[:60])
print("juggle: by eye ...")
print("```json")
print(answers)
print("```")
"""


@pytest.fixture
def stills(monkeypatch):
    """Every task draws a 30-frame grey video, so the frames track has real stills and sheets to cut."""
    import cv2
    import numpy as np

    def tiny(out):
        w = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), suite.FPS, (160, 90))
        for i in range(30):
            w.write(np.full((90, 160, 3), i * 8, dtype=np.uint8))
        w.release()
        return out
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: tiny), raising=False)


def test_run_frames_track_saves_answers_from_the_reply_and_names_the_track(tmp_path, stills, capsys):
    script = tmp_path / "reply_agent.py"
    script.write_text(REPLY, encoding="utf8")
    fill = tmp_path / "fill.json"
    fill.write_text(json.dumps({"suite": "svc-bench-1", "track": "frames", "answers": TRUTH}), encoding="utf8")
    out = tmp_path / "run"
    cmd = f'"{sys.executable}" "{script}" "{fill}" {{prompt_file}}'
    assert bench.main(["run", "--track", "frames", "--agent", "cmd", "--cmd", cmd, "--out", str(out),
                       "--name", "fake", "--model", "m-1"]) == 0
    assert not list(out.glob("*.mp4")) and list((out / "sheets").iterdir())
    assert "frames track" in (out / "PROMPT.txt").read_text(encoding="utf8")
    saved = json.loads((out / "answers.json").read_text(encoding="utf8"))
    assert saved == {"suite": "svc-bench-1", "track": "frames", "answers": TRUTH}
    res = result_of(out)
    assert res["track"] == "frames" and res["total"] == 1.0 and not S.problems(res)
    assert (out / S.default_path(res).name).exists() and S.default_path(res).name.endswith("-frames.json")
    printed = capsys.readouterr().out
    assert "saved from the json block" in printed
    url = [line for line in printed.splitlines() if line.startswith(R.ISSUE_FORM)][0]
    q = parse_qs(urlparse(url).query)
    assert q["title"] == ["[Benchmark]: fake m-1 on svc-bench-1 frames track (1.0)"]


def test_answers_from_reply_keeps_a_filled_file_and_ignores_the_prompt_text(tmp_path):
    blank = {"suite": "svc-bench-1", "track": "frames", "answers": {t: None for t in TRUTH}}
    (tmp_path / "answers.json").write_text(json.dumps(blank), encoding="utf8")
    # the prompt's own words "in one ```json block" are not a block; no reply block leaves the file as it was
    assert not R.answers_from_reply(tmp_path, R.prompt("svc-bench-1", "frames"), "svc-bench-1", "frames")
    reply = 'x\n```json\n{"jump-count": 3, "ghost": 1}\n```\n'
    assert R.answers_from_reply(tmp_path, reply, "svc-bench-1", "frames")
    got = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))["answers"]
    assert got["jump-count"] == 3 and "ghost" not in got
    assert not R.answers_from_reply(tmp_path, reply.replace("3", "9"), "svc-bench-1", "frames")  # already filled
    final = [{"type": "assistant"}, {"type": "result", "result": "the reply"}]
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in final), encoding="utf8")
    assert R.final_text(t, "claude") == "the reply" and R.final_text(t, "cmd").startswith('{"type"')


def test_frames_track_runs_claude_with_read_only_and_the_published_prompt(tmp_path, capsys):
    p = R.prompt("svc-bench-3", "frames", "claude")
    assert p.startswith("You are a contender in a sports film review benchmark (suite svc-bench-3, frames track).")
    assert "still images of 4 short videos" in p and p.endswith("Your only tool is Read: read TASKS.md first, "
                                                                "then the images it lists.")
    assert R.prompt("svc-bench-3", "frames", "cmd").endswith("frames/). Read TASKS.md first, then the images it "
                                                             "lists.")
    for text in (p, R.prompt("svc-bench-2", "frames")):
        assert "\n" not in text and not set(text) & set('"%^!&|<>')
    c = R.command("claude", p, tmp_path / "PROMPT.txt", "claude-sonnet-5-5", track="frames")
    assert c[c.index("--tools") + 1] == "Read" and "--restricted" in c and "--dangerously-skip-permissions" not in c
    with pytest.raises(SystemExit, match="frames"):
        R.command("codex", p, tmp_path / "PROMPT.txt", track="frames")
    assert bench.main(["run", "--track", "frames", "--suite", "svc-bench-3", "--agent", "claude",
                       "--out", str(tmp_path / "dry"), "--dry-run"]) == 0
    assert "--tools Read" in capsys.readouterr().out
