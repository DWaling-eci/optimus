---
expansion-status: filled
filled-by: founding-pass
filled-at: 2026-05-12
---

# M0 -- Foundation Skeleton (Task Decomposition)

**Status:** clean stub. Bodies fill in when M0 work begins.
**Founding-doc reference:** roadmap Milestone 0 outcomes + DoD (`docs/plans/TDD-ROADMAP.md`).
**Source:** v1 Phase 0.1/0.2 task seeds + active M0 DoD incorporated inline below.

## Phase 0.1 -- Repo Skeleton + Git Hygiene

Lock these tasks at M0 kickoff. The detailed three-deployment-surface tree (container / IDE bundles / host-singleton runtime) lives in `docs/decomp/M0-repo-layout.md`; this section captures the commit-level task shape.

- Default branch name: **trunk** (name explicitly at `git init`).
- Initialize repo and commit founding docs:
  - Files: `CHARTER.md`, `AGENTS.md`, `ARCHITECTURE.md` (stub -- "to be populated by M1.0 Architecture Spike"), `CHANGELOG.md` (stub, first entry: "v2 restart"), `VERSION` (0.0.1), `.gitignore`, `README.md` (stub). **Spike reports are NOT bundled into this commit** -- they land in separate pre-M0 commits when spike-1 and spike-2 actually run, at `docs/spikes/spike-1-retrieval-report.md` and `docs/spikes/spike-2-singleton-report.md` (date-less semantic names; the `docs/spikes/` directory is skeleton-marked in `docs/decomp/M0-repo-layout.md`).
  - Commit shape: `chore: v2 restart -- charter, AGENTS, stub docs`.
- Create directory skeleton per `docs/decomp/M0-repo-layout.md` (no module files yet; `src/optimus/__init__.py` minimal with `__version__ = "0.0.1"`; `bundlers/`, `installers/`, `container/`, `templates/` start empty with `.gitkeep`).
  - Commit shape: `chore: create directory skeleton`.
- `.gitignore` rules (minimum set; the canonical list lives in `docs/decomp/M0-repo-layout.md`): `body-files/`, `.cursor/local/`, `.claude/local/`, `.optimus/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `dist/`, `*.egg-info/`, plus `doc/for-review/` and decomp working drafts.
- Submodule strategy for v1 reference checkout (v1 github repo: `https://github.com/eci-rhc/optimus.git`).

## Phase 0.2 -- CI Pipeline (Lint + Stub Tests)

Detailed CI task list lives in `docs/decomp/M0-ci-pipeline.md` (TR-07 / TR-08 mapping + salvaged Phase 0.2 task seeds). Headline shape:

- Python linter (ruff or equivalent).
- Test stub runner (pytest).
- Coverage reporting (TR-08 floor: >=80% per module under `src/optimus/`).
- ASCII / em-dash check in CI.
- `pyproject.toml` with dev extras (pytest, ruff); commit shape `chore: add pyproject + dev tooling`.
- `.github/workflows/ci.yml` running install + ruff + pytest; commit shape `ci: add lint+test workflow`.
- Stub Docker image build job (`image/Dockerfile` on `python:3.10-slim` copying `src/` with `CMD echo "stub"`; `image/requirements.txt` empty at M0; CI runs `docker build`, no push); commit shape `ci: add Docker image build`.

## Phase 0.3 -- CLI Shim Bootstrap

The `optimus` binary needs to be on PATH from M0 onward so that `optimus chat-report` (Phase 1.5) and downstream subcommands are invokable from the host shell as documented, not deferred to M4.1.3b.

- Install a minimal `optimus` shell-script shim to the user's PATH (`~/.local/bin/optimus` or equivalent).
- Shim dispatches subcommands; only `optimus chat-report` is wired at M0.
- Full subcommand registry expands at M4.1.3b when the host-side installer matures.
- Detail in `docs/decomp/M0-cli-shim.md`.

## Phase 0.4 -- In-Container Debug Loop

Junior-developer debug experience for code that runs inside the singleton container:

- Add `debugpy` entrypoint to the container on a Unix-domain-socket target (per `docs/decomp/M0-debug-loop.md`). NO TCP port; `network_mode: "none"` is preserved.
- Document attach configuration for Cursor and Claude Code (and VSCode, since it works for free).
- Make the debug entrypoint optional (default off, opt-in via env var) so production runs aren't affected.
- Detail in `docs/decomp/M0-debug-loop.md`.

## Definition of Done

Mirrors the M0 DoD in `docs/plans/TDD-ROADMAP.md` (Milestone 0 section); verify intact post-refactor.

- Repo has the three-deployment-surface layout from CHARTER Founding Decision 1; provisional manifests in `docs/decomp/M0-repo-layout.md`.
- Default branch named `trunk` (explicit at `git init`).
- CI pipeline (GitHub Actions) runs lint + tests on every push (see `docs/decomp/M0-ci-pipeline.md`).
- Docker image builds successfully (with stub server).
- `optimus` CLI shim installed and on PATH (`docs/decomp/M0-cli-shim.md`); dispatches at minimum `optimus chat-report`; full subcommand registry expands at M4.
- In-container debug loop documented (`docs/decomp/M0-debug-loop.md`); debugpy entrypoint conditional on env var; attach configs for Cursor and Claude Code.
- Charter, AGENTS, ARCHITECTURE stub, REQUIREMENTS, CHANGELOG, VERSION committed.
- **No `src/optimus/` package implementation yet** -- just `__init__.py` stub. Module list is decided in M1.0, not M0.

## Sequencing notes

- Phases 0.1 and 0.2 are sequential (repo skeleton before CI).
- Phases 0.3 and 0.4 can run in parallel with 0.2.
- M0 must close before M1 (Pre-M1 spikes are a hard gate that runs *before* M0 per `docs/plans/TDD-ROADMAP.md`).