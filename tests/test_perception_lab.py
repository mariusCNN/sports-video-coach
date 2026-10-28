"""Synthetic geometry, evaluation and public CLI contracts; no downloaded models."""
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from hoop_tape_miner import perception_backends as backend
from hoop_tape_miner import perception_lab as lab


def test_wasb_affine_roundtrip_and_padding():
    for width, height in [(1280, 720), (640, 480), (480, 640)]:
        a = backend.wasb_affine(width, height)
        centre = a @ [width/2, height/2, 1]
        assert centre == pytest.approx([256, 144])
        inv = cv2.invertAffineTransform(a)
        assert inv @ [*centre, 1] == pytest.approx([width/2, height/2])
        assert a[0, 0] == a[1, 1]


def test_heatmap_mass_and_null_observation():
    hm = np.zeros((288, 512), np.float32)
    inv = cv2.invertAffineTransform(backend.wasb_affine(1280, 720))
    assert backend.decode_ball_heatmap(hm, inv, 1280, 720) == []
    hm[100, 200:202] = [.6, .9]
    ball = backend.decode_ball_heatmap(hm, inv, 1280, 720)[0]
    assert ball["xy"] == pytest.approx([501.5, 250])
    assert ball["score"] == pytest.approx(1.5)
    assert ball["score_kind"] == "heatmap_mass"


def test_heatmap_padding_not_a_ball():
    hm = np.zeros((288, 512), np.float32)
    hm[0, 0] = .9
    inv = cv2.invertAffineTransform(backend.wasb_affine(480, 640))
    assert backend.decode_ball_heatmap(hm, inv, 480, 640) == []


def test_kali_grid_matches_upstream_nonuniform_rows():
    grid = backend.kalicalib_grid()
    assert grid.shape == (91, 2)
    assert grid[0].tolist() == [0, 1500]
    assert grid[13].tolist() == [0, 1325]
    assert grid[-1].tolist() == [2800, 0]


def test_court_fit_requires_measured_inliers_and_no_mean_fallback():
    result = backend.fit_court_proposal([], [], 1280, 720)
    assert result["H"] is None
    assert result["trusted"] is False
    world = [[i, 0] for i in range(8)]
    assert backend.fit_court_proposal(world, world, 1280, 720)["reason"] == "collinear_correspondences"


def test_court_fit_converts_cm_to_m_and_near_sideline():
    world = backend.kalicalib_grid()
    H = np.array([[.3, 0, 100], [0, -.25, 600], [0, 0, 1.]])
    image = cv2.perspectiveTransform(world[None], H)[0]
    result = backend.fit_court_proposal(world, image, 1280, 720)
    assert result["status"] == "candidate"
    assert result["trusted"] is False
    projected = np.array(result["H"]) @ [28, 15, 1]
    assert (projected[:2]/projected[2]).tolist() == pytest.approx([940, 225], abs=.01)


def test_court_fit_rejects_tiny_hallucinated_polygon():
    world = backend.kalicalib_grid()
    image = world * .001
    assert backend.fit_court_proposal(world, image, 1280, 720)["reason"] == "implausible_court_area"


def test_court_evaluation_is_independent_not_training_residual():
    predictions = [{"id":"x", "court":{"H":np.eye(3).tolist()}}]
    labels = {"labels":[{"id":"x", "points":[{"world_m":[0,0], "image_xy":[3,4]}]}]}
    assert lab.evaluate_court(predictions, labels)["median_error_px"] == 5


def test_ball_wrong_position_counts_as_fp_and_fn():
    pred = [{"id":"a", "ball":[{"xy":[100,100], "score":.9}]}]
    labels = {"review_complete":True, "labels":[{"id":"a", "state":"visible", "xy":[0,0]}]}
    result = lab.evaluate_ball(pred, labels)
    assert (result["tp"], result["fp"], result["fn"]) == (0,1,1)


def test_ball_does_not_select_candidate_using_ground_truth():
    pred = [{"id":"a", "ball":[{"xy":[100,100], "score":.9}, {"xy":[0,0], "score":.3}]}]
    labels = {"review_complete":True, "labels":[{"id":"a", "state":"visible", "xy":[0,0]}]}
    result = lab.evaluate_ball(pred, labels)
    assert result["tp"] == 0
    assert result["any_candidate_hits"] == result["extra_candidates"] == 1


def test_ball_unclear_excluded_occluded_prediction_false_positive():
    pred = [{"id":x, "ball":[{"xy":[0,0], "score":.9}]} for x in ("a", "b")]
    labels = {"review_complete":True, "labels":[{"id":"a", "state":"unclear"},
                                               {"id":"b", "state":"occluded"}]}
    result = lab.evaluate_ball(pred, labels)
    assert result["evaluated_frames"] == result["unclear"] == result["fp"] == 1
    assert result["recall"] is None


def test_ball_rejects_unfinished_labels():
    with pytest.raises(ValueError):
        lab.evaluate_ball([], {"review_complete":False})


@pytest.mark.parametrize("change", [{"t":2}, {"image":"../frame.png"}, {"frame_index":-60}])
def test_samples_reject_misaligned_or_unsafe_data(change):
    sample = {"id":"a", "image":"frame.png", "t":1., "frame_index":60, **change}
    with pytest.raises(ValueError):
        lab.validate_samples({"fps":60, "samples":[sample]})


def test_provenance_rejects_unpinned_source(tmp_path):
    (tmp_path/"source-manifest.json").write_text(json.dumps({"commit":"latest"}))
    with pytest.raises(ValueError, match="Unsupported"):
        backend.provenance(tmp_path, "WASB-SBDT", [])


def test_lab_is_registered_and_help_needs_no_optional_models(capsys):
    from hoop_tape_miner.plugin import STAGES
    assert STAGES["perception-lab"][0] == "hoop_tape_miner.perception_lab"
    with pytest.raises(SystemExit) as ex:
        lab.main(["--help"])
    assert ex.value.code == 0
    assert "evaluate" in capsys.readouterr().out


def test_ball_rejects_incomplete_coverage_disguised_as_complete():
    with pytest.raises(ValueError, match="no label"):
        lab.evaluate_ball([{"id":"missing", "ball":[]}], {"review_complete":True,"labels":[]})


def test_real_sahi_restores_coordinates_and_suppresses_overlap():
    pytest.importorskip("sahi")
    class SyntheticDetector:
        threshold = .3
        def predict(self, image):
            if image.shape[1] > 128:
                return []  # simulate a ball missed in the full frame
            ys, xs = np.where(image[:, :, 0] > 0)
            if not len(xs):
                return []
            return [{"box":[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)],"score":.9}]
    image = np.zeros((256,512,3),np.uint8)
    image[135:145,345:355,0] = 255
    output = backend.sliced_ball_prediction(image, backend.sahi_model(SyntheticDetector()), size=128)
    assert len(output) == 1
    assert output[0]["xy"] == pytest.approx([350,140])


def test_report_link_is_optional_and_team_only(tmp_path):
    from hoop_tape_miner.perception_lab_page import report_section
    assert report_section(tmp_path, "en", 1) == ("", [])
    (tmp_path/"perception-lab").mkdir()
    (tmp_path/"perception-lab/index.html").write_text("test")
    assert report_section(tmp_path, "en", 1) == ("", [])
    (tmp_path/"game.json").write_text("{}")
    markup, titles = report_section(tmp_path, "en", 4)
    assert 'id="en-s4"' in markup
    assert 'href="perception-lab/index.html"' in markup
    assert len(titles) == 1
