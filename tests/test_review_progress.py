"""Interrupted review coverage resumes without losing or silently trusting changed inputs."""
import json

import pytest

from hoop_tape_miner import coach_review, coach_schema, review_progress as P
from hoop_tape_miner.coach_eval import part_coverage


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf8")


@pytest.fixture
def review(tmp_path):
    write(tmp_path / P.POLICY, {"sheet_coverage": 1})
    write(tmp_path / "part1.json", [
        {"pid": 1, "start": 0, "end": 5, "sheets": ["a.jpg", "b.jpg"]},
        {"pid": 2, "start": 5, "end": 10, "sheets": ["c.jpg"]}])
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (tmp_path / name).write_bytes(name.encode())
    return tmp_path


def checkpoint(review, pids):
    write(review / "coach_part1.json", [
        {"schema": 2, "pid": pid, "trip": 1, "t0": (pid - 1) * 5, "t1": pid * 5,
         "offence": "none", "result": "dead_ball", "shot": None, "fts": None, "foul": None,
         "evidence": {"result": [(pid - 1) * 5 + 1]}, "confidence": "low"} for pid in pids])


def test_interrupted_resume_preserves_checkpoint_and_lists_exact_remainder(review):
    checkpoint(review, [1])
    P.progress(review, 1, ["a.jpg", "b.jpg"])
    before = (review / "coach_part1.json").read_bytes()
    # A fresh command invocation recovers progress solely from disk.
    assert P.progress(review, 1)["pending"] == ["c.jpg"]
    assert (review / "coach_part1.json").read_bytes() == before
    assert part_coverage(review)
    checkpoint(review, [1, 2])
    P.progress(review, 1, ["c.jpg"])
    assert P.progress(review, 1)["read"] == 3
    assert part_coverage(review) == []
    coach_schema.main(["--review", str(review)])


def test_missing_sheet_blocks_check_even_when_all_possessions_exist(review):
    checkpoint(review, [1, 2])
    P.progress(review, 1, ["a.jpg", "c.jpg"])
    with pytest.raises(SystemExit):
        coach_schema.main(["--review", str(review)])
    assert P.progress(review, 1)["pending"] == ["b.jpg"]


def test_requires_saved_valid_possession_before_recording_read(review):
    with pytest.raises(ValueError, match="save coach"):
        P.progress(review, 1, ["a.jpg"])
    checkpoint(review, [1])
    with pytest.raises(ValueError, match="save pid 2"):
        P.progress(review, 1, ["c.jpg"])
    assert not (review / "read_part1.json").exists()
    write(review / "coach_part1.json", [{"pid": 1}])
    with pytest.raises(ValueError, match="invalid checkpoint"):
        P.progress(review, 1, ["a.jpg"])


def test_changed_or_missing_image_is_pending_again(review):
    checkpoint(review, [1, 2])
    P.progress(review, 1, ["a.jpg", "b.jpg", "c.jpg"])
    (review / "b.jpg").write_bytes(b"changed")
    (review / "c.jpg").unlink()
    assert P.progress(review, 1)["pending"] == ["b.jpg", "c.jpg"]
    with pytest.raises(ValueError, match="sheet not found"):
        P.progress(review, 1, ["c.jpg"])


def test_changed_partition_invalidates_prior_reads(review):
    checkpoint(review, [1, 2])
    P.progress(review, 1, ["a.jpg", "b.jpg", "c.jpg"])
    parts = json.loads((review / "part1.json").read_text())
    parts[0]["end"] = 6
    write(review / "part1.json", parts)
    assert P.progress(review, 1)["read"] == 0


def test_unknown_and_escaping_paths_rejected_without_writes(review):
    with pytest.raises(ValueError, match="not assigned"):
        P.progress(review, 1, ["other.jpg"])
    write(review / "part1.json", [{"pid": 1, "sheets": ["../escape.jpg"]}])
    with pytest.raises(ValueError, match="unsafe"):
        P.progress(review, 1)
    assert not (review / "read_part1.json").exists()


def test_legacy_review_compatible_and_corrupt_policy_fails(review):
    (review / P.POLICY).unlink()
    checkpoint(review, [1, 2])
    assert part_coverage(review) == []
    write(review / P.POLICY, {"sheet_coverage": 999})
    assert "unsupported" in part_coverage(review)[0]


@pytest.mark.parametrize("filename", ["coach_part1.json", "read_part1.json"])
def test_regeneration_refuses_checkpointed_folder_before_mutation(review, filename):
    write(review / filename, {})
    before = {p.name: p.read_bytes() for p in review.iterdir()}
    with pytest.raises(SystemExit, match="checkpoints already exist"):
        coach_review.main(["--run", str(review), "--game", "missing.json", "--out", str(review),
                           "--skip-sheets", "--max-sheets", "1"])
    assert before == {p.name: p.read_bytes() for p in review.iterdir()}


def test_progress_cli_is_machine_readable_and_bad_ledger_blocks(review, capsys):
    coach_review.main(["progress", "--review", str(review), "--part", "1"])
    assert json.loads(capsys.readouterr().out)["pending"] == ["a.jpg", "b.jpg", "c.jpg"]
    (review / "read_part1.json").write_text("broken", encoding="utf8")
    assert P.errors(review)


def test_interrupted_sheet_generation_cannot_pass_as_a_legacy_review(review):
    from types import SimpleNamespace
    from hoop_tape_miner.run import parts_listed
    (review / P.POLICY).unlink()
    checkpoint(review, [1, 2])
    (review / ".sheets-incomplete").write_text("in progress", encoding="utf8")
    assert not parts_listed(SimpleNamespace(review=review))
    assert "generation incomplete" in part_coverage(review)[0]
