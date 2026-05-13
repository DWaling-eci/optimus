# Decision Record: Transport + Discovery

**Status:** Decided -- locked (provisional, pre-M0). M1.0 Architecture Spike has revision authority per the hybrid pinning rule below.
**Owner:** Dustin (locked at refactor time). Revision authority delegated to the M1.0 Architecture Spike for findings-driven changes; further post-GA changes are Dustin-call.

## Why this record exists

Two independent IDE bundlers (Cursor in M4, Claude Code in M5) plus the spike-2 multi-client probe all need a **canonical agreed shape** for:

1. The discovery socket / named-pipe path (singleton container's listening endpoint).
2. The `.mcp.json` content schema that IDE projects use to point at the singleton.
3. The liveness-probe protocol (how a client distinguishes "container running" from "stale socket from a crashed container").
4. How a connecting client is authenticated as belonging to the singleton owner (no honor-system trust at the transport layer).

If M4 and M5 invent these independently, they produce incompatible bundles and the singleton model fails at the integration layer. Spike-2 also has no concrete target to validate against -- it would prototype a candidate, then potentially have to throw the work away if M1.0 picks differently. This decision record closes that loop.

## Hybrid pinning rule (revision authority)

This record is **pinned pre-M0 as a provisional version** so spike-2 has a concrete target to validate against. The pre-M0 values below are authoritative for spike-2, M4, and M5 unless revised.

The **M1.0 Architecture Spike has explicit authority to revise this record** based on implementation findings (transport behavior under concurrent load, WSL2 path translation surprises, MCP loader shape constraints discovered during bundler R&D, etc.). Any revision flows through the normal decision-record revision process: PR + sign-off, with a corresponding `optimus_protocol_version` bump (see Versioning below).

M1.0 is a **revision authority, not the original author.** Spike-2 runs against the pre-M0 version and is not blocked by anticipated revision.

## Locked design calls

### 1. Canonical socket / pipe path

- **Linux + macOS + WSL2:** `~/.optimus/optimus.sock` (Unix domain socket).
- **Windows native:** `\\.\pipe\optimus` (named pipe).

Note: macOS is out of scope for v2 GA per TR-09; the path is named here for forward-compatibility when macOS lands in v2.1+.

### 2. Permissions

- Unix domain socket: **mode 0600** (owner read/write only).
- Windows named pipe: default ACL restricted to the singleton owner's SID.

The transport endpoint is OS-protected as the first defense line. Process-credential verification (section 4) is the second.

### 3. `.mcp.json` minimum schema

Standard MCP convention with a `mcpServers` wrapper. Copy-paste-able example for each transport.

**Linux + macOS + WSL2:**

```json
{
  "mcpServers": {
    "optimus": {
      "transport": "unix-socket",
      "endpoint": "~/.optimus/optimus.sock",
      "optimus_protocol_version": "1.0"
    }
  }
}
```

**Windows native:**

```json
{
  "mcpServers": {
    "optimus": {
      "transport": "named-pipe",
      "endpoint": "\\\\.\\pipe\\optimus",
      "optimus_protocol_version": "1.0"
    }
  }
}
```

**Required fields:** `transport`, `endpoint`, `optimus_protocol_version`.

**Validation gate:** the schema above is the standard MCP shape but each IDE's MCP loader (Cursor, Claude Code) may impose shape-specific constraints discovered only during real-loader testing. **The schema MUST be validated against actual Cursor + Claude Code MCP loaders during M4/M5 bundle development**, and a small surgical revision to this record is permitted (under the hybrid pinning rule above) if a loader rejects the canonical shape.

### 4. Auth / client-identification model: process-credential check

Connecting clients are authenticated at handshake by verifying the connecting OS process's owning user matches the singleton container's owning user. Connections from a different user are rejected before any MCP frames are accepted.

- **Linux + macOS + WSL2:** `SO_PEERCRED` on the Unix domain socket. Read the peer's UID; reject the connection if it does not match the singleton owner's UID.
- **Windows native:** `GetNamedPipeClientProcessId` followed by an open-process-token + SID comparison. Reject the connection if the client process's user SID does not match the singleton owner's SID.

This is the locked answer for **TR-13 in `docs/requirements/REQUIREMENTS.md`** -- the honor-system trust model is NOT permanent; it is replaced at the transport layer by process-credential verification on every connection. TR-13's previous "decision pending" framing is retired. Hook-layer enforcement remains bypassable by design and is not the protection mechanism; the transport layer is.

Failure mode: a rejected connection surfaces a clear MCP error and is logged (per TR-14) with the offending peer PID/UID-or-SID. No silent drop.

### 5. Liveness-probe protocol

How a client decides "use the existing singleton" vs "spawn a new one":

1. Check the endpoint exists (`stat` on the socket path / named-pipe presence).
2. Open the connection and send an MCP `ping`-shaped request.
3. **Timeout: 500ms initial.** If no response, retry once after **200ms**. If still no response, treat the endpoint as stale.
4. On stale: client (or the installer's `optimus_doctor`) removes the stale endpoint file before spawning a fresh container.

**No pid-file companion.** Pid-files add lifecycle complexity (stale-pid detection, race conditions on cleanup) without delivering signal the socket-aliveness probe does not already provide. Endpoint existence + ping is the canonical liveness contract.

### 6. Versioning

Any post-v2-GA change to the transport choice, the `.mcp.json` schema, or the auth model goes through:

1. Normal decision-record revision (PR + sign-off).
2. Bump of `optimus_protocol_version` in the `.mcp.json` schema.
3. Re-emission of `.mcp.json` for each IDE by the bundlers at the new version.

No silent transport switches. **`optimus_protocol_version` is the canonical compatibility signal** between bundle and container; it complements the bundle-vs-container check in TR-19 and the MCP protocol version handshake in TR-18.

Mid-stream revisions during M1.0 (under the hybrid pinning rule) follow the same procedure: PR + sign-off, version bump if any consumer-visible field changes.

## Consumers (cross-reference)

- `CHARTER.md`, Founding Decision 1 -- references this record for the singleton's discovery + transport endpoint; hybrid pinning rule reflected there.
- `CHARTER.md`, Founding Decision 7 -- references this record for the singleton's liveness-probe protocol.
- `docs/requirements/REQUIREMENTS.md`, TR-13 -- consumes the process-credential auth model (replaces honor-system framing).
- `docs/requirements/REQUIREMENTS.md`, TR-18 -- consumes the transport mechanism, socket path, schema, and liveness probe.
- `docs/requirements/REQUIREMENTS.md`, TR-19 -- consumes `optimus_protocol_version` as the bundle/container compatibility signal.
- `docs/decomp/pre-M1-spikes.md` -- spike-2 DoD validates against this record's pre-M0 version.
- `docs/decomp/M1-tasks.md` -- Phase 1.0 holds revision authority over this record.
- `docs/decomp/M4-cursor-bundle.md` -- `.mcp.json` template emitted per this schema; loader validation gate lives here.
- `docs/decomp/M5-claude-code-bundle.md` -- same template; loader validation gate lives here.
- `docs/decisions/secure-singleton-mcp-baseline.md` -- singleton lifecycle / container baseline; this record owns the transport surface only.

## Status note

Locked at refactor time as a pre-M0 provisional version. Socket paths, permissions, `.mcp.json` schema, process-credential auth, and the 500ms+retry liveness-probe protocol are all decided. M1.0 Architecture Spike holds revision authority for findings-driven changes via normal decision-record revision; spike-2 validates against the pre-M0 version without waiting on revision. `optimus_protocol_version` is the compatibility signal for any future schema or transport change.
