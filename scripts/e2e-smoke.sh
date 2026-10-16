#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

# Native paths: Git Bash `/c/...` is unreadable by a Windows Python, so use `pwd -W`.
ROOT="$(pwd -W 2>/dev/null || pwd)"
# Any Python with the service dependencies works: `PY=$(command -v python) bash scripts/e2e-smoke.sh`
PY="${PY:-$ROOT/.venv-check/Scripts/python.exe}"
[ -x "$PY" ] || PY=python

# PYTHONPATH must be joined with the platform's own path separator: `;` under Git Bash on
# Windows, `:` on Linux/macOS. Using `:` on Windows makes Python see one bogus directory.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) SEP=";" ;;
  *) SEP=":" ;;
esac
SERVICES="api-gateway catalog-service inference-service vision-service geometry-service"
PATHS=""
for service in $SERVICES; do PATHS="${PATHS:+$PATHS$SEP}$ROOT/services/$service/src"; done
export PYTHONPATH="$PATHS${SEP}$ROOT/libs/byb-common/src"

# Ports are overridable because Docker Desktop's dead port proxies can squat on 8001-8006.
GATEWAY_PORT="${GATEWAY_PORT:-8001}"
CATALOG_PORT="${CATALOG_PORT:-8004}"
INFERENCE_PORT="${INFERENCE_PORT:-8002}"
VISION_PORT="${VISION_PORT:-8005}"
GEOMETRY_PORT="${GEOMETRY_PORT:-8003}"

# Postgres is the target database: `docker compose up -d postgres` before running this.
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://user:password@localhost:5432/beforeyoubuy}"
export UPLOAD_DIR="${UPLOAD_DIR:-$ROOT/uploads-e2e}"
mkdir -p "$UPLOAD_DIR"
export INTERNAL_TOKEN=e2e-token
export GATEWAY_URL="http://127.0.0.1:$GATEWAY_PORT"
export CATALOG_URL="http://127.0.0.1:$CATALOG_PORT"
export INFERENCE_URL="http://127.0.0.1:$INFERENCE_PORT"
export VISION_URL="http://127.0.0.1:$VISION_PORT"
export GEOMETRY_URL="http://127.0.0.1:$GEOMETRY_PORT"

rm -f *.svc.log
echo "database: ${DATABASE_URL%%@*}@<redacted>"
"$PY" -m uvicorn byb_gateway.main:app --port "$GATEWAY_PORT" --host 127.0.0.1 >gateway.svc.log 2>&1 &
"$PY" -m uvicorn byb_catalog.main:app --port "$CATALOG_PORT" --host 127.0.0.1 >catalog.svc.log 2>&1 &
"$PY" -m uvicorn byb_inference.main:app --port "$INFERENCE_PORT" --host 127.0.0.1 >inference.svc.log 2>&1 &
"$PY" -m uvicorn byb_vision.main:app --port "$VISION_PORT" --host 127.0.0.1 >vision.svc.log 2>&1 &
"$PY" -m uvicorn byb_geometry.main:app --port "$GEOMETRY_PORT" --host 127.0.0.1 >geometry.svc.log 2>&1 &
PIDS=$(jobs -p)
cleanup() { kill $PIDS 2>/dev/null; wait $PIDS 2>/dev/null; }
trap cleanup EXIT

PORTS="$GATEWAY_PORT $CATALOG_PORT $INFERENCE_PORT $VISION_PORT $GEOMETRY_PORT"
for port in $PORTS; do
  for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:$port/healthz" >/dev/null && break
    sleep 1
  done
done

echo "--- health ---"
for port in $PORTS; do printf "%s " "$port"; curl -s "http://127.0.0.1:$port/healthz"; echo; done

echo "--- POST /api/v1/simulations (link + uploaded room photo) ---"
printf 'fake image bytes' > room-photo.png
RESP=$(curl -s -X POST "http://127.0.0.1:$GATEWAY_PORT/api/v1/simulations" \
  -F "link=https://www.ikea.com/gb/p/billy-bookcase-white-b652fa01/" \
  -F "file=@room-photo.png;type=image/png" \
  -F "room_width_m=4.2" -F "room_depth_m=3.4" -F "room_height_m=2.5" \
  -F "shopper_notes=white bookcase for a small living room")
echo "$RESP"
ID=$(printf '%s' "$RESP" | "$PY" -c "import json,sys;print(json.load(sys.stdin).get('id',''))")
rm -f room-photo.png

echo "--- polling $ID ---"
for i in $(seq 1 25); do
  OUT=$(curl -s "http://127.0.0.1:$GATEWAY_PORT/api/v1/simulations/$ID")
  ST=$(printf '%s' "$OUT" | "$PY" -c "import json,sys;print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo parse-error)
  echo "poll $i: $ST"
  case "$ST" in completed|failed) break ;; esac
  sleep 1
done

echo "--- final payload ---"
echo "$OUT" | "$PY" -m json.tool || echo "$OUT"

echo "--- catalog passthrough ---"
curl -s "http://127.0.0.1:$GATEWAY_PORT/api/v1/catalog" | "$PY" -c 'import json,sys; rows=json.load(sys.stdin); print(len(rows), "skus; first:", rows[0]["sku"])'

echo "--- room scan ---"
# The uploaded bytes are not a photo, so this must say declared: the pipeline degrades, it does not fail.
echo "$OUT" | "$PY" -c 'import json,sys; scan=json.load(sys.stdin).get("room_scan") or {}; print("method:", scan.get("method"), "measured:", scan.get("measured"), "obstacles:", len(scan.get("obstacles") or []), "room:", scan.get("width_m"), "x", scan.get("depth_m"))'
