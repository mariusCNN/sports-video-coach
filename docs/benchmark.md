# Sports film review benchmark (svc-bench-1, svc-bench-2, svc-bench-3)

Which coding agent and vision model reviews sports film best? This benchmark scores each run against ground truth,
so every number is measured, not judged.

- **Leaderboard:** <https://mariusding.github.io/sports-video-coach/benchmark/> (in Chinese: <https://mariusding.github.io/sports-video-coach/benchmark/zh/>, built from the same result files)
- **Result files:** [`benchmark/results/`](../benchmark/results/)
- **Commands:** `sports-video-coach bench run | prepare | score | validate | page | baseline`
- **Install:** `uv tool install git+https://github.com/mariusDing/sports-video-coach` (needs ffmpeg on PATH), then
  [run your agent in one command](#add-your-agent-in-one-command).

## Suites

| Suite | Videos | What it tests |
|---|---|---|
| `svc-bench-3` (eyes) | 4, 21 to 53 s | Small, short and hidden events, for the frames track. See [below](#suite-svc-bench-3-eyes). |
| `svc-bench-2` (hard) | 5, 28 to 56 s | A hand-held camera, look-alike decoys, rule-defined events, noise. See [below](#suite-svc-bench-2-hard). |
| `svc-bench-1` | 4, 20 to 31 s | Still camera, flat colours. Saturated: every agent tried wrote a pixel tracker and scored 1.0. |

`bench prepare --out <dir>` draws `svc-bench-1`; add `--suite svc-bench-2` or `--suite svc-bench-3` for the others. `answers.json` names
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
- **Above chance** = the same, measured from a blind guess instead of from 0 (see
  [below](#floor-and-above-chance-score)).
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

A scripted pixel reader reads every task back from the drawn videos: dribble count, squat reps and shot outcomes
exactly, the 10 cone touches within 0.05 s, and the late cadence 0.2 % off (182.186 per minute is the truth, it reads
181.818); scored like an agent's answers, it gets 1.0 on every task. The reader was written knowing how the videos are
drawn, so it shows the truth is in the film, not that a blind reviewer will find it.

## Frames-only track (eyes)

On the default `code` track every agent so far wrote a pixel tracker and scored about 1.0, so the code track ranks
coding agents but not their models' eyes. The `frames` track asks the other question: how well does a model review
film by eye, with no code at all?

```bash
sports-video-coach bench prepare --out bench-frames --suite svc-bench-2 --track frames
```

- **What the agent gets.** No videos. Each video becomes its stills, every 2nd frame (one every 0.08 s), in
  `frames/<task>/` (640x360, named by time, e.g. `t012.48.jpg`) and on contact sheets of 25 in `sheets/<task>/`, the
  time printed under every still. `TASKS.md` lists every sheet; `answers.json` says `"track": "frames"`.
- **Why every 2nd frame.** The shortest thing a task needs seen is about 0.3 s (a treadmill step, a squat plate
  below the line), so it falls on at least 3 stills.
- **Same truth, same scoring** as the code track. `bench score` copies the track into the result file and names it
  `...-frames.json`; `bench validate` checks it like any other.
- **No tools that run code.** The agent may only look at the images and write its answers. If its harness has no
  file-writing tool, it ends its reply with `answers.json` in a `json` block and you save that file.
- The leaderboard shows the frames track in its own tables, under the code track.

How the first rows were run (both with stdin closed and a timeout; the transcript proves which tools existed).
`bench run --track frames --agent claude` runs the Claude Code row's command with the same prompt, and
`bench run --track frames --agent codex` the Codex row's (see [below](#add-your-agent-in-one-command)):

| Agent | How "no code" was enforced | Checked in the transcript |
|---|---|---|
| Claude Code | `claude -p --restricted --safe-mode --strict-mcp-config --tools Read --permission-prompts none --output-format stream-json --verbose --model M`, run in the prepared folder | The `init` event lists `tools: ["Read"]`, no MCP servers; `--restricted` confines Read to the folder; every `tool_use` is a Read of a file in the folder. |
| Codex CLI | `codex exec - -s read-only --json` (`bench run` drops `--json`, see below) with `--disable` for `shell_tool`, `unified_exec`, `code_mode_host`, `code_mode`, `view_image`, `browser_use`, `computer_use`, `apps`, `plugins`, `multi_agent`, `image_generation`; the prompt (with `TASKS.md`) on stdin and every contact sheet attached with `-i` | No `command_execution` item; the code-mode tool fails closed ("code-mode host is disabled"). Codex cannot open files this way, so it sees the sheets but not the full-size stills. |

`bench run --agent codex --track frames` runs `codex exec - -s read-only -c web_search=disabled` with
`--disable` for `shell_tool`, `unified_exec`, `code_mode_host`, `code_mode`, `browser_use`, `browser_use_external`,
`computer_use`, `apps`, `plugins`, `multi_agent`, `image_generation`, `view_image`, `goals` and `sleep_tool`, every
contact sheet attached with `-i`, the prompt on stdin and then stdin closed. That is as far as Codex CLI 0.159.3
lets a run restrict it: its docs ([config reference](https://developers.openai.com/codex/config-reference), read
2026-10-25) list switches for single tools but none that removes every tool, and the run still lists a few
(`functions.exec`, which fails closed, sub-agent and patch tools). **Beyond those switches, tool restriction is by
prompt only; the transcript shows every command it ran**, and `bench run` counts them (`commands_run` and
`tool_calls_refused` in `run.json`). It records the plain output (stderr merged in) rather than `--json`, because
only the plain header names the model and reasoning effort. Codex runs with your own config (see below), so your
hooks and `AGENTS.md` load too.

First rows (svc-bench-2, 2026-10-24; every run submitted, Sonnet ran twice with the same command):

| Agent | Model | Total | Wall | Cost |
|---|---|---|---|---|
| Claude Code 2.1.310 | claude-opus-5-5 | 1.000 | 522 s | $3.04 |
| Codex 0.159.3 | gpt-6-astra (xhigh) | 1.000 | 585 s | not reported |
| Claude Code 2.1.310 | claude-sonnet-5-5 | 0.755 | 77 s | $0.24 |
| Claude Code 2.1.310 | claude-sonnet-5-5 (second run) | 0.646 | 12 s | $0.05 |

- **Strong models still saturate by eye.** Opus read 118 images (sheets and full-size stills); Codex saw all 102
  sheets. Both got every task exactly right.
- **The spread measures diligence more than eyesight.** Sonnet opened 16 of the 102 sheets (13 cone sheets, 3
  squat sheets) and said it guessed the dribble count, the cadence and the shots without opening their sheets. The
  one task it looked at closely, the cones, is its one real eyesight miss: 4 of the 10 touches (0.40).
- **Guessing scores high.** Sonnet's unread shots, "made, missed" alternating, scored 0.83; its guessed dribble
  count 0.80. Sonnet's second run (submitted, same command) read `TASKS.md` and two sheets, guessed the rest and
  scored 0.646. Counts and rates get partial
  credit and the shot outcomes are mostly alternating, so a raw total overstates what was seen. The leaderboard
  therefore shows an [above-chance score](#floor-and-above-chance-score) next to the raw total.

## Floor and above-chance score

A guess scores more than 0: counts and rates earn partial credit, and an alternating shot list gets many shots
right. So
the leaderboard shows, next to each raw total, how far the run got above a blind guess.

**The floor: a blind baseline.** A deterministic guesser that sees no video and no still:

```bash
sports-video-coach bench baseline --suite svc-bench-2 [--track frames] [--date D] [--out FILE]
```

- It reads only the task text a contender gets (`TASKS.md` of that suite and track) and answers each task with
  the example in its "Answer:" line: `5` for a count, `30.5` or `150.5` for a rate, `[1.5, 4.25]` for timestamps.
- For outcomes it repeats the example's pattern (`"made", "missed"`) to the number of shots the task states.
- It holds no prior of its own and reads no truth (a test changes every truth and checks the answers stay the
  same). Same suite, same answers; the frames track asks the same questions, so it answers the same.
- It writes a normal result file with agent `blind baseline`, scored by the normal scorer; `bench validate`
  checks it like any other. The files are in `benchmark/results/` (`2026-10-24-blind-baseline*.json`).

Measured (2026-10-24; code and frames tracks give the same answers and scores):

| Suite | Task scores of the blind baseline | Total |
|---|---|---|
| `svc-bench-1` | jump-count 0.385, stroke-rate 0.000, cone-touches 0.110, shot-outcomes 0.800 | 0.324 |
| `svc-bench-2` | dribble-count 0.089, squat-reps 0.625, cadence-change 0.145, cone-touches-pan 0.090, shot-outcomes-hard 0.833 | 0.356 |
| `svc-bench-3` | juggle-touches 0.106, far-hoop-shots 0.500, pass-releases 0.167, stroke-rate 0.551 | 0.331 |

On `svc-bench-3` the example rate in the task text, `30.5`, lands close to the true stroke rate, so the blind guess
earns 0.551 there and any answer scoring at or below that counts 0 above chance.

**The formula.** Per task, with `floor` = the blind baseline's score on that task:

```text
above = clip((score - floor) / (1 - floor), 0, 1)
above-chance total = mean of `above` over the tasks
```

- 0 means no better than the blind guess on that task, 1 means right. A score below the floor counts as 0.
- A task whose floor is 1 would tell nothing; it is left out of the mean (no task has such a floor today).
- It is computed when the page is built, from the `score` of each task row already in the result files. No result
  file changes and none needs a new field.
- The raw total stays on the page and still ranks the rows. The baseline row is shown under each table, marked
  "Floor".
- This guesser knows no sport. A guesser that does (say, a typical running cadence of 180 per minute) scores more,
  so the floor is a lower bound on what guessing gets and the above-chance score an upper bound on what was seen.

**The summary.** Above each table of runs, a summary table has one line per contender (same agent, model and
settings; the agent version does not split them):

- Runs (n): how many result files that contender has on the suite and track.
- Mean total and mean above chance: plain means over those runs.
- Range: lowest to highest above-chance total over the runs; a dash when n = 1.
- Ranked by mean above chance, then mean total. The blind baseline is never a line; it stays the floor row of the
  table below. Without a baseline file for that suite and track, the above-chance cells show a dash and the
  ranking falls back to mean total.
- Every run still has its own row in the table below, bad runs too.

Above-chance totals of the rows on 2026-10-24:

| Suite, track | Agent / model | Raw | Above chance |
|---|---|---|---|
| svc-bench-3, frames | Claude Code / claude-opus-5-5 | 1.000 | 1.000 |
| svc-bench-3, frames | Claude Code / claude-opus-5-5 (second run) | 1.000 | 1.000 |
| svc-bench-3, frames | Claude Code / claude-fable-5-1 (second run, 3600 s limit; answered in 1645 s) | 0.989 | 0.988 |
| svc-bench-3, frames | Codex / gpt-6-astra | 0.862 | 0.727 |
| svc-bench-3, frames | Claude Code / claude-sonnet-5-5 | 0.612 | 0.497 |
| svc-bench-3, frames | Claude Code / claude-haiku-5-5 | 0.585 | 0.333 |
| svc-bench-3, frames | Claude Code / claude-sonnet-5-5 (second run) | 0.441 | 0.273 |
| svc-bench-3, frames | Claude Code / claude-fable-5-1 (killed at the 1700 s limit before answering) | 0.000 | 0.000 |
| svc-bench-3, code | Claude Code / claude-sonnet-5-5 (runner's own agent config, `--use-my-config`) | 0.995 | 0.994 |
| svc-bench-3, code | Claude Code / claude-sonnet-5-5 (clean room) | 0.958 | 0.951 |
| svc-bench-2, frames | Claude Code / claude-opus-5-5 | 1.000 | 1.000 |
| svc-bench-2, frames | Codex / gpt-6-astra | 1.000 | 1.000 |
| svc-bench-2, frames | Claude Code / claude-sonnet-5-5 | 0.755 | 0.564 |
| svc-bench-2, frames | Claude Code / claude-sonnet-5-5 (second run) | 0.646 | 0.460 |
| svc-bench-2, code | Claude Code / claude-sonnet-5-5 | 1.000 | 1.000 |
| svc-bench-2, code | Codex / gpt-6-astra | 1.000 | 1.000 |
| svc-bench-2, code | Claude Code / claude-opus-5-5 | 0.960 | 0.956 |
| svc-bench-1, code | Claude Code / claude-opus-5-5, Claude Code / claude-sonnet-5-5, Codex | 1.000 | 1.000 |

On `svc-bench-2`, Sonnet's alternating shot list (0.833) equals the floor on that task, so it adds 0 above chance.
On `svc-bench-3`, Codex's stroke rate (0.525) and Sonnet's (0.142) are both below the 0.551 floor, so that task adds
0 for both.

## Suite svc-bench-3 (eyes)

Built after the strong models scored 1.0 on `svc-bench-2` by eye. It is meant for the frames track: the events are
small, short or hidden, so they have to be found still by still, and a lazy reading lands near a plausible decoy.

```bash
sports-video-coach bench prepare --out bench-eyes --suite svc-bench-3 --track frames
```

- **Small things.** A ball 5 px in radius on a 640x360 frame, a ball 3 px in radius at a 16 px wide far rim, a small
  yellow oar blade.
- **Short events.** The two contacts of a double touch are 0.24 s (3 stills) apart; a one-touch pass has no hold.
- **Hidden moments.** A banner crosses the rim on 3 of the 12 shots; a red defender is in front of the passer at 4
  of the 12 releases. The rule says to judge those by where the ball goes.
- **Decoys with nearly the same answer.** A second juggler (44 touches against 47), a grey pair passing an
  identical ball, a far boat rowing about 31.8 a minute against 33.92.
- The camera is hand-held on every video. Drawn like `svc-bench-2`: the truth comes from the numbers that drive the
  drawing, with fixed seeds, and is never written to the run folder.

| Task | Kind | The rule (exact text in `TASKS.md`) | What a quick look gets wrong |
|---|---|---|---|
| `juggle-touches` | count | The left (red) player's foot touches, 29.76 s. A double touch is two; a floor bounce is none. | 9 double touches look like one; 6 floor bounces look like touches; the right player has 44. |
| `far-hoop-shots` | outcomes | 12 shots at a far hoop, 52.84 s. Rim-outs, a short ball and a ball that dips in and pops out are misses; rim rolls that drop are makes; one pump fake is not a shot. | Any ball near the 16 px rim looks like a make; 3 shots reach the rim behind a passing banner. |
| `pass-releases` | timestamps | Release times of 12 passes between three blue players, 21 s. Four pass fakes are not passes; two one-touch passes are released on arrival. | Fakes counted as passes; releases behind the defender missed; the grey pair's passes counted. |
| `stroke-rate` | rate | The near boat's catches from 15.0 s, 32 s. The rower changes rate at 15 s. | The whole-video rate is 31.37 and the far boat's 31.83, both more than 5 % off. |

**Read-back from the stills.** A scripted reader that opens only `frames/<task>/t*.jpg` of a frames-track folder
(the full-size stills an agent gets, every 0.08 s) recovers every answer: the 47 touches exactly, all 12 shot
outcomes, the 12 releases within 0.01 s, and the stroke rate at 33.920. Scored like an agent, it gets 1.0 on every
task. For the far hoop it places the rim from the pole and the floor, because the noisy 16 px rim is not found as a
red blob on its own. The reader was written knowing how the videos are drawn; it shows the answers are in the
stills, not that a model will find them. It was not run on the contact sheets alone, which is all Codex sees (see
the frames-track table above).

First rows (frames track, 2026-10-24, one run each, every run submitted; run as in the table above):

| Agent | Model | Total | Juggle | Shots | Passes | Rate | Wall | Cost |
|---|---|---|---|---|---|---|---|---|
| Claude Code 2.1.310 | claude-opus-5-5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 489 s | $3.91 |
| Codex 0.159.3 | gpt-6-astra (xhigh) | 0.862 | 1.000 | 1.000 | 0.923 | 0.525 | 766 s | not reported |
| Claude Code 2.1.310 | claude-sonnet-5-5 | 0.612 | 0.723 | 0.750 | 0.833 | 0.142 | 65 s | $0.23 |

- **Opus still gets 1.0, at a price.** 252 Reads (55 of the 69 sheets, 195 full-size stills), 489 s, $3.91. Its
  stroke rate, 33.9, is within the 2 % full-credit band, but by its own account it checked only the catches up to
  20.3 s and the ones near 25.6 and 30.9 s, and assumed a steady rate in between.
- **The spread is wider than on `svc-bench-2`.** The stroke rate separates the other two: Codex answered 37.5
  (10.6 % off) from the sheets.
- **Codex** counted the juggling and the shots exactly; it added one release (at 7.76 s, between two real ones) and
  was within 0.5 s on all 12 real ones.
- **Sonnet** opened 17 of 69 sheets: all 11 pass sheets, 4 rowing sheets, 1 juggling and 1 shot sheet. It said it
  estimated the juggling count from one sheet and guessed the shot outcomes; the guess scored 0.75.

### Fresh seeds (`--seed`)

The published suites and their truth ship in the open package, so a model may have seen them in training.
`svc-bench-3` can also be drawn anew at run time from an integer seed, which reduces the effect of memorising the
fixed suite's answers: the same four scenes and kinds of traps, with new counts,
shot outcomes, release times and stroke rates.

```bash
sports-video-coach bench prepare --out bench-fresh --suite svc-bench-3 --track frames --seed        # a random seed
sports-video-coach bench run --agent claude --model claude-opus-5-5 --suite svc-bench-3 --track frames --seed 4242
```

- **The prepared folder never holds the truth.** `bench score` and `bench validate` rebuild it from the `seed`
  in `answers.json` and in the result file. The scored result file does contain it (its `truth` fields), and so
  does the page once the file is in `benchmark/results/`: a published seed is spent, so each run should draw a new
  one (`--seed` alone picks a random one). The seed is in the run folder; turning it into the
  truth means running the package's generator, which the no-peeking rule already forbids.
- **Same task text, new numbers.** `TASKS.md` says the videos were drawn from a fresh seed and gives that seed's
  shot count (10 to 13) and video lengths; the rules are word for word the same.
- **Without `--seed`** nothing changes: the published suite is byte-identical (same videos, same truth).
- **Own board and floor.** Seeded runs are listed on the page under `svc-bench-3-fresh`. Each run's floor is the
  blind baseline on its own seed, computed at build time, never stored; above chance is measured against it.
- **Seeds that stay readable.** A random draw could hide an answer: a fast arc blurs the ball, the defender can
  stand in front of a catch. The generator keeps every seed within what the published suite asks of the eyes:
  a juggle's height grows with the time it takes, a pass across the middle player is a lob, no two one-touch passes
  follow each other, and the defender hides only a ball that is held, never a one-touch pass, a catch or a flight.
- **Read-back on seeds.** The scripted pixel reader above, run on the frames-track stills of seeds 5, 11, 77,
  2026, 4242 and 205159368, scores 1.000 on every task of every seed (`bench score` as an agent would). Like on the
  published suite, it shows the answers are in the stills, not that a model will find them.

Fresh-seed rows (frames track, 2026-10-25; Claude Code in the clean room at default effort, Codex with the
runner's own config at reasoning effort xhigh; each run drew its own random seed with `bench run --seed`; two runs
each for Opus and Sonnet, one each for Haiku and Codex, each run on its own seed):

| Agent | Model | Total | Above chance | Juggle | Shots | Passes | Rate | Wall | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Claude Code 2.1.310 | claude-opus-5-5 (seed 205159368) | 0.994 | 0.994 | 0.978 | 1.000 | 1.000 | 1.000 | 317 s | $2.32 |
| Claude Code 2.1.310 | claude-opus-5-5 (seed 613104018) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 378 s | $2.77 |
| Claude Code 2.1.310 | claude-sonnet-5-5 (seed 956466926) | 0.504 | 0.413 | 0.905 | 0.308 | 0.804 | 0.000 | 19 s | $0.07 |
| Claude Code 2.1.310 | claude-sonnet-5-5 (seed 406013493) | 0.583 | 0.426 | 0.933 | 0.583 | 0.816 | 0.000 | 16 s | $0.06 |
| Claude Code 2.1.310 | claude-haiku-5-5 (seed 166697672) | 0.440 | 0.198 | 0.500 | 0.455 | 0.250 | 0.556 | 96 s | $0.06 |
| Codex 0.159.3 | gpt-6-astra, xhigh (seed 911623366) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 514 s | not reported |

- **Opus nearly holds its published score on a seed drawn at run time.** It counted 44 touches against 45 (it
  said itself the count "could be off by one or two"), called all 11 shots, found the 11 releases within 0.05 s
  and gave a stroke rate of 33.1 against 33.149, in 121 Reads.
- **Sonnet looked at 4 of 71 sheets and estimated the rest.** It opened one sheet per video and said so:
  38 touches from a rate scaled over the clip (truth 42), a guessed list of 13 shot outcomes (4 right, below the
  blind floor of 0.462), the first release at 0.8 s and then an assumed steady 1.8 s spacing (4 of 11 within 0.5 s)
  and a stroke rate of 28 against 36.388 (23 % off). On the published svc-bench-3 it opened 17 of 69.
- **Opus's second run (seed 613104018) got every task right.** 41 touches exact, all 11 shots, the 11 releases
  within 0.08 s and a stroke rate of 35.1 against 35.156, in 150 Reads (56 of 68 sheets, 92 full-size frames).
- **Sonnet's second run (seed 406013493) estimated the same way.** It opened 4 of 68 sheets and said so: 48
  touches from a rate (truth 45), an alternating made / missed guess for the 12 shots (7 right, exactly that seed's
  blind floor of 0.583), a release every 2 s from 0.4 s (5 of 11 within 0.5 s) and a "typical" stroke rate of 28
  against 36.388 (both seeds happened to draw that rate).
- **Haiku opened 60 of 67 sheets but did not resolve them.** It said the stills were too small to track: 60
  touches from a rate (truth 40), 11 shot outcomes of which it read one (5 right), 3 pass releases of 12 (the
  scorer found 4 of the 12 within 0.5 s of them) and a "typical sculling rate" of 30 against 33.333, below that
  seed's blind floor of 0.639.
- **Codex (one run, seed 911623366, `bench run --agent codex --track frames`) got nothing wrong.** 47 touches
  exact, all 13 shots, the 11 releases within 0.08 s and a stroke rate of 37.3 against 37.19, from the 73 contact
  sheets alone (it cannot open the full-size stills), with no command run. It is one run; it says nothing about
  runs on other seeds. It replied in Chinese: Codex ran with the runner's own `AGENTS.md`.
- **Spread across seeds.** Above chance, Opus's two runs scored 0.994 and 1.000 (a spread of 0.006) and
  Sonnet's 0.413 and 0.426 (0.013), so the gap between them (about 0.58) is far wider than either model's spread
  over two seeds. That is two runs per model, each on its own seed: it is not a variance estimate, and on the
  fixed suite two Sonnet runs differed by 0.224.
- **What these rows say.** They show the fixed-suite order (Opus well ahead of Sonnet and Haiku) on five seeds
  no run had drawn before; they say nothing about what was in any model's training data. The truth is kept out
  of the prepared folder; it shows in each result file and on the page. Blind floors (juggle / shots / passes /
  rate): seed 205159368 0.111 / 0.455 / 0.142 / 0.667, seed 613104018 0.122 / 0.364 / 0.146 / 0.375, seed
  956466926 0.119 / 0.462 / 0.182 / 0.212, seed 406013493 0.111 / 0.583 / 0.165 / 0.212, seed 166697672
  0.125 / 0.273 / 0.153 / 0.639, seed 911623366 0.106 / 0.308 / 0.153 / 0.112 (published: 0.106 / 0.500 /
  0.167 / 0.551).

## Rules

- **No peeking.** The agent must not read the truth files or the package source (`src/sports_video_coach/bench/`).
- **Any tool on the videos is fine** on the code track. Looking at frames, ffmpeg, OpenCV or a script the agent
  writes all count: this ranks coding agents as film reviewers, and writing measuring code is part of the job. On the
  frames track no code at all (see [above](#frames-only-track-eyes)).
- **One run = one file.** Do not pick the best of several runs; submit each run or none.
- **Honest wall time.** `wall_seconds` is what the run really took, or `null` if you did not time it.
- **No hand edits.** `score` and `total` are written by `bench score` only.
- Name what you changed in `settings` (effort, prompts, extra tools). Defaults: leave it empty.

## Add your agent in one command

```bash
sports-video-coach bench run --agent claude --model claude-sonnet-5-5 --suite svc-bench-2
```

It draws the suite in a fresh folder, runs the agent there headless, scores the answers and prints the result file
and a prefilled issue form link. The frames track, as the leaderboard's frames rows were run:

```bash
sports-video-coach bench run --agent claude --model claude-sonnet-5-5 --suite svc-bench-3 --track frames
```

| Option | What it does |
|---|---|
| `--agent claude` | Claude Code: `claude -p --safe-mode --setting-sources project --strict-mcp-config --output-format stream-json --verbose --dangerously-skip-permissions` |
| `--agent codex` | Codex CLI: `codex exec --skip-git-repo-check -s workspace-write`, with your own Codex config (not isolated, see below) |
| `--agent <preset>` (`gemini`, `qwen`, `aider`, `opencode`, `cursor`, `copilot`, `goose`) | A preset for another agent CLI, built from its docs but **not run by the maintainer** (table below); code track only |
| `--agent cmd --cmd "..."` | Any other CLI. `{prompt}` becomes the prompt text, `{prompt_file}` a file holding it, `{model}` the model. It runs as given: keeping your own agent config out is up to you. |
| `--agent openai --base-url URL --model M` | Any vision model behind an OpenAI-compatible chat-completions endpoint (Ollama, LM Studio, vLLM, llama.cpp server, OpenRouter, ...); frames track only, see [below](#any-vision-model-behind-an-openai-compatible-api) |
| `--use-my-config` | Run Claude Code with your own agent config instead of the clean room (see below); `settings` then says so. Codex always runs with yours. |
| `--model M` | Passed to the agent as `--model M` |
| `--suite` | `svc-bench-1` (default), `svc-bench-2` or `svc-bench-3` |
| `--seed [N]` | `svc-bench-3` only: draw it from fresh seed N (0 to 2^63 - 1), or a random seed without N; see [Fresh seeds](#fresh-seeds---seed) |
| `--track frames` | Stills instead of videos, no code. Claude Code runs with Read as its only tool (the command in the [frames table](#frames-only-track-eyes)); the json block that ends the agent's reply becomes `answers.json`. Codex runs read-only with its tool features off and the sheets attached; beyond that, tool restriction is by prompt only (see [frames track](#frames-only-track-eyes)). |
| `--out DIR` | Run folder, new or empty (default `~/svc-bench-runs/<agent>-<model>-<time>`) |
| `--timeout N` | Kill the agent after N seconds (default 1200) |
| `--by HANDLE` | Your GitHub handle, saved as `submitted_by` |
| `--settings S` | What you changed from defaults (effort, prompts, tools); empty means defaults |
| `--evidence URL` | A published transcript or log (publish the redacted copy, see below) |
| `--dry-run` | Print the command it would run; run nothing |

**Presets for other agent CLIs (untested):**

```bash
sports-video-coach bench run --agent gemini --model <model> --suite svc-bench-3
```

Each preset runs the command below in the run folder (stdin closed, killed at the timeout, `<prompt>` is the
prompt text, `<prompt file>` is `PROMPT.txt`). The flags come only from each CLI's own docs, read on
2026-10-25. **The maintainer has none of these CLIs and never ran them**: the presets are tested against fake
binaries that record their arguments, not against the real CLIs. A flag may have changed since; `--dry-run` prints
the exact command, and `--agent cmd --cmd "..."` runs your own. The result's `settings` starts with `preset, not run
by the maintainer (--agent <name>)`; the version is read with the CLI's own version command.

**Use one of these agents?** [Issue #7](https://github.com/mariusDing/sports-video-coach/issues/7) asks for one run
of each preset: send the result row, or the error if a flag is wrong (or fix the argv in
`src/sports_video_coach/bench/run.py`).

| Preset | Agent | Command it runs | Flags from | Status |
|---|---|---|---|---|
| `--agent gemini` | Gemini CLI | `gemini --approval-mode yolo [--model M] -p <prompt>` | [docs](https://geminicli.com/docs/cli/cli-reference/) | not run by the maintainer; your own config; Google moved individual users to Antigravity CLI on 2026-06-18; API-key and Code Assist users keep Gemini CLI |
| `--agent qwen` | Qwen Code | `qwen --safe-mode --approval-mode yolo [--model M] -p <prompt>` | [docs](https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/) | not run by the maintainer; --safe-mode: no context files, hooks, extensions, skills, MCP servers or subagents |
| `--agent aider` | Aider | `aider --yes-always --no-git --no-check-update --no-pretty --no-stream [--model M] --read TASKS.md --message-file <prompt file> answers.json` | [docs](https://aider.chat/docs/config/options.html) | not run by the maintainer; your own config; it edits answers.json; whether --yes-always also runs the shell commands it suggests is not stated in the docs |
| `--agent opencode` | OpenCode | `opencode run --auto [--model M] <prompt>` | [docs](https://opencode.ai/docs/cli/) | not run by the maintainer; your own config; --model takes provider/model |
| `--agent cursor` | Cursor CLI | `agent -p --force --trust --output-format text [--model M] <prompt>` | [docs](https://cursor.com/docs/cli/reference/parameters) | not run by the maintainer; your own config |
| `--agent copilot` | GitHub Copilot CLI | `copilot -p <prompt> --allow-all-tools --no-ask-user -s [--model M]` | [docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically) | not run by the maintainer; your own config |
| `--agent goose` | Goose | `goose run --no-session [--model M] -t <prompt>` | [docs](https://goose-docs.ai/docs/guides/goose-cli-commands) | not run by the maintainer; your own config; tool approval follows your GOOSE_MODE (Autonomous by default) |

- Code track only: none of these CLIs documents a way to be limited to reading files (as Claude Code's `--tools
  Read` is), so `--track frames` with a preset stops with a message. Gemini CLI's plan mode is not read-only
  enough (it searches the web and, headless, switches to YOLO after the plan).
- Only Qwen Code has a documented clean-room flag (`--safe-mode`); the others load your own config.
- Not added: Antigravity CLI (`agy`), Gemini CLI's successor for individual users: its pages read on that date
  showed no headless prompt flag or auto-approve flag.
- `cost_usd` stays `null` for presets; the model is whatever `--model` says (empty without it).

Any other CLI, with its own non-interactive, auto-approve flags:

```bash
sports-video-coach bench run --agent cmd --name "My agent" --cmd "my-agent --yes -p {prompt}"
```

- The agent gets the same prompt as every other row (`PROMPT.txt` in the run folder), with stdin closed.
- **Clean room by default for Claude Code.** Your own agent config would make your row different from everyone
  else's, so `bench run` leaves it out and writes `clean-room: no user config` in `settings`:
  - Claude Code: `--safe-mode` drops CLAUDE.md, skills, plugins, hooks, MCP servers and custom agents;
    `--setting-sources project` skips your user settings file (model, effort, language, env); `--strict-mcp-config`
    skips other MCP configs. Your login still works; no file is copied or written.
  - Codex is not isolated: it runs with your own `CODEX_HOME` (`~/.codex`: AGENTS.md, `config.toml`, skills,
    hooks, rules, memories). Isolating it would mean copying your login file somewhere else, and `bench run` never
    copies, moves or writes credential files. `settings` says `Codex: runner's own config; not isolated, so
    credentials stay where they are`. For a clean Codex row, run it from a Codex setup without your own config.
  - The frames track was already clean (`--restricted --safe-mode`); its `settings` stay as before.
  - Session variables of a calling agent (`ORCA_*`, `CLAUDECODE`, `CLAUDE_PID`, `CLAUDE_CODE_SESSION_ID` and the
    like) are never passed on, with or without `--use-my-config`.
  - `--use-my-config` loads your Claude Code config instead; `settings` then says `runner's own agent config
    (--use-my-config)`. It changes nothing for Codex.
  - Does it matter? One measured pair (2026-10-24, Claude Code 2.1.310, claude-sonnet-5-5, `svc-bench-3` code
    track, run at the same time): clean room 0.958 in 264 s for $0.67; the maintainer's own config (198 skills,
    85 MCP servers, hooks) 0.995 in 214 s for $0.61. One pair is not enough to say either way: unclear.
- **Measured, not claimed:** `wall_seconds` is timed by `bench run`. `cost_usd` is filled only when the agent
  reports it (Claude Code's result event); otherwise `null`. Without `--model`, the model (and the Claude Code
  version, or the Codex reasoning effort) is read from what the agent itself prints (Claude Code's init event,
  the header of `codex exec`); a value the agent does not print stays empty.
- The run folder keeps the transcript, `stderr.log` and `run.json` (exit code, timed out or not), and a redacted
  copy of the transcript to publish (`transcript.redacted.jsonl`, or `.txt` for Codex). Read it before you do.
- `sports-video-coach bench transcript <src> [<dst>] [--redact WORD ...]` makes that copy from any transcript
  or log (`.gz` in or out works): images become `[image omitted: <file> <size>]`; home folders, your user name,
  host name and emails become `<home>`, `<user>`, `<host>`, `<email>`; environment listings, `PATH`, hook
  output, your skills / plugins / MCP servers and anything that looks like a key or token are dropped. Tool
  calls, the files read, the commands run and the final reply stay. `--redact` takes out any other word.
- A missing or broken `answers.json` scores 0; the run still writes a result file.
- Then submit the file as below. Running in a clone? Copy it to `benchmark/results/` for a pull request.
- Ran the steps by hand (`bench prepare`, your agent, `bench score`)? `bench score` prints the same issue form link.

## Any vision model behind an OpenAI-compatible API

A plain vision model has no tools, so it can only run the frames track. `--agent openai` makes `bench run` itself
the runner: it sends the model the stills and reads the answers from its reply. It works with anything that serves
`POST <base>/chat/completions` with image inputs: Ollama, LM Studio, vLLM, llama.cpp server, OpenRouter and the
like. A local model costs nothing to run.

With [Ollama](https://ollama.com) (no account needed):

```bash
ollama pull qwen3-vl:4b-instruct-q4_K_M
sports-video-coach bench run --agent openai --track frames --suite svc-bench-3 \
  --base-url http://localhost:11434/v1 --model qwen3-vl:4b-instruct-q4_K_M
```

A hosted API takes its key from an environment variable you name, e.g. `--base-url https://openrouter.ai/api/v1
--api-key-env OPENROUTER_API_KEY`. The key goes only into the `Authorization` header and is never written to any
file.

- **One request per task.** Each request holds the frames-track rules, that task's section of `TASKS.md` and that
  task's contact sheets (11 to 27 on `svc-bench-3`) as base64 JPEGs. Small local models have small contexts, so the
  tasks are not sent together. The full-size stills and the truth are never sent; the truth is not in the prepared
  folder at all.
- **The answer** is the last ```` ```json ```` block of each reply (`{"<task id>": answer}`). A reply without one,
  or a failed request, leaves that task `null` (it scores 0); `run.json` counts requests and failures.
- **Options:** `--temperature` (0), `--max-tokens` (4096), `--image-max-side PX` (scale the sheets down first;
  default as drawn, 1280 x 820), `--timeout` (for the whole run; a task not sent by then stays `null`).
- **Context.** Ollama scales every image itself (a sheet costs about 1,070 prompt tokens with qwen3-vl) and loads a
  model with a 4096-token context by default, too small for 27 sheets. Start the server with a bigger one, e.g.
  `OLLAMA_CONTEXT_LENGTH=40960 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve`, and say so with
  `--settings`. A fresh seed can draw more sheets (30 for one task, about 33,200 tokens), so 32768 is not always
  enough; a request over the context fails with HTTP 400 and its task stays `null`.
- **What the result records.** `settings` always says how the model was asked: the endpoint kind, the number of
  requests and images per request, the image size, temperature and max_tokens; anything in `--settings` is added
  after it. An Ollama server also names itself: the agent is `Ollama` with its version, and the weights'
  quantization and size (from `/api/show`) go into `settings`. Any other server shows as `OpenAI-compatible API`;
  use `--name` for a better label.
- **Transcript.** `transcript.jsonl` holds every request without its image bytes (file name, byte size and pixel
  size of each image instead) and every reply text; `transcript.redacted.jsonl` is the copy to publish.

## Submit your run

Pick one:

- **Pull request:** add your file to `benchmark/results/` as `<date>-<agent>-<model>.json` (lower case, `-` for
  spaces; `bench score` adds the suite for `svc-bench-2` and `svc-bench-3`, and `-frames` for the frames track) and fill the benchmark part of the PR template.
  Within minutes the pull request's checks show its score: open the `tests` run, then its Summary tab. For each
  added or changed result file it says whether the file validates, and gives the suite, track, contender, total,
  above chance, time, cost, where it would rank on its table, and per task your answer, the truth, the score and
  what was missed, with the same numbers the leaderboard page will show. A file that does not validate fails the
  check and the summary says why. To see the same report before you open the pull request:
  `sports-video-coach bench report benchmark/results/<your file>.json` (Markdown on stdout, exit 1 if invalid).
- **Issue form:** paste the file into the
  [benchmark result form](https://github.com/mariusDing/sports-video-coach/issues/new?template=benchmark_result.yml);
  a maintainer adds it. This is the path that needs no git.

An evidence link (a gist, a transcript, a log) is optional but makes your row easier to trust. The maintainer's
own runs keep their redacted transcripts in `benchmark/transcripts/<result-stem>.jsonl` (gzipped over 300 KB)
and link them; the page labels such a link "transcript".

## How rows are checked

- CI runs `sports-video-coach bench validate benchmark/results/*.json` on every pull request.
- On a pull request, CI also runs `sports-video-coach bench report` on the result files the pull request adds or
  changes (`git diff` against the base branch) and writes the Markdown into the run's Summary tab. The job is
  read-only (`contents: read`, no comment, no secret), so a pull request from a fork gets it too.
- `validate` re-scores each file from its `answer` fields against the suite's truth and rejects a file whose
  scores differ.
- The leaderboard page is rebuilt from the folder by `bench page` on every push to master. A file that does not
  parse is listed on the page as skipped, never silently dropped.
- A result file with a `seed` is re-scored against the truth rebuilt from that seed; the published truth or another
  seed's does not pass.
- Under each suite's table of runs, a folded "Where each contender fails" block lists, per task, the truth (from
  the suite, not from the result file), each run's stored answer, its score recomputed from the two, and a short
  line of what was missed: off by how much for counts and rates, which events were missed or extra (with their
  times) for timestamps, which shots were called wrong for outcomes. The blind baseline is left out. A task row
  without a stored answer says "answer not recorded" and keeps its stored score.
- Each Summary groups runs by agent, model and settings; a run whose settings only add a note to another run's
  (such as `; killed at the 1700 s time limit ...`) counts with that contender, so a failed run lowers its mean
  instead of standing apart. Equal means share a rank, marked `=`. Mean time and cost are over the runs that
  recorded them (`(k of n)` when only some did).
- The chips name the newest run's date. Under them, a folded "Before you trust this" block answers what a skeptic asks first, counted from the
  result files at build time: who submitted the runs, how many loaded the submitter's own agent config, how many
  contenders ran once and the largest gap between two runs with the same settings, the highest score the blind
  guess gets on one task, how many runs link evidence, and how many recorded time and cost. The Method section
  shows the exact prompt `bench run` sends.
- The same build draws `card.png`, the page's link preview image (`og:image`): per suite and track, the top
  contenders' mean above chance from the page's Summary tables (needs matplotlib; without it there is no card).
- It also draws a short clip at the top of the page, `clip.mp4` and `clip.gif` (about 18 s, `bench/clip.py`): the
  `svc-bench-3` juggling video as contenders get it, the frames-track stills around its first double touch (two
  touches 0.24 s apart) zoomed and slowed, then the truth against each run's answer on that task. Every number
  comes from the suite or the result files (tests check it); needs Pillow (with matplotlib) and ffmpeg, else no
  clip. For a post, `python -m sports_video_coach.bench.clip benchmark/results <dir>` draws it alone.
- "Count it yourself" (`#count`, `bench/count.py`), right after the first-screen links: the visitor plays
  `count.mp4`, the `svc-bench-3` juggling video exactly as contenders got it (no answer drawn on it, about 400 KB,
  needs ffmpeg only), types a count, and only then sees the truth, every stored answer to that task from the
  result files, the blind guess and a line to copy. Without JavaScript the answers sit behind a closed
  "count, then open" fold. The answer clip moves inside that fold. No tracking, no network calls.

## Honesty notes

- The benchmark and its page were built with a coding agent.
- Every row is reproducible: same suite, same commands, scores recomputed from the answers.
- The author wrote the tool, drew the suites and submitted the first runs, with their own agent config loaded
  where the Settings column says so. No outside runs yet; the page counts this from the files.
- `svc-bench-2` and `svc-bench-3` were each built after models scored 1.0 on the suite before, so the author knew
  which models already saturated it.
- Settings are not equalized across agents (Codex ran at reasoning effort xhigh, Claude Code at its default);
  each row names its own.
- The no-peeking rule is honour-based: CI re-scores the answers but does not read the transcripts. Every
  maintainer run links its redacted transcript (`benchmark/transcripts/`), so anyone can check which tools
  existed, which files the agent opened and what it replied. Redaction drops images, home folders, the runner's
  hook output and config lists; the six blind-guess baselines ran no agent and have none.
- Fresh seeds (`--seed`) reduce the effect of memorising the public answers, for `svc-bench-3` only (a seed
  becomes public too once its result file is published); `svc-bench-1` and
  `-2` have none.
- Most contenders ran once. Two Sonnet 5.5 runs with the same command on `svc-bench-3` frames differed by 0.224
  above chance, so smaller gaps between single runs are within noise.
- Failed and killed runs stay on the board and count in their contender's mean.
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

`suite` is `svc-bench-1`, `svc-bench-2` or `svc-bench-3`; the task ids must be that suite's. `track` is `"frames"` for a
frames-only run and absent for the code track. `seed` (an integer) marks a run drawn from a fresh seed of
`svc-bench-3`; absent for the published suite. Unknown fields are kept.
