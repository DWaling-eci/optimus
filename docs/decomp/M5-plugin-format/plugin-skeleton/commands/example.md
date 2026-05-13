---
description: Minimal slash command example -- prints a friendly greeting demonstrating the command frontmatter shape
argument-hint: Optional name to greet
allowed-tools: []
---

# /example -- minimal slash command reference

When the user invokes `/example` (with no argument) or `/example Bob` (with argument), respond:

- If `$ARGUMENTS` is present and non-empty: "Hello, $ARGUMENTS, from the chat-report plugin skeleton."
- Otherwise: "Hello, world, from the chat-report plugin skeleton."

Keep the response to one line. Do not invoke any tools -- this skeleton command demonstrates the prose-only command pattern.

---

This file is a REFERENCE for the Claude Code plugin format. It demonstrates:

- Kebab-case filename (`example.md`) becomes the slash-command name (`/example`).
- YAML frontmatter with three fields: `description` (required; one-line summary), `argument-hint` (UI hint shown next to the command), `allowed-tools` (empty array means the command body cannot invoke tools -- text-only).
- Body content is the prompt template that becomes the command's behavior. `$ARGUMENTS` is the placeholder for user-supplied arguments.

Source: empirical example based on `~/.claude/plugins/cache/claude-plugins-official/plugin-dev/unknown/commands/create-plugin.md` simplified to minimum.
