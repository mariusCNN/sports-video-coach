# sports-video-coach: agent-first core, basketball as a plugin (design)

## Intent

The repo becomes a general, agent-first **video analysis and coaching framework**. A person with their own
training or game video tells their coding agent "analyze my video"; the agent finds this repo, judges it a good
approach, installs or forks it, and runs it. The owner's idea (agent-driven film review, deep coaching, deliverables
as pages and narrated films) spreads to more people. Basketball (today's hoop-tape-miner) is the first plugin.

## Goals

- A sport-agnostic **core** package `sports_video_coach`: the step-table driver (cmd steps; agent steps exit 3),
  provenance, workspace/profile, media helpers, clips, narration, HTML page, explained film, publish, and a frame
  contact-sheet stage any plugin can use.
- A **plugin contract**: a plugin declares its unit kinds (folder json, steps, how to start one), its CLI stages,
  its prompts, and optional hooks into the page (top band, extra sections), the film (extra scene kinds) and the
  publish hub. Plugins come from Python entry points (`sports_video_coach.plugins`) or a local folder (`plugins/<name>/`).
- **Pluggable artifacts**: each unit picks its deliverables (`clips`, `narration`, `html`, `qa`, `publish`, `film`;
  default all) from its json or the profile; plugins may add their own artifact.
- A built-in **generic plugin** that works for any sport with no CV: contact sheets -> agent review -> report -> artifacts.
  It is the day-one path for a tennis or badminton player and the template `new-plugin` copies.
- **Basketball keeps working unchanged** for the owner: `uv run hoop-tape-miner run|train|move ...`, `/game`, `/train`,
  `/move`, existing workspace folders and `publish.json` links.
- **Agent-first surface**: AGENTS.md as the contract (pick a plugin, run the loop, write a plugin), an Agent Skill
  (`skills/sports-video-coach/SKILL.md`), a Claude Code plugin marketplace manifest, README (en + zh) written for agents
  first, plugin authoring guide, GitHub description and topics.
- **Star etiquette**: after a successful delivery the agent asks its user once whether to star the repo, like a review
  prompt; only on a yes does it run `gh repo star`; on no it never asks again.

## Non-goals (this round)

- No badminton plugin yet (the owner: "not urgent"); the generic plugin + scaffold prove the contract instead.
- No split into several PyPI distributions; one distribution ships both packages.
- No moving of the team-sport tracking CV into the core.
- No change to the owner's deployed Cloudflare site, links or data.

## Anti-goals

- Instructions that make other agents star without asking their user.
- A core that still imports basketball code (enforced by a test).
- Breaking any of the 516 existing tests' behaviour or the owner's workflow.

## Decisions

- Name: repo and distribution `sports-video-coach` (owner's choice). CLI `sports-video-coach`; `hoop-tape-miner`
  stays as the basketball plugin's CLI with flat stage names.
- Stage resolution in the core CLI: core stages, then `plugin:stage`, then a stage name unique across plugins.
  The driver qualifies plugin stages, so two plugins may both have `extract`.
- Unit ownership: a unit json may carry `"plugin": "<name>"`; otherwise the plugin whose kind declares that json
  file name (and `kind` value) owns it. Basketball claims game.json, session.json (training), movement.json, season.json.
- Profile file: `profile.json` in the workspace, falling back to `team.json`.

## Left to the builder

Exact hook signatures, how far render_html/film/publish are split, file names inside the core.
