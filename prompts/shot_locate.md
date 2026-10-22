# Shot locate, batch {batch}

You locate where on the court each shot below was taken, so the shot chart can draw it at its real spot. The film review already decided who shot and the result; you only read the spot. The zone follows from your spot, so read it from the frames, not from what the shot type suggests.

## What a sheet shows

Each sheet `s<NN>.jpg` in `{locate_dir}` is one shot: six frames T1-T6 around the reviewed release time (T1 = 1.8 s before, T2 = 1.2 s, T3 = 0.8 s, T4 = 0.4 s before, T5 = the reviewed release, T6 = 0.3 s after; each tile is stamped with its video time). The header names the reviewed shooter and result and the basket the team attacks.

- **Magenta lines** are the court lines projected from the camera calibration. Check them first: they should lie on the painted lines (baseline, lane, 3-point arc). If they are off by more than about half a metre near the shooter, the grid is off too: say so in `note` and use the painted lines instead, or answer unclear.
- **Grid** (court metres, on the attacked half): yellow lines labelled `x<N>` run across the court at N metres along its length (x = 0 is the left baseline, 28 the right one, 14 half-court); cyan lines labelled `y<N>` run along the court at N metres from the near sideline (y = 0 near the camera, 15 far side). Labels sit at every 2 m; thin lines between them are the odd metres.
- A **thick yellow box** marks the reviewed shooter where the tracker read his jersey; it can be missing or wrong. The orange trail is the ball.

## How to read a spot

1. Find the shooter: the player who releases the ball (ball trail, shooting motion). The reviewed release time is often late by up to a second, so the release can be as early as T2.
2. Pick the tile with the **last ground contact before take-off** (for a layup, the last foot plant before the jump; for a set shot, the feet at release). An airborne foot does not sit on the court: never read a spot from a foot in the air.
3. Read the point on the floor midway between his feet in that tile against the grid: x from the yellow lines, y from the cyan lines, interpolating between lines to 0.1 m. Sanity check: the 3-point arc is 6.75 m from the basket centre, the basket centre is 1.575 m in from the baseline at y = 7.5, the lane is 4.9 m wide (y 5.05-9.95) and 5.8 m deep.
4. Near the 3-point line (within about a metre of the arc or the corner line): zoom on the feet and add `"arc"`: `"inside"`, `"on"` (a foot touches the line: two points) or `"outside"` (both feet behind the line: three). Leave it out when you cannot see the feet on the line.
5. Close-ups: `uv run hoop-tape-miner coach-sheets zoom SHEET TILE X Y W H OUT --grid {lay_grid} --header {header} --scale 2` (TILE 0-5 row-major = T1-T6, X Y W H in pixels inside the tile). Write close-ups to `{locate_dir}/zoom/`.

Confidence: `high` when the feet are clearly visible on the grid and the court lines align (error about 0.5 m); `medium` when you interpolate across a gap or a foot is partly hidden (about 1 m); `low` when you are guessing. Low and null spots are not drawn, so never stretch: write `"xy": null` and a reason in `note` (shooter not in frame, feet hidden, camera panning, no grid, cannot tell who shot).

## Shots ({n})

{shots}

## Answer

Write `{answers}`: a JSON list with one object per shot above, nothing else in the file.

```json
[{{"n": 7, "xy": [24.3, 3.1], "tile": 4, "confidence": "high", "arc": "inside", "note": "left foot on y3, half a metre inside the arc"}},
 {{"n": 8, "xy": null, "tile": null, "confidence": "low", "note": "shooter hidden behind #23 at take-off"}}]
```

`n` is the sheet number (S07 -> 7), `tile` the tile you read (1-6). Reply in at most 6 lines: how many shots you located (high / medium / null) and any sheet where the court lines did not align.
