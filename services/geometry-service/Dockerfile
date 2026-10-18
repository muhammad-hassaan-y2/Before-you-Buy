# Build from the repository root: docker build -f services/geometry-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends curl libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY libs/ ./libs/
COPY services/geometry-service/pyproject.toml services/geometry-service/poetry.lock* services/geometry-service/README.md ./services/geometry-service/
# The dependency layer cannot see src/, so --no-root skips installing the service itself.
RUN cd services/geometry-service && poetry install --no-root --without dev --no-interaction --no-ansi \
    && rm -rf /root/.cache/pypoetry /root/.cache/pip

COPY services/geometry-service/src/ ./services/geometry-service/src/
ENV PYTHONPATH=/app/services/geometry-service/src:/app/libs/byb-common/src

RUN useradd --create-home --uid 10003 byb
USER byb

EXPOSE 8003

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8003/healthz || exit 1

CMD ["uvicorn", "byb_geometry.main:app", "--host", "0.0.0.0", "--port", "8003"]
