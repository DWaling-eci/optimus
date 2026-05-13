# Spike-1 Close-Out Design

**Status:** Approved by Dustin (PM) 2026-05-13 via interactive brainstorming.
**Trunk base:** `1e9de87` (post GPU-probe merge).
**Brief reference:** `docs/spikes/spike-1-prep-brief.md`. This design is the close-out plan that operationalizes the brief through to a POSITIVE-cold-reviewed `docs/spikes/spike-1-retrieval-report.md`.
**Downstream gate:** spike-1 close blocks M1.0 (Architecture Spike) per `docs/decomp/M1-tasks.md` Phase 1.0 inputs.

---

## 1. Goal

Produce a POSITIVE-cold-reviewed `docs/spikes/spike-1-retrieval-report.md` with hypothesis-by-hypothesis verdicts on:

- **H1** -- retrieval-only Optimus + accurate `DIRECTORY_INDEX.md` raises optimus tool-call ratio AND reduces broad sweeps vs no-Optimus baseline.
- **H2** -- killing memory leaves no retrieval gap that only memory was filling.
- **H3** -- drifted `DIRECTORY_INDEX.md` is NOT materially worse than no `DIRECTORY_INDEX.md`.

Verdicts are backed by 24 Claude Code session artifacts and the chat-report toolkit's structured JSON, executed against `c:\ms-superrepo\` on the GPU-ported spike-1 server.

---

## 2. Hard boundaries (out of scope)

- `ARCHITECTURE.md` authoring (M1.0 work; gated on this spike's evidence).
- Any `src/optimus/` module work (gated on M1.0).
- GPU stress / concurrency / throughput / thermal measurement as a primary deliverable. Dustin captures bonus host-side observation informally (see section 6.4).
- CUDA kernel toolkit install (`cuda-toolkit-12-1`). Current 0.5s/query crushes the 5s brief budget by 10x; the +1.5-2x kernel speedup buys nothing for spike-1 needs.
- `optimus_doctor`, `optimus_init`, `optimus_grep`, `optimus_list`, `optimus_delete`, `optimus_resolve`. None under test.
- spaCy on/off measurement. H4 retired and locked DROP per `docs/decisions/spacy-keep-drop.md`.
- Multi-client transport / concurrency. Validated by spike-2.

---

## 3. Cross-cutting decisions

| Decision | Resolution | Why |
|---|---|---|
| Server compute | GPU autodetect with CPU fallback code retained but unexercised in spike. | Probe (2026-05-13) showed 19x speedup, top-1 paths match, ~1.47 GB VRAM peak. Latency 0.5s/query vs brief's 5s budget. Tool latency would otherwise bias H1 (slow tool, agent ignores). M1.0 production-default direction. |
| `dense_k=30` PM call | Dead. No retrieval-config change. | The lever was a CPU-latency band-aid. GPU obviates it entirely. |
| Task count (N) | 4. Behavioral signal diversity, not GPU stress. | Brief leaves N open. Dustin explicit override of the 2x escalation trigger (`spike-1-prep-brief.md` section 2 trigger 1) for rigor on the hypothesis under test. |
| GPU stress probe | Deferred maybe-probe; "probably not." Not on the queue. | Dustin's call. N=4 buys diversity, not load; load-test belongs to a separate experiment if ever run. Bonus host-side thermal observation by Dustin during empirical runs is the only GPU-side signal captured. |
| Server topology | Port forward: apply GPU patches to `spike/pre-m1-retrieval/server-stdio.py`. `spike/pre-m1-gpu-feasibility/server-stdio-gpu.py` remains a historical probe artifact, not the spike-1 production server. | Single canonical server; probe scripts informed spike-1, did not replace it. |
| Task authoring | Spec defines shape and criteria. Concrete tasks drafted in prep phase against ms-superrepo, reviewed before empirical runs start. | Task authoring needs ms-superrepo browsing in Dustin's head; spec stays small and reviewable now. |
| Drift fixture | Per-task drift. `drift-fixture.py --task <1\|2\|3\|4>`. | Same drift across 4 task areas would mean 3 of 4 tasks see drift in irrelevant areas, weakening H3. |

---

## 4. Phases

```
Phase 0: Server port (GPU patches -> spike-1 server)
Phase 1: Prep (DIRECTORY_INDEX.md + 4 tasks + drift fixture, parallel-eligible)
Phase 2: Empirical runs (24 Claude Code sessions, serial)
Phase 3: Report + cold-reviewer
Phase 4: Single commit + memory bump
```

### Phase 0 -- Server port

**Code changes to `spike/pre-m1-retrieval/server-stdio.py`:**

1. Device autodetect at startup:
   ```python
   device = "cuda" if torch.cuda.is_available() else "cpu"
   ```
   Log device + VRAM info at startup. No env-var switch -- autodetect is the contract.

2. Wrapper patch (M1.0 finding from probe). Replace the MaxSim matmul:
   ```python
   # Was:  sim = q_colbert[0] @ d_emb.T
   # Is:   sim = q_colbert[0] @ d_emb.to(device=q_colbert.device, dtype=q_colbert.dtype).T
   ```
   Source of truth: `spike/pre-m1-gpu-feasibility/server-stdio-gpu.py:163`. Already proven on GPU during probe; top-1 paths matched CPU baseline.

3. `requirements.txt` switches to the GPU stack (forked from `spike/pre-m1-gpu-feasibility/requirements-gpu.txt`): `torch==2.5.1+cu121`, the 12 cu12 wheel deps, `triton==3.1.0`, `sentence-transformers==5.5.0`, `colbert-ai==0.2.22`. **Shai-Hulud dry-run scan on the new pin before install** per `[[shai-hulud-pip-install-discipline]]`.

4. Persistent GPU venv at `~/optimus-spike-gpu-venv/` in WSL2. Replaces (or installed alongside, Dustin's call at install time) the existing CPU spike venv. One-time install, reused across all 24 empirical sessions.

5. `spike/pre-m1-retrieval/README.md` updated with: new GPU-stack install steps, new venv activation line, current run protocol intact otherwise.

**What does NOT change:**

- `optimus_search` MCP tool contract.
- Index format (`embeddings.npy` + `chunks.jsonl` + `manifest.json`).
- Two-stage retrieval pipeline shape (Nomic dense top-100 -> ColBERTv2 MaxSim rerank top-5).
- Chunking strategy (1500-char window, no overlap).
- `confine_path` security.

**Phase 0 exit gate:** rerun the 3-query smoke (build system tests / http retry logic / kotlin coroutine) against the ported server. Confirm sub-second latency AND top-1 path match against the probe baseline. If either fails, escalate per `spike-1-prep-brief.md` section 2 trigger 2 (discovery-driven scope change).

### Phase 1 -- Prep (parallel-eligible internally)

**1A: `<ms-superrepo>/DIRECTORY_INDEX.md`**

- Path: `c:\ms-superrepo\DIRECTORY_INDEX.md`. **NOT** in optimus repo (brief section 6).
- Scope: top-2 levels with one-line summaries + selectively deeper detail in 1-2 "most-touched" areas, where most-touched is defined by which subsystems the 4 tasks exercise.
- Hand-authored by Dustin. Estimated 0.5-1 session.
- Format: Markdown, no schema lock. Full schema lands in M2 templates.
- Committed inside ms-superrepo's local clone (origin already removed per spike-2 protocol; no upstream push possible).

**1B: 4-task authoring**

Spec pins shape and criteria. Concrete tasks drafted by Dustin against ms-superrepo in this phase, reviewed by Zolt before empirical runs start.

| # | Shape | Example flavor | Success criterion class |
|---|---|---|---|
| 1 | Navigational ("find the thing") | "Where is the auth middleware for service X?" | Agent locates correct file in <= 3 tool calls without broad recursive listing. |
| 2 | Subsystem comprehension | "Explain how the X module's config gets loaded." | Agent produces accurate explanation citing real files. Dustin verifies. |
| 3 | Cross-module trace | "Trace how a request flows from API entry to data layer for endpoint Y." | Agent identifies the chain across module boundaries, no fabricated steps. |
| 4 | Pattern-find | "Find all places service X retries on failure; are they consistent?" | Agent enumerates the actual sites + judges consistency correctly. |

**Authoring rules:**

- Each task: prompt text + ms-superrepo grounding (which subsystems / files it touches) + success criteria Dustin can judge.
- Tasks reward retrieval-shaped behavior over broad sweeps. If a task is answerable by reading 2-3 files Dustin already knows the path to, it's a bad task -- redesign.
- Tasks held STABLE across all 24 sessions: same prompt, same target state, same fresh context. Stochasticity comes from the LLM, not task wording.
- Tasks ms-superrepo-grounded enough that drift in their area (Phase 1C) is meaningful.

**1B exit gate:** all 4 tasks reviewed by Zolt. Mismatches flagged before empirical runs start.

**1C: `spike/pre-m1-retrieval/drift-fixture.py`**

- CLI: `python drift-fixture.py --task <1|2|3|4>` applies per-task drift. `--reset` reverses it.
- Per-task drift content: 1 file added in a `DIRECTORY_INDEX.md`-listed directory relevant to that task. 1 directory renamed in a relevant area.
- Idempotent. `--reset` returns ms-superrepo to git-clean.
- Drift moment: invoked manually by Dustin after the agent's 3rd tool call OR 60s elapsed, whichever comes first (brief section 3).
- Drift content per task documented inline in the script + cited in the report.
- **Does not modify `DIRECTORY_INDEX.md`.** That is the simulation: stale index, drifted code.

### Phase 2 -- Empirical runs (24 Claude Code sessions, serial)

**Run-order recommendation:** group by task. Within a task, cycle through conditions (baseline -> Optimus + accurate -> Optimus + drifted). Within a condition, run the 2 runs back-to-back. So 1 task = 6 consecutive sessions. Easier mental context for Dustin per task block.

**Per-session loop:**

```
1. Reset ms-superrepo:
     git -C c:\ms-superrepo reset --hard HEAD && git -C c:\ms-superrepo clean -fd
   (DIRECTORY_INDEX.md is committed inside ms-superrepo per Phase 1A, so the
   reset restores it. clean -fd removes any untracked drift files from a prior
   run.)

2. Configure MCP + dir-index per condition:
     - Baseline: no .mcp.json entry for optimus; DIRECTORY_INDEX.md removed from
       working tree (git stash or rename to .bak); no optimus server running.
     - Optimus + accurate: spike-1 server started; .mcp.json points at it;
       DIRECTORY_INDEX.md present.
     - Optimus + drifted: same as accurate; drift fixture invoked at drift moment.

3. Start fresh Claude Code session, fresh CWD at c:\ms-superrepo.

4. Run task prompt.

5. For drifted condition only: invoke
     python spike/pre-m1-retrieval/drift-fixture.py --task <N>
   at drift moment.

6. Capture the session UUID when complete (basename of the active JSONL under
   ~/.claude/projects/<sanitized-cwd>/).

7. Run chat-report invocation (single-chat mode, JSON output, custom out-dir):
     python tools/ai-chat-report/claudecode/chat-report.py <session-uuid> \
         --shape locked \
         --format json \
         --out spike/pre-m1-retrieval/results/
   Rename the emitted JSON to task<N>-<condition>-run<R>.json after the call
   (the toolkit names by session UUID; spike-1 rename makes the result set
   addressable by experimental coordinates).

8. Sanity-check JSON has required fields: per-tool-class aggregate counts,
   optimus-tool-call attribution, per-Read informed-precision classification.
   If a field is missing, escalate per brief section 2 trigger 2.

9. Copy server log:
     cp ~/.optimus-spike/index/server.jsonl \
        spike/pre-m1-retrieval/results/task<N>-<condition>-run<R>.server.jsonl

10. End-of-session server handling:
     - Between CONDITIONS: stop spike-1 server cleanly. Restart fresh for the
       next condition (cold-cache baseline per condition).
     - Between the 2 RUNS within a single condition: server may remain running
       (warm cache acceptable, faster). Document the chosen warm-vs-cold
       protocol in the report.
```

**Bonus host-side observation:** Dustin watches fan / thermal / stability throughout. If anomalies appear, note in the report's scope-boundary section. Not a primary deliverable, not a gate.

**Discovery escalation during runs:**

- If H1 baseline shows the agent already barely uses broad sweeps (rare-but-possible LLM behavior change), halt and escalate -- the experiment's framing breaks.
- If chat-report JSON is missing fields needed for H1/H2/H3 measurement, halt and escalate per brief trigger 2.
- If LLM stochasticity proves higher than expected (direction inconsistent across the 2 runs per condition), invoke spike-runner methodology authority (brief section 1) and expand to 3+ runs per condition. Document the refinement in the report.

### Phase 3 -- Report + cold-reviewer

**Report shape** mirrors `docs/spikes/spike-2-singleton-report.md`:

1. Executive verdict table -- one row per hypothesis (H1/H2/H3): verdict (PASS / FAIL / PARTIAL), confidence (high / medium / low), one-line rationale.
2. Per-hypothesis evidence section -- raw counts, ratios, narrative color, cited session JSON artifacts by path. Cite `results/task<N>-<condition>-run<R>.json`.
3. Sources / citations -- every claim cites a file:line or a `results/` JSON path.
4. Scope-boundary section -- what this spike did NOT test (concurrency, large-target indexing, sustained-load thermal behavior, etc.). Bonus thermal observations land here.
5. Cross-references -- CHARTER, brief, decision records, M1.0 inputs.
6. Recommendation -- what M1.0 inherits as input from this spike. What's left.

**Pre-dispatch checklist** (mirrors spike-2 first-pass POSITIVE protocol):

- Re-grep every `file:line` citation against the live file.
- Re-read every `results/` JSON cited; verify field values match prose claims.
- Re-check decision-record section numbers and cited error codes against the live decision records.
- Pre-fix anything found.

**Cold-reviewer dispatch:**

- Fresh subagent (Explore or general-purpose), zero conversation context.
- Tasked with: ruthless filesystem-grounded check of every citation, every JSON claim, every gate-logic statement. Confirm verdicts match the JSON evidence.
- Verdict: POSITIVE | PARTIAL | NEGATIVE.
- PARTIAL: revise must-fixes, re-dispatch.
- POSITIVE: commit.

### Phase 4 -- Commit + memory bump

**Single commit** covering all spike-1 deliverables. Mirror spike-2 commit shape:

```
spike(pre-m1-retrieval): COMPLETE -- H1/H2/H3 verdicts + 24-session empirical artifacts
```

**Memory update:**

- Update `C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/optimus-kickoff-state.md` with spike-1 outcome.
- Update `MEMORY.md` index entry to reflect close.
- Note downstream consequences: M1.0 unblocked for ARCHITECTURE.md authoring. M2 scope adjustment if H3 fails (`optimus_doctor` becomes mandatory CI integration with no opt-out, per `pre-M1-spikes.md` gate logic).

---

## 5. Deliverables

| Path | Content |
|---|---|
| `spike/pre-m1-retrieval/server-stdio.py` | GPU-aware spike-1 production server: device autodetect, wrapper patch, locked stack preserved. |
| `spike/pre-m1-retrieval/requirements.txt` | GPU stack pin (forked from `requirements-gpu.txt`). |
| `spike/pre-m1-retrieval/drift-fixture.py` | `--task <1\|2\|3\|4>` applies per-task add+rename mid-task; `--reset` reverses. |
| `spike/pre-m1-retrieval/README.md` | Updated run protocol: GPU stack install, persistent venv, 24-session execution loop, chat-report invocation. |
| `<ms-superrepo>/DIRECTORY_INDEX.md` | Hand-authored, lives at test-target root. NOT in optimus. |
| `spike/pre-m1-retrieval/results/` (gitignored) | 24 chat-report JSON files + 24 server log files. |
| `docs/spikes/spike-1-retrieval-report.md` | Final hypothesis-by-hypothesis report. Cold-reviewer POSITIVE before commit. |
| Memory bump | `optimus-kickoff-state.md` + `MEMORY.md` index entry. |

---

## 6. Sizing + escalation

### 6.1 Brief baseline

`spike-1-prep-brief.md` section 2 estimates 5-7 sessions total (thin Optimus build was already done in prep sessions 1-3; remaining work is server port + Phase 1 prep + Phase 2 runs + Phase 3 report).

### 6.2 N=4 override

N=4 (vs implicit N=2-3 in the brief) scales Phase 2 from 12 to 24 Claude Code sessions. Dustin explicitly overrode the 2x escalation trigger (brief section 2 trigger 1) on the rationale of behavioral signal diversity, not GPU stress. This override is the only deviation from the brief's sizing discipline and is documented here.

Optimus-side workload (Phase 0 + 1 + 3 + 4) remains close to the brief baseline. Phase 2's 24 sessions are *empirical executions in Claude Code against ms-superrepo*, not Optimus development sessions; cost in Dustin's calendar time, not engineering complexity.

### 6.3 Trigger 2 (discovery scope change) remains active

Any of the following triggers immediate escalation regardless of session count:

- Locked stack (Nomic + ColBERTv2) cannot run within spike-1's GPU envelope on ms-superrepo (memory OOM, indexing >2h, etc.).
- chat-report toolkit v0.1.0 (current pin `eb201d0`) missing fields needed for H1/H2/H3 measurement.
- Test target too large for spike timeline -- subset to `~/.spike-test-corpus/` or pick smaller; document the change.
- Any H1/H2/H3 measurement that materially changes M2's scope (H3 fail -> mandatory `optimus_doctor` CI).
- Locked-decision-record revision needed.

### 6.4 Bonus host-side observation (informal)

Dustin watches fan / thermal / system stability throughout Phase 2 from the host OS side. Captured as informal notes; if anomalies surface, they go in the report's scope-boundary section. Not a primary deliverable. Not a gate.

---

## 7. Risks and open assumptions

- **Assumption** -- chat-report toolkit v0.1.0 (`tools/ai-chat-report` pinned at `eb201d0`) emits all required fields for H1/H2/H3. **Verification:** before Phase 2 starts, run chat-report against any recent Claude Code session and confirm field coverage (per-tool-class aggregates, optimus-tool-call attribution, per-Read informed-precision classification). If missing, escalate per trigger 2; do not start Phase 2.
- **Risk** -- LLM stochasticity across 24 sessions may show direction-inconsistency within a condition. Brief allows spike-runner authority to expand to 3+ runs per condition. Document the refinement in the report.
- **Risk** -- H3 fails (drifted dir-index materially worse than no dir-index): `optimus_doctor` becomes mandatory CI integration with no opt-out, per `pre-M1-spikes.md` gate logic. Material M2 scope expansion. Escalate to Dustin before continuing.
- **Risk** -- H1 fails (no behavior change): the entire v2 thesis is suspect per `pre-M1-spikes.md` gate logic. Pause and replan with Dustin before any further work.
- **Risk** -- GPU compute surprises (e.g., long-running memory leak, thermal throttle invisible at the spike-runner host). Bonus host-side observation flags this informally; formal escalation per trigger 2 if confirmed.

---

## 8. Cross-references

- `docs/spikes/spike-1-prep-brief.md` -- source brief.
- `docs/decomp/pre-M1-spikes.md` -- H1/H2/H3 framing + gate logic.
- `docs/decomp/M1-tasks.md` -- Phase 1.0 inputs (M1.0 hard gate; this spike's deliverable feeds it).
- `docs/decisions/spacy-keep-drop.md` -- H4 retired (locked DROP).
- `docs/decisions/secure-singleton-mcp-baseline.md` -- locked retrieval stack.
- `docs/decisions/colbert-wrapper-revision.md` -- 2026-05-13 wrapper revision (RAGatouille -> colbert-ai direct).
- `docs/decisions/transport-and-discovery.md` -- transport contract.
- `docs/decisions/success-metric.md` -- the >=1.0x AND-combined floor; H1 measures Component A.
- `docs/decisions/chat-report-sibling-charter.md` -- toolkit dual-IDE gate.
- `docs/spikes/spike-2-singleton-report.md` -- report shape + cold-reviewer methodology template.
- `spike/pre-m1-gpu-feasibility/RESULTS.md` -- GPU probe evidence; source for the wrapper patch and GPU production-default direction.
- `CHARTER.md` Founding Decisions 1, 3, 5, 7.

---

## 9. Status

Authored 2026-05-13 via interactive brainstorming session in optimus-trunk after the GPU probe merged to trunk (`1e9de87`). Approved by Dustin verbally; pending written-spec review per the brainstorming skill's user-review gate. Implementation plan to be authored by the `writing-plans` skill after this spec is approved in its written form.
