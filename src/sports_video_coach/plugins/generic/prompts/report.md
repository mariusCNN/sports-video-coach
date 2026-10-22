# Coaching report guide (generic plugin)

Write `README.md` (Chinese, when `zh` is in `languages`) and/or `README.<lang>.md` (e.g. `README.en.md`) in the
analysis folder, from `run/review/review.json`. Same facts in every language.

The reader must be able to scan it in seconds. One idea per line, short bullets, never a wall of text.

## Structure

```markdown
# <Sport>: <who>, <date>

**Bottom line:** one sentence, the single most important thing to change.

## 1. <The habit to fix, in plain words>

![What the clip shows](clip:01:12-01:20)

**What the video shows**
- the evidence: 2-3 moments with their times

**Why it happens**
- the cause (body, timing, decision); "likely" or "unclear" when the frames do not prove it

**The correct model**
- what good looks like, in one or two cues a player can remember

**Drill**
- one drill: name, sets x reps, the cue to say each rep

**How to check next time**
- a measurable check on the next video (e.g. "7 of 10 tosses in front of the head")

## 2. ...

## Keep doing
- 1-3 strengths, each with its clip
```

## Rules

- 2-4 numbered sections, most important first; each has a clip, then the same five bold-labelled parts in
  the same order.
- Every claim has a time or a clip from `review.json`. Never add what the review did not see.
- Clips: `![caption](clip:mm:ss-mm:ss)` in video time (`mm:ss.s` works too),
  4-15 s, one per section at least. The clips stage cuts them.
- Numbers and cues go in bold or their own bullet, not mid-sentence.
- At most two levels of nesting. Details (long reasoning, references) go at the end under `## Notes`.
