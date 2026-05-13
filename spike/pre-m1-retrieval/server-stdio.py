"""Spike-1 thin Optimus MCP server -- stdio, single-client.

Locked design per docs/spikes/spike-1-prep-brief.md section 5:
  - Single MCP tool: optimus_search(query) -> top-5 ranked chunks
  - Two-stage pipeline: Nomic CodeRankEmbed dense -> top-100 -> ColBERTv2 rerank -> top-5
  - On-disk chunk index built ONCE by indexer.py; this server READS the index at startup
  - Path-confinement at the MCP boundary (every agent path realpath-checked vs test-target root)
  - Per-call query + top-5 result paths logged for cross-check with chat-report toolkit

Out of scope (per brief): container, multi-client, transport auth, optimus_doctor,
optimus_grep, optimus_list, optimus_delete, telemetry plumbing, spaCy.
"""

from __future__ import annotations

import os
from pathlib import Path


CHAT_QUERY_PREFIX = "Represent this query for searching relevant code"
"""Nomic CodeRankEmbed query-side instruction prefix per the model card."""

INDEX_DIR_ENV = "OPTIMUS_SPIKE_INDEX_DIR"
"""Indexer output dir env var. Default: ~/.optimus-spike/index/"""

TEST_TARGET_ROOT_ENV = "OPTIMUS_SPIKE_TARGET_ROOT"
"""Test target root for path confinement. Default: c:/ms-superrepo/"""


def confine_path(user_path: str, target_root: Path) -> Path:
    """Resolve user-supplied path; raise ValueError if it escapes target_root.

    realpath + prefix check, NOT a bare exists() check. Symlinks pointing
    outside the root raise. Relative paths resolve against target_root.
    """
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
    """Read on-disk chunk index produced by indexer.py.

    Thin wrapper around _index_format.load_index. Returns (manifest, records,
    embeddings).
    """
    from _index_format import load_index as _load
    return _load(index_dir)


_INDEX_CACHE: dict = {"index_dir": None, "manifest": None, "records": None, "embeddings": None}
_MODELS_CACHE: dict = {"nomic": None, "colbert": None}


def _ensure_models():
    """Lazy-load Nomic + ColBERT, cache. Idempotent across calls."""
    if _MODELS_CACHE["nomic"] is None:
        from sentence_transformers import SentenceTransformer
        _MODELS_CACHE["nomic"] = SentenceTransformer(
            "nomic-ai/CodeRankEmbed", trust_remote_code=True
        )
    if _MODELS_CACHE["colbert"] is None:
        from colbert.modeling.checkpoint import Checkpoint
        from colbert.infra import ColBERTConfig
        _MODELS_CACHE["colbert"] = Checkpoint(
            "colbert-ir/colbertv2.0", colbert_config=ColBERTConfig()
        )
    return _MODELS_CACHE["nomic"], _MODELS_CACHE["colbert"]


def _ensure_index(index_dir: Path):
    """Lazy-load index, cache by index_dir."""
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
    """Nomic dense -> top-100 -> ColBERTv2 rerank -> top_k.

    Per secure-singleton-mcp-baseline.md section 3 pipeline. top_k=5 context
    clamp is intentional (NOT configurable from agent side at MCP boundary --
    the tool wrapper hardcodes 5; this function accepts top_k for unit tests).
    """
    import numpy as np

    nomic, colbert = _ensure_models()
    records, embeddings = _ensure_index(index_dir)

    query_emb = nomic.encode([CHAT_QUERY_PREFIX + ": " + query])[0].astype(np.float32)

    # Dense: cosine similarity. Normalize both sides.
    q_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)
    emb_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    sims = emb_norms @ q_norm
    dense_k = min(100, len(records))
    dense_top = np.argsort(-sims)[:dense_k]

    candidate_records = [records[i] for i in dense_top]
    candidate_texts = [r.text for r in candidate_records]

    # ColBERT MaxSim rerank
    q_colbert = colbert.queryFromText([query])  # [1, Nq, dim]
    docs_result = colbert.docFromText(candidate_texts, bsize=8, keep_dims=False)
    d_emb_list = docs_result[0] if isinstance(docs_result, tuple) else docs_result

    reranked = []
    for rec, d_emb in zip(candidate_records, d_emb_list):
        sim = q_colbert[0] @ d_emb.T
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
    """Stdio MCP server entrypoint. Spike-1 single-client, no transport auth."""
    raise NotImplementedError("Task 7: wire FastMCP stdio server + register optimus_search tool")


if __name__ == "__main__":
    main()
