"""Check a first-run environment without installing software or contacting a model provider."""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import media, workspace

PACKAGES = (("numpy", "numpy"), ("cv2", "opencv-python"),
            ("markdown_it", "markdown-it-py"), ("edge_tts", "edge-tts"))
AGENTS = ("claude", "codex", "agent")


def binary_check(name: str, command: str) -> dict:
    path = shutil.which(command)
    if not path:
        return dict(name=name, status="fail", detail=f"{name} not found; install ffmpeg and ffprobe: "
                    "https://ffmpeg.org/download.html (or set FFMPEG / FFPROBE)")
    try:
        result = subprocess.run([path, "-version"], stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, encoding="utf8", errors="replace", timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return dict(name=name, status="fail", detail=f"{name} could not run within 5 seconds")
    if result.returncode:
        return dict(name=name, status="fail", detail=f"{name} -version exited {result.returncode}")
    return dict(name=name, status="ok", detail=(result.stdout or result.stderr).splitlines()[0]
                if (result.stdout or result.stderr).strip() else f"{name} is executable")


def checks(agent: str | None = None) -> list[dict]:
    rows = [dict(name="Python", status="ok" if sys.version_info[:2] == (3, 11) else "fail",
                 detail=f"{sys.version.split()[0]}; this release needs Python 3.11")]
    for module, distribution in PACKAGES:
        found = importlib.util.find_spec(module) is not None
        try:
            version = importlib.metadata.version(distribution) if found else ""
        except importlib.metadata.PackageNotFoundError:
            version = "available"
        rows.append(dict(name=distribution, status="ok" if found else "fail",
                         detail=version if found else "missing; reinstall the CLI in its Python 3.11 environment"))
    rows += [binary_check("ffmpeg", media.ffmpeg_exe()), binary_check("ffprobe", media.ffprobe_exe())]
    folder = workspace.root().resolve()
    parent = folder
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    try:
        if not parent.is_dir():
            raise NotADirectoryError()
        with tempfile.TemporaryFile(dir=parent):
            pass
        rows.append(dict(name="workspace", status="ok", detail=f"writable parent for {folder}"))
    except OSError:
        rows.append(dict(name="workspace", status="fail", detail="workspace is not writable; set "
                         "SVC_WORKSPACE to a folder you can write"))
    available = [name for name in AGENTS if shutil.which(name)]
    if agent:
        rows.append(dict(name="agent", status="ok" if agent in available else "fail",
                         detail=f"{agent} found (login and image access not checked)" if agent in available else
                         f"{agent} not found; install your agent CLI and sign in before reviewing a video"))
    else:
        rows.append(dict(name="agent", status="ok" if available else "warn",
                         detail=f"{', '.join(available)} found (login and image access not checked)" if available else
                         "no supported agent CLI on PATH; the offline demo still works; your agent app may "
                         "drive the CLI from its own terminal"))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sports-video-coach doctor", description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable checks and next steps")
    ap.add_argument("--agent", choices=AGENTS, help="also require this agent executable (no login or API call)")
    a = ap.parse_args(argv)
    rows = checks(a.agent)
    ok = not any(row["status"] == "fail" for row in rows)
    next_steps = (["sports-video-coach demo --offline", "sports-video-coach run <video> --quick"] if ok else
                  ["Fix the failed checks above, then run sports-video-coach doctor again."])
    if a.json:
        print(json.dumps(dict(ok=ok, checks=rows, next_steps=next_steps), ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"[{row['status']}] {row['name']}: {row['detail']}")
        print("\nReady for the offline demo and local media steps." if ok else "\nSome required checks failed.")
        print("No software installed; no provider contacted. Agent login and image access are checked by your agent.")
        print("\n".join(next_steps))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
