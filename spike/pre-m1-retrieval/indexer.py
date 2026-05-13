"""Spike-1 on-disk chunk indexer.

SESSION 1 STATE: skeleton only. Real implementation lands in session 2.

Reads the test target's source tree, chunks every file, embeds each chunk with
Nomic CodeRankEmbed (NO query-side prefix at index time -- prefix is query-only
per the model card), and persists (chunks + embeddings + metadata) to disk.
The MCP server reads this artifact at startup; queries do NOT re-embed documents.

Locked design per docs/spikes/spike-1-prep-brief.md section 5:
  - Built ONCE per test target. Re-runnable.
  - No spaCy. No identifier normalization. No query-side preprocessing.
  - Index format = TBD (numpy .npz + JSON metadata most likely; finalize session 2).

Out of scope (per brief): incremental updates, watch-mode, multi-target, sharding.
"""

from __future__ import annotations

from pathlib import Path


DEFAULT_CHUNK_SIZE = 1500
"""Char-window chunk size per baseline-decision-record illustrative server.py.

Implementation may revise to AST-aware or garp-driven candidates per brief §1
"implementation tactics" unilateral-decision authority. Document any divergence
in the spike report's methodology section.
"""

DEFAULT_INDEX_DIR = Path.home() / ".optimus-spike" / "index"


def walk_target(target_root: Path):
    """Yield (file_path, content) for every readable text file under target_root.

    Skip dotfiles and dot-directories. Skip binary files (encoding errors).
    """
    raise NotImplementedError("session 2: implement file walk + binary skip + encoding handling")


def chunk_file(content: str, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """Yield (start_offset, chunk_text) tuples for the file content."""
    raise NotImplementedError("session 2: implement char-window chunking (or AST-aware variant)")


def embed_chunks(chunks):
    """Run Nomic CodeRankEmbed over a list of chunk texts.

    No query-side prefix at index time. Document-side prefix per the CodeRankEmbed
    model card (verify in session 1 install probe; record exact prefix in spike report).
    """
    raise NotImplementedError("session 2: implement after install probe confirms prefixes")


def persist_index(out_dir: Path, metadata, embeddings, texts):
    """Write index artifacts to out_dir.

    Format TBD; lock in session 2. Must round-trip via load_index() in server-stdio.py.
    """
    raise NotImplementedError("session 2: implement after format decision")


def main(target_root: Path, out_dir: Path = DEFAULT_INDEX_DIR) -> None:
    """Build index for target_root, write to out_dir."""
    raise NotImplementedError("session 2: wire walk -> chunk -> embed -> persist pipeline")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.stderr.write("usage: indexer.py <test-target-root> [out-dir]\n")
        sys.exit(2)
    target = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_INDEX_DIR
    main(target, out)
