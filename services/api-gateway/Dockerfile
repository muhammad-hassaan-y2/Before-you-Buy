# Build from the repository root so the shared library is available:
#   docker build -f services/api-gateway/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Dependencies first: this layer only rebuilds when a manifest changes.
COPY libs/ ./libs/
COPY services/api-gateway/pyproject.toml services/api-gateway/README.md ./services/api-gateway/
RUN cd services/api-gateway && poetry install --without dev --no-interaction --no-ansi

COPY services/api-gateway/src/ ./services/api-gateway/src/
ENV PYTHONPATH=/app/services/api-gateway/src:/app/libs/byb-common/src

RUN useradd --create-home --uid 10001 byb
USER byb

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8001/healthz || exit 1

CMD ["uvicorn", "byb_gateway.main:app", "--host", "0.0.0.0", "--port", "8001"]
