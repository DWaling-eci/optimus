# M2 -- Host-Project Artifacts (Detailed Manifest)

**Status:** clean stub. The principle ("host project gets standards artifacts, no install state") lives in CHARTER Founding Decision 1. The exact artifact manifest transplants here at refactor time.

**Source:** transplanted from CHARTER "What ships to the host project" section (current CHARTER Founding Decision 1 + Founding Decision 4 scaffold list).

## Artifacts written to a host project

Scaffolded by `optimus_init` (Founding Decision 4); maintained by the user (or `optimus_doctor` helper), not optimus-managed after scaffold:

- `.mcp.json` -- project-scoped MCP config, points at the host-singleton container (transport shape pinned in `docs/decisions/transport-and-discovery.md`).
- `ARCHITECTURE.md` -- living doc; CI-enforced via `optimus_doctor` (TR-15 applied to the host project).
- `DIRECTORY_INDEX.md` -- standards artifact; drift detection via `optimus_doctor`.
- `CODING_STANDARDS_INDEX.md` -- standards index template; drift detection via `optimus_doctor`.
- `AGENTS.md` -- agent-guidance template.

## What MUST NOT be written

- No `.optimus/` directory in the host project (v2 never creates that; container is host-singleton per Decision 7, per-project state is none).
- No install-state files.
- No per-machine config.
