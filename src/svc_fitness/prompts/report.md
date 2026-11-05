# Coaching report guide (fitness plugin)

Write `README.md` (Chinese, when `zh` is in `languages`) and/or `README.<lang>.md` in the session folder. Write it
from `run/review/review.json`, `run/review/sets.json`, `run/reps/reps.json` and the exercise cards
(`sports-video-coach fitness:library <id>`). Same facts in every language.

The page already shows the muscle map and the per-set table, in a fold above the report. Do not repeat them as
tables. Point to them ("见上面的「肌肉分布和每组数据」").

Background for the advice: `knowledge/programming.md`, `knowledge/technique.md`, `knowledge/basketball.md` next to
this plugin's `library/`. Cite them by their source keys in `## 备注` only; the body text stays free of keys.

## Structure

```markdown
# 体能训练：<who / the session in a few words>

**一句话：** the single most important change.

::: keys
- **6** 个动作
- **14** 组
- **92°** 前蹲最低膝角
:::

## 这次练了什么
- one bullet per exercise: name, sets x reps, load as seen, pattern (蹲 / 髋铰链 / 单腿 / 爆发拉)
- one line on balance: which patterns and muscles dominate, what is missing (see the muscle map)

## 1. <exercise name>: <the main thing to change, in plain words>

![What the clip shows](clip:03:12-03:24)

**这个动作练什么**
- main muscles with their share (from the card), what each does on court

**录像里看到的**
- 2-3 facts with times and measured numbers

**为什么会这样**
- the cause; "可能" when it is inferred

**正确的样子**
- 1-2 cues

**怎么调整**
- the dose (sets x reps, RIR, tempo), the variant, and a regression or progression
- knee and back notes when they apply

**下次怎么检查**
- a measurable check on the next video

## 2. <next exercise> ...

## 和篮球结合：怎么练、怎么调整
- the weekly placement around games (which day, how far from a game), microdose blocks of 10-20 min
- which exercise transfers to what on court (braking, first step, landing, contact)
- what to change when legs are sore or a game is close
- progression over 4 weeks, with one checkable number per week

## 继续保持
- 1-3 strengths, each with a clip

## 备注
- what was measured and what was not (view, 2D, proxies), and the sources
```

## Rules

- One numbered section per exercise type, most important first. Every section has a clip and the same six bold
  labels in the same order.
- Every claim has a time, a clip or a measured number. Write "可能" / "看不清" where it is inferred or unclear.
- Muscle shares are training-emphasis estimates from the library, not EMG. Say so once.
- Clips: `![caption](clip:mm:ss-mm:ss)`, 4-15 s, on the unit's timeline.
- Page blocks, the language rules and the humanize pass are the same as in the generic guide
  (`sports-video-coach guide report --plugin generic`).
- Scannable: one idea per line, numbers in bold or chips, no wall of text. Put long reasoning under `::: more`.
