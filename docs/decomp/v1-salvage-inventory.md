# v1 Salvage Inventory

**Status:** clean stub. The principle ("v1 is salvage source, not authority") lives in AGENTS.md. The file-by-file inventory transplants here at refactor time.

**Source:** v1 Salvage section of the active `CHARTER.md`, with the file-by-file table salvaged from the pre-reframe charter and filtered against the active project spec (CHARTER + REQUIREMENTS + TDD-ROADMAP).

**External-tool vendoring convention:** all external-tool dependencies (garp, chat-report, future tools) carry into v2 as SHA-pinned git submodules at `tools/<external-tool>/`, with pre-built artifacts at the relevant deployment-source paths plus companion manifests for traceability. End-users never need a build toolchain. Full convention in CHARTER Founding Decision 9.

## Salvageable items

| Component | Source in v1 | v2 Disposition |
|-----------|-------------|----------------|
| MCP server engine (retrieval portions) | `image/optimus_server.py` | Salvage retrieval portions only; drop memory portions; final module list set by the M1.0 Architecture Spike (CHARTER Decision 2). |
| Hook scripts (retained set) | `cursor/hooks/` | Port `search-redirect`, `shell-guard`, `read-guard`, `agent-scratch`. Source lives at `src/{hooks,...}/` in v2 (CHARTER Decision 1), not inside `src/optimus/`. |
| Agent definitions | `.cursor/agents/` | Carry forward; review for memory-protocol references and strip. |
| Tooling Quality Gate rule | `.cursor/rules/` | Carry forward into `src/rules/`. |
| Test suite (retrieval) | `tests/` | Carry forward retrieval tests; drop memory/parser/prune/extract tests. |
| garp proximity search tool | `image/tools/garp-json/` | Source moves to `tools/garp/` as a SHA-pinned git submodule (per CHARTER Founding Decision 9). Linux binary pre-built from the submodule SHA and committed at `container/vendor/garp-json` (with companion `container/vendor/garp-json.manifest.json` for traceability). The Docker image COPYs the pre-built binary -- no `git clone`, no `go build` at image-build time. See TR-10. |
| Cross-encoder reranker | `image/optimus_server.py` | **Superseded.** v2's reranker stack is locked: Nomic CodeRankEmbed (dense retrieval) + ColBERTv2 via colbert-ai direct (late-interaction rerank; wrapper revised 2026-05-13 per `docs/decisions/colbert-wrapper-revision.md`), per `docs/decisions/secure-singleton-mcp-baseline.md`. The dual-CE-vs-single-CE question is retired; the late-interaction architecture replaces it. No salvage from v1's CE wrapper code beyond reference value. |
| spaCy pipeline | `image/optimus_server.py` | **NOT SALVAGED** -- DROPPED per `docs/decisions/spacy-keep-drop.md` (locked 2026-05-13, research-backed verdict). v2 has no `spacy` dependency at runtime, build time, or install time. |
| ML model cache | `~/.optimus/model-cache/` | Already user-global; lands under host-singleton runtime per CHARTER Decision 1. **Installer-populated, container-mounted read-only**; container NEVER downloads models -- see `docs/decisions/secure-singleton-mcp-baseline.md` section 6. |
| Premortem/dogfood artifacts | `.cursor/docs/` | Historical record; copy to `docs/v1-archive/`. |
| chat-report toolkit (Cursor variant source) | `ref-projects/optimus/tools/chat-report.py` (origin); salvage already completed at upstream `https://github.com/dtwaling/ai-chat-report.git` (`cursor/` directory) | v2 consumes the salvaged toolkit via the `tools/ai-chat-report/` submodule per CHARTER Founding Decision 9 (per `docs/decisions/chat-report-sibling-charter.md`). Runs host-side, no compile step. The fresh salvage pass is done at the upstream level; v2 only pins the ref. |

## Anti-salvage (do NOT carry over)

- **v1 memory feature in its entirety.** No memory files, hooks, `optimus_prune`, `optimus_extract`, parser, or memory format invariant. Killed per CHARTER Founding Decision 3.
- **v1 hooks-as-container-modules placement.** v2 splits IDE-side artifacts (hooks, agents, skills, rules) out of `src/optimus/` into `src/{hooks,agents,skills,rules}/` so they ship to IDE bundles, NOT into the container, per CHARTER Decision 1.
- **Scattered `.cursor/` vs `.claude/` anti-pattern.** v2 authors IDE-agnostic source and adapts per-IDE at bundle time (CHARTER Decision 6).
- **AGENTS.md mutation pattern from v1 PR #37.** v2 treats AGENTS.md as a user-maintained host-project artifact, not optimus-managed.
- **Manual / unpinned garp clone (and in-Dockerfile `go build`).** v2 pins the garp source as a SHA-pinned submodule at `tools/garp/` and ships a pre-built Linux binary at `container/vendor/garp-json` (with a companion manifest); the Dockerfile COPYs the pre-built binary -- no `git clone`, no `go build` at image-build time. See CHARTER Founding Decision 9 and TR-10.
- **Any PowerShell 5 workarounds** confirmed unnecessary by the Pre-M1 validation spikes (CHARTER Decision 5).
- **`~/.optimus/memory/`, `~/.optimus/{agents,skills,hooks}/`,** and the per-project `.optimus/docker-compose.yml` location. The container is host-singleton in v2 (CHARTER Decision 7); IDE artifacts ship via per-IDE bundles (CHARTER Decision 6).
