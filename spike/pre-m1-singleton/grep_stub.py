"""Canned optimus_grep stub used by both transport variants.

Spike-2 is testing TRANSPORT + CONCURRENCY + DISCOVERY, NOT retrieval quality.
This stub does a real-but-shallow grep against the parent-mount so concurrent
calls can be verified for correctness, but does not pretend to be the
production retrieval pipeline (which is owned by M1.1+ per the secure-
singleton-mcp-baseline decision record).
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GrepMatch:
    path: str
    line_no: int
    line: str


async def grep_under_mount(
    mount_root: Path,
    pattern: str,
    *,
    file_glob: str = "*.md",
    max_files: int = 200,
    max_matches: int = 100,
    walk_budget_s: float = 3.0,
) -> tuple[list[GrepMatch], dict]:
    """Walk mount_root, find lines matching pattern, return up to max_matches.

    Has a wall-clock budget (walk_budget_s); if exceeded the walk truncates and
    the diagnostics dict surfaces truncated_by_budget=True. This is load-bearing
    for spike-2 -- bind-mounting Windows filesystems into WSL2 containers via 9P
    is dramatically slower than a native filesystem walk, and the spike needs to
    return a deterministic shape regardless of perf.

    Default file_glob narrowed from "*" to "*.md" -- this stub exists to validate
    concurrent transport, not retrieval quality. The narrow glob keeps the walk
    fast enough on slow-but-correct filesystems.

    Yields control to the event loop periodically so this coroutine doesn't
    block other concurrent calls under the asyncio main loop.
    """
    import time

    regex = re.compile(pattern)
    matches: list[GrepMatch] = []
    files_scanned = 0
    truncated_by_budget = False
    started = time.monotonic()

    try:
        for path in mount_root.rglob(file_glob):
            if time.monotonic() - started > walk_budget_s:
                truncated_by_budget = True
                break
            if files_scanned >= max_files:
                break
            if not path.is_file():
                continue
            files_scanned += 1
            try:
                with path.open("r", encoding="utf-8", errors="replace") as fh:
                    for line_no, line in enumerate(fh, start=1):
                        if regex.search(line):
                            matches.append(
                                GrepMatch(
                                    path=str(path.relative_to(mount_root)),
                                    line_no=line_no,
                                    line=line.rstrip("\n")[:200],
                                )
                            )
                            if len(matches) >= max_matches:
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if len(matches) >= max_matches:
                break
            # Yield to the event loop every file so concurrent grep calls interleave.
            await asyncio.sleep(0)
    except OSError as exc:
        # Filesystem walk error -- surface in diagnostics rather than crash.
        return matches, {
            "files_scanned": files_scanned,
            "walk_error": f"{type(exc).__name__}: {exc}",
            "truncated_by_budget": truncated_by_budget,
            "elapsed_s": time.monotonic() - started,
        }

    return matches, {
        "files_scanned": files_scanned,
        "truncated_by_budget": truncated_by_budget,
        "elapsed_s": time.monotonic() - started,
    }


def matches_to_jsonable(matches: list[GrepMatch]) -> list[dict[str, object]]:
    return [{"path": m.path, "line_no": m.line_no, "line": m.line} for m in matches]
