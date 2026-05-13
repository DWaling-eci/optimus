---
name: example-skill
description: Reference skill demonstrating the minimal valid SKILL.md format. Use when the user asks "how do I write a Claude Code skill", wants a one-file working example, or needs to inspect the YAML frontmatter shape. NOT a production skill -- the body is documentation, not actionable end-user instructions.
version: 0.1.0
---

# example-skill -- reference skill body

This SKILL.md is a REFERENCE. Reading it does not perform an action; it explains the format.

## What this file demonstrates

1. **Location:** `skills/example-skill/SKILL.md` -- subdirectory per skill, `SKILL.md` filename is the auto-discovery anchor (NOT `README.md`, NOT `index.md`).
2. **Frontmatter fields:**
   - `name`: kebab-case identifier. Matches the skill's directory name by convention.
   - `description`: shapes Claude Code's autonomous-activation heuristic. Write it with the trigger phrases / scenarios in the user's likely vocabulary.
   - `version`: semver string. Optional but recommended.
3. **Body content:** Markdown loaded into the agent's context when the Skill tool invokes this skill by name. The skill is not parsed structurally beyond the frontmatter -- treat it as prose-with-headings.

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
- Not loaded into context unless explicitly invoked via the Skill tool. The autonomous-activation heuristic is unlikely to trigger this skill in real use -- the description deliberately self-flags as reference-only.
