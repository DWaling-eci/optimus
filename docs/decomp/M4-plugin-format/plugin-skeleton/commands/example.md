---
description: Minimal slash command example -- prints a friendly greeting demonstrating the command frontmatter shape
---

# /example -- minimal slash command reference

When the user invokes `/example` (with no argument) or `/example Bob` (with argument), respond:

- If `$ARGUMENTS` is present and non-empty: "Hello, $ARGUMENTS, from the Cursor plugin skeleton."
- Otherwise: "Hello, world, from the Cursor plugin skeleton."

Keep the response to one line.

---

This file is a REFERENCE for the Cursor plugin command format. It demonstrates:

- Kebab-case filename (`example.md`) becomes the slash-command name (`/example`).
- YAML frontmatter with the minimum required field: `description` (one-line summary). Cursor's `create-skill` and `create-hook` specs are explicit about their frontmatter schemas; this report's empirical observation of `superpowers/b7a8f76/commands/*.md` confirms `description` is sufficient. Additional fields like `argument-hint` and `allowed-tools` (used in Claude Code's command format) MAY be supported by Cursor but were not empirically verified in this research -- M4 should probe before relying on them.
- Body content is the prompt template that becomes the command's behavior. `$ARGUMENTS` is the placeholder for user-supplied arguments.

Source: empirical example based on `~/.cursor/plugins/cache/cursor-public/superpowers/b7a8f76/commands/*.md` simplified to minimum.
