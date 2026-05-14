# Design: Spike-1 Phase-2 Path Contract -- Workspace-Relative Path Handling

**Date:** 2026-05-14
**Status:** Approved (brainstorming) -- pending implementation plan
**Owner:** Dustin
**Extends:** `docs/specs/2026-05-13-spike-1-closeout-design.md`

## Problem

Spike-1 Phase 2 runs 24 Claude Code sessions on the Windows host against `C:\_Source\ms-superrepo`, with the retrieval server in WSL2. The server's index bakes absolute paths, and `confine_path` is a pure security gate with no rebasing -- so the server would hand the Windows agent `/mnt/c/...` POSIX paths it cannot open. That contaminates the H1/H2/H3 agent-behavior metrics with a harness artifact.

About half of ~600 target developers run Claude/Cursor directly on Windows, so this is not a spike-harness quirk -- it is a production-critical adoption concern. The fix must be architecturally sound and forward-compatible, not a band-aid that diverges from real usage.

## The contract

**Invariant: Optimus never exchanges an absolute path across the MCP boundary.**

- Inbound: the agent passes workspace-relative paths; the server joins onto the workspace root and confines.
- Outbound: the server returns workspace-relative paths; the agent resolves them against its own workspace CWD.
- Because no absolute path crosses the boundary, the Windows-Linux path-domain seam has nothing to translate. It stops existing.

**Path uniqueness invariant.** Index-stored paths are relative to `target_root`, the root of the indexed scope, chosen so that every stored path is unique within the index. The path is carried metadata, never an input to the retrieval models, so the risk is not model confusion but key collision in the index as a store and in anything that compares or aggregates by path (the `server.jsonl` log, the chat-report cross-check). In spike-1, `target_root` is the `ms-superrepo` root, so every path leads with its submodule directory (`ms-core-api/...`, `ms-option-api/...`) and is unique by construction. Forward-compat: in production, where one index may span multiple project workspaces under the shared parent mount, `target_root` is the parent mount, so stored paths lead with the workspace directory name. The outbound wire format stays workspace-relative; the server strips the leading workspace component (see Scope boundary).

**Spike-1 simplification.** Spike-1 is single-client, single-workspace, so `workspace_root == target_root`, set statically from `OPTIMUS_SPIKE_TARGET_ROOT` (or the index manifest's `target_root`).

**Scope boundary.** The multi-client registration handshake -- how a running Optimus learns each IDE's active workspace root -- is spike-2 / M1 territory and is NOT built here. Spike-1's static single-workspace case is the correct degenerate case of that contract, not a shortcut around it.

## Approach (locked)

Relativization happens at **index-build time** (Approach 1 of 2 considered). The index stores workspace-relative paths, making the index artifact portable and mount-location-independent.

The rejected alternative (Approach 2: keep absolute paths in the index, relativize on return) leaves the index coupled to one machine's mount layout. It would "work" for spike-1 because the mount path is stable, but it bakes in exactly the host-specific assumption an architecturally-sound baseline must keep out, and would be redone for production anyway.

## Components and changes

### `_index_format.py`
- `ChunkRecord.file_path` becomes a workspace-relative POSIX string.
- `manifest.json` `schema_version` bumps 1 -> 2. Existing schema-1 (absolute-path) indexes become incompatible by design.

### `indexer.py`
- `main()` relativizes each file against `target_root` (`.relative_to(target_root).as_posix()`) before constructing the `ChunkRecord`.
- Corpus selection changes -- see "Index corpus correctness" below.

### `server-stdio.py`
- `confine_path` is **unchanged** -- it already accepts relative input, joins onto `target_root`, realpaths, and prefix-checks.
- `optimus_search` return shape changes: emit `confined.relative_to(target_root).as_posix()` instead of `str(confined)`.
- `server.jsonl` logs the relative path (what the agent sees) for clean cross-check against the chat-report toolkit.

### Data flow

```
BUILD TIME  (indexer.py, once over the target)
  walk target -> abs path -> relative_to(target_root) -> "ms-core-api/src/.../House.kt" -> index

QUERY TIME  (server-stdio.py)
  index record "ms-core-api/src/.../House.kt"
       | confine_path:  target_root / rel -> realpath -> prefix-check   [security gate, raises on escape]
       | return-shape:  .relative_to(target_root).as_posix()
       v
  "ms-core-api/src/.../House.kt" -> agent resolves against its own workspace CWD
```

## Index corpus correctness

The current indexes (`index-msrepo`, `index-msrepo-r600`) are unusable for Phase 2 independent of path shape: wrong corpus (ms-core + ms-core-api subset, not the full 26-submodule superrepo) and no build-artifact filtering (`ms-core-api/` carries `build/` and `target/`). The relative-path switch rides along on the required rebuild.

**Design call: index git-tracked source, not a raw filesystem walk.**

Rationale:

1. **Production faithfulness.** A production Optimus indexes source, not build output. `build/`, `target/`, `node_modules/` are gitignored. Git-tracked is the production-faithful, deterministic corpus definition.
2. **Dirty-repo isolation.** Developers routinely create new directories and files that may never be committed. Git-tracked semantics keep transient, uncommitted scratch out of the index -- the index reflects the intentional, committed codebase, not whatever happens to be sitting in the working tree at index-build time.

The enumeration *mechanism* (per-submodule `git ls-files` vs a `.gitignore`-respecting walk -- `git ls-files --recurse-submodules` did not recurse from WSL during prep probing) is an implementation-plan detail. Git-tracked semantics is the design target; a denylist walk is the fallback only if enumeration proves impractical.

## Error handling

- **Escape attempts.** `confine_path` raises `ValueError`, surfaced as a structured MCP error. Unchanged, still load-bearing.
- **Schema mismatch.** The server reading a `schema_version: 1` (absolute-path) index fails fast and loud with a clear "rebuild required" error. No silent mis-serving of stale absolute paths.
- **Mount independence.** Because records are relative, the server's runtime `target_root` may differ from the index's build-time `target_root` and everything still resolves. The manifest records build-time `target_root` for traceability only.

## Testing

- Unit -- `indexer` emits only relative POSIX paths: no absolute, no backslashes, no `..`.
- Unit -- `confine_path` still rejects `../` traversal and out-of-mount symlinks given relative input.
- Unit -- round-trip: index a fixture tree, query, assert returned paths are relative and resolve correctly under `target_root`.
- Forward-compat assertion -- the same index pointed at two different `target_root` values returns identical relative paths (proves mount independence).
- Regression -- the existing 36-test spike-1 suite stays green; this change touches all three tested modules.
- Manual smoke -- build the real index, run the server, issue a query, confirm the Windows agent opens a returned path.

## Open question -- deferred (not spike-1 scope)

**Un-indexed query path for uncommitted code.** Git-tracked indexing means new, uncommitted source is invisible to `optimus_search`. For broad-scope or planning tasks against a repo with relevant uncommitted changes -- e.g. cross-module-trace or pattern-find style queries (cf. `spike/pre-m1-retrieval/tasks.md` Task 3, Task 4) -- the developer's query should arguably include that new code.

Open: can `optimus_search` support an un-indexed or live fallback (a working-tree walk or grep over uncommitted-but-relevant paths, an incremental index, or a hybrid) so a feature-branch developer is not retrieving against a stale picture of their own work?

Recorded here so the trade-off is not silently lost. **Out of scope for spike-1.** Needs a home in M1 / spike-2 design or its own decision record. Captured 2026-05-14 at Dustin's direction.

## References

- `docs/specs/2026-05-13-spike-1-closeout-design.md` -- spike-1 close-out design this extends.
- `docs/plans/2026-05-13-spike-1-closeout.md` -- spike-1 plan; needs amendment for the index rebuild and this contract.
- `docs/decisions/secure-singleton-mcp-baseline.md` -- production path model (`${HOST_PARENT_DIR}` <-> `/mnt/parent_mount`, `_confine_path`).
- `docs/decomp/pre-M1-spikes.md` -- spike-1 vs spike-2 scope; spike-2 owns end-to-end WSL2 path translation.
- `spike/pre-m1-retrieval/` -- `server-stdio.py`, `indexer.py`, `_index_format.py`, `tasks.md`.
