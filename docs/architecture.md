# Architecture

One distribution (`sports-video-coach`), two packages:

| Package | What it is |
|---|---|
| `sports_video_coach` | the core: driver, media, frames, clips, narration, page, film, publish, plugin registry, CLI |
| `hoop_tape_miner` | the basketball plugin: tracking, league import, coach review, team / training / movement units |

The core never imports a plugin (`tests/test_core_independence.py`). Plugins call the core; the core calls plugins
only through the `Plugin` object and its hooks.

## The loop

```
video(s) ──new──▶ unit folder (analysis.json / game.json / session.json ...)
                     │
                     ▼
   run <folder> ── step table ──▶ cmd step: run a stage, record inputs and params (provenance)
                     │            agent step: exit 3 with instructions; the agent writes, runs again
                     ▼
             tail steps: clips ▶ narration ▶ html ▶ qa ▶ publish ▶ film
```

- **Unit**: one folder with a json, a `run/` folder for machine outputs and the report folders. `pipeline.Unit`.
- **Step**: `cmd` or `agent`, with a `done` check. The driver resumes at the first undone step, so every run is safe
  to repeat. `pipeline.drive`.
- **Provenance**: each cmd step records what it read and the settings it used (`.hoop-steps.json`); a change makes
  it and the steps after it stale.
- **Exit codes**: 0 done, 3 an agent step waits, 1 a command failed. An agent drives the loop with no other API.
- **Artifacts**: steps are tagged `clips`, `narration`, `html`, `qa`, `publish`, `film` (or a plugin's own); the
  unit json or profile picks which run. `artifacts.py`.

## The CLI

`sports-video-coach <stage>`: core stages first, then `plugin:stage`, then the default plugin's stage, then a name
unique across plugins (ambiguous names are an error). The driver always passes qualified names to child processes.
`hoop-tape-miner` is the same CLI with `basketball` as the default plugin and flat stage names.

## Plugin discovery

Built in (`generic`) ▶ entry points (`sports_video_coach.plugins`) ▶ local folders (`$SVC_PLUGIN_PATH`,
`<workspace>/plugins`, `./plugins`). A plugin that fails to import is listed with its error and skipped.

## Workspace

Personal data lives in `$SVC_WORKSPACE` (or `$HOOP_WORKSPACE`), default `./workspace`, gitignored. The profile
(languages, who to coach, default artifacts) is `profile.json` there, or `team.json` for basketball.

See [plugins.md](plugins.md) to write a plugin and [pipeline.md](pipeline.md) for the basketball stages.
