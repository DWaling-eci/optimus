# M5 -- Claude Code Bundle Manifest

**Status:** clean stub. Same pattern as M4. Exact bundle contents transplant here at refactor time.

---
### **Prerequisites** - *HARD REQUIREMENT*:**
- **R&D must be completed** ***before*** scoping and planning for this IDE bundler. 
	- Verify naming conventions and location requirements are followed for all artifacts installed on the host machine.
	- **If** the IDE automatically generates some files and/or config entries, ensure the the bundler uses correct param and value formats.
---

**Source:** transplanted from CHARTER "What ships per IDE" subsection (Claude Code portion).

## Bundle contents

- TODO: extract from CHARTER subsection.
- Claude-Code-specific transformations of hooks/rules/agents/skills
- `.mcp.json` per `docs/decisions/transport-and-discovery.md` schema

## Format-spec source

- Owned by the **chat-report sibling delegated session** (see `docs/decisions/chat-report-sibling-charter.md`, "First-priority discovery tasks -- 3b Claude Code plugin format research"). That session produces the spec source (URL or attribution), the Claude Code version it pins against, the per-OS install location, and the event/hook/tool surface mapping.
- M5 records the findings in this manifest at milestone-load time; M5 does not re-do the research.
- Per CHARTER Founding Decision 8: the bundle MUST declare an explicit `minimum_ide_version` against whichever version the delegated session pins.

### Research findings (delivered 2026-05-12)

The delegated session produced:

- **`docs/decomp/M5-plugin-format/M5-plugin-format-research.md`** -- the format-spec research report answering Q4-Q7 (spec source, version pin, per-OS install location, event/hook/tool surface mapping). Headline findings: (a) canonical spec source is the in-product `plugin-dev:plugin-structure` skill, Anthropic-authored; (b) Claude Code has NO format-version-pin mechanism in plugin manifests -- M5 enforces minimum-IDE-version externally; (c) install root is `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` (Windows: `%USERPROFILE%\.claude\plugins\...`), env-overridable via `CLAUDE_CONFIG_DIR`; (d) every Claude Code surface (commands, agents, skills, hooks, MCP) maps cleanly to optimus's `src/{hooks,agents,skills,rules}/` IDE-agnostic source, with two source-surface augmentations needed (add `src/commands/`; pick a rules-injection channel).
- **`docs/decomp/M5-plugin-format/plugin-skeleton/`** -- a minimal-but-conformant Claude Code reference plugin demonstrating each component type. Reference shape for M5's bundler to build against. Includes step-by-step install instructions in the skeleton's `README.md` for ad-hoc local verification.

M5 task body fill-in should extract bundle contents (above) from these findings and pin the `minimum_ide_version` per CHARTER FD8.
