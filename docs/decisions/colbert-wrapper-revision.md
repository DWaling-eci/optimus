# Decision Record: ColBERTv2 Wrapper Revision -- RAGatouille -> colbert-ai Direct

**Status:** Decided -- locked. **Supersedes** `docs/decisions/secure-singleton-mcp-baseline.md` § 3.1 (model-stack naming) and § 3 illustrative `server.py` example code (rerank invocation only). All other clauses of the baseline decision record remain in force.
**Owner:** Dustin (in-place call 2026-05-13). Discovery surfaced during spike-1 install probe in optimus-trunk session that wrapped spike-2 + landed the spaCy DROP decision.

## Why this record exists

The baseline decision record names the second-stage reranker as **"ColBERTv2 via RAGatouille"** and its illustrative `server.py` calls `RAGPretrainedModel.from_pretrained(...)` + `rag.rerank(...)`. The first attempt to assemble that stack on a real spike host (Windows 11, Python 3.12.6, 2026-05-13) hit a hard roadblock that the baseline record's own § 5 "roadblock-driven revision" clause was written for.

This record captures the roadblock, the revised wrapper choice, and the implications for adjacent locked decisions (notably `spacy-keep-drop.md`).

## The roadblock (evidence)

Two distinct findings, both surfaced by `pip install --dry-run --report` runs against `spike/pre-m1-retrieval/requirements.txt`:

1. **RAGatouille 0.0.9.x (latest) is bloated.** As of 2025-02-11, RAGatouille 0.0.9 onward transitively pulls `langchain`, `langchain-core`, `langgraph`, `langsmith`, `llama-index` (4 sub-packages), `openai`, `tiktoken`, `Flask`, `Werkzeug`, plus ~70 more transitive deps. Total resolved set with `ragatouille>=0.0.8`: **134 packages.** This blows past the spirit of the baseline § 2 isolation posture (`langsmith` defaults to telemetry POSTs incompatible with `network_mode: "none"`; `openai` client validates API keys at import in some versions; supply-chain attack surface explodes).
2. **RAGatouille 0.0.8.post4 (last pre-bloat) is unreachable.** All 0.0.7.x and 0.0.8.x versions exact-pin `colbert-ai==0.2.19` -- which has been **yanked from PyPI** as of 2026-05-13. Available colbert-ai versions: 0.2.15, 0.2.16, 0.2.17, 0.2.18, 0.2.20, 0.2.21, 0.2.22 (no 0.2.19). The clean RAGatouille era is therefore mechanically uninstallable today.

Per baseline § 5, "roadblock means hard-blocking, evidence-backed: a measurement, a reproducible failure, or a concrete incompatibility." This is concrete (a specific version is yanked) and reproducible (the dry-run JSON artifacts at `spike/pre-m1-retrieval/dry-run-report*.json` are evidence; the Mini Shai-Hulud contamination check that ran alongside is in the same artifact set).

## The revision

**Renamed stack (baseline § 3.1):** **"Nomic CodeRankEmbed (dense) + ColBERTv2 (rerank, via colbert-ai direct)"**.

**Mechanism preserved:** the two-stage pipeline (Nomic dense -> top-100 -> ColBERTv2 rerank -> top-5) is unchanged. ColBERTv2's MaxSim late-interaction scoring is the load-bearing operation; RAGatouille's `.rerank()` was a thin wrapper around `colbert.modeling.checkpoint.Checkpoint`'s MaxSim. Calling `Checkpoint` directly invokes the **same model, same scoring, same ranking output** -- only the invocation surface changes.

**API substitution:** baseline § 3 example code's RAGatouille call is replaced with the colbert-ai direct equivalent. See the inline edits to baseline § 3 example code (also landed in this commit).

**Package delta:** 134 -> 74 transitive packages (-60, ~45% reduction). Trust boundary shrinks proportionally.

## What this revision does NOT change

- **Model stack names.** Nomic CodeRankEmbed + ColBERTv2. Identical.
- **Two-stage pipeline shape.** Dense filter -> top-100 -> rerank -> top-5. Identical.
- **Container isolation posture (§ 2).** `network_mode: "none"`, RO parent mount, RO model cache, RW scratch + sockets. Identical.
- **Bipartite concurrency (§ 3.3).** Async main + dedicated ML worker process. Identical.
- **Transport binding (§ 3.4).** Unix socket / named pipe per `transport-and-discovery.md`. Identical.
- **Model distribution / trust posture (§ 6).** Installer-as-gatekeeper, SHA-verified manifest, RO model-cache bind-mount, `trust_remote_code=True` acceptable. Identical.
- **Roadblock-revision rule itself (§ 5).** Still active for any future hard-blocking, evidence-backed roadblock.

## Implications for `spacy-keep-drop.md`

The spaCy DROP decision (`docs/decisions/spacy-keep-drop.md`, 2026-05-13) was made with HIGH confidence sourced from the literature -- but its own "Open evidence gaps" section honestly notes: *"No published ablation that runs spaCy specifically against CodeRankEmbed -> ColBERTv2."*

The current revision narrows that gap slightly (we now have **less** empirical confidence in the locked stack's performance because we're swapping the wrapper for an equivalent-but-not-yet-empirically-verified one) and makes spike-1 a **more salient** revival trigger for the spaCy DROP verdict than it was when the spaCy record was authored. Specifically: if spike-1's H1 fails (no behavior change vs. no-Optimus baseline) AND the failure mode maps cleanly to "retrieval candidates are mis-ranked for queries dominated by code-identifier tokens," that is exactly the failure pattern spaCy preprocessing was historically expected to address.

A surgical edit to `spacy-keep-drop.md` § 4 lands alongside this record adding spike-1 H1 fail-mode-mapped-to-preprocessing-absence to the revision-trigger list. **No spaCy revival work is authorized by this revision.** spaCy stays DROPPED. The revision merely names spike-1 as an additional legitimate trigger if the empirical evidence demands it.

## Cross-references

- `docs/decisions/secure-singleton-mcp-baseline.md` § 3 + § 5 -- the baseline record this revision modifies in place.
- `docs/decisions/spacy-keep-drop.md` § 4 -- the spaCy revision-trigger list updated alongside this record.
- `docs/spikes/spike-1-prep-brief.md` § 5 -- consumer of the renamed stack; updated to reflect "colbert-ai direct" in place of "RAGatouille".
- `spike/pre-m1-retrieval/dry-run-report.json` -- 134-pkg baseline (RAGatouille >=0.0.8 resolves to 0.0.9.post2). Persisted artifact.
- `spike/pre-m1-retrieval/dry-run-report-direct.json` -- 74-pkg revised set (colbert-ai>=0.2.20 direct). Persisted artifact.
- The pinned `ragatouille==0.0.8.post4` and `ragatouille==0.0.7.post11` dry-runs failed at dependency resolution (`ERROR: Could not find a version that satisfies the requirement colbert-ai==0.2.19 ... (from versions: 0.2.15, 0.2.16, 0.2.17, 0.2.18, 0.2.20, 0.2.21, 0.2.22)`) -- pip does NOT write the `--report` JSON when resolution fails, so no JSON artifact exists for these. The pip stderr was captured in-conversation; the failure mode is reproducible by re-running the same `pip install --dry-run --report ... -r requirements.txt` against a requirements file pinning either of those ragatouille versions on a host with internet access to PyPI.
- Memory: [[shai-hulud-pip-install-discipline]] -- contamination-check protocol that ran alongside; verified 74-pkg set is contamination-clean.

## Status note

Locked 2026-05-13. First roadblock-driven revision against the baseline record's locked stack. Evidence: yanked colbert-ai 0.2.19 + RAGatouille 0.0.9.x bloat surface. Mechanism preserved (Nomic + ColBERTv2 + two-stage pipeline + top-5 clamp); only the rerank wrapper changes. Trust-boundary surface reduced by ~45%. Adjacent spaCy DROP record's revision-trigger list updated to name spike-1 H1 as an additional valid trigger. spaCy itself stays DROPPED -- no revival authorized by this revision.
