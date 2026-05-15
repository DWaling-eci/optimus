"""On-disk chunk-index format. Shared by indexer (write) and server (read).

Format:
  manifest.json       -- schema_version (2), target_root, chunk_size, model_id,
                         total_chunks, indexed_at_iso, embedding_dim
  chunks.jsonl        -- one JSON per line: chunk_id, file_path (workspace-relative
                         POSIX string), start_offset, end_offset, text
  embeddings.npy      -- numpy 2D float32 array, shape (total_chunks, embedding_dim).
                         Row index == chunk_id.

No pickle. No arbitrary code at load.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np


INDEX_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: int
    file_path: str  # workspace-relative POSIX path (relative to target_root)
    start_offset: int
    end_offset: int
    text: str


def persist_index(
    out_dir: Path,
    *,
    records: Iterable[ChunkRecord],
    embeddings: np.ndarray,
    target_root: Path,
    chunk_size: int,
    model_id: str,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = list(records)

    if embeddings.shape[0] != len(records):
        raise ValueError(
            f"embedding count {embeddings.shape[0]} != record count {len(records)}"
        )
    if embeddings.dtype != np.float32:
        embeddings = embeddings.astype(np.float32)

    np.save(out_dir / "embeddings.npy", embeddings)

    with (out_dir / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({
                "chunk_id": r.chunk_id,
                "file_path": r.file_path,
                "start_offset": r.start_offset,
                "end_offset": r.end_offset,
                "text": r.text,
            }) + "\n")

    manifest = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "target_root": str(target_root),
        "chunk_size": chunk_size,
        "model_id": model_id,
        "total_chunks": len(records),
        "embedding_dim": int(embeddings.shape[1]),
        "indexed_at_iso": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def load_index(index_dir: Path) -> tuple[dict, list[ChunkRecord], np.ndarray]:
    index_dir = Path(index_dir)
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no manifest.json at {index_dir}")

    manifest = json.loads(manifest_path.read_text())
    schema = manifest.get("schema_version")
    if schema != INDEX_SCHEMA_VERSION:
        raise ValueError(
            f"index at {index_dir} has schema_version {schema!r}; this build "
            f"requires schema_version {INDEX_SCHEMA_VERSION}. Schema 1 indexes "
            f"store absolute paths and must be rebuilt (see "
            f"docs/specs/2026-05-14-spike-1-path-contract-design.md)."
        )
    embeddings = np.load(index_dir / "embeddings.npy")

    records: list[ChunkRecord] = []
    with (index_dir / "chunks.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            records.append(ChunkRecord(
                chunk_id=d["chunk_id"],
                file_path=d["file_path"],
                start_offset=d["start_offset"],
                end_offset=d["end_offset"],
                text=d["text"],
            ))
    return manifest, records, embeddings
