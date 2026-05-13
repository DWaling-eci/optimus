"""Discovery + stale-endpoint probe per docs/decisions/transport-and-discovery.md section 5.

Validates:
1. Endpoint-exists check (`stat` on socket / named-pipe presence).
2. Open + send MCP-ish ping with 500ms initial timeout.
3. On timeout: retry once with 200ms timeout.
4. On stale (no response after retry): remove the stale endpoint file before respawning.

Transport-agnostic via --transport={wsl2|windows} flag.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import time
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


async def main_async(transport: str, socket_path: Path, results_dir: Path) -> int:
    if transport != "wsl2":
        print(f"[probe-discovery] transport={transport} not yet implemented in this script; see probe-windows.py for Windows-native", file=sys.stderr)
        return 2

    outcome = await probe_unix_socket(socket_path)

    # If the endpoint exists but is stale, demonstrate the cleanup step.
    cleanup_outcome = None
    if outcome["verdict"] in ("stale", "stale-not-socket"):
        cleanup_outcome = cleanup_stale_endpoint(socket_path)

    summary = {
        "transport": transport,
        "socket_path": str(socket_path),
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
        "--socket",
        default=os.environ.get("OPTIMUS_SOCKET_PATH", str(Path.home() / ".optimus" / "optimus.sock")),
    )
    parser.add_argument("--results-dir", default=str(Path(__file__).parent / "results"))
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args.transport, Path(args.socket), Path(args.results_dir))))


if __name__ == "__main__":
    main()
