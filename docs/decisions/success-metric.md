# Decision Record: Success Metric -- Quantified Threshold + Baseline

**Status:** Decided -- locked. v2 GA gate criterion for M6 dogfood evaluation.
**Owner:** Dustin (locked at refactor time). Future iterative tightening (post-GA) is Dustin-call.

## Why this record exists

The v2 thesis is that retrieval tooling + standards-layer guidance changes agent behavior on retrieval-shaped tasks -- specifically, agents lean on `optimus_*` calls and informed precision reads instead of broad sweeps (Read/Grep/Glob).

The roadmap Overview names this metric, but without a **quantified threshold**, a **baseline condition**, and a **separation rule** between the two metric components, M6 cannot declare pass/fail and the thesis becomes unfalsifiable.

This record locks all three, plus the partial-pass policy and the cross-IDE comparability rule.

## Locked design calls

### 1. Threshold

**`optimus_*` tool calls >= 1.0x the count of broad-sweep Read/Grep/Glob calls on retrieval-shaped tasks** (i.e., `optimus_*` must **outnumber** broad-sweep calls). Measured per controlled task run, not aggregated across sessions.

#### Threshold framing -- minimum baseline floor, not target

This >= 1.0x bar is intentionally a **minimum baseline floor** for v2 GA, **NOT** the target end-state.

Dustin's reasoning, in his own words:

> "`optimus_*` should be used at least some degree more than the tools/actions it is meant to override. We definitely want it to be much higher, but given my experience with IDEs (e.g. Cursor) this will be an iterative process once we know we can achieve a minimum baseline."

Explicit commitments encoded here:

- **v2 GA bar is "outnumber"** (>= 1.0x). That is the falsifiability floor for the dogfood eval at M6.
- This threshold is set as a minimum baseline floor knowing the real long-term target is materially higher.
- The threshold **will be tightened iteratively post-GA**, once the minimum baseline is empirically validated and we have evidence of what tightening is achievable per IDE.
- Future tightening is **expected, not optional**. Frame this as a **v2 GA threshold, v2.1+ tighter** trajectory.

This framing is load-bearing for future readers: we did not settle for low rigor. We picked an achievable falsifiability floor on purpose, with explicit iterative tightening on the roadmap.

### 2. Two-signal combination rule (AND-combine)

Track `optimus_*` calls and "informed precision reads" as **separately reported signals**, not a sum (summing is gameable -- an agent that reads DIRECTORY_INDEX.md 50 times and never searches would score well under a sum).

**Full pass requires BOTH components to hold:**

- **Component A:** `optimus_*` count >= 1.0x broad-sweep (Read/Grep/Glob) count.
- **AND Component B:** informed-precision-read count (per the heuristic in `docs/telemetry-heuristic.md`) >= 1.0x uninformed-read count.

A run that satisfies one component but not the other is a **partial pass**. Partial pass triggers investigation, **not** a thesis-validated outcome.

### 3. Partial-pass policy at the GA gate

**Partial pass BLOCKS GA.**

v2 GA requires full thesis validation -- both components pass. If the M6 dogfood eval returns a partial-pass result:

- M6 does **not** declare success.
- GA is **gated** until full pass is achieved.
- No "ship with caveats." No "iterate post-GA on a half-validated thesis."
- Partial pass triggers investigation + iteration, then re-evaluation, before GA proceeds.

### 4. Cross-IDE threshold

**Same threshold for both IDEs.** Cursor and Claude Code use the same >= 1.0x bar (and the same iterative-tightening trajectory post-GA).

Chat-log granularity differences between IDEs are handled in the **chat-report toolkit's normalization layer**, not in the metric. The metric stays comparable across IDEs by construction. See `docs/decisions/chat-report-sibling-charter.md` for the toolkit contract that owns the normalization.

## Decided defaults

### Baseline condition

- **Baseline:** same agent (Cursor or Claude Code), same task prompt, same target codebase, **Optimus tools disabled / not installed**. Read/Grep/Glob is the only retrieval surface.
- **Treatment:** same agent, same task, same codebase, Optimus tools available, DIRECTORY_INDEX.md present and accurate.

Comparison is treatment-vs-baseline on the SAME task class. Different task classes (debug vs feature-add vs onboarding) are measured separately.

### Task corpus shape

- **Number of task classes:** 3-5 (e.g., debug, feature-add, onboarding, code-review, refactor).
- **Number of tasks per class:** 3-5 each, to manage LLM stochasticity.
- **Runs per task:** >= 2, to detect single-run variance.
- **Task list location:** `tests/dogfood/tasks.jsonl`.

Eval-corpus methodology proper (retrieval-quality corpus, distinct from this dogfood-behavior corpus) is owned by `docs/decisions/eval-corpus-methodology.md`. Both records are locked; downstream consumers depend on this record for the dogfood-behavior side.

## Consumers (cross-reference)

- `CHARTER.md`, Product Thesis section -- references this record for the falsifiability bar.
- `docs/requirements/REQUIREMENTS.md`, EUR-10 -- consumes the threshold + baseline as the acceptance criterion.
- `docs/plans/TDD-ROADMAP.md`, M6 DoD -- consumes the threshold as the dogfood-readiness gate.
- `docs/telemetry-heuristic.md` -- defines the informed-precision-read heuristic this record measures.
- `docs/decisions/chat-report-sibling-charter.md` -- owns the chat-report toolkit (including the cross-IDE normalization layer) this metric depends on for measurement.
- `docs/decisions/eval-corpus-methodology.md` -- relates; that's the retrieval-quality corpus, this is the dogfood-behavior corpus.

## Status note

Locked at refactor time. Threshold is >= 1.0x as a **minimum baseline floor**, AND-combined across both components, with partial-pass blocking GA, same bar for both IDEs (normalization in the chat-report toolkit). Iterative post-GA tightening is on the roadmap, not optional. Founding docs reference this record by name without inlining; updates here propagate.
