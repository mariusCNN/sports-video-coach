# Movement lab: running pattern, force pattern, layup approach, fuel and recovery

## Intent

Many adult rec players can run long distances but feel "heavy" when they sprint full court. A common cause: they
run like distance runners (upright, short steps, calf-driven), while basketball is mostly sprints, which need
forward lean, full hip-knee-ankle extension and long, fast steps. The same pattern can hurt layup approaches and
the full-court speed dribble.

A player wants three things:

1. **Diagnosis**: an expert read of their running and force pattern, how it should look for basketball (sprints,
   transition, speed dribble, layup approach and take-off), and how to fix and train it.
2. **Fuel and recovery**: how to eat and recover around this training.
3. **Repeatable pipeline**: a knowledge base and pipeline in the repo, so new videos update the analysis by running
   the pipeline again.

Deliverables per session: an HTML page and an explained video per language, built from the footage that exists,
with every gap marked as such.

## Goals

- **Knowledge base** (repo, `prompts/`), sourced like `prompts/skill_kb.md` (Symptom / Why it happens / What to
  check on film / Cue zh+en / Drill / Target / Source, "(our rule)" labels, trial values marked):
  - `movement_kb.md`: running and force pattern for basketball. Starting entry list (builder may merge or split):
    acceleration posture, braking touchdown / overstride, calf- or ankle-dominant push vs hip extension, short
    acceleration stride, backside mechanics, arm action, transition sprint with the head up, speed / push-ahead
    dribble, layup approach and penultimate step, one-foot take-off, deceleration and stopping, landing,
    repeated-sprint fade, calf and knee load capacity, distance-running habits that carry over.
  - `fuel_recovery_kb.md`: energy and macros by day type, protein per meal, carbs around training and games,
    hydration, game-day timing, supplements with strong evidence only (AIS group A), sleep, recovery methods ranked
    by evidence, soreness vs pain and red flags, load progression and deload, body composition trade-off.
  - Each entry says which measured field or film observation triggers it, so reviewers and writers can cite slugs.
- **Claims checked**: claims the player brings (from a coach, a teammate, the internet) each get a verdict
  (supported / partly / not supported) with the source, shown on the page. A claim is a useful hypothesis, not
  an authority. Claims live in the player's gitignored workspace folder, never in the repo.
- **Pipeline** (repo, `src/hoop_tape_miner/`): a `move` flow that mirrors `train`. One command, deterministic
  stages, exit 3 where the agent looks or writes, rerunnable when new clips arrive.
- **Baseline analysis** from existing footage, written to the player KB and delivered as page + film.
- **Plan** that slots the running work into the player's existing program (if any) instead of a second, competing
  program, plus a filming protocol for the re-shoot and re-tests.

## Non-goals

- No 3D biomechanics, force plates, IMUs or ground-reaction forces. "Force pattern" is inferred from kinematics
  (joint angles, foot placement, timing) and stated as inference.
- No medical diagnosis. Pain complaints get load advice, capacity work and red flags that send the player to a
  physio.
- No re-run of the game CV pass. No new game analysis.
- No numeric sprint claims from game tracking: a game's tracks give too few sprint bursts per player, with camera
  pans and few identified tracklets. Report as "unclear".

## Anti-goals

- Generic running advice not tied to the player's footage or complaints.
- Stating a gait fault as seen when the footage cannot show it. Without a side-view sprint clip, sprint-gait faults
  are "hypotheses to test on the re-shoot", never "seen".
- Inferring muscles or force direction from 2D pose: "glute-driven" and similar are models from the literature,
  not measurements.
- A diet that turns into a cut that saps power during a training block.
- Claims built on a handful of reps (e.g. a knee-angle difference between makes and misses from 3 misses).

## Constraints

- Privacy as in `docs/privacy.md`: all personal output under `workspace/players/<player>/` (gitignored), heavy media
  under `<media root>/players/<player>/movement/<date>/`. Repo gets only code, prompts (KB), docs, tests.
- 2D pose from one camera (YOLO `yolo11s-pose`, 17 COCO keypoints, as in `train_scan.py`):
  - angles are projections, comparable only between clips from a similar camera spot;
  - contact and flight times only at 100 fps or more (a 2D running study needed >= 100 Hz for event detection),
    and only after the validation check below;
  - at 30 fps: step counts, cadence, posture and placement only.
- At most 3 subagents at once; browser checks via the `browser-check` subagent.
- Code, docs, KB in English; page and film bilingual.

## Design (decided)

**Layout.** A movement session lives in `<workspace>/players/<player>/movement/<YYYY-MM-DD>[-n]/` with:

- `movement.json`: kind `movement`, player, date, clips with `kind`, `fps`, camera `view` (side | front | behind |
  game), time ranges, and `sources` for footage reused from training or game folders;
- the review, `summary.json`, `facts.md`, figures, page, film scripts and `plan.json`.

Heavy files go to the media root as in training.

**Clip kinds.**

| Kind | What |
|---|---|
| `sprint` | side view, 20-30 m from standing / falling start |
| `run` | side, steady or treadmill |
| `dribble-sprint` | speed dribble full court |
| `layup` | approach, take-off, landing, side or 45° |
| `decel` | sprint to stop |
| `game` | reference moments from a game video |
| `training` | reference moments from a training session |

**Stages** (one module each, registered in `cli.py`):

| Stage | Does |
|---|---|
| `move-new` | scaffold the session folder from clips or from references into existing training/game videos |
| `move-scan` | pose per clip at native fps (cap 120), follow the main person (reuse `train_scan.scan/pick`), detect foot contacts, compute per-step and per-clip metrics, write `gait.json` per clip |
| `move-sheets` | key-frame sheets (touchdown, mid-stance, toe-off, penultimate, take-off, landing) with skeleton and angle overlays; overlay mp4 per clip; filled briefs from `prompts/movement_review_brief.md` |
| agent | reviewer per clip group writes `review.json`: faults seen / not seen / not visible, each tied to times and KB slugs, confidence |
| `move-summary` | merge metrics + review -> `summary.json`, `facts.md`, figures (zh + en), reference ranges from the KB, progress vs earlier movement sessions |
| agent | `README.md` / `README.en.md` (`prompts/movement_report.md`), `plan.json`, `listen.<lang>.md`, `film.<lang>.md` |
| existing | `narrate`, `film`, `html`, `publish` reuse (`game_config.load_game` must find `movement.json`) |
| `move` | orchestrator over the above, same exit-code contract as `train` |

**Metrics** (2D, per clip; missing = unknown, never zero):

- Running: step count and cadence; step length in leg lengths (static, side-on camera); trunk lean at the first
  three touchdowns and at speed; shin angle at touchdown; touchdown point ahead of the hip (braking indicator);
  knee lift; heel recovery height; thigh separation at toe-off; hip-height bounce; arm swing range; contact /
  flight time when fps >= 100.
- Layup: relative length of the last three steps, hip drop on the penultimate step, take-off knee and trunk angle,
  take-off foot ahead of the hip, landing knee flexion.
- Dribble-sprint: dribbles per court length, ball height vs hip (when the ball is detected), head angle.

**Baseline from existing footage.**

- Sources: a training session (and its `pose.npz`, minus any window where the tracker followed someone else) and
  reference moments from a game video.
- Pose: `move-scan` re-runs pose at the video's native fps only inside reference windows (about 2 s before to
  1.5 s after each reviewed finish, plus drive / first-step / landing moments), not over the whole video. A 15 fps
  training `pose.npz` is not used for gait.
- Layups: reviewed finishes from the training review (`run/train_review/review_part*.json`, `category: finish`).
  Prefer a clean block of side-on wing drives; label contested reps.
- Game footage is review-only: the reviewer watches the listed moments; `move-scan` computes no metrics on
  `view: game` clips (panning camera, small players).
- Shared code: `move-scan` imports `train_scan.scan/pick`; `game_config.load_game` gets the `movement.json` lookup.
- Overlap with `prompts/skill_kb.md`: `movement_kb.md` cross-references its slugs instead of duplicating them;
  `fuel_recovery_kb.md` goes deeper than the skill KB's recovery entry, which points to it.
- Program: the running work is merged into the player's existing program in place, the old file kept as a backup.
- Sharing: page and films stay local; publish only when the player asks.

**Page order.** Claims with verdicts; the model (distance running vs sprint vs basketball movement) with simple
diagrams; what the footage shows, with overlay stills and clips; what it cannot show yet; fixes (cues, drills) and
where they go in the program; fuel by day type; recovery week and pain care with red flags; filming protocol and
tests for the re-shoot. The film follows the same story in about 4-6 minutes per language.

**Player KB updates.** `focus.md` gains the running/force focus, `log.md` gets a dated entry, `README.md` lists
the movement folder.

**Measurement validation** (before any metric reaches the page):

- Hand-label foot contacts, penultimate step and take-off frame by frame on about 10 real layup approaches.
- Compare with `move-scan`: timing error, missed and extra contacts, identity switches.
- A metric whose check fails is not shown; the reviewer reads it off the key-frame sheets and says so.
- Synthetic tests cover the code, the hand-labelled check covers the measurement. The flow follows the player
  (`seed` / `look`), not the ball.

**Safety order.** A pain check (0-10 scale, next-morning response) comes before any new sprint or jump load; load
rises only when the check stays low (thresholds from the KB). Cross-session comparisons need the same camera spot,
action and metric version (`metrics_version` in `gait.json`).

**Build order.** KB from the research -> measurement validation on real clips -> baseline page and film from what
is confirmed -> more automatic metrics -> program merge.

## Left to the builder

- Final KB entry list and wording, from research notes kept under `<media root>/players/<player>/movement/research/`.
- Foot-contact detection method and thresholds (ankle height / velocity minima; toe keypoints are not in COCO-17),
  smoothing, how to pick the main person in sprint clips.
- Figure designs, page layout (follow the existing training and program page styles), film scene list.
- Test coverage: synthetic keypoint series for contact detection and each metric; no GPU or video in tests.
