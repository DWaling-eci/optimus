r"""Discovery + stale-endpoint probe per docs/decisions/transport-and-discovery.md section 5.

Validates:
1. Endpoint-exists check (`stat` on socket / named-pipe presence).
2. Open + send MCP-ish ping with 500ms initial timeout.
3. On timeout: retry once with 200ms timeout.
4. On stale (no response after retry): remove the stale endpoint file before respawning.

Transport-agnostic via --transport={wsl2|windows} flag. Windows-named-pipe
discovery has a slightly different stale-endpoint shape than Unix sockets:
the pipe kernel object disappears when the last handle closes, so a "stale"
named-pipe file does not normally persist past server exit. The "stale" case
on Windows is therefore: pipe exists but no process is reading/writing
(ping times out).
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import socket
import sys
import threading
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path


PING_TIMEOUT_INITIAL_S = 0.5
PING_TIMEOUT_RETRY_S = 0.2


async def probe_unix_socket(socket_path: Path) -> dict:
    """Phase 1 of discovery: existence + liveness probe.

    Returns a structured outcome dict the orchestrator can use to decide whether
    to use the existing endpoint vs spawn a fresh one.
    """
    outcome: dict[str, object] = {
        "transport": "wsl2-unix-socket",
        "socket_path": str(socket_path),
        "exists": False,
        "is_socket_file": False,
        "ping_attempts": [],
        "verdict": None,
    }

    if not socket_path.exists():
        outcome["verdict"] = "no-endpoint"
        return outcome
    outcome["exists"] = True

    # Verify it's actually a socket (not a regular file left over from a bad shutdown).
    try:
        st = os.stat(socket_path)
        import stat
        outcome["is_socket_file"] = stat.S_ISSOCK(st.st_mode)
    except OSError as exc:
        outcome["verdict"] = "stat-failed"
        outcome["error"] = str(exc)
        return outcome

    if not outcome["is_socket_file"]:
        outcome["verdict"] = "stale-not-socket"
        return outcome

    # Attempt the ping twice per the protocol.
    for attempt_idx, timeout_s in enumerate([PING_TIMEOUT_INITIAL_S, PING_TIMEOUT_RETRY_S]):
        attempt: dict[str, object] = {"attempt": attempt_idx, "timeout_s": timeout_s}
        t0 = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(path=str(socket_path)),
                timeout=timeout_s,
            )
            req = {"id": f"discovery-{attempt_idx}", "method": "ping", "params": {"payload": "discovery"}}
            writer.write((json.dumps(req) + "\n").encode("utf-8"))
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=timeout_s)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            attempt["elapsed_ms"] = elapsed_ms
            if not line:
                attempt["result"] = "no-response"
            else:
                resp = json.loads(line.decode("utf-8"))
                attempt["result"] = "pong" if resp.get("result", {}).get("pong") else "unexpected-response"
                attempt["raw_response"] = resp
            writer.close()
            await writer.wait_closed()
            outcome["ping_attempts"].append(attempt)
            if attempt["result"] == "pong":
                outcome["verdict"] = "alive"
                return outcome
        except asyncio.TimeoutError:
            attempt["result"] = "timeout"
            attempt["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            outcome["ping_attempts"].append(attempt)
        except (ConnectionRefusedError, FileNotFoundError) as exc:
            attempt["result"] = "connection-refused"
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            attempt["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            outcome["ping_attempts"].append(attempt)
            # ConnectionRefused on a socket file usually means stale (server not running)
            break
        except Exception as exc:
            attempt["result"] = "exception"
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            attempt["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            outcome["ping_attempts"].append(attempt)

    # Both attempts (or refusal) failed -> stale endpoint
    outcome["verdict"] = "stale"
    return outcome


# ---------------------------------------------------------------------------
# Windows named-pipe discovery
# ---------------------------------------------------------------------------


def _probe_named_pipe_sync(pipe_name: str) -> dict:
    """Phase 1 of discovery for Windows named-pipe transport.

    Mirrors probe_unix_socket's outcome shape so the report can compare
    side-by-side.
    """
    if sys.platform != "win32":
        return {
            "transport": "windows-named-pipe",
            "pipe_name": pipe_name,
            "exists": False,
            "ping_attempts": [],
            "verdict": "wrong-platform",
            "error": f"Windows discovery requires sys.platform == 'win32'; running on {sys.platform}",
        }

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    ERROR_FILE_NOT_FOUND = 2
    ERROR_PIPE_BUSY = 231
    ERROR_SEM_TIMEOUT = 121
    ERROR_BROKEN_PIPE = 109

    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    outcome: dict[str, object] = {
        "transport": "windows-named-pipe",
        "pipe_name": pipe_name,
        "exists": False,
        "ping_attempts": [],
        "verdict": None,
    }

    # Existence check via WaitNamedPipeW(timeout=0): returns immediately. If the
    # pipe exists but no instance is currently waiting, we get ERROR_SEM_TIMEOUT
    # (still "exists"). FILE_NOT_FOUND means truly absent.
    if kernel32.WaitNamedPipeW(pipe_name, 0):
        outcome["exists"] = True
    else:
        err = ctypes.get_last_error()
        if err == ERROR_FILE_NOT_FOUND:
            outcome["verdict"] = "no-endpoint"
            return outcome
        if err == ERROR_SEM_TIMEOUT:
            outcome["exists"] = True  # exists but no available instance
        else:
            outcome["verdict"] = "wait-failed"
            outcome["error"] = f"GetLastError={err}"
            return outcome

    # Try ping twice per the protocol. Each attempt: connect + write + read,
    # all within timeout_s. We use a worker thread so a hung ReadFile can be
    # left to die without blocking the discovery probe past the budget.
    for attempt_idx, timeout_s in enumerate([PING_TIMEOUT_INITIAL_S, PING_TIMEOUT_RETRY_S]):
        attempt: dict[str, object] = {"attempt": attempt_idx, "timeout_s": timeout_s}
        attempt_result: dict = {}

        def _do_ping(out: dict) -> None:
            t0 = time.monotonic()
            handle = kernel32.CreateFileW(pipe_name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
            if handle == INVALID_HANDLE_VALUE or handle is None:
                err = ctypes.get_last_error()
                out["result"] = "connect-failed"
                out["error"] = f"GetLastError={err}"
                out["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
                return
            try:
                req = json.dumps({"id": f"discovery-{attempt_idx}", "method": "ping", "params": {"payload": "discovery"}}) + "\n"
                data = req.encode("utf-8")
                nwritten = wintypes.DWORD(0)
                if not kernel32.WriteFile(handle, data, len(data), ctypes.byref(nwritten), None):
                    err = ctypes.get_last_error()
                    out["result"] = "write-failed"
                    out["error"] = f"GetLastError={err}"
                    out["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
                    return
                buf = (ctypes.c_byte * 4096)()
                nread = wintypes.DWORD(0)
                line_buf = bytearray()
                while b"\n" not in line_buf:
                    if not kernel32.ReadFile(handle, buf, 4096, ctypes.byref(nread), None):
                        err = ctypes.get_last_error()
                        out["result"] = "read-failed"
                        out["error"] = f"GetLastError={err}"
                        out["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
                        return
                    if nread.value == 0:
                        break
                    line_buf.extend(bytes(buf[: nread.value]))
                resp = json.loads(line_buf.split(b"\n")[0].decode("utf-8"))
                out["raw_response"] = resp
                out["result"] = "pong" if resp.get("result", {}).get("pong") else "unexpected-response"
                out["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            finally:
                with suppress(Exception):
                    kernel32.CloseHandle(handle)

        worker = threading.Thread(target=_do_ping, args=(attempt_result,), daemon=True)
        worker.start()
        worker.join(timeout=timeout_s)
        if worker.is_alive():
            attempt["result"] = "timeout"
            attempt["elapsed_ms"] = int(timeout_s * 1000)
        else:
            attempt.update(attempt_result)
        outcome["ping_attempts"].append(attempt)
        if attempt.get("result") == "pong":
            outcome["verdict"] = "alive"
            return outcome

    outcome["verdict"] = "stale"
    return outcome


async def probe_named_pipe(pipe_name: str) -> dict:
    return await asyncio.to_thread(_probe_named_pipe_sync, pipe_name)


def cleanup_stale_named_pipe(pipe_name: str) -> dict:
    """Windows named-pipe stale cleanup is a no-op: the kernel object disappears
    when the last handle closes. Production optimus's installer/optimus_doctor
    on Windows kills the zombie server PID rather than removing a file.
    """
    return {
        "cleaned": False,
        "reason": "windows-named-pipe-stale-cleanup-is-pid-kill-not-file-unlink",
    }


def cleanup_stale_endpoint(socket_path: Path) -> dict:
    """Remove the stale endpoint per transport-and-discovery.md section 5.

    Production optimus's installer / optimus_doctor owns this step; the probe
    just demonstrates the contract.
    """
    if not socket_path.exists():
        return {"cleaned": False, "reason": "endpoint-not-present"}
    try:
        socket_path.unlink()
        return {"cleaned": True}
    except OSError as exc:
        return {"cleaned": False, "error": f"{type(exc).__name__}: {exc}"}


async def main_async(transport: str, endpoint: str, results_dir: Path) -> int:
    if transport == "wsl2":
        outcome = await probe_unix_socket(Path(endpoint))
        cleanup_outcome = None
        if outcome["verdict"] in ("stale", "stale-not-socket"):
            cleanup_outcome = cleanup_stale_endpoint(Path(endpoint))
        endpoint_key = "socket_path"
    elif transport == "windows":
        outcome = await probe_named_pipe(endpoint)
        cleanup_outcome = None
        if outcome["verdict"] == "stale":
            cleanup_outcome = cleanup_stale_named_pipe(endpoint)
        endpoint_key = "pipe_name"
    else:
        print(f"[probe-discovery] unknown transport={transport}", file=sys.stderr)
        return 2

    summary = {
        "transport": transport,
        endpoint_key: endpoint,
        "started_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "discovery_outcome": outcome,
        "cleanup_outcome": cleanup_outcome,
    }

    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = results_dir / f"probe-discovery-{transport}-{ts}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        f"[probe-discovery] transport={transport} verdict={outcome['verdict']} "
        f"attempts={len(outcome.get('ping_attempts', []))} "
        f"cleanup={cleanup_outcome} -> {out_path}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["wsl2", "windows"], default="wsl2")
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Socket path (wsl2) or named-pipe name (windows). Defaults from env / convention.",
    )
    # Backwards-compat alias for the WSL2 leg's existing flag name.
    parser.add_argument("--socket", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--results-dir", default=str(Path(__file__).parent / "results"))
    args = parser.parse_args()

    endpoint = args.endpoint or args.socket
    if endpoint is None:
        if args.transport == "wsl2":
            endpoint = os.environ.get("OPTIMUS_SOCKET_PATH", str(Path.home() / ".optimus" / "optimus.sock"))
        else:  # windows
            endpoint = os.environ.get("OPTIMUS_PIPE_NAME", r"\\.\pipe\optimus")

    sys.exit(asyncio.run(main_async(args.transport, endpoint, Path(args.results_dir))))


if __name__ == "__main__":
    main()
