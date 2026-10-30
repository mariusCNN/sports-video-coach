"""pipeline: the step driver shared by run / train / move, its exit protocol and make-style freshness."""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from sports_video_coach import pipeline as P


class Unit(P.Unit):
    JSON = "unit.json"

    @classmethod
    def load(cls, folder: Path) -> "Unit":
        return cls(Path(folder), json.loads((Path(folder) / cls.JSON).read_text(encoding="utf8")), ("zh",))


@pytest.fixture
def unit(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    folder = tmp_path / "u"
    (folder / "run").mkdir(parents=True)
    (folder / "unit.json").write_text(json.dumps({"fps": 10}), encoding="utf8")
    (folder / "src.txt").write_text("a", encoding="utf8")
    return folder


class Runner:
    """Stands in for subprocess.run: records stage argv and writes `<stage>.out` in the run folder."""
    def __init__(self, folder: Path, rc: int = 0):
        self.folder, self.rc, self.calls = folder, rc, []

    def __call__(self, cmd, **kw):
        cmd = [*cmd[:3], cmd[3].split(":", 1)[-1], *cmd[4:]]   # bare stage name, without "basketball:"
        argv = cmd[3:]
        self.calls.append(argv)
        out = self.folder / "run" / f"{argv[0]}.out"
        out.write_text(uuid.uuid4().hex, encoding="utf8")   # new content every run
        return subprocess.CompletedProcess(cmd, self.rc)


def made(name):
    return lambda g: (g.run / f"{name}.out").exists()


def steps():
    """a reads src.txt (fps param); b reads a's output; c depends on a by its run stamp (`after`); d is untracked."""
    return [
        P.Step("a", "cmd", made("a"), lambda g: [["a"]], inputs=lambda g: [g.folder / "src.txt"],
               params=lambda g: {"fps": g.game.get("fps")}, again=("--force",)),
        P.Step("b", "cmd", made("b"), lambda g: [["b"]], inputs=lambda g: [g.run / "a.out"]),
        P.Step("c", "cmd", made("c"), lambda g: [["c"]], inputs=lambda g: [], after=("a",)),
        P.Step("d", "cmd", made("d"), lambda g: [["d"]]),
    ]


def test_first_drive_runs_everything_and_records_tracked_steps(unit):
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), runner=r) == 0
    assert [c[0] for c in r.calls] == ["a", "b", "c", "d"]
    recs = json.loads((unit / P.STORE).read_text(encoding="utf8"))["steps"]
    assert set(recs) == {"a", "b", "c"}
    assert recs["a"]["inputs"] == {"src.txt": P.signature(unit / "src.txt")} and recs["a"]["params"] == {"fps": 10}
    assert set(recs["b"]["inputs"]) == {"run/a.out"} and recs["c"]["after"] == {"a": recs["a"]["run"]}
    r2 = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), runner=r2) == 0 and r2.calls == []


def test_folder_without_records_counts_as_done_and_is_adopted(unit, capsys):
    for n in "abcd":
        (unit / "run" / f"{n}.out").write_text("old", encoding="utf8")
    g = Unit.load(unit)
    assert all(ok for _, _, ok in P.status(g, steps()))
    assert not (unit / P.STORE).exists()                       # --status never writes
    assert P.drive(g, steps(), dry=True, runner=Runner(unit)) == 0
    assert not (unit / P.STORE).exists()                       # nor does --dry
    r = Runner(unit)
    assert P.drive(g, steps(), runner=r) == 0 and r.calls == []
    assert set(json.loads((unit / P.STORE).read_text(encoding="utf8"))["steps"]) == {"a", "b", "c"}


def test_changed_input_makes_the_step_stale_and_its_dependants_follow(unit, capsys):
    P.drive(Unit.load(unit), steps(), runner=Runner(unit))
    (unit / "src.txt").write_text("b", encoding="utf8")
    g = Unit.load(unit)
    rows = {n: (ok, why) for n, _, ok, why in P.rows(g, steps())}
    assert rows["a"] == (False, ["src.txt"]) and rows["b"][0] and rows["d"][0]
    P.print_status(g, steps())
    assert "stale: src.txt" in capsys.readouterr().out
    r = Runner(unit)
    assert P.drive(g, steps(), runner=r) == 0
    assert r.calls == [["a", "--force"], ["b"], ["c"]]         # a over its old output; b (new a.out), c (a ran again)
    assert "changed since its last run: src.txt" in capsys.readouterr().out


def test_same_content_rewritten_is_not_a_change(unit):
    P.drive(Unit.load(unit), steps(), runner=Runner(unit))
    later = time.time() + 30
    os.utime(unit / "src.txt", (later, later))                 # small files are signed by content
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), runner=r) == 0 and r.calls == []


def test_params_change_makes_the_step_stale(unit):
    P.drive(Unit.load(unit), steps(), runner=Runner(unit))
    (unit / "unit.json").write_text(json.dumps({"fps": 15}), encoding="utf8")
    g = Unit.load(unit)
    assert P.changes(steps()[0], g, P.Store(unit)) == ["params"]
    r = Runner(unit)
    P.drive(g, steps(), runner=r)
    assert r.calls[0] == ["a", "--force"]


def test_redo_makes_downstream_steps_stale(unit):
    P.drive(Unit.load(unit), steps(), runner=Runner(unit))
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), redo="a", runner=r) == 0
    assert r.calls == [["a", "--force"], ["b"], ["c"]]          # d tracks nothing: left alone


def test_redo_of_an_adopted_folder_reaches_its_dependants(unit):
    for n in "abcd":
        (unit / "run" / f"{n}.out").write_text("old", encoding="utf8")
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), redo="a", runner=r) == 0
    assert [c[0] for c in r.calls] == ["a", "b", "c"]


def test_until_stops_on_a_stale_step_after_running_it(unit, capsys):
    P.drive(Unit.load(unit), steps(), runner=Runner(unit))
    (unit / "src.txt").write_text("b", encoding="utf8")
    r = Runner(unit)
    assert P.drive(Unit.load(unit), steps(), until="a", runner=r) == 0
    assert r.calls == [["a", "--force"]] and "paused after a" in capsys.readouterr().out


def test_dry_prints_the_rerun_with_its_extra_args(unit, capsys):
    P.drive(Unit.load(unit), steps(), runner=Runner(unit))
    (unit / "src.txt").write_text("b", encoding="utf8")
    assert P.drive(Unit.load(unit), steps(), dry=True, runner=Runner(unit)) == 0
    assert "[dry] a: sports-video-coach a --force" in capsys.readouterr().out


def test_untracked_now_counts_as_fresh(unit):
    s = P.Step("m", "cmd", lambda g: True, lambda g: [["m"]], inputs=lambda g: None)
    store = P.Store(unit)
    assert not P.record(s, Unit.load(unit), store) and P.changes(s, Unit.load(unit), store) == []


def test_unreadable_store_counts_as_empty(unit):
    (unit / P.STORE).write_text("{not json", encoding="utf8")
    assert P.Store(unit).steps == {}


def test_input_keys_survive_moving_the_folder(unit, tmp_path):
    g = Unit.load(unit)
    assert P.input_key(g, unit / "src.txt") == "src.txt"
    assert P.input_key(g, unit / "run" / "x.pkl") == "run/x.pkl"
    assert P.input_key(g, tmp_path / "video.mp4") == "ext/video.mp4"


def test_large_files_are_signed_by_size_and_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "SMALL", 4)
    p = tmp_path / "big.bin"
    p.write_bytes(b"0123456789")
    sig = P.signature(p)
    assert sig.startswith("10:")
    os.utime(p, (time.time() + 30, time.time() + 30))
    assert P.signature(p) != sig and P.signature(tmp_path / "nope") == "missing"


def test_agent_step_waits_with_exit_3_and_fills_its_instructions(unit, capsys):
    s = [P.Step("ask", "agent", lambda g: False, how="look in {run}", errors=lambda g: [f"e{i}" for i in range(14)])]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    out = capsys.readouterr().out
    assert "waiting for the agent: ask" in out and (unit / "run").as_posix() in out and "... 2 more" in out
    assert (unit / "run" / "review").is_dir()                     # ready for review.json and the helpers' parts


def test_agent_script_is_out_of_date_when_what_it_follows_changes(unit, capsys):
    src, out = unit / "src.txt", unit / "script.md"
    out.write_text("v1", encoding="utf8")
    s = [P.Step("script", "agent", lambda g: out.exists(), how="write {folder}/script.md",
                derives=lambda g: [(out, [src])])]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0          # recorded as it is
    assert "outputs" in json.loads((unit / P.STORE).read_text(encoding="utf8"))["steps"]["script"]
    src.write_text("b", encoding="utf8")                                  # the report it follows was corrected
    capsys.readouterr()
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    said = capsys.readouterr().out
    assert "script is out of date" in said and "script.md: src.txt changed after it was written" in said
    assert "--accept script" in said
    assert P.rows(Unit.load(unit), s)[0][3] == ["script.md: src.txt changed after it was written"]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit), accept="script") == 0
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0          # accepted stays accepted
    src.write_text("c", encoding="utf8")
    out.write_text("v2", encoding="utf8")                                 # the agent followed the change
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0


def test_failed_long_step_exits_1_with_its_log_tail(unit, capsys):
    s = [P.Step("a", "cmd", made("a"), lambda g: [["a"]], long=True)]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit, rc=2)) == 1
    out = capsys.readouterr().out
    assert "a failed (exit 2)" in out and "last lines of" in out


def test_passed_long_step_shows_its_result_lines_and_absolute_log(unit, capsys, monkeypatch):
    def runner(cmd, stdout=None, **kw):
        stdout.write("progress 10%\rprogress 100%\nmeasured 42 reps\n\nwrote run/a.out\n\n")
        (unit / "run" / "a.out").write_text("x", encoding="utf8")
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.chdir(unit)
    monkeypatch.setenv("HOOP_WORKSPACE", ".")  # a relative workspace: the printed log path is still absolute
    s = [P.Step("a", "cmd", made("a"), lambda g: [["a"]], long=True)]
    assert P.drive(Unit.load(unit), s, runner=runner) == 0
    out = capsys.readouterr().out
    assert "[run]   a: measured 42 reps\n[run]   a: wrote run/a.out\n" in out and "progress" not in out
    log = next(ln for ln in out.splitlines() if "log: " in ln).split("log: ", 1)[1]
    assert Path(log).is_absolute() and Path(log).is_file()
    assert P.result_lines(unit / "missing.log") == []


def test_failed_step_writes_no_record(unit):
    s = steps()[:1]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit, rc=1)) == 1
    assert P.Store(unit).steps == {}                            # only the code stamp (runlock), no step record


def test_publish_runs_only_with_publish(unit, capsys):
    s = [P.Step("publish", "cmd", lambda g: False, lambda g: [["publish"]])]
    r = Runner(unit)
    assert P.drive(Unit.load(unit), s, runner=r) == 0 and r.calls == []
    assert "publish skipped" in capsys.readouterr().out
    assert P.drive(Unit.load(unit), s, publish=True, runner=r) == 0 and r.calls == [["publish"]]


def test_newer_tolerates_files_copied_together(tmp_path):
    out, inp = tmp_path / "out", tmp_path / "in"
    out.write_text("o")
    inp.write_text("i")
    t = out.stat().st_mtime
    os.utime(inp, (t + 1, t + 1))
    assert P.newer(out, inp)
    os.utime(inp, (t + 10, t + 10))
    assert not P.newer(out, inp)
    assert not P.newer(tmp_path / "missing", inp)


# ---- the drivers' step tables ---------------------------------------------------------------------------------

@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path))
    folder = tmp_path / "teams" / "red-foxes" / "2025-03-08"
    (folder / "run").mkdir(parents=True)
    video = tmp_path / "game.mp4"
    video.write_bytes(b"v1")
    g = {"video": str(video), "periods": [[0, 1200]], "us": {"team": "Night Owls", "focus_player": "7"},
         "them": {"team": "Red Foxes"}, "rosters": {"us": [], "them": []}}
    (folder / "game.json").write_text(json.dumps(g), encoding="utf8")
    for f in ("detections.pkl", "embeddings.npz", "cluster_names.json", "camera.npz", "tracks.pkl", "jersey.json",
              "possessions.pkl", "possession_metrics.pkl"):
        (folder / "run" / f).write_text(f, encoding="utf8")
    return folder


class StageRunner:
    """subprocess.run stand-in that only records the stage argv."""
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        cmd = [*cmd[:3], cmd[3].split(":", 1)[-1], *cmd[4:]]   # bare stage name, without "basketball:"
        self.calls.append(cmd[3:])
        return subprocess.CompletedProcess(cmd, 0)


def game_steps(*names):
    from hoop_tape_miner import run as R
    return [s for s in R.STEPS if s.name in names]


def test_game_redo_tracks_reruns_the_steps_after_it(game):
    from hoop_tape_miner import run as R
    steps = game_steps("tracks", "jersey", "analyze")
    r = StageRunner()
    assert R.drive(R.Game.load(game), redo="tracks", runner=r, steps=steps) == 0
    assert [c[0] for c in r.calls] == ["tracks", "jersey", "analyze"]
    r = StageRunner()
    assert R.drive(R.Game.load(game), runner=r, steps=steps) == 0 and r.calls == []


def test_game_new_periods_rerun_analyze(game):
    from hoop_tape_miner import run as R
    steps = game_steps("tracks", "jersey", "analyze")
    R.drive(R.Game.load(game), runner=StageRunner(), steps=steps)              # adopts the old run
    g = json.loads((game / "game.json").read_text(encoding="utf8"))
    (game / "game.json").write_text(json.dumps(dict(g, periods=[[5, 1000]])), encoding="utf8")
    assert not {n: ok for n, _, ok in R.status(R.Game.load(game))}["analyze"]
    r = StageRunner()
    R.drive(R.Game.load(game), runner=r, steps=steps)
    assert [c[0] for c in r.calls] == ["analyze"]


def test_game_clips_recut_with_force_when_the_video_changes(game):
    from hoop_tape_miner import run as R
    steps = game_steps("clips")
    for d in (game, game / "player-7"):  # the reports exist (clips are not done before them); no clip marks
        d.mkdir(exist_ok=True)
        (d / "README.md").write_text("# r\n", encoding="utf8")
    R.drive(R.Game.load(game), runner=StageRunner(), steps=steps)
    (game.parents[2] / "game.mp4").write_bytes(b"v2")
    r = StageRunner()
    R.drive(R.Game.load(game), runner=r, steps=steps)
    assert r.calls and all(c[0] == "clips" and c[-1] == "--force" for c in r.calls)


def test_game_status_does_not_write(game, capsys):
    from hoop_tape_miner import run as R
    R.main([str(game), "--status"])
    assert "done  tracks" in capsys.readouterr().out and not (game / P.STORE).exists()


def test_session_tables_share_the_tail_and_train_sheets_is_not_tracked():
    from hoop_tape_miner import move_run, train_run
    tail = ["clips", "listen-script", "film-script", "narrate", "html", "qa", "publish", "film"]
    by = {s.name: s for s in train_run.TRAIN_STEPS}
    assert by["sheets"].inputs is None and by["summary"].inputs and by["scan"].inputs
    assert train_run.NAMES[-8:] == tail and move_run.NAMES[-8:] == tail


def two_scripts(unit):
    """Two agent steps that both follow src.txt, recorded as they are; then src.txt changes."""
    src = unit / "src.txt"
    outs = [unit / "one.md", unit / "two.md"]
    for o in outs:
        o.write_text("v1", encoding="utf8")
    s = [P.Step(o.stem, "agent", lambda g, o=o: o.exists(), how="write {folder}/" + o.name,
                derives=lambda g, o=o: [(o, [src])]) for o in outs]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0
    src.write_text("b", encoding="utf8")
    return s


def test_one_stop_lists_every_out_of_date_agent_step_and_accept_takes_several(unit, capsys):
    s = two_scripts(unit)
    capsys.readouterr()
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    said = capsys.readouterr().out
    assert "one is out of date" in said and "two is out of date too" in said and "two.md: src.txt changed" in said
    assert f"`sports-video-coach run {P.slash(unit)} --accept one two`" in said  # the full command
    assert P.drive(Unit.load(unit), s, runner=Runner(unit), accept=["one", "two"]) == 0
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0


def test_accept_takes_one_or_several_steps_on_the_command_line():
    import argparse
    ap = argparse.ArgumentParser()
    P.add_drive_args(ap, ["one", "two"])
    assert ap.parse_args(["--accept", "one"]).accept == ["one"]
    assert ap.parse_args(["--accept", "one", "two"]).accept == ["one", "two"]


def test_checks_keep_an_agent_step_waiting_until_fixed_or_accepted(unit, capsys):
    out = unit / "script.md"
    out.write_text("bad", encoding="utf8")
    s = [P.Step("script", "agent", lambda g: out.exists(), how="write it",
                checks=lambda g: ["script.md: fix the sentence"] if out.read_text(encoding="utf8") == "bad" else []),
         P.Step("after", "cmd", made("after"), lambda g: [["after"]])]
    r = Runner(unit)
    assert P.drive(Unit.load(unit), s, runner=r) == P.WAITING and r.calls == []
    said = capsys.readouterr().out
    assert "script has something to fix" in said and "script.md: fix the sentence" in said
    assert P.rows(Unit.load(unit), s)[0][2:] == (False, ["script.md: fix the sentence"])
    assert P.drive(Unit.load(unit), s, runner=r, accept="script") == 0 and r.calls == [["after"]]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0          # accepted stays accepted


def test_listen_script_waits_on_a_wrong_stated_length_before_narrate(unit, capsys):
    tail = {t.name: t for t in P.tail_steps(lambda g: g.folder / "v.mp4", "write listen", "qa", "film")}
    s = [tail["listen-script"], tail["narrate"]]
    (unit / "README.md").write_text("# r\n", encoding="utf8")
    (unit / "listen.zh.md").write_text("这份报告大约五分钟。传球要快。\n", encoding="utf8")
    r = Runner(unit)
    assert P.drive(Unit.load(unit), s, runner=r) == P.WAITING and r.calls == []   # no TTS render yet
    said = capsys.readouterr().out
    assert "listen.zh.md says about 5 min" in said and '"这份报告大约五分钟。"' in said
    assert "--accept listen-script" in said
    assert P.drive(Unit.load(unit), s, runner=r, accept=["listen-script"]) == 0 and r.calls[0][0] == "narrate"
    (unit / "listen.zh.md").write_text("传球要快。\n", encoding="utf8")          # fixed: nothing left to flag
    assert P.listen_checks(Unit.load(unit)) == []


def test_qa_is_not_done_while_a_step_before_it_is_not(unit):
    s = [P.Step("html", "cmd", made("html"), lambda g: [["html"]]),
         P.Step("qa", "agent", lambda g: True, how="check", needs_all=True)]
    assert P.rows(Unit.load(unit), s)[1] == ("qa", "agent", False, ["waits for html"])
    (unit / "run" / "html.out").write_text("x", encoding="utf8")
    assert [ok for _, _, ok, _ in P.rows(Unit.load(unit), s)] == [True, True]
    tail = {t.name: t for t in P.tail_steps(lambda g: None, "", "", "")}
    assert tail["qa"].needs_all and tail["film"].again == ("--force",)   # film keeps languages that are up to date


def test_whitespace_only_edit_does_not_make_a_script_out_of_date(unit, capsys):
    src, out = unit / "README.md", unit / "script.md"
    src.write_text("# Report\n\nPass early.\n", encoding="utf8")
    out.write_text("v1", encoding="utf8")
    s = [P.Step("script", "agent", lambda g: out.exists(), how="write it", derives=lambda g: [(out, [src])])]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0
    src.write_text("# Report \n\n\nPass  early.\r\n", encoding="utf8")    # a space, a blank line, CRLF
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0
    src.write_text("# Report\n\nPass late.\n", encoding="utf8")          # a real edit still counts
    capsys.readouterr()
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    said = capsys.readouterr().out
    assert "script.md: README.md changed after it was written" in said
    assert "Only a typo or wording fix" in said and "--accept script` keeps them" in said


def test_text_signature_ignores_whitespace_only_for_small_text_files(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("这份报告 大约两分钟。\n", encoding="utf8")
    b.write_text("这份报告大约两分钟。", encoding="utf8")
    assert P.text_signature(a) == P.text_signature(b) and P.text_signature(a).startswith("text:")
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"\x00 \x01")
    assert P.text_signature(clip) == P.signature(clip)                     # not text: the raw signature
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe x")
    assert P.text_signature(bad) == P.signature(bad)                       # not UTF-8: raw
    assert P.text_signature(tmp_path / "none.md") == "missing"


def test_records_from_before_text_signatures_compare_raw_then_are_rewritten(unit):
    src, out = unit / "README.md", unit / "script.md"
    src.write_text("# r\n", encoding="utf8")
    out.write_text("v1", encoding="utf8")
    s = [P.Step("script", "agent", lambda g: out.exists(), how="write it", derives=lambda g: [(out, [src])])]
    old = {"version": 1, "steps": {"script": {"outputs": {"script.md": {
        "sig": P.signature(out), "inputs": {"README.md": P.signature(src)}}}}}}
    (unit / P.STORE).write_text(json.dumps(old), encoding="utf8")
    assert P.outdated(s[0], Unit.load(unit), P.Store(unit)) == []           # unchanged: still fresh
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0            # and the record is rewritten
    rec = json.loads((unit / P.STORE).read_text(encoding="utf8"))["steps"]["script"]["outputs"]["script.md"]
    assert rec["inputs"]["README.md"].startswith("text:")
    (unit / P.STORE).write_text(json.dumps(old), encoding="utf8")
    src.write_text("# r \n", encoding="utf8")                               # old raw record: any byte counts
    assert P.outdated(s[0], Unit.load(unit), P.Store(unit)) == ["script.md: README.md changed after it was written"]


def qa_unit(unit, body="<p>传球要快。</p>"):
    """A built one-page unit (zh) with a page-check draft qa.md whose stamp is stale."""
    from sports_video_coach import page_check as PC
    (unit / "README.md").write_text("# r\n", encoding="utf8")
    (unit / "index.html").write_text('<html lang="zh-CN"><head><meta name="viewport" content="width=device-width">'
                                     f'</head><body><article class="report" lang="zh-CN">{body}</article></body>'
                                     '</html>', encoding="utf8")
    (unit / "qa.md").write_text(PC.qa_text([(unit, [], [])], "0123456789abcdef"), encoding="utf8")
    return [t for t in P.tail_steps(lambda g: None, "", "check the page", "") if t.name == "qa"]


def test_qa_rewrites_an_untouched_page_check_draft_itself(unit, capsys):
    s = qa_unit(unit)
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0
    said = capsys.readouterr().out
    assert "qa.md is a page-check draft: checked again" in said and "PASS" in said
    text = (unit / "qa.md").read_text(encoding="utf8")
    assert text.startswith("PASS") and f"checked: {P.qa_hash(Unit.load(unit))}" in text
    assert "NOT checked:" in text                                           # still says what was not checked
    assert P.drive(Unit.load(unit), s, runner=Runner(unit), dry=True) == 0


def test_qa_draft_that_finds_problems_stops_the_run(unit, capsys):
    s = qa_unit(unit)
    (unit / "listen.zh.md").write_text("Ã© broken\n", encoding="utf8")    # page-check warns: mojibake
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    said = capsys.readouterr().out
    assert "mojibake" in said and "FAIL" in said and "waiting for the agent: qa" in said
    assert (unit / "qa.md").read_text(encoding="utf8").startswith("FAIL")
    assert "\n  it checks links" in said and max(map(len, P.QA_STAMP.split("\n"))) < 110   # short lines


def test_qa_draft_with_agent_notes_or_by_hand_is_left_to_the_agent(unit, capsys):
    s = qa_unit(unit)
    with (unit / "qa.md").open("a", encoding="utf8") as f:
        f.write("\n## Agent notes\n\n- layout checked in a browser\n")
    before = (unit / "qa.md").read_text(encoding="utf8")
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    assert (unit / "qa.md").read_text(encoding="utf8") == before
    assert "changed after QA" in capsys.readouterr().out
    (unit / "qa.md").write_text("PASS by hand\nchecked: 0123456789abcdef\n", encoding="utf8")
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    assert (unit / "qa.md").read_text(encoding="utf8") == "PASS by hand\nchecked: 0123456789abcdef\n"


def test_film_script_with_an_unknown_scene_prefix_waits_before_the_film_render(unit, capsys):
    """The prefix check the film render stops on (film.prefix_problem) runs in the film-script step: the run waits
    naming the file, the line and the prefix; a script with known prefixes passes."""
    step = next(s for s in P.tail_steps(lambda g: g.folder / "v.mp4", "listen", "qa", "write {folder}/film.zh.md")
                if s.name == "film-script")
    script = unit / "film.zh.md"
    script.write_text("开场。\n\n![罚球](reel:9 12)\n犯规太多。\n\n![快攻](clip:0:01-0:04)\n跑起来。\n", encoding="utf8")
    assert P.drive(Unit.load(unit), [step]) == P.WAITING
    out = capsys.readouterr().out
    assert "[run] waiting for the agent: film-script" in out
    assert f"{script.as_posix()}: line 3: unknown scene prefix 'reel:' (known here: clip:, stat:" in out
    script.write_text(script.read_text(encoding="utf8").replace("reel:9 12", "stats:9 罚球 | 12 犯规"), encoding="utf8")
    assert P.drive(Unit.load(unit), [step]) == 0
    assert "unknown scene prefix" not in capsys.readouterr().out


def test_a_together_step_is_asked_for_in_the_same_stop(unit, capsys):
    one, two = unit / "one.md", unit / "two.md"
    s = [P.Step("one", "agent", lambda g: one.exists(), how="write one"),
         P.Step("mid", "cmd", made("mid"), lambda g: [["mid"]]),
         P.Step("two", "agent", lambda g: two.exists(), how="write two", together="one")]
    r = Runner(unit)
    assert P.drive(Unit.load(unit), s, runner=r) == P.WAITING and r.calls == []
    said = capsys.readouterr().out
    assert "waiting for the agent: one" in said and "write it alongside one): two" in said
    one.write_text("x", encoding="utf8"), two.write_text("x", encoding="utf8")
    assert P.drive(Unit.load(unit), s, runner=r) == 0 and r.calls == [["mid"]]


def test_a_together_step_already_written_is_not_asked_again(unit, capsys):
    one, two = unit / "one.md", unit / "two.md"
    two.write_text("x", encoding="utf8")
    s = [P.Step("one", "agent", lambda g: one.exists(), how="write one"),
         P.Step("two", "agent", lambda g: two.exists(), how="write two", together="one")]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    assert "alongside" not in capsys.readouterr().out


def test_timing_log_times_commands_and_agent_waits(unit):
    out = unit / "script.md"
    s = [P.Step("a", "cmd", made("a"), lambda g: [["a"]]),
         P.Step("script", "agent", lambda g: out.exists(), how="write it")]
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == P.WAITING
    out.write_text("x", encoding="utf8")
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0
    log = [json.loads(x) for x in (unit / P.TIMING).read_text(encoding="utf8").splitlines()]
    assert [(e["step"], e["event"]) for e in log] == [("a", "start"), ("a", "done"), ("script", "waiting"),
                                                      ("script", "passed")]
    assert isinstance(log[1]["secs"], int) and isinstance(log[3]["secs"], int)
    assert "asked" not in json.loads((unit / P.STORE).read_text(encoding="utf8")).get("notes", {})
    assert P.drive(Unit.load(unit), s, runner=Runner(unit)) == 0     # a passing step is logged once
    assert len((unit / P.TIMING).read_text(encoding="utf8").splitlines()) == 4


def test_dry_runs_leave_no_timing_log(unit):
    s = [P.Step("a", "cmd", made("a"), lambda g: [["a"]]), P.Step("w", "agent", lambda g: False, how="x")]
    P.drive(Unit.load(unit), s, dry=True, runner=Runner(unit))
    assert not (unit / P.TIMING).exists()
