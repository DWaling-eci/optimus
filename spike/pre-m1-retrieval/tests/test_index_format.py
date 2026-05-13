"""Persist/load round-trip + schema tests."""

import json
from pathlib import Path

import numpy as np
import pytest

from _index_format import (
    INDEX_SCHEMA_VERSION,
    ChunkRecord,
    load_index,
    persist_index,
)


def test_persist_creates_three_files(tmp_path):
    records = [ChunkRecord(0, Path("/x/foo.py"), 0, 10, "hello")]
    embeddings = np.zeros((1, 768), dtype=np.float32)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=1500,
        model_id="nomic-ai/CodeRankEmbed",
    )
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "chunks.jsonl").exists()
    assert (tmp_path / "embeddings.npy").exists()


def test_manifest_schema(tmp_path):
    records = [ChunkRecord(0, Path("/x/foo.py"), 0, 10, "hello")]
    embeddings = np.zeros((1, 768), dtype=np.float32)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=1500,
        model_id="nomic-ai/CodeRankEmbed",
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["schema_version"] == INDEX_SCHEMA_VERSION
    assert manifest["target_root"] == "/x"
    assert manifest["chunk_size"] == 1500
    assert manifest["model_id"] == "nomic-ai/CodeRankEmbed"
    assert manifest["total_chunks"] == 1
    assert manifest["embedding_dim"] == 768
    assert "indexed_at_iso" in manifest


def test_round_trip_preserves_records_and_embeddings(tmp_path):
    records = [
        ChunkRecord(0, Path("/x/a.py"), 0, 100, "alpha"),
        ChunkRecord(1, Path("/x/a.py"), 100, 200, "beta"),
        ChunkRecord(2, Path("/x/b.py"), 0, 50, "gamma"),
    ]
    embeddings = np.arange(3 * 768, dtype=np.float32).reshape(3, 768)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=1500,
        model_id="nomic-ai/CodeRankEmbed",
    )
    loaded_manifest, loaded_records, loaded_emb = load_index(tmp_path)
    assert loaded_manifest["total_chunks"] == 3
    assert [r.chunk_id for r in loaded_records] == [0, 1, 2]
    assert [r.text for r in loaded_records] == ["alpha", "beta", "gamma"]
    assert [r.file_path for r in loaded_records] == [Path("/x/a.py"), Path("/x/a.py"), Path("/x/b.py")]
    np.testing.assert_array_equal(loaded_emb, embeddings)


def test_round_trip_preserves_chunk_id_row_alignment(tmp_path):
    """chunk_id MUST equal the row index in embeddings.npy."""
    records = [ChunkRecord(i, Path(f"/x/f{i}.py"), 0, 10, f"text{i}") for i in range(5)]
    embeddings = np.random.rand(5, 768).astype(np.float32)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=1500,
        model_id="nomic-ai/CodeRankEmbed",
    )
    _, loaded_records, loaded_emb = load_index(tmp_path)
    for rec in loaded_records:
        np.testing.assert_array_equal(loaded_emb[rec.chunk_id], embeddings[rec.chunk_id])


def test_load_missing_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_index(tmp_path)
