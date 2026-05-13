# Decision Record: chat-report Sibling Project Charter

**Status:** Decided -- locked. Hard prerequisite for spike-1 kickoff.
**Owner:** Delegated future session. A scoped Claude Code session (or future principal-agent engagement) builds the toolkit. Dustin remains PM and reviews at milestone boundaries.

## Why this record exists

The roadmap and AGENTS.md both treat the `chat-report` toolkit (Cursor + Claude Code variants) as a **pre-kickoff prerequisite** -- spike-1 telemetry depends on it, Phase 1.5 integrates it, the v2 success metric depends on it.

This is the largest external dependency in the v2 plan. It blocks spike-1, which blocks M1, which blocks everything downstream. This record makes the dependency concrete: owner, location, gating rule, and the hard dual-IDE bar.

## What the chat-report toolkit must do

Take a chat session ID (Cursor chat ID or Claude Code session ID), locate the corresponding chat-history store on disk, and emit a structured report (markdown + JSON) covering:

- **Tool-call trajectory** -- what calls fired, in what order.
- **Aggregate counts per tool class** -- broad-sweep Read/Grep/Glob vs `optimus_*` vs DIRECTORY_INDEX.md reads.
- **Informed-precision-read heuristic classification** per Read call.

Both IDE variants emit the **same** structured report shape so downstream consumers (spike-1 telemetry, success-metric evaluation, M1.5 integration) treat them interchangeably.

## Locked design calls

### 1. Owner

**Delegated future session.** Not Dustin personally. A separately scoped Claude Code session (or future principal-agent engagement) executes the build. Dustin remains PM and reviewer at milestone boundaries (Cursor-variant DoD, Claude Code feasibility discovery gate, Claude Code-variant DoD).

### 2. Location on disk

`tools/ai-chat-report/` (relative path, inside the optimus-v2 repo).

Treated as an **external project / dependency**, managed as a git submodule (or equivalent vendored-with-pinned-ref convention). Rationale: `tools/<external-tool>/` is the home for external/sibling tooling dependencies generally. The toolkit has its own lifecycle and version pin; optimus-v2 consumes it at a known ref.

**Upstream repo:** `https://github.com/dtwaling/ai-chat-report.git`. Brought into optimus-v2 as a git submodule at `tools/ai-chat-report/` per CHARTER Founding Decision 9.

**Existing state at upstream (inherited by the delegated session):**

- **Cursor variant -- salvage already complete.** The three files originally from v1 optimus's `ref-projects/optimus/tools/chat-report.py` (and adjacent files) are already salvaged into the upstream repo's `cursor/` directory. The Cursor-variant DoD reduces to "adapt + harden + test against the locked structured-report shape" -- the salvage step itself is done at the upstream level.
- **Claude Code variant -- empty scaffolding.** The upstream has an empty `claudecode/` directory ready for the delegated session's reverse-engineering work (chat-history store schema + plugin format research). This is the actual greenfield work.

**Access:** Dustin is a contributor on `dtwaling/ai-chat-report` (and on `dtwaling/garp`). The delegated session operates under Dustin's GitHub credentials, so submodule pulls and commits work without additional access provisioning.

### 3. Timeline

**Hard gate. No fixed calendar date.**

- Spike-1 cannot start until BOTH variants land.
- The project pauses if this slips. There is no soft deadline and no "default to partial signal" arrangement.
- Progress here is the critical path; everything downstream waits on it.

### 4. Dual-IDE coverage: MANDATORY

**No fallback.** Spike-1 does not start until BOTH the Cursor variant AND the Claude Code variant are complete and emitting the structured report shape.

If the Claude Code variant proves impossible during reverse-engineering, the project pauses pending a re-scope discussion with Dustin. This is a hard "block on dual-IDE" commitment, not a "default to A if slip" arrangement.

The project-pause path is the only safety valve. There is no Cursor-only fallback, no manual-inspection fallback, no degraded-signal compromise. Either dual-IDE coverage exists, or the project halts at this gate for re-scope.

## First-priority discovery tasks: Claude Code internals

Two Claude-Code-internals discovery efforts are **co-located in this delegated session** because both probe the same surface (Claude Code's on-disk artifacts and undocumented format internals). Sharing one delegated owner avoids duplicating reverse-engineering setup and keeps both findings under a single feasibility gate.

### 3a. Chat-history store feasibility (load-bearing for spike-1 + Phase 1.5)

Before significant build effort begins on the Claude Code chat-report variant, the delegated session must answer:

**Does the Claude Code chat-history store support the tool-attribution granularity we need?**

Concretely:
- Where is the chat-history store on disk (per supported OS)?
- What is the schema (SQLite? JSONL? proprietary?)?
- Is tool-call attribution captured per turn, with sufficient granularity to reconstruct the trajectory and classify Read calls under the informed-precision heuristic?

### 3b. Claude Code plugin format research (load-bearing for M5)

The same delegated session also covers Claude Code plugin format research, in support of M5 (Claude Code Bundle + Installer):

- What is the Claude Code plugin format spec source (official docs URL, attribution, or -- if undocumented -- the empirical contract reverse-engineered from existing plugins)?
- Which Claude Code version is the format pinned against (per CHARTER Founding Decision 8 -- minimum-supported-IDE-version model)?
- What plugin install location does Claude Code use, per supported OS?
- What event/hook/tool surfaces does Claude Code expose, and how do they map to the IDE-agnostic `src/{hooks,agents,skills,rules}/` source surface?

M5 (`docs/decomp/M5-tasks.md`, `docs/decomp/M5-claude-code-bundle.md`) consumes the findings from this discovery; M5 does not duplicate the research.

### Unified escalation gate

**Gate:** if EITHER discovery comes back negative -- the chat-history store cannot support the required attribution, OR the plugin format is undocumented AND reverse-engineering proves infeasible -- the delegated session **escalates back to Dustin** for a project-pause / re-scope discussion. This is an instance of the unified delegated-session escalation policy in `AGENTS.md` ("Delegated Session Escalation Policy"): discovery results that would change project scope trigger escalation regardless of sizing. The delegated session does NOT silently switch to a degraded fallback. The unified policy also applies the 2x-sizing-estimate trigger; see AGENTS.md for the full rule.

## Cursor variant -- Definition of Done

- **Source of salvage:** already complete in the upstream repo's `cursor/` directory (3 files originally from v1 optimus's `ref-projects/optimus/tools/chat-report.py` and adjacent). M0 init brings the submodule in at the pinned ref; no fresh salvage pass needed.
- **Effort estimate:** small -- adapt + harden + test against the locked structured-report shape.
- **Parses:** Cursor's `state.vscdb` + `ai-code-tracking.db`.
- **Emits:** the structured report shape defined above (markdown + JSON, tool-call trajectory, aggregate counts, informed-precision-read classification).

## Claude Code variant -- Definition of Done

- **Source of salvage:** none -- zero prior art. The upstream's `claudecode/` directory is scaffolded but empty; schema reverse-engineering required (see feasibility discovery above). This is the greenfield half of the delegated session's work.
- **Parses:** Claude Code's chat-history store, on each supported OS.
- **Emits:** the SAME structured report shape as the Cursor variant (this is the integration contract -- downstream consumers don't branch on IDE).

## Consumers (cross-reference)

- `AGENTS.md` -- references this record as the pre-kickoff gate; owns the unified **Delegated Session Escalation Policy** that the feasibility gate below is an instance of.
- `docs/plans/TDD-ROADMAP.md` -- spike-1 telemetry consumes the output of these tools; M1.5 integrates them for ongoing build-time validation signal.
- `docs/decomp/pre-M1-spikes.md` -- spike-1 DoD depends on chat-report output shape.
- `docs/decisions/success-metric.md` -- depends on this for measurement.
- `docs/decomp/M5-tasks.md` and `docs/decomp/M5-claude-code-bundle.md` -- consume the plugin-format research findings produced by this delegated session (per "First-priority discovery tasks -- 3b").

## Status note

Locked at refactor time. Owner is delegated; location is pinned at `tools/ai-chat-report/`; timeline is a hard gate with project-pause as the only slip outcome; dual-IDE coverage is mandatory. The Claude Code feasibility discovery (chat-history store **AND** plugin format) is the named first-priority task set and the only sanctioned escalation point -- both governed by the unified policy in `AGENTS.md`.
