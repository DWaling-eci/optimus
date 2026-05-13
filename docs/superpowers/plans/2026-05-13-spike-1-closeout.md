# Spike-1 Close-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the spike-1 close-out -- GPU-port the spike-1 MCP server, author DIRECTORY_INDEX.md + 4 controlled tasks + drift fixture, run 24 Claude Code empirical sessions on ms-superrepo, produce a POSITIVE cold-reviewed `docs/spikes/spike-1-retrieval-report.md`, single-commit + memory bump.

**Architecture:** Port the GPU-feasibility-probe's 1-line wrapper patch into spike-1's production server with device autodetect; install the GPU stack persistently in WSL2; hand-author the dir-index at the test-target root; build a per-task drift fixture; manually drive 24 Claude Code sessions through a 10-step protocol; write the report mirroring spike-2's shape; cold-reviewer subagent gates the final commit.

**Tech Stack:** Python 3.12 (WSL2 venv), torch 2.5.1+cu121, sentence-transformers, colbert-ai 0.2.22, mcp Python SDK, pytest. Runtime: Claude Code on Windows host talking to spike-1 server over stdio MCP; server runs in WSL2 with GPU passthrough.

**Approved spec:** `docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md` (Dustin-approved 2026-05-13).

---

## File Structure

**Files to create (in optimus repo):**

| Path | Purpose |
|---|---|
| `spike/pre-m1-retrieval/drift-fixture.py` | Per-task add+rename drift script; `--task <1\|2\|3\|4>` applies, `--reset` reverses. |
| `spike/pre-m1-retrieval/tests/test_device_autodetect.py` | Verifies the new device-selection helper. |
| `spike/pre-m1-retrieval/tests/test_drift_fixture.py` | Verifies drift fixture apply / reset / idempotency. |
| `docs/spikes/spike-1-retrieval-report.md` | Final hypothesis-by-hypothesis report; cold-reviewer POSITIVE before commit. |

**Files to modify (in optimus repo):**

| Path | Reason |
|---|---|
| `spike/pre-m1-retrieval/server-stdio.py` | Add device autodetect; apply 1-line wrapper patch at MaxSim matmul (line 163). |
| `spike/pre-m1-retrieval/requirements.txt` | Switch from CPU torch wheel to `torch==2.5.1+cu121` GPU stack (mirror of `requirements-gpu.txt`). |
| `spike/pre-m1-retrieval/README.md` | New GPU-stack install instructions; new venv path; persistent venv reused across 24 sessions. |
| `C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/optimus-kickoff-state.md` | Spike-1 outcome bump. |
| `C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/MEMORY.md` | Index entry refresh. |

**Files to create (outside optimus repo):**

| Path | Purpose |
|---|---|
| `c:/ms-superrepo/DIRECTORY_INDEX.md` | Hand-authored, lives at test-target root. NOT in optimus. |

---

## Phase 0 -- Server port

### Task 1: Shai-Hulud pre-install scan for the new GPU pin

**Files:** none (read-only check)

- [ ] **Step 1: Run the dry-run pip resolution + contamination check**

In WSL2, where the spike venv lives:

```bash
wsl.exe -- bash -c 'cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python3 -m pip install --dry-run --report /tmp/dry-run-gpu.json --only-binary :all: \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    -r /mnt/c/_Source/optimus/spike/pre-m1-gpu-feasibility/requirements-gpu.txt'
```

Expected: `Successfully reported into /tmp/dry-run-gpu.json`, no install actually performed.

- [ ] **Step 2: Verify zero contamination matches**

```bash
wsl.exe -- bash -c 'python3 -c "
import json
report = json.load(open(\"/tmp/dry-run-gpu.json\"))
compromised = {
    (\"mistralai\", \"x\"),
    (\"guardrails-ai\", \"x\"),
    (\"lightning\", \"2.6.2\"),
    (\"lightning\", \"2.6.3\"),
}
hits = []
for pkg in report.get(\"install\", []):
    name = pkg[\"metadata\"][\"name\"]
    ver = pkg[\"metadata\"][\"version\"]
    if any(name == bad_name and (bad_ver == \"x\" or ver == bad_ver) for bad_name, bad_ver in compromised):
        hits.append(f\"{name}=={ver}\")
print(\"HITS:\", hits)
print(\"TOTAL PACKAGES:\", len(report.get(\"install\", [])))
"'
```

Expected: `HITS: []`, `TOTAL PACKAGES: ~101`.

If HITS is non-empty: STOP and escalate per `[[shai-hulud-pip-install-discipline]]`. Do not proceed to Task 6.

### Task 2: Write failing test for device autodetect helper

**Files:**
- Create: `spike/pre-m1-retrieval/tests/test_device_autodetect.py`

- [ ] **Step 1: Write the test**

The spike-1 server file is `server-stdio.py` (with hyphen) which isn't a valid Python module name for `import`. The existing test suite uses `importlib.util.spec_from_file_location` to load it (see `tests/test_two_stage_search.py` for the pattern). Mirror that.

```python
"""Verify the spike-1 server's device-autodetect helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "server_stdio",
    Path(__file__).resolve().parent.parent / "server-stdio.py",
)
server_stdio = importlib.util.module_from_spec(_spec)
sys.modules["server_stdio"] = server_stdio
_spec.loader.exec_module(server_stdio)


def test_select_device_returns_valid_string():
    """select_device returns 'cuda' or 'cpu', never None or anything else."""
    device = server_stdio.select_device()
    assert device in ("cuda", "cpu"), f"unexpected device: {device!r}"


def test_select_device_matches_torch_availability():
    """select_device returns 'cuda' iff torch reports CUDA available."""
    import torch

    expected = "cuda" if torch.cuda.is_available() else "cpu"
    assert server_stdio.select_device() == expected
```

- [ ] **Step 2: Verify the test fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python -m pytest tests/test_device_autodetect.py -v'
```

Expected: FAIL with `AttributeError: module 'server_stdio' has no attribute 'select_device'`.

### Task 3: Implement device autodetect in server-stdio.py

**Files:**
- Modify: `spike/pre-m1-retrieval/server-stdio.py` (add `select_device` helper near the top of the module, after the constants)

- [ ] **Step 1: Add the helper**

In `spike/pre-m1-retrieval/server-stdio.py`, add this function after the `DEFAULT_RERANK_BSIZE` constant (around line 40, before `confine_path`):

```python
def select_device() -> str:
    """Autodetect compute device. Returns 'cuda' if available, else 'cpu'.

    M1.0 production direction: GPU default with CPU fallback. Spike-1 close-out
    runs on GPU per `docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md`
    section 3; CPU path is retained but unexercised in the empirical runs.
    """
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"
```

- [ ] **Step 2: Log device + VRAM at server startup**

In `main()` (currently line 180), after `_ensure_models()`, add device logging:

```python
def main() -> None:
    """Stdio MCP server entrypoint. Spike-1 single-client, no transport auth."""
    from mcp.server.fastmcp import FastMCP

    index_dir = Path(os.environ.get(INDEX_DIR_ENV, Path.home() / ".optimus-spike" / "index"))
    target_root_env = os.environ.get(TEST_TARGET_ROOT_ENV)
    if target_root_env:
        target_root = Path(target_root_env).resolve()
    else:
        manifest, _, _ = load_index(index_dir)
        target_root = Path(manifest["target_root"]).resolve()

    log_path = index_dir / "server.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Warm caches at startup so the first tool call isn't a multi-second cold load
    _ensure_models()
    _ensure_index(index_dir)

    # Log device selection to stderr (stdout reserved for JSON-RPC frames)
    import torch
    device = select_device()
    vram_gb = (
        torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if device == "cuda"
        else 0.0
    )
    print(
        f"[spike-1 server] device={device} vram_total_gb={vram_gb:.2f}",
        file=sys.stderr,
    )

    app = FastMCP("optimus-spike-1")
    # ... rest unchanged
```

- [ ] **Step 3: Run test to verify it passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python -m pytest tests/test_device_autodetect.py -v'
```

Expected: PASS.

### Task 4: Apply the wrapper patch to two_stage_search

**Files:**
- Modify: `spike/pre-m1-retrieval/server-stdio.py:162-163` (the MaxSim matmul line)

- [ ] **Step 1: Apply the patch**

In `spike/pre-m1-retrieval/server-stdio.py`, replace the existing rerank loop (currently lines 161-166):

```python
    reranked = []
    for rec, d_emb in zip(candidate_records, d_emb_list):
        sim = q_colbert[0] @ d_emb.T
        score = float(sim.max(dim=-1).values.sum().item())
        reranked.append((rec, score))
    reranked.sort(key=lambda t: t[1], reverse=True)
```

With:

```python
    reranked = []
    for rec, d_emb in zip(candidate_records, d_emb_list):
        # GPU patch (probe-validated 2026-05-13, top-1 paths match CPU baseline):
        # colbert-ai 0.2.22's docFromText(keep_dims=False) returns per-doc tensors
        # on CPU, while q_colbert stays on GPU -- align device + dtype before matmul.
        # On CPU this .to() is a no-op (tensors already aligned).
        d_aligned = d_emb.to(device=q_colbert.device, dtype=q_colbert.dtype)
        sim = q_colbert[0] @ d_aligned.T
        score = float(sim.max(dim=-1).values.sum().item())
        reranked.append((rec, score))
    reranked.sort(key=lambda t: t[1], reverse=True)
```

- [ ] **Step 2: Run existing two-stage-search regression test in CPU venv (sanity)**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python -m pytest tests/test_two_stage_search.py -v'
```

Expected: PASS. On CPU, the `.to()` call is a no-op; behavior is byte-identical to pre-patch.

This is a sanity check BEFORE switching the venv to GPU. If this fails on CPU, the patch broke something unrelated to device; debug before moving on.

### Task 5: Switch requirements.txt to the GPU stack

**Files:**
- Modify: `spike/pre-m1-retrieval/requirements.txt`

- [ ] **Step 1: Replace requirements.txt content**

Open `spike/pre-m1-retrieval/requirements.txt` and replace the entire file with:

```
# Spike-1 GPU stack (post-2026-05-13 close-out per
# docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md Phase 0).
#
# Forked from spike/pre-m1-gpu-feasibility/requirements-gpu.txt which the
# 2026-05-13 GPU feasibility probe validated end-to-end (19x speedup on RTX
# A500 Laptop, top-1 paths match CPU baseline, ~1.47 GB VRAM peak).
#
# CUDA wheel choice: cu121 (forward-compatible with the host's 12.8 runtime per
# CUDA's enhanced compatibility for major version 12.x). Driver 573.44 (host) /
# 570.170 (WSL2) -- both well above the 525+ minimum cu121 wheels need.
#
# Why the explicit `+cu121` local version specifier:
#   `--extra-index-url` is a FALLBACK, so PyPI wins on higher versions. The
#   `+cu121` local tag is only published on the pytorch cu121 index, forcing
#   pip to fetch from there. Locked at torch 2.5.1 (the latest cu121 build
#   available for py3.12 as of 2026-05-13 -- torch 2.6.0+ shipped only as
#   cu124/cu126/cu128).
#
# Mini Shai-Hulud contamination check: dry-run with this set against the
# attack-window contamination list (mistralai, guardrails-ai, lightning
# 2.6.2/2.6.3) before installing. See [[shai-hulud-pip-install-discipline]].
--extra-index-url https://download.pytorch.org/whl/cu121

sentence-transformers>=2.5.0
colbert-ai>=0.2.20
# transformers 5.x breaks colbert-ai 0.2.22's HF_ColBERT (missing
# all_tied_weights_keys attribute introduced in transformers 5.x). Pin to
# 4.x; sentence-transformers accepts >=4.41.0,<6.0.0 so this is safe.
transformers>=4.41.0,<5
einops>=0.7.0
# Explicit +cu121 local tag forces resolution from the pytorch cu121 index.
torch==2.5.1+cu121
# Cap numpy to <3 (torch 2.5.x is built against numpy 2.x; numpy 3 not supported)
numpy>=1.26.0,<3
psutil>=5.9.0
pytest>=8.0.0
mcp>=1.0.0
```

- [ ] **Step 2: Confirm requirements.txt parses**

```bash
wsl.exe -- bash -c 'python3 -m pip install --dry-run --only-binary :all: \
  --extra-index-url https://download.pytorch.org/whl/cu121 \
  -r /mnt/c/_Source/optimus/spike/pre-m1-retrieval/requirements.txt 2>&1 | head -5'
```

Expected: pip resolves the set without errors. No install yet (dry-run).

### Task 6: Install persistent GPU venv

**Files:** none in optimus repo. Installs to WSL2 home.

- [ ] **Step 1: Create the persistent GPU venv**

```bash
wsl.exe -- bash -c 'python3 -m venv ~/optimus-spike-gpu-venv && \
  source ~/optimus-spike-gpu-venv/bin/activate && \
  python -m pip install --upgrade pip'
```

Expected: venv created at `~/optimus-spike-gpu-venv/`, pip upgraded to latest.

- [ ] **Step 2: Install the GPU stack into the venv**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && \
  python -m pip install --only-binary :all: \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    -r /mnt/c/_Source/optimus/spike/pre-m1-retrieval/requirements.txt'
```

Expected: ~5 GB install, completes without errors. `torch==2.5.1+cu121` resolved, 12 cu12 NVIDIA wheels installed, no PyPI-side cu13 leak.

- [ ] **Step 3: Verify GPU visibility**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && \
  python -c "import torch; print(f\"cuda={torch.cuda.is_available()} device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}\")"'
```

Expected output: `cuda=True device=NVIDIA RTX A500 Laptop GPU` (or your local GPU).

### Task 7: Regression test sweep on GPU venv

**Files:** none (test execution only).

- [ ] **Step 1: Run the full spike-1 test suite in the GPU venv**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python -m pytest tests/ -v'
```

Expected: 28+ tests pass (existing suite + new `test_device_autodetect.py`). Smoke tests (`test_smoke_index.py`, `test_two_stage_search.py`) now run on GPU.

If any non-smoke test fails, debug before proceeding -- the wrapper patch or device autodetect introduced a regression invisible on CPU venv.

If smoke tests fail with OOM or device-mismatch, escalate per brief section 2 trigger 2.

### Task 8: Phase 0 exit gate -- 3-query smoke vs probe baseline

**Files:** none (test execution only).

- [ ] **Step 1: Confirm an indexed test corpus exists for ms-core + ms-core-api**

The existing spike-1 work indexed `~/.spike-test-corpus-lite/` (ms-core + ms-core-api) at chunk_size=600. Verify it's present:

```bash
wsl.exe -- bash -c 'ls -la ~/.optimus-spike/index/ 2>&1 | head'
```

Expected: `manifest.json`, `chunks.jsonl`, `embeddings.npy` present. If missing, rebuild per spike-1 README "Build the index" section before continuing.

- [ ] **Step 2: Run the 3-query smoke against the ported server**

Create a tiny smoke runner if one doesn't exist. The probe used these queries:

| Query | Probe CPU latency | Probe GPU latency |
|---|---|---|
| "how does the build system run tests" | 12.41s | 0.83s |
| "http retry logic" | 10.65s | 0.47s |
| "kotlin coroutine cancellation" | 11.26s | 0.46s |

Run via direct pytest if a smoke script lacks, or via a stdio-MCP test client. The simplest path is to invoke `two_stage_search` directly:

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python -c "
import os, time
os.environ[\"OPTIMUS_SPIKE_INDEX_DIR\"] = str(os.path.expanduser(\"~/.optimus-spike/index\"))
os.environ[\"OPTIMUS_SPIKE_TARGET_ROOT\"] = os.path.expanduser(\"~/.spike-test-corpus-lite\")
import server_stdio
from pathlib import Path
index_dir = Path(os.environ[\"OPTIMUS_SPIKE_INDEX_DIR\"])
server_stdio._ensure_models()
server_stdio._ensure_index(index_dir)
queries = [
    \"how does the build system run tests\",
    \"http retry logic\",
    \"kotlin coroutine cancellation\",
]
for q in queries:
    t0 = time.perf_counter()
    results = server_stdio.two_stage_search(q, index_dir, top_k=5)
    elapsed = time.perf_counter() - t0
    top1 = results[0][\"file_path\"] if results else None
    print(f\"{elapsed:.2f}s top1={top1} query={q!r}\")
"'
```

Expected:
- Each query completes in < 2.0s (probe showed 0.46-0.83s; allow margin for warm/cold cache variance).
- Top-1 paths match what the probe RESULTS.md table records (see `spike/pre-m1-gpu-feasibility/RESULTS.md` "Headline result" section).

- [ ] **Step 3: Verify against probe RESULTS.md**

Open `spike/pre-m1-gpu-feasibility/RESULTS.md` and cross-check the top-1 path per query. If a path mismatches, do NOT proceed -- the port isn't behaviorally equivalent to the probe artifact. Escalate per brief section 2 trigger 2.

If latency exceeds 2s/query, ALSO escalate -- something regressed vs the probe.

### Task 9: Update spike-1 README with GPU stack notes + commit Phase 0

**Files:**
- Modify: `spike/pre-m1-retrieval/README.md` (replace the WSL2 setup section + add GPU stack section).

- [ ] **Step 1: Update the README's "WSL2 setup" section**

The current README references `~/optimus-spike-venv` (CPU venv). Replace with the GPU venv. In `spike/pre-m1-retrieval/README.md`, find the "### WSL2 setup (one-time)" section and replace it with:

```markdown
### WSL2 setup (one-time, GPU stack)

```bash
sudo apt install -y python3.12-venv build-essential
python3 -m venv ~/optimus-spike-gpu-venv
source ~/optimus-spike-gpu-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --only-binary :all: \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    -r /mnt/c/_Source/optimus/spike/pre-m1-retrieval/requirements.txt
```

After install, confirm GPU visibility:

```bash
python -c "import torch; print(f'cuda={torch.cuda.is_available()} device={torch.cuda.get_device_name(0)}')"
```

Expected: `cuda=True device=<your GPU>`.
```

Then find the "Build the index" and "Run the MCP server" sections and replace every `~/optimus-spike-venv` reference with `~/optimus-spike-gpu-venv`.

Add a new section at the top of "How to run" pointing at the GPU stack rationale:

```markdown
### GPU stack (post-close-out 2026-05-13)

The spike-1 server runs on GPU per `docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md` Phase 0. The wrapper patch (1-line `d_emb.to(device, dtype)` in MaxSim matmul) is validated against the probe's `spike/pre-m1-gpu-feasibility/server-stdio-gpu.py` artifact. Device autodetect via `server_stdio.select_device()`; CPU fallback retained but unexercised in the empirical runs.

requirements.txt switched to `torch==2.5.1+cu121` and the matching cu12 wheel stack. Persistent venv at `~/optimus-spike-gpu-venv/` is reused across all 24 Phase-2 empirical sessions.
```

- [ ] **Step 2: Stage Phase 0 changes**

```bash
git add spike/pre-m1-retrieval/server-stdio.py \
        spike/pre-m1-retrieval/requirements.txt \
        spike/pre-m1-retrieval/README.md \
        spike/pre-m1-retrieval/tests/test_device_autodetect.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): GPU port -- device autodetect + wrapper patch + cu121 stack

Phase 0 of spike-1 close-out per docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md.
Ports the probe-validated wrapper patch into spike-1's production server with
runtime device autodetect; switches requirements.txt to the GPU stack; updates
README install + run sections to reference the persistent GPU venv. Probe smoke
(3-query) matches probe RESULTS.md top-1 paths; latency < 2s/query.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: clean commit, working tree clean after.

---

## Phase 1 -- Prep (parallel-eligible internally)

Phase 1A and 1B/1C can run in parallel. 1B (task authoring) depends partly on 1A's dir-index detail level for the "most-touched areas" to be coherent, so prefer 1A first or interleaved.

### Task 10: Author DIRECTORY_INDEX.md at ms-superrepo root (Dustin)

**Files:**
- Create: `c:/ms-superrepo/DIRECTORY_INDEX.md` (outside optimus repo)

- [ ] **Step 1: Author the dir-index**

Dustin hand-authors `c:/ms-superrepo/DIRECTORY_INDEX.md`. Per design spec section 4 Phase 1A:

- Scope: top-2 levels of ms-superrepo with one-line summaries per directory.
- Selectively-deeper detail (3rd level + per-file notes) in 1-2 areas the 4 controlled tasks will exercise (the "most-touched areas").
- Format: Markdown, no schema lock (M2 templates land the schema later).
- Estimated 0.5-1 session of Dustin-time.

Example shape (placeholder structure, fill with real ms-superrepo content):

```markdown
# ms-superrepo -- Directory Index

Last hand-authored: 2026-05-13. Spike-1 H3 fixture.

## Top-level layout

| Path | One-line purpose |
|---|---|
| `ms-core/` | Core service: <one line>. |
| `ms-core-api/` | Public API surface for ms-core: <one line>. |
| `dockerLab/` | Container build artifacts (NOT INDEXED -- excluded from spike-1 corpus). |
| ... | ... |

## ms-core (deeper detail -- exercised by Task 2 + Task 4)

| Path | Purpose |
|---|---|
| `ms-core/src/main/kotlin/.../config/` | Config loading + validation. Tasks 2 reads this. |
| ... | ... |
```

- [ ] **Step 2: Verify dir-index file present**

```bash
ls -la c:/ms-superrepo/DIRECTORY_INDEX.md
```

Expected: file exists, non-empty.

### Task 11: Commit DIRECTORY_INDEX.md inside ms-superrepo's local clone

**Files:** none in optimus repo. Commit happens inside ms-superrepo.

- [ ] **Step 1: Commit inside ms-superrepo**

```bash
cd c:/ms-superrepo
git add DIRECTORY_INDEX.md
git commit -m "docs: add DIRECTORY_INDEX.md (spike-1 H3 fixture, hand-authored 2026-05-13)"
git -C c:/ms-superrepo log --oneline -1
```

Expected: commit recorded inside ms-superrepo. NO push (origin already removed per spike-2 protocol).

Verify no remote is configured:

```bash
git -C c:/ms-superrepo remote -v
```

Expected: empty output. If a remote exists, ABORT -- DIRECTORY_INDEX.md must not push upstream.

### Task 12: Draft the 4 controlled tasks (Dustin + Zolt)

**Files:**
- Create: `spike/pre-m1-retrieval/tasks.md` (controlled-task definitions for empirical runs)

- [ ] **Step 1: Dustin drafts 4 task prompts grounded in ms-superrepo**

Each task: prompt text + grounding (which ms-superrepo subsystems / files it touches) + Dustin-judgeable success criteria. Per spec section 4 Phase 1B table:

| # | Shape | Example |
|---|---|---|
| 1 | Navigational | "Where is the auth middleware for service X?" |
| 2 | Subsystem comprehension | "Explain how the X module's config gets loaded." |
| 3 | Cross-module trace | "Trace how a request flows from API entry to data layer for endpoint Y." |
| 4 | Pattern-find | "Find all places service X retries on failure; are they consistent?" |

Authoring rules:
- Each task rewards retrieval over broad sweeps. If answerable by reading 2-3 known files, redesign.
- ms-superrepo-grounded -- references real subsystems Dustin can verify against.
- Stable wording -- exact same prompt across all 6 sessions for that task (3 conditions × 2 runs).

- [ ] **Step 2: Save tasks.md**

Save to `spike/pre-m1-retrieval/tasks.md`. Format:

```markdown
# Spike-1 Controlled Tasks

**For empirical runs only.** Each task runs in 3 conditions × 2 runs = 6 Claude Code sessions.

## Task 1 -- Navigational

**Prompt (copy verbatim into each session):**

> <Dustin's draft>

**Grounding:** <which ms-superrepo paths>
**Success criteria:** <how Dustin will judge correctness>

## Task 2 -- Subsystem comprehension

<same shape>

## Task 3 -- Cross-module trace

<same shape>

## Task 4 -- Pattern-find

<same shape>
```

- [ ] **Step 3: Zolt review pass**

Zolt (or current Optimus agent) reads tasks.md and flags:
- Any task that doesn't reward retrieval (answerable trivially with 2-3 reads).
- Any task whose success criteria isn't Dustin-judgeable.
- Any duplication across the 4 task shapes.

Iterate until clean. This task exits when both Dustin and Zolt sign off on tasks.md.

### Task 13: Write failing tests for drift fixture

**Files:**
- Create: `spike/pre-m1-retrieval/tests/test_drift_fixture.py`

- [ ] **Step 1: Write the test file**

```python
"""Verify drift-fixture.py applies + reverses cleanly per task."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _load_drift_plans():
    """Import DRIFT_PLANS from the actual script under test."""
    spec_path = Path(__file__).resolve().parent.parent / "drift-fixture.py"
    spec = importlib.util.spec_from_file_location("drift_fixture", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DRIFT_PLANS


@pytest.fixture
def fake_target(tmp_path: Path) -> Path:
    """Build a fake test-target tree containing every directory DRIFT_PLANS expects.

    Reads DRIFT_PLANS from drift-fixture.py so the fixture stays in sync if the
    plans are edited (Task 14 Step 2 expects DRIFT_PLANS to be retargeted at the
    real ms-superrepo layout).

    Also git-inits + commits baseline so --reset (git-backed) works in tests.
    """
    plans = _load_drift_plans()
    # Materialize every rename source directory with one placeholder file.
    for task_n, plan in plans.items():
        rename_src = tmp_path / plan["rename"][0]
        rename_src.mkdir(parents=True, exist_ok=True)
        (rename_src / f"placeholder_{task_n}.kt").write_text(
            f"// placeholder for task {task_n}\n"
        )
    # git-init + commit baseline so --reset has somewhere to return to
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@spike"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "spike-test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "baseline"], cwd=tmp_path, check=True
    )
    return tmp_path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Invoke drift-fixture via the same interpreter pytest is running under."""
    env = os.environ.copy()
    env["DRIFT_TARGET_ROOT"] = str(cwd)
    return subprocess.run(
        [sys.executable, "drift-fixture.py", *args],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _snapshot(target_root: Path) -> set[str]:
    """Set of tree paths relative to target_root, excluding .git/ internals."""
    return {
        str(p.relative_to(target_root))
        for p in target_root.rglob("*")
        if ".git" not in p.relative_to(target_root).parts
    }


def test_apply_task1_adds_file_and_renames_dir(fake_target):
    """--task 1 adds one file + renames one directory."""
    before = _snapshot(fake_target)
    result = _run(["--task", "1"], fake_target)
    assert result.returncode == 0, result.stderr
    after = _snapshot(fake_target)
    # State changed: at least one path differs from before.
    assert after != before, f"task 1 produced no observable change"


def test_reset_returns_target_to_pristine(fake_target):
    """--reset reverses the apply cleanly (git status --porcelain empty after reset)."""
    snapshot_before = _snapshot(fake_target)
    _run(["--task", "1"], fake_target)
    _run(["--reset"], fake_target)
    snapshot_after = _snapshot(fake_target)
    assert snapshot_before == snapshot_after, (
        f"reset did not restore tree: differs at {snapshot_before ^ snapshot_after}"
    )
    # Also confirm git sees a clean working tree
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=fake_target,
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout.strip() == "", f"git not clean after reset: {status.stdout!r}"


def test_apply_is_idempotent(fake_target):
    """Re-applying the same task is a no-op (or graceful skip)."""
    _run(["--task", "1"], fake_target)
    snapshot1 = _snapshot(fake_target)
    result2 = _run(["--task", "1"], fake_target)
    snapshot2 = _snapshot(fake_target)
    assert snapshot1 == snapshot2, "second apply changed state"
    # returncode 0 (idempotent success) or non-zero with a clear "already applied" message
    if result2.returncode != 0:
        msg = (result2.stderr + result2.stdout).lower()
        assert "already" in msg, f"non-zero exit without 'already' message: {msg}"


def test_all_four_tasks_have_drift_content(fake_target):
    """Tasks 1-4 each define a non-empty drift action."""
    for task_n in (1, 2, 3, 4):
        # reset first to be safe
        _run(["--reset"], fake_target)
        before = _snapshot(fake_target)
        result = _run(["--task", str(task_n)], fake_target)
        assert result.returncode == 0, f"task {task_n}: {result.stderr}"
        after = _snapshot(fake_target)
        assert before != after, f"task {task_n} produced no drift"
```

- [ ] **Step 2: Verify the test fails**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python -m pytest tests/test_drift_fixture.py -v'
```

Expected: all 4 tests FAIL with `FileNotFoundError` or similar (drift-fixture.py does not exist yet).

### Task 14: Implement drift-fixture.py

**Files:**
- Create: `spike/pre-m1-retrieval/drift-fixture.py`

- [ ] **Step 1: Write the script**

```python
"""Per-task drift fixture for spike-1 H3 (drifted dir-index resilience).

Applies a task-specific filesystem mutation (1 file added, 1 directory renamed)
to the test target. Manual invocation by spike runner at the drift moment per
docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md section 4 Phase 1C.

CLI:
    python drift-fixture.py --task <1|2|3|4>   # apply drift for task N
    python drift-fixture.py --reset            # revert all drift

Reset is git-backed (the script runs `git checkout -- .` + `git clean -fd` inside
the target root, which reverses both the renamed dir and the added file).

Target root resolution:
    1. env var DRIFT_TARGET_ROOT (used by tests)
    2. default: c:/ms-superrepo
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


# Per-task drift plans. Each task: ONE add (file path relative to target_root)
# + ONE rename (oldpath -> newpath). Update these path templates to match the
# real ms-superrepo layout that the 4 controlled tasks exercise.
#
# IMPORTANT: the added file must land in a directory the DIRECTORY_INDEX.md
# lists, and the renamed directory must be one the dir-index references. That's
# the realistic-drift simulation the brief specifies.

DRIFT_PLANS = {
    1: {
        "add": "ms-core/config/drift_added_1.kt",
        "rename": ("ms-core/config", "ms-core/config_renamed_1"),
    },
    2: {
        "add": "ms-core-api/routes/drift_added_2.kt",
        "rename": ("ms-core-api/routes", "ms-core-api/routes_renamed_2"),
    },
    3: {
        "add": "ms-core/services/drift_added_3.kt",
        "rename": ("ms-core/services", "ms-core/services_renamed_3"),
    },
    4: {
        "add": "ms-core-api/handlers/drift_added_4.kt",
        "rename": ("ms-core-api/handlers", "ms-core-api/handlers_renamed_4"),
    },
}


def resolve_target_root() -> Path:
    """Pick target root from env or fall back to c:/ms-superrepo."""
    env = os.environ.get("DRIFT_TARGET_ROOT")
    if env:
        return Path(env).resolve()
    return Path("c:/ms-superrepo").resolve()


def is_git_repo(path: Path) -> bool:
    """True if `path` is a git working tree."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def apply_drift(task_n: int, target_root: Path) -> int:
    """Apply task N's drift to target_root. Returns 0 on success."""
    plan = DRIFT_PLANS.get(task_n)
    if plan is None:
        print(f"error: unknown task {task_n}; valid: 1-4", file=sys.stderr)
        return 2

    add_path = target_root / plan["add"]
    rename_from = target_root / plan["rename"][0]
    rename_to = target_root / plan["rename"][1]

    # Idempotency check: if both already drifted, exit 0 with notice.
    if add_path.exists() and rename_to.exists() and not rename_from.exists():
        print(f"task {task_n} drift already applied (idempotent skip)", file=sys.stderr)
        return 0

    # Sanity: source dir must exist before rename
    if not rename_from.exists():
        print(
            f"error: rename source {rename_from} does not exist. Reset first or "
            f"check DRIFT_PLANS matches the real target layout.",
            file=sys.stderr,
        )
        return 3

    # Apply
    add_path.parent.mkdir(parents=True, exist_ok=True)
    add_path.write_text(
        f"// spike-1 drift fixture -- task {task_n}, added 2026-05-13\n"
    )
    rename_from.rename(rename_to)
    print(
        f"task {task_n}: added {plan['add']}, renamed {plan['rename'][0]} -> {plan['rename'][1]}",
        file=sys.stderr,
    )
    return 0


def reset_drift(target_root: Path) -> int:
    """Reset target_root to git HEAD + clean untracked. Returns 0 on success."""
    if not is_git_repo(target_root):
        print(
            f"error: {target_root} is not a git repo; cannot reset",
            file=sys.stderr,
        )
        return 4
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=target_root, check=True)
    subprocess.run(["git", "clean", "-fd"], cwd=target_root, check=True)
    print(f"reset {target_root} to HEAD + clean", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spike-1 H3 drift fixture")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--task", type=int, choices=[1, 2, 3, 4], help="apply drift for task N")
    g.add_argument("--reset", action="store_true", help="reset target root via git")
    args = parser.parse_args(argv)

    target_root = resolve_target_root()
    if not target_root.is_dir():
        print(f"error: target root {target_root} not found or not a directory", file=sys.stderr)
        return 1

    if args.reset:
        return reset_drift(target_root)
    return apply_drift(args.task, target_root)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Update DRIFT_PLANS to match ms-superrepo's real layout**

The path templates in `DRIFT_PLANS` are placeholders matched to common Kotlin-monorepo shapes. After Task 12 produces `tasks.md`, edit `DRIFT_PLANS` so each task's `add` directory and `rename` source are:
1. Real paths in ms-superrepo.
2. Listed in `c:/ms-superrepo/DIRECTORY_INDEX.md` from Task 10.
3. Relevant to that task's controlled prompt (the drift should be in an area the task actually navigates).

This edit makes the fixture realistic. Without it, the drift fires in places the agent never looks, which weakens H3 per spec section 4 Phase 1C.

- [ ] **Step 3: Run tests to verify drift fixture passes**

```bash
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  python -m pytest tests/test_drift_fixture.py -v'
```

Expected: all 4 tests PASS.

Note: the `test_apply_is_idempotent` test allows either returncode 0 OR a graceful "already applied" message. Verify the script's behavior matches one of those.

### Task 15: Manual smoke against real ms-superrepo

**Files:** none.

- [ ] **Step 1: Confirm ms-superrepo is at a clean baseline**

```bash
cd c:/ms-superrepo
git status
git log --oneline -1
```

Expected: working tree clean (DIRECTORY_INDEX.md committed in Task 11). Note the HEAD SHA -- we'll use it for reset verification.

- [ ] **Step 2: Apply task 1 drift, verify, reset, verify**

```bash
cd c:/_Source/optimus/spike/pre-m1-retrieval
python drift-fixture.py --task 1
cd c:/ms-superrepo
git status     # should show the renamed dir + new untracked file
ls -la ms-core/config_renamed_1/  # or whatever DRIFT_PLANS[1] specifies
ls -la ms-core/config 2>&1 || echo "good, original dir is gone"

cd c:/_Source/optimus/spike/pre-m1-retrieval
python drift-fixture.py --reset
cd c:/ms-superrepo
git status     # should be clean
ls -la ms-core/config/   # should be back
ls -la ms-core/config_renamed_1 2>&1 || echo "good, renamed dir is gone"
```

Expected: drift applies, git status reflects mutations, reset returns to clean state.

- [ ] **Step 3: Repeat for tasks 2, 3, 4**

Same loop. Quick spot-check that DRIFT_PLANS entries don't reference paths that don't exist in ms-superrepo. If a `rename` source path is missing, edit DRIFT_PLANS to a real path before continuing.

### Task 16: Commit Phase 1

- [ ] **Step 1: Stage Phase 1 artifacts**

```bash
git add spike/pre-m1-retrieval/drift-fixture.py \
        spike/pre-m1-retrieval/tasks.md \
        spike/pre-m1-retrieval/tests/test_drift_fixture.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): Phase 1 prep -- drift fixture + tasks.md + DIRECTORY_INDEX

Phase 1 of spike-1 close-out per docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md.
Per-task drift fixture with git-backed reset; 4 controlled-task definitions
authored against ms-superrepo; DIRECTORY_INDEX.md hand-authored and committed
inside ms-superrepo's local clone (origin removed; no upstream push).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 -- Empirical runs (24 Claude Code sessions, manual)

This phase is **operator-driven**, not subagent-driven. Dustin runs each session in Claude Code on the Windows host; the spike-1 server runs in WSL2 listening on stdio MCP. Each session loop produces one JSON artifact under `spike/pre-m1-retrieval/results/`.

**Bonus host-side observation (informal, per spec section 6.4):** Dustin watches fan / thermal / system-stability behavior throughout the 24 sessions from the Windows host side. Captured informally; if anomalies surface they go in the report's scope-boundary section. Not a primary deliverable, not a gate. A scratch note (e.g., `spike/pre-m1-retrieval/results/thermal-notes.md`, gitignored) is fine for capture.

### Task 17: Pre-Phase-2 verification -- chat-report field coverage

**Files:** none.

- [ ] **Step 1: Find a recent Claude Code session UUID**

```bash
ls -t ~/.claude/projects/C---Source-optimus/ | head -3
```

Expected: most-recent session JSONL files.

- [ ] **Step 2: Run chat-report on it and inspect output**

```bash
python tools/ai-chat-report/claudecode/chat-report.py <recent-session-uuid> \
    --shape locked \
    --format json \
    --out /tmp/chat-report-precheck/
```

Expected: JSON emitted to `/tmp/chat-report-precheck/`.

- [ ] **Step 3: Verify required fields are present**

Open the emitted JSON and confirm it has the H1/H2/H3 measurement fields:
- per-tool-class aggregate counts (`Read`, `Grep`, `Glob`, `optimus_*`)
- optimus-tool-call attribution
- per-Read informed-precision classification

If a field is missing, STOP and escalate per brief section 2 trigger 2 -- spike-1 cannot start Phase 2 without the toolkit's measurement surface.

### Task 18: Execute Task 1 sessions (6 Claude Code runs)

**Files (artifacts produced):**
- Create: `spike/pre-m1-retrieval/results/task1-baseline-run1.json` (+ `.md`)
- Create: `spike/pre-m1-retrieval/results/task1-baseline-run2.json`
- Create: `spike/pre-m1-retrieval/results/task1-accurate-run1.json`
- Create: `spike/pre-m1-retrieval/results/task1-accurate-run2.json`
- Create: `spike/pre-m1-retrieval/results/task1-drifted-run1.json`
- Create: `spike/pre-m1-retrieval/results/task1-drifted-run2.json`
- Plus matching `.server.jsonl` copies for the optimus-condition runs.

The 10-step per-session loop runs 6 times for Task 1. The same loop runs in Tasks 19-21 for Tasks 2, 3, 4.

**Per-session loop (run for EACH of the 6 sessions in this task block):**

- [ ] **Step 1: Reset ms-superrepo to baseline**

```bash
cd c:/ms-superrepo
git reset --hard HEAD
git clean -fd
git log --oneline -1   # should show Task 11's DIRECTORY_INDEX.md commit
```

- [ ] **Step 2: Configure per-condition fixtures**

CONDITION = baseline:
```bash
cd c:/ms-superrepo
mv DIRECTORY_INDEX.md DIRECTORY_INDEX.md.bak    # hide dir-index for baseline
# do NOT start the optimus server
# do NOT add .mcp.json entry for optimus
```

CONDITION = optimus-accurate:
```bash
cd c:/ms-superrepo
ls DIRECTORY_INDEX.md     # confirm present (no .bak rename)
# In a separate terminal, start the spike-1 server in WSL2:
wsl.exe -- bash -c 'source ~/optimus-spike-gpu-venv/bin/activate && \
  cd /mnt/c/_Source/optimus/spike/pre-m1-retrieval && \
  OPTIMUS_SPIKE_INDEX_DIR=~/.optimus-spike/index \
  OPTIMUS_SPIKE_TARGET_ROOT=/mnt/c/ms-superrepo \
  python server-stdio.py'
# Ensure c:/ms-superrepo/.mcp.json registers the optimus server (point at the WSL server stdio)
```

CONDITION = optimus-drifted:
Same as accurate (dir-index present, server running, .mcp.json wired) -- DO NOT pre-apply drift; drift fires mid-task.

- [ ] **Step 3: Open a fresh Claude Code session at c:/ms-superrepo**

```
cd c:/ms-superrepo
claude
```

The session JSONL lands at `~/.claude/projects/C---ms-superrepo/<session-uuid>.jsonl`.

- [ ] **Step 4: Paste the task prompt verbatim from spike/pre-m1-retrieval/tasks.md**

Use the EXACT prompt for Task 1, no modifications.

- [ ] **Step 5: If drifted condition: invoke drift fixture at drift moment**

Watch for the drift moment: after the agent's 3rd tool call OR 60 seconds elapsed, whichever first. In a side terminal:

```bash
cd c:/_Source/optimus/spike/pre-m1-retrieval
python drift-fixture.py --task 1
```

For baseline and accurate conditions, skip this step.

- [ ] **Step 6: Let the agent complete the task**

Wait until Claude Code finishes its response loop. Note the session UUID (visible in the prompt or via `ls -t ~/.claude/projects/C---ms-superrepo/`).

- [ ] **Step 7: Capture the session UUID + verify session JSONL exists**

```bash
ls -la ~/.claude/projects/C---ms-superrepo/<session-uuid>.jsonl
```

- [ ] **Step 8: Run chat-report against the session**

```bash
python tools/ai-chat-report/claudecode/chat-report.py <session-uuid> \
    --cwd c:/ms-superrepo \
    --shape locked \
    --format json \
    --out spike/pre-m1-retrieval/results/
```

Expected: JSON + Markdown emitted under `results/`.

- [ ] **Step 9: Rename the emitted artifact to spike-1 coordinates**

```bash
cd spike/pre-m1-retrieval/results/
# The toolkit names files by session UUID; rename to task<N>-<condition>-run<R>.json:
mv <session-uuid>.json task1-<condition>-run<R>.json
mv <session-uuid>.md   task1-<condition>-run<R>.md    # if .md was also produced
```

Use `<condition>` in {baseline, accurate, drifted} and `<R>` in {1, 2}.

- [ ] **Step 10: Copy server log (optimus-conditions only) and end session**

For optimus-accurate / optimus-drifted runs only:

```bash
wsl.exe -- bash -c 'cp ~/.optimus-spike/index/server.jsonl /mnt/c/_Source/optimus/spike/pre-m1-retrieval/results/task1-<condition>-run<R>.server.jsonl'
```

Then:
- If between RUNS of the same condition: leave the server running (warm cache acceptable).
- If between CONDITIONS: stop the spike-1 server cleanly (Ctrl-C in its terminal). Restart fresh for the next condition.
- For baseline condition: no server to stop.

For drifted condition runs: invoke `python drift-fixture.py --reset` BEFORE the next session's Step 1 reset (the next Step 1 git-reset will reverse drift too, but explicit reset is safer + faster).

**Repeat the 10-step loop until all 6 Task-1 sessions complete** (baseline x2, accurate x2, drifted x2).

- [ ] **Step 11: Sanity-check Task 1's 6 result JSONs**

```bash
ls -la spike/pre-m1-retrieval/results/task1-*.json | wc -l
```

Expected: 6.

For each: open the JSON and verify required fields present (per-tool-class aggregates, optimus-tool-call attribution, per-Read informed-precision). If any is missing, escalate per brief trigger 2.

### Task 19: Execute Task 2 sessions (6 Claude Code runs)

Same 10-step loop as Task 18, but with the Task 2 prompt from `tasks.md` and Task 2's drift plan. Substitute `task2` in artifact filenames.

- [ ] **Step 1: Execute the per-session loop 6 times for Task 2** (baseline x2, accurate x2, drifted x2). See Task 18 for the loop steps.

- [ ] **Step 2: Sanity-check Task 2's 6 result JSONs**

```bash
ls -la spike/pre-m1-retrieval/results/task2-*.json | wc -l
```

Expected: 6.

### Task 20: Execute Task 3 sessions (6 Claude Code runs)

Same 10-step loop, Task 3 prompt, Task 3 drift plan. Substitute `task3` in artifact filenames.

- [ ] **Step 1: Execute the per-session loop 6 times for Task 3**

- [ ] **Step 2: Sanity-check Task 3's 6 result JSONs**

```bash
ls -la spike/pre-m1-retrieval/results/task3-*.json | wc -l
```

Expected: 6.

### Task 21: Execute Task 4 sessions (6 Claude Code runs)

Same 10-step loop, Task 4 prompt, Task 4 drift plan. Substitute `task4` in artifact filenames.

- [ ] **Step 1: Execute the per-session loop 6 times for Task 4**

- [ ] **Step 2: Sanity-check Task 4's 6 result JSONs**

```bash
ls -la spike/pre-m1-retrieval/results/task4-*.json | wc -l
```

Expected: 6.

### Task 22: Phase-2 close sanity check

- [ ] **Step 1: Verify all 24 result JSONs exist with required fields**

```bash
ls -la spike/pre-m1-retrieval/results/task*-*.json | wc -l
```

Expected: 24.

- [ ] **Step 2: Document warm-vs-cold protocol actually used**

Track in a scratch note for Phase 3: which conditions ran warm-cache (server left running between runs) vs cold-cache. This goes in the report's scope-boundary section.

- [ ] **Step 3: Document any LLM stochasticity refinements**

If you expanded any condition to 3+ runs per LLM stochasticity (per brief authority), note which task / condition / extra run count and why. Goes in the report.

No commit here -- the results/ tree is gitignored. Artifacts land in the final single commit at Task 27.

---

## Phase 3 -- Report + cold-reviewer

### Task 23: Author docs/spikes/spike-1-retrieval-report.md

**Files:**
- Create: `docs/spikes/spike-1-retrieval-report.md`

- [ ] **Step 1: Read spike-2's report as the template**

```bash
cat docs/spikes/spike-2-singleton-report.md | head -80
```

Note the section structure: executive verdict table, per-hypothesis evidence, sources, scope boundary, cross-references, recommendation.

- [ ] **Step 2: Author the report**

Use this skeleton (fill with real evidence from `results/`):

```markdown
# Spike-1 -- Retrieval Behavior Validation -- Report

**Status:** [PASS / PARTIAL / FAIL] -- cold-reviewer POSITIVE [date].
**Spike workspace:** `spike/pre-m1-retrieval/`
**Test target:** `c:/ms-superrepo/` (Kotlin monorepo, origin removed per spike-2 protocol)
**Compute:** GPU (NVIDIA RTX A500 Laptop, cu121 wheel via `optimus-spike-gpu-venv`)
**Session count:** 24 (4 tasks x 3 conditions x 2 runs)

## Executive Verdict

| Hypothesis | Verdict | Confidence | One-line rationale |
|---|---|---|---|
| H1 (behavior change) | [PASS/FAIL/PARTIAL] | [high/medium/low] | <one line> |
| H2 (no memory gap) | [PASS/FAIL/PARTIAL] | [high/medium/low] | <one line> |
| H3 (drift resilience) | [PASS/FAIL/PARTIAL] | [high/medium/low] | <one line> |

## H1 -- Behavior Change

### Per-task results

[Tables: optimus tool-call ratio (sum(optimus_*) / sum(broad_sweep)) per condition,
per run, with min/median/max across the 2 runs.]

### Evidence

[Cite specific JSON artifacts: results/task1-baseline-run1.json,
results/task1-accurate-run1.json, etc. Quote field values verbatim where load-bearing.]

### Verdict rationale

[Why PASS or FAIL or PARTIAL. Direction-consistency check across runs.
Reference to success-metric.md Component A >= 1.0x floor.]

## H2 -- No Memory Gap

[Qualitative analysis of task-failure patterns in the 24 sessions.
Look for "agent forgot X across sessions" patterns; document confidence level.]

## H3 -- Drift Resilience

### Per-task results

[Tables: ratio under drifted-dir-index condition vs no-dir-index baseline.
PASS criterion: drifted is NOT materially worse than no-dir-index.]

### Evidence

[Cite drifted-condition JSONs and the matching baseline-condition JSONs.]

### Downstream consequence

[If H3 PASS: optimus_doctor stays default-on with config-driven opt-out (current).
If H3 FAIL: optimus_doctor becomes mandatory CI integration; M2 scope expands.]

## Scope boundaries -- what this spike did NOT measure

- Concurrent multi-client load (spike-2's territory)
- Large-target indexing (ms-superrepo subset only)
- Sustained-load thermal behavior (Dustin's host-side informal observation captured below)
- Cross-IDE comparability (spike-1 is Claude Code only; Cursor variant lands at M6)
- spaCy on/off (H4 retired, locked DROP per spacy-keep-drop.md)

### Bonus host-side observation

[Dustin's notes on fan / thermal / stability throughout 24 sessions. If nothing
notable: "no anomalies observed; system remained stable throughout".]

## N=4 override + LLM stochasticity refinements

- N=4 explicit override of brief section 2 trigger 1 (PM authority, design spec section 6.2).
- Stochasticity refinements (if any): [list expanded run counts].
- Warm-vs-cold protocol actually used: [from Task 22 step 2].

## Cross-references

- Spec: `docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md`
- Brief: `docs/spikes/spike-1-prep-brief.md`
- Hypothesis framing: `docs/decomp/pre-M1-spikes.md`
- Locked retrieval stack: `docs/decisions/secure-singleton-mcp-baseline.md`
- Wrapper revision: `docs/decisions/colbert-wrapper-revision.md`
- GPU probe results: `spike/pre-m1-gpu-feasibility/RESULTS.md`
- Spike-2 template: `docs/spikes/spike-2-singleton-report.md`

## Recommendation -- inputs to M1.0

[What M1.0 inherits from this spike for ARCHITECTURE.md:
- Wrapper patch confirmed-correct as production code
- GPU production-default validated under empirical agent-driven query load
- optimus_doctor scope per H3 verdict
- Any unexpected findings.]
```

- [ ] **Step 3: Fill every section with real data from results/**

This is the load-bearing authoring step. For each H1/H2/H3 section: open each cited JSON, compute the ratios, write the rationale, cite the artifact paths inline.

### Task 24: Pre-dispatch checklist (cold-reviewer prep)

**Files:** none (review-only).

- [ ] **Step 1: Re-grep every file:line citation in the report against live files**

For every `path:line` reference in the report, run a grep to confirm the line still contains what the report says it does. Update line numbers if the file has changed.

- [ ] **Step 2: Re-read every results/ JSON cited; verify field values match prose**

For every "ratio X.Yx" / "Z tool calls" / specific quote in the report, open the JSON and confirm the value is exactly as quoted.

- [ ] **Step 3: Re-check decision-record section numbers**

For every reference to `docs/decisions/<record>.md` section X.Y or similar, open the file and confirm the section number is still correct.

- [ ] **Step 4: Pre-fix anything found**

Inline. No re-review pass needed after fixing.

### Task 25: Dispatch cold-reviewer subagent

**Files:** none (subagent dispatch).

- [ ] **Step 1: Dispatch a fresh subagent (Explore or general-purpose, zero context)**

Use the Agent tool. Subagent prompt:

```
You are a cold reviewer for the spike-1 close-out report at
docs/spikes/spike-1-retrieval-report.md. You have NO prior context on this work.

Your job: ruthless filesystem-grounded check of every claim in the report.

For every:
- file:line citation -- open the file, confirm the line matches.
- JSON quote (ratio, count, path) -- open spike/pre-m1-retrieval/results/<artifact>
  and confirm the value matches verbatim.
- Decision-record section reference -- open docs/decisions/<record> and confirm
  section numbers are accurate.
- Gate-logic claim (e.g., "H3 PASS means optimus_doctor stays opt-in") --
  cross-check against docs/decomp/pre-M1-spikes.md gate logic.
- Verdict claim ("PASS / FAIL / PARTIAL") -- confirm the cited evidence supports it.

Output verdict: POSITIVE, PARTIAL, or NEGATIVE.

POSITIVE = report ready to commit.
PARTIAL = list specific issues; revise + re-dispatch.
NEGATIVE = report has fundamental problems; don't commit.

Report findings in under 1000 words.
```

- [ ] **Step 2: Read the subagent's verdict**

If POSITIVE: proceed to Task 26 (commit).
If PARTIAL: fix the cited issues + re-dispatch this task. Loop until POSITIVE.
If NEGATIVE: STOP. Escalate to Dustin.

### Task 26: Iterate if PARTIAL

**Files:** `docs/spikes/spike-1-retrieval-report.md` (revise as needed).

- [ ] **Step 1: For each PARTIAL finding, fix inline + verify**

- [ ] **Step 2: Re-dispatch Task 25**

Continue until POSITIVE.

---

## Phase 4 -- Single commit + memory bump

### Task 27: Single commit covering all spike-1 deliverables

**Files (staged):**
- `spike/pre-m1-retrieval/` modifications (drift fixture, tasks.md, test file). Note: results/ is gitignored.
- `docs/spikes/spike-1-retrieval-report.md`
- README.md update (next step).

- [ ] **Step 1: Append "Phase 2 empirical results" section to spike-1 README**

GPU install / venv / run-section updates already landed in Task 9. Now add a new section at the bottom of `spike/pre-m1-retrieval/README.md`:

```markdown
## Phase 2 empirical results (2026-05-13)

24 Claude Code sessions on `c:/ms-superrepo/` (4 controlled tasks x 3 conditions x 2 runs, N=4 explicit override of brief's 2x trigger). Hypothesis verdicts and full evidence in:

- **Report:** `docs/spikes/spike-1-retrieval-report.md` (cold-reviewer POSITIVE)
- **Per-session artifacts:** `spike/pre-m1-retrieval/results/` (gitignored)
- **Controlled-task definitions:** `spike/pre-m1-retrieval/tasks.md`
- **Drift fixture:** `spike/pre-m1-retrieval/drift-fixture.py`

The H1/H2/H3 outcomes feed M1.0 ARCHITECTURE.md authoring as Phase 1.0 input per `docs/decomp/M1-tasks.md`.
```

- [ ] **Step 2: Confirm working tree state**

```bash
git status
```

Expected: all Phase-0/Phase-1 commits already landed. Phase 3's new artifacts pending: `docs/spikes/spike-1-retrieval-report.md`, README updates.

- [ ] **Step 3: Stage + commit**

```bash
git add docs/spikes/spike-1-retrieval-report.md \
        spike/pre-m1-retrieval/README.md
```

```bash
git commit -m "$(cat <<'EOF'
spike(pre-m1-retrieval): COMPLETE -- H1/H2/H3 verdicts + 24-session empirical artifacts

Closes spike-1 per docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md.
24 Claude Code sessions on ms-superrepo (4 tasks x 3 conditions x 2 runs, N=4
override of brief 2x trigger). Cold-reviewer POSITIVE.

Hypothesis verdicts:
- H1 [PASS/FAIL/PARTIAL]: <one-liner>
- H2 [PASS/FAIL/PARTIAL]: <one-liner>
- H3 [PASS/FAIL/PARTIAL]: <one-liner>

M1.0 unblocked for ARCHITECTURE.md authoring; wrapper patch validated under
empirical agent-driven load on GPU; <H3-downstream-line>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Fill `<PASS/FAIL/PARTIAL>` and `<one-liner>` placeholders with the real verdicts. Fill `<H3-downstream-line>` with the M2 scope statement (opt-in stays / opt-out removed).

### Task 28: Memory bump

**Files:**
- Modify: `C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/optimus-kickoff-state.md`
- Modify: `C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/MEMORY.md`

- [ ] **Step 1: Read current optimus-kickoff-state.md**

```bash
cat "C:/Users/dwaling/.claude/projects/C---Source-optimus/memory/optimus-kickoff-state.md"
```

- [ ] **Step 2: Update the memory entry with spike-1 outcome**

Edit the description and body to reflect:
- Spike-1 COMPLETE with H1/H2/H3 verdicts
- Cold-reviewer POSITIVE
- M1.0 ARCHITECTURE.md authoring unblocked
- Any downstream M2 scope adjustments per H3 verdict

- [ ] **Step 3: Update MEMORY.md index entry**

Replace the kickoff-state line with a one-liner reflecting spike-1 close. Keep < 150 chars.

- [ ] **Step 4: (Optional) Add new memory file if surprises surfaced**

If the spike surfaced any non-obvious finding worth persisting (e.g., a wrapper subtlety, a chat-report toolkit field oddity, a thermal observation), create a new memory file per `[[memory-write-protocol]]`. Skip if nothing surprised.

---

## Sizing summary

| Phase | Estimated Optimus-side sessions | Notes |
|---|---|---|
| Phase 0 (Server port) | 0.5-1 | Tasks 1-9 |
| Phase 1 (Prep) | 1-1.5 | Tasks 10-16. Dir-index authoring is Dustin's half-session. |
| Phase 2 (Empirical runs) | 0 Optimus, ~6-12 Dustin-hours in Claude Code | Tasks 17-22. 24 sessions, manual, parallel-ineligible. |
| Phase 3 (Report + cold-reviewer) | 1-1.5 | Tasks 23-26 |
| Phase 4 (Commit + memory) | 0.25 | Tasks 27-28 |

Total Optimus-side: ~3-4 sessions. Dustin's parallel cost: ~6-12 hours of manual Claude Code session driving (one-shot per session).

Escalation triggers from brief section 2 trigger 2 remain active throughout. The N=4 override is documented in spec section 6.2 + Phase 2 above + Task 27 commit message.

---

## Cross-references

- Approved spec: `docs/superpowers/specs/2026-05-13-spike-1-closeout-design.md`
- Source brief: `docs/spikes/spike-1-prep-brief.md`
- Hypothesis framing + gate logic: `docs/decomp/pre-M1-spikes.md`
- Locked retrieval stack: `docs/decisions/secure-singleton-mcp-baseline.md`
- Wrapper revision history: `docs/decisions/colbert-wrapper-revision.md`
- Probe results (port source): `spike/pre-m1-gpu-feasibility/RESULTS.md`
- Spike-2 report template: `docs/spikes/spike-2-singleton-report.md`
- Success metric (>= 1.0x floor): `docs/decisions/success-metric.md`
- Chat-report toolkit contract: `docs/decisions/chat-report-sibling-charter.md`
- Memory: `[[shai-hulud-pip-install-discipline]]`, `[[gpu-probe-side-mission]]`, `[[optimus-kickoff-state]]`
