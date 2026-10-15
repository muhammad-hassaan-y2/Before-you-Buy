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
export PYTHONPATH="$ROOT/services/api-gateway/src${SEP}$ROOT/services/inference-service/src${SEP}$ROOT/services/geometry-service/src${SEP}$ROOT/libs/byb-common/src"

# Postgres is the target database: `docker compose up -d postgres` before running this.
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://user:password@localhost:5432/beforeyoubuy}"
export UPLOAD_DIR="${UPLOAD_DIR:-$ROOT/uploads-e2e}"
mkdir -p "$UPLOAD_DIR"
export INTERNAL_TOKEN=e2e-token
export GATEWAY_URL=http://127.0.0.1:8001
export INFERENCE_URL=http://127.0.0.1:8002
export GEOMETRY_URL=http://127.0.0.1:8003

rm -f *.svc.log
echo "database: ${DATABASE_URL%%@*}@<redacted>"
"$PY" -m uvicorn byb_gateway.main:app --port 8001 --host 127.0.0.1 >gateway.svc.log 2>&1 &
"$PY" -m uvicorn byb_inference.main:app --port 8002 --host 127.0.0.1 >inference.svc.log 2>&1 &
"$PY" -m uvicorn byb_geometry.main:app --port 8003 --host 127.0.0.1 >geometry.svc.log 2>&1 &
PIDS=$(jobs -p)
cleanup() { kill $PIDS 2>/dev/null; wait $PIDS 2>/dev/null; }
trap cleanup EXIT

for port in 8001 8002 8003; do
  for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:$port/healthz" >/dev/null && break
    sleep 1
  done
done

echo "--- health ---"
for port in 8001 8002 8003; do printf "%s " "$port"; curl -s "http://127.0.0.1:$port/healthz"; echo; done

echo "--- POST /api/v1/simulations (link + uploaded room photo) ---"
printf 'fake image bytes' > room-photo.png
RESP=$(curl -s -X POST http://127.0.0.1:8001/api/v1/simulations \
  -F "link=https://www.example.com/linen-sofa" \
  -F "file=@room-photo.png;type=image/png" \
  -F "room_width_m=4.2" -F "room_depth_m=3.4" -F "room_height_m=2.5" \
  -F "shopper_notes=three-seater linen sofa for a small living room")
echo "$RESP"
ID=$(printf '%s' "$RESP" | "$PY" -c "import json,sys;print(json.load(sys.stdin).get('id',''))")
rm -f room-photo.png

echo "--- polling $ID ---"
for i in $(seq 1 25); do
  OUT=$(curl -s "http://127.0.0.1:8001/api/v1/simulations/$ID")
  ST=$(printf '%s' "$OUT" | "$PY" -c "import json,sys;print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo parse-error)
  echo "poll $i: $ST"
  case "$ST" in completed|failed) break ;; esac
  sleep 1
done

echo "--- final payload ---"
echo "$OUT" | "$PY" -m json.tool
echo "--- uploads stored ---"
ls -1 uploads-e2e 2>/dev/null | head -3
