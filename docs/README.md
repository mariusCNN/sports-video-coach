# sports-video-coach docs

sports-video-coach is agent-first sports video analysis: your coding agent turns your own game or training video into a coach's film review, a coaching page with narration and clips, and an explained video. Sports come as plugins; `generic` works for any sport, `basketball` adds tracking and a team workflow.

Start with the [project README](../README.md) ([中文](../README.zh.md)) and, for agents, [AGENTS.md](../AGENTS.md).

| Doc | For | What's in it |
|---|---|---|
| [features.md](features.md) | users and agents | Complete feature catalog, advantages, commands and limitations |
| [perception.md](perception.md) | basketball users and researchers | OpenHoopVision candidate evidence, reviews and validation media |
| [perception-lab.md](perception-lab.md) | vision researchers and agents | WASB, SAHI and KaliCalib, independent evaluation and measured limitations |
| [architecture.md](architecture.md) | contributors | The core, the step driver, plugins, artifacts, the CLI |
| [plugins.md](plugins.md) | plugin authors | Writing a plugin for a new sport: template, contract, steps, hooks, tests |
| [basketball.md](basketball.md) ([中文](basketball.zh.md)) | basketball users | What the basketball plugin gives, quick start, commands, FAQ |
| [playbook.md](playbook.md) | basketball users and AI agents | The one-command run and every step from a league link (or a video) to the pages and the explained video |
| [pipeline.md](pipeline.md) | contributors | Every basketball stage, its inputs and outputs, and the design choices behind them |
| [review_protocol.md](review_protocol.md) | contributors | The optional possession event review that feeds the shot charts |
| [privacy.md](privacy.md) | everyone | What stays in `workspace/`, sharing reports, minors and consent |
| [research.md](research.md) | contributors | Open-source projects and papers this builds on, and what was adapted |
| [optimization-backlog.md](optimization-backlog.md) | contributors | Measured speed and cost improvements, done and to do |

Basketball writing guides and the coaching knowledge base the insights cite ([`coach_kb.md`](../prompts/coach_kb.md)) are in [`prompts/`](../prompts/). To contribute, see [CONTRIBUTING.md](../CONTRIBUTING.md).
