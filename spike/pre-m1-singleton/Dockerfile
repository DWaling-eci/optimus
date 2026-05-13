# Minimal spike-2 container for the WSL2 Unix-socket transport.
#
# NOT a production optimus container. The spike validates the transport +
# concurrency + auth contract from docs/decisions/transport-and-discovery.md,
# not the full secure-singleton-mcp-baseline stack (Nomic, ColBERTv2, etc.).

FROM python:3.12-slim

# Non-root user so the container's process UID can be passed via --user
# at compose time to match the host WSL2 user's UID. This is critical
# for the SO_PEERCRED check: peer UID == server UID is enforced inside
# the server process, so the server must run as the user whose socket
# clients will be connecting from.
RUN useradd --create-home --uid 1000 spike

WORKDIR /spike
COPY server-wsl2.py grep_stub.py /spike/

USER spike

# Defaults that compose.yml can override.
ENV OPTIMUS_SOCKET_PATH=/var/optimus/sockets/optimus.sock \
    OPTIMUS_MOUNT_ROOT=/workspace \
    OPTIMUS_CONCURRENCY_CAP=4

CMD ["python3", "-u", "server-wsl2.py"]
