"""Reproducible optional ball / court backend comparison on labelled source frames."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import statistics
import time
from pathlib import Path

from .perception_backends import sha256


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")
    temp.replace(path)


def prepare(args):
    """Decode native frames and write an explicit timestamp / geometry manifest."""
    import cv2
    video, root = Path(args.video).resolve(), Path(args.output)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Cannot open source video")
    fps, count = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rows, seen = [], set()
    root.mkdir(parents=True, exist_ok=True)
    try:
        for t in args.times:
            if not math.isfinite(t) or t < 0 or not fps > 0:
                raise ValueError("Finite, nonnegative times and a positive source fps required")
            index = round(t * fps)
            if index >= count or index in seen:
                raise ValueError("Sample is outside the video or duplicates a native frame")
            seen.add(index)
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"Cannot decode frame {index}")
            identity = f"frame-{index:09d}"
            filename = identity + ".png"
            if not cv2.imwrite(str(root / filename), frame):
                raise ValueError("Cannot write source frame")
            rows.append({"id": identity, "frame_index": index, "t": index/fps,
                         "image": filename, "width": frame.shape[1], "height": frame.shape[0]})
    finally:
        cap.release()
    write_json(root / "samples.json", {"video": str(video), "fps": fps, "samples": rows})
    print(root / "samples.json")


def validate_samples(manifest):
    ids = set()
    fps = manifest["fps"]
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("Manifest requires a positive source fps")
    for row in manifest["samples"]:
        if row["id"] in ids or not row["id"] or Path(row["image"]).name != row["image"]:
            raise ValueError("Sample IDs must be unique and image paths must be local filenames")
        ids.add(row["id"])
        if (not math.isfinite(row["t"]) or row["t"] < 0 or
                not isinstance(row["frame_index"], int) or
                abs(row["frame_index"] / fps - row["t"]) > 1e-6):
            raise ValueError("Sample timestamp and native frame index disagree")
    if not ids:
        raise ValueError("No samples")


def evaluate_ball(predictions, labels, radius=12):
    """Top-1 per source frame; wrong location counts as FP + FN, unclear excluded.

    Also count extra candidates: high top-1 recall must not hide slice clutter.
    Scores from different backends are never mixed or interpreted as accuracy.
    """
    if not labels.get("review_complete") or radius <= 0:
        raise ValueError("Complete independent labels and positive radius required")
    by_id = {p["id"]: p for p in predictions}
    if len(by_id) != len(predictions):
        raise ValueError("Duplicate prediction IDs")
    seen, errors = set(), []
    counts = dict(tp=0, fp=0, fn=0, tn=0, visible=0, occluded=0, unclear=0,
                  extra_candidates=0, any_candidate_hits=0)
    for label in labels["labels"]:
        identity, state = label["id"], label["state"]
        if identity in seen or identity not in by_id or state not in ("visible", "occluded", "unclear"):
            raise ValueError("Invalid, duplicate or unmatched label")
        seen.add(identity)
        counts[state] += 1
        if state == "unclear":
            continue
        candidates = sorted(by_id[identity]["ball"], key=lambda p: -p["score"])
        counts["extra_candidates"] += max(0, len(candidates)-1)
        if state == "occluded":
            counts["fp" if candidates else "tn"] += 1
            continue
        xy = label["xy"]
        if xy is None or len(xy) != 2 or not all(math.isfinite(v) for v in xy):
            raise ValueError("Visible labels require a finite centre")
        distances = [math.dist(p["xy"], xy) for p in candidates]
        counts["any_candidate_hits"] += int(any(d <= radius for d in distances))
        if not distances:
            counts["fn"] += 1
        elif distances[0] <= radius:
            counts["tp"] += 1
            errors.append(distances[0])
        else:
            counts["fp"] += 1
            counts["fn"] += 1
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    if seen != set(by_id):
        raise ValueError("Review marked complete but some prediction frames have no label")
    return {**counts, "radius_px": radius, "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "matched_median_error_px": statistics.median(errors) if errors else None,
            "evaluated_frames": len(seen)-counts["unclear"],
            "unlabelled_predictions": len(by_id)-len(seen)}


def evaluate_court(predictions, labels):
    import cv2
    import numpy as np
    by_id = {p["id"]: p for p in predictions}
    rows, errors = [], []
    for row in labels["labels"]:
        proposal = by_id[row["id"]]["court"]
        H = proposal.get("H")
        if H is None:
            rows.append({"id": row["id"], "points": len(row["points"]), "status": "rejected"})
            continue
        src = np.array([p["world_m"] for p in row["points"]], np.float32)
        dst = np.array([p["image_xy"] for p in row["points"]], np.float32)
        mapped = cv2.perspectiveTransform(src[None], np.array(H))[0]
        err = np.linalg.norm(mapped-dst, axis=1).tolist()
        errors.extend(err)
        rows.append({"id": row["id"], "points": len(err), "status": "candidate",
                     "median_error_px": statistics.median(err), "max_error_px": max(err)})
    return {"frames": rows, "points_evaluated": len(errors),
            "median_error_px": statistics.median(errors) if errors else None,
            "max_error_px": max(errors) if errors else None, "trusted": False}


def infer(args):
    import cv2
    import numpy as np
    import torch
    from .perception_backends import WASB, KaliCalib, BallDetector, sahi_model, sliced_ball_prediction
    manifest = read_json(args.samples)
    validate_samples(manifest)
    root = Path(args.samples).parent
    video = Path(manifest["video"])
    if args.temporal_step < 1:
        raise ValueError("Temporal step must be positive")
    torch.set_num_threads(4)
    cv2.setNumThreads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.backend == "wasb":
        model = WASB(Path(args.upstream) / "WASB-SBDT", device)
    elif args.backend == "kalicalib":
        model = KaliCalib(Path(args.upstream) / "KaliCalib", device, args.kali_checkpoint)
    else:
        model = BallDetector(args.checkpoint, args.threshold)
    adapter = sahi_model(model) if args.backend == "sahi" else None
    image_hashes = {r["id"]: sha256(root/r["image"]) for r in manifest["samples"]}
    provenance = {"backend": args.backend, "model": model.provenance,
                  "video_sha256": sha256(video), "samples_sha256": sha256(args.samples),
                  "image_sha256": image_hashes, "device": device,
                  "temporal_step": args.temporal_step, "slice_size": args.slice_size,
                  "slice_overlap": .2, "slice_merge": "NMS/IOU/0.5", "schema": 1,
                  "code_sha256": sha256(__file__),
                  "adapter_sha256": sha256(Path(__file__).with_name("perception_backends.py")),
                  "packages": {p: importlib.metadata.version(p) for p in ["torch", "rfdetr", "numpy"]}}
    if args.backend == "sahi":
        import sahi
        provenance["packages"]["sahi"] = importlib.metadata.version("sahi")
        package_root = Path(sahi.__file__).parent
        provenance["sahi_source_sha256"] = {p: sha256(package_root/p) for p in
                                            ("predict.py", "slicing.py", "postprocess/combine.py")}
    dest = Path(args.output) / f"{args.backend}.json"
    if dest.exists() and not args.force and read_json(dest).get("provenance") == provenance:
        print(f"Current: {dest}")
        return
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened() or abs(cap.get(cv2.CAP_PROP_FPS) - manifest["fps"]) > .001:
        raise ValueError("Cannot open source or manifest fps differs from source")
    duration_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rows, timings = [], []
    warmed = False
    try:
        for row in manifest["samples"]:
            bgr = cv2.imread(str(root/row["image"]))
            if bgr is None or bgr.shape[:2] != (row["height"], row["width"]):
                raise ValueError(f"Invalid source image: {row['id']}")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            if args.backend == "wasb":
                indices = [row["frame_index"] + k * args.temporal_step for k in (-1, 0, 1)]
                if min(indices) < 0 or max(indices) >= duration_frames:
                    raise ValueError("WASB context would cross the video boundary")
                frames = []
                for index in indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                    ok, frame = cap.read()
                    if not ok:
                        raise ValueError("Cannot decode temporal context")
                    frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if not np.array_equal(rgb, frames[1]):
                    raise ValueError("Sample does not match the claimed source frame")
                predict = lambda: model.predict(frames)[1]
            elif args.backend == "sahi":
                predict = lambda: sliced_ball_prediction(rgb, adapter, args.slice_size)
            else:
                predict = lambda: model.predict(rgb)
            if not warmed:
                predict()
                warmed = True
            if device == "cuda":
                torch.cuda.synchronize()
            start = time.perf_counter()
            value = predict()
            if device == "cuda":
                torch.cuda.synchronize()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            rows.append({"id": row["id"], "t": row["t"], "frame_index": row["frame_index"],
                         "court" if args.backend == "kalicalib" else "ball": value,
                         "seconds": elapsed})
    finally:
        cap.release()
    result = {"provenance": provenance, "trusted": False, "predictions": rows,
              "runtime": {"frames": len(rows), "median_seconds": statistics.median(timings),
                          "total_seconds": sum(timings), "warmup_excluded": True,
                          "decode_and_model_load_excluded": True}}
    write_json(dest, result)
    print(f"Wrote {dest}: {len(rows)} frames; median {statistics.median(timings):.3f}s")


def evaluate(args):
    root = Path(args.output)
    labels = read_json(args.labels)
    report = {"schema": 1, "labels_sha256": sha256(args.labels), "ball": {}, "court": None}
    for backend in ("full", "sahi", "wasb"):
        path = root / f"{backend}.json"
        if path.exists():
            prediction = read_json(path)
            if labels.get("samples_sha256") != prediction["provenance"]["samples_sha256"]:
                raise ValueError("Labels do not belong to this source-frame manifest")
            report["ball"][backend] = {"prediction_sha256": sha256(path),
                "metrics": evaluate_ball(prediction["predictions"], labels),
                "sensitivity": {str(r): evaluate_ball(prediction["predictions"], labels, r)
                                for r in (8, 20)}, "runtime": prediction["runtime"]}
    if args.court_labels and (root / "kalicalib.json").exists():
        path = root / "kalicalib.json"
        report["court"] = {**evaluate_court(read_json(path)["predictions"], read_json(args.court_labels)),
                           "prediction_sha256": sha256(path), "labels_sha256": sha256(args.court_labels)}
    write_json(root / "evaluation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare", help="extract native source frames for independent annotation")
    prep.add_argument("--video", required=True)
    prep.add_argument("--output", required=True)
    prep.add_argument("--times", nargs="+", type=float, required=True, help="source times in seconds (CFR video)")
    run = sub.add_parser("infer", help="run an optional local backend on a source-frame manifest")
    run.add_argument("--samples", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--backend", choices=["wasb", "full", "sahi", "kalicalib"], required=True)
    run.add_argument("--upstream", help="parent of pinned WASB-SBDT and KaliCalib checkouts")
    run.add_argument("--checkpoint", help="local basketball RF-DETR checkpoint for full / sahi")
    run.add_argument("--threshold", type=float, default=.3)
    run.add_argument("--kali-checkpoint", default="models/model_test.pth")
    run.add_argument("--slice-size", type=int, default=640)
    run.add_argument("--temporal-step", type=int, default=1)
    run.add_argument("--force", action="store_true")
    score = sub.add_parser("evaluate", help="score predictions against independent manual labels")
    score.add_argument("--output", required=True)
    score.add_argument("--labels", required=True)
    score.add_argument("--court-labels")
    render = sub.add_parser("render", help="build the local comparison HTML and optional four-way video")
    render.add_argument("--samples", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--labels", required=True)
    render.add_argument("--court-labels")
    render.add_argument("--motion-samples")
    render.add_argument("--motion-output")
    args = parser.parse_args(argv)
    if args.action == "prepare":
        prepare(args)
    elif args.action == "infer":
        if args.backend in ("wasb", "kalicalib") and not args.upstream:
            parser.error("--upstream is required for WASB and KaliCalib")
        if args.backend in ("full", "sahi") and not args.checkpoint:
            parser.error("--checkpoint is required for full-frame and SAHI inference")
        infer(args)
    elif args.action == "evaluate":
        evaluate(args)
    else:
        from .perception_lab_page import build_page, render_video
        if args.motion_samples:
            if not args.motion_output:
                parser.error("--motion-output is required with --motion-samples")
            render_video(args.motion_samples, args.motion_output, Path(args.output)/"comparison.mp4")
        print(build_page(args.samples, args.output, args.labels, args.court_labels))


if __name__ == "__main__":
    main()
