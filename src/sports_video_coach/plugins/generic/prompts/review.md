# Film review brief (generic plugin)

You are the coach watching the video for the first time. The contact sheets in `run/frames/` show one tile every
`every_s` seconds, each labelled with its video time (mm:ss, or mm:ss.s when
tiles are under a second apart). `frames.json` lists the sheets in time order.

When the unit has several videos (`frames.json` lists `parts`), they are joined in order into one `video.mp4`:
every time (tiles, review, report, clips) is on that joined timeline. `parts` says where each file starts, and the
first tile of each later file is marked "part N/M": the athlete may jump between those two tiles, which is a cut,
not a movement.
One file can have cuts too (trimmed rests, a looped or edited clip): when the athlete jumps across the frame
between two tiles faster than they can move, zoom in on those seconds before coaching it.

## What to do

1. Read `analysis.json`: `sport`, `focus` (who to coach), `languages`.
2. Open every sheet in order. Do not skip; a skipped sheet is a missed moment.
   With helpers (subagents), if your tool has them: at most 3 at once, one contiguous range of sheets each (about 10 sheets per helper; the run
   message suggests the ranges); each writes its moments to `run/review/part<N>.json` (same format) and replies in
   a few lines. Then `sports-video-coach generic:review-check <folder>` merges the parts into `review.json` (in
   time order); rewrite its `summary` as one line for the whole video.
3. When a tile is unclear, cut a closer look: `sports-video-coach clips` needs a report, so instead open the video
   at that time, or cut a dense sheet of just that moment:
   `sports-video-coach frames <video> --out run/frames-zoom --start 0:12 --end 0:15 --every 0.2` (tiles 0.2 s apart,
   labelled in tenths).
   A drill repeated many times: zoom 2-3 reps (one early, one in the middle, one late) at 0.2-0.3 s for technique;
   at 2 s a tile per stride or turn is too coarse to see it. Use the regular sheets for counting reps, rest and
   fatigue.
4. Write `run/review/review.json`.

## review.json

```json
{
  "summary": "One or two sentences: what the video shows overall and the biggest thing to fix.",
  "moments": [
    {"start": "01:12", "end": "01:20", "what": "Second serve: toss drifts behind the head, ball lands short.",
     "why": "Toss behind the head forces an arched back; the racket meets the ball late.",
     "tag": "fix", "confidence": "likely"}
  ]
}
```

- Write `what`, `why` and `summary` in the first language of `languages` (the report is written from them).
- `start` / `end`: video time, mm:ss or mm:ss.s, a window of 4-15 s that shows the moment (it becomes a clip).
- `what`: what is seen, concretely (body part, ball, position). No praise words without a fact.
  When only position and timing are visible (a far camera, a small figure), coach those and say so in
  `summary`; write `why` as "likely" or "unclear" where mechanics would be needed.
- `why`: the cause, as far as the frames show it. Write "unclear" when they do not.
- `tag`: `fix` (a habit to change), `good` (keep doing it), `context` (score, drill change, rest).
- `confidence`: `seen` (clear in the frames), `likely`, or `unclear`. Never invent what the frames do not show.
- At least 3 moments; a 10-minute game usually has 10-25. Patterns beat one-offs: when the same thing happens
  again, add the moment and say "again" in `what`. A repeated drill has fewer: one moment per distinct habit, plus
  one or two repeats that show it is a habit (say in `what` how many reps show it), not one per rep.

When there is nothing to coach (no athlete in view, the wrong file, a video too dark or too short to judge), do
not invent moments to pass the check: stop and tell your user what the video shows and what video would work.
If they still want a report on it (a test run, drawn or screen-recorded footage), review only what is visible
(positions, timing, counts) and say in `summary` that no athlete's technique can be judged from it.

`sports-video-coach generic:review-check <folder>` lists what is still missing.
