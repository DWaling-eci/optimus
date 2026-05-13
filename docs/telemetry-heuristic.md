# Telemetry Heuristic -- Failure Modes + Implementation Notes

**Status:** stub. The principle ("EUR-10 is build-time validation aid, not runtime telemetry feature") lives in REQUIREMENTS EUR-10. Heuristic implementation detail + failure modes transplant here at refactor time.

## What the heuristic does

Classifies Read tool calls in an IDE chat trajectory as **informed** (preceded by a DIRECTORY_INDEX.md consult within the same agent turn) vs **uninformed** (broad sweep without prior dir-index context).

## Known failure modes

These are explicit limitations of the heuristic, not bugs to fix:

1. **System-prompt dir-index:** if DIRECTORY_INDEX.md is in the system prompt (never explicitly read), all reads classify as uninformed sweeps even if the agent is using the dir-index effectively.

2. **Dir-index then sweep:** an agent that reads DIRECTORY_INDEX.md AND then does a broad sweep -- the dir-index consult doesn't prevent the sweep. The heuristic classifies the sweep as informed (false positive).

3. **Cached context:** an agent may have the dir-index in context from an earlier turn without re-reading. The heuristic classifies all such reads as uninformed (false negative).

4. **"Same agent turn" boundary:** in multi-step agentic runs where turns can span tool calls, the boundary is ambiguous. Different chat-history-store granularities (Cursor vs Claude Code) further muddy this.

5. **Cross-IDE comparability:** metrics from Cursor and Claude Code chat-history stores are NOT directly comparable. Different stores log at different granularities; normalization is required before cross-IDE aggregation.

## Implementation requirements

- TODO: spec the per-tool-call inspection logic.
- TODO: spec the "same turn" boundary definition per IDE.
- TODO: normalization rules for cross-IDE aggregation.

## Consumers

- `docs/decisions/success-metric.md` -- consumes the informed-precision-read classification as Component B of the success metric.
- roadmap M6.1 (Telemetry Refinement) -- this is where the heuristic implementation lives.
