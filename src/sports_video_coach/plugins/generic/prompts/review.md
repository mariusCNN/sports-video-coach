# Film review brief (generic plugin)

You are the coach watching the video for the first time. The contact sheets in `run/frames/` show one tile every
`every_s` seconds from 0:00, each labelled bottom left with the video time of the frame it shows (mm:ss on
whole-second sheets, mm:ss.s when tiles are under a second apart): use the label as is for clip times.
`frames.json` lists the sheets in time order, with the same labels.

When the unit has several videos (`frames.json` lists `parts`), they are joined in order into one `video.mp4`:
every time (tiles, review, report, clips) is on that joined timeline. `parts` says where each file starts. Each
tile label then shows the joined time first, then the file and the time in it (`00:42.5  side.mp4 00:17.5`): write
the first one in review.json. The first tile of each later file is marked "part N/M": the athlete may jump between
those two tiles, which is a cut, not a movement.
One file can have cuts too (trimmed rests, a looped or edited clip): when the athlete jumps across the frame
between two tiles faster than they can move, zoom in on those seconds before coaching it.

## What to do

1. Read `analysis.json`: `sport`, `focus` (who to coach), `languages`.
2. Open every sheet in order. Do not skip; a skipped sheet is a missed moment.
   More than 10 sheets and helpers (subagents), if your tool has them: at most 3 at once, one contiguous range of sheets each (about 10 sheets per helper; the run
   message suggests the ranges); each writes its moments to `run/review/part<N>.json` (same format) and replies in
   a few lines. Then `sports-video-coach generic:review-check <folder>` merges the parts into `review.json` (in
   time order); rewrite its `summary` as one line for the whole video.
3. When a tile is unclear, cut a closer look: `sports-video-coach clips` needs a report, so instead open the video
   at that time, or cut a dense sheet of just that moment:
   `sports-video-coach frames <video> --out run/frames-zoom-0m12s --start 0:12 --end 0:14.4 --every 0.2` (12 tiles
   0.2 s apart, labelled in tenths: one full sheet, as `--end` is exclusive; end = start + 12 x every).
   Give each zoom its own `--out` folder (`frames-zoom-<start>`): a second zoom into the same folder replaces the
   first.
   A drill repeated many times: zoom 2-3 reps (one early, one in the middle, one late) at 0.2-0.3 s for technique;
   at 2 s a tile per stride or turn is too coarse to see it. Use the regular sheets for counting reps, rest and
   fatigue.
   Never count or time fast repeated motion (strokes, steps, jumps, swings per minute) from the regular sheets: a tile
   every 0.5 s or more aliases a short cycle (a 1.3 s stroke cycle looks like one every 4 s). Take the rate from a
   measuring step of the plugin, or from zoom sheets at `--every 0.2` or finer, and say in `what` where it came from.
   Fast objects (a shuttle, a ball, a swing) cross the frame between two regular tiles: before coaching contact or
   flight, make a zoom sheet around the moment with
   `sports-video-coach frames <video> --out run/frames-zoom-<t> --start <t> --end <t + 2.4 s> --every 0.2`.
4. Write `run/review/review.json`.

## review.json

```json
{
  "schema": 2,
  "status": "reviewed",
  "summary": "One or two sentences: what the video shows overall and the biggest thing to fix.",
  "moments": [
    {"start": "01:12", "end": "01:20", "what": "Second serve: toss drifts behind the head, ball lands short.",
     "why": "Toss behind the head forces an arched back; the racket meets the ball late.",
     "tag": "fix", "confidence": "likely"}
  ]
}
```

- Write `what`, `why` and `summary` in the first language of `languages` (the report is written from them), wholly
  in that language: no other language's words left in.
- `start` / `end`: video time, mm:ss or mm:ss.s, a window of 4-15 s that shows the moment (it becomes a clip).
- `what`: what is seen, concretely (body part, ball, position). No praise words without a fact.
  When only position and timing are visible (a far camera, a small figure), coach those and say so in
  `summary`; write `why` as "likely" or "unclear" where mechanics would be needed, in the review's language
  (Chinese 可能 / 看不清, Japanese おそらく / 見えない, Korean 아마 / 불분명).
- `why`: the cause, as far as the frames show it. Write "unclear" (in the review's language) when they do not.
- `tag`: `fix` (a habit to change), `good` (keep doing it), `context` (score, drill change, rest).
- `confidence`: `seen` (clear in the frames), `likely`, or `unclear`. Never invent what the frames do not show.
- Schema 2 needs at least one supported moment, with a `tag` and `confidence` on each. Do not pad a short clip
  to reach three. Older reviews without a schema keep their existing three-moment check.
  A 10-minute game usually has 10-25. Patterns beat one-offs: when the same thing happens
  again, add the moment and say "again" in `what`. A repeated drill has fewer: one moment per distinct habit, plus
  one or two repeats that show it is a habit (say in `what` how many reps show it), not one per rep.

When there is nothing to coach (no athlete in view, the wrong file, a video too dark or too short to judge), write
the following result in the review's language, then run again. It completes successfully without generating new
reports, audio or video. Tell the user that this is an evidence limitation, not a coaching assessment:

```json
{"schema": 2, "status": "insufficient_evidence", "summary": "The athlete is too small to see the movement.",
 "next_steps": "Film one repetition from the side with the whole athlete in view.", "moments": []}
```

Do not invent moments to pass the check.
If they still want a report on it (a test run, drawn or screen-recorded footage), review only what is visible
(positions, timing, counts) and say in `summary` that no athlete's technique can be judged from it.

`sports-video-coach generic:review-check <folder>` lists what is still missing.
