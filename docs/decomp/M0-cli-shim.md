# M0 -- CLI Shim Bootstrap

**Status:** Decided -- locked.
**Owner:** M0 host-side install workstream; per-IDE installer (M4) is the downstream consumer.

## Why this record exists

The `optimus` CLI binary must be on PATH from M0 onward so subcommands documented as M1.5 (chat-report integration) are actually invokable as host-shell commands, not deferred to M4.1.3b. Earlier drafts framed this as a clean stub with the language still in question (Bash + PowerShell pair vs Go). That framing is retired -- the calls below are locked.

The CLI shim is a **first-party** optimus-v2 deliverable, not an external-tool dependency. It does NOT live under `tools/` (which is reserved for SHA-pinned external submodules per CHARTER Founding Decision 9). It lives at its own top-level path, `cli-shim/`. The binary-distribution discipline that FD9 mandates for external-tool binaries applies here equally -- pre-built per OS, companion manifest, end-user never compiles.

## Locked design calls

### 1. Language: Go

Single static binary per OS, no runtime dependencies. Rationale:

- Single static binary per OS, no runtime deps; fast startup (~5ms).
- Excellent cross-compile from any host via `GOOS` + `GOARCH`.
- Aligns with CHARTER Founding Decision 9's "ship pre-built binaries per OS" rule.
- Already in the stack via garp (`tools/garp/` is Go).
- Mature CLI tooling ecosystem (cobra, urfave/cli).

The previous Bash + PowerShell pair is rejected: two parallel script sets, environment-dependent PowerShell behavior, and a raw-script attack surface the compiled binary eliminates.

### 2. Source + binary layout: `cli-shim/` top-level

- **Source:** `cli-shim/src/` (Go source).
- **Pre-built binaries:** `cli-shim/bin/<os-arch>/optimus[.exe]` where `<os-arch>` is one of `linux-amd64`, `linux-arm64`, `darwin-amd64`, `darwin-arm64`, `windows-amd64`. Use `.exe` suffix on Windows.
- **Companion manifest:** `cli-shim/bin/<os-arch>/optimus.manifest.json` per binary. Records:

  ```json
  {
    "source_sha": "<git commit SHA when binary was built>",
    "go_version": "<exact Go toolchain version>",
    "built_at": "<ISO timestamp>",
    "build_env": "<CI runner identifier or 'maintainer-local'>"
  }
  ```

  CI checks that `source_sha` matches the optimus-v2 commit SHA on each rebuild.

### 3. Distribution discipline (mirrors CHARTER Founding Decision 9)

First-party tool, NOT vendored from an external repo -- but the binary-distribution discipline matches FD9's external-tool rule:

- Pre-built binary per supported OS-arch, committed at a deterministic path.
- Companion `*.manifest.json` adjacent to each binary with source-SHA traceability.
- End-user install never requires Go, git, or any compile step.

The only axis on which first-party differs from external-tool is **source location**: external sources live at `tools/<external-tool>/` as SHA-pinned submodules; first-party sources live at their own first-party path (here, `cli-shim/src/`). Binary-distribution discipline is unified across both.

See CHARTER Founding Decision 9 for the unified convention.

### 4. Per-OS support targets

Five binaries total. CI cross-compiles all five from the same source tree:

- `linux-amd64`
- `linux-arm64` (ARM Linux hosts, including some WSL2 setups)
- `darwin-amd64` (Intel Macs -- declining but still real)
- `darwin-arm64` (Apple Silicon -- default for new Macs)
- `windows-amd64`

`linux-arm64` and `darwin-amd64` are forward/legacy coverage. If a strong reason to drop either surfaces during M0 implementation, that is a future decision; for this record, all five are locked.

### 5. Maintainer / CI workflow

1. Change to `cli-shim/src/` via PR.
2. CI cross-compiles all five binaries on merge to main (or release branch).
3. CI commits (or release-time-generates) the binaries at `cli-shim/bin/<os-arch>/optimus[.exe]` plus their `optimus.manifest.json` companions.
4. CI check: each manifest's `source_sha` matches the commit SHA at build time.

This mirrors CHARTER Founding Decision 9's pattern for external-tool binaries; the only difference is that no submodule SHA bump is involved (the source lives in-tree).

### 6. Installer responsibility

The installer (`optimus_doctor` plus per-IDE installers, M4) selects the correct binary for the user's OS and architecture from `cli-shim/bin/<os-arch>/` and places it on PATH. **End-user never needs Go or any build toolchain.** The installer is the consumer of the pre-built binaries; the CLI shim's source location and build workflow are invisible to end users.

## Subcommand surface

Illustrative, not exhaustive. Specific subcommand surface is decided per-milestone as underlying tools land:

- `optimus init` (M2) -- MCP-tool mirror; scaffolds standards artifacts.
- `optimus doctor` (M0+) -- MCP-tool mirror; drift detection plus host-side install state self-check.
- `optimus chat-report` (M1.5) -- host-side; dispatches to `tools/ai-chat-report/`.
- Container lifecycle commands (start / stop / status) -- host-side.
- `optimus list` / `optimus delete` -- MCP-tool mirrors; forward to container's MCP scratch ops.
- `optimus update-bundles` (M4+) -- host-side; per CHARTER Founding Decision 8 / TR-19.

Subcommand dispatch is hyphen-separated per TR-20 (e.g., `optimus update-bundles`, not `optimus update_bundles`).

## Install path

- **Linux / WSL2:** `~/.local/bin/optimus` (no sudo required; assume `~/.local/bin` on PATH).
- **macOS:** `~/.local/bin/optimus` (same convention; macOS is v2.1+ per TR-09, but the install path is named here for forward compatibility).
- **Windows native:** `%USERPROFILE%\bin\optimus.exe` (or `%LOCALAPPDATA%\Programs\optimus\optimus.exe`).

The installer is responsible for ensuring the chosen path is on PATH for the user's shell environment.

## Cross-references

- **CHARTER Founding Decision 9** -- External-tool vendoring + first-party-tool binary-distribution discipline (unified convention).
- **`docs/decomp/M0-repo-layout.md`** -- Repo skeleton including `cli-shim/` top-level.
- **M4 installer work** (`docs/decomp/M4-tasks.md`, populated at milestone-load time) -- the installer is the consumer that selects and places the right per-OS-arch binary on PATH.
- **`docs/decisions/chat-report-sibling-charter.md`** -- the sibling toolkit the `optimus chat-report` subcommand dispatches to.
- **TR-20** -- CLI entry point + conventions.

## Status note

Locked at refactor time. Language is Go; layout is `cli-shim/src/` (source) plus `cli-shim/bin/<os-arch>/optimus[.exe]` (per-OS-arch binaries with companion manifests); five OS-arch targets are pinned; the installer is the consumer that puts the right binary on PATH. The binary-distribution discipline matches CHARTER Founding Decision 9's external-tool rule -- source location varies (first-party vs `tools/<external>/`), binary-distribution discipline is unified.
