"""Per-task drift fixture for spike-1 H3 (drifted dir-index resilience).

Applies a task-specific filesystem mutation (1 file added, 1 directory renamed)
to the test target. Manual invocation by spike runner at the drift moment per
docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md section 4 Phase 1C.

CLI:
    python drift-fixture.py --task <1|2|3|4>   # apply drift for task N
    python drift-fixture.py --reset            # revert all drift

Reset is git-backed AND submodule-aware. The test target (c:/_Source/ms-superrepo)
is a SUPERREPO of git submodules, and every drift lands inside a submodule working
tree. A superrepo-level `git reset --hard` + `git clean -fd` does NOT reach inside
submodules, so --reset resets each affected submodule individually (the set of
submodules DRIFT_PLANS touches), then the superrepo.

Target root resolution:
    1. env var DRIFT_TARGET_ROOT (used by tests)
    2. default: c:/_Source/ms-superrepo
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


# Per-task drift plans. Each task: ONE add (file path relative to target_root)
# + ONE rename (oldpath -> newpath). Retargeted at the real ms-superrepo layout
# (Task 14 Step 2): every path is a real directory, listed in
# c:/_Source/ms-superrepo/DIRECTORY_INDEX.md, inside the git submodule that the
# matching controlled task (spike/pre-m1-retrieval/tasks.md) exercises.
#
# CONSTRAINT: each task's `add` file MUST live inside its `rename` source dir.
# tests/test_drift_fixture.py's fake_target fixture only materializes `rename`
# source dirs; an `add` parent outside that subtree would never get created. It
# is also realistic drift -- a file added to a dir that then gets renamed.

DRIFT_PLANS = {
    1: {
        "add": "ms-core-api/src/test/drift_added_1.kt",
        "rename": ("ms-core-api/src/test", "ms-core-api/src/test_renamed_1"),
    },
    2: {
        "add": "ms-core-api/config/custom/drift_added_2.json",
        "rename": ("ms-core-api/config/custom", "ms-core-api/config/custom_renamed_2"),
    },
    3: {
        "add": "ms-option-api/config/custom/drift_added_3.json",
        "rename": ("ms-option-api/config/custom", "ms-option-api/config/custom_renamed_3"),
    },
    4: {
        "add": "ms-event-store/config/drift_added_4.kt",
        "rename": ("ms-event-store/config", "ms-event-store/config_renamed_4"),
    },
}


def resolve_target_root() -> Path:
    """Pick target root from env or fall back to c:/_Source/ms-superrepo."""
    env = os.environ.get("DRIFT_TARGET_ROOT")
    if env:
        return Path(env).resolve()
    return Path("c:/_Source/ms-superrepo").resolve()


def is_git_repo(path: Path) -> bool:
    """True if `path` is a git working tree."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def affected_submodules() -> list[str]:
    """Submodule dirs DRIFT_PLANS touches -- the first path component of every
    add/rename path. Used to scope --reset to exactly those submodules."""
    subs: set[str] = set()
    for plan in DRIFT_PLANS.values():
        subs.add(Path(plan["add"]).parts[0])
        subs.add(Path(plan["rename"][0]).parts[0])
    return sorted(subs)


def apply_drift(task_n: int, target_root: Path) -> int:
    """Apply task N's drift to target_root. Returns 0 on success."""
    plan = DRIFT_PLANS.get(task_n)
    if plan is None:
        print(f"error: unknown task {task_n}; valid: 1-4", file=sys.stderr)
        return 2

    add_path = target_root / plan["add"]
    rename_from = target_root / plan["rename"][0]
    rename_to = target_root / plan["rename"][1]

    # Idempotency check: the rename is the load-bearing signal. If the target
    # dir exists and the source is gone, drift is already applied -- exit 0.
    # (Cannot key on add_path: `add` lives inside `rename_from`, so the added
    # file moves to rename_to/... on apply and add_path no longer exists.)
    if rename_to.exists() and not rename_from.exists():
        print(f"task {task_n} drift already applied (idempotent skip)", file=sys.stderr)
        return 0

    # Sanity: source dir must exist before rename
    if not rename_from.exists():
        print(
            f"error: rename source {rename_from} does not exist. Reset first or "
            f"check DRIFT_PLANS matches the real target layout.",
            file=sys.stderr,
        )
        return 3

    # Apply: add the file first (inside rename_from, asserted present above),
    # then rename the dir -- the added file moves with the rename to rename_to/...
    # If a future DRIFT_PLANS entry placed `add` outside rename_from, write_text
    # raises FileNotFoundError loudly rather than a silent mkdir masking it.
    add_path.write_text(
        f"// spike-1 drift fixture -- task {task_n}, added 2026-05-13\n"
    )
    rename_from.rename(rename_to)
    print(
        f"task {task_n}: added {plan['add']}, renamed {plan['rename'][0]} -> {plan['rename'][1]}",
        file=sys.stderr,
    )
    return 0


def reset_drift(target_root: Path) -> int:
    """Reset target_root to git HEAD + clean untracked. Returns 0 on success.

    target_root is a submodule superrepo; all drift lands inside submodule
    working trees. A superrepo-level reset/clean does not recurse into
    submodules, so reset each affected submodule individually first, then the
    superrepo. Scoped to the submodules DRIFT_PLANS touches -- not all 27.
    """
    if not is_git_repo(target_root):
        print(
            f"error: {target_root} is not a git repo; cannot reset",
            file=sys.stderr,
        )
        return 4
    # Reverse drift inside each affected submodule.
    subs = affected_submodules()
    for sub in subs:
        sub_path = target_root / sub
        if not sub_path.is_dir():
            # Keeps --reset safe to run on a partially-set-up target.
            print(f"reset: submodule dir {sub} not found, skipping", file=sys.stderr)
            continue
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=sub_path, check=True)
        subprocess.run(["git", "clean", "-fd"], cwd=sub_path, check=True)
    # Then the superrepo itself (gitlinks + any superrepo-level untracked).
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=target_root, check=True)
    subprocess.run(["git", "clean", "-fd"], cwd=target_root, check=True)
    print(
        f"reset {target_root}: {len(subs)} submodule(s) + superrepo to HEAD + clean",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spike-1 H3 drift fixture")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--task", type=int, choices=[1, 2, 3, 4], help="apply drift for task N")
    g.add_argument("--reset", action="store_true", help="reset target root via git")
    args = parser.parse_args(argv)

    target_root = resolve_target_root()
    if not target_root.is_dir():
        print(f"error: target root {target_root} not found or not a directory", file=sys.stderr)
        return 1

    if args.reset:
        return reset_drift(target_root)
    return apply_drift(args.task, target_root)


if __name__ == "__main__":
    sys.exit(main())
