"""Optional, local-only perception experiments. No model or package downloads.

WASB and KaliCalib architectures stay in separately licensed source checkouts.
SAHI runs its real sliced prediction implementation with our local RF-DETR model.
All coordinates are source pixels; observations are candidates, never game facts.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

PINS = {
    "WASB-SBDT": "923462cacdeb3353b84ddebdedb3f4b7a8553b0f",
    "KaliCalib": "3b3f52b59e8e38e155ba7e9c681281d44748c173",
    "sahi": "b5a153ee7bcb1fd84a7b868575ff14131e7423ce",
}


class _Config(dict):
    """Upstream HRNet uses both mapping and attribute access (normally OmegaConf)."""
    def __getattr__(self, name):
        value = self[name]
        return _Config(value) if isinstance(value, dict) else value


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def provenance(root, name, files):
    root = Path(root)
    if (root / "source-manifest.json").exists():
        manifest = json.loads((root / "source-manifest.json").read_text(encoding="utf8"))
    else:
        import subprocess
        commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        manifest = {"commit": commit}
    if manifest.get("commit") != PINS[name]:
        raise ValueError(f"Unsupported {name} revision; expected {PINS[name]}")
    return {**manifest, "files": {p: sha256(root / p) for p in files}}


def normalized_tensor(rgb, device):
    import numpy as np
    import torch
    a = np.ascontiguousarray(rgb.transpose(2, 0, 1))
    t = torch.from_numpy(a).float().div(255)
    return ((t - torch.tensor([.485, .456, .406])[:, None, None]) /
            torch.tensor([.229, .224, .225])[:, None, None]).to(device)


def wasb_affine(width, height):
    """Exact upstream zero-rotation, max-side affine (including non-16:9 padding)."""
    import numpy as np
    scale = 512 / max(width, height)
    return np.array([[scale, 0, 256 - width * scale / 2],
                     [0, scale, 144 - height * scale / 2]], dtype=np.float32)


def decode_ball_heatmap(heatmap, inverse, width, height, threshold=.5):
    import cv2
    import numpy as np
    count, labels = cv2.connectedComponents((heatmap > threshold).astype(np.uint8))
    candidates = []
    for label in range(1, count):
        ys, xs = np.where(labels == label)
        weights = heatmap[ys, xs]
        mass = float(weights.sum())
        xy = inverse @ np.array([(xs * weights).sum() / mass,
                                 (ys * weights).sum() / mass, 1])
        if 0 <= xy[0] < width and 0 <= xy[1] < height:
            candidates.append({"xy": xy.tolist(), "score": mass,
                               "score_kind": "heatmap_mass", "peak": float(weights.max())})
    return sorted(candidates, key=lambda x: -x["score"])


class WASB:
    def __init__(self, root, device="cuda"):
        import torch
        import yaml
        self.root, self.device = Path(root), device
        files = ["src/models/hrnet.py", "src/configs/model/wasb.yaml", "basketball.pth"]
        self.provenance = provenance(self.root, "WASB-SBDT", files)
        arch = source_module(self.root / files[0], "svc_wasb_hrnet")
        cfg = yaml.safe_load((self.root / files[1]).read_text(encoding="utf8"))
        self.model = arch.HRNet(_Config(cfg))
        state = torch.load(self.root / files[2], map_location="cpu", weights_only=True)
        self.model.load_state_dict(state["model_state_dict"], strict=True)
        self.model.to(device).eval()

    def predict(self, frames):
        """Three consecutive RGB frames -> three detections, in chronological order.

        Caller owns clip boundaries and timestamps; never carry context across cuts.
        Empty lists represent no observation (not a synthetic interpolated ball).
        """
        import cv2
        import torch
        if len(frames) != 3 or len({f.shape for f in frames}) != 1:
            raise ValueError("WASB requires exactly three equal-sized consecutive frames")
        height, width = frames[0].shape[:2]
        affine = wasb_affine(width, height)
        inverse = cv2.invertAffineTransform(affine)
        tensor = torch.cat([normalized_tensor(cv2.warpAffine(f, affine, (512, 288)), self.device)
                            for f in frames], dim=0)[None]
        with torch.inference_mode():
            heatmaps = self.model(tensor)[0].sigmoid()[0].cpu().numpy()
        return [decode_ball_heatmap(hm, inverse, width, height) for hm in heatmaps]


class BallDetector:
    """Same RF-DETR checkpoint, threshold and input policy for full and sliced views."""
    def __init__(self, checkpoint, threshold=.3, short_side=768):
        from rfdetr import from_checkpoint
        if not 0 < threshold < 1 or short_side < 32:
            raise ValueError("Invalid detector threshold or input size")
        self.threshold, self.short_side = threshold, short_side
        self.model = from_checkpoint(str(checkpoint))
        names = self.model.class_names
        entries = names.items() if isinstance(names, dict) else enumerate(names)
        self.ball_ids = {int(k) for k, v in entries if str(v).lower().strip() == "ball"}
        if not self.ball_ids:
            raise ValueError("Checkpoint has no explicitly named ball class")
        self.provenance = {"checkpoint_sha256": sha256(checkpoint), "threshold": threshold,
                           "short_side": short_side, "ball_class_ids": sorted(self.ball_ids)}

    def predict(self, rgb):
        h, w = rgb.shape[:2]
        scale = min(1., self.short_side / min(h, w), 1333 / max(h, w))
        shape = (max(32, int(h * scale) // 32 * 32), max(32, int(w * scale) // 32 * 32))
        result = self.model.predict(rgb, threshold=self.threshold, shape=shape,
                                    include_source_image=False)
        return [{"box": box.tolist(), "xy": [(float(box[0])+float(box[2]))/2,
                                                (float(box[1])+float(box[3]))/2],
                 "score": float(score), "score_kind": "detector_confidence"}
                for box, score, cls in zip(result.xyxy, result.confidence, result.class_id)
                if int(cls) in self.ball_ids]


def sahi_model(detector):
    """Build an official SAHI DetectionModel adapter without any cloud inference."""
    from sahi.models.base import DetectionModel
    from sahi.prediction import ObjectPrediction

    class LocalBallModel(DetectionModel):
        def perform_inference(self, image):
            self._original_predictions = detector.predict(image)

        def _create_object_prediction_list_from_original_predictions(
            self, shift_amount_list=None, full_shape_list=None
        ):
            shift = shift_amount_list or [0, 0]
            full = full_shape_list
            if isinstance(shift[0], (list, tuple)):
                shift = shift[0]
            if full and isinstance(full[0], (list, tuple)):
                full = full[0]
            self._object_prediction_list_per_image = [[
                ObjectPrediction(bbox=p["box"], category_id=0, category_name="ball",
                                 score=p["score"], shift_amount=shift, full_shape=full)
                for p in self._original_predictions]]

    return LocalBallModel(load_at_init=False, confidence_threshold=detector.threshold,
                          device="cpu")  # device is managed by the already loaded RF-DETR


def sliced_ball_prediction(rgb, adapter, size=640, overlap=.2):
    from sahi.predict import get_sliced_prediction
    if size < 32 or not 0 <= overlap < 1:
        raise ValueError("Invalid slice size or overlap")
    result = get_sliced_prediction(
        rgb, adapter, slice_height=size, slice_width=size,
        overlap_height_ratio=overlap, overlap_width_ratio=overlap,
        perform_standard_pred=True, postprocess_type="NMS",
        postprocess_match_metric="IOU", postprocess_match_threshold=.5, verbose=0)
    output = []
    for prediction in result.object_prediction_list:
        box = prediction.bbox.to_xyxy()
        output.append({"box": list(box), "xy": [(box[0]+box[2])/2, (box[1]+box[3])/2],
                       "score": float(prediction.score.value), "score_kind": "detector_confidence"})
    return sorted(output, key=lambda p: -p["score"])


def kalicalib_grid():
    """91 floor points in upstream centimetres; elevated rim channels excluded."""
    import numpy as np
    return np.array([[i * 2800 / 12, 1500 - (175*j + 15*j*(j-1))]
                     for j in range(7) for i in range(13)], dtype=np.float32)


def fit_court_proposal(world, image, width, height):
    """Fit measured correspondences only. Never return upstream mean-camera fallback."""
    import cv2
    import numpy as np
    result = {"H": None, "trusted": False, "status": "rejected", "points": len(world)}
    world, image = np.asarray(world, np.float32), np.asarray(image, np.float32)
    if len(world) < 6 or not np.isfinite(world).all() or not np.isfinite(image).all():
        return {**result, "reason": "fewer_than_six_finite_correspondences"}
    if np.linalg.matrix_rank(world - world.mean(0)) < 2:
        return {**result, "reason": "collinear_correspondences"}
    cv2.setRNGSeed(0)
    H, mask = cv2.findHomography(world, image, cv2.RANSAC, 35 * width / 960, maxIters=2000)
    if H is None or mask is None or not np.isfinite(H).all():
        return {**result, "reason": "homography_failed"}
    inliers = mask.ravel().astype(bool)
    if inliers.sum() < 6 or inliers.mean() < .5:
        return {**result, "reason": "insufficient_inliers", "inliers": int(inliers.sum())}
    # Select display orientation from projected geometry, without reference labels.
    corners = np.array([[0, 0], [2800, 0], [2800, 1500], [0, 1500]], np.float32)
    projected = cv2.perspectiveTransform(corners[None], H)[0]
    denom = (H @ np.c_[corners, np.ones(4)].T)[2]
    if (not np.isfinite(projected).all() or np.any(denom == 0) or
            not (np.all(denom > 0) or np.all(denom < 0)) or
            not cv2.isContourConvex(projected.astype(np.float32))):
        return {**result, "reason": "invalid_court_polygon"}
    area = abs(cv2.contourArea(projected))
    if not .02 * width * height < area < 20 * width * height:
        return {**result, "reason": "implausible_court_area"}
    flip_x = projected[[0, 3], 0].mean() > projected[[1, 2], 0].mean()
    flip_y = projected[[0, 1], 1].mean() < projected[[2, 3], 1].mean()
    transform = np.array([[-100 if flip_x else 100, 0, 2800 if flip_x else 0],
                          [0, -100 if flip_y else 100, 1500 if flip_y else 0], [0, 0, 1]])
    mapped = cv2.perspectiveTransform(world[None], H)[0]
    errors = np.linalg.norm(mapped - image, axis=1)
    H = H @ transform
    return {**result, "H": (H / H[2, 2]).tolist(), "status": "candidate",
            "reason": "requires_independent_landmark_review", "inliers": int(inliers.sum()),
            "inlier_median_px": float(np.median(errors[inliers])),
            "coordinate_system": "FIBA metres: x left-to-right, y near-to-far",
            "axis_flips": [bool(flip_x), bool(flip_y)]}


class KaliCalib:
    def __init__(self, root, device="cuda", checkpoint="models/model_test.pth"):
        import torch
        self.root, self.device = Path(root), device
        files = ["kalicalib/model_resnet.py", checkpoint]
        self.provenance = provenance(self.root, "KaliCalib", files)
        arch = source_module(self.root / files[0], "svc_kalicalib_model")
        self.model = arch.makeModel()
        self.model.load_state_dict(torch.load(self.root / checkpoint, map_location="cpu", weights_only=True))
        self.model.to(device).eval()

    def predict(self, rgb):
        import cv2
        import numpy as np
        import torch
        height, width = rgb.shape[:2]
        tensor = normalized_tensor(cv2.resize(rgb, (960, 540)), self.device)[None]
        with torch.inference_mode():
            heatmaps = self.model(tensor)[0].cpu().numpy()
        winners = heatmaps.argmax(axis=0)
        world, image = [], []
        for i, point in enumerate(kalicalib_grid()):
            # Upstream uses the centroid of pixels for which this channel wins.
            ys, xs = np.where(winners == i)
            if len(xs):
                world.append(point)
                image.append([float(xs.mean() * 4 * width / 960), float(ys.mean() * 4 * height / 540)])
        return fit_court_proposal(world, image, width, height)
