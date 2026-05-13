# Chunk 5 — Verification Review Findings

Re-dispatched the same three reviewers (architect, red-team, junior) **blind** — same prompts as round 1, no hint about what changed. Below: the deltas, the prioritized fix list, and the Chunk 6 recommendation.

---

## Verdict deltas (round 1 → round 2)

Massive improvement across the board:

| Reviewer  | Round 1                              | Round 2                                              |
| --------- | ------------------------------------ | ---------------------------------------------------- |
| Architect | Not ready — fix 6 items first        | **Ready with caveats** — fix 9 items                 |
| Red-team  | Halt — fix 5 items first             | **Halt** — fix 6 items (smaller / more tractable)    |
| Junior    | I'd need a real walkthrough          | **I could start with a 30-min sync, coding by lunch** |

The decision-record bones are now described as "exceptional" / "unusually tight" / "above-average." We solved the substantive design questions. The remaining findings are real but tractable — cleanup, small specs, and a couple of genuine bug fixes in the illustrative code. None are existential.

---

## Findings grouped by type

### A. Mechanical cleanup (no decisions needed)

- Stray `docs/decomp/M2-host-project-artifacts.~md` backup file — delete (all three reviewers flagged it).
- `AGENTS.md:3-6` meta-todo about unfinished housekeeping is out of date now — remove or rewrite.
- `docs/archive/*-v1-pre-reframe.md` files — purge per AGENTS.md's own instruction.
- `TR-13` and `v1-salvage-inventory.md:31` both cite "Founding Decision 1" when they mean **Founding Decision 9** (external-tool vendoring) — fix the citation drift.
- `M1-tasks.md:24` still lists "dual CE vs single CE (with spike data)" as a Phase 1.0 decision section — that question is retired per the locked baseline; scrub.
- Glossary polish: add a `TR-XX` / `EUR-XX` / `FD9` legend up front; disambiguate "host" vs "host project."

### B. Open calls needing your input (small decisions)

- `optimus_doctor` always-on vs opt-in drift detection. Currently blocks M2 DoD.
- Image registry path for v2 GA. Currently blocks M6 DoD.
- Claude Code plugin format research — who owns it, when does it land?
- "Delegated future session" escalation policy. The pattern is now used three times (chat-report owner, eval-corpus authoring, eval-corpus labeling) with no documented escalation trigger or handoff path.

### C. New small specs (mostly mechanical once decided)

- EUR-06 `<URL>` placeholder — pick the install distribution endpoint.
- Add a spaCy keep/drop hypothesis to spike-1 DoD. Currently the keep/drop call is gated on spike-1 evidence that spike-1 doesn't gather.
- Add a machine-checkable `STATUS: AWAITING_PM_FILL` marker (or equivalent) to skeleton M1-M6 task bodies, so autonomous agent loops have a structural halt, not just prose.
- One-page commit / PR / issue convention doc. Currently no contract; agents will be inconsistent.

### D. Genuine bugs in illustrative code (security + correctness)

- **`optimus_search` example in `secure-singleton-mcp-baseline.md`** walks `search_dirs[].path` with only an `os.path.exists` check — no `realpath` + prefix-check against `/mnt/parent_mount`. Agents will copy this CWE-22 path-traversal pattern. Red-team flagged this as top-1 exploit risk.
- **`M0-debug-loop.md` exposes debugpy port 5678** but the baseline locks `network_mode: "none"`. They're incompatible. Pick one and resolve in both docs.
- **`M0-tasks.md:13`** lists `docs/spike-2026-05-10-{retrieval,singleton}.md` as "already produced" files to commit at M0 init — those files don't exist. Either pre-create empty stubs or rewrite the M0 instruction as "will produce" pointers. The date `2026-05-10` in the filename is also stale (today is 2026-05-12) — rename or use a date-less filename.

### E. Deferred for a separate pass (not Chunk 6)

- **Telemetry heuristic has three TODOs** (per-tool-call inspection, same-turn boundary, normalization rules across IDEs). This is real spec work and probably wants its own focused pass before M1.4. Worth flagging but not blocking M0 kickoff.
- **Architect's "failure-recovery policy"** (what happens when an agent fails a phase DoD — rollback / retry contract). Defer to M1+ when the iterative loop actually runs and we have empirical input.

---

## My recommendation: Chunk 6, three sub-chunks

- **6a — Mechanical cleanup (Category A).** Pure agent work, no decisions. ~20 minutes.
- **6b — Small design calls (Category B).** Four `AskUserQuestion` taps, then an agent propagates. ~15 minutes.
- **6c — Specs + bug fixes (Categories C + D bundled).** Six items, each tightly scoped. One agent dispatch. ~30 minutes.

Then re-dispatch **one cold reviewer** (just the architect, since they're the broadest lens) for a final verification pass. If it comes back "Ready to dispatch agents," we're done.

### Alternative

Ship with the known fixup list and call it Wave 1. Open M0 with awareness of the gaps; sweep them as we go. Faster to kickoff, slightly more friction during M0.

---

## What say you?

- Proceed with Chunk 6 (recommended)?
- Ship Wave 1 with known fixups?
- Something else / nuance?
