# Writing the coach report (README.md + README.en.md)

Audience: the players and coach of an amateur team, reading on a phone, often in a group chat. Goal: they understand why the game went the way it did and know what to practise this week.

## Inputs (read these, not the raw sheets)

- `game.json`, `run/official.json` (if any), `run/review_v1/summary.json`, `run/review_v1/plusminus.json`, `run/review_v1/insights.json` (critic-checked coaching insights), `players_facts.md`, focus players' `player<N>_facts.md`, the `memo_part<N>.md` files, the momentum figure (`hoop-tape-miner momentum`).
- **Conclusions and practice come from `insights.json`.** Sections 3, 4 and 5 and each focus player's **Fix** / **Practice** are built from its insights (team insights: `player` null; focus player: `player` = jersey), in its order: `claim` (with its counts), `why`, `rule`, `drill`, `target_next_game`, and the `evidence` / `counter_examples` times as clips or clip links. Do not add a conclusion, rule or drill that is not in it; if something important is missing, say so instead of inventing it. Memos give colour and the narrative of sections 1-2, not new conclusions.
- Every number and every video time in the report must come from these files. If a fact is not there, leave it out or mark it "likely".

## Section skeleton

Keep the headings and order. The HTML page uses the H1 as page title and turns each H2 into a table-of-contents entry, so: exactly one H1, sections as H2, sub-points as H3.

```
# Coach's review: {us_team} {us_score}–{them_score} {them_team} ({date})

Us = {us_colour} {us_team} (home/away). Them = {them_colour} {them_team}. Times are video time (mm:ss).

::: verdict
<Where the game was won or lost, in one sentence with its number.>

<One or two short sentences: the cause, then what worked.>
:::

::: do This week
1. <The first rule from section 4, as an order.>
2. <The second.>
3. <The third.>
:::

::: keys
- **9–21** first half
- **22–4** their run, 07:30–21:12
- **10–2** free throws made
- **8** fast breaks against us (17 of their 38)
:::

![momentum](momentum.en.png)        (README.md: momentum.png, rendered with --lang zh)

<One sentence on the Four Factors from `summary.json` `all.four_factors.decided.text`, with its numbers (eFG%, TOV% live/dead, ORB%, FT rate = FTM/FGA, from `all.four_factors.us|them`) and the points per trip that explain it from `all.ppp`. When `decided.status` is "unclear", say so and why; never pick one yourself. The page draws the Four Factors bars right after this, before section 1.>

::: note
Sources: official = <league feed, what it records>; film = review of N possessions and M trips. <What is estimated; jersey-reading accuracy; what "likely" means.>
:::
```

The page turns these blocks into the first screen: `verdict` is the headline sentence, `keys` become stat tiles
(the bold number first, a short label after it; 3-6 tiles, each a number the report proves later), `do` is the
yellow "what to do" box, `note` is small print. Two more blocks work anywhere: `::: more <summary line>` folds
long evidence (a full scoring table, the play-by-play of a run) behind one line, and `> **Rule:** …` (a
blockquote) marks the one rule of a section. Keep the order verdict, orders, keys: the score board already fills
half a phone screen, so the verdict and the three orders must fit under it (verdict two short sentences, each
order one line). Everything else is below section 1. Keep the `note` to at most two short sentences (<= 220
characters; Chinese <= 110); the source details that do not fit go in a `::: more Sources` fold right after it.

```

---

## 1. Game flow and momentum
- Table of 3-5 stretches: label, video time, score in the stretch, what happened.
- The decisive run, point by point: totals by type first (one line each), then the table of every opposing score in it (official time, score, how we gave it up, type) inside `::: more`.
- Our offence in the same stretch, in counts (possessions, points, ball screens, ball stops, isolations, transition trips and points; `<stretch>.four_factors` and `<stretch>.ppp` give the stretch's Four Factors and points per trip from the film alone).
- Check the team's own theory (e.g. "it was the substitutions") against the film and say plainly whether it holds.
- Comparison table: the bad stretch vs the good stretch, 3-5 rows.

## 2. Scouting report: how {them_team} play
### How they score (in order of importance)
### Key players   (table: #, official points, how to guard)
### How they defend

## 3. How we played and what went wrong
Numbered list, one item per team insight in `insights.json` order: the claim with its count, then why it happened (the insight's `why`, in plain words), with 1-3 video times from its `evidence` (the clearest one as a clip). Low-confidence insights say "likely". End with "What worked (keep doing it)", from the insights' `counter_examples` and the plays the memos praise.
Film clips (see "Film clips" below) go under the decisive-run table, the scouting weapons, our recurring mistakes and what worked.

## 4. Game plan for the next game against {them_team}
**Defence (top priority)** · **Offence** · **Rotation**: numbered, each rule one line, phrased as an instruction: the insights' `rule` fields, grouped; add scouting rules from section 2 only when the film shows them.

## 5. Team practice priorities (in order)
Table: #, focus, drill, measurable target: one row per team insight (its `drill` and `target_next_game`), in `insights.json` order.

## 6. Player-by-player review and practice plan
- 2-3 notes (minutes are estimates; official sheet limits; team problems are not one player's fault).
- Summary table: #, official line, est. minutes (video), one line.
- One H3 per player who played, most minutes first: **Went well** (first, with times) · **Fix** (with times) · **Practice** (two drills, each with a measurable target). For a focus player, **Fix** and **Practice** come from that player's insights (`player` = jersey).
- Roster players the film cannot identify: one short line inviting them to say when they played.
```

## Film clips: show the play next to the claim

Readers discuss the report together, and an argument about "what happened at 12:42" ends the moment everyone watches it. Put a short clip of our video directly under the most important claims, so the page reads: claim, clip, then what to do differently.

**Marker.** One line of its own, under the paragraph, table or list item it proves:

```
![#7 drives into #11's press; no outlet, steal, and-one](clip:03:10-03:19)
```

Times are video time (mm:ss, optionally `mm:ss.s`). Use the *same* window in `README.md` and `README.en.md` (one file serves both); write the caption naturally in each language. Then run `hoop-tape-miner clips <folder>` (it cuts `clips/<from>-<to>.mp4` + poster) and `hoop-tape-miner html <folder>`. The page numbers the clips ("Clip 3 · 03:10–03:19") and adds a slow-motion button. Elsewhere in the text, link to a clip with `[▶ 03:10](#clip-0310-0319)`.

**Which plays get a clip (be selective).** Choose the plays a coach would stop the tape for: the ones that explain the result or that the team will change. Team report: 8–14 clips; player deep dive: 6–8. In order of priority:

1. The decisive run: the 3–5 opposing scores that best show *how* it happened (one clip per type: e.g. turnover → break, nobody back, help foul). Not every basket.
2. The opponent's main weapons from the scouting section: one clip per weapon (their best player's favourite move, their press, their set).
3. Our recurring mistakes from section 3, each with the clearest example.
4. **What worked**: at least 3 clips of us doing it right (the comeback, the best possession). The fix is easier to copy when the team can see it already did it.
5. Player sections: link to a team clip already shown (`[▶ 03:10](#clip-0310-0319)`) rather than adding new ones; add a clip only for a player's single most important habit if no team clip shows it.

Skip plays the film does not show clearly (camera off the ball, players hidden), and plays whose cause the facts sheets mark "unclear".

**Window.** 6–20 s; never over 45 s. Start 2–4 s before the cause (the bad pass, the missed box-out, the leak-out), not at the basket, and end 1–2 s after the result. Official feed times lag the play and have 10 s resolution: take the start from the film-review notes, not from the feed.

**Caption.** One sentence, 25 words at most: who, what happened, and the moment to watch ("watch #19 leave before the rebound"). Jersey numbers only. A caption states what is visible; uncertain identities say "likely".

**Check before you send.** Watch every clip once (or have a subagent read 3–4 frames of each): the play described must be in it, start to finish. Fix the window, re-run `clips` (`--force` re-cuts), delete clip files the stage reports as unused.

## Writing rules

1. **No possession ids, trip ids or file names** in the text. Refer to plays by video time (`12:05`, or `24:10–24:18` for a range). Readers rewatch by time.
2. **No methods appendix.** One "Sources" line under the scoreboard is all the method the reader sees. No talk of CV, clusters, models, pipelines or tokens.
3. Numbers before adjectives: "10 of their 16 points in that stretch came on the break", not "we struggled in transition".
4. Honest uncertainty: "likely #N" when the jersey was unreadable; "unclear" when the film does not show it. Never assign an undecided basket to make totals add up.
5. Every criticism has a video time; every fix has a drill; every drill has a measurable target (count, percentage or time).
6. Start each player's section with what went well. Criticise decisions and habits, not people. Team failures (e.g. nobody back on defence) are framed as team failures.
7. Refer to players by jersey number only, never by name.
8. Plain words for amateur players; short sentences; coaching terms only when the drill uses them.
9. Tables at most 4-5 columns so they fit a phone. Images by relative file name next to the README. Clip markers go on their own line below a table, never inside a cell.
10. No local paths and no links into the repo or the workspace.
11. **Both languages, each a complete file**: `README.md` in Chinese and `README.en.md` in English (the HTML page currently reads exactly these two). Same facts, numbers, times and section order; write each naturally in its language rather than translating word for word. Headings carry the same section numbers in every language.
12. Length: roughly 2,000-3,000 words per language. Cut prose before cutting evidence; fold long tables with `::: more`.

## Voice: an analyst writing for the head coach

Write it the way a team's video coordinator hands the head coach a post-game report: label, number, order.
Short lines a coach can read between two possessions.

- Number first, then what it means, then the order: "Fast breaks against us: 8, for 17 of their 38. Sprint back
  before you look at the ball." / "快攻被打 8 次，丢 17 分（全场 38）。投完先跑回来，再看球。"
- A number needs its baseline or sample: "4 of 11", "in 39 trips", "vs 21–17 after the break".
- Imperatives for fixes, one action each. No "we should consider", no "it is important to".
- Name the play the way players say it: help foul, leak-out, outlet, box-out, 回防、协防、卡位、出球.
- No not-X-but-Y lines, no "notably", "it's worth noting", "overall", no self-asked questions, no closing
  morals, no hype words, no triads for rhythm, few dashes. `sports-video-coach humanize <folder>` flags these;
  the run waits on it. `sports-video-coach guide humanize` has the before/after tables.
- Chinese: 中文与数字之间留空格（"投 5 中 2"），全角标点，不用斜体；短句，一句一个动作。

## Before you finish

- Recount every total you state against `official.json` / `game.json`.
- Check that every video time you cite exists in the facts sheets.
- Every item in sections 3-5 traces to an insight in `insights.json` (same claim, rule, drill, target).
- Grep both files for `P0`, `pid`, `trip`, `.json`, `run/`: none should remain.
- Both files carry the same `clip:` windows (`hoop-tape-miner clips` lists them); every clip shows the play its caption describes.
