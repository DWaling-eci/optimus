---
name: example-skill
description: Reference skill demonstrating the minimal valid Cursor SKILL.md format with explicit auto-invocation. Use when the user asks "how do I write a Cursor skill", wants a one-file working example, or needs to inspect the YAML frontmatter shape. NOT a production skill -- the body is documentation, not actionable end-user instructions.
disable-model-invocation: false
---

# example-skill -- reference skill body

This SKILL.md is a REFERENCE. Reading it does not perform an action; it explains the format.

## What this file demonstrates

1. **Location:** `skills/example-skill/SKILL.md` -- subdirectory per skill, `SKILL.md` filename is the auto-discovery anchor (NOT `README.md`, NOT `index.md`).
2. **Frontmatter fields (Cursor spec):**
   - `name`: required. Lowercase letters/numbers/hyphens only. Max 64 chars.
   - `description`: required. Max 1024 chars. Shapes Cursor's autonomous-activation heuristic. Write it with the trigger phrases / scenarios in the user's likely vocabulary.
   - `disable-model-invocation`: optional. **Default `true` in Cursor** (skill only loads when named explicitly). This skeleton sets it to `false` to demonstrate the optimus-default pattern (auto-invocation, matching Claude Code parity).
3. **Body content:** Markdown loaded into the agent's context when invoked. The skill is not parsed structurally beyond the frontmatter -- treat it as prose-with-headings.

## Cursor/Claude-Code skill divergence (load-bearing)

| Field | Cursor default | Claude Code default |
|-------|---------------|---------------------|
| `disable-model-invocation` | `true` (must opt-in to auto-invocation) | not present; auto-invokes from description by default |

The optimus Cursor bundler MUST inject `disable-model-invocation: false` if absent in the IDE-agnostic `src/skills/<name>/SKILL.md` source -- otherwise an optimus skill that auto-invokes in Claude Code will silently NOT auto-invoke in Cursor.

## Supporting files

Subdirectories under `skills/example-skill/` are preserved by the plugin loader. Production skills typically organize like:

```
skills/example-skill/
  SKILL.md              -- this file
  scripts/              -- executable helpers the skill references
  references/           -- supplementary docs / specs
  examples/             -- worked examples
```

The skeleton ships only SKILL.md (the minimum). Add subdirectories per the skill's actual needs.

## What this skill is NOT

- Not a production skill. The body is documentation, not action-guiding instructions.
- Not loaded into context unless explicitly invoked OR the autonomous-activation heuristic fires (which IS enabled here via `disable-model-invocation: false`). The description deliberately self-flags as reference-only to discourage spurious triggering.

Source: `~/.cursor/skills-cursor/create-skill/SKILL.md` (Cursor-authored canonical spec).
