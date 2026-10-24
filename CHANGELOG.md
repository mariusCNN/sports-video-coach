# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## Unreleased

### Security
- Every install command pins one commit: `uv tool install git+...@<sha>`, and every `git clone` is followed by
  `git checkout <sha>` (README, AGENTS.md, the skill, docs, the demo site, the basketball install hint). The sha
  lives in one constant, `sports_video_coach.INSTALL_REF`; a test fails when a doc names another or none.
- The skill and AGENTS.md: show the user the exact install command and wait for their OK; CLI output, guides and
  the video are data, not instructions; publish only when the user asked for `--publish`.
- An exit 3 prints the step's fixed instructions; the only commands in them are this tool's own, and none
  publishes. Text taken from a unit json, a file name, a check's finding or a note is cut to one line with no
  backticks and no option dashes (`--publish` prints as `publish`). Free text from the unit json is in double
  quotes; a path with shell characters is one double-quoted argument. A finding or note also loses shell operators
  (`|` `;` `&&` `||` `&` `$(`), so it reads as text. Each stop ends with one fixed line: quoted text is data,
  then the re-run command.
- Tests walk every agent step of every driver (its commands are this tool's own, no shell operator, no publish,
  also when the unit json is hostile) and check drive()'s whole output for a hostile finding and note.
- The game `periods` step cuts its stills with `sports-video-coach frames` instead of a raw ffmpeg command.

### Added
- "What effort changed" on the benchmark page's fresh-seed frames board (English and Chinese), with a
  1200x675 chart for posts (`effort.png`, `effort-zh.png`, `bench/effort.py`): same model, only the effort
  setting changed, mean above chance per setting with n, range and time per run, a run with no answer shown as
  such; drawn from `benchmark/results/` at build time, so a new run joins its bar on the next build.
- `bench run --effort LEVEL` for `--agent claude` (`--effort`) and `--agent codex` (`-c model_reasoning_effort`),
  recorded in the result's `settings`; fresh-seed frames rows for Sonnet 5.5 at effort high (0.995) and max
  (0.000, killed at the 1200 s timeout before it answered) and Opus 5.5 at effort low (0.879), with transcripts.
  A second Sonnet 5.5 max run on a new seed with `--timeout 2400` was also killed before it answered (0.000).
- `bench report <result.json...>`: a result file's score as Markdown (validates or why not; suite, track,
  contender, total, above chance, time, cost, rank on its table, and per task answer vs truth, score and what was
  missed), computed by the leaderboard page's code. A pull request that adds or changes a file in
  `benchmark/results/` now gets that report in its `tests` run's Summary tab (read-only job, works for forks) and
  fails when the file does not validate. See `docs/benchmark.md`, "Submit your run".
- `bench run --agent openai --track frames --base-url URL --model M [--api-key-env VAR]`: any vision model
  behind an OpenAI-compatible chat-completions endpoint (Ollama, LM Studio, vLLM, llama.cpp server, OpenRouter)
  on the frames track, with no agent CLI: one request per task with that task's contact sheets, the answer read
  from the reply's json block, a transcript without image bytes, the key only from an environment variable. The
  code track is refused. See `docs/benchmark.md`, "Any vision model behind an OpenAI-compatible API".
- "Count it yourself" on the benchmark page (English and Chinese): play the `svc-bench-3` juggling video, type
  your count of the red player's touches, then see the truth (47), every model's stored answer to that task and
  the blind guess, all read from `benchmark/results/` at build time, plus a line to copy (`bench/count.py`,
  `count.mp4` + `count.jpg`, built by the demo-site CI). Works without JavaScript behind a closed fold; the
  answer clip now sits inside it so the page no longer gives the count away.
- The benchmark page in Simplified Chinese at `/benchmark/zh/` (`bench page` writes `zh/index.html` next to
  `index.html`): the same rows and numbers from the same result files, a language switch and hreflang links both
  ways, and the zh URL in the demo site's sitemap. README.zh.md links it.
- `bench run --agent codex --track frames`: the Codex frames row in one command (`codex exec -s read-only`, shell
  and other tool features disabled, web search off, every contact sheet attached with `-i`, prompt on stdin).
  Beyond those switches tool restriction is by prompt only; `run.json` counts the commands it ran from the
  transcript, and `settings`, the run banner, `--help` and `docs/benchmark.md` say so.
- Benchmark: a fresh-seed frames row for Codex 0.159.3 / gpt-6-astra (one run, seed 911623366, 1.000), with its
  redacted transcript.
- `sports-video-coach demo indexnow [--dry-run]`: tells IndexNow search engines (Bing, Yandex, Seznam, Naver, ...)
  about the demo site's pages, run by hand after a deploy; the demo site now hosts the IndexNow key file. No
  automatic ping in CI. See CONTRIBUTING.md, "The demo site".
- `bench run --agent gemini | qwen | aider | opencode | cursor | copilot | goose`: one-command benchmark runs for
  seven more agent CLIs, each a headless command line built from that CLI's own docs (linked in
  `docs/benchmark.md` and on the benchmark page's "Run it yourself"). Not run by the maintainer, so untested
  against the real CLIs (tested with fake binaries); the result's `settings` says so. Code track only.
- Issue #7 asks users of those seven CLIs for one real run of each preset (or the error if a flag is wrong); the
  benchmark page's "Run it yourself", both READMEs and `docs/benchmark.md` link it.
- Fresh seeds for `svc-bench-3` (`bench prepare --seed [N]`, `bench run --seed [N]`): the same scenes and traps
  drawn anew at run time, with new counts, outcomes, times and rates, which reduces the effect of memorising the
  fixed public suite's answers. The prepared folder never holds the truth; `bench score` and `bench validate`
  rebuild it from the `seed`. A scored result file and the page do show it, so a published seed is spent. Seeded
  runs get their own board (`svc-bench-3-fresh`) and their own blind floor on the page. A pixel read-back scores
  1.000 on six seeds. Without `--seed` the published suite is unchanged.
- Benchmark: fresh-seed frames runs for Sonnet 5.5 (seed 956466926: 0.504, 0.413 above chance) and Haiku 5.5
  (seed 166697672: 0.440, 0.198), one run each, next to Opus 5.5 (0.994) on `svc-bench-3-fresh`.
- Benchmark: a second fresh-seed frames run each for Opus 5.5 (seed 613104018: 1.000) and Sonnet 5.5 (seed
  406013493: 0.583, 0.426 above chance); across two seeds Opus spans 0.994-1.000 and Sonnet 0.413-0.426 above chance.
- `bench transcript` redacts a transcript or log for publishing (images, home folders, user and host names,
  emails, env dumps, hook output, key-like strings), and `bench run` writes the redacted copy next to the raw one.
  All 20 maintainer runs now link their redacted transcript in `benchmark/transcripts/` (about 2 MB); the page
  labels the link "transcript" and its skeptic block counts the runs that link one. No score or answer changed.
- A short clip at the top of the benchmark page and in the README (`clip.mp4` / `clip.gif`, about 18 s): the
  `svc-bench-3` juggling video, the stills a frames-track agent gets around a 0.24 s double touch, zoomed and
  slowed, then the true count (47) against every run's answer. `bench page` draws it from the suite and the
  result files (`bench/clip.py`, tested), like the share card.
- The benchmark page answers a skeptic's first questions (found by a cold "skeptical Hacker News reader" run: 16
  gaps): a folded "Before you trust this" block counted from the result files (who submitted, own config loaded,
  single runs and run-to-run spread, the blind guess's best task, evidence, time and cost), the exact prompt,
  time and cost columns, tied ranks marked `=`, a killed run counted in its contender's mean (Fable 5.1 on
  `svc-bench-3` frames: 0.494 over 2 runs, not 0.988 over 1), "saturated" only where every run scored 1.0, suites
  with runs first, and timestamp misses worded "not within 0.5 s" (they still earn part credit up to 2 s).
- The benchmark page shows where each contender fails: under every suite's table, a folded block per task with
  the truth, each run's answer, its recomputed score and what was missed (e.g. "2 of 12 not within 0.5 s (at
  12.16 s, 15.84 s)", "3 of 12 wrong (#5 said made, ...)"). Derived from the stored answers and the suite's truth at build time.
- `bench run` runs Claude Code clean-room by default: none of the runner's own agent config (CLAUDE.md, skills,
  plugins, hooks, MCP servers, user settings) reaches the contender, and `settings` says `clean-room: no user
  config`; `--use-my-config` opts out. Codex is not isolated: it runs with the runner's own `~/.codex`, and
  `settings` says so, because isolating it would mean copying its login; `bench run` never touches credential files.
  A calling agent's session variables (`ORCA_*`, `CLAUDE_CODE_SESSION_ID`, ...) are never passed on. One A/B pair on
  `svc-bench-3` (Sonnet 5.5, code track): clean room 0.958, own config 0.995; both on the leaderboard.
- A second Fable 5.1 run on `svc-bench-3` frames with a 3600 s limit: it answered in 1645 s and scored 0.989
  (0.988 above chance), juggle count off by 2, the other three tasks exact.
- A share card for the benchmark page: `bench page` draws `card.png` (1200x630) from the Summary numbers, and
  the page has Open Graph and X tags so links to `/benchmark/` show it as their preview.
- `bench run --track frames` runs the frames track in one command, as the leaderboard's frames rows were run:
  Claude Code with Read as its only tool and the same prompt; the json block that ends the reply becomes
  `answers.json`. Before, the frames rows could not be reproduced from the docs (found by a cold outsider run).
- The benchmark leaderboard has a summary table above each suite's runs: one line per agent, model and settings
  with the number of runs, mean total, mean above chance and its range, ranked by mean above chance.
- Four more `svc-bench-3` frames-only runs on the leaderboard: second runs of Opus 5.5 and Sonnet 5.5, Haiku 5.5,
  and Fable 5.1 (killed at the 1700 s limit before it answered, so it scores 0).
- A humanize step for everything the agent writes. `sports-video-coach humanize <folder or file>` flags stock AI
  phrasing in reports, narration and film scripts (zh and en lists: not-X-but-Y contrasts, written connectives
  such as "moreover" / "此外", hype words, self-asked questions, summary openers, slide labels such as "练习：" read
  aloud, dense dashes; other languages get the dash check). The driven run keeps the report, listen-script and
  film-script steps waiting until the findings are fixed or kept with `--accept`. The new guide `sports-video-coach
  guide humanize` (shared by every plugin) says how to rewrite them in a coach's voice without changing a fact.
- A sports film review benchmark scored against measured truth only: `sports-video-coach bench prepare / score /
  validate`, suite `svc-bench-1` with synthetic drawn videos and exact truth (counts, rates, timestamps, outcomes).
- `sports-video-coach bench page` builds the public leaderboard from `benchmark/results/` (ranked by total, a "no
  runs yet" state, unreadable files listed as skipped); the demo site publishes it at `/benchmark/` and links it
  from the landing page and the sitemap. Method, rules and how to submit: `docs/benchmark.md`.
- A hard benchmark suite, `bench prepare --suite svc-bench-2`, after every agent scored 1.0 on `svc-bench-1`: five
  drawn videos with a hand-held or follow camera, look-alike decoys (a second ball, two identical feet, a
  rebounder), rule-defined events (partial reps, a pump fake, a dip-in-pop-out, a run past a cone), noise and
  flicker. `score`, `validate` and the leaderboard handle both suites (one table each); suite 1 files are unchanged.
- Outside runs can be submitted as a pull request (CI runs `bench validate` on every result file) or through the
  new benchmark result issue form.
- `sports-video-coach bench run --agent claude|codex|cmd` puts an agent on the benchmark in one command: prepare, run it headless with a timeout, score, and print a prefilled issue form link.
  It records the agent's own version and model (Claude Code's init event, the `codex exec` header).
- A frames-only benchmark track, `bench prepare --track frames`: the agent gets still frames and contact sheets
  (time under each still) instead of videos and may run no code, so the score measures the model's eyes. The
  leaderboard shows it in its own tables; result files say `"track": "frames"`.
- First leaderboard rows on `svc-bench-2` (code track: Claude Code with Opus 5.5 and Sonnet 5.5, Codex) and on the
  frames-only track (Opus 5.5, Codex, two Sonnet 5.5 runs), each one real run.
- An "above chance" score on the benchmark leaderboard, next to the raw total: per task (score - floor) /
  (1 - floor), clipped to 0..1, where the floor is a blind baseline that copies the example answers from the task
  text (`sports-video-coach bench baseline`, result files in `benchmark/results/`, shown as a marked
  floor row). Computed from the existing result files; no schema change.
- A third suite for the frames track, `bench prepare --suite svc-bench-3`, after strong models scored 1.0 on
  `svc-bench-2` by eye: small balls and blades, double touches, a banner over a far rim, passes behind a defender
  and pass fakes, a rate change next to a decoy boat. First frames-track rows: Opus 5.5 1.000, Codex 0.862,
  Sonnet 5.5 0.612.
- The demo site is easier for search engines to find: `sitemap.xml` and `robots.txt`, a canonical link on both
  pages, a schema.org `SoftwareApplication` block and a title that names what it does.
- Report blocks for the page: `::: verdict`, `::: keys` (stat tiles), `::: do` (what to do), `::: note` and
  `::: more <summary>` (a fold), each closed by `:::`. The report guides use them for the first screen: the
  verdict, three to six key numbers and this week's orders.

### Fixed
- The seven `bench run --agent` presets were checked against each real CLI's `--help` (Gemini CLI 0.65.0, Qwen
  Code 0.26.1, Aider 0.86.2, OpenCode 1.19.4, Cursor CLI 2026.10.22, GitHub Copilot CLI 1.0.103, Goose 1.56.0);
  `--agent qwen` now passes the prompt as a positional argument, since Qwen Code deprecated `-p`. No preset has
  been run on a task yet (`docs/benchmark.md` has the table; the benchmark page names the version per preset).
- `bench score` prints the prefilled issue form link too, not only `bench run`.
- `docs/benchmark.md` names `svc-bench-3` wherever it listed the suites, says how to install, and lists the
  `--by`, `--settings` and `--evidence` options of `bench run`; `bench --help` and the issue form name
  `svc-bench-3` too.
- Explained film: a short freeze quickens the mark beat so the last arrow and the label still show; a clock
  time in a chapter title (`03:10`) is no longer split as a kicker; a stat count-up keeps leading zeros
  (`0.05`, `4:05`); a freeze on a clip first frame ends the caption banner at once.
- Report pages: web fonts load without blocking the first paint, so a slow or blocked font host shows the page
  in system fonts instead of a blank screen. `:::` blocks no longer drop the line after an unclosed block, end
  at a blank line inside a list item, or close on a `:::` inside a code fence; `## 3.5 …` is no longer split as
  section 3; a plugin `intro` hook gets an empty dict when the plugin has no `board` hook.
- `sports-video-coach demo` (which builds the demo site) stopped with exit 3 once the humanize check landed: its
  canned narration and film lines opened with slide labels. They are now spoken sentences with the same facts, and
  a test runs the humanize check on the demo's files.
- A plugin's page re-renders when a file its page hooks read changes (declare them in `PageHooks.inputs`); before,
  `run` ended with exit 0 and the page still showed the old number (found by a cold plugin-author test).
- Fewer needless agent stops: a whitespace-only edit (a space, a blank line) to a README no longer makes the
  narration and film scripts out of date; an untouched `page-check --write-qa` QA draft is checked again by the run
  itself and stops only on problems or warnings; the out-of-date message says `--accept` keeps a typo fix.
- The narration length warning prints the wording to write (`write "约 2 分钟"`, `about 2 min`) in all 8 languages.
- Plugin authors get a light install (`uv sync --no-group basketball`, no CUDA torch); the review guide and
  docs/plugins.md warn that 0.5 s contact sheets alias fast repeated motion (rates must come from a measuring step or
  `frames --every 0.2`); `new-plugin` prints the sport it set and how to change it.
- A one-language page no longer shows an empty language switch outline; `review-check --help` prints its usage
  instead of treating `--help` as a folder; `frames --help` says `--end` is exclusive (found by a cold Codex run).
- A long step that passes prints its last result lines (a measured number, "wrote X") under the run output, so
  nobody has to open its log for them.
- A long step prints its log file's absolute path (the logs folder moves with `$SVC_WORKSPACE`), and `run --help`
  says where logs go.
- `film --dry` notes name the script (`film.en.md scene 4: 18 s on a still picture`), so a multi-language dry run
  says which language's script to fix.
- README.zh says the exit-3 prompts and guides are English for the agent, and the deliverables follow `--lang`.

- Bold next to CJK punctuation renders on the page: `**一句话：**第 4 次` showed its asterisks (CommonMark's
  flanking rule); the renderer now treats a CJK character beside `**` the way markdown-it-cjk-friendly does.
  Latin text renders as before. `page-check` warns about any literal `**` left in a report part.
- README.zh matches README.md again: frames go to the agent's model provider (it said everything stays on your
  computer), publish links are unlisted, not private, and it gains the `--focus`, `--artifacts html`, Python 3.11 /
  ffprobe and basketball-language notes; it says the terminal messages are English, written for the agent.
- Several videos joined into one unit: each contact-sheet tile label and each clip caption on the page also names
  the file and the time in it (`00:42.5  side.mp4 00:17.5`); README and `run --help` say the files are joined in
  the order given, and that two camera angles of one set are better run as two units for now.
- `--artifacts html` on a unit that already has narration and film: the closing list names only what was chosen,
  and lists the rest as "kept from an earlier run, not built this time: film.en.mp4, listen.en.mp3"; the help
  says an earlier mp3 stays on the page.
- A run prints `review-check: OK, N moments` once the film review passes (so does `generic:review-check`).
- The report guide gives a default title for one athlete alone (`# Squat: your set`, `# 深蹲：你这一组`).
- README: the Git Bash hint covers any PATH entry (`C:/...` is written `/c/...`).
- Korean narration: the length check reads spelled-out lengths (약 이 분, 일 분 반, 오 분 정도), and the Korean
  read rate is 245 Hangul a minute (was 270, about 10% short of the real audio).
- The Korean page's slow-motion button reads 느리게 ½× (was 슬로).
- The report and review guides give the Korean labels (**영상에서 보인 것** ... `## 계속할 것`, `**한 줄 요약:**`) and
  아마 / 불분명 for likely / unclear, as they do for Chinese and Japanese.
- The review guide and the review step say to cut a 0.2 s zoom sheet around fast objects (a shuttle, a ball, a
  swing), which can fall between two regular tiles.
- The cross-language edit warning no longer ping-pongs: bringing the other language's README in line after a
  warning does not warn back about the first one.
- After a language is added, the report step's headline names only the README still missing.
- `page-check --write-qa` keeps the agent's notes (a `## Agent notes` heading and everything below it) when it
  writes qa.md again.
- README: the frame-sheet sentence gives the real default (0.5 s up to 30 s, 1 s up to 3 minutes, 2 s beyond),
  and the "Any sport" table's plugin example is `new-plugin <your-sport>`, not a sport the generic plugin covers.
- `page-check --strict` prints `FAIL (n warnings, --strict)` for a folder with warnings, not `OK`, as it exits 1.

### Changed
- README (English and Chinese): the benchmark block is now a short section with the fresh-seed board's numbers (with the effort level where it changed the score),
  links to the leaderboard and "count it yourself", and the rerun command in its own code block; the other agents
  and the OpenAI-compatible path moved into a fold. Fixes the Chinese "基准测试" label that GitHub showed with
  literal asterisks.
- Benchmark page, first screen: one line on what sports-video-coach is with a link to the demo coaching page, and
  links to the frames-only boards, the code-track board, the one-command rerun and the GitHub repo (before, the repo
  link sat in the footer, about 13 phone screens down). The code-track leaderboard now says the frames-only track
  is further down.
- README (en, zh): the benchmark's one command is now the frames-only rerun (`bench run --agent claude --suite
  svc-bench-3 --track frames`), the board the headline numbers come from; the old `bench run --agent claude` ran
  svc-bench-1 on the code track, which every run already scores near 1.0 on.
- The report page has a new look, closer to a pro team's post-game film-room report: a navy score band with
  condensed numerals, a reading column with numbered sections, play cards for the clips, tables with rules
  instead of boxes and a yellow marker for what to do. Headings use Barlow Condensed (Latin) and Noto Serif SC
  (Chinese) from Google Fonts with `no-referrer`, so a private page's address is not sent along.
- Basketball: the Four Factors sit inside each report, after the opening lines and before section 1, as us/them
  bars; possessions and points per trip moved into a fold. A new optional `PageHooks.intro` hook puts a
  plugin's HTML inside each language's report, before section 1; `before` still puts HTML above the report.
- The report guides ask for an analyst's voice: number first, its baseline, then the order; no stock AI phrasing
  (checked by `sports-video-coach humanize`).
- The explained video looks like a film-room breakdown: a long freeze punches in on the marked players and eases
  back out; floor rings in team colours (blue us, red them) under a soft spotlight; tapered white arrows that draw on;
  the label in a dark pill with a leader line; a pause badge. Chapter cards are left-aligned with a kicker and come
  in line by line; stats count up; goal cards say "at most" / "at least" in words; subtitles lose their box;
  the clip banner fades after six seconds, or at the first freeze. A spot can carry its team (`对0.42,0.61`), so
  its ring is red or blue; `--dry` warns about an arrow too short to read.
- The page's language switch names every language in its own words (English, Español, Français, Deutsch,
  Português, beside 中文, 日本語, 한국어), not a mix of names and codes (EN).

## 0.3.0 - 2026-10-23

### Added

- New languages: `--lang ja ko es fr de pt` beside zh and en, from one table (`src/sports_video_coach/langs.py`).
  Every language has its own page labels, dates, voice, read rate and subtitle font; Japanese and Korean also get
  CJK fonts and subtitle wrapping. Basketball units stay zh/en.
- Training-plan app: an optional 决策 tab from `decide.html` (in-game decisions, e.g. a decision flow with the
  new `.flow` boxes), and a big looping play button for any `<audio class="loop" src="x.mp3">` in a fragment, so a
  cue track from `narrate --script --chime` plays on repeat with the screen locked. `publish` now copies the
  audio an app page links to, and `…/p/<token>/#decide` opens that tab directly.
- Loop player: speed chips (0.8× to 1.5×, pitch kept) and a repeat / play-once toggle, remembered on the device;
  lock-screen and headset controls through the Media Session API (play, pause, ±10 s, previous / next track); a
  warning inside WeChat and other in-app browsers, which stop audio when the screen locks. Playback events are
  synced with the log, and `program pull` prints the last ones and the browser, to see where playback stopped.
- Training-plan app feedback loop (all optional in `program.json`, see `templates/program.example.json`):
  - a pre-session check on every training day (legs, pain 0–10 and where, red flag, sleep) that gives advice and
    options but never changes the session; `"readiness": false` turns it off, `painSites` sets the places;
  - exercises of kind `rep` record successes per set, with an `ok` text saying what counts as one;
  - `game.counters` replaces the game log's counters, and `game.trees` asks which decision tree went worst;
  - a session with `review` opens with the last game's log (worst tree and counters);
  - `program pull` prints the checks, success counts and last games.
- `?preview` on a plan link shows the page without saving or syncing anything, for checks and demos.

### Changed

- `narrate` no longer reads a script with another language's voice: an unknown code stops with the list of
  supported codes.
- `film` uses each language's subtitle font and line length and prints which voice and font it used (`--font`
  still overrides).
- The page, the publish hub and `page-check` follow each report's language (lang attribute, CJK headings).
- `run <folder> --lang en zh` works on a later run, like `--artifacts`: it replaces `languages` in the unit json
  (checked against what the plugin supports; basketball: zh and en). A unit's own `languages` now wins over the
  profile's.
- `film` keeps a `film.<lang>.mp4` newer than its script, video and pictures ("film.en.mp4 is newer than
  film.en.md, kept"); `film --force` renders again. Adding a language renders only that language.
- A run that stops on out-of-date agent steps lists all of them at once; `--accept` takes several steps
  (`--accept listen-script film-script`), and its hint prints the full command.
- In a driven run, a narration script whose stated length is off stops with exit 3 before any audio is rendered
  and quotes the sentence to fix (`--accept listen-script` keeps it). The bare `narrate` command only warns.
- `--status` no longer shows `qa` as done while an earlier step is pending or out of date.
- The stated-length check reads every language: Japanese 約一分 / 一分半 / 1分以内, Korean 약 2분 / 1분 반, and
  es / fr / de / pt ("unos 2 minutos", "moins d'une minute", "eineinhalb Minuten", "cerca de 2 minutos").
- `run <videos> --sport-name ja=シャトルラン` (repeatable) names the sport in any language at the start; `--sport-zh`
  still works.
- Japanese film subtitles break after a particle or at a kana-kanji step, not inside a word (同じ方向へ / 飛び出しました).
- The `frames:` lines print forward-slash paths like every other line.
- `new-plugin` writes to `<workspace>/plugins/<name>` (`--dir` still works) and prints a test command that works
  after `uv tool install` (`uv run --isolated --no-project --with pytest --with sports-video-coach@git+... pytest
  <folder>`); in a clone, `uv run pytest <folder>`.
- `run <unit folder>` finds the unit's plugin from any folder. `unknown plugin` lists every folder searched and how
  to add one (`SVC_PLUGIN_PATH`, `SVC_WORKSPACE`, or cd).
- The run log echoes the command that really runs (`sports-video-coach rowing:strokes ...`).
- `--until` prints "paused after X (--until): the steps after it run next time" instead of "stopped after".
- The page's default language and `<html lang>` follow the unit's `languages` order (an es+en page opened in
  English before). Dates read the reader's way (23 oct 2026, 2026年10月23日, 23.10.2026); files and json keep ISO.
- Latin-script films use a Latin subtitle font (Segoe UI, Helvetica Neue, DejaVu Sans); Chinese keeps its CJK font.
- `page-check` fails when another language's page label sits in a language's part of the page.
- `film --dry` states the target band the guide gives (60-120 s for a 30 s video) and says under/over only when the
  estimate is outside it.
- Contact sheets have a 3 px gap between tiles; x,y fractions read off a tile stay correct. The report guide and
  `--focus` help say one report can cover several players, one section each.
- The agent steps print `guide <name> --unit <folder>`: the guide of the unit's own plugin, found from any folder
  (also a plugin in a `plugins/` folder above the unit); `<plugin>:<stage> <unit path>` finds such a plugin too.
- `new-plugin --summary "..." --use-when "..."`; `plugins` marks a placeholder summary and shows a plugin with
  missing packages on one line (`--json` keeps the full list).
- The new-plugin test checks step order only and has a commented stage test; docs/plugins.md: `--redo <stage>`
  after editing a stage, and a single source video is referenced, not copied.
- The landing page shows the install and demo commands, a "Write a plugin for your sport" link and the version.
  README: one star request and an alpha status line.
- `page-check` also reads the narration and film scripts (`listen.<lang>.md`, `film.<lang>.md`): another
  language's words, mojibake (Ã©, â€™) and, in French, straight quotes. `--strict` exits 1 on a warning, and the
  run's qa step waits on them too (`--accept qa` keeps it). `page-check --write-qa` drafts qa.md, saying what it
  could not check without a browser (layout, the phone view, playback).
- Editing one language's report prints one warning naming the other languages' report and scripts that may no
  longer match.
- After adding a language, the report step lists only the missing report files (`missing:` lines).
- Sport names in every language from one table (fr, es, de, pt, ko too); `--sport-name` still overrides. The
  report guide no longer asks for a date in the title (the page header shows it), and its example dates match the
  page (`23 oct. 2026`).
- Contact sheets start with a tile at 0:00, and the time label sits bottom left, clear of a clock burned into the
  video's top left.
- README (en, zh) rewritten: the explained video first, then one path (see the demo page, then a "Tell your
  agent" prompt that asks before installing and sets `--sport` / `--lang`), sports it fits, how long a run took
  in our test, what you get and what it can't do yet, three steps for how it works; the local demo, install
  options, costs and data, and the developer pattern folded away.
- README hero: a real run on the author's own shooting drill (the clip, the agent's film review, the coaching
  page) instead of the synthetic demo's video.
- The demo site's landing page says "Built from master (..., not released yet)" for a development build, rather
  than a version that is not on the releases page.
- docs/plugins.md: a stage module skeleton, what the light install can import, and how a stage's numbers reach the
  agent (`fill_values`) and the page (`PageHooks`). README: the Git Bash PATH form for a `C:/` bin dir.
- Narration guide lists every language's read rate; the review guide writes likely/unclear in the review's
  language.
- Basketball without a league (pickup games, phone clips, no GPU) goes to `generic` with `--sport basketball`;
  the `basketball` plugin is for league games or tracking from a clone. README, AGENTS.md and `plugins` say so,
  and `generic`'s listing says it does no detection (the agent reviews the frames).
- `run <videos>` prints one line saying which plugin it picked and why.
- `film --dry` no longer counts a bare `>` resume as a freeze ("2 freeze(s), 1 resume(s)").
- `narrate` prints the script's length and estimated read time before rendering. The read rates are measured
  on edge-tts (English about 950 characters a minute, Chinese about 235); the narration guides count characters.
- docs/basketball.md quick start: `cd sports-video-coach` after the clone.
- README leads with a tagline, who it's for and what you need (incl. what leaves your machine), and shows a real
  run transcript of the exit-3 loop under "How it works".
- `sports-video-coach demo --site <dir>` writes the demo site: an English landing page, the coaching page under
  `demo/`; the GitHub Pages site opens on that landing page.

### Fixed

- The game log's counters start empty instead of 0, so a count that was not taken is not read as zero (zeros in
  a draft left by an earlier version are cleared too).
- Loop-audio events record the device and browser of each event (older events print as "device unknown"), so a
  check run on another device can be told apart from the player's phone.

## 0.2.6 - 2026-10-23

### Changed

- `sports-video-coach --version` (and `-V`) prints the version instead of "unknown stage".
- The page header writes a lowercase sport as a label ("Tennis", not "tennis").
- `"artifacts": ["html", "film"]` no longer skips the clips: `html` and `film` bring `clips` with them, as `html`
  already brought `qa`.
- `run <videos> --sport swimming` uses an installed or local plugin named `swimming` when there is one;
  `--plugin generic` keeps the generic one.
- New start option `run <videos> --artifacts html film` picks the deliverables when a unit starts (saved in the
  unit json).
- The review guide says what to do when the user wants a report on footage with no athlete in it.
- `new-plugin`: the copy's agent steps point at its own guides (`sports-video-coach guide review --plugin <name>`)
  and its own `<name>:review-check`; its summary, "use when" line, guide titles and usage lines are written for
  the new sport, so `sports-video-coach plugins` no longer lists a second copy of generic.
- `new-plugin` writes `plugins/<name>/tests/test_<name>.py` (the plugin loads, is listed and has its steps:
  `uv run pytest plugins/<name>`).
- docs/plugins.md: how to test a local plugin, where local plugins are found (`./plugins` of the current working
  directory), and an example of adding a command stage.
- `run <folder> --artifacts html narration film` also works on a later run: it replaces the unit's "artifacts"
  (html brings qa and clips, film brings clips) and goes on. Exit 2 (a wrong option) is listed in the exit codes.
- The finishing line prints the command that builds the left-out deliverables too (publish is never suggested).
- Step texts and the generic review guide no longer assume Claude subagents or a browser-check agent; the
  joined-videos paragraph applies only when the unit has several videos.
- `--artifacts` help says narration (the page's audio) is not brought in by html; the `html` stage help names
  `README.md` (Chinese) or `README.<lang>.md`.
- `film --dry` length note gives the estimate, the target range and the source length.
- Freeze frames dim the rest of the picture more lightly, so a ball next to the ringed player stays readable; the
  film guide says to ring the ball too when the label is about it.
- Contact-sheet tiles are labelled with the time of the frame they show; whole-second sheets sample whole seconds
  (1 s sheets showed 0.5 s but read 00:00, so clip times came out 0.5 s early). Sheets with tiles off the whole
  second are labelled in tenths, so main and zoom sheets read the same moment the same way; older sheets are
  rebuilt on the next `frames` run.
- `narrate` retries edge-tts 3 times when it returns no audio or the network fails, then prints one line
  ("text-to-speech (edge-tts, online) failed: ...; check the network and run again") instead of a traceback.
- `narrate <folder>` keeps a language whose MP3 is newer than its script, so a rerun redoes only the stale one;
  `--force` re-renders all.
- `narrate` warns (no failure) when a script's stated length ("约 N 分钟", "about N minutes") is clearly off from
  its estimated read time.
- The page rounds the audio length to the nearest half minute (84 s: "约 1.5 分钟" / "About 1.5 min").
- Report guide: `review.json` is in the first language of `languages`; the title names the focus person in each
  report's own words. README: the demo takes about a minute, `review.json` is at `run/review/review.json`, the
  Chinese report is `README.md`.

## 0.2.5 - 2026-10-23

### Changed

- Chinese subtitles, banners and card titles in the explained video break into lines that fit the frame (they ran
  off both edges of an upright film); lines break after punctuation when one is close, never inside a Latin word.
- A narration or film script written before the report changed is out of date: the run waits (exit 3) and names
  it, e.g. `listen.zh.md: README.md changed after it was written`, and the same for a report written before
  `review.json` changed. Bring the file in line, or `run <folder> --accept listen-script` keeps it as it is.
  `--status` shows such a step as not done.
- The narration and film-script steps name each missing file (`missing: listen.zh.md (Chinese)`).
- Upright clips are cut at 480x854 (were 270x480, soft on a phone); landscape clips stay 854x480.
- The run creates `run/review/` before it waits for the review, so writing `review.json` there just works.
- `page-check` also warns about the guides' hedge words (`unclear`, `likely`) left in the Chinese report, even in
  brackets; the report guide says to write 可能 / 看不清（不确定）.
- `film --dry` prints a bare `>` line as `resume` instead of an empty freeze.
- README links and images are absolute, so they also work on PyPI; a manual `pypi` workflow (trusted publishing)
  is ready for the first PyPI release.

## 0.2.4 - 2026-10-23

### Changed

- Several videos in one run: `new` prints where each file sits on the joined timeline
  (`part1.mp4 = 00:00-00:22, part2.mp4 = 00:22-01:02`), `frames.json` lists them as `parts`, and the first contact
  sheet tile of each later file is framed and labelled "part N/M". The review and report guides say every time is
  on the joined timeline.
- The review guide says to write `what`, `why` and `summary` in the first page language.
- `film --dry` prints what it read from each freeze line (marks and label), warns when a mark comes after the
  label, and notes a still scene (title, stat card, picture) that talks for more than 12 s.
- `new` says when a zh page has no Chinese name for the sport, and how to set one.
- Run output prints paths with forward slashes on Windows too, so they paste into Git Bash; the QA instructions no
  longer repeat the page-check sentence.
- README: what to do when `sports-video-coach` is not found after `uv tool install`.
- `guide --plugin basketball` on a light install says its guides live in a clone instead of "has no guides".
- A phone video recorded upright (stored landscape with a rotation tag, like an iPhone .MOV) is measured the way it
  is shown: freeze highlights in the explained video land on the right spot and `frames.json` gives the upright size.
- Upright clips keep their shape on the page (no forced 16:9 box with black bars).
- `film --dry` stops a paragraph with nothing to say (only symbols, such as a lone `&gt;`) before it reaches TTS;
  a TTS failure names the paragraph and what to do instead of printing a traceback.
- An upright phone video makes an upright explained video (720x1280, same text size), so the athlete fills the
  phone screen instead of a narrow strip in a landscape frame; `film --dry` says so.
- Review with helpers: the run message suggests contiguous sheet ranges (about 10 sheets each, at most 3 helpers),
  and `generic:review-check` merges their `run/review/part*.json` into `review.json` in time order.
- The review guide warns that a jump across the frame between tiles may be a cut in the footage, says to zoom 2-3
  reps of a repeated drill at 0.2-0.3 s, and asks for one moment per distinct habit in a drill, not one per rep.
- `--sport-zh 折返跑` names the sport on the zh page at the start (no JSON edit); the run message says
  `README.md (Chinese)`.
- Contact sheets are denser for videos up to 3 minutes (a tile every 1 s, was 2 s from 30 s on), so a 1-2 s
  moment in a drill gets more than one tile.
- `page-check` warns (without failing) about English phrases left inside the Chinese report; names in Title Case and
  glosses in brackets are not flagged.
- Stage output reaches an agent line by line (unbuffered), and narration prints a line per language before TTS
  starts, so a long step no longer looks stuck.
- The film guide shows a freeze line with two marks before the label.

## 0.2.3 - 2026-10-23

### Changed

- A finished generic run also lists the narration MP3s and the clips folder, not only the page and the explained video.
- A Chinese page names the sport in Chinese (`tennis` shows as 网球 on the zh page). Other sports: set `"sport": {"zh": "...", "en": "..."}` in analysis.json; a sport it cannot name is left out of the zh header instead of showing in English.
- The report guide gives the Chinese section labels (录像里看到的, 为什么会这样 ...), so a zh report has no English headings and every Chinese report reads the same.
- Every command prints Chinese correctly through a Git Bash pipe or a cp1252 / GBK console (was `???`).
- `film --dry`: languages in the unit's order, a calibrated Chinese speech rate, and a short-film note that says never pad.
- The title card no longer repeats the date when the heading already has it.
- A short arrow on a freeze rings only its start, not two overlapping spots.
- `frames --every` under a second snaps to tenths (`0.25` -> `0.2`), so tile labels match clip times.
- Agent steps point at `sports-video-coach guide <name>` instead of a path inside site-packages; the QA step says a `page-check` pass is accepted without a browser.

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
