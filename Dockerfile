# SocioSim — reproducible research image (research use only).
# Default CMD runs a deterministic CLI simulation. The web console binds
# 127.0.0.1 (single-user research tool); to use it from a container run with
#   docker run --rm -p 8765:8765 -e SOCIOSIM_ACCESS_TOKEN=change-me \
#     -e SOCIOSIM_ALLOWED_HOSTS=127.0.0.1,localhost sociosim \
#     python run.py --web --no-open --bind 0.0.0.0
# (binding 0.0.0.0 exposes the console; use only behind trusted network controls).
FROM python:3.11-slim@sha256:b27df5841f3355e9473f9a516d38a6783b6c8dfeacaf2d14a240f443b368ddb6

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY socio_sim ./socio_sim
COPY run.py ./
RUN pip install -e .
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

# SBOM release artifact:
#   syft packages dir:. -o spdx-json > sbom.spdx.json

# Deterministic, network-free default run (template content mode).
CMD ["python", "run.py", "--profile", "quick"]
