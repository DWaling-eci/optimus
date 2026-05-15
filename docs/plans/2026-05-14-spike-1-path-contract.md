# Spike-1 Path Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the spike-1 retrieval stack exchange only workspace-relative POSIX paths across the MCP boundary, and rebuild the index from the full git-tracked ms-superrepo corpus, so Phase 2's 24 Windows-host Claude Code sessions are not contaminated by a `/mnt/c/...` path-domain artifact.

**Architecture:** Relativization happens at index-build time (spec Approach 1). `ChunkRecord.file_path` becomes a workspace-relative POSIX string and `manifest.json` `schema_version` bumps 1->2; old absolute-path indexes are rejected fast. The indexer enumerates git-tracked source (per-submodule `git ls-files`, not a raw walk) so build output and uncommitted scratch stay out. The server's `confine_path` security gate is untouched; a thin `confined_relative` wrapper reshapes the outbound path. A full-superrepo index rebuild and a `.mcp.json` registration block ride along on the same change.

**Tech Stack:** Python 3.12 (WSL2 `~/optimus-spike-gpu-venv`), pytest, git, mcp Python SDK. Runtime: Claude Code on the Windows host talking to the spike-1 server over stdio MCP; server in WSL2 with GPU passthrough.

**Approved spec:** `docs/specs/2026-05-14-spike-1-path-contract-design.md` (Approved, brainstorming, 2026-05-14). Extends `docs/specs/2026-05-13-spike-1-closeout-design.md`.

---

## File Structure

**Files to modify (optimus repo):**

| Path | Reason |
|---|---|
| `spike/pre-m1-retrieval/_index_format.py` | `INDEX_SCHEMA_VERSION` 1->2; `ChunkRecord.file_path` -> relative POSIX `str`; `load_index` rejects schema mismatch. |
| `spike/pre-m1-retrieval/indexer.py` | Add `iter_records` (relativizes against `target_root`); add git-tracked enumeration (`git_tracked_files`, `_git_ls_files`, `_submodule_paths`, `_read_indexable`, `select_walker`); `main()` auto-selects the enumerator. |
| `spike/pre-m1-retrieval/server-stdio.py` | Add `confined_relative` helper; `optimus_search` returns workspace-relative paths; `two_stage_search` returns the stored relative path directly. `confine_path` UNCHANGED. |
| `spike/pre-m1-retrieval/tests/test_index_format.py` | Rewrite for the relative-`str` + schema-2 contract. |
| `spike/pre-m1-retrieval/tests/test_smoke_index.py` | `r.file_path` is now a `str`, not a `Path`. |
| `spike/pre-m1-retrieval/tests/test_two_stage_search.py` | Returned `file_path` is workspace-relative. |
| `spike/pre-m1-retrieval/tests/test_confine.py` | Add `confined_relative` coverage. |
| `docs/plans/2026-05-13-spike-1-closeout.md` | Insert Phase 1.5 gate; fix Phase 2 index-path + `.mcp.json` references. |

**Files to create (optimus repo):**

| Path | Purpose |
|---|---|
| `spike/pre-m1-retrieval/tests/test_iter_records.py` | `iter_records` emits relative POSIX paths. |
| `spike/pre-m1-retrieval/tests/test_path_contract.py` | Round-trip + mount-independence invariants (model-free). |
| `spike/pre-m1-retrieval/tests/test_git_enumeration.py` | `git_tracked_files` includes tracked + submodule files, excludes untracked/gitignored/gitlink. |
| `spike/pre-m1-retrieval/verify-index.py` | Standalone index sanity checker (diagnostic script, no test -- mirrors `diag-tokens.py` convention). |

**Files to create (outside optimus repo):**

| Path | Purpose |
|---|---|
| `c:/_Source/ms-superrepo/.mcp.json` | Registers the spike-1 WSL2 server with Claude Code. Committed inside ms-superrepo (origin removed; no upstream push). |

**Artifacts produced (outside the repo, not committed):**

| Path | Purpose |
|---|---|
| `~/.optimus-spike/index-msrepo-full-r600/` | Full-superrepo git-tracked relative-path index (WSL2). Supersedes the stale `index-msrepo-r600` subset. |

---

## Phase A -- Workspace-relative path contract

### Task 1: Index stores workspace-relative paths

`_index_format.py` and `indexer.py` change together -- "the index stores relative paths" is one coherent commit. The test files this ripples into are updated in the same task.

**Files:**
- Modify: `spike/pre-m1-retrieval/_index_format.py`
- Modify: `spike/pre-m1-retrieval/indexer.py`
- Modify: `spike/pre-m1-retrieval/tests/test_index_format.py` (full rewrite)
- Create: `spike/pre-m1-retrieval/tests/test_iter_records.py`
- Modify: `spike/pre-m1-retrieval/tests/test_smoke_index.py`
- Modify: `spike/pre-m1-retrieval/tests/test_two_stage_search.py`

- [ ] **Step 1: Rewrite `tests/test_index_format.py`**

Replace the entire file with:

```python
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
```

- [ ] **Step 2: Create `tests/test_iter_records.py`**

```python
"""iter_records: chunk records carry workspace-relative POSIX file paths."""

from indexer import iter_records


def test_iter_records_paths_are_relative_posix(tiny_corpus):
    records = list(iter_records(tiny_corpus))
    assert records, "expected at least one record from tiny_corpus"
    for r in records:
        assert isinstance(r.file_path, str)
        assert not r.file_path.startswith("/")     # no POSIX-absolute path
        assert "\\" not in r.file_path             # no Windows separators
        assert ".." not in r.file_path.split("/")  # no traversal segments
        assert ":" not in r.file_path              # no Windows drive letter


def test_iter_records_chunk_ids_are_contiguous(tiny_corpus):
    records = list(iter_records(tiny_corpus))
    assert [r.chunk_id for r in records] == list(range(len(records)))


def test_iter_records_paths_resolve_under_target(tiny_corpus):
    for r in iter_records(tiny_corpus):
        resolved = (tiny_corpus / r.file_path).resolve()
        assert resolved.is_relative_to(tiny_corpus.resolve())
```

- [ ] **Step 3: Update `tests/test_smoke_index.py`**

`r.file_path` is now a `str`. Replace the two `.name` uses. Find:

```python
    file_names = {r.file_path.name for r in records}
    assert "foo.py" in file_names
    assert "bar.py" in file_names
    assert "baz.md" in file_names

    # bar.py is sized to span multiple chunks
    bar_chunks = [r for r in records if r.file_path.name == "bar.py"]
    assert len(bar_chunks) >= 2
```

Replace with:

```python
    file_names = {r.file_path.rsplit("/", 1)[-1] for r in records}
    assert "foo.py" in file_names
    assert "bar.py" in file_names
    assert "baz.md" in file_names

    # bar.py is sized to span multiple chunks
    bar_chunks = [r for r in records if r.file_path.rsplit("/", 1)[-1] == "bar.py"]
    assert len(bar_chunks) >= 2
```

- [ ] **Step 4: Update `tests/test_two_stage_search.py`**

`two_stage_search` now returns workspace-relative paths. Find `test_search_returns_chunks_inside_target`:

```python
def test_search_returns_chunks_inside_target(tiny_corpus, tmp_path):
    build_index(tiny_corpus, tmp_path)
    results = server_stdio.two_stage_search("http client", tmp_path, top_k=2)
    for r in results:
        assert Path(r["file_path"]).resolve().is_relative_to(tiny_corpus.resolve())
```

Replace with:

```python
def test_search_returns_chunks_inside_target(tiny_corpus, tmp_path):
    build_index(tiny_corpus, tmp_path)
    results = server_stdio.two_stage_search("http client", tmp_path, top_k=2)
    for r in results:
        # Path contract: file_path is workspace-relative; join onto the target root.
        resolved = (tiny_corpus / r["file_path"]).resolve()
        assert resolved.is_relative_to(tiny_corpus.resolve())
```

- [ ] **Step 5: Run the touched tests to verify they fail**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_index_format.py tests/test_iter_records.py tests/test_smoke_index.py tests/test_two_stage_search.py -v'
```

Expected: RED. `test_index_format.py` fails on `str`/schema assertions; `test_iter_records.py` fails to import `iter_records`; the two smoke files fail on the relative-path assertions (or `AttributeError` on `.name`).

- [ ] **Step 6: Edit `_index_format.py` -- schema 2 + relative-`str` file_path + schema rejection**

Change the module docstring's format block (lines ~4-9) so the `manifest.json` and `chunks.jsonl` lines read:

```
  manifest.json       -- schema_version (2), target_root, chunk_size, model_id,
                         total_chunks, indexed_at_iso, embedding_dim
  chunks.jsonl        -- one JSON per line: chunk_id, file_path (workspace-relative
                         POSIX string), start_offset, end_offset, text
```

Change the schema constant:

```python
INDEX_SCHEMA_VERSION = 2
```

Change the `ChunkRecord` dataclass `file_path` field type:

```python
@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: int
    file_path: str  # workspace-relative POSIX path (relative to target_root)
    start_offset: int
    end_offset: int
    text: str
```

In `persist_index`, the `chunks.jsonl` writer line currently reads `"file_path": str(r.file_path),`. Change it to write the relative string as-is:

```python
                "file_path": r.file_path,
```

In `load_index`, after `manifest = json.loads(manifest_path.read_text())` and **before** `embeddings = np.load(...)`, add a fail-fast schema check, and change the `ChunkRecord` construction to keep `file_path` as a `str`:

```python
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
```

- [ ] **Step 7: Edit `indexer.py` -- add `iter_records`, relativize in `main()`**

Add `iter_records` immediately after `chunk_file` (before `embed_chunks`):

```python
def iter_records(target_root: Path, walker=walk_target):
    """Yield ChunkRecords for every file `walker` enumerates under target_root.

    file_path on each record is workspace-relative POSIX (relative to
    target_root) per docs/specs/2026-05-14-spike-1-path-contract-design.md.
    Relativization happens here, at index-build time, so the persisted index is
    portable and mount-location-independent.
    """
    from _index_format import ChunkRecord

    target_root = target_root.resolve()
    chunk_id = 0
    for file_path, content in walker(target_root):
        rel = file_path.resolve().relative_to(target_root).as_posix()
        for start, text in chunk_file(content):
            yield ChunkRecord(
                chunk_id=chunk_id,
                file_path=rel,
                start_offset=start,
                end_offset=start + len(text),
                text=text,
            )
            chunk_id += 1
```

Replace the entire `main()` function with:

```python
def main(target_root: Path, out_dir: Path = DEFAULT_INDEX_DIR, *, walker=walk_target) -> None:
    """Build index for target_root, write to out_dir.

    `walker` selects the corpus enumeration strategy. Task 5 of the path-contract
    plan changes the default to auto-select git-tracked enumeration for git
    working trees; until then it is a plain filtered filesystem walk.
    """
    target_root = target_root.resolve()
    records = list(iter_records(target_root, walker))
    if not records:
        raise RuntimeError(f"no indexable files under {target_root}")

    embeddings = embed_chunks([r.text for r in records])
    persist_index(out_dir, records, embeddings, target_root)
    print(f"Indexed {len(records)} chunks from {target_root} -> {out_dir}")
```

- [ ] **Step 8: Run the touched tests to verify they pass**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_index_format.py tests/test_iter_records.py tests/test_smoke_index.py tests/test_two_stage_search.py -v'
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add spike/pre-m1-retrieval/_index_format.py spike/pre-m1-retrieval/indexer.py spike/pre-m1-retrieval/tests/test_index_format.py spike/pre-m1-retrieval/tests/test_iter_records.py spike/pre-m1-retrieval/tests/test_smoke_index.py spike/pre-m1-retrieval/tests/test_two_stage_search.py
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): path contract -- index stores workspace-relative paths

Phase A Task 1 of docs/plans/2026-05-14-spike-1-path-contract.md.

ChunkRecord.file_path is now a workspace-relative POSIX string; manifest
schema_version bumps 1->2; load_index rejects schema-1 (absolute-path) indexes
fast and loud. indexer.iter_records relativizes each file against target_root
at build time, so the index artifact is mount-location-independent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2: Server returns workspace-relative paths

**Files:**
- Modify: `spike/pre-m1-retrieval/server-stdio.py`
- Modify: `spike/pre-m1-retrieval/tests/test_confine.py`

- [ ] **Step 1: Add failing `confined_relative` tests to `tests/test_confine.py`**

Append to the end of `tests/test_confine.py`:

```python
confined_relative = server_stdio.confined_relative


def test_confined_relative_returns_posix_relative(tmp_path):
    inside = tmp_path / "sub" / "file.txt"
    inside.parent.mkdir()
    inside.write_text("ok")
    result = confined_relative(str(inside), tmp_path)
    assert result == "sub/file.txt"
    assert not result.startswith("/")
    assert "\\" not in result


def test_confined_relative_accepts_relative_input(tmp_path):
    (tmp_path / "x.txt").write_text("ok")
    assert confined_relative("x.txt", tmp_path) == "x.txt"


def test_confined_relative_rejects_dotdot_escape(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        confined_relative("../escape.txt", tmp_path)


def test_confined_relative_rejects_symlink_escape(tmp_path):
    target = tmp_path.parent / "real_secret.txt"
    target.write_text("escape")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this filesystem")
    with pytest.raises(ValueError, match="outside"):
        confined_relative(str(link), tmp_path)
```

- [ ] **Step 2: Run to verify it fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_confine.py -v'
```

Expected: FAIL with `AttributeError: module 'server_stdio' has no attribute 'confined_relative'`.

- [ ] **Step 3: Add `confined_relative` to `server-stdio.py`**

Insert immediately after `confine_path` (after its closing `return resolved` line, before `def load_index`):

```python
def confined_relative(user_path: str, target_root: Path) -> str:
    """Confine user_path to target_root, then return it workspace-relative (POSIX).

    The outbound half of the path contract
    (docs/specs/2026-05-14-spike-1-path-contract-design.md): Optimus never emits
    an absolute path across the MCP boundary. Wraps confine_path -- the security
    gate is unchanged; this only reshapes the confined result.
    """
    confined = confine_path(user_path, target_root)
    return confined.relative_to(target_root.resolve()).as_posix()
```

- [ ] **Step 4: Change `two_stage_search` to return the stored relative path**

In `two_stage_search`, the result-dict comprehension currently has `"file_path": str(rec.file_path),`. Since `rec.file_path` is already a workspace-relative string from the index, drop the `str()`:

```python
    return [
        {
            "file_path": rec.file_path,
            "start_offset": rec.start_offset,
            "end_offset": rec.end_offset,
            "score": score,
            "text": rec.text,
        }
        for rec, score in reranked[:top_k]
    ]
```

- [ ] **Step 5: Change the `optimus_search` tool wrapper to emit workspace-relative paths**

In `main()`, inside the `optimus_search` tool function, replace the result-confinement block:

```python
        # Path-confine result paths (defensive; indexer should already guarantee this)
        confined = []
        for r in results:
            try:
                confined_path = confine_path(r["file_path"], target_root)
                confined.append({**r, "file_path": str(confined_path)})
            except ValueError:
                continue  # Drop any chunk whose path escapes target_root
```

With:

```python
        # Path-confine + reshape result paths to workspace-relative -- the path
        # contract's outbound invariant. confine_path still raises on escape.
        confined = []
        for r in results:
            try:
                rel_path = confined_relative(r["file_path"], target_root)
                confined.append({**r, "file_path": rel_path})
            except ValueError:
                continue  # Drop any chunk whose path escapes target_root
```

The `server.jsonl` log line already records `r["file_path"]` from `confined`, so it now logs the workspace-relative path automatically -- no further change. The server also inherits schema-mismatch fail-fast for free: `main()` -> `_ensure_index` -> `load_index`, which now raises on `schema_version != 2` at startup.

- [ ] **Step 6: Run to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_confine.py tests/test_two_stage_search.py -v'
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add spike/pre-m1-retrieval/server-stdio.py spike/pre-m1-retrieval/tests/test_confine.py
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): path contract -- server returns workspace-relative paths

Phase A Task 2 of docs/plans/2026-05-14-spike-1-path-contract.md.

Adds confined_relative (wraps the unchanged confine_path security gate, reshapes
the result to workspace-relative POSIX). optimus_search emits relative paths;
two_stage_search returns the stored relative path directly. server.jsonl now
logs what the agent sees. confine_path itself is untouched.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3: Path-contract invariant test

A model-free test file that pins the round-trip and the forward-compat (mount-independence) invariants the spec's Testing section calls for.

**Files:**
- Create: `spike/pre-m1-retrieval/tests/test_path_contract.py`

- [ ] **Step 1: Create `tests/test_path_contract.py`**

```python
"""Path-contract invariants -- docs/specs/2026-05-14-spike-1-path-contract-design.md.

Model-free: builds indexes by hand (zero embeddings) so these run without the
WSL2 GPU venv. Proves (1) round-trip stores + returns workspace-relative paths,
(2) the same index is mount-independent -- identical relative paths under two
different target_root values.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np

from _index_format import ChunkRecord, load_index, persist_index

_spec = importlib.util.spec_from_file_location(
    "server_stdio",
    Path(__file__).resolve().parent.parent / "server-stdio.py",
)
server_stdio = importlib.util.module_from_spec(_spec)
sys.modules["server_stdio"] = server_stdio
_spec.loader.exec_module(server_stdio)

confined_relative = server_stdio.confined_relative


def _hand_built_index(index_dir: Path, rel_paths: list[str]) -> None:
    """Persist a minimal schema-2 index with the given relative paths."""
    records = [
        ChunkRecord(i, rel, 0, 10, f"chunk {i}") for i, rel in enumerate(rel_paths)
    ]
    embeddings = np.zeros((len(records), 768), dtype=np.float32)
    persist_index(
        index_dir,
        records=records,
        embeddings=embeddings,
        target_root=Path("/build/time/root"),
        chunk_size=600,
        model_id="nomic-ai/CodeRankEmbed",
    )


def test_index_round_trips_relative_paths(tmp_path):
    rels = ["ms-core-api/src/House.kt", "ms-option-api/config/app.json"]
    _hand_built_index(tmp_path, rels)
    _, records, _ = load_index(tmp_path)
    for r in records:
        assert isinstance(r.file_path, str)
        assert not r.file_path.startswith("/")
        assert "\\" not in r.file_path
        assert ".." not in r.file_path.split("/")
    assert [r.file_path for r in records] == rels


def test_index_is_mount_independent(tmp_path):
    """The same stored relative path resolves identically under two target roots."""
    rel = "ms-core-api/src/House.kt"
    index_dir = tmp_path / "index"
    _hand_built_index(index_dir, [rel])
    _, records, _ = load_index(index_dir)
    stored = records[0].file_path

    # Two different "mounts" -- e.g. /mnt/c/... in WSL2 vs C:\... on Windows.
    root_a = tmp_path / "mount_a" / "ms-superrepo"
    root_b = tmp_path / "mount_b" / "elsewhere" / "ms-superrepo"
    for root in (root_a, root_b):
        (root / "ms-core-api" / "src").mkdir(parents=True)
        (root / rel).write_text("class House")

    out_a = confined_relative(stored, root_a)
    out_b = confined_relative(stored, root_b)
    assert out_a == out_b == rel
```

- [ ] **Step 2: Run to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_path_contract.py -v'
```

Expected: PASS (Tasks 1-2 already implement the contract; this test locks it).

- [ ] **Step 3: Commit**

```bash
git add spike/pre-m1-retrieval/tests/test_path_contract.py
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): path contract -- round-trip + mount-independence tests

Phase A Task 3 of docs/plans/2026-05-14-spike-1-path-contract.md.

Model-free invariant test: index round-trips workspace-relative POSIX paths, and
the same index resolves identically under two different target_root values
(proves the artifact is mount-location-independent per the spec).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase B -- Git-tracked corpus enumeration

### Task 4: `git_tracked_files` enumerator

Index git-tracked source, not a raw walk -- build output (`build/`, `target/`, `node_modules/`) is gitignored and excluded by construction, and uncommitted scratch stays out. ms-superrepo is a submodule superrepo; `git ls-files --recurse-submodules` did not recurse reliably from WSL2 during prep, so enumeration is per-submodule.

**Files:**
- Modify: `spike/pre-m1-retrieval/indexer.py`
- Create: `spike/pre-m1-retrieval/tests/test_git_enumeration.py`

- [ ] **Step 1: Create `tests/test_git_enumeration.py`**

```python
"""git_tracked_files: tracked superrepo + submodule files only.

Builds a real git superrepo with one initialized submodule, then asserts the
enumerator includes tracked + submodule files and excludes untracked,
gitignored, and the submodule gitlink entry.
"""

import subprocess
from pathlib import Path

import pytest

from indexer import _submodule_paths, git_tracked_files


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def git_superrepo(tmp_path):
    # --- submodule origin ---
    sub_origin = tmp_path / "sub_origin"
    sub_origin.mkdir()
    _git(sub_origin, "init", "-q")
    _git(sub_origin, "config", "user.email", "t@spike")
    _git(sub_origin, "config", "user.name", "spike")
    (sub_origin / "sub_tracked.py").write_text("# submodule tracked\n")
    _git(sub_origin, "add", "-A")
    _git(sub_origin, "commit", "-q", "-m", "sub baseline")

    # --- superrepo ---
    root = tmp_path / "superrepo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@spike")
    _git(root, "config", "user.name", "spike")
    (root / "root_tracked.py").write_text("# root tracked\n")
    (root / ".gitignore").write_text("build/\n")
    (root / "build").mkdir()
    (root / "build" / "artifact.js").write_text("// built\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "root baseline")
    # Local-path submodule transport must be explicitly allowed.
    _git(root, "-c", "protocol.file.allow=always", "submodule", "add",
         str(sub_origin), "vendored")
    _git(root, "commit", "-q", "-m", "add submodule")
    # Untracked scratch -- created after the last commit, never added.
    (root / "untracked_scratch.py").write_text("# never committed\n")
    return root


def _rels(root):
    return {
        p.resolve().relative_to(root.resolve()).as_posix()
        for p, _ in git_tracked_files(root)
    }


def test_includes_root_and_submodule_files(git_superrepo):
    rels = _rels(git_superrepo)
    assert "root_tracked.py" in rels
    assert "vendored/sub_tracked.py" in rels


def test_excludes_untracked(git_superrepo):
    assert "untracked_scratch.py" not in _rels(git_superrepo)


def test_excludes_gitignored(git_superrepo):
    assert "build/artifact.js" not in _rels(git_superrepo)


def test_excludes_gitlink_entry(git_superrepo):
    # The submodule directory itself must not appear as a file entry.
    assert "vendored" not in _rels(git_superrepo)


def test_submodule_paths_reads_gitmodules(git_superrepo):
    assert _submodule_paths(git_superrepo) == ["vendored"]
```

- [ ] **Step 2: Run to verify it fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_git_enumeration.py -v'
```

Expected: FAIL on `ImportError: cannot import name 'git_tracked_files'` (collection error).

- [ ] **Step 3: Add `subprocess` + `sys` imports to `indexer.py`**

The current `indexer.py` import block is:

```python
from __future__ import annotations

from pathlib import Path
```

Replace it with:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
```

- [ ] **Step 4: Extract `_read_indexable` and refactor `walk_target` to use it**

Add `_read_indexable` immediately before `walk_target`:

```python
def _read_indexable(file_path: Path) -> str | None:
    """Return file text, or None if oversized / binary / unreadable.

    Shared by walk_target and git_tracked_files so corpus filtering is identical
    regardless of enumeration strategy.
    """
    try:
        if file_path.stat().st_size > MAX_FILE_BYTES:
            return None
        return file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
```

Replace the body of `walk_target` with the `_read_indexable`-based version (behavior-preserving -- `tests/test_walk.py` stays green):

```python
def walk_target(target_root: Path):
    """Yield (file_path, content) for every readable text file under target_root.

    Skips: dotfiles, dot-directories, binary files, files over MAX_FILE_BYTES.
    Yielded paths are absolute + resolved. Use for non-git targets (test
    fixtures, plain trees); git working trees use git_tracked_files.
    """
    import os

    target_root = target_root.resolve()
    for dirpath, dirnames, filenames in os.walk(target_root):
        # In-place filter dot-dirs so os.walk doesn't descend into them.
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            file_path = Path(dirpath) / name
            content = _read_indexable(file_path)
            if content is None:
                continue
            yield file_path.resolve(), content
```

- [ ] **Step 5: Add `_git_ls_files`, `_submodule_paths`, `git_tracked_files`**

Add these three functions immediately after `walk_target`:

```python
def _git_ls_files(repo_dir: Path) -> list[str]:
    """Tracked file paths within repo_dir (relative to repo_dir, POSIX)."""
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "ls-files", "-z"],
        check=True, capture_output=True, text=True,
    )
    return [p for p in result.stdout.split("\0") if p]


def _submodule_paths(target_root: Path) -> list[str]:
    """Submodule paths registered in target_root's .gitmodules (POSIX, relative)."""
    if not (target_root / ".gitmodules").exists():
        return []
    result = subprocess.run(
        ["git", "-C", str(target_root), "config", "--file", ".gitmodules",
         "--get-regexp", r"^submodule\..*\.path$"],
        check=False, capture_output=True, text=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        # line: "submodule.<name>.path <relpath>"
        parts = line.split(None, 1)
        if len(parts) == 2:
            paths.append(parts[1].strip())
    return sorted(paths)


def git_tracked_files(target_root: Path):
    """Yield (file_path, content) for every git-tracked text file under target_root.

    target_root may be a submodule superrepo. Enumerates the superrepo's own
    tracked files plus each initialized submodule's tracked files (per-submodule
    git ls-files; `git ls-files --recurse-submodules` does not recurse reliably
    from WSL2). Build output (build/, target/, node_modules/) is gitignored and
    therefore excluded by construction -- the production-faithful corpus per
    docs/specs/2026-05-14-spike-1-path-contract-design.md.
    """
    target_root = target_root.resolve()
    submodules = _submodule_paths(target_root)
    submodule_set = set(submodules)

    # Superrepo's own tracked files, minus the gitlink entries for submodules.
    for rel in _git_ls_files(target_root):
        if rel in submodule_set:
            continue
        file_path = (target_root / rel).resolve()
        content = _read_indexable(file_path)
        if content is None:
            continue
        yield file_path, content

    # Each submodule's tracked files, prefixed with the submodule path.
    for sub in submodules:
        sub_dir = target_root / sub
        if not (sub_dir / ".git").exists():
            # Submodule not initialized -- skip rather than fail the whole build.
            print(f"[indexer] submodule {sub} not initialized, skipping", file=sys.stderr)
            continue
        for rel in _git_ls_files(sub_dir):
            file_path = (sub_dir / rel).resolve()
            content = _read_indexable(file_path)
            if content is None:
                continue
            yield file_path, content
```

- [ ] **Step 6: Run the git-enumeration + walk tests to verify they pass**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_git_enumeration.py tests/test_walk.py -v'
```

Expected: PASS (new git-enumeration tests green; `test_walk.py` still green -- the `_read_indexable` extraction is behavior-preserving).

- [ ] **Step 7: Commit**

```bash
git add spike/pre-m1-retrieval/indexer.py spike/pre-m1-retrieval/tests/test_git_enumeration.py
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): path contract -- git-tracked corpus enumeration

Phase B Task 4 of docs/plans/2026-05-14-spike-1-path-contract.md.

Adds git_tracked_files: enumerates the superrepo's tracked files plus each
initialized submodule's tracked files (per-submodule git ls-files -- the
--recurse-submodules flag does not recurse reliably from WSL2). Build output is
gitignored and excluded by construction; uncommitted scratch stays out. Extracts
_read_indexable so walk_target and git_tracked_files filter identically.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 5: Auto-select the enumerator in `main()`

**Files:**
- Modify: `spike/pre-m1-retrieval/indexer.py`
- Modify: `spike/pre-m1-retrieval/tests/test_git_enumeration.py`

- [ ] **Step 1: Add failing `select_walker` tests**

Append to `tests/test_git_enumeration.py`:

```python
def test_select_walker_git_repo_uses_git_tracked(git_superrepo):
    from indexer import git_tracked_files, select_walker
    assert select_walker(git_superrepo) is git_tracked_files


def test_select_walker_plain_dir_uses_walk(tmp_path):
    from indexer import select_walker, walk_target
    assert select_walker(tmp_path) is walk_target
```

- [ ] **Step 2: Run to verify it fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_git_enumeration.py -k select_walker -v'
```

Expected: FAIL with `ImportError: cannot import name 'select_walker'`.

- [ ] **Step 3: Add `select_walker` and wire it into `main()`**

Add `select_walker` immediately after `git_tracked_files`:

```python
def select_walker(target_root: Path):
    """Pick the corpus enumerator: git-tracked for git working trees, else walk.

    Git-tracked is production-faithful (build output gitignored, uncommitted
    scratch excluded). Non-git trees -- test fixtures -- fall back to the
    filtered filesystem walk.
    """
    return git_tracked_files if (target_root / ".git").exists() else walk_target
```

Change the `main()` signature default from `walker=walk_target` to `walker=None` and add the auto-select. The function becomes:

```python
def main(target_root: Path, out_dir: Path = DEFAULT_INDEX_DIR, *, walker=None) -> None:
    """Build index for target_root, write to out_dir.

    Corpus enumeration auto-selects: git-tracked files for git working trees
    (production-faithful), else a filtered filesystem walk. Pass `walker`
    explicitly to override.
    """
    target_root = target_root.resolve()
    if walker is None:
        walker = select_walker(target_root)

    records = list(iter_records(target_root, walker))
    if not records:
        raise RuntimeError(f"no indexable files under {target_root}")

    embeddings = embed_chunks([r.text for r in records])
    persist_index(out_dir, records, embeddings, target_root)
    print(f"Indexed {len(records)} chunks from {target_root} -> {out_dir}")
```

- [ ] **Step 4: Run the full enumeration + smoke suite to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/test_git_enumeration.py tests/test_smoke_index.py tests/test_two_stage_search.py -v'
```

Expected: PASS. `tiny_corpus` is not a git repo, so the smoke tests still route through `walk_target` via the auto-select.

- [ ] **Step 5: Commit**

```bash
git add spike/pre-m1-retrieval/indexer.py spike/pre-m1-retrieval/tests/test_git_enumeration.py
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): path contract -- main() auto-selects the enumerator

Phase B Task 5 of docs/plans/2026-05-14-spike-1-path-contract.md.

select_walker picks git_tracked_files for git working trees, walk_target
otherwise. main()'s walker defaults to that auto-select; non-git test fixtures
still route through the filesystem walk.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase C -- Verification tooling + regression gate

### Task 6: Author `verify-index.py` index sanity checker

A standalone diagnostic script (no test -- mirrors the `diag-tokens.py` / `install_probe.py` convention in this directory). Makes the Task 9 index verification non-fragile (no `python -c` / heredoc trip hazard per `[[heredoc-via-wsl-quoting-trap]]`).

**Files:**
- Create: `spike/pre-m1-retrieval/verify-index.py`

- [ ] **Step 1: Create `verify-index.py`**

```python
"""Standalone index sanity checker -- path-contract invariants.

Diagnostic script (no test, per the spike-1 convention for diag-tokens.py /
install_probe.py). Loads an on-disk index and asserts the
docs/specs/2026-05-14-spike-1-path-contract-design.md contract:
  - manifest schema_version == 2
  - every chunk file_path is a workspace-relative POSIX string
    (no leading '/', no '\\', no '..' segment, no drive letter)

Usage:
    python verify-index.py <index-dir>

Exit 0 = all invariants hold. Exit 1 = violation (details on stderr).
Exit 2 = bad invocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _index_format import INDEX_SCHEMA_VERSION, load_index


def verify(index_dir: Path) -> int:
    manifest, records, embeddings = load_index(index_dir)

    if manifest.get("schema_version") != INDEX_SCHEMA_VERSION:
        print(
            f"FAIL: schema_version {manifest.get('schema_version')!r} "
            f"!= {INDEX_SCHEMA_VERSION}",
            file=sys.stderr,
        )
        return 1

    violations: list[str] = []
    for r in records:
        p = r.file_path
        if not isinstance(p, str):
            violations.append(f"chunk {r.chunk_id}: file_path is {type(p).__name__}, not str")
            continue
        if p.startswith("/"):
            violations.append(f"chunk {r.chunk_id}: absolute POSIX path {p!r}")
        if "\\" in p:
            violations.append(f"chunk {r.chunk_id}: backslash in {p!r}")
        if ".." in p.split("/"):
            violations.append(f"chunk {r.chunk_id}: '..' segment in {p!r}")
        if len(p) >= 2 and p[1] == ":":
            violations.append(f"chunk {r.chunk_id}: drive letter in {p!r}")

    if violations:
        for v in violations[:20]:
            print(f"FAIL: {v}", file=sys.stderr)
        if len(violations) > 20:
            print(f"... and {len(violations) - 20} more", file=sys.stderr)
        return 1

    print(
        f"OK: {index_dir} -- schema {manifest['schema_version']}, "
        f"{len(records)} chunks, {embeddings.shape[0]} embeddings, "
        f"all paths workspace-relative POSIX"
    )
    for r in records[:5]:
        print(f"  sample: {r.file_path}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python verify-index.py <index-dir>", file=sys.stderr)
        return 2
    index_dir = Path(argv[1])
    if not index_dir.is_dir():
        print(f"error: {index_dir} is not a directory", file=sys.stderr)
        return 2
    return verify(index_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 2: Smoke the CLI (error paths -- no real index exists yet)**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python verify-index.py ; echo "exit=$?" ; python verify-index.py /tmp/does-not-exist ; echo "exit=$?"'
```

Expected: first call prints the usage line and `exit=2`; second prints the not-a-directory error and `exit=2`. (Functional verification against a real index is Task 9.)

- [ ] **Step 3: Commit**

```bash
git add spike/pre-m1-retrieval/verify-index.py
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): path contract -- verify-index.py sanity checker

Phase C Task 6 of docs/plans/2026-05-14-spike-1-path-contract.md.

Standalone diagnostic (no test, per the diag-tokens.py convention). Loads an
index and asserts the path contract: schema_version 2, every file_path a
workspace-relative POSIX string. Used to verify the Task 9 rebuild without a
fragile python -c / heredoc invocation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 7: Full regression sweep (GPU venv)

**Files:** none (test execution only).

- [ ] **Step 1: Run the entire spike-1 suite in the GPU venv**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python -m pytest tests/ -v'
```

Expected: **zero failures.** The suite grows from the prior 36 to roughly 48 (added: `test_iter_records.py` ~3, `test_path_contract.py` 2, `test_git_enumeration.py` 7; modified files keep their counts). The exact number is whatever pytest reports -- the gate is no failures and no collection errors. If anything fails, debug before Phase D; do not build the real index against unproven code.

### Task 8: (intentionally merged into Task 7)

Phase A/B code is committed per-task; Task 7 is the regression gate. No separate commit task -- proceed to Phase D.

---

## Phase D -- Operational: rebuild the index + wire the server

### Task 9: Build the full-superrepo git-tracked index

**Files:** none in the optimus repo. Produces `~/.optimus-spike/index-msrepo-full-r600/` in WSL2.

- [ ] **Step 1: Confirm ms-superrepo is at a clean baseline**

```bash
git -C c:/_Source/ms-superrepo status --short
git -C c:/_Source/ms-superrepo log --oneline -1
```

Expected: clean working tree; HEAD is the `DIRECTORY_INDEX.md` commit (`286c47f` or later). If dirty, run `python c:/_Source/optimus/spike/pre-m1-retrieval/drift-fixture.py --reset` first.

- [ ] **Step 1b: Confirm every submodule is initialized**

`git_tracked_files` skips uninitialized submodules with only a single stderr line — which scrolls past in the build's model output, producing a quietly incomplete index. An uninitialized submodule does NOT show in `git status`; it shows in `git submodule status` with a leading `-`. Gate on it explicitly:

```bash
git -C c:/_Source/ms-superrepo submodule status | findstr /b /c:"-"
```

Expected: **no output** (exit 1 from `findstr` is fine — it means no match, i.e. nothing uninitialized). Any `-`-prefixed line is an uninitialized submodule — STOP and run `git -C c:/_Source/ms-superrepo submodule update --init --recursive` before continuing. (Bash equivalent: `git -C c:/_Source/ms-superrepo submodule status | grep '^-'`.)

- [ ] **Step 2: Build the index against the full superrepo**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python indexer.py /mnt/c/_Source/ms-superrepo $HOME/.optimus-spike/index-msrepo-full-r600'
```

Expected: `Indexed <N> chunks from /mnt/c/_Source/ms-superrepo -> .../index-msrepo-full-r600`, where `<N>` is substantially larger than the old ms-core + ms-core-api subset (thousands of chunks across the ~26 submodules). The build runs on GPU; allow a few minutes.

- [ ] **Step 3: Verify the path contract with `verify-index.py`**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && python verify-index.py $HOME/.optimus-spike/index-msrepo-full-r600 ; echo "exit=$?"'
```

Expected: `OK: ... schema 2, <N> chunks, ... all paths workspace-relative POSIX`, `exit=0`. The sample paths lead with a submodule directory (e.g. `ms-core-api/...`, `ms-option-api/...`).

- [ ] **Step 4: Confirm build output is excluded from the corpus**

```bash
wsl.exe -- bash -c 'grep -oE "\"file_path\": \"[^\"]*(build|target|node_modules)/" $HOME/.optimus-spike/index-msrepo-full-r600/chunks.jsonl | head ; echo "match-count=$(grep -cE "\"file_path\": \"[^\"]*(build|target|node_modules)/" $HOME/.optimus-spike/index-msrepo-full-r600/chunks.jsonl || true)"'
```

Expected: `match-count=0` -- git-tracked enumeration excludes gitignored build output by construction. If non-zero, a submodule commits its build output (or has no `.gitignore` for it); inspect the matched paths and decide with Dustin whether that submodule's build dir is intentional source.

### Task 10: Author + validate `c:/_Source/ms-superrepo/.mcp.json`

**Files:**
- Create: `c:/_Source/ms-superrepo/.mcp.json` (outside the optimus repo).

- [ ] **Step 1: Create `c:/_Source/ms-superrepo/.mcp.json`**

```json
{
  "mcpServers": {
    "optimus-spike-1": {
      "command": "wsl.exe",
      "args": [
        "--",
        "bash",
        "-c",
        "source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && OPTIMUS_SPIKE_INDEX_DIR=$HOME/.optimus-spike/index-msrepo-full-r600 OPTIMUS_SPIKE_TARGET_ROOT=/mnt/c/_Source/ms-superrepo python server-stdio.py"
      ]
    }
  }
}
```

`$HOME` (not `~`) is used inside the env-var assignment so bash expands it unambiguously. The spike-1 server stays stdio + WSL2 host-process (not containerized -- locked; container is spike-2).

- [ ] **Step 2: Validate the server boots from the exact `.mcp.json` command**

Run the same command `.mcp.json` will invoke, bounded by `timeout` (the server blocks on stdio for JSON-RPC frames that will not arrive here):

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && OPTIMUS_SPIKE_INDEX_DIR=$HOME/.optimus-spike/index-msrepo-full-r600 OPTIMUS_SPIKE_TARGET_ROOT=/mnt/c/_Source/ms-superrepo timeout 90 python server-stdio.py ; echo "exit=$?"'
```

Expected: the startup line `[spike-1 server] device=cuda vram_total_gb=<...>` appears on stderr, no traceback, then `timeout` kills the idle server (`exit=124`). A `schema_version` `ValueError` here means the index dir is wrong or stale -- recheck Task 9.

- [ ] **Step 3: Commit `.mcp.json` inside ms-superrepo**

```bash
git -C c:/_Source/ms-superrepo add .mcp.json
git -C c:/_Source/ms-superrepo commit -m "chore: add .mcp.json -- optimus spike-1 server registration"
git -C c:/_Source/ms-superrepo remote -v
```

Expected: commit recorded; `remote -v` empty. If a remote exists, ABORT -- `.mcp.json` must not push upstream (spike-2 protocol).

- [ ] **Step 4: End-to-end smoke -- the Windows agent opens a returned path (manual)**

Controller- or Dustin-run. Open a throwaway Claude Code session at `c:/_Source/ms-superrepo`, confirm the `optimus-spike-1` MCP server registered (`/mcp` or the tool list), ask it to call `optimus_search` for any code concept, then `Read` one returned path verbatim.

Expected: `optimus_search` returns workspace-relative paths (e.g. `ms-core-api/src/.../Foo.kt`), and `Read` opens that path against the session CWD without a `/mnt/c/...` translation error. This is the contract's whole point -- no absolute path crossed the MCP boundary. If `Read` fails on a returned path, STOP and escalate; the path contract is not holding end-to-end.

---

## Phase E -- Closeout-plan amendment + close

### Task 11: Amend `docs/plans/2026-05-13-spike-1-closeout.md` and commit

**Files:**
- Modify: `docs/plans/2026-05-13-spike-1-closeout.md`
- Commit: this plan (`docs/plans/2026-05-14-spike-1-path-contract.md`) if not already committed.

- [ ] **Step 1: Insert the Phase 1.5 gate section**

In `docs/plans/2026-05-13-spike-1-closeout.md`, find the `---` separator that closes Phase 1 (immediately before the `## Phase 2 -- Empirical runs (24 Claude Code sessions, manual)` heading). Insert this section between that `---` and the Phase 2 heading:

```markdown
## Phase 1.5 -- Path contract + full-superrepo index rebuild

**Added 2026-05-14.** Phase-2 prep surfaced a Windows<->WSL2 path-domain gap and a
stale/wrong-corpus index. Both are resolved by a separate, self-contained plan
that MUST complete before Phase 2 starts:

- **Plan:** `docs/plans/2026-05-14-spike-1-path-contract.md`
- **Spec:** `docs/specs/2026-05-14-spike-1-path-contract-design.md`

Deliverables Phase 2 depends on:
- `_index_format.py` / `indexer.py` / `server-stdio.py` exchange workspace-relative
  POSIX paths (schema_version 2). The Phase-0 interim index
  (`~/.optimus-spike/index-msrepo-r600`, ms-core + ms-core-api subset, absolute
  paths) is superseded -- Task 8's exit-gate smoke used it and remains valid as a
  historical record.
- A full-superrepo git-tracked index at `~/.optimus-spike/index-msrepo-full-r600/`.
- `c:/_Source/ms-superrepo/.mcp.json` registering the spike-1 server.

The Phase 2 task steps below are updated to reference these artifacts.

---
```

- [ ] **Step 2: Fix the Phase 2 per-condition fixture block (Task 18 Step 2)**

In Task 18, find **Step 2: Configure per-condition fixtures** and replace the three CONDITION blocks (the `baseline`, `optimus-accurate`, and `optimus-drifted` blocks) with:

````markdown
CONDITION = baseline:
```bash
cd c:/_Source/ms-superrepo
mv DIRECTORY_INDEX.md DIRECTORY_INDEX.md.bak    # hide dir-index for baseline
mv .mcp.json .mcp.json.bak                       # hide optimus server registration
# Claude Code starts no optimus server when .mcp.json is absent.
```

CONDITION = optimus-accurate:
```bash
cd c:/_Source/ms-superrepo
ls DIRECTORY_INDEX.md .mcp.json    # confirm both present (no .bak rename)
# No manual server start: .mcp.json registers the spike-1 server and Claude Code
# owns its lifecycle -- it spawns the WSL2 stdio server on session start.
```

CONDITION = optimus-drifted:
Same as accurate (dir-index present, `.mcp.json` present) -- DO NOT pre-apply
drift; drift fires mid-task.

> **NOTE (2026-05-14, flag for Dustin):** Wiring the server through `.mcp.json`
> means Claude Code starts a fresh server per session -- the server cache is
> always cold at session start. This supersedes Task 18 Step 10's "leave the
> server running between runs (warm cache acceptable)" note. It is the more
> production-faithful setup, but it removes warm-cache runs from the protocol.
> Confirm this is the intended Phase 2 protocol before starting the 24 sessions;
> if warm-cache runs are still wanted, they need an explicit manual-server path.
````

- [ ] **Step 3: Fix the index path in Task 18 Step 10**

In Task 18 **Step 10**, find the server-log copy command:

```bash
wsl.exe -- bash -c 'cp ~/.optimus-spike/index/server.jsonl /mnt/c/_Source/optimus/spike/pre-m1-retrieval/results/task1-<condition>-run<R>.server.jsonl'
```

Replace `~/.optimus-spike/index/server.jsonl` with `~/.optimus-spike/index-msrepo-full-r600/server.jsonl`:

```bash
wsl.exe -- bash -c 'cp ~/.optimus-spike/index-msrepo-full-r600/server.jsonl /mnt/c/_Source/optimus/spike/pre-m1-retrieval/results/task1-<condition>-run<R>.server.jsonl'
```

- [ ] **Step 4: Update the File Structure tables**

In the `## File Structure` section, add to **"Files to create (outside optimus repo)"**:

```markdown
| `c:/_Source/ms-superrepo/.mcp.json` | Registers the spike-1 WSL2 server with Claude Code. Committed inside ms-superrepo; toggled per condition (`.bak` for baseline). |
```

And add a row to **"Files to modify (in optimus repo)"**:

```markdown
| `spike/pre-m1-retrieval/_index_format.py`, `indexer.py`, `server-stdio.py` | Path contract + git-tracked corpus -- see `docs/plans/2026-05-14-spike-1-path-contract.md`. |
```

- [ ] **Step 5: Verify the closeout plan still reads coherently**

```bash
wsl.exe -- bash -c 'grep -n "Phase 1.5\|index-msrepo-full-r600\|.mcp.json.bak" /mnt/c/_Source/optimus/docs/plans/2026-05-13-spike-1-closeout.md'
```

Expected: the Phase 1.5 heading, the new index path in Step 10, and the `.mcp.json.bak` baseline line all appear. Skim the Phase 1.5 -> Phase 2 transition once for flow.

- [ ] **Step 6: Commit**

```bash
git add docs/plans/2026-05-13-spike-1-closeout.md docs/plans/2026-05-14-spike-1-path-contract.md
git commit -m "$(cat <<'EOF'
docs(spike-1): path-contract plan + closeout-plan Phase 1.5 amendment

Phase E Task 11 of docs/plans/2026-05-14-spike-1-path-contract.md.

Adds the path-contract implementation plan and inserts a Phase 1.5 gate into the
close-out plan: path contract + full-superrepo index rebuild must land before
Phase 2. Fixes Phase 2 references -- new index dir (index-msrepo-full-r600),
.mcp.json-driven server lifecycle (baseline hides it via .bak, symmetric with
DIRECTORY_INDEX.md). Flags the cold-cache implication of the .mcp.json-managed
server for Dustin to confirm before the 24 sessions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(If this plan file was already committed when it was written, `git add` of it is a no-op and the commit carries only the closeout-plan amendment.)

---

## Self-Review

**Spec coverage** (`docs/specs/2026-05-14-spike-1-path-contract-design.md`):

| Spec requirement | Task |
|---|---|
| `_index_format.py`: `file_path` workspace-relative POSIX `str`; `schema_version` 1->2 | Task 1 |
| `indexer.py`: `main()` relativizes against `target_root`; corpus selection changes | Tasks 1 (relativize), 4-5 (git-tracked corpus) |
| `server-stdio.py`: `confine_path` unchanged; `optimus_search` return shape; `server.jsonl` logs relative | Task 2 |
| Index git-tracked source, not a raw walk; per-submodule enumeration | Task 4 |
| Error: schema-1 index fails fast and loud | Task 1 (`load_index` raises), Task 2 (server inherits via `_ensure_index`) |
| Error: escape attempts still raise via `confine_path` | Task 2 (`confined_relative` delegates; `test_confine.py` covers) |
| Test: indexer emits only relative POSIX paths | Task 1 (`test_iter_records.py`) |
| Test: `confine_path` rejects `../` + symlink escape on relative input | Task 2 (`test_confine.py`) |
| Test: round-trip -- index, query, paths relative + resolve | Task 3 (`test_path_contract.py`), Task 1 (`test_two_stage_search.py`) |
| Test: forward-compat -- same index, two `target_root`s, identical paths | Task 3 (`test_index_is_mount_independent`) |
| Test: existing suite stays green | Task 7 |
| Manual smoke -- Windows agent opens a returned path | Task 10 Step 4 |
| Closeout plan needs amendment for index rebuild + contract | Task 11 |

All spec sections map to a task. The spec's "Open question -- deferred" (un-indexed query path for uncommitted code) is explicitly out of spike-1 scope -- correctly absent from this plan.

**Placeholder scan:** No TBD / "add error handling" / "write tests for the above" / "similar to Task N" -- every code step carries complete content.

**Type consistency:** `ChunkRecord.file_path: str` (Task 1) is consumed as a `str` everywhere downstream -- `iter_records` builds it via `.as_posix()`, `persist_index`/`load_index` write/read it raw, `two_stage_search` returns it directly, `confined_relative` returns `.as_posix()`, `verify-index.py` asserts `isinstance(..., str)`. `walk_target` and `git_tracked_files` share the `(Path, str)` yield contract and the `_read_indexable` filter. `select_walker` returns one of those two callables; `iter_records(target_root, walker)` and `main(..., walker=...)` accept it. Consistent throughout.
