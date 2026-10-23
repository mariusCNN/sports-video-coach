# sports-video-coach

**Your AI agent watches your game film and coaches you.**

[![tests](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml/badge.svg)](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/pyproject.toml)
[![Agent: Claude Code | Codex | any AGENTS.md agent](https://img.shields.io/badge/agent-Claude%20Code%20%7C%20Codex-8A2BE2.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)
[![Live demo](https://img.shields.io/badge/demo-live-2ea44f.svg)](https://mariusding.github.io/sports-video-coach/)

English · [中文](https://github.com/mariusDing/sports-video-coach/blob/master/README.zh.md)

Drop in a phone video of a game or workout.
Claude Code or Codex reviews it like a coach and gives back a phone page with clips, audio narration, drills and a
target for next time.
Runs on your machine.

## Try it in a minute

**No install:** [open the demo's coaching page](https://mariusding.github.io/sports-video-coach/demo/) (clips, narration) and its explained video ([English](https://mariusding.github.io/sports-video-coach/film.en.mp4), [中文](https://mariusding.github.io/sports-video-coach/film.zh.mp4)). CI rebuilds them from the `demo` command below.

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # needs ffmpeg on PATH
sports-video-coach demo                                   # about a minute: page, clips, narration, explained video
```

[![The explained video from the demo: the clip pauses where the block stalls, a ring marks it, subtitles say why](https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/demo-film.gif)](https://mariusding.github.io/sports-video-coach/film.en.mp4)

- The demo draws a synthetic drill video and uses a pre-written review: every deliverable, no agent, no video of your own.
- `--lang en zh` for both languages; `--offline` with no network (clips and the page only).
- With your own video, your agent writes the review: see [For agents](#for-agents-start-here).

<details><summary>Install trouble? (download size, proxy, PATH)</summary>

- The install downloads about 60 MB (mostly OpenCV and NumPy; no torch).
- No git, or git fails behind a proxy: `uv tool install https://github.com/mariusDing/sports-video-coach/archive/refs/heads/master.zip`.
- `sports-video-coach: command not found`: run `uv tool update-shell` and open a new terminal.
  Or in bash (Git Bash too): `export PATH="$HOME/.local/bin:$PATH"` (the default; `uv tool dir --bin` prints yours).

</details>

If the demo made you want this for your own game, a star helps other athletes find it.

## Who it's for

- **Athletes:** one session in, back out: what to fix, one drill, a check for next time.
- **Coaches:** one game in: a team page and a page per player, with clips and audio, shared as private links.
- **Developers:** the pattern is a resumable CLI that pauses (exit 3) whenever it needs the agent's eyes or words,
  with a validator for each agent step. Reusable for any agent + media pipeline; a new sport plugin is one command.

## What you need

| | |
|---|---|
| **Tools** | a coding agent (Claude Code, Codex, Cursor ...), [uv](https://docs.astral.sh/uv/), ffmpeg on PATH |
| **Cost** | free (MIT) + your agent plan |
| **Languages** | Chinese, English, Japanese, Korean, Spanish, French, German, Portuguese: `--lang zh en ja ko es fr de pt` (basketball: zh and en) |
| **Leaves your machine** | what your agent reads (frame sheets, stats, reports) goes to its model provider; narration text goes to an online text-to-speech service |
| **Only if you ask** | private links on Cloudflare, with `--publish` |

Your videos never go to an analytics service. Details: [docs/privacy.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/privacy.md).

![Example output (basketball plugin): score, narration, the coach's write-up](https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/hero.png)

## For agents: start here

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # light: no torch; needs ffmpeg on PATH
sports-video-coach plugins                                # which plugin fits this video (--json)
sports-video-coach run my_video.mp4 --sport tennis        # generic plugin; makes workspace/analysis/tennis/<date>/
                                                          # (--lang en zh for both languages; run --help lists all)
# exit 3: do the step it prints, then run again on the folder it made
sports-video-coach run workspace/analysis/tennis/2025-03-15
```

To fork, write a plugin or use basketball tracking: `git clone` this repo and `uv sync` (Python 3.11; installs the
basketball CV stack with CUDA torch too), then prefix commands with `uv run`.

The contract (exit codes, choosing a plugin, artifacts, star etiquette) is in [AGENTS.md](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md).

- Claude Code: `/plugin marketplace add mariusDing/sports-video-coach`, then
  `/plugin install sports-video-coach@sports-video-coach` adds the skill; in a clone, `/analyze <video>` runs the loop.
- Any Agent Skills client (Codex, Cursor, ...): `npx skills add mariusDing/sports-video-coach`, or copy
  [skills/sports-video-coach/SKILL.md](https://github.com/mariusDing/sports-video-coach/blob/master/skills/sports-video-coach/SKILL.md).

## What you get

| Artifact | What it is |
|---|---|
| `run/review/review.json` | the film review: timed moments, what happened, why |
| `README.<lang>.md` | the coaching report: what to work on, drills, a checkable target (the Chinese one is `README.md`, not `README.zh.md`) |
| `clips` | short clips cut at the moments the report marks |
| `narration` | `listen.<lang>.mp3`, the report read aloud |
| `html` + `qa` | `index.html`, one phone-friendly page with clips and audio, checked before sharing |
| `publish` | a private link per page (Cloudflare Workers, optional) |
| `film` | `film.<lang>.mp4`, an explained video: narration over the clips, with freeze frames and marks |

Pick what you want with `"artifacts": ["html", "film"]` in the unit json or your profile, or `--artifacts html film`
on any run (a later run replaces the choice); default is all. `html` and `film` bring `clips` with them (both show
the clips), `html` brings `qa`; `narration` (the page's audio) comes only when you pick it.

## How it works

This repo is the procedure; **your AI agent is the coach**.

- The CLI cuts frames, measures what it can, keeps track of every step and renders the deliverables.
- It stops with exit code 3 whenever it needs the agent to watch or write, and says exactly what.
- Every agent step has a validator, so the agent knows what its output still lacks.
- Every step knows the file it produces and what it read: a run resumes where it stopped and redoes only what a
  change made stale.

```
your video ─▶ plugin `new` ─▶ unit folder ─▶ run: cmd steps (frames, pose, tracking ...)
                                               agent steps (exit 3: review, write)  ◀─ your agent
                                             ─▶ clips ▶ narration ▶ page ▶ QA ▶ publish ▶ film
```

A real run on the demo's drill video (paths shortened, long lines cut with `...`):

```console
$ sports-video-coach run drill.mp4 --sport tennis
[run] plugin: generic (no plugin named for --sport tennis; `--plugin NAME` picks one)
[run] frames: sports-video-coach frames drill.mp4 --out .../run/frames --every 0.5
frames: 4 sheets (0.5 s per tile) in .../run/frames
[run] waiting for the agent: review
Film review: open every sheet in .../run/frames (frames.json lists them in time order) and write
.../run/review/review.json as the review guide says (`sports-video-coach guide review --plugin generic` ...) ...
[run]   .../run/review/review.json missing                                     # exit 3

$ sports-video-coach run workspace/analysis/tennis/2025-03-15                  # agent wrote a thin review
[run] waiting for the agent: review
[run]   .../run/review/review.json: needs a `moments` list with at least 3 entries   # exit 3: the validator

$ sports-video-coach run workspace/analysis/tennis/2025-03-15                  # agent fixed it
[run] waiting for the agent: report
Write the coaching report README.en.md in ... from .../run/review/review.json, as
`sports-video-coach guide report --plugin generic` says (en) ...               # exit 3: next step
```

Details: [docs/architecture.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/architecture.md).

## Plugins

| Plugin | For | Adds |
|---|---|---|
| `generic` (built in) | any sport or activity, any clip; also pickup basketball, phone clips, no league or no GPU (`--sport basketball`) | contact sheets ▶ agent film review ▶ report; no detection: the agent reviews the frames |
| `basketball` ([docs](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.md)) | league games (stats site link) or tracking from a clone (`uv sync`, GPU); personal training, movement | player and ball tracking, league box score, team and player pages, shot charts, court diagrams in the film |

A new sport takes one command: `uv run sports-video-coach new-plugin badminton` writes a working plugin folder to
start from. Then write its review prompt and add measurements. Guide: [docs/plugins.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/plugins.md). Share yours
with the GitHub topic `sports-video-coach-plugin`.

## Basketball

The project started as `hoop-tape-miner`, a basketball film-room for an amateur team, and that still works the same:
`uv run hoop-tape-miner run <league game link>`, `/game`, `/train`, `/move`. See [docs/basketball.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.md).

No league, a pickup game or a phone clip: `sports-video-coach run clip.mp4 --sport basketball` (generic plugin, any clip).

## Privacy

Your videos, frames, reports and profile stay in `workspace/` (gitignored). Pages show real people: share them only
with the people in them. Narration text goes to an online text-to-speech service. See [docs/privacy.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/privacy.md).

## Contributing

Plugins, prompts for a sport you know, fixes and docs are welcome: [CONTRIBUTING.md](https://github.com/mariusDing/sports-video-coach/blob/master/CONTRIBUTING.md). Never attach
real players' videos, frames or names to issues or pull requests.

If this helped you or your agent, a star tells the author it did. Agents: ask your user first (see AGENTS.md).

## License

[MIT](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE). Models downloaded at run time keep their own licences.
