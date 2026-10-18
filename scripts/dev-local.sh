#!/usr/bin/env bash
# Run the whole stack on the host, no Docker: SQLite instead of Postgres, direct HTTP between
# services instead of Dapr. Needs `uv` and Node/pnpm. First run creates .venv-local.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
VENV=$ROOT/.venv-local
RUN=$ROOT/.local
mkdir -p "$RUN/logs" "$RUN/uploads"

if [ ! -x "$VENV/bin/python" ]; then
  uv venv --python 3.12 "$VENV"
  for d in libs/byb-common services/*/; do uv pip install -q --python "$VENV/bin/python" -e "$d"; done
fi
[ -d frontend/node_modules ] || (cd frontend && pnpm install)

export INTERNAL_TOKEN=${INTERNAL_TOKEN:-dev-internal-token}
export DATABASE_URL="sqlite:///$RUN/byb.db"
export UPLOAD_DIR="$RUN/uploads"
export ALLOWED_ORIGINS="http://localhost:3000"
export AGENT_ALLOWED_ORIGINS="http://localhost:3000"
unset DAPR_HTTP_ENDPOINT || true

pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

start() { # name module port
  (cd "services/$1" && exec "$VENV/bin/uvicorn" "$2:app" --host 127.0.0.1 --port "$3") >"$RUN/logs/$1.log" 2>&1 &
  pids+=($!); echo "started $1 on :$3"
}
start api-gateway byb_gateway.main 8001
start inference-service byb_inference.main 8002
start geometry-service byb_geometry.main 8003
start catalog-service byb_catalog.main 8004
start vision-service byb_vision.main 8005
start scene-service byb_scene.main 8006
start agent-service byb_agent.main 8007

(cd frontend && exec pnpm dev -p 3000) >"$RUN/logs/frontend.log" 2>&1 &
pids+=($!); echo "started frontend on :3000 — logs in .local/logs"
wait
