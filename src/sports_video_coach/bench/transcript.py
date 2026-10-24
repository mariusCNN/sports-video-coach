"""`sports-video-coach bench transcript <src> <dst>`: a copy of an agent transcript that is safe to publish.

It keeps what shows how the answers were reached (every tool call, the files read, the commands run and their
output, the final reply) and takes out what is about the machine or the person who ran it:

- image payloads (base64) become `[image omitted: <file> <size>]`; other long base64 blobs are dropped too;
- home folders (`C:\\Users\\<name>`, `/c/Users/<name>`, `/home/<name>`, `/Users/<name>`) become `<home>`, and the
  user name, the host name and any `--redact` word become `<user>`, `<host>`, `<redacted>`; e-mail addresses
  become `<email>`;
- a listing of environment variables becomes `[environment listing omitted]`, a PATH value `[PATH omitted]`,
  and anything that looks like a key, token or password `[secret omitted]`;
- in a Claude Code stream-json transcript, the lists of the runner's own skills, plugins, MCP servers, agents and
  commands in the `init` event shrink to a count, its local-only fields (memory folders, extra directories,
  message socket) are dropped, and what the runner's own hooks printed is left out (that they ran stays).

A JSON-lines transcript stays JSON lines (one event per line); any other text is redacted line by line. A
destination ending in `.gz` is gzipped. `bench run` writes one next to every transcript it records.
"""
from __future__ import annotations

import argparse
import getpass
import gzip
import json
import os
import re
import socket
from pathlib import Path

# The runner's own setup, shown only as a count: what was loaded is in the result's settings, the names are theirs.
INIT_COUNTED = ("mcp_servers", "slash_commands", "skills", "plugins", "agents", "terminal_slash_commands")
INIT_DROPPED = ("memory_paths", "additional_directories", "messaging_socket_path", "powershell_path")
HOOK_OUTPUT = ("output", "stdout", "stderr")

SEP = r"(?:\\{1,4}|/)"
HOME = re.compile(r"(?i)(?:\b[a-z]:" + SEP + r"+(?:users|documents and settings)|(?<![\w.])/(?:[a-z]/)?users|"
                  r"(?<![\w.])/home)" + SEP + r"+([^\\/\s\"'<>:|*?`;,]+)")
EMAIL = re.compile(r"[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
SECRETS = [
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"),                       # OpenAI / Anthropic / Stripe style
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),                         # Slack
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                                   # AWS access key id
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),                               # Google API key
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),   # JWT
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*"),
]
# NAME=value / "name": "value" where the name says it is a secret: the value goes, the name stays.
SECRET_ASSIGN = re.compile(r"(?i)\b([\w.-]*(?:api[_-]?key|token|secret|passw(?:or)?d|credential|authorization)"
                           r"[\w.-]*)(\"?\s*[:=]\s*\"?)((?=[^\s\"',;]*[A-Za-z])[^\s\"',;]{8,})")
ENV_LINE = re.compile(r"^\s*(?:declare -x\s+|export\s+|set\s+)?[A-Za-z_][A-Za-z0-9_]*(?:=|\s{2,}\S).*$")
ENV_NAMES = re.compile(r"(?m)^\s*(?:declare -x\s+|export\s+)?(PATH|HOME|USERPROFILE|USERNAME|USER|APPDATA|"
                       r"COMPUTERNAME|HOSTNAME|SHELL|TEMP|TMP|PATHEXT)\b")
# A PATH value (six or more folders in a row), as `echo $PATH` or an error message prints it: it lists the
# programs installed on the machine.
PATH_LIST = re.compile(r"(?:(?:<home>|/)[^:;\n\"']*:){5,}(?:<home>|/)[^:;\n\"']*|"
                       r"(?:(?:<home>|[A-Za-z]:\\)[^;\n\"']*;){5,}(?:<home>|[A-Za-z]:\\)[^;\n\"']*")
BASE64 = re.compile(r"^[A-Za-z0-9+/=\r\n_-]+$")
LONG_B64 = 1000          # a string this long made only of base64 characters is a blob, not text


def kb(n_chars: int) -> str:
    """The decoded size of n base64 characters, as text."""
    n = n_chars * 3 // 4
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


def is_env_dump(text: str) -> bool:
    """A listing of environment variables (env, set, Get-ChildItem env:): many NAME=value lines with the usual
    names among them."""
    lines = [x for x in text.splitlines() if x.strip()]
    if len(lines) < 5:
        return False
    hits = sum(1 for x in lines if ENV_LINE.match(x))
    return hits >= 0.6 * len(lines) and len(set(ENV_NAMES.findall(text))) >= 2


class Redactor:
    def __init__(self, words: list[str] | None = None, user: str | None = None, host: str | None = None):
        self.words: dict[str, str] = {}
        for w, tag in [(user if user is not None else self._user(), "<user>"),
                       (host if host is not None else self._host(), "<host>")] + [(w, "<redacted>")
                                                                                  for w in words or []]:
            if w and len(w.strip()) >= 3:
                self.words.setdefault(w.strip(), tag)
        self.image_names: dict[str, str] = {}   # tool_use id -> the file it read

    @staticmethod
    def _user() -> str:
        try:
            return getpass.getuser()
        except (OSError, KeyError, ImportError):
            return os.environ.get("USERNAME") or os.environ.get("USER") or ""

    @staticmethod
    def _host() -> str:
        try:
            return socket.gethostname()
        except OSError:
            return ""

    def text(self, s: str) -> str:
        if len(s) >= LONG_B64 and BASE64.match(s):
            return f"[base64 omitted: {kb(len(s))}]"
        if is_env_dump(s):
            return "[environment listing omitted]"
        for name in HOME.findall(s):
            if len(name) >= 3:
                self.words.setdefault(name, "<user>")
        s = HOME.sub("<home>", s)
        s = PATH_LIST.sub("[PATH omitted]", s)
        s = EMAIL.sub("<email>", s)
        for rx in SECRETS:
            s = rx.sub("[secret omitted]", s)
        s = SECRET_ASSIGN.sub(lambda m: m.group(1) + m.group(2) + "[secret omitted]", s)
        for w, tag in sorted(self.words.items(), key=lambda kv: -len(kv[0])):
            s = re.sub(r"(?i)(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])", tag, s)
        return s

    def value(self, v, key: str = ""):
        if isinstance(v, str):
            return self.text(v)
        if isinstance(v, list):
            return [self.value(x) for x in v]
        if not isinstance(v, dict):
            return v
        if v.get("type") == "tool_use" and isinstance(v.get("input"), dict):
            path = v["input"].get("file_path") or v["input"].get("path")
            if isinstance(path, str) and isinstance(v.get("id"), str):
                self.image_names[v["id"]] = Path(self.text(path).replace("\\", "/")).name
        if v.get("type") == "tool_result" and isinstance(v.get("tool_use_id"), str):
            name = self.image_names.get(v["tool_use_id"], "")
            return {k: (self.image_blocks(x, name) if k == "content" else self.value(x, k)) for k, x in v.items()}
        if v.get("type") == "image" and isinstance(v.get("source"), dict):
            return self.image(v, "")
        return {k: self.value(x, k) for k, x in v.items()}

    def image_blocks(self, content, name: str):
        if isinstance(content, list):
            return [self.image(x, name) if isinstance(x, dict) and x.get("type") == "image" and "source" in x
                    else self.value(x)
                    for x in content]
        return self.value(content)

    def image(self, block: dict, name: str) -> dict:
        src = block.get("source")
        data = src.get("data") if isinstance(src, dict) else None
        size = f" {kb(len(data))}" if isinstance(data, str) else ""
        return {"type": "text", "text": f"[image omitted: {name or 'image'}{size}]"}

    def event(self, ev):
        if isinstance(ev, dict) and ev.get("type") == "system" and ev.get("subtype") == "init":
            ev = {k: (f"[{len(v)} omitted]" if k in INIT_COUNTED and isinstance(v, list) else v)
                  for k, v in ev.items() if k not in INIT_DROPPED}
        if isinstance(ev, dict) and ev.get("type") == "system" and ev.get("subtype") == "hook_response":
            # the runner's own hooks (with --use-my-config): that they ran stays, what they injected is theirs
            ev = {k: (f"[hook output omitted: {len(v)} chars]" if k in HOOK_OUTPUT and isinstance(v, str) and v.strip()
                      else v) for k, v in ev.items()}
        if isinstance(ev, dict) and isinstance(ev.get("toolUseResult"), dict):
            # Claude Code repeats the tool output here; an image read keeps its bytes under file.base64
            f = ev["toolUseResult"].get("file")
            if isinstance(f, dict) and isinstance(f.get("base64"), str):
                f = dict(f, base64=f"[image omitted: {kb(len(f['base64']))}]")
                ev = dict(ev, toolUseResult=dict(ev["toolUseResult"], file=f))
        return self.value(ev)

    def lines(self, text: str) -> list[str]:
        for name in HOME.findall(text):      # the user name, also where it shows up outside a path
            if len(name) >= 3:
                self.words.setdefault(name, "<user>")
        out = []
        for line in text.splitlines():
            try:
                ev = json.loads(line) if line.lstrip().startswith(("{", "[")) else None
            except ValueError:
                ev = None
            if ev is None:
                out.append(self.text(line))
            else:
                out.append(json.dumps(self.event(ev), ensure_ascii=False, separators=(",", ":")))
        return out


def redact(src: Path, dst: Path, words: list[str] | None = None, user: str | None = None,
           host: str | None = None) -> Path:
    """Write the redacted copy of `src` to `dst` (gzipped if it ends in .gz) and return `dst`."""
    raw = Path(src).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    body = "\n".join(Redactor(words, user, host).lines(raw.decode("utf8", errors="replace"))) + "\n"
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = body.encode("utf8")
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.write_bytes(gzip.compress(data, mtime=0) if dst.suffix == ".gz" else data)
    tmp.replace(dst)
    return dst


def default_dst(src: Path) -> Path:
    """transcript.jsonl -> transcript.redacted.jsonl (next to it)."""
    src = Path(src)
    name = src.name[:-3] if src.name.endswith(".gz") else src.name
    stem, dot, ext = name.rpartition(".")
    return src.with_name(f"{stem}.redacted.{ext}" if dot else f"{name}.redacted")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="sports-video-coach bench transcript",
        description="Write a copy of an agent transcript that is safe to publish: images, home folders, user and "
                    "host names, e-mail addresses, environment listings and key-like strings are taken out; tool "
                    "calls, files read and the final answer stay.")
    ap.add_argument("src", type=Path, help="the transcript (Claude Code stream-json, Codex --json, or plain text)")
    ap.add_argument("dst", type=Path, nargs="?", default=None,
                    help="where to write it (.gz to gzip); default <src stem>.redacted.<ext> next to it")
    ap.add_argument("--redact", action="append", default=[], metavar="WORD",
                    help="one more word to replace (a name, a team, a project); repeat for more")
    a = ap.parse_args(argv)
    if not a.src.is_file():
        ap.error(f"{a.src} is not a file")
    dst = redact(a.src, a.dst or default_dst(a.src), a.redact)
    print(f"wrote {dst} ({dst.stat().st_size / 1024:.0f} KB). Read it before you publish it: the redaction "
          "catches the usual leaks, not every name you may have typed.")
    return 0
