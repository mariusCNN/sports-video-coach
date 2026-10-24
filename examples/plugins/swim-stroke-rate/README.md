# swim-stroke-rate: a worked example plugin

One sport, one measured number. This plugin is `sports-video-coach new-plugin swim-stroke-rate --sport swimming`
plus one measuring stage. Copy it when you write your own.

## What it measures

- **Stroke rate:** full arm cycles per minute, from a side-view video with a still camera.
- **How:** each frame shrunk to grey 64x36, its first principal components over time, the peak of their spectrum
  in 15-120 cycles/min. Plain OpenCV and NumPy: no GPU, no model download.
- **Output:** `run/stroke/stroke.json` (`stroke_rate_spm`, `cycle_s`, `peak_strength`, a rate per 10 s window).
- **Checked:** a drawn swimmer at a known 45 cycles/min measures 45.0 (`tests/test_swim_example.py` in the repo).
  Rates from 20 to 120 measured within 0.1 on the same kind of clip.
- **Not checked:** real pool video. Splashes, a moving camera or two swimmers in frame will move the number.

## Run it in 3 commands

In a clone, after `uv sync --no-group basketball`:

```bash
export SVC_PLUGIN_PATH=examples/plugins          # PowerShell: $env:SVC_PLUGIN_PATH = "examples/plugins"
uv run sports-video-coach swim-stroke-rate:synth swim.mp4 --spm 45 --seconds 20   # a test swimmer, truth 45
uv run sports-video-coach run swim.mp4 --plugin swim-stroke-rate
```

- The run measures the rate, cuts the frame sheets and stops with **exit 3** at the film review.
- From there it is the normal loop (`AGENTS.md`): your agent writes the review and the report, you run again.
- Measure only: `uv run sports-video-coach swim-stroke-rate:stroke swim.mp4 --out out/`.
- Tests: `uv run pytest examples/plugins/swim-stroke-rate`.

## Which file does what

| File | Plugin contract |
|---|---|
| `__init__.py` | `PLUGIN`: name, summary, `use_when`, stages, the unit kind, the page hook |
| `stroke.py` | the `stroke` stage: video -> `stroke.json` (the one new piece of computer vision) |
| `unit.py` | the step table: `stroke` before `frames` and `review`; the review's text names `{stroke}` |
| `page.py` | `PageHooks.before`: the measured rate above the report; `inputs` re-renders it when the json changes |
| `synth.py` | the `synth` stage: a test video with a known rate, so tests need no real footage |
| `new.py` | the `new` stage from the template: starts a unit folder from the video |
| `prompts/` | the template's writing guides; `review.md` says to quote the rate from `stroke.json` |
| `tests/` | the template's tests (loads, listed, step order) plus `stroke` before `review` |

Everything else (clips, narration, page, QA, film) comes from the core through `pipeline.tail_steps`.

## Turn it into your sport

1. **Start fresh:** `sports-video-coach new-plugin rowing --summary "..." --use-when "..."`.
2. **Copy the stage:** `stroke.py` -> `<yours>.py`. Keep `main(argv)`, `--out` and one json.
3. **Change the measurement:** a rowing stroke is also one cycle, so the spectrum may work as it is.
   A count, an angle or a speed needs your own code in `measure()`.
4. **Wire it in:** the stage in `__init__.py`, the step in `unit.py` before `review`, the path in `fill_values()`.
5. **Show it:** a `page.py` hook, with `inputs` naming the json.
6. **Test it:** a `synth` of your motion with a known truth, and one test that measures it.

Read `docs/plugins.md` for the full contract and the hooks.
