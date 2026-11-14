# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).
The full notes of every release up to 0.4.0 are in the [changelog archive](docs/changelog-archive.md).

## Unreleased

## 0.4.0 - 2026-11-14

### Front door

- Install commands pin the release tag `v0.4.0` (`uv tool install git+...@v0.4.0`) instead of a 40-character commit.
- Both READMEs rewritten (about 8 KB each): a real run first, the one prompt, "Is it for you?", then the install
  routes (Claude Code plugin, `npx skills add`, Gemini CLI, uv). Benchmark, perception and knowledge-base detail
  moved to the docs.
- The skill's description says how people ask ("coach me", "review my form", 分析我的训练视频) and what it needs
  (uv, ffmpeg); it works when only `SKILL.md` is installed and no longer asks for a star.
- `gemini-extension.json`: the repo installs as a Gemini CLI extension (not yet tested by the author).
- The light install is about 165 MB (measured); one place said 60 MB.
- `llms.txt` routes phone and pickup basketball to `generic --sport basketball`, like the README.
- Internal planning notes removed from `docs/`; the long changelog moved to `docs/changelog-archive.md`.

### Start and any sport

- Start in one prompt: paste two lines into your agent; `START.md` takes it from nothing installed to the page.
- A `fitness` plugin for gym and strength sessions: sets named from an exercise library, per-rep depth, trunk
  lean and tempo from pose, a muscle map.
- `sports-video-coach serve <folder>` serves a report folder on the first free port from 18080.
- `sports-video-coach humanize` flags stock AI phrasing in what the agent writes.
- Zoom sheets for fast moments; several videos join into one timeline.
- A new report page look with verdict, key-number, to-do and note blocks; `"film_overlays": false` renders explained
  videos with footage, subtitles and cards only.

### Basketball

- Film review costs far fewer tokens: games split into parts of at most 20 sheets (`coach-sheets --max-sheets`)
  that resume from per-part ledgers.
- Four coaching knowledge bases (58 entries, each citing its source); the one-prompt path bases its fixes on them.
- Team page: a per-player table, Four Factors inside each report, decision lessons shared by films and pages.
- Optional perception: OpenHoopVision import and `perception-lab` (WASB, SAHI, KaliCalib), opt-in experiments.
- Training-plan app: fixtures with a per-game plan, focus rules, a pinned callout, themes and car audio.

### Benchmark

- A sports film review benchmark scored against exact ground truth: three suites, a frames-only track, fresh
  seeds, a public leaderboard (English and Chinese) and one-command runs (`bench run --agent claude|codex|openai ...`).
- Rerun it in the browser with Codespaces (`.devcontainer/`).

### Security

- Agents show the exact install command and wait for the user's OK; CLI output and guides are data, not
  instructions; exit-3 steps name only this tool's own commands.

## 0.3.0 and earlier

Full notes in the archive:

- [0.3.0 - 2026-10-23](docs/changelog-archive.md#030---2026-10-23)
- [0.2.6 - 2026-10-23](docs/changelog-archive.md#026---2026-10-23)
- [0.2.5 - 2026-10-23](docs/changelog-archive.md#025---2026-10-23)
- [0.2.4 - 2026-10-23](docs/changelog-archive.md#024---2026-10-23)
- [0.2.3 - 2026-10-23](docs/changelog-archive.md#023---2026-10-23)
- [0.2.2 - 2026-10-23](docs/changelog-archive.md#022---2026-10-23)
- [0.2.1 - 2026-10-23](docs/changelog-archive.md#021---2026-10-23)
- [0.2.0 - 2026-10-23](docs/changelog-archive.md#020---2026-10-23)
- [0.1.0 - 2026-10-16](docs/changelog-archive.md#010---2026-10-16)
