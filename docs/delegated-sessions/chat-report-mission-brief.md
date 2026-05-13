# Chat-report Sibling -- Delegated Session Mission Brief

**Brief authored:** 2026-05-12
**Authoring authority:** PM (Dustin Waling) via Claude Code session prior to dispatch
**Parent project:** Optimus v2 (`github.com/DWaling-eci/optimus`, default branch `trunk`)
**Delegated workspace:** `C:/_Source/ai-chat-report/` (separate clone of `github.com/dtwaling/ai-chat-report`)
**Working branch:** `claudecode-variant-discovery` (already created off `master`)
**This document path inside optimus:** `docs/delegated-sessions/chat-report-mission-brief.md`
**Convenience copy at clone root:** `C:/_Source/ai-chat-report/MISSION-BRIEF.md` (gitignored locally; do not push)

---

## 0. Read this section first

You are operating as a **delegated future session** under Optimus v2's governance. You are NOT inside the optimus repo's session -- you are working in a sibling clone of the upstream `ai-chat-report` repository. The parent project (optimus) lives at `C:/_Source/optimus/` and you have read access to it for canonical decision records and conventions.

**Your mission has a single sentence:** stand up the chat-report toolkit -- both Cursor and Claude Code variants -- such that Optimus v2's pre-M1 spike-1 can consume their output, with **mandatory dual-IDE coverage** and **project-pause as the only sanctioned slip outcome**.

**Before any tool work, read in this order:**

1. This entire brief.
2. `C:/_Source/optimus/AGENTS.md` -- project identity, conventions, Delegated Session Escalation Policy (section "Delegated Session Escalation Policy"; load-bearing).
3. `C:/_Source/optimus/CHARTER.md` -- founding decisions; especially Decision 9 (External-Tool Vendoring & Distribution) and Decision 6 (IDE coverage).
4. `C:/_Source/optimus/docs/decisions/chat-report-sibling-charter.md` -- **your charter**. This brief operationalizes that charter. Charter beats brief on any contradiction; escalate.
5. `C:/_Source/optimus/docs/decisions/success-metric.md` -- the downstream consumer your output enables measurement of.
6. `C:/_Source/optimus/docs/telemetry-heuristic.md` -- the informed-precision-read heuristic that your output must support (note: this doc carries 3 explicit TODOs deferred to M6.1; you are NOT expected to resolve those, but you must produce output that allows the heuristic to be implemented later).
7. `C:/_Source/optimus/docs/decomp/M5-claude-code-bundle.md` and `C:/_Source/optimus/docs/decomp/M5-tasks.md` -- M5 consumes your plugin-format research findings.
8. `C:/_Source/optimus/docs/decomp/pre-M1-spikes.md` -- spike-1 consumes your structured-report output.
9. `C:/_Source/optimus/docs/glossary.md` -- load anytime you hit an unfamiliar term.

**Brief beats no source.** Charter beats brief. Escalate ambiguity rather than guess.

---

## 1. Authority and Boundaries

### What you can decide unilaterally

- Implementation tactics within either variant (data structures, parsing approach, intermediate file formats, test layout).
- Refactoring of the existing Cursor-variant code (`cursor/chat-report.py`, `cursor/chat-report-verify.py`, `cursor/chat-report-verify.config.template.json`) to harden + match the locked report shape.
- Branch/PR hygiene on `dtwaling/ai-chat-report` for the `claudecode-variant-discovery` branch you are on.
- Reverse-engineering methodology for the Claude Code chat-history store.

### What you must escalate

- Any **feasibility-gate negative** (see section 5).
- Any session-count overrun (see section 5; sizing estimate is in section 2).
- Any change to the locked structured-report shape (see section 4).
- Any change that would re-open a locked decision in `docs/decisions/` (touch nothing in the parent project except `docs/spikes/`, `docs/issues/`, and your own brief revision-history line below).
- A request from the user to push to upstream `master` directly (always go via PR on `claudecode-variant-discovery`).

### What you must never do

- Push to `dtwaling/ai-chat-report:master` directly. Always PR.
- Modify the optimus repo's submodule pin (`tools/ai-chat-report`) -- that bump is the parent project's responsibility once your PR merges upstream.
- Switch to a "Cursor-only fallback" if the Claude Code variant proves hard. There is NO fallback. Escalate per section 5.
- Silently degrade signal quality below what spike-1 consumes (see section 4 for the contract).
- Commit `MISSION-BRIEF.md` (the convenience copy at the clone root) -- it must remain in the clone's local `.gitignore`.

---

## 2. Sizing Estimate and Escalation Triggers

**Sizing estimate (per AGENTS.md "Delegated Session Escalation Policy"):** **medium**, roughly:

- Cursor-variant adapt + harden: **1 session** (the cursor/ code is 80KB+ Python already; mostly verification against the locked shape plus refactor where needed).
- Claude Code feasibility discovery (chat-history store + plugin format): **2-3 sessions**.
- Claude Code variant build: **2-3 sessions** post-feasibility-positive.
- Cross-IDE normalization + integration testing: **1 session**.

**Total baseline: ~6-8 sessions.**

**Trigger 1 (session-count overrun):** if actual session count exceeds **2x** the baseline (i.e., 12+ sessions), STOP and escalate.

**Trigger 2 (discovery-driven scope change):** any of the following triggers immediate escalation regardless of session count:
- Claude Code chat-history store lacks tool-call attribution granularity required for the informed-precision-read heuristic.
- Claude Code plugin format is undocumented AND empirical reverse-engineering proves infeasible.
- Cursor and Claude Code chat-history stores cannot be normalized to a common report shape without losing load-bearing signal.
- Any finding that invalidates an assumption load-bearing for a downstream milestone (especially M1.5 integration and M5 plugin bundle).

**Escalation shape:** stop forward work on the affected scope, write up the finding + recommended re-scope options in `docs/issues/<slug>.md` inside the optimus repo (NOT inside ai-chat-report -- the issue lives in the parent project), surface it for a re-scope discussion. Do NOT silently switch to a degraded fallback. Project-pause + re-scope is the only sanctioned outcome at the feasibility gate.

---

## 3. Two-Part Deliverable

### Part A -- Cursor variant (adapt + harden)

**Starting state.** `cursor/chat-report.py`, `cursor/chat-report-verify.py`, `cursor/chat-report-verify.config.template.json` already exist (salvaged from v1 optimus). Read them first; they already implement most of what's needed and emit a markdown + JSON report shape. The existing reads are:

- `%APPDATA%\Cursor\User\globalStorage\state.vscdb` (Cursor chat history)
- `%USERPROFILE%\.cursor\ai-tracking\ai-code-tracking.db` (Cursor AI tracking)

**Your task on Part A:**

1. Run the existing code against a real Cursor chat session of your own (have the user pick a recent session ID for you to test against; use Cursor's "Copy Request ID" UI gesture). Verify the report emits without errors.
2. Compare the emitted shape against the **Locked Structured-Report Shape** in section 4 below. Identify deltas.
3. Adapt the code so the emitted shape matches section 4 exactly. Add unit tests covering the shape contract.
4. Harden for the failure modes the existing code already comments on (denial markers, multi-OS path resolution, edge cases in bubble parsing).
5. Cross-platform: the cursor variant runs on Windows today. Add macOS + Linux path resolution (Cursor stores chat history at different paths per OS; document what you find).

**Part A Definition of Done:**

- All three CLI modes work: single-chat, `--diff <idA> <idB>`, `--aggregate <id> ...`.
- Emitted output (both markdown and JSON) conforms to section 4's shape, verified by automated test (run a known fixture chat session through the tool, assert JSON shape).
- Tests pass on Windows AND macOS AND Linux (use synthetic SQLite fixtures for the cross-OS test where wiring up Cursor on a non-Windows CI runner is impractical -- document this clearly).
- README in `cursor/README.md` documents: how to invoke, what each mode does, where chat history is stored per OS, what each report section means.
- PR opened against `master` on `dtwaling/ai-chat-report` with a clear changelog.

### Part B -- Claude Code variant (greenfield, schema reverse-engineering)

**Starting state.** `claudecode/.gitkeep` only. Zero prior art.

**Your task on Part B is split into two feasibility-discovery sub-tasks (3a + 3b in the charter) followed by the actual build.**

#### B.1 -- Chat-history store discovery (load-bearing)

Answer:

- **Q1.** Where on disk is the Claude Code chat-history store, per supported OS (Windows, macOS, Linux)? Document exact paths.
- **Q2.** What is the storage format? (SQLite? JSONL? proprietary binary? mixed?) Document the schema with examples.
- **Q3.** Is tool-call attribution captured per turn? Specifically, can you reconstruct:
   - The exact tool name used (Read, Grep, Glob, Bash, Edit, Write, etc., plus MCP-tool calls like `mcp__optimus__optimus_search`).
   - The input parameters per tool call.
   - The output / result.
   - The temporal ordering within a turn.
   - The "agent turn" boundary (where one assistant message + its tool calls end and the next begin)?

These four sub-questions are what the informed-precision-read heuristic needs. **If the answer to Q3 is "no" for any sub-question that breaks the heuristic, ESCALATE.** Do not invent a workaround.

**Deliverable for B.1:** a discovery report at `claudecode/DISCOVERY.md` in this clone, covering all three questions with code samples / schema dumps proving each finding. Commit this to `claudecode-variant-discovery` branch. PR it as a standalone milestone for human review before B.3 starts.

#### B.2 -- Plugin format research (load-bearing for M5)

Same delegated session, same escalation gate. Answer:

- **Q4.** What is the Claude Code plugin format spec source? (Official docs URL preferred; if undocumented, the empirical contract reverse-engineered from existing plugins.)
- **Q5.** Which Claude Code version is the format pinned against?
- **Q6.** What plugin install location does Claude Code use, per supported OS?
- **Q7.** What event/hook/tool surfaces does Claude Code expose? Specifically: hooks (PreToolUse, PostToolUse, Stop, etc.), commands (slash commands), agents (subagent definitions), skills (the `Skill` tool surface), MCP server registration. Map each to the IDE-agnostic `src/{hooks,agents,skills,rules}/` source surface that optimus uses (per `AGENTS.md` and `docs/decomp/M5-tasks.md`).

Note: Claude Code itself is the harness you are running inside of. You can introspect your own runtime extensively. You can also read the Claude Code documentation that is in the public domain. You CAN ask the user to run `claude --help` or paste config output if needed.

**Deliverable for B.2:** a research report at `claudecode/PLUGIN-FORMAT-RESEARCH.md` covering all four questions, plus a concrete `claudecode/plugin-skeleton/` demonstrating the format. Commit + PR for human review before B.3 starts.

#### B.3 -- Claude Code variant build

**Only proceed if both B.1 and B.2 came back positive.**

Build `claudecode/chat-report.py` (or whatever language is most appropriate given the chat-history store format -- Python is the default given the cursor variant is Python, but if the store is Node-y enough that JS is more appropriate, propose and escalate).

**Part B.3 Definition of Done:**

- Same three CLI modes as Part A (single-chat, `--diff`, `--aggregate`).
- Emitted output (markdown + JSON) conforms to **the exact same shape** as the Cursor variant (per section 4).
- Tests pass on Windows AND macOS AND Linux against fixture chat sessions.
- README in `claudecode/README.md`.
- PR opened against `master` on `dtwaling/ai-chat-report`.

### Cross-cutting -- shared library

If you find significant code duplication between `cursor/chat-report.py` and `claudecode/chat-report.py` (report rendering, JSON schema, CLI plumbing), extract a `common/` package shared by both variants. Discretionary; do not over-engineer. The contract is "same shape," not "same code path."

---

## 4. Locked Structured-Report Shape (the integration contract)

This is the contract that spike-1 telemetry, success-metric evaluation (Components A and B), and M1.5 integration depend on. **Both IDE variants emit the same shape.** Downstream consumers must not branch on IDE.

### 4.1 JSON output schema (canonical machine-readable form)

```json
{
  "report_version": "1.0",
  "report_kind": "single-chat" | "diff" | "aggregate",
  "ide": "cursor" | "claude-code",
  "ide_version": "<string>",
  "session_id": "<string>",
  "session_id_normalized": "<string>",
  "session_start_iso": "<ISO 8601>",
  "session_end_iso": "<ISO 8601>",
  "session_duration_s": <int>,
  "turns": [
    {
      "turn_index": <int>,
      "role": "user" | "assistant",
      "started_iso": "<ISO 8601>",
      "ended_iso": "<ISO 8601>",
      "tool_calls": [
        {
          "call_index": <int>,
          "tool_name": "<string>",
          "tool_class": "broad-sweep-read"
                       | "broad-sweep-grep"
                       | "broad-sweep-glob"
                       | "optimus-mcp"
                       | "directory-index-read"
                       | "edit" | "write" | "bash" | "other",
          "input_summary": "<string -- short, deterministic; full payload in input_payload>",
          "input_payload": <object | string>,
          "output_summary": "<string>",
          "output_status": "ok" | "error" | "denied" | "blocked",
          "denial_reason": "<string | null>",
          "elapsed_ms": <int | null>,
          "informed_precision_read": {
            "applicable": <bool>,
            "classification": "informed" | "uninformed" | "n/a",
            "reason": "<string -- explains the classification>"
          }
        }
      ]
    }
  ],
  "aggregates": {
    "total_tool_calls": <int>,
    "by_class": {
      "broad-sweep-read": <int>,
      "broad-sweep-grep": <int>,
      "broad-sweep-glob": <int>,
      "optimus-mcp": <int>,
      "directory-index-read": <int>,
      "edit": <int>,
      "write": <int>,
      "bash": <int>,
      "other": <int>
    },
    "success_metric_components": {
      "component_a": {
        "definition": "optimus_* count >= 1.0x broad-sweep (read+grep+glob) count",
        "optimus_count": <int>,
        "broad_sweep_count": <int>,
        "ratio": <float>,
        "pass": <bool>
      },
      "component_b": {
        "definition": "informed-precision-read count >= 1.0x uninformed-read count",
        "informed_count": <int>,
        "uninformed_count": <int>,
        "ratio": <float>,
        "pass": <bool>,
        "heuristic_failure_modes_flagged": ["<string>", ...]
      },
      "overall": {
        "pass": <bool>,
        "partial_pass": <bool>
      }
    },
    "denials": [
      {
        "tool_name": "<string>",
        "denial_reason": "<string>",
        "turn_index": <int>,
        "call_index": <int>
      }
    ],
    "errors": [
      {
        "tool_name": "<string>",
        "error_excerpt": "<string>",
        "turn_index": <int>,
        "call_index": <int>
      }
    ]
  },
  "warnings": [
    {
      "code": "<string>",
      "message": "<string>"
    }
  ]
}
```

**Notes on the JSON shape:**

- `session_id_normalized`: a canonical form (lowercased, no separators) so cross-IDE aggregation can match by content rather than IDE-specific format.
- `tool_class`: classification done IN the chat-report tool, so downstream consumers don't need to know how to classify per IDE.
- `informed_precision_read.classification`: implements the heuristic in `docs/telemetry-heuristic.md`. Only meaningful for Read calls (`applicable: true`); other tool calls get `applicable: false, classification: "n/a"`.
- `heuristic_failure_modes_flagged`: list of failure-mode codes from `docs/telemetry-heuristic.md` section "Known failure modes" (5 modes today). Surface honestly when a known failure mode may have polluted the classification.
- `success_metric_components`: pre-computed Components A and B per `docs/decisions/success-metric.md`. Downstream consumers can use these directly.

### 4.2 Markdown output (human-readable)

The markdown report is generated from the same data, structured as:

1. **Header.** Session ID, IDE, dates, duration.
2. **Summary table.** Aggregate counts per tool class.
3. **Success metric snapshot.** Component A + Component B pass/fail, ratios.
4. **Turn-by-turn trajectory.** Numbered turns; for each, a numbered list of tool calls with input/output summaries.
5. **Denials section.** All denial events listed.
6. **Errors section.** All error events listed.
7. **Warnings section.** Any per-report warnings (e.g., known failure modes flagged).

The markdown is for humans; the JSON is the integration contract. **JSON is the source of truth; markdown is a rendering.** A consumer that branches on markdown shape is a bug; flag and fix.

### 4.3 Aggregate-mode output

`--aggregate <id> ...` emits a top-level aggregate JSON with the same `aggregates` block (summed across input sessions) plus per-session `aggregates` snippets. Same shape, same versioning.

### 4.4 Diff-mode output

`--diff <idA> <idB>` emits a diff JSON with `before` (idA), `after` (idB), and `delta` blocks. Delta is `after - before` per aggregate counter and per Component A/B ratio. Same shape, same versioning.

### 4.5 Shape versioning

`report_version: "1.0"` at the top of every JSON. Any breaking change (renaming a field, changing a type, removing a key) bumps minor. Any additive non-breaking change (new optional field, new tool_class enum value) does NOT bump version. Document the version policy in `cursor/README.md` and `claudecode/README.md`.

### 4.6 What you must NOT include in the shape

- No raw chat-history-store bytes. The report is a derived signal, not an archive.
- No agent thinking blocks (Cursor variant currently captures these; remove or move them into a separate non-default output file -- not part of the locked contract).
- No tool output payloads larger than a configurable byte budget (default: 1024 bytes per output_summary; full payload available in a separate `--full-payloads` output file).
- No PII unless explicitly requested (file paths are fine; usernames in chat content are stripped).

---

## 5. Feasibility Gates (the only sanctioned escalation point)

You have **two** feasibility gates, both governed by AGENTS.md's unified Delegated Session Escalation Policy.

### Gate 1 -- Chat-history store discovery (after B.1)

**Positive:** all four sub-questions in B.1 (Q1-Q3 plus the four parts of Q3) can be answered with concrete schema. Tool-call attribution is sufficient to implement the informed-precision-read heuristic.

**Negative:** any of the following:
- Q1: store location cannot be determined or is not stable across Claude Code versions.
- Q2: format is opaque (encrypted, undocumented binary that resists reverse-engineering, etc.).
- Q3.a: tool name is not captured per call.
- Q3.b: input parameters are not captured.
- Q3.c: outputs are not captured (this is acceptable IF tool name + input are captured -- denials and errors are required, but full output content can be omitted; degrade output_summary gracefully).
- Q3.d: temporal ordering within a turn is not recoverable.
- Q3.e: agent-turn boundary is fundamentally ambiguous.

**On positive:** PR `claudecode/DISCOVERY.md` for human review. Wait for sign-off before B.3.

**On negative:** ESCALATE. Stop B.3. Write `docs/issues/chat-report-claudecode-feasibility-negative-<YYYY-MM-DD>.md` in the optimus repo with: which sub-question failed, evidence, recommended re-scope options (e.g., Cursor-only at degraded thesis falsifiability, project-pause for Claude Code engineering investment, etc.). Do not silently switch to a degraded variant.

### Gate 2 -- Plugin format research (after B.2)

**Positive:** all four sub-questions in B.2 (Q4-Q7) answered. Either via official docs OR via empirical contract you reverse-engineered. The `claudecode/plugin-skeleton/` demonstrates a minimal working plugin.

**Negative:** plugin format is undocumented AND reverse-engineering proved infeasible (e.g., plugin format is in a proprietary archive format you can't crack, or plugin loading is gated on cloud-side auth you can't replicate).

**On positive:** PR `claudecode/PLUGIN-FORMAT-RESEARCH.md` + `claudecode/plugin-skeleton/` for human review. M5 consumes these findings.

**On negative:** ESCALATE. Write `docs/issues/m5-plugin-format-feasibility-negative-<YYYY-MM-DD>.md` in optimus. This blocks M5 even if Gate 1 was positive; the project pauses for re-scope on plugin delivery (manual install? VS Code marketplace? other?).

---

## 6. Workflow and Branch/PR Ceremony

### 6.1 Your home

- **Working directory:** `C:/_Source/ai-chat-report/`
- **Current branch:** `claudecode-variant-discovery` (already created off `master`)
- **Remote:** `origin` -> `https://github.com/dtwaling/ai-chat-report.git`

### 6.2 Commits

- Use conventional-commits prefixes per optimus convention: `chore:`, `feat:`, `docs:`, `ci:`, `fix:`, `refactor:`, `test:` (see `C:/_Source/optimus/docs/conventions/git-and-issues.md`).
- One logical change per commit. If you're hardening + refactoring + adding tests, that's three commits.
- Co-author trailer required: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or whichever model is actually executing).

### 6.3 PR cadence

Open a PR for human review at each of the following milestones, NOT all at once:

1. **PR 1 (Cursor-variant adapt + harden, Part A complete).** Title: `feat(cursor): conform output to optimus v2 locked report shape`.
2. **PR 2 (B.1 discovery report).** Title: `docs(claudecode): chat-history store discovery findings`. Body: paste DISCOVERY.md content.
3. **PR 3 (B.2 plugin format research).** Title: `docs(claudecode): plugin format research + minimal skeleton`. Body: paste PLUGIN-FORMAT-RESEARCH.md content.
4. **PR 4 (B.3 Claude Code variant build).** Title: `feat(claudecode): chat-report variant emitting locked shape`.
5. **PR 5 (cross-IDE integration tests + shared lib, if any).** Title: `test: cross-IDE shape conformance`.

PR bodies use the optimus convention: "What changed / Why / Test plan / Risk" sections via `--body-file` (write to a tempfile, pass `--body-file <tempfile>`).

**Each PR waits for human review.** Do not merge yourself. Do not stack PRs that depend on unmerged work without flagging the dependency in the PR body.

### 6.4 Optimus submodule bump (NOT your job, but know how it works)

When a PR merges to `dtwaling/ai-chat-report:master`, the SHA of `master` advances. The optimus repo's `tools/ai-chat-report` submodule is currently pinned at `a4daa732e22c4f0d26547e0ccadc98732ce33f57` (the SHA at the time of optimus's founding commit). Bumping the pin is a deliberate PR in the optimus repo by Dustin (or whoever holds optimus repo write access at the time of the bump). You produce the merge in upstream; the parent project consumes it.

If the optimus PM needs a specific upstream SHA bumped urgently (e.g., to unblock spike-1), the PM will reach out -- not your concern from inside this session.

### 6.5 The convenience copy of this brief

`C:/_Source/ai-chat-report/MISSION-BRIEF.md` exists in your clone root as a convenience copy. It is in the clone's local `.git/info/exclude` (or `.gitignore` -- check both). **It must not be pushed to upstream.** If you find it staged, unstage it.

---

## 7. Methodology Notes (from optimus's "lessons learned")

These come from the parent project's hard-won experience. Apply them.

### 7.1 Chunking pattern (from optimus memory: chunking-pattern-for-doc-cleanups)

For any multi-area cleanup or design pass (3+ orthogonal concerns), break into explicit chunks rather than trying to land everything in one pass. Reserve `AskUserQuestion` blocks for 1-4 questions max per block. Bundle by record/concern, not by chunk -- four TODO records means four sub-chunks (3a/b/c/d), not one mega-ask with 16 design questions.

Why this matters here: Part B alone has Q1-Q7 across two feasibility gates. Don't try to land all 7 in one back-and-forth with the user. Land them in feasibility-gate order.

### 7.2 Cold reviewer pass

After any substantive design or implementation work, do a **blind cold-reviewer pass**. Dispatch a fresh subagent (Agent tool, isolation: worktree) with the original review prompt -- do NOT bias it toward expected findings. Compare verdict trajectory across rounds. Verdict deltas are honest signal.

Apply this to: the DISCOVERY.md before PR 2; the PLUGIN-FORMAT-RESEARCH.md before PR 3; the Claude Code variant code before PR 4.

### 7.3 Don't bundle decisions with implementation

When you discover something that affects scope (e.g., "the Claude Code chat-history store is JSONL, so the parser is straightforward, but the file rotates every N MB which means a session can span multiple files"), separate the discovery from the implementation:

1. Document the discovery (what + why + impact on plan).
2. Surface the decision (does this change Part B sizing?).
3. ONLY THEN implement against the chosen path.

Don't quietly implement around discovery findings and only mention them in the PR description.

### 7.4 Verification before "complete"

Per superpowers:verification-before-completion -- never claim a milestone is complete without running verification commands and confirming output. "Tests pass" without showing the test output is a flag.

---

## 8. Definition of Done (for the entire delegated session)

When all of the following are true, the delegated session is COMPLETE and Dustin can resume optimus's pre-M1 spike-1 work:

- [ ] PR 1 merged (Cursor variant adapted + hardened + tests + cross-OS).
- [ ] PR 2 merged (B.1 chat-history store discovery findings approved).
- [ ] PR 3 merged (B.2 plugin format research + skeleton approved).
- [ ] PR 4 merged (Claude Code variant built + tests + cross-OS).
- [ ] PR 5 merged if applicable (cross-IDE shape conformance test suite).
- [ ] Both variants emit identical structured-report shape (verified by automated test).
- [ ] Both variants tested on Windows, macOS, Linux (use fixtures where wiring up a real IDE on a CI runner is impractical).
- [ ] M5 plugin-format research findings are landed in `dtwaling/ai-chat-report:master` at a known SHA, ready for optimus M5 to consume.
- [ ] No outstanding `docs/issues/*-feasibility-negative-*` records in the optimus repo from this session.
- [ ] `MISSION-BRIEF.md` in clone root is NOT pushed to upstream.

**On completion:** notify Dustin via the optimus repo (open `docs/issues/chat-report-delegated-session-complete-<YYYY-MM-DD>.md` with the final upstream SHA and a summary of all 5 PRs). The optimus PM then bumps the submodule pin and resumes spike-1.

---

## 9. Out of scope (do not do these in this session)

- The informed-precision-read heuristic implementation refinements (M6.1 -- the 3 TODOs in `docs/telemetry-heuristic.md`). Your output must SUPPORT the heuristic; refining the heuristic itself is a future delegated session.
- The eval corpus query authoring or relevance labeling (separate delegated session per `docs/decisions/eval-corpus-methodology.md`).
- Anything in the optimus repo's `src/`, `container/`, `cli-shim/`, `bundlers/`, `installers/`, `templates/`, `tests/` directories. Those are downstream of you.
- Modifying any locked decision record in `docs/decisions/*.md`. Read-only.
- Auto-bumping the optimus submodule SHA. Parent project's job.

---

## 10. First moves checklist (for your first day)

When you start, in order:

1. [ ] Read this brief in full.
2. [ ] Read AGENTS.md and CHARTER.md from optimus.
3. [ ] Read chat-report-sibling-charter.md and success-metric.md.
4. [ ] `git status` in `C:/_Source/ai-chat-report/`; confirm you're on `claudecode-variant-discovery`, working tree clean.
5. [ ] `ls cursor/` and read `cursor/chat-report.py` top-to-bottom. Form opinions about shape conformance.
6. [ ] Open a working notes file at `claudecode/WORKING-NOTES.md` (gitignored; track your own thinking). Add a one-line revision-history entry to this brief in optimus under section 11 below.
7. [ ] Decide whether to attack Part A first (Cursor adapt + harden, fastest win) or B.1 (feasibility discovery, biggest risk). RECOMMENDED: B.1 first, because a negative gate makes Part A's value questionable. Confirm with the user before sinking effort into Part A.

---

## 11. Brief revision history

| Date | Reviser | Change |
|------|---------|--------|
| 2026-05-12 | Initial author (PM via optimus session) | Brief authored. |

---

**End of brief. When in doubt: re-read the charter at `C:/_Source/optimus/docs/decisions/chat-report-sibling-charter.md`. Charter beats brief. Escalate ambiguity.**
