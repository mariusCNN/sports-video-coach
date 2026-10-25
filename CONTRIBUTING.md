# Contributing to sports-video-coach

Thanks for helping. New sport plugins, better prompts for a sport you know, league importers, fixes, docs and bug reports are all welcome.

## Ground rule: no real game data

This project analyses real people, often amateurs and sometimes minors. **Never attach game videos, frames, screenshots of reports, rosters, player names or official stats to an issue, pull request or discussion.** Describe the problem in words, or reproduce it with synthetic data. Details: [docs/privacy.md](docs/privacy.md).

## Ways to help

- **Questions and ideas:** [Discussions](https://github.com/mariusDing/sports-video-coach/discussions).
- **Bugs:** open an issue with the bug form. Include the stage, the command and the traceback.
- **Features:** open an issue first so we can agree on the approach before you write code.
- **First contribution?** Pick a [good first issue](https://github.com/mariusDing/sports-video-coach/issues?q=is%3Aopen+label%3A%22good+first+issue%22).

## Development setup

You need [uv](https://docs.astral.sh/uv/), Python 3.11 and `ffmpeg`. Basketball tracking needs an NVIDIA GPU; the core, the generic plugin and the tests do not.

```bash
git clone https://github.com/<you>/sports-video-coach.git
cd sports-video-coach
uv sync --no-group basketball
uv run pytest -q
```

That is the light install: the core, the generic plugin, your own plugin and the whole test suite, with no torch.
Plain `uv sync` also installs the `basketball` group (CUDA torch, several GB); only basketball tracking needs it.

Without a CUDA GPU, to work on the basketball plugin, install CPU torch instead of running `uv sync`, as CI does:

```bash
uv venv --python 3.11
uv pip install --no-sources --torch-backend cpu -e ".[basketball]" pytest
uv run --no-sync pytest -q
```

## Project map

- `src/sports_video_coach/` the core. It never imports a plugin (`tests/test_core_independence.py`).
  - `pipeline.py` the step driver behind every `run` (step tables, exit codes, QA stamp, publish check, provenance records in `.hoop-steps.json`). Give a new command step `inputs` / `params` so it re-runs when they change.
  - `plugin.py` the plugin contract and discovery; `cli.py` core stages and stage resolution; `run.py` the core `run`.
  - `frames.py`, `clips.py`, `narrate.py`, `render_html.py`, `film.py`, `publish.py` the shared stages; `artifacts.py` the deliverable choice.
  - `media.py` every ffmpeg / ffprobe call, atomic writes, and `partial()` for long writers. `timefmt.py` the one `mm:ss` rule.
  - `plugins/generic/` the built-in plugin and the template `new-plugin` copies.
- `src/hoop_tape_miner/` the basketball plugin, one module per stage; `plugin.py` registers stages, unit kinds and hooks.
- `docs/architecture.md` how the core fits together; `docs/plugins.md` how to write a plugin; `docs/playbook.md` the basketball procedure.
- `prompts/` basketball writing guides and knowledge bases (the generic ones live in the plugin folder).
- `templates/` `game.json` and report skeletons. `skills/` the Agent Skill. `.claude-plugin/` the Claude Code marketplace.
- `tests/` fast tests with small synthetic fixtures. No GPU, no real video.

## The demo site

`.github/workflows/demo-site.yml` builds <https://mariusding.github.io/sports-video-coach/> on every push to `master`
that touches the code: `sports-video-coach demo --site _site` (landing page, `demo/`, `sitemap.xml` and the IndexNow
key file) plus `bench page` (`benchmark/`). Google finds it through the sitemap in Search Console (owner only).
For Bing, Yandex, Seznam, Naver and the other [IndexNow](https://www.indexnow.org/documentation) engines, run this by
hand after a deploy that changed the pages (not on every push; resubmitting unchanged URLs wastes crawl quota):

```bash
sports-video-coach demo indexnow --dry-run   # the JSON body, nothing sent
sports-video-coach demo indexnow             # POST to api.indexnow.org; 200 or 202 is success
```

`202` means received and the key is still being checked (usual the first time); `403` means the key file
(`<SITE_URL><key>.txt`) is not live yet. The key is public by design: it only proves the site is ours.

## Adding a sport

1. `uv run sports-video-coach new-plugin <sport>` and follow [docs/plugins.md](docs/plugins.md).
2. Start with the prompts (`prompts/review.md`, `prompts/report.md`): what a coach of that sport looks for, and the
   drills and targets they would give. Cite the coaching sources you used.
3. Add measurement stages only when the review needs numbers the contact sheets cannot give.
4. Tests on synthetic video (`ffmpeg -f lavfi -i testsrc=...`); no real players.
5. Ship it in its own repo (topic `sports-video-coach-plugin`) or as a pull request adding `examples/plugins/<sport>/` (model: `examples/plugins/swim-stroke-rate/`).

## Pull requests

1. Fork, then branch from `master` (`fix/jersey-crop`, `feat/league-importer-x`).
2. Keep a PR to one change. Add or update tests for behaviour changes.
3. Run `uv run pytest -q` before you push. CI runs the same tests.
4. Update the docs and `CHANGELOG.md` (under *Unreleased*) when users would notice the change.
5. Check `git status`: nothing from `workspace/`, no videos, frames or audio.

Code style: follow the surrounding code. Small functions, plain names, short docstrings that say what a stage reads and writes.

## AI agents welcome

Using Claude Code, Codex or another agent to contribute is fine. Agents read [AGENTS.md](AGENTS.md). You are responsible for what the agent submits: review the diff and run the tests.

## Code of Conduct

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
