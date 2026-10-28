# WASB, SAHI and KaliCalib perception lab

Optional local adapters for basketball ball detection and court registration, with independent evaluation
and visual comparison. These are implemented experiments, not default replacements for the existing pipeline.
They do not modify official scores, reviewed trips, player identities or `camera.npz`.

[Feature catalog](features.md) · [OpenHoopVision](perception.md) · [Basketball workflow](playbook.md)

## Integrated capabilities

| Backend | Implementation | Output |
|---|---|---|
| Full-frame reference | Existing local basketball RF-DETR checkpoint | Ball boxes, source-pixel centres and detector confidence |
| SAHI | Official `get_sliced_prediction`, local `DetectionModel` adapter, overlapping crops plus full-image pass, coordinate restoration and NMS | Ball candidates, including extra detections for false-positive review |
| WASB | Official HRNet and basketball checkpoint; upstream affine/ImageNet normalization; three chronological frames; sigmoid heatmaps and weighted connected-component centres | Candidates scored by heatmap mass; empty list means no observation |
| KaliCalib | Official network; 91 floor-grid channels excluding elevated rims; RANSAC; centimetres-to-metres conversion and display orientation | Untrusted FIBA homography candidates or a rejection reason |

KaliCalib requires six or more inliers, at least 50% inliers, nondegenerate geometry, consistent projective
denominators and a plausible convex court polygon. These gates are necessary, not proof of correctness.
The upstream mean-camera fallback and 3D camera fitting are not used. External source stays in separate
checkouts with its original license; no model weights are shipped here.

## Measured diagnostic, not a leaderboard

One private amateur game, 45 fixed 1280×720 frames across three windows. An independent reviewer labelled
the target-court ball from original frames and nearby temporal context before viewing predictions:
35 visible, six occluded and four unclear. Unclear frames were excluded. Estimated annotation error: 3–5 px.
Model thresholds were not tuned against these labels.

At a fixed **12 px** centre tolerance, each method chooses its own highest-scoring candidate:

| Method | Correct / visible | Precision | Recall | False-positive frames | Extra candidates | Median inference |
|---|---:|---:|---:|---:|---:|---:|
| RF-DETR full frame | 20/35 | 64.5% | 57.1% | 11 | 8 | 52 ms |
| SAHI + same RF-DETR | 22/35 | 62.9% | 62.9% | 13 | 27 | 221 ms |
| WASB basketball | 1/35 | 1/1 predictions | 2.9% | 0 | 0 | 59 ms |

A wrong location counts as both FP and FN. Predictions on occluded frames count as FP. Extra candidates
are separate; the evaluator never picks the ground-truth-nearest prediction to inflate top-1 recall.
It also reports 8 px and 20 px sensitivity. SAHI found two more top-ranked balls, with more false positives
and about 4.2× inference cost. WASB's one correct prediction does **not** establish useful precision or coverage.
Sparse localization does not measure continuous tracking, event recognition or identity accuracy.

A different reviewer independently labelled 21 FIBA floor intersections in three frames (about 4 px estimated
annotation uncertainty; physical court dimensions were not surveyed):

- `model_test.pth`: 0/45 proposals passed geometry; no held-out error is reported.
- Exploratory `model_challenge.pth`: 24/45 passed geometry, 19 lacked sufficient inliers, two had invalid court
  polygons. Two labelled frames had proposals: 15 independent points, median error **36.1 px**, maximum
  **103.3 px**. The third labelled frame was rejected.
- Neither checkpoint is approved for automatic calibration replacement. Acceptance rate is not accuracy.

Timing: RTX 3070, FP32, warmed models, synchronized CUDA; loading and decoding excluded. GPU sharing and
small sample size limit comparisons. Both RF-DETR modes used threshold 0.3 and the same 768 short-side policy,
capped at native scale. SAHI: 640 px tiles, 20% overlap, IOU 0.5 NMS. WASB: heatmap threshold 0.5, temporal stride
two on a 60 fps source. All settings and source/checkpoint hashes are recorded in output JSON.

## Setup and sources

Use a current clone containing `hoop-tape-miner perception-lab --help`; older pinned releases lack this command.
The basketball environment supplies torch, RF-DETR, OpenCV and NumPy. SAHI is optional:

```bash
uv sync --extra perception-lab
uv run hoop-tape-miner perception-lab --help
```

For CPU-only setup see [CONTRIBUTING.md](../CONTRIBUTING.md). No package, source, model or dataset is downloaded
by `perception-lab` itself. Keep these upstream checkouts under an ignored folder such as `workspace/tools/vision/`:

| Source | Tested revision | License / checkpoint |
|---|---|---|
| [WASB-SBDT](https://github.com/nttcom/WASB-SBDT) | `923462cacdeb3353b84ddebdedb3f4b7a8553b0f` | MIT; basketball WASB weights in official [MODEL_ZOO.md](https://github.com/nttcom/WASB-SBDT/blob/923462cacdeb3353b84ddebdedb3f4b7a8553b0f/MODEL_ZOO.md) |
| [SAHI](https://github.com/obss/sahi) | `b5a153ee7bcb1fd84a7b868575ff14131e7423ce` / 0.12.8 | MIT; reuses the local detector weights |
| [KaliCalib](https://github.com/CEA-LIST/KaliCalib) | `3b3f52b59e8e38e155ba7e9c681281d44748c173` | CeCILL 2.1; upstream `models/model_test.pth` and `models/model_challenge.pth` |

For exact SAHI source reproduction install its pinned checkout instead of the package-index build.
Place the WASB basketball checkpoint at `WASB-SBDT/basketball.pth`; keep KaliCalib weights in their upstream
locations. Source adapters accept a pinned Git checkout, or an archive with `source-manifest.json` containing
that commit. Actual executed source/config/weight hashes also distinguish local changes. The project MIT
license does not relicense external source or weights.

## Prepare, label, infer, evaluate

Use constant-frame-rate video. Do not reuse a manifest for a trimmed/resized/VFR copy. Pick windows before
viewing predictions; keep temporal context away from camera cuts.

```bash
uv run hoop-tape-miner perception-lab prepare --video game.mp4 --output workspace/lab/labels --times 10 11 12
```

`samples.json` has source `video`, `fps`, and `samples: [{id, frame_index, t, image, width, height}]`.
Images are lossless source-size PNGs. An independent reviewer writes `labels.json`, labelling every frame:

```json
{
  "schema": 1,
  "review_complete": true,
  "samples_sha256": "SHA256 of samples.json",
  "method": "manual source-frame review before predictions",
  "labels": [
    {"id": "frame-000000600", "state": "visible", "xy": [320, 240], "note": "Target-court ball"},
    {"id": "frame-000000660", "state": "occluded", "xy": null, "note": "Hidden by the handler"},
    {"id": "frame-000000720", "state": "unclear", "xy": null, "note": "Cannot distinguish the ball"}
  ]
}
```

Do not equate an unlocated ball with definite occlusion. Exclude neighbouring-court and stationary bench balls.
Example commands (replace model paths with your own):

```bash
uv run hoop-tape-miner perception-lab infer --backend full --samples workspace/lab/labels/samples.json --output workspace/lab/results --checkpoint workspace/models/rf-detr-basketball.pth
uv run hoop-tape-miner perception-lab infer --backend sahi --samples workspace/lab/labels/samples.json --output workspace/lab/results --checkpoint workspace/models/rf-detr-basketball.pth
uv run hoop-tape-miner perception-lab infer --backend wasb --samples workspace/lab/labels/samples.json --output workspace/lab/results --upstream workspace/tools/vision
uv run hoop-tape-miner perception-lab infer --backend kalicalib --samples workspace/lab/labels/samples.json --output workspace/lab/results --upstream workspace/tools/vision
uv run hoop-tape-miner perception-lab evaluate --output workspace/lab/results --labels workspace/lab/labels/labels.json
uv run hoop-tape-miner perception-lab render --samples workspace/lab/labels/samples.json --output workspace/lab/results --labels workspace/lab/labels/labels.json
```

WASB defaults to adjacent native frames; `--temporal-step 2` reproduces the diagnostic above. Its adapter
returns all three heatmaps; sparse inference retains the centre-frame observation once per sample. It does
not run upstream's online trajectory tracker or fabricate interpolated observations. Padding detections are discarded.

For the other KaliCalib checkpoint, use `--kali-checkpoint models/model_challenge.pth` and a separate output
directory. Pass `--court-labels court-labels.json` to `evaluate` and `render` for independent court checks:
`{labels: [{id, points: [{name, world_m: [x,y], image_xy: [u,v]}]}]}`. Court metres: x=0 left baseline, x=28 right,
y=0 near sideline, y=15 far. Never fit and validate against the same manual points.

## Comparison artifacts

`render` writes interactive HTML, source images and raw JSON links, checking label/prediction/frame hashes.
Failed models remain visible. To add a four-way MP4, prepare a second manifest of dense regular frames,
grouped by source window, ordered within each window, with `playback_fps` matching the sample rate (default 12).
Infer all four backends into another directory, then add `--motion-samples <manifest>` and
`--motion-output <prediction-directory>` to `render`. Circles come from each current frame; no audio is added.
The sparse evaluation says nothing about the unlabelled reel frames. HTTP Range support is needed for seeking.

Results under `<game>/perception-lab/` add a team-report link on the next HTML build. Full-length coaching films
remain separate. Labels, footage, rosters, model weights and actual game data stay in the ignored workspace;
never attach them to public issues or PRs.

## References

- [WASB official paper/code](https://github.com/nttcom/WASB-SBDT): temporal heatmap ball detection.
- [SAHI prediction documentation](https://obss.github.io/sahi/predict/): sliced inference and postprocessing.
- [KaliCalib paper](https://arxiv.org/abs/2209.07795) and [code](https://github.com/CEA-LIST/KaliCalib): learned court registration.
