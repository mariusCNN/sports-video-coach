# Possession event review protocol (`review` sheets)

This is the optional event review that feeds shot charts in `report`. The main coach film review (trips, actions, fouls, transition defence) uses `coach-sheets` and the checklist in `prompts/film_review_brief.md`.

`hoop-tape-miner review` writes one or more sheets per possession: `review/pNNN_k.jpg` (possession `NNN`, sheet `k`), plus `manifest.json`.

## Reading a sheet

- 3x2 grid of frames, 1 s apart, timestamp burnt in.
- Boxes are coloured by team: one colour for us, one for them, grey for referees (default purple = us, green = them; the sheet header and `game.json` say which is which).
- White `#N` = recognised jersey number (may be missing or wrong; say so in `notes`).

## Labelling

For each possession, emit zero or more events as JSON. One possession can produce several events (e.g. miss, offensive rebound, made putback = 3 events). Set `t` to the time in seconds of the event itself, not of the sheet. Use `null` for fields that do not apply, and lower `confidence` rather than guessing.

## Event schema

```json
{
  "pid": 12,
  "t": 431.5,
  "offence": "us",
  "event": "shot",
  "result": "made",
  "points": 2,
  "shot_type": "layup",
  "shooter": "7",
  "zone": "paint",
  "side": "left",
  "play_type": "drive",
  "rebound": null,
  "defence_seen": "man",
  "confidence": "high",
  "notes": "short text"
}
```

| Field | Values |
|---|---|
| `pid` | int, possession id |
| `t` | float, seconds of the event |
| `offence` | `"us"` \| `"them"` |
| `event` | `"shot"` \| `"free_throws"` \| `"turnover"` \| `"foul"` \| `"end_of_period"` \| `"other"` |
| `result` | `"made"` \| `"missed"` \| `null` |
| `points` | `0` \| `1` \| `2` \| `3` \| `null` (unresolved) |
| `shot_type` | `"layup"` \| `"jumper"` \| `"three"` \| `"putback"` \| `"floater"` \| `"post"` \| `null` |
| `shooter` | jersey number as string, e.g. `"7"`, or `null` |
| `zone` | `"paint"` \| `"midrange"` \| `"three"` \| `null` |
| `side` | `"left"` \| `"center"` \| `"right"` \| `null`, from the attacker's view facing the basket |
| `play_type` | `"transition"` \| `"pick_and_roll"` \| `"drive"` \| `"post_up"` \| `"catch_and_shoot"` \| `"isolation"` \| `"second_chance"` \| `"cut"` \| `"other"` |
| `rebound` | `"offensive"` \| `"defensive"` \| `null` |
| `defence_seen` | `"man"` \| `"zone"` \| `"press"` \| `"unclear"` |
| `confidence` | `"high"` \| `"medium"` \| `"low"` |
| `notes` | short free text |

The reviewed file is a JSON list of such objects, passed to `report --events`.

An observed shot with an unseen outcome has `result: null` and `points: null`; it is not a miss. A made field goal has 2 or 3 points and a missed field goal has 0. Do not infer a made basket just because the other team advances the ball. Unresolved free-throw totals also use `points: null`. Low-confidence outcomes are excluded from reported makes and observed points. The points chart is a partial count of reviewed evidence, never the official score.

These "possessions" are CV half-court segments and can contain several real possessions or dead balls. Check the actual jersey colours before assigning the offence. Adjacent sheets include two seconds of padding; label a boundary event only once. OCR jersey overlays are suggestions, not verified identities.

Optional `report --coverage coverage.json` accepts a list of `{"pid": 12, "reviewed_sheets": ["...jpg"], "issues": ["outcome obscured"]}` records. Include reviewed segments with no visible events, so coverage does not depend on how many labels were emitted. When the review is split across agents, each writes `events_partN.json` and `coverage_partN.json`; the merge step refuses incomplete or duplicate sheet coverage.
