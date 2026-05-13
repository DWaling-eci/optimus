# M4 -- Cursor Bundle Manifest

**Status:** clean stub. The principle ("per-IDE bundle ships hooks/rules/agents/skills, plus `.mcp.json` pointing at singleton") lives in CHARTER Founding Decision 6. Exact bundle contents transplant here at refactor time.

---
### **Prerequisites** - *HARD REQUIREMENT*:**
- **R&D must be completed** ***before*** scoping and planning for this IDE bundler. 
	- Verify naming conventions and location requirements are followed for all artifacts installed on the host machine.
	- **If** the IDE automatically generates some files and/or config entries, ensure the the bundler uses correct param and value formats.
---

**Source:** transplanted from CHARTER "What ships per IDE" subsection (Cursor portion).

## Bundle contents

Per-IDE plugin bundle, installed via Cursor's native AI plugin mechanism. Bundle contents are *built* from the optimus repo's canonical IDE-agnostic source (`src/{hooks,rules,agents,skills}/`) by the Cursor bundler in `bundlers/cursor/`. The bundle includes only what Cursor supports.

- Cursor-specific transformations of hooks/rules/agents/skills (e.g., `.mdc` rule format and any Cursor-specific manifest fields applied at bundle time)
- Agent definitions and skills sourced from `src/agents/` and `src/skills/`
- Hook scripts sourced from `src/hooks/` (Node.js ESM, IDE-agnostic source -- bundler maps Cursor-specific event names per TR-17)
- Bundle manifest declaring `minimum_ide_version`, `bundle_format_version`, `optimus_version` (per CHARTER Founding Decision 8)
- `.mcp.json` per `docs/decisions/transport-and-discovery.md` schema

## Per-IDE adaptations

Hook source is IDE-agnostic; per-IDE event-name mapping and format transformation happen exclusively in this bundler. If Cursor exposes a pre-tool-call event that Claude Code does not, the Cursor bundle wires it; the Claude Code bundle handles it differently or omits.
