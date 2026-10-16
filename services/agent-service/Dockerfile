# Build from the repository root: docker build -f services/agent-service/Dockerfile .
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
COPY services/agent-service/pyproject.toml services/agent-service/poetry.lock services/agent-service/README.md ./services/agent-service/
# The dependency layer cannot see src/, so --no-root skips installing the service itself.
RUN cd services/agent-service && poetry install --no-root --without dev --no-interaction --no-ansi

COPY services/agent-service/src/ ./services/agent-service/src/
ENV PYTHONPATH=/app/services/agent-service/src:/app/libs/byb-common/src

RUN useradd --create-home --uid 10007 byb
USER byb

EXPOSE 8007

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8007/healthz || exit 1

CMD ["uvicorn", "byb_agent.main:app", "--host", "0.0.0.0", "--port", "8007"]
