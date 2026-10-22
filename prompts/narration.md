# Writing narration scripts (listen.<lang>.md)

A spoken version of a report, rendered to MP3 by `hoop-tape-miner narrate` (edge-tts) and embedded in the HTML page as a "listen" button. Many players will only listen, on the way to practice. Write for the ear, not the eye.

## Files

- Team report: `listen.zh.md` and `listen.en.md` next to `README.md` / `README.en.md` in the game folder.
- Player deep dive: `player-<N>/listen.zh.md` and `listen.en.md`.
- The suffix picks the voice: `zh` and `en` are supported; defaults can be changed in `game.json` `narration.voices`. The HTML listen button appears only when both MP3s exist.

## Format the renderer understands

- Lines starting with `#` are **not read** (any level: `#`, `##`). Use the first line as a writer's note and `##` lines as section markers for yourself.
- Blank lines separate paragraphs; each paragraph boundary becomes a short pause. One idea per paragraph, 2-6 sentences.
- Everything else is read aloud exactly as written. No tables, lists, links, images, bold, emoji or code.

## Writing rules

1. **Numbers spelled out** the way they are said: "forty-one to thirty-six", "a sixteen to two run", "twelve oh five" for a video time, "number eleven" for a jersey, "plus six", "forty percent". In Chinese: Chinese numerals and spoken forms ("四十一比三十六", "十一号", "十二分零五秒").
2. **No symbols**: no `#`, `–`, `/`, `%`, `+/-`, `≥`, parentheses or abbreviations the voice may mangle (write "free throws", not "FT"; "pick and roll", not "PnR").
3. Open with: whose review this is, opponent, date, result, and the real length ("It runs about nine minutes").
4. Bottom line first (the one-sentence summary of the report), then follow the report's sections in order, shorter. Keep only the times worth rewatching; two or three per section at most.
5. Short sentences, active voice, second person for a player script. Repeat the key rule once at the end of its section; repetition helps listeners.
6. Same facts and numbers as the written report; never add a claim that is not in it.
7. Jersey numbers only, no names (the text is sent to an online TTS service; see `docs/privacy.md`).
8. End with a short sign-off ("See you at practice.").
9. Target length: team report about 8-10 minutes (count characters, not words: English about 950 characters per minute with spaces, 130-190 words depending on word length; Chinese about 235 characters per minute without punctuation; `narrate` prints its estimate before rendering); player deep dive about 3 minutes.

## After rendering

1. `uv run hoop-tape-miner narrate <folder>` writes `listen.zh.mp3` and `listen.en.mp3` next to the scripts (`--lang en` for one language, `--rate "-5%"` to slow down).
2. Measure the real length: `ffprobe -v error -show_entries format=duration -of csv=p=0 listen.<lang>.mp3`.
3. If the "runs about N minutes" sentence is off by a minute or more, fix it and re-render. The HTML page shows the measured length on the play button, so the two must agree.
4. Listen to the first and last 30 seconds: check how jersey numbers, scores and team names are pronounced; respell phonetically in the script if needed.
