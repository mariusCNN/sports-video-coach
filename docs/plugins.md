# Writing a plugin

A plugin teaches sports-video-coach one sport (or any video domain): what a unit folder looks like, which steps
turn the video into facts, what the agent reviews, and how the page and the film show it. The core does the rest:
the step driver, provenance, clips, narration, the page, QA, publish links and the explained video.

**Do you need one?** Not to analyse one video: `sports-video-coach run <video> --plugin generic` already gives any
sport a film review, a report, clips, narration, a page and a film. Write a plugin when you want the same sport
again and again with its own prompts, measurements (pose, tracking, a scoreboard reader) or a league import.

## Start from the template

```bash
uv run sports-video-coach new-plugin tennis            # writes ./plugins/tennis/ (a copy of generic)
uv run sports-video-coach plugins                      # lists tennis
uv run sports-video-coach run serve.mp4 --plugin tennis
```

The copy runs as it is. Make it yours in this order:

1. `prompts/review.md`: what the agent looks for on the contact sheets, in the words of a coach of that sport.
2. `prompts/report.md`: the report's sections (what to work on, drills, a checkable target).
3. Stages for your own measurements, added to the step table before the review.

Local plugins load from `./plugins/<name>/`, `<workspace>/plugins/<name>/` and every folder on `$SVC_PLUGIN_PATH`.
To ship one as a package, declare an entry point:

```toml
[project.entry-points."sports_video_coach.plugins"]
tennis = "svc_tennis.plugin:PLUGIN"
```

## The contract

A plugin is a `sports_video_coach.plugin.Plugin` object named `PLUGIN`:

| Field | What it is |
|---|---|
| `name` | lowercase id; stages are addressed as `<name>:<stage>` |
| `summary`, `use_when` | one line each; `sports-video-coach plugins` shows them so agents can choose |
| `stages` | `{"stage": ("module", "help")}`; each module has `main(argv)` |
| `kinds` | the unit folders it drives (`Kind`, below) |
| `prompts` | folder of writing guides; agent steps refer to it as `{prompts}` |
| `claims` | `claims(target) -> bool`: take a target such as a league url (`run <url>` then calls your `run` stage) |
| `artifacts` | extra deliverable names (`{"scorecard": "help"}`) your steps can be tagged with |
| `page`, `scenes`, `film`, `site`, `clip_windows` | optional hooks into the page, the film and the publish site |

A `Kind` maps a json file to a unit:

```python
Kind("analysis", "analysis.json",            # name, json file in the unit folder
     "svc_plugin_tennis.unit:Analysis",       # pipeline.Unit subclass with load(folder)
     "svc_plugin_tennis.unit:STEPS",          # the step table
     match=lambda d: d.get("plugin") == "tennis")
```

A folder belongs to the plugin named in its json `"plugin"` key, else to the first plugin whose `Kind` has that json
name and whose `match` accepts the data. Set `PLUGIN = "tennis"` on your Unit class so its command steps run your
stages (`tennis:<stage>`); two plugins may then both have a stage called `extract`.

## Steps

The step table is a list of `pipeline.Step`. The driver walks it in order, skips steps whose `done(unit)` is true,
and stops at the first that is not:

- `Step("pose", "cmd", done, args)` runs `args(unit)` (one or more stage argv). Give it `inputs` and `params` so it
  re-runs when its inputs or settings change; `long=True` logs to a file.
- `Step("review", "agent", done, how="...", errors=fn)` stops with exit 3 and prints `how`, with `{folder}`,
  `{run}`, `{review}`, `{prompts}`, `{langs}` and your `fill_values()` filled in. `errors(unit)` says what the
  output still lacks; agents fix exactly that.
- End with `*pipeline.tail_steps(video_fn, listen_how=..., qa_how=..., film_script_how=...)`: clips, narration,
  page, QA, publish, explained film, each tagged with its artifact.

Rules that keep agents honest: every agent step has a validator (`errors`), every number the agent writes comes from
a file a command step made, and the review format says "unclear" is a valid answer.

## Hooks

All optional; without them the page and the film are the generic ones.

Each field of each hook object falls back to the default on its own, so set only what you need.

| Hook | Fields | Use it for |
|---|---|---|
| `page` (`render_html.PageHooks`) | `ui`, `board`, `band`, `before`, `sections` | page labels, the top band (a score, a summary), HTML above or after the report |
| `scenes` (`{"court": film.SceneKind}`) | `prefix`, `noun`, `parse`, `render`, `problems`, `steps` | new scene kinds in `film.<lang>.md`, e.g. `![...](court:play.json)` |
| `film` (`film.FilmHooks`) | `title`, `colours`, `parse_ref`, `tracks`, `mark_help` | the title card, colours, freeze marks that follow a tracked player |
| `site` (`publish.SiteHooks`) | `hidden`, `group`, `groups`, `titles`, `ui`, `is_app`, `app_page` | how your units appear on the publish hub, app pages at `/p/<token>/` |
| `clip_windows(folder)` | | extra clip windows a page needs beyond the `clip:` marks in the report |

Keep `import <your plugin>` cheap (no torch or matplotlib at import time): `sports-video-coach plugins` imports
every plugin to list it.

The basketball plugin (`src/hoop_tape_miner/plugin.py`) uses every hook; read it as the full example.

## Test it

- Keep tests fast with synthetic video (`ffmpeg -f lavfi -i testsrc=...`), as `tests/test_generic_plugin.py` does.
- Check the loop: `run <video> --plugin <name>` exits 3 at your first agent step; `--status` lists your steps.
- `sports-video-coach plugins` must show your plugin with no load error.

## Share it

Publish it as its own repo or package with the GitHub topic `sports-video-coach-plugin`, or open a pull request
here to add it under `plugins/`. Never put real players' video, frames or names in a plugin repo or its tests.
