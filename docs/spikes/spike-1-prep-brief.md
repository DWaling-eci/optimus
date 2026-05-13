# Spike-1 Prep Brief -- Retrieval Behavior Validation

**Brief authored:** 2026-05-13
**Authoring authority:** PM (Dustin) via the optimus-trunk Claude Code session that wrapped spike-2 + landed the spaCy keep/drop decision
**Parent project:** Optimus v2 (`github.com/DWaling-eci/optimus`, default branch `trunk`)
**Spike workspace:** `spike/pre-m1-retrieval/` (to be created in optimus-trunk by the spike runner)
**Spike report destination:** `docs/spikes/spike-1-retrieval-report.md` (final deliverable)

---

## 0. Read this section first

You are the **next session** picking up spike-1 in optimus-trunk. You did NOT run spike-2; you did NOT land the spaCy decision. This brief is your operational map -- if the brief and a decision record disagree, the decision record wins; escalate.

**Your mission, one sentence:** stand up a thin retrieval-only Optimus + a hand-authored DIRECTORY_INDEX.md against a real test codebase, run three controlled task conditions in Claude Code with structured-report telemetry, and produce a go/no-go verdict on H1 + H2 + H3 in `docs/spikes/spike-1-retrieval-report.md` -- replicating the spike-2 methodology rigor (per-condition empirical artifacts + cold-reviewer pass + revision-to-POSITIVE before commit).

**Before any tool work, read in this order:**

1. This entire brief.
2. `C:/_Source/optimus/AGENTS.md` -- project identity, conventions, Delegated Session Escalation Policy (load-bearing).
3. `C:/_Source/optimus/CHARTER.md` -- founding decisions; especially Decision 1 (host-singleton), Decision 3 (no memory), Decision 5 (salvage discipline), Decision 7 (host-singleton singleton-mode).
4. `C:/_Source/optimus/docs/decomp/pre-M1-spikes.md` -- spike-1 framing source (H1+H2+H3; H4 RETIRED -- see step 5).
5. `C:/_Source/optimus/docs/decisions/spacy-keep-drop.md` -- locked DROP verdict that retired H4. Your spike does NOT measure or build spaCy.
6. `C:/_Source/optimus/docs/decisions/secure-singleton-mcp-baseline.md` -- the locked retrieval stack (Nomic CodeRankEmbed + ColBERTv2 via RAGatouille). Your thin Optimus uses this stack -- NOT a substitute.
7. `C:/_Source/optimus/docs/decisions/transport-and-discovery.md` -- locked transport contract (validated by spike-2). Your thin Optimus speaks MCP over stdio (single-client; spike-2 already validated multi-client transport).
8. `C:/_Source/optimus/docs/decisions/success-metric.md` -- the >=1.0x outnumber floor + AND-combined two-component framing your H1 measurement compares against (one component this spike, full two-component eval at M6).
9. `C:/_Source/optimus/docs/decisions/chat-report-sibling-charter.md` -- the toolkit your telemetry depends on; dual-IDE bar.
10. `C:/_Source/optimus/docs/spikes/spike-2-singleton-report.md` -- the methodology template (cold-reviewer pass + per-condition empirical artifacts in `results/`).
11. `C:/_Source/optimus/docs/glossary.md` -- load anytime you hit unfamiliar term.

**Brief beats no source. Charter beats brief. Escalate ambiguity rather than guess.**

---

## 1. Authority and Boundaries

### What you can decide unilaterally

- Implementation tactics for the thin Optimus (chunking strategy, on-disk index format, MCP tool registration shape, error-handling specifics) -- as long as the locked retrieval stack (Nomic + ColBERTv2) is preserved per `secure-singleton-mcp-baseline.md`.
- Operational details for the test-run protocol (task prompts, drift introduction timing, prompt-injection-test taxonomy outside H1/H2/H3 scope).
- Branch/commit hygiene on `optimus` trunk for the `spike/pre-m1-retrieval/` work tree.
- Methodology refinements (e.g., adding a 4th run-per-condition if LLM stochasticity proves higher than expected; adjusting drift-fixture aggressiveness). **Document the refinement in the report; don't silently change the protocol.**

### What you must escalate

- Any **gate-logic-relevant negative finding** -- H1 fails (no behavior change), H2 fails (memory gap exists), H3 fails (stale dir-index proves worse than no dir-index). All three trigger different downstream consequences per `pre-M1-spikes.md` gate logic; do not silently work around.
- Any **discovery-driven scope change** -- e.g., the locked retrieval stack (Nomic + ColBERTv2) cannot run within spike-1's resource envelope on the chosen test target, OR the chat-report toolkit's structured-report shape is missing fields needed for H1/H2 measurement.
- Any session-count overrun (see section 2 sizing estimate; 2x trigger applies).
- Any change that would re-open a locked decision in `docs/decisions/`.
- Any need to author a graded-relevance corpus for ANY hypothesis (the H4 corpus problem is exactly what got that hypothesis retired; do not reintroduce the contamination surface for H1/H2/H3).

### What you must never do

- Do NOT build `src/optimus/spacy_pipeline.py`, install `spacy`, or measure spaCy on/off. **H4 is RETIRED** per `docs/decisions/spacy-keep-drop.md`. The thin Optimus has no spaCy.
- Do NOT use a synthetic / fabricated test target. Spike-1's framing requires a real existing codebase per `pre-M1-spikes.md` ("synthetic projects bias agent behavior toward what the test was built to validate").
- Do NOT push the chosen test target back to its upstream. Run `git remote remove origin` (or equivalent) on the test target's clone BEFORE the spike begins. Spike-2 followed this protocol with `c:\ms-superrepo\`; mirror it.
- Do NOT commit the test target into optimus -- it lives elsewhere on disk and is referenced by absolute path or a config file (gitignored).
- Do NOT skip the cold-reviewer pass on the final report. Per the M5 / M4 / spike-2 validated methodology, cold-reviewer is non-optional; it caught real empirical-accuracy issues on every prior pass except spike-2 (which got POSITIVE first-pass because the line-citation accuracy was hand-verified pre-dispatch).

---

## 2. Sizing Estimate and Escalation Triggers

**Sizing estimate:** **medium-large**, roughly:

- Thin retrieval-only Optimus build (stdio MCP server + Nomic + ColBERTv2 + on-disk chunk index + indexer): **2 sessions.** This is the largest unknown.
- Test-target choice + prep (clone, origin-remove, sample sub-tree if too large for spike timeline, verify thin Optimus indexes it cleanly): **0.5-1 session.**
- DIRECTORY_INDEX.md authoring: **0.5-1 session** (depending on test-target size and depth).
- Drift fixture design + dry-run: **0.5 session.**
- Three controlled task runs in Claude Code with telemetry capture (>= 2 runs per condition for stochasticity): **1-2 sessions.**
- Final report + cold-reviewer pass + revision: **1 session.**

**Total baseline: ~5-7 sessions.** This exceeds the original `pre-M1-spikes.md` estimate of 1-2 sessions, which was authored before the locked Nomic + ColBERTv2 stack was decided -- the original estimate assumed a much thinner / simpler retrieval pipeline. Calibration is honest; a 1-2 session estimate for a Nomic-CodeRankEmbed-driven thin Optimus is unrealistic.

**Trigger 1 (session-count overrun):** if actual session count exceeds **2x baseline (~10-14 sessions)**, STOP and escalate to Dustin. Do NOT silently extend; the project's critical path depends on knowing whether spike-1 is on or off track.

**Trigger 2 (discovery-driven scope change):** any of the following triggers immediate escalation regardless of session count:

- The locked Nomic + ColBERTv2 stack cannot be assembled within spike-1's resource envelope on the chosen test target (e.g., RAGatouille install proves blocked, Nomic load OOMs on the spike host, indexing the test target takes >24 hours).
- The chat-report toolkit's structured-report shape (per `chat-report-sibling-charter.md`) is missing a field needed for H1/H2 measurement (broad-sweep classification, optimus tool-call attribution, informed-precision-read heuristic). The toolkit is a hard prerequisite; if its output is insufficient, spike-1 pauses.
- The chosen test target is too large for the spike's timeline (e.g., even an indexing pre-pass runs longer than the per-task budget). Subset the target or pick a smaller one; document the change.
- An H1/H2/H3 measurement returns a result that materially changes the scope of the next milestone (e.g., H3 fails -> `optimus_doctor` becomes mandatory CI integration with no opt-out; this would expand M2 scope materially and Dustin should know before you keep going).

---

## 3. Hypothesis-by-hypothesis operational gloss

Reference: `pre-M1-spikes.md` "Spike-1: Retrieval Behavior Validation". This section operationalizes that framing -- what to measure, how to capture evidence, and what counts as PASS.

### H1 -- Behavior change

**Claim:** Retrieval-only Optimus + an accurate hand-authored DIRECTORY_INDEX.md raises optimus tool-call ratio AND reduces broad sweeps relative to a no-Optimus baseline.

**Operational measurement (per `success-metric.md` Component A):**

- For each controlled task, run >= 2 independent Claude Code sessions per condition (3 conditions = 6+ sessions per task).
- After each session, invoke the chat-report toolkit with the session ID. The toolkit emits per-tool-class aggregate counts: `Read`, `Grep`, `Glob`, `optimus_*`, plus per-Read informed-precision classification.
- Compute, per session: ratio of `sum(optimus_*) / sum(broad_sweep)` where `broad_sweep = Read + Grep + Glob`. The success-metric floor is **>= 1.0x** on the Optimus + accurate-dir-index condition; the no-Optimus baseline serves as the comparison anchor.
- PASS = optimus-tool-call ratio under the Optimus + accurate-dir-index condition is **materially higher** than under the no-Optimus baseline AND meets the >= 1.0x floor. Direction-of-change must be consistent across all >= 2 runs per condition.
- The full success-metric AND-combined two-component evaluation (Component A: optimus-vs-broad-sweep, Component B: informed-vs-uninformed Read) is **deferred to M6**. Spike-1 measures Component A primarily; capture Component B's raw data so M6 can replay if needed.

**Evidence to record per session in `spike/pre-m1-retrieval/results/`:**

- The chat-report toolkit's structured JSON output (verbatim from the toolkit; no manual editing).
- Per-condition aggregate (mean / median / min-max ratio across runs).
- A short narrative paragraph per task: did the agent's behavior look qualitatively different? (This is informational color, NOT the gate.)

### H2 -- No memory gap

**Claim:** Killing memory does not leave a retrieval gap that ONLY memory was filling. Optimus + dir-index covers the cross-session continuity needs that memory served in v1.

**Operational measurement:**

- The H1 protocol already runs without memory (CHARTER Decision 3 killed memory in v2). H2 is essentially a counterfactual check: are there task patterns where the agent demonstrably needed memory and Optimus + dir-index did not substitute?
- Look for task-failure patterns in the H1 runs that map to "the agent forgot X across sessions" -- e.g., re-discovering a file in session 2 that session 1 already knew about, OR asking the user about something the chat history would have answered.
- PASS = no task-failure pattern in the H1 runs maps cleanly to "memory would have helped" -- agent behavior gaps are explained by retrieval-quality issues (which spike-1 is testing) rather than missing-context issues (which memory would have addressed).

**Evidence to record:** per-task gap analysis in the report's H2 section; cite specific session IDs + chat-report excerpts.

**Note:** H2 has a softer measurement than H1. There's no clean numerical bar -- it's a qualitative assessment based on the H1 data. Be honest in the report about confidence level.

### H3 -- Dir-index drift resilience

**Claim:** The hand-authored DIRECTORY_INDEX.md remains useful under realistic edit velocity. Stale dir-index is NOT worse than no dir-index.

**Operational measurement:**

- Add a fourth run condition: **Optimus + drifted dir-index**. Drift = "add a file, rename a dir" introduced mid-task per `pre-M1-spikes.md`.
- Drift fixture: pre-author a small drift script that, when invoked at a specified mid-task point, modifies the test target's filesystem AND does NOT update DIRECTORY_INDEX.md. This simulates the realistic "developer made a change, dir-index got stale" condition.
- Run >= 2 sessions per task in this condition; capture chat-report output.
- PASS = optimus-tool-call ratio under Optimus + drifted-dir-index is **NOT MATERIALLY WORSE** than the no-Optimus baseline. (Not "as good as accurate dir-index" -- that's an unrealistic bar; the question is whether stale dir-index actively HARMS behavior compared to no dir-index at all.)

**Drift fixture design specifics:**

- Drift moment: introduced after the agent's 3rd tool call, OR 60 seconds into the task, whichever comes first. Captures realistic mid-task drift, not "drift before task started."
- Drift content: 1 file added in a directory the dir-index lists, 1 directory renamed. Simulates the most common realistic drift pattern (new feature work touching one area).
- The drift script lives in `spike/pre-m1-retrieval/drift-fixture.sh` (or `.py`); it's invoked manually at the drift moment by the spike runner. Document in the report the exact drift content per task run for reproducibility.

**Evidence to record:** per-condition optimus-vs-broad-sweep ratio; explicit comparison of `drifted-dir-index` vs `no-dir-index` baseline; verdict + confidence.

### H4 -- RETIRED

H4 (spaCy preprocessing contribution) is **retired** per `docs/decisions/spacy-keep-drop.md`. **DO NOT measure spaCy on/off; do not install `spacy`; do not author a graded-relevance corpus for H4.** The decision is locked DROP based on the literature. The thin Optimus has no spaCy in the query path.

---

## 4. Test target choice

**Recommendation: REUSE `c:\ms-superrepo\`** -- the same target spike-2 used. Rationale:

- Already cloned locally with `git remote remove origin` performed (spike-2 protocol). Re-running the protocol on a fresh target costs a session.
- Real ~3.4GB monorepo, multi-language, multi-project. Per `pre-M1-spikes.md` selection criteria: real (yes), large (yes), spike-runner familiar (yes -- you / Dustin authored a 324MB subset for spike-2).
- The ms-superrepo subset (`~/.spike-test-corpus/` from spike-2's `run-wsl2-spike.sh`) is also available if the full repo is too large for indexing within the spike timeline.

**If you choose differently:** document the rationale in the report. The selection-criteria gate is `pre-M1-spikes.md` -- real existing codebase, not synthetic, large enough to tempt broad-sweep behavior, locally cloned with origin removed.

**Indexing budget:** if Nomic embedding the full ms-superrepo takes >2 hours, subset to `~/.spike-test-corpus/` or pick a smaller test target. Indexing time is not a hypothesis under test; it's setup overhead.

---

## 5. Thin retrieval-only Optimus -- scope definition

The thin Optimus is **not** the v2 production server. It is the minimum viable retrieval surface that lets spike-1 measure agent behavior change. Locked scope:

**MUST include (load-bearing for the spike):**

- Stdio MCP server (single-client; spike-2 already validated multi-client transport -- spike-1 is one Claude Code instance).
- One MCP tool: `optimus_search(query: str) -> list[ranked_chunk]`. Returns top-5 ranked chunks per `secure-singleton-mcp-baseline.md` two-stage pipeline.
- The locked retrieval stack: Nomic CodeRankEmbed (dense, with the `"Represent this query for searching relevant code"` task-instruction prefix) + ColBERTv2 via RAGatouille (rerank). No spaCy in the query path per `spacy-keep-drop.md`.
- An on-disk chunk index built ONCE at indexing time (chunk all files, embed all chunks, persist embeddings). The MCP server reads the index at startup; queries do not re-embed documents.
- Path-confinement: every agent-supplied path realpath-resolved against the test-target root before any FS operation. Per `secure-singleton-mcp-baseline.md` SECURITY callout.
- Logging: at minimum, log every tool call's query + top-5 result paths to a per-session log file (for cross-checking against the chat-report toolkit's output).

**MUST NOT include (out of scope; defer to M1+):**

- Singleton container, Docker, network_mode none, model-cache bind-mount. (The spike runs the thin Optimus as a host-side Python process. Nomic/ColBERTv2 weights download to host once via `huggingface-cli` or `sentence-transformers`'s default cache; the spike is not testing the container model -- spike-2 did that.)
- `optimus_doctor`, `optimus_init`, `optimus_grep`, `optimus_list`, `optimus_delete`, `optimus_resolve`, telemetry plumbing beyond the chat-report-toolkit-driven measurement. None of these are under test in spike-1.
- `.mcp.json` schema validation, `optimus_protocol_version` handshake, SO_PEERCRED / SID auth. Spike-2 validated those. Spike-1 runs single-client stdio in a trusted local context.
- Multi-client concurrency, cap, busy_retry. Spike-2 validated these.
- Pretty UI, summarization, anything that adds value beyond "return ranked chunks."

**Implementation location:** `spike/pre-m1-retrieval/` (sibling to spike-2's `spike/pre-m1-singleton/`). Mirror the spike-2 layout: README.md, server-stdio.py, indexer.py, drift-fixture.py (or .sh), results/ (gitignored).

**Performance budget:** per-query latency <= **5 seconds** end-to-end on the test target (indexing-time can be higher). If queries take >5 seconds, the agent will time out or behave unnaturally; that's a discovery-driven escalation per section 2 trigger 2.

---

## 6. DIRECTORY_INDEX.md scope

**Hand-authored** per `pre-M1-spikes.md` -- not agent-generated, not auto-generated from the codebase structure (that would be auto-fresh and miss the drift-resilience question).

**Recommended scope:** top-2 levels of the test target with one-line summaries per directory, plus selectively-deeper detail for the most-touched areas. Deep enough that the agent can find the right area without recursive listing; shallow enough that you can author it in <1 session.

**Living test artifact:** the dir-index for the chosen test target lives at the test target's repo root (`<test-target>/DIRECTORY_INDEX.md`), NOT inside optimus. Reason: the dir-index is a property of the codebase being indexed, not optimus's source.

**Drift fixture pairing:** when the drift script runs, it modifies the codebase but NOT the dir-index. So the H3 measurement is "stale dir-index vs absent dir-index"; not "out-of-date dir-index vs synchronized dir-index." Document the exact drift content per session in the report.

---

## 7. Telemetry hookup contract (chat-report toolkit invocation)

The chat-report toolkit is the measurement instrument for H1 + H2 + H3. By the time spike-1 starts, BOTH variants must be complete (`chat-report-sibling-charter.md` dual-IDE bar, no fallback).

**Toolkit state at spike-1 kickoff (verify before starting):**

- Cursor variant: complete (PRs #2 + #3 merged on `dtwaling/ai-chat-report` as of 2026-05-13).
- Claude Code variant (B.3): complete and merged upstream. **VERIFY BEFORE STARTING.** If B.3 is not yet merged, spike-1 cannot start; pause per the dual-IDE charter rule.
- Optimus's `tools/ai-chat-report/` submodule pin updated to consume both variants. **VERIFY** -- if the submodule is still pinned to the pre-B.3 SHA, bump it before spike-1 starts (this is the "one deliberate bump" the submodule-bump policy reserves for this milestone).

**Per-session invocation pattern:**

After each Claude Code session for a controlled task, invoke (illustrative; check the upstream toolkit's actual CLI):

```bash
python tools/ai-chat-report/claudecode/chat-report.py \
    --session-id <session-id> \
    --output-format json \
    --output-path spike/pre-m1-retrieval/results/<task>-<condition>-<run>.json
```

Verify the output contains the structured-report fields needed for H1 + H2 measurement: per-tool-class aggregate counts, optimus-tool-call attribution, per-Read informed-precision classification. If a field is missing, escalate per section 2 trigger 2 (discovery-driven scope change).

**Cross-IDE comparability:** spike-1 runs in Claude Code only. The Cursor variant is consumed by the success-metric eval at M6, not by this spike. But because both variants emit the SAME structured-report shape (per the charter), spike-1's measurement code is portable to Cursor at M6 with zero adaptation -- this is the integration contract.

---

## 8. Definition of Done

Spike-1 ships when ALL of the following hold:

- The thin Optimus is built and runs reliably on the chosen test target. (Section 5 scope; section 4 target.)
- DIRECTORY_INDEX.md authored and committed at the test target's repo root. (Section 6.)
- Drift fixture authored, dry-run verified, idempotent (re-runnable). (Section 7.3.)
- Three controlled-task conditions x N tasks x >= 2 runs each completed in Claude Code with chat-report toolkit output captured per session. (Sections 3 + 7.)
- All chat-report JSON artifacts persisted to `spike/pre-m1-retrieval/results/` (gitignored).
- `docs/spikes/spike-1-retrieval-report.md` authored with hypothesis-by-hypothesis verdicts + evidence + cited artifacts. Mirror the spike-2 report's shape (`docs/spikes/spike-2-singleton-report.md`): executive verdict table, per-hypothesis evidence section, sources/citations, scope-boundary section, cross-references, recommendation.
- Cold-reviewer pass on the report (per section 9) -> POSITIVE before commit.
- Single commit covering all spike-1 deliverables (mirror the spike-2 commit shape: `spike(pre-m1-retrieval): COMPLETE -- H1/H2/H3 ...`).
- Memory bump reflecting spike-1 outcome + downstream consequences (Phase 1.0 inputs, M2 scope adjustments per H3 outcome, etc.).

---

## 9. Cold-reviewer methodology

Per the validated M5 / M4 / spike-2 pattern, the final report goes through a fresh-subagent cold-reviewer pass against the live filesystem before commit.

**Dispatch shape (use the spike-2 report's cold-reviewer dispatch as a template; see `docs/spikes/spike-2-singleton-report.md` cross-references + the trunk commit `d3edaa6`'s commit-body description of the cold-reviewer protocol):**

- Fresh subagent (Explore or general-purpose), zero conversation context.
- Tasked with: read the spike-1 report, then check it ruthlessly against the live filesystem -- byte-for-byte file-line citations, per-hypothesis JSON-shape claims against the actual `results/` artifacts, decision-record section references, gate-logic claims against `pre-M1-spikes.md`.
- Verdict: POSITIVE | PARTIAL | NEGATIVE.
- PARTIAL = revise must-fixes, re-dispatch.
- POSITIVE = commit.

**Pre-dispatch checklist** (this is what got spike-2's report POSITIVE on first pass; mirror it):

- Re-grep every `file:line` citation in the report against the live file. Update if the file has grown since you wrote the section.
- Re-read every artifact JSON quoted in the report. Verify field values match.
- Re-check decision-record section numbers + cited error codes against the live decision records.
- Pre-fix anything you catch before dispatching. The reviewer is the final gate, not the only gate.

---

## 10. Per-deliverable artifact paths

| Deliverable | Path |
|---|---|
| Thin Optimus implementation | `spike/pre-m1-retrieval/server-stdio.py`, `spike/pre-m1-retrieval/indexer.py` |
| Drift fixture | `spike/pre-m1-retrieval/drift-fixture.py` (or `.sh`) |
| Spike README + how-to-run | `spike/pre-m1-retrieval/README.md` |
| Spike artifacts (JSON) | `spike/pre-m1-retrieval/results/` (gitignored) |
| DIRECTORY_INDEX.md | `<test-target-root>/DIRECTORY_INDEX.md` (lives in the test target's clone, NOT in optimus) |
| Spike final report | `docs/spikes/spike-1-retrieval-report.md` |
| Cold-reviewer dispatch | (in-conversation via Agent tool; no persistent artifact) |
| Memory bump | `C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/optimus-kickoff-state.md` (+ MEMORY.md index entry) |

---

## 11. Cross-references

- `docs/decomp/pre-M1-spikes.md` -- spike-1 framing source (H1+H2+H3; H4 retired).
- `docs/decisions/spacy-keep-drop.md` -- the H4 retirement record. Read before assuming you need to measure spaCy.
- `docs/decisions/secure-singleton-mcp-baseline.md` -- the locked retrieval stack the thin Optimus uses.
- `docs/decisions/transport-and-discovery.md` -- transport contract (validated by spike-2; thin Optimus uses stdio MCP).
- `docs/decisions/success-metric.md` -- the >=1.0x AND-combined floor; H1 measures Component A.
- `docs/decisions/chat-report-sibling-charter.md` -- the toolkit gate (dual-IDE mandatory).
- `docs/decisions/eval-corpus-methodology.md` -- the M1.3 graded corpus methodology (NOT consumed by spike-1; mentioned because the H4 retirement directly engages with this record's deferral discipline).
- `docs/spikes/spike-2-singleton-report.md` -- methodology template (per-condition empirical artifacts + cold-reviewer pass).
- `docs/glossary.md` -- spaCy entry reflects DROPPED status.
- `CHARTER.md` Founding Decisions 1, 3, 5, 7 -- v2's foundation.

---

## 12. Status note

Brief authored 2026-05-13 in optimus-trunk session that wrapped spike-2 + landed `docs/decisions/spacy-keep-drop.md`. Spike-1 is **prep-unblocked, empirically gated** -- prep work (this brief, target choice, dir-index authoring, thin-Optimus design) can start now; empirical task runs cannot start until B.3 (Claude Code chat-report variant) ships and the optimus submodule pin consumes it.

Revision history: this section is the only one the next session may modify (to add a "next session updates" line); all other sections are PM-locked and require Dustin's review to change.
