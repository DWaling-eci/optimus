"""Spike-1 install probe -- verify the locked retrieval stack assembles + loads.

Run AFTER `pip install -r requirements.txt` (or equivalent) inside the spike venv.
Captures: package versions, model load timing, peak RSS, trivial query roundtrip
on each model. Writes JSON to results/install-probe.json.

Locked stack: Nomic CodeRankEmbed + ColBERTv2 via colbert-ai direct (per
docs/decisions/colbert-wrapper-revision.md; RAGatouille wrapper retired).

Failure modes this probe is designed to catch (per spike-1-prep-brief.md §2 trigger 2):
  - colbert-ai incompatible with Python 3.12 (import or load errors)
  - Nomic CodeRankEmbed model gated / download fails
  - Either model OOMs on load
  - Either model takes pathologically long to load (> 5 min)
  - Checkpoint MaxSim scoring produces unexpected output shape

Any of those => print escalation banner; exit non-zero; the JSON still gets written
so the report has the failure evidence.
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

RESULTS = Path(__file__).parent / "results" / "install-probe.json"
NOMIC_MODEL_ID = "nomic-ai/CodeRankEmbed"
COLBERT_MODEL_ID = "colbert-ir/colbertv2.0"
NOMIC_QUERY_PREFIX = "Represent this query for searching relevant code: "

# A few synthetic code-shaped strings so we can sanity-check the pipeline e2e
# without needing the indexed test target. Real measurement happens in session 2+.
SAMPLE_DOCS = [
    "def parse_config(path): return json.loads(open(path).read())",
    "class HttpClient: def get(self, url): return requests.get(url).json()",
    "func handleRequest(w http.ResponseWriter, r *http.Request) { ... }",
    "SELECT user_id, email FROM users WHERE active = true",
    "<div className='card'>{title}</div>",
]
SAMPLE_QUERY = "how do I parse a json config file"


def _rss_mb() -> float | None:
    """Best-effort current process RSS in MB. None if psutil missing."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def _pip_freeze() -> dict[str, str]:
    """Map of installed package -> version, scoped to this venv."""
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


def probe_nomic() -> dict:
    """Load CodeRankEmbed, embed query + sample docs, capture timings."""
    result: dict = {"model_id": NOMIC_MODEL_ID, "ok": False}
    try:
        t0 = time.perf_counter()
        from sentence_transformers import SentenceTransformer
        result["import_seconds"] = round(time.perf_counter() - t0, 3)
        result["rss_mb_after_import"] = _rss_mb()

        t0 = time.perf_counter()
        model = SentenceTransformer(NOMIC_MODEL_ID, trust_remote_code=True)
        result["load_seconds"] = round(time.perf_counter() - t0, 3)
        result["rss_mb_after_load"] = _rss_mb()

        t0 = time.perf_counter()
        query_emb = model.encode([NOMIC_QUERY_PREFIX + SAMPLE_QUERY])
        doc_embs = model.encode(SAMPLE_DOCS)
        result["encode_seconds"] = round(time.perf_counter() - t0, 3)
        result["query_embedding_shape"] = list(query_emb.shape)
        result["doc_embeddings_shape"] = list(doc_embs.shape)
        result["ok"] = True
    except Exception as exc:
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
    return result


def probe_colbert_direct() -> dict:
    """Load ColBERTv2 via colbert-ai direct, score sample docs, capture timings.

    Uses colbert.modeling.checkpoint.Checkpoint per the wrapper revision
    (docs/decisions/colbert-wrapper-revision.md). MaxSim scoring is computed
    inline -- same mechanism RAGatouille's .rerank() wrapped in the pre-bloat era.
    """
    result: dict = {"model_id": COLBERT_MODEL_ID, "ok": False}
    try:
        t0 = time.perf_counter()
        from colbert.modeling.checkpoint import Checkpoint
        from colbert.infra import ColBERTConfig
        import torch
        result["import_seconds"] = round(time.perf_counter() - t0, 3)
        result["rss_mb_after_import"] = _rss_mb()

        t0 = time.perf_counter()
        cfg = ColBERTConfig()
        ckpt = Checkpoint(COLBERT_MODEL_ID, colbert_config=cfg)
        result["load_seconds"] = round(time.perf_counter() - t0, 3)
        result["rss_mb_after_load"] = _rss_mb()

        # Encode query + docs and compute MaxSim scores end-to-end to prove
        # the full pipeline works (not just model load). docFromText with
        # bsize returns a tuple (list_of_tensors, *optional_text); unwrap.
        t0 = time.perf_counter()
        q_emb = ckpt.queryFromText([SAMPLE_QUERY])  # [1, Nq, dim]
        docs_result = ckpt.docFromText(SAMPLE_DOCS, bsize=8, keep_dims=False)
        d_emb_list = docs_result[0] if isinstance(docs_result, tuple) else docs_result
        # MaxSim per doc: max similarity across doc tokens per query token, sum.
        ranked = []
        for doc_text, d_emb in zip(SAMPLE_DOCS, d_emb_list):
            sim = q_emb[0] @ d_emb.T  # [Nq, doc_tokens]
            score = float(sim.max(dim=-1).values.sum().item())
            ranked.append((doc_text, score))
        ranked.sort(key=lambda r: r[1], reverse=True)
        result["encode_and_score_seconds"] = round(time.perf_counter() - t0, 3)
        result["query_embedding_shape"] = list(q_emb.shape)
        result["doc_count"] = len(d_emb_list)
        result["doc_embedding_shapes"] = [list(d.shape) for d in d_emb_list]
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
    report = {
        "schema_version": 1,
        "spike": "pre-m1-retrieval",
        "probe": "install",
        "host": {
            "platform": platform.platform(),
            "python": sys.version,
            "executable": sys.executable,
            "rss_mb_baseline": _rss_mb(),
        },
        "pip_freeze": _pip_freeze(),
        "nomic": probe_nomic(),
        "colbert": probe_colbert_direct(),
    }
    RESULTS.write_text(json.dumps(report, indent=2))

    nomic_ok = report["nomic"].get("ok", False)
    colbert_ok = report["colbert"].get("ok", False)
    print(f"\nResults: {RESULTS}")
    print(f"Nomic CodeRankEmbed: {'OK' if nomic_ok else 'FAIL'}")
    print(f"ColBERTv2 (colbert-ai direct): {'OK' if colbert_ok else 'FAIL'}")
    if not (nomic_ok and colbert_ok):
        print("\n*** ESCALATION TRIGGER -- spike-1-prep-brief §2 trigger 2 ***")
        print("One or both load probes failed. Review the JSON for details before proceeding.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
