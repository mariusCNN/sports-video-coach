# Optional basketball perception

For ball-localization and court-model experiments, see the separate
[WASB / SAHI / KaliCalib perception lab](perception-lab.md). Its candidates never replace reviewed facts.

OpenHoopVision can supply visual shot, pass, dribble, rebound and possession-change
candidates alongside the existing basketball analysis. Its detector, RTMPose pose,
SVTRv2 jersey OCR, OSNet identity association and learned court mapper run in an
external process. Existing tracking caches, reviewed trips and official statistics
remain the sources for the established coaching report.

## Source and environment

Use [OpenHoopVision](https://github.com/feifeifei85/OpenHoopVision) at commit
`ec969037b2c02b983a77b260c50cb9eb36fe9fc1`. The adapter checks this commit and requires
real checkpoint payloads, not Git LFS pointers. Prepare its environment according
to its README. `--python` selects a separate backend interpreter; omit it to use an
already compatible environment. The command never installs packages or downloads
weights automatically. Do not apply the upstream CUDA lock file to an existing
environment without checking compatibility.

The original upstream code and project models are declared Apache-2.0 in its
README; third-party components retain their own terms. This package does not
vendor or redistribute upstream source or weights. Keep the checkout, weights,
videos and JSONL under private, ignored storage.

## Run and import

```bash
uv run hoop-tape-miner perception analyze --game GAME/game.json --checkout OPENHOOPVISION
uv run hoop-tape-miner perception import --game GAME/game.json --dark-team us
uv run hoop-tape-miner perception media --game GAME/game.json --limit 12
uv run hoop-tape-miner html GAME
```

Verify which jerseys upstream calls dark/light before supplying `--dark-team`.
Without that mapping, teams stay unknown. Imports also apply the game's rosters
to identity-number candidates; raw observations remain available for diagnosis.

- `analyze --start 120 --end 240` limits processing to an original-video interval.
- The source average frame rate and a 768-pixel short-side limit are the defaults.
  Input is normalized to constant frame rate for the upstream frame-index clock. Optional
  `--fps`, `--short-side` and `--batch` need validation on the actual footage.
- `import --tracks PATH [PATH ...] --offset 120` imports existing
  `basketball_frame_v2` JSONL. A sibling `run.json` supplies each clip's true offset.
  Compact `events.json` is rejected because it drops evidence and non-shot events.
- Bare external streams remain `external_unverified`: they supply candidates but
  cannot establish exhaustive evaluation coverage or aligned overlays/projections.
  Verified completion requires the pinned commit, a matching source-video binding,
  a final JSONL digest and a complete recorded frame span. Temporary paths are rejected.
- Analysis uses atomic completion and a settings/video signature to reuse a
  completed result. Logs, configuration, runtime and checkpoint hashes are kept
  next to the completed JSONL. Tracked source edits fail the pinned-revision check;
  new completion records also hash the JSONL. A failed run is not imported automatically.
- Overlapping source windows are rejected rather than counted twice.
- Frame numbers must be consecutive from 1, with consistent timestamps and event
  seconds/frame fields. A sparse stream cannot claim continuous analysis coverage.

To enable analysis/import in `run`, add this optional block to `game.json`:

```json
{
  "perception": {
    "enabled": true,
    "checkout": "C:/tools/OpenHoopVision",
    "dark_team": "us",
    "batch": 2
  }
}
```

Without the block, analysis, import and media steps are skipped. `media_limit`
controls the number of illustrated events (default 12). New coach-sheet manifests include
`perception_candidates` for the corresponding possession interval. Existing
reviews do not become confirmed merely because a model agrees with them.

## Evidence and review

`run/perception/evidence.json` contains:

- Original-video times, raw categorical evidence, source line references and hashes.
- All supported event kinds, including raw relationships between passers/receivers.
- Roster-gated number observations and global/local identity associations, namespaced per source.
  Repeated per-frame number values are not independent OCR reads or confirmations.
- Observed versus interpolated ball coverage, pose and court-observation coverage.
- Optional candidate coordinates projected through the existing FIBA calibration.
- One-to-one time matches and conflicts against previously reviewed shots. These
  are diagnostic comparisons, not a ground-truth accuracy score.

All imported events start as `pending`. For an event reviewed against the film,
write `run/perception/reviews.json`, keyed by the event's stable ID:

```json
{
  "ohv-SOURCEHASH-00001": {
    "status": "unclear",
    "note": "The ball disappears behind the rim; the outcome is not visible.",
    "note_zh": "球在篮筐后被遮挡，结果看不清。"
  }
}
```

Statuses are `confirmed`, `rejected`, or `unclear`; every review needs an evidence
note. Re-import to apply reviews. IDs include the source hash, offset and team mapping, so changed inference
cannot silently inherit old reviews. Unknown review IDs fail validation.

NBA locations and the upstream two-point fallback never become confirmed FIBA
points. `points` stays null. Our calibrated positions are also explicitly marked
untrusted candidates: a wrong inferred player still gives the wrong shot location.
Coordinates are used only when the adapter can verify original-frame alignment;
an external crop or resize has no implicit identity transform.
The adapter does not manufacture assists, blocks or fouls.

## Independent local validation

Following the separate detection/association assessment used by
[SportsMOT](https://github.com/MCG-NJU/SportsMOT) and
[SoccerNet Game State Reconstruction](https://github.com/SoccerNet/sn-gamestate),
evaluate attempts, outcomes and team attribution separately. Official score-feed
timestamps and the existing coach review are not independent release-time labels.

Optionally write `run/perception/labels.json` before inspecting predictions:

```json
{
  "schema": "svc_perception_labels_v1",
  "source": "Independent review of original frames; describe the sampling here",
  "windows": [{
    "start": 120,
    "end": 135,
    "split": "validation",
    "shots": [{"release": [126.4, 126.6], "team": "us", "result": "missed"}]
  }]
}
```

Each window must be fully reviewed and contain **every visible attempt**, including
none when there are no shots. Exclude ambiguous/unreviewed intervals. `team` and
`result` may be null when the attempt is clear but attribution/outcome is not.
Keep any footage used to choose settings marked `development`, not `validation`.

Import evaluates only windows fully covered by completed analysis. It uses maximum
one-to-one temporal matching, then minimum release-time error, with a one-second
tolerance outside the annotated release interval. Extra candidates and missed
labels stay separate; outcome and team accuracy use matched attempts only.
False makes and unresolved outcomes/teams are retained in the evidence JSON.
The HTML displays counts and denominators by window. Small samples establish a
local diagnostic, not full-game accuracy or cross-gym generalization.

## Deliverables and validation

`perception media` writes selected original clips and an overlay validation reel
under `GAME/perception/`. The reel shows player/pose/ball observations with explicit
candidate labels, not an official scoreboard. The normal bilingual HTML appends
event cards, review notes and measured coverage. Evidence changes invalidate the
page through the basketball page hooks.
The import cache also follows completed source files, mapping, rosters, reviews,
labels and calibration, so an earlier short pilot cannot stand in for a later full run.

No global identity candidates are attributed to a personal player page. Share-mode
HTML omits external perception videos. Media caching checks every referenced clip;
overlays use timestamp-normalized decoding so lower-rate or variable-rate sources
do not drift when the validation reel is rendered at 24 fps.
The renderer rechecks source digests, limits the time distance to a displayed
observation, and labels player/pose colors as model-predicted uniform groups.

Compare settings on the same labelled clips before choosing a faster configuration.
Measure shot precision/recall, false makes, attribution errors, unknown outcomes,
OCR precision/coverage and runtime separately. A detector mAP or a count of number
observations does not establish full-game event accuracy or minutes played.
