"""svc-bench-3 on fresh seeds: new events from an integer seed, truth rebuilt from the seed, never written out."""
import json

import pytest

from sports_video_coach import bench
from sports_video_coach.bench import baseline, page, run, score as S, suite as suite1, suite3

SUITE = suite3.SUITE
SEEDS = [0, 1, 7, 42, 121, 2026, 999_999_999, suite3.MAX_SEED]


def test_published_suite_is_unchanged_by_the_seed_machinery():
    assert S.suite_tasks(SUITE) is suite3
    assert suite3.DEFAULT.seed is None and suite3.DEFAULT_INSTANCE.TASKS is suite3.TASKS
    truth = {t.id: t.truth for t in suite3.TASKS}
    assert truth["juggle-touches"] == len(suite3.JUG_TOUCHES)
    assert len(truth["far-hoop-shots"]) == 12 and truth["pass-releases"] == suite3.RELEASES


@pytest.mark.parametrize("seed", SEEDS)
def test_a_seed_gives_the_same_suite_every_time_and_keeps_its_rules(seed):
    a, b = suite3.Instance(suite3.fresh(seed)), suite3.seeded(seed)
    assert [t.truth for t in a.TASKS] == [t.truth for t in b.TASKS] and b.seed == seed
    assert [t.id for t in b.TASKS] == [t.id for t in suite3.TASKS]
    shots = b.spec.shots
    assert 10 <= len(shots) <= 13 and sum(s.endswith("*") for s in shots) == 3
    assert 3 <= b.BY_ID["far-hoop-shots"].truth.count("made") <= len(shots) - 3
    assert any(s.startswith("fake+") for s in shots)
    assert f"takes {len(shots)} shots" in b.BY_ID["far-hoop-shots"].question
    assert sum(p[2] == "touch" for p in b.spec.passes) >= 1 and sum(p[4] for p in b.spec.passes) >= 2
    assert len(b.spec.pass_hidden) == 4 and set(b.spec.pass_hidden) <= set(b.releases)
    # kept readable on the stills (pixel read-back, docs/benchmark.md): a pass across the middle player is a lob, no
    # two one-touch passes in a row, the defender never hides a one-touch pass
    styles = {r: p[2] for r, p in zip(b.releases, b.spec.passes)}
    assert all(p[2] == "lob" for p in b.spec.passes if {p[0], p[1]} == {"A", "C"})
    assert not any(a[2] == c[2] == "touch" for a, c in zip(b.spec.passes, b.spec.passes[1:]))
    assert all(styles[r] != "touch" for r in b.spec.pass_hidden)
    assert b.spec.juggle[0][1] != 6 and all(h <= 5 * g + 2 for k, g, h in b.spec.juggle if k == "F" and g != 6)
    kinds = [k for _, k, _ in b.jug_contacts]
    assert "N" in kinds and any(g == 6 for _, g, _ in b.spec.juggle)
    rate = b.BY_ID["stroke-rate"].truth
    assert 60 * 25 / 50 < rate and 60 * 25 / min(b.spec.row_decoy) < rate     # faster than the far boat


def test_seeds_differ_from_each_other_and_from_the_published_suite():
    truths = {json.dumps([t.truth for t in suite3.seeded(s).TASKS]) for s in range(20)}
    assert len(truths) == 20
    assert json.dumps([t.truth for t in suite3.TASKS]) not in truths


@pytest.mark.parametrize("bad", [-1, suite3.MAX_SEED + 1, 1.5, "3", True, None])
def test_bad_seeds_are_refused(bad):
    with pytest.raises(ValueError):
        suite3.fresh(bad)


def test_only_svc_bench_3_has_fresh_seeds():
    assert S.SEEDED == [SUITE]
    with pytest.raises(ValueError):
        S.suite_tasks(suite1.SUITE, 3)


def fake_draw(monkeypatch, *seeds):
    """Draw nothing (the seeds' tasks are built first: a Task cannot be made while `draw` is patched)."""
    for seed in seeds:
        suite3.seeded(seed)
    drawn = []
    monkeypatch.setattr(suite1.Task, "draw", property(lambda t: lambda out: drawn.append(out) or out), raising=False)
    return drawn


def test_prepare_with_a_seed_records_it_and_writes_no_truth(tmp_path, monkeypatch):
    fake_draw(monkeypatch, 4242)
    assert bench.main(["prepare", "--out", str(tmp_path), "--suite", SUITE, "--seed", "4242"]) == 0
    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    v = suite3.seeded(4242)
    assert data == {"suite": SUITE, "seed": 4242, "answers": {t.id: None for t in v.TASKS}}
    md = (tmp_path / "TASKS.md").read_text(encoding="utf8")
    assert "drawn from a fresh seed" in md and f"takes {len(v.spec.shots)} shots" in md
    for t in v.TASKS:
        if t.kind != "count":
            assert json.dumps(t.truth) not in md
    assert not any(str(r) in md for r in v.releases if len(str(r)) >= 4)   # 12.48, not 2.0


def test_prepare_without_a_seed_is_as_before(tmp_path, monkeypatch):
    fake_draw(monkeypatch)
    assert bench.main(["prepare", "--out", str(tmp_path), "--suite", SUITE]) == 0
    assert "seed" not in json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    assert bench.tasks_md(SUITE, "frames") == bench.tasks_md(SUITE, "frames", seed=None)
    assert "fresh seed" not in bench.tasks_md(SUITE, "frames")


def test_bare_seed_picks_a_random_one_and_other_suites_refuse(tmp_path, monkeypatch, capsys):
    fake_draw(monkeypatch, 31337)
    monkeypatch.setattr(suite3, "new_seed", lambda: 31337)
    assert bench.main(["prepare", "--out", str(tmp_path), "--suite", SUITE, "--seed"]) == 0
    assert json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))["seed"] == 31337
    with pytest.raises(SystemExit):
        bench.main(["prepare", "--out", str(tmp_path / "x"), "--suite", "svc-bench-2", "--seed", "3"])
    with pytest.raises(SystemExit):
        bench.main(["prepare", "--out", str(tmp_path / "y"), "--suite", SUITE, "--seed", "-4"])


def test_score_and_validate_rebuild_the_truth_from_the_seed(tmp_path, monkeypatch):
    v = suite3.seeded(77)
    answers = {t.id: t.truth for t in v.TASKS}
    (tmp_path / "answers.json").write_text(json.dumps({"suite": SUITE, "seed": 77, "answers": answers}),
                                           encoding="utf8")
    monkeypatch.chdir(tmp_path)
    assert bench.main(["score", str(tmp_path), "--agent", "Codex", "--model", "gpt-x"]) == 0
    files = list((tmp_path / "benchmark" / "results").glob("*.json"))
    assert len(files) == 1 and files[0].name.endswith("-svc-bench-3-seed77.json")
    res = json.loads(files[0].read_text(encoding="utf8"))
    assert res["seed"] == 77 and res["total"] == 1.0
    assert S.validate_file(files[0]) == []
    # the published suite's truth does not pass for a seeded row, nor another seed's
    assert S.problems(dict(res, seed=78)) and S.problems({k: x for k, x in res.items() if k != "seed"})
    assert any("seed" in p for p in S.problems(dict(res, seed=-1)))
    assert any("seed" in p for p in S.problems(dict(res, suite="svc-bench-2")) + S.problems(dict(res, seed="77")))


def test_answers_from_reply_keeps_the_seed(tmp_path):
    v = suite3.seeded(5)
    (tmp_path / "answers.json").write_text(json.dumps({"suite": SUITE, "track": "frames", "seed": 5,
                                                       "answers": {t.id: None for t in v.TASKS}}), encoding="utf8")
    reply = "done\n```json\n" + json.dumps({"answers": {"juggle-touches": 40}}) + "\n```"
    assert run.answers_from_reply(tmp_path, reply, SUITE, "frames", 5)
    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf8"))
    assert data["seed"] == 5 and data["answers"]["juggle-touches"] == 40


def test_run_dry_run_names_the_seed(capsys):
    assert run.main(["--agent", "claude", "--suite", SUITE, "--track", "frames", "--seed", "12", "--dry-run"]) == 0
    assert "from fresh seed 12" in capsys.readouterr().out


def test_blind_baseline_on_a_seed_reads_that_seed_s_task_text():
    v = suite3.seeded(9)
    guess = baseline.answers(SUITE, "frames", seed=9)
    assert len(guess["far-hoop-shots"]) == len(v.spec.shots)
    res = baseline.result(SUITE, "frames", seed=9)
    assert res["seed"] == 9 and S.problems(res) == []


def seeded_row(seed: int, model: str, right: int) -> dict:
    v = suite3.seeded(seed)
    answers = {t.id: (t.truth if i < right else None) for i, t in enumerate(v.TASKS)}
    res = S.result(answers, "Claude Code", model, "2.1", "frames track", "someone", 100, "", "2026-10-25", SUITE,
                   "frames", seed)
    return res


def test_page_lists_seeded_runs_on_their_own_board_with_their_own_floor(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "a.json").write_text(json.dumps(seeded_row(11, "m1", 4)), encoding="utf8")
    (results / "b.json").write_text(json.dumps(seeded_row(12, "m2", 2)), encoding="utf8")
    assert page.main([str(results), str(tmp_path / "site")]) == 0
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf8")
    assert 'id="frames-svc-bench-3-fresh"' in html and "seed 11" in html and "seed 12" in html
    assert "2 of 2 runs drew svc-bench-3 from a fresh seed" in html
    rows = page.load(results)[0]
    assert {page.suite_of(r) for r in rows} == {"svc-bench-3-fresh"}
    assert page.above_value(rows[0], None) is not None          # its own seed's floor, computed
    tasks = page.fails(rows, "svc-bench-3-fresh")
    assert tasks and all(t["truth"] is None for t in tasks)
    juggle = next(t for t in tasks if t["id"] == "juggle-touches")
    assert {x["truth"] for x in juggle["runs"]} == {suite3.seeded(11).BY_ID["juggle-touches"].truth,
                                                    suite3.seeded(12).BY_ID["juggle-touches"].truth}
