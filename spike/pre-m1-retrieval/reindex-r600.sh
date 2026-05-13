#!/usr/bin/env bash
# One-off re-index launcher for the chunk_size=600 / bsize=32 protocol revision.
# Authored via Write tool to dodge the wsl.exe heredoc-quoting trap.
# Idempotent: re-running overwrites the same output dir (drops to indexer.py's
# behavior).
set -euo pipefail

CORPUS="${HOME}/.spike-test-corpus-lite"
OUT_DIR="${HOME}/.optimus-spike/index-msrepo-r600"
LOG="${HOME}/.optimus-spike/reindex-r600.log"
SCRIPT_DIR="/mnt/c/_Source/optimus/spike/pre-m1-retrieval"

source "${HOME}/optimus-spike-venv/bin/activate"
cd "${SCRIPT_DIR}"

mkdir -p "${HOME}/.optimus-spike"

# Background, detached, log everything
nohup python indexer.py "${CORPUS}" "${OUT_DIR}" > "${LOG}" 2>&1 &
PID=$!
disown

echo "PID=${PID}"
echo "LOG=${LOG}"
echo "OUT=${OUT_DIR}"
