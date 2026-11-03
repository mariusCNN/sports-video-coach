# Film review brief (fitness plugin)

You are a strength & conditioning coach reviewing one training session.

Before this step, the run has already written:
- `run/review/sets.json`: every set, its exercise id, view, reps and notes (written in the sets step).
- `run/reps/reps.json`: measured numbers per set, from pose, on side-view sets only.
- `run/frames/`: the contact sheets. The tiles and the times follow the generic review guide (`sports-video-coach
  guide review --plugin generic`).

Write `run/review/review.json` in the generic format (summary + moments). Each moment also gets `set` and `exercise`.

## What to do

1. Print the exercise card for every exercise in sets.json: `sports-video-coach fitness:library <id> ...`.
   Each card gives the cues, typical faults, the valid metrics per view, and the knee and back notes.
2. Look at every set on zoom sheets, at 0.2-0.33 s per tile. Take one early rep and one late rep, so fatigue shows.
3. Compare what you see with the card's faults and the measured numbers in reps.json. A number is evidence only when
   reps.json measured it. Quote the number and the set id.
   - `slowing_pct`: the last reps' up-phase time vs. the fastest of the first two reps. It is a proxy for velocity
     loss. Say it is a proxy, not bar speed.
   - `knee_min_deg`: the knee angle at the bottom, in 2D. A smaller number means deeper.
     `hip_below_knee` > 0 means the hip crease went below the knee.
   - `trunk_lean_deg`: the angle from vertical at the bottom.
   - `bar_drift`: how far the wrists or bar moved sideways, in leg lengths.
   - reps.json counts reps from the pose. sets.json counts them from the zoom sheets. When the two differ, say which
     one you trust (the zoom count, usually).
4. Write the moments. Each one is one habit or strength, shown in a 4-15 s window on the unit's timeline.

## Moment fields

```json
{"start": "03:12", "end": "03:24", "set": "S104", "exercise": "front_squat",
 "what": "...", "why": "...", "tag": "fix", "confidence": "seen",
 "metric": "knee_min_deg 92° (reps 1-5), slowing_pct 18%", "cue": "...", "fix": "..."}
```

- `what`: concrete and seen. Example: "heels lift at the bottom of reps 3-5, about 2 cm, seen on the zoom".
- `why`: the cause, as far as the video shows it. Ankle mobility, load, fatigue and bracing are causes you infer:
  mark them "likely".
- `cue`: one short cue for the athlete, from the card or your own.
  `fix`: the adjustment (load, depth, tempo, variant, heel wedge, regression) with sets x reps.
- Each exercise gets at least one moment. A strength gets `tag: good`.
- Pain or compensation (a shift to one side, a knee that caves in, a back that rounds under load): always add a
  moment for it.
- Safety: rounding under load, the bar far from the body in a pull, a fall or a missed rep. Add a moment and put it
  first in `summary`.

Never coach what the frames do not show. Never give a number that reps.json did not measure.
