# Optimus v2 -- Glossary

Background terms referenced across CHARTER.md, REQUIREMENTS.md, and the roadmap. Read this if you're new to the project.

This doc is living. When a new reader hits a term that needs an entry, add it here rather than expanding the founding docs.

## Shorthand legend

- **`TR-XX`** -- Technical Requirement (defined in `docs/requirements/REQUIREMENTS.md`).
- **`EUR-XX`** -- End-User Requirement (same doc).
- **`FD<N>`** -- CHARTER Founding Decision N (defined in `CHARTER.md`).

---

## garp

`garp` is a CLI proximity search tool (Go binary) used by Optimus for code search. Given a project root and a list of terms, it returns files where all terms co-appear within a configurable distance window (i.e. the terms are "close" to each other in the file, not just present somewhere).

Key facts for implementation:

- **Source/repo:** `garp` is an external project in a public Github repo located here: `https://github.com/dtwaling/garp.git`. This is a fork of the original and it is the working source for v2 -- it includes Dustin's added functionality (`--startdir`, `--json`, `--pathscope`) that v2 depends on.
- **In-repo source location:** vendored at `tools/garp/` as a git submodule pinned to a specific commit SHA (per CHARTER Founding Decision 9 -- External Tool Vendoring & Distribution). Bumping the SHA is a deliberate PR with rationale.
- **Deployment artifact:** the Linux binary is pre-built from the submodule SHA and committed at `container/vendor/garp-json`, with a companion `container/vendor/garp-json.manifest.json` recording `source_sha`, `submodule_path`, `built_at`, and `build_env` for traceability. The Dockerfile COPYs the pre-built binary -- **no `git clone`, no `go build` inside the image build**. CI verifies the submodule SHA matches the manifest's `source_sha` field. See TR-10.
- **Minimum version:** v0.7. Adds three flags that v2 relies on:
  - `--startdir <path>` -- required; the project root to scope the search to. v2's `optimus_grep` always passes this so the container (which mounts a parent dir per Decision 7) knows which project to search.
  - `--json` -- machine-readable output for MCP. `optimus_grep` always passes this; agents do not.
  - `--pathscope <glob,glob,...>` -- optional sub-tree filter inside the project. Lets agents narrow to e.g. `web-app/*tests/*,api/*tests/*` for monorepo queries.
- **Why proximity vs grep/ripgrep:** garp finds *contextually related* matches (multiple terms in proximity). ripgrep finds *literal* matches. Optimus uses both for different purposes: garp powers `optimus_grep`'s multi-term proximity surface; ripgrep-style search lives inside `optimus_search` for single-term retrieval.
- **Implementation in optimus:** `src/optimus/garp_shell.py` is a thin subprocess wrapper around the garp binary. The binary lives inside the Docker image at `/usr/local/bin/garp-json` (baked in at image-build time from `container/vendor/garp-json`).

---

## host (machine) vs host project

CHARTER and the rest of the docs use "host" in two distinct senses; they are NOT interchangeable:

- **host (machine)** -- the developer's local machine running the singleton Docker container. Where `~/.optimus/` lives, where the parent-mount is configured, where per-IDE bundles install. Synonymous with "the developer's laptop / workstation."
- **host project** -- a project on the host machine that Optimus operates on. Receives `optimus_init` scaffolding (ARCHITECTURE.md, DIRECTORY_INDEX.md, CODING_STANDARDS_INDEX.md, AGENTS.md), has its own `DIRECTORY_INDEX.md` consulted by agents, and lives under the user-configured parent-mount (per FD7).

When a sentence says "host" alone, it means the machine. When it says "host project" (or "the project"), it means a project Optimus is scaffolding or searching against.

---

## optimus CLI shim

The `optimus` CLI shim is a host-side Go binary placed on the user's PATH by the host-side installer. It is the user-facing entry point for both MCP-tool-mirror subcommands (`optimus init`, `optimus doctor`, `optimus list`, `optimus delete`) and host-side-only subcommands (`optimus chat-report`, `optimus update-bundles`, container lifecycle).

Key facts:

- **First-party, not vendored.** Source lives at `cli-shim/src/` (Go) -- a first-party path, NOT under `tools/` (which is reserved for SHA-pinned external-tool submodules per CHARTER Founding Decision 9).
- **Pre-built binaries:** `cli-shim/bin/<os-arch>/optimus[.exe]` for `linux-amd64`, `linux-arm64`, `darwin-amd64`, `darwin-arm64`, `windows-amd64` -- each with a companion `optimus.manifest.json` recording `source_sha`, `go_version`, `built_at`, `build_env`. Same binary-distribution discipline as FD9 mandates for external tools; CI verifies `source_sha` matches the optimus-v2 commit SHA at build time.
- **End-user never compiles.** The installer selects the binary for the user's OS-arch and places it on PATH; no Go toolchain required.
- **Dispatches subcommands** -- some land in M0 (`doctor`), some in M1.5 (`chat-report`), some in later milestones; full subcommand surface in TR-20 and `docs/decomp/M0-cli-shim.md`.
- **Full record:** `docs/decomp/M0-cli-shim.md` (language locked Go; layout locked `cli-shim/src/` + `cli-shim/bin/<os-arch>/`; five OS-arch targets).

---

## MCP (Model Context Protocol)

MCP is the protocol AI coding agents use to call external tools. Spec: <https://modelcontextprotocol.io>.

Practical mental model for Optimus:

- **The Optimus server is an MCP server.** It exposes tools (`optimus_search`, `optimus_grep`, `optimus_init`, `optimus_doctor`, etc.) that an IDE-hosted agent (Cursor, Claude Code) can call.
- **Transport:** stdio is the most common MCP transport. v1 used stdio per-IDE-instance. v2 needs **multi-client transport** (TR-18) because one container serves multiple IDEs and multiple agents concurrently. The canonical transport mechanism, discovery socket path, and `.mcp.json` schema are pinned in `docs/decisions/transport-and-discovery.md` -- consulted by both bundlers and the spike-2 probe.
- **Tool contract:** each MCP tool has an input schema, an output schema, and a documented behavior. TR-12 mandates these are machine-checkable (JSON Schema) and CI-validated.
- **Where the spec lives:** transport details, tool-call message shape, capability negotiation, and error responses are all defined in the MCP spec. v2 implements the spec; it does not invent its own protocol.

---

## index-free

A characterization of v2's retrieval surface: **no pre-built persistent search index**. Retrieval happens on-the-fly via lexical search (garp / ripgrep) optionally followed by cross-encoder reranking. There is no Elasticsearch, no vector store, no embedding database, no on-disk inverted index that needs to be built, refreshed, or invalidated.

This does NOT mean "pure file-scan grep" -- v2 still runs a neural reranker on lexical hits. The term scopes the *infrastructure*, not the *intelligence*. Specifically:

- **No index lifecycle to manage:** no "rebuild the index when files change," no stale-index failure mode, no chunking decisions, no embedding-model-version-skew across re-indexing runs.
- **First-run cost = subsequent-run cost:** every query is computed fresh; nothing is cached server-side beyond the loaded ML model weights themselves.
- **Trade-off:** retrieval latency is higher per-query than an indexed system, but the operational surface is dramatically smaller (and there's no "the index is wrong" failure mode).

---

## Reranking model stack (locked: Nomic + ColBERTv2)

A **reranker** scores retrieval candidates against the query to produce a precision-ordered top-N. v2's reranker stack is locked in `docs/decisions/secure-singleton-mcp-baseline.md`:

Optimus retrieval pipeline (locked):

1. **First-stage dense retrieval** -- **Nomic CodeRankEmbed** (code-specific embeddings, `trust_remote_code=True` under the installer-gatekeeper trust model) embeds the query and all candidate chunks; cosine similarity + `torch.topk` filters to the top 100 dense candidates.
2. **Late-interaction reranking** -- **ColBERTv2 via RAGatouille** scores the dense candidates with token-level late-interaction. Faster than a traditional cross-encoder while delivering near-SOTA precision inside the 8 GB container envelope (TR-04).
3. Return top-5 to the agent (context-clamped).

**Historical note on dual-CE vs single-CE:** earlier drafts framed this as a pending M1.0 spike decision (v1 used dual cross-encoders -- one for code, one for prose). That framing is retired. The Nomic + ColBERTv2 stack supersedes the dual-CE question entirely; the late-interaction architecture is the v2 answer rather than picking between two traditional CEs. M1.0 Architecture Spike retains revision authority over the locked stack ONLY if a hard, evidence-backed roadblock surfaces during implementation.

---

## spaCy pipeline (v2 role)

spaCy is a Python NLP library. v1 used it for tokenization, entity extraction, and dependency parsing -- primarily in service of the memory feature (extracting structured info from session text).

**v2 has no memory feature** (Decision 3), so the obvious v1 consumer is gone. The model stack itself (Nomic CodeRankEmbed + ColBERTv2 via RAGatouille) is locked in `docs/decisions/secure-singleton-mcp-baseline.md`; that record is silent on spaCy. The spaCy retain/drop call therefore remains gated on **Pre-M1 spike-1 hypothesis H4** (per CHARTER Decision 5 and `docs/decomp/pre-M1-spikes.md`), narrowly scoped to whether spaCy adds value as a preprocessing layer **ahead of** the locked Nomic + ColBERTv2 pipeline (not as a substitute for it). Provisional candidates:

- Query preprocessing for `optimus_search` (lemmatization, stop-word filtering) feeding into Nomic.
- Tokenization for proximity-distance calculations in retrieval.
- Possibly nothing -- if H4 holds (no material Recall@10 / nDCG@10 improvement on the spike-1 task corpus with spaCy on vs off), the dependency is dropped.

**Gating evidence (H4):** spike-1 runs identical retrieval inputs with spaCy-on vs spaCy-off and compares Recall@10 / nDCG@10 directly. H4-holds drops spaCy; H4-fails keeps spaCy and its scope is documented in the Phase 1.0 Architecture Spike output. This is the only retrieval-side spike question still open; the rest of the pipeline is locked.

---

## Cursor AI plugins (vs VS Code extensions)

Cursor exposes two distinct surfaces for third-party tooling, and they are NOT interchangeable:

| Surface | What it is | Manifest | Install path | Agent integration |
|---------|-----------|----------|--------------|-------------------|
| **VS Code extension** | Inherited from VS Code; standard `.vsix` packaging | `package.json` w/ `contributes` | `~/.cursor/extensions/` | Generic IDE features (commands, language servers, themes) |
| **Cursor AI plugin** | Cursor's own plugin format, purpose-built for agentic tooling | Cursor-specific manifest | Cursor-managed AI plugin location | First-class agent integration (tools, rules, hooks, agent definitions) |

**v2 targets Cursor AI plugins, NOT VS Code extensions.** The agent-facing tooling surface (MCP tool registration, agent rules, hooks) lives in Cursor's AI plugin space. Trying to ship optimus as a VS Code extension would force every agent-feature into the wrong abstraction layer.

This is the single most common terminology confusion in Cursor integration work. When you read "Cursor extension" in any v2 doc, that's either a stale reference (file an issue) or a deliberate contrast with the AI plugin surface.

---

## IDE hooks (lifecycle events)

Hooks are scripts that fire on specific IDE lifecycle events. Both Cursor and Claude Code expose hook interfaces; the exact event vocabulary differs per IDE.

The four hooks v2 ports from v1 (with memory hooks killed per Decision 3):

| Hook | Purpose |
|------|---------|
| `search-redirect` | Intercept built-in search calls and route to `optimus_search` when appropriate |
| `shell-guard` | Pre-flight shell commands the agent wants to run; block dangerous patterns |
| `read-guard` | Intercept agent file reads; redirect from broad sweeps to targeted reads via DIRECTORY_INDEX.md |
| `agent-scratch` | Manage scratch-space lifecycle (create on session start, sweep on session end) |

**Source format vs bundle format:** v2 authors hooks in `src/hooks/` (sibling of `src/optimus/`, NOT inside it) as IDE-agnostic Node.js ESM. The per-IDE bundlers (`bundlers/cursor/`, `bundlers/claude-code/`) transform these into each IDE's expected hook format (Cursor `.mjs` in `hooks/`, Claude Code `settings.json` declarations, etc.) at bundle time.

**IDE-agnostic source means:** hook source code contains no IDE-specific conditionals. Per-IDE event-name mapping and format transformation happen exclusively in the bundler (per TR-17), NOT in the hook source.

**Lifecycle event mapping:** each bundler maps IDE-specific events to the IDE-agnostic surface the hooks consume. If Cursor exposes a `pre-tool-call` event that Claude Code does not, the Cursor bundle wires it; the Claude Code bundle omits that hook (or maps to the closest equivalent).

---

## Claude Code chat-history store

Claude Code's local persistent storage of chat sessions -- analogous to Cursor's `state.vscdb` + `ai-code-tracking.db` pair. Used by the chat-report tooling to extract tool-call trajectories for telemetry analysis.

**Schema is TBD via the chat-report sibling project.** See `docs/decisions/chat-report-sibling-charter.md`. Reverse-engineering this schema (file path on each OS, storage format, tool-call attribution model) is the highest-variance work in the pre-kickoff sibling project; it may scope as anywhere from "small" to "multi-session research effort." Phase 1.5 (M1) integrates whatever the sibling project produces; it does not re-research.

---

## DIRECTORY_INDEX.md

A project-root markdown file that lists the project's directory tree with a one-line purpose per directory. Agents consult it to scope searches and reads instead of calling recursive `ls` / `glob`.

- **Created by:** `optimus_init` (EUR-12, ships M2). Seeded from a `.gitignore`-aware tree walk.
- **Maintained by:** the project's developers and agents working in the project.
- **Drift detection:** `optimus_doctor` (EUR-13, ships M2) compares the file to the actual tree; emits a unified-diff patch on drift.

**Why this matters:** the v2 thesis is that an accurate dir-index does more for agent token cost than any retrieval tool. Agents stop sweeping directories; they do *informed precision reads*. The Pre-M1 spike-1 validates this empirically.

---

## "Informed precision read"

A read where the agent consulted DIRECTORY_INDEX.md (or equivalent project map) to identify the target file *before* opening it -- as opposed to a "sweep read" where the agent opens many files to find what it needs.

The chat-report parser classifies these heuristically by looking at tool-call trajectory in the IDE's chat history: a read with a preceding DIRECTORY_INDEX.md consult within the same agent turn counts as informed; otherwise sweep.

**The heuristic has documented failure modes** -- see `docs/telemetry-heuristic.md` for the full list. Headline cases: dir-index in system prompt (all reads misclassified as uninformed), dir-index read then sweep (sweep misclassified as informed), cross-IDE granularity differences (Cursor and Claude Code chat logs are not directly comparable without normalization). The heuristic is approximate-and-biased, not pristine; treat the resulting metric accordingly.

EUR-10 in v2 is a build-time validation aid rather than a runtime telemetry feature -- it ships as the `optimus chat-report` CLI subcommand, not as a server-side counter. The pass/fail threshold + baseline condition for the success metric (which consumes this classification) are pinned in `docs/decisions/success-metric.md`.

---

## Retrieval evaluation metrics (Recall@K, MRR, nDCG@K)

Used in the M1 DoD's "Retrieval quality bar." Definitions:

- **Recall@K:** of all documents that ARE relevant to a query, what fraction did the system surface in its top-K results? Range 0-1. RAG-pipeline floor is typically 0.85+ at K=10 -- below that, the agent misses too much context. The M1 bar is `Recall@10 >= 0.85`.

- **MRR (Mean Reciprocal Rank):** how quickly does the system surface the *first* relevant result, averaged across all queries? If the first relevant result is at position 1, RR=1.0; position 2 = 0.5; position 5 = 0.2. Best fit for navigational / "find the thing" queries -- the agent's typical pattern. The M1 bar is `MRR >= 0.60` (the first relevant result lands in roughly the top 2 positions on average).

- **nDCG@K (Normalized Discounted Cumulative Gain):** the gold-standard ranking metric. Accounts for both position (higher results count more) and graded relevance (some results are more relevant than others, not just relevant/irrelevant). Range 0-1, where 1.0 is the ideal ranking. The M1 bar has two parts: (a) an **absolute floor** of `nDCG@10 >= 0.65` (calibrated against CoIR leaderboard entries; prevents the regression-only gate from protecting a mediocre baseline), and (b) a **regression alert** -- `nDCG@10` captured at M1.4 completion as a baseline; CI fails on subsequent commits if it drops more than 5%.

**Sample size:** 50+ queries (directional confidence per standard search-eval guidance; 200+ would give statistical significance but is overkill for M1 DoD).

**Methodology rules** are pinned in `docs/decisions/eval-corpus-methodology.md` -- target codebase selection, query authorship discipline, labeling methodology, 80/20 held-out test set (held-out is the authoritative DoD gate), and corpus versioning policy (any corpus change requires baseline recapture).

**Reference benchmark:** **CoIR (Code Information Retrieval)** -- the published academic benchmark for code retrieval. v2's test corpus structure aims for CoIR-compatibility so we can later score against the leaderboard for sanity, but v2 does NOT need to top CoIR at M1 DoD. The bars above are RAG-production floors, not SOTA targets.

---

## chat-report.py (telemetry approach)

v2's primary instrument for validating the success metric ("`optimus_*` calls plus informed precision reads outnumber broad-sweep Read/Grep/Glob calls"). It's a post-session report generator that reads IDE-native chat-history stores and emits markdown + JSON reports of tool-call trajectories, attribution, errors, and guard/denial events.

Key facts for implementation:

- **Source/repo:** the chat-report toolkit is a sibling project in a public Github repo: `https://github.com/dtwaling/ai-chat-report.git`. Dual-variant layout upstream: `cursor/` (salvage from v1 optimus already complete) and `claudecode/` (empty scaffolding; reverse-engineering work owned by the delegated session per the sibling charter).
- **In-repo source location:** vendored at `tools/ai-chat-report/` as a git submodule pinned to a specific commit SHA (per CHARTER Founding Decision 9 -- External Tool Vendoring & Distribution). Interpreted Python tool: no compile step, no binary artifact, no manifest -- the installer references the submodule path directly.
- **Full charter:** `docs/decisions/chat-report-sibling-charter.md` (upstream state, access, dual-IDE DoD, feasibility gates).

**Why this approach instead of MCP-server-side telemetry:** the MCP server only sees calls made TO it. IDE-builtin Read/Grep/Glob go through the IDE's own tool stack and never cross the MCP boundary. Counting them requires reading where they ARE logged -- inside the IDE's chat-history store.

**v1 source (Cursor only):** `ref-projects/optimus/tools/chat-report.py` reads Cursor's `state.vscdb` (chat bubbles via `cursorDiskKV.composerData:<chatId>` and `cursorDiskKV.bubbleId:<chatId>:<bubbleId>`) and `ai-code-tracking.db` (per-conversation file attribution).

**v2 plan:**
- **Pre-kickoff (sibling project, BEFORE Optimus v2 roadmap starts):** salvage v1's Cursor script into a standalone, maintained chat-report toolkit. Add a Claude Code variant by reverse-engineering Claude Code's chat-history store schema. Charter + DoD + fallback in `docs/decisions/chat-report-sibling-charter.md`.
- **In-repo vendoring (M0):** once the sibling project is established, it is vendored into v2 at `tools/ai-chat-report/` as a SHA-pinned git submodule per CHARTER Founding Decision 9. Python source runs in place host-side; no compile step, no binary artifact, no manifest.
- **Phase 1.5 (M1):** integrate the pre-existing chat-report tools into the `optimus` CLI as `optimus chat-report <id>` -- auto-detect Cursor vs Claude Code via available stores, adapt output paths to `~/.optimus/chat-reports/`, cross-platform-ify per TR-09. CLI shim installed at M0 (per `docs/decomp/M0-cli-shim.md`) so the command is invokable from M1.5 onward, not deferred to M4.
- **Phase 6.1.1 (M6):** informed-precision-read heuristic on top of both variants -- see `docs/telemetry-heuristic.md` for failure modes the implementation must handle.
- **Phase 6.1.2 (M6):** aggregate + weekly summary rolling up across IDEs.

**Spike-1 implication:** chat-report capability is the prerequisite for spike-1 telemetry. If the Claude Code variant slips, spike-1 falls back to Cursor-only (per the sibling charter).

---

## Parent-mount (Decision 7)

The user-configured host directory that the singleton Optimus container bind-mounts. All projects intended to use Optimus must live somewhere under this directory.

- **Recorded in:** `~/.optimus/config.json` at install time.
- **User must know:** the installer surfaces this as an explicit prerequisite. Changing the parent is a config edit + container restart.
- **Fallback:** if a user can't fit projects under one parent, v2.1 multi-mount mode is the supported alternative (Decision 7 fallback).

---

## v1 vs v2 (project history shorthand)

- **v1:** the original Optimus MCP server. Archived at `ref-projects/optimus/`. Supported product for Cursor-only memory users. Memory works there; v2 deliberately drops it.
- **v2:** clean-repo restart. This project. Retrieval + standards layer + safe filesystem ops; no memory. Cursor + Claude Code only.
- **The salvage relationship:** v2 lifts garp, the cross-encoder reranker, and spaCy from v1 as components but does NOT inherit v1's architecture, module list, or conventions. Don't read v1 as ground truth -- it's a parts shop, not a reference implementation. File-by-file salvage inventory in `docs/decomp/v1-salvage-inventory.md`.
