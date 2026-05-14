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

**`c:\_Source\ms-superrepo\`** (reused from spike-2). Real ~3.4GB monorepo, multi-language. Origin already removed per spike-2 protocol. Subset path `~/.spike-test-corpus/` available if full repo is too large for spike-1's indexing budget.

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

DIRECTORY_INDEX.md lives at the **test target's** repo root (`c:\_Source\ms-superrepo\DIRECTORY_INDEX.md`), NOT inside optimus. Per brief §6: it's a property of the codebase being indexed.

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

## How to run -- working pipeline (session 2+)

End-to-end pipeline lands in session 2/3: indexer + stdio MCP server + tests. Test
suite: 28 tests across `tests/test_chunk.py` (7), `tests/test_walk.py` (7),
`tests/test_index_format.py` (5), `tests/test_confine.py` (5), plus model-loading
smokes (`tests/test_smoke_index.py`, `tests/test_two_stage_search.py`). All green
on WSL2 venv.

### GPU stack (post-close-out 2026-05-13)

The spike-1 server runs on GPU per `docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md` Phase 0. The wrapper patch (1-line `d_emb.to(device, dtype)` in MaxSim matmul) is validated against the probe's `spike/pre-m1-gpu-feasibility/server-stdio-gpu.py` artifact. Device autodetect via `server_stdio.select_device()`; CPU fallback retained but unexercised in the empirical runs.

requirements.txt switched to `torch==2.5.1+cu121` and the matching cu12 wheel stack. Persistent venv at `~/optimus-spike-gpu-venv/` is reused across all 24 Phase-2 empirical sessions.

### WSL2 setup (one-time, GPU stack)

```bash
sudo apt install -y python3.12-venv build-essential
python3 -m venv ~/optimus-spike-gpu-venv
source ~/optimus-spike-gpu-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --only-binary :all: \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    -r /mnt/c/_Source/optimus/spike/pre-m1-retrieval/requirements.txt
```

After install, confirm GPU visibility:

```bash
python -c "import torch; print(f'cuda={torch.cuda.is_available()} device={torch.cuda.get_device_name(0)}')"
```

Expected: `cuda=True device=<your GPU>`.

### Build the index

```bash
source ~/optimus-spike-gpu-venv/bin/activate
cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval
python indexer.py <test-target-root> <out-dir>
```

The indexer walks `<test-target-root>`, chunks every file (char-window
`indexer.DEFAULT_CHUNK_SIZE`; revised to 600 in session 3 -- see Empirical
observations below), embeds with Nomic CodeRankEmbed (no query prefix at
index time), and persists `manifest.json` + `chunks.jsonl` + `embeddings.npy`
to `<out-dir>`. Re-runnable (idempotent; replace `<out-dir>` to invalidate).

### Run the MCP server

```bash
OPTIMUS_SPIKE_INDEX_DIR=<out-dir-from-above> \
OPTIMUS_SPIKE_TARGET_ROOT=<test-target-root> \
python server-stdio.py
```

The server is stdio-only, single-client. It registers one tool: `optimus_search(query: str) -> list[dict]`. Each call logs to `<OPTIMUS_SPIKE_INDEX_DIR>/server.jsonl` for cross-check against the chat-report toolkit.

### Run the test suite

```bash
source ~/optimus-spike-gpu-venv/bin/activate
cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval
python -m pytest tests/ -v
```

### Empirical observations (sessions 2/3, 2026-05-13)

Test target: `~/.spike-test-corpus-lite` (`ms-core` + `ms-core-api` copied from
spike-2's `~/.spike-test-corpus/`). 8.4 MB, 819 files pre-filter, mostly Kotlin
(583 .kt) plus SQL/Markdown/YAML/scripts.

**Subset rationale (brief §1 implementation-tactics authority + §2 trigger-2):**
The full spike-2 subset (`~/.spike-test-corpus/`, 324 MB) is dominated by
`dockerLab/` (316 MB), which is overwhelmingly Docker-image blobs that the
walker filters as binaries. A timing probe on `ms-core` alone (2.2 MB, 740
chunks) ran for 7m16s (~1.7 chunks/sec on CPU); extrapolating to the full
324 MB → ~5 hr indexing, well over the brief's 2 hr soft budget. Subsetted to
the two Kotlin codebases (ms-core + ms-core-api). dockerLab indexing is
out-of-scope for spike-1 measurement and skipped.

#### Indexing time

| Corpus | Bytes | chunk_size | Chunks | Elapsed | Rate |
|---|---|---|---|---|---|
| ms-core (probe) | 2.2 MB | 1500 | 740 | 7m16s | 1.7 chunks/sec |
| ms-core + ms-core-api (session 2) | 8.4 MB | 1500 | 3418 | ~38 min | ~1.5 chunks/sec |
| ms-core + ms-core-api (session 3, post-revision) | 8.4 MB | 600 | 7915 | ~33 min | ~4.0 chunks/sec |

Re-indexing at the revised chunk_size took LESS wall-clock than the session-2
indexing despite producing 2.3x more chunks. Nomic was warm-cached on the
re-index; per-chunk forward-pass cost is bounded by chunk content (not
chunk_size constant) so the 2.3x chunk count is offset by ~60% smaller per-chunk
forward time + better SentenceTransformer batching at the smaller size.

#### Query latency (3-query smoke)

| Query | Session 2 (1500/8) | Session 3 (600/32) | Δ |
|---|---|---|---|
| "how does the build system run tests" | 14.5 s | 12.4 s | -14% |
| "http retry logic" | 12.0 s | 10.7 s | -11% |
| "kotlin coroutine cancellation" | 11.3 s | 11.3 s | 0% |

Retrieval correctness directionally sensible across both runs:
build → ms-core-api README, retry/HTTP → metrics test extensions,
coroutine → test framework. Top-1 paths converge between sessions; top-1
scores differ slightly (post-revision ColBERT sees full chunks, no
truncation, so scores shift).

**LATENCY FINDING (still §2-trigger-2):** the protocol revision dropped latency
by ~10-15%, NOT the ~4x predicted by the original "bsize 8 -> 32 = 4x fewer
forward passes" math. Per-query latency remains **10-13 s, 2-3x over the
brief §5 5s budget.**

#### Truncation: confirmed fixed

| Metric | Session 2 (chunk_size=1500) | Session 3 (chunk_size=600) | Δ |
|---|---|---|---|
| ColBERTv2 `doc_maxlen` | 220 tokens | 220 tokens | unchanged |
| Mean chunk size (chars) | 1325 | 572 | 2.3x smaller |
| Mean chunk size (tokens) | 383 | 167 | 2.3x smaller |
| Chunks exceeding doc_maxlen | 2,979 / 3,418 (87.2%) | 836 / 7,915 (10.6%) | 8.2x reduction |
| Tokens discarded at rerank | 604,036 (46.2% of all indexed) | 35,351 (2.7% of all indexed) | **17.1x reduction** |
| ColBERT query-time `bsize` | 8 (hardcoded) | 32 (= `ColBERTConfig().bsize` default) | matches upstream |

**Translation:** the original 46% information-loss confound is essentially
eliminated. The residual 2.7% truncation comes from a small tail of
pathological chunks (e.g. SQL with weird tokenization, generated/binary-adjacent
text); the dominant Kotlin content is well within doc_maxlen. ColBERT rerank
now scores nearly all of the indexed content, so the measurement is no longer
"Optimus + 46% blindness" -- it is Optimus.

Reproducer (post-revision):
```bash
source ~/optimus-spike-gpu-venv/bin/activate
cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval
python diag-tokens.py ~/.optimus-spike/index-msrepo-r600
```

#### Why latency didn't drop ~4x as predicted

The PRIORITY 1 finding from session 2 framed the bsize lever as "4x fewer
forward passes per query." That count claim is correct -- at bsize=32 vs 8 we
issue ~3-4 batches per query instead of ~13. But on **CPU**, wall-clock cost
per batch scales with total tokens computed inside the batch, not with batch
overhead. CPU does not parallelize the way GPU does across batch items, so
the bsize lever buys back only per-batch loop overhead, not actual computation.

The chunk_size 1500→600 lever helps slightly because each rerank doc now
encodes fewer real tokens (mean 167 vs 220-truncated-from-383 before). But the
session-2 setup was ALREADY truncating to 220 tokens at the ColBERT side, so
the per-doc encode cost was bounded at the same value either way. The
~10-15% latency improvement comes from (a) reduced batch-loop overhead at
bsize=32 and (b) some real per-doc encode savings on chunks that are now ~167
tokens instead of 220-truncated.

Math check (rough):
- 100 docs × ~167 mean tokens × ~6e-4 s/token (this CPU) ≈ 10 s rerank
- Plus ~1 s Nomic query encode + sub-ms numpy cosine = ~11 s observed. Matches.

Conclusion: **the rerank-stage CPU cost on this host is genuinely ~10s for a
top-100 candidate pool, regardless of bsize.** To get under 5s, the remaining
tactical levers are dense_k or skipping rerank or GPU. All have quality or
scope tradeoffs.

### PRIORITY 1 APPLIED 2026-05-13 (protocol revision -- truncation finding)

**Status: APPLIED. Truncation fixed (17x reduction). Latency partial (still over budget).**

Commits in this revision:
- `indexer.py` `DEFAULT_CHUNK_SIZE` 1500 -> 600. (Original PRIORITY 1 plan was
  ~700 chars; TDD with an adversarial-dense Kotlin fixture surfaced that 700
  produces 224 tokens for the densest realistic code -- 4 over `doc_maxlen=220`.
  Dropped to 600 so the dense worst case stays at ~192 tokens with 20-token
  safety margin. Per brief §1 implementation-tactics authority.)
- `server-stdio.py` `DEFAULT_RERANK_BSIZE = 32` hoisted as a module constant
  + used at the `docFromText` call site. Pinned via
  `tests/test_rerank_bsize.py` to track `ColBERTConfig().bsize` upstream.
- `server-stdio.py` query-time `_stdout_to_stderr` wrapping. Session 2's
  wrapper only covered model load; ColBERT's `QueryTokenizer.tensorize` and
  `Checkpoint.docFromText` ALSO emit debug messages per query, which (a)
  corrupted MCP JSON-RPC framing on the second smoke pass and (b) added
  measurable wall-clock cost. Now wrapped per query.
- `tests/test_chunk_colbert_invariant.py` -- new test, pins
  `DEFAULT_CHUNK_SIZE` against ColBERT's `doc_maxlen` via the real ColBERTv2
  tokenizer on a dense Kotlin fixture. Failed at 1500, failed at 700, passes
  at 600.
- `tests/test_rerank_bsize.py` -- new test, pins `DEFAULT_RERANK_BSIZE`
  equal to `ColBERTConfig().bsize`.
- `diag-tokens.py` parametrized to accept `<index_dir>` argv or
  `OPTIMUS_DIAG_INDEX_DIR` env var (default unchanged).
- `reindex-r600.sh` -- one-off re-index launcher (idempotent), authored via
  the Write tool to dodge the wsl.exe heredoc-quoting trap.

**Empirical verdict on the revision (see tables in "Empirical observations"
above):**

| Goal | Predicted | Actual | Verdict |
|---|---|---|---|
| Truncation 46% → ~0% | ~0% | 2.7% | ✅ achieved (17x reduction) |
| Chunks truncated 87% → ~0% | ~0% | 10.6% | ✅ mostly achieved (8.2x reduction) |
| Latency 11-14s → 2-3s | 2-3 s | 10-13 s | ❌ NOT achieved (~10-15% improvement only) |
| Index time ≤ 2 hr | ~80 min | ~33 min | ✅ better than predicted |

**Cross-condition comparability:** preserved. The revised protocol is the
same protocol applied across no-Optimus / Optimus+accurate / Optimus+drifted
conditions. The 11-14s ⇒ 10-13s shift removes a confound (information loss)
without introducing a new one.

**Open question for next session (or PM in-place):** the brief §5 5s/query
budget is still missed by 2-3x. Options:

1. **Accept 10-13s and proceed.** Brief §2 trigger-2 case, documented; the
   spike still measures retrieval BEHAVIOR (cross-condition comparable),
   even if it doesn't hit the latency target. Claude Code's MCP tool timeout
   is generous (60s+); the agent does not actually time out. Latency may
   still influence behavior (hesitation, fewer `optimus_*` calls) -- which
   is itself signal.

2. **Reduce `dense_k` from 100 → 30** at the rerank stage. Expected wall-clock
   ~3-4 s rerank → ~5 s total. Quality tradeoff: smaller candidate pool may
   miss good answers the dense stage ranked 30-100. Still cross-condition
   comparable if applied uniformly.

3. **Skip ColBERT rerank** for the spike, return Nomic-only top-5. Expected
   ~1-2 s. Quality tradeoff: loses late-interaction reranking entirely.

4. **GPU**: out of spike-1 scope; M1.0 architecture decides production GPU/CPU.

**Recommendation (Zolt, codewizard call):** option 1 (accept and proceed)
unless Dustin/PM prefers option 2 (dense_k=30, single additional lever).
Either choice preserves cross-condition comparability. Option 1 captures the
"Optimus as built" measurement honestly; option 2 captures "Optimus tuned to
budget" measurement and risks burying the rerank-CPU finding under a
tighter dial.

**Host resources (FYI -- still not the bottleneck):** WSL2 reports 20 CPU
cores, 10.4 GB RAM, 9.0 GB available. The bottleneck is per-token CPU encode
cost in ColBERTv2's MaxSim path, not cores or memory. M1's Dockerfile +
M1.0's architecture spike are the appropriate places to revisit GPU/CPU.

**Latest smoke artifacts (gitignored):**
- `results/smoke-msrepo-r600.py` -- the post-revision smoke client (same
  3 queries as session 2's `smoke-msrepo.py`).
- `results/smoke-msrepo-r600.txt` -- raw output.
- `~/.optimus-spike/index-msrepo-r600/` -- new index dir (manifest stamps
  `chunk_size: 600`, `total_chunks: 7915`). Old `index-msrepo/` retained
  for cross-comparison.

### MCP-client smoke artifacts

- `results/smoke-msrepo.py` (gitignored) -- the smoke client used to capture
  the latencies above. Authored via Write tool (heredoc-via-cmd.exe nested
  escapes mangle f-strings; use Write-authored standalone scripts).
- `results/smoke-msrepo.txt` (gitignored) -- raw smoke output.
- `results/index-msrepo-timing.txt` (gitignored) -- indexing summary.
- `results/install-probe.json` (gitignored, session 1) -- install probe output.

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
