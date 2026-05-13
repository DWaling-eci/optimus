# M0 -- CI Pipeline (Detailed Tasks)

**Status:** clean stub. The principle ("CI exists and gates merges before M1 work begins") lives in roadmap M0 outcomes. Detailed task list fills in at M0 work time.

**Source:** transplanted from TR-07 + roadmap M0 CI bullet. v1 TR-07/TR-08 + Phase 0.2 task seeds incorporated inline below.

Full Container and MCP Server example for baseline implementation is laid out in the [Secure Singleton MCP Baseline](../decisions/secure-singleton-mcp-baseline.md) document.

## TR-07 scope (from current `docs/requirements/REQUIREMENTS.md`)

The CI/CD pipeline MUST:

- Build the Docker image on every PR.
- Run the full test suite inside the container on every PR.
- Run a smoke test (start container, call `optimus_search`, assert response) on every PR.
- Run `optimus_doctor` against the optimus repo itself on every PR (dogfood the standards layer).
- Run the retrieval-quality eval (per TR-12 quality gate, M1 onward) on every PR once the eval corpus lands.
- Block merge on any test failure.
- Publish a versioned Docker image tag on trunk push.

## TR-08 coverage target (from current `docs/requirements/REQUIREMENTS.md`)

Per-module test coverage MUST be >=80% for all modules under `src/optimus/`. Tests MUST run inside the Docker container to catch dependency and env issues. (The v1-era >=90% prune-module target is removed; no prune module exists in v2.)

## Tasks

- Linter (ruff or equivalent)
- Test stub runner (pytest)
- Coverage reporting (target thresholds per TR-08 above)
- ASCII / em-dash check (per conventions defined by Dustin)
- Pre-commit hook setup
- CI job names + triggers + matrix (`ubuntu-latest`, `macos-latest`, `windows-latest`; WSL2 covered via unit-test simulation + spike-2 -- see "WSL2 coverage strategy" below)
- `optimus_doctor` self-check job (per TR-07; depends on M2 landing the tool -- stub job in M0, real check wired when M2 ships)
- Docker image publish-on-trunk job (per TR-07; image registry locked to **`ghcr.io/DWaling-eci/optimus:<tag>`** -- GitHub Container Registry. Owner placeholder until repo lands on GitHub).

### Task seeds (salvaged from v1 Phase 0.2, kept where still applicable to v2 M0)

- **`pyproject.toml` + ruff + pytest**
  - Files: `pyproject.toml` (minimal -- name, version, dev extras: pytest, ruff)
  - Commit shape: `chore: add pyproject + dev tooling`
- **GitHub Actions CI (lint + test job)**
  - File: `.github/workflows/ci.yml`
  - Job: install deps, ruff check, pytest (no tests at M0 close is fine; the wiring is what matters)
  - Commit shape: `ci: add lint+test workflow`
- **Docker image build job**
  - `image/Dockerfile` (stub: python:3.10-slim, copies `src/`, CMD echo "stub")
  - `image/requirements.txt` (empty at M0)
  - CI job: `docker build`, no push at M0 (publish wires up when TR-07 publish job lands)
  - Commit shape: `ci: add Docker image build`

## Runner matrix (M0)

M0 CI runs on the three GitHub-hosted runners that map to v2's primary supported platforms:

- **`ubuntu-latest`** -- Linux runner. Also carries WSL2-aware unit tests that simulate `/mnt/c/...`-style path patterns (see "WSL2 coverage strategy" below). WSL2 IS Linux for code-execution purposes; the WSL2-specific surface is path translation + Windows<->Linux interop, both unit-testable on a Linux runner.
- **`macos-latest`** -- macOS runner. (macOS is out of scope for v2 GA per TR-09, but the runner is cheap to keep green and catches Unix-portability regressions early; if the cost rises later it can be dropped without changing the platform-support story.)
- **`windows-latest`** -- Windows-native runner. Covers PowerShell 5.1 + 7.x shells and Windows-path semantics (per TR-09's Windows-native install target).

The five OS-arch shim binaries (per `docs/decomp/M0-cli-shim.md`) are cross-compiled from `ubuntu-latest` via `GOOS` + `GOARCH`. No per-OS-arch runner is needed just for shim builds; per-OS runners exist only for tests that need to execute on their native platform.

## WSL2 coverage strategy

M0 CI does NOT ship a WSL2 runner. WSL2 is covered via three complementary layers:

1. **WSL2-aware unit tests on `ubuntu-latest`.** WSL2 is Linux underneath, so code-execution-level behavior is already exercised by the Linux runner. The WSL2-specific surface (Windows<->Linux path translation, e.g. `C:\foo` <-> `/mnt/c/foo`) is unit-testable: tests simulate WSL2 path patterns and assert the code resolves them correctly. This runs on every PR.
2. **Spike-2 end-to-end validation on a real WSL2 dev machine.** Spike-2's probe matrix explicitly includes WSL2 (see `docs/decomp/pre-M1-spikes.md`, Spike-2). End-to-end WSL2 behavior -- singleton container under WSL2 networking, Unix-socket transport on WSL2's filesystem, multi-client probes from a WSL2-hosted client -- gets exercised there, not in M0 CI.
3. **Dev dogfooding + M6 dogfood pass.** WSL2 regressions in shipped code surface during developer dogfooding and the M6 dogfood milestone before reaching users.

### What gets caught where

| WSL2 concern | Caught by |
|---|---|
| Path translation logic (`/mnt/c/...` <-> `C:\...`) | Unit tests on `ubuntu-latest` (every PR) |
| Code that runs on WSL2 == code that runs on Linux | `ubuntu-latest` CI (every PR) |
| WSL2-specific kernel behavior, networking, mount semantics | Spike-2 end-to-end gate (Pre-M1) |
| WSL2 regressions in shipped code post-M1 | M6 dogfood + dev dogfooding + user reports |

### Why not a WSL2 runner

GitHub Actions doesn't ship WSL2 runners natively. Self-hosting adds infrastructure burden, maintenance, and a single point of failure for CI throughput. Container-based WSL2 simulation on a Windows runner looks like coverage but isn't (no real WSL2 kernel). For M0 the cost/value ratio doesn't justify it -- WSL2-specific bugs are predominantly integration-shaped, not unit-shaped, and the unit-shaped slice is already covered by `ubuntu-latest`.

### Trade-off (explicit)

WSL2 regressions that are NOT caught by the Linux runner surface at spike-2 / dogfood rather than at PR-time. This is acceptable because (a) WSL2 is Linux underneath, so most regressions ARE caught by Linux CI, and (b) the WSL2-specific surface is small and integration-shaped. Spike-2 is the named end-to-end gate; if spike-2 reveals the WSL2 integration surface is larger or more fragile than assumed, this trade-off gets revisited (and a self-hosted WSL2 runner becomes a real option).
