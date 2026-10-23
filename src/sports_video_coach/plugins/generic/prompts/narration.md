# Narration guide (listen.<lang>.md)

A spoken version of the report, rendered to MP3 by `sports-video-coach narrate <folder>` (edge-tts). Write for the ear.

- Lines starting with `#` are not read. Blank lines are short pauses. Everything else is read exactly as written.
- No tables, lists, links, images, symbols or abbreviations. Spell numbers the way they are said
  ("seven of ten", "one minute twelve").
- Open with who and what this is and its real length ("about three minutes"), then the bottom line, then the
  report's sections in order, shorter. End with a short sign-off.
- Same facts as the report; never add a claim. No names of people unless the user asked for them (the text goes
  to an online text-to-speech service).
- Before rendering, estimate the length so the "about N minutes" sentence is right the first time. Count
  characters, not words: English about 950 characters a minute with spaces (130-190 words, depending on word
  length), Chinese about 235 characters a minute without punctuation, Japanese about 285 (kana and kanji, without
  punctuation), Korean about 245 (Hangul without spaces), Spanish about 850, French and German about 950,
  Portuguese about 800 characters a minute with spaces. `narrate` prints this estimate
  before it renders, warns when the sentence is clearly off, and prints the real length after.
- Write each script wholly in its own language, numbers and the length sentence too (Japanese: 「約三分」, Korean: 「약 이 분」), with no
  other language's words left in: the voice reads them with the wrong accent.
