# Optimus v2 -- Charter

**Status:** Founding document. Locks the foundational decisions before any code moves.
**Date:** 2026-05-10
**Origin:** v1 dogfood-test debrief + foundations doc + post-PR-#47 restructuring analysis + multiple critical-review passes.

---

## Scope framing: scoped, not minimal

v2 is **scoped, not minimal.** The core surface (multi-client MCP transport, singleton container lifecycle, retrieval tools, standards layer, safe filesystem ops, four hooks, two bundlers, two installers, cross-platform host-side installer, build-time validation telemetry, and refinement work in M6) is deliberately compact relative to v1's 18-module sprawl -- but it is not a single-shot MVP. v2 has a focused product thesis (Pillars 1-3 in priority order) and a milestone sequence that delivers each pillar with hard gates between them. That focus is the discipline; minimalism is not the goal.

---

## Naming Conventions

The project carries one identity in dev docs and a different one on user-facing surfaces. Keep the two cleanly separated:

- **Codename / project identity:** `optimus-v2` -- used in dev docs, working-directory naming during development, and any "v2 vs v1" framing. v1 was R&D and never released; the "v2" suffix preserves that distinction in dev-side language.
- **GitHub repo:** `DWaling-eci/optimus` -- the canonical end-user-facing repo name. URLs, clone paths, and Release/registry references all use `optimus` (no `-v2` suffix). Post-clone the working directory is `optimus/`.
- **Container image:** `ghcr.io/DWaling-eci/optimus:<tag>`.
- **Binary on PATH:** `optimus` (the CLI shim; see `docs/decomp/M0-cli-shim.md`).
- **End-user product name:** "Optimus."

Rule of thumb: if it's a URL, repo path, image ref, or anything a user types/sees, use `optimus`. If it's prose discussing the project as a codename or distinguishing v2 from v1, use `optimus-v2`. See AGENTS.md for the agent-loop perspective on the same distinction.

---

## Why a Clean Start

v1 started as a project code/doc retrieval MCP PoC. When the PoC proved out, scope expanded in-place rather than in a new repo. Result: scattered artifacts, load-bearing coupling between unrelated modules, and a 3,619-line god-file. Every structural improvement was blocked waiting for another structural improvement.

The clean-repo restart corrects the original sin. v1 is preserved and tagged as `archive/v1-dogfood-PoC` so nothing is lost. [v1](https://github.com/eci-rhc/optimus/releases/tag/archive%2Fv1-dogfood-PoC) also remains in place (the initial Cursor-only PoC) and includes the memory implementation (see Decision 3).

---

## Founding Decision 1 -- Three Deployment Surfaces

v2 has three independent deployment surfaces. No surface duplicates another's canonical source, and each is built/written by a different mechanism.

| Surface                    | Where                                                                     | Canonical source                                                                 | Written by                 |
| -------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | -------------------------- |
| **Container runtime**      | Docker image, started on demand (shared across IDEs if already running)   | `src/optimus/` (Python package)                                                  | Docker build               |
| **IDE bundles**            | Each IDE's plugin location (Cursor AI plugin, Claude Code plugin)         | `src/{hooks,agents,skills,rules}/` (IDE-agnostic source, OUTSIDE `src/optimus/`) | Per-IDE bundler (M4/M5)    |
| **Host-singleton runtime** | `~/.optimus/` (Linux + WSL2) / `%USERPROFILE%\.optimus\` (Windows native) | host-side installer                                                              | Host-side installer (M4.1) |

**Key principle:** IDE-side artifacts (hooks, agents, skills, rules) are authored at the repo root in `src/{hooks,...}/`, NOT inside `src/optimus/`. They are not Python; they are not container concerns; they live outside the container package. The rule is: anything that ships *into* the container goes under `src/optimus/`. Anything that ships *to an IDE* lives in `src/{hooks,agents,skills,rules}/`. Anything that lives *on the host machine* (runtime state, config, model cache, transport socket) lands under `~/.optimus/`.  The only known deviations are TBD based on R&D during scope and plan phases for milestones [M4 - Cursor Bundle](docs/decomp/M4-cursor-bundle.md) and [M5 - Claude Code Bundle](docs/decomp/M5-claude-code-bundle.md).

**Detailed manifests for each surface:**

- Container module list -- finalized at the M1.0 Architecture Spike per Decision 2. Provisional layout transplanted to `docs/decomp/M0-repo-layout.md`.
- What ships to the host project -- `docs/decomp/M2-host-project-artifacts.md`.
- What ships to user-profile -- `docs/decomp/M4-user-profile-layout.md`.
- What ships per IDE -- `docs/decomp/M4-cursor-bundle.md` and `docs/decomp/M5-claude-code-bundle.md`.

**Discovery + transport endpoints** (canonical socket path, `.mcp.json` schema, liveness-probe protocol) are pinned in `docs/decisions/transport-and-discovery.md` -- consulted by both bundlers AND the spike-2 probe, so all three implementations build to the same shape rather than inventing it independently.

**Why discovery is a decision record, not a spike output:** if spike-2 invents transport and the M1.0 Architecture Spike picks differently, the spike's work is wasted and M4/M5 bundlers face an undefined target. The decision record is **pinned pre-M0 as a provisional version**; spike-2 validates against that pre-M0 version. The **M1.0 Architecture Spike has authority to revise the record** based on implementation findings, via the normal decision-record revision process (PR + sign-off + protocol-version bump). M1.0 is a revision authority, not the original author.

---

## Founding Decision 2 -- Architecture Spike Before Module Lock-In

v1's 18-module decomposition was sized for v1 scope (retrieval + memory + extract + prune + dual cross-encoder reranking). v2 scope is materially smaller. Lifting v1's module list would be the same kind of structural debt the clean-restart was meant to avoid.

**v2 starts Milestone 1 with an Architecture Spike** (Phase 1.0, gates everything downstream).

**Inputs to the spike:**
- v2 scope (retrieval + standards + safe filesystem ops; no memory)
- v1 retained components (garp shell, spaCy pipeline, reranker)
- Pre-M1 validation spike findings (Decision 5)
- The transport-and-discovery decision record (cannot defer; required for module-list coherence)

**Required outputs:**
- The actual `src/optimus/` module list with rationale per module.
- `optimus_resolve` retain/drop call, with evidence basis from spike-1.
- spaCy retain/drop call (per Decision 5 spike-1 evidence).

**Model stack and worker-pool / concurrency strategy are LOCKED** in `docs/decisions/secure-singleton-mcp-baseline.md`: Nomic CodeRankEmbed (dense retrieval) + ColBERTv2 via colbert-ai direct (reranker; wrapper revised 2026-05-13 per `docs/decisions/colbert-wrapper-revision.md`), bipartite concurrency with a singleton ML worker process. M1.0 has revision authority over the baseline ONLY if a hard, evidence-backed roadblock surfaces during implementation; absent a roadblock, the locked stack is built. The Architecture Spike does NOT re-pick the model stack or concurrency strategy from scratch.

**No module lands in `src/` without an entry in this spike's output.** This is not "no new abstractions"; it's "abstractions justified by v2 scope, not inherited from v1."

---

## Founding Decision 3 -- Memory Feature: KILLED in v2

**Decision:** v2 ships zero memory functionality. No memory files, no memory hooks, no `optimus_prune`, no `optimus_extract`, no memory parser, no memory format invariant.

**Rationale:**

- The 2026-05-06 dogfood test confirmed Claude Code agents made 0/109 calls to optimus memory tools because Claude's native memory was already handling that workflow. Building a parallel memory protocol on a different IDE is negative value.
- The foundations doc explicitly named this: "ClaudeCode has the memory mechanics built-in now, so does not seem needed here."
- The "Cursor full / CC native / others same as CC" stance from prior drafts was a half-measure that preserved v1 code at the cost of ~30% of the v2 codebase serving a deprecated path.
- "Use the IDE's native primitives where they exist" is a real cross-IDE strategy. Optimus duplicating those primitives is anti-strategy.

**v1 remains a reference point from the Cursor-only memory PoC.** It already works, the dogfood test for *Cursor* showed value, and v1 remains tagged and installable (whether or not the memory feature is re-introduced as an option after v2 is TBD).

**Impact:** v2 drops parser/memory_io/extract/prune modules, memory hooks, memory requirements (EUR-01, EUR-05, TR-02). Hooks that ship: `search-redirect`, `shell-guard`, `read-guard`, `agent-scratch`. Detailed salvage/anti-salvage inventory in `docs/decomp/v1-salvage-inventory.md`.

---

## Founding Decision 4 -- Standards Layer is a First-Class Deliverable

The foundations doc named three pillars in this order: Standards, Tooling, Best Practices. v1 inverted that priority -- retrieval tooling shipped first and standards never followed. v2 corrects this.

**v2 ships, as MCP tools and CLI invocations:**

| Capability          | Surface        | Purpose                                                                                                         |
| ------------------- | -------------- | --------------------------------------------------------------------------------------------------------------- |
| `optimus_init`      | MCP tool + CLI | Scaffold ARCHITECTURE.md, DIRECTORY_INDEX.md, CODING_STANDARDS_INDEX.md, AGENTS.md guidance into a host project |
| `optimus_doctor`    | MCP tool + CLI | Detect drift between DIRECTORY_INDEX.md and the actual tree; flag stale entries; emit a fixup patch             |
| Standards templates | `templates/`   | Versioned, opinionated starting points; agents read these before authoring                                      |

**Rationale:**

- Agents stop listing directories when they have an accurate map. The dir-index *is* the answer to the recursive-listing problem; an MCP listing endpoint is defense-in-depth, not the primary lever.
- A dir-index that goes stale is worse than no dir-index, because agents trust it and miss real files. `optimus_doctor` is non-optional.
- TR-15 (ARCHITECTURE.md as living doc, CI-enforced) applies in v2 to the **host project's** ARCHITECTURE.md too -- via `optimus_doctor`. Not just the optimus repo's own.

The Standards Layer ships as **Milestone 2** in the roadmap (after Core Engine but before Hooks/Installer). v2 cannot be "shipped" without the standards layer in place; that's deliberate.

---

## Founding Decision 5 -- Empirical Foundation Validation Before Architecture Lock-In

Paper-only review is not enough validation. The risk: build M0 -> M1 -> M2 -> M3 in the new structure, then dogfood at M3 and discover the same lessons all over again because the structural fix masked the symptom but the empirical validation never happened.

**Pre-M1 validation spikes (mandatory gate, split into two):** the original single-spike formulation bundled two unrelated hypotheses and was unrealistically sized. v2 splits the gate into two independent spikes that run before M0 and may run in parallel:

- **Spike-1 -- Retrieval Behavior Validation:** does retrieval-only Optimus + a hand-authored DIRECTORY_INDEX.md change agent behavior on retrieval-shaped tasks? Includes a dir-index drift hypothesis: if a stale index degrades agent behavior worse than no index, `optimus_doctor` becomes load-bearing infrastructure rather than convenience.

- **Spike-2 -- Singleton Container Feasibility:** does a single host-singleton container with a user-configured parent mount serve multiple concurrent MCP clients without crashing, dropping requests, or imposing unreasonable UX cost? **Validates against** `docs/decisions/transport-and-discovery.md` (does not invent transport). Probe matrix must include 4-client concurrent dispatch (matching the envisioned workload from Decision 7) and WSL2 path translation (since WSL2 is a primary supported platform per TR-09, not an enterprise edge case).

Full hypothesis lists, gate logic, sizing, and DoDs live in `docs/decomp/pre-M1-spikes.md`. 
Proposals for spikes 1: "*Zero-trust Container network isolation*" and spike 2: "*Asynchronous Main Loop with Singleton ML Worker*" are described in [M1 Spikes Proposals](docs/decomp/pre-M1-spikes-proposals.md).
The high-level gate principle stays here in CHARTER.

**Spike outputs:** two go/no-go reports -- `docs/spikes/spike-1-retrieval-report.md` and `docs/spikes/spike-2-singleton-report.md` -- committed before M0 starts (separate pre-M0 commits, not bundled into M0 init). The scratch code under `spike/` is deleted once the reports land.

**Stochasticity note:** LLM-driven validation runs are noisy. Spike-1 protocol requires minimum 2 independent runs per condition with consistent direction across runs for a pass. Single-run "looks good" results don't gate downstream work.

---

## Founding Decision 6 -- IDE Deployment via Native Plugin Bundles

**Decision:** v2 deploys IDE-visible tooling (agents, skills, hooks, rules) as **per-IDE plugin bundles**, built from canonical sources in `src/{hooks,agents,skills,rules}/`. v2 ships bundles for **Cursor (as Cursor AI plugins, NOT VS Code extensions) and Claude Code only**. Codex, Hermes, and any future MCP-capable harness are out of scope for v2 GA as deployment targets.

**Rationale:**

- IDEs only load tooling from their own expected paths. A symlink layer from `~/.optimus/` into IDE paths is technically possible but fragile -- Windows symlink permissions, IDE-side path validation, and plugin-update conflicts make it a chronic support burden.
- Both Cursor and Claude Code have established plugin standards. Using their native plugin format eliminates the symlink fragility and aligns with how their users expect to install third-party tooling.
- A "pointer skill that lists optimus tools" approach was considered and rejected: skills behind a manual fetch step see massive usage drop-off versus auto-loaded skills.
- Source-of-truth stays single. `src/optimus/` is the Python package that ships INTO the Docker container. `src/{hooks,agents,skills,rules}/` is the canonical authoring location for IDE-side tooling -- those artifacts ship to IDEs via per-IDE bundlers, NOT into the container.

**IDE-agnostic source + per-IDE bundler adaptation:** hooks/agents/skills/rules contain no IDE-specific conditionals in source. The bundler maps IDE-specific events and transforms format at bundle time (per TR-17). If Cursor exposes an event Claude Code doesn't, the Cursor bundle wires it; the Claude Code bundle omits or maps to closest equivalent.

**Implications:**

- Per-IDE installer work is sequenced *after* core engine + standards layer are rock-solid. Milestones: M4 = Cursor bundle + installer; M5 = Claude Code bundle + installer.
- Pre-bundle (M1 + M2 + M3), the only consumer of optimus is direct CLI invocation against the container. This is sufficient to exercise and stabilize the engine; IDE integration is the *delivery* mechanism, not the *validation* mechanism.

**Non-goal:** universal plugin format or custom plugin abstraction layer. Two IDEs, two bundlers, two installers. No abstraction until a third IDE drives generalization pressure.

---

## Founding Decision 7 -- Host-Singleton Container with Parent-Mount

**Decision:** One Optimus container per host machine, not per IDE instance, not per project. The container is started once (lazily, on first MCP client connection) and shared across every IDE and every project on that host. The container mounts a **user-configured parent directory** that contains all projects the user may invoke optimus from.

**Rationale:**

- v1 spawns a container per IDE instance. Two IDEs open = two containers, each holding ~3GB resident. Real cost on a developer's laptop.
- Concurrent agent dispatch (reviewer + 3 implementers firing `optimus_grep` simultaneously) is a foreseeable load pattern that per-IDE handles poorly: each container is single-MCP-connection, so parallel sub-agents serialize through one container anyway. A singleton with internal concurrency handles this *better*, not worse.
- A "common parent directory" is not an uncommon developer convention (`~/dev/`, `~/projects/`, `/mnt/bro/thinktank/`). Stipulating it as a v2 prerequisite is a reasonable simplification compared to per-project container lifecycles.

**Hard constraints introduced:**

1. **MCP transport must be multi-client.** Multiple IDEs and multiple sub-agents within an IDE must connect concurrently. Stdio-with-single-parent semantics don't work.
2. **Concurrent request handling is non-optional.** Inflight requests are queued or processed in parallel with a configurable concurrency cap. Overflow returns a structured "busy, retry" MCP error -- never silent drops, never crashes. Worker-pool strategy named at M1.0 Architecture Spike (per Decision 2).
3. **Discovery + lifecycle.** Clients check for an existing container (per `docs/decisions/transport-and-discovery.md` liveness-probe protocol) before spawning. Stale-state cleanup on container restart.
4. **Parent-mount user agreement.** The installer prompts for the parent directory and records it in `~/.optimus/config.json`. The user MUST be informed at install time that all projects intended to use Optimus must live under that parent. Changing the parent is a config-edit + container-restart operation.
5. **Per-project scoping at the tool layer.** `optimus_grep` already takes `--startdir`. `optimus_search` MUST also accept a `project_root` parameter; the singleton container can serve any project under the parent mount, but no tool may return results from outside the calling project's root.

**Exact resource bounds** (memory cap, peak-rerank ceiling, concurrency cap default) live in TR-04 and TR-18 with the implementation; the founding constraint here is "bounds exist," not "the bound is exactly N."

See [M1 Spikes Proposals](docs/decomp/pre-M1-spikes-proposals.md) for details covering a possible resolution to these constraints.

**Fallback: multi-mount mode (v2.1)**

If singleton + parent-mount hits a hard road-block during M1.0 Architecture Spike or M1 implementation, v2 falls back to multi-mount: container per project, bind-mount that project's root. This mode already works in v1; it is the safety net, not the target.

The fallback is gated on Pre-M1 spike-2 outcomes and on M1.0 findings. **Fallback transparency:** because the multi-client transport layer is built for the singleton case, "fallback to multi-mount" is not literally zero rework -- the transport layer needs a runtime config flag to operate in single-client mode. This is named here so the fallback path is honest, not asserted as a config flip.

**Out of scope for v2:** multi-host coordination, container auto-restart on parent-mount config change, per-project container overrides.

---

## Founding Decision 8 -- IDE Plugin Format Versioning

**Decision:** Per-IDE bundles pin a **minimum supported IDE version** at bundle build time. v2 does NOT ship plugin format negotiation. When an IDE major version update breaks plugin format compatibility, v2 ships an updated bundle and the host-side installer exposes `optimus update-bundles` to fetch + re-install per-IDE bundles without touching container state.

**Rationale:**

- Both Cursor's AI plugin format and Claude Code's plugin format are moving targets. Neither is contract-stable at v2 GA.
- Format negotiation (one bundle that adapts to multiple IDE versions) is the wrong layer of abstraction this early -- adds complexity for a problem that hasn't yet manifested.
- A pinned minimum-version + explicit update command is the simplest model that survives the first major IDE update without surprising users.
- v2.1+ revisit if format-churn becomes a real support burden.

**Implications:**

- Each bundle manifest declares: `minimum_ide_version`, `bundle_format_version`, `optimus_version`.
- Installer checks `minimum_ide_version` against the detected IDE install. If older, install fails with a clear message.
- Host-side installer gains `optimus update-bundles` to re-download + re-install all registered per-IDE bundles. Does NOT touch container state, model cache, or config.
- **MCP protocol version handshake** is the companion check (TR-19): bundle vs container is one axis; the IDE's MCP client version vs the server's MCP protocol version is another. Both must succeed before tool calls proceed.

**Non-goal:** auto-update on IDE version change. User runs `optimus update-bundles` explicitly.

---

## Founding Decision 9 -- External Tool Vendoring & Distribution

**Decision:** every external-tool dependency v2 carries (garp, the chat-report toolkit, any future external tool) lives in the repo at `tools/<external-tool>/` as a **git submodule pinned to a specific commit SHA**. Pre-built artifacts (binaries for compiled tools; in-place source for interpreted tools) are committed at the relevant deployment-source path so end-users never need a build toolchain. Every pre-built binary ships with a companion `*.manifest.json` recording the source SHA, build date, and build environment for traceability.

**Rationale:**

- End-user install must never require git, Go, Python build deps, or any compile step. The host-side installer assembles pre-built artifacts; the Docker image build COPYs pre-built artifacts. Anything else makes the install fragile and the image build dependent on upstream availability.
- Pinning external tools to a SHA via submodule (not a tag, not a branch, not an unpinned `git clone`) is the only way to make "what version of tool X did we ship" answerable from a single repo state.
- Pre-built binary + companion manifest is the audit trail: at any point we can answer "this binary was built from which submodule SHA, when, on what platform" without re-running anything.

**Convention:**

- **Source location:** `tools/<external-tool>/` -- git submodule, SHA-pinned. Bumping the SHA is a deliberate PR with rationale, NOT an automated update.
- **Pre-built binaries (for compiled tools):** committed at the relevant deployment-source path (e.g., `container/vendor/<tool>` for container-side tools the Docker image consumes; host-side installer path for host-side tools). Linux binary for container-side tools; per-platform binaries for host-side tools as needed.
- **Companion manifest:** `<binary-path>.manifest.json` adjacent to each pre-built binary. Contents: `{"source_sha": "...", "submodule_path": "tools/<tool>/", "built_at": "...", "build_env": "..."}`. The submodule SHA and the manifest's `source_sha` MUST match -- CI check.
- **Interpreted-tool variant (no compile step):** the submodule contains the source; the installer references the submodule path directly. No binary artifact, no manifest. Example: chat-report (Python).

**Maintainer / CI workflow:**

1. Bump submodule SHA in `tools/<tool>/` via PR with rationale.
2. Build binary from the new ref (CI step or documented maintainer script).
3. Commit the updated binary AND its manifest at the deployment-source location.
4. CI verifies submodule SHA == manifest `source_sha` before image publish.

**Tool-specific placements (v2 GA):**

- **garp** -- `tools/garp/` (submodule) -> `container/vendor/garp-json` + `container/vendor/garp-json.manifest.json`. Runs IN the container. Linux binary baked into the image at build via COPY (no `go build`, no `git clone` at image-build time). See TR-10.
- **chat-report** -- `tools/ai-chat-report/` (submodule). Python; no compile step. Installer references the submodule path. See `docs/decisions/chat-report-sibling-charter.md`.
- **CLI shim** -- first-party Go tool, source at `cli-shim/src/`, pre-built binaries at `cli-shim/bin/<os-arch>/optimus[.exe]` with companion `optimus.manifest.json` each. See `docs/decomp/M0-cli-shim.md` for the locked record.

**First-party tools that ship as binaries:** the binary-distribution discipline above applies to BOTH external-tool vendoring (sources under `tools/<external-tool>/` as SHA-pinned submodules) AND first-party tools that ship as pre-built binaries (sources at their own first-party paths, e.g., `cli-shim/`). Source location varies -- external sources live at `tools/<external-tool>/`, first-party sources live at their own first-party path -- but the binary-distribution discipline (pre-built per OS, companion `*.manifest.json`, end-user never compiles) is unified across both. The CI integrity check correspondingly differs: external-tool manifests verify `source_sha == submodule SHA`; first-party-tool manifests verify `source_sha == optimus-v2 commit SHA at build time`.

**Non-goal:** vendoring tool *source* in-tree by copy-and-paste. Submodules with explicit SHA pins are the mechanism for external tools; in-tree copies hide upstream drift.

---

## Product Thesis (Three Pillars, Properly Ordered)

### Pillar 1 -- Standards Enforcement (LEAD)

Baseline project health standards for AI coding agents, regardless of IDE or project architecture. Shipped as `optimus_init` (scaffold) and `optimus_doctor` (drift detection) plus opinionated templates for ARCHITECTURE.md, DIRECTORY_INDEX.md, coding-standards INDEX.md, and AGENTS.md guidance.

**Why first:** the dir-index pattern means agents do *informed precision reads* instead of broad sweeps. That single change does more for token cost and reliability than any retrieval tool. Retrieval tooling (Pillar 2) is downstream of well-maintained foundation docs.

**Priority vs ship-order:** Pillar 1 is the lead pillar in *priority and adoption*, but ships in M2 (after the M1 retrieval engine) because `optimus_init` and `optimus_doctor` are MCP tools that require the engine + container to run. Standards-leads-in-priority + standards-ships-second is intentional sequencing, not a contradiction.

### Pillar 2 -- Purpose-Built Retrieval Tooling

RAG-style retrieval using the repo as source of truth. No embedding index, no external APIs, no cloud dependency. Everything runs in a Docker container on the developer's machine. See glossary entry "index-free" for the precise meaning.

Tools: `optimus_search`, `optimus_grep`, `optimus_resolve`. The exact set is confirmed by the validation spike -- `optimus_resolve` may be dropped or merged based on M1.0 evidence.

**Success criterion:** on retrieval-shaped tasks, `optimus_*` calls outnumber built-in Read/Grep/Glob calls. **Quantified threshold + baseline condition + two-signal separation rule live in `docs/decisions/success-metric.md`.** Without those, the metric is unfalsifiable; with them, the M6 dogfood gate has a real pass/fail decision.

### Pillar 3 -- Agent Coding Best Practices (Determinism + Cost)

Minimize cost of AI-assisted development while keeping the process reliable and efficient. Predictable outcomes for enterprise-grade development. Designed to provide more value the larger the project.

Surfaces: build-time validation telemetry (EUR-10), CI-enforced standards (TR-15 applied to host projects via `optimus_doctor`), safe filesystem ops (TR-13), reviewer grounding.

---

## Pre-Kickoff Prerequisite

Before M0 begins, the **chat-report sibling project** must exist. It provides the telemetry instrumentation that spike-1 and Phase 1.5 depend on. Charter, DoD, and the dual-IDE-mandatory / project-pause-only escalation policy live in `docs/decisions/chat-report-sibling-charter.md`.

This is currently the largest external dependency in v2 planning. Without it, the success-metric instrument doesn't exist and the v2 thesis cannot be validated.

---

## v1 Salvage

v1 is a parts shop, not a reference implementation. Salvageable components (garp, cross-encoder reranker, spaCy pipeline, hook source for the four retained hooks, retrieval tests) are inventoried in `docs/decomp/v1-salvage-inventory.md`. Anti-salvage entries (memory feature, scattered `.cursor/` vs `.claude/`, AGENTS.md mutation pattern, in-Dockerfile garp clone+build) live in the same doc. External-tool vendoring (garp, chat-report, future tools) follows Founding Decision 9.
