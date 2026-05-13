---
expansion-status: skeleton
filled-by: null
filled-at: null
---

# M1 -- Core Engine (Task Decomposition)

**Status:** clean stub. Milestone outcomes + DoD live in roadmap M1. Per-phase tasks transplant here at refactor time.

**Source:** transplanted from active TDD-ROADMAP.md Milestone 1 (Phases 1.0 through 1.5). Reviewed against CHARTER + REQUIREMENTS triad.

## Phase 1.0 -- Architecture Spike

- **Evaluate and validate before implementing.** Phase 1.0 is the hard gate; no `src/optimus/` module work begins until ARCHITECTURE.md lands per the current roadmap (TDD-ROADMAP M1 DoD).
```markdown
### Phase 1.0 -- Architecture Spike (HARD GATE FOR M1.x)

#### Task 1.0.1: Author ARCHITECTURE.md from spike inputs

**Inputs:**
- v2 scope (CHARTER Decision 1, 3, 4)
- v1 retrieval/reranker/garp components (salvage list -- spaCy excluded per `docs/decisions/spacy-keep-drop.md`).
- Pre-M1 spike findings (spike-1 H1/H2/H3 + spike-2 transport/concurrency feasibility). spaCy keep/drop is no longer a spike output -- see `docs/decisions/spacy-keep-drop.md` for the locked DROP verdict and revision bar.

**Output:** `ARCHITECTURE.md` containing:
- Module list under `src/optimus/`, with one-line purpose per module
- Cross-module dependency graph
- Decision section: `optimus_resolve` retained vs dropped vs merged
- (`spacy_pipeline` is NOT a Phase 1.0 decision -- DROPPED per `docs/decisions/spacy-keep-drop.md`. ARCHITECTURE.md's module list does not include `spacy_pipeline.py`.)
- **Validate locked transport + protocol-version against spike findings.** `docs/decisions/transport-and-discovery.md` locks Unix socket (Linux/macOS/WSL2) + named pipe (Windows), the `.mcp.json` schema, 500ms+200ms liveness probe, and `SO_PEERCRED` / `GetNamedPipeClientProcessId` auth. M1.0 has **hybrid revision authority per the locked record** — revise ONLY on hard roadblock surfaced during implementation, via normal decision-record revision (PR + sign-off + `optimus_protocol_version` bump). Otherwise: confirm the locks hold and proceed.
- **Decision section: concurrency model and request queueing.** How does the container handle parallel `optimus_grep`/`optimus_search` calls from multiple clients? Worker pool size default. Backpressure strategy. Failure-mode contract for "busy, retry."
- **Decision section: singleton lifecycle and discovery.** Socket location and stale-state cleanup (no pid-file; see `docs/decisions/transport-and-discovery.md`), container-not-running detection from the MCP client side.

**Commit:** `docs: ARCHITECTURE.md -- v2 module list and design decisions`

**Gate:** ARCHITECTURE.md is reviewed and approved before any module implementation begins.

#### Task 1.0.2: Create module stubs per ARCHITECTURE.md + import smoke tests

Mirror the v1 M0.2 pattern (stubs + import tests) but driven by the **actual** module list from 1.0.1, not v1's 18 modules.

**Commit:** `feat: package stubs per ARCHITECTURE.md`

```
- **Named deliverables:**
  - Worker-pool / concurrency strategy -- explicit answer to "how do we not block the event loop on CPU-bound rerank with multiple concurrent clients."
  - Transport + discovery decision record -- Phase 1.0 may revise `docs/decisions/transport-and-discovery.md` based on findings, via the normal decision-record revision process (PR + sign-off + `optimus_protocol_version` bump). The record is **pinned pre-M0 as a provisional version**; M1.0 is a **revision authority, not the original author**. Spike-2 already validated against the pre-M0 version.
  - `optimus_resolve` retain/drop call -- explicit answer based on spike-1 evidence.

## Phase 1.1 -- Leaf Modules

- TODO: extract from Phase 1.1 section.
- **`spacy_pipeline.py` is NOT BUILT** per `docs/decisions/spacy-keep-drop.md` (DROP verdict, locked 2026-05-13). Phase 1.1 module list omits it. v2 has no runtime, build-time, or install-time dependency on `spacy`. Other leaf modules (config, garp_shell) proceed normally.

## Phase 1.2 -- Mid-Tier Modules

- TODO: extract from Phase 1.2 section.
- Multi-client MCP transport implementation is the highest-variance task in this phase (no reference implementation to crib from).

## Phase 1.3 -- Retrieval + Safe-Ops Surface

- TODO: extract from Phase 1.3 section.
- **Eval corpus authoring per `docs/decisions/eval-corpus-methodology.md`** -- corpus stub committed before ranker implementation starts.
- **`project_root` parameter added to `optimus_search` contract** -- mirror garp's `--startdir` scoping for the retrieval surface.
- **Input sanitization at MCP boundary** -- `--pathscope` / `--startdir` and any other agent-string parameters validated before reaching subprocess.

## Phase 1.4 -- Server Entrypoint + Singleton Lifecycle + Smoke Test

- TODO: extract from Phase 1.4 section.
- **TR-14 logging implementation** -- configurable level, auto-trim to 500 entries, per-call log format. Currently orphan in REQUIREMENTS; this is its work item.
- **MCP protocol version handshake** -- accept loop validates connecting client's MCP version against server's supported range; clear error on mismatch.
- **CI retrieval-quality eval job** -- runs the held-out 20% of the eval corpus; reports Recall@10 / MRR / nDCG@10; gates merges on absolute floor + 5% regression.

## Phase 1.5 -- Chat-Report Integration

- TODO: extract from Phase 1.5 section.
- **Depends on `docs/decisions/chat-report-sibling-charter.md`** -- the sibling project must have shipped BOTH Cursor and Claude Code variants (dual-IDE mandatory; no fallback per the locked charter) before this phase begins.
- **CLI dispatch** -- `optimus chat-report <id>` works as a host-shell command from M0 onward (per Phase 0.3 shim install).
- **ID disambiguation logic**: probe Cursor store first, then Claude Code; error on found-in-both or found-in-neither; `--ide` flag for explicit override.

## Definition of Done

- TODO: extract from roadmap M1 DoD bullets.
- Add absolute nDCG@10 floor alongside the 5% regression threshold (prevents regression-only gates from protecting a mediocre baseline).
- Phase 1.5 status in DoD must be explicit -- can M1 ship without 1.5 if the sibling project slips, or does 1.5 block M1 close?

## Sizing estimate

- **Estimate:** 8-12 sessions, with multi-client MCP transport (Phase 1.2) as the highest-variance task. Revisit after Phase 1.0 closes.
