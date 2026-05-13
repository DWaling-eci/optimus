"""WSL2 / Linux Unix-socket MCP-stub server for spike-2.

Validates the WSL2 + Linux transport-and-discovery contract:
- Unix domain socket at SOCKET_PATH (default: ~/.optimus/optimus.sock)
- Mode 0600 on the socket file
- SO_PEERCRED-based UID auth: reject if peer UID != server UID
- Newline-delimited JSON-RPC-ish framing (NOT a full MCP server -- enough to exercise transport + concurrency)
- Methods: ping (H1 probe), grep (H2 probe), shutdown (test-harness lifecycle)
- Concurrency cap: configured via CONFIG_PATH; requests beyond cap get structured {"error": {"code": "busy_retry", ...}}

NOT a production server. The spike's purpose is to validate the transport + concurrency + auth contract,
not to be a real optimus MCP implementation.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import sys
from contextlib import suppress
from pathlib import Path

from grep_stub import grep_under_mount, matches_to_jsonable


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_SOCKET_PATH = os.environ.get("OPTIMUS_SOCKET_PATH", str(Path.home() / ".optimus" / "optimus.sock"))
DEFAULT_MOUNT_ROOT = Path(os.environ.get("OPTIMUS_MOUNT_ROOT", "/workspace"))
DEFAULT_CONCURRENCY_CAP = int(os.environ.get("OPTIMUS_CONCURRENCY_CAP", "4"))
SHUTDOWN_TOKEN = os.environ.get("OPTIMUS_SHUTDOWN_TOKEN", "spike-test-shutdown")

# SO_PEERCRED on Linux returns a struct ucred {pid, uid, gid}
UCRED_FMT = "3i"
UCRED_SIZE = struct.calcsize(UCRED_FMT)


# ---------------------------------------------------------------------------
# In-flight tracking for concurrency cap
# ---------------------------------------------------------------------------


class InFlightCounter:
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self._count = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self) -> bool:
        async with self._lock:
            if self._count >= self.cap:
                return False
            self._count += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def count(self) -> int:
        return self._count


# ---------------------------------------------------------------------------
# JSON framing -- newline-delimited
# ---------------------------------------------------------------------------


async def read_request(reader: asyncio.StreamReader) -> dict | None:
    line = await reader.readline()
    if not line:
        return None
    try:
        return json.loads(line.decode("utf-8"))
    except json.JSONDecodeError:
        return {"id": None, "_parse_error": True}


async def write_response(writer: asyncio.StreamWriter, resp: dict) -> None:
    writer.write((json.dumps(resp) + "\n").encode("utf-8"))
    await writer.drain()


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------


async def method_ping(params: dict, mount_root: Path) -> dict:
    return {"pong": True, "received": params.get("payload"), "server_pid": os.getpid()}


async def method_grep(params: dict, mount_root: Path) -> dict:
    pattern = params.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return {"error": {"code": "bad_params", "message": "pattern (string) is required"}}
    file_glob = params.get("file_glob", "*.md")
    max_matches = int(params.get("max_matches", 100))
    walk_budget_s = float(params.get("walk_budget_s", 3.0))
    matches, diag = await grep_under_mount(
        mount_root, pattern, file_glob=file_glob, max_matches=max_matches, walk_budget_s=walk_budget_s
    )
    # Spike-only knob: hold the inflight-slot open for hold_ms before returning,
    # to make the cap probe deterministically exercise busy_retry. Production
    # MCP server has no such knob.
    hold_ms = int(params.get("hold_ms", 0))
    if hold_ms > 0:
        await asyncio.sleep(hold_ms / 1000.0)
    return {
        "matches": matches_to_jsonable(matches),
        "count": len(matches),
        "mount_root": str(mount_root),
        "diagnostics": diag,
    }


# ---------------------------------------------------------------------------
# Connection handler
# ---------------------------------------------------------------------------


async def handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    inflight: InFlightCounter,
    mount_root: Path,
    server_uid: int,
    shutdown_event: asyncio.Event,
) -> None:
    sock: socket.socket = writer.get_extra_info("socket")
    peer_uid = -1
    peer_pid = -1
    try:
        creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, UCRED_SIZE)
        peer_pid, peer_uid, _peer_gid = struct.unpack(UCRED_FMT, creds)
    except OSError as exc:
        await write_response(writer, {"id": None, "error": {"code": "peercred_failed", "message": str(exc)}})
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        return

    if peer_uid != server_uid:
        await write_response(
            writer,
            {
                "id": None,
                "error": {
                    "code": "auth_rejected",
                    "message": f"peer uid {peer_uid} != server uid {server_uid}",
                    "peer_pid": peer_pid,
                },
            },
        )
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        return

    # Authenticated. Serve requests until the client closes or shutdown fires.
    try:
        while not shutdown_event.is_set():
            req = await read_request(reader)
            if req is None:
                break
            if req.get("_parse_error"):
                await write_response(writer, {"id": None, "error": {"code": "parse_error"}})
                continue

            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            # Lifecycle method (not concurrency-capped)
            if method == "shutdown":
                if params.get("token") == SHUTDOWN_TOKEN:
                    await write_response(writer, {"id": req_id, "result": {"shutting_down": True}})
                    shutdown_event.set()
                    break
                else:
                    await write_response(writer, {"id": req_id, "error": {"code": "bad_token"}})
                    continue

            # Concurrency-capped methods
            acquired = await inflight.try_acquire()
            if not acquired:
                await write_response(
                    writer,
                    {
                        "id": req_id,
                        "error": {
                            "code": "busy_retry",
                            "message": f"concurrency cap reached ({inflight.cap}); retry shortly",
                            "in_flight": inflight.count,
                            "cap": inflight.cap,
                        },
                    },
                )
                continue

            try:
                if method == "ping":
                    result = await method_ping(params, mount_root)
                elif method == "grep":
                    result = await method_grep(params, mount_root)
                else:
                    result = {"error": {"code": "unknown_method", "message": f"unknown method: {method}"}}

                if "error" in result and len(result) == 1:
                    await write_response(writer, {"id": req_id, "error": result["error"]})
                else:
                    await write_response(writer, {"id": req_id, "result": result})
            except Exception as exc:
                await write_response(
                    writer,
                    {"id": req_id, "error": {"code": "internal", "message": f"{type(exc).__name__}: {exc}"}},
                )
            finally:
                await inflight.release()
    finally:
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


async def serve(socket_path: Path, mount_root: Path, concurrency_cap: int) -> None:
    # Remove stale socket file if present (per discovery protocol section 5).
    if socket_path.exists():
        try:
            socket_path.unlink()
        except OSError as exc:
            print(f"[server] failed to remove stale socket: {exc}", file=sys.stderr)
            sys.exit(1)

    socket_path.parent.mkdir(parents=True, exist_ok=True)
    inflight = InFlightCounter(concurrency_cap)
    shutdown_event = asyncio.Event()
    server_uid = os.getuid()

    async def _handler(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        await handle_connection(
            r,
            w,
            inflight=inflight,
            mount_root=mount_root,
            server_uid=server_uid,
            shutdown_event=shutdown_event,
        )

    server = await asyncio.start_unix_server(_handler, path=str(socket_path))
    # Apply mode 0600 per transport-and-discovery.md section 2.
    os.chmod(socket_path, 0o600)
    print(
        f"[server] listening on {socket_path} (mode 0600, uid {server_uid}, cap {concurrency_cap}, mount {mount_root})",
        flush=True,
    )

    async with server:
        await asyncio.gather(
            server.serve_forever(),
            _wait_for_shutdown(server, shutdown_event),
        )


async def _wait_for_shutdown(server: asyncio.AbstractServer, shutdown_event: asyncio.Event) -> None:
    await shutdown_event.wait()
    print("[server] shutdown requested; closing", flush=True)
    server.close()
    await server.wait_closed()


def main() -> None:
    socket_path = Path(DEFAULT_SOCKET_PATH)
    mount_root = DEFAULT_MOUNT_ROOT
    concurrency_cap = DEFAULT_CONCURRENCY_CAP
    try:
        asyncio.run(serve(socket_path, mount_root, concurrency_cap))
    except KeyboardInterrupt:
        pass
    finally:
        with suppress(FileNotFoundError):
            socket_path.unlink()


if __name__ == "__main__":
    main()
