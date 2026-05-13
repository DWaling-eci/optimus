---
expansion-status: skeleton
filled-by: null
filled-at: null
---

# M6 -- Dogfood Readiness (Task Decomposition)

**Status:** clean stub. Milestone outcomes + DoD live in roadmap M6. Per-phase tasks transplant here at refactor time.

**Source:** transplanted from roadmap Phases 6.1 through 6.3.

## Phase 6.1 -- Telemetry Refinement (Heuristics + Aggregates)

- TODO: extract from Phase 6.1 section.
- Heuristic + aggregate refinements only (Cursor + Claude Code chat-report variants land pre-kickoff per `docs/decisions/chat-report-sibling-charter.md`).

## Phase 6.2 -- Reviewer Grounding + Reviewability

- TODO: extract from Phase 6.2 section.
- `.github/copilot-instructions.md` is OUT of scope (Copilot is not a v2 target).

## Phase 6.3 -- CI Image Publish

- TODO: extract from Phase 6.3 section.
- Default branch: `trunk` (named at M0 per `M0-tasks.md`).

## Dogfood pass/fail gate

Per `docs/decisions/success-metric.md`:
- Quantified threshold for `optimus_*` calls vs broad sweeps.
- Baseline condition (Optimus tools disabled).
- Two-signal separation (component A: `optimus_*` count, component B: informed precision reads).
- Both components must meet threshold for full pass; one meeting + one missing = partial pass + investigation.
