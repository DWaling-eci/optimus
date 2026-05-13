# Optimus v2: Architecture & Security Proposals

**Target:** M1.0 Architecture Spike Inputs
Authors: Architecture & Security Teams

The following proposals address critical vulnerabilities and performance bottlenecks in the v2 design.

## 🛡️ Proposal 1: Zero-Trust Container Network Isolation

*Addressing the Red-Team's data exfiltration concerns and enforcing TR-06.*

**The Problem:**
Requirement `TR-06` mandates "Zero External API Calls," but relying on application-layer logic to enforce this is a major security flaw. Given the "parent-mount" blast radius, a compromised container or a parameter injection attack via `optimus_grep` could easily execute a script to exfiltrate proprietary code.

**The Proposed Design:** ***Unix Domain Sockets & Kernel-Level Isolation***
To guarantee absolute network isolation, we must disable the Docker container's network stack entirely and rely on file-based communication.

1. `--network none`: The `docker-compose.yml` generated in `~/.optimus/` will explicitly set `network_mode: none`. This instructs the Linux kernel to strip the container of any networking interfaces (no `eth0`, no loopback to the host network).
2. **Unix Domain Sockets:** Instead of using TCP-on-loopback for the multi-client MCP transport, the server will bind to a Unix Domain Socket.
3. **Mount Implementation:** - The host-side installer creates `~/.optimus/sockets/`.
	- This directory is bind-mounted into the container at `/var/optimus/sockets/`.
	- The Python MCP server binds to `unix:///var/optimus/sockets/mcp.sock`.
	- Cursor and Claude Code connect directly to this socket file on the host.

**Benefits:**

- **Absolute Exfiltration Prevention:** Even if an agent hallucinates a malicious payload or a dependency is compromised, it is physically impossible for the container to route traffic to the internet.
- **Improved Performance:** Unix domain sockets have lower latency and less overhead than TCP connections, which improves the responsiveness of the MCP protocol.

## ⚡ Proposal 2: Asynchronous Main Loop with Singleton ML Worker

*Addressing the Software Architect's concerns regarding the Python GIL and TR-04 memory limits.*

**The Problem:**
Optimus v2 must handle multiple concurrent clients (`TR-18`). However, the spaCy pipeline and Cross-Encoder reranker are intensely CPU-bound. If executed in the main process, they will block the Python Global Interpreter Lock (GIL), freezing the MCP event loop for all connected IDEs. Conversely, if we use a standard `ProcessPoolExecutor` with 4 workers, each worker will load a copy of the 1GB+ models, instantly violating the 8GB memory limit (`TR-04`) and causing Out-Of-Memory (OOM) crashes.

**The Proposed Design:** ***Bipartite Concurrency Architecture***
We will separate the I/O-bound MCP transport layer from the CPU-bound ML workloads using a Singleton ML Worker pattern.

1. **The Main Process (`asyncio` Event Loop):**
	- Handles the multi-client MCP transport via the Unix socket.
	- Manages request parsing, fast path validations, and safe filesystem ops (optimus_list, optimus_delete).
	- Spawns `garp` searches using `asyncio.create_subprocess_exec`. (Because `garp` is an external Go binary, it runs outside the Python process and naturally bypasses the GIL).
2. **The Singleton ML Worker (`multiprocessing.Process`):**
	- A single, dedicated background process spawned at container startup.
	- It pre-loads the spaCy pipeline and Cross-Encoder models into its isolated memory space exactly once.
3. **Inter-Process Communication (IPC):**
	- The Main Process communicates with the ML Worker via an `asyncio`-aware `multiprocessing.Queue` (or `Pipe`).
	- When a complex `optimus_search` is called, the Main Process places the `(task_id, query, candidate_texts)` tuple into the queue and awaits the result.
	- The ML Worker processes tasks sequentially (or batches them intelligently if multiple queries pile up) and returns the reranked scores to the Main Process.

**Benefits:**

**Unblocked Event Loop:** The MCP server remains hyper-responsive to ping requests, cancellations, and fast I/O ops from other agents, even while heavy reranking is occurring.

**Strict Memory Bounding:** By guaranteeing the heavy ML models are only loaded into a single subprocess, we easily stay under the 8GB constraint while maximizing CPU utilization for that specific task.