# Write decision lessons for ordinary players

The audience includes teammates and players who have never seen this team. Use friendly,
literal language. Point out who to watch by shirt and location before using a jersey number.
Teach one visible cue and one usable action, including when that action would be unsuitable.

## Observe before explaining

1. Re-open the original play around the choice, including the time before it. Contact sheets
   locate a moment; sample more densely if release, control or a coverage change is ambiguous.
2. Record the observable cue, actual action, decision quality, execution and outcome separately.
   A miss can follow a reasonable shot. A completed pass can be useful without a basket.
3. Propose only alternatives the player could plausibly use with the visible information.
   State their conditions. Keep multiple reasonable choices. Unknown team calls stay unknown.
4. Keep uncertainty separate for identity, timing, choice and outcome. Do not turn a manual's
   coaching principle, a player's reflection or a tracking proposal into an observed game fact.
5. Count distinct physical possessions. Two timestamps in one trip are not repetition. A missed
   shot and putback can cross trip labels while remaining one possession; group them explicitly.

## Author one shared source

Write `lessons.json` in each report folder, using `templates/lessons.example.json`.
Team and personal lessons are separate bundles. Private notebooks stay in the private workspace.

- `episodes`: source windows, decision/action/outcome times, visible cues, observations,
  conditional alternatives, source types, uncertainty, exact inspected frame paths and coordinates.
- `lessons`: stable id, main episode, contrast episode(s) or an honest limitation, one objective,
  a small representative practice experiment or observation, and aligned Chinese/English text.
- `text.<lang>`: `title`, `look`, `good`, `change`, `next`, `exception`, `question`, `rationale`,
  plus 2–4 choices with stable ids, `acceptable` and a reason. More than one can be reasonable.
  `look` starts at the beginning of the source window, not at the decision freeze. Check what
  the opening frame shows; use a sequence such as "After the turnover, watch..." for a later cue.
  A valid decision-frame observation can still be misleading when spoken several seconds early.
  Shared text must also work with the web page's original clips: identify a person by position
  and shirt, without referring to a circle or arrow that only appears in the explained film.
- `dependencies`: the actual local evidence, statistics and principles used. Include source
  notes for personal content privately; the public exporter uses an explicit field allowlist.
- `introduction` / `closing`: the same message in each language. Keep them short.

Start with what the players did well, then a small number of fixes. Select contrasting examples
because they change the viewer's choice, not just to add another highlight. Do not pad a runtime.
Use a score change to locate a stretch, not to declare its cause. Explain the observed mechanisms.

## Say it so a player can use it

Bad: "Improve weak-side rotations and transition balance."

Better: "Your teammate is already in front of the driver. Look across: the player in the corner
has nobody near him. Move toward him while keeping the ball in view. Help inside if the driver
gets past your teammate."

Bad: "You have to attack more."

Better: "Before the ball reaches you, look at the defender. If you have room within your usual
range, be ready to shoot. If a teammate has the better opening, the direct pass is still useful."

Every explanation answers: what worked, what needs changing, what to do next. A positive example
does not need an invented mistake; `change` may explicitly say no specific error is established.
Avoid "always", "must" and fixed player counts unless the situation actually requires them.
Do not diagnose fear, effort, fatigue or technique from an outcome or one obstructed view.

The freeze is before the relevant action. A pre-catch freeze is not automatically pre-pass.
Do not narrate later information as if it were already visible. Use a short question on the
freeze, then play the action. Keep labels short and identify at most the relevant people.
Keep film paragraphs brief enough that the play does not end under a long speech.

## Practice and follow-up

Reproduce the cue and choice with a defender or variable cue where possible; isolated technique
can prepare the movement but does not test the read. Respect the owner's existing schedule and
dose. Self-chosen quotas need `kind: training_experiment` and `basis`; otherwise observe first.
Record real opportunities, appropriate decisions, execution and outcomes separately. Missing
counts stay unknown. Agree to retain, revise or retire a reminder after reviewing an example.

## Independent review and compilation

1. `hoop-tape-miner lessons check <folder> --draft` checks structure and referenced files.
2. A separate film reviewer re-opens every selected moment, including contrast examples, and
   writes `lesson-review.json`: `reviewer`, `reviewer_kind` (`independent_agent` or `human_coach`),
   and `verdicts` (`id`, `verdict: keep|revise|drop`, `reopened`, `evidence_check`,
   `alternative_check`, `plain_language_check`, `translation_check`). State what was checked.
3. Fix disagreements from original evidence. A timestamp, cue or translation change needs review.
4. The reviewer runs `hoop-tape-miner lessons sign <folder>`; then compile with
   `hoop-tape-miner lessons compile <folder>`. This writes both film scripts and a public lesson
   export from the same signed source. It hashes dependencies; downstream manual edits are stale.
5. Render only after source/content checks. Set `film_speech_tempo` in the unit or pass
   `film --speech-tempo 1.25`; speech/cues change together, actual play keeps its source speed.

## Four separate checks

- Evidence: can the original clip support the claim and alternative? What remains unknown?
- Teaching: can an unfamiliar amateur identify the cue, action and exception in ordinary words?
  An agent can audit wording; only actual viewer responses count as human comprehension evidence.
- Media: frame placement, annotation positions, subtitle fit, audio timing, pacing and playback.
- Learning: immediate recall, later recall and decisions in later real opportunities. Preference,
  clicks, completion, made shots and agent agreement are not substitutes. Never invent responses.

For comparisons use `coach-insights ab --review <review> --pairs pairs.json --out sheet.md`.
Each pair must address the same episode and objective. Keep the private key from raters, keep
full wording, split reference cases by game and retain difficult/unclear cases. Report how cases
were selected; a curated small sample does not measure whole-game accuracy or training transfer.
