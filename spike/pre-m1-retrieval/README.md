# Spike-1 -- Retrieval Behavior Validation

**Status:** SESSION 1 -- workspace scaffold + install probe only. No working pipeline yet.
**Spike framing source:** `docs/decomp/pre-M1-spikes.md` section "Spike-1: Retrieval Behavior Validation".
**Operational brief:** `docs/spikes/spike-1-prep-brief.md` (PM-locked).
**Decision records under test:**
- `docs/decisions/secure-singleton-mcp-baseline.md` -- the locked retrieval stack (Nomic CodeRankEmbed + ColBERTv2 via colbert-ai direct).
- `docs/decisions/colbert-wrapper-revision.md` -- 2026-05-13 wrapper revision (RAGatouille -> colbert-ai direct; mechanism preserved). Surfaced by this spike's install probe.
- `docs/decisions/spacy-keep-drop.md` -- H4 retired; thin Optimus has no spaCy. **Trigger update 2026-05-13:** spike-1 H1 added as a legitimate spaCy revival trigger.

## Thesis (per `pre-M1-spikes.md`)

Retrieval-only Optimus + a hand-authored DIRECTORY_INDEX.md changes Claude Code's tool-call mix on real codebases: more `optimus_*` calls, fewer broad `Read` / `Grep` / `Glob` sweeps, no memory gap, no drift catastrophe.

## Hypotheses

- **H1 (behavior change):** thin Optimus + accurate dir-index raises `optimus_*` ratio AND reduces broad sweeps relative to a no-Optimus baseline. PASS = ratio materially higher AND meets the >=1.0x floor from `success-metric.md`.
- **H2 (no memory gap):** killing v1 memory does not leave a retrieval gap that ONLY memory was filling. PASS = no H1-run failure pattern maps cleanly to "memory would have helped."
- **H3 (drift resilience):** stale dir-index is NOT worse than no dir-index. PASS = optimus-tool-call ratio under drifted-dir-index condition is not materially worse than no-dir-index baseline.
- **H4 -- RETIRED** per `docs/decisions/spacy-keep-drop.md`. Do not measure spaCy on/off; do not install `spacy`.

## Test target

**`c:\ms-superrepo\`** (reused from spike-2). Real ~3.4GB monorepo, multi-language. Origin already removed per spike-2 protocol. Subset path `~/.spike-test-corpus/` available if full repo is too large for spike-1's indexing budget.

## Layout

```
spike/pre-m1-retrieval/
  README.md                  -- this file
  server-stdio.py            -- single-client stdio MCP server skeleton (S1: shape only)
  indexer.py                 -- on-disk chunk index builder skeleton (S1: shape only)
  drift-fixture.py           -- (deferred to S3) mid-task filesystem drift introducer
  results/                   -- run artifacts (gitignored; install-probe.json lands here too)
  .venv/                     -- spike-local virtualenv (gitignored)
```

DIRECTORY_INDEX.md lives at the **test target's** repo root (`c:\ms-superrepo\DIRECTORY_INDEX.md`), NOT inside optimus. Per brief §6: it's a property of the codebase being indexed.

## Scope discipline

This spike is **not** the v2 production server. Per brief §5:

**MUST include (load-bearing):**
- Stdio MCP server, single-client (spike-2 already validated multi-client transport).
- One MCP tool: `optimus_search(query: str) -> list[ranked_chunk]`. Top-5 ranked chunks per `secure-singleton-mcp-baseline.md` two-stage pipeline.
- Locked stack: Nomic CodeRankEmbed (with the `"Represent this query for searching relevant code"` task-instruction prefix per the model card) + ColBERTv2 via colbert-ai direct (`colbert.modeling.checkpoint.Checkpoint` MaxSim per `docs/decisions/colbert-wrapper-revision.md`). **No spaCy.**
- On-disk chunk index built ONCE (chunk all files, embed all chunks, persist embeddings). MCP server reads index at startup; queries do NOT re-embed documents.
- Path-confinement at the MCP boundary (every agent-supplied path realpath-resolved against test-target root before any FS op).
- Per-call query + top-5 result-paths logging (cross-check against chat-report toolkit output).

**MUST NOT include (out of scope):**
- Singleton container, Docker, network_mode none, model-cache bind-mount. (Spike runs as host-side Python process.)
- `optimus_doctor`, `optimus_init`, `optimus_grep`, `optimus_list`, `optimus_delete`, `optimus_resolve`, telemetry plumbing.
- `.mcp.json` schema validation, `optimus_protocol_version` handshake, SO_PEERCRED / SID auth.
- Multi-client concurrency, cap, busy_retry. Spike-2 validated.
- spaCy, query-side preprocessing, identifier normalization.

**Performance budget:** per-query latency <= 5 seconds end-to-end. Indexing-time can be higher. >5s = §2-trigger-2 escalation per brief.

## How to run (current state -- session 1)

Skeletons (`server-stdio.py`, `indexer.py`) are shape-only -- no working pipeline yet. The install probe is the working deliverable; runs end-to-end via `run-probe.sh` from WSL2.

```bash
# WSL2 setup (one-time):
sudo apt install -y python3.12-venv build-essential
python3 -m venv ~/optimus-spike-venv
source ~/optimus-spike-venv/bin/activate
python -m pip install --only-binary :all: -r /mnt/c/_Source/optimus/spike/pre-m1-retrieval/requirements.txt

# Run the probe (any time; idempotent):
wsl.exe -- bash /mnt/c/_Source/optimus/spike/pre-m1-retrieval/run-probe.sh
```

**Why WSL2 and not Windows host:** colbert-ai's `Checkpoint.__init__` JIT-compiles a C++ extension (`segmented_maxsim_cpp`) at load time. The extension's source uses `pthread.h` (POSIX-only) and is uncompilable on Windows without a POSIX shim. WSL2 has pthread natively, gcc + build-essential pre-installable via apt, and matches the production-container env shape (production runs in a Linux container regardless of host OS). See "Install probe findings" below for the full Windows attempt chain that led to this.

**Files of interest:**
- `run-probe.sh` -- WSL2 entrypoint (activates venv, invokes install_probe.py)
- `run-probe.ps1` -- Windows entrypoint (sources VS Pro 2022 vcvarsall.bat). Historical -- demonstrates the Windows blocker chain; NOT the working path.

## Install probe (session 1 deliverable)

The probe verifies the locked stack assembles + loads on this host. Output lands at `results/install-probe.json` (gitignored). Findings summarized in this README under "Install probe findings" once the probe runs.

What the probe captures:
- Python + pip + virtualenv versions.
- Install commands that worked (or escalation if blocked).
- Version pins (sentence-transformers, colbert-ai, torch, etc.).
- Model download paths + sizes.
- Load-time timing per model.
- Memory footprint at idle + after both models loaded.
- A trivial query roundtrip on each model (Nomic embed, ColBERT MaxSim score).

If install or load fails for hard reasons (colbert-ai incompatible with Python 3.12, Nomic OOM, model gated, etc.) -> brief §2-trigger-2 escalation to Dustin. The first roadblock-driven revision (RAGatouille wrapper retired) already fired and landed at `docs/decisions/colbert-wrapper-revision.md`; further roadblocks would feed the same revision flow.

## Install probe findings

**Status:** PASS (WSL2). 2026-05-13.

### Verdict

The locked retrieval stack (Nomic CodeRankEmbed dense + ColBERTv2 via colbert-ai direct) assembles + loads + runs end-to-end on WSL2 with a CPU-only torch wheel. Synthetic-query MaxSim ranking is sensible (top-1 score 22.6 for the query "how do I parse a json config file" → `def parse_config(path): return json.loads(...)`; competing distractors all score < 13).

### Pinned versions (validated)

| Package | Version | Notes |
|---|---|---|
| Python | 3.12.3 | WSL2 Ubuntu 24 |
| torch | 2.12.0+cpu | CPU wheel via PyPI's pytorch CPU index |
| sentence-transformers | 5.5.0 | Nomic CodeRankEmbed loader |
| colbert-ai | 0.2.22 | ColBERTv2 Checkpoint + MaxSim |
| transformers | 4.57.6 | Pinned `<5` because transformers 5.x breaks colbert-ai's HF_ColBERT (`all_tied_weights_keys` API change) |
| huggingface-hub | 0.36.2 | Auto-downgraded with transformers pin |
| numpy | 2.4.4 | |
| einops | 0.8.2 | |
| psutil | 7.2.2 | Probe-only RSS measurement |

Total resolved set: **65 packages** on WSL2 (vs 134 with RAGatouille >=0.0.8 bloat, vs 74 with Windows wheels + CUDA-disabled).

### Timings + footprint (single-doc-batch sample, CPU)

| Phase | Nomic CodeRankEmbed | ColBERTv2 (colbert-ai direct) |
|---|---|---|
| Import | 6.1s | 0.4s (transformers already imported by Nomic) |
| Load (warm cache, JIT-built) | 3.8s | 0.95s |
| Encode + MaxSim score | 0.25s (5 docs to 768d) | 0.39s (5 docs, query 32 tokens × 128d, doc tokens variable) |
| RSS after load | ~1008 MB | ~1055 MB (Nomic + ColBERT both loaded) |

**Cold-cache caveat:** `Checkpoint(...)` first invocation also JIT-compiles `segmented_maxsim_cpp` (~10-30s on first run; subprocess to ninja → cl.exe-equivalent). Subsequent invocations use cached `.so`. Production-container builds should pre-compile this extension at image-build time (or bake the compiled .so into the image) to keep boot fast.

### Mini Shai-Hulud contamination check

CLEAN at all checkpoints. Dry-run reports:
- `dry-run-report.json` — initial 134-pkg set with RAGatouille >=0.0.8 (clean).
- `dry-run-report-direct.json` — Windows 74-pkg set after wrapper revision (clean).
- `dry-run-report-tx4.json` — transformers <5 + hf-hub downgrade-only delta (clean).
- `dry-run-report-wsl2.json` — Linux 87+pkg set with CUDA bloat (clean but bloated).
- `dry-run-report-wsl2-cpu.json` — Linux 65-pkg set with CPU-only torch (clean; final).

Per memory `[[shai-hulud-pip-install-discipline]]`. Window remains open; re-check on any future install.

### Roadblock chain (full session arc, for institutional memory)

The path to PASS was not direct. Five distinct roadblocks surfaced in one session; each yielded either a code/config fix or a decision-record revision:

1. **RAGatouille 0.0.9.x bloat.** Latest RAGatouille pulls langchain + llama-index + langgraph + langsmith + openai + Flask transitively (134 pkgs). Trust-boundary explosion vs. baseline §2 isolation posture. **Resolution:** decision-record revision dropping RAGatouille for colbert-ai direct (`docs/decisions/colbert-wrapper-revision.md`).
2. **RAGatouille 0.0.8.post4 (last clean version) is unreachable.** All 0.0.7.x and 0.0.8.x exact-pin `colbert-ai==0.2.19` which has been YANKED from PyPI. **Resolution:** subsumed into the wrapper revision -- the clean RAGatouille era is mechanically dead.
3. **transformers 5.x breaks colbert-ai 0.2.22's HF_ColBERT.** transformers introduced `all_tied_weights_keys` API; colbert-ai 0.2.22 only implements the older `_tied_weights_keys`; AttributeError at load. **Resolution:** pin `transformers>=4.41.0,<5` in requirements.txt (sentence-transformers accepts the range).
4. **colbert-ai's `Checkpoint.__init__` JIT-compiles a C++ extension that uses `pthread.h`.** Windows doesn't have pthread; `cl.exe` from VS Pro 2022 fails with "fatal error C1083: Cannot open include file: 'pthread.h'". Even with VS Build Tools fully installed + vcvarsall sourced, this extension is uncompilable on Windows without a POSIX shim (pthread-win32 / vcpkg-pthreads / patched colbert source). **Resolution:** pivot the spike to WSL2 (Linux has pthread; production env is also Linux container -- spike now matches prod env shape).
5. **Linux torch wheel pulls 19+ NVIDIA/CUDA packages by default** (cublas, cudnn, nccl, triton, cuda-toolkit, etc.). 5-10 GB of GPU runtime libs we don't need (spike is retrieval-behavior validation, not throughput). **Resolution:** pin `--extra-index-url https://download.pytorch.org/whl/cpu` in requirements.txt; resolves `torch-2.12.0+cpu`. Per brief §1 implementation-tactics authority; production GPU/CPU choice is M1.0's call.

Plus one of-mine API bug along the way: `keep_dims="return_mask"` is INTERNAL to colbert-ai's `docFromText`, not a public option. Public values are `True`, `False`, `"flatten"`. Fixed in both probe + decision-record example code.

### Recommendation for M1

- The locked stack (Nomic CodeRankEmbed + ColBERTv2 via colbert-ai direct) **does work** end-to-end with the pins captured above. The `colbert-wrapper-revision.md` revision is empirically validated by this probe.
- M1.0 / M1.1 build should adopt these pins as the production starting point.
- M1's Dockerfile should pre-compile `segmented_maxsim_cpp` at image-build time (don't rely on JIT at container boot).
- M1 should also revisit the `transformers<5` pin periodically; once colbert-ai upstream catches up to transformers 5.x, the pin can relax.
- The Windows-host install path is **not viable for spike-1 or production** without substantial workarounds. Per the WSL2 pivot, the spike-1 brief's "host-side Python process" framing has been generalized to "WSL2-side Python process on Windows hosts; native Linux equivalent on Linux hosts."

## What this spike is NOT (session 1)

- Not the v2 production retrieval server. Single-client stdio, no container, no transport hardening, no concurrency.
- Not a measurement of agent behavior. That requires the chat-report toolkit (B.3) and is gated per brief §7.
- Not an `optimus_search` implementation. Skeleton only this session.

## Cross-references

- `docs/spikes/spike-1-prep-brief.md` -- operational brief (PM-locked).
- `docs/decomp/pre-M1-spikes.md` -- spike framing + DoD.
- `docs/decisions/secure-singleton-mcp-baseline.md` -- locked retrieval stack.
- `docs/decisions/spacy-keep-drop.md` -- H4 retirement record.
- `docs/decisions/transport-and-discovery.md` -- transport contract (validated by spike-2; spike-1 uses single-client stdio).
- `docs/decisions/success-metric.md` -- the >=1.0x AND-combined floor.
- `docs/decisions/chat-report-sibling-charter.md` -- toolkit dual-IDE bar.
- `docs/spikes/spike-2-singleton-report.md` -- methodology template.
- `CHARTER.md` Founding Decisions 1, 3, 5, 7.
