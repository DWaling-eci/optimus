"""GPU-feasibility-probe MCP server -- parallel to spike-1's server-stdio.py.

Lives in spike/pre-m1-gpu-feasibility/ to keep the spike-1 wrapper frozen at
commit 428cf7e per the README's "out of scope" guarantee. This variant exists
SOLELY to make the GPU smoke run end-to-end so M1.0 has wall-clock numbers.

Single-line semantic delta vs spike/pre-m1-retrieval/server-stdio.py:

  Original line 163:
      sim = q_colbert[0] @ d_emb.T

  GPU-aware line:
      sim = q_colbert[0] @ d_emb.to(device=q_colbert.device, dtype=q_colbert.dtype).T

Why the change is required (probe findings, install-probe-gpu.json):

  1. colbert-ai 0.2.22's `docFromText(keep_dims=False)` returns per-doc tensors
     moved to CPU (see colbert/modeling/checkpoint.py); the query stays on GPU.
     The original matmul fails on GPU with:
         RuntimeError: Expected all tensors to be on the same device, but found
         at least two devices, cuda:0 and cpu! (mat2)

  2. AMP autocast can produce mixed dtypes (Half vs Float) across the query and
     doc embedding paths. The original matmul fails with:
         RuntimeError: expected mat1 and mat2 to have the same dtype

  Both errors are silenced on CPU because everything's already on the same
  device + same dtype. The bugs only manifest under GPU + AMP.

This wrapper is M1.0 architecture-prep data. The 1-line fix above is the
minimum patch the production wrapper will need to run on GPU. Whether M1.0
adopts that vs. the `keep_dims=True` redesign is the M1.0 architect's call.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Reuse spike-1's _index_format and on-disk index. Same manifest, chunks,
# embeddings -- GPU-agnostic format per `[[optimus-kickoff-state]]`.
_SPIKE1_DIR = Path(__file__).resolve().parent.parent / "pre-m1-retrieval"
if str(_SPIKE1_DIR) not in sys.path:
    sys.path.insert(0, str(_SPIKE1_DIR))


CHAT_QUERY_PREFIX = "Represent this query for searching relevant code"
INDEX_DIR_ENV = "OPTIMUS_SPIKE_INDEX_DIR"
TEST_TARGET_ROOT_ENV = "OPTIMUS_SPIKE_TARGET_ROOT"
DEFAULT_RERANK_BSIZE = 32


def confine_path(user_path: str, target_root: Path) -> Path:
    target_root = target_root.resolve()
    candidate = Path(user_path)
    if not candidate.is_absolute():
        candidate = target_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(target_root)
    except ValueError:
        raise ValueError(f"path {user_path!r} resolves outside target_root {target_root}")
    return resolved


def load_index(index_dir: Path):
    from _index_format import load_index as _load
    return _load(index_dir)


_INDEX_CACHE: dict = {"index_dir": None, "manifest": None, "records": None, "embeddings": None}
_MODELS_CACHE: dict = {"nomic": None, "colbert": None}


@contextlib.contextmanager
def _stdout_to_stderr():
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old


def _ensure_models():
    if _MODELS_CACHE["nomic"] is None:
        with _stdout_to_stderr():
            from sentence_transformers import SentenceTransformer
            _MODELS_CACHE["nomic"] = SentenceTransformer(
                "nomic-ai/CodeRankEmbed", trust_remote_code=True
            )
    if _MODELS_CACHE["colbert"] is None:
        with _stdout_to_stderr():
            from colbert.modeling.checkpoint import Checkpoint
            from colbert.infra import ColBERTConfig
            _MODELS_CACHE["colbert"] = Checkpoint(
                "colbert-ir/colbertv2.0", colbert_config=ColBERTConfig()
            )
    return _MODELS_CACHE["nomic"], _MODELS_CACHE["colbert"]


def _ensure_index(index_dir: Path):
    if _INDEX_CACHE["index_dir"] != index_dir:
        manifest, records, embeddings = load_index(index_dir)
        _INDEX_CACHE.update({
            "index_dir": index_dir,
            "manifest": manifest,
            "records": records,
            "embeddings": embeddings,
        })
    return _INDEX_CACHE["records"], _INDEX_CACHE["embeddings"]


def two_stage_search(query: str, index_dir: Path, top_k: int = 5):
    import numpy as np

    nomic, colbert = _ensure_models()
    records, embeddings = _ensure_index(index_dir)

    with _stdout_to_stderr():
        query_emb = nomic.encode(
            [CHAT_QUERY_PREFIX + ": " + query], show_progress_bar=False
        )[0].astype(np.float32)

    q_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)
    emb_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    sims = emb_norms @ q_norm
    dense_k = min(100, len(records))
    dense_top = np.argsort(-sims)[:dense_k]

    candidate_records = [records[i] for i in dense_top]
    candidate_texts = [r.text for r in candidate_records]

    with _stdout_to_stderr():
        q_colbert = colbert.queryFromText([query])  # [1, Nq, dim] on cuda:0
        docs_result = colbert.docFromText(
            candidate_texts, bsize=DEFAULT_RERANK_BSIZE, keep_dims=False
        )
    d_emb_list = docs_result[0] if isinstance(docs_result, tuple) else docs_result

    reranked = []
    for rec, d_emb in zip(candidate_records, d_emb_list):
        # GPU patch: align d_emb to q_colbert's device + dtype before matmul.
        # See module docstring for the bug analysis.
        d_aligned = d_emb.to(device=q_colbert.device, dtype=q_colbert.dtype)
        sim = q_colbert[0] @ d_aligned.T
        score = float(sim.max(dim=-1).values.sum().item())
        reranked.append((rec, score))
    reranked.sort(key=lambda t: t[1], reverse=True)

    return [
        {
            "file_path": str(rec.file_path),
            "start_offset": rec.start_offset,
            "end_offset": rec.end_offset,
            "score": score,
            "text": rec.text,
        }
        for rec, score in reranked[:top_k]
    ]


def main() -> None:
    from mcp.server.fastmcp import FastMCP

    index_dir = Path(os.environ.get(INDEX_DIR_ENV, Path.home() / ".optimus-spike" / "index"))
    target_root_env = os.environ.get(TEST_TARGET_ROOT_ENV)
    if target_root_env:
        target_root = Path(target_root_env).resolve()
    else:
        manifest, _, _ = load_index(index_dir)
        target_root = Path(manifest["target_root"]).resolve()

    log_path = index_dir / "server-gpu.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _ensure_models()
    _ensure_index(index_dir)

    app = FastMCP("optimus-spike-gpu")

    @app.tool()
    def optimus_search(query: str) -> list[dict]:
        """Retrieve top-5 code chunks matching the query (GPU variant)."""
        t0 = time.perf_counter()
        results = two_stage_search(query, index_dir, top_k=5)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        confined = []
        for r in results:
            try:
                confined_path = confine_path(r["file_path"], target_root)
                confined.append({**r, "file_path": str(confined_path)})
            except ValueError:
                continue

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts_iso": datetime.now(timezone.utc).isoformat(),
                "query": query,
                "elapsed_ms": elapsed_ms,
                "results": [{"path": r["file_path"], "score": r["score"]} for r in confined],
            }) + "\n")

        return confined

    app.run()


if __name__ == "__main__":
    main()
