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
        assert ":" not in r.file_path  # no Windows drive letter
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
        # confine_path calls Path.resolve(); the file must exist for the
        # realpath syscall to execute identically on all platforms.
        (root / "ms-core-api" / "src").mkdir(parents=True)
        (root / rel).write_text("class House")

    out_a = confined_relative(stored, root_a)
    out_b = confined_relative(stored, root_b)
    assert out_a == out_b == rel
