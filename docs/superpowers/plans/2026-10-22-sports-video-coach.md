# sports-video-coach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the repo into a sport-agnostic core package `sports_video_coach` and a basketball plugin
(`hoop_tape_miner`), add a generic plugin, a plugin scaffold and an agent-first surface, then rename the repo.

**Architecture:** One distribution ships two packages. The core owns the step driver, artifacts, media, page, film
and publish, and finds plugins through entry points or local folders; plugins declare kinds, stages, prompts and hooks.
`hoop-tape-miner` keeps working as the basketball CLI.

**Tech Stack:** Python 3.11, uv / uv_build, pytest, ffmpeg, edge-tts, markdown-it-py.

**Spec:** `docs/superpowers/specs/2026-10-22-sports-video-coach-design.md`

## Global Constraints

- `uv run pytest -q` stays green (516 tests at start) after every task; no network, GPU or real user data in tests.
- `src/sports_video_coach/**` never imports `hoop_tape_miner` (test `test_core_independence`).
- `uv run hoop-tape-miner <stage>` keeps every current stage name and behaviour; `pipeline` child processes run
  `python -m sports_video_coach.cli <stage>` with plugin stages qualified as `basketball:<stage>`.
- Distribution name `sports-video-coach`, scripts `sports-video-coach` and `hoop-tape-miner`.
- Entry-point group `sports_video_coach.plugins`; local plugin folders from `SVC_PLUGIN_PATH`, `<workspace>/plugins`, `./plugins`.
- English in code, docs, commits; nothing from `workspace/` in git.

## Review Focus

- Two plugins defining the same stage name: unqualified call errors listing `a:stage`, `b:stage`.
- A broken local plugin folder (syntax error): `plugins` lists it as broken, other plugins still load.
- A unit json with an unknown `"plugin"`: clear error naming installed plugins.
- `artifacts` naming an unknown artifact, or `publish` without `html`: clear error before any step runs.
- Old game folders without `"plugin"` keep resolving to basketball (game.json, session.json kind training, movement.json, season.json).

---

### Task 1: Core package, plugin registry, CLI

**Files:**
- Create: `src/sports_video_coach/{__init__,plugin,cli}.py`
- Move (git mv, fix imports): `pipeline, media, timefmt, device, narrate, workspace` -> `src/sports_video_coach/`
- Create: `src/sports_video_coach/units.py` (generic part of game_config: `find_up`, `load_unit_json`, colour helpers)
- Create: `src/hoop_tape_miner/plugin.py` (`PLUGIN`); modify `src/hoop_tape_miner/cli.py` to delegate
- Modify: `pyproject.toml` (name, scripts, entry point, `module-name = ["sports_video_coach", "hoop_tape_miner"]`)
- Test: `tests/test_plugin_registry.py`, `tests/test_core_independence.py`; update tests importing moved modules

**Interfaces (produces):**
- `plugin.Kind(name, json, unit: "mod:attr", steps: "mod:attr", match: Callable[[dict], bool] | None, driver: str | None)`
- `plugin.Plugin(name, summary, use_when, stages: dict[str, tuple[str, str]], kinds: list[Kind], prompts: Path | None,
  page=None, scenes: dict = {}, site=None, clip_windows=None, artifacts: dict = {}, claims=None)`
- `plugin.plugins() -> dict[str, Plugin]`, `plugin.get(name) -> Plugin`, `plugin.errors() -> dict[str, str]`,
  `plugin.owner(folder) -> tuple[Plugin, Kind, dict] | None`, `plugin.json_names() -> list[str]`
- `cli.main(argv, prog="sports-video-coach", default: str | None = None)`; `cli.resolve(stage, default) -> (module, label)`
- `pipeline.Unit.PLUGIN: str | None`; `pipeline.stage_cmd(argv, plugin=None)`

- [ ] Write failing tests: registry lists `basketball` and `generic`; `owner()` maps old game.json to basketball; ambiguous stage error; core-independence grep.
- [ ] Implement; run `uv run pytest -q` -> all pass.
- [ ] Commit `Core package sports_video_coach: plugin registry and CLI; basketball as a plugin`.

### Task 2: Artifacts and clips in the core

**Files:** Create `src/sports_video_coach/artifacts.py`; move `clips.py` to core (clip windows via `Plugin.clip_windows`);
`pipeline.tail_steps` delegates to `artifacts.steps`. Test: `tests/test_artifacts.py`.

**Interfaces:** `artifacts.NAMES = ("clips", "narration", "html", "qa", "publish", "film")`;
`artifacts.selected(unit) -> list[str]` (unit json `artifacts`, else profile `artifacts`, else all; raises `SystemExit`
on unknown names or `publish` without `html`); `artifacts.steps(unit_cls_or_none, video, listen_how, qa_how, film_script_how, film_run, select) -> list[Step]`.

- [ ] Tests: default = all six in order; `["html","publish"]` drops clips/narration/film/qa? (qa kept whenever html is kept); unknown name exits.
- [ ] Implement; tests green; commit.

### Task 3: Page renderer in the core (subagent A)

Move `render_html.py` to core; basketball bands (score, season, training, movement), Four Factors, film_index and
tracking sections move behind `render_html.PageHooks` provided by `hoop_tape_miner.page_hooks`. Default band: title, date, sport.
Existing page tests must produce the same HTML for basketball fixtures.

### Task 4: Film in the core (subagent B)

Move `film.py` and the generic drawing of `film_draw.py` to core; `court:` scenes, track-resolved marks and the game
title move behind `film.SceneKind` / title hook provided by the basketball plugin. Existing film tests unchanged in meaning.

### Task 5: Publish in the core (subagent C)

Move `publish.py` + `publish_worker.js` to core; hub grouping, hidden personal folders (`player-<N>`), seasons and
program pages behind `publish.SiteHooks` from the basketball plugin. Registry format and tokens unchanged.

### Task 6: Frames stage, generic plugin, scaffold

**Files:** `src/sports_video_coach/frames.py` (stage `frames`: video -> `run/frames/sheet_NNN.jpg` + `frames.json`),
`src/sports_video_coach/plugins/generic/` (kind `analysis`, json `analysis.json`, steps frames -> review -> report ->
artifacts; prompts `review.md`, `report.md`; `new` stage), `src/sports_video_coach/scaffold.py` (stage `new-plugin <name>`
copies generic into `plugins/<name>/`). Test: `tests/test_generic_plugin.py` (synthetic 6 s lavfi video; status rows;
review validator; scaffolded plugin loads from `SVC_PLUGIN_PATH`).

### Task 7: Agent-first surface

AGENTS.md (core contract, choose a plugin, run loop, write a plugin, star etiquette), CLAUDE.md, README.md / README.zh.md
rewrite, `docs/plugins.md`, `docs/architecture.md`, `skills/sports-video-coach/SKILL.md`, `.claude-plugin/marketplace.json`
+ `plugin.json`, `.claude/commands/analyze.md`, CHANGELOG, CITATION.cff, CONTRIBUTING plugin section.

### Task 8: Ship

Full tests, `uv build`, smoke `sports-video-coach plugins`, `hoop-tape-miner run <existing game> --status`, generic
plugin end to end on a synthetic video; scrub check; merge to master; push; `gh repo rename sports-video-coach`;
description + topics; update local remote and memory.
