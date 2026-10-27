# Writing a plugin

A plugin teaches sports-video-coach one sport (or any video domain): what a unit folder looks like, which steps
turn the video into facts, what the agent reviews, and how the page and the film show it. The core does the rest:
the step driver, provenance, clips, narration, the page, QA, publish links and the explained video.

**Do you need one?** Not to analyse one video: `sports-video-coach run <video> --plugin generic` already gives any
sport a film review, a report, clips, narration, a page and a film. Write a plugin when you want the same sport
again and again with its own prompts, measurements (pose, tracking, a scoreboard reader) or a league import.

## Start from the template

```bash
sports-video-coach new-plugin tennis            # writes <workspace>/plugins/tennis/ (a copy of generic)
sports-video-coach plugins                      # lists tennis
sports-video-coach run serve.mp4 --plugin tennis
```

`<workspace>` is `$SVC_WORKSPACE`, else `./workspace`; `--dir <folder>` writes elsewhere. In a clone, install with
`uv sync --no-group basketball` (no torch; plain `uv sync` adds CUDA torch, several GB, that only basketball tracking
needs) and prefix each command with `uv run`. `new-plugin` sets the plugin's sport to its name; pass `--sport swimming`
for another (the command says which it set; `SPORT` in `__init__.py` holds it). `new-plugin` also prints the command for the tests it wrote (see [Test it](#test-it)).

The copy gets its own name everywhere: `summary` and `use_when`, the stage names in its texts
(`tennis:review-check`) and its agent steps, which say `sports-video-coach guide review --unit <folder>` so the agent
reads the unit's plugin's guides (yours, not the generic ones) from any folder, also when your plugin lives in a
`plugins/` folder above the unit (`guide review --plugin tennis` prints the same file). Agents pick a plugin by `summary`
and `use_when`: give them with `new-plugin tennis --summary "..." --use-when "..."`, or rewrite them in
`__init__.py`; until then `plugins` marks the plugin "summary not written yet".

A unit refers to its source video where it is (`analysis.json` `video` holds its absolute path; only several videos
are joined into the unit's own `video.mp4`), so keep the video in place, or update `video` after moving it.

The copy runs as it is. Make it yours in this order:

1. `prompts/review.md`: what the agent looks for on the contact sheets, in the words of a coach of that sport.
   Sheets are one tile per 0.5 s or more, so they alias fast repeated motion: a 1.3 s stroke cycle can look like one
   every 4 s. Cycle rates and counts of fast motions (strokes, steps, jumps) must come from a measuring step of yours,
   or from zoomed sheets (`frames --every 0.2` or finer), never from the regular sheets. Say so in your `review.md`.
2. `prompts/report.md`: the report's sections (what to work on, drills, a checkable target).
3. Stages for your own measurements, added to the step table before the review.

Local plugins load from `<dir>/<name>/` for these `<dir>`:

- every folder on `$SVC_PLUGIN_PATH` (separated by `;` on Windows, `:` elsewhere).
- `<workspace>/plugins` (where `new-plugin` writes). Set `SVC_WORKSPACE` and it is found from any folder.
- `./plugins`: the `plugins` folder in the current working directory, not the repo or the install folder.
- a `plugins/` folder above a unit folder whose json names the plugin (`"plugin": "tennis"`), so
  `run <unit folder>` finds the plugin of a unit inside the workspace from any folder. The driver passes the
  folders it found to its stages (`SVC_PLUGIN_PATH`).

A plugin that is not found exits with `unknown plugin 'tennis'`, the folders searched (`(missing)` when one does not
exist) and how to add one.

A local plugin imports as the package `svc_plugin_<name>` (`-` becomes `_`), so its own modules are
`svc_plugin_<name>.unit` and so on; inside the plugin use relative imports (`from . import NAME`).

To ship one as a package, declare an entry point:

```toml
[project.entry-points."sports_video_coach.plugins"]
tennis = "svc_tennis.plugin:PLUGIN"
```

## Worked example

[`examples/plugins/swim-stroke-rate/`](../examples/plugins/swim-stroke-rate/) is this template filled in for one
sport: a `stroke` stage measures swimming stroke rate with plain OpenCV and NumPy (no GPU), the review step quotes
it, the page shows it, and a `synth` stage draws a test swimmer at a known rate for the tests. Its README says which
file does what and how to turn it into your sport. Try it in a clone with `SVC_PLUGIN_PATH=examples/plugins`.

Two worked examples: a rate: swim-stroke-rate (above); a count:
[`examples/plugins/jump-rope/`](../examples/plugins/jump-rope/), whose `skip` stage counts jump-rope skips from a
still side view, with its truth test in the plugin's own `tests/`.

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
| `requires`, `install` | import names your stages need beyond the core, and how to get them; `plugins` marks the plugin as not usable while one is missing |
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

### Example: add a command stage

A `pose` stage that writes `run/pose/pose.json` before the review. In `__init__.py`, next to the other stages:

```python
stages={
    "pose": (f"{__name__}.pose", "measure body angles per frame: run/pose/pose.json"),  # pose.py has main(argv)
    ...
},
```

In `unit.py`, a step in `STEPS` before `review`. Its args give the bare stage name; the driver runs it as
`sports-video-coach tennis:pose ...` (`pipeline.stage_cmd` adds the Unit's `PLUGIN`):

```python
P.Step("pose", "cmd", lambda g: (g.run / "pose" / "pose.json").exists(),
       lambda g: [["pose", str(g.video), "--out", str(g.run / "pose")]],
       inputs=lambda g: [g.video], long=True),
```

Try the stage alone with `sports-video-coach tennis:pose <video> --out <folder>`; the run log echoes it in that
form (`[run] pose: sports-video-coach tennis:pose ...`), so a failed step can be pasted and run again.

Provenance tracks a step's `inputs` and `params`, not its code: after editing `pose.py`, run
`sports-video-coach run <unit> --redo pose` (it runs again; a later step that lists its output in `inputs` follows).

`pose.py` is a module with `main(argv)`; the CLI calls it with the arguments after the stage name. The light
install has the core's dependencies: OpenCV (`cv2`), NumPy, edge-tts and markdown-it-py. Anything else (a pose
model, pandas) goes in `requires` and `install` so `plugins` says what is missing.

```python
"""Stage `pose <video> --out <folder>`: body angles per frame -> <folder>/pose.json."""
import argparse
import json
from pathlib import Path

import cv2


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sports-video-coach tennis:pose")
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cap = cv2.VideoCapture(a.video)
    fps, frames = cap.get(cv2.CAP_PROP_FPS) or 30.0, []
    ok, img = cap.read()
    while ok:
        frames.append({"t": round(len(frames) / fps, 2), "knee_deg": None})  # your measurement here
        ok, img = cap.read()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pose.json").write_text(json.dumps({"frames": frames}), encoding="utf8")
```

The agent sees the json through the review step: add its path to `fill_values()` in `unit.py` and name it in the
step's `how` text, which the driver prints with the placeholders filled in:

```python
def fill_values(self) -> dict:          # in class Analysis
    return dict(super().fill_values(), ..., pose=self.run / "pose" / "pose.json")

P.Step("review", "agent", ..., how="Film review: ... Use the knee angles in {pose} (one row per frame) ...")
```

The page shows it through the `page` hook (`render_html.PageHooks`, see [Hooks](#hooks)); `before` returns HTML
above the report (`intro` instead puts HTML inside each language's report, before its first section; it is
called once per language, with that one language in `langs`):

```python
def pose_file(folder):
    from .unit import Analysis
    return Analysis.load(folder).run / "pose" / "pose.json"

def pose_box(folder, band, langs):      # page.py; band data and langs as render_html passes them
    p = pose_file(folder)
    return f"<p>{len(json.loads(p.read_text(encoding='utf8'))['frames'])} frames measured</p>" if p.exists() else ""

# in __init__.py: from .page import pose_box, pose_file
PLUGIN = Plugin(..., page=PageHooks(before=pose_box, inputs=lambda folder: [pose_file(folder)]))
```

`inputs` names the files your page hooks read. The run's html step then re-renders the page when one of them
changes, as it does for READMEs, audio and clips. Without it, a re-measured number stays old on the page and the
run still ends with exit 0.

Rules that keep agents honest: every agent step has a validator (`errors`), every number the agent writes comes from
a file a command step made, and the review format says "unclear" is a valid answer.

## Hooks

All optional; without them the page and the film are the generic ones.

Each field of each hook object falls back to the default on its own, so set only what you need.

| Hook | Fields | Use it for |
|---|---|---|
| `page` (`render_html.PageHooks`) | `ui`, `board`, `band`, `before`, `intro`, `sections`, `inputs` | page labels, the top band (a score, a summary), HTML above the report, before its section 1 or after it, the files those read |
| `scenes` (`{"court": film.SceneKind}`) | `prefix`, `noun`, `parse`, `render`, `problems`, `steps` | new scene kinds in `film.<lang>.md`, e.g. `![...](court:play.json)` |
| `film` (`film.FilmHooks`) | `title`, `colours`, `parse_ref`, `tracks`, `mark_help` | the title card, colours, freeze marks that follow a tracked player |
| `site` (`publish.SiteHooks`) | `hidden`, `group`, `groups`, `titles`, `ui`, `is_app`, `app_page` | how your units appear on the publish hub, app pages at `/p/<token>/` |
| `clip_windows(folder)` | | extra clip windows a page needs beyond the `clip:` marks in the report |

Keep `import <your plugin>` cheap (no torch or matplotlib at import time): `sports-video-coach plugins` imports
every plugin to list it.

The basketball plugin (`src/hoop_tape_miner/plugin.py`) uses every hook; read it as the full example.

## Test it

`new-plugin` writes `<name>/tests/test_<name>.py` in the plugin folder and prints the command that runs it.
After `uv tool install` the tool's environment has no pytest (and a plain `uv run pytest` may pick up an unrelated
project), so it runs in a throwaway environment on the commit you installed (the one below is the pinned install):

```bash
uv run --isolated --no-project --with pytest --with sports-video-coach@git+https://github.com/mariusDing/sports-video-coach@ef4fb792e8a37ee4f27d5d189c03157468757520 pytest workspace/plugins/tennis
```

In a clone: `uv run pytest workspace/plugins/tennis` (or the folder you gave `--dir`); `uv sync --no-group basketball` is enough.

It checks three things, and is the pattern for your own tests:

- The plugin loads with no error: it puts the plugin's parent folder on `SVC_PLUGIN_PATH`, drops
  `svc_plugin_<name>` from `sys.modules` and calls `plugin.plugins(refresh=True)`.
- `sports-video-coach plugins --json` lists it with its stages.
- Its step table (`PLUGIN.kinds[0].step_table()`) runs frames before review before report and ends with film, so a
  step you add before the review keeps it passing.

A hyphen in the name (`swim-rate`) is fine, also with relative imports in `__init__.py` (`from .page import ...`):
pytest would import such a folder's `__init__.py` as a lone module, so sports-video-coach installs a small pytest
plugin that collects it as a plain folder. Nothing to add to your plugin for it.

A commented example at the end runs one of your stages on a 3-second ffmpeg test video in `tmp_path`: uncomment it
and name your stage once you have one.

More:

- Keep tests fast with synthetic video (`ffmpeg -f lavfi -i testsrc=...`), as `tests/test_generic_plugin.py` does.
- Check the loop: `run <video> --plugin <name>` exits 3 at your first agent step; `--status` lists your steps.
- `sports-video-coach plugins` must show your plugin with no load error.

## Share it

Publish it as its own repo or package with the GitHub topic `sports-video-coach-plugin`, or open a pull request
here to add it under `examples/plugins/`, modelled on a worked example (a rate:
[`examples/plugins/swim-stroke-rate/`](../examples/plugins/swim-stroke-rate/); a count:
[`examples/plugins/jump-rope/`](../examples/plugins/jump-rope/)). Never put real players' video, frames or names in a plugin repo or its tests.

For a pull request, write it there from the start, in a clone of your fork:

```bash
uv sync --no-group basketball
uv run sports-video-coach new-plugin rowing --dir examples/plugins --summary "..." --use-when "..."
export SVC_PLUGIN_PATH=examples/plugins          # PowerShell: $env:SVC_PLUGIN_PATH = "examples/plugins"
uv run sports-video-coach plugins                # lists rowing
```

`./workspace/` (the default place) is gitignored, so a plugin left there never shows in `git status`.
`examples/plugins/` is not searched unless it is on `SVC_PLUGIN_PATH`; `new-plugin` prints that line first.

Ready for review when:

- `README.md` in the plugin folder says what it measures, how, the output file, what was checked against a known
  truth (the numbers) and what was not.
- Its `tests/` measure a synthetic video (ffmpeg-drawn, no people) and assert the known truth, not just that a file
  exists; CI has ffmpeg, so they run there.
- `uv run sports-video-coach run <test video> --plugin <name>` runs your measurement and stops with exit 3 at the review.
- `uv run pytest -q` passes (the whole suite collects `examples/plugins/`), and `CHANGELOG.md` has a line under
  *Unreleased* / *Added*.
