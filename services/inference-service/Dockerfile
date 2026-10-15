# Build from the repository root: docker build -f services/inference-service/Dockerfile .
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
COPY services/inference-service/pyproject.toml services/inference-service/README.md ./services/inference-service/
RUN cd services/inference-service && poetry install --without dev --no-interaction --no-ansi

COPY services/inference-service/src/ ./services/inference-service/src/
ENV PYTHONPATH=/app/services/inference-service/src:/app/libs/byb-common/src

RUN useradd --create-home --uid 10002 byb
USER byb

EXPOSE 8002

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8002/healthz || exit 1

CMD ["uvicorn", "byb_inference.main:app", "--host", "0.0.0.0", "--port", "8002"]
