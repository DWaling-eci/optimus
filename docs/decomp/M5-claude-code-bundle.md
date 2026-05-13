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
