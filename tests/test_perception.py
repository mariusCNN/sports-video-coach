import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hoop_tape_miner import perception as P
from hoop_tape_miner.perception_media import select_events
from hoop_tape_miner.perception_review import compare_reviewed, project_candidates
from hoop_tape_miner.perception_eval import evaluate, match_times
from hoop_tape_miner import perception_media as PM


def frame(number=1, events=None):
    return dict(schema="basketball_frame_v2", frame=number, time=(number - 1) / 25, fps=25,
                ball=dict(observed=True, interpolated=False), players=[dict(
                    id=4, local_track_id=9, team_semantic="dark", jersey_number="7",
                    box=[20, 10, 40, 30], pose=[[1, 2, .9]], court_xy=[20, 8])], events=events or [])


def write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf8")
    return path


def shot(**kw):
    return dict(event="shot", start_frame=1, end_frame=2, result="made", team="dark", player_id=4,
                points=2, points_source="two_point_fallback", result_source="ball_in_basket", **kw)


def test_clock_offset_uncertainty_and_provenance(tmp_path):
    source = write(tmp_path / "frames.jsonl", [frame(), frame(2, [shot()])])
    data = P.import_jsonl(source, offset=100, team_map={"dark": "us", "light": "them"}, rosters={"us": ["7"]})
    event = data["events"][0]
    assert (event["start"], event["end"], event["team"]) == (100, 100.04, "us")
    assert event["points"] is None and event["court_xy"] is None
    assert event["review_status"] == "pending"
    assert event["raw"]["points"] == 2
    assert event["evidence"]["points_source"] == "two_point_fallback"
    assert data["identities"][0]["numbers"] == {"7": 2}
    assert P.bundle([data])["upstream_commit"] is None


def test_unknown_outcome_and_unmapped_team_stay_unknown(tmp_path):
    event = shot()
    event["result"] = "unknown"
    data = P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [event])]))
    assert data["events"][0]["result"] is None
    assert data["events"][0]["team"] is None
    assert data["identities"][0]["numbers"] == {}


def test_all_event_types_deduplicate_completed_events(tmp_path):
    events = [dict(event=kind, start=0, end=.04, player_id=1) for kind in P.EVENTS]
    path = write(tmp_path / "x", [frame(), frame(2, events), frame(3, events)])
    result = P.bundle([P.import_jsonl(path)])
    assert set(result["event_counts"]) == P.EVENTS
    assert len(result["events"]) == len(P.EVENTS)
    assert result["counts"]["frames"] == 3


@pytest.mark.parametrize("patch", [dict(schema="v2"), dict(fps=0), dict(time=2), dict(frame=1.5), dict(time=float("nan"))])
def test_bad_frame_rejected_with_line_number(tmp_path, patch):
    with pytest.raises(ValueError, match=":1:"):
        P.import_jsonl(write(tmp_path / "x", [{**frame(), **patch}]))


def test_duplicate_frames_rejected(tmp_path):
    with pytest.raises(ValueError, match="increase"):
        P.import_jsonl(write(tmp_path / "x", [frame(), frame()]))


def test_gaps_cannot_claim_continuous_analyzed_coverage(tmp_path):
    with pytest.raises(ValueError, match="consecutively"):
        P.import_jsonl(write(tmp_path / "x", [frame(), frame(251)]))


def test_conflicting_event_seconds_and_frame_are_rejected(tmp_path):
    event = shot(start=1)
    with pytest.raises(ValueError, match="seconds and frame disagree"):
        P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [event])]))


def test_conflicting_repeated_event_is_not_silently_kept(tmp_path):
    first, second = shot(), shot()
    second["result"] = "missed"
    with pytest.raises(ValueError, match="conflicting copies"):
        P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [first]), frame(3, [second])]))


def test_overlap_and_ambiguous_team_map_rejected(tmp_path):
    source = write(tmp_path / "x", [frame()])
    with pytest.raises(ValueError, match="one-to-one"):
        P.import_jsonl(source, team_map={"dark": "us", "light": "us"})
    one = P.import_jsonl(source)
    with pytest.raises(ValueError, match="overlapping"):
        P.bundle([one, copy.deepcopy(one)])


def test_roster_rejects_unlisted_number(tmp_path):
    data = P.import_jsonl(write(tmp_path / "x", [frame()]), team_map={"dark": "us"}, rosters={"us": ["9"]})
    assert data["identities"][0]["numbers"] == {}
    assert data["counts"]["number_observations"] == 1  # raw coverage is not accepted identity


def test_reviews_need_known_ids_and_evidence(tmp_path):
    doc = P.bundle([P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [shot()])]))])
    with pytest.raises(ValueError, match="unknown event"):
        P.apply_reviews(doc, {"bad": dict(status="confirmed", note="seen")})
    key = doc["events"][0]["id"]
    with pytest.raises(ValueError, match="evidence note"):
        P.apply_reviews(doc, {key: dict(status="confirmed")})
    P.apply_reviews(doc, {key: dict(status="rejected", note="ball stayed with holder")})
    assert doc["events"][0]["review_status"] == "rejected"
    assert doc["events"][0]["points"] is None
    with pytest.raises(ValueError, match="damaged encoding"):
        P.apply_reviews(doc, {key: dict(status="rejected", note="seen", note_zh="?????????")})


def test_comparison_is_one_to_one_and_flags_team_conflict(tmp_path):
    doc = P.bundle([P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [shot()])]), team_map={"dark": "us"})])
    (tmp_path / "coach_part1.json").write_text(json.dumps([
        dict(shot=dict(t=0, made=True), offence="them"), dict(shot=dict(t=.01, made=True), offence="us")]))
    compare_reviewed(doc, tmp_path)
    assert doc["comparison"]["matched"] == 1
    assert doc["events"][0]["existing_review"]["conflicts"] == ["team"]
    assert doc["events"][0]["review_status"] == "pending"


def test_fiba_projection_uses_our_calibration_and_never_points(tmp_path):
    import numpy as np
    doc = P.bundle([P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [shot()])]))])
    camera = tmp_path / "camera.npz"
    doc["sources"][0]["spatial"] = dict(aligned=True)
    np.savez(camera, t=[0], H=[[[2, 0, 0], [0, 3, 0], [0, 0, 1]]], quality=[1])
    project_candidates(doc, camera)
    event = doc["events"][0]
    assert event["court_xy"] == [15, 10]
    assert event["points"] is None
    assert event["court_evidence"]["trusted"] is False


def test_page_escapes_review_and_tracks_evidence_dependency(tmp_path):
    from hoop_tape_miner import page_hooks, perception_page
    (tmp_path / "game.json").write_text(json.dumps(dict(video="v.mp4", run="run")))
    root = tmp_path / "run" / "perception"
    root.mkdir(parents=True)
    doc = P.bundle([P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [shot()])]))])
    key = doc["events"][0]["id"]
    P.apply_reviews(doc, {key: dict(status="unclear", note='<script>alert(1)</script>')})
    (root / "evidence.json").write_text(json.dumps(doc))
    assets = tmp_path / "perception"
    assets.mkdir()
    (assets / "media.json").write_text(json.dumps(dict(event_ids=[key])))
    rendered, heads = perception_page.sections(tmp_path, "en", 3)
    assert '<script>alert(1)</script>' not in rendered
    assert '&lt;script&gt;' in rendered
    assert 'id="en-s3"' in rendered and len(heads) == 1
    assert root / "evidence.json" in page_hooks.page_inputs(tmp_path)


def test_backend_not_enabled_by_default():
    assert not P.enabled(SimpleNamespace(game={}))
    assert P.enabled(SimpleNamespace(game={"perception": {"enabled": True}}))


def test_selection_keeps_reviewed_examples():
    events = [dict(id=str(i), type="shot", start=i, review_status="pending") for i in range(20)]
    events[18]["review_status"] = "rejected"
    result = select_events(events, 3)
    assert len(result) == 3 and events[18] in result


def test_selection_reserves_remaining_places_for_unrepresented_kinds():
    events = [dict(id=str(i), type="shot", start=i, review_status="confirmed") for i in range(10)]
    events += [dict(id=str(i), type=kind, start=i, review_status="pending")
               for i, kind in enumerate(("shot", "turnover", "dribble"), 10)]
    result = select_events(events, 12)
    assert {e["type"] for e in result} == {"shot", "turnover", "dribble"}


def test_event_relationships_stay_namespaced(tmp_path):
    event = dict(event="turnover", start=0, end=0, player_id=2, gained_by=3,
                 team="dark", gained_team="light", cause="steal")
    doc = P.import_jsonl(write(tmp_path / "x", [frame(events=[event])]), source_id="clip-a",
                         team_map={"dark": "us", "light": "them"})
    candidate = doc["events"][0]
    assert candidate["gained_by"] == "clip-a:3"
    assert candidate["gained_team"] == "them" and candidate["team"] == "us"
    assert candidate["cause"] == "steal" and candidate["type"] == "turnover"


def test_matching_maximizes_pairs_before_minimizing_error():
    # Greedy would pair 1.1 with 1 and lose 0's only match.
    assert match_times([0, 1.1], [(1, 1), (2, 2)], 1) == [(0, 0), (1, 1)]
    assert match_times([4], [(3.8, 4.2)], 0) == [(0, 0)]
    assert match_times([], [], 1) == []


def test_local_evaluation_separates_attempts_outcome_and_team():
    doc = dict(sources=[dict(start=0, end=10, finalization="adapter_completed_run")], events=[
        dict(id="a", type="shot", start=2, team="them", result="made"),
        dict(id="b", type="shot", start=2.2, team="us", result="missed"),
        dict(id="c", type="shot", start=8, team=None, result=None)])
    labels = dict(schema="svc_perception_labels_v1", windows=[dict(start=0, end=10, shots=[
        dict(release=[1.9, 2.1], team="us", result="missed"),
        dict(release=[7.9, 8.1], team="them", result="made")])])
    result = evaluate(doc, labels)["totals"]
    assert result["matched"] == 2 and result["unmatched_candidates"] == 1
    assert result["false_makes"] == 1 and result["outcome_correct"] == 0
    assert result["outcome_unresolved"] == 1 and result["team_unresolved"] == 1
    assert result["team_correct"] == 0
    labels["windows"][0]["end"] = 11
    with pytest.raises(ValueError, match="not fully covered"):
        evaluate(doc, labels)
    labels["windows"][0]["end"] = 10
    doc["sources"][0]["finalization"] = "external_unverified"
    with pytest.raises(ValueError, match="not fully covered"):
        evaluate(doc, labels)


def test_completed_analysis_requires_full_video_and_matching_settings(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    game = SimpleNamespace(game={"perception": dict(enabled=True, fps=24)}, video=video, run=tmp_path)
    root = tmp_path / "perception" / "clip"
    root.mkdir(parents=True)
    (root / "tracks.jsonl").write_text("completed")
    sig = dict(upstream_commit=P.PIN, start=0, end=12, fps=24, short_side=768, batch=2,
               video=str(video.resolve()), video_size=video.stat().st_size, video_mtime=video.stat().st_mtime_ns)
    monkeypatch.setattr(P.media, "duration_s", lambda p: 100)
    (root / "run.json").write_text(json.dumps(dict(signature=sig)))
    assert not P.analysis_done(game)
    sig["end"] = 100
    (root / "run.json").write_text(json.dumps(dict(signature=sig)))
    assert P.analysis_done(game)
    game.game["perception"]["fps"] = 12
    assert not P.analysis_done(game)
    game.game["perception"].update(fps=24, checkout=str(tmp_path / "backend"))
    weights = tmp_path / "backend" / "weights"
    weights.mkdir(parents=True)
    model = weights / "model.pth"
    model.write_bytes(b"first weights")
    (root / "run.json").write_text(json.dumps(dict(signature=sig, weights={model.name: P.digest(model)})))
    assert P.analysis_done(game)
    model.write_bytes(b"new model weights")
    assert not P.analysis_done(game)


def test_completion_needs_video_binding_digest_and_full_span(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    source = dict(sha256="digest", start=0, end=12, fps=24)
    sig = dict(upstream_commit=P.PIN, start=0, end=12, video=str(video.resolve()),
               video_size=video.stat().st_size, video_mtime=video.stat().st_mtime_ns)
    stamp = dict(signature=sig, command=["python", "main.py"], weights={"model": "sha"}, tracks_sha256="digest")
    assert P.verified_completion(stamp, source, video)
    for key in ("tracks_sha256", "signature", "command", "weights"):
        bad = copy.deepcopy(stamp)
        bad.pop(key)
        assert not P.verified_completion(bad, source, video)
    stamp["signature"]["end"] = 20
    assert not P.verified_completion(stamp, source, video)


def test_media_cache_requires_every_referenced_asset(tmp_path):
    manifest = dict(signature={"test": 1}, event_ids=["a"])
    (tmp_path / "media.json").write_text(json.dumps(manifest))
    for name in ("a.mp4", "a-overlay.mp4", "validation.mp4"):
        (tmp_path / name).write_bytes(b"video")
    assert PM.complete(tmp_path, manifest["signature"])
    (tmp_path / "a.mp4").unlink()
    assert not PM.complete(tmp_path, manifest["signature"])
    manifest["event_ids"] = []
    (tmp_path / "media.json").write_text(json.dumps(manifest))
    assert PM.complete(tmp_path, manifest["signature"])


def test_unverified_external_coordinates_are_not_projected_or_overlaid(tmp_path):
    import numpy as np
    doc = P.bundle([P.import_jsonl(write(tmp_path / "x", [frame(), frame(2, [shot()])]))])
    camera = tmp_path / "camera.npz"
    np.savez(camera, t=[0], H=[[[2, 0, 0], [0, 3, 0], [0, 0, 1]]], quality=[1])
    project_candidates(doc, camera)
    assert doc["events"][0]["court_xy"] is None
    assert PM.frame_rows(doc, doc["events"]) == {}


def test_overlay_rejects_changed_evidence_stream(tmp_path):
    source = write(tmp_path / "x", [frame(), frame(2, [shot()])])
    doc = P.bundle([P.import_jsonl(source)])
    doc["sources"][0]["spatial"] = dict(aligned=True)
    source.write_text("changed after import", encoding="utf8")
    with pytest.raises(ValueError, match="changed after import"):
        PM.frame_rows(doc, doc["events"])


def test_overlay_handles_source_frame_rate_below_output(tmp_path):
    import shutil
    pytest.importorskip("cv2")
    if not shutil.which(P.media.ffmpeg_exe()):
        pytest.skip("ffmpeg unavailable")
    source, out = tmp_path / "source.mp4", tmp_path / "overlay.mp4"
    P.media.ffmpeg("-f", "lavfi", "-i", "testsrc2=size=320x180:rate=8:duration=1", "-c:v", "libx264", source)
    PM.render_overlay(source, out, dict(type="shot", review_status="pending"), [], 0, 1)
    assert abs(P.media.duration_s(out) - 1) < .06


def test_perception_steps_are_optional_and_in_order():
    from hoop_tape_miner.run import STEPS
    names = [s.name for s in STEPS]
    assert names.index("perception") < names.index("perception-import") < names.index("perception-media") < names.index("html")
    disabled = SimpleNamespace(game={})
    assert all(s.done(disabled) for s in STEPS if s.name.startswith("perception"))
