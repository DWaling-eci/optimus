# GPU Feasibility Probe -- M1.0 Architecture Data

**Status:** QUEUED 2026-05-13. Branch reserved: `experiment/gpu-probe`. Not yet executed.

**Framing:** This is **M1.0 architecture data**, NOT a spike-1 protocol revision. The brief
explicitly carves GPU/CPU as M1.0's call (`docs/spikes/spike-1-prep-brief.md` §1
implementation-tactics scope is the spike-1 line, not this one). Spike-1's empirical task
runs continue on CPU per the post-`428cf7e` protocol; this probe answers a separate
question: **"if we put the retrieval pipeline on the dev laptop's GPU, does latency
disappear, and at what env cost?"** The result feeds M1.0's GPU/CPU production default
decision.

## Why this exists

Commit `428cf7e` landed the truncation fix (17x reduction in token waste) but only
~15% latency improvement (11-14s → 10-13s vs the predicted 4x). Root cause: ColBERTv2's
MaxSim rerank is fundamentally a matrix-math workload, and CPU doesn't parallelize across
batch items the way GPU does. **The remaining wall-clock budget (10s) is bounded by
per-token CPU compute, not by tuneable batch knobs.** To get under the brief's 5s budget
without quality tradeoffs (dense_k cut, skip rerank), the only lever left is silicon.

Late-session GPU survey on the host machine returned a more capable target than expected
-- see "Hardware confirmed" below. The probe is cheap to run, gives M1.0 a concrete data
point, and de-risks the architecture conversation before M1.0 has to commit a default.

## Hardware confirmed (2026-05-13 host survey)

```
NVIDIA RTX A500 Laptop GPU
  Architecture:   Ampere (compute capability 8.6, RTX 30-series family)
  CUDA cores:     2,048
  Tensor Cores:   2nd-gen (FP16 / BF16 / INT8 acceleration)
  FP32 peak:      ~2 TFLOPs
  FP16 peak:      ~4-8 TFLOPs (Tensor Cores engaged)
  VRAM:           4,096 MiB total, 2,424 MiB free at survey time
  Driver:         573.44 (host) / 570.170 (WSL2 nvidia-smi)
  CUDA runtime:   12.8 (visible from WSL2 distro, no extra plumbing required)
```

Memory budget for the retrieval workload (both models loaded + peak rerank activations):

| Component | FP32 | FP16 |
|---|---|---|
| Nomic CodeRankEmbed (~140M params) | ~560 MB | ~280 MB |
| ColBERTv2 BERT-base + projection (~110M params) | ~440 MB | ~220 MB |
| Activations at bsize=32, seq=220 (peak per query) | ~250 MB | ~125 MB |
| CUDA context + cuDNN workspace | ~500 MB | ~500 MB |
| **Total in-flight** | **~1.75 GB** | **~1.13 GB** |

Comfortable headroom under 2.4 GB free even at FP32. With FP16/AMP (default in
colbert-ai recent versions; we already see the AMP GradScaler scaffolding firing
and disabling in current CPU pytest runs) we have ~1.3 GB to spare.

## Expected outcome

| Mode | Predicted rerank wall-clock | Predicted total per-query |
|---|---|---|
| Current CPU baseline (chunk_size=600, bsize=32) | ~10 s | 10-13 s |
| GPU FP32, Tensor Cores idle | ~1.3-2 s | ~2-3 s |
| GPU FP16, Tensor Cores engaged (AMP) | ~0.3-0.7 s | ~1-1.5 s |

Sub-second per-query retrieval on a $0/hr dev-laptop GPU would meaningfully reshape the
M1.0 architecture conversation -- production default could be "use what's local," with
GPU detection + fallback shape replacing "GPU is a cloud-only consideration."

## Out of scope (do NOT change in this probe)

- **Spike-1 protocol.** The CPU-based protocol (commit `428cf7e`) stays in place for
  empirical task runs. GPU is a separate measurement; mixing them contaminates
  cross-condition comparability in the spike-1 retrieval-behavior report.
- **The locked retrieval stack.** Nomic CodeRankEmbed + ColBERTv2 via colbert-ai direct.
  Per `docs/decisions/secure-singleton-mcp-baseline.md`. No model swaps.
- **Wrapper code.** `server-stdio.py` and `indexer.py` need NO source changes -- both
  sentence-transformers and colbert-ai auto-detect CUDA and move models to GPU via
  `torch.cuda.is_available()` checks. Confirm with `install_probe.py` output, not
  assumption.
- **Index format.** `manifest.json` + `chunks.jsonl` + `embeddings.npy` is GPU-agnostic.
  The probe reuses `~/.optimus-spike/index-msrepo-r600/` from commit `428cf7e`. **No
  re-indexing needed.**
- **CPU env.** Existing `~/optimus-spike-venv/` stays intact. GPU venv lives at
  `~/optimus-spike-venv-gpu/` (parallel). Zero risk of cross-contamination.

## Plan (executable from a fresh session)

### Step 0: branch up

```bash
git checkout experiment/gpu-probe  # already created at trunk HEAD `428cf7e`
# All work in this probe lands on this branch. Merge to trunk only after results
# are in hand and M1.0 has signed off.
```

### Step 1: parallel GPU venv on WSL2

```bash
python3 -m venv ~/optimus-spike-venv-gpu
source ~/optimus-spike-venv-gpu/bin/activate
```

### Step 2: requirements with CUDA torch wheel

Author `spike/pre-m1-gpu-feasibility/requirements-gpu.txt` -- mirrors the CPU
`requirements.txt` but swaps the torch wheel source. Concrete shape:

```
# Match CPU requirements pin-for-pin EXCEPT torch wheel source
--extra-index-url https://download.pytorch.org/whl/cu121

# Locked stack
sentence-transformers>=5.0.0,<6
colbert-ai==0.2.22
transformers>=4.41.0,<5  # colbert-ai 0.2.22 vs transformers 5.x API breakage
huggingface-hub>=0.30.0,<1
einops>=0.8.0,<1
numpy>=2.0.0,<3
psutil>=6.0.0

# MCP
mcp>=1.0.0,<2

# torch with CUDA 12.1+ (matches host driver 573.44 / CUDA 12.8)
torch  # NO +cpu suffix; resolves via --extra-index-url to torch+cu121
```

Install:

```bash
pip install --only-binary :all: -r spike/pre-m1-gpu-feasibility/requirements-gpu.txt
```

**Mini Shai-Hulud dry-run check first** per `[[shai-hulud-pip-install-discipline]]`:

```bash
pip install --dry-run --only-binary :all: --report /tmp/gpu-dryrun.json \
  -r spike/pre-m1-gpu-feasibility/requirements-gpu.txt
# Inspect for any package in the compromised list before the real install
```

Disk cost: ~3-5 GB of CUDA/NVIDIA libs (cuBLAS, cuDNN, nccl, etc.). One-time.

### Step 3: install probe verifies CUDA visibility

Reuse the existing `spike/pre-m1-retrieval/install_probe.py`. It already reports
`torch.cuda.is_available()` and model load timings. Expected output deltas vs the
session-1 CPU probe:

- `torch.cuda.is_available()`: True (vs False on CPU)
- Nomic load: ~2-3 s (vs ~3.8 s warm CPU) -- model moves to GPU
- ColBERT load: ~3-5 s including CUDA extension JIT (`segmented_maxsim_cu` first build)
- Both models reported on `device: cuda:0`
- RSS: lower than CPU (most weights now live in VRAM)
- nvidia-smi during probe: ~1.0-1.3 GB used by python process

### Step 4: re-run the post-revision smoke against existing index

```bash
source ~/optimus-spike-venv-gpu/bin/activate
cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval
python results/smoke-msrepo-r600.py | tee results/smoke-msrepo-r600-gpu.txt
```

Index is reused from `428cf7e` (`~/.optimus-spike/index-msrepo-r600/`, 7915 chunks at
chunk_size=600). Same 3 queries:

1. "how does the build system run tests"
2. "http retry logic"
3. "kotlin coroutine cancellation"

Expected: 0.5-2 s/query (vs 10-13 s on CPU).

### Step 5: capture

Land results in `spike/pre-m1-gpu-feasibility/results/` (gitignored sibling to spike-1's
results/). Capture:

- `smoke-msrepo-r600-gpu.txt` -- raw smoke output
- `install-probe-gpu.json` -- install probe output
- `nvidia-smi-snapshot.txt` -- VRAM utilization during a live query
- Mini comparison table CPU-vs-GPU in this README's "Results" section (initially empty)

### Step 6: short report at workspace root

Author `spike/pre-m1-gpu-feasibility/RESULTS.md` (committed; sibling to README.md):

- Comparison table: CPU baseline vs GPU FP32 vs GPU FP16 wall-clock per query
- Whether AMP engaged automatically (look for the "GradScaler enabled" log without the
  CUDA-unavailable disable warning)
- Memory peak observed (nvidia-smi snapshot during a query)
- Top-1 result paths -- should match CPU (no model-output divergence; GPU ≠ better
  retrieval, just faster compute)
- Verdict for M1.0: viable / not viable / depends on factor X

### Step 7: branch merge call

Merge `experiment/gpu-probe` to trunk only after M1.0 has the data in hand AND signed off
on either keeping GPU optional (host detection + fallback) or deferring to a separate
M1.0 architecture commit. The probe artifacts stay on the branch until then.

## Definition of Done

- [ ] Branch `experiment/gpu-probe` checked out + clean
- [ ] `~/optimus-spike-venv-gpu/` venv assembled with cu121 torch
- [ ] Mini Shai-Hulud dry-run report attached (clean)
- [ ] `install_probe.py` reports `cuda available: True` + both models on `cuda:0`
- [ ] Smoke run completes 3 queries, wall-clock captured per query
- [ ] Top-1 paths match the CPU baseline (no retrieval-quality regression)
- [ ] `nvidia-smi` snapshot during a live query (memory + util)
- [ ] `RESULTS.md` authored with CPU-vs-GPU comparison table + M1.0 verdict
- [ ] Memory updated with branch + RESULTS.md pointer

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| CUDA torch wheel pulls a Shai-Hulud-contaminated transitive dep | Mandatory dry-run + transitive-list inspection BEFORE install |
| 4 GB VRAM squeezed under heavy desktop load (Chrome + Teams + etc) | Run smoke when desktop is quiet; PyTorch OOM raises cleanly, retry |
| colbert-ai's CUDA segmented_maxsim extension JIT-build fails | Pre-flight: confirm `nvcc --version` shows 12.x in WSL2; sudo apt install cuda-toolkit-12-1 if missing |
| FP16/AMP doesn't engage automatically | Probe explicitly: check ColBERTConfig.amp setting + check Checkpoint dtype. If not auto, document; this is M1.0's call whether to force it |
| Top-1 paths differ between CPU and GPU (numerical precision artifact) | Expected if FP16 engages; capture both and note. Spike-1's measurement integrity is unaffected -- spike runs CPU. |

## Cross-references

- `spike/pre-m1-retrieval/README.md` -- spike-1 workspace + "PRIORITY 1 APPLIED" section
  containing the CPU-bound latency analysis that motivated this probe
- `docs/spikes/spike-1-prep-brief.md` §1 -- implementation-tactics scope (note: GPU is
  explicitly OUT of spike-1 scope; this probe is M1.0 prep, not a spike-1 revision)
- `docs/decisions/secure-singleton-mcp-baseline.md` -- the locked retrieval stack this
  probe runs on GPU
- `docs/decisions/colbert-wrapper-revision.md` -- the colbert-ai direct wrapper this
  probe also uses (no wrapper changes)
- Commit `428cf7e` -- post-truncation-fix trunk HEAD; this branch starts here
- `[[shai-hulud-pip-install-discipline]]` -- memory note; install discipline applies
- `[[optimus-kickoff-state]]` -- memory note; cross-session state including this probe's
  queued status

## Estimated cost

- 1 session, ~1-2 hours wall
- ~3-5 GB disk for the GPU venv
- 0 churn on trunk (branch-isolated)
- 0 risk to spike-1 CPU env (parallel venv)

## Why this is worth doing now (the case Dustin made)

> "bro, that 17% reduction ain't hittin it ... if I were any more down for this I be in
> the fuckin ground!"
> -- 2026-05-13

If M1.0 ends up deciding GPU is the production default, this probe saves M1.0 from
having to discover the same data inside the architecture commit. If M1.0 decides CPU is
the production default, this probe gives the receipt for *why* (and an upper-bound
"here's what we left on the table"). Either outcome makes M1.0's architecture record
stronger.
