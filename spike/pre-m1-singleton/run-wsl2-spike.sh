#!/usr/bin/env bash
# Orchestrator for the WSL2 leg of spike-2.
#
# Invoke from WSL2:
#   cd /mnt/c/_Source/optimus/spike/pre-m1-singleton
#   ./run-wsl2-spike.sh                 # default: run H1 probe
#   ./run-wsl2-spike.sh h1              # H1: multi-client transport
#   ./run-wsl2-spike.sh h2              # H2: concurrent grep correctness
#   ./run-wsl2-spike.sh cap              # concurrency cap probe (low cap)
#   ./run-wsl2-spike.sh discovery       # discovery + stale-cleanup probe
#   ./run-wsl2-spike.sh all              # H1, H2, cap, discovery in sequence
#
# Or from Windows PowerShell:
#   wsl bash -c "cd /mnt/c/_Source/optimus/spike/pre-m1-singleton && ./run-wsl2-spike.sh all"

set -euo pipefail

cd "$(dirname "$0")"

HYPOTHESIS="${1:-h1}"

# Ensure ~/.optimus exists for the bind mount.
mkdir -p "${HOME}/.optimus"

# The cap probe wants a deliberately low cap so 4 clients trigger busy_retry.
if [[ "${HYPOTHESIS}" == "cap" ]]; then
    export OPTIMUS_CONCURRENCY_CAP=2
fi

export HOST_UID="$(id -u)"
export HOST_GID="$(id -g)"

# Pre-stage a WSL2-native test corpus from ms-superrepo. Bind-mounting Windows
# paths into a WSL2 container via 9P translation is dramatically slower than
# WSL2-native filesystem access (the spike found this empirically -- the
# rglob walk on /mnt/c/ms-superrepo blocks the server's event loop for 10+
# seconds per call, causing client timeouts even on narrow file globs). This
# is a load-bearing finding for production optimus: WSL2-native parent mounts
# should be the recommended deployment shape, NOT Windows-path-via-9P.
CORPUS_DIR="${HOME}/.spike-test-corpus"
SOURCE_DIR="${SOURCE_DIR:-/mnt/c/ms-superrepo}"
if [[ ! -d "${CORPUS_DIR}" ]]; then
    echo "[run-wsl2-spike] pre-staging WSL2-native corpus from ${SOURCE_DIR}..."
    mkdir -p "${CORPUS_DIR}"
    # Copy a representative subset: top-level docs/configs + 2 sub-projects.
    # This keeps corpus size bounded while exercising recursive grep paths.
    for f in AGENTS.md MEMORY.md README.md; do
        [[ -f "${SOURCE_DIR}/$f" ]] && cp "${SOURCE_DIR}/$f" "${CORPUS_DIR}/" || true
    done
    for d in dockerLab ms-core ms-core-api; do
        [[ -d "${SOURCE_DIR}/$d" ]] && cp -r "${SOURCE_DIR}/$d" "${CORPUS_DIR}/" || true
    done
    echo "[run-wsl2-spike] corpus staged: $(du -sh "${CORPUS_DIR}" | cut -f1)"
fi
export MS_SUPERREPO="${CORPUS_DIR}"

cleanup() {
    echo "[run-wsl2-spike] tearing down container..."
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    # Stale-socket cleanup: server's normal shutdown removes it; this is a
    # safety net.
    rm -f "${HOME}/.optimus/optimus.sock"
}
trap cleanup EXIT

echo "[run-wsl2-spike] starting container (hypothesis=${HYPOTHESIS}, cap=${OPTIMUS_CONCURRENCY_CAP:-4})..."
docker compose up -d --build >/dev/null

# Wait for the socket to appear, up to 5 seconds.
SOCKET_PATH="${HOME}/.optimus/optimus.sock"
for _ in $(seq 1 50); do
    if [[ -S "${SOCKET_PATH}" ]]; then
        break
    fi
    sleep 0.1
done
if [[ ! -S "${SOCKET_PATH}" ]]; then
    echo "[run-wsl2-spike] FAIL: socket did not appear at ${SOCKET_PATH} within 5s" >&2
    docker compose logs --tail=20 >&2
    exit 1
fi

ls -l "${SOCKET_PATH}"

run_probe() {
    local hyp="$1"
    echo ""
    echo "=== probe-wsl2.py hypothesis=${hyp} ==="
    python3 probe-wsl2.py --hypothesis "${hyp}" || echo "[run-wsl2-spike] probe-wsl2 exited non-zero for ${hyp}"
}

run_discovery() {
    echo ""
    echo "=== probe-discovery.py ==="
    python3 probe-discovery.py --transport wsl2 --socket "${SOCKET_PATH}" || echo "[run-wsl2-spike] probe-discovery exited non-zero"
}

case "${HYPOTHESIS}" in
    h1) run_probe h1 ;;
    h2) run_probe h2 ;;
    cap) run_probe cap ;;
    discovery) run_discovery ;;
    all)
        run_probe h1
        run_probe h2
        # Cap probe needs a restart with a different concurrency cap to actually
        # exercise the busy_retry path with only 4 clients.
        echo ""
        echo "[run-wsl2-spike] restarting container with cap=2 for cap-probe..."
        docker compose down --remove-orphans >/dev/null
        OPTIMUS_CONCURRENCY_CAP=2 docker compose up -d --build >/dev/null
        for _ in $(seq 1 50); do
            [[ -S "${SOCKET_PATH}" ]] && break
            sleep 0.1
        done
        run_probe cap
        run_discovery
        ;;
    *)
        echo "Unknown hypothesis: ${HYPOTHESIS}" >&2
        exit 2
        ;;
esac

echo ""
echo "[run-wsl2-spike] done. Results in ./results/"
