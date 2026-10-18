# Build from the repository root: docker build -f services/catalog-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY libs/ ./libs/
COPY services/catalog-service/pyproject.toml services/catalog-service/poetry.lock* services/catalog-service/README.md ./services/catalog-service/
# The dependency layer cannot see src/, so --no-root skips installing the service itself.
RUN cd services/catalog-service && poetry install --no-root --without dev --no-interaction --no-ansi \
    && rm -rf /root/.cache/pypoetry /root/.cache/pip

COPY services/catalog-service/src/ ./services/catalog-service/src/
ENV PYTHONPATH=/app/services/catalog-service/src:/app/libs/byb-common/src

RUN useradd --create-home --uid 10004 byb
USER byb

EXPOSE 8004

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8004/healthz || exit 1

CMD ["uvicorn", "byb_catalog.main:app", "--host", "0.0.0.0", "--port", "8004"]
