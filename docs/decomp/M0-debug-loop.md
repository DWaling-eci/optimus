# M0 -- In-Container Debug Loop

**Status:** clean stub. The dev experience for stepping through code that runs inside the singleton container is currently undocumented. The shape below is dictated by the container baseline implementation defined in the [Secure Singleton MCP Baseline](docs/decisions/secure-singleton-mcp-baseline.md) document -- specifically the locked `network_mode: "none"` isolation posture.

## Goal

A developer assigned to fix a bug in (say) `src/optimus/retrieval/search.py` can attach a debugger from their IDE in seconds, set breakpoints, and step through the code as it runs inside the container.

## Hard constraint: no TCP debug port

`network_mode: "none"` (per `secure-singleton-mcp-baseline.md` section 2) is the architectural enforcement of TR-06's zero-external-runtime-traffic mandate. **Production isolation MUST NOT be relaxed for development convenience.** Exposing a debugpy TCP port (e.g., `5678`) is incompatible with the locked network posture; if a future need requires a different debug pattern, it goes through normal decision-record revision (PR + sign-off + cross-doc propagation), NOT a quiet hole punched in the container.

debugpy v1.x supports Unix-domain-socket listen targets natively (`debugpy.listen(("unix:///path/to/sock",))` -- see the [debugpy server-side API docs](https://github.com/microsoft/debugpy)). We use that instead.

## Approach

- Add `debugpy` to the container's Python environment.
- Container entrypoint conditionally starts debugpy listening on a **Unix domain socket** at `/var/optimus/sockets/debugpy.sock` when `OPTIMUS_DEBUG=1`.
- Host-side: the socket is bind-mounted from `~/.optimus/debugpy.sock` -- the same pattern that exposes `optimus.sock` per the transport-and-discovery decision record. IDE attach configurations point at the host-side socket path.
- Default: debug off; the socket is NOT created. Opt-in via env var.
- `network_mode: "none"` is preserved unchanged. No TCP port is exposed for debug.

## Tasks

- TODO: add `debugpy` to `container/requirements.txt` (or `pyproject.toml`).
- TODO: container entrypoint conditionally starts debugpy on `OPTIMUS_DEBUG=1`, listening on `unix:///var/optimus/sockets/debugpy.sock` (NOT on a TCP port).
- TODO: docker-compose mounts `~/.optimus/debugpy.sock` into the container at the socket path (same surface that already exposes `optimus.sock`); ensure socket directory permissions match transport-and-discovery section 4.
- TODO: document IDE attach config for Cursor -- reference debugpy's socket-attach syntax; exact configuration schema depends on Cursor's debugger surface (Cursor inherits VSCode's `launch.json` shape, so a `"connect": { "host": "/path/to/debugpy.sock" }`-style entry is the starting point; verify against current debugpy + Cursor docs at task time).
- TODO: document IDE attach config for Claude Code -- attach syntax depends on Claude Code's debugger surface; reference debugpy's docs at task time.
- TODO: smoke test -- start container with `OPTIMUS_DEBUG=1`, attach from each IDE via the Unix socket, hit a breakpoint. Confirm `network_mode: "none"` is unchanged in the running container.

## Cross-reference

- `docs/decisions/secure-singleton-mcp-baseline.md` section 2 -- locked network isolation posture; this debug loop honors it.
- `docs/decisions/transport-and-discovery.md` -- Unix-domain-socket mount pattern that the debugpy socket reuses.
