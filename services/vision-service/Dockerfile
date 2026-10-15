# Build from the repository root: docker build -f services/vision-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=false

# libgomp1 is what the OpenCV headless wheels link against.
RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY libs/ ./libs/
COPY services/vision-service/pyproject.toml services/vision-service/README.md ./services/vision-service/
# The dependency layer cannot see src/, so --no-root skips installing the service itself.
RUN cd services/vision-service && poetry install --no-root --without dev --no-interaction --no-ansi

COPY services/vision-service/src/ ./services/vision-service/src/
ENV PYTHONPATH=/app/services/vision-service/src:/app/libs/byb-common/src

RUN useradd --create-home --uid 10005 byb
USER byb

EXPOSE 8005

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8005/healthz || exit 1

CMD ["uvicorn", "byb_vision.main:app", "--host", "0.0.0.0", "--port", "8005"]
