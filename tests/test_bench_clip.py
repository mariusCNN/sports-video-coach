"""The benchmark page's clip (`bench.clip`): every number it draws comes from the result files or the suite."""
import json
from pathlib import Path

import pytest

from sports_video_coach.bench import clip, page, suite3
from sports_video_coach.bench.suite import FPS

RESULTS = Path(__file__).resolve().parents[1] / "benchmark" / "results"


def task_runs() -> list[tuple[str, dict, dict]]:
    """(file name, result, juggle-touches task) for every svc-bench-3 frames result file in the repo (not on a fresh
    seed: the clip shows the published suite)."""
    out = []
    for f in sorted(RESULTS.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf8"))
        if r.get("suite") == clip.SUITE and r.get("track") == clip.TRACK and r.get("seed") is None:
            out.append((f.name, r, next(t for t in r["tasks"] if t["id"] == clip.TASK)))
    return out


def test_every_run_of_the_task_is_shown_once_with_its_file_answer():
    rows, _ = page.load(RESULTS)
    data = clip.clip_data(rows)
    shown = {run["file"]: run for c in data["contenders"] for run in c["runs"]}
    files = task_runs()
    assert len(files) >= 2 and sorted(shown) == sorted(name for name, _, _ in files)
    for name, r, task in files:
        assert shown[name]["answer"] == task["answer"] and shown[name]["score"] == (task["score"] or 0.0)
        assert task["truth"] == data["truth"] == suite3.BY_ID[clip.TASK].truth
    assert data["contenders"][-1]["baseline"]                         # the blind guess comes last
    assert data["runs"] == sum(1 for _, r, _ in files if not page.is_baseline(r))


def test_drawn_text_matches_the_files():
    rows, _ = page.load(RESULTS)
    data = clip.clip_data(rows)
    text = clip.scenes(data)
    assert text["answers"]["title"] == f"Truth: {suite3.BY_ID[clip.TASK].truth} touches"
    drawn = {r["label"]: r["answers"] for r in text["answers"]["rows"]}
    for name, r, task in task_runs():
        c = r["contender"]
        label = "Blind guess" if page.is_baseline(r) else clip.model_label(c["agent"], c.get("model") or "")
        assert ("–" if task["answer"] is None else str(task["answer"])) in drawn[label]
    assert sum(len(a) for a in drawn.values()) == len(task_runs())


def test_the_hard_moment_comes_from_the_suite():
    m = clip.double_touch()
    f0, f1 = m["frames"]
    assert f0 in suite3.JUG_TOUCHES and f1 in suite3.JUG_TOUCHES and f1 - f0 <= 6
    assert m["numbers"] == [suite3.JUG_TOUCHES.index(f0) + 1, suite3.JUG_TOUCHES.index(f1) + 1]
    assert m["gap_s"] == round((f1 - f0) / FPS, 2) == 0.24
    assert (f0, "F", m["hop_px"]) in suite3.JUG_CONTACTS and m["ball_r"] == suite3.JUG_R
    caption = " ".join(clip.scenes(clip.clip_data(page.load(RESULTS)[0]))["slow"]["caption"])
    assert f"{m['gap_s']:.2f} s apart" in caption and f"hops {m['hop_px']} px" in caption


def test_no_clip_without_a_run_of_the_task():
    rows, _ = page.load(RESULTS)
    assert clip.clip_data([r for r in rows if page.suite_of(r) != clip.SUITE]) is None
    assert clip.clip_data([r for r in rows if r["suite"] == clip.SUITE and page.is_baseline(r)]) is None


def test_a_file_whose_truth_differs_from_the_suite_is_refused():
    rows, _ = page.load(RESULTS)
    bad = [json.loads(json.dumps(r)) for r in rows if page.suite_of(r) == clip.SUITE and page.track_of(r) == "frames"]
    next(t for t in bad[0]["tasks"] if t["id"] == clip.TASK)["truth"] = 1
    with pytest.raises(ValueError, match="truth"):
        clip.clip_data(bad)


def test_model_label():
    assert clip.model_label("Claude Code", "claude-opus-5-5") == "Opus 5.5"
    assert clip.model_label("Codex", "gpt-6-astra") == "Codex · gpt-6-astra"
    assert clip.model_label("aider", "") == "aider"


def test_page_shows_the_clip_only_when_drawn():
    rows, notes = page.load(RESULTS)
    with_clip = page.render(rows, notes, clip=True)
    assert f'<video src="{clip.MP4}"' in with_clip and f'alt="{page.esc(clip.ALT)}"' in with_clip
    assert with_clip.index("<video") < with_clip.index('id="leaderboard"')     # at the top
    assert "<video" not in page.render(rows, notes)
