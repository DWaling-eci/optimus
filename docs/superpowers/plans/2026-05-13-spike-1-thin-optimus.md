# Spike-1 Thin Optimus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the spike-1 `indexer.py` + `server-stdio.py` skeletons so the thin retrieval-only Optimus indexes a test target and serves `optimus_search` over stdio MCP to a single Claude Code client. Output is the working pipeline needed for empirical task runs against H1/H2/H3.

**Architecture:**
- **Indexer:** walk target tree → char-window chunk (1500) → embed with Nomic CodeRankEmbed (document-side, no query prefix) → persist as `embeddings.npy` (numpy 2D float32) + `chunks.jsonl` (chunk metadata + text) + `manifest.json`.
- **Server:** stdio MCP single-client. Loads index at startup. Registers one tool `optimus_search(query)` → two-stage retrieval (Nomic dense top-100 → ColBERTv2 MaxSim rerank top-5) → returns ranked chunks. Logs every call to `server.jsonl` for cross-check against chat-report toolkit.
- **Tests:** focused on load-bearing functions — chunking determinism, index round-trip, path confinement, end-to-end smoke. Not exhaustive; spike scope.

**Tech Stack:** Python 3.10+ (3.12 in WSL2 spike venv), sentence-transformers (Nomic), colbert-ai direct (`colbert.modeling.checkpoint.Checkpoint` MaxSim), `mcp` Python SDK for stdio framing, numpy for embeddings, pytest for tests. WSL2-only runtime per install probe finding.

**Brief reference:** `docs/spikes/spike-1-prep-brief.md` sections 5 (scope), 7 (telemetry hookup), 10 (artifact paths). **Skeleton constants already locked:** `DEFAULT_CHUNK_SIZE=1500`, `DEFAULT_INDEX_DIR=~/.optimus-spike/index/`, `CHAT_QUERY_PREFIX="Represent this query for searching relevant code"`, env vars `OPTIMUS_SPIKE_INDEX_DIR` + `OPTIMUS_SPIKE_TARGET_ROOT`.

**Execution environment:** all pytest + indexer + server runs go through WSL2 venv. Command prefix:
```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && <command>'
```
Plan steps inline the full command each time so the engineer doesn't need to remember.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `spike/pre-m1-retrieval/indexer.py` | exists (skeleton) | walk → chunk → embed → persist pipeline |
| `spike/pre-m1-retrieval/server-stdio.py` | exists (skeleton) | stdio MCP server, optimus_search, two-stage search |
| `spike/pre-m1-retrieval/_index_format.py` | NEW | shared persist/load helpers (DRY: indexer writes, server reads) |
| `spike/pre-m1-retrieval/tests/__init__.py` | NEW | empty package marker |
| `spike/pre-m1-retrieval/tests/conftest.py` | NEW | fixture: tiny_corpus path |
| `spike/pre-m1-retrieval/tests/fixtures/tiny_corpus/` | NEW (dir) | 3-4 small files for chunking/walk/index tests |
| `spike/pre-m1-retrieval/tests/test_chunk.py` | NEW | chunk_file determinism + boundary tests |
| `spike/pre-m1-retrieval/tests/test_walk.py` | NEW | walk_target filter tests |
| `spike/pre-m1-retrieval/tests/test_index_format.py` | NEW | persist/load round-trip |
| `spike/pre-m1-retrieval/tests/test_confine.py` | NEW | path confinement security tests |
| `spike/pre-m1-retrieval/tests/test_smoke.py` | NEW | end-to-end index + query smoke (hits real models; WSL2-only) |
| `spike/pre-m1-retrieval/requirements.txt` | exists | add `mcp>=1.0.0` |

**Decomposition rationale:** `_index_format.py` is split out because both indexer and server need identical persist/load behavior. Putting it in either file forces a circular reasoning or duplication. Tests are sized one-concern-per-file so failures localize cleanly.

---

## Tactical decisions locked in this plan

1. **Chunking strategy:** char-window 1500, no overlap. Matches `DEFAULT_CHUNK_SIZE` in skeleton + baseline-decision-record illustrative server.py. Simpler than AST-aware; spike isn't optimizing chunk quality, it's measuring retrieval behavior.
2. **On-disk index format:** `embeddings.npy` (2D float32 [N, 768]) + `chunks.jsonl` (one JSON per line: `{chunk_id, file_path, start_offset, end_offset, text}`) + `manifest.json` (`{schema_version, target_root, chunk_size, model_id, total_chunks, indexed_at_iso, embedding_dim}`). Inline text in JSONL — ms-superrepo subset is ~324MB; ~500MB JSONL is acceptable for spike. No pickle (Shai-Hulud hygiene: no arbitrary code execution at load).
3. **MCP framing:** official `mcp` Python SDK. Stdio transport, single-client. Hand-rolling JSON-RPC is dead weight when the spike's measurement is what matters. Adds one dep — gets shai-hulud dry-run check in Task 7.
4. **Top-K dense:** 100 (Nomic) → 5 (ColBERTv2 reranked). Per baseline decision record.
5. **File-walk filters:** skip dotfiles + dot-dirs, skip on `UnicodeDecodeError` (binary), cap individual files at 1 MB (a 100MB log file would tank indexing time).
6. **Path confinement:** `confine_path()` becomes a utility used by `load_index()` to verify every chunk's `file_path` is inside `target_root` at load time (catches index/target-root mismatch). Real agent-supplied paths don't exist in spike-1 (`optimus_search` takes a query string only), so this is defensive.
7. **Logging:** per-call JSONL at `<index_dir>/server.jsonl` — `{ts_iso, query, results: [{path, score}], elapsed_ms}`. Cross-checkable against chat-report toolkit.

---

## Session split

This plan covers spike-1-prep session 2 + session 3. Natural cut: tasks 1-5 are session 2 (indexer fully working + path confinement). Tasks 6-9 are session 3 (server + end-to-end + ms-superrepo subset smoke). If session 2 has capacity, push into 6.

---

## Task 1: Test fixtures + chunk_file determinism

**Files:**
- Create: `spike/pre-m1-retrieval/tests/__init__.py` (empty)
- Create: `spike/pre-m1-retrieval/tests/conftest.py`
- Create: `spike/pre-m1-retrieval/tests/fixtures/tiny_corpus/foo.py`
- Create: `spike/pre-m1-retrieval/tests/fixtures/tiny_corpus/bar.py`
- Create: `spike/pre-m1-retrieval/tests/fixtures/tiny_corpus/sub/baz.md`
- Create: `spike/pre-m1-retrieval/tests/test_chunk.py`
- Modify: `spike/pre-m1-retrieval/indexer.py` (implement `chunk_file`)

- [ ] **Step 1: Create fixture files**

`tests/fixtures/tiny_corpus/foo.py` (small, < 1500 chars):
```python
"""foo module docstring."""


def parse_config(path):
    """Parse a JSON config from disk."""
    import json
    with open(path) as f:
        return json.loads(f.read())


def main():
    cfg = parse_config("config.json")
    print(cfg)


if __name__ == "__main__":
    main()
```

`tests/fixtures/tiny_corpus/bar.py` (larger, > 1500 chars to force multi-chunk — fill with repeated content):
```python
"""bar module -- HTTP client wrapper for legacy services."""

import requests


class HttpClient:
    """Thin wrapper around requests with retry + timeout."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str):
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.get(url, timeout=self.timeout).json()

    def post(self, path: str, body: dict):
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.post(url, json=body, timeout=self.timeout).json()

    def delete(self, path: str):
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.delete(url, timeout=self.timeout).status_code

    def put(self, path: str, body: dict):
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.put(url, json=body, timeout=self.timeout).json()

    def patch(self, path: str, body: dict):
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.patch(url, json=body, timeout=self.timeout).json()


def quick_check(base: str) -> bool:
    """Probe a health endpoint."""
    client = HttpClient(base)
    try:
        result = client.get("/health")
        return result.get("status") == "ok"
    except Exception:
        return False
```

`tests/fixtures/tiny_corpus/sub/baz.md`:
```markdown
# Notes

Mixed-language fixture: a Markdown file in a subdirectory.
Ensures the walker descends and that non-Python files are not skipped by extension.
```

- [ ] **Step 2: Create `tests/__init__.py`**

Empty file. Marker only.

- [ ] **Step 3: Create `tests/conftest.py`**

```python
"""Spike-1 pytest shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tiny_corpus(tmp_path_factory) -> Path:
    """Path to the bundled tiny_corpus fixture tree."""
    return Path(__file__).parent / "fixtures" / "tiny_corpus"
```

- [ ] **Step 4: Write the failing test**

`tests/test_chunk.py`:
```python
"""Chunk_file determinism + boundary tests.

The spike's measurement integrity depends on chunking being deterministic
(same input -> same chunks across runs). If chunks drift between runs, the
retrieval-behavior comparisons in the report become noisy.
"""

import pytest

from indexer import DEFAULT_CHUNK_SIZE, chunk_file


def test_chunk_file_returns_offset_text_tuples():
    content = "a" * 100
    chunks = list(chunk_file(content))
    assert all(isinstance(c, tuple) and len(c) == 2 for c in chunks)
    start, text = chunks[0]
    assert isinstance(start, int)
    assert isinstance(text, str)


def test_chunk_file_short_content_single_chunk():
    content = "short content fits in one chunk"
    chunks = list(chunk_file(content))
    assert len(chunks) == 1
    assert chunks[0] == (0, content)


def test_chunk_file_long_content_multiple_chunks():
    content = "x" * (DEFAULT_CHUNK_SIZE * 2 + 100)
    chunks = list(chunk_file(content))
    assert len(chunks) == 3
    assert chunks[0][0] == 0
    assert chunks[1][0] == DEFAULT_CHUNK_SIZE
    assert chunks[2][0] == DEFAULT_CHUNK_SIZE * 2


def test_chunk_file_offsets_are_non_overlapping_and_contiguous():
    content = "y" * (DEFAULT_CHUNK_SIZE * 3 + 50)
    chunks = list(chunk_file(content))
    # Reconstructed string must equal original
    reconstructed = "".join(text for _, text in chunks)
    assert reconstructed == content


def test_chunk_file_is_deterministic():
    content = "deterministic content " * 200
    runs = [list(chunk_file(content)) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_chunk_file_empty_content_yields_nothing():
    assert list(chunk_file("")) == []


def test_chunk_file_custom_chunk_size():
    content = "z" * 100
    chunks = list(chunk_file(content, chunk_size=30))
    assert len(chunks) == 4
    assert [c[0] for c in chunks] == [0, 30, 60, 90]
```

- [ ] **Step 5: Run test to verify it fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_chunk.py -v'
```

Expected: ALL FAIL with `NotImplementedError: session 2: implement char-window chunking (or AST-aware variant)`.

- [ ] **Step 6: Implement `chunk_file` in `indexer.py`**

Replace the `chunk_file` body in `spike/pre-m1-retrieval/indexer.py`:
```python
def chunk_file(content: str, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """Yield (start_offset, chunk_text) tuples for the file content.

    Char-window split, no overlap. Deterministic.
    """
    for start in range(0, len(content), chunk_size):
        yield start, content[start:start + chunk_size]
```

- [ ] **Step 7: Run test to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_chunk.py -v'
```

Expected: 7 passed.

- [ ] **Step 8: Commit**

```bash
git add spike/pre-m1-retrieval/tests/ spike/pre-m1-retrieval/indexer.py
git commit -m "spike(pre-m1-retrieval): chunk_file char-window splitter + tests"
```

---

## Task 2: walk_target with filters

**Files:**
- Modify: `spike/pre-m1-retrieval/indexer.py` (implement `walk_target`)
- Modify: `spike/pre-m1-retrieval/tests/fixtures/tiny_corpus/` (add dotfile + binary)
- Create: `spike/pre-m1-retrieval/tests/test_walk.py`

- [ ] **Step 1: Add edge-case fixtures**

Create `tests/fixtures/tiny_corpus/.hidden_file` (content: `should be skipped`).
Create `tests/fixtures/tiny_corpus/.hidden_dir/secret.py` (content: `# should also be skipped`).
Create `tests/fixtures/tiny_corpus/icon.bin` — bytes containing `\x00\xff\xfe` followed by zeros. Use Python to write:
```bash
wsl.exe -- bash -c 'cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -c "from pathlib import Path; Path(\"tests/fixtures/tiny_corpus/icon.bin\").write_bytes(b\"\x00\xff\xfe\" + b\"\x00\" * 64)"'
```

- [ ] **Step 2: Write the failing test**

`tests/test_walk.py`:
```python
"""walk_target filter tests."""

from pathlib import Path

import pytest

from indexer import walk_target


def test_walk_yields_path_content_tuples(tiny_corpus):
    results = list(walk_target(tiny_corpus))
    assert all(isinstance(p, Path) and isinstance(c, str) for p, c in results)


def test_walk_includes_python_files(tiny_corpus):
    paths = [p.name for p, _ in walk_target(tiny_corpus)]
    assert "foo.py" in paths
    assert "bar.py" in paths


def test_walk_descends_subdirs(tiny_corpus):
    paths = [p.name for p, _ in walk_target(tiny_corpus)]
    assert "baz.md" in paths


def test_walk_skips_dotfiles(tiny_corpus):
    paths = [p.name for p, _ in walk_target(tiny_corpus)]
    assert ".hidden_file" not in paths


def test_walk_skips_dot_directories(tiny_corpus):
    paths = [str(p) for p, _ in walk_target(tiny_corpus)]
    assert not any(".hidden_dir" in p for p in paths)


def test_walk_skips_binary_files(tiny_corpus):
    paths = [p.name for p, _ in walk_target(tiny_corpus)]
    assert "icon.bin" not in paths


def test_walk_skips_oversized_files(tmp_path):
    big = tmp_path / "big.txt"
    big.write_text("x" * (2 * 1024 * 1024))  # 2 MB > 1 MB cap
    small = tmp_path / "small.txt"
    small.write_text("ok")
    paths = [p.name for p, _ in walk_target(tmp_path)]
    assert "small.txt" in paths
    assert "big.txt" not in paths
```

- [ ] **Step 3: Run test to verify it fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_walk.py -v'
```

Expected: ALL FAIL with `NotImplementedError`.

- [ ] **Step 4: Implement `walk_target` in `indexer.py`**

Replace `walk_target` body. Add `MAX_FILE_BYTES` constant near the existing constants:
```python
MAX_FILE_BYTES = 1 * 1024 * 1024  # Cap per file to keep indexing bounded. 1 MB.


def walk_target(target_root: Path):
    """Yield (file_path, content) for every readable text file under target_root.

    Skips: dotfiles, dot-directories, binary files (UnicodeDecodeError), files
    over MAX_FILE_BYTES. Yielded paths are absolute.
    """
    import os

    target_root = target_root.resolve()
    for dirpath, dirnames, filenames in os.walk(target_root):
        # In-place filter dot-dirs so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            file_path = Path(dirpath) / name
            try:
                if file_path.stat().st_size > MAX_FILE_BYTES:
                    continue
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            yield file_path.resolve(), content
```

- [ ] **Step 5: Run test to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_walk.py -v'
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add spike/pre-m1-retrieval/tests/ spike/pre-m1-retrieval/indexer.py
git commit -m "spike(pre-m1-retrieval): walk_target with dotfile/binary/size filters"
```

---

## Task 3: `_index_format.py` persist/load round-trip

**Files:**
- Create: `spike/pre-m1-retrieval/_index_format.py`
- Create: `spike/pre-m1-retrieval/tests/test_index_format.py`

- [ ] **Step 1: Write the failing test**

`tests/test_index_format.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails (import error)**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_index_format.py -v'
```

Expected: collection error — `ModuleNotFoundError: No module named '_index_format'`.

- [ ] **Step 3: Implement `_index_format.py`**

Create `spike/pre-m1-retrieval/_index_format.py`:
```python
"""On-disk chunk-index format. Shared by indexer (write) and server (read).

Format:
  manifest.json       -- schema_version, target_root, chunk_size, model_id,
                         total_chunks, indexed_at_iso, embedding_dim
  chunks.jsonl        -- one JSON per line: chunk_id, file_path, start_offset,
                         end_offset, text
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


INDEX_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: int
    file_path: Path
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
                "file_path": str(r.file_path),
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
    embeddings = np.load(index_dir / "embeddings.npy")

    records: list[ChunkRecord] = []
    with (index_dir / "chunks.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            records.append(ChunkRecord(
                chunk_id=d["chunk_id"],
                file_path=Path(d["file_path"]),
                start_offset=d["start_offset"],
                end_offset=d["end_offset"],
                text=d["text"],
            ))
    return manifest, records, embeddings
```

- [ ] **Step 4: Run test to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_index_format.py -v'
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add spike/pre-m1-retrieval/_index_format.py spike/pre-m1-retrieval/tests/test_index_format.py
git commit -m "spike(pre-m1-retrieval): _index_format persist/load round-trip"
```

---

## Task 4: Wire indexer pipeline + Nomic embedding + smoke index

**Files:**
- Modify: `spike/pre-m1-retrieval/indexer.py` (implement `embed_chunks`, `persist_index`, `main`)
- Create: `spike/pre-m1-retrieval/tests/test_smoke_index.py`

- [ ] **Step 1: Replace stub indexer bodies**

In `spike/pre-m1-retrieval/indexer.py`, replace `embed_chunks`, `persist_index`, and `main`. Delete the existing `DEFAULT_INDEX_DIR` reference inside `persist_index`; the new design takes out_dir explicitly. Add `NOMIC_MODEL_ID` constant at top.

Replace from `def embed_chunks` through the end of `def main`:
```python
NOMIC_MODEL_ID = "nomic-ai/CodeRankEmbed"


def embed_chunks(chunk_texts):
    """Run Nomic CodeRankEmbed over chunk texts. No query prefix at index time."""
    from sentence_transformers import SentenceTransformer
    import numpy as np

    model = SentenceTransformer(NOMIC_MODEL_ID, trust_remote_code=True)
    embeddings = model.encode(list(chunk_texts), show_progress_bar=False)
    return np.asarray(embeddings, dtype=np.float32)


def persist_index(out_dir: Path, records, embeddings, target_root: Path) -> None:
    """Wrapper around _index_format.persist_index with spike defaults."""
    from _index_format import persist_index as _persist
    _persist(
        out_dir,
        records=records,
        embeddings=embeddings,
        target_root=target_root,
        chunk_size=DEFAULT_CHUNK_SIZE,
        model_id=NOMIC_MODEL_ID,
    )


def main(target_root: Path, out_dir: Path = DEFAULT_INDEX_DIR) -> None:
    """Build index for target_root, write to out_dir."""
    from _index_format import ChunkRecord

    records: list = []
    chunk_id = 0
    for file_path, content in walk_target(target_root):
        for start, text in chunk_file(content):
            records.append(ChunkRecord(
                chunk_id=chunk_id,
                file_path=file_path,
                start_offset=start,
                end_offset=start + len(text),
                text=text,
            ))
            chunk_id += 1

    if not records:
        raise RuntimeError(f"no indexable files under {target_root}")

    embeddings = embed_chunks([r.text for r in records])
    persist_index(out_dir, records, embeddings, target_root)
    print(f"Indexed {len(records)} chunks from {target_root} -> {out_dir}")
```

- [ ] **Step 2: Write the smoke test**

`tests/test_smoke_index.py`:
```python
"""End-to-end indexer smoke test. Hits real Nomic model -- WSL2 venv required.

Skipped if sentence_transformers is unavailable.
"""

import json
from pathlib import Path

import numpy as np
import pytest

st = pytest.importorskip("sentence_transformers")

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
```

- [ ] **Step 3: Run the smoke test**

This step downloads the Nomic model on first run (~1GB) and takes a few seconds. WSL2 venv required.

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_smoke_index.py -v'
```

Expected: 1 passed. First run downloads model; cached after.

- [ ] **Step 4: Commit**

```bash
git add spike/pre-m1-retrieval/indexer.py spike/pre-m1-retrieval/tests/test_smoke_index.py
git commit -m "spike(pre-m1-retrieval): wire indexer pipeline + Nomic embedding + smoke"
```

---

## Task 5: confine_path security boundary

**Files:**
- Modify: `spike/pre-m1-retrieval/server-stdio.py` (implement `confine_path`)
- Create: `spike/pre-m1-retrieval/tests/test_confine.py`

- [ ] **Step 1: Write the failing test**

`tests/test_confine.py`:
```python
"""Path confinement security tests.

Mirrors the contract in secure-singleton-mcp-baseline.md SECURITY callout:
realpath + prefix check; symlinks escaping must raise.
"""

from pathlib import Path

import pytest

# server-stdio is a hyphenated filename; import via importlib
import importlib.util
import sys

_spec = importlib.util.spec_from_file_location(
    "server_stdio",
    Path(__file__).resolve().parent.parent / "server-stdio.py",
)
server_stdio = importlib.util.module_from_spec(_spec)
sys.modules["server_stdio"] = server_stdio
_spec.loader.exec_module(server_stdio)

confine_path = server_stdio.confine_path


def test_confine_path_inside_root_returns_resolved(tmp_path):
    inside = tmp_path / "sub" / "file.txt"
    inside.parent.mkdir()
    inside.write_text("ok")
    result = confine_path(str(inside), tmp_path)
    assert result == inside.resolve()


def test_confine_path_outside_root_raises(tmp_path):
    outside = tmp_path.parent / "other.txt"
    outside.write_text("nope")
    with pytest.raises(ValueError, match="outside"):
        confine_path(str(outside), tmp_path)


def test_confine_path_symlink_escaping_raises(tmp_path):
    target = tmp_path.parent / "real.txt"
    target.write_text("escape")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this filesystem")
    with pytest.raises(ValueError, match="outside"):
        confine_path(str(link), tmp_path)


def test_confine_path_relative_resolved_against_root(tmp_path):
    inside = tmp_path / "x.txt"
    inside.write_text("ok")
    result = confine_path("x.txt", tmp_path)
    assert result == inside.resolve()


def test_confine_path_dotdot_escape_raises(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        confine_path("../escape.txt", tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_confine.py -v'
```

Expected: ALL FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement `confine_path` in `server-stdio.py`**

Replace the `confine_path` body:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_confine.py -v'
```

Expected: 4 passed, 1 skipped if symlinks unsupported (5 passed if supported).

- [ ] **Step 5: Commit**

```bash
git add spike/pre-m1-retrieval/server-stdio.py spike/pre-m1-retrieval/tests/test_confine.py
git commit -m "spike(pre-m1-retrieval): confine_path realpath+prefix security check"
```

**↑ End of session 2 natural stopping point. Memory bump after this task if stopping here.**

---

## Task 6: Two-stage search (Nomic dense → ColBERTv2 MaxSim → top-5)

**Files:**
- Modify: `spike/pre-m1-retrieval/server-stdio.py` (implement `load_index`, `two_stage_search`)
- Create: `spike/pre-m1-retrieval/tests/test_two_stage_search.py`

- [ ] **Step 1: Replace `load_index` in `server-stdio.py`**

```python
def load_index(index_dir: Path):
    """Read on-disk chunk index produced by indexer.py.

    Returns: (manifest, records, embedding_matrix).
    """
    from _index_format import load_index as _load
    return _load(index_dir)
```

- [ ] **Step 2: Implement `two_stage_search`**

Add module-level lazy singletons + replace `two_stage_search`:
```python
_INDEX_CACHE: dict = {"index_dir": None, "manifest": None, "records": None, "embeddings": None}
_MODELS_CACHE: dict = {"nomic": None, "colbert": None}


def _ensure_models():
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

    Returns: list of dicts {file_path, start_offset, end_offset, score, text}.
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
```

- [ ] **Step 3: Write the smoke test**

`tests/test_two_stage_search.py`:
```python
"""Two-stage search smoke test. Hits real Nomic + ColBERT -- WSL2 venv required."""

from pathlib import Path

import pytest

pytest.importorskip("sentence_transformers")
pytest.importorskip("colbert")

import importlib.util
import sys

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
        assert tiny_corpus.resolve() in Path(r["file_path"]).resolve().parents or \
               Path(r["file_path"]).resolve().parent == tiny_corpus.resolve() or \
               tiny_corpus.resolve() == Path(r["file_path"]).resolve().parent.parent
```

- [ ] **Step 4: Run smoke test**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_two_stage_search.py -v'
```

Expected: 2 passed. First run downloads ColBERT (~500MB) and compiles `segmented_maxsim_cpp`.

- [ ] **Step 5: Commit**

```bash
git add spike/pre-m1-retrieval/server-stdio.py spike/pre-m1-retrieval/tests/test_two_stage_search.py
git commit -m "spike(pre-m1-retrieval): two-stage search (Nomic dense -> ColBERT rerank)"
```

---

## Task 7: Stdio MCP server with optimus_search tool

**Files:**
- Modify: `spike/pre-m1-retrieval/requirements.txt` (add `mcp>=1.0.0`)
- Modify: `spike/pre-m1-retrieval/server-stdio.py` (implement `main()`)

- [ ] **Step 1: Shai-Hulud dry-run check before adding `mcp`**

Per memory `shai-hulud-pip-install-discipline`: check transitive deps for contamination before installing.

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && python -m pip install --dry-run --report /tmp/mcp-deps.json --only-binary :all: mcp && cat /tmp/mcp-deps.json | python -c "import json,sys; d=json.load(sys.stdin); pkgs=[x[\"metadata\"][\"name\"]+\"==\"+x[\"metadata\"][\"version\"] for x in d[\"install\"]]; print(\"\\n\".join(pkgs))"'
```

Expected: list of packages with versions. Visually scan for: `mistralai`, `guardrails-ai`, `lightning==2.6.2`, `lightning==2.6.3` (the 2026-05-11/12 worm wave). If any of these surface, STOP and escalate.

- [ ] **Step 2: Add `mcp` to requirements + install**

Append to `spike/pre-m1-retrieval/requirements.txt`:
```
mcp>=1.0.0
```

Install in the venv:
```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && python -m pip install --only-binary :all: -r /mnt/c/_Source/optimus/spike/pre-m1-retrieval/requirements.txt'
```

- [ ] **Step 3: Implement `main()` with stdio MCP server**

Replace the imports header + `main()` in `server-stdio.py`. Add these imports near the top:
```python
import asyncio
import json
import time
from datetime import datetime, timezone
```

Replace `main()`:
```python
def main() -> None:
    """Stdio MCP server entrypoint. Spike-1 single-client, no transport auth."""
    from mcp.server.fastmcp import FastMCP

    index_dir = Path(os.environ.get(INDEX_DIR_ENV, Path.home() / ".optimus-spike" / "index"))
    target_root = Path(os.environ.get(TEST_TARGET_ROOT_ENV, "/c/ms-superrepo")).resolve()
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
        confined_results = []
        for r in results:
            try:
                confined_path = confine_path(r["file_path"], target_root)
                confined_results.append({**r, "file_path": str(confined_path)})
            except ValueError:
                continue  # Drop any chunk whose path escapes target_root

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts_iso": datetime.now(timezone.utc).isoformat(),
                "query": query,
                "elapsed_ms": elapsed_ms,
                "results": [{"path": r["file_path"], "score": r["score"]} for r in confined_results],
            }) + "\n")

        return confined_results

    app.run()
```

- [ ] **Step 4: Manual smoke -- run server, send initialize + tools/call**

Open one WSL2 shell and start the server pointing at the tiny_corpus index (which we'll build inline):

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python indexer.py tests/fixtures/tiny_corpus /tmp/tiny-index && OPTIMUS_SPIKE_INDEX_DIR=/tmp/tiny-index OPTIMUS_SPIKE_TARGET_ROOT=$(pwd)/tests/fixtures/tiny_corpus python server-stdio.py < /dev/null & sleep 5 && kill %1'
```

Expected: server starts, warms caches (Nomic + ColBERT load logs to stderr), reads stdin (EOF), exits. No traceback.

For a more thorough smoke, use the `mcp` SDK's client. Skip this if `app.run()` exits cleanly with the above:
```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -c "
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def smoke():
    params = StdioServerParameters(
        command=\"python\",
        args=[\"server-stdio.py\"],
        env={
            \"OPTIMUS_SPIKE_INDEX_DIR\": \"/tmp/tiny-index\",
            \"OPTIMUS_SPIKE_TARGET_ROOT\": \"tests/fixtures/tiny_corpus\",
            \"PATH\": __import__(\"os\").environ.get(\"PATH\", \"\"),
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(\"tools:\", [t.name for t in tools.tools])
            result = await session.call_tool(\"optimus_search\", {\"query\": \"parse json config\"})
            print(\"result:\", result.content[0].text[:200])

asyncio.run(smoke())
"'
```

Expected: `tools: ['optimus_search']` and a result printout with a chunk excerpt.

- [ ] **Step 5: Commit**

```bash
git add spike/pre-m1-retrieval/requirements.txt spike/pre-m1-retrieval/server-stdio.py
git commit -m "spike(pre-m1-retrieval): stdio MCP server with optimus_search tool"
```

---

## Task 8: End-to-end smoke against ms-superrepo subset

**Files:**
- Modify: `spike/pre-m1-retrieval/README.md` (add session-2/3 "How to run -- working pipeline" section + indexing-time + query-latency observations)

- [ ] **Step 1: Prepare the test corpus subset in WSL2**

The brief recommends the spike-2 subset (`~/.spike-test-corpus/`, ~324MB). If it already exists from spike-2, reuse. Otherwise, the spike-2 script creates it.

```bash
wsl.exe -- bash -c 'ls -la ~/.spike-test-corpus/ 2>/dev/null | head -5 || echo "subset not present"'
```

If absent, check the spike-2 README for the subset-creation steps and run them. (Subset creation is outside the indexer's responsibility — it's a one-time prep.)

- [ ] **Step 2: Time the indexing run**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && time python indexer.py ~/.spike-test-corpus ~/.optimus-spike/index-msrepo 2>&1 | tee results/index-msrepo-timing.txt'
```

Expected: total elapsed printed by `time`. If > 2 hours, escalate per brief §2 trigger 2 (subset further or pick smaller target).

- [ ] **Step 3: Smoke a sample query through the server**

Use the same client smoke pattern as Task 7 step 4 but pointed at the msrepo index:

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -c "
import asyncio, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def smoke():
    params = StdioServerParameters(
        command=\"python\",
        args=[\"server-stdio.py\"],
        env={
            \"OPTIMUS_SPIKE_INDEX_DIR\": __import__(\"os\").path.expanduser(\"~/.optimus-spike/index-msrepo\"),
            \"OPTIMUS_SPIKE_TARGET_ROOT\": __import__(\"os\").path.expanduser(\"~/.spike-test-corpus\"),
            \"PATH\": __import__(\"os\").environ.get(\"PATH\", \"\"),
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for q in [\"how does the build system run tests\", \"http retry logic\", \"kotlin coroutine cancellation\"]:
                t0 = time.perf_counter()
                result = await session.call_tool(\"optimus_search\", {\"query\": q})
                print(f\"[{int((time.perf_counter()-t0)*1000)}ms] {q!r} -> {result.content[0].text[:120]}\")

asyncio.run(smoke())
"' 2>&1 | tee results/server-msrepo-smoke.txt
```

Expected: 3 queries return inside 5 seconds each (brief §5 performance budget). Latency > 5s = escalate per brief §2 trigger 2.

- [ ] **Step 4: Update spike README with observations**

In `spike/pre-m1-retrieval/README.md`, replace the "How to run (current state -- session 1)" section heading with `## How to run -- working pipeline (session 2+)` and add:
- Indexing command + observed elapsed time
- Server-launch env-var pattern
- Sample query latencies from step 3
- Any anomalies (queries > 5s, corpus subset decisions, etc.)

- [ ] **Step 5: Commit**

```bash
git add spike/pre-m1-retrieval/README.md spike/pre-m1-retrieval/results/
git commit -m "spike(pre-m1-retrieval): end-to-end smoke against ms-superrepo subset"
```

---

## Task 9: Session 2/3 wrap commit + memory bump

**Files:**
- Modify: `C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/optimus-kickoff-state.md`

- [ ] **Step 1: Sanity-check all tests still pass**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/ -v'
```

Expected: all tests pass. Note any skipped (e.g., symlink test on Windows-bound filesystem).

- [ ] **Step 2: Update kickoff-state memory**

Edit `optimus-kickoff-state.md`:
- Frontmatter description: note that spike-1 thin Optimus is implemented (indexer + server + tests + e2e smoke).
- Commit list: add the new commits with brief rationale.
- Status section: B.3 / submodule-bump gates already cleared; thin Optimus implementation is now done; next gate is the DIRECTORY_INDEX.md authoring + drift fixture (the remaining prep deliverables) before empirical task runs can start.
- Next-moves: update to reflect new state (DIRECTORY_INDEX.md authoring + drift fixture remain).

- [ ] **Step 3: Commit memory update is automatic (memory is outside the repo)**

No git commit needed for memory. The repo commits from Tasks 1-8 are the spike-1 prep session 2/3 record.

- [ ] **Step 4: Push trunk**

```bash
git push origin trunk
```

---

## Definition of Done for this plan

- All 9 tasks completed, each with its own commit on `trunk`.
- `pytest tests/ -v` from `spike/pre-m1-retrieval/` passes end-to-end in WSL2 venv.
- `indexer.py` builds an index against `~/.spike-test-corpus/` in < 2 hours.
- `server-stdio.py` serves `optimus_search` queries at < 5s p50 latency on the msrepo subset.
- Spike README reflects working-pipeline state.
- Kickoff-state memory bumped.
- Remaining spike-1 prep deliverables (DIRECTORY_INDEX.md authoring + drift fixture) are the *only* gate left before empirical task runs.
