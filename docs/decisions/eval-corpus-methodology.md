# Decision Record: Eval Corpus Methodology

**Status:** Decided -- locked. Hard prerequisite for Phase 1.3 retrieval implementation kickoff. Specific target codebase choice is deferred to Phase 1.0 prep against locked selection criteria.
**Owner:** Dustin (methodology locked at refactor time). Target-codebase selection and corpus authoring are **delegated future sessions** at Phase 1.0 prep, per the same pattern as the `chat-report` sibling.

## Why this record exists

The M1 retrieval-quality bar (Recall@10 >= 0.85, MRR >= 0.60, nDCG@10 regression-tracked) is well-anchored against external benchmarks (CallSphere, CoIR, Sourcegraph BM25F). But the *measurement methodology* is structurally gameable unless authored discipline, labeling discipline, and corpus selection are pinned before the ranker exists:

- If the corpus (50+ queries) is authored by the same developer implementing the retrieval system, queries drift toward shapes the ranker already handles.
- If relevance labels are self-assigned by the implementer post-hoc, the labels become a knob the ranker can turn.
- If the target codebase is "TBD at spike-1 prep time," contamination risk compounds (the implementer's mental model of the codebase shapes both the queries and the ranker).

This is a classic eval-contamination setup. Recall@10 >= 0.85 can be made to pass by labeling the system's own results as relevant rather than by retrieving relevant results -- and the quality bar becomes performative, not predictive. This record closes the loop.

## Locked design calls

### 1. Target codebase selection -- criteria locked, specific choice deferred to Phase 1.0 prep

Specific codebase choice is deferred to **Phase 1.0 prep** (not spike-1 prep -- spike-1 is too early to lock the contamination surface). The selection criteria are locked now:

- **Real codebase, not synthetic.** Synthetic projects bias retrieval evaluation toward what the corpus was constructed to validate.
- **~20+ top-level directories, 10k+ files, multi-language.** Relaxed from the original stub's "50+ top-level directories." Rationale: most realistic "very large" codebases are monorepos that land in the ~20+ top-level-directory range, often with submodule-style composition. 50+ was overly strict and excluded many legitimately-large real-world targets. **Submodule-style monorepos qualify.**
- **Forked + remote-removed** for the optimus-v2 evaluation. Prevents accidental upstream writes during eval runs.
- **Selection happens before retrieval implementation starts** (i.e., before Phase 1.3), not at spike-1 prep time. This is the contamination guard the original stub flagged and is now pinned.

### 2. Query authorship -- delegated session, pre-implementation

A **delegated future session** -- same pattern as the `chat-report` sibling (a separately scoped Claude Code session or future principal-agent engagement) -- authors the **50+ queries before retrieval implementation starts** (i.e., before Phase 1.3). Not Dustin self-authoring. Not post-implementation. Not harvested from spike-1 logs.

Rationale: stronger discipline than self-authoring (no implementer-bias on which queries the ranker has seen), and the queries are locked before the ranker has a chance to optimize for them. The "delegated session" convention is consistent with `docs/decisions/chat-report-sibling-charter.md`; the doc-set treats delegated sessions as the standard answer for scoped, pre-gate build work.

Queries reflect realistic agent tasks ("find the auth middleware," "where is the rate-limiter configured?"), not queries the implementer knows the ranker handles.

**Sizing estimate (inferred):** medium -- 2-3 sessions. Authoring 50+ realistic queries against a multi-language ~20-top-level-dir codebase is non-trivial but bounded (single deliverable, single shape).

**Escalation:** subject to the unified **Delegated Session Escalation Policy** in `AGENTS.md`. The 2x sizing trigger applies (escalate if the effort exceeds ~6 sessions); discovery-driven escalation applies if the corpus authoring surfaces a structural finding that invalidates the methodology (e.g., the chosen target codebase fails the selection criteria mid-authoring).

### 3. Relevance labeling -- delegated session, graded 0-3 scale

The same delegated session (or another separately scoped session) labels each query with a **graded 0-3 relevance scale**:

- **0** -- not relevant.
- **1** -- partially / tangentially relevant.
- **2** -- relevant.
- **3** -- highly relevant.

**Tie / ambiguous rule:** when uncertain between two grades, mark **down** -- default to the lower grade. Specifically:

- Ambiguous between 0 and 1 defaults to **0**.
- Ambiguous between 2 and 3 defaults to **2**.

**Labels are committed before the ranker sees the query.** No post-hoc label adjustment. Labels are not a knob.

**Sizing estimate (inferred):** small-to-medium -- 1-2 sessions. Labeling 50+ queries against a known target codebase is mechanical but careful work; smaller than authoring because the queries already exist.

**Escalation:** subject to the unified **Delegated Session Escalation Policy** in `AGENTS.md`. The 2x sizing trigger applies (escalate if the effort exceeds ~4 sessions); discovery-driven escalation applies if labeling surfaces structural problems with the query set (e.g., a meaningful fraction of queries have no relevant documents in the target codebase, indicating a query-set vs target-codebase mismatch).

### 4. Graded-vs-binary metric semantics -- binarization rule

The M1 retrieval-quality bar names three metrics. Graded labels feed them differently; this is load-bearing and is stated explicitly so future changes are explicit decision-record revisions, not silent shifts.

- **nDCG@10 -- uses graded labels (0-3) directly.** This is the primary retrieval-quality metric and nDCG is graded-friendly by construction.
- **Recall@10 and MRR -- binarized via threshold.** Labels **>= 2** are "relevant"; labels **0 or 1** are "not relevant." The threshold is **2**.

Any change to the binarization threshold (e.g., switching to `>= 1`) is a methodology change requiring a decision-record revision **and** baseline recapture per the versioning policy below. The threshold is not a per-run tuning knob.

### 5. Held-out split -- 80/20, held-out is the DoD gate

- 80% of the corpus is **used during M1.3 retrieval implementation** (visible to the implementer).
- 20% is **held out** and only consulted at **M1.4 DoD evaluation**.
- Held-out queries live in the same `tests/retrieval/corpus.jsonl` and are marked with a `held_out: true` field.
- CI evaluation reports two scores: dev-set + held-out set. **Held-out set is the authoritative DoD gate.**

### 6. Absolute nDCG@10 floor: 0.65

In addition to the 5% relative regression alert (per the M1 quality bar), an **absolute nDCG@10 floor of 0.65** is locked. Calibrated against CoIR leaderboard entries.

Rationale: a regression-only gate would protect a mediocre baseline forever. The absolute floor prevents that failure mode. The 5% relative alert continues to apply against the current baseline; the absolute floor is the additional ceiling-from-below.

### 7. Storage -- git submodule with pinned ref

- The target codebase is stored as a **git submodule with pinned ref** at `tests/retrieval/corpus-repo/`. Aligns with the `tools/<external-tool>/` submodule pattern established in `docs/decisions/chat-report-sibling-charter.md` for external/sibling dependencies.
- The **corpus query file** (queries + graded labels + `held_out` flags) lives at `tests/retrieval/corpus.jsonl` in optimus-v2 directly -- **not** inside the submodule. The corpus file is owned by optimus-v2; the codebase being searched is the pinned external ref.

### 8. Corpus versioning policy

Any change to `tests/retrieval/corpus.jsonl` requires:

- **Baseline recapture.** Update the stored nDCG@10 baseline.
- **PR note explaining the change in domain terms** -- e.g., "added 10 queries covering API-shape retrieval gap." Not in outcome terms ("made the numbers better"). Outcome-framed PR notes are rejected.

The 5% regression-alert threshold applies to the **current** baseline; corpus changes do not grandfather old baselines.

### 9. Multi-codebase evaluation -- out of scope for v2 GA

**v2 GA uses one target codebase.** A future v2.x or v3 release may extend to multi-codebase evaluation (corpus split by codebase, or aggregated across codebases); the methodology for that extension is **out of scope for this record** and will be a separate decision when the time comes.

## Consumers (cross-reference)

- `docs/requirements/REQUIREMENTS.md` -- consumes the methodology rules (target codebase selection, query authorship discipline, labeling rules, 80/20 held-out split, corpus versioning) as the M1 retrieval-quality gate.
- `docs/plans/TDD-ROADMAP.md`, M1 DoD -- consumes the threshold + methodology rules; held-out 20% is the authoritative DoD gate.
- `docs/decomp/M1-tasks.md`, Phase 1.3 -- corpus authoring task references this record; the delegated session executes against these locks.
- `docs/glossary.md`, "Retrieval evaluation metrics" entry -- references this record for the methodology.
- `docs/decisions/chat-report-sibling-charter.md` -- precedent for the delegated-session pattern used here for both query authorship and labeling, and for the `tools/<external-tool>/` submodule pattern adapted here for the corpus repo.
- `docs/decisions/success-metric.md` -- relates; that record owns the dogfood-behavior corpus, this record owns the retrieval-quality corpus.
- `AGENTS.md` -- the **Delegated Session Escalation Policy** governs both delegated sessions in this record (query authoring + relevance labeling). Sizing estimates above feed the 2x trigger; discovery-driven escalation applies independently.

## Status note

Locked at refactor time. Selection criteria, authorship pattern, labeling scale, binarization threshold, held-out split, absolute floor, submodule storage layout, versioning policy, and multi-codebase scope are all decided. The only deferred item is the specific target-codebase choice, which is owned by Phase 1.0 prep and constrained by the locked criteria above. Retrieval implementation does not begin until this record's prerequisites (corpus authored, labels committed, codebase pinned) are satisfied.
