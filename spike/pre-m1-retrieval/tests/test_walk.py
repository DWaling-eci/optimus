"""walk_target filter tests."""

from pathlib import Path

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
