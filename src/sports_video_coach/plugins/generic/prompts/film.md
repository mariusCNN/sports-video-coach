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
  `![caption](picture.png)` (a figure in the folder).
- Freeze lines after a clip: `> mm:ss <x,y> "label"` stops the clip and rings the spot (fractions of width and
  height); `>` alone resumes. Paragraphs after a line are read over it.
- Plugins may add scene kinds (basketball adds `court:` diagrams); `film --dry` names the kinds it knows.
- Keep it to 2-4 minutes. Same facts as the report.
