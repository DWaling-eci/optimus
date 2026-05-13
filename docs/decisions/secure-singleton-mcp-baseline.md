# Decision Record: Secure Singleton MCP Baseline (Docker + Server + Models)

**Status:** Decided -- locked. This is the stack and approach v2 builds against. M1.0 Architecture Spike retains revision authority ONLY if a hard roadblock surfaces during implementation; absent such a roadblock, the stack below is built as-is.
**Owner:** Dustin (locked at refactor time). Roadblock-driven revision flows through normal decision-record revision (PR + sign-off).

## Why this record exists

The singleton container baseline ties together four concerns that the rest of the v2 plan depends on as a single coherent shape:

- The Docker isolation posture (network-none, RO parent mount, RW scratch, model-cache bind-mount).
- The MCP server lifecycle (single process, bipartite concurrency, singleton ML worker).
- The model stack and how models reach the container (install-time distribution, NOT runtime download).
- The transport binding (Unix domain socket / named pipe per `docs/decisions/transport-and-discovery.md`).

If any of those four drift independently the singleton design fails at integration. This record locks all four so M1 implementation, the spike-2 probe, and both bundlers (M4/M5) build to the same shape.

## Locked design calls

### 1. Model stack -- locked

- **First-stage dense retrieval:** **Nomic CodeRankEmbed** (`nomic-ai/nomic-embed-text-v1.5`-class, code-specific). `trust_remote_code=True` is required and is acceptable under the trust model captured in section 6 below.
- **Reranker:** **ColBERTv2 via colbert-ai direct** (`colbert-ir/colbertv2.0`, invoked through `colbert.modeling.checkpoint.Checkpoint`'s MaxSim scoring). Late-interaction token scoring; runs materially faster than a traditional cross-encoder while delivering near-SOTA precision within the 8 GB container envelope (TR-04). **Wrapper revised 2026-05-13** per `docs/decisions/colbert-wrapper-revision.md` -- mechanism preserved, only invocation surface changed; see that record for the roadblock evidence.
- **Two-stage pipeline:** dense filter -> top-100 candidates -> ColBERTv2 rerank -> top-5 returned to the agent. Context-clamping at `top_k = 5` is intentional.

This stack supersedes the prior "dual-CE vs single-CE pending M1.0" framing in `docs/glossary.md`. The dual-CE question is retired; Nomic + ColBERTv2 is the answer.

### 2. Container isolation posture -- locked

- **`network_mode: "none"`** on the singleton container. Absolute network isolation at the kernel level. Even a compromised dependency or hallucinated payload cannot route traffic outbound.
- **Parent mount: read-only.** `${HOST_PARENT_DIR}:/mnt/parent_mount:ro` -- the container reads user projects but cannot write to them.
- **Scratch mount: read-write.** `~/.optimus/scratch:/var/optimus/scratch:rw` -- isolated writable surface for agent-authored scratch artifacts (per `agent-scratch` hook).
- **Model cache mount: read-only.** `~/.optimus/model-cache:/root/.cache/huggingface:ro` -- installer-populated; container cannot tamper with weights.
- **Socket directory mount: read-write.** `~/.optimus/sockets:/var/optimus/sockets:rw` -- needed for the server to create the listening Unix socket; the socket file itself is owner-only (0600) per the transport decision.

This isolation posture is the architectural enforcement of TR-06 (zero external API calls at runtime).

### 3. Bipartite concurrency -- singleton ML worker -- locked

- The **main process** runs the MCP server: async I/O only, lightweight, services concurrent client connections.
- A **dedicated ML worker process** (`multiprocessing.Process`, spawned once at boot) loads Nomic + ColBERTv2 exactly once and lives for the container's lifetime. The worker reads from a `multiprocessing.Queue` and returns results via a result queue.
- The main process dispatches ML work via `asyncio.to_thread` against the queue, never blocks the event loop, and yields back periodically so other in-flight MCP RPCs are not starved.

This is the GIL-mitigation strategy and the answer to TR-18's worker-pool requirement: one worker process handles serialized ML execution, and the async main process handles concurrent MCP transport. Concurrency cap defaults are tuned from spike-2 evidence (>= 4 concurrent clients probed per Charter Decision 7).

### 4. Transport binding -- Unix socket / named pipe (delegated)

The server binds to a Unix domain socket (Linux + WSL2) or a named pipe (Windows native) per `docs/decisions/transport-and-discovery.md`. Socket path, permissions, `.mcp.json` schema, liveness-probe protocol, and `SO_PEERCRED` / `GetNamedPipeClientProcessId` process-credential auth are all owned by that record. This baseline implements that contract; it does not redefine it.

The MCP server example in section 8 demonstrates the **correct** binding (Unix socket) -- not `stdio_server()`. Stdio is incompatible with the multi-client singleton model and was a holdover snippet from the MCP SDK quickstart.

### 5. Roadblock-revision rule -- locked

Dustin's call, verbatim: *"This is the stack and approach we will go for ... we only reconsider if we run into roadblocks on that path."*

- The Nomic + ColBERTv2 stack, the bipartite concurrency model, and the isolation posture are **built as decided.** No "we'll pick at M1.0" framing applies any more.
- **M1.0 Architecture Spike retains revision authority IF AND ONLY IF a hard roadblock surfaces** during implementation (e.g., RAGatouille incompatibility with the container env, Nomic load failure under the memory cap, an unforeseen MCP/Unix-socket integration block). Revision flows through normal decision-record revision (PR + sign-off + cross-doc propagation).
- "Roadblock" means hard-blocking, evidence-backed: a measurement, a reproducible failure, or a concrete incompatibility -- not a preference shift. Soft preference revisions do not qualify.

**First roadblock-driven revision landed 2026-05-13** -- see `docs/decisions/colbert-wrapper-revision.md` for evidence and scope. The revision modifies § 3.1 wrapper naming and § 3 illustrative-code rerank invocation only; all other locked clauses (model stack identity, isolation posture, bipartite concurrency, transport binding, model distribution / trust posture) remain in force. The roadblock-revision rule itself is unchanged.

### 6. Model Distribution & Trust Posture -- locked

This section codifies how models reach the container, who is the gatekeeper, and why `trust_remote_code=True` is acceptable here.

- **Hosting:** Models are attached as **GitHub Release artifacts on the optimus repo.** Each release ships a manifest pinning model SHAs (`models-manifest.json` or equivalent), so what users get is the exact bytes the release was tested against.
- **Installer is the gatekeeper.** `optimus_doctor` (or the install/update path) downloads model artifacts from the optimus repo's release, **SHA-verifies** them against the release's pinned manifest, and places them in `~/.optimus/model-cache/`. No download is trusted without SHA verification.
- **Smart-skip:** The installer compares the current release's manifest against `~/.optimus/installer-state/models-manifest.json` (the cached-state record of what is currently on disk). If they match, no download. If they differ, download + verify + replace.
- **The Docker image NEVER downloads models.** Not at build time. Not at runtime. The Dockerfile MUST NOT pull from Hugging Face, MUST NOT `git clone` model repos, MUST NOT include any model-fetch step. Image build is model-decoupled and fast; image size stays small; image build does not depend on HF availability.
- **Runtime:** The container bind-mounts `~/.optimus/model-cache/` **read-only** at `/root/.cache/huggingface`. The singleton ML worker loads weights from the mounted cache. If the cache is empty or weights are missing, the worker fails at boot fast and loudly -- the `network_mode: "none"` isolation guarantees the container cannot recover by silently phoning home.
- **`trust_remote_code=True` is acceptable** under this trust model. The trust boundary is **our installer + our pinned manifest**, NOT direct Hugging Face trust at runtime. The model code that loads under `trust_remote_code=True` is part of the SHA-verified artifact shipped with our release; it has been reviewed and pinned by us. Future readers: this is intentional. The flag is set because the trust boundary moved up-stack to the installer, not because we are trusting HF at runtime.

**TR-06 reconciliation:** TR-06 mandates zero external API calls **at runtime.** The install-time model download is an installer event (host-side, executed by `optimus_doctor` before the container starts), not a runtime event. TR-06's runtime claim is preserved by the `network_mode: "none"` enforcement in section 2.

## Baseline Implementation

This section provides the foundational Docker configuration and an illustrative server.py demonstrating the mechanics described above.

> **Illustrative, not literal template.** The `server.py` example below is a **GUIDE** demonstrating the mechanics of the singleton + MCP + isolation pattern. It is **NOT** a literal template. Specific code WILL diverge during M1 implementation per the modular package layout (TR-01) and per findings during build. Only the demonstrated **mechanics** are load-bearing: singleton lifecycle, isolation properties, MCP server shape, transport binding, model-load discipline. Source-level details (function signatures, import organization, error-handling specifics) are M1 implementer's call.

### 1. `image/Dockerfile`

Slim Python 3.10 image. **Contains no model-download step.** Models arrive via the installer-managed bind-mount at runtime (section 6 above). **Contains no build toolchain step for garp.** The garp Linux binary is pre-built from the SHA-pinned `tools/garp/` submodule and committed to `container/vendor/garp-json` (alongside a `container/vendor/garp-json.manifest.json` traceability manifest); the image build COPYs the pre-built artifact. End-users never need a Go toolchain. See CHARTER Founding Decision 1 (External Tool Vendoring & Distribution) for the full convention, and TR-10 for garp-specific pinning.

```dockerfile
# No build stage needed for garp: the Linux binary is pre-built from the
# tools/garp/ submodule and committed at container/vendor/garp-json. Bumping
# the submodule SHA and rebuilding the vendored binary is a deliberate PR with
# a matching update to container/vendor/garp-json.manifest.json. See CHARTER
# Founding Decision 1 and TR-10.

FROM python:3.10-slim
# Install system dependencies (build-essential needed for some ML libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# ~~ Vars from Optimus v1 (in case they become useful here) ~~
# Silence rogue stdout/stderr noise from ML libs (Issue #8, Phase 1).
# Progress bars and warnings written to stdout can corrupt the JSON-RPC
# stream and drive Cursor's MCP client to transport_closed. PYTHONUNBUFFERED
# is belt-and-braces with the `-u` flag already in CMD.
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ENV TQDM_DISABLE=1
# ENV TOKENIZERS_PARALLELISM=false
# ENV TRANSFORMERS_VERBOSITY=error

WORKDIR /app

# Pre-built garp binary; source pinned at tools/garp/ submodule SHA recorded
# in container/vendor/garp-json.manifest.json. CI verifies the manifest's
# source_sha matches the submodule SHA before image publish.
COPY container/vendor/garp-json /usr/local/bin/garp-json
RUN chmod +x /usr/local/bin/garp-json

# Install ML and MCP requirements
# Note: RAGatouille provides the optimized ColBERTv2 implementation.
# IMPORTANT: requirements.txt MUST NOT include any model-fetch step (no `huggingface-cli download`,
# no `git clone <hf-model-repo>`, no python-side preload-on-import). Models arrive at runtime
# via the installer-managed bind-mount on ~/.optimus/model-cache/. See section 6 above.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Expected requirements.txt:
# mcp==1.0.0
# sentence-transformers>=2.5.0
# colbert-ai>=0.2.20            # direct; ragatouille wrapper retired per colbert-wrapper-revision.md
# einops>=0.7.0
# torch>=2.1.0

# Copy the source code
COPY src/ /app/src/

# Create the socket directory for IPC with the host
RUN mkdir -p /var/optimus/sockets/

# Ensure the model-cache mountpoint exists (populated by host bind-mount at runtime; NEVER pre-populated here)
RUN mkdir -p /root/.cache/huggingface/

# Entrypoint runs the MCP server
CMD ["python", "-u", "src/optimus/server.py"]
```

**Build-toolchain decoupling:** the image build is pure assembly of pre-built artifacts. No `git clone` of external tool sources at build time, no `go build`, no compile step. Combined with section 6's model-decoupling, image build is fast, reproducible, and independent of upstream availability (GitHub, Hugging Face).

### 2. `~/.optimus/docker-compose.yml`

This configuration applies the strict isolation and resource constraints dictated by TR-04 and TR-06.

```yml
version: '3.8'
services:
  optimus:
    # Publish target locked: ghcr.io/DWaling-eci/optimus:<tag> (GitHub Container Registry).
    # DWaling-eci placeholder until the optimus repo lands on GitHub; see TR-07.
    image: ghcr.io/DWaling-eci/optimus:v2.0.0
    container_name: optimus_mcp
    # Zero-Trust Isolation: Completely disables the network stack
    network_mode: "none"
    # Enforce TR-04: Hard memory limit
    deploy:
      resources:
        limits:
          memory: 8G
    volumes:
      # Mount the installer-populated ML models (Read-Only to prevent tampering)
      - ~/.optimus/model-cache:/root/.cache/huggingface:ro
      # Mount the Unix socket directory for MCP Transport
      - ~/.optimus/sockets:/var/optimus/sockets:rw
      # Mount the shared Scratch directory
      - ~/.optimus/scratch:/var/optimus/scratch:rw
      # Mount the user-configured parent directory where projects live.
      # HOST_PARENT_DIR is REQUIRED -- no default. The installer (optimus_doctor)
      # is responsible for ensuring this env var is populated per the user's TR-18
      # parent-directory configuration (~/.optimus/config.json). If unset, compose
      # errors out cleanly rather than silently mounting an unintended directory
      # (e.g., `..` from the invocation cwd, which from $HOME would mount the entire home tree).
      - ${HOST_PARENT_DIR:?HOST_PARENT_DIR must be set; run optimus_doctor or check ~/.optimus/config.json}:/mnt/parent_mount:ro
      # Placeholder for project IDE chat-log directories
      # - <~/.cursor/globalStorage/state.vscdb
      # - <~/.cursor/ai-tracking/ai-code-tracking.db
    environment:
      - WORKSPACE_DIR=/workspace
      # Environment variables to control behavior
      - LOG_LEVEL=info
      # Transport endpoint -- see docs/decisions/transport-and-discovery.md for the locked schema
      - MCP_TRANSPORT=unix:///var/optimus/sockets/mcp.sock
      # Optimus configurations
      - RERANK_BATCH_SIZE=16
```

### 3. `src/optimus/server.py` -- ***ILLUSTRATIVE GUIDE, NOT LITERAL TEMPLATE***

The code below demonstrates the **mechanics** of singleton+MCP+isolation. Actual M1 implementation will use a modular layout per TR-01 (one module per logical subsystem; `server.py` is the thin entrypoint <= 100 lines). What this guide demonstrates and what M1 MUST preserve:

- **Singleton ML worker process** spawned once at boot, models loaded exactly once.
- **Bipartite concurrency:** async main process for MCP I/O, dedicated multiprocessing worker for ML work, queues bridging the two.
- **Two-stage retrieval pipeline:** Nomic dense retrieval -> top_k_dense filter -> ColBERTv2 rerank -> top_k=5 returned.
- **Unix-domain-socket transport binding** -- NOT stdio. The server listens on the path defined by `docs/decisions/transport-and-discovery.md`.
- **Context clamping** at `top_k = 5`.
- **Path-confinement at the MCP boundary** -- every user-supplied path is `realpath`-resolved and prefix-checked against the parent-mount root BEFORE any FS operation. Implemented by `_confine_path` in the illustrative code below.

What may diverge during M1: function signatures, module organization, error-handling shape, logging integration, request-queueing details, exact tool-registration plumbing.

> **SECURITY -- PATH CONFINEMENT IS NON-NEGOTIABLE.**
>
> The illustrative `optimus_search` below applies `_confine_path` to every agent-supplied path before any filesystem operation. **Any tool implementation that accepts paths (`optimus_search`, `optimus_grep`, `optimus_list`, `optimus_delete`, future endpoints) MUST apply equivalent path-confinement at the MCP boundary.** A bare `os.path.exists` check is **insufficient** -- it does not catch `../` traversal, does not resolve symlinks pointing outside the parent mount, and does not enforce the prefix invariant.
>
> This is the architectural enforcement of TR-13's mandate that **all agent-provided string inputs (paths, glob fragments, scope filters) MUST be sanitized at the MCP boundary BEFORE reaching any subprocess invocation**. `network_mode: "none"` (section 2) contains outbound traffic; path confinement contains in-bound filesystem reach. Both layers are load-bearing; neither is sufficient alone.
>
> Failure mode: an agent payload like `search_dirs=[{"path": "../../etc"}]` MUST raise a structured MCP error (via `_confine_path`'s `ValueError`), NOT silently walk outside the parent mount. Symlinks pointing outside the mount MUST also raise -- `os.path.realpath` is the load-bearing call.

#### Pipeline summary

- **`task_type == "search_pipeline"`** keeps the entire two-stage execution inside `ml_worker_loop` so heavy tensors do not cross the process boundary back to the main process.
- **`torch.nn.functional.cosine_similarity`** computes the vectorized query against the repository vector block in one pass.
- **`torch.topk`** efficiently trims to `top_k_dense = 100` candidates before passing to ColBERTv2.

```python
# ============================================================================
# ILLUSTRATIVE GUIDE -- NOT A LITERAL TEMPLATE.
# M1 implementation will modularize per TR-01. The mechanics demonstrated here
# (singleton ML worker, bipartite concurrency, Unix-socket transport binding,
# two-stage Nomic -> ColBERTv2 pipeline, top-5 context clamp) are load-bearing
# and MUST be preserved. The exact code shape is M1 implementer's call.
# ============================================================================

import asyncio
import logging
import multiprocessing as mp
import os
from queue import Empty

# MCP SDK Imports
from mcp.server import Server
# Transport: Unix domain socket (Linux + WSL2) / named pipe (Windows native).
# See docs/decisions/transport-and-discovery.md for the locked transport spec:
# socket path, 0600 permissions, .mcp.json schema, liveness-probe protocol,
# and SO_PEERCRED / GetNamedPipeClientProcessId process-credential auth.
# Stdio is NOT used -- it is incompatible with the multi-client singleton model.

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optimus.server")

# Resolved by the transport-and-discovery decision record. Mounted from the host
# at ~/.optimus/sockets/mcp.sock (the host installer manages the directory; the
# container creates the socket file at boot and removes it on shutdown).
MCP_SOCKET_PATH = os.environ.get("MCP_SOCKET_PATH", "/var/optimus/sockets/mcp.sock")

# Parent-mount root inside the container. Locked by docker-compose per section 2.
# Every agent-supplied path is realpath-resolved and prefix-checked against this
# root before ANY filesystem operation. See TR-13 + the SECURITY callout above.
PARENT_MOUNT = "/mnt/parent_mount"


def _confine_path(user_path: str) -> str:
    """Resolve user-supplied path and ensure it stays within PARENT_MOUNT.

    Raises ValueError on escape attempts (`..` traversal, symlinks pointing
    outside the mount, absolute paths reaching elsewhere). MUST be called at
    the MCP boundary on every user-supplied path BEFORE any FS operation.
    This is the architectural enforcement of TR-13's sanitization mandate;
    a bare os.path.exists check is NOT sufficient.
    """
    abs_path = os.path.realpath(os.path.join(PARENT_MOUNT, user_path.lstrip("/")))
    if not abs_path.startswith(PARENT_MOUNT + os.sep) and abs_path != PARENT_MOUNT:
        raise ValueError(f"path escapes parent mount: {user_path}")
    return abs_path

# =====================================================================
# SINGLETON ML WORKER
# =====================================================================
def ml_worker_loop(task_queue: mp.Queue, result_queue: mp.Queue):
    """
    Runs in a dedicated background process.
    Pre-loads the ML models exactly once to respect the 8GB memory limit.
    Models are loaded from the host-bind-mounted cache at /root/.cache/huggingface
    (read-only). The container itself NEVER downloads models -- see section 6.
    """
    logger.info("ML Worker: Initializing Nomic CodeRankEmbed and ColBERTv2...")

    import torch
    import torch.nn.functional as F
    from sentence_transformers import SentenceTransformer
    from colbert.modeling.checkpoint import Checkpoint
    from colbert.infra import ColBERTConfig

    # 1. Load Nomic CodeRankEmbed.
    # trust_remote_code=True is acceptable under our trust model: the model files
    # are part of our SHA-verified, installer-pinned release artifact, NOT a
    # runtime HF trust. See section 6 of the baseline decision record.
    query_prefix = "search_query: "
    document_prefix = "search_document: "
    embed_model = SentenceTransformer(
        "nomic-ai/nomic-embed-text-v1.5",
        trust_remote_code=True
    )

    # 2. Load ColBERTv2 via colbert-ai direct (wrapper revised per
    #    docs/decisions/colbert-wrapper-revision.md). Checkpoint exposes
    #    queryFromText / docFromText for encoding and the MaxSim score
    #    operator the rerank uses.
    colbert_cfg = ColBERTConfig()  # defaults sufficient for in-memory rerank
    reranker_ckpt = Checkpoint("colbert-ir/colbertv2.0", colbert_config=colbert_cfg)

    logger.info("ML Worker: Models loaded successfully. Awaiting tasks.")

    while True:
        try:
            task = task_queue.get(timeout=1.0)
            task_id, task_type, payload = task

            if task_type == "search_pipeline":
                query = payload["query"]
                documents = payload["documents"]
                top_k_dense = payload.get("top_k_dense", 100)

                # --- STAGE 1: Dense Retrieval (Nomic) ---
                query_emb = embed_model.encode([query_prefix + query], convert_to_tensor=True)
                doc_texts = [document_prefix + d for d in documents]
                doc_embs = embed_model.encode(doc_texts, convert_to_tensor=True)

                cos_scores = F.cosine_similarity(query_emb, doc_embs)

                k = min(top_k_dense, len(documents))
                top_results = torch.topk(cos_scores, k=k)
                top_indices = top_results.indices.tolist()

                dense_candidates = [documents[i] for i in top_indices]

                # --- STAGE 2: Late-Interaction Reranking (ColBERTv2 MaxSim) ---
                # Encode query + candidates; compute per-candidate MaxSim score;
                # sort descending. Equivalent to RAGatouille's rerank() in the
                # pre-bloat era but without the wrapper's transitive-dep surface.
                # API notes (verified against colbert-ai 0.2.22):
                #   - docFromText's public keep_dims values are True (padded
                #     tensor), False (per-doc list), "flatten" (flat tensor +
                #     doclens). keep_dims=False gives per-doc embeddings without
                #     padding, so MaxSim doesn't have to mask out pad tokens.
                #   - When bsize is set, docFromText returns a TUPLE wrapping
                #     the result (return_text is splat-appended). Unwrap.
                q_emb = reranker_ckpt.queryFromText([query])  # [1, Nq, dim]
                docs_result = reranker_ckpt.docFromText(
                    dense_candidates, bsize=16, keep_dims=False
                )
                d_emb_list = docs_result[0] if isinstance(docs_result, tuple) else docs_result
                ranked_docs = []
                for doc_text, d_emb in zip(dense_candidates, d_emb_list):
                    # MaxSim: for each query token, max similarity across doc
                    # tokens; sum across query tokens.
                    sim = q_emb[0] @ d_emb.T  # [Nq, doc_tokens]
                    score = float(sim.max(dim=-1).values.sum().item())
                    ranked_docs.append({"document": doc_text, "score": score})
                ranked_docs.sort(key=lambda r: r["score"], reverse=True)
                result_queue.put((task_id, {"ranked_results": ranked_docs}))

            elif task_type == "shutdown":
                logger.info("ML Worker: Shutting down.")
                break

        except Empty:
            continue
        except Exception as e:
            logger.error(f"ML Worker Error: {str(e)}")
            result_queue.put((task_id, {"error": str(e)}))

# =====================================================================
# ASYNC MCP SERVER (MAIN PROCESS)
# =====================================================================
class OptimusServer:
    def __init__(self):
        self.app = Server("optimus-mcp")
        self.task_queue = mp.Queue()
        self.result_queue = mp.Queue()
        self.worker_process = None
        self.task_counter = 0
        self.setup_tools()

    def start_worker(self):
        """Spawns the background ML process before taking MCP requests."""
        self.worker_process = mp.Process(
            target=ml_worker_loop,
            args=(self.task_queue, self.result_queue),
            daemon=True
        )
        self.worker_process.start()

    async def _dispatch_ml_task(self, task_type: str, payload: dict) -> dict:
        """
        Asynchronously sends a task to the ML worker and awaits the result
        without blocking the main asyncio event loop.
        """
        self.task_counter += 1
        task_id = self.task_counter

        self.task_queue.put((task_id, task_type, payload))

        while True:
            try:
                res_id, response = await asyncio.to_thread(self.result_queue.get, True, 0.1)
                if res_id == task_id:
                    if "error" in response:
                        raise RuntimeError(response["error"])
                    return response
            except Empty:
                await asyncio.sleep(0.05)  # Yield control back to the event loop

    def setup_tools(self):
        @self.app.call_tool()
        async def optimus_search(query: str, search_dirs: list[dict] | None = None) -> str:
            """
            Primary MCP tool for natural language codebase queries.
            1. Resolves targets: `search_dirs` or default workspace root.
            2. Reads and chunks candidate files (baseline implementation).
            3. Dispatches to ML Worker for two-stage retrieval (Nomic -> ColBERTv2).
            """
            logger.info(f"Received optimus_search for: '{query}' in dirs: {search_dirs}")

            # Path confinement: every agent-supplied path MUST be resolved and
            # prefix-checked against PARENT_MOUNT before any FS operation.
            # Bare os.path.exists is insufficient (does not catch ../ traversal
            # or symlinks pointing outside the mount). See TR-13 + the SECURITY
            # callout above the code block. Any sibling tool (optimus_grep,
            # optimus_list, optimus_delete) MUST apply equivalent confinement.
            dirs_to_search = []
            if search_dirs:
                for d in search_dirs:
                    if "path" in d:
                        try:
                            dirs_to_search.append(_confine_path(d["path"]))
                        except ValueError as exc:
                            # Surface as a structured MCP error rather than walking
                            # an unintended directory or returning a generic crash.
                            return f"Optimus Search Error: {exc}"
            else:
                dirs_to_search = [PARENT_MOUNT]

            candidate_chunks = []
            for target_dir in dirs_to_search:
                if not os.path.exists(target_dir):
                    continue

                for root, _, files in os.walk(target_dir):
                    if "/." in root or "\\." in root:
                        continue

                    for file in files:
                        if file.startswith('.'):
                            continue

                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                                # Baseline chunking; future: AST-aware or garp-driven candidates.
                                chunk_size = 1500
                                for i in range(0, len(content), chunk_size):
                                    chunk = content[i:i+chunk_size]
                                    candidate_chunks.append(f"File: {file_path}\n{chunk}")
                        except Exception:
                            continue

            if not candidate_chunks:
                return "No readable text files found in the specified directories."

            try:
                ml_result = await self._dispatch_ml_task("search_pipeline", {
                    "query": query,
                    "documents": candidate_chunks,
                    "top_k_dense": 100
                })

                ranked_results = ml_result["ranked_results"]

                # Context clamp: only the top 5 results reach the agent.
                top_k = 5
                output = f"Top {top_k} results for '{query}':\n\n"

                for i, res in enumerate(ranked_results[:top_k], 1):
                    score = res['score']
                    doc_snippet = res['document'].strip()
                    output += f"--- Result {i} (Score: {score:.2f}) ---\n{doc_snippet}\n\n"

                return output

            except Exception as e:
                logger.error(f"Optimus Search Error: {str(e)}")
                return f"Optimus Search Error: {str(e)}"

    async def run(self):
        # Start the singleton ML worker BEFORE accepting MCP connections.
        self.start_worker()

        # Bind to a Unix domain socket per docs/decisions/transport-and-discovery.md.
        # NOT stdio -- stdio is single-client and incompatible with the host-singleton model.
        # The host installer ensures the parent directory exists with 0700 perms;
        # the container creates the socket here with 0600 perms (owner-only).
        # Stale socket cleanup (if a prior container crashed without removing it) is
        # the liveness-probe-driven host-side concern -- see transport-and-discovery.md
        # section 5 for the canonical cleanup protocol.
        if os.path.exists(MCP_SOCKET_PATH):
            os.unlink(MCP_SOCKET_PATH)

        logger.info(f"Optimus Server binding to Unix socket: {MCP_SOCKET_PATH}")

        # Pseudocode for the Unix-socket bind. The exact MCP SDK call shape is
        # M1 implementer's call -- what matters is: AF_UNIX socket, 0600 perms,
        # process-credential auth at handshake per transport-and-discovery.md section 4.
        server = await asyncio.start_unix_server(
            self._handle_mcp_connection,
            path=MCP_SOCKET_PATH,
        )
        os.chmod(MCP_SOCKET_PATH, 0o600)

        async with server:
            await server.serve_forever()

    async def _handle_mcp_connection(self, reader, writer):
        # Process-credential check (SO_PEERCRED on Unix, GetNamedPipeClientProcessId on Windows)
        # is the load-bearing auth step. Reject the connection if the peer UID/SID does not
        # match the singleton owner. See docs/decisions/transport-and-discovery.md section 4
        # for the canonical implementation requirements and the logging requirement on rejects.
        # ... peer-cred check ...
        await self.app.run(reader, writer, self.app.create_initialization_options())


if __name__ == "__main__":
    server = OptimusServer()
    asyncio.run(server.run())
```

## Consumers (cross-reference)

- `CHARTER.md`, Founding Decision 7 -- this record owns the singleton container baseline; transport surface is delegated to `docs/decisions/transport-and-discovery.md`.
- `docs/decisions/transport-and-discovery.md` -- owns the transport binding shape that this record implements.
- `docs/requirements/REQUIREMENTS.md` -- TR-03 (model isolation + bind-mount), TR-04 (memory bounds), TR-06 (zero runtime external calls), TR-07 (installer self-check including model manifest), TR-18 (concurrency + parent-mount).
- `docs/decomp/M4-user-profile-layout.md` -- consumer of the installer-populated model-cache directory.
- `docs/decomp/M1-tasks.md`, Phase 1.0 -- holds the narrow roadblock-driven revision authority over this record.
- `docs/decomp/pre-M1-spikes.md` -- spike-2 validates the singleton + transport mechanics described here.
- `docs/decisions/colbert-wrapper-revision.md` -- 2026-05-13 roadblock-driven revision to § 3.1 wrapper naming + § 3 illustrative-code rerank invocation. Mechanism preserved; only the wrapper changes.

## Status note

Locked at refactor time. The stack (Nomic CodeRankEmbed + ColBERTv2 via colbert-ai direct -- RAGatouille wrapper retired 2026-05-13 per `docs/decisions/colbert-wrapper-revision.md`), the bipartite concurrency model, the isolation posture (`network_mode: "none"`, RO parent mount, RO model-cache, RW scratch + sockets), the Unix-socket transport binding, and the install-time-only model distribution (with `trust_remote_code=True` acceptable under the installer-as-gatekeeper trust model) are all decided. M1.0 Architecture Spike retains revision authority ONLY for hard, evidence-backed roadblocks; absent such a roadblock, this is what gets built. The `server.py` block is an illustrative guide demonstrating the mechanics, NOT a literal template.

## Revision history

| Date | Revision | Authority | Reference |
|---|---|---|---|
| 2026-05-13 | First roadblock-driven revision: ColBERTv2 wrapper changed from RAGatouille to colbert-ai direct. Mechanism preserved; trust-boundary surface reduced ~45% (134 -> 74 transitive packages). § 3.1 + § 3 illustrative code updated; all other clauses unchanged. | `docs/decisions/secure-singleton-mcp-baseline.md` § 5 + `docs/decisions/colbert-wrapper-revision.md` | spike-1 install probe dry-run JSONs at `spike/pre-m1-retrieval/dry-run-report*.json` |
