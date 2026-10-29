# Coaching knowledge base

The coaching advice in a report is not made up on the spot. The agent ties what it saw on the film to an entry in a
fixed knowledge base (KB): why the problem happens, what to check on the film, a cue, a drill and a target to check
next time. The KBs are plain Markdown files in this repo, written in our own words from public coaching material
(FIBA WABC coaches manuals, Jr. NBA practice material) and sports-science studies, with a source on every entry.
They are not endorsed by FIBA, the NBA or any author they cite.

They are open to contributions: a new entry, a better drill, a correction, a newer study, or a KB for another sport.

## What is in it (basketball)

| File | Entries | Covers | Used by |
|---|---|---|---|
| [`prompts/coach_kb.md`](../prompts/coach_kb.md) | 12, `KB-<slug>` | Team play of an adult rec-league team: transition defence, press break, spacing, cuts, help defence, closeouts, rebounding, fouls, shot selection, pick and roll, end of period | The game workflow's coaching insights and their critic (`prompts/coach_insights.md`, `coach_critic.md`) |
| [`prompts/skill_kb.md`](../prompts/skill_kb.md) | 19, `KB-<slug>` | One player's skills (shooting base and arc, release, catch-and-shoot, pull-up, free throws, layups, finishing, handling, first step, defence) and conditioning (energy demands, repeated sprints, landing, strength, warm-up, fatigue, weekly load) | Personal training sessions (`prompts/training_review_brief.md`, `training_report.md`) |
| [`prompts/movement_kb.md`](../prompts/movement_kb.md) | 16, `MV-<slug>` | How a player runs, finishes and stops: acceleration posture, braking, stride, arm action, transition, speed dribble, layup approach and take-off, stopping, landing, capacity; plus 2D-pose limits, reference values, a filming protocol, a re-test battery and a pain gate | Movement sessions (`prompts/movement_review_brief.md`, `movement_report.md`) |
| [`prompts/fuel_recovery_kb.md`](../prompts/fuel_recovery_kb.md) | 11, `FR-<slug>` | Energy by day, protein, carbs and timing, game day, hydration, supplements, sleep, recovery methods ranked, soreness vs pain, load progression, body composition; plus a plate method, example menus and a weekly recovery template | Movement and training plans; the "recovery and food" step of [START.md](../START.md) |

`tests/test_coach_kb.py` checks that every `coach_kb.md` entry has all its fields and a source with a page or a URL.

## How an entry is built

Every entry is one `### <PREFIX>-<slug>` section (lower-case slug, words joined by `-`), with labelled fields:

| Field | What goes in it |
|---|---|
| **Symptom (observable)** (fuel/recovery: **Situation**) | What the film, the numbers or the player's notes show, in terms the reviewer can see. No symptom in the data: the entry is not used. |
| **Why it happens** | The mechanism, in short bullets, each backed by a source. |
| **What to check on film** | What the reviewer looks for to confirm it, and from which camera view it can be judged at all. |
| **Cue** (skill, movement) or **In-game rule** (team) | One short line the player or team can say on court. |
| **Drill** | Name, sets x reps, the setup; sized for the audience the KB states (adult rec players, little time, simple gear). |
| **Target** (team: **Next-game target**; skill: **Next-session target**; movement: **Success measure**; fuel/recovery: **Check**) | Something measurable on the next video or in the log. |
| **Evidence level** (movement, fuel/recovery) | Strong / moderate / expert opinion / our rule, as the KB's header defines them. The team and skill KBs cite manual pages and studies per entry instead. |
| **Source** | Manual and page, or a link to the study (a DOI, PubMed / Europe PMC record or the publisher's page). |

Two markers keep our own choices apart from what the sources say:

- **"(our rule)"**: a cue, threshold, drill variant or dose we chose; the source supports the principle, not the
  detail. Reports present it as our choice, never as "the book says".
- **Trial values**: target numbers are our own starting values unless a source is cited; the plan re-sets them from
  what the player actually managed.

## How the agent uses it in a run

1. The film reviewer marks a moment with the entry whose symptom it shows (`"kb": "MV-braking-touchdown"`,
   `coach_note`, `form` notes), with a status such as seen / not seen / not visible.
2. The report writer cites the entry by slug, explains the "why" from it, and copies the cue, drill and target into
   the page and `plan.json` only when the session data shows the symptom.
3. Checks and critics reject a claim whose symptom is not in the data (the team critic wants it in at least two
   trips). Pain and injury questions never get a drill: they go to a physiotherapist or doctor.

**The one-prompt start ([START.md](../START.md)), basketball on the `generic` plugin:** the agent reads the team,
skill and movement KBs from the clone before it writes the report. It bases each fix and drill on the entry whose
symptom it saw in the film and names that entry; when no entry fits, it says the advice is its own. The entries
guide the advice only: this path does no tracking or measuring, so every claim still comes from what the agent saw.

## Sources and copyright

- Paraphrase in your own words. At most one short quoted sentence per entry.
- Cite every entry: manual title, edition and page, or a link. Do not add PDFs, scans, long excerpts or images from
  manuals, books or paywalled papers to the repo; the full texts stay with whoever owns them.
- Say how strong the evidence is. A lab study on trained sprinters is not proof for a 30-year-old rec player: write
  "likely" and give the evidence level.
- Never imply that a federation, league or author endorses this project.
- No real players: no names, team names, photos or frames of people in an entry or an issue.

## Propose an entry or a correction

- **Quickest:** open a [Coaching knowledge issue](https://github.com/mariusDing/sports-video-coach/issues/new?template=coaching_knowledge.yml)
  with the sport, the entry (new or which slug), the change, the source with a link and the evidence level. Coaches
  who do not write code are welcome; we turn a good issue into an entry.
- **As a pull request:** edit the KB file, keep the fields in the order above, put the source on the entry, and run
  `uv run pytest -q` (see [CONTRIBUTING.md](../CONTRIBUTING.md)). A new slug that a guide or plan should use also
  needs a mention where it is used (the review brief or the report guide that lists slugs).

## A knowledge base for another sport

Running, the gym, HYROX, soccer and every other sport run through the `generic` plugin today: the agent reviews the
film with general coaching guides (`review.md`, `report.md`), with no sport-specific tracking and no sport KB. Basketball
is the only sport with its own KBs so far. A sport gets its own KB through its plugin:

1. `sports-video-coach new-plugin <sport> --dir examples/plugins` makes a working copy of the generic plugin
   ([docs/plugins.md](plugins.md)).
2. Put the KB in the plugin's `prompts/` folder, e.g. `prompts/kb.md`, with entries built as above. Every Markdown
   file there is a guide: `sports-video-coach guide kb --unit <folder>` prints it.
3. In the plugin's `prompts/review.md` and `prompts/report.md`, tell the agent to read that guide, tie each moment
   to an entry and cite the slug, and use an entry only when its symptom is in the film.
4. Ship it as a pull request adding `examples/plugins/<sport>/` or in its own repo (see
   [docs/plugins.md](plugins.md#share-it)).

Not ready to write a plugin? Open a [Coaching knowledge issue](https://github.com/mariusDing/sports-video-coach/issues/new?template=coaching_knowledge.yml)
with a few entries for your sport: what you look for on film, the cue, the drill and the source. That is the
start of a plugin.
