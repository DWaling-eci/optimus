# GPU Feasibility Probe -- Results

**Status:** EXECUTED 2026-05-13. Branch: `experiment/gpu-probe`. Trunk base: `428cf7e`.

## Verdict for M1.0

**GPU is viable as a production default on the dev-laptop class of hardware.**
Sub-second per-query retrieval at $0/hr on a 4 GB RTX A500 Laptop, **15-24x faster
than the CPU baseline**, with no retrieval-quality regression (top-1 paths and
ColBERT scores match the CPU baseline to 4 significant figures).

Two **non-obvious wrapper findings** surfaced that the README's "out of scope -- no
wrapper changes needed" claim did NOT predict. They are documented below and are
M1.0's call to land in the production wrapper.

## Headline numbers

| Query | CPU baseline (s) | GPU (s) | Speedup |
|---|---|---|---|
| "how does the build system run tests" | 12.41 | **0.83** | 15.0x |
| "http retry logic" | 10.65 | **0.47** | 22.7x |
| "kotlin coroutine cancellation" | 11.26 | **0.46** | 24.4x |
| **Mean** | **11.44** | **0.59** | **~19x** |

CPU baseline from `spike/pre-m1-retrieval/results/smoke-msrepo-r600.txt` (commit
`428cf7e` post-truncation-fix). Same index, same 3 queries, same `chunk_size=600`
+ `DEFAULT_RERANK_BSIZE=32` retrieval protocol. The GPU smoke wraps the CPU
wrapper with a 1-line patch (see "Wrapper findings" below); the index itself is
GPU-agnostic and reused as-is.

## Top-1 path parity (no quality regression)

| Query | Top-1 path | CPU score | GPU score | Δ |
|---|---|---|---|---|
| build system tests | `ms-core-api/README.md` | 18.441 | 18.443 | +0.002 |
| http retry logic | `MicrometerTestExtensions.kt` | 15.232 | 15.232 | 0.000 |
| kotlin coroutine | `ms-core-lib-test/README.md` | 14.813 | 14.814 | +0.001 |

Numerical precision deltas are within FP32 rounding noise. All three top-1 paths
match exactly. The retrieval pipeline produces equivalent results on GPU; this
is purely a compute-speed change, not a quality change.

## Memory + utilization (nvidia-smi)

Captured via `nvidia-smi dmon -d 1 -s um` running concurrent with the smoke
(see `results/nvidia-smi-dmon.log`).

| Metric | Value |
|---|---|
| Driver / WSL2 CUDA runtime | 573.44 host / 570.170 WSL2, CUDA 12.8 visible |
| GPU | NVIDIA RTX A500 Laptop GPU |
| Compute capability | 8.6 (Ampere, RTX 30-series family) |
| Total VRAM | 4096 MiB |
| **VRAM baseline** (idle desktop) | **1455 MiB** (Chrome / Teams / etc) |
| **VRAM peak during smoke** | **2921 MiB** |
| **Our process delta** | **1466 MiB** |
| SM utilization peak | 94% (1 sample) |
| Memory bandwidth util peak | 100% (1 sample) |

The 1.47 GB process delta matches the install-probe expectation (Nomic 540 MB +
ColBERT 614 MB load weights + activations + CUDA context, FP32). We are
**well under the 2.4 GB headroom** the README budget called out. M1.0 has
comfortable margin even with full desktop load.

## GPU stack

| Component | Pin | Notes |
|---|---|---|
| torch | `2.5.1+cu121` | Required local-version pin -- bare `torch>=2.1.0` resolved to `2.12.0` with cu13 bundled libs, which would fail on this driver. See `requirements-gpu.txt` for the rationale. |
| CUDA wheel libs | `nvidia-cublas-cu12-12.1.3.1`, `nvidia-cudnn-cu12-9.1.0.70`, etc | 12 NVIDIA wheel deps, all cu12 series |
| triton | `3.1.0` | torch 2.5.1's bundled JIT |
| sentence-transformers | `5.5.0` | Auto-moves to cuda:0 on construction |
| colbert-ai | `0.2.22` | Auto-moves model weights to cuda:0 (verified via probe -- README claim **was correct** on this point) |
| Total install footprint | ~5 GB | Disk cost vs ~250 MB for CPU venv. One-time per laptop. |

`segmented_maxsim_cuda` extension **did NOT JIT-build** -- `nvcc` is not installed
in this WSL2 distro (per README "Risks + mitigations" pre-flight note). ColBERT
falls back to the native torch maxsim path. The 22x speedup is **without** the
CUDA-kernel optimization. With `cuda-toolkit-12-1` installed, the
`segmented_maxsim_cuda` path is expected to give another 1.5-2x on top -- M1.0
should decide whether that's worth ~3 GB of toolkit install on every dev box.

## Shai-Hulud check

Per `[[shai-hulud-pip-install-discipline]]`: dry-run report at
`results/dry-run-report-gpu.json` was scanned for the attack-window compromised
list (`mistralai`, `guardrails-ai`, `lightning 2.6.2`/`2.6.3`, TeamPCP). **101
packages would be installed; none matched the compromised list.** Clean install.

## Wrapper findings (M1.0 must land)

The README's "Out of scope -- no source changes needed" claim has TWO failure
modes that only manifest on GPU + AMP. The probe surfaced both via end-to-end
testing rather than assumption.

### Finding #1: `docFromText(keep_dims=False)` moves doc embeddings to CPU

colbert-ai 0.2.22's `docFromText(..., keep_dims=False)` explicitly calls
`.cpu()` on the per-doc tensors before returning the list (see
`colbert/modeling/checkpoint.py`). The query tensor stays on GPU. When the
wrapper then does the MaxSim matmul:

```python
sim = q_colbert[0] @ d_emb.T  # spike-1's server-stdio.py:163
```

...it fails on GPU with:
```
RuntimeError: Expected all tensors to be on the same device, but found at
least two devices, cuda:0 and cpu! (mat2)
```

On CPU this silently works (both already on CPU). The bug is invisible until
you switch silicon.

### Finding #2: AMP autocast can produce mixed dtypes across query/doc paths

With `ColBERTConfig().amp == True` (default in colbert-ai 0.2.22), the query and
doc encode paths can return tensors in different dtypes (Half vs Float)
depending on where autocast wraps the forward pass. Even after fixing #1, the
matmul fails with:
```
RuntimeError: expected mat1 and mat2 to have the same dtype, but got:
float != c10::Half
```

Again invisible on CPU because CPU path doesn't engage autocast at all.

### M1.0 wrapper patch

Single-line fix at `server-stdio.py:163`:

```python
# Before (CPU only):
sim = q_colbert[0] @ d_emb.T

# After (CPU + GPU compatible):
sim = q_colbert[0] @ d_emb.to(device=q_colbert.device, dtype=q_colbert.dtype).T
```

This patch is applied in `spike/pre-m1-gpu-feasibility/server-stdio-gpu.py` (a
copy of spike-1's wrapper with only this one semantic change, so the diff is
auditable). M1.0 can either adopt the patch as-is, or pursue `keep_dims=True`
which avoids the CPU round-trip entirely.

## Artifacts (in `results/`, gitignored)

- `dry-run-report-gpu.json` (1.3 MB) -- full pip resolver output, Shai-Hulud check input
- `install-gpu.log` (31 KB) -- pip install transcript
- `install-probe-gpu.json` (5.8 KB) -- per-model device/timing/VRAM data
- `install-probe-gpu.log` (1.6 KB) -- probe stdout
- `smoke-msrepo-r600-gpu.py` -- the GPU smoke script (parallel to spike-1's)
- `smoke-msrepo-r600-gpu.txt` -- 3-query smoke output (timings + top-1 paths)
- `nvidia-smi-dmon.log` -- 1Hz GPU monitor during smoke (90 samples)
- `nvidia-smi-snapshot.txt` -- single nvidia-smi snapshot post-smoke

Committed (top-level of `spike/pre-m1-gpu-feasibility/`):
- `README.md` -- the original plan (commit `554a40a`)
- `requirements-gpu.txt` -- cu121 torch pin + rationale comments
- `install_probe_gpu.py` -- the GPU install probe
- `server-stdio-gpu.py` -- the patched wrapper for the smoke
- `RESULTS.md` -- this file

## M1.0 implications

1. **GPU production default is viable on dev-laptop hardware.** $0/hr, sub-second
   per query, 19x mean speedup, no quality regression. The "cloud-only GPU"
   framing the brief had can be revised.

2. **GPU detection + graceful CPU fallback** is the right architecture pattern.
   The wrapper should `torch.cuda.is_available()` at startup and pick the
   matmul path accordingly. CPU users still get the spike-1 protocol; GPU
   users get the 19x bump.

3. **The 1-line wrapper patch is required for GPU compatibility** -- M1.0
   wrapper-code work cannot be skipped. The bugs only manifest under GPU + AMP,
   so any CPU-only test suite will pass while production GPU fails.

4. **CUDA toolkit install is M1.0's call.** Without it (this probe): 19x speedup
   via torch-native maxsim. With it: estimated 25-35x via the
   `segmented_maxsim_cuda` JIT kernel. Cost: ~3 GB more disk per dev box,
   `apt install cuda-toolkit-12-1` plumbing in the install docs.

5. **Memory headroom is comfortable on a 4 GB card.** Even with full Chrome +
   Teams + desktop load, our process fit in 1.47 GB. Larger candidate sets
   (`dense_k > 100`) or longer documents (`chunk_size > 600`) would scale up,
   but at the current protocol there's ~1.4 GB of slack.

## Risks remaining (handed to M1.0)

| Risk | Status |
|---|---|
| Driver heterogeneity across dev boxes | OPEN. Other devs may have older driver / no GPU. Detection + fallback covers this. |
| FP16 numerical drift on different GPUs | OPEN. Probe shows numerical delta < 0.002 on this GPU; cross-GPU validation needed before flipping the production default. |
| 4 GB VRAM under heavy desktop load | LOW. We saw 2.92 GB peak with 1.45 GB baseline; would only OOM if baseline climbs to 3+ GB, which is unusual. |
| `segmented_maxsim_cuda` JIT failure modes | OPEN if M1.0 wants the kernel optimization. Currently absent and the path works without it. |

## Definition of Done (from README)

- [x] Branch `experiment/gpu-probe` checked out + clean
- [x] `~/optimus-spike-venv-gpu/` venv assembled with cu121 torch
- [x] Mini Shai-Hulud dry-run report attached (clean -- 101 packages, no hits)
- [x] `install_probe.py` (gpu variant) reports `cuda available: True` + both models on `cuda:0`
- [x] Smoke run completes 3 queries, wall-clock captured per query
- [x] Top-1 paths match the CPU baseline (no retrieval-quality regression)
- [x] `nvidia-smi` snapshot during a live query (memory + util)
- [x] `RESULTS.md` authored with CPU-vs-GPU comparison table + M1.0 verdict
- [x] Memory updated with branch + RESULTS.md pointer

## Cross-references

- `README.md` -- the queued plan (commit `554a40a`)
- `spike/pre-m1-retrieval/results/smoke-msrepo-r600.txt` -- CPU baseline numbers
- `docs/spikes/spike-1-prep-brief.md` §1 -- implementation-tactics scope
- `docs/decisions/secure-singleton-mcp-baseline.md` -- the locked retrieval stack
- Commit `428cf7e` -- trunk HEAD this branch is based on
- `[[shai-hulud-pip-install-discipline]]` -- contamination check followed
- `[[gpu-probe-side-mission]]` -- memory note for this side-mission
