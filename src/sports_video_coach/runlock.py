"""One writer per unit folder, and no rewrite by older code: what `pipeline.drive` holds around a run that writes.

- Lock: `<folder>/.run-lock.json` (pid, host, start time, code version) exists while a run works on the folder. A
  second run exits 1 naming the holder; a lock whose process is gone (same host) is taken over with a warning, by
  exactly one run. A lock from another host cannot be checked: it holds until that run ends or someone deletes
  the file. The lock is made with its content in one step (hard link), and one that cannot be read counts as
  held for UNREADABLE_GRACE seconds.
- Code stamp: the run state (`.hoop-steps.json` "code") names the code that last wrote the folder: the package
  version and the commit (a git checkout's HEAD, else the commit uv recorded at install); a checkout also adds its
  path (`source`) and whether src/ has uncommitted changes (`dirty`). A run exits 1 unless `--allow-older-code` when
  its commit is an ancestor of the stamped one (older), when the two diverged or the stamped commit is not in this
  checkout, or when uncommitted code wrote the folder and this run is another checkout (newer commits do not hold
  those changes) or that checkout at a HEAD that is not a descendant (it committed and moved on: newer). Unknown commits on either side, or two commits an installed tool (no git)
  cannot order: a warning, no stop.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from . import installed_commit

LOCK = ".run-lock.json"
UNREADABLE_GRACE = 60   # seconds an unreadable lock counts as held (a run may be writing it)
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


def alive(pid: int) -> bool:
    """Whether process `pid` runs on this host (Windows: OpenProcess, since os.kill there would end it)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5   # access denied: it exists
        try:
            code = wintypes.DWORD()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read(path: Path) -> dict | None:
    """The lock's JSON: None when there is no file, {} when it cannot be read or parsed (empty, partial)."""
    raw = snapshot(path)
    if raw is None:
        return None
    try:
        data = json.loads(raw.decode("utf8"))
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def snapshot(path: Path) -> bytes | None:
    """The file's bytes; None when it is missing, b'' when it cannot be read."""
    try:
        return retried(path.read_bytes)
    except FileNotFoundError:
        return None
    except OSError:
        return b""


def retried(fn, *args):
    """fn(*args), retried for a moment on PermissionError (Windows: another process has the file open)."""
    for _ in range(100):
        try:
            return fn(*args)
        except PermissionError:
            time.sleep(0.02)
    return fn(*args)


def create(path: Path, info: dict) -> bool:
    """Make `path` holding `info` in one step, only if it does not exist: the JSON goes to a unique temp file that
    is then hard-linked to `path` (atomic on NTFS and POSIX), so no reader ever sees it empty or half written."""
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(info, indent=1), encoding="utf8")
    try:
        os.link(tmp, path)
        return True
    except FileExistsError:
        return False
    except OSError:   # no hard links here (some network or FAT drives): create, then write; a reader that sees it
        try:          # empty meanwhile counts it as held (UNREADABLE_GRACE)
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf8") as f:
            json.dump(info, f, indent=1)
        return True
    finally:
        retried(tmp.unlink, True)


def age(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0.0


def holder(info: dict) -> str:
    return (f"pid {info.get('pid', '?')} on {info.get('host', '?')} since {info.get('started', '?')}, "
            f"{shown(info.get('code'))}")


def take_over(path: Path, raw: bytes, me: dict) -> bool:
    """Replace the stale lock whose bytes were `raw` with ours; one taker wins. The takers race for a guard file
    (made like the lock); the winner re-reads the lock and replaces it only when it is still those bytes, with
    os.replace, so the lock never goes missing for a fresh run to slip in."""
    guard = path.with_name(path.name + ".takeover")
    if not create(guard, me):
        if age(guard) > UNREADABLE_GRACE:   # a taker died inside the guard
            retried(guard.unlink, True)
        return False
    try:
        if snapshot(path) != raw:
            return False   # another taker won, or the lock changed
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(me, indent=1), encoding="utf8")
        try:
            retried(os.replace, tmp, path)
        except OSError:
            retried(tmp.unlink, True)
            raise
        return True
    finally:
        retried(guard.unlink, True)


@contextmanager
def hold(folder: Path, code: dict):
    """Hold `<folder>/.run-lock.json` for the block; exit 1 when a live run holds it (a dead one's is taken over by
    exactly one run; one that cannot be read counts as held until it is UNREADABLE_GRACE seconds old)."""
    path = Path(folder) / LOCK
    me = {"pid": os.getpid(), "host": socket.gethostname(),
          "started": dt.datetime.now().isoformat(timespec="seconds"), "code": code, "token": uuid.uuid4().hex}
    for _ in range(200):
        if create(path, me):
            break
        raw = snapshot(path)
        if raw is None:
            continue   # it ended just now
        other = read(path)
        if not other:
            if age(path) <= UNREADABLE_GRACE:
                sys.exit(f"[run] {folder}: another run may be starting on this folder: {path.name} cannot be read "
                         f"({age(path):.0f} s old).\n[run] Run again in a minute; a lock still unreadable after "
                         f"{UNREADABLE_GRACE} s is taken over.")
        elif other.get("host") != me["host"] or alive(int(other.get("pid") or 0)):
            sys.exit(f"[run] {folder}: another run is working on this folder ({holder(other)}).\n"
                     f"[run] Wait for it to end, then run again. If that run is gone (it crashed, or ran on "
                     f"another machine), delete {path} and run again.")
        if take_over(path, raw, me):
            print(f"[run] warning: taking over a stale lock ({holder(other) if other else 'unreadable'}): "
                  "that run is gone")
            break
        time.sleep(0.05)   # another run is taking it over: look again
    else:
        sys.exit(f"[run] {folder}: could not take {path}; run again")
    try:
        yield
    finally:
        if (read(path) or {}).get("token") == me["token"]:
            retried(path.unlink, True)
