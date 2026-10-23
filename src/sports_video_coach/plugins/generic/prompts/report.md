# Coaching report guide (generic plugin)

Write `README.md` (Chinese, when `zh` is in `languages`) and/or `README.<lang>.md` (e.g. `README.en.md`) in the
analysis folder, from `run/review/review.json`. Same facts in every language.

The reader must be able to scan it in seconds. One idea per line, short bullets, never a wall of text.

## Structure

```markdown
# <Sport>: <who>

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
  joined `video.mp4` (`analysis.json` `sources` gives each file's `start`). The page's clip captions already add
  the file and the time in it (e.g. "00:42.5 · side.mp4 00:17.5"), so the text need not repeat it.
- Numbers and cues go in bold or their own bullet, not mid-sentence.
- At most two levels of nesting. Details (long reasoning, references) go at the end under `## Notes`.
- Write the labels in the report's language. In `README.md` (Chinese) use these, so every Chinese report reads the
  same: **录像里看到的** / **为什么会这样** / **正确的样子** / **练习** / **下次怎么检查**, `## 继续保持`, `## 备注`,
  and `**一句话：**` for the bottom line. In `README.ja.md` (Japanese): **映像で見えたこと** / **なぜ起きるか** /
  **正しい形** / **練習** / **次回の確認方法**, `## 続けること`, `## 備考`, and `**ひとことで：**`. In
  `README.ko.md` (Korean): **영상에서 보인 것** / **왜 그런가** / **올바른 모습** / **연습** / **다음에 확인할 방법**,
  `## 계속할 것`, `## 메모`, and `**한 줄 요약:**`. Any other language: the same labels in that language.
- Write every deliverable in its own language, with no other language's words left in. review.json is written in
  the first language of `languages`; the report in that language may use its words, every other report translates
  them. `likely` / `unclear` become **可能** / **看不清（不确定）** in Chinese, **おそらく** / **見えない（不確か）**
  in Japanese, **아마** / **불분명** in Korean, and every other English phrase is translated unless it is a name (`page-check` flags the ones left, in the page and in the listen / film scripts).
- The title's `<who>` is the focus person: `focus` in `analysis.json`, named in each report's own words (e.g.
  "the player in orange" -> 穿橙色的球员 in `README.md`). No `focus`: name who the review coached; one athlete
  alone in the video (a solo set, a drill) is simply "you": `# Squat: your set` (`# 深蹲：你这一组` in Chinese).
- No date in the title: the page header under it already shows the sport and the date (`analysis.json` `date`).
  A date anywhere else in the text is written as the header prints it for that language: en `23 Oct 2026`,
  fr `23 oct. 2026`, es `23 oct 2026`, de `23.10.2026`, pt `23/10/2026`, zh and ja `2026年10月23日`,
  ko `2026년 10월 23일`.
- Several players in one report: `focus` names them all (`--focus "A in red, B in yellow"`). The title names them
  all, then one `## ` part per player, in the order `focus` gives, each with its own numbered habits (`### 1. ...`
  with the same five parts) and its own clips; `## Keep doing` last, one bullet group per player. Keep one player's
  evidence in that player's part.
- The page shows the sport under the title, named in each page language for tennis, basketball, football,
  volleyball and about 25 more (zh, ja, ko, es, fr, de, pt). Another sport is left out of a zh, ja or ko header and
  shows its English name in the others; to name it, start with `--sport-name zh=折返跑` (repeat it per language:
  `--sport-name fr=navette`), or later set `"sport": {"zh": "折返跑", "fr": "Navette", "en": "shuttle run"}` in
  `analysis.json`. A name given this way always wins over the built-in one.
- French: quotation marks are « … » (with a space inside), not "…".
