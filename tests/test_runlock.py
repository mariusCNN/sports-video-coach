"""runlock: one writer per unit folder, and no rewrite of a folder by code older than the code that last wrote it."""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time

import pytest

from sports_video_coach import pipeline as P
from sports_video_coach import runlock

from test_driver import Runner, Unit, steps, unit  # noqa: F401  (the fixture)

OLD, NEW = {"version": "1.0", "commit": ""}, {"version": "1.1", "commit": ""}


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A checkout with base -> newer on main and base -> side on a branch: {name: commit}."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    shas = {}
    for name in ("base", "newer"):
        git(root, "commit", "-q", "--allow-empty", "-m", name)
        shas[name] = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "-q", "-b", "side", shas["base"])
    git(root, "commit", "-q", "--allow-empty", "-m", "side")
    shas["side"] = git(root, "rev-parse", "HEAD")
    shas["root"] = root
    return shas


def code(sha):
    return {"version": "0.3.1", "commit": sha}


def dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def lock(folder, pid, host=None):
    """A leftover `.run-lock.json` naming `pid` (what a run killed hard leaves)."""
    info = {"pid": pid, "host": host or socket.gethostname(), "started": "2026-10-25T10:05:00", "code": code("f" * 40)}
    (folder / runlock.INFO).write_text(json.dumps(info), encoding="utf8")


HOLDER = """
import os, sys, time
from pathlib import Path
from sports_video_coach import runlock
folder, go, out = Path(sys.argv[1]), float(sys.argv[2]), Path(sys.argv[3])
while time.time() < go:
    pass
try:
    with runlock.hold(folder, {"version": "t", "commit": "f" * 40}):
        out.write_text(f"WON {os.getpid()}")
        while not (folder / "stop").exists():
            time.sleep(0.05)
except SystemExit:
    out.write_text("HELD")
"""


def start(folder, out, go=0.0):
    return subprocess.Popen([sys.executable, "-c", HOLDER, str(folder), str(go), str(out)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def kill(out, p):
    """Kill the holder hard (SIGKILL / TerminateProcess: no cleanup runs), by the pid it reported: on Windows
    `p` can be a venv launcher whose child runs the code."""
    words = out.read_text().split() if out.exists() else []
    if len(words) == 2 and p.poll() is None:   # still running (so its pid is not reused yet)
        try:
            os.kill(int(words[1]), getattr(signal, "SIGKILL", signal.SIGTERM))
        except OSError:
            pass
    p.kill()
    p.wait(timeout=60)


def wait_for(*outs, timeout=60):
    end = time.time() + timeout
    while not all(o.exists() and o.read_text() for o in outs):
        assert time.time() < end, "the holder processes did not report"
        time.sleep(0.05)


@pytest.fixture
def held(tmp_path):
    """A folder whose lock another process holds (until the test ends); yields (folder, its pid, kill it)."""
    folder, out = tmp_path / "held", tmp_path / "out"
    folder.mkdir()
    p = start(folder, out)
    try:
        wait_for(out)
        assert out.read_text().startswith("WON ")
        yield folder, int(out.read_text().split()[1]), lambda: kill(out, p)
    finally:
        kill(out, p)


def test_a_run_holds_the_lock_while_it_works_and_lets_go_after(unit):  # noqa: F811
    seen = []

    class Watch(Runner):
        def __call__(self, cmd, **kw):
            seen.append(json.loads((unit / runlock.INFO).read_text(encoding="utf8")))
            with pytest.raises(SystemExit, match="another run is working on this folder"):
                with runlock.hold(unit, {}):                 # a second open of the lock file cannot take it
                    pass
            return super().__call__(cmd, **kw)

    assert P.drive(Unit.load(unit), steps()[:1], runner=Watch(unit)) == 0
    assert seen[0]["pid"] == os.getpid() and seen[0]["host"] == socket.gethostname() and "commit" in seen[0]["code"]
    assert not (unit / runlock.INFO).exists() and not list(unit.glob("*.tmp"))
    with runlock.hold(unit, {}):                              # let go: the next run takes it
        pass


def test_a_second_run_on_a_held_folder_exits_1_naming_the_holder(held, unit):  # noqa: F811
    folder, pid, _ = held
    with pytest.raises(SystemExit) as e:
        with runlock.hold(folder, {}):
            pass
    msg = str(e.value.code)
    assert "another run is working on this folder" in msg and f"pid {pid}" in msg and "ffffffffffff" in msg
    assert json.loads((folder / runlock.INFO).read_text(encoding="utf8"))["pid"] == pid   # the holder's stays
    (folder / runlock.INFO).write_text("{", encoding="utf8")                                # unreadable info
    with pytest.raises(SystemExit, match="another run holds the lock"):
        with runlock.hold(folder, {}):
            pass
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), dry=True, runner=r) == 0 and r.calls == []   # --dry takes no lock


def test_a_holder_killed_hard_lets_the_next_run_in_at_once(held):
    folder, pid, kill_it = held
    kill_it()
    assert read_pid(folder) == pid                            # it left its info behind
    with runlock.hold(folder, {}):
        assert read_pid(folder) == os.getpid()


def read_pid(folder):
    return json.loads((folder / runlock.INFO).read_text(encoding="utf8"))["pid"]


def test_leftover_holder_info_from_a_dead_run_does_not_block(unit):  # noqa: F811
    lock(unit, dead_pid())
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), runner=r) == 0 and len(r.calls) == 4
    assert not (unit / runlock.INFO).exists()


def test_runs_racing_for_one_folder_one_wins(tmp_path):
    for round_ in range(3):
        folder = tmp_path / f"f{round_}"
        folder.mkdir()
        if round_:
            lock(folder, dead_pid())                          # with and without a dead run's info
        outs = [folder / f"out{i}" for i in range(6)]
        go = time.time() + 3
        procs = [start(folder, o, go) for o in outs]
        try:
            wait_for(*outs)
            got = [o.read_text().split()[0] for o in outs]
            (folder / "stop").write_text("")
            for p in procs:
                p.wait(timeout=60)
        finally:
            for o, p in zip(outs, procs):
                kill(o, p)
        assert got.count("WON") == 1 and got.count("HELD") == 5, got
        assert not (folder / runlock.INFO).exists() and not list(folder.glob("*.tmp"))


def test_compare_uses_git_ancestry(repo):
    root = repo["root"]
    assert runlock.compare(code(repo["newer"]), code(repo["base"]), root)[0] == "older"
    assert runlock.compare(code(repo["base"]), code(repo["newer"]), root)[0] == "newer"
    assert runlock.compare(code(repo["side"]), code(repo["newer"]), root)[0] == "differs"
    assert runlock.compare(code("e" * 40), code(repo["newer"]), root) == (
        "differs", "commit eeeeeeeeeeee is not in this checkout (git fetch, then run again)")
    assert runlock.compare(code(repo["newer"]), code(repo["base"]), None) == (                # no git to tell
        "unknown", "no git checkout here to tell which commit is newer")
    assert runlock.compare(code(repo["base"]), code(repo["base"]), root)[0] == "same"
    assert runlock.compare(None, code(repo["base"]), root)[0] == "same"                     # never stamped
    assert runlock.compare(code(""), code(repo["base"]), root)[0] == "unknown"
    assert runlock.compare(code(repo["base"]), code(""), root)[0] == "unknown"


def test_a_writing_run_stamps_the_code_version(unit, monkeypatch):  # noqa: F811
    monkeypatch.setattr(runlock, "code_version", lambda: code("a" * 40))
    assert P.drive(Unit.load(unit), steps(), runner=Runner(unit)) == 0
    stamp = P.Store(unit).code
    assert stamp["commit"] == "a" * 40 and stamp["version"] == "0.3.1" and stamp["host"] == socket.gethostname()


def stamped(folder, sha):
    store = P.Store(folder)
    store.code = {**code(sha), "at": "2026-10-25T10:05:00", "host": "box"}
    store.save()


def test_older_code_refuses_to_rewrite_the_folder(unit, repo, monkeypatch):  # noqa: F811
    stamped(unit, repo["newer"])
    monkeypatch.setattr(runlock, "code_version", lambda: code(repo["base"]))
    monkeypatch.setattr(runlock, "checkout", lambda: repo["root"])
    r = Runner(unit)
    with pytest.raises(SystemExit) as e:
        P.drive(Unit.load(unit), steps(), runner=r)
    msg = str(e.value.code)
    assert "refusing to rewrite outputs last written by newer code" in msg
    assert f"folder:   sports-video-coach 0.3.1 @ {repo['newer'][:12]}, written 2026-10-25T10:05:00 on box" in msg
    assert f"this run: sports-video-coach 0.3.1 @ {repo['base'][:12]} (" in msg and "is an ancestor of" in msg
    assert "--allow-older-code`" in msg
    assert r.calls == [] and P.Store(unit).code["commit"] == repo["newer"] and not (unit / runlock.INFO).exists()


def test_diverged_code_refuses_too_and_the_flag_overrides(unit, repo, monkeypatch, capsys):  # noqa: F811
    stamped(unit, repo["side"])
    monkeypatch.setattr(runlock, "code_version", lambda: code(repo["newer"]))
    monkeypatch.setattr(runlock, "checkout", lambda: repo["root"])
    with pytest.raises(SystemExit, match="other code that this run cannot show to be older"):
        P.drive(Unit.load(unit), steps(), runner=Runner(unit))
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), runner=r, allow_older_code=True) == 0 and len(r.calls) == 4
    assert "--allow-older-code: rewriting outputs" in capsys.readouterr().out
    assert P.Store(unit).code["commit"] == repo["newer"]       # the last writer's code


def test_newer_code_goes_on_and_restamps(unit, repo, monkeypatch):  # noqa: F811
    stamped(unit, repo["base"])
    monkeypatch.setattr(runlock, "code_version", lambda: code(repo["newer"]))
    monkeypatch.setattr(runlock, "checkout", lambda: repo["root"])
    assert P.drive(Unit.load(unit), steps(), runner=Runner(unit)) == 0
    assert P.Store(unit).code["commit"] == repo["newer"]


def dirty(sha, source):
    return {**code(sha), "source": source, "dirty": True}


def test_uncommitted_code_holds_the_folder_against_other_checkouts(repo):
    root = repo["root"]
    stamp = dirty(repo["base"], "/checkouts/main")
    assert runlock.compare(stamp, {**code(repo["newer"]), "source": "/checkouts/sprint"}, root) == (
        "differs", "the folder was last written by uncommitted code in /checkouts/main")
    assert runlock.compare(stamp, dirty(repo["base"], "/checkouts/main"), root)[0] == "same"   # still editing
    assert runlock.compare(stamp, {**code(repo["base"]), "source": "/checkouts/main"}, root)[0] == "same"


def test_the_same_checkout_committing_its_work_is_newer(repo):
    """Dirty at A in checkout X, then X commits and runs at descendant B: go on. An older or diverged HEAD in X
    still blocks."""
    root, stamp = repo["root"], dirty(repo["base"], "/checkouts/main")
    assert runlock.compare(stamp, {**code(repo["newer"]), "source": "/checkouts/main"}, root) == ("newer", "")
    assert runlock.compare(stamp, {**code(repo["side"]), "source": "/checkouts/main"}, root)[0] == "newer"
    assert runlock.compare(dirty(repo["newer"], "/checkouts/main"),
                           {**code(repo["base"]), "source": "/checkouts/main"}, root)[0] == "differs"   # older
    assert runlock.compare(dirty(repo["side"], "/checkouts/main"),
                           {**code(repo["newer"]), "source": "/checkouts/main"}, root)[0] == "differs"  # diverged
    assert runlock.compare(stamp, {**code(repo["newer"]), "source": "/checkouts/main"}, None)[0] == "differs"


def test_a_dirty_folder_goes_on_after_its_checkout_commits(unit, repo, monkeypatch):  # noqa: F811
    store = P.Store(unit)
    store.code = dirty(repo["base"], "/checkouts/main")
    store.save()
    monkeypatch.setattr(runlock, "code_version", lambda: {**code(repo["newer"]), "source": "/checkouts/main",
                                                          "dirty": False})
    monkeypatch.setattr(runlock, "checkout", lambda: repo["root"])
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), runner=r) == 0 and len(r.calls) == 4
    assert P.Store(unit).code["commit"] == repo["newer"] and not P.Store(unit).code["dirty"]


def test_the_incident_a_newer_commit_elsewhere_cannot_overwrite_uncommitted_work(unit, repo, monkeypatch):  # noqa: F811
    """The owner's checkout at an older HEAD with uncommitted features wrote the folder; a sprint worktree at a
    descendant commit ran on it."""
    store = P.Store(unit)
    store.code = {**dirty(repo["base"], "/checkouts/main"), "at": "2026-10-25T09:00:00", "host": "box"}
    store.save()
    monkeypatch.setattr(runlock, "code_version", lambda: {**code(repo["newer"]), "source": "/checkouts/sprint",
                                                          "dirty": False})
    monkeypatch.setattr(runlock, "checkout", lambda: repo["root"])
    r = Runner(unit)
    with pytest.raises(SystemExit) as e:
        P.drive(Unit.load(unit), steps(), runner=r)
    msg = str(e.value.code)
    assert "refusing to rewrite outputs last written by other code" in msg
    assert f"@ {repo['base'][:12]} with uncommitted changes, written 2026-10-25T09:00:00" in msg
    assert "(the folder was last written by uncommitted code in /checkouts/main)" in msg
    assert r.calls == [] and P.Store(unit).code["dirty"]


def test_an_installed_tool_on_another_commit_warns_and_restamps(unit, monkeypatch, capsys):  # noqa: F811
    """No git checkout (an upgraded `uv tool install`): two known commits it cannot order do not block."""
    stamped(unit, "b" * 40)
    monkeypatch.setattr(runlock, "code_version", lambda: code("c" * 40))
    monkeypatch.setattr(runlock, "checkout", lambda: None)
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), runner=r) == 0 and len(r.calls) == 4
    assert "no git checkout here to tell which commit is newer); going on" in capsys.readouterr().out
    assert P.Store(unit).code["commit"] == "c" * 40


def test_unknown_versions_warn_and_go_on(unit, monkeypatch, capsys):  # noqa: F811
    stamped(unit, "b" * 40)
    monkeypatch.setattr(runlock, "code_version", lambda: code(""))
    assert P.drive(Unit.load(unit), steps(), runner=Runner(unit)) == 0
    assert "warning: cannot compare this code" in capsys.readouterr().out
    assert P.Store(unit).code["commit"] == "b" * 40           # an unknown commit never replaces a known stamp


def test_every_driver_takes_allow_older_code():
    ap = argparse.ArgumentParser()
    P.add_drive_args(ap, ["a"])
    assert ap.parse_args(["--allow-older-code"]).allow_older_code and not ap.parse_args([]).allow_older_code


def test_code_version_reads_the_checkout_or_the_install_record(repo, monkeypatch):
    root = repo["root"]
    monkeypatch.setattr(runlock, "checkout", lambda: root)
    v = runlock.code_version()
    assert v["commit"] == repo["side"] and v["source"] == str(root.resolve()) and v["dirty"] is False
    (root / "notes.txt").write_text("x", encoding="utf8")          # outside src/: not a code change
    assert runlock.code_version()["dirty"] is False
    (root / "src").mkdir()
    (root / "src" / "new.py").write_text("x = 1", encoding="utf8")   # an uncommitted module
    assert runlock.code_version()["dirty"] is True
    monkeypatch.setattr(runlock, "checkout", lambda: None)
    monkeypatch.setattr(runlock, "installed_commit", lambda: "c" * 40)
    assert runlock.code_version()["commit"] == "c" * 40
    monkeypatch.setattr(runlock, "installed_commit", lambda: "")
    assert runlock.code_version()["commit"] == ""
