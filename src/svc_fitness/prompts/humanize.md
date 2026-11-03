# Humanize pass: make it sound like a coach wrote it

The last pass over every report, narration script (`listen.<lang>.md`) and film script (`film.<lang>.md`). The
run checks the files (`sports-video-coach humanize <folder>` runs the same check) and keeps the writing step
waiting while it finds stock AI phrasing. Fix each finding, or keep a phrase you really mean with
`--accept <step>`.

The goal is not to beat a detector. A player stops listening the moment the text sounds like a chatbot or a
press release. Make it sound like their coach talking to them after the game.

## Rules

1. **Keep every fact.** Numbers, times, players, clip markers, freeze lines and the order of points stay exactly
   as they are. Rewrite only the wording. If a sentence has no fact in it, it can usually go.
2. **Say the thing.** Not "it's not X, it's Y" / "不是…而是…": say Y. Not "the key is…" / "关键在于…": say
   the action.
3. **Spoken register.** Short sentences. "So", "and", "but", not "moreover", "thus", "此外", "从而", "然而".
   Read it out loud once; if you would not say it on the bench, change it.
4. **Concrete, not hyped.** No "crucial", "game-changer", "masterclass", "至关重要", "教科书级", "完美诠释".
   Point at what happened: "he stopped at half court and watched".
5. **No host talk, no staging.** No "let's dive in", "让我们一起来看看", no asking a question to answer it
   ("Why? Because…" / "为什么？因为…"), no summary openers ("overall", "总的来说"), no one-line moral at the end
   of a paragraph ("这就是为什么…").
6. **No slide labels in speech.** A narration paragraph does not open with "练习：" or "Goal:". Say it:
   "练的是…", "下场我们要…". Labels belong on cards and in the page's headings, not in what is read aloud.
   "看：" / "注意：" / "Watch:" are fine; that is how a coach points at the screen.
7. **Few dashes.** Use a full stop or a comma. A dash in every other sentence is the clearest sign of
   generated text.
8. **Vary it.** Not every point in threes, not every paragraph the same length, not every sentence opening
   the same way.

## Chinese: how a coach says it

| Stock phrasing | A coach says |
|---|---|
| 问题不在他，在于没人接应 | 他没错，是没人去接他 |
| 这不仅仅是体能问题，更是习惯问题 | 这是习惯，不是累 |
| 值得注意的是，第三节我们只回防了一人 | 第三节，只有一个人回防 |
| 为什么？因为他在看球 | 他在看球，没跑 |
| 因此，我们需要提前补防 | 所以补防要早一步 |
| 练习：四打四转换 | 练的是四打四转换 |
| 总的来说，这场输在回防 | （删掉，前面已经说过了） |

Use the words players use on the court: 回防、补位、协防、挡拆、空切、卡位、出球、落位. Use 我们 for the team.
Short sentences, one action each.

## English: how a coach says it

| Stock phrasing | A coach says |
|---|---|
| It's not about effort, it's about timing | You were working. You were just late. |
| Notably, only one player got back | Only one guy got back. |
| This is a crucial habit to build | Build this habit. |
| Why? Because he was ball-watching | He was watching the ball. |
| Let's take a closer look at this play | Watch this one. |
| Overall, transition defense cost us the game | (cut it; you already said it) |

## How to do the pass

1. Run `sports-video-coach humanize <folder>` (or read the run's message: it lists each finding with the file).
2. Rewrite each flagged sentence by the rules above. Keep the facts; check the numbers against the review.
3. Read the whole script once more for what the check cannot see: forced triads, every paragraph ending on a
   punchline, the same opening twice in a row, praise that the film does not show.
4. Run the check again; run the pipeline again.
