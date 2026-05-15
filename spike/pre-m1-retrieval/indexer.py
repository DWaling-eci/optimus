"""Spike-1 on-disk chunk indexer.

SESSION 1 STATE: skeleton only. Real implementation lands in session 2.

Reads the test target's source tree, chunks every file, embeds each chunk with
Nomic CodeRankEmbed (NO query-side prefix at index time -- prefix is query-only
per the model card), and persists (chunks + embeddings + metadata) to disk.
The MCP server reads this artifact at startup; queries do NOT re-embed documents.

Locked design per docs/spikes/spike-1-prep-brief.md section 5:
  - Built ONCE per test target. Re-runnable.
  - No spaCy. No identifier normalization. No query-side preprocessing.
  - Index format: manifest.json + chunks.jsonl + embeddings.npy via
    _index_format.py (no pickle).

Out of scope (per brief): incremental updates, watch-mode, multi-target, sharding.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


DEFAULT_CHUNK_SIZE = 600
"""Char-window chunk size, revised 2026-05-13 from the baseline-record's 1500.

Why 600 (not 700 as initially planned): ColBERTv2's `doc_maxlen = 220`
tokens. Kotlin code in the live test corpus tokenizes at ~3.5 chars/token
on average, but TDD with an adversarial-dense Kotlin fixture (no
whitespace gaps, no comments) measured 3.125 chars/token worst case. At
700 chars, the dense worst case hits 224 tokens -- 4 over doc_maxlen.
At 600 chars, the dense worst case is ~192 tokens, with 20-token safety
margin under doc_maxlen for tokenizer special tokens + future corpus
shifts.

At the original 1500, 87% of chunks exceeded doc_maxlen and 46% of all
indexed tokens were silently truncated at rerank time (`diag-tokens.py`
reproducer, 2026-05-13).

Per brief §1 implementation-tactics authority. Cross-condition
comparability preserved because the revised protocol applies uniformly
across all spike conditions. Invariant under test:
`tests/test_chunk_colbert_invariant.py`.
"""

DEFAULT_INDEX_DIR = Path.home() / ".optimus-spike" / "index"

MAX_FILE_BYTES = 1 * 1024 * 1024  # Cap per file to keep indexing bounded. 1 MB.

NOMIC_MODEL_ID = "nomic-ai/CodeRankEmbed"


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

    NOTE: unlike walk_target, this includes tracked dotfiles and
    dot-directories (.gitignore, .github/, .cursor/, etc.) -- git-tracked means
    the whole committed corpus, not a filtered view of it.
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


def select_walker(target_root: Path):
    """Pick the corpus enumerator: git-tracked for git working trees, else walk.

    Git-tracked is production-faithful (build output gitignored, uncommitted
    scratch excluded). Non-git trees -- test fixtures -- fall back to the
    filtered filesystem walk.
    """
    # .exists() (not .is_dir()) is deliberate: a git worktree or submodule root
    # has .git as a FILE, not a directory, and git ls-files works fine from it.
    return git_tracked_files if (target_root / ".git").exists() else walk_target


def chunk_file(content: str, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """Yield (start_offset, chunk_text) tuples for the file content.

    Char-window split, no overlap. Deterministic.
    """
    for start in range(0, len(content), chunk_size):
        yield start, content[start:start + chunk_size]


def iter_records(target_root: Path, walker=walk_target):
    """Yield ChunkRecords for every file `walker` enumerates under target_root.

    A `walker` yields (absolute Path, str content) tuples; it does NOT need to
    relativize -- `iter_records` resolves each path and rebases it against
    target_root. Paths a walker yields MUST be under target_root.

    file_path on each record is workspace-relative POSIX (relative to
    target_root) per docs/specs/2026-05-14-spike-1-path-contract-design.md.
    Relativization happens here, at index-build time, so the persisted index is
    portable and mount-location-independent.

    `walker` defaults to walk_target here so iter_records stays callable
    independently; main() auto-selects via select_walker when not overridden.
    """
    from _index_format import ChunkRecord

    target_root = target_root.resolve()
    chunk_id = 0
    for file_path, content in walker(target_root):
        try:
            rel = file_path.resolve().relative_to(target_root).as_posix()
        except ValueError:
            raise ValueError(
                f"walker yielded {file_path!r}, which is not under "
                f"target_root={target_root!r}. Check the walker implementation."
            ) from None
        for start, text in chunk_file(content):
            yield ChunkRecord(
                chunk_id=chunk_id,
                file_path=rel,
                start_offset=start,
                end_offset=start + len(text),
                text=text,
            )
            chunk_id += 1


def embed_chunks(chunk_texts):
    """Run Nomic CodeRankEmbed over chunk texts. No query prefix at index time.

    The query-side prefix is only applied at search time per the CodeRankEmbed
    model card. Document-side encoding is plain text.
    """
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


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.stderr.write("usage: indexer.py <test-target-root> [out-dir]\n")
        sys.exit(2)
    target = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_INDEX_DIR
    main(target, out)
