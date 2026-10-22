# sports-video-coach (Claude Code)

@AGENTS.md

## Claude Code specifics

- Your own machine-specific rules go in `CLAUDE.local.md` (gitignored, auto-loaded).
- Film review: one subagent per part, at most 3 subagents at once; they write files and reply in a few lines.
- Browser checks and screenshots go to the `browser-check` subagent in `.claude/agents/` (text result only).
- Do not switch model or toggle MCP servers/plugins mid-session (invalidates the prompt cache).

# Compact instructions

Keep: decisions made, file paths, video alignment offsets, official game result, open TODOs. Drop: tool output, logs, screenshots.
