"""Verify drift-fixture.py applies + reverses cleanly per task."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _load_drift_plans():
    """Import DRIFT_PLANS from the actual script under test."""
    spec_path = Path(__file__).resolve().parent.parent / "drift-fixture.py"
    spec = importlib.util.spec_from_file_location("drift_fixture", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DRIFT_PLANS


@pytest.fixture
def fake_target(tmp_path: Path) -> Path:
    """Build a fake test-target tree containing every directory DRIFT_PLANS expects.

    Reads DRIFT_PLANS from drift-fixture.py so the fixture stays in sync if the
    plans are edited (Task 14 Step 2 expects DRIFT_PLANS to be retargeted at the
    real ms-superrepo layout).

    Also git-inits + commits baseline so --reset (git-backed) works in tests.
    """
    plans = _load_drift_plans()
    # Materialize every rename source directory with one placeholder file.
    for task_n, plan in plans.items():
        rename_src = tmp_path / plan["rename"][0]
        rename_src.mkdir(parents=True, exist_ok=True)
        (rename_src / f"placeholder_{task_n}.kt").write_text(
            f"// placeholder for task {task_n}\n"
        )
    # git-init + commit baseline so --reset has somewhere to return to
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@spike"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "spike-test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "baseline"], cwd=tmp_path, check=True
    )
    return tmp_path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Invoke drift-fixture via the same interpreter pytest is running under."""
    env = os.environ.copy()
    env["DRIFT_TARGET_ROOT"] = str(cwd)
    return subprocess.run(
        [sys.executable, "drift-fixture.py", *args],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _snapshot(target_root: Path) -> set[str]:
    """Set of tree paths relative to target_root, excluding .git/ internals."""
    return {
        str(p.relative_to(target_root))
        for p in target_root.rglob("*")
        if ".git" not in p.relative_to(target_root).parts
    }


def test_apply_task1_adds_file_and_renames_dir(fake_target):
    """--task 1 adds one file + renames one directory."""
    before = _snapshot(fake_target)
    result = _run(["--task", "1"], fake_target)
    assert result.returncode == 0, result.stderr
    after = _snapshot(fake_target)
    # State changed: at least one path differs from before.
    assert after != before, f"task 1 produced no observable change"


def test_reset_returns_target_to_pristine(fake_target):
    """--reset reverses the apply cleanly (git status --porcelain empty after reset)."""
    snapshot_before = _snapshot(fake_target)
    _run(["--task", "1"], fake_target)
    _run(["--reset"], fake_target)
    snapshot_after = _snapshot(fake_target)
    assert snapshot_before == snapshot_after, (
        f"reset did not restore tree: differs at {snapshot_before ^ snapshot_after}"
    )
    # Also confirm git sees a clean working tree
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=fake_target,
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout.strip() == "", f"git not clean after reset: {status.stdout!r}"


def test_apply_is_idempotent(fake_target):
    """Re-applying the same task is a no-op (or graceful skip)."""
    _run(["--task", "1"], fake_target)
    snapshot1 = _snapshot(fake_target)
    result2 = _run(["--task", "1"], fake_target)
    snapshot2 = _snapshot(fake_target)
    assert snapshot1 == snapshot2, "second apply changed state"
    # returncode 0 (idempotent success) or non-zero with a clear "already applied" message
    if result2.returncode != 0:
        msg = (result2.stderr + result2.stdout).lower()
        assert "already" in msg, f"non-zero exit without 'already' message: {msg}"


def test_all_four_tasks_have_drift_content(fake_target):
    """Tasks 1-4 each define a non-empty drift action."""
    for task_n in (1, 2, 3, 4):
        # reset first to be safe
        _run(["--reset"], fake_target)
        before = _snapshot(fake_target)
        result = _run(["--task", str(task_n)], fake_target)
        assert result.returncode == 0, f"task {task_n}: {result.stderr}"
        after = _snapshot(fake_target)
        assert before != after, f"task {task_n} produced no drift"
