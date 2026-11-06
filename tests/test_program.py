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


def test_learning_goals_require_evidence_and_versions():
    plan = json.loads(EXAMPLE.read_text(encoding='utf8'))
    goal = dict(id='catch-read', version='v1', title='Read the defender', when='Before the catch',
                action='Prepare a shot with room', exception='Pass when the receiver has the better opening',
                practice='Vary the approach', measure='Record opportunities separately', source_url='https://example.org/play')
    plan.setdefault('game', {})['learning_goals'] = [goal]
    assert not program.validate(plan)
    goal['source_url'] = 'javascript:alert(1)'
    assert any('source_url' in e for e in program.validate(plan))
    goal['version'] = ''
    assert any('version' in e for e in program.validate(plan))


@pytest.mark.skipif(not shutil.which('node'), reason='needs node')
def test_learning_log_preserves_unknown_counts_and_prior_versions(tmp_path):
    engine = program.ENGINE.read_text(encoding='utf8')
    code = engine[engine.index('const LEARN_COUNTS ='):engine.index('function renderLog()')]
    script = 'const assert=require("node:assert/strict");\n' + code + r'''
const draft={}, goal={id:'read',version:'v1',title:'Read',source_url:'https://example.org'};
const first=lessonTrial(draft,goal);
assert.equal(first.opportunities,null);
assert.equal(changeLessonCount(first,'opportunities',-1),true);
assert.equal(first.opportunities,0);
assert.equal(changeLessonCount(first,'decisions',1),false);
changeLessonCount(first,'opportunities',1);
changeLessonCount(first,'decisions',1);
assert.equal(changeLessonCount(first,'opportunities',-1),false);
const next=lessonTrial(draft,{...goal,version:'v2'});
assert.equal(next.opportunities,null);
assert.equal(draft.lesson_trials['read:v1'].decisions,1);
assert.equal(first.outcomes,null);
'''
    (tmp_path / 'learning.cjs').write_text(script, encoding='utf8')
    result = subprocess.run(['node', 'learning.cjs'], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_audio_starts_at_125_even_with_legacy_saved_speed(tmp_path):
    engine = program.ENGINE.read_text(encoding="utf8")
    pref = next(line for line in engine.splitlines() if line.startswith("const apref ="))
    script = 'const assert = require("node:assert/strict");\n'
    script += 'for (const saved of [null, "{", JSON.stringify({rate:1,loop:false}), JSON.stringify({rate:1.5})]) {\n'
    script += 'const AKEY="test", localStorage={getItem:()=>saved};\n' + pref + '\n'
    script += 'assert.equal(apref.rate,1.25); if(saved?.includes("false")) assert.equal(apref.loop,false);\n}\n'
    (tmp_path / "audio.cjs").write_text(script, encoding="utf8")
    r = subprocess.run(["node", "audio.cjs"], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


def briefing_example():
    profile = {"title": "Read before play", "cues": [
        {"cue": "Look first", "action": "Read the help defender", "check": "Count the right reads"}],
        "timeline": [{"when": "30 minutes before", "text": "Review the cue"}], "watch": [], "recap": []}
    return {mode: dict(profile) for mode in ("training", "league", "half", "full")}


@pytest.mark.parametrize("field,value,issue", [
    ("priority", None, "priority: must be an object"),
    ("priority", {"title": "Current focus", "cues": []}, "priority.cues: give one to three cues"),
    ("training", None, "training: must be an object"),
    ("sessions", [], "sessions: must be an object"),
    ("sessions", {"unknown": {}}, "unknown session"),
    ("training", {"title": "X", "cues": []}, "one to three cues"),
    ("training", {"title": "X", "cues": [None]}, "each needs cue"),
    ("training", {"title": "X", "cues": [], "timeline": ["bad"]}, "when/text strings"),
    ("training", {"title": "X", "cues": [], "watch": "bad"}, "list of strings"),
])
def test_briefing_validation_reports_bad_profiles(field, value, issue):
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    plan["briefing"] = briefing_example()
    plan["briefing"][field] = value
    assert any(issue in error for error in program.validate(plan))


def test_briefing_accepts_session_overrides_and_escapes_script_data(tmp_path):
    folder = plan_folder(tmp_path)
    plan = json.loads((folder / "program.json").read_text(encoding="utf8"))
    plan["briefing"] = briefing_example()
    plan["briefing"]["sessions"] = {"G": {"title": "Morning shooting </script>"}}
    plan["briefing"]["priority"] = dict(plan["briefing"]["training"], title="Priority </script>")
    assert program.validate(plan) == []
    (folder / "program.json").write_text(json.dumps(plan), encoding="utf8")
    page = program.page(folder)
    assert "Morning shooting \\u003c/script>" in page
    assert "Priority \\u003c/script>" in page
    assert page.count("</script>") == 1


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_briefing_browser_model_uses_date_fixture_and_explicit_mode(tmp_path):
    engine = program.ENGINE.read_text(encoding="utf8")
    model = engine[engine.index("const EX = PLAN.exercises"):engine.index("/* icons (lucide paths)")]
    brief = engine[engine.index("const BRIEF = PLAN.briefing;"):engine.index("function renderBrief()")]
    plan = {"start": "2025-03-03", "week1": "2025-03-03", "days": 14, "phases": ["Practice"] * 3,
            "exercises": {}, "sessions": {"M": {}, "G": {"game": "league"}, "P": {"game": "half"}},
            "weekdays": {str(k): "P" if k == 0 else "G" if k == 3 else "M" for k in range(7)},
            "special": {"2025-03-12": "M"}, "fixture": {"games": [
                {"date": "2025-03-05", "bye": True},
                {"date": "2025-03-12", "time": "19:30", "vs": "Team B"}]},
            "briefing": briefing_example()}
    plan["briefing"]["sessions"] = {"M": {"title": "Today's training"}}
    script = 'const assert = require("node:assert/strict"); const location = {hash:""};\n'
    script += "const PLAN = " + json.dumps(plan) + ";\n" + model + brief
    script += r'''
assert.equal(briefingModel("2025-03-03").mode, "training");
assert.equal(briefingModel("2025-03-03").profile.title, "Today's training");
assert.equal(briefingModel("2025-03-09").mode, "half");
assert.equal(briefingModel("2025-03-05").mode, "training");
assert.equal(briefingModel("2025-03-05", "league").fixture.bye, true);
assert.equal(briefingModel("2025-03-12", null, new Date(2025,2,12,9,0)).mode, "training");
assert.equal(briefingModel("2025-03-12", null, new Date(2025,2,12,18,59)).mode, "training");
assert.equal(briefingModel("2025-03-12", null, new Date(2025,2,12,19,0)).mode, "league");
assert.equal(briefingModel("2025-03-12", "training", new Date(2025,2,12,19,0)).mode, "training");
assert.equal(briefingModel("2025-03-03", "full").mode, "full");
assert.equal(briefingModel("2025-03-03", "invalid").mode, "training");
assert.equal(briefingModel("2025-04-01"), null);
briefModes["2025-03-12"] = "training";
assert.equal(finishGameType("2025-03-12"), null);
briefModes["2025-03-03"] = "full";
assert.equal(finishGameType("2025-03-03"), "full");
'''
    (tmp_path / "briefing.cjs").write_text(script, encoding="utf8")
    r = subprocess.run(["node", "briefing.cjs"], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


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
    for marker in ("/*PLAN*/", "/*VIDEOS*/", "/*REFS*/", "<!--TITLE-->", "<!--CAL-->", "<!--DECIDE-->", "<!--LIB-->"):
        assert marker not in page


def test_page_script_parses(tmp_path):
    if not shutil.which("node"):
        pytest.skip("needs node")
    page = program.page(plan_folder(tmp_path))
    js = page[page.index("<script>") + 8:page.rindex("</script>")]
    (tmp_path / "app.js").write_text(js, encoding="utf8")
    r = subprocess.run(["node", "--check", "app.js"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def test_page_has_a_preview_mode_that_saves_nothing(tmp_path):
    page = program.page(plan_folder(tmp_path))
    assert "const PREVIEW" in page and "if (PREVIEW) return" in page


def test_session_of_takes_special_dates_first():
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    assert program.session_of(plan, "2025-03-05") == "TS"  # a Wednesday, but a test day
    assert program.session_of(plan, "2025-03-06") == "M"  # Thursday
    assert program.session_of(plan, "2025-03-09") == "R"  # Sunday = weekday 0
    assert program.session_of(plan, "nope") is None


def test_summary_reads_checks_success_counts_and_game_counters():
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    data = {"rd": {"2025-03-06": {"legs": 3, "pain": 2, "where": ["knee"], "flag": True, "sleep": 6.5}},
            # M on Thursday: item 2 is the "rep" drill; item 1 is timed, so it is not counted
            "s": {"2025-03-06:2:0": {"v": "7"}, "2025-03-06:2:1": {"v": "8"}, "2025-03-06:2:2": {"v": ""},
                  "2025-03-06:1:0": {"v": "45"}},
            "log": [{"date": "2025-03-08", "type": "league", "worst": "On the catch", "ast": 3, "to": None,
                     "quick": 0}, {"date": "2025-03-09", "type": "shoot"}]}
    out = program.summary(plan, data)
    assert "  ready 2025-03-06 legs 3/4 pain 2/10 (knee) RED FLAG sleep 6.5 h" in out
    assert "  reps reads: 15 successes over 2 sets" in out
    game = [line for line in out if line.startswith("  game")]
    assert game == ["  game 2025-03-08 league worst On the catch · Assists 3 Caught and acted at once 0"]


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


def test_publish_copies_the_loop_audio_of_a_fragment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    folder = plan_folder(tmp_path)
    (folder / "decide.html").write_text('<h2>Reads</h2><audio class="loop" src="cues.zh.mp3" title="Cues"></audio>'
                                        '<audio class="loop" src="../secret.mp3"></audio>', encoding="utf8")
    (folder / "cues.zh.mp3").write_bytes(b"ID3")
    (folder / "cues.zh.md").write_text("not linked, not published", encoding="utf8")
    assert '<section data-panel="decide" hidden><h2>Reads</h2>' in program.page(folder)
    publish.main([str(folder)])
    tok = json.loads((tmp_path / "publish.json").read_text(encoding="utf8"))["programs"]["players/p0/program/2026-11-02"]
    out = tmp_path / "site" / "p" / tok
    assert sorted(f.name for f in out.iterdir()) == ["cues.zh.mp3", "index.html"]
    page = (out / "index.html").read_text(encoding="utf8")
    assert 'src="cues.zh.mp3"' in page and "../secret.mp3" not in page
    assert "i.ytimg.com/vi/${yid}" in page  # the app's own script is left as it is


def test_car_audio_of_sessions_is_one_player_per_file_and_published(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    folder = plan_folder(tmp_path)
    plan = json.loads((folder / "program.json").read_text(encoding="utf8"))
    plan["sessions"]["G"]["car"] = "car.G.zh.mp3"
    plan["sessions"]["TS"]["car"] = {"src": "car.G.zh.mp3", "title": "Game day <drive>"}
    plan["sessions"]["L"]["car"] = "car.L.zh.mp3"
    (folder / "program.json").write_text(json.dumps(plan), encoding="utf8")
    (folder / "car.G.zh.mp3").write_bytes(b"ID3")
    (folder / "car.L.zh.mp3").write_bytes(b"ID3")
    page = program.page(folder)
    assert page.count('class="carp"') == 2 and "<!--CAR-->" not in page
    assert '<div class="carp" data-codes="G TS" hidden><audio class="loop car" src="car.G.zh.mp3"' in page
    assert 'title="Game day &lt;drive&gt;"' in page  # a title given by any session sharing the file
    publish.main([str(folder)])
    tok = json.loads((tmp_path / "publish.json").read_text(encoding="utf8"))["programs"]["players/p0/program/2026-11-02"]
    assert sorted(f.name for f in (tmp_path / "site" / "p" / tok).iterdir()) == ["car.G.zh.mp3", "car.L.zh.mp3",
                                                                                 "index.html"]


def test_validate_rejects_car_audio_outside_the_folder():
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    plan["sessions"]["G"]["car"] = "../secret.mp3"
    plan["sessions"]["L"]["car"] = {"title": "no file"}
    errors = program.validate(plan)
    assert any("sessions[G].car" in e for e in errors) and any("sessions[L].car" in e for e in errors)


def test_validate_checks_fixture_games():
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    assert plan["fixture"]["games"]  # the example shows the schema
    plan["fixture"]["games"] += [{"date": "8/3/2025", "vs": "X"}, {"date": "2025-03-09"},
                                 {"date": "2025-03-10", "vs": "Y", "score": "42-38"}]
    errors = program.validate(plan)
    assert any("fixture.games[5]: date" in e for e in errors)
    assert any("fixture.games[6]: give the opponent" in e for e in errors)
    assert any("fixture.games[7].score" in e for e in errors)


def test_page_shows_the_fixture_on_today_calendar_and_game_tabs(tmp_path):
    page = program.page(plan_folder(tmp_path))
    assert '"vs": "Team B"' in page or '"vs":"Team B"' in page
    for hook in ("${fixNote(selD)}", "grid + fixTable()", "fixLine(FIX[ds])"):
        assert hook in page


@pytest.mark.parametrize("fixture,issue", [
    ([], "fixture: must be an object"),
    ({"games": {}}, "fixture.games: must be a list"),
    ({"games": [None]}, "fixture.games[0]: must be an object"),
    ({"games": [{"date": "2025-02-30", "vs": "A"}]}, "date must be a valid"),
    ({"games": [{"date": "2025-03-01", "bye": "false"}]}, ".bye: must be true or false"),
    ({"games": [{"date": "2025-03-01", "vs": "A", "score": [True, 2]}]}, "non-negative integers"),
    ({"games": [{"date": "2025-03-01", "vs": "A", "score": [-1, 2]}]}, "non-negative integers"),
    ({"games": [{"date": "2025-03-01", "vs": "A"}, {"date": "2025-03-01", "bye": True}]}, "duplicate date"),
])
def test_fixture_errors_are_reported_before_rendering(fixture, issue):
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    plan["fixture"] = fixture
    assert any(issue in error for error in program.validate(plan))


@pytest.mark.parametrize("src", ["../car.mp3", "..\\car.mp3", "sub\\car.mp3", "C:car.mp3"])
def test_car_audio_requires_a_plain_filename_on_every_platform(src):
    assert program.car_src(src) is None


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
    assert "media-src 'self'" in page["content-security-policy"]  # the loop audio next to the app
    assert "connect-src 'self'" in page["content-security-policy"]
    assert out["get"]["headers"]["referrer-policy"] == "no-referrer"  # only plan pages send a referrer


def test_priority_rules_are_pinned_on_today_and_game_tabs(tmp_path):
    folder = plan_folder(tmp_path)
    plan = json.loads((folder / "program.json").read_text(encoding="utf8"))
    plan["briefing"] = briefing_example()
    plan["briefing"]["priority"] = {"title": "Every time", "cues": [
        {"cue": "Three to four dribbles", "action": "Then pass", "check": "Count them"}]}
    (folder / "program.json").write_text(json.dumps(plan), encoding="utf8")
    page = program.page(folder)
    assert 'class="brief pin"' in page
    assert 'getElementById("gameBox").innerHTML = `${priorityHtml()}' in page


def focus_example():
    return {"title": "Must do", "rules": [
        {"cue": "Three to four dribbles", "action": "Then pass or call a screen"},
        {"cue": "Read your spot before the catch", "action": "Look before the ball arrives",
         "points": ["Check your defender's feet", "Find the help behind"]}],
        "sessions": {}}


def test_focus_is_valid_and_switches_the_today_tab_to_the_lean_view(tmp_path):
    folder = plan_folder(tmp_path)
    plan = json.loads((folder / "program.json").read_text(encoding="utf8"))
    code = next(iter(plan["sessions"]))
    plan["focus"] = dict(focus_example(), sessions={code: "Sit back on the box"})
    assert program.validate(plan) == []
    (folder / "program.json").write_text(json.dumps(plan), encoding="utf8")
    page = program.page(folder)
    assert "function renderLean(" in page
    assert "Sit back on the box" in page
    assert "Find the help behind" in page and "r.points" in page


@pytest.mark.parametrize("value,issue", [
    ([], "focus: must be an object"),
    ({"title": "X", "rules": []}, "focus.rules: give one to three rules"),
    ({"title": "X", "rules": [{"cue": "a", "action": "b"}] * 4}, "focus.rules: give one to three rules"),
    ({"title": "X", "rules": [{"cue": "", "action": "b"}]}, "focus.rules: each needs cue and action text"),
    ({"title": "X", "rules": [{"cue": "a", "action": "b", "points": []}]}, "focus.rules: points must be"),
    ({"title": "X", "rules": [{"cue": "a", "action": "b", "points": ["x"] * 6}]}, "focus.rules: points must be"),
    ({"title": "X", "rules": [{"cue": "a", "action": "b", "points": ["x", " "]}]}, "focus.rules: points must be"),
    ({"title": "", "rules": [{"cue": "a", "action": "b"}]}, "focus.title"),
    ({"title": "X", "rules": [{"cue": "a", "action": "b"}], "sessions": {"nope": "c"}}, "focus.sessions.nope: unknown session"),
    ({"title": "X", "rules": [{"cue": "a", "action": "b"}] * 3, "sessions": {"__first__": "c"}}, "at most three points"),
])
def test_focus_validation(value, issue):
    plan = json.loads(EXAMPLE.read_text(encoding="utf8"))
    if isinstance(value, dict) and "__first__" in value.get("sessions", {}):
        value = dict(value, sessions={next(iter(plan["sessions"])): "c"})
    plan["focus"] = value
    assert any(issue in error for error in program.validate(plan)), program.validate(plan)


def test_theme_picker_ships_every_theme_and_stays_local(tmp_path):
    page = program.page(plan_folder(tmp_path))
    for theme in ("court", "ice", "mint", "paper"):
        assert f'html[data-theme="{theme}"]' in page
    assert 'data-act="theme"' in page
    assert 'localStorage.setItem("plan-theme"' in page
    assert page.count("</script>") == 1
