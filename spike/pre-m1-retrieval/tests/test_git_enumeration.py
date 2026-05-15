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


def test_exact_tracked_set(git_superrepo):
    """The enumerated set is exactly the tracked files -- tracked dotfiles
    (.gitignore, .gitmodules) included, gitlink/untracked/gitignored excluded."""
    expected = {
        "root_tracked.py",
        ".gitignore",
        ".gitmodules",
        "vendored/sub_tracked.py",
    }
    assert _rels(git_superrepo) == expected


def test_select_walker_git_repo_uses_git_tracked(git_superrepo):
    from indexer import git_tracked_files, select_walker
    assert select_walker(git_superrepo) is git_tracked_files


def test_select_walker_plain_dir_uses_walk(tmp_path):
    from indexer import select_walker, walk_target
    assert select_walker(tmp_path) is walk_target
