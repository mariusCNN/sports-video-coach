# jump-rope: a second worked example plugin

One sport, one measured number, a count this time (the swim example measures a rate). This plugin is
`sports-video-coach new-plugin jump-rope` plus one measuring stage.

## What it measures

- **Skips:** how many times the jumper leaves the ground, the rate per minute and the time of each skip, from a
  side view with a still camera.
- **How:** each frame shrunk to grey 160 px wide; the pixels that differ from the median frame give the jumper's
  height; one skip is one rise past 70 % of the height range after a fall below 30 %. Plain OpenCV and NumPy.
- **Output:** `run/skip/skip.json` (`skips`, `skips_per_min`, `at_s`, `duration_s`).
- **Checked:** a drawn jumper with grain at 1.5, 2.3 and 3.0 skips per second counts 15, 46 and 30, the exact
  truth (`tests/test_jump_rope.py`).
- **Not checked:** real video. A swinging rope, a second person or a moving camera will move the count; a skip cut
  off by the end of the video counts once it is past 70 % of the height.

## Run it

In a clone, after `uv sync --no-group basketball`:

```bash
export SVC_PLUGIN_PATH=examples/plugins          # PowerShell: $env:SVC_PLUGIN_PATH = "examples/plugins"
ffmpeg -f lavfi -i color=c=0x202830:s=320x240:r=30:d=20 -f lavfi -i color=c=white:s=40x80:r=30:d=20 \
  -filter_complex "[0][1]overlay=x=140:y='140-50*abs(sin(PI*2.3*t))':shortest=1,format=yuv420p" skip.mp4   # truth 46
uv run sports-video-coach jump-rope:skip skip.mp4 --out out/      # 46 skips (138.0/min)
uv run sports-video-coach run skip.mp4 --plugin jump-rope         # counts, cuts the sheets, exit 3 at the review
uv run pytest examples/plugins/jump-rope
```

## Which file does what

| File | Plugin contract |
|---|---|
| `__init__.py` | `PLUGIN`: name, summary, `use_when`, stages, the unit kind, the page hook |
| `skip.py` | the `skip` stage: video -> `skip.json` |
| `unit.py` | the step table: `skip` before `frames` and `review`; the review's text names `{skip}` |
| `page.py` | `PageHooks.before`: the count above the report; `inputs` re-renders it when the json changes |
| `prompts/review.md` | quote the count from `skip.json`; what a jump-rope coach looks for |
| `tests/` | the template's tests plus `skip` before `review` and the count on drawn video |

Everything else (`new.py`, the other prompts, clips, narration, page, QA, film) is the template and the core.
