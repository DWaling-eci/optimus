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
