---
expansion-status: skeleton
filled-by: null
filled-at: null
---

# M2 -- Standards Layer (Task Decomposition)

**Status:** clean stub. Milestone outcomes + DoD live in roadmap M2. Per-phase tasks transplant here at refactor time.

**Source:** transplanted from roadmap Phases 2.1 through 2.4.

## Parallelization note

**Phase 2.1 (standards template authoring) is parallel-eligible with Phase 1.0 Architecture Spike.** Template content is documentation work; it doesn't depend on transport / concurrency decisions. A junior contributor blocked on M1 can pick up template authoring without waiting for the spike to close.

## Phase 2.1 -- Templates

- TODO: extract from Phase 2.1 section.

## Phase 2.2 -- `optimus_init`

- TODO: extract from Phase 2.2 section.
- **Resolve opinionated-vs-auto-populated tension**: templates supply opinionated structure; first-run population is generated from tree walk; re-run is merge-with-prompt (NOT overwrite-with-confirm).
- **Tree-walk + parent-mount + .gitignore handling**: `project_root` parameter required; nested `.gitignore` files honored; sibling-project bleeding prevented.

## Phase 2.3 -- `optimus_doctor`

- TODO: extract from Phase 2.3 section.
- **Parent-mount precondition**: EUR-13 acceptance must include the parent-mount precondition; error UX outside the mount specified explicitly (not just "structured MCP error response").
- **Drift-detection default posture (v2 GA)**: drift detection runs **default-on** in host projects with a config-driven opt-out (per TR-07). If spike-1 H3 fails (`docs/decomp/pre-M1-spikes.md`), the opt-out is removed and drift detection becomes mandatory CI integration -- update this phase to drop the opt-out wiring at that point.

## Phase 2.4 -- Dogfood

- TODO: extract from Phase 2.4 section.
