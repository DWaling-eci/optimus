r"""4-client concurrent probe for the Windows-native named-pipe spike-2 server.

Verifies H1 (multi-client transport) + H2 (concurrent requests don't crash) for
the Windows-native transport per docs/decisions/transport-and-discovery.md
sections 1, 2, 4 -- mirror of probe-wsl2.py's shape so the spike-2 report can
quote both legs side-by-side.

Cross-user (SID-mismatch) rejection: per the 2026-05-12 spike-2 scoping call,
the Windows cross-user empirical test is design-verified (server-windows.py's
SID-compare path mirrors the WSL2 SO_PEERCRED path that IS empirically tested)
rather than executed here -- the realistic deployment is single-user dev host
with multiple IDE processes, not multi-user Terminal Services. See the spike-2
report's "Defense-in-depth: cross-user rejection" section for the full
reasoning trail.

Runs on Windows native (Python 3.10+, no pywin32 dependency -- pure ctypes).
Targets the named pipe the server exposes (default \\.\pipe\optimus).

Output: writes a structured JSON record to results/probe-windows-<timestamp>.json
documenting per-client connect success, per-call correctness, concurrency-cap
behavior, and timing.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from contextlib import suppress
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PIPE_NAME = os.environ.get("OPTIMUS_PIPE_NAME", r"\\.\pipe\optimus")


# ---------------------------------------------------------------------------
# Win32 surface for client side
# ---------------------------------------------------------------------------

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_PIPE_BUSY = 231
ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
NMPWAIT_USE_DEFAULT_WAIT = 0

_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_kernel32.CreateFileW.restype = wintypes.HANDLE

_kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_kernel32.WaitNamedPipeW.restype = wintypes.BOOL

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

_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
_kernel32.FlushFileBuffers.restype = wintypes.BOOL


def _winerr(prefix: str) -> str:
    code = ctypes.get_last_error()
    return f"{prefix}: GetLastError={code}"


def connect_pipe(pipe_name: str, busy_wait_ms: int = 5000) -> wintypes.HANDLE:
    """Open the named-pipe client side, retrying once on PIPE_BUSY.

    The server pre-spawns multiple acceptors, but if all are saturated WaitNamedPipeW
    blocks until an instance is free or busy_wait_ms elapses.
    """
    deadline = time.monotonic() + busy_wait_ms / 1000.0
    while True:
        h = _kernel32.CreateFileW(pipe_name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
        if h != INVALID_HANDLE_VALUE and h is not None:
            return h
        err = ctypes.get_last_error()
        if err == ERROR_PIPE_BUSY:
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                raise OSError(_winerr("CreateFileW (busy timeout)"))
            wait_ms = max(1, int(remaining * 1000))
            if not _kernel32.WaitNamedPipeW(pipe_name, wait_ms):
                raise OSError(_winerr("WaitNamedPipeW"))
            continue
        raise OSError(_winerr("CreateFileW"))


def read_line(handle: wintypes.HANDLE, buffer_state: dict, timeout_s: float = 15.0) -> str | None:
    buf = buffer_state.setdefault("buf", bytearray())
    deadline = time.monotonic() + timeout_s
    while True:
        nl = buf.find(b"\n")
        if nl != -1:
            line = bytes(buf[:nl]).decode("utf-8", errors="replace")
            del buf[: nl + 1]
            return line
        if time.monotonic() > deadline:
            raise TimeoutError(f"read_line timed out after {timeout_s}s")
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
        raise OSError(_winerr("WriteFile"))
    _kernel32.FlushFileBuffers(handle)


# ---------------------------------------------------------------------------
# Per-client session (one thread per client; same plan shape as probe-wsl2.py)
# ---------------------------------------------------------------------------


def send_request(handle: wintypes.HANDLE, buffer_state: dict, req: dict, timeout_s: float = 15.0) -> dict:
    write_line(handle, json.dumps(req))
    line = read_line(handle, buffer_state, timeout_s=timeout_s)
    if line is None:
        return {"_no_response": True}
    return json.loads(line)


def client_session(client_id: int, pipe_name: str, plan: list[dict]) -> dict:
    result = {"client_id": client_id, "calls": [], "errors": [], "connected": False}
    try:
        handle = connect_pipe(pipe_name)
        result["connected"] = True
    except Exception as exc:
        result["errors"].append({"step": "connect", "exception": f"{type(exc).__name__}: {exc}"})
        return result

    buffer_state: dict = {}
    try:
        for i, req_template in enumerate(plan):
            req = dict(req_template)
            req["id"] = f"c{client_id}-r{i}"
            t0 = time.monotonic()
            try:
                resp = send_request(handle, buffer_state, req)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                result["calls"].append({"id": req["id"], "method": req.get("method"), "elapsed_ms": elapsed_ms, "response": resp})
            except Exception as exc:
                result["errors"].append({"step": f"call:{req.get('method')}", "exception": f"{type(exc).__name__}: {exc}"})
                break
    finally:
        with suppress(Exception):
            _kernel32.CloseHandle(handle)
    return result


# ---------------------------------------------------------------------------
# Plans (mirror probe-wsl2.py)
# ---------------------------------------------------------------------------


def make_plan_h1() -> list[dict]:
    return [{"method": "ping", "params": {"payload": "hello"}}]


def make_plan_h2(pattern: str) -> list[dict]:
    return [
        {"method": "grep", "params": {"pattern": pattern, "max_matches": 50, "file_glob": "*.md", "walk_budget_s": 3.0}},
        {"method": "grep", "params": {"pattern": pattern, "max_matches": 50, "file_glob": "*.json", "walk_budget_s": 3.0}},
        {"method": "grep", "params": {"pattern": pattern, "max_matches": 50, "file_glob": "*.yml", "walk_budget_s": 3.0}},
    ]


def make_plan_cap_probe() -> list[dict]:
    return [{"method": "grep", "params": {"pattern": ".*", "max_matches": 5, "file_glob": "*.md", "hold_ms": 500}}]


# ---------------------------------------------------------------------------
# Threaded run
# ---------------------------------------------------------------------------


def run_probe(pipe_name: str, num_clients: int, hypothesis: str, pattern: str) -> dict:
    if hypothesis == "h1":
        plan = make_plan_h1()
    elif hypothesis == "h2":
        plan = make_plan_h2(pattern)
    elif hypothesis == "cap":
        plan = make_plan_cap_probe()
    else:
        raise ValueError(f"unknown hypothesis: {hypothesis}")

    results: list[dict] = [None] * num_clients  # type: ignore[list-item]
    threads: list[threading.Thread] = []

    def _run(idx: int) -> None:
        results[idx] = client_session(idx, pipe_name, plan)

    t0 = time.monotonic()
    for i in range(num_clients):
        t = threading.Thread(target=_run, args=(i,), daemon=True, name=f"probe-client-{i}")
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    summary = {
        "hypothesis": hypothesis,
        "transport": "windows-named-pipe",
        "pipe_name": pipe_name,
        "num_clients": num_clients,
        "plan_length": len(plan),
        "elapsed_ms": elapsed_ms,
        "started_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "clients": results,
    }

    all_connected = all(r["connected"] for r in results)
    total_calls = sum(len(r["calls"]) for r in results)
    expected_calls = num_clients * len(plan)
    any_busy_retry = any(
        any(c.get("response", {}).get("error", {}).get("code") == "busy_retry" for c in r["calls"])
        for r in results
    )
    any_auth_rejected = any(
        any(c.get("response", {}).get("error", {}).get("code") == "auth_rejected" for c in r["calls"])
        for r in results
    )
    summary["verdict"] = {
        "all_connected": all_connected,
        "total_calls": total_calls,
        "expected_calls": expected_calls,
        "all_calls_completed": total_calls == expected_calls,
        "any_busy_retry": any_busy_retry,
        "any_auth_rejected": any_auth_rejected,
    }
    return summary


def write_results(summary: dict, results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = results_dir / f"probe-windows-{summary['hypothesis']}-{ts}.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipe", default=DEFAULT_PIPE_NAME)
    parser.add_argument("--clients", type=int, default=4)
    parser.add_argument("--hypothesis", choices=["h1", "h2", "cap"], default="h1")
    parser.add_argument("--pattern", default="def ")
    parser.add_argument("--results-dir", default=str(Path(__file__).parent / "results"))
    args = parser.parse_args()

    summary = run_probe(args.pipe, args.clients, args.hypothesis, args.pattern)
    out_path = write_results(summary, Path(args.results_dir))
    v = summary["verdict"]
    print(
        f"[probe-windows] hypothesis={args.hypothesis} all_connected={v['all_connected']} "
        f"completed={v['all_calls_completed']} busy_retry={v['any_busy_retry']} "
        f"auth_rejected={v['any_auth_rejected']} elapsed_ms={summary['elapsed_ms']} -> {out_path}"
    )
    sys.exit(0 if v["all_connected"] and v["all_calls_completed"] else 1)


if __name__ == "__main__":
    main()
