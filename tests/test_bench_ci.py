"""The PR-only `bench-report` job in `.github/workflows/tests.yml`: its step script, run as GitHub runs it
(`bash --noprofile --norc -eo pipefail`) in a throwaway git repo with a stub `sports-video-coach`, reports the added
result files and fails closed when it cannot list them (a shallow checkout with no `HEAD^1`)."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STEP = "Score the added or changed result files into the job summary"


def step_script() -> str:
    """The `run: |` block of the bench-report step, dedented."""
    lines = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf8").splitlines()
    i = next(n for n, x in enumerate(lines) if x.strip() == f"- name: {STEP}")
    j = next(n for n in range(i + 1, len(lines)) if lines[n].strip() == "run: |")
    indent = len(lines[j]) - len(lines[j].lstrip()) + 2
    body = []
    for x in lines[j + 1:]:
        if x.strip() and len(x) - len(x.lstrip()) < indent:
            break
        body.append(x[indent:])
    return "\n".join(body).strip() + "\n"


def find_bash() -> str | None:
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")             # Git for Windows' bash, not WSL's System32\bash.exe
    if not git:
        return None
    up = Path(git).resolve().parents                  # Git\cmd\git.exe or Git\mingw64\bin\git.exe
    return next((str(b) for b in (up[1] / "bin" / "bash.exe", up[2] / "bin" / "bash.exe") if b.exists()), None)


BASH = find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no bash")


def git(repo: Path, *args: str):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def run_step(tmp_path: Path, commits: int) -> subprocess.CompletedProcess:
    """The step in a repo of `commits` commits, the last one adding a result file."""
    repo = tmp_path / "repo"
    (repo / "benchmark" / "results").mkdir(parents=True)
    git(repo, "init", "-q")
    for n in range(commits):
        name = "README.md" if n < commits - 1 else "benchmark/results/2026-10-30-x.json"
        (repo / name).write_text("{}\n", encoding="utf8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", f"c{n}")
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "sports-video-coach").write_text('#!/bin/sh\necho "stub $*"\n', encoding="utf8", newline="\n")
    (stub / "sports-video-coach").chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(step_script(), encoding="utf8", newline="\n")
    env = os.environ | {"PATH": str(stub) + os.pathsep + os.environ["PATH"],
                        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"), "RUNNER_TEMP": str(tmp_path)}
    return subprocess.run([BASH, "--noprofile", "--norc", "-eo", "pipefail", script.as_posix()], cwd=repo, env=env,
                          capture_output=True, text=True)


def test_step_script_is_found():
    s = step_script()
    assert "git diff" in s and "bench report" in s


@needs_bash
def test_step_reports_the_added_result_file(tmp_path):
    p = run_step(tmp_path, commits=2)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "result files added or changed: 1" in p.stdout
    assert "stub bench report benchmark/results/2026-10-30-x.json" in p.stdout
    assert "stub bench report" in (tmp_path / "summary.md").read_text(encoding="utf8")


@needs_bash
def test_step_fails_closed_without_the_base_commit(tmp_path):
    p = run_step(tmp_path, commits=1)                 # a depth-1 checkout: HEAD has no first parent
    assert p.returncode != 0, p.stdout + p.stderr
    assert re.search(r"^::error::.*HEAD\^1", p.stdout, re.M), p.stdout + p.stderr
    assert "stub bench report" not in p.stdout        # never a green "no result file changed" report


def test_job_stays_read_only_with_depth_2():
    wf = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf8")
    job = wf[wf.index("  bench-report:"):]
    assert "fetch-depth: 2" in job
    assert "secrets." not in job and not re.search(r"(^|\s)gh\s", job) and not re.search(r"[\w-]+: *write", job)
