"""`bench run --agent openai`: any vision model behind an OpenAI-compatible chat-completions endpoint (Ollama, LM
Studio, vLLM, llama.cpp server, OpenRouter, ...), on the frames track.

A plain model has no tools, so there is no agent CLI: this module is the runner. It sends one request per task: the
frames-track rules, that task's section of TASKS.md and the task's contact sheets as base64 JPEG images (a small
local model has a small context, so one task at a time), and reads the task's answer from the json block at the end
of the reply. The truth is never sent: it is not in the prepared folder. The full-size stills are not sent either.

The transcript (transcript.jsonl) holds every request without its image bytes (file, size and pixel size of each
image instead) and every reply text, so a row can be checked. The API key is read from an environment variable and
only ever goes into the Authorization header; it is never written to any file.
"""
from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import media
from . import frames as F, score as S

NAME = "OpenAI-compatible API"
REQUEST = (
    "You are a contender in a sports film review benchmark (suite {suite}, frames track). "
    "This track measures how well you review film by eye: you get still images of a short video and no way to run "
    "code. Judge by looking only. Work alone and do not ask questions. "
    "The {n} attached images are the contact sheets of task `{task}`, in time order: 25 stills to a sheet, read left "
    "to right, top to bottom, each with its time under it. The full-size stills in frames/ are not available to you; "
    "the sheets are. Answer only this task. End your reply with one line on how you got your answer, then "
    + "`" * 3 + 'json\n{{"{task}": <your answer in the stated format>}}\n' + "`" * 3 + "\n\n"
    "The benchmark's rules and the task follow.\n\n{rules}\n\n{section}"
)


def split_tasks(md: str) -> tuple[str, dict[str, str]]:
    """TASKS.md as (everything before `## Tasks`, {task id: its `### ...` section})."""
    head, _, body = md.partition("\n## Tasks\n")
    sections = {}
    for part in re.split(r"\n(?=### )", body):
        m = re.match(r"### \d+\. `([^`]+)`", part.strip())
        if m:
            sections[m.group(1)] = part.strip()
    return head.strip(), sections


def image(path: Path, max_side: int = 0) -> tuple[str, dict]:
    """A sheet as base64 JPEG (scaled down so its longer side is at most `max_side`, when given) and what the
    transcript records of it."""
    data = Path(path).read_bytes()
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    if max_side and max(w, h) > max_side:
        k = max_side / max(w, h)
        w, h = round(w * k), round(h * k)
        ok, buf = cv2.imencode(".jpg", cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA),
                               [cv2.IMWRITE_JPEG_QUALITY, F.QUALITY])
        if not ok:
            raise RuntimeError(f"could not encode {path}")
        data = buf.tobytes()
    return base64.b64encode(data).decode("ascii"), {"width": w, "height": h, "bytes": len(data)}


def post(url: str, body: dict, key: str, timeout: float) -> dict:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf8"))


def get(url: str, timeout: float = 10, body: dict | None = None) -> dict | None:
    """A JSON GET (or POST with `body`) that never raises: None when it fails."""
    try:
        data = None if body is None else json.dumps(body).encode("utf8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode("utf8"))
        return out if isinstance(out, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def server_info(base_url: str, model: str) -> dict:
    """What the server itself states about itself and the model: an Ollama server answers /api/version and
    /api/show (version, quantization, parameter count); any other server states nothing here."""
    root = re.sub(r"/v1/?$", "", base_url.rstrip("/"))
    ver = get(root + "/api/version")
    if not ver or not isinstance(ver.get("version"), str):
        return {}
    out = {"server": "Ollama", "version": ver["version"]}
    show = get(root + "/api/show", body={"model": model}) or {}
    d = show.get("details") if isinstance(show.get("details"), dict) else {}
    for k in ("quantization_level", "parameter_size"):
        if isinstance(d.get(k), str) and d[k]:
            out[k] = d[k]
    return out


def reply_text(resp: dict) -> tuple[str, str]:
    """(text, finish_reason) of a chat-completions response."""
    choice = (resp.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content")
    if isinstance(content, list):     # some servers return content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return (content if isinstance(content, str) else ""), str(choice.get("finish_reason") or "")


def answer_of(text: str, task_id: str):
    """The task's answer from the last json block of a reply: {"<task id>": answer}, also inside "answers"
    (None when there is none)."""
    from .run import last_json_block
    data = last_json_block(text)
    if isinstance(data, dict) and isinstance(data.get("answers"), dict):
        data = data["answers"]
    return data.get(task_id) if isinstance(data, dict) else None


def run(out: Path, suite: str, seed: int | None, base_url: str, model: str, key: str, timeout: float,
        temperature: float, max_tokens: int, max_side: int, transcript: Path) -> dict:
    """Send every task of the prepared folder `out` to the endpoint, one request per task, until `timeout` seconds
    have passed; write the answers into answers.json and every request and reply into `transcript`. Returns what
    the run did (requests, failures, images, timing)."""
    url = base_url.rstrip("/") + "/chat/completions"
    rules, sections = split_tasks((out / "TASKS.md").read_text(encoding="utf8"))
    tasks = S.suite_tasks(suite, seed).TASKS
    answers = {t.id: None for t in tasks}
    info = {"endpoint": url, "requests": 0, "failed_requests": 0, "timed_out": False, "images": [], "sides": set()}
    t0 = time.monotonic()
    with open(transcript, "w", encoding="utf8") as log:
        def write(ev):
            log.write(json.dumps(ev, ensure_ascii=False) + "\n")
            log.flush()
        for t in tasks:
            left = timeout - (time.monotonic() - t0)
            if left <= 0:
                info["timed_out"] = True
                write({"type": "skipped", "task": t.id, "reason": "time limit reached"})
                continue
            sheets = F.sheets(out, t.id)
            text = REQUEST.format(suite=suite, n=len(sheets), task=t.id, rules=rules, section=sections.get(t.id, ""))
            content, shown = [{"type": "text", "text": text}], []
            for rel in sheets:
                b64, meta = image(out / rel, max_side)
                content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}})
                shown.append({"file": rel, **meta})
                info["sides"].add(max(meta["width"], meta["height"]))
            body = {"model": model, "messages": [{"role": "user", "content": content}],
                    "temperature": temperature, "max_tokens": max_tokens, "stream": False}
            write({"type": "request", "task": t.id, "url": url, "model": model, "temperature": temperature,
                   "max_tokens": max_tokens, "images": shown, "prompt": text})
            info["requests"] += 1
            info["images"].append(len(sheets))
            r0 = time.monotonic()
            try:
                resp = post(url, body, key, left)
            except (OSError, ValueError, urllib.error.URLError) as e:
                info["failed_requests"] += 1
                if isinstance(e, TimeoutError) or "timed out" in str(e):
                    info["timed_out"] = True
                detail = ""
                if isinstance(e, urllib.error.HTTPError):
                    try:
                        detail = e.read().decode("utf8", errors="replace")[:2000]
                    except OSError:
                        pass
                write({"type": "error", "task": t.id, "seconds": round(time.monotonic() - r0, 1),
                       "error": f"{type(e).__name__}: {e}", "body": detail})
                continue
            reply, finish = reply_text(resp)
            answers[t.id] = answer_of(reply, t.id)
            write({"type": "reply", "task": t.id, "seconds": round(time.monotonic() - r0, 1), "text": reply,
                   "finish_reason": finish, "model": resp.get("model"), "usage": resp.get("usage")})
            write({"type": "answer", "task": t.id, "answer": answers[t.id]})
    fresh = {} if seed is None else {"seed": seed}
    media.write_json_atomic(out / "answers.json",
                            {"suite": suite, "track": "frames", **fresh,
                             "answers": answers})
    info["sides"] = sorted(info["sides"])
    return info


def settings(info: dict, server: dict, temperature: float, max_tokens: int, max_side: int) -> str:
    """The result's settings: everything about how the model was asked, as the run did it."""
    kind = (f"{server['server']} {server['version']}" if server.get("server") else "an OpenAI-compatible server")
    weights = ", ".join(server[k] for k in ("quantization_level", "parameter_size") if server.get(k))
    imgs = info["images"]
    per = f"{min(imgs)}-{max(imgs)}" if imgs and min(imgs) != max(imgs) else f"{imgs[0]}" if imgs else "0"
    sides = "/".join(str(x) for x in info["sides"]) or "-"
    size = (f"sheets scaled to at most {max_side} px on the longer side ({sides} px)" if max_side else
            f"sheets as drawn ({sides} px on the longer side)")
    return "; ".join(x for x in (
        f"frames track; OpenAI-compatible chat completions on {kind}" + (f", weights {weights}" if weights else ""),
        f"one request per task ({info['requests']} requests, {per} contact sheets each as base64 JPEG, {size}), "
        "the task's section of TASKS.md and the rules in the prompt, no full-size stills, no tools",
        f"temperature {temperature:g}, max_tokens {max_tokens}",
    ) if x)
