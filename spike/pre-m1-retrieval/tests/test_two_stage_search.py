"""Two-stage search smoke test. Hits real Nomic + ColBERT -- WSL2 venv required."""

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("sentence_transformers")
pytest.importorskip("colbert")

_spec = importlib.util.spec_from_file_location(
    "server_stdio",
    Path(__file__).resolve().parent.parent / "server-stdio.py",
)
server_stdio = importlib.util.module_from_spec(_spec)
sys.modules["server_stdio"] = server_stdio
_spec.loader.exec_module(server_stdio)

from indexer import main as build_index


def test_search_returns_top_k_in_descending_order(tiny_corpus, tmp_path):
    build_index(tiny_corpus, tmp_path)
    results = server_stdio.two_stage_search("how do I parse a json config file", tmp_path, top_k=3)
    assert len(results) == 3
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_returns_chunks_inside_target(tiny_corpus, tmp_path):
    build_index(tiny_corpus, tmp_path)
    results = server_stdio.two_stage_search("http client", tmp_path, top_k=2)
    for r in results:
        # Path contract: file_path is workspace-relative; join onto the target root.
        resolved = (tiny_corpus / r["file_path"]).resolve()
        assert resolved.is_relative_to(tiny_corpus.resolve())


def test_search_result_shape(tiny_corpus, tmp_path):
    build_index(tiny_corpus, tmp_path)
    results = server_stdio.two_stage_search("parse json", tmp_path, top_k=1)
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == {"file_path", "start_offset", "end_offset", "score", "text"}
    assert isinstance(r["score"], float)
    assert isinstance(r["text"], str)
