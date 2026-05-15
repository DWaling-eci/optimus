"""Path confinement security tests.

Mirrors the contract in secure-singleton-mcp-baseline.md SECURITY callout:
realpath + prefix check; symlinks escaping must raise.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# server-stdio is a hyphenated filename; import via importlib
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
