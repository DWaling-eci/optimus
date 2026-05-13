# Optimus v2 -- AGENTS.md

## Project Identity

Optimus v2 is a clean-repo restart of the Optimus MCP server. The v1 codebase
(ref-projects/optimus/) is preserved as archive/reference -- use it as salvage
source, not as ground truth for architecture or conventions.

**Naming:** `optimus-v2` is the **codename** used in dev docs and dev-side
working-directory framing; `optimus` is the **GitHub repo** name
(`DWaling-eci/optimus`), the container image (`ghcr.io/DWaling-eci/optimus`),
the binary on PATH, and the end-user-facing product name. Post-clone the
working directory is `optimus/`. Full naming-convention block lives in
CHARTER.md ("Naming Conventions" section).

## Purpose

Deterministic, no-pre-built-index MCP server (see glossary -- "index-free") that gives AI coding
agents knowledge retrieval, code search, and a standards-enforcement layer
(project scaffolding + drift detection). v2 ships zero memory functionality
(see CHARTER Decision 3).

Deployed as a host-singleton Docker container (CHARTER Decision 7) with
per-IDE plugin bundles for **Cursor and Claude Code only** at v2 GA
(CHARTER Decision 6). Codex, Hermes, and other MCP-capable harnesses are out
of scope for v2 **as deployment targets**.

## Directory Layout

```
optimus/
  AGENTS.md           -- this file
  CHARTER.md          -- founding decisions and product thesis (read second)
  docs/
    plans/            -- implementation plan files
    decomp/           -- per-milestone task decomposition (just-in-time)
    decisions/        -- canonical decision records (transport+discovery,
                       success metric, eval corpus, chat-report sibling)
    issues/           -- issue body drafts (body-files/ pattern)
    requirements/     -- technical and end-user requirements
  body-files/         -- untracked; CLI --body-file inputs
  src/                -- skeleton dirs exist from M0 day 1 (per
                       docs/decomp/M0-repo-layout.md); source files
                       within each subdir are populated per-milestone
                       as code comes online
  bundlers/           -- per-IDE bundle builders (skeleton from M0; populated M4 onward)
  installers/         -- per-IDE installers (skeleton from M0; populated M4 onward)
  cli-shim/           -- first-party `optimus` CLI shim (Go);
                       cli-shim/src/ holds Go source,
                       cli-shim/bin/<os-arch>/ holds pre-built per-OS-arch
                       binaries with companion optimus.manifest.json each;
                       see CHARTER Founding Decision 9 and
                       docs/decomp/M0-cli-shim.md
  container/          -- host-side container bootstrap (skeleton from M0; populated M1)
    vendor/           -- pre-built binaries baked into the Docker image
                       (e.g., garp-json + garp-json.manifest.json);
                       see CHARTER Founding Decision 9
  templates/          -- standards templates (skeleton from M0; populated M2)
  tests/              -- skeleton from M0; populated per-milestone alongside src/
  tools/              -- external-tool git submodules, SHA-pinned (e.g., tools/garp/,
                       tools/ai-chat-report/); see CHARTER Founding Decision 9
```

## Current State

1. **Phase:** pre-init. Founding docs only; no code committed.
2. **Next gate:** **chat-report toolkit (Cursor + Claude Code variants)** as a
  standalone sibling project. Must exist before Optimus v2 kicks off; charter
  + DoD live in `docs/decisions/chat-report-sibling-charter.md`.
3. **Then:** Pre-M1 Validation Spikes (spike-1 retrieval behavior + spike-2
  singleton container). See `docs/plans/TDD-ROADMAP.md`.
4. **Spike status:** not yet started - *Outputs land at*
  `docs/spikes/spike-1-retrieval-report.md` (spike-1) and
  `docs/spikes/spike-2-singleton-report.md` (spike-2).
5. **Read order:**
	  1. AGENTS.md (this file -- step 0, you are here)
	  2. CHARTER.md
	  3. docs/requirements/REQUIREMENTS.md
	  4. docs/plans/TDD-ROADMAP.md
	  5. docs/glossary.md (load anytime you hit an unfamiliar term)

## Milestone-Boundary Posture

At each milestone boundary (M1->M2, M2->M3, etc.), a human PM or designated principal-agent expands the next milestone's task body with concrete tasks before any agent loop picks it up. M0's task body in `docs/decomp/M0-tasks.md` is the kickoff exemplar (fully populated); M1-M6 task bodies are intentionally skeleton placeholders that get filled at milestone-load time. Autonomous agent loops MUST halt at the boundary and wait for fill-in rather than guessing tasks from milestone DoD alone. This is the load-bearing checkpoint that keeps just-in-time decomposition honest -- skip it and the skeleton placeholders silently become the plan.

**Machine-checkable HALT marker (load-bearing).** Each `docs/decomp/M<n>-tasks.md` file carries a YAML frontmatter block at the top:

```yaml
---
expansion-status: skeleton    # or: filled
filled-by: null               # or: <handle> when filled
filled-at: null               # or: <ISO 8601 timestamp> when filled
---
```

Autonomous agent loops MUST parse this frontmatter before consuming the milestone body. **If `expansion-status: skeleton`, the loop MUST halt and surface "milestone awaiting expansion" to the human; it MUST NOT proceed to decomposition or task execution.** Only when a human PM or principal-agent flips the status to `filled` (and records `filled-by` + `filled-at`) may the loop proceed. M0 is `filled` (founding-pass exemplar); M1-M6 are `skeleton` until milestone-load time. The prose-only posture above is reinforced by this structural marker -- agents that paper over the prose still trip the YAML check.

## Delegated Session Escalation Policy

Every delegated future session (chat-report sibling, eval-corpus query authoring, eval-corpus relevance labeling, future scoped-build engagements) inherits this policy. The policy captures both "this is taking too long" and "this isn't what we thought it was."

**Sizing estimate.** Each delegated effort gets a **sizing estimate** recorded in its decision record (rough granularity is fine -- e.g., "small," "medium," or "N sessions"). The estimate is the baseline the escalation triggers measure against.

**Trigger 1 -- session-count overrun.** If actual session count exceeds **2x the sizing estimate**, the delegated owner escalates back to Dustin for re-scope. Trying to push through past 2x silently is the failure mode this rule prevents.

**Trigger 2 -- discovery-driven scope change.** Independent of sizing, any discovery result that would change project scope triggers escalation regardless of session count. Examples:

- A variant proven infeasible (e.g., Claude Code chat-history store lacks required tool-call attribution).
- A hard roadblock surfaced (e.g., plugin format is undocumented AND reverse-engineering is infeasible).
- A finding that invalidates an assumption load-bearing for a downstream milestone.

**Escalation shape.** "Escalate to Dustin" means: stop forward work on the affected scope, write up the finding + the recommended re-scope options, and surface it for a re-scope discussion. The delegated session does NOT silently switch to a degraded fallback. Project-pause + re-scope is the only sanctioned outcome at the gate.

**Consumers (cross-reference):**

- `docs/decisions/chat-report-sibling-charter.md` -- chat-report's Claude Code feasibility gate (both chat-history store and plugin format research) is an instance of this policy.
- `docs/decisions/eval-corpus-methodology.md` -- query authoring and relevance labeling delegated sessions inherit this policy.

## Loop-level Failure Recovery

When an agent executing a milestone task fails a DoD check -- test failure, gate failure, uncaught exception, or any other condition the task contract names as a fail-stop:

1. **Single retry.** Re-attempt the failing task ONCE. This absorbs flaky failures (LLM stochasticity, transient network, race conditions) without burning human cycles.
2. **Halt + auto-issue on second failure.** If the retry also fails, halt the loop immediately. File an issue body at `docs/issues/<task-slug>-failure-<YYYY-MM-DD>.md` capturing:
   - Which DoD check failed (test name, gate condition, exception class)
   - Last ~50 lines of relevant logs / output
   - Task identifier, commit SHA at retry point, retry count
   - WIP location (branch name, uncommitted-file list)
3. **Escalate to human review.** Human picks the recovery path: retry-with-fix, manual takeover, or re-scope (which may also trigger the Delegated Session Escalation Policy above if the failure indicates scope change rather than implementation slip).

No silent third retry. No automatic recovery beyond the single flake-absorbing retry. The contract is "one retry handles flakes; everything else is human territory."

**Consumers (cross-reference):**

- `docs/conventions/git-and-issues.md` -- issue body templates and label set (use `bug` + `blocked` + relevant `milestone:M<n>` for failure issues).

## Conventions

- No em-dashes; use `--` (double-hyphen)
- ASCII-only symbols in all content
- `body-files/` is gitignored -- for gh/git CLI body inputs only
- **Commits, PRs, and issues.** Conventional-commits prefixes (`chore:`, `feat:`,
  `docs:`, `ci:`, `fix:`, `refactor:`, `test:`); PR bodies via `--body-file` with
  "What changed / Why / Test plan / Risk" sections; issue bodies drafted at
  `docs/issues/<slug>.md` and filed via `gh issue create --body-file`. Full spec
  + initial label set in `docs/conventions/git-and-issues.md`.
- **External-tool vendoring.** Every external-tool dependency (garp, chat-report,
  future tools) lives at `tools/<external-tool>/` as a git submodule pinned to a
  specific commit SHA. Pre-built binaries for compiled tools ship at the relevant
  deployment-source path (e.g., `container/vendor/garp-json` for container-side
  tools), each with a companion `*.manifest.json` recording the source SHA.
  End-user install never requires git, Go, or any build toolchain. Full rationale
  and CI workflow in CHARTER Founding Decision 9.
