# Optimus v2 -- TDD Milestone Roadmap

**Document type:** Implementation roadmap with TDD milestone decomposition
**Status:** Founding pass
**Date:** 2026-05-10
**Source:** CHARTER.md + REQUIREMENTS.md + multiple critical-review passes

> For Agents: use the subagent driven development when executing milestones. Parent agent is the implementation agent; the resulting product targets Cursor + Claude Code only.
>
> Each milestone is a discrete deliverable with its own definition of done. Per-phase task decomposition lives in `docs/decomp/M<n>-tasks.md`, written/filled just-in-time as each milestone loads.

---

## Overview

```
Pre-Kickoff -- chat-report sibling project (see docs/decisions/chat-report-sibling-charter.md)
  |
Pre-M1 Validation Spikes (parallel-eligible, hard gate)
  Spike-1 (retrieval behavior)
  Spike-2 (singleton container feasibility)
  |
Milestone 0 -- Foundation Skeleton (repo + CI + CLI shim + debug loop)
  |
Milestone 1 -- Core Engine
  |  Phase 1.0: Architecture Spike (module list + transport choice + concurrency strategy)
  |  Phase 1.1-1.3: leaf -> mid-tier -> retrieval + safe-ops surface (TR-13)
  |  Phase 1.4: server entrypoint + singleton lifecycle + tool contracts (TR-12) + smoke tests
  |  Phase 1.5: chat-report integration (validation signal for M1-M5)
  |
Milestone 2 -- Standards Layer (optimus_init + optimus_doctor + templates)
  |  Phase 2.1 (templates) is parallel-eligible with Phase 1.0 Architecture Spike
  |
Milestone 3 -- Hook Layer (IDE-agnostic hook source; ported + tested; no installer)
  |
Milestone 4 -- Cursor Bundle + Installer (host-side installer + Cursor AI plugin bundle)
  |
Milestone 5 -- Claude Code Bundle + Installer
  |
Milestone 6 -- Dogfood Readiness (telemetry refinement, reviewer grounding, image publish)
```

Each milestone is shippable on its own. Milestones are strictly ordered (each gates the next) except where parallel-eligibility is named. IDE-by-IDE sequencing for M4 and M5 is deliberate -- one IDE focus at a time per CHARTER Decision 6.

> **Milestone-boundary posture:** task bodies in `docs/decomp/M<n>-tasks.md` for M1-M6 are intentionally skeleton placeholders. At each milestone boundary, a human PM or designated principal-agent expands the next milestone's task body before agent execution resumes. See `AGENTS.md` ("Milestone-Boundary Posture").

**Overall success metric:** on retrieval-shaped tasks in a real product codebase, `optimus_*` calls plus *informed precision reads* outnumber broad-sweep `Read/Grep/Glob` calls in both Cursor and Claude Code, verified by telemetry (EUR-10). **Quantified threshold, baseline condition, and two-signal separation rule live in `docs/decisions/success-metric.md`.** Without those, the metric is unfalsifiable and M6 cannot declare pass/fail; this is the v2 thesis's falsifiability anchor.

---

## Pre-Kickoff Prerequisite

Before M0 begins, the **chat-report sibling project** must exist. It provides the telemetry instrumentation that spike-1 and Phase 1.5 depend on.

- **Charter, DoD, owner, gating rule:** `docs/decisions/chat-report-sibling-charter.md` (locked; owner is a delegated future session; hard gate, no calendar date).
- **Dual-IDE coverage is MANDATORY.** No fallback. Spike-1 does not start until BOTH the Cursor variant AND the Claude Code variant are complete and emitting the structured report shape. If the Claude Code variant proves infeasible during reverse-engineering, the project pauses pending a re-scope discussion. There is no Cursor-only-fallback, no manual-inspection-fallback, no degraded-signal compromise.

This is the single largest external dependency in v2 planning. Without it, the v2 thesis cannot be validated empirically.

---

## Pre-M1 Validation Spikes (HARD GATE)

**Why split into two spikes:** the original single-spike formulation bundled two unrelated hypotheses (retrieval-shape behavior change AND singleton-container feasibility). Each is independently load-bearing. Splitting them lets each be sized realistically, fail independently, and run in parallel.

**Shared environment:** both spikes run from `spike/`, gitignored, throwaway. The spike code validates hypotheses; the durable artifact is each spike's go/no-go report.

**Detailed DoDs + hypotheses + gate logic + LLM-stochasticity protocol** live in `docs/decomp/pre-M1-spikes.md`.

### Spike-1: Retrieval Behavior Validation

**Thesis:** retrieval-only Optimus + a hand-authored DIRECTORY_INDEX.md changes agent behavior on retrieval-shaped tasks. The v2 thesis is wrong if this does not happen.

**Hypotheses:** behavior-change (H1), no-memory-gap (H2), drift-resilience (H3).

**LLM-stochasticity protocol:** minimum 2 independent runs per condition; consistent direction across runs required for a pass. Single-run "looks good" results don't gate downstream work.

**Estimated size:** 2-4 sessions (hand-authoring DIRECTORY_INDEX.md for a real codebase is hours alone).

**Test target:** real codebase, chosen at spike-prep time per the criteria in `docs/decomp/pre-M1-spikes.md`. No synthetic projects.

**Gate logic:** H1 fails -> v2 thesis suspect, pause and replan. H2 fails -> revisit CHARTER Decision 3 with Dustin. H3 fails -> `optimus_doctor` CI integration becomes mandatory (not opt-in).

### Spike-2: Singleton Container Feasibility

**Thesis:** a single host-singleton container with a user-configured parent-mount can serve multiple concurrent MCP clients without crashing, dropping requests, or imposing unreasonable UX cost.

**Hypotheses:** multi-client transport works (H1), concurrent requests don't crash or drop (H2), parent-mount UX acceptable (H3).

**Validates against `docs/decisions/transport-and-discovery.md`** -- does not invent transport. The decision record locks the canonical transport + discovery socket path + `.mcp.json` schema + liveness-probe protocol BEFORE spike-2 runs.

**Probe matrix requirements:**
- **4 concurrent clients** (matching CHARTER D7's envisioned reviewer + 3 implementers workload, not just 2 clients as in earlier drafts).
- **WSL2 path translation** (since WSL2 is a primary supported platform per TR-09, NOT an enterprise edge case to defer).

**Estimated size:** 1-2 sessions.

**Gate logic:** H1 or H2 fails -> fall back to multi-mount mode per CHARTER D7. H3 fails -> escalate to Dustin; charter-level reconsideration.

### Parallelization

Spike-1 and Spike-2 are independent; may run in parallel. Both must pass before M0 starts.

---

## Milestone 0 -- Foundation Skeleton

**Thesis:** Lock the structure. Every subsequent commit has a clean home.

**Definition of Done:**
- Repo has the three-deployment-surface layout from CHARTER Decision 1; provisional manifests in `docs/decomp/M0-repo-layout.md`.
- Default branch named `trunk` (explicit at `git init`).
- CI pipeline runs lint + tests on every push (`docs/decomp/M0-ci-pipeline.md` for detail).
- Docker image builds successfully (with stub server).
- **`optimus` CLI shim installed and on PATH** (`docs/decomp/M0-cli-shim.md`). Dispatches at minimum `optimus chat-report`; full subcommand registry expands at M4.
- **In-container debug loop documented** (`docs/decomp/M0-debug-loop.md`). debugpy entrypoint conditional on env var; attach configs for Cursor and Claude Code.
- Charter, AGENTS, ARCHITECTURE stub, REQUIREMENTS, CHANGELOG, VERSION committed.
- **No `src/optimus/` package implementation yet** -- just `__init__.py` stub. Module list is decided in M1.0.

**Estimated size:** 1-2 sessions (the CLI shim + debug loop adds scope).

**Hard prerequisite:** chat-report sibling project landed (per pre-kickoff); Pre-M1 spikes both pass (or fallback agreed).

---

## Milestone 1 -- Core Engine

**Thesis:** all retrieval MCP tools (final list per Architecture Spike) work correctly, with full test suite green, running inside Docker.

**Definition of Done:**
- Architecture Spike output (`ARCHITECTURE.md`) lists every module with rationale, including transport choice, MCP protocol version pinning, concurrency strategy (worker-pool / GIL handling), singleton lifecycle + discovery details, and dual-CE vs single-CE call.
- Each listed module is implemented with >=80% test coverage.
- Final retrieval tools (`optimus_search`, `optimus_grep`, optionally `optimus_resolve`) meet the **retrieval quality bar** below on a documented test corpus.
- Safe filesystem ops (`optimus_list`, `optimus_delete`, TR-13) ship with path-escape safety smoke tests passing AND **input-sanitization at MCP boundary** verified.
- `optimus_search` accepts a `project_root` parameter (per CHARTER D7 hard constraint #5); no cross-project leak.
- Tool contracts (TR-12) published as JSON Schema in `docs/contracts/`; CI drift-check job green.
- **MCP protocol version handshake** active at accept time (TR-18); mismatched clients get a clear MCP error.
- **TR-14 logging** implemented (configurable level, auto-trim, per-call format).
- **Phase 1.5 condition:** if the chat-report Claude Code variant landed pre-kickoff, Phase 1.5 must complete for M1 close. If only the Cursor variant exists (fallback), Phase 1.5 completes for Cursor only; Claude Code arm holds for M5/M6.
- Full test suite green inside Docker container.
- Smoke test (`optimus_search` against a fixture corpus + concurrent-call test + discovery test + MCP-version-handshake test + retrieval-quality eval) passes in CI.

**Retrieval quality bar:**
- `Recall@10 >= 0.85` for `optimus_search` queries.
- `MRR >= 0.60` for `optimus_search` "find the thing" navigational queries.
- **`nDCG@10 >= 0.65` absolute floor** (calibrated against CoIR leaderboard; prevents regression-only gates from protecting a mediocre baseline).
- **`nDCG@10` regression alert** -- baseline captured at M1.4 completion; CI fails if subsequent commits drop more than 5% from baseline.
- Corpus methodology (target codebase, query authorship, labeling, 80/20 held-out split, corpus versioning policy) pinned in `docs/decisions/eval-corpus-methodology.md`. Held-out 20% is the authoritative DoD gate (not visible during ranker implementation).

**Estimated size:** 8-12 sessions (multi-client MCP transport in Phase 1.2 is the highest-variance task with no reference implementation).

**Hard prerequisite:** Pre-M1 spikes pass; M0 complete.

**Phase task decomposition:** `docs/decomp/M1-tasks.md` (Phase 1.0 through 1.5).

---

## Milestone 2 -- Standards Layer

**Thesis:** v2 cannot be "shipped" without the standards foundation. `optimus_init` scaffolds it; `optimus_doctor` keeps it honest.

**Definition of Done:**
- `optimus_init` scaffolds ARCHITECTURE.md, DIRECTORY_INDEX.md, CODING_STANDARDS_INDEX.md, AGENTS.md guidance into a host project. Re-run is merge-with-prompt (not overwrite-with-confirm).
- `optimus_doctor` detects drift between DIRECTORY_INDEX.md and the actual tree and emits an actionable patch. Errors clearly when target project is outside the parent mount (EUR-13 precondition).
- Both surfaces work as MCP tools AND as `optimus <subcommand>` CLI invocations (the CLI shim from M0 dispatches; full subcommand registration completes at M4.1 but the M2 tools register on top of the M0 shim).
- Templates are opinionated, version-stamped, and shipped via installer (not embedded as Python literals).
- Optimus repo itself dogfoods: its own DIRECTORY_INDEX.md is generated by `optimus_init` and CI-checked by `optimus_doctor`.

**Parallelization note:** Phase 2.1 (standards template authoring) is parallel-eligible with M1.0 Architecture Spike. Template content authoring doesn't depend on transport / concurrency decisions; a contributor blocked on M1 can pick up template work without waiting for M1.0 to close.

**Estimated size:** 2-3 sessions.

**Hard prerequisite:** M1 complete (server + retrieval working). Exception: Phase 2.1 can start at M1.0.

**Phase task decomposition:** `docs/decomp/M2-tasks.md`.

---

## Milestone 3 -- Hook Layer (IDE-Agnostic Source)

**Thesis:** port the four retained v1 hooks into a clean IDE-agnostic shape in `src/hooks/`. **No installer in this milestone.** Hooks tested in isolation via fixture harness; IDE wiring is M4/M5 concern.

**Definition of Done:**
- `src/hooks/` contains: `search-redirect`, `shell-guard`, `read-guard`, `agent-scratch`. **Lives at the repo root (sibling of `src/optimus/`), NOT inside the container package.**
- Each hook has unit tests + a lifecycle integration test using a fixture harness (simulated IDE event input -> hook output).
- Hooks consume only an IDE-agnostic surface (CHARTER Decision 6); no Cursor-specific or Claude-Code-specific event shape leaks into source.
- Audit document records v1->v2 changes per hook (env-var renames, path adjustments, memory removal).

**Estimated size:** 1-2 sessions.

**Hard prerequisite:** M2 complete.

**Phase task decomposition:** `docs/decomp/M3-tasks.md`.

---

## Milestone 4 -- Cursor Bundle + Installer

**Thesis:** Optimus is installable in Cursor as a Cursor AI plugin via a host-side installer. One IDE focus at a time per CHARTER Decision 6.

> **Cursor terminology reminder:** Cursor exposes two distinct surfaces -- inherited VS Code extensions (`.vsix`, marketplace) and Cursor AI plugins (Cursor's own format, agentic tooling). v2 targets **Cursor AI plugins, NOT VS Code extensions.** See glossary.

**Definition of Done:**
- Host-side installer (`install.sh` + `install.ps1`) bootstraps `~/.optimus/` (container + model cache + telemetry + config), prompts for parent-mount path, starts the singleton container. Detailed user-profile layout in `docs/decomp/M4-user-profile-layout.md`.
- `bundlers/cursor/` produces a Cursor AI plugin bundle from `src/{hooks,agents,skills,rules}/` (NOT from `src/optimus/`). Detailed bundle manifest in `docs/decomp/M4-cursor-bundle.md`.
- `installers/cursor/` installs the bundle into Cursor's AI plugin location via Cursor's native plugin mechanism.
- Installer works on Linux, Windows WSL2, Windows native PS5/PS7. **macOS is out of scope for v2 GA** (TR-09).
- A user with Cursor running can invoke `optimus_search` from inside Cursor, end-to-end, after running the installer once.
- Body-bearing CLI invocations use `--body-file` pattern across all platforms (TR-09).
- **install.sh distribution endpoint** named explicitly (where `curl <URL>` resolves to). EUR-06's `curl <URL>` must resolve to a real target before M4 ships.

**Estimated size:** 3-4 sessions.

**Hard prerequisite:** M3 complete.

**Phase task decomposition:** `docs/decomp/M4-tasks.md` (incl. install.sh --upgrade EUR-08, install.sh --purge EUR-09, optimus update-bundles TR-19).

---

## Milestone 5 -- Claude Code Bundle + Installer

**Thesis:** same shape as M4, focused on Claude Code. Host-side installer is shared (M4); M5 ships the Claude Code-specific bundler + installer.

**Definition of Done:**
- `bundlers/claude-code/` produces a Claude Code plugin bundle from `src/{hooks,agents,skills,rules}/`.
- `installers/claude-code/` installs the bundle into Claude Code's expected location.
- A user with Claude Code running can invoke `optimus_*` tools after running the Claude Code installer.
- Both IDEs (Cursor + Claude Code) running on the same host share one container, one model cache, one telemetry sink (CHARTER Decision 7 / EUR-07 acceptance).
- Claude Code plugin format spec source documented (URL or attribution); bundle built against a specific named version.

**Estimated size:** 2-4 sessions (Claude Code plugin format is described in CHARTER D8 as a moving target; may require reverse-engineering effort).

**Hard prerequisite:** M4 complete.

**Phase task decomposition:** `docs/decomp/M5-tasks.md`.

---

## Milestone 6 -- Dogfood Readiness

**Thesis:** refine the trust loop. The chat-report integration from M1.5 and the safe-ops endpoints from M1.3 are already live; M6 adds heuristics, summaries, reviewer grounding, and image publishing that close out v2 GA.

**Definition of Done:**
- Telemetry refined to capture the "informed precision read" distinction on top of the M1.5 chat-report integration. **Failure modes documented in `docs/telemetry-heuristic.md` alongside the implementation.**
- Aggregate + weekly summary CLI (`optimus chat-report --weekly`) emits a human-readable cross-IDE report.
- `agent-optimus-reviewer` agent definition explicitly fetches `.gitignore`, test files, peer agent definitions, and ARCHITECTURE.md before issuing verdicts.
- Reviewability artifacts: `docs/scratch-contract.md`.
- Docker image published to **`ghcr.io/DWaling-eci/optimus:<tag>`** on trunk merge. Owner placeholder until the optimus repo lands on GitHub; one-host distribution for image + models + binaries (aligns with CHARTER Founding Decision 9).
- **v2 success metric pass/fail gate evaluated per `docs/decisions/success-metric.md`** -- threshold + baseline condition + two-signal separation. Partial-pass vs full-pass decided per the decision record.

**Estimated size:** 1-2 sessions (parallel-eligible: 6.1, 6.2 can run concurrently).

**Hard prerequisite:** M5 complete.

> **Note on scope changes from earlier drafts:** filesystem ops (`optimus_list`, `optimus_delete`, TR-13) moved to Phase 1.3 -- security-sensitive, belongs with the rest of the MCP tool surface. Chat-report integration moved to Phase 1.5 -- so M1-M5 generate validation signal. M6 keeps only refinement work that genuinely depends on having both IDE bundles deployed. GitHub Copilot integration removed entirely (out of scope per Decision 6).

**Phase task decomposition:** `docs/decomp/M6-tasks.md`.

---

## Migration Tool (Deferred, Not in v2 GA)

A v1 -> v2 migration tool is **removed from v2 GA scope** to keep core implementation narrowly focused. Rationale:

- v1 remains the supported product for Cursor memory users; most v1 installs should NOT migrate.
- Non-memory v1 users can uninstall v1 and install v2 manually.
- A migration tool that handles "drop memory artifacts with confirmation" is non-trivial UX that does not earn its way into v2 GA.

Candidate for v2.0.1 patch or v2.1, dependent on user demand observed during v2 GA dogfooding.

---

## Milestone Dependency Graph

```
chat-report sibling project (pre-kickoff)
  |
Pre-M1 Validation Spikes (HARD GATE)
  Spike-1 (retrieval behavior) -- PARALLEL with Spike-2
  Spike-2 (singleton container) -- PARALLEL with Spike-1
  |
M0 (skeleton + CI + CLI shim + debug loop)
  |
M1.0 (Architecture Spike + ARCHITECTURE.md, incl. transport + concurrency + lifecycle decisions) [HARD GATE for M1.x]
  |
M1.1 (leaf modules)               -- PARALLEL within phase
M1.2 (mid-tier incl. transport)   -- after M1.1
M1.3 (retrieval surface + safe-ops + eval corpus)  -- after M1.2
M1.4 (server + singleton + smoke test + retrieval eval)  -- after M1.3
M1.5 (chat-report integration)    -- after M1.4 (or M1.4-parallel for Cursor-only fallback)
  |
M2.1 (templates)              -- PARALLEL-ELIGIBLE WITH M1.0 (template content is content authoring, no M1 dependency)
M2.2 -> M2.3 -> M2.4          -- sequential, after M1 + M2.1
  |
M3.1 (hook audit) -> M3.2 (port + test)
  |
M4.1 (host-side installer)         -- shared base for M4 + M5
M4.2 (Cursor bundler)               -- PARALLEL with M4.1
M4.3 (Cursor installer)             -- after M4.1 + M4.2
  |
M5.1 (Claude Code bundler)          -- PARALLEL with M4.3 (resolved: per the dependency graph, parallel is approved)
M5.2 (Claude Code installer + cross-IDE test) -- after M4.3 + M5.1
  |
M6.1 (telemetry refinement)         -- PARALLEL with M6.2
M6.2 (reviewer + reviewability)     -- PARALLEL with M6.1
M6.3 (image publish)                -- after M6.1 + M6.2
```

---

## Sequencing Notes

- **Pre-kickoff chat-report sibling is non-negotiable.** Until its DoD + owner + deadline are set in `docs/decisions/chat-report-sibling-charter.md`, every downstream milestone has hidden risk. Fallback (Cursor-only spike-1 + Cursor-only M1.5) is named in the same record.
- **Pre-M1 spikes are non-negotiable.** Split into two; each independently load-bearing; both must pass (or fallback agreed) before M0.
- **M1.0 Architecture Spike is also a hard gate.** No `src/optimus/` module work begins until ARCHITECTURE.md is written and reviewed -- including transport choice (per `docs/decisions/transport-and-discovery.md`), concurrency strategy (GIL handling, worker pool), singleton lifecycle, MCP protocol version pinning.
- **M2.1 templates can run in parallel with M1.0.** Content authoring is independent of transport / concurrency decisions; this unblocks parallel contributors.
- **M2 ships before any installer work** -- standards templates are independent of IDE deployment.
- **M3 is hook source only.** No installer in M3 -- lets hook source stabilize against a fixture harness before any IDE wiring.
- **M4 and M5 are IDE-by-IDE deliberate.** Per CHARTER Decision 6, one IDE at a time keeps focus narrow. M4 lands the shared host-side installer that M5 reuses.
- **M5.1 may start in parallel with M4.3** (per the dependency graph above; this resolves the prior Open Question 3).
- **M6 phases are parallel-eligible** but only after M5 lands the second IDE installer (some M6 work touches installed artifacts in both IDEs).

---

## Open Questions for Dustin (Decisions Pending)

(All previously open questions resolved -- see below.)

**Resolved:**

1. `optimus_doctor` drift detection (formerly Task 2.3.2 open question): **default-on with config-driven opt-out** in host projects, gated by spike-1 H3. If H3 fails (stale dir-index proves worse than no dir-index), opt-out is removed and drift detection becomes mandatory CI integration. See TR-07 in `docs/requirements/REQUIREMENTS.md` and gate logic in `docs/decomp/pre-M1-spikes.md` (spike-1).
2. Image registry: **`ghcr.io/DWaling-eci/optimus:<tag>`** (GitHub Container Registry). Owner placeholder pending repo landing on GitHub. Aligns with CHARTER Founding Decision 9 (model artifacts also ship via GitHub Releases on the same repo); one-host distribution for image + models + binaries.
3. M4.3 / M5.1 parallel-eligibility -- resolved per the dependency graph above: parallel approved.

(Test target codebase selection moved into spike-1 DoD via `docs/decomp/pre-M1-spikes.md` -- chosen at spike-prep time per documented criteria, not pinned in this plan.)

(Spike-1 IDE-target question resolved: chat-report capability for Cursor (salvage) and Claude Code (sibling project) exists pre-kickoff; spike-1 IDE choice is operational, not architectural. See `docs/decisions/chat-report-sibling-charter.md`.)
