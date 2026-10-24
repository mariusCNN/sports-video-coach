"""`bench run --agent codex --track frames`, run against a fake `codex` binary on PATH."""
import json
import os
import sys

import pytest

from sports_video_coach import bench
from sports_video_coach.bench import run as R, score as S, suite

TRUTH = {t.id: t.truth for t in suite.TASKS}

# Prints a `codex exec` header and progress on stderr and the final message on stdout, like its plain mode does.
FAKE = r"""
import json, os, pathlib, sys, time
args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.159.3")
    sys.exit(0)
prompt = sys.stdin.read()
pathlib.Path("seen.json").write_text(json.dumps({"argv": args, "stdin": prompt}), encoding="utf8")
if "SLEEP" in os.environ:
    time.sleep(60)
err = sys.stderr
err.write("Reading additional input from stdin...\nOpenAI Codex v0.159.3\n--------\nworkdir: " + os.getcwd() +
          "\nmodel: gpt-fake\nprovider: openai\napproval: never\nsandbox: read-only\nreasoning effort: xhigh\n"
          "--------\nuser\n" + prompt[:200] + "\n")
err.write("2026-10-25T00:00:00Z ERROR codex_core::tools::router: error=code-mode host is disabled\n")
if "RUN_CMD" in os.environ:
    err.write("exec\n\"dir\" in " + os.getcwd() + "\n succeeded in 5ms:\n")
err.flush()
answers = json.loads(pathlib.Path(os.environ["FILL"]).read_text(encoding="utf8"))
block = json.dumps({"suite": "svc-bench-1", "track": "frames", "answers": answers})
reply = "juggle: by eye\n```json\n" + block + "\n```\n"
err.write("codex\n" + reply + "tokens used\n1,234\n")
err.flush()
sys.stdout.write(reply)
"""


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    """A fake `codex` on PATH, tiny grey videos for every task, and the truth as its answers."""
    import cv2
    import numpy as np

    def tiny(out):
        w = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), suite.FPS, (160, 90))
        for i in range(30):
            w.write(np.full((90, 160, 3), i * 8, dtype=np.uint8))
        w.release()
        return out
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: tiny), raising=False)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    script = bin_ / "fake_codex.py"
    script.write_text(FAKE, encoding="utf8")
    if os.name == "nt":
        (bin_ / "codex.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf8")
    else:
        exe = bin_ / "codex"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf8")
        exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_) + os.pathsep + os.environ.get("PATH", ""))
    fill = tmp_path / "fill.json"
    fill.write_text(json.dumps(TRUTH), encoding="utf8")
    monkeypatch.setenv("FILL", str(fill))
    return tmp_path


def result_of(out):
    files = [p for p in out.glob("*.json") if p.name not in ("answers.json", "run.json", "seen.json")]
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf8"))


def test_codex_frames_run_attaches_every_sheet_and_scores_the_reply(fake_codex, capsys):
    out = fake_codex / "run"
    assert bench.main(["run", "--agent", "codex", "--track", "frames", "--out", str(out)]) == 0
    seen = json.loads((out / "seen.json").read_text(encoding="utf8"))
    argv = seen["argv"]
    assert argv[:2] == ["exec", "-"]                                    # the prompt is read from stdin
    assert argv[argv.index("-s") + 1] == "read-only" and "web_search=disabled" in argv
    off = [argv[i + 1] for i, x in enumerate(argv) if x == "--disable"]
    assert {"shell_tool", "unified_exec", "code_mode_host", "view_image", "multi_agent"} <= set(off)
    imgs = [argv[i + 1] for i, x in enumerate(argv) if x == "-i"]
    sheets = [p for t in suite.TASKS for p in R.F.sheets(out, t.id)]
    assert imgs == sheets and imgs                                     # every sheet, task by task, in time order
    prompt = (out / "PROMPT.txt").read_text(encoding="utf8")
    assert seen["stdin"].replace("\r\n", "\n") == prompt               # all of the prompt, then end of input
    assert "frames track" in prompt and "TASKS.md:" in prompt and "images 1-" in prompt
    assert (out / "TASKS.md").read_text(encoding="utf8") in prompt and '"answers"' in prompt
    assert not (out / "stderr.log").exists()                           # stderr is in the transcript
    res = result_of(out)
    assert res["track"] == "frames" and res["total"] == 1.0 and not S.problems(res)
    c = res["contender"]
    assert c["agent"] == "Codex" and c["model"] == "gpt-fake" and c["agent_version"] == "0.159.3"
    assert c["settings"] == R.CODEX_OWN + "; " + R.CODEX_FRAMES_SETTINGS + "; reasoning effort xhigh"
    assert "by prompt only" in c["settings"] and "every command it ran" in c["settings"]
    run = json.loads((out / "run.json").read_text(encoding="utf8"))
    assert run["commands_run"] == 0 and run["tool_calls_refused"] == 1 and run["exit_code"] == 0
    redacted = (out / "transcript.redacted.txt").read_text(encoding="utf8")
    assert "reasoning effort: xhigh" in redacted and "```json" in redacted
    printed = capsys.readouterr().out
    assert "0 commands run, 1 tool calls refused" in printed and "by prompt only" in printed


def test_codex_frames_counts_the_commands_it_ran(fake_codex, monkeypatch):
    monkeypatch.setenv("RUN_CMD", "1")
    out = fake_codex / "run"
    assert bench.main(["run", "--agent", "codex", "--track", "frames", "--out", str(out), "--model", "m"]) == 0
    assert json.loads((out / "run.json").read_text(encoding="utf8"))["commands_run"] == 1
    argv = json.loads((out / "seen.json").read_text(encoding="utf8"))["argv"]
    assert argv[argv.index("--model") + 1] == "m" and argv.index("--model") < argv.index("-i")


def test_codex_frames_is_killed_at_the_timeout(fake_codex, monkeypatch):
    monkeypatch.setenv("SLEEP", "1")
    out = fake_codex / "run"
    assert bench.main(["run", "--agent", "codex", "--track", "frames", "--out", str(out), "--timeout", "3"]) == 0
    run = json.loads((out / "run.json").read_text(encoding="utf8"))
    assert run["timed_out"] and run["exit_code"] is None
    assert result_of(out)["total"] == 0.0


def test_codex_frames_dry_run_and_command(tmp_path, capsys):
    c = R.command("codex", "P", tmp_path / "PROMPT.txt", track="frames")
    assert c[:3] == ["codex", "exec", "-"] and c[-1] == R.IMAGES_ARG and "P" not in c
    assert "workspace-write" not in c and "--json" not in c          # plain output keeps the header
    assert bench.main(["run", "--agent", "codex", "--track", "frames", "--suite", "svc-bench-3",
                       "--out", str(tmp_path / "dry"), "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "<every contact sheet>" in printed and "prompt on stdin, then closed" in printed
    assert "by prompt only" in printed and not (tmp_path / "dry").exists()


def test_codex_commands_reads_exec_blocks_and_refused_calls(tmp_path):
    log = tmp_path / "t.txt"
    log.write_text("codex\nexec\n\"ls\" in x\nERROR codex_core::tools::router: error=no\nexec\n", encoding="utf8")
    assert R.codex_commands(log) == {"commands_run": 2, "tool_calls_refused": 1}
    assert R.codex_commands(tmp_path / "missing") == {}
