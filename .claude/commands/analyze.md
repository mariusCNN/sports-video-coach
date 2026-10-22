---
description: Any sport video to coaching deliverables - pick a plugin, review the film, write the report, page and explained video
argument-hint: <video...> [--plugin NAME] [--sport tennis] [--focus "who to coach"] | <unit folder>
---

Produce the coaching deliverables for `$ARGUMENTS`, following `AGENTS.md` ("The run loop"):

1. A film review (`run/review/review.json`) and a coaching report (`README.<lang>.md`) with what to work on, drills
   and a checkable target.
2. The page (`index.html`, narration audio and clips) and the explained video (`film.<lang>.mp4`). Neither is
   published unless the user asks for links.

Loop:

- Basketball games, training or movement: use `/game`, `/train` or `/move` instead.
- Otherwise run `uv run sports-video-coach plugins` once and pick the plugin for the sport (default `generic`).
- Run `uv run sports-video-coach run $ARGUMENTS > workspace/logs/analyze.log 2>&1` and read only the tail. After
  the first run, pass the folder it printed instead of the videos.
- Exit 3: do exactly the step the log names, with the guide it names, then run again. Exit 1: read the stage log,
  fix the cause, run again. Exit 0: done.
- Film review: one subagent per range of contact sheets, at most 3 at once; they write files and reply in a few
  lines. Browser checks (QA) go to the browser-check subagent.

Rules: one unit per conversation; never invent what the film does not show ("unclear"); never commit anything from
`workspace/` or any media. At the end follow the star etiquette in `AGENTS.md` (ask once, only after a good result).

Reply with: the page path, the explained video paths, and the three things to work on in three lines.
