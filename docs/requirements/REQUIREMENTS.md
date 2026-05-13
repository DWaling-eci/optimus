# Optimus v2 -- Requirements

**Document type:** Requirements reference (technical + end-user)
**Status:** Founding pass
**Date:** 2026-05-10

---

## End-User Requirements

These describe what the system must do from the perspective of a developer using Optimus in their daily AI-coding workflow.

### EUR-01: *Intentionally retired -- see CHARTER Founding Decision 3 (memory feature killed in v2).*

### EUR-02: Intelligent Retrieval

The system MUST retrieve relevant project knowledge in response to natural-language queries. Retrieval MUST NOT require embeddings, vector databases, or external API calls.

Acceptance: `optimus_search("how does the reranker batch size affect memory")` returns the relevant ARCHITECTURE.md and project doc entries with correct ranking, running entirely offline.
- Full framework details for the core Optimus MCP Server design are in the [Secure Singleton MCP Baseline](docs/decisions/secure-singleton-mcp-baseline.md) document (*all code snips are "close" examples and optimus_server.py only demonstrates `optimus_search()`*).

### EUR-03: Code Search

The system MUST provide multi-term proximity code search across a single project (NOT across all projects under the parent mount).

Acceptance: `optimus_grep(["rerank_batch_size", "memory"], project_root=<active project>)` returns files where both terms appear within a configurable distance window, in under 3s on a 10k-file repo.

**Per-call scope restriction is mandatory:** every search/grep call carries a `project_root` parameter that scopes results to one project under the parent mount. The container serves any project under the mount; tools never return results from outside the calling project's root. Implementation-level garp flags (`--startdir`, `--json`, `--pathscope`) live in `docs/decomp/M1-tasks.md`.

### EUR-04: Scope Resolution

The system SHOULD identify which subdirectories and submodules are relevant to a query before performing a broad search.

**Note:** This requirement is conditional. The M1.0 Architecture Spike makes the retain/drop call for `optimus_resolve` based on spike-1 evidence. If a current DIRECTORY_INDEX.md (EUR-11) makes scope-resolution-as-MCP-tool redundant, the tool is dropped or merged into `optimus_search`.

Acceptance (if retained): `optimus_resolve("authentication middleware")` returns the correct subdirectories with confidence scores in under 2s.

### EUR-05: *Intentionally retired -- see CHARTER Founding Decision 3 (memory feature killed in v2).*

### EUR-06: Minimum-Step Install

A developer with Docker and modern Node.js (Node 18 LTS or newer) installed MUST be able to install Optimus with a small, named set of steps -- not a single command, but a small enough sequence that documentation can prescribe it.

Acceptance: the full install consists of:
1. **Host-side base install** (one command: `curl -fsSL https://raw.githubusercontent.com/DWaling-eci/optimus/<version-tag>/install.sh | bash` on Linux/WSL2, equivalent PS on Windows). Sets up `~/.optimus/`, installs the singleton container, registers the `optimus` CLI shim on PATH.
2. **Per-IDE bundle install** (one command per IDE). Installs the per-IDE plugin bundle.

After these steps, `optimus_*` tool calls succeed immediately in each IDE without restart. **Total: 1 + N commands for N IDEs.** This is the floor; framing it as "one command" was inaccurate.

**Install command URL pattern (locked):** the host-side install command resolves to the version-tagged `install.sh` at the optimus GitHub repo root: `https://raw.githubusercontent.com/DWaling-eci/optimus/<version-tag>/install.sh`. `DWaling-eci` is filled in when the optimus repo lands on GitHub; `<version-tag>` is the release tag (e.g., `v2.0.0`). Version-tagged URLs guarantee install reproducibility. This is the install-script endpoint -- a separate concern from the image registry endpoint (`ghcr.io/DWaling-eci/optimus:<tag>`, per TR-07) and from per-IDE bundle distribution (per `docs/decomp/M4-tasks.md`). All three endpoints live on the same `optimus` GitHub repo, aligning with CHARTER Founding Decision 9's one-host-distribution discipline.

### EUR-07: Cross-IDE Portability

A developer using both Cursor and Claude Code on the same machine MUST be able to use Optimus in both without running redundant installers or maintaining duplicate state.

In v2:
- One host-singleton container serves both IDEs (CHARTER Decision 7 / TR-18).
- One user-profile install (`~/.optimus/`) sets up the container, model cache, telemetry, and parent-mount config.
- Per-IDE plugin bundles install once per IDE per machine via each IDE's native plugin mechanism (CHARTER Decision 6 / TR-17). Installing the Claude Code bundle after the Cursor bundle does NOT re-install or duplicate user-profile artifacts.

Acceptance: After running the host-side installer once and installing each per-IDE bundle once, using Optimus in both Cursor and Claude Code requires no additional setup. Sub-agents in both IDEs reach the same container and the same telemetry sink.

**v2 IDE scope:** Cursor and Claude Code only. Codex, Hermes, and other MCP-capable harnesses are out of scope for v2 GA.

### EUR-08: Upgrade Without Config Loss

Upgrading Optimus MUST NOT modify or delete user configuration. User-authored settings in `~/.optimus/config.json` (parent-mount path, concurrency cap, log level, etc.) MUST survive an upgrade.

Acceptance: `install.sh --upgrade` on a host with a customized `~/.optimus/config.json` results in the user's overrides being preserved (merge or prompt, not silent overwrite). Per-IDE bundle versions are upgraded independently and MUST NOT clobber unrelated bundles.

### EUR-09: Clean Uninstall

Uninstalling Optimus MUST remove all installer-managed artifacts. A `--purge` flag MUST enable full teardown including Docker image and user-profile cache.

Acceptance: Post-uninstall, `~/.optimus/` no longer contains installer-managed artifacts (default `--uninstall` preserves `~/.optimus/model-cache/`; `--purge` removes the entire `~/.optimus/` tree). The singleton container is stopped and (for `--purge`) the Docker image removed. Per-IDE plugin bundles uninstalled via each IDE's registered uninstaller.

### EUR-10: Telemetry for Trust (Build-Time Validation Aid)

The system MUST provide a way to verify, post-session, that agents are actually reaching for `optimus_*` tools versus falling back to IDE-builtin Read/Grep/Glob. This is the empirical instrument behind the v2 thesis.

**Architecture note:** the MCP server cannot observe IDE-builtin tool calls -- those go to the IDE's native tool stack and never cross the MCP boundary. Therefore v2 does NOT instrument telemetry at the MCP-server layer. Instead, v2 leverages the fact that **each supported IDE already logs all agent tool calls in its own chat-history store** and ships report-generator scripts that parse those stores into actionable metrics.

The telemetry tooling itself is built as a sibling project before Optimus v2 kickoff -- see `docs/decisions/chat-report-sibling-charter.md`. Phase 1.5 integrates the pre-existing tools; it does not build them.

**Quantified success threshold + baseline condition + two-signal separation rule** (informed reads vs `optimus_*` calls tracked independently) live in `docs/decisions/success-metric.md`. Without those, the metric is unfalsifiable.

**Informed-precision-read distinction (heuristic):** the chat-report parser classifies reads as "informed" (read followed a DIRECTORY_INDEX.md consult within the same agent turn) vs "sweep" (no preceding dir-index consult). The heuristic has documented failure modes -- see `docs/telemetry-heuristic.md`.

**Status in v2:** this is a **build-time validation aid**, not a polished GA telemetry product. A more polished telemetry surface is a v2.1+ enhancement candidate.

### EUR-11: Agent Directory Index (Standards Layer)

A developer maintaining a well-structured project MUST be able to provide agents with an accurate directory-structure index that eliminates recursive directory-listing operations. Agents consult this doc to scope searches rather than calling a tool.

Acceptance: A project with a current `DIRECTORY_INDEX.md` at repo root results in agents performing targeted reads/searches rather than broad directory sweeps, as measured by telemetry (EUR-10).

### EUR-12: Project Scaffolding (`optimus_init`)

The system MUST provide a one-command scaffolding tool that drops the standards foundation into a host project: `ARCHITECTURE.md`, `DIRECTORY_INDEX.md`, `CODING_STANDARDS_INDEX.md`, and AGENTS.md guidance.

**Templates supply opinionated structure; first-run population generates content from the project tree; re-run is merge-with-prompt (NOT overwrite-with-confirm).** The "opinionated AND auto-populated" distinction matters:

- *Opinionated structure:* templates ship with concrete section headings, opinionated organization, version stamps. NOT blank stubs.
- *Generated content:* on first run, `optimus_init` walks the project tree (respecting `.gitignore`) and populates seed content (e.g., DIRECTORY_INDEX.md entries).
- *Merge on re-run:* if files exist, prompt-and-merge each section, never overwrite blanket.

Acceptance: `optimus_init` on a fresh project creates all four artifacts. Re-running on a project with existing files merges per section with user confirmation; no silent overwrites.

### EUR-13: Standards Drift Detection (`optimus_doctor`)

The system MUST detect drift between `DIRECTORY_INDEX.md` (and optionally `ARCHITECTURE.md`) and the actual repo state. Drift output MUST be actionable (a patch the agent or developer can apply).

**Preconditions:**
- The target project MUST live under the configured parent mount (TR-18). If the project is outside the parent mount, `optimus_doctor` MUST return a clear actionable error naming the precondition and pointing at the user-profile config to update -- NOT a generic "access denied" or unstructured failure.

Acceptance: After adding a new top-level directory to a project under the parent mount, `optimus_doctor` detects the missing entry and emits either a unified diff or a structured report. Exit code is non-zero on drift, zero on clean. Outside the parent mount, the tool errors with a clear precondition message.

---

## Technical Requirements

These describe what the system must do at the implementation and operations level.

### TR-01: Python Package Structure

The MCP server MUST be implemented as a proper Python package (`src/optimus/`) with one module per logical subsystem. The top-level entrypoint MUST be a thin wrapper (<=100 lines) that delegates to subsystem modules.

**Module list is finalized by the Architecture Spike (CHARTER Decision 2), not pre-specified here.** Provisional grouping lives in `docs/decomp/M0-repo-layout.md`; the Architecture Spike output (an updated `ARCHITECTURE.md`) is what TR-01 enforces against.

### TR-02: *Intentionally retired -- see CHARTER Founding Decision 3 (memory feature killed in v2).*

### TR-03: ML Model Isolation

ML model weights (Nomic CodeRankEmbed + ColBERTv2 via colbert-ai direct, per `docs/decisions/secure-singleton-mcp-baseline.md` + `docs/decisions/colbert-wrapper-revision.md`) MUST be stored in a user-global cache (`~/.optimus/model-cache/`) shared across all Optimus projects on the machine. The Docker image MUST NOT bake in or download model weights -- not at build time and not at runtime. Models are downloaded by the installer from the optimus repo's GitHub Releases, SHA-verified against the release's pinned manifest, placed in `~/.optimus/model-cache/`, and bind-mounted **read-only** into the container at runtime. The `network_mode: "none"` posture (TR-06) makes runtime model fetches physically impossible, which is the architectural enforcement of this requirement. Full distribution + trust model (including the `trust_remote_code=True` rationale) lives in `docs/decisions/secure-singleton-mcp-baseline.md` section 6.

### TR-04: Memory Bounds

The Docker container MUST operate within 8 GB memory at all times. Intra-call rerank peak MUST NOT exceed 1 GB. Baseline resident MUST NOT exceed 3 GB after warm-up. These bounds are enforced by `mem_limit: 8g` in docker-compose and tuned via `rerank_batch_size` (default 16).

**Note:** "Memory" here means container RAM, not the v1 memory feature.

### TR-05: Determinism

Search results MUST be deterministic: identical inputs produce identical ranked outputs. No randomness in retrieval or ranking. This enables regression testing and trust-building with end users.

### TR-06: Zero External API Calls

The MCP server MUST operate entirely offline after Docker image build and model cache warmup. No calls to OpenAI, HuggingFace inference endpoints, or any external service during tool operation.

**Enforcement layer:** this MUST be enforced architecturally, not solely in application logic. The singleton container MUST run with a restrictive Docker network configuration (e.g., `--network none` after model-cache warmup, or an equivalent egress block). If an agent payload or model anomaly attempts an outbound HTTP request, the OS / Docker layer prevents it; application-layer enforcement alone is insufficient as defense-in-depth.

### TR-07: CI/CD Pipeline

The repo MUST have a CI/CD pipeline (lint + unit + container smoke test + retrieval-quality eval + `optimus_doctor` self-check + image publish on trunk push). Detailed task breakdown in `docs/decomp/M0-ci-pipeline.md`.

**Image registry (locked):** the Docker image is published to **GitHub Container Registry**: `ghcr.io/DWaling-eci/optimus:<tag>`. The `DWaling-eci` placeholder is filled in when the optimus repo lands on GitHub. Rationale: free for public images, no pull rate limits, integrated with the optimus GitHub repo + Releases. Aligns with CHARTER Founding Decision 9 -- model artifacts also ship via GitHub Releases on the same repo, giving v2 a single-host distribution surface for image + models + binaries.

**`optimus_doctor` self-check scope** (consumed by this CI step and by installer/update flows): the self-check MUST validate (a) the host-side install state (`~/.optimus/` layout, `VERSION` file, parent-mount config), (b) the **model-manifest state** -- compare the current optimus release's `models-manifest.json` against `~/.optimus/installer-state/models-manifest.json` and trigger smart-skip vs SHA-verified download+replace -- and (c) the bundle-vs-container compatibility per TR-19. Full model distribution + trust model in `docs/decisions/secure-singleton-mcp-baseline.md` section 6.

**Drift-detection default posture (host projects):** `optimus_doctor`'s DIRECTORY_INDEX.md (and optional ARCHITECTURE.md) drift detection runs **default-on** in host projects with a **config-driven opt-out** (e.g., `optimus.config.json` `doctor.drift_detection: false` or equivalent). This is the v2 GA posture. **H3 gate (per `docs/decomp/pre-M1-spikes.md`, spike-1):** if spike-1 H3 fails -- i.e., a stale dir-index proves worse than no dir-index -- the opt-out is **removed** and `optimus_doctor` drift detection becomes **mandatory CI integration** with no opt-out. Until the H3 result is known, default-on-with-opt-out is the posture. The optimus repo itself dogfoods drift detection unconditionally (TR-15); the opt-out applies only to host projects.

### TR-08: Test Coverage Targets

Per-module test coverage MUST be >=80% for all modules under `src/optimus/`. Tests MUST run inside the Docker container to catch dependency and env issues.

### TR-09: Installer Cross-Platform Correctness

The installer MUST work correctly on:
- Linux (bash, tested on Ubuntu 22.04+)
- Windows with WSL2 (bash in WSL2)
- Windows native (PowerShell 5.1 and 7.x)

**macOS is explicitly out of scope for v2 GA.** macOS is a candidate for v2.1+; a clean additive surface.

**WSL2 is a primary supported platform, not an edge case.** Spike-2 probes WSL2 path translation specifically (since the singleton + parent-mount design depends on path resolution working across the Windows / WSL2 boundary).

Body-bearing CLI invocations (gh, git) MUST use `--body-file` / `-F` pattern rather than inline string interpolation, on all platforms.

### TR-10: garp Version Pinning

The `garp` proximity search tool MUST be pinned to a specific commit SHA via the `tools/garp/` git submodule (per CHARTER Founding Decision 9 -- External Tool Vendoring & Distribution). The Linux binary MUST be pre-built from that submodule SHA and committed at `container/vendor/garp-json`, with a companion `container/vendor/garp-json.manifest.json` recording the source SHA, build date, and build environment. The Dockerfile COPYs the pre-built binary; **no `git clone`, no `go build`, no compile step inside the image build**. CI MUST verify the submodule SHA matches the manifest's `source_sha` field before image publish. Minimum garp version: v0.7 (provides the `--startdir`, `--json`, and `--pathscope` flags v2 depends on). Detailed flag usage in `docs/decomp/M1-tasks.md`.

### TR-11-rev: Hook IDE Compatibility

All v2 hooks MUST work in the v2-supported IDEs: **Cursor and Claude Code only** (per CHARTER Decision 6). **Hook source code MUST contain no IDE-specific conditionals.** Per-IDE event-name mapping and format transformation happen exclusively in the bundler (per TR-17), NOT in the hook source.

Support for additional MCP-capable harnesses (Codex, Hermes, future) is explicitly out of scope for v2 GA and a v2.1+ candidate.

### TR-12: MCP Tool Contracts

Every MCP tool MUST have a documented contract:
- Input parameter types and validation rules
- Return shape (schema, example)
- Error conditions and how they surface
- Performance target (P95 latency on representative corpus)

Tool contracts MUST be machine-checkable (OpenAPI or JSON Schema) so the CI pipeline can validate them against the actual server implementation. Per-tool contract enumeration lives in M1/M2 decomp.

**Retrieval quality gate** (consumed by M1 DoD): `optimus_search` and `optimus_grep` must meet Recall@10 / MRR / nDCG@10 thresholds on a documented test corpus. Methodology -- target codebase selection, query authorship discipline, labeling rules, 80/20 held-out split, corpus versioning -- pinned in `docs/decisions/eval-corpus-methodology.md`. The held-out 20% is the authoritative DoD gate.

### TR-13: Filesystem-Ops Endpoints (Safe Ops)

The MCP server MUST provide:
- `optimus_list(paths, filter?)` -- safe directory listing, project-relative paths only, no wildcards in input, no shell tokenization
- `optimus_delete(path, recursive?)` -- safe delete, confined to scratch roots or an explicit config allowlist

These endpoints MUST perform path validation server-side. **All agent-provided string inputs (paths, glob fragments, scope filters) MUST be sanitized at the MCP boundary BEFORE reaching any subprocess invocation (garp, ripgrep, etc.).** No shell-out without sanitization. No regex or wildcard injection vectors. Errors MUST be surfaced as actionable MCP error responses, not crashes.

**Framing:** these are defense-in-depth for the small surface where DIRECTORY_INDEX.md is insufficient. They are not the primary listing mechanism.

**Multi-project trust model (CHARTER Decision 7 implication):** the host-singleton container serves all projects under the user-configured parent mount. Cross-project safety relies on the **scratch-file naming convention** (every agent-authored scratch file/directory prefixed with a unique identifier tying it to the originating agent). The `agent-scratch` hook injects the identifier at creation time; `optimus_delete` confines to scratch roots and agent-id-scoped paths.

The scratch-file convention remains the cross-project safety contract at the **application** layer, appropriate for a single-machine, single-user local development environment.

**Connection-layer enforcement (locked):** the honor-system framing at the transport boundary is **retired**. Every MCP connection to the singleton container is authenticated at handshake by **process-credential verification** -- `SO_PEERCRED` UID check on Unix domain sockets (Linux + macOS + WSL2), `GetNamedPipeClientProcessId` + token SID check on Windows named pipes. Connections from any user other than the singleton owner are rejected before MCP frames are accepted. This protects against non-hook MCP clients (CI scripts, test harnesses, future IDEs) because hook-layer enforcement is bypassable by design and was never the real fix.

Full implementation spec (auth model details, failure mode, logging requirements) lives in `docs/decisions/transport-and-discovery.md` section 4.

### TR-14: Logging + Observability

Every tool call MUST be logged to `optimus-tool.log` with at minimum: timestamp, tool name, and completion status. Log level MUST be configurable via `optimus.config.json` (`false`, `"info"`, `"detail"`, `"debug"`). Log MUST auto-trim to a configurable entry count (default 500).

**Implementation milestone:** logging lands at M1.4 (see `docs/decomp/M1-tasks.md`); previously orphan.

### TR-15: ARCHITECTURE.md as Living Doc (Self + Host Projects)

`ARCHITECTURE.md` MUST reflect the current module layout, line counts, and system diagram at all times. PRs that change module structure MUST include `ARCHITECTURE.md` updates. CI-enforced for the optimus repo itself. The tool MUST gracefully handle pre-existing `ARCHITECTURE.md` docs in host projects -- suggest changes to meet minimum requirements; recognize external file references (e.g., `*.drawio` diagrams) that fulfill required elements.

For host projects, `optimus_doctor` (EUR-13) provides the equivalent enforcement. **Default posture: default-on with config-driven opt-out** (per TR-07's drift-detection default posture); opt-out is removed if spike-1 H3 fails (`docs/decomp/pre-M1-spikes.md`).

### TR-16: Standards Templates Are Opinionated

`optimus_init` templates MUST supply opinionated structure (per EUR-12 -- structure is opinionated, content is generated, re-run is merge-with-prompt). Templates MUST include concrete section structure (NOT blank stubs), a version stamp tying the template to the optimus version that emitted it, and seed content that demonstrates the expected fill-in style.

Templates MUST be authored and tested in `templates/` and shipped via the installer to user-profile, not embedded as Python string literals.

### TR-17: IDE Bundle + Installer Surface

Per CHARTER Decision 6, v2 deploys IDE-visible tooling via per-IDE plugin bundles built from a single canonical source.

Requirements:
- Canonical source for IDE-side artifacts MUST live under `src/{agents,skills,hooks,rules}/` -- **OUTSIDE `src/optimus/`**. `src/optimus/` is reserved for the MCP server Python package.
- Per-IDE bundlers live under `bundlers/<ide>/` and produce the IDE's native plugin format. v2 ships `bundlers/cursor/` and `bundlers/claude-code/`.
- Per-IDE installers live under `installers/<ide>/` and install via the IDE's native plugin mechanism (NOT symlinks).
- Each bundle MAY include a subset of source artifacts; per-IDE inclusion/exclusion is the bundler's responsibility, not the source's.
- Bundle versioning ties to the optimus-v2 VERSION; mismatched versions surface as installer warnings, not silent overlays.

Detailed bundle manifests live in `docs/decomp/M4-cursor-bundle.md` and `docs/decomp/M5-claude-code-bundle.md`.

### TR-18: Container Lifecycle + Concurrency

Per CHARTER Decision 7, v2 operates as a host-singleton container with a user-configured parent-mount.

Requirements:
- The MCP server MUST support multi-client transport. **The canonical transport mechanism (Unix socket / named pipe / TCP-loopback), discovery socket path, `.mcp.json` schema, and liveness-probe protocol are pinned in `docs/decisions/transport-and-discovery.md`.** Spike-2 validates against that decision record; it does not invent transport.
- Concurrent requests with a configurable concurrency cap. Overflow returns a structured "busy, retry" MCP error. **Worker-pool strategy** (how CPU-bound rerank work is parallelized given Python's GIL) MUST be named at M1.0 Architecture Spike. Concurrency cap default is set from spike-2 evidence with at least 4 concurrent clients probed.
- Discovery + lifecycle per the transport-and-discovery decision record (existing-container detection, liveness probe to distinguish live from stale, cleanup on container restart).
- Single user-configured parent directory bind-mount. Path recorded in `~/.optimus/config.json`. Surfaced to the user at install time. Hot-swap is NOT required.
- **MCP protocol version handshake:** at connection accept time, the server validates the connecting client's MCP protocol version against its supported range. Mismatch surfaces a clear MCP error before tool calls are accepted (companion to TR-19 bundle/container check).
- Fallback to multi-mount mode (per CHARTER Decision 7) is a config + launcher mode change. **Honest framing:** because the multi-client transport is built for the singleton case, fallback requires the transport layer to operate via a runtime config flag -- not literally zero code, but minimized.

### TR-19: IDE Plugin Format Versioning

Per CHARTER Decision 8, per-IDE bundles MUST pin a minimum supported IDE version at build time. v2 does NOT ship plugin format negotiation.

Requirements:
- Each bundle manifest declares `minimum_ide_version`, `bundle_format_version`, `optimus_version`.
- Installer verifies the detected IDE meets `minimum_ide_version`. Failure surfaces a clear actionable message.
- **Bundle-container compatibility check.** Bundle's `optimus_version` MUST match the running container's `optimus_version` (read from `~/.optimus/VERSION`). Mismatch fails with an actionable message (update container, or downgrade bundle).
- Host-side installer exposes `optimus update-bundles` to re-download + re-install all registered per-IDE bundles. Does NOT touch container state, model cache, or config.
- **MCP protocol version compatibility:** the MCP protocol version the server implements is pinned in `~/.optimus/VERSION` (`mcp_protocol_version` key). TR-18 specifies the per-connection handshake that consumes this value.
- File format for `~/.optimus/VERSION`: INI-style `key=value`, one line per required value. Required keys: `optimus_version`, `mcp_protocol_version`. Both MUST be present.

### TR-20: CLI Entry Point + Conventions

The `optimus` CLI is the user-facing command surface for v2. MCP tools (`optimus_init`, `optimus_doctor`, `optimus_list`, `optimus_delete`) and host-side operations (`optimus update-bundles`, `optimus chat-report`) are invokable both as MCP tools (agent-facing) and as CLI commands (developer-facing).

**Scope of this TR:** define the CLI surface enough to prevent incompatible implementations across milestones. Do NOT pin specific subcommand argument signatures here -- those evolve per-milestone.

Requirements:
- `optimus` MUST be a single host-side command available on PATH after the host-side install. **The minimum shim (dispatching at least `optimus chat-report`) installs at M0** (per `docs/decomp/M0-cli-shim.md`) so the command is invokable from Phase 1.5 onward. Full subcommand registry expands at M4.1.3b.
- CLI dispatches by subcommand using **hyphen-separated form**: `optimus update-bundles`, NOT `optimus update_bundles`. The underscore form refers to MCP tool registration names only.
- Subcommands fall into two classes:
  - **MCP-tool-mirror subcommands** (`optimus init`, `optimus doctor`, `optimus list`, `optimus delete`): thin client for MCP server; logic lives in the server.
  - **Host-side-only subcommands** (`optimus update-bundles`, `optimus chat-report`): operate on host-side state; do NOT require the container.
- `optimus --version` reports both optimus version and MCP protocol version from `~/.optimus/VERSION`.
- `optimus --help` lists available subcommands.
- Specific argument signatures are defined per-milestone as underlying tools land.

---

## Constraints

- Docker is required on the host machine (minimum 6 GB available; 8 GB recommended).
- **Node.js 18 LTS (or newer)** required for hook scripts. (Earlier drafts targeted Node 14; Node 14 reached EOL in April 2023 and lacks stable ESM support. v2 baseline is Node 18.)
- Python 3.10+ inside the Docker image.
- No elevated privileges required for install.
- No external API calls at runtime (enforced architecturally per TR-06).
- No embeddings / vector database (see glossary "index-free").
- No memory feature (use v1 if Cursor memory functionality is required).
- All body-bearing CLI invocations (installer + agents) MUST use file-based body passing.
- **Parent-mount prerequisite (v2):** All projects intending to use Optimus must live under a single user-configured parent directory (TR-18).
- **IDE scope (v2):** Cursor and Claude Code only.
