---
expansion-status: skeleton
filled-by: null
filled-at: null
---

# M3 -- Hook Layer (Task Decomposition)

**Status:** clean stub. Milestone outcomes + DoD live in roadmap M3. Per-phase tasks transplant here at refactor time.

**Source:** transplanted from roadmap Phases 3.1 through 3.2.

## Phase 3.1 -- Hook Audit

- TODO: extract from Phase 3.1 section.

## Phase 3.2 -- Port + Test

- TODO: extract from Phase 3.2 section.

## Sourcing note

Hook source lives in `src/hooks/` (sibling of `src/optimus/`), NOT inside the container package. M4/M5 bundlers pull from `src/{hooks,agents,skills,rules}/`, not from `src/optimus/`.
