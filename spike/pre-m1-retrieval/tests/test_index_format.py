"""Persist/load round-trip + schema tests.

Path contract (2026-05-14): ChunkRecord.file_path is a workspace-relative POSIX
string; manifest schema_version is 2; load_index rejects older schemas.
"""

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
    records = [ChunkRecord(0, "foo.py", 0, 10, "hello")]
    embeddings = np.zeros((1, 768), dtype=np.float32)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=600,
        model_id="nomic-ai/CodeRankEmbed",
    )
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "chunks.jsonl").exists()
    assert (tmp_path / "embeddings.npy").exists()


def test_manifest_schema_is_v2(tmp_path):
    records = [ChunkRecord(0, "foo.py", 0, 10, "hello")]
    embeddings = np.zeros((1, 768), dtype=np.float32)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=600,
        model_id="nomic-ai/CodeRankEmbed",
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["schema_version"] == 2
    assert INDEX_SCHEMA_VERSION == 2
    assert manifest["target_root"] == "/x"
    assert manifest["chunk_size"] == 600
    assert manifest["model_id"] == "nomic-ai/CodeRankEmbed"
    assert manifest["total_chunks"] == 1
    assert manifest["embedding_dim"] == 768
    assert "indexed_at_iso" in manifest


def test_round_trip_preserves_relative_paths(tmp_path):
    records = [
        ChunkRecord(0, "a.py", 0, 100, "alpha"),
        ChunkRecord(1, "a.py", 100, 200, "beta"),
        ChunkRecord(2, "sub/b.py", 0, 50, "gamma"),
    ]
    embeddings = np.arange(3 * 768, dtype=np.float32).reshape(3, 768)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=600,
        model_id="nomic-ai/CodeRankEmbed",
    )
    loaded_manifest, loaded_records, loaded_emb = load_index(tmp_path)
    assert loaded_manifest["total_chunks"] == 3
    assert [r.chunk_id for r in loaded_records] == [0, 1, 2]
    assert [r.text for r in loaded_records] == ["alpha", "beta", "gamma"]
    # file_path round-trips as a relative POSIX string, not a Path.
    assert [r.file_path for r in loaded_records] == ["a.py", "a.py", "sub/b.py"]
    assert all(isinstance(r.file_path, str) for r in loaded_records)
    np.testing.assert_array_equal(loaded_emb, embeddings)


def test_round_trip_preserves_chunk_id_row_alignment(tmp_path):
    """chunk_id MUST equal the row index in embeddings.npy."""
    records = [ChunkRecord(i, f"f{i}.py", 0, 10, f"text{i}") for i in range(5)]
    embeddings = np.random.rand(5, 768).astype(np.float32)
    persist_index(
        tmp_path,
        records=records,
        embeddings=embeddings,
        target_root=Path("/x"),
        chunk_size=600,
        model_id="nomic-ai/CodeRankEmbed",
    )
    _, loaded_records, loaded_emb = load_index(tmp_path)
    for rec in loaded_records:
        np.testing.assert_array_equal(loaded_emb[rec.chunk_id], embeddings[rec.chunk_id])


def test_load_missing_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_index(tmp_path)


def test_load_rejects_schema_v1(tmp_path):
    """A schema_version 1 index (absolute paths) must be rejected, not mis-served."""
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "target_root": "/x",
        "chunk_size": 600,
        "model_id": "nomic-ai/CodeRankEmbed",
        "total_chunks": 0,
        "embedding_dim": 768,
        "indexed_at_iso": "2026-05-13T00:00:00+00:00",
    }))
    (tmp_path / "chunks.jsonl").write_text("")
    np.save(tmp_path / "embeddings.npy", np.zeros((0, 768), dtype=np.float32))
    with pytest.raises(ValueError, match="schema_version"):
        load_index(tmp_path)
