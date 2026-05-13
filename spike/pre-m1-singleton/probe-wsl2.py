"""4-client concurrent probe for the WSL2 Unix-socket spike-2 server.

Verifies H1 (multi-client transport) + H2 (concurrent requests don't crash) +
discovery probe behavior per docs/decisions/transport-and-discovery.md section 5.

Runs in WSL2 / Linux. Targets the Unix socket the spike-2 server exposes (default
~/.optimus/optimus.sock). Designed to be invoked from the host via
`wsl --cd .../spike/pre-m1-singleton python3 probe-wsl2.py`, or directly from a
WSL2 shell.

Output: writes a structured JSON record to results/probe-wsl2-<timestamp>.json
documenting per-client connect success, per-call correctness, concurrency-cap
behavior, and timing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SOCKET_PATH = os.environ.get("OPTIMUS_SOCKET_PATH", str(Path.home() / ".optimus" / "optimus.sock"))


async def send_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, req: dict, timeout_s: float = 15.0) -> dict:
    writer.write((json.dumps(req) + "\n").encode("utf-8"))
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout=timeout_s)
    if not line:
        return {"_no_response": True}
    return json.loads(line.decode("utf-8"))


async def client_session(client_id: int, socket_path: Path, plan: list[dict]) -> dict:
    """Run a sequence of requests as one client; return per-call results."""
    result = {"client_id": client_id, "calls": [], "errors": [], "connected": False}
    try:
        reader, writer = await asyncio.open_unix_connection(path=str(socket_path))
        result["connected"] = True
    except Exception as exc:
        result["errors"].append({"step": "connect", "exception": f"{type(exc).__name__}: {exc}"})
        return result

    try:
        for i, req_template in enumerate(plan):
            req = dict(req_template)
            req["id"] = f"c{client_id}-r{i}"
            t0 = time.monotonic()
            try:
                resp = await send_request(reader, writer, req)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                result["calls"].append({"id": req["id"], "method": req.get("method"), "elapsed_ms": elapsed_ms, "response": resp})
            except Exception as exc:
                result["errors"].append({"step": f"call:{req.get('method')}", "exception": f"{type(exc).__name__}: {exc}"})
                break
    finally:
        with suppress(Exception):
            writer.close()
            await writer.wait_closed()
    return result


def make_plan_h1() -> list[dict]:
    """H1 probe plan: each client pings once. Verifies multi-client transport."""
    return [{"method": "ping", "params": {"payload": "hello"}}]


def make_plan_h2(pattern: str) -> list[dict]:
    """H2 probe plan: each client issues 3 sequential greps to keep its connection
    active while other clients also grep concurrently. The CONCURRENT axis comes
    from the 4 client tasks; each client is itself sequential. All globs are
    deliberately narrow to keep the walk fast even on slow filesystems
    (e.g. Windows-mount-via-9P in WSL2).
    """
    return [
        {"method": "grep", "params": {"pattern": pattern, "max_matches": 50, "file_glob": "*.md", "walk_budget_s": 3.0}},
        {"method": "grep", "params": {"pattern": pattern, "max_matches": 50, "file_glob": "*.json", "walk_budget_s": 3.0}},
        {"method": "grep", "params": {"pattern": pattern, "max_matches": 50, "file_glob": "*.yml", "walk_budget_s": 3.0}},
    ]


def make_plan_cap_probe() -> list[dict]:
    """Concurrency-cap probe: each client fires a SLOW grep concurrently. The
    hold_ms param keeps each request's inflight-slot open for 500ms, giving
    cap-exhaustion a deterministic window. With 4 clients and cap=2 (set via
    OPTIMUS_CONCURRENCY_CAP in the server's env), 2 acquire the slot and the
    other 2 get busy_retry while the first 2 hold.
    """
    return [{"method": "grep", "params": {"pattern": ".*", "max_matches": 5, "file_glob": "*.md", "hold_ms": 500}}]


async def run_probe(socket_path: Path, num_clients: int, hypothesis: str, pattern: str) -> dict:
    if hypothesis == "h1":
        plan = make_plan_h1()
    elif hypothesis == "h2":
        plan = make_plan_h2(pattern)
    elif hypothesis == "cap":
        plan = make_plan_cap_probe()
    else:
        raise ValueError(f"unknown hypothesis: {hypothesis}")

    t0 = time.monotonic()
    results = await asyncio.gather(
        *[client_session(i, socket_path, plan) for i in range(num_clients)],
        return_exceptions=False,
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    summary = {
        "hypothesis": hypothesis,
        "socket_path": str(socket_path),
        "num_clients": num_clients,
        "plan_length": len(plan),
        "elapsed_ms": elapsed_ms,
        "started_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "clients": results,
    }

    # Verdict heuristics
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
    out = results_dir / f"probe-wsl2-{summary['hypothesis']}-{ts}.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default=DEFAULT_SOCKET_PATH)
    parser.add_argument("--clients", type=int, default=4)
    parser.add_argument("--hypothesis", choices=["h1", "h2", "cap"], default="h1")
    parser.add_argument("--pattern", default="def ")
    parser.add_argument("--results-dir", default=str(Path(__file__).parent / "results"))
    args = parser.parse_args()

    summary = asyncio.run(
        run_probe(Path(args.socket), args.clients, args.hypothesis, args.pattern)
    )
    out_path = write_results(summary, Path(args.results_dir))
    # Print a one-line verdict + the artifact path so the host runner can parse it.
    v = summary["verdict"]
    print(
        f"[probe-wsl2] hypothesis={args.hypothesis} all_connected={v['all_connected']} "
        f"completed={v['all_calls_completed']} busy_retry={v['any_busy_retry']} "
        f"auth_rejected={v['any_auth_rejected']} elapsed_ms={summary['elapsed_ms']} -> {out_path}"
    )
    sys.exit(0 if v["all_connected"] and v["all_calls_completed"] else 1)


if __name__ == "__main__":
    main()
