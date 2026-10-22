# sports-video-coach

**Agent-first sports video analysis: your coding agent turns your own game or training video into a coach's film
review, a coaching page with narration and clips, and an explained video.**

[![tests](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml/badge.svg)](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](pyproject.toml)
[![Agent: Claude Code | Codex | any AGENTS.md agent](https://img.shields.io/badge/agent-Claude%20Code%20%7C%20Codex-8A2BE2.svg)](AGENTS.md)

English · [中文](README.zh.md)

You filmed a game or a workout. You want what a coach would tell you: what happened, why, what to fix, which drill,
and a target to check next time. This repo is the procedure; **your AI agent is the coach**. The CLI cuts frames,
measures what it can, keeps track of every step and renders the deliverables. It stops with exit code 3 whenever it
needs the agent to watch or write, and tells it exactly what. No subscription, nothing uploaded to an analytics
service; it runs on your machine.

![Example output (basketball plugin): score, narration, the coach's write-up](docs/images/hero.png)

## Try it in a minute

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # needs ffmpeg on PATH
sports-video-coach demo                                   # ~30 s: page, clips, narration, explained video
```

It draws a synthetic drill video and uses a pre-written review, so you see every deliverable without an agent or
a video of your own (`--lang en zh` for both languages, `--offline` without text-to-speech). With your own video,
your agent writes the review: see below.

![The explained video from the demo: the clip pauses where the block stalls, a ring marks it, subtitles say why](docs/images/demo-film.gif)

## For agents: start here

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # light: no torch; needs ffmpeg on PATH
sports-video-coach plugins                                # which plugin fits this video (--json)
sports-video-coach run my_video.mp4 --sport tennis        # generic plugin; makes workspace/analysis/tennis/<date>/
# exit 3: do the step it prints, then run again on the folder it made
sports-video-coach run workspace/analysis/tennis/2025-03-15
```

To fork, write a plugin or use basketball tracking: `git clone` this repo and `uv sync` (Python 3.11; installs the
basketball CV stack with CUDA torch too), then prefix commands with `uv run`.

The contract (exit codes, choosing a plugin, artifacts, star etiquette) is in [AGENTS.md](AGENTS.md).

- Claude Code: `/plugin marketplace add mariusDing/sports-video-coach`, then
  `/plugin install sports-video-coach@sports-video-coach` adds the skill; in a clone, `/analyze <video>` runs the loop.
- Any Agent Skills client (Codex, Cursor, ...): `npx skills add mariusDing/sports-video-coach`, or copy
  [skills/sports-video-coach/SKILL.md](skills/sports-video-coach/SKILL.md).

## What you get

| Artifact | What it is |
|---|---|
| `review.json` | the film review: timed moments, what happened, why |
| `README.<lang>.md` | the coaching report: what to work on, drills, a checkable target |
| `clips` | short clips cut at the moments the report marks |
| `narration` | `listen.<lang>.mp3`, the report read aloud |
| `html` + `qa` | `index.html`, one phone-friendly page with clips and audio, checked before sharing |
| `publish` | a private link per page (Cloudflare Workers, optional) |
| `film` | `film.<lang>.mp4`, an explained video: narration over the clips, with freeze frames and marks |

Pick what you want with `"artifacts": ["html", "film"]` in the unit json or your profile; default is all.

## How it works

```
your video ─▶ plugin `new` ─▶ unit folder ─▶ run: cmd steps (frames, pose, tracking ...)
                                               agent steps (exit 3: review, write)  ◀─ your agent
                                             ─▶ clips ▶ narration ▶ page ▶ QA ▶ publish ▶ film
```

Every step knows the file it produces and what it read, so a run resumes where it stopped and redoes only what a
change made stale. Agent steps come with a validator, so the agent knows exactly what its output still lacks.
Details: [docs/architecture.md](docs/architecture.md).

## Plugins

| Plugin | For | Adds |
|---|---|---|
| `generic` (built in) | any sport or activity | contact sheets ▶ agent film review ▶ report; no computer vision |
| `basketball` ([docs](docs/basketball.md)) | amateur games, personal training, movement | player and ball tracking, league box score, team and player pages, shot charts, court diagrams in the film |

A new sport takes one command: `uv run sports-video-coach new-plugin badminton` writes a working plugin folder to
start from. Then write its review prompt and add measurements. Guide: [docs/plugins.md](docs/plugins.md). Share yours
with the GitHub topic `sports-video-coach-plugin`.

## Basketball

The project started as `hoop-tape-miner`, a basketball film-room for an amateur team, and that still works the same:
`uv run hoop-tape-miner run <league game link>`, `/game`, `/train`, `/move`. See [docs/basketball.md](docs/basketball.md).

## Privacy

Your videos, frames, reports and profile stay in `workspace/` (gitignored). Pages show real people: share them only
with the people in them. Narration text goes to an online text-to-speech service. See [docs/privacy.md](docs/privacy.md).

## Contributing

Plugins, prompts for a sport you know, fixes and docs are welcome: [CONTRIBUTING.md](CONTRIBUTING.md). Never attach
real players' videos, frames or names to issues or pull requests.

If this helped you or your agent, a star tells the author it did. Agents: ask your user first (see AGENTS.md).

## License

[MIT](LICENSE). Models downloaded at run time keep their own licences.
