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

import contextlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


CHAT_QUERY_PREFIX = "Represent this query for searching relevant code"
"""Nomic CodeRankEmbed query-side instruction prefix per the model card."""

INDEX_DIR_ENV = "OPTIMUS_SPIKE_INDEX_DIR"
"""Indexer output dir env var. Default: ~/.optimus-spike/index/"""

TEST_TARGET_ROOT_ENV = "OPTIMUS_SPIKE_TARGET_ROOT"
"""Test target root for path confinement. Default: c:/ms-superrepo/"""

DEFAULT_RERANK_BSIZE = 32
"""ColBERTv2 batch size at rerank-time docFromText, revised 2026-05-13 from
hardcoded 8. Matches ColBERTConfig().bsize default; ~4x fewer forward passes
per query on the top-100 candidate batch. Pinned via test_rerank_bsize.py
(asserts equality with ColBERTConfig().bsize so the value tracks upstream).
"""


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


@contextlib.contextmanager
def _stdout_to_stderr():
    """Redirect stdout to stderr while ML libs noisily print to it.

    MCP stdio transport REQUIRES stdout to carry only JSON-RPC frames; ColBERT
    prints '[<date>] Loading checkpoint...' to stdout, which corrupts the stream.
    """
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old


def _ensure_models():
    """Lazy-load Nomic + ColBERT, cache. Idempotent across calls."""
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

    # Wrap ALL ML-lib invocations in _stdout_to_stderr. Both libs noisily print
    # to stdout per call (Nomic: sentence-transformers progress bars; ColBERT:
    # QueryTokenizer/Checkpoint debug dumps of Input/Output IDs and masks).
    # These corrupted MCP's JSON-RPC framing and added measurable wall-clock
    # latency. Load-time wrapping (from `_ensure_models`) was insufficient
    # because both libs print on every query too.
    with _stdout_to_stderr():
        query_emb = nomic.encode(
            [CHAT_QUERY_PREFIX + ": " + query], show_progress_bar=False
        )[0].astype(np.float32)

    # Dense: cosine similarity. Normalize both sides.
    q_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)
    emb_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    sims = emb_norms @ q_norm
    dense_k = min(100, len(records))
    dense_top = np.argsort(-sims)[:dense_k]

    candidate_records = [records[i] for i in dense_top]
    candidate_texts = [r.text for r in candidate_records]

    # ColBERT MaxSim rerank
    with _stdout_to_stderr():
        q_colbert = colbert.queryFromText([query])  # [1, Nq, dim]
        docs_result = colbert.docFromText(
            candidate_texts, bsize=DEFAULT_RERANK_BSIZE, keep_dims=False
        )
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
    from mcp.server.fastmcp import FastMCP

    index_dir = Path(os.environ.get(INDEX_DIR_ENV, Path.home() / ".optimus-spike" / "index"))
    target_root_env = os.environ.get(TEST_TARGET_ROOT_ENV)
    if target_root_env:
        target_root = Path(target_root_env).resolve()
    else:
        # Fallback: read target_root from the index manifest
        manifest, _, _ = load_index(index_dir)
        target_root = Path(manifest["target_root"]).resolve()

    log_path = index_dir / "server.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Warm caches at startup so the first tool call isn't a multi-second cold load
    _ensure_models()
    _ensure_index(index_dir)

    app = FastMCP("optimus-spike-1")

    @app.tool()
    def optimus_search(query: str) -> list[dict]:
        """Retrieve top-5 code chunks matching the query from the indexed test target."""
        t0 = time.perf_counter()
        results = two_stage_search(query, index_dir, top_k=5)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Path-confine result paths (defensive; indexer should already guarantee this)
        confined = []
        for r in results:
            try:
                confined_path = confine_path(r["file_path"], target_root)
                confined.append({**r, "file_path": str(confined_path)})
            except ValueError:
                continue  # Drop any chunk whose path escapes target_root

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
