"""`bench run --agent openai`: a vision model behind an OpenAI-compatible endpoint, against a local fake server."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sports_video_coach import bench
from sports_video_coach.bench import api as A, run as R, score as S, suite

TRUTH = {t.id: t.truth for t in suite.TASKS}
KEY = "sk-test-0123456789abcdefghij"


@pytest.fixture
def stills(monkeypatch):
    """Every task draws a 30-frame grey video, so the frames track has real stills and sheets to send."""
    import cv2
    import numpy as np

    def tiny(out):
        w = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), suite.FPS, (160, 90))
        for i in range(30):
            w.write(np.full((90, 160, 3), i * 8, dtype=np.uint8))
        w.release()
        return out
    monkeypatch.setattr(suite.Task, "draw", property(lambda t: tiny), raising=False)


@pytest.fixture
def server():
    """A fake chat-completions server: it answers each task with the truth in a json block (or `reply`), and
    records every request. `ollama` makes it answer /api/version and /api/show like Ollama."""
    state = {"requests": [], "reply": None, "ollama": False, "status": 200}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, obj):
            data = json.dumps(obj).encode("utf8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/api/version" and state["ollama"]:
                return self.send(200, {"version": "0.0.1-test"})
            self.send(404, {"error": "not found"})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/api/show" and state["ollama"]:
                return self.send(200, {"details": {"quantization_level": "Q4_K_M", "parameter_size": "4.4B"}})
            if self.path != "/v1/chat/completions":
                return self.send(404, {"error": "not found"})
            state["requests"].append({"headers": dict(self.headers), "body": body})
            if state["status"] != 200:
                return self.send(state["status"], {"error": "boom"})
            text = body["messages"][0]["content"][0]["text"]
            task = next(t for t in TRUTH if f"task `{t}`" in text)
            reply = state["reply"] if state["reply"] is not None else \
                f"by eye\n```json\n{json.dumps({task: TRUTH[task]})}\n```"
            self.send(200, {"model": body["model"], "choices": [{"message": {"role": "assistant", "content": reply},
                                                                 "finish_reason": "stop"}],
                            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    state["url"] = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    yield state
    srv.shutdown()


def run(tmp_path, server, *extra):
    out = tmp_path / "run"
    code = bench.main(["run", "--agent", "openai", "--track", "frames", "--base-url", server["url"],
                       "--model", "vis-1:4b", "--out", str(out), *extra])
    return code, out


def result_of(out):
    files = [p for p in out.glob("*.json") if p.name not in ("answers.json", "run.json")]
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf8"))


def test_one_request_per_task_with_its_sheets_and_the_answers_scored(tmp_path, stills, server, capsys):
    code, out = run(tmp_path, server)
    assert code == 0
    reqs = server["requests"]
    assert len(reqs) == len(suite.TASKS)
    for t, req in zip(suite.TASKS, reqs):
        body = req["body"]
        assert body["model"] == "vis-1:4b" and body["temperature"] == 0 and body["stream"] is False
        content = body["messages"][0]["content"]
        assert content[0]["type"] == "text" and f"task `{t.id}`" in content[0]["text"]
        imgs = [c for c in content[1:] if c["type"] == "image_url"]
        assert len(imgs) == len(content) - 1 == len(R.F.sheets(out, t.id))
        assert all(c["image_url"]["url"].startswith("data:image/jpeg;base64,") for c in imgs)
        assert "Authorization" not in req["headers"]
        other = [x.id for x in suite.TASKS if x.id != t.id]
        assert not any(f"`{o}` (" in content[0]["text"] for o in other)   # only this task's section
    res = result_of(out)
    assert res["track"] == "frames" and res["total"] == 1.0 and not S.problems(res)
    c = res["contender"]
    assert c["agent"] == A.NAME and c["model"] == "vis-1:4b" and c["agent_version"] == ""
    assert f"{len(suite.TASKS)} requests" in c["settings"] and "temperature 0" in c["settings"]
    assert "one request per task" in c["settings"] and "no tools" in c["settings"]
    run_ = json.loads((out / "run.json").read_text(encoding="utf8"))
    assert run_["requests"] == len(suite.TASKS) and run_["failed_requests"] == 0 and not run_["timed_out"]
    events = [json.loads(x) for x in (out / "transcript.jsonl").read_text(encoding="utf8").splitlines()]
    assert [e["type"] for e in events[:3]] == ["request", "reply", "answer"]
    assert "base64," not in (out / "transcript.jsonl").read_text(encoding="utf8")     # no image bytes
    assert events[0]["images"][0]["file"].startswith("sheets/") and events[0]["images"][0]["bytes"] > 0
    assert (out / "transcript.redacted.jsonl").exists() and not (out / "PROMPT.txt").exists()


def test_ollama_server_names_itself_and_the_weights(tmp_path, stills, server):
    server["ollama"] = True
    code, out = run(tmp_path, server, "--image-max-side", "640", "--settings", "context 32768")
    res = result_of(out)
    c = res["contender"]
    assert c["agent"] == "Ollama" and c["agent_version"] == "0.0.1-test"
    assert "Ollama 0.0.1-test, weights Q4_K_M, 4.4B" in c["settings"] and c["settings"].endswith("context 32768")
    assert "at most 640 px" in c["settings"]
    widths = {i["width"] for e in map(json.loads, (out / "transcript.jsonl").read_text(encoding="utf8")
                                      .splitlines()) if e["type"] == "request" for i in e["images"]}
    assert widths == {640}


def test_api_key_comes_from_the_env_and_is_never_written(tmp_path, stills, server, monkeypatch):
    monkeypatch.setenv("TEST_VIS_KEY", KEY)
    code, out = run(tmp_path, server, "--api-key-env", "TEST_VIS_KEY")
    assert code == 0
    assert all(r["headers"]["Authorization"] == f"Bearer {KEY}" for r in server["requests"])
    for p in out.rglob("*"):
        if p.is_file() and p.suffix in (".json", ".jsonl", ".txt", ".md"):
            assert KEY not in p.read_text(encoding="utf8", errors="replace"), p


def test_missing_key_env_is_an_error(tmp_path, server, monkeypatch):
    monkeypatch.delenv("TEST_VIS_KEY", raising=False)
    with pytest.raises(SystemExit):
        run(tmp_path, server, "--api-key-env", "TEST_VIS_KEY")
    assert not server["requests"]


def test_a_bad_reply_scores_zero_and_a_server_error_is_recorded(tmp_path, stills, server):
    server["reply"] = "I cannot tell from these images."
    code, out = run(tmp_path, server)
    assert code == 0 and result_of(out)["total"] == 0.0
    assert all(v is None for v in S.read_answers(out).values())
    server["reply"], server["status"] = None, 500
    out2 = tmp_path / "run2"
    assert bench.main(["run", "--agent", "openai", "--track", "frames", "--base-url", server["url"],
                       "--model", "m", "--out", str(out2)]) == 0
    run_ = json.loads((out2 / "run.json").read_text(encoding="utf8"))
    assert run_["failed_requests"] == run_["requests"] == len(suite.TASKS)
    events = [json.loads(x) for x in (out2 / "transcript.jsonl").read_text(encoding="utf8").splitlines()]
    assert any(e["type"] == "error" and "500" in e["error"] for e in events)
    assert result_of(out2)["total"] == 0.0


def test_the_code_track_is_refused(tmp_path, server, capsys):
    with pytest.raises(SystemExit):
        bench.main(["run", "--agent", "openai", "--base-url", server["url"], "--model", "m",
                    "--out", str(tmp_path / "run")])
    assert "frames track only" in capsys.readouterr().err and not server["requests"]


def test_base_url_and_model_are_required_and_only_for_openai(tmp_path, capsys):
    with pytest.raises(SystemExit):
        bench.main(["run", "--agent", "openai", "--track", "frames", "--model", "m", "--out", str(tmp_path / "a")])
    with pytest.raises(SystemExit):
        bench.main(["run", "--agent", "claude", "--base-url", "http://x/v1", "--out", str(tmp_path / "b")])
    assert "only for --agent openai" in capsys.readouterr().err


def test_answer_of_reads_the_task_from_the_last_json_block():
    assert A.answer_of('x\n```json\n{"a": 1}\n```\n```json\n{"a": 2}\n```', "a") == 2
    assert A.answer_of('```json\n{"answers": {"a": [1.5]}}\n```', "a") == [1.5]
    assert A.answer_of('```json\n{"b": 1}\n```', "a") is None
    assert A.answer_of("```json\nnot json\n```", "a") is None and A.answer_of("", "a") is None


def test_split_tasks_keeps_the_rules_and_one_section_per_task(tmp_path):
    md = bench.tasks_md("svc-bench-3", "frames")
    rules, sections = A.split_tasks(md)
    assert "## Rules" in rules and "### " not in rules
    assert list(sections) == [t.id for t in S.SUITES["svc-bench-3"].TASKS]
    assert all(s.startswith("### ") for s in sections.values())
