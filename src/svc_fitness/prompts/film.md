# Explained video guide (film.<lang>.md)

`sports-video-coach film <folder> --video <video>` renders `film.<lang>.md` into `film.<lang>.mp4`: the narration
plays over the clips it talks about, with subtitles. Write it for watching; every point should be seen.

```
# Writer's note (lines starting with # are not read)
Opening paragraph, read over the title card.

## The toss drifts behind your head
A chapter card. One or two sentences.

![Second serve, toss behind the head](clip:01:12-01:20)
Watch the toss hand.

> 01:15 0.48,0.30 "toss here"
Stop. The ball is behind your head, so your back has to arch.

>
Now watch where the serve lands.

![Tosses in front of the head, out of ten](stat:7)
Seven of ten tosses in front of the head: that is the target for next week.
```

- Scene lines: `## Title` (chapter card), `![caption](clip:mm:ss-mm:ss)`, `![caption](stat:<number>)`,
  `![caption](stats:<number> <label> | <number> <label>)` (a board of key numbers, rows of three),
  `![caption](picture.png)` (a figure in the folder).
- Freeze lines after a clip: `> 0:12.5 0.45,0.80 "label"` stops the clip at 0:12.5 and rings that spot (x,y as
  fractions of the frame from the top left, no brackets; read them off the contact-sheet tile, whose frame ends at
  the thin dark gap around it, not off the whole sheet; to mark a person,
  point at their feet). `0.2,0.8->0.6,0.8` draws an arrow; several marks may follow the time, but only one
  `"label"` per line, always last: `> 0:12.5 0.45,0.80 0.60,0.78 "both feet"` rings two spots. `>` alone resumes.
  The frame outside the rings is dimmed, so ring the ball too (a second spot) when the label is about it.
  Paragraphs after a line are read over it.
- Plugins may add scene kinds (basketball adds `court:` diagrams); `film --dry` names the kinds it knows.
- Keep it to 2-4 minutes; for a source video under a minute, two to four times its length (a 22 s drill:
  45-90 s). Same facts as the report; a short report makes a shorter film, never pad it. `film --dry`
  estimates the length.
- One `film.<lang>.md` per language of `languages`, each wholly in its own language (captions, freeze labels and
  chapter titles too), with no other language's words left in. The subtitles, the voice and the font follow the
  file's language (`film` prints which voice and font it used).
- Last, the humanize pass (`sports-video-coach guide humanize`): it must sound like a coach talking, not a chatbot. The run flags stock AI phrasing (not-X-but-Y, "moreover"/"此外", hype words, self-asked questions, slide labels read aloud, dashes) and waits until it is fixed; keep every fact while you rewrite.
