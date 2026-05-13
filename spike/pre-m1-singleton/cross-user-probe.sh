#!/usr/bin/env bash
# Cross-user SO_PEERCRED rejection probe for the WSL2 leg of spike-2.
#
# Validates docs/decisions/transport-and-discovery.md section 4 (process-credential
# auth) by attempting a connection from a UID different from the singleton owner's
# UID. Expected outcome: the server reads SO_PEERCRED, sees the UID mismatch, and
# writes an `auth_rejected` error before any request frame is accepted.
#
# Layered defense (defense-in-depth) per transport-and-discovery.md sections 2 + 4:
#   - Defense 1: socket mode 0600 -- different UID hits OS-level EACCES on open()
#     before SO_PEERCRED runs at all.
#   - Defense 2: SO_PEERCRED UID compare -- runs only if defense 1 is bypassed.
# This wrapper temporarily relaxes defense 1 (chmod 0666 -> 0600 cleanup) so the
# probe actually exercises defense 2 empirically. TEST-ONLY escape hatch; production
# posture is mode 0600 + SO_PEERCRED both active.
#
# Cross-user actor: an ephemeral python:3.12-slim docker container running with
# --user ${CROSS_USER_UID}:${CROSS_USER_GID} (default 65534:65534 = nobody). Docker
# provides the UID isolation; no host sudo / sudoers config required. SO_PEERCRED
# in WSL2 reports the host-namespace UID across the bind-mounted unix socket, so
# the server sees uid=65534 != server uid (1000) and rejects.
#
# Prereqs:
#   - WSL2 server (server-wsl2.py via compose.yml) is UP and listening at
#     ${SOCKET_PATH:-~/.optimus/optimus.sock}.
#   - docker available to the WSL2 user.
#
# Invoke from WSL2:
#   cd /mnt/c/_Source/optimus/spike/pre-m1-singleton
#   ./cross-user-probe.sh
#
# Or via the orchestrator:
#   ./run-wsl2-spike.sh cross-user

set -euo pipefail

cd "$(dirname "$0")"

SOCKET_PATH="${OPTIMUS_SOCKET_PATH:-${HOME}/.optimus/optimus.sock}"
SOCKET_DIR="$(dirname "${SOCKET_PATH}")"
SOCKET_NAME="$(basename "${SOCKET_PATH}")"
CROSS_USER_UID="${CROSS_USER_UID:-65534}"
CROSS_USER_GID="${CROSS_USER_GID:-65534}"
RESULTS_DIR="$(pwd)/results"
TMP_RESULTS_DIR="/tmp/spike-cross-user-results"
PROBE_IMAGE="${PROBE_IMAGE:-python:3.12-slim}"

# --- Preflight ---------------------------------------------------------------

if [[ ! -S "${SOCKET_PATH}" ]]; then
    echo "[cross-user-probe] FAIL: socket not present at ${SOCKET_PATH}" >&2
    echo "[cross-user-probe]   bring the WSL2 server up first (./run-wsl2-spike.sh h1 or docker compose up -d)" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "[cross-user-probe] FAIL: docker is required (the cross-user actor runs in an ephemeral container)" >&2
    exit 1
fi

SERVER_UID="$(stat -c '%u' "${SOCKET_PATH}")"
SELF_UID="$(id -u)"
if [[ "${CROSS_USER_UID}" == "${SERVER_UID}" ]]; then
    echo "[cross-user-probe] FAIL: CROSS_USER_UID=${CROSS_USER_UID} matches server UID; cannot test cross-user rejection" >&2
    exit 1
fi

# Probe needs to write its results JSON; UID 65534 can't write to RESULTS_DIR
# (owned by spike user). Stage to /tmp (world-writable) then move into RESULTS_DIR.
mkdir -p "${RESULTS_DIR}"
rm -rf "${TMP_RESULTS_DIR}"
mkdir -p "${TMP_RESULTS_DIR}"
chmod 0777 "${TMP_RESULTS_DIR}"

# --- Defense-1 relax + cleanup trap ------------------------------------------

ORIGINAL_MODE="$(stat -c '%a' "${SOCKET_PATH}")"
echo "[cross-user-probe] socket mode before: ${ORIGINAL_MODE} (defense 1: file-permission)"
echo "[cross-user-probe] server UID: ${SERVER_UID}, probe will run as: UID ${CROSS_USER_UID} (in container), self UID: ${SELF_UID}"

restore_mode() {
    if [[ -S "${SOCKET_PATH}" ]]; then
        chmod "${ORIGINAL_MODE:-600}" "${SOCKET_PATH}" || true
        echo "[cross-user-probe] socket mode restored to ${ORIGINAL_MODE:-600}"
    fi
}
trap restore_mode EXIT

chmod 0666 "${SOCKET_PATH}"
echo "[cross-user-probe] socket mode relaxed to 0666 (defense 1 bypassed for test); SO_PEERCRED is the only remaining gate"

# --- Run the probe inside an ephemeral container as a different UID ----------
#
# Bind mounts:
#   - spike dir (read-only): /spike  -- probe-wsl2.py and friends
#   - socket dir:            /var/optimus/sockets  -- the unix socket itself
#   - tmp results dir:       /results -- world-writable, the probe writes its JSON here
#
# Network: --network none keeps the container offline (matches singleton policy).
#
# Note: WSL2 SO_PEERCRED across docker-bind-mount returns the host-namespace UID
# of the in-container process. With --user 65534:65534 + Docker default (no
# user-namespace remapping), that's UID 65534 on the host -- a true cross-user
# condition from the server's perspective.

set +e
docker run --rm \
    --network none \
    --user "${CROSS_USER_UID}:${CROSS_USER_GID}" \
    -v "$(pwd):/spike:ro" \
    -v "${SOCKET_DIR}:/var/optimus/sockets" \
    -v "${TMP_RESULTS_DIR}:/results" \
    -w /spike \
    "${PROBE_IMAGE}" \
    python3 probe-wsl2.py \
        --hypothesis cross-user \
        --clients 1 \
        --socket "/var/optimus/sockets/${SOCKET_NAME}" \
        --results-dir /results
PROBE_EXIT="$?"
set -e

# --- Move artifact into RESULTS_DIR ------------------------------------------

shopt -s nullglob
for f in "${TMP_RESULTS_DIR}"/probe-wsl2-cross-user-*.json; do
    cp "$f" "${RESULTS_DIR}/"
    echo "[cross-user-probe] artifact: ${RESULTS_DIR}/$(basename "$f")"
done
shopt -u nullglob

if [[ "${PROBE_EXIT}" -eq 0 ]]; then
    echo "[cross-user-probe] PASS: SO_PEERCRED defense path verified empirically (cross-UID connection rejected)"
else
    echo "[cross-user-probe] FAIL: probe exited ${PROBE_EXIT}; inspect the artifact for details" >&2
    exit "${PROBE_EXIT}"
fi
