# SocioSim — reproducible research image (research use only).
# Default CMD runs a deterministic CLI simulation. The web console binds
# 127.0.0.1 (single-user research tool); to use it from a container run with
#   docker run --rm -p 8765:8765 -e SOCIOSIM_ACCESS_TOKEN=change-me \
#     -e SOCIOSIM_ALLOWED_HOSTS=127.0.0.1,localhost sociosim \
#     python run.py --web --no-open --bind 0.0.0.0
# (binding 0.0.0.0 exposes the console; use only behind trusted network controls).
#
# PINNED BASE IMAGE — update the digest when bumping the base:
#   docker pull python:3.11-slim
#   docker inspect python:3.11-slim --format='{{index .RepoDigests 0}}'
#
# SBOM generation (run after building the image):
#   syft sociosim -o spdx-json > sociosim.sbom.spdx.json
#   grype sbom:sociosim.sbom.spdx.json  # vulnerability scan of image contents
FROM python:3.11-slim@sha256:cdbd05fb6f457ca275ff51ce00d93d865ca0b6a25f5ffb08262d94f6835771e5

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY socio_sim ./socio_sim
COPY run.py ./
RUN pip install -e .

# Drop root: create an unprivileged user and run as it.
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

# Liveness probe for WEB mode (python run.py --web --bind 0.0.0.0): succeeds
# while the console port is accepting connections. The default one-shot CLI run
# exits before the probe is ever evaluated, so this is a no-op for CLI use.
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8765), 3).close()"]

# Deterministic, network-free default run (template content mode).
CMD ["python", "run.py", "--profile", "quick"]
