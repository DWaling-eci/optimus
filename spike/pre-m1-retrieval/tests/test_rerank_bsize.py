"""Pin DEFAULT_RERANK_BSIZE to ColBERT's own default.

Rationale (per spike/pre-m1-retrieval/README.md PRIORITY 1 section): the
initial pipeline hardcoded bsize=8 at the docFromText call site. ColBERT's
own default is 32 (ColBERTConfig().bsize). At 100 dense candidates the
8-vs-32 difference is ~12-13 forward passes vs ~3-4 -- a ~4x latency
multiplier on the rerank stage, which is ~95% of per-query wall-clock.

Pinning to ColBERT's own default removes a magic-number drift risk: if
upstream ColBERT moves its default, ours moves with it.

WSL2 venv required (loads ColBERTConfig).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("colbert")

from colbert.infra import ColBERTConfig


_spec = importlib.util.spec_from_file_location(
    "server_stdio",
    Path(__file__).resolve().parent.parent / "server-stdio.py",
)
server_stdio = importlib.util.module_from_spec(_spec)
sys.modules["server_stdio"] = server_stdio
_spec.loader.exec_module(server_stdio)


def test_default_rerank_bsize_matches_colbert_config_default():
    assert server_stdio.DEFAULT_RERANK_BSIZE == ColBERTConfig().bsize
