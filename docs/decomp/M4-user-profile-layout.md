# M4 -- Host-Side User-Profile Layout (`~/.optimus/`)

**Status:** clean stub. The principle ("`~/.optimus/` holds runtime state for the singleton container") lives in CHARTER Founding Decision 1 + 7. Exact subdirectory manifest transplants here at refactor time.

**Source:** reconciled against the active CHARTER (Founding Decisions 1 + 7) and `docs/decisions/transport-and-discovery.md`.

## Layout

```
~/.optimus/
  VERSION              -- INI: optimus_version=..., mcp_protocol_version=... (per TR-19)
  config.json          -- container config: parent-mount path, concurrency cap, log level (Founding Decision 7)
  docker-compose.yml   -- singleton container definition (host-singleton per Founding Decision 7)
  templates/           -- versioned standards templates (read by optimus_init; Founding Decision 4)
  model-cache/         -- installer-populated ML model cache (Nomic CodeRankEmbed + ColBERTv2 via colbert-ai direct per secure-singleton-mcp-baseline.md + colbert-wrapper-revision.md). Container bind-mounts this RO at /root/.cache/huggingface. The container NEVER downloads models -- weights arrive here exclusively via the installer's SHA-verified download from the optimus repo's GitHub Releases.
  telemetry/           -- tool-call ratio JSONL
  installer-state/     -- per-IDE install records, version tracking (written by M4.1 installer + per-IDE installers). Includes models-manifest.json -- the cached record of the model manifest currently on disk; the installer compares this against the current release's manifest to decide smart-skip vs download+verify+replace.
  optimus.sock         -- Unix socket (Linux/WSL2/macOS; see docs/decisions/transport-and-discovery.md). No pid-file; liveness detected via socket-aliveness probe.
```

Notes vs v1:
- No `memory/` directory -- memory feature killed (Founding Decision 3).
- No `agents/`, `skills/`, or `hooks/` directories here -- those ship via per-IDE plugin bundles, not user-profile (Founding Decision 6).
- `docker-compose.yml` lives here (not in each host project) because the container is host-singleton in v2 (Founding Decision 7).
- `model-cache/` is installer-populated (NOT container-populated). The container is model-cache-decoupled at build time and bind-mounts the cache read-only at runtime; this is enforced by `network_mode: "none"` (TR-06) which makes runtime model fetches physically impossible.

## Installer writes

- Created once per machine by the host-side installer (M4.1).
- Owner: `0700` (user-only).
- `optimus.sock` is runtime artifact (created/cleaned by container lifecycle, NOT installer).
- `model-cache/` populated by the installer via SHA-verified download of model artifacts from the optimus repo's GitHub Releases. Smart-skip: installer compares the current release's `models-manifest.json` against the previously-cached manifest in `installer-state/models-manifest.json`; download only on mismatch. Full distribution + trust model in `docs/decisions/secure-singleton-mcp-baseline.md` section 6.
