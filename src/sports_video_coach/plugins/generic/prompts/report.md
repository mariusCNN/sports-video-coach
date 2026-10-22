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
  4-15 s, one per section at least. The clips stage cuts them. Several videos joined: these are times on the
  joined `video.mp4` (`analysis.json` `sources` gives each file's `start`); say which part a clip is from when it
  helps the reader find it in their own file (e.g. "part 2, 00:08").
- Numbers and cues go in bold or their own bullet, not mid-sentence.
- At most two levels of nesting. Details (long reasoning, references) go at the end under `## Notes`.
- Write the labels in the report's language. In `README.md` (Chinese) use these, so every Chinese report reads the
  same: **录像里看到的** / **为什么会这样** / **正确的样子** / **练习** / **下次怎么检查**, `## 继续保持`, `## 备注`,
  and `**一句话：**` for the bottom line.
- The page shows the sport under the title. A sport the page cannot name in Chinese (it knows tennis, basketball,
  football and about 25 more) is left out of the zh header; to name it, set `"sport": {"zh": "折返跑", "en": "shuttle
  run"}` in `analysis.json`.
