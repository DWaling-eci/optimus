---
expansion-status: skeleton
filled-by: null
filled-at: null
---

# M5 -- Claude Code Bundle + Installer (Task Decomposition)

**Status:** clean stub. Milestone outcomes + DoD live in roadmap M5. Per-phase tasks transplant here at refactor time.

**Source:** transplanted from roadmap Phases 5.1 through 5.2.

## Phase 5.1 -- Claude Code Bundle Builder

- TODO: extract from Phase 5.1 section.
- **Bundler pulls from `src/{hooks,agents,skills,rules}/`** -- NOT from `src/optimus/`. (Same hook-source-outside-container rule as M4.)

## Phase 5.2 -- Claude Code Installer

- TODO: extract from Phase 5.2 section.
- **Cross-IDE end-to-end test** -- both IDEs open simultaneously, each independently reaches the same singleton container. May require manual verification rather than fully automated CI (running two IDE instances in CI is non-trivial).

## Sizing estimate

- **Original:** 1-2 sessions.
- **Revised:** 2-4 sessions. Claude Code plugin format is described in CHARTER Decision 8 as a moving target; bundler authoring may require non-trivial reverse-engineering effort.

## Claude Code plugin format

- Plugin format research is covered by the **chat-report sibling delegated session** (see `docs/decisions/chat-report-sibling-charter.md`, "First-priority discovery tasks -- 3b Claude Code plugin format research"). The same delegated owner that reverse-engineers the chat-history store also produces the plugin format spec source + version + install location + event-surface mapping. M5 consumes the findings; M5 does not duplicate the research.
- Co-location rationale: both efforts probe Claude Code internals and benefit from a single delegated owner. They share the unified escalation gate (per `AGENTS.md` "Delegated Session Escalation Policy"): if the format is undocumented AND reverse-engineering proves infeasible, escalate to Dustin for re-scope.
