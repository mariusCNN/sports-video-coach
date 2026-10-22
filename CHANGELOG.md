# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## Unreleased

### Changed

- A finished generic run also lists the narration MP3s and the clips folder, not only the page and the explained video.

## 0.2.2 - 2026-10-23

### Added

- The demo's output is online (GitHub Pages, rebuilt by CI from `sports-video-coach demo`): the coaching page with clips and narration, and the explained videos. The README links it, so you can see the deliverables before installing.
- `sports-video-coach guide [<name>]` prints a writing guide (review, report, narration, film) or lists them, for agents that cannot read the install folder the step names.
- `frames --start 0:12 --end 0:15 --every 0.2` cuts dense sheets of one moment only, for a close look; the review guide suggests it.

### Changed

- A second video of the same sport on the same day starts its own analysis folder (`<date>-2`) instead of taking over the first one's.
- The film guide spells out the freeze line syntax (`> 0:12.5 0.45,0.80 "label"`, no brackets; arrows with `->`).
- `run --help` is written for users: the three ways to call it, the exit codes, and every start option (`--lang`, `--focus`, `--every`, ...) and driver option (`--status`, `--redo`, ...).
- A new analysis picks the contact-sheet interval from the video length: a tile every 0.5 s up to 30 s, 1 s up to 2 min, else 2 s (it was always 2 s, too sparse for a short drill). `--every` still overrides it, and a second start keeps the interval already used.
- Contact-sheet labels show tenths (`00:12.5`) when tiles are under a second apart; the guides say `mm:ss.s` works in reviews, clips and freezes.
- `film --dry` asks for a shorter film when the source video is under a minute (from about twice its length) instead of always 2-4 min.
- The narration guide has the speaking rates to get the "about N minutes" sentence right before rendering.
- Contact-sheet tiles under a second apart fall on whole tenths (00:00.3, 00:00.8, ...: even gaps, exact labels); a `--start` window starts at `--start`.
- A freeze line with two labels says "only one label per freeze line" instead of "cannot read"; the film guide says so, and gives the short-source length as 2-4x the source (a 22 s drill: 45-90 s).
- The review step names the close-look command; README "For agents" mentions `--lang`; `html`'s help no longer reads as if Chinese were required; the no-browser QA note says to state that the 390 px layout was not checked.

## 0.2.1 - 2026-10-23

### Fixed

- The explained video's title card on a generic unit shows the report's heading instead of the folder name.
- Agent step instructions print paths with forward slashes only (no `C:\u\run/review` mix on Windows).
- README: the Claude Code install line was wrong (`--marketplace` is no flag): add the marketplace, then `install sports-video-coach@sports-video-coach`. Added `npx skills add` for other Agent Skills clients.
- The `qa` step says why `qa.md` does not count yet (no PASS, no stamp, or files changed after QA with the new stamp) instead of waiting silently.
- README: `demo --offline` makes clips and the page only (it said: without text-to-speech).
- A failed short step says its error is printed just above (it keeps no log); a stopped `demo` says to fix the cause first and offers `--offline`. AGENTS.md: `git status` only in a clone.
- Pages declare an empty favicon, so opening one from a local server logs no 404.
- Narration, the explained video and joining videos no longer fail with `PermissionError` inside a sandboxed agent on Windows (e.g. Codex): work files go to a plain folder next to the output instead of `tempfile`, whose owner-only folders (CPython 3.11.10+ / 3.12.4+) a restricted token cannot open. The work folder is absolute, so a relative unit folder (`run ws/analysis/...`) works too.

### Added

- `sports-video-coach page-check <folder...>`: a static check of a report page for agents with no browser (every local link and anchor resolves, every clip and audio file is linked and readable, no local disk path, a mobile viewport). The qa step mentions it; `demo` uses it for its scripted QA.
- README: a GIF of the demo's explained video.
- README: install from the GitHub ZIP when git is missing or blocked.
- `run` ends with one line naming the deliverables it built and the ones the unit's `artifacts` left out.

## 0.2.0 - 2026-10-23

### sports-video-coach: an agent-first core, basketball as a plugin

- The repo and distribution are now `sports-video-coach` (was hoop-tape-miner; old GitHub links redirect). The sport-agnostic core is the package `sports_video_coach` with its own CLI `sports-video-coach`; basketball is the `basketball` plugin (`hoop_tape_miner`), and `uv run hoop-tape-miner ...`, `/game`, `/train`, `/move`, existing workspace folders and publish links work as before.
- Plugins: built in (`generic`), installed (entry point group `sports_video_coach.plugins`) or local folders (`./plugins`, `<workspace>/plugins`, `$SVC_PLUGIN_PATH`). `sports-video-coach plugins [--json]` lists what each analyses and when to use it; plugin stages are addressed as `<plugin>:<stage>`. A plugin declares unit kinds, stages, prompts and optional page / film / publish hooks (`docs/plugins.md`).
- `generic` plugin for any sport, no computer vision: `sports-video-coach run <video> --sport tennis` makes contact sheets (`frames`), waits for the agent's film review (`review.json`, checked) and report, then builds clips, narration, the page, QA and the explained video. `new-plugin <name>` copies it as the start of a new sport's plugin.
- Selectable deliverables: `"artifacts": [...]` in the unit json or the profile picks `clips`, `narration`, `html`, `qa`, `publish`, `film` (default all; `qa` comes with `html`).
- Light install: the core needs only ffmpeg, OpenCV, edge-tts and markdown-it (`uv tool install git+https://github.com/mariusDing/sports-video-coach`); basketball tracking is the `basketball` extra, installed by `uv sync` in a clone as before.
- Agent-first docs: `AGENTS.md` is the contract (run loop, choosing a plugin, star etiquette: ask the user once after a good result, never star automatically), an Agent Skill (`skills/sports-video-coach/SKILL.md`), a Claude Code plugin marketplace (`.claude-plugin/`), `/analyze`, and `docs/architecture.md`. The basketball README moved to `docs/basketball.md`.
- `SVC_WORKSPACE` and `profile.json` (falling back to `HOOP_WORKSPACE` and `team.json`).

### Changed

- The page renderer (`html`) moved into the core (`sports_video_coach.render_html`); basketball's score / season / training / movement bands, Four Factors, shot chart, playlists and tracking sections come from the plugin's `PageHooks`, and a folder no plugin owns gets a plain band (title, date, sport). Basketball pages are unchanged.
- `publish` moved into the core (`sports_video_coach.publish`): any plugin's reports, or a folder no plugin owns, get a stable link and a hub entry; the hub rules (player pages hidden, seasons pinned, program app at /p/) come from each plugin's `SiteHooks`. Existing links in publish.json are unchanged.
- `film` (explained video) moved into the sport-agnostic core: any folder gets clips, pictures, stats and cards with a generic title card; basketball adds `court:` diagrams, 我#7 / 对#11 marks and its title card as plugin hooks; an unknown `<prefix>:` scene now stops with the known prefixes.
- Training program app: exercise cards no longer list the video titles (or a YouTube search link) under the sets; the play button in the card header opens the demos.
- Shot chart redrawn as an NBA.com-style zone chart: correct FIBA court (the 3-point arc was drawn around the wrong centre; free-throw circle, no-charge semicircle and centre circle added), each zone coloured on a blue-to-red points-per-shot scale with a made/att and FG% label, and the shots listed as chips under the court (tap a zone to filter) instead of a grid of dots.

### Added

- `sports-video-coach demo`: every deliverable in about 30 s on the light install, with no agent and no video of your own. It draws a synthetic drill video (a red block running between two cones, no people), copies in a pre-written review, report, narration and film script, and runs the normal pipeline; `--lang en zh`, `--no-film`, `--offline` (clips and the page only).

- Training program app: `program build | check | pull` turns `program.json` (schema `templates/program.example.json`) into a phone page for a month of training, with today's session opened by date (`#d=YYYY-MM-DD` deep links), coach tips per exercise, YouTube demos, a weekly calendar grid with coloured session badges, set logging, game-day plans and a game stat log. `publish` puts a program folder at `/p/<token>/`; on that link the log syncs to `/api/sync/<token>` (Workers KV namespace `<project>-sync`, created on the first deploy, newest copy wins, daily copies for 60 days) so it follows the player across devices, and `program pull` saves it as `progress.json` for analysis. Plan pages send their origin as referrer so YouTube embeds play (error 153 otherwise).
- Shot locate step (`shot-locate`, run steps `locate-sheets` and `shot-locate` after the film review): one sheet per reviewed shot with the court lines and a labelled 1 m grid projected from the calibration; reviewers read the take-off spot and `shot-locate merge` writes `shot.xy` (court metres, with its source and confidence) or `"xy": null` plus a reason into the trips, never a guessed spot. A located spot sets the shot's zone (missed shots also their 2/3 points; the review's values are kept in `zone_review` / `points_review`); spots within 0.5 m of a zone line keep the reviewed zone, and made shots that disagree on 2 vs 3 points are flagged for a decision instead of changed. A shot's attacked half follows the shots around it when the possession's side disagrees with 5 of its 6 neighbours (a shot by the other team inside our possession), and `shot-locate sheets --only N,M` redoes single sheets. `coach-sheets zoom` takes `--grid` and `--header` for other sheet layouts.
- Shot chart: located shots are drawn at their spot on the half court (dot = made, cross = missed, dashed ring = unclear), filtered with the team / zone / player filters; a click plays the shot's clip, and a line under the court says how many of the shots shown are located.
- The published team hub has the reports' 中文 / EN switch: each game shows its title in the chosen language (a report without that language keeps its own title), the choice is shared with the report pages, and the reports open in it.
- Four Factors: `coach-summary --official` adds `four_factors` (eFG%, TOV% split live/dead, ORB%, FT rate as FTM/FGA, possessions, points per possession, and the deciding factor by Dean Oliver's weights, "unclear" below 15 possessions a side) and `ppp` by trip type (transition, half court, second chance, after a live-ball turnover) to summary.json. The team page shows a Four Factors panel. The trip schema has optional `transition` and `turnover_kind` (`live` / `dead`) fields that the film review brief asks for; without them, a trip whose first shot or foul comes within 8 s counts as transition (our rule), otherwise unknown.
- Clickable zone shot chart on the team and player pages from the reviewed shots (filters by team, player and half; an unclear make/miss is shown as unclear; a dot plays its clip), and automatic per-player and per-theme playlists (turnovers, live-ball turnovers, fouls, their scores, transition defence, offensive rebounds; at most 12 clips each, played in sequence). `clips` cuts these windows once and `publish` copies them.
- Honest coach gates: `coach-check` and the run's `film-review` step require every possession of a part to be covered with no gap over 20 s (our rule), and a made shot, made free throw or foul to name its jersey or carry `"unknown: <why>"`. Insights must cite an existing pid/trip for every evidence time and every number must resolve in its source file (`"unknown"` allowed). A new `critic` run step needs a separate critic's `critic.json` that lists the sheets it re-opened, signed by `coach-insights critic` (editing insights.json afterwards breaks the signature). A new `coach-eval` run step gates on points recall and precision of at least 0.8 for both teams (our rule), warns on a drop against the previous eval and shows in `run --status`. Games finished before these gates get a note naming what is now required.

- Movement sessions: `move` (Claude Code: `/move`) turns windows of any video into a movement page (running form, force pattern, layup approach, stops), an explained video and `plan.json` (drills in sessions A-D, re-tests, fuel by day type, recovery). Stages `move-new` (segments joined into one reel), `move-scan` (pose at native fps up to 120 real fps; foot contacts, trunk lean, shin angle, touchdown distance, contact time, cadence, layup penultimate step and take-off, speed-dribble numbers), `move-sheets` (skeleton overlay reel, key-frame sheets, label strips, review briefs) and `move-summary` (findings per KB entry, progress). Numbers come only from side-view segments and are shown only when the scan's foot contacts match a hand-labelled check; running faults seen from other views stay hypotheses for a side-view re-shoot. With a trainer or defender in frame, `move-scan` writes numbered identity frames (`who_<id>.jpg`) for an agent to pick the player, then follows that person along the cheapest path over the detections (movement plus a clothing-colour model from every pick in the session); extra picks (`"more"`, sheet `who_<id>.more.jpg`) pin the path at contacts, and `--repick` re-chooses without re-running the models. Reviewers mark stretches where the crop is on someone else as `wrong_person`, and the summary drops findings inside them. Knowledge bases `prompts/movement_kb.md` (sprinting, transitions, layup, stopping and landing, capacity; claims the player brings graded; reference bands; filming protocol; re-tests; pain gate) and `prompts/fuel_recovery_kb.md` (energy by day type, protein, carbs, game day, hydration, sleep, recovery, Chinese-food menus); writing guide `prompts/movement_report.md`.
- 2D gait, layup and dribble metrics from pose keypoints (`gait.py`).
- Individual skill and conditioning knowledge base `prompts/skill_kb.md` (19 entries: shooting, finishing, handling, one-on-one, defence; energy demands, repeated sprints, landing, strength, warm-up, fatigue, recovery), each with an observable symptom, cause, cue, drill and a `plan.json`-ready target, sourced from FIBA WABC manuals and studies. Training reviewers tag form notes with its slugs; the training report adds "what to fix and how" and "between sessions: skill and conditioning" (`plan.json` `between_sessions`).
- Training sessions with a trainer or partner in frame: `train-scan --follow ball` (or `"follow": "ball"` in `session.json`) follows whoever holds the ball instead of the nearest box, so contact in 1-on-1 drills no longer swaps the player; `"look"` tells the reviewers who the player is. The scan now keeps every person and ball in `run/pose_all.npz`, and `train-scan --repick` chooses the player again without re-running the models.
- Personal training sessions: `train <phone videos>` (Claude Code: `/train`) turns one player's solo workout into a session page, an explained video and `plan.json` for next time. New stages `train-new` (joins the phone files), `train-scan` (YOLO pose and ball: shot and finish candidates with knee bend, elbow angles, dip-to-release and jump; dribble segments), `train-sheets` (rim probe, rep sheets with a rim filmstrip, briefs) and `train-summary` (percentages by zone, spot, type and hand, miss directions, form for makes vs misses, dribbling, last session's targets checked, progress over sessions, figures). Agents judge make or miss and write the report with `prompts/training_review_brief.md` and `prompts/training_report.md`. `html` shows a training band instead of the score, `film` a training title card, and `publish` gives a session its own link without listing it on the team hub.
- `narrate --tight` trims the silence the TTS voice leaves around each paragraph, so `--gap` is the real pause between cues (e.g. `--gap 0.4` for a tight on-court loop; before, every gap was about a second longer than asked).
- `coach-features` stage (run step `features`, after the film review): per-trip numbers measured from the court tracks (players back on defence 2 s into the opponent's trip, offensive spacing, paint crowd, standing still, time to cross half court) in `features.json`, and a ball-track quality report. The insights writer quotes these numbers and `coach-insights check` verifies them.
- `coach-sheets event`: fact-check sheets at 4 fps around each official score event (reaching back over the league feed's 10-30 s lag) and each reviewed foul, with the likely shooter or fouler boxed thicker and a short question file per window (who shot, made, 2/3/FT, foul by/on/type), so a reviewer can confirm the facts on just the frames that matter. `coach-sheets event-merge` writes a new review folder with those answers merged into the trips (earlier values kept) and a change log.
- Coaching insights step with a critic: after the summary, `run` waits for `insights.json`, written by a writer subagent (`prompts/coach_insights.md`: patterns seen on at least two trips, the mechanism from the coaching knowledge base, one rule, one drill, a measurable next-game target) and checked by a critic subagent (`prompts/coach_critic.md`) that re-opens the cited sheets and drops what the film does not show. The new `coach-insights check` rejects evidence times outside any trip, unknown knowledge-base entries, numbers that differ from `summary.json` and insights without a critic verdict; `coach-insights ab` builds a blind A/B rating sheet against the memo conclusions. The coach report's conclusions and practice plan now come from `insights.json`. Optional team-profile key `coach_library` points the writer to a local folder of coaching texts.
- `coach-eval` stage: scores a film review against the league feed (points recall and precision against the score flow, per-player points and fouls against the box score, result values outside the brief) and lints coaching conclusions for evidence times, reasons, drills and targets. Results go to `<review>/eval/<label>.json` and a running `eval/log.md`, so each change to the coach review can be compared with the last.
- `coach-check` stage and trip schema v2: film-review trips use a fixed `result` list plus `shot`, `fts` and `foul` objects with jersey fields and evidence times; `coach-check` lists every invalid trip, and `--migrate` converts v1 reviews without losing their free text. `run` treats a review part as done only when it passes, the brief asks reviewers to run the check before replying, and `coach-eval` / `coach-summary` read v2 (`coach-eval` also reports official shot and free-throw events matched one-to-one).
- One-command run: `run <league game url | game folder>` drives every stage in order, resumes from the outputs that exist, stops with exit 3 where the agent must judge (calibration points, cluster names, film review, writing, QA) and publishes only with `--publish`. Claude Code users type `/game <url>`.
- `fetch` stage: reads a Glory League game (teams, rosters, final and halftime score, periods, box score, score flow) over its API, downloads the league video (resumable) and writes `game.json` and `official.json`. Our team, focus player, colours, languages and the league secrets file come from a team profile `workspace/team.json` (`templates/team.example.json`); heavy files can live under its `media_root`.
- Calibration without a GUI: `calibrate --grid` writes frames with a pixel grid and a numbered landmark map for an agent to read; `calibrate --points` solves them and prints PASS/WEAK per frame with the worst points (exit 2 while any frame is weak).
- `film --crf` (default 23) and a poster `film.<lang>.jpg` next to each explained video.
- Film clips in reports: mark a play with `![caption](clip:mm:ss-mm:ss)`, cut it with the new `clips` stage, and the HTML page shows a numbered player with a slow-motion button next to the analysis (embedded in `--share` files). Writing guides say which plays deserve a clip.
- Explained video: the new `film` stage turns `film.<lang>.md` into one MP4 where the narration plays over chapter cards, charts and the report's clips, with burned-in subtitles; clips replay at half speed when the explanation is longer than the play. Writing guide: `prompts/film.md`. The film can freeze a clip and draw on it: `> 03:13 我#7 对#11 "label"` dims the frame, rings the players (found in the CV tracks, or placed by hand) and adds arrows. It also has animated court diagrams (`![caption](court:plays/x.json)`), big-number stat scenes (`stat:`) and chapter cards over blurred game footage (` · ` splits a title into lines). A `>` line on its own resumes the clip while the narration goes on. Speech has its trailing silence trimmed, so scene changes no longer pause.
- `publish` stage: builds a private-link website from report folders (audio and clips as files, no local paths) and deploys it to Cloudflare (Workers static assets) for free with `--deploy`. Each report keeps one random URL across updates, and team reports are listed on a hub page.

- `ball-track`, `rim-scan` and `shot-proposals` stages (also `run` steps before the coach sheets): a smoothed ball track and shot-attempt candidates at each rim from the ball arc, labelled made only when an official score event matches. Coach sheets draw the ball trail and a "CV attempt?" marker on the rim and list `cv_attempts` per possession for reviewers to confirm; they are candidates, never results.
- `season` stage: one page per season from every game folder (results, points per half, Four Factors per game with small charts, last game's targets checked in the next game, recurring coaching themes, per-player on/off and 5-player lineups pooled with shrinkage and small-sample flags); missing data is listed, never filled in. `season --brief [--opponent <name>]` writes a pre-game listen script for `narrate --script`, and `publish` pins the season page at the top of the team hub with its own stable link.
- `scout --opponent <name>`: a rematch dossier per opponent (`scout.json` + `scout.md`) with record, their top scorers by jersey, pooled Four Factors and points per trip, what decided each game and our past targets checked against the next game; `new-game --dossier` refreshes it.
- Training sessions start from the last game: `train-new` stores that game's insights for the player's jersey (`game_focus`), and `train-summary` adds a "Game vs practice" make-rate table with sample-size labels.
- Insights may carry `target_check` (`{number, max and/or min}`, the number also listed in `numbers`); the season page and the scout mark it met or missed in the next game.
- `load` stage: running load per stint (distance, sprints, top speed, high-speed distance) with tracking coverage; low-coverage stints are flagged and gaps never filled. Shown on the player page.
- `matchups` stage: defender distance at each reviewed shot (tight / contested / open / unknown) and who guarded whom, weighted by time; both pages get a "Matchups and shot defence" section.
- `posters` stage: clip posters ring the players the clip is about, dim the rest and draw an arrow from fouler to fouled; pages use the marked poster.
- `reels` stage: a 9:16 phone reel of one player's clips, the crop following the player, with a title card; never published.
- `run` runs `load` and `matchups` before the fact sheets and `posters` right after `clips`; games whose pages are already built skip them.
- `stitch` stage (a `run` step between `jersey` and `analyze`): splits and joins tracklets into player chains (at most five per team) and pools jersey reads per chain; `analyze` uses it. Games analysed before keep their possessions unless it is run by hand.
- `track-eval` stage: label-free tracking proxies from a run, plus HOTA / IDF1 against labelled MOT clips (`--export-mot` writes pre-labels).
- `jersey` reads a pose torso crop behind a legibility gate and weights votes by read confidence (needs the yolo11s-pose weights); `tracks --tracking joint` tracks both teams together as an option.

### Changed

- Training sessions: `"jersey": null` in `session.json` marks a guest (e.g. a friend filmed in the same video); no game focus or game-vs-practice rates are linked to them.
- `run`, `train` and `move` share one driver (`pipeline.py`, with `media.py` and `timefmt.py` helpers). A step whose inputs or settings changed re-runs by itself, `--redo X` also re-runs the steps after X, and `--status` marks them `(stale: ...)`. Old folders count as done; their freshness records are written on the next run, never by `--status` or `--dry`. `clips` re-cuts with `--force` when its video changes; `move-scan` and `move-sheets` re-run with `--force`.
- Default deliverables are the team page, the focus player's page (with narration and clips) and the explained video; the opponent dossier, court cues, replay, CV figures, event review and the single-file share are optional extras. `new-game` creates the opponent dossier only with `--dossier`.
- The playbook starts with the one-command run; step numbers changed.
- HTML pages carry `noindex, nofollow`.
- Coaching knowledge base checked page by page against its sources: the press-break entry now separates trap/zone presses (three passing options) from man-to-man presses (clear out, or a forward cuts back), page references were corrected (pick-and-roll show, help the helper, pack-line weaknesses, last-possession timing), Free Throw Golf scoring was fixed, and the team's own rules and all target and success numbers are labelled as "our rule" / trial values. The audience is an adult rec team.
- QA must be redone after any edit: `qa.md` needs `PASS` plus the `checked: <stamp>` line that `run` prints at the QA step (older `qa.md` files are asked for again).
- A report counts as published only after a successful `--deploy`; `publish.json` is written atomically with a `.bak`, and a failed wrangler run is retried on the next `run --publish` (links stay the same).
- Publishing is safer: raw HTML in READMEs is shown as text, pages only take media from their own report folder, and the Worker sends Content-Security-Policy, nosniff, no-referrer and noindex headers on every response (live after the next deploy).
- Report languages come from `team.json` `languages` (zh and/or en, default both).
- `train-sheets` refuses to rebuild sheets once review files exist unless `--force` is given (the flag was documented but missing).
- `run <url>` reuses an already-fetched game folder; a re-fetch keeps your own video alignment unless `--force`.
- Movement label checks compare slow-motion clips in real time and only validate segments of the same kind, view, source file and frame rate; other segments are listed as unvalidated and not quoted.
- `move-scan` and `train-scan` caches are keyed by their inputs (video content, window, fps, picks, seed, follow), so a re-run re-picks the player after `who.json` or seed changes; sheets and the overlay are redrawn after a re-pick.

### Fixed

- Report pages no longer load fonts from Google Fonts: no request leaves the page (a privacy promise, and the fonts were blocked in some networks); the page uses the system fonts.
- The page said "About 1 min" for a 47 s recording; under a minute it now gives seconds. `narrate` prints the length of each MP3, so a script's "about N minutes" can be checked without ffprobe.
- Stage logs of a unit made with `--out` outside the workspace go to its `run/logs/` instead of a new `workspace/` folder in the current directory.
- `run --status` shows `publish` as `skip (only with --publish)` instead of a missing step; `film --dry` notes when the film is outside the guide's 2-4 min.
- The generic film-review brief says what to do when a video has nothing to coach: tell the user instead of inventing moments.
- `run --status` showed `clips` as done before any report existed (nothing to cut yet counted as all cut), which misled a new session picking up a unit.
- In the light install, a basketball stage (or `html` on a basketball folder) crashed with a `ModuleNotFoundError` traceback; it now says which package is missing, and `sports-video-coach plugins` marks a plugin whose packages are not installed and how to get them (`missing` / `install` in `--json`).
- Glory League box scores with two players wearing the same number kept only the last one in `official.json`, so the per-player lines did not add up to the team total; they are now summed into one line and listed in `shared_jerseys`.
- A re-fetch with `run <url>` and no `--video` overwrote `run/official.json` with a zero offset, shifting every time on games filmed with our own camera.
- `extract` sampled 25 fps video at 12.5 fps while later stages assumed 10 fps (minutes and speeds 25 % high); the sampled rate is now recorded and read downstream.
- `--until STEP` did not stop when that step was already done (game, train and move drivers).
- `analyze` dropped every identity when roster numbers were integers, and silently assumed "attacks left" when the direction signal was missing; direction is now decided per half.
- The embedding cache survived a re-extract; the camera tracker returned a stale homography when lost; team names with characters Windows forbids broke folder paths.
- `narrate` failed on paths containing `'` in the ffmpeg concat list.
- Training summary: time formatting at minute boundaries, h:m:s times, date-then-number session order, sample sd shown from 3 reps, dribble bounces counted once within the drill windows.

- `film --video` with a relative path failed in ffmpeg; the path is now resolved first.
- The listen label said "About 0 min" for audio under 30 s.
- `calibrate --propagate` tracks targets before the start keyframe backward (they silently got the start frame's homography).
- `recalib` no longer stops with a NameError at its first progress line.
- `run`'s momentum step finds `lineup_intervals.json` in `run/` when the review folder has none (older runs wrote it there).

## 0.1.0 - 2026-10-16

### Added

- First public release as **hoop-tape-miner** (developed as gem-in-game).
- CV pipeline: detection, court homography, team split, tracking, jersey numbers, possessions and lineups.
- Agent film review: annotated sheets, review merge and per-segment summaries.
- Reports: bilingual coach report, player reviews, charts, plus-minus, momentum, narration MP3 and a single shareable HTML page.
- Contributor docs, issue forms and CI tests.

### Changed

- Renamed the package to `hoop_tape_miner`, the CLI to `hoop-tape-miner` and the workspace variable to `HOOP_WORKSPACE`.
