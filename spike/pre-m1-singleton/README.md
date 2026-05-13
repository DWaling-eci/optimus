# Spike-2 -- Singleton Container Feasibility

**Status:** in-progress.
**Spike framing source:** `docs/decomp/pre-M1-spikes.md` section "Spike-2: Singleton Container Feasibility".
**Decision record under test:** `docs/decisions/transport-and-discovery.md` (pre-M0 provisional version per the hybrid pinning rule).

## Thesis (per `pre-M1-spikes.md`)

A single host-singleton container with a user-configured parent-mount can serve multiple concurrent MCP clients (multiple IDEs, parallel sub-agents) without crashing, dropping requests, or imposing unreasonable UX cost.

## Hypotheses

- **H1 (multi-client MCP transport works):** clients can connect to the same container concurrently and both get correct responses. No serialization through a single stdio pipe.
- **H2 (concurrent requests don't crash or drop):** parallel `optimus_grep` calls return correct results; concurrent calls do not crash each other or drop silently.
- **H3 (parent-mount UX is acceptable for the spike's test target):** the test codebase fits under a single user-configured parent without contortion.

## Test target

**`c:\ms-superrepo\`** -- a real multi-project monorepo, ~3.4GB, multi-language (`ms-*` subprojects covering db, license services, bbj-server, compiler, core, etc.). Selected as the spike-2 target because:
1. It is a real existing codebase, not synthetic (per spike-1's framing, transplanted to spike-2 H3).
2. It is likely to be an early-release Optimus user once GA ships.
3. Its `origin` remote has been removed (`git remote remove origin` run before the spike began) so accidental writes cannot push to upstream.
4. Its size and structure exercise the parent-mount model meaningfully (a small synthetic fixture would not).

## Transport coverage

**BOTH transports per PM ruling 2026-05-12 (full DoD coverage):**

1. **WSL2 Unix-socket** (Linux container under WSL2): the primary supported deployment per TR-09 + CHARTER FD7. Validates against `transport-and-discovery.md` sections 1-5 (Linux path).
2. **Windows-native named-pipe** (direct Python server on Windows): per `transport-and-discovery.md` section 1 the Windows-native form is `\\.\pipe\optimus`. Note: Windows-native does NOT run inside a Docker container in this spike -- the container model is WSL2-only at v2 GA; the Windows-native variant runs as a direct Python service. The spike validates the named-pipe transport + SID auth even though the deployment shape differs.

Each transport gets its own server stub and its own probe harness; the H1/H2/H3 verdicts are reported per transport.

## Layout

```
spike/pre-m1-singleton/
  README.md                  -- this file
  server-wsl2.py             -- Linux/WSL2 MCP-stub server (Unix socket + SO_PEERCRED + mode 0600)
  server-windows.py          -- Windows-native MCP-stub server (named pipe + ACL + SID compare)
  probe-wsl2.py              -- 4-client concurrent probe for WSL2 transport
  probe-windows.py           -- 4-client concurrent probe for Windows-native transport
  probe-discovery.py         -- discovery + stale-endpoint cleanup probe (transport-agnostic)
  grep_stub.py               -- shared canned optimus_grep impl over the parent-mount
  config-example.json        -- example ~/.optimus/config.json (parent-mount + concurrency cap)
  Dockerfile                 -- minimal Linux container for WSL2 transport
  compose.yml                -- docker compose with --network none + parent-mount + socket bind-mount
  results/                   -- run artifacts (gitignored)
```

## How to run

Prerequisites: Docker Desktop (with WSL2 backend), Python 3.10+, on Windows.

### WSL2 path (H1/H2/H3 verdicts for WSL2 transport)

```powershell
# From spike/pre-m1-singleton/
docker compose -f compose.yml up -d --build
# Server is now listening on the socket inside the container, bind-mounted to ~/.optimus/optimus.sock on the host.
python probe-wsl2.py
# Expected: 4 clients connect concurrently, all get pings back; concurrent grep correctness verified; stale-endpoint cleanup demonstrated.
docker compose -f compose.yml down
```

### Windows-native path (H1/H2 verdicts for named-pipe transport)

```powershell
# From spike/pre-m1-singleton/
python server-windows.py &
# Server listens on \\.\pipe\optimus with restricted ACL.
python probe-windows.py
# Expected: 4 clients connect concurrently; cross-user-SID rejection demonstrated; concurrent grep correctness verified.
```

### Discovery + stale-endpoint cleanup (transport-agnostic)

```powershell
python probe-discovery.py
# Expected: socket-aliveness probe per transport-and-discovery.md section 5 (500ms initial + 200ms retry); stale endpoint cleaned up before respawn.
```

## What we record per run

For each run we capture:
- Timestamps (start, end, duration).
- Client connection success/failure per client.
- Response correctness per call (probe asserts a known shape per stub-tool call).
- Concurrency-cap behavior (when configured concurrency is exceeded, do clients beyond the cap get a structured "busy, retry" response, NOT a silent drop or crash?).
- Discovery probe results (existing-container detection, stale-endpoint detection + cleanup).
- WSL2-specific: parent-mount path translation (host path `c:\ms-superrepo\` resolves to `/workspace/ms-superrepo/` inside the container; the stub grep returns results matching the host filesystem state).

Recorded JSON artifacts land in `results/` (gitignored). The aggregated verdict goes in `docs/spikes/spike-2-singleton-report.md`.

## What this spike is NOT

- Not a real optimus MCP server. The stub does minimal MCP-shaped request/response framing and a canned `optimus_grep` -- enough to exercise the transport + concurrency + discovery contract, NOT to do real retrieval.
- Not a test of retrieval relevance. That's spike-1's territory.
- Not a test of the secure-singleton-mcp-baseline stack (Nomic, ColBERTv2 via RAGatouille). The spike uses a minimal in-process stub.
- Not Cursor/Claude-Code integration testing. The probe clients are Python; real IDE-loader integration happens in M4/M5.

## Gate logic (per `pre-M1-spikes.md`)

- H1 + H2 + H3 confirm on BOTH transports -> spike-2 passes; v2 proceeds with singleton model.
- H1 or H2 fails on either transport -> fall back to multi-mount mode; TR-18 requirements amended; M1.0 Architecture Spike inputs adjusted; record the asymmetry per transport.
- H3 fails (parent-mount UX unreasonable on `ms-superrepo`) -> escalate to Dustin before proceeding; this is a charter-level reconsideration.

## Cross-references

- `docs/decomp/pre-M1-spikes.md` -- spike framing + DoD.
- `docs/decisions/transport-and-discovery.md` -- the contract this spike validates against.
- `docs/decisions/secure-singleton-mcp-baseline.md` -- singleton lifecycle / container baseline (not the focus here).
- `CHARTER.md` Founding Decision 5 (validation spikes) + Founding Decision 7 (host-singleton container).
- `docs/requirements/REQUIREMENTS.md` TR-13 (process-credential auth), TR-18 (transport + concurrency).
