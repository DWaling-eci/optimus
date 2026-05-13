# Pre-M1 Validation Spikes -- Detailed DoDs

**Status:** clean stub. High-level spike framing + gate logic lives in CHARTER Founding Decision 5 + roadmap Pre-M1 section. Detailed DoDs transplant here at refactor time.

**Source:** transplanted from roadmap Pre-M1 Validation Spikes section.

## Spike-1: Retrieval Behavior Validation

**Thesis:** Retrieval-only Optimus + a hand-authored DIRECTORY_INDEX.md changes Claude Code agent behavior on retrieval-shaped tasks. The v2 thesis is wrong if this does not happen.

**Hypotheses under test:**

- **H1:** Retrieval-only Optimus + a hand-authored DIRECTORY_INDEX.md raises optimus tool-call ratio and reduces broad sweeps relative to a no-Optimus baseline.
- **H2:** Killing memory does not leave a retrieval gap that only memory was filling.
- **H3 (dir-index drift resilience):** the hand-authored DIRECTORY_INDEX.md remains useful under realistic edit velocity. Intentionally introduce drift mid-task (add a file, rename a dir) and measure whether agent behavior degrades. If a stale dir-index is worse than no dir-index, `optimus_doctor` is load-bearing infrastructure, not convenience.

**H4 (spaCy preprocessing contribution): RETIRED 2026-05-13.** The spaCy keep/drop call was originally framed as an empirical spike-1 measurement (Recall@10 / nDCG@10 with spaCy on vs off). It is **retired** here and replaced by `docs/decisions/spacy-keep-drop.md`, which lands the verdict (DROP) sourced from the literature -- the empirical test was unnecessary given (a) Nomic CodeRankEmbed's model-card prescribed contract (raw query + fixed prefix; silent on further preprocessing), (b) ColBERTv2's internal tokenization + `[mask]` padding mechanism (upstream stripping mechanically harmful), and (c) the closest direct ablation (CodeSearchNet identifier normalization, ~50% relative MRR loss). See that record for the full evidence and revision bar.

**Definition of Done:**

- Thin retrieval-only Optimus runs on a real test target codebase (chosen at spike-prep time; see "Test target selection" below).
- Hand-authored DIRECTORY_INDEX.md lives in the test target's repo root.
- Three controlled task runs in Claude Code with telemetry captured:
  - Baseline (no Optimus, no dir-index)
  - Optimus + accurate dir-index
  - Optimus + drifted dir-index (drift introduced mid-task)
- Go/no-go report at `docs/spikes/spike-1-retrieval-report.md` covering H1 + H2 + H3 with evidence.

**Test target selection (spike-prep step):**

The test target is chosen at spike-prep time, not pinned up front. Requirements:

- Real existing codebase, NOT a synthetic / fabricated test project (synthetic projects bias agent behavior toward what the test was built to validate).
- Cloned locally, with `git remote remove origin` (or equivalent) BEFORE the spike begins, so any accidental writes cannot push to the upstream repo.
- Large enough to exercise broad-sweep behavior (an agent should be tempted to do recursive listings if the dir-index isn't present).
- A codebase the spike runner has enough familiarity with to judge agent-output correctness on the task runs.

If the chosen project's requirements shift mid-spike-development, swap to a different real project rather than fabricating a fit.

**LLM stochasticity protocol:** minimum 2 independent runs per condition; consistent direction across runs required for pass.

**Telemetry capture dependency:** depends on `docs/decisions/chat-report-sibling-charter.md` deliverable. Dual-IDE coverage is mandatory; spike-1 does not start until BOTH Cursor and Claude Code chat-report variants are complete and emitting the structured report shape. If the Claude Code variant proves infeasible, the project pauses pending re-scope per the locked charter.

**Estimated size:** 1-2 sessions.

**Outputs:**

- `docs/spikes/spike-1-retrieval-report.md` -- hypothesis-by-hypothesis findings.
- Confirmed-real vs confirmed-not-needed v1 retrieval issues.
- Input for the Architecture Spike (Phase 1.0): which retrieval components mattered, which didn't.

**Gate logic:**

- H1 + H2 + H3 all confirm -> spike-1 passes. **Current default holds:** `optimus_doctor` drift detection runs default-on in host projects with a config-driven opt-out (per TR-07).
- H1 fails (no behavior change) -> the entire v2 thesis is suspect; pause and replan.
- H2 fails (memory gap exists) -> revisit CHARTER Decision 3 with Dustin before proceeding.
- H3 fails (stale dir-index proves worse than no dir-index) -> the opt-out is **removed**; `optimus_doctor` drift detection becomes **mandatory CI integration** with no opt-out. Update TR-07 in `docs/requirements/REQUIREMENTS.md` and Phase 2.3 in `docs/decomp/M2-tasks.md` accordingly.

(spaCy keep/drop is no longer a spike-1 gate -- see `docs/decisions/spacy-keep-drop.md`. Verdict locked: DROP. Revision bar: evidence-backed roadblock surfaced by M6 dogfood-eval or the M1.3 graded corpus.)

## Spike-2: Singleton Container Feasibility

**Thesis:** A single host-singleton container with a user-configured parent-mount can serve multiple concurrent MCP clients (multiple IDEs, parallel sub-agents) without crashing, dropping requests, or imposing unreasonable UX cost.

**Hypotheses under test:**

- **H1 (multi-client MCP transport works):** clients can connect to the same container concurrently and both get correct responses. No serialization through a single stdio pipe.
- **H2 (concurrent requests don't crash or drop):** parallel `optimus_grep` calls return correct results; concurrent calls do not crash each other or drop silently.
- **H3 (parent-mount UX is acceptable for the spike's test target):** the test codebase fits under a single user-configured parent without contortion. (Real-world enterprise edge cases beyond the probe matrix below become a v2.1 risk per CHARTER Decision 7.)

**Definition of Done:**

- Singleton-mode container runs with a parent-mount config (`~/.optimus/config.json` skeleton).
- Multi-client probe harness in `spike/pre-m1-singleton/` opens concurrent MCP connections and issues parallel requests.
- Concurrency cap behavior verified: requests beyond the cap get a structured "busy, retry" response (not silent drop, not crash).
- Discovery mechanism prototyped: second client detects existing container via socket-aliveness probe (no pid-file; see `docs/decisions/transport-and-discovery.md`) and does not spawn a duplicate.
- Go/no-go report at `docs/spikes/spike-2-singleton-report.md` with transport-mechanism recommendation.

**Validates against** `docs/decisions/transport-and-discovery.md`, not against a free choice. The decision record locks the canonical transport + discovery socket path + `.mcp.json` schema + liveness-probe protocol BEFORE spike-2 runs.

**Probe matrix:**

- **Concurrent-client count: 4 clients**, matching CHARTER Decision 7's envisioned workload. A 2-client probe is insufficient evidence for the concurrency cap default.
- **WSL2 path translation included.** WSL2 is a primary supported platform per TR-09; cannot be excluded from spike testing. M0 CI does not run a WSL2 runner (see `docs/decomp/M0-ci-pipeline.md`, "WSL2 coverage strategy"); spike-2 is the named end-to-end gate for WSL2 behavior under the singleton + parent-mount design.

**Estimated size:** 1-2 sessions.

**Outputs:**

- `docs/spikes/spike-2-singleton-report.md` -- feasibility report with transport-mechanism recommendation (Unix socket vs TCP-on-loopback vs hybrid).
- Input for the Architecture Spike (Phase 1.0): transport mechanism, concurrency cap default, discovery protocol.
- If H1 or H2 fails: documented fallback path to multi-mount mode (per-project container) per CHARTER Decision 7.

**Gate logic:**

- H1 + H2 + H3 confirm -> spike-2 passes; v2 proceeds with singleton model.
- H1 or H2 fails -> fall back to multi-mount mode; TR-18 requirements amended; M1.0 Architecture Spike inputs adjusted.
- H3 fails (parent-mount UX unreasonable even on a controlled codebase) -> escalate to Dustin before proceeding; this is a charter-level reconsideration.

## Parallelization

- Spike-1 and Spike-2 are independent and can run in parallel.
- M2.1 (standards template authoring) is parallel-eligible with the spikes since template content authoring doesn't depend on transport / concurrency decisions.
