# Sets guide: split a training session into sets

You write `run/review/sets.json`: every set in the video, in time order, with the exercise named from the library.
A later step measures each side-view set from the athlete's pose, so the windows and views must be right.

## What counts as a set

- One set = the reps of one exercise done without a break longer than about 10 s.
- Warm-up sets count as sets. Write `"warmup": true` on them.
- Rest, walking around, loading plates and talking are not sets.
- A superset (A then B with no rest) is two sets. Give each its own window.
- One side, then the other (a single-leg exercise): one set per side, with `"side": "L"` or `"R"`.
  Use `"both"` when the sides alternate rep by rep.

## How to find them

1. The regular sheets (one tile every 1-2 s) show where the sets are.
   They alias fast motion, so do not count reps on them.
2. For each set, cut a zoomed sheet and count the reps there:
   `sports-video-coach frames <video> --out run/frames-zoom-S01 --start 1:02 --end 1:05 --every 0.25`.
   Make it one tile every 0.2-0.33 s. Take several zooms for a long set.
3. Pick the exercise id from `sports-video-coach fitness:library`. `fitness:library <id>` prints one card.
   No id fits: use `"exercise": "other"` and give `"name"`, one per language: `{"zh": "摆臂", "en": "arm swings"}`.

## sets.json

```json
{
 "summary": "<one sentence: what the session was>",
 "sets": [
  {"id": "S01", "start": "0:12", "end": "0:41", "exercise": "front_squat", "name": "",
   "view": "side", "reps": 5, "load": "barbell + 2x10 kg (likely 40 kg)", "side": "",
   "warmup": false, "who": null, "tempo_seen": "slow down ~2 s, fast up",
   "notes": "<what you saw, in the report language, with times: depth, heels, trunk, knees, bar path, breathing>"}
 ]
}
```

- `start` / `end`: mm:ss on the unit's timeline (a joined unit: the joined timeline the sheets show).
  Start about 1 s before the first rep and end about 1 s after the last.
- `view`: the camera relative to the athlete.
  - `side`: you see the profile, so knee and hip angles are valid.
  - `front` / `back`: knees in or out, and left vs right.
  - `oblique`: in between; angles are approximate.
  - `unclear`
- `reps`: counted on a zoomed sheet. Write `null` when you cannot tell. Never guess.
- `load`: only what you can see or read (plates, dumbbell numbers). A guess must say "likely". Unknown: `"unclear"`.
- `who`: when other people are in the frame, the athlete's box `[x0, y0, x1, y1]` in source-video pixels at the set
  start. Otherwise `null`.
- `notes`: concrete observations with times. Do not judge here. The review does that.

Check with `sports-video-coach fitness:sets-check <folder>` until it says OK.
