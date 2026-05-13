"""End-to-end indexer smoke test. Hits real Nomic model -- WSL2 venv required.

Skipped if sentence_transformers is unavailable.
"""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("sentence_transformers")

from indexer import main as build_index
from _index_format import load_index


def test_index_tiny_corpus_end_to_end(tiny_corpus, tmp_path):
    build_index(tiny_corpus, tmp_path)

    manifest, records, embeddings = load_index(tmp_path)

    assert manifest["total_chunks"] >= 3  # foo.py + bar.py (multiple chunks) + baz.md
    assert manifest["embedding_dim"] == 768
    assert embeddings.shape == (manifest["total_chunks"], 768)
    assert embeddings.dtype == np.float32

    file_names = {r.file_path.name for r in records}
    assert "foo.py" in file_names
    assert "bar.py" in file_names
    assert "baz.md" in file_names

    # bar.py is sized to span multiple chunks
    bar_chunks = [r for r in records if r.file_path.name == "bar.py"]
    assert len(bar_chunks) >= 2

    # chunk_id matches row index
    for r in records:
        assert 0 <= r.chunk_id < embeddings.shape[0]
