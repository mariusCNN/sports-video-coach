<div align="center">

# sports-video-coach

### Your coding agent reviews your sports video and coaches you.

[![release](https://img.shields.io/github/v/release/mariusDing/sports-video-coach)](https://github.com/mariusDing/sports-video-coach/releases)
[![tests](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml/badge.svg)](https://github.com/mariusDing/sports-video-coach/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE)
[![Works with Claude Code and Codex](https://img.shields.io/badge/agent-Claude%20Code%20%7C%20Codex%20%7C%20AGENTS.md-8A2BE2.svg)](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md)

**English** · [中文](https://github.com/mariusDing/sports-video-coach/blob/master/README.zh.md)

<img alt="A real run on the author's shooting drill: the clip, the agent's film review pausing where the finish is held, then the coaching page" src="https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/real-session.gif" width="720">

<sub>A real run on the author's own shooting drill: your video → the agent's film review → your coaching page.
No install needed to see a full example: <a href="https://mariusding.github.io/sports-video-coach/demo/">the demo page</a> (a synthetic drill).</sub>

</div>

Film yourself with a phone: a game, a drill, a workout, any sport.
Your coding agent (Claude Code, Codex, Cursor ...) reviews it from timestamped frame sheets, and can ask for a
denser sheet of a fast moment. You get back a phone page with the clips that matter, a drill and a target for each fix, a spoken
version of the report, and an explained video. The tool runs on your machine; the frames your agent looks at go to
its model provider, like anything else you show it. Free and MIT.

## Try it

**1. See what you get, no install:** the [demo coaching page](https://mariusding.github.io/sports-video-coach/demo/) and its explained video
([English](https://mariusding.github.io/sports-video-coach/film.en.mp4), [中文](https://mariusding.github.io/sports-video-coach/film.zh.mp4)).

**2. Tell your agent** (paste into Claude Code, Codex or any coding agent; set your sport and language):

```text
Coach me on my sports video <path to your video>. Ask me before installing anything.
Install the CLI: `uv tool install git+https://github.com/mariusDing/sports-video-coach` (it needs ffmpeg).
Run `sports-video-coach run <video> --sport soccer --lang en`, do each step it hands you (exit code 3)
until it exits 0, then show me the coaching page.
```

No GPU needed. In a game, say who to watch: `--focus "the player in red"` or a jersey number.
For just the page and clips (no audio, no explained video, nothing sent to the text-to-speech service): `--artifacts html`.

A match, a drill or a workout: soccer, tennis, badminton, running, the gym, basketball ...
Several videos are joined in the order given into one timeline; two camera angles of the same set are better run
as two units for now.
In one of our runs a 40-second clip took about 3 minutes and 5 agent steps; a full game takes longer and more of your
agent plan.

<details><summary>Run the demo on your machine (about a minute, no agent or video needed)</summary>

A synthetic drill with a pre-written review, rendered end to end:

```bash
uv tool install git+https://github.com/mariusDing/sports-video-coach   # needs ffmpeg on PATH
sports-video-coach demo
```

</details>

## What you get

<img align="right" width="260" alt="The coaching page on a phone: score, audio read-out, the report" src="https://raw.githubusercontent.com/mariusDing/sports-video-coach/master/docs/images/mobile.png">

- **A coaching page for your phone:** what to fix, with a drill and a target to check next time for each fix,
  the clips that show it, and a spoken version of the report.
- **An explained video:** the clip pauses where it goes wrong, a ring marks the spot, a subtitle says why.
- **The film review behind it:** timed moments, what happened and why, in a json your agent can build on.
- In Chinese, English, Japanese, Korean, Spanish, French, German and Portuguese (`--lang`; basketball plugin: Chinese and English).

**What it can't do (yet):** the agent reviews frame sheets (by default one frame every 0.5 s for a video up to
30 s, every second up to 3 minutes, every 2 s beyond), so very fast details can slip between frames unless it cuts
a denser zoom sheet of that moment; automatic player and ball tracking and box scores need the basketball plugin. Each run uses some of your
agent plan.

<br clear="right">

## How it works

1. **The tool cuts your video into frame sheets** and measures what it can (the basketball plugin also tracks
   players and the ball).
2. **Your agent writes the review and the report.** Whenever the tool needs eyes or words it stops (exit code 3) and says what to
   write: the film review, then the report. A checker tells the agent what its answer still lacks.
3. **The tool renders the rest:** clips, narration, the page, the explained video. Edit the report and run again:
   only what the change affects is redone.

The full agent contract is [AGENTS.md](https://github.com/mariusDing/sports-video-coach/blob/master/AGENTS.md);
how the pipeline fits together is in [docs/architecture.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/architecture.md).

## Any sport

| Plugin | For |
|---|---|
| `generic` (built in) | any sport; the advice depends on what the frames show (pickup basketball too: `--sport basketball`) |
| `basketball` | league games with a stats link, or tracking from a clone with a GPU: team and player pages, shot charts ([docs](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.md)) |
| yours | `sports-video-coach new-plugin <your-sport>` writes a working plugin to start from ([guide](https://github.com/mariusDing/sports-video-coach/blob/master/docs/plugins.md)) |

<details><summary><b>Install for your agent</b> (Claude Code plugin, Agent Skills, uv, clone)</summary>

- **Claude Code:** `/plugin marketplace add mariusDing/sports-video-coach`, then
  `/plugin install sports-video-coach@sports-video-coach`.
- **Any Agent Skills client** (Codex, Cursor ...): `npx skills add mariusDing/sports-video-coach`, or copy
  [skills/sports-video-coach/SKILL.md](https://github.com/mariusDing/sports-video-coach/blob/master/skills/sports-video-coach/SKILL.md).
- **The CLI alone:** `uv tool install git+https://github.com/mariusDing/sports-video-coach` (about 60 MB, no torch;
  ffmpeg on PATH), then `sports-video-coach plugins` and `sports-video-coach run <video> --sport <sport>`.
- **Fork, write a plugin, basketball tracking:** `git clone` and `uv sync` (Python 3.11, CUDA torch), then prefix
  commands with `uv run`.
- No git or a proxy: install from `https://github.com/mariusDing/sports-video-coach/archive/refs/heads/master.zip`.
- `command not found`: `uv tool update-shell` and a new terminal; in Git Bash, write `C:/...` PATH entries as `/c/...` (e.g. `/c/Users/<you>/.local/bin`).

</details>

<details><summary><b>What you need, what it costs, what leaves your machine</b></summary>

| | |
|---|---|
| **Tools** | a coding agent, [uv](https://docs.astral.sh/uv/) (Python 3.11; uv fetches it), ffmpeg and ffprobe on PATH |
| **Cost** | free (MIT) + your agent plan |
| **Leaves your machine** | what your agent reads (frame sheets, stats, reports) goes to its model provider; narration text goes to an online text-to-speech service |
| **Only if you ask** | unlisted links on Cloudflare with `--publish` (anyone with the link can open them) |

A single video stays where it is; frames, clips and reports go in the workspace folder. Nothing goes to an analytics service.
Pages show real people: share them only with the people in them. Details: [docs/privacy.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/privacy.md).

</details>

<details><summary><b>For developers: the exit-3 pattern</b></summary>

A resumable CLI that pauses with exit code 3 whenever it needs the agent's eyes or words, with a check on each
agent step (required files and review fields) and file-level freshness, so a run resumes where it stopped and redoes only what a change made stale.
Architecture: [docs/architecture.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/architecture.md);
the project began as `hoop-tape-miner`, a film room for an amateur basketball team ([docs/basketball.md](https://github.com/mariusDing/sports-video-coach/blob/master/docs/basketball.md)).

</details>

## Status and contributing

Early (alpha): built and tested by its author on their own games and training, and on synthetic runs.
Plugins for a sport you know, prompts, fixes and docs are welcome:
[CONTRIBUTING.md](https://github.com/mariusDing/sports-video-coach/blob/master/CONTRIBUTING.md),
[good first issues](https://github.com/mariusDing/sports-video-coach/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
Never attach real players' videos, frames or names to issues or pull requests.
If it helped your game, a star helps other athletes find it.

[MIT](https://github.com/mariusDing/sports-video-coach/blob/master/LICENSE). Models downloaded at run time keep their own licences.
