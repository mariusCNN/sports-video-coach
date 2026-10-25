"""One writer per unit folder, and no rewrite by older code: what `pipeline.drive` holds around a run that writes.

- Lock: a run holds an OS advisory lock (flock; Windows: msvcrt.locking) on `<folder>/.run-lock` while it works
  on the folder; the OS drops it when the run's process ends, however it ends, so there is no stale lock to clean
  up. Once it holds the lock the run names itself (pid, host, start time, code version) in `.run-lock.json`, which
  serves only the message of a second run: that one exits 1 naming the holder.
- Code stamp: the run state (`.hoop-steps.json` "code") names the code that last wrote the folder: the package
  version and the commit (a git checkout's HEAD, else the commit uv recorded at install); a checkout also adds its
  path (`source`) and whether src/ has uncommitted changes (`dirty`). A run exits 1 unless `--allow-older-code` when
  its commit is an ancestor of the stamped one (older), when the two diverged or the stamped commit is not in this
  checkout, or when uncommitted code wrote the folder and this run is another checkout (newer commits do not hold
  those changes) or that checkout at a HEAD that is not a descendant (a descendant committed them: newer). Unknown
  commits on either side, or two commits an installed tool (no git) cannot order: a warning, no stop.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from . import installed_commit

LOCK = ".run-lock"        # the file the OS lock is on; never deleted
INFO = ".run-lock.json"   # who holds it
PKG = Path(__file__).resolve().parent


def git(root: Path, *args: str) -> subprocess.CompletedProcess | None:
    """`git -C root args...`, or None when git is missing or hangs."""
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None


@lru_cache(maxsize=1)
def checkout() -> Path | None:
    """The git checkout (clone or worktree) this code runs from, else None (an installed tool; a venv that merely
    sits inside some other repo does not count: the checkout must hold this package at src/sports_video_coach)."""
    r = git(PKG, "rev-parse", "--show-toplevel")
    if not r or r.returncode or not r.stdout.strip():
        return None
    top = Path(r.stdout.strip())
    return top if (top / "src" / "sports_video_coach").resolve() == PKG else None


def code_version() -> dict:
    """{"version": the package version, "commit": the running commit}; '' for what is not known. From a checkout
    also "source" (its path) and "dirty" (src/ has uncommitted changes, untracked files included)."""
    from importlib import metadata
    try:
        version = metadata.version("sports-video-coach")
    except metadata.PackageNotFoundError:
        version = ""
    root = checkout()
    if not root:
        return {"version": version, "commit": installed_commit()}
    r = git(root, "rev-parse", "HEAD")
    commit = r.stdout.strip() if r and not r.returncode else ""
    st = git(root, "status", "--porcelain", "--", "src")
    dirty = bool(st and not st.returncode and st.stdout.strip())
    return {"version": version, "commit": commit, "source": str(root.resolve()), "dirty": dirty}


def shown(code: dict | None) -> str:
    """'sports-video-coach 0.3.1 @ 0123456789ab' (what is known of it)."""
    code = code or {}
    text = f"sports-video-coach {code.get('version') or '(version unknown)'}"
    text += f" @ {code['commit'][:12]}" if code.get("commit") else " (commit unknown)"
    text += " with uncommitted changes" if code.get("dirty") else ""
    if code.get("at"):
        text += f", written {code['at']}" + (f" on {code['host']}" if code.get("host") else "")
    return text


def compare(stamp: dict | None, now: dict, root: Path | None = None) -> tuple[str, str]:
    """(verdict, why) of this run's code against the folder's stamp: 'same', 'newer', 'unknown' (go on), or
    'older', 'differs' (stop without --allow-older-code). `root`: the checkout to compare commits in."""
    old, new = (stamp or {}).get("commit"), now.get("commit")
    if not stamp:
        return "same", ""
    if not old or not new:
        return "unknown", "a commit is not known"
    if stamp.get("dirty"):   # uncommitted changes live only in that checkout, until it commits them
        if stamp.get("source") == now.get("source"):
            if old == new:
                return "same", ""
            if root is not None and ancestor(root, old, new):
                return "newer", ""   # that checkout committed and moved on
        return "differs", f"the folder was last written by uncommitted code in {stamp.get('source') or '?'}"
    if old == new:
        return "same", ""
    if root is None:
        return "unknown", "no git checkout here to tell which commit is newer"
    r = git(root, "cat-file", "-e", f"{old}^{{commit}}")
    if not r or r.returncode:
        return "differs", f"commit {old[:12]} is not in this checkout (git fetch, then run again)"
    if ancestor(root, new, old):
        return "older", f"{new[:12]} is an ancestor of {old[:12]}"
    if ancestor(root, old, new):
        return "newer", ""
    return "differs", "the two commits are on different branches"


def ancestor(root: Path, a: str, b: str) -> bool:
    """Whether commit `a` is an ancestor of commit `b` in the checkout at `root`."""
    return getattr(git(root, "merge-base", "--is-ancestor", a, b), "returncode", 1) == 0


def check(folder: Path, stamp: dict | None, now: dict, allow: bool, hint: str, root: Path | None = None) -> None:
    """Exit 1 with what differs when this run's code is older than (or not provably newer than) the code that
    last wrote the folder, unless `allow`; warn when it cannot tell."""
    verdict, why = compare(stamp, now, checkout() if root is None else root)
    if verdict == "unknown":
        print(f"[run] warning: cannot compare this code with the code that last wrote {folder.name} ({why}); "
              f"going on. Folder: {shown(stamp)}; this run: {shown(now)}")
    if verdict not in ("older", "differs"):
        return
    what = "newer code" if verdict == "older" else "other code that this run cannot show to be older"
    lines = [f"[run] {folder}: refusing to rewrite outputs last written by {what}",
             f"[run]   folder:   {shown(stamp)}",
             f"[run]   this run: {shown(now)} ({why})"]
    if allow:
        print("\n".join(lines).replace("refusing to rewrite", "--allow-older-code: rewriting", 1))
        return
    lines.append("[run] Run the newer code instead (update this checkout or reinstall the tool); to rewrite the "
                 f"outputs with this code anyway: `{hint}`")
    sys.exit("\n".join(lines))


def stamp_for(old: dict | None, now: dict) -> dict:
    """The stamp a writing run leaves: its own code, when its commit is known or the old stamp's is not either."""
    if old and old.get("commit") and not now.get("commit"):
        return old
    return {**now, "at": dt.datetime.now().isoformat(timespec="seconds"), "host": socket.gethostname()}


def locked(fd: int) -> bool:
    """Take a non-blocking exclusive OS lock on open file `fd` (POSIX flock; Windows: byte 0); False when another
    process holds it. The OS drops the lock when its process ends, however it ends."""
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def unlock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def retried(fn, *args):
    """fn(*args), retried for a moment on PermissionError (Windows: another process has the file open)."""
    for _ in range(100):
        try:
            return fn(*args)
        except PermissionError:
            time.sleep(0.02)
    return fn(*args)


def read(path: Path) -> dict:
    """The holder info at `path`, or {} when it is missing or cannot be read."""
    try:
        data = json.loads(retried(path.read_text, "utf8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def holder(info: dict) -> str:
    return (f"pid {info.get('pid', '?')} on {info.get('host', '?')} since {info.get('started', '?')}, "
            f"{shown(info.get('code'))}")


@contextmanager
def hold(folder: Path, code: dict):
    """Hold the OS lock on `<folder>/.run-lock` for the block and name this run in `<folder>/.run-lock.json`; exit 1
    naming the holder when another run holds the lock."""
    folder = Path(folder)
    fd = os.open(folder / LOCK, os.O_CREAT | os.O_RDWR)
    if not locked(fd):
        os.close(fd)
        other = read(folder / INFO)
        who = f"another run is working on this folder ({holder(other)})" if other else "another run holds the lock"
        sys.exit(f"[run] {folder}: {who}.\n[run] Wait for it to end, then run again.")
    try:
        me = {"pid": os.getpid(), "host": socket.gethostname(),
              "started": dt.datetime.now().isoformat(timespec="seconds"), "code": code}
        tmp = folder / f"{INFO}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(me, indent=1), encoding="utf8")
        retried(os.replace, tmp, folder / INFO)
        try:
            yield
        finally:
            retried((folder / INFO).unlink, True)   # while the lock is still ours, so no one else's info goes
    finally:
        unlock(fd)
        os.close(fd)
