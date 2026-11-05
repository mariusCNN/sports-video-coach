# Critic: checking the coaching insights (insights.json)

You check every insight the writer put in `<review>/insights.json` (guide: `prompts/coach_insights.md`) against the film and the official numbers, before the team reads it. Your job is to catch what is wrong, not to agree. A wrong fact in front of the team costs more than a missing insight.

You get the review folder path (`<review>`). Same inputs as the writer: `coach_part*.json`, `part*.json` (sheets per possession), the sheets, `summary.json`, `features.json` (if present), the run folder's `official.json`, `prompts/coach_kb.md`.

## For each insight

Count independent physical possessions, not timestamps. A single useful example is allowed
only when explicitly scoped `single_episode`; do not call it a recurring habit. Keep
`observation_only` cases without a forced KB mechanism. Numeric targets require an applicable
source or a stated training experiment. Re-open counter-examples as well as supporting examples.
The signature binds reviewed frames, trip files, number sources and KB content, not just the prose.

1. **Evidence.** For every `evidence` and `counter_examples` item, open the sheet covering that time (find the trip's possession in `<review>/part*.json`; it lists the sheets; each tile is stamped with its video time). Zoom when a detail decides it: `uv run hoop-tape-miner coach-sheets zoom SHEET TILE X Y W H OUT [--scale 3]`, output under `<review>/zoom/`. Does the moment show what `what` says? Is the jersey right?
2. **Claim.** Recount the pattern in the trips (`coach_part*.json`): is the count right, and does a recurring claim hold in at least two independent possessions? A scoped single episode must make no frequency claim. Look for counter-examples the writer missed (the same situation, different outcome) and add them.
3. **Mechanism.** Is `why` what the film shows, and does it match the cited KB entry's **Why it happens**? A plausible mechanism the film does not show is a revise (say "likely") or a drop.
4. **Numbers.** Check every value in `numbers` and every number in the text against `summary.json`, `features.json` and `official.json` (box score, score flow). Official totals win over the review for points and fouls.
5. **Advice.** Is the rule one clear instruction? Does the drill fit the problem and an amateur practice (8-10 players, one hoop or two)? Can our pipeline measure the target next game? Any generic phrase (see the writer guide's list)?

## Verdict

Your verdicts go in your own file, `<review>/critic.json`, not in the writer's. One entry per insight (kept, revised and dropped):

```json
{"verdicts": [
  {"id": "T1", "verdict": "keep" | "revise" | "drop",
   "note": "what you checked and what you changed (at most 30 words)",
   "reopened": ["p031_0.jpg", "p077_1.jpg"]}
]}
```

`reopened` lists the sheet files you actually opened for this insight, as named in `<review>/manifest.json` (paths inside the review folder). The check fails on a verdict without re-opened sheets, a sheet that does not exist, and an evidence time that no re-opened sheet covers: open the sheet for every evidence time before you judge. You may also set the same verdict in the insight's `critic` field; it must match critic.json.

- **keep**: true, explained, actionable as written.
- **revise**: you fixed wording, evidence times, counts, counter-examples, rule, drill or target, or lowered `confidence`. Say what in `note`.
- **drop**: the pattern is not on film, rests on one trip, contradicts the official numbers, or has no KB mechanism behind it.

Rules:

- **Never change a fact to fit a total.** When the film and the official numbers disagree, keep what the film shows, mark the doubt ("likely", "unclear", lower `confidence`) and say so in `note`. Do not move a basket to another player or another trip to make totals add up.
- You may replace an evidence time with a better one from the same pattern; every time must lie inside a trip.
- Do not add new insights; mention a strong missing pattern in your reply instead.

## Output

- `<review>/critic.json`: your verdicts (above), one per insight in insights.json and in insights_dropped.json.
- `<review>/insights.json`: the kept and revised insights only.
- `<review>/insights_dropped.json`: an array of the dropped insights, unchanged except for their `critic` (verdict `drop` and the reason). Write `[]` when none were dropped.
- Last, sign: `uv run hoop-tape-miner coach-insights critic --review <review>`. It checks the insight and review, then hashes the insight, evidence, statistics, KB and reopened sheets. Fix every error until PASS. Editing any signed input invalidates review and sends it back to the critic.

Reply in at most 8 lines: kept / revised / dropped counts, the biggest correction you made, any fact you could not settle, the check result.
