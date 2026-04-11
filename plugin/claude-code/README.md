# AI Memory Brain — Claude Code Plugin

This plugin teaches Claude Code to save memories proactively via the AI Memory Brain MCP server.

## What It Does

- **SKILL.md** — Behavioral instructions loaded by Claude Code that describe when and how to save memories (triggers, format, importance calibration, anti-patterns).
- **Hooks** — Shell scripts that fire at session start, session stop, and after context compaction to remind the agent to call the appropriate MCP tools.
- **settings.json** — Reference template for hook configuration. Adapt the event names and paths to match your Claude Code version (e.g. `PreToolUse`, `PostToolUse`, `Stop`).

## Setup

### 1. Connect the MCP server

Add AI Memory Brain to your `.mcp.json` (see the root project README for details). Ensure `MEMORY_API_KEY` is exported before starting Claude Code.

### 2. Install the plugin

Copy (or symlink) the plugin directory into your project:

```bash
cp -r plugin/claude-code /path/to/your-project/.claude/plugins/memory-brain
```

Or merge the hook configuration from `settings.json` into your existing `.claude/settings.json`. Note that `settings.json` is a reference template — hook event names and structure may vary between Claude Code versions, so adapt it to your setup.

### 3. Add the SKILL.md

Place `SKILL.md` where Claude Code can read it. You can either:

- Copy it into your project's `.claude/` directory.
- Reference it from CLAUDE.md with a note like: "Follow the memory protocol in plugin/claude-code/SKILL.md".

### 4. Verify

Start a Claude Code session and confirm:

1. The session-start hook prints a reminder to call `get_project_context`.
2. The MCP server is connected (check the MCP panel).
3. Claude Code begins saving memories proactively as you work.

## Three Layers of the Protocol

| Layer               | Mechanism            | Scope              |
|---------------------|----------------------|--------------------|
| serverInstructions  | MCP protocol field   | All MCP clients    |
| MCP resource        | `memory://protocol`  | Programmatic access|
| Claude Code plugin  | SKILL.md + hooks     | Claude Code only   |

The serverInstructions provide the baseline behavior for any MCP client. The SKILL.md extends this with concrete examples and anti-patterns specific to Claude Code. The hooks automate session lifecycle reminders.
