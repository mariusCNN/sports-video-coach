"""`sports-video-coach serve <folder> [--port N]`: serve a report folder over http for a browser check.

Picks the first free port from --port (default 18080) on 127.0.0.1, prints the URL and the page title (check the
browser shows that title: another server on a busy port would show another page), and serves until stopped
(Ctrl+C). A port is free only when nothing answers on it and an exclusive bind works: Python's own http.server
binds with SO_REUSEADDR, which on Windows lets two servers share a port silently.
"""
from __future__ import annotations

import argparse
import functools
import html
import re
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
FIRST_PORT = 18080
TRIES = 50


class Server(ThreadingHTTPServer):
    allow_reuse_address = False   # never share a port with another server
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):   # Windows: refuse a port another socket holds
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def answers(port: int, host: str = HOST) -> bool:
    """True when something already accepts connections on host:port."""
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def open_server(folder: Path, first: int = FIRST_PORT, tries: int = TRIES, host: str = HOST) -> Server:
    """A server for `folder` on the first free port from `first`; SystemExit when none of `tries` ports is free."""
    handler = functools.partial(Quiet, directory=str(folder))
    for port in range(first, first + tries):
        if answers(port, host):
            continue
        try:
            return Server((host, port), handler)
        except OSError:
            continue
    sys.exit(f"serve: no free port in {first}-{first + tries - 1}; pass another start with --port")


def page_title(folder: Path) -> str:
    """The <title> of folder/index.html, '' without one."""
    p = folder / "index.html"
    if not p.exists():
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", p.read_text(encoding="utf8", errors="replace"), re.S | re.I)
    return html.unescape(m[1]).strip() if m else ""


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach serve", description=__doc__.split("\n\n")[1])
    ap.add_argument("folder", type=Path, help="a report folder (with index.html)")
    ap.add_argument("--port", type=int, default=FIRST_PORT, help=f"first port to try (default {FIRST_PORT})")
    a = ap.parse_args(argv)
    if not a.folder.is_dir():
        sys.exit(f"serve: {a.folder} is not a folder")
    srv = open_server(a.folder.resolve(), a.port)
    url = f"http://{HOST}:{srv.server_address[1]}/"
    title = page_title(a.folder)
    print(f"serving {a.folder} at {url}" + (f"\npage title: {title!r} (check the browser shows it)" if title else
                                            "\nno index.html in it yet"), flush=True)
    print("stop with Ctrl+C", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
