---
expansion-status: skeleton
filled-by: null
filled-at: null
---

# M4 -- Cursor Bundle + Installer (Task Decomposition)

**Status:** clean stub. Milestone outcomes + DoD live in roadmap M4. Per-phase tasks transplant here at refactor time.

**Source:** transplanted from roadmap Phases 4.1 through 4.3.

## Phase 4.1 -- Host-Side Installer (Shared Base)

- TODO: extract from Phase 4.1 section.
- **Task 4.1.3b (CLI shim install)** -- promoted to M0 (see `M0-cli-shim.md`). M4 expands the subcommand registry; M0 wires the minimum (`chat-report`).
- **install.sh distribution endpoint** -- name where the install script is hosted (GitHub Releases asset / raw repo URL / dedicated CDN). EUR-06's `curl <URL>` must resolve to a real target.

## Phase 4.2 -- Cursor Bundle Builder

- TODO: extract from Phase 4.2 section.
- **Bundler pulls from `src/{hooks,agents,skills,rules}/`** -- NOT from `src/optimus/`. Hook source lives outside the container package so it ships via per-IDE bundlers, not into the runtime image.

## Phase 4.3 -- Cursor Installer

- TODO: extract from Phase 4.3 section.
