#!/usr/bin/env bash
# Spike-1 install-probe wrap script -- WSL2 / Linux entrypoint.
#
# Why this exists:
#   colbert-ai's Checkpoint init JIT-compiles a C++ extension (segmented_maxsim_cpp)
#   at load time. On Windows this fails because the cpp source uses pthread.h
#   (POSIX-only) -- see run-probe.ps1's history for the full Windows attempt
#   chain. The spike was pivoted to WSL2 / Linux per the operator's call
#   2026-05-13 because (a) Linux has pthread natively, (b) the production
#   env shape is a Linux container regardless of host OS, so spike-1 should
#   validate against the env shape production will actually have.
#
# Usage (from any shell that can launch WSL2; assumes run from the spike workspace):
#   wsl.exe -- bash /mnt/c/_Source/optimus/spike/pre-m1-retrieval/run-probe.sh
#
# Or from inside a WSL2 shell:
#   bash /mnt/c/_Source/optimus/spike/pre-m1-retrieval/run-probe.sh
#
# Prerequisites:
#   - WSL2 with Ubuntu (24+ tested) and python3 + python3-venv installed:
#       sudo apt install -y python3.12-venv build-essential
#   - Spike WSL2 venv at ~/optimus-spike-venv/ (placed in $HOME native FS to
#     dodge the spike-2 9P perf cliff for /mnt/c/...). To create:
#       python3 -m venv ~/optimus-spike-venv
#       source ~/optimus-spike-venv/bin/activate
#       python -m pip install --only-binary :all: -r /mnt/c/_Source/optimus/spike/pre-m1-retrieval/requirements.txt

set -euo pipefail

# Spike workspace root -- expected to be /mnt/c/_Source/optimus/spike/pre-m1-retrieval/
# but resolve dynamically from the script's own location for portability.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_DIR="${OPTIMUS_SPIKE_VENV:-$HOME/optimus-spike-venv}"
VENV_PYTHON="$VENV_DIR/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: Spike venv python not found at $VENV_PYTHON" >&2
    echo "Create the venv first:" >&2
    echo "  python3 -m venv $VENV_DIR" >&2
    echo "  source $VENV_DIR/bin/activate" >&2
    echo "  python -m pip install --only-binary :all: -r $SCRIPT_DIR/requirements.txt" >&2
    exit 2
fi

PROBE="$SCRIPT_DIR/install_probe.py"
if [[ ! -f "$PROBE" ]]; then
    echo "ERROR: install_probe.py not found at $PROBE" >&2
    exit 2
fi

echo "[run-probe.sh] Venv: $VENV_DIR"
echo "[run-probe.sh] Python: $($VENV_PYTHON --version 2>&1)"
echo "[run-probe.sh] Probe: $PROBE"

# Activate the venv so its bin/ is on PATH -- needed because torch's
# cpp_extension.verify_ninja_availability() shells out to find `ninja` on
# PATH, and ninja is installed inside the venv (not system-wide). Activation
# is the supported way to make venv binaries discoverable to subprocesses.
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[run-probe.sh] Invoking probe..."
exec python "$PROBE"
