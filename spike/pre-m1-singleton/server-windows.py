r"""Windows-native named-pipe MCP-stub server for spike-2.

Validates the Windows-native transport-and-discovery contract:
- Named pipe at PIPE_NAME (default: \\.\pipe\optimus)
- Default ACL: pipe is created with NULL security attributes, which Windows
  resolves to the creator-process default ACL -- full control to the creator's
  SID + LocalSystem, no access to other users. Per
  docs/decisions/transport-and-discovery.md section 2.
- SID-based auth per section 4: GetNamedPipeClientProcessId ->
  OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) -> OpenProcessToken(TOKEN_QUERY) ->
  GetTokenInformation(TokenUser) -> EqualSid against the server's own user SID.
  Mismatch -> auth_rejected error written, pipe closed.
- Newline-delimited JSON-RPC-ish framing (matches server-wsl2.py).
- Methods: ping (H1 probe), grep (H2 probe), shutdown (test-harness lifecycle).
- Concurrency cap (CONCURRENCY_CAP env): requests beyond cap get structured
  {"error": {"code": "busy_retry", ...}} -- same shape as the WSL2 leg.

Pure ctypes; no pywin32 dependency. Multiple pre-spawned acceptor threads, each
owning one pipe instance for the life of one client connection then recreating.

NOT a production server. The spike's purpose is to validate the transport +
concurrency + auth contract from transport-and-discovery.md sections 1-5,
NOT to be a real optimus MCP implementation.

Run from PowerShell:
    python server-windows.py
Stop with Ctrl+C, or send a {"method": "shutdown", "params": {"token": "..."}}.
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import os
import sys
import threading
import time
from contextlib import suppress
from ctypes import wintypes
from pathlib import Path

from grep_stub import grep_under_mount, matches_to_jsonable


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PIPE_NAME = os.environ.get("OPTIMUS_PIPE_NAME", r"\\.\pipe\optimus")
DEFAULT_MOUNT_ROOT = Path(os.environ.get("OPTIMUS_MOUNT_ROOT", str(Path.home() / ".spike-test-corpus")))
DEFAULT_CONCURRENCY_CAP = int(os.environ.get("OPTIMUS_CONCURRENCY_CAP", "4"))
SHUTDOWN_TOKEN = os.environ.get("OPTIMUS_SHUTDOWN_TOKEN", "spike-test-shutdown")
ACCEPTOR_COUNT = int(os.environ.get("OPTIMUS_ACCEPTOR_COUNT", "8"))


# ---------------------------------------------------------------------------
# Win32 API surface (ctypes)
# ---------------------------------------------------------------------------

# Loaded once at import; the spike runs only on Windows native.
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

# Constants from Winbase.h / WinNT.h
PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_PIPE_CONNECTED = 535
ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
ERROR_PIPE_LISTENING = 536
ERROR_INSUFFICIENT_BUFFER = 122
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TokenUser = 1  # TOKEN_INFORMATION_CLASS

_kernel32.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
]
_kernel32.CreateNamedPipeW.restype = wintypes.HANDLE

_kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
_kernel32.ConnectNamedPipe.restype = wintypes.BOOL

_kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
_kernel32.DisconnectNamedPipe.restype = wintypes.BOOL

_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_kernel32.ReadFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_kernel32.ReadFile.restype = wintypes.BOOL

_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_kernel32.WriteFile.restype = wintypes.BOOL

_kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
_kernel32.FlushFileBuffers.restype = wintypes.BOOL

_kernel32.GetNamedPipeClientProcessId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_kernel32.GetNamedPipeClientProcessId.restype = wintypes.BOOL

_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE

_kernel32.GetCurrentProcess.argtypes = []
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE

_advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_advapi32.OpenProcessToken.restype = wintypes.BOOL

_advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]
_advapi32.GetTokenInformation.restype = wintypes.BOOL

_advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_advapi32.EqualSid.restype = wintypes.BOOL

_advapi32.GetLengthSid.argtypes = [ctypes.c_void_p]
_advapi32.GetLengthSid.restype = wintypes.DWORD

_advapi32.CopySid.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
_advapi32.CopySid.restype = wintypes.BOOL

_advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
_advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

_kernel32.LocalFree.argtypes = [wintypes.HANDLE]
_kernel32.LocalFree.restype = wintypes.HANDLE


def _winerr(prefix: str) -> str:
    code = ctypes.get_last_error()
    return f"{prefix}: GetLastError={code}"


# ---------------------------------------------------------------------------
# SID helpers
# ---------------------------------------------------------------------------


def _get_token_user_sid_copy(token_handle: wintypes.HANDLE) -> bytes:
    """Read TokenUser from a token, return a heap-detached copy of the SID bytes."""
    needed = wintypes.DWORD(0)
    _advapi32.GetTokenInformation(token_handle, TokenUser, None, 0, ctypes.byref(needed))
    if needed.value == 0:
        raise OSError(_winerr("GetTokenInformation(size)"))
    buf = (ctypes.c_byte * needed.value)()
    if not _advapi32.GetTokenInformation(token_handle, TokenUser, buf, needed.value, ctypes.byref(needed)):
        raise OSError(_winerr("GetTokenInformation"))
    # TOKEN_USER {SID_AND_ATTRIBUTES User{PSID Sid; DWORD Attributes;}}
    # On both x64 and x86, the first field is a pointer to the SID immediately
    # following the TOKEN_USER struct in the same buffer.
    sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
    sid_len = _advapi32.GetLengthSid(sid_ptr)
    if sid_len == 0:
        raise OSError(_winerr("GetLengthSid"))
    out = (ctypes.c_byte * sid_len)()
    if not _advapi32.CopySid(sid_len, out, sid_ptr):
        raise OSError(_winerr("CopySid"))
    return bytes(out)


def get_self_user_sid() -> bytes:
    """Return the current process's user SID as a heap-owned bytes blob."""
    proc = _kernel32.GetCurrentProcess()
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(proc, TOKEN_QUERY, ctypes.byref(token)):
        raise OSError(_winerr("OpenProcessToken(self)"))
    try:
        return _get_token_user_sid_copy(token)
    finally:
        _kernel32.CloseHandle(token)


def get_pipe_client_user_sid(pipe_handle: wintypes.HANDLE) -> tuple[bytes, int]:
    """Return (SID bytes, client_pid) for the connected client."""
    client_pid = wintypes.DWORD(0)
    if not _kernel32.GetNamedPipeClientProcessId(pipe_handle, ctypes.byref(client_pid)):
        raise OSError(_winerr("GetNamedPipeClientProcessId"))
    proc = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, client_pid.value)
    if not proc:
        raise OSError(_winerr("OpenProcess(client)"))
    try:
        token = wintypes.HANDLE()
        if not _advapi32.OpenProcessToken(proc, TOKEN_QUERY, ctypes.byref(token)):
            raise OSError(_winerr("OpenProcessToken(client)"))
        try:
            return _get_token_user_sid_copy(token), client_pid.value
        finally:
            _kernel32.CloseHandle(token)
    finally:
        _kernel32.CloseHandle(proc)


def sid_to_string(sid_bytes: bytes) -> str:
    sid_buf = (ctypes.c_byte * len(sid_bytes)).from_buffer_copy(sid_bytes)
    out = wintypes.LPWSTR()
    if not _advapi32.ConvertSidToStringSidW(sid_buf, ctypes.byref(out)):
        return "<convert-failed>"
    try:
        return ctypes.wstring_at(out)
    finally:
        _kernel32.LocalFree(ctypes.cast(out, wintypes.HANDLE))


def sids_equal(a: bytes, b: bytes) -> bool:
    if not a or not b:
        return False
    a_buf = (ctypes.c_byte * len(a)).from_buffer_copy(a)
    b_buf = (ctypes.c_byte * len(b)).from_buffer_copy(b)
    return bool(_advapi32.EqualSid(a_buf, b_buf))


# ---------------------------------------------------------------------------
# Pipe instance create / connect / read / write
# ---------------------------------------------------------------------------


def create_pipe_instance(first: bool) -> wintypes.HANDLE:
    open_mode = PIPE_ACCESS_DUPLEX
    if first:
        open_mode |= FILE_FLAG_FIRST_PIPE_INSTANCE  # ensures no foreign pipe with this name pre-exists
    pipe_mode = PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS
    handle = _kernel32.CreateNamedPipeW(
        PIPE_NAME,
        open_mode,
        pipe_mode,
        PIPE_UNLIMITED_INSTANCES,
        65536,  # out buffer
        65536,  # in buffer
        0,      # default timeout (50ms; only matters for WaitNamedPipe consumers)
        None,   # NULL security attributes -> default ACL = creator's SID + LocalSystem
    )
    if handle == INVALID_HANDLE_VALUE or handle is None:
        raise OSError(_winerr("CreateNamedPipeW"))
    return handle


def accept_one(handle: wintypes.HANDLE) -> None:
    """Block until a client connects to this pipe instance."""
    ok = _kernel32.ConnectNamedPipe(handle, None)
    if not ok:
        err = ctypes.get_last_error()
        if err != ERROR_PIPE_CONNECTED:
            raise OSError(_winerr("ConnectNamedPipe"))


def read_line(handle: wintypes.HANDLE, buffer_state: dict) -> str | None:
    """Block on ReadFile; return the next newline-terminated line as str, or None at EOF.

    buffer_state is a dict {'buf': bytearray} owned by this connection so we can
    accumulate partial reads across multiple ReadFile calls.
    """
    buf = buffer_state.setdefault("buf", bytearray())
    while True:
        nl = buf.find(b"\n")
        if nl != -1:
            line = bytes(buf[:nl]).decode("utf-8", errors="replace")
            del buf[: nl + 1]
            return line
        chunk = (ctypes.c_byte * 4096)()
        nread = wintypes.DWORD(0)
        ok = _kernel32.ReadFile(handle, chunk, 4096, ctypes.byref(nread), None)
        if not ok:
            err = ctypes.get_last_error()
            if err in (ERROR_BROKEN_PIPE, ERROR_NO_DATA):
                if buf:
                    line = bytes(buf).decode("utf-8", errors="replace")
                    buf.clear()
                    return line
                return None
            raise OSError(_winerr("ReadFile"))
        if nread.value == 0:
            return None
        buf.extend(bytes(chunk[: nread.value]))


def write_line(handle: wintypes.HANDLE, payload: str) -> None:
    data = (payload + "\n").encode("utf-8")
    nwritten = wintypes.DWORD(0)
    ok = _kernel32.WriteFile(handle, data, len(data), ctypes.byref(nwritten), None)
    if not ok:
        err = ctypes.get_last_error()
        if err in (ERROR_BROKEN_PIPE, ERROR_NO_DATA):
            return  # client gone; swallow
        raise OSError(_winerr("WriteFile"))
    _kernel32.FlushFileBuffers(handle)


# ---------------------------------------------------------------------------
# Concurrency cap (thread-safe sibling of the asyncio version in server-wsl2.py)
# ---------------------------------------------------------------------------


class InFlightCounter:
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self._count = 0
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            if self._count >= self.cap:
                return False
            self._count += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def count(self) -> int:
        return self._count


# ---------------------------------------------------------------------------
# Methods (ping, grep)
# ---------------------------------------------------------------------------


def method_ping(params: dict) -> dict:
    return {"pong": True, "received": params.get("payload"), "server_pid": os.getpid()}


def method_grep(params: dict, mount_root: Path) -> dict:
    pattern = params.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return {"error": {"code": "bad_params", "message": "pattern (string) is required"}}
    file_glob = params.get("file_glob", "*.md")
    max_matches = int(params.get("max_matches", 100))
    walk_budget_s = float(params.get("walk_budget_s", 3.0))
    hold_ms = int(params.get("hold_ms", 0))
    matches, diag = asyncio.run(
        grep_under_mount(mount_root, pattern, file_glob=file_glob, max_matches=max_matches, walk_budget_s=walk_budget_s)
    )
    if hold_ms > 0:
        time.sleep(hold_ms / 1000.0)
    return {
        "matches": matches_to_jsonable(matches),
        "count": len(matches),
        "mount_root": str(mount_root),
        "diagnostics": diag,
    }


# ---------------------------------------------------------------------------
# Connection handler (thread-per-pipe-instance)
# ---------------------------------------------------------------------------


def handle_connection(
    handle: wintypes.HANDLE,
    *,
    server_sid: bytes,
    inflight: InFlightCounter,
    mount_root: Path,
    shutdown_event: threading.Event,
) -> None:
    """Single connection lifecycle: SID-check, then serve frames until close/shutdown."""
    peer_pid = -1
    try:
        try:
            peer_sid, peer_pid = get_pipe_client_user_sid(handle)
        except OSError as exc:
            with suppress(Exception):
                write_line(handle, json.dumps({"id": None, "error": {"code": "peercred_failed", "message": str(exc)}}))
            return

        if not sids_equal(peer_sid, server_sid):
            with suppress(Exception):
                write_line(
                    handle,
                    json.dumps(
                        {
                            "id": None,
                            "error": {
                                "code": "auth_rejected",
                                "message": f"peer sid {sid_to_string(peer_sid)} != server sid {sid_to_string(server_sid)}",
                                "peer_pid": peer_pid,
                            },
                        }
                    ),
                )
            return

        buffer_state: dict = {}
        while not shutdown_event.is_set():
            try:
                line = read_line(handle, buffer_state)
            except OSError as exc:
                with suppress(Exception):
                    write_line(handle, json.dumps({"id": None, "error": {"code": "io_error", "message": str(exc)}}))
                return
            if line is None:
                return
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                with suppress(Exception):
                    write_line(handle, json.dumps({"id": None, "error": {"code": "parse_error"}}))
                continue

            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "shutdown":
                if params.get("token") == SHUTDOWN_TOKEN:
                    write_line(handle, json.dumps({"id": req_id, "result": {"shutting_down": True}}))
                    shutdown_event.set()
                    return
                else:
                    write_line(handle, json.dumps({"id": req_id, "error": {"code": "bad_token"}}))
                    continue

            acquired = inflight.try_acquire()
            if not acquired:
                write_line(
                    handle,
                    json.dumps(
                        {
                            "id": req_id,
                            "error": {
                                "code": "busy_retry",
                                "message": f"concurrency cap reached ({inflight.cap}); retry shortly",
                                "in_flight": inflight.count,
                                "cap": inflight.cap,
                            },
                        }
                    ),
                )
                continue

            try:
                if method == "ping":
                    result = method_ping(params)
                elif method == "grep":
                    result = method_grep(params, mount_root)
                else:
                    result = {"error": {"code": "unknown_method", "message": f"unknown method: {method}"}}

                if "error" in result and len(result) == 1:
                    write_line(handle, json.dumps({"id": req_id, "error": result["error"]}))
                else:
                    write_line(handle, json.dumps({"id": req_id, "result": result}))
            except Exception as exc:
                with suppress(Exception):
                    write_line(
                        handle,
                        json.dumps(
                            {"id": req_id, "error": {"code": "internal", "message": f"{type(exc).__name__}: {exc}"}}
                        ),
                    )
            finally:
                inflight.release()
    finally:
        with suppress(Exception):
            _kernel32.DisconnectNamedPipe(handle)
        with suppress(Exception):
            _kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# Acceptor thread (one pipe instance per acceptor; recreate after each client)
# ---------------------------------------------------------------------------


def acceptor_loop(
    acceptor_id: int,
    *,
    server_sid: bytes,
    inflight: InFlightCounter,
    mount_root: Path,
    shutdown_event: threading.Event,
    first_lock: threading.Lock,
    first_done: dict,
) -> None:
    while not shutdown_event.is_set():
        try:
            with first_lock:
                first = not first_done.get("done", False)
                if first:
                    first_done["done"] = True
            handle = create_pipe_instance(first=first)
        except OSError as exc:
            print(f"[acceptor-{acceptor_id}] CreateNamedPipeW failed: {exc}", file=sys.stderr)
            time.sleep(0.5)
            continue

        try:
            accept_one(handle)
        except OSError as exc:
            print(f"[acceptor-{acceptor_id}] ConnectNamedPipe failed: {exc}", file=sys.stderr)
            with suppress(Exception):
                _kernel32.CloseHandle(handle)
            continue

        if shutdown_event.is_set():
            with suppress(Exception):
                _kernel32.CloseHandle(handle)
            break

        handle_connection(
            handle,
            server_sid=server_sid,
            inflight=inflight,
            mount_root=mount_root,
            shutdown_event=shutdown_event,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def serve(mount_root: Path, concurrency_cap: int, acceptor_count: int) -> None:
    if sys.platform != "win32":
        raise RuntimeError("server-windows.py requires Windows; use server-wsl2.py for Linux/WSL2")

    server_sid = get_self_user_sid()
    inflight = InFlightCounter(concurrency_cap)
    shutdown_event = threading.Event()
    first_lock = threading.Lock()
    first_done: dict = {"done": False}

    print(
        f"[server] listening on {PIPE_NAME} "
        f"(sid {sid_to_string(server_sid)}, cap {concurrency_cap}, mount {mount_root}, acceptors {acceptor_count})",
        flush=True,
    )

    threads: list[threading.Thread] = []
    for i in range(acceptor_count):
        t = threading.Thread(
            target=acceptor_loop,
            args=(i,),
            kwargs={
                "server_sid": server_sid,
                "inflight": inflight,
                "mount_root": mount_root,
                "shutdown_event": shutdown_event,
                "first_lock": first_lock,
                "first_done": first_done,
            },
            daemon=True,
            name=f"pipe-acceptor-{i}",
        )
        t.start()
        threads.append(t)

    try:
        while not shutdown_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_event.set()
        print("[server] shutdown requested; closing", flush=True)
        # Acceptor threads are daemons; they exit when shutdown_event is set
        # AFTER they finish their current accept/handle. For a clean shutdown
        # we'd need to "kick" each blocked ConnectNamedPipe with a self-connect.
        # The spike treats the test-harness shutdown method as the canonical
        # path; Ctrl+C is best-effort.


def main() -> None:
    serve(DEFAULT_MOUNT_ROOT, DEFAULT_CONCURRENCY_CAP, ACCEPTOR_COUNT)


if __name__ == "__main__":
    main()
