"""Training-plan app: program.json is validated and inlined safely, publish puts it at /p/<token>/, and the Worker
stores its synced progress only for published plans and same-origin writes."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hoop_tape_miner import program
from sports_video_coach import publish

EXAMPLE = Path(__file__).parents[1] / "templates" / "program.example.json"
WORKER = Path(publish.__file__).with_name("publish_worker.js")


def plan_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "players" / "p0" / "program" / "2026-11-02"
    folder.mkdir(parents=True)
    shutil.copy(EXAMPLE, folder / "program.json")
    return folder


def test_example_program_is_valid():
    assert program.validate(json.loads(EXAMPLE.read_text(encoding="utf8"))) == []


def test_validate_names_unknown_sessions_and_exercises():
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    plan["weekdays"]["5"] = "X"
    plan["sessions"]["M"]["items"][0]["ex"] = "nope"
    errors = program.validate(plan)
    assert any("unknown session 'X'" in e for e in errors)
    assert any("sessions[M].items[0]: unknown exercise 'nope'" in e for e in errors)
    assert program.validate({"title": "x"})[0].startswith("missing key")


def test_page_inlines_data_fragments_and_verified_videos_only(tmp_path):
    folder = plan_folder(tmp_path)
    plan = json.loads((folder / "program.json").read_text(encoding="utf8"))
    plan["title"] = "A & B"
    plan["exercises"]["W"]["how"] = "</script><script>alert(1)</script>"
    (folder / "program.json").write_text(json.dumps(plan), encoding="utf8")
    (folder / "videos.json").write_text(json.dumps({"videos": {"warmup": [
        {"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "ok", "verified": True},
        {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "gone", "verified": False}]}}),
        encoding="utf8")
    (folder / "game.html").write_text('<div class="card">game notes</div>\n', encoding="utf8")
    page = program.page(folder)
    assert "<title>A &amp; B</title>" in page
    assert page.count("<script>") == 1 and page.count("</script>") == 1  # the data cannot close the script
    assert '\\u003c/script>' in page
    assert "game notes" in page and "aaaaaaaaaaa" in page and "bbbbbbbbbbb" not in page
    for marker in ("/*PLAN*/", "/*VIDEOS*/", "/*REFS*/", "<!--TITLE-->", "<!--CAL-->", "<!--LIB-->"):
        assert marker not in page


def test_page_script_parses(tmp_path):
    if not shutil.which("node"):
        pytest.skip("needs node")
    page = program.page(plan_folder(tmp_path))
    js = page[page.index("<script>") + 8:page.rindex("</script>")]
    (tmp_path / "app.js").write_text(js, encoding="utf8")
    r = subprocess.run(["node", "--check", "app.js"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def test_build_exits_on_invalid_program(tmp_path):
    folder = plan_folder(tmp_path)
    plan = json.loads((folder / "program.json").read_text(encoding="utf8"))
    plan["special"]["2026-11-04"] = "missing"
    (folder / "program.json").write_text(json.dumps(plan), encoding="utf8")
    with pytest.raises(SystemExit):
        program.build(folder)


def test_publish_puts_program_under_p_with_stable_link(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    folder = plan_folder(tmp_path)
    publish.main([str(folder)])
    reg = json.loads((tmp_path / "publish.json").read_text(encoding="utf8"))
    key = "players/p0/program/2026-11-02"
    tok = reg["programs"][key]
    page = (tmp_path / "site" / "p" / tok / "index.html").read_text(encoding="utf8")
    assert "script-src 'sha256-" in page  # the app's script pinned by hash
    assert key not in reg["reports"] and "hub" not in reg  # never listed on the team hub
    publish.main([str(folder)])
    assert json.loads((tmp_path / "publish.json").read_text(encoding="utf8"))["programs"][key] == tok


def test_worker_config_binds_sync_kv(tmp_path):
    cfg = json.loads(publish.worker_config(tmp_path / "site", "team-film", tmp_path / "w", "abc123")
                     .read_text(encoding="utf8"))
    assert cfg["kv_namespaces"] == [{"binding": "SYNC", "id": "abc123"}]
    cfg = json.loads(publish.worker_config(tmp_path / "site", "team-film", tmp_path / "w").read_text(encoding="utf8"))
    assert "kv_namespaces" not in cfg


NODE_SYNC = r"""
import worker from "./worker.mjs";
const TOK = "0123456789abcdef", OTHER = "fedcba9876543210", kv = new Map(), puts = [];
const env = {
  ASSETS: { async fetch(req) {
    const path = new URL(req.url).pathname;
    return path === `/p/${TOK}/` ? new Response("<!doctype html>", { status: 200, headers: { "Content-Type": "text/html" } })
                                 : new Response("nope", { status: 404 });
  } },
  SYNC: { async get(k) { return kv.has(k) ? kv.get(k) : null; },
          async put(k, v, o) { puts.push([k, o || null]); kv.set(k, v); } },
};
const O = "https://x.dev", body = JSON.stringify({ updated: 5, s: { a: 1 } });
const out = {};
for (const [name, url, init] of [
    ["page", `${O}/p/${TOK}/`, {}],
    ["empty", `${O}/api/sync/${TOK}`, {}],
    ["foreign", `${O}/api/sync/${TOK}`, { method: "PUT", body, headers: { Origin: "https://evil.dev" } }],
    ["unknown", `${O}/api/sync/${OTHER}`, { method: "PUT", body, headers: { Origin: O } }],
    ["badjson", `${O}/api/sync/${TOK}`, { method: "PUT", body: "{", headers: { Origin: O } }],
    ["noupdated", `${O}/api/sync/${TOK}`, { method: "PUT", body: "[1]", headers: { Origin: O } }],
    ["big", `${O}/api/sync/${TOK}`, { method: "PUT", body: JSON.stringify({ updated: 1, x: "a".repeat(300000) }), headers: { Origin: O } }],
    ["put", `${O}/api/sync/${TOK}`, { method: "PUT", body, headers: { Origin: O } }],
    ["put2", `${O}/api/sync/${TOK}`, { method: "PUT", body, headers: { Origin: O } }],
    ["get", `${O}/api/sync/${TOK}`, {}],
    ["delete", `${O}/api/sync/${TOK}`, { method: "DELETE" }]]) {
  const r = await worker.fetch(new Request(url, init), env);
  out[name] = { status: r.status, headers: Object.fromEntries(r.headers), text: await r.text() };
}
out.puts = puts;
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_worker_sync_api(tmp_path):
    shutil.copy(WORKER, tmp_path / "worker.mjs")
    (tmp_path / "check.mjs").write_text(NODE_SYNC, encoding="utf8")
    r = subprocess.run(["node", "check.mjs"], cwd=tmp_path, capture_output=True, text=True, encoding="utf8",
                       timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["empty"]["status"] == 200 and json.loads(out["empty"]["text"]) == {"updated": 0}
    assert out["empty"]["headers"]["cache-control"] == "no-store"
    assert out["foreign"]["status"] == 403 and out["unknown"]["status"] == 404
    assert out["badjson"]["status"] == 400 and out["noupdated"]["status"] == 400 and out["big"]["status"] == 413
    assert out["put"]["status"] == 200 and json.loads(out["get"]["text"]) == {"updated": 5, "s": {"a": 1}}
    assert out["delete"]["status"] == 405
    keys = [k for k, _ in out["puts"]]
    # two writes of the main key, one daily backup with an expiry
    assert keys.count("sync:0123456789abcdef") == 2
    backups = [o for k, o in out["puts"] if k != "sync:0123456789abcdef"]
    assert len(backups) == 1 and backups[0]["expirationTtl"] == 60 * 86400
    page = out["page"]["headers"]
    assert page["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-src https://www.youtube-nocookie.com" in page["content-security-policy"]
    assert "connect-src 'self'" in page["content-security-policy"]
    assert out["get"]["headers"]["referrer-policy"] == "no-referrer"  # only plan pages send a referrer
