import base64
import gzip
import json

from sports_video_coach import bench
from sports_video_coach.bench import transcript as T

PNG = base64.b64encode(b"\x89PNG" + bytes(range(256)) * 20).decode()


def events():
    """A small Claude Code stream-json transcript with everything the redaction must handle."""
    return [
        {"type": "system", "subtype": "init", "cwd": "C:\\Users\\jdoe\\runs\\r1", "model": "claude-x",
         "tools": ["Read"], "skills": ["secret-skill", "other"], "plugins": [{"name": "p", "path": "/home/jdoe/p"}],
         "memory_paths": {"auto": "C:\\Users\\jdoe\\.claude\\memory"}, "claude_code_version": "2.1.0"},
        {"type": "system", "subtype": "hook_response", "hook_name": "SessionStart:startup",
         "output": "my private context", "stdout": "my private context", "stderr": "", "exit_code": 0},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "tu1", "name": "Read",
             "input": {"file_path": "C:\\Users\\jdoe\\runs\\r1\\frames\\t01.0.jpg"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu1",
             "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": PNG}}]}]},
         "toolUseResult": {"type": "image", "file": {"base64": PNG, "type": "image/png"}}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "tu2", "name": "Bash", "input": {"command": "env; echo $PATH"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tu2", "content": (
            "PATH=/usr/bin:/bin\nHOME=/home/jdoe\nUSER=jdoe\nSHELL=/bin/bash\nLANG=C.UTF-8\nTERM=xterm\n")}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tu3", "content": (
            "/c/Users/jdoe/bin:/usr/local/bin:/usr/bin:/bin:/c/Program Files/x/bin:/mingw64/bin:/opt/y\n"
            "key sk-ant-abcdefghijklmnopqrstuv and ghp_abcdefghijklmnopqrstuvwxyz0123 "
            "ANTHROPIC_API_KEY=abc123def456ghi mail jdoe@example.com, host box-42, jdoe wrote it")}]}},
        {"type": "result", "subtype": "success", "total_cost_usd": 0.5,
         "result": "jump-count: 13, from frames in C:/Users/jdoe/runs/r1\n```json\n{\"answers\": {\"a\": 13}}\n```"},
    ]


def redacted(tmp_path, evs=None, name="t.jsonl", **kw):
    src = tmp_path / "transcript.jsonl"
    src.write_text("\n".join(json.dumps(e) for e in (evs or events())) + "\n", encoding="utf8")
    dst = T.redact(src, tmp_path / name, user=kw.pop("user", "nobody"), host=kw.pop("host", "box-42"), **kw)
    raw = dst.read_bytes()
    text = (gzip.decompress(raw) if name.endswith(".gz") else raw).decode("utf8")
    return text, [json.loads(line) for line in text.splitlines()]


def test_images_become_a_note_with_the_file_name(tmp_path):
    text, evs = redacted(tmp_path)
    assert PNG[:200] not in text
    block = evs[3]["message"]["content"][0]["content"][0]
    assert block["type"] == "text" and block["text"].startswith("[image omitted: t01.0.jpg ")
    assert evs[3]["toolUseResult"]["file"]["base64"].startswith("[image omitted: ")


def test_home_folders_user_host_email_and_keys_are_replaced(tmp_path):
    text, evs = redacted(tmp_path)
    for leak in ("jdoe", "Users\\\\jdoe", "example.com", "box-42", "sk-ant-", "ghp_", "abc123def456ghi",
                 "Program Files"):
        assert leak not in text, leak
    assert evs[0]["cwd"] == "<home>\\runs\\r1"
    final = evs[-1]["result"]
    assert "<home>/runs/r1" in final and "jump-count: 13" in final and '{"answers": {"a": 13}}' in final
    tail = evs[6]["message"]["content"][0]["content"]
    assert tail.startswith("[PATH omitted]") and "<email>" in tail and "<host>" in tail
    assert "[secret omitted]" in tail and "ANTHROPIC_API_KEY=[secret omitted]" in tail
    assert "<user> wrote it" in tail          # the user name learned from a home folder, also outside a path


def test_env_dump_hooks_and_own_config_are_dropped_tool_calls_stay(tmp_path):
    text, evs = redacted(tmp_path)
    assert evs[5]["message"]["content"][0]["content"] == "[environment listing omitted]"
    assert evs[1]["output"].startswith("[hook output omitted") and evs[1]["stderr"] == ""
    assert "my private context" not in text and "secret-skill" not in text
    init = evs[0]
    assert init["skills"] == "[2 omitted]" and init["plugins"] == "[1 omitted]" and "memory_paths" not in init
    assert init["tools"] == ["Read"] and init["model"] == "claude-x"
    assert evs[4]["message"]["content"][0]["input"]["command"] == "env; echo $PATH"
    assert evs[-1]["total_cost_usd"] == 0.5


def test_plain_text_gzip_and_extra_words(tmp_path):
    src = tmp_path / "log.txt"
    src.write_text("workdir: C:\\Users\\jdoe\\r\nTeam Rockets played\n" + "A" * 2000 + "\n", encoding="utf8")
    dst = T.redact(src, tmp_path / "out.txt.gz", words=["Rockets"], user="", host="")
    text = gzip.decompress(dst.read_bytes()).decode("utf8")
    assert text.splitlines() == ["workdir: <home>\\r", "Team <redacted> played", "[base64 omitted: 1 KB]"]


def test_numbers_and_ordinary_words_are_left_alone(tmp_path):
    evs = [{"type": "result", "result": "outputTokens: 551689, token count 12; the author said made, missed",
            "usage": {"cacheReadInputTokens": 551689}}]
    _, out = redacted(tmp_path, evs)
    assert out == evs


def test_cli_writes_next_to_the_source(tmp_path, capsys):
    src = tmp_path / "transcript.jsonl"
    src.write_text(json.dumps(events()[-1]) + "\n", encoding="utf8")
    assert bench.main(["transcript", str(src)]) == 0
    assert (tmp_path / "transcript.redacted.jsonl").exists() and "wrote" in capsys.readouterr().out
    assert T.default_dst(tmp_path / "transcript.txt").name == "transcript.redacted.txt"


def test_a_plain_codex_exec_log_keeps_header_commands_and_reply(tmp_path):
    """`bench run --agent codex --track frames` records codex exec's plain output with stderr merged in."""
    from sports_video_coach.bench import run as R
    log = tmp_path / "transcript.txt"
    log.write_text("Reading additional input from stdin...\nOpenAI Codex v0.159.3\n--------\n"
                   "workdir: C:/Users/jdoe/svc-bench-runs/r1\nmodel: gpt-x\nprovider: openai\napproval: never\n"
                   "sandbox: read-only\nreasoning effort: xhigh\nsession id: 01a1\n--------\nuser\nthe prompt\n"
                   "hook: SessionStart\nhook: SessionStart Completed\n"
                   "2026-10-25T00:00:00Z ERROR codex_core::tools::router: error=code-mode host is disabled\n"
                   "exec\n\"ls\" in C:/Users/jdoe/svc-bench-runs/r1\n succeeded in 5ms:\n"
                   "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuv\ncodex\nmail jdoe@example.com\n"
                   "```json\n{\"a\": 1}\n```\ntokens used\n1,234\n",
                   encoding="utf8")
    out = T.redact(log, tmp_path / "t.redacted.txt.gz", user="jdoe", host="box")
    text = gzip.decompress(out.read_bytes()).decode("utf8")
    assert "jdoe" not in text and "sk-abc" not in text and "example.com" not in text
    assert "workdir: <home>/svc-bench-runs/r1" in text and "hook: SessionStart Completed" in text
    assert "```json\n{\"a\":1}\n```" in text
    plain = tmp_path / "t.redacted.txt"
    plain.write_text(text, encoding="utf8")
    assert R.codex_stats(plain) == {"model": "gpt-x", "effort": "xhigh"}
    assert R.codex_commands(plain) == {"commands_run": 1, "tool_calls_refused": 1}
