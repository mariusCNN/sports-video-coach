# Fitness plugin (`fitness`)

Turns gym and strength & conditioning videos into a coaching page and an explained video. It covers squats,
hinges, pulling derivatives, single-leg work, plyometrics and short "microdose" sessions.

```bash
sports-video-coach run legs1.mp4 legs2.mp4 --plugin fitness --focus "the lifter in the blue shirt" --lang zh
```

Several videos are joined into one timeline (`video.mp4`). The pose pass still reads each source file at its own
frame rate, capped at 60 fps.

## Steps

| Step | Who | Writes |
|---|---|---|
| `frames` | CLI | `run/frames/` contact sheets |
| `sets` | agent (`guide sets`) | `run/review/sets.json`: every set, the exercise id from the library, the view, the reps |
| `pose` | CLI | `run/pose/<set>.npz`: YOLO pose of the lifter in every side, oblique or front-view set |
| `reps` | CLI | `run/reps/reps.json`: per-rep metrics |
| `review` | agent (`guide review`) | `run/review/review.json`: moments with the set, the exercise, the measured number, a cue and a fix |
| `report` | agent (`guide report`) | `README.md`: one section per exercise, then how to fit the training around the sport |
| clips, html, qa, narration, film | core | as for every plugin |

## The exercise library

`src/svc_fitness/library/exercises.json`. It holds every exercise's muscle shares (they sum to 100), cues, typical
faults, dose, regressions and progressions, knee and back notes, its use in basketball, and its sources
(`library/SOURCES.md`).

```bash
sports-video-coach fitness:library               # list
sports-video-coach fitness:library front_squat   # one card
sports-video-coach fitness:library --check       # consistency
```

The muscle shares are training-emphasis estimates from EMG and coaching literature, not EMG of the athlete. The page
weights them by the reps of each set.

## What is measured, and what is not

- Angles (knee at the bottom, trunk lean, hip extension) come only from sets filmed from the side. An oblique set
  is flagged approximate. Front and back views give only rep counts and timing.
- `hip_below_knee`: the hip crease height relative to the knee at the bottom, in leg lengths. A value > 0 means
  below parallel.
- Tempo: the eccentric and concentric times, and the pause at the turn (speed below 0.15 leg lengths/s). Tempo is
  reported only from video at 24 fps or more.
- `slowing_pct`: the concentric time of the last two reps vs. the faster of the first two. It is a proxy for
  velocity loss, not bar speed.
- Not measured: the load (only what can be seen or read), bar speed, force, EMG, and anything out of frame.

## Knowledge

`src/svc_fitness/knowledge/` holds short, sourced notes the report guide points to:
- `programming.md`: dose, microdosing, velocity loss and recovery
- `technique.md`: the main lifts
- `basketball.md`: how to place and adjust the work around games and pickup

## Adding exercises

Add an entry to `exercises.json` with the same fields. Run `fitness:library --check` and `uv run pytest -q
tests/test_fitness.py`.
