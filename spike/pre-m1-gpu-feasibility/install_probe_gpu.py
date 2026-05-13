"""GPU install probe -- verify CUDA torch + per-model device placement.

Runs INSIDE ~/optimus-spike-venv-gpu/ (the cu121 venv, parallel to the CPU
spike-1 venv). Captures:

  - torch.version.cuda (what the wheel was built against)
  - torch.cuda.is_available() / device_count / get_device_name(0)
  - Compute capability (sanity-check Ampere SM 8.6)
  - For each model (Nomic CodeRankEmbed, ColBERTv2):
      - load time
      - `.device` reported by the framework
      - device of an actual parameter (model.parameters() .device) -- ground truth
      - peak VRAM allocated after load
      - tiny encode roundtrip on GPU, time + peak VRAM after encode
  - For ColBERT specifically: which segmented_maxsim extension loaded
    (`_cuda` = JIT-compiled CUDA kernel, `_cpp` = CPU fallback)
  - nvidia-smi snapshot taken via subprocess

Why a separate probe instead of reusing spike/pre-m1-retrieval/install_probe.py:
  - Spike-1's probe is frozen at commit 428cf7e (no source changes per
    README "Out of scope")
  - Spike-1's probe does not report per-model device, VRAM, or kernel selection
  - The Nomic + ColBERT custom-code paths can silently fall back to CPU under
    `trust_remote_code=True` -- this probe asserts they did NOT

Exit codes:
  0 if both models loaded onto cuda:0 AND encoded successfully on GPU
  1 if torch.cuda.is_available() is False (wrong wheel, no driver, etc.)
  2 if either model loaded on CPU when CUDA is available (silent fallback)
  3 if either model failed to load/encode (capture error in JSON anyway)

Writes JSON to `spike/pre-m1-gpu-feasibility/results/install-probe-gpu.json`.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

RESULTS = Path(__file__).parent / "results" / "install-probe-gpu.json"
NOMIC_MODEL_ID = "nomic-ai/CodeRankEmbed"
COLBERT_MODEL_ID = "colbert-ir/colbertv2.0"
NOMIC_QUERY_PREFIX = "Represent this query for searching relevant code: "

SAMPLE_DOCS = [
    "def parse_config(path): return json.loads(open(path).read())",
    "class HttpClient: def get(self, url): return requests.get(url).json()",
    "func handleRequest(w http.ResponseWriter, r *http.Request) { ... }",
    "SELECT user_id, email FROM users WHERE active = true",
    "<div className='card'>{title}</div>",
]
SAMPLE_QUERY = "how do I parse a json config file"


def _rss_mb() -> float | None:
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def _pip_freeze() -> dict[str, str]:
    out = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True, text=True, check=False,
    )
    pins: dict[str, str] = {}
    for line in out.stdout.splitlines():
        if "==" in line:
            name, _, version = line.partition("==")
            pins[name.strip()] = version.strip()
    return pins


def _nvidia_smi() -> str:
    try:
        return subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.free,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader"],
            capture_output=True, text=True, check=False, timeout=10,
        ).stdout.strip()
    except Exception as exc:
        return f"(nvidia-smi failed: {exc!r})"


def _torch_cuda_summary() -> dict:
    import torch
    available = torch.cuda.is_available()
    summary: dict = {
        "torch_version": torch.__version__,
        "torch_cuda_build": torch.version.cuda,  # what wheel was compiled for
        "cuda_available": available,
        "device_count": torch.cuda.device_count() if available else 0,
    }
    if available:
        summary["device_name"] = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        summary["compute_capability"] = f"{cap[0]}.{cap[1]}"
        props = torch.cuda.get_device_properties(0)
        summary["total_memory_mb"] = round(props.total_memory / (1024 * 1024), 1)
        summary["multi_processor_count"] = props.multi_processor_count
    return summary


def _peak_vram_mb() -> float:
    import torch
    return round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1) if torch.cuda.is_available() else 0.0


def _reset_vram_peak() -> None:
    import torch
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def probe_nomic_gpu() -> dict:
    """Load Nomic CodeRankEmbed; verify GPU placement; tiny encode on GPU."""
    import torch
    result: dict = {"model_id": NOMIC_MODEL_ID, "ok": False, "on_gpu": False}
    try:
        _reset_vram_peak()

        t0 = time.perf_counter()
        from sentence_transformers import SentenceTransformer
        result["import_seconds"] = round(time.perf_counter() - t0, 3)

        t0 = time.perf_counter()
        # No explicit device= -- prove auto-detection works (matches wrapper code)
        model = SentenceTransformer(NOMIC_MODEL_ID, trust_remote_code=True)
        result["load_seconds"] = round(time.perf_counter() - t0, 3)

        result["framework_device"] = str(model.device)
        result["first_param_device"] = str(next(model.parameters()).device)
        result["on_gpu"] = result["first_param_device"].startswith("cuda")
        result["peak_vram_mb_after_load"] = _peak_vram_mb()
        result["rss_mb_after_load"] = _rss_mb()

        _reset_vram_peak()
        t0 = time.perf_counter()
        query_emb = model.encode([NOMIC_QUERY_PREFIX + SAMPLE_QUERY])
        doc_embs = model.encode(SAMPLE_DOCS)
        result["encode_seconds"] = round(time.perf_counter() - t0, 3)
        result["peak_vram_mb_during_encode"] = _peak_vram_mb()
        result["query_embedding_shape"] = list(query_emb.shape)
        result["doc_embeddings_shape"] = list(doc_embs.shape)
        result["ok"] = True
    except Exception as exc:
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
    return result


def probe_colbert_gpu() -> dict:
    """Load ColBERTv2 via colbert-ai direct; verify GPU placement; tiny rerank."""
    import torch
    result: dict = {"model_id": COLBERT_MODEL_ID, "ok": False, "on_gpu": False}
    try:
        _reset_vram_peak()

        t0 = time.perf_counter()
        from colbert.modeling.checkpoint import Checkpoint
        from colbert.infra import ColBERTConfig
        result["import_seconds"] = round(time.perf_counter() - t0, 3)

        t0 = time.perf_counter()
        cfg = ColBERTConfig()
        ckpt = Checkpoint(COLBERT_MODEL_ID, colbert_config=cfg)
        result["load_seconds_pre_move"] = round(time.perf_counter() - t0, 3)

        # FINDING (probe surfaced this): colbert-ai 0.2.22 does NOT auto-move
        # the entire Checkpoint to GPU on construction. The BERT submodule
        # gets moved via internal logic (tokenization tensors show cuda:0)
        # but the linear projection layer stays on CPU, causing a device
        # mismatch during the projection matmul. M1.0 wrapper code will need
        # an explicit `.to(device)` call after Checkpoint construction. We
        # do that here to capture the actual GPU encode performance.
        result["pre_move_first_param_device"] = str(next(ckpt.parameters()).device)
        pre_move_devices = {str(p.device) for p in ckpt.parameters()}
        result["pre_move_param_device_set"] = sorted(pre_move_devices)
        t0 = time.perf_counter()
        ckpt = ckpt.to("cuda")
        torch.cuda.synchronize()
        result["explicit_to_cuda_seconds"] = round(time.perf_counter() - t0, 3)
        result["load_seconds"] = result["load_seconds_pre_move"] + result["explicit_to_cuda_seconds"]

        first_param = next(ckpt.parameters())
        result["first_param_device"] = str(first_param.device)
        result["first_param_dtype"] = str(first_param.dtype)
        result["on_gpu"] = result["first_param_device"].startswith("cuda")
        result["amp_enabled"] = bool(getattr(cfg, "amp", False))
        result["peak_vram_mb_after_load"] = _peak_vram_mb()
        result["rss_mb_after_load"] = _rss_mb()

        # Which segmented_maxsim extension got loaded? Look at imported modules.
        # colbert.modeling.segmented_maxsim binds either _cpp or _cuda.
        try:
            import colbert.modeling.colbert as _colbert_mod  # may trigger ext load
        except Exception:
            pass
        loaded_exts = [m for m in sys.modules if "segmented_maxsim" in m]
        result["segmented_maxsim_modules_loaded"] = loaded_exts

        _reset_vram_peak()
        t0 = time.perf_counter()
        q_emb = ckpt.queryFromText([SAMPLE_QUERY])
        docs_result = ckpt.docFromText(SAMPLE_DOCS, bsize=8, keep_dims=False)
        d_emb_list = docs_result[0] if isinstance(docs_result, tuple) else docs_result

        result["query_emb_device"] = str(q_emb.device)
        result["doc_emb_device"] = str(d_emb_list[0].device) if d_emb_list else "n/a"

        # FINDING: colbert-ai's docFromText(keep_dims=False) moves the per-doc
        # output tensors to CPU (see colbert/modeling/checkpoint.py); query
        # tensor stays on GPU. The wrapper's MaxSim matmul (server-stdio.py:163)
        # `q_colbert[0] @ d_emb.T` will fail on GPU with device mismatch unless
        # we either pass keep_dims=True OR move d_emb back to cuda. M1.0
        # wrapper must add `.to(q_colbert.device)` to be GPU-compatible.
        result["docFromText_keep_dims_false_returns_cpu"] = (
            d_emb_list[0].device.type == "cpu" if d_emb_list else None
        )
        # FINDING #2: AMP-enabled ColBERT can return query and doc embeddings in
        # different dtypes (Half vs Float) depending on autocast context. Wrapper
        # must reconcile before MaxSim matmul. Capture both for the report.
        result["q_emb_dtype"] = str(q_emb.dtype)
        result["d_emb_dtype"] = str(d_emb_list[0].dtype) if d_emb_list else "n/a"
        ranked = []
        for doc_text, d_emb in zip(SAMPLE_DOCS, d_emb_list):
            # Cast d_emb to match q_emb device AND dtype before matmul
            d_aligned = d_emb.to(device=q_emb.device, dtype=q_emb.dtype)
            sim = q_emb[0] @ d_aligned.T
            score = float(sim.max(dim=-1).values.sum().item())
            ranked.append((doc_text, score))
        ranked.sort(key=lambda r: r[1], reverse=True)
        result["encode_and_score_seconds"] = round(time.perf_counter() - t0, 3)
        result["peak_vram_mb_during_encode"] = _peak_vram_mb()
        result["query_embedding_shape"] = list(q_emb.shape)
        result["doc_count"] = len(d_emb_list)
        result["top1_score"] = ranked[0][1]
        result["top1_content"] = ranked[0][0]
        result["all_ranked"] = [{"score": s, "doc": d} for d, s in ranked]
        result["ok"] = True
    except Exception as exc:
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
    return result


def main() -> int:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    torch_summary = _torch_cuda_summary()
    report = {
        "schema_version": 1,
        "spike": "pre-m1-gpu-feasibility",
        "probe": "install-gpu",
        "host": {
            "platform": platform.platform(),
            "python": sys.version,
            "executable": sys.executable,
            "rss_mb_baseline": _rss_mb(),
        },
        "nvidia_smi_pre_probe": _nvidia_smi(),
        "torch_cuda": torch_summary,
        "pip_freeze": _pip_freeze(),
    }

    if not torch_summary["cuda_available"]:
        report["nomic"] = {"ok": False, "skipped": "cuda_unavailable"}
        report["colbert"] = {"ok": False, "skipped": "cuda_unavailable"}
        report["nvidia_smi_post_probe"] = _nvidia_smi()
        RESULTS.write_text(json.dumps(report, indent=2))
        print(f"\nResults: {RESULTS}")
        print("*** FAIL: torch.cuda.is_available() == False ***")
        print("    Either the wheel is CPU-only or the driver isn't visible from this venv.")
        return 1

    report["nomic"] = probe_nomic_gpu()
    report["colbert"] = probe_colbert_gpu()
    report["nvidia_smi_post_probe"] = _nvidia_smi()
    RESULTS.write_text(json.dumps(report, indent=2))

    nomic_ok = report["nomic"].get("ok", False) and report["nomic"].get("on_gpu", False)
    colbert_ok = report["colbert"].get("ok", False) and report["colbert"].get("on_gpu", False)

    print(f"\nResults: {RESULTS}")
    print(f"torch:        {torch_summary['torch_version']} (cu{torch_summary['torch_cuda_build']})")
    print(f"GPU:          {torch_summary['device_name']} (SM {torch_summary['compute_capability']}, "
          f"{torch_summary['total_memory_mb']:.0f} MB)")
    print(f"Nomic:        load={report['nomic'].get('load_seconds')}s  "
          f"encode={report['nomic'].get('encode_seconds')}s  "
          f"device={report['nomic'].get('first_param_device')}  "
          f"peakVRAM={report['nomic'].get('peak_vram_mb_during_encode')} MB  "
          f"{'OK' if nomic_ok else 'FAIL'}")
    print(f"ColBERT:      load={report['colbert'].get('load_seconds')}s  "
          f"encode={report['colbert'].get('encode_and_score_seconds')}s  "
          f"device={report['colbert'].get('first_param_device')}  "
          f"dtype={report['colbert'].get('first_param_dtype')}  "
          f"peakVRAM={report['colbert'].get('peak_vram_mb_during_encode')} MB  "
          f"{'OK' if colbert_ok else 'FAIL'}")
    print(f"maxsim ext:   {report['colbert'].get('segmented_maxsim_modules_loaded')}")

    if not (nomic_ok and colbert_ok):
        print("\n*** ESCALATION: one or both models NOT on GPU ***")
        if not report["nomic"].get("ok", False):
            print(f"  Nomic error: {report['nomic'].get('error')}")
        elif not report["nomic"].get("on_gpu", False):
            print(f"  Nomic on CPU silently -- check trust_remote_code path")
        if not report["colbert"].get("ok", False):
            print(f"  ColBERT error: {report['colbert'].get('error')}")
        elif not report["colbert"].get("on_gpu", False):
            print(f"  ColBERT on CPU silently -- check ColBERTConfig.device")
        return 3 if (not report["nomic"].get("ok") or not report["colbert"].get("ok")) else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
