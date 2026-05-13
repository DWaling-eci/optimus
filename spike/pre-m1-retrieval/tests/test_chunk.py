"""Chunk_file determinism + boundary tests.

The spike's measurement integrity depends on chunking being deterministic
(same input -> same chunks across runs). If chunks drift between runs, the
retrieval-behavior comparisons in the report become noisy.
"""

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
