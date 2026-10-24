# Sports film review benchmark (svc-bench-1, svc-bench-2)

Which coding agent and vision model reviews sports film best? This benchmark scores each run against ground truth,
so every number is measured, not judged.

- **Leaderboard:** <https://mariusding.github.io/sports-video-coach/benchmark/>
- **Result files:** [`benchmark/results/`](../benchmark/results/)
- **Commands:** `sports-video-coach bench prepare | score | validate | page`

## Suites

| Suite | Videos | What it tests |
|---|---|---|
| `svc-bench-2` (hard) | 5, 28 to 56 s | A hand-held camera, look-alike decoys, rule-defined events, noise. See [below](#suite-svc-bench-2-hard). |
| `svc-bench-1` | 4, 20 to 31 s | Still camera, flat colours. Saturated: every agent tried wrote a pixel tracker and scored 1.0. |

`bench prepare --out <dir>` draws `svc-bench-1`; add `--suite svc-bench-2` for the hard suite. `answers.json` names
its suite, and `bench score` and `bench validate` score each file against the suite it names. The leaderboard shows
one table per suite.

## How it works

1. `bench prepare` draws the suite's synthetic videos and an empty `answers.json`.
2. Your agent watches the videos (frames, contact sheets, any tool it likes) and fills `answers.json`.
3. `bench score` compares the answers with the truth and writes one result file.

The videos are drawn by the tool, so the truth is exact: no human labels, no judge model.

## Task kinds and scoring

Every task scores from 0 to 1.

| Kind | What the agent answers | Score |
|---|---|---|
| `count` | How many reps, bounces or shots | `max(0, 1 - abs(answer - truth) / truth)` |
| `rate` | A cadence or a percentage | 1 within 2 % of the truth, linear down to 0 at 20 % |
| `timestamps` | When each event happens | per event: 1 if the error is at most 0.5 s, linear down to 0 at 2 s, 0 if missing; the sum is divided by `max(len(truth), len(answer))` |
| `outcomes` | Made or missed, in order | fraction correct by position |

- **Total** = the mean of the task scores, rounded to 3 decimals.
- Dividing timestamps by the longer list means extra, invented events cost as much as missed ones.
- A missing answer scores 0.

## Suite svc-bench-2 (hard)

Built after suite 1 saturated. Every task defeats a naive colour-blob tracker (one colour mask, fixed pixel rows,
one event per blob), while a careful reviewer who reads the rule and checks the film still gets it exactly right.

- **The camera moves.** Hand-held shake on every video, a slow tilt on the squat video and a lagged follow camera on
  the cone run, so fixed pixel positions mean nothing. Every rule is relative to something in the scene.
- **Look-alike decoys.** A second dribbler with an identical ball, two identical feet, a rebounder under the hoop.
- **Rule-defined events.** Shallow squats and a double dip, a pump fake, a ball that dips into the ring and pops
  out, a run past a cone, a stop between cones.
- **Harder pictures.** Sensor noise, a 6 % brightness flicker, a short motion blur and stronger compression.
- The frames are drawn with numpy and OpenCV and piped to ffmpeg. The truth is computed from the same numbers that
  drive the drawing, with a fixed noise seed, so every `bench prepare` draws the same videos.

| Task | Kind | The rule (exact text in `TASKS.md`) | What a naive tracker gets wrong |
|---|---|---|---|
| `dribble-count` | count | Count the blue player's bounces only, however low. He carries his ball behind a pillar: no bounce while it is hidden. | Counts the green player's identical ball, loses the ball when the two cross, misses 16 to 22 px dribbles. |
| `squat-reps` | count | A rep is good when the plate centre goes below the lower white line and then back above the upper one. A double dip is one rep; a squat that never locks out does not count. | Counts every dip (13 attempts, 8 good); fixed pixel rows drift with the camera tilt. |
| `cadence-change` | rate | Foot strikes per minute from 20.0 s to the end. Either foot counts; arm swings do not. | Averages the whole video (about 8 % off) or counts both feet as one. |
| `cone-touches-pan` | timestamps | The time the runner arrives at a cone where he stops or turns back. A pass-by, a pace change at a cone and a stop between cones are not touches. | Measures the runner in screen pixels, which the follow camera keeps near the centre; reports every cone arrival. |
| `shot-outcomes-hard` | outcomes | Made only if the ball goes down through the ring and out of the net before anyone else touches it. A pump fake is not a shot; dip-in-pop-out and a rebounder's tip-in are misses. | Counts a pump fake as a shot; calls any ball near the ring a make. |

The truth of every task was also read back from the drawn pixels by a careful scripted reader before the suite was
published, so a reviewer who follows the rules can reach it from the film alone.

## Rules

- **No peeking.** The agent must not read the truth files or the package source (`src/sports_video_coach/bench/`).
- **Any tool on the videos is fine.** Looking at frames, ffmpeg, OpenCV or a script the agent writes all count: this
  ranks coding agents as film reviewers, and writing measuring code is part of the job.
- **One run = one file.** Do not pick the best of several runs; submit each run or none.
- **Honest wall time.** `wall_seconds` is what the run really took, or `null` if you did not time it.
- **No hand edits.** `score` and `total` are written by `bench score` only.
- Name what you changed in `settings` (effort, prompts, extra tools). Defaults: leave it empty.

## Submit your run

Pick one:

- **Pull request:** add your file to `benchmark/results/` as `<date>-<agent>-<model>.json` (lower case, `-` for
  spaces; `bench score` adds `-svc-bench-2` for the hard suite) and fill the benchmark part of the PR template.
- **Issue form:** paste the file into the
  [benchmark result form](https://github.com/mariusDing/sports-video-coach/issues/new?template=benchmark_result.yml);
  a maintainer adds it.

An evidence link (a gist, a transcript, a log) is optional but makes your row easier to trust.

## How rows are checked

- CI runs `sports-video-coach bench validate benchmark/results/*.json` on every pull request.
- `validate` re-scores each file from its `answer` fields against the suite's truth and rejects a file whose
  scores differ.
- The leaderboard page is rebuilt from the folder by `bench page` on every push to master. A file that does not
  parse is listed on the page as skipped, never silently dropped.

## Honesty notes

- The benchmark and its page were built with a coding agent.
- Every row is reproducible: same suite, same commands, scores recomputed from the answers.
- The author's own tool and agent get no special treatment; their misses are shown like anyone else's.
- Synthetic drills test counting and timing. They do not cover every part of a coach's review (cues, drills,
  judgement of technique).

## Result file format (schema 1)

```json
{
  "schema": 1, "suite": "svc-bench-1", "tool_version": "0.x.y", "date": "2026-10-24",
  "contender": {"agent": "Claude Code", "agent_version": "", "model": "", "settings": ""},
  "submitted_by": "github-handle",
  "tasks": [{"id": "reps-bounce", "kind": "count", "truth": 7, "answer": 7, "score": 1.0, "note": ""}],
  "total": 1.0, "wall_seconds": null, "evidence": ""
}
```

`suite` is `svc-bench-1` or `svc-bench-2`; the task ids must be that suite's. Unknown fields are kept.
