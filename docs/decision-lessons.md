# Evidence-bound decision lessons

The useful unit is a choice a player can recognize again: visible cue, feasible action and
exception. A report, page and video should teach the same choice from the same evidence.
The authoring guide is [lessons.md](../prompts/lessons.md); start from
[lessons.example.json](../templates/lessons.example.json).

## Workflow

New basketball games set `coaching_lessons: true`; archived games opt in with the same key.
The driver pauses after the independent insight critic and before reports. Write one
`lessons.json` in each report folder. Existing CV output is reused.

```sh
hoop-tape-miner lessons check GAME --draft
# An independent reviewer reopens original frames and writes lesson-review.json.
hoop-tape-miner lessons sign GAME
hoop-tape-miner lessons compile GAME
hoop-tape-miner clips GAME
hoop-tape-miner html GAME
hoop-tape-miner film GAME --speech-tempo 1.25
```

Repeat for a personal report folder. Compilation emits both languages' film scripts and
`lesson.public.json`. The page asks for a choice using a clip that ends before the action;
only after a response does it reveal the complete clip and rationale. Responses stay in
localStorage under the lesson id and source digest and can be exported. They are self-responses,
not automatically graded comprehension. Raw notes and local paths are excluded from the export.

## Evidence and invalidation

An episode records pre-action time, action time, outcome time, observed cues, conditional
alternatives and uncertainty in identity, timing, choice and outcome. Source types separate
film observations, official statistics, player reports, model proposals, principles and
training experiments. The sign operation checks the review record; it does not observe the film.

The digest includes all languages, all episode content, declared source documents and inspected
frames. Changing any of them invalidates review and compilation. Film and HTML builds reject
stale derivatives. Reports follow facts and lessons; facts follow evidence and insight review.
An insight critic now also signs its evidence, statistics and KB, including reopened sheets.

Distinct trip ids are the automated minimum for recurrence. Human/agent review must additionally
group physical possessions split across ids (for example a missed shot and a putback). A single
episode can be useful when labelled as such; it cannot establish frequency or a recurring habit.

## Four different validation questions

| Layer | Evidence required | Does not establish |
|---|---|---|
| Evidence | Reopened source, temporal ordering, identities, feasible alternatives, resolved or retained disagreements | Whole-game event accuracy |
| Teaching | One cue/action/exception; independent plain-language and translation review | Human comprehension |
| Media | Rendered placement, subtitle fit/timing, audio tempo, actual playback | Learning |
| Learning | Real viewer explanation, later recall, later observed opportunities | Causation from preference or a small uncontrolled sample |

For a viewer check, ask the person to name the cue, action and an exception after one viewing.
Record their actual response before independent scoring. Later recall uses the same version.
Game transfer counts real opportunities separately from appropriate choices, execution and
outcomes. Missing opportunities are unknown, not zero. No fabricated viewer data is acceptable.

`lessons evaluate FOLDER --records records.json` writes separate layer summaries and rejects
impossible denominators. Records need lesson id/version, rater id/kind, phase, actual viewer
response and viewer id, plus independent cue/action/exception judgements for comprehension/retention.
The rater must differ from the viewer. `rater_kind: agent` never becomes a
human result. A game-transfer record supplies opportunities, appropriate_decisions and executed;
uncounted values may be null. This is a measurement record, not an efficacy certification.

## Compare the same decisions

```sh
hoop-tape-miner coach-insights ab --review REVIEW --pairs pairs.json --out sheet.md --seed 7
```

Each pair contains `episode_id`, `game_id`, `split`, `before`, `after`, addressing the same
objective. Order is randomized within each pair; complete text is kept. Keep the key private.
The older unmatched sheet remains exploratory and explicitly cannot support an effectiveness claim.

Build a reference set across multiple games, split by game, and keep unclear cases and multiple
reasonable choices. Independent annotations and adjudication should record actual reopened
frames. Agent consensus is provisional, not human gold. Withhold outcomes and later frames from
pre-action prompts. A later event can clarify an observation but cannot be a cue the player saw
earlier. Inspect disputed intervals densely before trying a larger perception model.

```sh
hoop-tape-miner lesson-bench prepare --cases reference-cases.json --out benchmark
hoop-tape-miner lesson-bench score --cases reference-cases.json --ratings ratings.json --out benchmark
```

Cases carry episode/game ids, split, recurrence group, decision time, timestamped pre-action
cues/frames and annotation provenance. Preparation checks time and game separation and exports
only pre-action inputs, alongside a private reference key. Ratings identify variant, author and
independent reviewer, with pass/fail/unclear for fact support, conditional action and plain language.
Unrated cases remain unrated; agent reviews are reported separately from human reviews.

Change a detector/model only after a measured baseline on held-out frames, including false
positives, misses and cost. The existing [perception lab](perception-lab.md) remains the place
for those comparisons. No new vision framework is required by the lesson workflow.

## App follow-up

`game.learning_goals` in program.json accepts up to three entries with id, version, title,
when, action, exception, practice, measure, source_url and retained/revised/retired status.
The UI stores per-game observations in `lesson_trials` inside the existing draft/game log,
preserving previous versions and sync behavior. Practice remains within the existing schedule;
do not silently add intensity or quota targets. See [program.example.json](../templates/program.example.json)
for the base plan and the validator's field messages when adding goals.

## Research basis and limits

The design uses video plus questioning and separates decision quality from execution, as in
[Gil-Arias et al.](https://peerj.com/articles/7392/). That small youth study is not proof of
effectiveness for an adult amateur team. Representative practice preserves information and
action together ([Pinder et al.](https://pubmed.ncbi.nlm.nih.gov/21451175/)). Short, focused
explanations also follow the limited-capacity reasoning in
[Mayer and Moreno](https://carpentries.github.io/instructor-training/files/papers/mayer-reduce-cognitive-load-2003.pdf).
These inform the workflow; they do not establish a universal freeze length or a guaranteed gain.
