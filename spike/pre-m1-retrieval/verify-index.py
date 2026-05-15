"""Standalone index sanity checker -- path-contract invariants.

Diagnostic script (no test, per the spike-1 convention for diag-tokens.py /
install_probe.py). Loads an on-disk index and asserts the
docs/specs/2026-05-14-spike-1-path-contract-design.md contract:
  - manifest schema_version == 2
  - every chunk file_path is a workspace-relative POSIX string
    (no leading '/', no '\\', no '..' segment, no drive letter)

Usage:
    python verify-index.py <index-dir>

Exit 0 = all invariants hold. Exit 1 = violation (details on stderr).
Exit 2 = bad invocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _index_format import INDEX_SCHEMA_VERSION, load_index


def verify(index_dir: Path) -> int:
    manifest, records, embeddings = load_index(index_dir)

    if manifest.get("schema_version") != INDEX_SCHEMA_VERSION:
        print(
            f"FAIL: schema_version {manifest.get('schema_version')!r} "
            f"!= {INDEX_SCHEMA_VERSION}",
            file=sys.stderr,
        )
        return 1

    violations: list[str] = []
    for r in records:
        p = r.file_path
        if not isinstance(p, str):
            violations.append(f"chunk {r.chunk_id}: file_path is {type(p).__name__}, not str")
            continue
        if p.startswith("/"):
            violations.append(f"chunk {r.chunk_id}: absolute POSIX path {p!r}")
        if "\\" in p:
            violations.append(f"chunk {r.chunk_id}: backslash in {p!r}")
        if ".." in p.split("/"):
            violations.append(f"chunk {r.chunk_id}: '..' segment in {p!r}")
        if len(p) >= 2 and p[1] == ":":
            violations.append(f"chunk {r.chunk_id}: drive letter in {p!r}")

    if violations:
        for v in violations[:20]:
            print(f"FAIL: {v}", file=sys.stderr)
        if len(violations) > 20:
            print(f"... and {len(violations) - 20} more", file=sys.stderr)
        return 1

    print(
        f"OK: {index_dir} -- schema {manifest['schema_version']}, "
        f"{len(records)} chunks, {embeddings.shape[0]} embeddings, "
        f"all paths workspace-relative POSIX"
    )
    for r in records[:5]:
        print(f"  sample: {r.file_path}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python verify-index.py <index-dir>", file=sys.stderr)
        return 2
    index_dir = Path(argv[1])
    if not index_dir.is_dir():
        print(f"error: {index_dir} is not a directory", file=sys.stderr)
        return 2
    return verify(index_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
