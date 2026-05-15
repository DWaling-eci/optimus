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

    `walker` defaults to walk_target here; `main()` keeps its own keyword-only
    default (Task 5 of the path-contract plan switches main()'s default to an
    auto-selector).
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


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.stderr.write("usage: indexer.py <test-target-root> [out-dir]\n")
        sys.exit(2)
    target = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_INDEX_DIR
    main(target, out)
