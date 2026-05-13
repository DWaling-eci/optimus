# M0 -- Repo Root Layout (Detailed Manifest)

**Status:** clean stub. The three-surface principle lives in CHARTER Founding Decision 1. The exact directory tree below is implementation-level detail that fills in at M0 work time.

**Founding-doc reference:** CHARTER Founding Decision 1 ("three deployment surfaces: container, IDE bundles, host-singleton runtime").

## Container surface (`src/optimus/`)

The Python MCP server package. Ships into the singleton Docker container, never to a host project or IDE.

```
src/
  (server.py, config.py, garp_shell.py, retrieval/, mcp/, transport.py, concurrency.py, etc.)
  optimus/          -- Python package (scope-driven, NOT a 1:1 lift of v1's 18 modules)
    __init__.py
    server.py       -- thin MCP entrypoint (<=100 lines per TR-01)
    config.py       -- env-var config
    transport.py    -- MCP transport (multi-client; see Decision 7)
    garp_shell.py   -- garp proximity search wrapper
    retrieval/      -- search, grep, resolve (and any helpers retained after spike)
    standards/      -- optimus_init, optimus_doctor, dir-index drift detection
    filesystem_ops/ -- optimus_list, optimus_delete (safe ops)
```

## IDE bundles surface (`src/{hooks,agents,skills,rules}/`)

Sibling directories at the repo root (NOT inside `src/optimus/`). These are IDE-agnostic source artifacts that the M4/M5 bundlers package per-IDE.

```
src/
  agents/         -- agent definitions (IDE-agnostic source)
  hooks/          -- IDE-agnostic Node.js ESM hook source
  skills/         -- skill definitions (IDE-agnostic source)
  rules/          -- rule definitions (IDE-agnostic source)
  {config files}  -- TBD: pending finding during IDE bundle R&D 
```

These are consumed by bundlers (M4 Cursor, M5 Claude Code) which transform them into per-IDE deployable artifacts.

## Host-singleton runtime surface (`~/.optimus/`)

User-profile directory written by the host-side installer once per machine. Holds runtime state for the singleton container.

```
~/.optimus/
  VERSION             -- INI: optimus_version=..., mcp_protocol_version=... (per TR-19)
  config.json         -- per-machine config (parent-mount path, concurrency cap, log level)
  docker-compose.yml  -- singleton container definition
  model-cache/        -- installer-populated ML model cache (per secure-singleton-mcp-baseline.md §6)
  telemetry/          -- tool-call ratio JSONL (build-time validation telemetry, EUR-10)
  installer-state/    -- per-IDE install records, version tracking
  templates/          -- versioned standards templates (read by optimus_init)
  optimus.sock        -- Unix socket (Linux/WSL2/macOS); see docs/decisions/transport-and-discovery.md. No pid-file; liveness via socket-aliveness probe.
```

## Repo root supporting directories

```
optimus/
  docs/
    plans/                  -- implementation plans
    decomp/                 -- per-milestone task decomposition (THIS FILE LIVES HERE)
    decisions/              -- canonical decision records (transport+discovery, success metric, etc.)
    requirements/           -- TR/EUR docs
    issues/                 -- gh issue body drafts
    conventions/            -- git / PR / issue conventions (docs/conventions/git-and-issues.md)
    spikes/                 -- pre-M1 spike reports (spike-1-retrieval-report.md,
                             spike-2-singleton-report.md); populated when spikes run 🔶
  bundlers/                 -- per-IDE bundle builders (populated M4) 🔶
  installers/               -- per-IDE installers (populated M4) 🔶
  cli-shim/                 -- first-party `optimus` CLI shim (Go). Per
                             CHARTER Founding Decision 9 (binary-distribution
                             discipline) and docs/decomp/M0-cli-shim.md. 🔶
    src/                    -- Go source for the CLI shim 🔶
    bin/<os-arch>/          -- pre-built binaries per supported OS-arch
                             (linux-amd64, linux-arm64, darwin-amd64,
                             darwin-arm64, windows-amd64) plus companion
                             optimus.manifest.json per binary 🔶
  container/                -- host-side container bootstrap (populated M1) 🔶
    vendor/                 -- pre-built binaries consumed by the Docker image build
                             (e.g., garp-json + garp-json.manifest.json). Per
                             CHARTER Founding Decision 9. 🔶
  templates/                -- standards templates (populated M2) 🔶
  tests/                    -- (populated when building begins)
  tools/                    -- external-tool git submodules, SHA-pinned
                             (e.g., tools/garp/, tools/ai-chat-report/). Per
                             CHARTER Founding Decision 9. 🔶
  body-files/               -- untracked; CLI --body-file inputs (per ThinkTank convention)
```

🔶 **Note**: Full skeleton visible from day 1 - Create and keep these directories from this point onward - for the flagged directories that will start empty use `.gitkeep`, then as each is populated during its respective milestones remove its `.gitkeep` file. `tools/` and `container/vendor/` follow the external-tool-vendoring convention (CHARTER Founding Decision 9): `tools/` holds SHA-pinned submodules for external-tool sources; `container/vendor/` holds the pre-built binaries that the Dockerfile COPYs into the image (each with a companion `*.manifest.json` for source-SHA traceability). `cli-shim/` is the first-party-tool analog -- source at `cli-shim/src/`, pre-built per-OS-arch binaries at `cli-shim/bin/<os-arch>/` with companion `optimus.manifest.json` each; same binary-distribution discipline as FD9 mandates for external tools (full record at `docs/decomp/M0-cli-shim.md`).

### **"Standard" Project Documents Observed by Optimus:**
📐 - *Enforced standards Artifacts (by M2)*
📏 - *Suggested Standards Artifacts (by M2)*
```markdown
 📏 AGENTS.md📏
 📏 CODING_STANDARDS_INDEX.md 📏 (if coding standards exist, dir where they live should be configurable)
 📐 DIRECTORY_INDEX.md📐 (stubbed and seeded by `optimus_init`)
 📐 ARCHITECTURE.md📐 (stub -- "to be populated by M1.0 Architecture Spike")
```

### **Documents in this project repo:**
(Some files will be created as development and testing progress.)

```markdown
 📄 AGENTS.md📏
 📄 CHARTER.md
 📄 `docs/plans/` TDD-ROADMAP.md
 📄 `docs/requirements/` REQUIREMENTS.md
 📄 `docs/` glossary.md
 📄 `docs/`telemetry-heuristic.md
 📄 .gitignore
 📄 README.md (stub)
 📄 DIRECTORY_INDEX.md📐 (stubbed and seeded by `optimus_init`)
 📄 ARCHITECTURE.md📐 (stub -- "to be populated by M1.0 Architecture Spike")
 📄 CHANGELOG.md (stub, first entry: "v2 restart")
 📄 VERSION (0.0.1)
```

### **`.gitignore` includes:**

```gitignore
body-files/
.cursor/local/
.claude/local/
.optimus/
__pycache__/
*.pyc
.pytest_cache/
dist/
*.egg-info/
```