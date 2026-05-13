"""Spike-1 thin Optimus MCP server -- stdio, single-client.

SESSION 1 STATE: skeleton only. No working pipeline. Function shapes + docstrings
only; real implementation lands in session 2 after install probe greenlights the
locked stack.

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
    """Resolve user-supplied path; raise if it escapes the test-target root.

    Mirrors the secure-singleton-mcp-baseline _confine_path contract: realpath
    + prefix check, NOT a bare exists() check. Symlinks pointing outside the
    root must raise.
    """
    raise NotImplementedError("session 2: implement after install probe passes")


def load_index(index_dir: Path):
    """Read on-disk chunk index produced by indexer.py.

    Returns: (chunk_metadata, embedding_matrix, document_texts) -- exact shape
    finalized in session 2 alongside indexer.py persist format.
    """
    raise NotImplementedError("session 2: implement after indexer persist format settled")


def two_stage_search(query: str, top_k: int = 5):
    """Nomic dense -> top-100 -> ColBERTv2 rerank -> top_k.

    Per secure-singleton-mcp-baseline.md section 3 pipeline. top_k=5 context
    clamp is intentional (NOT configurable from agent side).
    """
    raise NotImplementedError("session 2: implement after stack loaded + indexer ready")


def main() -> None:
    """Stdio MCP server entrypoint. Spike-1 single-client, no transport auth."""
    raise NotImplementedError("session 2: wire MCP stdio server + register optimus_search tool")


if __name__ == "__main__":
    main()
