"""`bench run --agent <preset>` for other agent CLIs, run against fake binaries of the same name on PATH."""
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

from sports_video_coach import bench
from sports_video_coach.bench import page, run as R, suite

TRUTH = {t.id: t.truth for t in suite.TASKS}
DOC = Path(__file__).resolve().parents[1] / "docs" / "benchmark.md"

# Records its argv and stdin in the run folder, answers --version / version, then fills answers.json from the file
# named by FAKE_FILL (or sleeps, with FAKE_SLEEP; or prints FAKE_LIMIT to FAKE_STREAM and hangs, like OpenCode at
# its free usage limit).
FAKE = """
import json, os, pathlib, sys, time
args = sys.argv[1:]
if args in (["--version"], ["version"]):
    print("fake-cli 9.8.7")
    sys.exit(0)
json.dump({"argv": args, "stdin": sys.stdin.read()}, open("argv.json", "w"))
print("fake agent ran", flush=True)
if os.environ.get("FAKE_LIMIT"):
    print(os.environ["FAKE_LIMIT"], file=getattr(sys, os.environ.get("FAKE_STREAM", "stderr")), flush=True)
    time.sleep(60)
if os.environ.get("FAKE_SLEEP"):
    time.sleep(60)
answers = json.loads(pathlib.Path(os.environ["FAKE_FILL"]).read_text(encoding="utf8"))
json.dump({"suite": "svc-bench-1", "answers": answers}, open("answers.json", "w"))
"""


@pytest.fixture
def fake_bin(tmp_path, monkeypatch):
    """A fake binary for every preset's program on PATH, and no real drawing of videos."""
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: lambda out: out), raising=False)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    script = bin_ / "fake_cli.py"
    script.write_text(FAKE, encoding="utf8")
    for prog in {p.argv[0] for p in R.PRESETS.values()}:
        if os.name == "nt":
            (bin_ / f"{prog}.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf8")
        else:
            exe = bin_ / prog
            exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf8")
            exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_) + os.pathsep + os.environ.get("PATH", ""))
    fill = tmp_path / "fill.json"
    fill.write_text(json.dumps(TRUTH), encoding="utf8")
    monkeypatch.setenv("FAKE_FILL", str(fill))
    return bin_


def result_of(out):
    files = [p for p in out.glob("*.json") if p.name not in ("answers.json", "run.json", "argv.json")]
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf8"))


@pytest.mark.parametrize("agent", sorted(R.PRESETS))
def test_each_preset_runs_its_documented_command_and_scores(tmp_path, fake_bin, agent):
    out = tmp_path / "run"
    assert bench.main(["run", "--agent", agent, "--model", "m-1", "--out", str(out)]) == 0
    seen = json.loads((out / "argv.json").read_text(encoding="utf8"))
    text = (out / "PROMPT.txt").read_text(encoding="utf8").strip()
    assert seen["argv"] == R.command(agent, text, out / "PROMPT.txt", "m-1")[1:]   # exactly the preset's argv
    assert seen["stdin"] == ""                                                     # stdin closed
    p = R.PRESETS[agent]
    assert [p.model_flag, "m-1"] == seen["argv"][seen["argv"].index(p.model_flag):][:2]
    res = result_of(out)
    assert res["total"] == 1.0
    assert res["contender"]["agent"] == p.name and res["contender"]["model"] == "m-1"
    assert res["contender"]["agent_version"] == "9.8.7"                            # read with the preset's command
    said = "run by the maintainer" if p.ran else "not run by the maintainer"
    assert res["contender"]["settings"].startswith(f"preset, {said} (--agent {agent})")
    assert (out / "transcript.txt").read_text(encoding="utf8").strip() == "fake agent ran"


def test_preset_prompt_placement_and_no_model(tmp_path):
    pf = tmp_path / "PROMPT.txt"
    assert R.command("gemini", "P", pf) == ["gemini", "--approval-mode", "yolo", "-p", "P"]
    # qwen 0.26.1 --help: -p "deprecated: Use the positional prompt instead"; the positional "Defaults to one-shot"
    assert R.command("qwen", "P", pf, "q") == ["qwen", "--safe-mode", "--approval-mode", "yolo", "--model", "q", "P"]
    aider = R.command("aider", "P", pf)
    assert aider[aider.index("--message-file") + 1] == str(pf) and aider[-1] == "answers.json"
    assert "P" not in aider and "--yes-always" in aider and "--no-git" in aider
    # OpenCode 1.19.4 worked in the folder `bench run` was started from, not the process's working folder
    assert R.command("opencode", "P", pf) == ["opencode", "run", "--auto", "--print-logs", "--log-level", "ERROR",
                                                "--dir", str(tmp_path), "P"]
    assert R.command("cursor", "P", pf)[:4] == ["agent", "-p", "--force", "--trust"]
    assert R.command("copilot", "P", pf) == ["copilot", "-p", "P", "--allow-all-tools", "--no-ask-user", "-s"]
    assert R.command("goose", "P", pf, "g") == ["goose", "run", "--no-session", "--model", "g", "-t", "P"]


@pytest.mark.parametrize("agent", sorted(R.PRESETS))
def test_presets_refuse_the_frames_track(tmp_path, agent):
    with pytest.raises(SystemExit, match="does not run the frames track"):
        R.command(agent, "P", tmp_path / "PROMPT.txt", track="frames")


def test_preset_is_killed_at_the_timeout(tmp_path, fake_bin, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "1")
    out = tmp_path / "run"
    t0 = time.monotonic()
    assert bench.main(["run", "--agent", "gemini", "--out", str(out), "--timeout", "2"]) == 0
    assert time.monotonic() - t0 < 30
    info = json.loads((out / "run.json").read_text(encoding="utf8"))
    assert info["timed_out"] is True and info["exit_code"] is None
    assert result_of(out)["total"] == 0.0


# OpenCode 1.19.4 at its free limit, as --print-logs --log-level ERROR puts it on stderr (then it hangs, no exit)
LIMIT_LOG = ('timestamp=2026-10-25T05:19:59.388Z level=ERROR message="stream error" error.error="AI_APICallError: '
             'Free usage limit reached. Free models work in OpenCode (https://opencode.ai); subscribe to OpenCode Go '
             'to keep going: https://opencode.ai/go"')


@pytest.mark.parametrize("stream", ["stderr", "stdout"])
def test_preset_stops_at_the_providers_usage_limit(tmp_path, fake_bin, monkeypatch, capsys, stream):
    monkeypatch.setenv("FAKE_LIMIT", LIMIT_LOG)
    monkeypatch.setenv("FAKE_STREAM", stream)
    out = tmp_path / "run"
    t0 = time.monotonic()
    assert bench.main(["run", "--agent", "opencode", "--out", str(out), "--timeout", "30"]) == 0
    assert time.monotonic() - t0 < 20                     # stopped at the line, not at the timeout
    info = json.loads((out / "run.json").read_text(encoding="utf8"))
    assert info["exit_code"] is None and info["timed_out"] is False
    assert info["usage_limit"].startswith("Free usage limit reached. Free models work in OpenCode")
    res = result_of(out)
    assert res["total"] == 0.0
    assert "stopped early by the provider's usage limit: \"Free usage limit reached." in res["contender"]["settings"]
    printed = capsys.readouterr().out
    assert "usage limit" in printed and "rerun after the quota resets" in printed


def test_usage_limit_lines_are_preset_data():
    assert R.PRESETS["opencode"].limits == ("Free usage limit reached",)
    assert {"--print-logs", "--log-level"} <= set(R.PRESETS["opencode"].argv)   # its ERROR log lines on stderr
    hit = R.limit_hit("x\n\x1b[91mError: Free usage limit reached. Go on\x1b[0m\n",
                      ("Free usage limit reached",))
    assert hit == "Free usage limit reached. Go on"
    assert R.limit_hit("all fine\n", ("Free usage limit reached",)) == ""
    assert R.limit_hit("Free usage limit reached\n", ()) == ""


def test_dry_run_prints_the_preset_command_and_says_untested(tmp_path, capsys):
    dry = tmp_path / "dry"
    assert bench.main(["run", "--agent", "opencode", "--model", "p/m", "--out", str(dry), "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert f"opencode run --auto --print-logs --log-level ERROR --dir {dry.resolve()} --model p/m" in printed
    assert "You are a contender" in printed
    assert "run by the maintainer on a task (OpenCode 1.19.4" in printed and "https://opencode.ai/docs/cli/" in printed
    assert bench.main(["run", "--agent", "goose", "--out", str(dry), "--dry-run"]) == 0
    assert "not run by the maintainer" in capsys.readouterr().out
    assert not dry.exists()


@pytest.mark.parametrize("agent", ["gemini", "opencode"])
def test_dry_run_preset_line_has_no_empty_parenthesis(tmp_path, capsys, agent):
    assert bench.main(["run", "--agent", agent, "--out", str(tmp_path / "dry"), "--dry-run"]) == 0
    line = next(ln for ln in capsys.readouterr().out.splitlines() if "by the maintainer on a task" in ln)
    assert "(;" not in line and "()" not in line
    assert line.count("(") == line.count(")")
    assert f"; flags from {R.PRESETS[agent].docs}, checked against the --help of version" in line


def test_help_says_presets_are_untested(capsys):
    with pytest.raises(SystemExit):
        R.main(["--help"])
    help_ = " ".join(capsys.readouterr().out.split())
    assert "NOT run by the maintainer" in help_ and all(k in help_ for k in R.PRESETS)
    assert "except opencode (OpenCode 1.19.4" in help_


def test_settings_name_the_preset():
    assert R.settings_text("qwen", "code", False) == ("preset, not run by the maintainer (--agent qwen); --safe-mode: "
                                                      "no context files, hooks, extensions, skills or MCP servers")
    assert R.settings_text("gemini", "code", False, "effort high").endswith("runner's own config; effort high")
    assert R.settings_text("opencode", "code", False).startswith("preset, run by the maintainer (--agent opencode)")


def test_only_presets_run_on_a_task_say_so():
    assert {k for k, p in R.PRESETS.items() if p.ran} == {"opencode"}
    assert R.shown("opencode") == ("opencode run --auto --print-logs --log-level ERROR --dir <run folder> "
                                  "[--model M] <prompt>")


def test_presets_name_the_cli_version_their_flags_were_checked_against():
    # checked against each real CLI's --help on HELP_CHECKED; a re-check updates these and the docs table
    assert {k: p.checked for k, p in R.PRESETS.items()} == {
        "gemini": "0.65.0", "qwen": "0.26.1", "aider": "0.86.2", "opencode": "1.19.4",
        "cursor": "2026.10.22-27dcf5f", "copilot": "1.0.103", "goose": "1.56.0"}
    assert [t for t in R.PRESETS["qwen"].argv if t == "-p"] == []
    doc = DOC.read_text(encoding="utf8")
    for key, p in R.PRESETS.items():
        assert re.search(rf"^\| `{key}` \| {re.escape(p.name)} {re.escape(p.checked)} \|", doc, re.M), key
    for lang in ("en", "zh"):
        html = page.render([], [], lang=lang)
        assert all(p.checked in html for p in R.PRESETS.values()) and R.HELP_CHECKED in html


def test_shown_command_lines():
    assert R.shown("gemini") == "gemini --approval-mode yolo [--model M] -p <prompt>"
    assert R.shown("aider").endswith("--message-file <prompt file> answers.json")


def test_docs_table_and_page_list_every_preset():
    doc = DOC.read_text(encoding="utf8")
    html = page.render([], [])
    for key, p in R.PRESETS.items():
        row = [line for line in doc.splitlines() if line.startswith(f"| `--agent {key}`")]
        assert len(row) == 1, key
        assert p.docs in row[0] and R.shown(key) in row[0]
        assert ("run by the maintainer on a task" if p.ran else "not run by the maintainer") in row[0], key
        assert f"--agent {key}</code> {p.name}" in html     # the page links the docs table, not outside sites
    assert R.DOCS_READ in doc
    assert re.search(r"not run by the maintainer", html)


def test_page_readmes_and_docs_link_the_wanted_issue():
    assert page.WANTED_URL.endswith("/issues/7")
    assert f'<a href="{page.WANTED_URL}">issue #7</a>' in page.render([], [])
    assert f'<a href="{page.WANTED_URL}">issue #7</a>' in page.render([], [], lang="zh")
    for f in (DOC, DOC.parent.parent / "README.md", DOC.parent.parent / "README.zh.md"):
        assert page.WANTED_URL in f.read_text(encoding="utf8"), f.name
